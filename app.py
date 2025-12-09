"""
Flask应用主文件
"""
from flask import Flask, request, jsonify
from models_v2 import db, Question, AnswerVersion, UserSession, DailyActiveUser
from question_service_v2 import QuestionService
import os
import sys
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import uuid
import logging
import json
import base64

# 配置日志（在Flask app创建前配置）
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    force=True  # 强制重新配置
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# 加载环境变量（处理编码错误）
env_loaded = False
try:
    load_dotenv()
    env_loaded = True
except UnicodeDecodeError as e:
    # 如果.env文件编码有问题，尝试使用latin-1编码
    logger.warning(f"加载.env文件时出现编码错误: {e}，尝试修复...")
    import io
    try:
        with open('.env', 'r', encoding='latin-1') as f:
            content = f.read()
        # 重新写入为UTF-8
        with open('.env', 'w', encoding='utf-8') as f:
            f.write(content)
        load_dotenv()
        env_loaded = True
    except Exception as e2:
        logger.warning(f"无法修复.env文件: {e2}，将使用环境变量或默认值")
        # 如果修复失败，删除有问题的DATABASE_URL
        try:
            with open('.env', 'r', encoding='latin-1') as f:
                lines = f.readlines()
            # 过滤掉DATABASE_URL行
            filtered_lines = [line for line in lines if not line.strip().startswith('DATABASE_URL')]
            with open('.env', 'w', encoding='utf-8') as f:
                f.writelines(filtered_lines)
            logger.info("已从.env文件中移除有问题的DATABASE_URL行")
        except:
            pass
except Exception as e:
    logger.warning(f"加载.env文件时出错: {e}，将使用环境变量或默认值")

app = Flask(__name__)

# 配置Flask的日志
app.logger.setLevel(logging.DEBUG)
werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.setLevel(logging.INFO)  # Werkzeug日志设为INFO，减少噪音

# 数据库配置 - 支持多级回退：PostgreSQL -> SQLite -> MySQL
# 安全地读取DATABASE_URL，如果出现编码错误则使用备选方案
database_url = None
database_type = None  # 'postgresql', 'sqlite', 'mysql'

try:
    database_url = os.getenv('DATABASE_URL')
    # 如果读取成功，尝试验证编码
    if database_url:
        # 安全地处理可能的编码问题
        try:
            # 如果database_url是bytes类型，先解码
            if isinstance(database_url, bytes):
                database_url = database_url.decode('utf-8', errors='ignore')
            
            # 尝试编码为UTF-8，如果失败说明有编码问题
            database_url.encode('utf-8')
            
            # 如果是PostgreSQL URL，检查是否包含非ASCII字符
            if 'postgres' in database_url.lower():
                database_url.encode('ascii')  # PostgreSQL URL应该只包含ASCII字符
                database_type = 'postgresql'
            elif 'mysql' in database_url.lower():
                database_type = 'mysql'
            else:
                database_type = 'sqlite'
        except (UnicodeDecodeError, UnicodeEncodeError, AttributeError) as encoding_err:
            logger.warning(f"DATABASE_URL编码验证失败: {encoding_err}，将使用SQLite")
            database_url = None
except (UnicodeDecodeError, UnicodeEncodeError, AttributeError) as e:
    logger.warning(f"读取DATABASE_URL时出现编码错误: {e}，将使用备选数据库")
    # 删除有问题的环境变量
    if 'DATABASE_URL' in os.environ:
        del os.environ['DATABASE_URL']
    database_url = None
except Exception as e:
    logger.warning(f"读取DATABASE_URL时出现其他错误: {e}，将使用备选数据库")
    database_url = None

if not database_url:
    # 如果没有配置，按优先级尝试：SQLite -> MySQL
    # 首先尝试SQLite（最简单，无需配置）
    database_url = 'sqlite:///gongkao_test.db'
    database_type = 'sqlite'
    print("⚠️ 未配置DATABASE_URL，使用SQLite测试数据库: gongkao_test.db")
    print("   生产环境请配置Supabase数据库或MySQL数据库")
else:
    # 检查并清理数据库URL（处理编码问题）
    original_url = database_url
    try:
        # 如果URL包含无效字符，尝试修复
        if isinstance(database_url, bytes):
            database_url = database_url.decode('utf-8', errors='ignore')
        # 移除可能的BOM或其他无效字符
        database_url = database_url.strip().strip('\ufeff')
        
        # 检查URL是否包含无效字符（编码错误）
        database_url.encode('utf-8')
        
        # 尝试测试连接（不实际连接，只检查URL格式）
        if 'postgres' in database_url.lower():
            # 对于PostgreSQL，检查URL格式是否正确
            # 如果包含非ASCII字符，可能是编码问题
            try:
                # 尝试解析URL
                database_url.encode('ascii')
            except UnicodeEncodeError:
                # 包含非ASCII字符，可能是编码问题
                raise UnicodeDecodeError('utf-8', original_url.encode('latin-1') if isinstance(original_url, str) else original_url, 0, 1, 'invalid start byte')
    except (UnicodeDecodeError, UnicodeEncodeError) as e:
        logger.warning(f"数据库URL编码错误: {e}，使用SQLite")
        database_url = 'sqlite:///gongkao_test.db'
        use_sqlite = True
    except Exception as e:
        logger.warning(f"数据库URL处理失败: {e}，使用SQLite")
        database_url = 'sqlite:///gongkao_test.db'
        use_sqlite = True

# 如果Supabase连接字符串是postgres://开头，需要转换为postgresql://
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

# 标记是否已经回退到SQLite
_db_fallback_to_sqlite = False

# 安全地设置数据库URL并初始化
try:
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # 根据数据库类型配置连接池（支持高并发批量处理）
    if 'sqlite' in database_url.lower():
        # SQLite 连接池配置（SQLite 对并发支持有限，但可以增加连接数）
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_pre_ping': True,
            'pool_recycle': 300,
            'pool_size': 20,          # SQLite 支持更多连接
            'max_overflow': 30,       # 溢出连接数
            'pool_timeout': 30,       # 连接超时时间
            'connect_args': {
                'check_same_thread': False,  # 允许多线程访问
                'timeout': 30                # SQLite 连接超时
            }
        }
    else:
        # PostgreSQL/MySQL 连接池配置（支持高并发）
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_pre_ping': True,    # 检查连接是否有效
            'pool_recycle': 300,      # 回收连接时间（秒）
            'pool_size': 20,          # 连接池大小（默认5不够，增加到20）
            'max_overflow': 30,       # 最大溢出连接数（默认10不够，增加到30）
            'pool_timeout': 30,       # 获取连接的超时时间（秒）
        }
    
    # 初始化数据库
    db.init_app(app)
except Exception as init_error:
    # 如果初始化时出现编码错误，回退到SQLite
    error_msg = str(init_error)
    if 'codec' in error_msg.lower() or 'decode' in error_msg.lower() or 'utf-8' in error_msg.lower():
        logger.warning(f"数据库初始化时出现编码错误: {init_error}，回退到SQLite")
        database_url = 'sqlite:///gongkao_test.db'
        database_type = 'sqlite'
        app.config['SQLALCHEMY_DATABASE_URI'] = database_url
        # 更新连接池配置为SQLite配置
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_pre_ping': True,
            'pool_recycle': 300,
            'pool_size': 20,
            'max_overflow': 30,
            'pool_timeout': 30,
            'connect_args': {
                'check_same_thread': False,
                'timeout': 30
            }
        }
        db.init_app(app)
        _db_fallback_to_sqlite = True
    else:
        # 其他错误，重新抛出
        raise

# 测试数据库连接（在app_context中）
def test_database_connection():
    """测试数据库连接，如果失败则回退到SQLite"""
    try:
        with app.app_context():
            db.engine.connect()
        logger.info("✅ 数据库连接成功！")
        return True
    except (UnicodeDecodeError, UnicodeEncodeError) as e:
        logger.error(f"❌ 数据库连接编码错误：{e}")
        if not use_sqlite:
            logger.warning("⚠️ 回退到SQLite数据库")
            app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///gongkao_test.db'
            try:
                with app.app_context():
                    db.engine.connect()
                logger.info("✅ SQLite数据库连接成功！")
                return True
            except Exception as e2:
                logger.error(f"❌ SQLite数据库连接也失败：{e2}")
                return False
        return False
    except Exception as e:
        logger.error(f"❌ 数据库连接失败：{e}")
        if not use_sqlite:
            logger.warning("⚠️ 回退到SQLite数据库")
            app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///gongkao_test.db'
            try:
                with app.app_context():
                    db.engine.connect()
                logger.info("✅ SQLite数据库连接成功！")
                return True
            except Exception as e2:
                logger.error(f"❌ SQLite数据库连接也失败：{e2}")
                return False
        return False

# 在启动时测试连接（延迟到if __name__ == '__main__'中）

# 初始化题目服务
question_service = QuestionService()

# 初始化用户统计服务
from user_statistics_service import get_user_statistics_service
user_statistics_service = get_user_statistics_service()

# 文件上传配置
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# APK文件配置
APK_FOLDER = 'apk'
os.makedirs(APK_FOLDER, exist_ok=True)
APK_VERSION_FILE = os.path.join(APK_FOLDER, 'version.json')  # 存储APK版本信息

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _check_version_update(client_version, server_version):
    """
    检查客户端版本是否需要更新
    
    Args:
        client_version: 客户端版本号（如 "1.0.0"）
        server_version: 服务端版本号（如 "2.0.0"）
        
    Returns:
        dict: 更新信息
    """
    import json
    
    # 默认更新信息
    update_info = {
        'required': False,
        'latest_version': server_version,
        'download_url': '/api/apk/download',
        'release_notes': ''
    }
    
    # 如果没有提供客户端版本，不检查更新
    if not client_version:
        return update_info
    
    # 读取APK版本信息（如果存在）
    apk_info = {}
    if os.path.exists(APK_VERSION_FILE):
        try:
            with open(APK_VERSION_FILE, 'r', encoding='utf-8') as f:
                apk_info = json.load(f)
                if 'version' in apk_info:
                    update_info['latest_version'] = apk_info['version']
                if 'release_notes' in apk_info:
                    update_info['release_notes'] = apk_info['release_notes']
        except Exception as e:
            logger.warning(f"[API] 读取APK版本信息失败: {e}")
    
    # 简单的版本比较（支持语义化版本号 x.y.z）
    try:
        client_parts = [int(x) for x in client_version.split('.')]
        server_parts = [int(x) for x in update_info['latest_version'].split('.')]
        
        # 补齐版本号长度
        max_len = max(len(client_parts), len(server_parts))
        client_parts.extend([0] * (max_len - len(client_parts)))
        server_parts.extend([0] * (max_len - len(server_parts)))
        
        # 比较版本号
        for i in range(max_len):
            if server_parts[i] > client_parts[i]:
                update_info['required'] = True
                break
            elif server_parts[i] < client_parts[i]:
                break
    except Exception as e:
        logger.warning(f"[API] 版本号比较失败: {e}，假设需要更新")
        # 如果版本号格式不正确，假设需要更新
        if client_version != update_info['latest_version']:
            update_info['required'] = True
    
    return update_info


@app.route('/api/questions/analyze', methods=['POST'])
def analyze_question():
    """
    题目内容分析接口（只返回题目内容，不返回答案和解析）
    
    请求格式：multipart/form-data
    参数：
    - image: 图片文件（必需）
    - raw_text: 前端OCR原始文本（可选）
    - question_text: 前端提取的题干（可选，可能不准确）
    - options: 前端提取的选项（可选，JSON字符串或数组）
    - question_type: 题目类型（可选，默认"TEXT"）
    - force_reanalyze: 是否强制重新分析（可选，默认false）
    
    返回：只包含题目内容（题干、选项），不包含答案和解析
    流程：
    1. 利用前端提供的数据进行快速去重检查（缓存）
    2. 如果找到重复题且不强制重新分析，直接返回缓存
    3. 否则使用火山引擎OCR提取题目内容，存入数据库并返回
    """
    try:
        logger.info("=" * 60)
        logger.info("[API] ========== 收到题目分析请求 ==========")
        
        # 检查必需参数
        if 'image' not in request.files:
            logger.warning("[API] ❌ 缺少图片文件")
            return jsonify({'error': '缺少图片文件', 'code': 400}), 400
        
        image_file = request.files['image']
        if image_file.filename == '':
            logger.warning("[API] ❌ 图片文件为空")
            return jsonify({'error': '图片文件为空', 'code': 400}), 400
        
        # 获取前端OCR数据
        raw_text = request.form.get('raw_text', '').strip()
        question_text = request.form.get('question_text', '').strip()
        options_str = request.form.get('options', '')
        question_type = request.form.get('question_type', 'TEXT').strip()
        force_reanalyze = request.form.get('force_reanalyze', 'false').lower() == 'true'
        
        # 解析options（可能是JSON字符串）
        options = []
        if options_str:
            try:
                if isinstance(options_str, str):
                    options = json.loads(options_str) if options_str.startswith('[') else [options_str]
                else:
                    options = options_str if isinstance(options_str, list) else []
            except json.JSONDecodeError:
                logger.warning(f"[API] ⚠️ 无法解析options JSON: {options_str}")
                options = []
        
        logger.info(f"[API] 📝 请求参数:")
        logger.info(f"[API]    - 图片文件名: {image_file.filename}")
        logger.info(f"[API]    - 图片大小: {len(image_file.read())} bytes")
        image_file.seek(0)  # 重置文件指针
        
        if raw_text:
            logger.info(f"[API]    - 前端OCR原始文本: {raw_text[:100]}...")
        if question_text:
            logger.info(f"[API]    - 前端提取题干: {question_text[:100]}...")
        if options:
            logger.info(f"[API]    - 前端提取选项数: {len(options)}")
        logger.info(f"[API]    - 题目类型: {question_type}")
        logger.info(f"[API]    - 强制重新分析: {force_reanalyze}")
        
        logger.info(f"[API] 🔍 开始分析题目（优化流程）...")
        
        # 调用题目服务
        result = question_service.analyze_question_from_image(
            image_file=image_file,
            frontend_raw_text=raw_text if raw_text else None,
            frontend_question_text=question_text if question_text else None,
            frontend_options=options if options else None,
            question_type=question_type,
            force_reanalyze=force_reanalyze
        )
        
        logger.info(f"[API] ✅ 题目内容分析完成!")
        logger.info(f"[API]    - 题目ID: {result.get('id')}")
        logger.info(f"[API]    - 题干: {result.get('question_text', '')[:100]}...")
        logger.info(f"[API]    - 选项数: {len(result.get('options', []))}")
        logger.info(f"[API]    - OCR置信度: {result.get('ocr_confidence')}")
        logger.info(f"[API]    - 来自缓存: {result.get('from_cache', False)}")
        logger.info(f"[API]    - 是重复题: {result.get('is_duplicate', False)}")
        logger.info(f"[API]    - 存入数据库: {result.get('saved_to_db', False)}")
        if result.get('similarity_score'):
            logger.info(f"[API]    - 相似度分数: {result.get('similarity_score'):.3f}")
        if result.get('matched_question_id'):
            logger.info(f"[API]    - 匹配题目ID: {result.get('matched_question_id')}")
        logger.info(f"[API] ==========================================")
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"[API] ❌ 接口出错: {e}", exc_info=True)
        return jsonify({
            'error': str(e),
            'code': 500
        }), 500


@app.route('/api/questions/analyze/batch', methods=['POST'])
def analyze_questions_batch():
    """
    批量题目内容分析接口
    
    支持两种请求格式：
    1. multipart/form-data（推荐用于文件上传）
    2. application/json（推荐用于base64编码的图片）
    
    请求参数（multipart/form-data）：
    - images[]: 多个图片文件（必需）
    - raw_texts[]: 对应的原始文本数组（JSON字符串，可选）
    - question_texts[]: 对应的题干数组（JSON字符串，可选）
    - options_array[]: 对应的选项数组（JSON字符串数组的JSON字符串，可选）
    - question_types[]: 对应的题目类型数组（JSON字符串，可选）
    - force_reanalyze: 布尔值，统一应用到所有题目（可选，默认false）
    
    请求参数（application/json）：
    {
        "questions": [
            {
                "image": "base64编码的图片数据",
                "raw_text": "OCR原始文本（可选）",
                "question_text": "题干（可选）",
                "options": ["A. ...", "B. ..."]（可选）,
                "question_type": "TEXT"（可选）,
                "force_reanalyze": false（可选）
            }
        ]
    }
    
    返回：
    {
        "results": [
            {
                "success": true,
                "question": {...},
                "error": null
            },
            {
                "success": false,
                "question": null,
                "error": {
                    "code": 400,
                    "message": "错误信息"
                }
            }
        ],
        "total": 2,
        "success_count": 1,
        "failed_count": 1
    }
    
    注意事项：
    - 建议单次请求不超过 20 个题目
    - 批量处理可能需要较长时间，建议超时时间设置为 60 秒
    - 部分题目失败不影响其他题目的处理
    """
    try:
        logger.info("=" * 60)
        logger.info("[API] ========== 收到批量题目分析请求 ==========")
        
        # 批量大小限制
        MAX_BATCH_SIZE = 20
        
        # 判断请求格式
        content_type = request.content_type or ''
        is_json = 'application/json' in content_type
        
        results = []
        questions_data = []
        
        if is_json:
            # JSON 格式
            logger.info("[API] 📦 请求格式: application/json")
            data = request.get_json()
            
            if not data or 'questions' not in data:
                logger.warning("[API] ❌ JSON格式错误：缺少questions字段")
                return jsonify({
                    'error': '请求格式错误：缺少questions字段',
                    'code': 400
                }), 400
            
            questions_list = data.get('questions', [])
            if not isinstance(questions_list, list) or len(questions_list) == 0:
                logger.warning("[API] ❌ questions必须是非空数组")
                return jsonify({
                    'error': 'questions必须是非空数组',
                    'code': 400
                }), 400
            
            if len(questions_list) > MAX_BATCH_SIZE:
                logger.warning(f"[API] ❌ 批量大小超过限制: {len(questions_list)} > {MAX_BATCH_SIZE}")
                return jsonify({
                    'error': f'批量大小超过限制，最多支持{MAX_BATCH_SIZE}个题目',
                    'code': 400
                }), 400
            
            logger.info(f"[API] 📊 批量大小: {len(questions_list)}")
            
            # 解析JSON格式的题目数据
            for idx, q_data in enumerate(questions_list):
                if 'image' not in q_data:
                    logger.warning(f"[API] ⚠️ 题目{idx+1}缺少image字段")
                    results.append({
                        'success': False,
                        'question': None,
                        'error': {
                            'code': 400,
                            'message': f'题目{idx+1}缺少image字段'
                        }
                    })
                    continue
                
                # 解码base64图片
                try:
                    image_base64 = q_data['image']
                    if not image_base64 or not isinstance(image_base64, str):
                        raise ValueError(f"图片数据无效: type={type(image_base64)}")
                    
                    # 移除data:image/xxx;base64,前缀（如果有）
                    if ',' in image_base64:
                        image_base64 = image_base64.split(',', 1)[1]
                    
                    logger.info(f"[API] 📷 题目{idx+1}开始解码图片，base64长度: {len(image_base64)}")
                    image_data = base64.b64decode(image_base64)
                    logger.info(f"[API] ✅ 题目{idx+1}图片解码成功，图片大小: {len(image_data)} bytes")
                    
                    # 创建文件对象
                    from io import BytesIO
                    image_file = BytesIO(image_data)
                    image_file.name = f'question_{idx+1}.png'  # 设置文件名
                    
                    questions_data.append({
                        'image_file': image_file,
                        'raw_text': q_data.get('raw_text', '').strip() or None,
                        'question_text': q_data.get('question_text', '').strip() or None,
                        'options': q_data.get('options', []),
                        'question_type': q_data.get('question_type', 'TEXT').strip(),
                        'force_reanalyze': q_data.get('force_reanalyze', False)
                    })
                    logger.info(f"[API] ✅ 题目{idx+1}已添加到处理队列")
                except Exception as e:
                    logger.error(f"[API] ❌ 题目{idx+1}图片解码失败: {e}", exc_info=True)
                    results.append({
                        'success': False,
                        'question': None,
                        'error': {
                            'code': 400,
                            'message': f'图片解码失败: {str(e)}'
                        }
                    })
            
            logger.info(f"[API] 📋 成功解析 {len(questions_data)} 个题目数据，失败 {len(results)} 个")
        
        else:
            # multipart/form-data 格式
            logger.info("[API] 📦 请求格式: multipart/form-data")
            
            # 获取图片文件列表
            if 'images[]' in request.files:
                image_files = request.files.getlist('images[]')
            elif 'images' in request.files:
                image_files = [request.files['images']]
            else:
                logger.warning("[API] ❌ 缺少图片文件")
                return jsonify({
                    'error': '缺少图片文件（images[]或images）',
                    'code': 400
                }), 400
            
            if len(image_files) == 0 or all(f.filename == '' for f in image_files):
                logger.warning("[API] ❌ 图片文件为空")
                return jsonify({
                    'error': '图片文件为空',
                    'code': 400
                }), 400
            
            if len(image_files) > MAX_BATCH_SIZE:
                logger.warning(f"[API] ❌ 批量大小超过限制: {len(image_files)} > {MAX_BATCH_SIZE}")
                return jsonify({
                    'error': f'批量大小超过限制，最多支持{MAX_BATCH_SIZE}个题目',
                    'code': 400
                }), 400
            
            logger.info(f"[API] 📊 批量大小: {len(image_files)}")
            
            # 获取其他参数（数组格式）
            raw_texts_str = request.form.get('raw_texts[]', '[]')
            question_texts_str = request.form.get('question_texts[]', '[]')
            options_array_str = request.form.get('options_array[]', '[]')
            question_types_str = request.form.get('question_types[]', '[]')
            force_reanalyze = request.form.get('force_reanalyze', 'false').lower() == 'true'
            
            # 解析JSON数组
            try:
                raw_texts = json.loads(raw_texts_str) if raw_texts_str else []
                question_texts = json.loads(question_texts_str) if question_texts_str else []
                options_array = json.loads(options_array_str) if options_array_str else []
                question_types = json.loads(question_types_str) if question_types_str else []
            except json.JSONDecodeError as e:
                logger.warning(f"[API] ⚠️ 无法解析参数JSON: {e}")
                raw_texts = []
                question_texts = []
                options_array = []
                question_types = []
            
            # 确保数组长度一致
            max_len = len(image_files)
            raw_texts = (raw_texts + [''] * max_len)[:max_len]
            question_texts = (question_texts + [''] * max_len)[:max_len]
            options_array = (options_array + [[]] * max_len)[:max_len]
            question_types = (question_types + ['TEXT'] * max_len)[:max_len]
            
            # 构建题目数据列表
            for idx, image_file in enumerate(image_files):
                if image_file.filename == '':
                    continue
                
                questions_data.append({
                    'image_file': image_file,
                    'raw_text': raw_texts[idx].strip() if raw_texts[idx] else None,
                    'question_text': question_texts[idx].strip() if question_texts[idx] else None,
                    'options': options_array[idx] if options_array[idx] else None,
                    'question_type': question_types[idx].strip() if question_types[idx] else 'TEXT',
                    'force_reanalyze': force_reanalyze
                })
        
        # 批量处理题目（并行处理以提高效率）
        MAX_WORKERS = 3  # 最大并发数，降低以提高稳定性（3个并发平衡速度和稳定性）
        logger.info(f"[API] 🔍 开始批量处理 {len(questions_data)} 个题目（并发数: {MAX_WORKERS}）...")
        
        def process_single_question(q_data, idx):
            """处理单个题目（线程安全）"""
            try:
                logger.info(f"[API] 📝 处理题目 {idx+1}/{len(questions_data)}")
                
                # 调用题目服务
                result = question_service.analyze_question_from_image(
                    image_file=q_data['image_file'],
                    frontend_raw_text=q_data['raw_text'],
                    frontend_question_text=q_data['question_text'],
                    frontend_options=q_data['options'],
                    question_type=q_data['question_type'],
                    force_reanalyze=q_data['force_reanalyze']
                )
                
                logger.info(f"[API] ✅ 题目 {idx+1} 处理成功")
                return {
                    'success': True,
                    'question': result,
                    'error': None,
                    'index': idx
                }
            except Exception as e:
                logger.error(f"[API] ❌ 题目 {idx+1} 处理失败: {e}", exc_info=True)
                return {
                    'success': False,
                    'question': None,
                    'error': {
                        'code': 500,
                        'message': str(e)
                    },
                    'index': idx
                }
        
        # 并行处理（如果只有1张图片，直接处理，避免线程开销）
        if len(questions_data) == 1:
            result = process_single_question(questions_data[0], 0)
            results = [result]
        else:
            # 使用线程池并行处理
            from concurrent.futures import ThreadPoolExecutor, as_completed
            
            results = [None] * len(questions_data)
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                # 提交所有任务
                future_to_idx = {
                    executor.submit(process_single_question, q_data, idx): idx
                    for idx, q_data in enumerate(questions_data)
                }
                
                # 收集结果（保持原始顺序）
                for future in as_completed(future_to_idx):
                    result = future.result()
                    results[result['index']] = result
            
            # 移除index字段，保持响应格式一致
            for r in results:
                if 'index' in r:
                    del r['index']
        
        # 统计结果
        total = len(results)
        success_count = sum(1 for r in results if r['success'])
        failed_count = total - success_count
        
        logger.info(f"[API] ✅ 批量处理完成!")
        logger.info(f"[API]    - 总数: {total}")
        logger.info(f"[API]    - 成功: {success_count}")
        logger.info(f"[API]    - 失败: {failed_count}")
        logger.info(f"[API] ==========================================")
        
        return jsonify({
            'results': results,
            'total': total,
            'success_count': success_count,
            'failed_count': failed_count
        })
    
    except Exception as e:
        logger.error(f"[API] ❌ 批量接口出错: {e}", exc_info=True)
        return jsonify({
            'error': str(e),
            'code': 500
        }), 500


@app.route('/api/questions/extract/batch', methods=['POST'])
def extract_questions_batch():
    """
    快速批量提取题目和选项接口（使用本地OCR + DeepSeek，高并发）
    
    特点：
    - 使用本地OCR（免费、快速）
    - 使用DeepSeek提取（费用最低 ¥0.000117/次，准确率1.00）
    - 高并发处理（默认10个并发，50题约2-3分钟）
    - 每道题独立请求（错误隔离好）
    
    请求格式1（multipart/form-data）：
    - images[]: 多个图片文件（必需）
    - max_workers: 并发数（可选，默认10，范围3-20）
    
    请求格式2（application/json）：
    {
        "images": [
            {"filename": "image1.jpg", "data": "base64编码的图片数据"},
            ...
        ],
        "max_workers": 10  // 可选，默认10
    }
    
    返回：
    {
        "success": true,
        "results": [
            {
                "success": true,
                "question_text": "完整的题干内容",
                "options": ["A. 选项A", "B. 选项B", "C. 选项C", "D. 选项D"],
                "raw_text": "OCR原始文本",
                "ocr_time": 6.5,
                "ai_time": 7.2,
                "total_time": 13.7,
                "input_tokens": 345,
                "output_tokens": 197,
                "total_tokens": 542,
                "cost": 0.000117
            }
        ],
        "statistics": {
            "total": 50,
            "success_count": 48,
            "failed_count": 2,
            "total_time": 150.5,
            "avg_time_per_question": 3.14,
            "total_cost": 0.005616
        }
    }
    
    性能：
    - 并发10：50题约2-3分钟
    - 并发20：50题约1-2分钟
    """
    try:
        logger.info("=" * 60)
        logger.info("[API] ========== 收到批量提取请求（本地OCR+DeepSeek）==========")
        
        # 导入批量处理服务
        from batch_question_service import process_batch_concurrent
        
        # 批量大小限制
        MAX_BATCH_SIZE = 100
        MAX_WORKERS_DEFAULT = 10
        MAX_WORKERS_MAX = 20
        
        # 判断请求格式
        content_type = request.content_type or ''
        is_json = 'application/json' in content_type
        
        logger.info(f"[API] Content-Type: {content_type}")
        
        image_files = []
        
        if is_json:
            # JSON格式
            logger.info("[API] 📦 请求格式: application/json")
            
            # 解析JSON数据，处理可能的解析错误
            try:
                data = request.get_json(force=True)  # force=True确保即使Content-Type不对也尝试解析
                logger.info(f"[API] JSON解析成功，数据keys: {list(data.keys()) if isinstance(data, dict) else 'not a dict'}")
            except Exception as e:
                logger.error(f"[API] ❌ JSON解析失败: {e}", exc_info=True)
                return jsonify({
                    'success': False,
                    'error': f'JSON格式错误: {str(e)}',
                    'code': 400
                }), 400
            
            if not data:
                logger.error("[API] ❌ 请求体为空或无法解析为JSON")
                logger.error(f"[API] 请求数据: {request.data[:200] if request.data else 'None'}...")
                return jsonify({
                    'success': False,
                    'error': '请求体为空或不是有效的JSON格式',
                    'code': 400
                }), 400
            
            if 'images' not in data:
                logger.error(f"[API] ❌ 缺少images字段，请求数据keys: {list(data.keys()) if isinstance(data, dict) else 'not a dict'}")
                return jsonify({
                    'success': False,
                    'error': '请求格式错误：缺少images字段',
                    'code': 400
                }), 400
            
            images_data = data.get('images', [])
            
            # 添加详细的调试日志
            logger.info(f"[API] 📊 images_data类型: {type(images_data).__name__}")
            logger.info(f"[API] 📊 images_data长度: {len(images_data) if isinstance(images_data, list) else 'N/A'}")
            if isinstance(images_data, list) and len(images_data) > 0:
                logger.info(f"[API] 📊 第一个元素类型: {type(images_data[0]).__name__}")
                logger.info(f"[API] 📊 第一个元素keys: {list(images_data[0].keys()) if isinstance(images_data[0], dict) else 'not a dict'}")
                if isinstance(images_data[0], dict):
                    logger.info(f"[API] 📊 第一个元素内容预览: {str(images_data[0])[:200]}...")
            
            if not isinstance(images_data, list):
                logger.error(f"[API] ❌ images字段不是数组类型: {type(images_data).__name__}")
                return jsonify({
                    'success': False,
                    'error': 'images字段必须是数组类型',
                    'code': 400
                }), 400
            
            if len(images_data) == 0:
                logger.error("[API] ❌ images数组为空")
                return jsonify({
                    'success': False,
                    'error': 'images数组不能为空',
                    'code': 400
                }), 400
            
            if len(images_data) > MAX_BATCH_SIZE:
                logger.error(f"[API] ❌ 批量大小超过限制: {len(images_data)} > {MAX_BATCH_SIZE}")
                return jsonify({
                    'success': False,
                    'error': f'批量大小超过限制，最多支持{MAX_BATCH_SIZE}个题目',
                    'code': 400
                }), 400
            
            # 解码base64图片，并提取前端OCR结果（如果有）
            from io import BytesIO
            frontend_ocr_texts = []  # 前端提供的OCR结果列表
            
            decode_errors = []  # 记录解码错误
            
            for idx, img_data in enumerate(images_data):
                # 添加详细的调试信息
                logger.info(f"[API] 🔍 处理图片{idx+1}: 类型={type(img_data).__name__}")
                if isinstance(img_data, dict):
                    logger.info(f"[API] 🔍 图片{idx+1} keys: {list(img_data.keys())}")
                else:
                    logger.warning(f"[API] ⚠️ 图片{idx+1}不是字典类型: {type(img_data).__name__}")
                
                if not isinstance(img_data, dict):
                    decode_errors.append(f"图片{idx+1}: 不是字典类型，而是{type(img_data).__name__}")
                    continue
                
                if 'data' not in img_data:
                    logger.warning(f"[API] ⚠️ 图片{idx+1}缺少data字段，现有keys: {list(img_data.keys())}")
                    decode_errors.append(f"图片{idx+1}: 缺少data字段，现有字段: {list(img_data.keys())}")
                    continue
                
                try:
                    image_base64 = img_data['data']
                    if ',' in image_base64:
                        image_base64 = image_base64.split(',', 1)[1]
                    
                    image_bytes = base64.b64decode(image_base64)
                    
                    # 验证解码后的数据是否是有效的图片
                    if len(image_bytes) == 0:
                        decode_errors.append(f"图片{idx+1}: base64解码后数据为空")
                        continue
                    
                    image_file = BytesIO(image_bytes)
                    image_file.name = img_data.get('filename', 'image.jpg')
                    image_files.append(image_file)
                    
                    # 提取前端OCR结果（如果有）
                    frontend_ocr_text = img_data.get('ocr_text', '').strip() if img_data.get('ocr_text') else None
                    frontend_ocr_texts.append(frontend_ocr_text)
                except Exception as e:
                    error_msg = f"图片{idx+1}: base64解码失败 - {str(e)}"
                    decode_errors.append(error_msg)
                    logger.warning(f"[API] {error_msg}")
                    continue
            
            # 检查是否成功解码了至少一张图片
            if len(image_files) == 0:
                error_detail = "所有图片解码失败"
                if decode_errors:
                    error_detail += f": {', '.join(decode_errors[:3])}"  # 只显示前3个错误
                    if len(decode_errors) > 3:
                        error_detail += f" 等共{len(decode_errors)}个错误"
                
                logger.error(f"[API] ❌ {error_detail}")
                return jsonify({
                    'success': False,
                    'error': error_detail,
                    'code': 400,
                    'details': decode_errors[:5]  # 返回前5个错误详情
                }), 400
            
            # 如果有部分图片解码失败，记录警告
            if len(decode_errors) > 0:
                logger.warning(f"[API] ⚠️ {len(decode_errors)}张图片解码失败，成功解码{len(image_files)}张")
        
        else:
            # multipart/form-data格式
            logger.info("[API] 📦 请求格式: multipart/form-data")
            
            if 'images[]' in request.files:
                image_files = request.files.getlist('images[]')
            elif 'images' in request.files:
                image_files = [request.files['images']]
            else:
                return jsonify({
                    'success': False,
                    'error': '缺少图片文件（images[]或images）',
                    'code': 400
                }), 400
            
            # 过滤空文件
            image_files = [f for f in image_files if f.filename]
            
            if len(image_files) == 0:
                return jsonify({
                    'success': False,
                    'error': '图片文件为空',
                    'code': 400
                }), 400
            
            if len(image_files) > MAX_BATCH_SIZE:
                return jsonify({
                    'success': False,
                    'error': f'批量大小超过限制，最多支持{MAX_BATCH_SIZE}个题目',
                    'code': 400
                }), 400
            
            # 提取前端OCR结果（如果有）
            frontend_ocr_texts = []
            ocr_texts_str = request.form.get('ocr_texts[]', '[]')
            try:
                ocr_texts_list = json.loads(ocr_texts_str) if ocr_texts_str else []
                # 确保长度与图片数量一致
                frontend_ocr_texts = (ocr_texts_list + [None] * len(image_files))[:len(image_files)]
            except:
                frontend_ocr_texts = [None] * len(image_files)
        
        # 获取并发数
        if is_json:
            max_workers = min(int(data.get('max_workers', MAX_WORKERS_DEFAULT)), MAX_WORKERS_MAX)
        else:
            max_workers_str = request.form.get('max_workers', str(MAX_WORKERS_DEFAULT))
            try:
                max_workers = min(int(max_workers_str), MAX_WORKERS_MAX)
            except:
                max_workers = MAX_WORKERS_DEFAULT
        
        max_workers = max(3, max_workers)  # 最少3个并发
        
        # 最终检查：确保至少有一张有效的图片
        if len(image_files) == 0:
            logger.error("[API] ❌ 没有有效的图片文件（所有图片解码/读取失败）")
            return jsonify({
                'success': False,
                'error': '没有有效的图片文件，请检查图片格式和base64编码是否正确',
                'code': 400
            }), 400
        
        logger.info(f"[API] 📊 批量大小: {len(image_files)}, 并发数: {max_workers}")
        
        # 处理前端OCR结果列表（如果JSON格式，已在前面提取；如果是multipart，也已提取）
        if is_json:
            # JSON格式已经在前面提取了frontend_ocr_texts
            pass
        else:
            # multipart格式已经在前面提取了frontend_ocr_texts
            pass
        
        # 确保frontend_ocr_texts与image_files长度一致
        if 'frontend_ocr_texts' not in locals():
            frontend_ocr_texts = [None] * len(image_files)
        elif len(frontend_ocr_texts) < len(image_files):
            frontend_ocr_texts = frontend_ocr_texts + [None] * (len(image_files) - len(frontend_ocr_texts))
        elif len(frontend_ocr_texts) > len(image_files):
            frontend_ocr_texts = frontend_ocr_texts[:len(image_files)]
        
        if any(ocr for ocr in frontend_ocr_texts if ocr):
            logger.info(f"[API] 接收到 {sum(1 for ocr in frontend_ocr_texts if ocr)} 道题的前端OCR结果")
        
        # 调用批量处理服务（传递 app 参数，让每个线程都有自己的应用上下文）
        logger.info(f"[API] 🚀 开始调用批量处理服务...")
        logger.info(f"[API]    - 图片数量: {len(image_files)}")
        logger.info(f"[API]    - 并发数: {max_workers}")
        logger.info(f"[API]    - app对象: {app is not None}")
        
        batch_result = process_batch_concurrent(image_files, frontend_ocr_texts=frontend_ocr_texts, max_workers=max_workers, app=app)
        
        logger.info(f"[API] ✅ 批量处理服务调用完成")
        
        # 格式化响应
        logger.info(f"[API] ✅ 批量提取完成!")
        logger.info(f"[API]    - 总数: {batch_result['total']}")
        logger.info(f"[API]    - 成功: {batch_result['success_count']}")
        logger.info(f"[API]    - 失败: {batch_result['failed_count']}")
        logger.info(f"[API]    - 总耗时: {batch_result['total_time']:.1f}秒 ({batch_result['total_time']/60:.1f}分钟)")
        logger.info(f"[API]    - 总费用: ¥{batch_result['total_cost']:.6f}")
        logger.info(f"[API] ==========================================")
        
        return jsonify({
            'success': True,
            'results': batch_result['results'],
            'statistics': {
                'total': batch_result['total'],
                'success_count': batch_result['success_count'],
                'failed_count': batch_result['failed_count'],
                'total_time': batch_result['total_time'],
                'avg_time_per_question': batch_result['avg_time_per_question'],
                'total_cost': batch_result['total_cost']
            }
        })
    
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        logger.error(f"[API] ❌ 批量提取接口出错: {e}")
        logger.error(f"[API] 错误堆栈: {error_traceback}")
        return jsonify({
            'success': False,
            'error': str(e),
            'code': 500,
            'traceback': error_traceback if app.debug else None  # 仅在debug模式下返回堆栈信息
        }), 500


@app.route('/api/questions/extract/batch/async', methods=['POST'])
def extract_questions_batch_async():
    """
    异步批量提取题目和选项接口（立即返回，后台处理）
    
    立即返回任务ID，避免超时
    客户端需要轮询查询任务状态
    
    请求格式：与同步接口相同
    
    返回：
    {
        "success": true,
        "task_id": "任务ID",
        "message": "任务已提交，正在处理中"
    }
    """
    try:
        from task_manager import get_task_manager, TaskStatus
        from threading import Thread
        
        logger.info("=" * 60)
        logger.info("[API] ========== 收到异步批量提取请求 ==========")
        
        # 复用同步接口的请求解析逻辑
        from batch_question_service import process_batch_concurrent
        
        # 批量大小限制
        MAX_BATCH_SIZE = 100
        MAX_WORKERS_DEFAULT = 10
        MAX_WORKERS_MAX = 20
        
        # 判断请求格式
        content_type = request.content_type or ''
        is_json = 'application/json' in content_type
        
        logger.info(f"[API] Content-Type: {content_type}")
        
        image_files = []
        
        if is_json:
            # JSON格式
            logger.info("[API] 📦 请求格式: application/json")
            
            try:
                data = request.get_json(force=True)
                logger.info(f"[API] JSON解析成功，数据keys: {list(data.keys()) if isinstance(data, dict) else 'not a dict'}")
            except Exception as e:
                logger.error(f"[API] ❌ JSON解析失败: {e}", exc_info=True)
                return jsonify({
                    'success': False,
                    'error': f'JSON格式错误: {str(e)}',
                    'code': 400
                }), 400
            
            if not data or 'images' not in data:
                return jsonify({
                    'success': False,
                    'error': '请求格式错误：缺少images字段',
                    'code': 400
                }), 400
            
            images_data = data.get('images', [])
            
            if not isinstance(images_data, list) or len(images_data) == 0:
                return jsonify({
                    'success': False,
                    'error': 'images数组不能为空',
                    'code': 400
                }), 400
            
            if len(images_data) > MAX_BATCH_SIZE:
                return jsonify({
                    'success': False,
                    'error': f'批量大小超过限制，最多支持{MAX_BATCH_SIZE}个题目',
                    'code': 400
                }), 400
            
            # 解码base64图片
            from io import BytesIO
            frontend_ocr_texts = []
            decode_errors = []
            
            for idx, img_data in enumerate(images_data):
                if not isinstance(img_data, dict) or 'data' not in img_data:
                    decode_errors.append(f"图片{idx+1}: 格式错误")
                    continue
                
                try:
                    image_base64 = img_data['data']
                    if ',' in image_base64:
                        image_base64 = image_base64.split(',', 1)[1]
                    
                    image_bytes = base64.b64decode(image_base64)
                    
                    if len(image_bytes) == 0:
                        decode_errors.append(f"图片{idx+1}: base64解码后数据为空")
                        continue
                    
                    image_file = BytesIO(image_bytes)
                    image_file.name = img_data.get('filename', 'image.jpg')
                    image_files.append(image_file)
                    
                    frontend_ocr_text = img_data.get('ocr_text', '').strip() if img_data.get('ocr_text') else None
                    frontend_ocr_texts.append(frontend_ocr_text)
                except Exception as e:
                    decode_errors.append(f"图片{idx+1}: base64解码失败 - {str(e)}")
                    continue
            
            if len(image_files) == 0:
                return jsonify({
                    'success': False,
                    'error': '所有图片解码失败',
                    'code': 400,
                    'details': decode_errors[:5]
                }), 400
            
            max_workers = min(int(data.get('max_workers', MAX_WORKERS_DEFAULT)), MAX_WORKERS_MAX)
        else:
            # multipart/form-data格式
            logger.info("[API] 📦 请求格式: multipart/form-data")
            
            if 'images[]' in request.files:
                image_files = request.files.getlist('images[]')
            elif 'images' in request.files:
                image_files = [request.files['images']]
            else:
                return jsonify({
                    'success': False,
                    'error': '缺少图片文件',
                    'code': 400
                }), 400
            
            image_files = [f for f in image_files if f.filename]
            
            if len(image_files) == 0 or len(image_files) > MAX_BATCH_SIZE:
                return jsonify({
                    'success': False,
                    'error': f'图片数量无效（0-{MAX_BATCH_SIZE}）',
                    'code': 400
                }), 400
            
            # 提取前端OCR结果
            frontend_ocr_texts = []
            ocr_texts_str = request.form.get('ocr_texts[]', '[]')
            try:
                ocr_texts_list = json.loads(ocr_texts_str) if ocr_texts_str else []
                frontend_ocr_texts = (ocr_texts_list + [None] * len(image_files))[:len(image_files)]
            except:
                frontend_ocr_texts = [None] * len(image_files)
            
            max_workers_str = request.form.get('max_workers', str(MAX_WORKERS_DEFAULT))
            try:
                max_workers = min(int(max_workers_str), MAX_WORKERS_MAX)
            except:
                max_workers = MAX_WORKERS_DEFAULT
        
        max_workers = max(3, max_workers)
        
        # 确保frontend_ocr_texts与image_files长度一致
        if 'frontend_ocr_texts' not in locals():
            frontend_ocr_texts = [None] * len(image_files)
        elif len(frontend_ocr_texts) < len(image_files):
            frontend_ocr_texts = frontend_ocr_texts + [None] * (len(image_files) - len(frontend_ocr_texts))
        elif len(frontend_ocr_texts) > len(image_files):
            frontend_ocr_texts = frontend_ocr_texts[:len(image_files)]
        
        # 创建任务
        task_manager = get_task_manager()
        task_params = {
            'image_count': len(image_files),
            'max_workers': max_workers,
            'has_frontend_ocr': any(ocr for ocr in frontend_ocr_texts if ocr)
        }
        task_id = task_manager.create_task('batch_extract', task_params)
        
        # 保存图片文件数据到临时位置（因为BytesIO对象无法在线程间传递）
        import tempfile
        temp_files = []
        for idx, img_file in enumerate(image_files):
            img_file.seek(0)
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
            temp_file.write(img_file.read())
            temp_file.close()
            temp_files.append(temp_file.name)
        
        # 在后台线程中处理任务
        def process_task():
            import time
            task_start_time = time.time()
            
            try:
                logger.info(f"[任务-{task_id[:8]}] 🚀 后台线程开始处理任务")
                logger.info(f"[任务-{task_id[:8]}] 📊 任务参数: 图片数量={len(temp_files)}, 并发数={max_workers}, 前端OCR={any(ocr for ocr in frontend_ocr_texts if ocr)}")
                
                task_manager.update_task_status(task_id, TaskStatus.PROCESSING)
                logger.info(f"[任务-{task_id[:8]}] ✅ 任务状态已更新为 PROCESSING")
                
                # 重新打开临时文件
                file_prep_start = time.time()
                from io import BytesIO
                processed_image_files = []
                for idx, temp_path in enumerate(temp_files):
                    with open(temp_path, 'rb') as f:
                        img_data = f.read()
                    img_file = BytesIO(img_data)
                    img_file.name = os.path.basename(temp_path)
                    processed_image_files.append(img_file)
                    logger.debug(f"[任务-{task_id[:8]}] 📄 已加载图片 {idx+1}/{len(temp_files)}: {img_file.name}, 大小={len(img_data)/1024:.1f}KB")
                
                file_prep_time = time.time() - file_prep_start
                logger.info(f"[任务-{task_id[:8]}] ✅ 文件准备完成，耗时={file_prep_time:.2f}秒")
                
                # 更新任务进度
                task_manager.update_task_status(task_id, TaskStatus.PROCESSING, progress={
                    'total': len(processed_image_files),
                    'completed': 0,
                    'failed': 0,
                    'current_item': None
                })
                
                # 执行批量处理
                batch_start_time = time.time()
                logger.info(f"[任务-{task_id[:8]}] 🔄 开始执行批量处理...")
                
                # 定义进度更新回调函数
                def update_progress(completed, total, failed):
                    try:
                        task_manager.update_task_status(task_id, TaskStatus.PROCESSING, progress={
                            'total': total,
                            'completed': completed,
                            'failed': failed,
                            'current_item': f"处理中: {completed}/{total}"
                        })
                        progress_percent = int((completed / total * 100)) if total > 0 else 0
                        logger.info(f"[任务-{task_id[:8]}] 📊 进度更新: {completed}/{total} ({progress_percent}%), 失败={failed}")
                    except Exception as e:
                        logger.error(f"[任务-{task_id[:8]}] ❌ 进度更新失败: {e}", exc_info=True)
                
                batch_result = process_batch_concurrent(
                    processed_image_files, 
                    frontend_ocr_texts=frontend_ocr_texts, 
                    max_workers=max_workers, 
                    app=app,
                    progress_callback=update_progress
                )
                batch_time = time.time() - batch_start_time
                logger.info(f"[任务-{task_id[:8]}] ✅ 批量处理完成，耗时={batch_time:.2f}秒")
                logger.info(f"[任务-{task_id[:8]}] 📊 处理结果: 总数={batch_result.get('total', 0)}, 成功={batch_result.get('success_count', 0)}, 失败={batch_result.get('failed_count', 0)}")
                logger.info(f"[任务-{task_id[:8]}] ⏱️  统计: 总耗时={batch_result.get('total_time', 0):.2f}秒, 平均={batch_result.get('avg_time_per_question', 0):.2f}秒/题, 费用=¥{batch_result.get('total_cost', 0):.6f}")
                
                # 更新任务为完成
                task_manager.update_task_status(
                    task_id, 
                    TaskStatus.COMPLETED,
                    result=batch_result,
                    progress={
                        'total': batch_result['total'],
                        'completed': batch_result['success_count'],
                        'failed': batch_result['failed_count'],
                        'current_item': None
                    }
                )
                
                total_task_time = time.time() - task_start_time
                logger.info(f"[任务-{task_id[:8]}] ✅ 异步任务完成，总耗时={total_task_time:.2f}秒")
                
            except Exception as e:
                total_task_time = time.time() - task_start_time
                error_type = type(e).__name__
                error_msg = str(e)
                logger.error(f"[任务-{task_id[:8]}] ❌ 异步任务失败: {error_type}: {error_msg}, 耗时={total_task_time:.2f}秒", exc_info=True)
                task_manager.update_task_status(
                    task_id,
                    TaskStatus.FAILED,
                    error=str(e)
                )
            finally:
                # 清理临时文件
                cleanup_start = time.time()
                cleaned_count = 0
                for temp_path in temp_files:
                    try:
                        if os.path.exists(temp_path):
                            os.unlink(temp_path)
                            cleaned_count += 1
                    except Exception as e:
                        logger.warning(f"[任务-{task_id[:8]}] ⚠️ 清理临时文件失败: {temp_path}, 错误: {e}")
                
                cleanup_time = time.time() - cleanup_start
                logger.info(f"[任务-{task_id[:8]}] 🧹 临时文件清理完成: 清理了 {cleaned_count}/{len(temp_files)} 个文件, 耗时={cleanup_time:.2f}秒")
        
        # 启动后台线程
        thread = Thread(target=process_task, daemon=True)
        thread.start()
        
        logger.info(f"[API] ✅ 异步任务已创建: {task_id}, 图片数量: {len(image_files)}")
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': '任务已提交，正在处理中',
            'status_url': f'/api/tasks/{task_id}/status',
            'result_url': f'/api/tasks/{task_id}/result'
        }), 202  # 202 Accepted
        
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        logger.error(f"[API] ❌ 异步批量提取接口出错: {e}")
        logger.error(f"[API] 错误堆栈: {error_traceback}")
        return jsonify({
            'success': False,
            'error': str(e),
            'code': 500
        }), 500


@app.route('/api/tasks/<task_id>/status', methods=['GET'])
def get_task_status(task_id):
    """
    查询任务状态
    
    返回：
    {
        "success": true,
        "task": {
            "id": "任务ID",
            "status": "pending|processing|completed|failed",
            "progress": {
                "total": 10,
                "completed": 5,
                "failed": 0,
                "current_item": null
            },
            "created_at": "2025-12-07T...",
            "started_at": "2025-12-07T...",
            "completed_at": null,
            "total_time": null
        }
    }
    """
    try:
        from task_manager import get_task_manager
        
        task_manager = get_task_manager()
        task_summary = task_manager.get_task_summary(task_id)
        
        if not task_summary:
            logger.warning(f"[API] ❌ 查询任务状态: 任务不存在 - {task_id}")
            return jsonify({
                'success': False,
                'error': '任务不存在',
                'code': 404
            }), 404
        
        # 记录查询日志（用于调试）
        progress = task_summary.get('progress', {})
        logger.debug(
            f"[API] 📊 查询任务状态: {task_id[:8]}, "
            f"状态={task_summary.get('status')}, "
            f"进度={progress.get('completed', 0)}/{progress.get('total', 0)}, "
            f"失败={progress.get('failed', 0)}"
        )
        
        return jsonify({
            'success': True,
            'task': task_summary
        })
        
    except Exception as e:
        logger.error(f"[API] ❌ 查询任务状态出错: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e),
            'code': 500
        }), 500


@app.route('/api/tasks/<task_id>/result', methods=['GET'])
def get_task_result(task_id):
    """
    获取任务结果
    
    返回：
    - 如果任务完成：返回完整的处理结果
    - 如果任务进行中：返回当前状态
    - 如果任务失败：返回错误信息
    """
    try:
        from task_manager import get_task_manager, TaskStatus
        
        task_manager = get_task_manager()
        task = task_manager.get_task(task_id)
        
        if not task:
            return jsonify({
                'success': False,
                'error': '任务不存在',
                'code': 404
            }), 404
        
        if task['status'] == TaskStatus.COMPLETED.value:
            result_data = task['result']
            
            # 记录返回给前端的数据结构信息（用于调试）
            if result_data and 'results' in result_data:
                results_count = len(result_data.get('results', []))
                success_count = result_data.get('success_count', 0)
                logger.info(f"[API] 📤 返回任务结果: 任务ID={task_id[:8]}, 结果数量={results_count}, 成功={success_count}")
                
                # 检查每道题的字段完整性
                for idx, item in enumerate(result_data.get('results', [])):
                    has_question_text = 'question_text' in item and item.get('question_text')
                    has_options = 'options' in item and isinstance(item.get('options'), list) and len(item.get('options', [])) > 0
                    has_success = 'success' in item
                    
                    logger.debug(
                        f"[API]   题目#{idx+1}: success={item.get('success', False)}, "
                        f"有题目文本={has_question_text}, 有选项={has_options}, "
                        f"题目类型={item.get('question_type', 'N/A')}, "
                        f"初步答案={item.get('preliminary_answer', 'N/A')}"
                    )
                    
                    if not has_question_text:
                        logger.warning(f"[API] ⚠️ 题目#{idx+1} 缺少题目文本")
                    if not has_options:
                        logger.warning(f"[API] ⚠️ 题目#{idx+1} 缺少选项")
            
            response_data = {
                'success': True,
                'status': 'completed',
                'result': result_data
            }
            
            # 记录返回数据的简要信息（用于调试）
            if result_data and 'results' in result_data:
                logger.info(f"[API] ✅ 返回任务结果给前端: 任务ID={task_id[:8]}, 包含 {len(result_data.get('results', []))} 道题结果")
            
            return jsonify(response_data)
        elif task['status'] == TaskStatus.FAILED.value:
            return jsonify({
                'success': False,
                'status': 'failed',
                'error': task.get('error', '未知错误'),
                'code': 500
            }), 500
        else:
            # pending 或 processing
            return jsonify({
                'success': True,
                'status': task['status'],
                'message': '任务尚未完成，请稍后再试',
                'progress': task['progress']
            }), 202  # 202 Accepted
        
    except Exception as e:
        logger.error(f"[API] ❌ 获取任务结果出错: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e),
            'code': 500
        }), 500


@app.route('/api/questions/<question_id>/detail', methods=['GET'])
def get_question_detail(question_id):
    """
    获取题目详情接口（返回答案、解析、标签等）
    
    请求参数：
    - question_id: 题目ID（路径参数）
    
    返回：包含答案、解析、标签等完整详情
    """
    try:
        logger.info("=" * 60)
        logger.info(f"[API] ========== 获取题目详情: {question_id} ==========")
        
        # 调用题目服务获取详情
        result = question_service.analyze_question_detail(question_id)
        
        logger.info(f"[API] ✅ 题目详情获取完成!")
        logger.info(f"[API]    - 题目ID: {result.get('id')}")
        logger.info(f"[API]    - 正确答案: {result.get('correct_answer')}")
        logger.info(f"[API]    - 答案版本数: {len(result.get('answer_versions', []))}")
        logger.info(f"[API]    - 标签: {result.get('tags')}")
        logger.info(f"[API] ==========================================")
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"[API] ❌ 接口出错: {e}", exc_info=True)
        return jsonify({
            'error': str(e),
            'code': 500
        }), 500


@app.route('/api/upload', methods=['POST'])
def upload_image():
    """
    上传图片文件接口
    
    返回：
    {
        "success": true,
        "data": {
            "image_url": "uploads/xxx.jpg",
            "filename": "xxx.jpg"
        }
    }
    """
    try:
        logger.info("[UPLOAD] 收到文件上传请求")
        app.logger.info("[UPLOAD] 收到文件上传请求")  # 同时输出到Flask日志
        if 'file' not in request.files:
            logger.warning("[UPLOAD] 请求中没有文件")
            return jsonify({
                'success': False,
                'error': '没有文件'
            }), 400
        
        file = request.files['file']
        if file.filename == '':
            logger.warning("[UPLOAD] 文件名为空")
            return jsonify({
                'success': False,
                'error': '文件名为空'
            }), 400
        
        logger.info(f"[UPLOAD] 文件名: {file.filename}, 大小: {len(file.read())} bytes")
        file.seek(0)  # 重置文件指针
        
        if file and allowed_file(file.filename):
            # 生成唯一文件名
            filename = secure_filename(file.filename)
            ext = filename.rsplit('.', 1)[1].lower()
            unique_filename = f"{uuid.uuid4().hex}.{ext}"
            filepath = os.path.join(UPLOAD_FOLDER, unique_filename)
            file.save(filepath)
            
            logger.info(f"[UPLOAD] 文件保存成功: {filepath}")
            
            # 返回文件路径（相对于项目根目录）
            image_url = f"file://{os.path.abspath(filepath)}"
            
            return jsonify({
                'success': True,
                'data': {
                    'image_url': image_url,
                    'filename': unique_filename,
                    'path': filepath
                }
            })
        else:
            logger.warning(f"[UPLOAD] 不支持的文件类型: {file.filename}")
            return jsonify({
                'success': False,
                'error': '不支持的文件类型'
            }), 400
    
    except Exception as e:
        logger.error(f"[UPLOAD] 上传出错: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/test', methods=['GET'])
def test_api():
    """
    测试接口 - 用于验证内网穿透是否可用
    
    返回简单的JSON响应，包含服务状态和时间戳
    不需要数据库查询，快速响应
    """
    from datetime import datetime, timedelta
    
    try:
        # 获取客户端IP
        client_ip = request.remote_addr
        if request.headers.get('X-Forwarded-For'):
            client_ip = request.headers.get('X-Forwarded-For').split(',')[0].strip()
        
        # 获取请求头信息（用于调试）
        user_agent = request.headers.get('User-Agent', 'Unknown')
        
        response_data = {
            'success': True,
            'message': '服务运行正常',
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'server_time': datetime.now().isoformat(),
            'service': '公考题库分析服务',
            'version': '2.0',
            'status': 'online',
            'client_ip': client_ip,
            'endpoints': {
                'test': '/api/test',
                'version': '/api/version',
                'health': '/api/health',
                'stats': '/api/stats',
                'analyze': '/api/questions/analyze',
                'analyze_batch': '/api/questions/analyze/batch',
                'extract_batch': '/api/questions/extract/batch',
                'extract_batch_async': '/api/questions/extract/batch/async',
                'task_status': '/api/tasks/<task_id>/status',
                'task_result': '/api/tasks/<task_id>/result',
                'detail': '/api/questions/<question_id>/detail',
                'upload': '/api/upload',
                'apk_download': '/api/apk/download',
                'apk_upload': '/api/apk/upload',
                'apk_info': '/api/apk/info',
                'user_stats': '/api/users/stats',
                'user_retention': '/api/users/retention',
                'user_cohort': '/api/users/cohort'
            }
        }
        
        logger.info(f"[API] ✅ 测试接口被访问 - 客户端IP: {client_ip}")
        
        return jsonify(response_data)
    
    except Exception as e:
        logger.error(f"[API] ❌ 测试接口出错: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@app.route('/api/version', methods=['GET'])
def get_version():
    """
    获取应用版本信息接口
    
    返回应用版本、API版本、构建信息等
    用于前端检查后端版本兼容性
    
    请求参数（可选）：
    - client_version: 客户端版本号（如 "1.0.0"）
    
    返回：
    {
        "success": true,
        "version": {
            "app_version": "2.0.0",
            "api_version": "2.0",
            "build_time": "2025-01-07T12:00:00",
            "git_commit": "abc123..." (如果有),
            "git_branch": "main" (如果有),
            "python_version": "3.11.0",
            "flask_version": "3.0.0"
        },
        "update": {
            "required": true/false,  // 是否需要更新
            "latest_version": "2.0.0",  // 最新版本
            "download_url": "/api/apk/download",  // APK下载链接
            "release_notes": "更新说明"  // 更新说明
        },
        "service": "公考题库分析服务",
        "status": "online"
    }
    """
    import sys
    import platform
    from datetime import datetime, timedelta
    
    try:
        # 获取应用版本
        app_version = "2.0.0"
        api_version = "2.0"
        
        # 获取客户端版本（如果提供）
        client_version = request.args.get('client_version', '')
        
        # 检查是否需要更新
        update_info = _check_version_update(client_version, app_version)
        
        # 获取Python版本
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        
        # 获取Flask版本
        try:
            import flask
            flask_version = flask.__version__
        except:
            flask_version = "unknown"
        
        # 获取Git信息（如果可用）
        git_info = {}
        try:
            import subprocess
            import os
            
            # 检查是否在Git仓库中
            if os.path.exists('.git'):
                try:
                    # 获取Git commit hash
                    commit_hash = subprocess.check_output(
                        ['git', 'rev-parse', '--short', 'HEAD'],
                        stderr=subprocess.DEVNULL
                    ).decode('utf-8').strip()
                    git_info['commit'] = commit_hash
                except:
                    pass
                
                try:
                    # 获取Git分支
                    branch = subprocess.check_output(
                        ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                        stderr=subprocess.DEVNULL
                    ).decode('utf-8').strip()
                    git_info['branch'] = branch
                except:
                    pass
                
                try:
                    # 获取最后提交时间
                    commit_time = subprocess.check_output(
                        ['git', 'log', '-1', '--format=%ci'],
                        stderr=subprocess.DEVNULL
                    ).decode('utf-8').strip()
                    git_info['last_commit_time'] = commit_time
                except:
                    pass
        except:
            pass
        
        # 构建版本信息
        version_info = {
            'app_version': app_version,
            'api_version': api_version,
            'build_time': datetime.now().isoformat(),
            'python_version': python_version,
            'flask_version': flask_version,
            'platform': platform.system(),
            'platform_version': platform.version()
        }
        
        # 添加Git信息（如果有）
        if git_info:
            version_info.update(git_info)
        
        response_data = {
            'success': True,
            'version': version_info,
            'update': update_info,
            'service': '公考题库分析服务',
            'status': 'online',
            'timestamp': datetime.now().isoformat()
        }
        
        if client_version:
            logger.info(f"[API] 📦 版本检查 - 客户端: {client_version}, 服务端: {app_version}, 需要更新: {update_info['required']}")
        else:
            logger.info(f"[API] 📦 版本信息查询 - 版本: {app_version}, API: {api_version}")
        
        # 自动追踪用户活动（仅在版本验证时记录）
        try:
            device_id = request.headers.get('X-Device-ID') or request.args.get('device_id')
            app_version_param = request.headers.get('X-App-Version') or request.args.get('app_version') or client_version
            
            if device_id:
                device_id = user_statistics_service.get_or_create_device_id(device_id)
                
                # 获取设备信息
                device_info = {
                    'user_agent': request.headers.get('User-Agent', ''),
                    'ip': request.remote_addr,
                    'platform': platform.system()
                }
                
                # 记录用户活动（版本检查通常表示用户打开应用）
                user_statistics_service.track_user_activity(
                    device_id=device_id,
                    device_info=device_info,
                    app_version=app_version_param,
                    question_count=0  # 版本检查不涉及题目分析
                )
                logger.info(f"[API] 📊 用户活动已记录: {device_id}")
        except Exception as e:
            logger.warning(f"[API] 用户活动追踪失败（不影响主流程）: {e}")
        
        return jsonify(response_data)
    
    except Exception as e:
        logger.error(f"[API] ❌ 获取版本信息出错: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e),
            'version': {
                'app_version': '2.0.0',
                'api_version': '2.0',
                'status': 'error'
            },
            'timestamp': datetime.now().isoformat()
        }), 500


@app.route('/api/apk/download', methods=['GET'])
def download_apk():
    """
    APK下载接口
    
    返回最新的APK文件
    
    返回：
    - 如果APK存在：返回APK文件
    - 如果APK不存在：返回404错误
    """
    import json
    from flask import send_file, abort
    
    try:
        # 读取APK版本信息
        apk_info = {}
        apk_filename = None
        
        if os.path.exists(APK_VERSION_FILE):
            try:
                with open(APK_VERSION_FILE, 'r', encoding='utf-8') as f:
                    apk_info = json.load(f)
                    apk_filename = apk_info.get('filename')
            except Exception as e:
                logger.error(f"[API] ❌ 读取APK版本信息失败: {e}")
        
        # 如果没有指定文件名，尝试查找apk文件夹中的第一个.apk文件
        if not apk_filename:
            apk_files = [f for f in os.listdir(APK_FOLDER) if f.endswith('.apk')]
            if apk_files:
                apk_filename = apk_files[0]  # 使用第一个找到的APK文件
                logger.info(f"[API] 自动找到APK文件: {apk_filename}")
        
        if not apk_filename:
            logger.warning("[API] ❌ 未找到APK文件")
            return jsonify({
                'success': False,
                'error': 'APK文件不存在',
                'code': 404
            }), 404
        
        apk_path = os.path.join(APK_FOLDER, apk_filename)
        
        if not os.path.exists(apk_path):
            logger.warning(f"[API] ❌ APK文件不存在: {apk_path}")
            return jsonify({
                'success': False,
                'error': 'APK文件不存在',
                'code': 404
            }), 404
        
        logger.info(f"[API] 📥 APK下载请求: {apk_filename}")
        
        # 返回APK文件
        return send_file(
            apk_path,
            mimetype='application/vnd.android.package-archive',
            as_attachment=True,
            download_name=apk_filename
        )
    
    except Exception as e:
        logger.error(f"[API] ❌ APK下载失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e),
            'code': 500
        }), 500


@app.route('/api/apk/upload', methods=['POST'])
def upload_apk():
    """
    APK上传接口（管理员用）
    
    上传新的APK文件并更新版本信息
    
    请求参数（multipart/form-data）：
    - file: APK文件（必需）
    - version: 版本号（如 "2.0.0"）（必需）
    - release_notes: 更新说明（可选）
    
    返回：
    {
        "success": true,
        "message": "APK上传成功",
        "version": "2.0.0",
        "filename": "app-v2.0.0.apk"
    }
    """
    import json
    from datetime import datetime, timedelta
    
    try:
        # 检查是否有文件
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': '没有文件',
                'code': 400
            }), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': '文件名为空',
                'code': 400
            }), 400
        
        # 检查文件扩展名
        if not file.filename.lower().endswith('.apk'):
            return jsonify({
                'success': False,
                'error': '文件必须是APK格式',
                'code': 400
            }), 400
        
        # 获取版本号和更新说明
        version = request.form.get('version', '').strip()
        if not version:
            return jsonify({
                'success': False,
                'error': '版本号不能为空',
                'code': 400
            }), 400
        
        release_notes = request.form.get('release_notes', '').strip()
        
        # 生成安全的文件名
        safe_filename = secure_filename(file.filename)
        # 如果文件名不包含版本号，添加版本号
        if version not in safe_filename:
            name, ext = os.path.splitext(safe_filename)
            safe_filename = f"{name}-v{version}{ext}"
        
        apk_path = os.path.join(APK_FOLDER, safe_filename)
        
        # 保存APK文件
        file.save(apk_path)
        logger.info(f"[API] ✅ APK文件已保存: {apk_path}")
        
        # 更新版本信息文件
        apk_info = {
            'version': version,
            'filename': safe_filename,
            'release_notes': release_notes,
            'upload_time': datetime.now().isoformat(),
            'file_size': os.path.getsize(apk_path)
        }
        
        with open(APK_VERSION_FILE, 'w', encoding='utf-8') as f:
            json.dump(apk_info, f, indent=2, ensure_ascii=False)
        
        logger.info(f"[API] ✅ APK版本信息已更新: {version}")
        
        return jsonify({
            'success': True,
            'message': 'APK上传成功',
            'version': version,
            'filename': safe_filename,
            'file_size': apk_info['file_size']
        })
    
    except Exception as e:
        logger.error(f"[API] ❌ APK上传失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e),
            'code': 500
        }), 500


@app.route('/api/apk/info', methods=['GET'])
def get_apk_info():
    """
    获取APK信息接口
    
    返回当前APK的版本信息和下载链接
    
    返回：
    {
        "success": true,
        "apk": {
            "version": "2.0.0",
            "filename": "app-v2.0.0.apk",
            "release_notes": "更新说明",
            "upload_time": "2025-01-07T12:00:00",
            "file_size": 12345678,
            "download_url": "/api/apk/download"
        }
    }
    """
    import json
    
    try:
        apk_info = {}
        
        if os.path.exists(APK_VERSION_FILE):
            try:
                with open(APK_VERSION_FILE, 'r', encoding='utf-8') as f:
                    apk_info = json.load(f)
            except Exception as e:
                logger.error(f"[API] ❌ 读取APK信息失败: {e}")
        
        if not apk_info:
            return jsonify({
                'success': False,
                'error': 'APK信息不存在',
                'code': 404
            }), 404
        
        # 添加下载链接
        apk_info['download_url'] = '/api/apk/download'
        
        return jsonify({
            'success': True,
            'apk': apk_info
        })
    
    except Exception as e:
        logger.error(f"[API] ❌ 获取APK信息失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e),
            'code': 500
        }), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """
    健康检查接口 - 用于监控服务状态
    
    返回服务健康状态，包括数据库连接状态
    """
    from datetime import datetime, timedelta
    
    try:
        health_status = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'service': '公考题库分析服务',
            'checks': {}
        }
        
        # 检查数据库连接
        try:
            with app.app_context():
                # 首先检查当前配置的数据库URL
                current_db_url = app.config.get('SQLALCHEMY_DATABASE_URI', '')
                current_db_type = 'unknown'
                if 'sqlite' in current_db_url.lower():
                    current_db_type = 'sqlite'
                elif 'postgres' in current_db_url.lower():
                    current_db_type = 'postgresql'
                elif 'mysql' in current_db_url.lower():
                    current_db_type = 'mysql'
                
                # 如果当前配置是SQLite，直接尝试SQLite连接（绕过可能有问题的engine）
                if 'sqlite' in current_db_url.lower():
                    try:
                        sqlite_url = 'sqlite:///gongkao_test.db'
                        from sqlalchemy import create_engine
                        test_engine = create_engine(sqlite_url, echo=False)
                        with test_engine.connect() as conn:
                            pass
                        health_status['checks']['database'] = {
                            'status': 'connected',
                            'type': 'sqlite'
                        }
                    except Exception as sqlite_error:
                        health_status['checks']['database'] = {
                            'status': 'disconnected',
                            'error': f'SQLite连接失败: {str(sqlite_error)[:100]}',
                            'type': 'sqlite'
                        }
                        health_status['status'] = 'degraded'
                else:
                    # 对于非SQLite数据库，尝试使用db.engine连接
                    try:
                        db.engine.connect()
                        health_status['checks']['database'] = {
                            'status': 'connected',
                            'type': current_db_type or database_type or 'unknown'
                        }
                    except Exception as db_error:
                        # 所有数据库连接错误
                        error_msg = str(db_error)
                        error_type = type(db_error).__name__
                        
                        # 检测是否是编码错误
                        is_encoding_error = (
                            isinstance(db_error, (UnicodeDecodeError, UnicodeEncodeError)) or
                            'codec' in error_msg.lower() or 
                            'decode' in error_msg.lower() or 
                            'utf-8' in error_msg.lower() or
                            'invalid start byte' in error_msg.lower()
                        )
                        
                        if is_encoding_error:
                            # 编码错误，尝试SQLite连接
                            logger.warning(f"[API] 数据库连接编码错误: {error_type}，尝试SQLite")
                            try:
                                sqlite_url = 'sqlite:///gongkao_test.db'
                                from sqlalchemy import create_engine
                                test_engine = create_engine(sqlite_url, echo=False)
                                with test_engine.connect() as conn:
                                    pass
                                health_status['checks']['database'] = {
                                    'status': 'degraded',
                                    'type': 'sqlite',
                                    'note': '主数据库配置有编码错误，已回退到SQLite'
                                }
                            except Exception:
                                health_status['checks']['database'] = {
                                    'status': 'disconnected',
                                    'error': '数据库配置编码错误，建议检查.env文件中的DATABASE_URL配置或删除该配置使用SQLite',
                                    'type': current_db_type or database_type or 'unknown'
                                }
                        else:
                            # 其他数据库连接错误
                            health_status['checks']['database'] = {
                                'status': 'disconnected',
                                'error': error_msg[:150] if len(error_msg) > 150 else error_msg,
                                'type': current_db_type or database_type or 'unknown'
                            }
                        health_status['status'] = 'degraded'
        except Exception as outer_error:
            # 外层异常（可能是编码错误发生在engine创建时）
            error_msg = str(outer_error)
            is_encoding_error = (
                isinstance(outer_error, (UnicodeDecodeError, UnicodeEncodeError)) or
                'codec' in error_msg.lower() or 
                'decode' in error_msg.lower() or 
                'utf-8' in error_msg.lower()
            )
            
            if is_encoding_error:
                logger.warning(f"[API] 数据库初始化编码错误: {type(outer_error).__name__}")
                health_status['checks']['database'] = {
                    'status': 'disconnected',
                    'error': '数据库配置编码错误，建议检查.env文件中的DATABASE_URL配置',
                    'type': database_type or 'unknown'
                }
            else:
                health_status['checks']['database'] = {
                    'status': 'disconnected',
                    'error': '数据库连接异常',
                    'type': database_type or 'unknown'
                }
            health_status['status'] = 'degraded'
        
        # 检查文件上传目录
        try:
            if os.path.exists(UPLOAD_FOLDER) and os.path.isdir(UPLOAD_FOLDER):
                health_status['checks']['upload_folder'] = {
                    'status': 'available',
                    'path': UPLOAD_FOLDER
                }
            else:
                health_status['checks']['upload_folder'] = {
                    'status': 'missing',
                    'path': UPLOAD_FOLDER
                }
                health_status['status'] = 'degraded'
        except Exception as folder_error:
            health_status['checks']['upload_folder'] = {
                'status': 'error',
                'error': str(folder_error)
            }
        
        # 检查OCR服务状态
        try:
            from ocr_service import get_ocr_service
            ocr_service = get_ocr_service()
            
            if ocr_service and ocr_service.ocr_engine:
                engine_name = "未知"
                if hasattr(ocr_service.ocr_engine, 'ocr'):
                    engine_name = "PaddleOCR"
                elif ocr_service.ocr_engine == 'tesseract':
                    engine_name = "Tesseract"
                
                health_status['checks']['ocr_service'] = {
                    'status': 'loaded',
                    'engine': engine_name,
                    'note': 'OCR服务已加载，可以立即使用'
                }
            else:
                health_status['checks']['ocr_service'] = {
                    'status': 'not_loaded',
                    'note': 'OCR服务未加载，将在首次请求时初始化'
                }
                health_status['status'] = 'degraded'
        except Exception as ocr_error:
            health_status['checks']['ocr_service'] = {
                'status': 'error',
                'error': str(ocr_error)[:100]
            }
        
        logger.info(f"[API] 🏥 健康检查 - 状态: {health_status['status']}")
        
        # 如果所有检查都通过，返回200，否则返回503
        status_code = 200 if health_status['status'] == 'healthy' else 503
        
        return jsonify(health_status), status_code
    
    except Exception as e:
        logger.error(f"[API] ❌ 健康检查出错: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@app.route('/api/stats', methods=['GET'])
def get_stats():
    """
    获取统计信息（题目和答案版本）
    """
    try:
        logger.info("[API] 📊 获取统计信息...")
        question_count = Question.query.count()
        answer_version_count = AnswerVersion.query.count()
        
        logger.info(f"[API]    - 题目数: {question_count}")
        logger.info(f"[API]    - 答案版本数: {answer_version_count}")
        
        return jsonify({
            'success': True,
            'data': {
                'questions': question_count,
                'answer_versions': answer_version_count
            }
        })
    except Exception as e:
        logger.error(f"[API] ❌ 获取统计信息出错: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/users/stats', methods=['GET'])
def get_user_statistics():
    """
    获取用户统计数据（留存率、DAU等）
    
    请求参数（可选）:
    - days: 统计最近多少天（默认30天）
    
    返回：
    {
        "success": true,
        "data": {
            "total_users": 1000,
            "active_users": 500,
            "new_users": 50,
            "avg_dau": 200.5,
            "daily_active_users": [...]
        }
    }
    """
    try:
        days = int(request.args.get('days', 30))
        days = max(1, min(days, 365))  # 限制在1-365天之间
        
        logger.info(f"[API] 📊 获取用户统计数据（最近{days}天）...")
        
        stats = user_statistics_service.get_user_statistics(days=days)
        
        if 'error' in stats:
            return jsonify({
                'success': False,
                'error': stats['error']
            }), 500
        
        logger.info(f"[API]    - 总用户数: {stats.get('total_users', 0)}")
        logger.info(f"[API]    - 活跃用户数: {stats.get('active_users', 0)}")
        logger.info(f"[API]    - 新增用户数: {stats.get('new_users', 0)}")
        
        return jsonify({
            'success': True,
            'data': stats
        })
    except Exception as e:
        logger.error(f"[API] ❌ 获取用户统计数据出错: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/users/retention', methods=['GET'])
def get_retention_rate():
    """
    获取留存率数据
    
    请求参数（可选）:
    - start_date: 起始日期（YYYY-MM-DD格式，默认：7天前）
    - days: 计算多少天的留存率（默认7天）
    
    返回：
    {
        "success": true,
        "data": {
            "start_date": "2025-01-01",
            "new_users": 100,
            "retention_data": [
                {
                    "day": 0,
                    "date": "2025-01-01",
                    "retained_users": 100,
                    "retention_rate": 100.0
                },
                ...
            ]
        }
    }
    """
    try:
        from datetime import datetime as dt, date, timedelta
        
        start_date_str = request.args.get('start_date')
        if start_date_str:
            start_date = dt.strptime(start_date_str, '%Y-%m-%d').date()
        else:
            days = int(request.args.get('days', 7))
            start_date = date.today() - timedelta(days=days)
        
        days = int(request.args.get('days', 7))
        days = max(1, min(days, 90))  # 限制在1-90天之间
        
        logger.info(f"[API] 📊 计算留存率（起始日期: {start_date}, 追踪{days}天）...")
        
        retention_data = user_statistics_service.calculate_retention_rate(
            start_date=start_date,
            days=days
        )
        
        if 'error' in retention_data:
            return jsonify({
                'success': False,
                'error': retention_data['error']
            }), 500
        
        logger.info(f"[API]    - 新增用户数: {retention_data.get('new_users', 0)}")
        
        return jsonify({
            'success': True,
            'data': retention_data
        })
    except ValueError as e:
        logger.error(f"[API] ❌ 日期格式错误: {e}")
        return jsonify({
            'success': False,
            'error': f'日期格式错误，请使用YYYY-MM-DD格式: {str(e)}'
        }), 400
    except Exception as e:
        logger.error(f"[API] ❌ 计算留存率出错: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/users/cohort', methods=['GET'])
def get_cohort_retention():
    """
    获取Cohort留存率（按首次使用日期分组）
    
    请求参数（可选）:
    - cohort_days: 计算多少天的cohort（默认7天）
    - retention_days: 追踪多少天的留存（默认30天）
    
    返回：
    {
        "success": true,
        "data": {
            "cohorts": [
                {
                    "cohort_date": "2025-01-01",
                    "new_users": 100,
                    "retention_data": [...]
                },
                ...
            ]
        }
    }
    """
    try:
        cohort_days = int(request.args.get('cohort_days', 7))
        retention_days = int(request.args.get('retention_days', 30))
        
        cohort_days = max(1, min(cohort_days, 30))  # 限制在1-30天
        retention_days = max(1, min(retention_days, 90))  # 限制在1-90天
        
        logger.info(f"[API] 📊 计算Cohort留存率（cohort_days: {cohort_days}, retention_days: {retention_days}）...")
        
        cohort_data = user_statistics_service.get_cohort_retention(
            cohort_days=cohort_days,
            retention_days=retention_days
        )
        
        if 'error' in cohort_data:
            return jsonify({
                'success': False,
                'error': cohort_data['error']
            }), 500
        
        logger.info(f"[API]    - Cohort数量: {len(cohort_data.get('cohorts', []))}")
        
        return jsonify({
            'success': True,
            'data': cohort_data
        })
    except Exception as e:
        logger.error(f"[API] ❌ 计算Cohort留存率出错: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/clear', methods=['POST'])
def clear_database():
    """
    清理数据库接口（危险操作，建议添加认证）
    
    请求体（可选）:
    {
        "clear_type": "all"  // "all"清空所有, "answers"只清空答案版本
    }
    """
    try:
        data = request.get_json() or {}
        clear_type = data.get('clear_type', 'all')
        
        if clear_type == 'answers':
            # 只清空答案版本
            count = AnswerVersion.query.count()
            AnswerVersion.query.delete()
            db.session.commit()
            logger.warning(f"[API] 清空答案版本记录: {count} 条")
            return jsonify({
                'success': True,
                'message': f'已清空 {count} 条答案版本记录',
                'cleared': count
            })
        else:
            # 清空所有（答案版本会自动级联删除）
            answer_count = AnswerVersion.query.count()
            question_count = Question.query.count()
            AnswerVersion.query.delete()
            Question.query.delete()
            db.session.commit()
            logger.warning(f"[API] 清空所有数据: 题目 {question_count} 条, 答案版本 {answer_count} 条")
            return jsonify({
                'success': True,
                'message': f'已清空所有数据（题目 {question_count} 条, 答案版本 {answer_count} 条）',
                'cleared': {
                    'questions': question_count,
                    'answer_versions': answer_count
                }
            })
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"[API] 清理数据库出错: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == '__main__':
    with app.app_context():
        try:
            # 测试数据库连接
            db.engine.connect()
            logger.info("✅ 数据库连接成功！")
            
            # 创建表（如果不存在）
            db.create_all()
            logger.info("✅ 数据库表已就绪！")
            
            # 检查表是否存在
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            logger.info(f"📊 数据库表: {', '.join(tables)}")
            
        except (UnicodeDecodeError, UnicodeEncodeError) as e:
            logger.error(f"❌ 数据库连接编码错误：{e}")
            # 如果是编码错误，完全清除有问题的环境变量
            if 'DATABASE_URL' in os.environ:
                del os.environ['DATABASE_URL']
                logger.info("已清除有问题的DATABASE_URL环境变量")
            
            # 第一优先级：尝试SQLite
            logger.warning("⚠️ 检测到编码错误，尝试使用SQLite数据库...")
            sqlite_success = False
            try:
                sqlite_url = 'sqlite:///gongkao_test.db'
                app.config['SQLALCHEMY_DATABASE_URI'] = sqlite_url
                
                # 重新创建engine（完全清除旧的，使用新的URL和连接池配置）
                from sqlalchemy import create_engine
                from sqlalchemy.orm import scoped_session, sessionmaker
                # 确保URL是纯ASCII
                sqlite_url_clean = str(sqlite_url).encode('ascii', errors='ignore').decode('ascii')
                # 使用SQLite连接池配置
                engine_options = {
                    'pool_pre_ping': True,
                    'pool_recycle': 300,
                    'pool_size': 20,
                    'max_overflow': 30,
                    'pool_timeout': 30,
                    'connect_args': {
                        'check_same_thread': False,
                        'timeout': 30
                    }
                }
                engine = create_engine(sqlite_url_clean, echo=False, **engine_options)
                
                # 直接替换db的内部engine属性
                db.get_engine = lambda bind=None: engine
                db.session = scoped_session(sessionmaker(bind=engine))
                
                # 测试SQLite连接（直接使用engine，不使用db.engine）
                with engine.connect() as conn:
                    pass  # 测试连接
                
                # 使用新的engine创建表
                from models_v2 import Question, AnswerVersion
                Question.metadata.create_all(engine)
                AnswerVersion.metadata.create_all(engine)
                
                logger.info("✅ SQLite数据库连接成功！")
                logger.info("✅ 数据库表已就绪！")
                
                # 检查表是否存在
                from sqlalchemy import inspect
                inspector = inspect(engine)
                tables = inspector.get_table_names()
                logger.info(f"📊 数据库表: {', '.join(tables)}")
                sqlite_success = True
                database_type = 'sqlite'  # 更新数据库类型
            except Exception as e2:
                logger.warning(f"⚠️ SQLite数据库连接失败：{e2}")
                import traceback
                logger.debug(f"SQLite错误详情: {traceback.format_exc()}")
            
            # 如果SQLite失败，尝试MySQL
            if not sqlite_success:
                logger.warning("⚠️ 尝试使用MySQL数据库作为最后备选...")
                try:
                    # 从环境变量读取MySQL配置（确保使用ASCII字符）
                    mysql_host = str(os.getenv('MYSQL_HOST', 'localhost'))
                    mysql_port = str(os.getenv('MYSQL_PORT', '3306'))
                    mysql_user = str(os.getenv('MYSQL_USER', 'root'))
                    mysql_password = str(os.getenv('MYSQL_PASSWORD', ''))
                    mysql_database = str(os.getenv('MYSQL_DATABASE', 'gongkao_test'))
                    
                    # 确保所有值都是ASCII编码
                    mysql_host = mysql_host.encode('ascii', errors='ignore').decode('ascii')
                    mysql_user = mysql_user.encode('ascii', errors='ignore').decode('ascii')
                    mysql_password = mysql_password.encode('ascii', errors='ignore').decode('ascii')
                    mysql_database = mysql_database.encode('ascii', errors='ignore').decode('ascii')
                    
                    mysql_url = f'mysql+pymysql://{mysql_user}:{mysql_password}@{mysql_host}:{mysql_port}/{mysql_database}?charset=utf8mb4'
                    app.config['SQLALCHEMY_DATABASE_URI'] = mysql_url
                    
                    # 重新创建engine（使用连接池配置）
                    from sqlalchemy import create_engine
                    from sqlalchemy.orm import scoped_session, sessionmaker
                    engine_options = {
                        'pool_pre_ping': True,
                        'pool_recycle': 300,
                        'pool_size': 20,
                        'max_overflow': 30,
                        'pool_timeout': 30,
                    }
                    engine = create_engine(mysql_url, echo=False, **engine_options)
                    db.get_engine = lambda bind=None: engine
                    db.session = scoped_session(sessionmaker(bind=engine))
                    
                    # 测试MySQL连接
                    conn = engine.connect()
                    conn.close()
                    db.create_all()
                    logger.info("✅ MySQL数据库连接成功！")
                    logger.info("✅ 数据库表已就绪！")
                    
                    # 检查表是否存在
                    from sqlalchemy import inspect
                    inspector = inspect(engine)
                    tables = inspector.get_table_names()
                    logger.info(f"📊 数据库表: {', '.join(tables)}")
                except ImportError:
                    logger.error("❌ MySQL驱动未安装，请运行: pip install pymysql")
                    print("\n请检查：")
                    print("1. DATABASE_URL 环境变量编码是否正确（建议删除.env中的DATABASE_URL）")
                    print("2. SQLite数据库文件权限")
                    print("3. MySQL配置（MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE）")
                    print("4. 如果使用MySQL，请安装驱动: pip install pymysql")
                    print("5. 可以手动删除.env文件中的DATABASE_URL行，然后重新运行")
                    exit(1)
                except Exception as e3:
                    logger.error(f"❌ MySQL数据库连接也失败：{e3}")
                    print("\n请检查：")
                    print("1. DATABASE_URL 环境变量编码是否正确（建议删除.env中的DATABASE_URL）")
                    print("2. SQLite数据库文件权限")
                    print("3. MySQL配置（MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE）")
                    print("4. MySQL服务是否正在运行")
                    print("5. 如果使用MySQL，请安装驱动: pip install pymysql")
                    print("6. 可以手动删除.env文件中的DATABASE_URL行，然后重新运行")
                    exit(1)
        except Exception as e:
            error_msg = str(e)
            # 检查是否是编码错误
            is_encoding_error = (
                isinstance(e, (UnicodeDecodeError, UnicodeEncodeError)) or
                'codec' in error_msg.lower() or 
                'decode' in error_msg.lower() or 
                'utf-8' in error_msg.lower() or
                'invalid start byte' in error_msg.lower()
            )
            
            if is_encoding_error:
                logger.error(f"❌ 数据库连接编码错误：{e}")
                # 清除有问题的环境变量并回退到SQLite
                if 'DATABASE_URL' in os.environ:
                    del os.environ['DATABASE_URL']
                    logger.info("已清除有问题的DATABASE_URL环境变量")
                
                logger.warning("⚠️ 自动回退到SQLite数据库...")
                try:
                    sqlite_url = 'sqlite:///gongkao_test.db'
                    app.config['SQLALCHEMY_DATABASE_URI'] = sqlite_url
                    
                    from sqlalchemy import create_engine
                    from sqlalchemy.orm import scoped_session, sessionmaker
                    sqlite_url_clean = str(sqlite_url).encode('ascii', errors='ignore').decode('ascii')
                    # 使用SQLite连接池配置
                    engine_options = {
                        'pool_pre_ping': True,
                        'pool_recycle': 300,
                        'pool_size': 20,
                        'max_overflow': 30,
                        'pool_timeout': 30,
                        'connect_args': {
                            'check_same_thread': False,
                            'timeout': 30
                        }
                    }
                    engine = create_engine(sqlite_url_clean, echo=False, **engine_options)
                    
                    db.get_engine = lambda bind=None: engine
                    db.session = scoped_session(sessionmaker(bind=engine))
                    
                    with engine.connect() as conn:
                        pass
                    
                    from models_v2 import Question, AnswerVersion
                    Question.metadata.create_all(engine)
                    AnswerVersion.metadata.create_all(engine)
                    
                    logger.info("✅ SQLite数据库连接成功！")
                    logger.info("✅ 数据库表已就绪！")
                    database_type = 'sqlite'
                    
                    from sqlalchemy import inspect
                    inspector = inspect(engine)
                    tables = inspector.get_table_names()
                    logger.info(f"📊 数据库表: {', '.join(tables)}")
                except Exception as e2:
                    logger.error(f"❌ SQLite数据库连接也失败：{e2}")
                    print("\n请检查：")
                    print("1. SQLite数据库文件权限")
                    print("2. 可以手动删除.env文件中的DATABASE_URL行，然后重新运行")
                    exit(1)
            else:
                logger.error(f"❌ 数据库连接失败：{e}")
                print("\n请检查：")
                print("1. DATABASE_URL 环境变量是否正确配置")
                print("2. Supabase数据库连接是否正常")
                print("3. 网络连接是否正常")
                print("4. 如果遇到编码错误，可以删除.env文件中的DATABASE_URL，使用SQLite测试")
                exit(1)
    
    # 预加载OCR服务（在启动时加载，避免首次请求延迟）
    # 可通过环境变量 PRELOAD_OCR=true/false 控制是否预加载（默认true）
    preload_ocr = os.getenv('PRELOAD_OCR', 'true').lower() in ('true', '1', 'yes')
    
    if preload_ocr:
        print("\n" + "=" * 60)
        print("正在预加载OCR服务（PaddleOCR）...")
        print("=" * 60)
        
        try:
            from ocr_service import get_ocr_service
            import time
            
            start_time = time.time()
            logger.info("[启动] 开始预加载OCR服务...")
            print("📦 正在初始化PaddleOCR模型...")
            print("   提示: 首次启动可能需要下载模型文件，请耐心等待")
            
            # 获取OCR服务实例（这会触发PaddleOCR初始化）
            ocr_service = get_ocr_service()
            
            elapsed_init = time.time() - start_time
            
            if ocr_service and ocr_service.ocr_engine:
                # 判断使用的OCR引擎
                engine_name = "未知"
                if hasattr(ocr_service.ocr_engine, 'ocr'):
                    engine_name = "PaddleOCR"
                elif ocr_service.ocr_engine == 'tesseract':
                    engine_name = "Tesseract"
                
                logger.info(f"[启动] OCR服务初始化完成，使用引擎: {engine_name}")
                print(f"✅ OCR服务初始化完成！耗时: {elapsed_init:.1f}秒")
                print(f"   📝 使用的引擎: {engine_name}")
                
                # 可选：进行一个简单的测试识别，确保模型完全加载
                # 可通过环境变量 PRELOAD_OCR_TEST=true/false 控制（默认false，避免额外延迟）
                test_ocr = os.getenv('PRELOAD_OCR_TEST', 'false').lower() in ('true', '1', 'yes')
                
                if test_ocr:
                    logger.info("[启动] 开始OCR测试识别...")
                    print("🔍 进行测试识别以确保模型已完全加载...")
                    
                    try:
                        from PIL import Image
                        import tempfile
                        
                        # 创建一个简单的测试图片
                        test_img = Image.new('RGB', (100, 30), color='white')
                        test_file = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
                        test_img.save(test_file.name, 'JPEG')
                        test_file.close()
                        
                        # 进行一次测试识别
                        test_start = time.time()
                        test_result = ocr_service.extract_text(test_file.name, use_preprocess=False)
                        test_elapsed = time.time() - test_start
                        
                        logger.info(f"[启动] ✅ OCR测试识别成功，耗时: {test_elapsed:.1f}秒")
                        print(f"✅ OCR测试识别成功！测试耗时: {test_elapsed:.1f}秒")
                        
                        # 清理测试文件
                        try:
                            os.unlink(test_file.name)
                        except:
                            pass
                    except Exception as test_error:
                        logger.warning(f"[启动] OCR测试识别失败，但服务已初始化: {test_error}")
                        print(f"⚠️ OCR测试识别失败，但服务已初始化（可能不影响使用）")
                else:
                    print("   💡 提示: 已跳过测试识别（设置 PRELOAD_OCR_TEST=true 可启用测试）")
            else:
                logger.warning(f"[启动] ⚠️ OCR服务初始化失败或未找到OCR引擎")
                print(f"⚠️ OCR服务初始化失败或未找到OCR引擎（耗时: {elapsed_init:.1f}秒）")
                print("   提示: 首次请求时可能会自动重试")
                
        except Exception as e:
            logger.warning(f"[启动] OCR服务预加载失败: {e}")
            print(f"⚠️ OCR服务预加载失败: {e}")
            print("   提示: 将在首次请求时尝试初始化")
            import traceback
            logger.debug(f"OCR预加载错误详情: {traceback.format_exc()}")
    else:
        logger.info("[启动] 跳过OCR服务预加载（PRELOAD_OCR=false）")
        print("\n" + "=" * 60)
        print("⏭️  跳过OCR服务预加载（PRELOAD_OCR=false）")
        print("=" * 60)
        print("   提示: OCR服务将在首次请求时初始化")
    
    print("\n" + "=" * 60)
    print("Flask服务启动中...")
    print("=" * 60)
    print("API地址: http://localhost:5000")
    print("测试接口: GET http://localhost:5000/api/test")
    print("健康检查: GET http://localhost:5000/api/health")
    print("统计接口: GET http://localhost:5000/api/stats")
    print("分析接口: POST http://localhost:5000/api/questions/analyze")
    print("测试脚本: python test_api_v2.py")
    print("=" * 60)
    print("\n提示: 服务已启动，等待请求...")
    print("   发送请求后才会看到详细日志\n")
    
    app.run(debug=True, port=5000)

