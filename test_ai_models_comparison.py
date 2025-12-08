"""
测试多个AI服务的各种模型
统一使用本地OCR，然后将OCR文字发送给各AI模型提取题目和选项
测试指标：准确率、速度、费用、token数量
"""
import os
import json
import sys
import time
import re
from typing import Dict, List, Optional
from statistics import mean
from openai import OpenAI
import requests

# 修复Windows控制台编码问题
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 加载环境变量
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ==================== AI服务配置 ====================

# 阿里云（通义千问）配置
ALIBABA_API_KEY = 'sk-52e5c7f48ecb429e9d4569ec19e47223'
ALIBABA_API_BASE = 'https://dashscope.aliyuncs.com/compatible-mode/v1'

# DeepSeek配置
DEEPSEEK_API_KEY = 'sk-7de12481a17045819fcf3a2838d884a1'
DEEPSEEK_API_BASE = 'https://api.deepseek.com/v1'

# 火山引擎配置（需要从环境变量或配置文件获取）
VOLCENGINE_API_KEY = os.getenv('VOLCENGINE_API_KEY', 'bebcec52-ce96-4f6f-bb1e-9a1b49ad5cf8')
VOLCENGINE_API_BASE = 'https://ark.cn-beijing.volces.com/api/v3'

# ==================== 模型列表 ====================

# 阿里云通义千问模型列表
ALIBABA_MODELS = [
    'qwen-turbo',           # 速度快，成本低
    'qwen-plus',            # 平衡版
    'qwen-max',             # 最强性能
    'qwen-max-longcontext', # 长文本版
    'qwen-long',            # 超长文本版（支持千万字）
]

# DeepSeek模型列表
DEEPSEEK_MODELS = [
    'deepseek-chat',        # 标准版
    'deepseek-reasoner',    # 推理版（不使用思考模式）
]

# 火山引擎豆包模型列表
# 注意：火山引擎文本模型需要通过接入点ID（ep-xxxxxx）调用
# 可以通过环境变量 VOLCENGINE_ENDPOINT_IDS 配置，用逗号分隔多个接入点ID
# 例如：VOLCENGINE_ENDPOINT_IDS=ep-20251207111153-rxbqb,ep-xxxxxx
# 如果没有配置环境变量，使用默认的接入点ID
volcengine_endpoint_ids = os.getenv('VOLCENGINE_ENDPOINT_IDS', '').strip()
if volcengine_endpoint_ids:
    VOLCENGINE_MODELS = [ep.strip() for ep in volcengine_endpoint_ids.split(',') if ep.strip().startswith('ep-')]
else:
    # 默认接入点ID（用户提供的示例）
    VOLCENGINE_MODELS = ['ep-20251207111153-rxbqb']  # 默认接入点，用户可添加更多

# ==================== 价格配置（元/千token） ====================

PRICING = {
    'qwen-turbo': {'input': 0.0003, 'output': 0.0006},
    'qwen-plus': {'input': 0.0008, 'output': 0.002},
    'qwen-max': {'input': 0.02, 'output': 0.06},
    'qwen-max-longcontext': {'input': 0.0005, 'output': 0.002},
    'qwen-long': {'input': 0.0003, 'output': 0.0012},  # 超长文本版
    'deepseek-chat': {'input': 0.00014, 'output': 0.00056},
    'deepseek-reasoner': {'input': 0.00055, 'output': 0.002},
    # 火山引擎模型价格（根据接入点ID对应的实际模型定价）
    'ep-20251207111153-rxbqb': {'input': 0.001, 'output': 0.004},  # 示例价格，需要根据实际模型确认
}

# ==================== 工具函数 ====================

def load_test_images(max_images=None):
    """加载测试图片"""
    ceshi_dir = 'uploads/ceshi'
    if not os.path.exists(ceshi_dir):
        print(f"⚠️  错误: 测试目录不存在: {ceshi_dir}")
        return []
    
    images = []
    for file in sorted(os.listdir(ceshi_dir)):
        if file.lower().endswith(('.png', '.jpg', '.jpeg')):
            # 跳过预处理文件
            if '_preprocessed' not in file.lower():
                full_path = os.path.join(ceshi_dir, file)
                if os.path.exists(full_path):
                    images.append(full_path)
                    if max_images and len(images) >= max_images:
                        break
    
    return images

def preprocess_ocr_text(raw_text: str) -> str:
    """快速预处理OCR文本，过滤明显的界面元素"""
    if not raw_text:
        return raw_text
    
    lines = raw_text.split('\n')
    filtered_lines = []
    
    # 严格的界面元素关键词
    strict_interface_keywords = [
        'KB/s', '首页', '朋友', '消息', '我', '拍同', '点击推荐',
        '粉笔正确率', '华图正确率', '答案一样', '解析在作品', '解析在作品简',
        '展开', '收起', '分享', '点赞', '收藏', '评论',
        '@公考行测每日一练', '公考行测每日一练的橱窗',
        '橱窗|', '点击推荐', '祝各位国考', '行测80', '申论85',
        'Never give up'
    ]
    
    option_markers = ['A.', 'B.', 'C.', 'D.', 'E.', 'F.', 'A ', 'B ', 'C ', 'D ']
    question_keywords = ['这段文字', '意在说明', '根据', '以下', '题目', '题干']
    
    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue
        
        # 跳过明确的界面元素
        is_interface = any(keyword in line_stripped for keyword in strict_interface_keywords)
        if is_interface:
            continue
        
        # 保留选项标记
        has_option_marker = any(line_stripped.startswith(marker) for marker in option_markers)
        if has_option_marker:
            filtered_lines.append(line_stripped)
            continue
        
        # 保留题干关键词
        has_question_keyword = any(keyword in line_stripped for keyword in question_keywords)
        if has_question_keyword:
            filtered_lines.append(line_stripped)
            continue
        
        # 保留较长的文本行
        if len(line_stripped) > 3:
            if len(line_stripped) > 10 or any(p in line_stripped for p in ['。', '，', '、', '；', '？', '：']):
                filtered_lines.append(line_stripped)
    
    return '\n'.join(filtered_lines)

def get_ocr_text(image_path: str) -> Dict:
    """统一使用本地OCR获取文字"""
    from ocr_service import get_ocr_service
    ocr_service = get_ocr_service()
    
    if not ocr_service.ocr_engine:
        return {'success': False, 'error': 'OCR不可用'}
    
    start = time.time()
    raw_text = ocr_service.extract_text(image_path)
    elapsed = time.time() - start
    
    if raw_text:
        return {
            'success': True,
            'raw_text': raw_text,
            'time': elapsed,
            'char_count': len(raw_text)
        }
    else:
        return {'success': False, 'error': 'OCR未识别到文字', 'time': elapsed}

def call_ai_model(provider: str, model: str, ocr_text: str) -> Dict:
    """
    调用AI模型提取题目和选项
    
    Args:
        provider: 'alibaba', 'deepseek', 'volcengine'
        model: 模型名称
        ocr_text: OCR识别的文字
    
    Returns:
        dict: {
            'success': bool,
            'question_text': str,
            'options': List[str],
            'time': float,
            'input_tokens': int,
            'output_tokens': int,
            'cost': float,
            'raw_response': str
        }
    """
    # 预处理OCR文字
    preprocessed_text = preprocess_ocr_text(ocr_text)[:3000]  # 限制长度
    
    # 构建提示词（简短、明确、快速）
    prompt = f"""从以下OCR识别文字中提取题目和选项，忽略所有界面元素。

OCR文字：
{preprocessed_text}

要求：
1. 只提取题目内容和选项
2. 题干必须完整，包括所有段落内容
3. 选项必须以"A. "、"B. "、"C. "、"D. "开头
4. 不要包含界面元素

返回JSON格式（只返回JSON，不要其他文字）：
{{
    "question_text": "完整的题干内容",
    "options": ["A. 选项A", "B. 选项B", "C. 选项C", "D. 选项D"]
}}"""
    
    start_time = time.time()
    
    try:
        if provider == 'alibaba':
            return _call_alibaba_api(model, prompt, start_time)
        elif provider == 'deepseek':
            return _call_deepseek_api(model, prompt, start_time)
        elif provider == 'volcengine':
            return _call_volcengine_api(model, prompt, start_time)
        else:
            return {'success': False, 'error': f'未知服务: {provider}'}
    except Exception as e:
        elapsed = time.time() - start_time
        return {
            'success': False,
            'error': str(e)[:100],
            'time': elapsed
        }

def _call_alibaba_api(model: str, prompt: str, start_time: float) -> Dict:
    """调用阿里云通义千问API（禁用思考模式）"""
    client = OpenAI(api_key=ALIBABA_API_KEY, base_url=ALIBABA_API_BASE)
    
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "你是一个专业的题目提取助手，擅长从OCR文字中准确提取完整的题目和选项。只返回JSON格式。"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.1,
        max_tokens=1500,
        timeout=20,
        extra_body={"enable_thinking": False}  # 禁用思考模式
    )
    
    elapsed = time.time() - start_time
    content = response.choices[0].message.content.strip()
    
    # 统计token
    input_tokens = response.usage.prompt_tokens if hasattr(response, 'usage') else 0
    output_tokens = response.usage.completion_tokens if hasattr(response, 'usage') else 0
    
    # 计算费用
    pricing = PRICING.get(model, {'input': 0, 'output': 0})
    cost = (input_tokens / 1000 * pricing['input']) + (output_tokens / 1000 * pricing['output'])
    
    # 解析JSON
    json_match = re.search(r'\{[\s\S]*\}', content)
    if json_match:
        result = json.loads(json_match.group())
        question_text = result.get('question_text', '').strip()
        options = result.get('options', [])
        
        # 格式化选项
        formatted_options = []
        for i, opt in enumerate(options):
            opt_str = str(opt).strip()
            if not re.match(r'^[A-F]\.?\s', opt_str):
                opt_str = f"{chr(65+i)}. {opt_str}"
            formatted_options.append(opt_str)
        
        return {
            'success': True,
            'question_text': question_text,
            'options': formatted_options,
            'time': elapsed,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'total_tokens': input_tokens + output_tokens,
            'cost': cost,
            'raw_response': content
        }
    else:
        return {
            'success': False,
            'error': 'JSON解析失败',
            'time': elapsed,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'cost': cost,
            'raw_response': content
        }

def _call_deepseek_api(model: str, prompt: str, start_time: float) -> Dict:
    """调用DeepSeek API（禁用思考模式）"""
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_API_BASE)
    
    # 禁用思考模式（包括deepseek-reasoner）
    extra_body = {"thinking": {"type": "disabled"}} if model == "deepseek-reasoner" else {}
    
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "你是一个专业的题目提取助手，擅长从OCR文字中准确提取完整的题目和选项。只返回JSON格式。"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.1,
        max_tokens=1500,
        timeout=20,
        **({"extra_body": extra_body} if extra_body else {})  # 仅当需要时添加extra_body
    )
    
    elapsed = time.time() - start_time
    content = response.choices[0].message.content.strip()
    
    # 统计token
    input_tokens = response.usage.prompt_tokens if hasattr(response, 'usage') else 0
    output_tokens = response.usage.completion_tokens if hasattr(response, 'usage') else 0
    
    # 计算费用
    pricing = PRICING.get(model, {'input': 0, 'output': 0})
    cost = (input_tokens / 1000 * pricing['input']) + (output_tokens / 1000 * pricing['output'])
    
    # 解析JSON
    json_match = re.search(r'\{[\s\S]*\}', content)
    if json_match:
        result = json.loads(json_match.group())
        question_text = result.get('question_text', '').strip()
        options = result.get('options', [])
        
        # 格式化选项
        formatted_options = []
        for i, opt in enumerate(options):
            opt_str = str(opt).strip()
            if not re.match(r'^[A-F]\.?\s', opt_str):
                opt_str = f"{chr(65+i)}. {opt_str}"
            formatted_options.append(opt_str)
        
        return {
            'success': True,
            'question_text': question_text,
            'options': formatted_options,
            'time': elapsed,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'total_tokens': input_tokens + output_tokens,
            'cost': cost,
            'raw_response': content
        }
    else:
        return {
            'success': False,
            'error': 'JSON解析失败',
            'time': elapsed,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'cost': cost,
            'raw_response': content
        }

def _call_volcengine_api(model: str, prompt: str, start_time: float) -> Dict:
    """调用火山引擎豆包API（使用OpenAI兼容的chat/completions端点）"""
    url = f"{VOLCENGINE_API_BASE}/chat/completions"
    
    # 使用OpenAI兼容的格式
    data = {
        "model": model,  # 接入点ID
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "max_tokens": 4096,
        "temperature": 0.3
        # 不使用思考模式，所以不设置 reasoning_effort 参数
    }
    
    headers = {
        'Authorization': f'Bearer {VOLCENGINE_API_KEY}',
        'Content-Type': 'application/json'
    }
    
    response = requests.post(url, json=data, headers=headers, timeout=30)
    elapsed = time.time() - start_time
    
    if response.status_code != 200:
        error_text = response.text[:200] if response.text else '未知错误'
        return {
            'success': False,
            'error': f'HTTP {response.status_code}: {error_text}',
            'time': elapsed
        }
    
    result = response.json()
    
    # 提取内容（OpenAI兼容格式）
    content = ''
    if 'choices' in result and len(result['choices']) > 0:
        choice = result['choices'][0]
        if 'message' in choice and 'content' in choice['message']:
            content = choice['message']['content'].strip()
    
    # 统计token
    input_tokens = 0
    output_tokens = 0
    if 'usage' in result:
        usage = result['usage']
        input_tokens = usage.get('prompt_tokens', usage.get('input_tokens', 0))
        output_tokens = usage.get('completion_tokens', usage.get('output_tokens', 0))
    
    # 计算费用（火山引擎价格需要根据实际模型确定）
    pricing = PRICING.get(model, {'input': 0.001, 'output': 0.004})  # 默认价格
    cost = (input_tokens / 1000 * pricing['input']) + (output_tokens / 1000 * pricing['output'])
    
    # 解析JSON
    if content:
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            try:
                parsed = json.loads(json_match.group())
                question_text = parsed.get('question_text', '').strip()
                options = parsed.get('options', [])
                
                # 格式化选项
                formatted_options = []
                for i, opt in enumerate(options):
                    opt_str = str(opt).strip()
                    if not re.match(r'^[A-F]\.?\s', opt_str):
                        opt_str = f"{chr(65+i)}. {opt_str}"
                    formatted_options.append(opt_str)
                
                return {
                    'success': True,
                    'question_text': question_text,
                    'options': formatted_options,
                    'time': elapsed,
                    'input_tokens': input_tokens,
                    'output_tokens': output_tokens,
                    'total_tokens': input_tokens + output_tokens,
                    'cost': cost,
                    'raw_response': content
                }
            except Exception as e:
                # 如果JSON解析失败，尝试直接提取
                pass
    
    return {
        'success': False,
        'error': '解析失败',
        'time': elapsed,
        'input_tokens': input_tokens,
        'output_tokens': output_tokens,
        'cost': cost,
        'raw_response': content or str(result)[:500]
    }

def evaluate_result(result: Dict) -> Dict:
    """评估提取结果的质量"""
    if not result.get('success'):
        return {
            'has_question': False,
            'has_options': False,
            'options_count': 0,
            'score': 0.0
        }
    
    question_text = result.get('question_text', '').strip()
    options = result.get('options', [])
    
    has_question = len(question_text) > 10
    has_options = len(options) >= 2
    options_count = len(options)
    
    # 评分（0-1）
    score = 0.0
    if has_question:
        score += 0.5
    if has_options:
        score += 0.3
    if 2 <= options_count <= 6:
        score += 0.2
    
    return {
        'has_question': has_question,
        'has_options': has_options,
        'options_count': options_count,
        'score': score,
        'question_length': len(question_text)
    }

def main():
    print("="*70)
    print("🚀 多AI服务模型对比测试")
    print("="*70)
    print("\n测试配置：")
    print("  1. 统一使用本地OCR（PaddleOCR）")
    print("  2. OCR文字发送给各AI模型提取题目和选项")
    print("  3. 测试指标：准确率、速度、费用、token数量")
    print("  4. 不使用思考模式，只提取题目和选项\n")
    
    # 初始化OCR
    print("📦 正在初始化PaddleOCR模型...")
    try:
        from ocr_service import get_ocr_service
        load_start = time.time()
        ocr_service = get_ocr_service()
        load_time = time.time() - load_start
        
        if not ocr_service.ocr_engine:
            print("❌ 本地OCR不可用（PaddleOCR未安装）")
            return
        else:
            print(f"✅ OCR已就绪，加载耗时: {load_time:.2f}秒\n")
    except Exception as e:
        print(f"❌ OCR初始化失败: {e}")
        return
    
    # 加载测试图片
    test_images = load_test_images(max_images=None)
    if not test_images:
        print("❌ 未找到测试图片")
        return
    
    print(f"📷 找到 {len(test_images)} 张测试图片\n")
    
    # 显示AI服务配置状态
    print("🔧 AI服务配置状态:")
    print(f"   ✅ 阿里云: {len(ALIBABA_MODELS)} 个模型")
    print(f"   ✅ DeepSeek: {len(DEEPSEEK_MODELS)} 个模型")
    if VOLCENGINE_MODELS:
        print(f"   ✅ 火山引擎: {len(VOLCENGINE_MODELS)} 个接入点")
    else:
        print(f"   ⚠️  火山引擎: 未配置接入点ID（将在测试时跳过）")
        print(f"      提示: 设置环境变量 VOLCENGINE_ENDPOINT_IDS=ep-xxxxxx 以启用火山引擎测试")
    print()
    
    # 定义要测试的模型配置
    test_configs = []
    
    # 阿里云模型
    for model in ALIBABA_MODELS:
        test_configs.append({
            'provider': 'alibaba',
            'model': model,
            'name': f'阿里云-{model}'
        })
    
    # DeepSeek模型
    for model in DEEPSEEK_MODELS:
        test_configs.append({
            'provider': 'deepseek',
            'model': model,
            'name': f'DeepSeek-{model}'
        })
    
    # 火山引擎模型
    for model in VOLCENGINE_MODELS:
        test_configs.append({
            'provider': 'volcengine',
            'model': model,
            'name': f'火山引擎-{model}'
        })
    
    print(f"📊 将测试 {len(test_configs)} 个AI模型配置\n")
    
    # 存储所有结果
    all_results = {}
    
    # 对每张图片进行测试
    for img_idx, img_path in enumerate(test_images, 1):
        image_name = os.path.basename(img_path)
        print(f"\n{'='*70}")
        print(f"📷 图片 {img_idx}/{len(test_images)}: {image_name}")
        print(f"{'='*70}\n")
        
        # 第一步：OCR识别（只执行一次）
        print("⏳ 步骤1: OCR识别中...")
        ocr_result = get_ocr_text(img_path)
        
        if not ocr_result.get('success'):
            print(f"❌ OCR识别失败: {ocr_result.get('error')}\n")
            continue
        
        raw_text = ocr_result.get('raw_text', '')
        print(f"✅ OCR识别成功 - 耗时: {ocr_result['time']:.2f}秒")
        print(f"📊 OCR识别字符数: {len(raw_text)} 字符\n")
        
        # 显示OCR内容（简要）
        print("📝 OCR识别内容（前200字符）:")
        print(f"{raw_text[:200]}...\n")
        
        # 第二步：使用各个AI模型提取
        for config_idx, config in enumerate(test_configs, 1):
            provider = config['provider']
            model = config['model']
            config_name = config['name']
            
            print(f"  [{config_idx}/{len(test_configs)}] 测试 {config_name}...", end=' ', flush=True)
            
            try:
                ai_result = call_ai_model(provider, model, raw_text)
                
                if ai_result.get('success'):
                    eval_result = evaluate_result(ai_result)
                    print(f"✅ 成功")
                    print(f"     耗时: {ai_result['time']:.2f}秒")
                    print(f"     题目长度: {eval_result['question_length']} 字符")
                    print(f"     选项数: {eval_result['options_count']}")
                    print(f"     评分: {eval_result['score']:.2f}")
                    print(f"     Token: {ai_result.get('total_tokens', 0)} (输入:{ai_result.get('input_tokens', 0)}, 输出:{ai_result.get('output_tokens', 0)})")
                    print(f"     费用: ¥{ai_result.get('cost', 0):.6f}")
                    print(f"\n     📝 识别结果:")
                    question_text = ai_result.get('question_text', '').strip()
                    if question_text:
                        print(f"     题目: {question_text}")
                    options = ai_result.get('options', [])
                    if options:
                        print(f"     选项:")
                        for opt in options:
                            print(f"       {opt}")
                    
                    # 保存结果
                    key = f"{image_name}|{config_name}"
                    all_results[key] = {
                        'image_name': image_name,
                        'provider': provider,
                        'model': model,
                        'config_name': config_name,
                        'ocr_time': ocr_result['time'],
                        'ai_time': ai_result['time'],
                        'total_time': ocr_result['time'] + ai_result['time'],
                        'question_text': ai_result.get('question_text', ''),
                        'options': ai_result.get('options', []),
                        'options_count': eval_result['options_count'],
                        'score': eval_result['score'],
                        'input_tokens': ai_result.get('input_tokens', 0),
                        'output_tokens': ai_result.get('output_tokens', 0),
                        'total_tokens': ai_result.get('total_tokens', 0),
                        'cost': ai_result.get('cost', 0),
                        'success': True
                    }
                else:
                    print(f"❌ 失败: {ai_result.get('error', 'unknown')}")
                    key = f"{image_name}|{config_name}"
                    all_results[key] = {
                        'image_name': image_name,
                        'provider': provider,
                        'model': model,
                        'config_name': config_name,
                        'ocr_time': ocr_result['time'],
                        'ai_time': ai_result.get('time', 0),
                        'total_time': ocr_result['time'] + ai_result.get('time', 0),
                        'error': ai_result.get('error', 'unknown'),
                        'success': False
                    }
            except Exception as e:
                print(f"❌ 异常: {str(e)[:50]}")
                key = f"{image_name}|{config_name}"
                all_results[key] = {
                    'image_name': image_name,
                    'provider': provider,
                    'model': model,
                    'config_name': config_name,
                    'error': str(e)[:100],
                    'success': False
                }
            
            print()  # 空行分隔
    
    # 打印统计总结
    print(f"\n{'='*70}")
    print("📊 测试结果统计总结")
    print(f"{'='*70}\n")
    
    # 按模型分组统计
    model_stats = {}
    for key, result in all_results.items():
        config_name = result['config_name']
        if config_name not in model_stats:
            model_stats[config_name] = {
                'results': [],
                'provider': result.get('provider', 'unknown'),
                'model': result.get('model', 'unknown')
            }
        model_stats[config_name]['results'].append(result)
    
    # 打印每个模型的统计
    print("各模型测试结果:\n")
    
    for config_name in sorted(model_stats.keys()):
        stats = model_stats[config_name]
        results = stats['results']
        success_results = [r for r in results if r.get('success')]
        
        if not success_results:
            print(f"❌ {config_name}: 全部失败")
            continue
        
        success_rate = len(success_results) / len(results) * 100
        avg_time = mean([r['total_time'] for r in success_results])
        avg_score = mean([r.get('score', 0) for r in success_results])
        avg_tokens = mean([r.get('total_tokens', 0) for r in success_results])
        total_cost = sum([r.get('cost', 0) for r in success_results])
        avg_cost = total_cost / len(success_results) if success_results else 0
        
        print(f"📊 {config_name}:")
        print(f"   成功率: {success_rate:.1f}% ({len(success_results)}/{len(results)})")
        print(f"   平均耗时: {avg_time:.2f}秒")
        print(f"   平均评分: {avg_score:.2f}")
        print(f"   平均Token: {avg_tokens:.0f}")
        print(f"   平均费用: ¥{avg_cost:.6f}/次")
        print()
    
    # 打印详细的识别内容对比
    print(f"\n{'='*70}")
    print("📝 各模型识别内容详细对比")
    print(f"{'='*70}\n")
    
    for img_idx, img_path in enumerate(test_images, 1):
        image_name = os.path.basename(img_path)
        print(f"\n📷 图片 {img_idx}/{len(test_images)}: {image_name}")
        print("="*70)
        
        # 按模型分组显示结果
        for config in test_configs:
            config_name = config['name']
            key = f"{image_name}|{config_name}"
            result = all_results.get(key)
            
            if not result:
                continue
                
            if result.get('success'):
                print(f"\n【{config_name}】")
                question_text = result.get('question_text', '').strip()
                if question_text:
                    print(f"题目: {question_text}")
                options = result.get('options', [])
                if options:
                    print("选项:")
                    for opt in options:
                        print(f"  {opt}")
                print(f"耗时: {result.get('ai_time', 0):.2f}秒 | Token: {result.get('total_tokens', 0)} | 费用: ¥{result.get('cost', 0):.6f}")
            else:
                print(f"\n【{config_name}】❌ 失败: {result.get('error', 'unknown')}")
        
        print("\n" + "-"*70)
    
    print(f"\n{'='*70}")
    print("✅ 测试完成")
    print(f"{'='*70}\n")

if __name__ == '__main__':
    main()
