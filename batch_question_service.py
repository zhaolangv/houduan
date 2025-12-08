"""
批量题目处理服务 - 使用本地OCR + DeepSeek，支持高并发
专门用于快速批量处理50+道题
"""
import os
import json
import re
import time
import logging
from typing import Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI
from io import BytesIO
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

# DeepSeek 配置
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', 'sk-7de12481a17045819fcf3a2838d884a1')
DEEPSEEK_API_BASE = 'https://api.deepseek.com/v1'
MODEL = 'deepseek-chat'

# 价格配置（元/千token）
DEEPSEEK_PRICING = {'input': 0.00014, 'output': 0.00056}


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


def get_ocr_text(image_path_or_file, use_preprocess=True) -> Dict:
    """
    统一使用本地OCR获取文字
    
    Args:
        image_path_or_file: 图片文件对象或路径
        use_preprocess: 是否使用图片预处理（默认True，批量处理时可设为False提高速度）
    """
    import logging
    logger = logging.getLogger(__name__)
    
    from ocr_service import get_ocr_service
    ocr_service = get_ocr_service()
    
    if not ocr_service.ocr_engine:
        logger.warning("[OCR] ⚠️ OCR引擎不可用")
        return {'success': False, 'error': 'OCR不可用'}
    
    start = time.time()
    
    # 获取文件名用于日志
    if hasattr(image_path_or_file, 'name'):
        file_name = image_path_or_file.name
    elif isinstance(image_path_or_file, str):
        file_name = os.path.basename(image_path_or_file)
    else:
        file_name = '未知'
    
    logger.debug(f"[OCR] 🔍 开始OCR识别: {file_name}, 预处理={'是' if use_preprocess else '否'}")
    
    # 处理文件对象或路径
    if hasattr(image_path_or_file, 'read'):
        # 是文件对象，需要先保存到临时文件
        import tempfile
        temp_path = None
        try:
            image_path_or_file.seek(0)
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
                tmp_file.write(image_path_or_file.read())
                temp_path = tmp_file.name
            
            raw_text = ocr_service.extract_text(temp_path, use_preprocess=use_preprocess)
            elapsed = time.time() - start
        finally:
            # 清理临时文件
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except:
                    pass
    else:
        # 是文件路径
        raw_text = ocr_service.extract_text(image_path_or_file, use_preprocess=use_preprocess)
        elapsed = time.time() - start
    
    elapsed_total = time.time() - start
    
    if raw_text:
        char_count = len(raw_text)
        logger.info(f"[OCR] ✅ OCR识别成功: {file_name}, 提取到 {char_count} 字符, 耗时={elapsed_total:.2f}秒")
        logger.debug(f"[OCR] 📝 OCR文本预览（前100字符）: {raw_text[:100]}...")
        return {
            'success': True,
            'raw_text': raw_text,
            'time': elapsed_total,
            'char_count': char_count
        }
    else:
        logger.warning(f"[OCR] ⚠️ OCR未识别到文字: {file_name}, 耗时={elapsed_total:.2f}秒")
        return {'success': False, 'error': 'OCR未识别到文字', 'time': elapsed_total}


def call_deepseek_extract(ocr_text: str, include_classification: bool = True) -> Dict:
    """
    调用DeepSeek提取题目和选项，同时进行分类和初步答案提取
    
    Args:
        ocr_text: OCR识别的文本
        include_classification: 是否包含分类和初步答案（默认True）
    
    Returns:
        Dict: 包含题目、选项、分类、初步答案等信息
    """
    import logging
    logger = logging.getLogger(__name__)
    
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_API_BASE)
    
    # 预处理OCR文本
    preprocessed_text = preprocess_ocr_text(ocr_text)[:3000]  # 限制长度
    
    logger.info(f"[AI] 🤖 准备调用DeepSeek API提取题目")
    logger.debug(f"[AI] 📝 OCR文本长度: {len(ocr_text)}字符, 预处理后: {len(preprocessed_text)}字符")
    
    if include_classification:
        # 提示词（包含分类和初步答案）
        prompt = f"""从以下OCR识别文字中提取题目和选项，并进行分类和初步答案分析，忽略所有界面元素。

OCR文字：
{preprocessed_text}

要求：
1. 提取完整的题目内容和选项
2. 题干必须完整，包括所有段落内容
3. 选项必须以"A. "、"B. "、"C. "、"D. "开头
4. 判断题目类型：行测(言语理解、数量关系、判断推理、资料分析、常识判断) 或 申论
5. 给出初步答案（A/B/C/D）和简要理由
6. 不要包含界面元素

返回JSON格式（只返回JSON，不要其他文字）：
{{
    "question_text": "完整的题干内容",
    "options": ["A. 选项A", "B. 选项B", "C. 选项C", "D. 选项D"],
    "question_type": "行测-言语理解" 或 "行测-数量关系" 或 "申论" 等,
    "preliminary_answer": "B",
    "answer_reason": "简要的理由说明"
}}"""
    else:
        # 提示词（仅提取题目和选项，不分类）
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
    api_request_start = time.time()
    
    # 记录API请求信息
    logger.info(f"[AI] 🚀 开始调用DeepSeek API (模型: {MODEL})")
    logger.info(f"[AI] 📋 API信息: provider=DeepSeek, model={MODEL}, base_url={DEEPSEEK_API_BASE}")
    logger.info(f"[AI] 📝 请求参数: prompt长度={len(prompt)}字符, include_classification={include_classification}, max_tokens={2000 if include_classification else 1500}, temperature=0.1")
    
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system", 
                    "content": "你是一个专业的题目提取和分析助手，擅长从OCR文字中准确提取完整的题目和选项，并进行题目分类和初步答案分析。只返回JSON格式。"
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=2000 if include_classification else 1500,
            timeout=30
        )
        
        api_request_time = time.time() - api_request_start
        elapsed = time.time() - start_time
        content = response.choices[0].message.content.strip()
        
        # 统计token和费用
        input_tokens = response.usage.prompt_tokens if hasattr(response, 'usage') else 0
        output_tokens = response.usage.completion_tokens if hasattr(response, 'usage') else 0
        total_tokens = input_tokens + output_tokens
        cost = (input_tokens / 1000 * DEEPSEEK_PRICING['input']) + (output_tokens / 1000 * DEEPSEEK_PRICING['output'])
        
        # 记录API响应信息
        response_length = len(content) if content else 0
        logger.info(f"[AI] ✅ DeepSeek API调用成功")
        logger.info(f"[AI] ⏱️  耗时统计: API请求={api_request_time:.2f}秒, 总计={elapsed:.2f}秒")
        logger.info(f"[AI] 📊 响应统计: 内容长度={response_length}字符, prompt_tokens={input_tokens}, completion_tokens={output_tokens}, total_tokens={total_tokens}")
        logger.info(f"[AI] 💰 费用: ¥{cost:.6f}")
        if response_length > 0:
            logger.debug(f"[AI] 📝 响应内容预览（前300字符）:\n{content[:300]}...")
        
        # 解析JSON
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            try:
                parsed_result = json.loads(json_match.group())
                question_text = parsed_result.get('question_text', '').strip()
                options = parsed_result.get('options', [])
                
                # 格式化选项
                formatted_options = []
                for i, opt in enumerate(options):
                    opt_str = str(opt).strip()
                    if not re.match(r'^[A-F]\.?\s', opt_str):
                        opt_str = f"{chr(65+i)}. {opt_str}"
                    formatted_options.append(opt_str)
                
                result = {
                    'success': True,
                    'question_text': question_text,
                    'options': formatted_options,
                    'time': elapsed,
                    'input_tokens': input_tokens,
                    'output_tokens': output_tokens,
                    'total_tokens': total_tokens,
                    'cost': cost
                }
                
                # 如果有分类和初步答案信息，添加到结果中
                if include_classification:
                    result['question_type'] = parsed_result.get('question_type', 'TEXT')
                    result['preliminary_answer'] = parsed_result.get('preliminary_answer', '')
                    result['answer_reason'] = parsed_result.get('answer_reason', '')
                
                logger.info(f"[AI] ✅ 题目提取成功: 题干长度={len(question_text)}字符, 选项数={len(formatted_options)}, 类型={result.get('question_type', 'N/A')}")
                
                return result
            except json.JSONDecodeError as e:
                return {
                    'success': False,
                    'error': f'JSON解析失败: {str(e)}',
                    'time': elapsed,
                    'total_tokens': total_tokens,
                    'cost': cost,
                    'raw_response': content[:500]
                }
        else:
            return {
                'success': False,
                'error': '未找到JSON格式响应',
                'time': elapsed,
                'total_tokens': total_tokens,
                'cost': cost,
                'raw_response': content[:500]
            }
    
    except Exception as e:
        elapsed = time.time() - start_time
        api_elapsed = time.time() - api_request_start if 'api_request_start' in locals() else 0
        error_type = type(e).__name__
        error_msg = str(e)
        logger.error(f"[AI] ❌ DeepSeek API调用失败: {error_type}: {error_msg}, API耗时={api_elapsed:.2f}秒, 总计={elapsed:.2f}秒", exc_info=True)
        return {
            'success': False,
            'error': f'API调用失败: {str(e)}',
            'time': elapsed
        }


def check_duplicate_from_ocr_text(ocr_text: str, app=None) -> Dict:
    """
    基于OCR文本检测重复题目，如果找到则直接从题库提取
    
    注意：此函数需要在Flask应用上下文中调用
    
    Args:
        ocr_text: OCR识别的文本
        app: Flask 应用实例（如果不在应用上下文中，需要提供）
    
    Returns:
        Dict: {
            'is_duplicate': bool,  # 是否找到重复题
            'question': Question对象或None,  # 重复的题目对象
            'similarity': float  # 相似度分数
        }
    """
    if not ocr_text or len(ocr_text.strip()) < 10:
        return {'is_duplicate': False, 'question': None, 'similarity': 0.0}
    
    try:
        from flask import has_app_context
        
        # 如果没有应用上下文且有 app 实例，创建应用上下文
        if not has_app_context():
            if app is None:
                logger.warning("[BatchService] 重复检测失败: 无应用上下文且未提供 app 实例")
                return {'is_duplicate': False, 'question': None, 'similarity': 0.0}
            
            with app.app_context():
                return _check_duplicate_in_context(ocr_text)
        else:
            # 已在应用上下文中
            return _check_duplicate_in_context(ocr_text)
            
    except Exception as e:
        logger.warning(f"[BatchService] 重复检测失败: {e}")
        return {'is_duplicate': False, 'question': None, 'similarity': 0.0}


def _check_duplicate_in_context(ocr_text: str) -> Dict:
    """在应用上下文中执行重复检测（优化版本：快速检查）"""
    from question_service_v2 import QuestionService
    from models_v2 import Question
    
    # 快速检查：如果数据库中没有题目，直接跳过
    try:
        question_count = Question.query.count()
        logger.info(f"[BatchService] 🔍 重复检测: 数据库中现有 {question_count} 道题目")
        if question_count == 0:
            logger.info("[BatchService] ⚠️ 数据库为空，跳过重复检测")
            return {'is_duplicate': False, 'question': None, 'similarity': 0.0}
    except Exception as e:
        logger.warning(f"[BatchService] 检查数据库题目数量失败: {e}，继续执行重复检测")
    
    question_service = QuestionService()
    
    # 记录OCR文本长度用于日志
    ocr_text_length = len(ocr_text) if ocr_text else 0
    logger.info(f"[BatchService] 🔍 开始重复检测: OCR文本长度={ocr_text_length}字符, 相似度阈值=0.85")
    
    # 在应用上下文中调用（已优化：只查询最近1000条）
    duplicate_check_start = time.time()
    duplicate_question, similarity = question_service.find_duplicate_by_text_similarity(
        ocr_text, 
        threshold=0.85
    )
    duplicate_check_time = time.time() - duplicate_check_start
    
    if duplicate_question and similarity >= 0.85:
        logger.info(f"[BatchService] ✅ 检测到重复题目: ID={duplicate_question.id}, 相似度={similarity:.3f}, 检测耗时={duplicate_check_time:.2f}秒")
        return {
            'is_duplicate': True,
            'question': duplicate_question,
            'similarity': similarity
        }
    
    logger.info(f"[BatchService] ℹ️ 未发现重复题目 (相似度={similarity:.3f if similarity else 0.0:.3f}, 阈值=0.85, 检测耗时={duplicate_check_time:.2f}秒)")
    return {'is_duplicate': False, 'question': None, 'similarity': similarity or 0.0}


def extract_from_duplicate_question(question, similarity: float) -> Dict:
    """
    从重复题目中提取信息（直接从题库提取，无需OCR和AI）
    
    Args:
        question: Question对象
        similarity: 相似度分数
    
    Returns:
        Dict: 提取结果（格式与process_single_question一致）
    """
    import json
    
    options = question.options
    if isinstance(options, str):
        try:
            options = json.loads(options)
        except:
            options = []
    elif not isinstance(options, list):
        options = []
    
    return {
        'success': True,
        'question_text': question.question_text or '',
        'options': options,
        'raw_text': question.raw_text or '',
        'question_type': question.question_type or 'TEXT',
        'question_id': str(question.id),
        'is_duplicate': True,
        'similarity': similarity,
        'ocr_time': 0,  # 从题库提取，无需OCR
        'ai_time': 0,   # 从题库提取，无需AI
        'total_time': 0.01,  # 几乎瞬间完成
        'input_tokens': 0,
        'output_tokens': 0,
        'total_tokens': 0,
        'cost': 0.0,
        'extraction_method': 'database_cache'  # 标记从数据库提取
    }


def process_single_question(image_file, question_index: int = None, frontend_ocr_text: str = None, app=None) -> Dict:
    """
    处理单道题（一次发送一道题）
    
    注意：此函数在并发线程中调用时，需要 app 参数来创建应用上下文
    
    Args:
        image_file: 图片文件对象或路径
        question_index: 题目索引（用于日志）
        frontend_ocr_text: 前端提供的OCR结果（可选，如果提供则先检测重复）
        app: Flask 应用实例（用于在并发线程中创建应用上下文）
    
    Returns:
        Dict: 处理结果
    """
    import logging
    logger = logging.getLogger(__name__)
    
    index_str = f"题目{question_index+1}" if question_index is not None else "题目"
    question_start_time = time.time()
    
    logger.info(f"[BatchService] 🚀 {index_str}: 开始处理...")
    
    try:
        # 0. 如果前端提供了OCR结果，先检测重复
        if frontend_ocr_text and len(frontend_ocr_text.strip()) >= 10:
            logger.info(f"[BatchService] {index_str}: 🔍 前端提供了OCR结果（{len(frontend_ocr_text)}字符），先检测重复...")
            duplicate_check = check_duplicate_from_ocr_text(frontend_ocr_text, app=app)
            
            if duplicate_check['is_duplicate']:
                logger.info(f"[BatchService] {index_str}: ✅ 检测到重复题，直接从题库提取 (相似度={duplicate_check.get('similarity', 0):.3f})")
                result = extract_from_duplicate_question(
                    duplicate_check['question'],
                    duplicate_check['similarity']
                )
                result['index'] = question_index
                return result
            else:
                logger.info(f"[BatchService] {index_str}: ℹ️ 未检测到重复，继续处理")
        
        # 1. OCR识别（如果前端没有提供，或检测未发现重复）
        ocr_start = time.time()
        
        # 如果前端提供了OCR结果，使用前端的；否则使用本地OCR
        if frontend_ocr_text and len(frontend_ocr_text.strip()) >= 10:
            ocr_result = {
                'success': True,
                'raw_text': frontend_ocr_text,
                'time': 0,  # 前端OCR，时间不计入
                'char_count': len(frontend_ocr_text)
            }
            ocr_time = 0
            logger.info(f"[BatchService] {index_str}: 使用前端OCR结果（{ocr_result['char_count']}字符）")
        else:
            # 使用本地OCR（跳过预处理以提高速度，批量处理时速度优先）
            ocr_result = get_ocr_text(image_file, use_preprocess=False)
            ocr_time = time.time() - ocr_start
        
        if not ocr_result['success']:
            return {
                'success': False,
                'error': f"OCR失败: {ocr_result.get('error')}",
                'ocr_time': ocr_time,
                'ai_time': 0,
                'total_time': ocr_time
            }
        
        # 再次检测重复（使用本地OCR结果）
        if not frontend_ocr_text:  # 如果之前没用前端OCR检测过
            logger.info(f"[BatchService] {index_str}: 🔍 使用本地OCR结果进行重复检测 (OCR文本长度={len(ocr_result.get('raw_text', ''))}字符)...")
            
            # 检查 app 是否可用
            if app is None:
                logger.warning(f"[BatchService] {index_str}: ⚠️ app 参数为 None，跳过数据库去重检测")
            else:
                duplicate_check = check_duplicate_from_ocr_text(ocr_result['raw_text'], app=app)
                if duplicate_check['is_duplicate']:
                    logger.info(f"[BatchService] {index_str}: ✅ 检测到重复题，直接从题库提取 (相似度={duplicate_check.get('similarity', 0):.3f})")
                    result = extract_from_duplicate_question(
                        duplicate_check['question'],
                        duplicate_check['similarity']
                    )
                    result['ocr_time'] = ocr_time  # 保留OCR时间
                    result['index'] = question_index
                    return result
                else:
                    similarity = duplicate_check.get('similarity', 0.0)
                    logger.info(f"[BatchService] {index_str}: ℹ️ 未检测到重复 (最高相似度={similarity:.3f}, 阈值=0.85)，继续AI提取")
        
        # 2. AI提取（单题单请求，包含分类和初步答案）
        ai_result = call_deepseek_extract(ocr_result['raw_text'], include_classification=True)
        
        # 合并结果
        total_time = time.time() - question_start_time
        result = {
            'success': ai_result.get('success', False),
            'ocr_time': ocr_time,
            'ai_time': ai_result.get('time', 0),
            'total_time': total_time
        }
        
        if ai_result.get('success'):
            result.update({
                'question_text': ai_result.get('question_text', ''),
                'options': ai_result.get('options', []),
                'raw_text': ocr_result.get('raw_text', ''),
                'input_tokens': ai_result.get('input_tokens', 0),
                'output_tokens': ai_result.get('output_tokens', 0),
                'total_tokens': ai_result.get('total_tokens', 0),
                'cost': ai_result.get('cost', 0)
            })
            
            # 添加分类和初步答案信息
            if 'question_type' in ai_result:
                result['question_type'] = ai_result.get('question_type', 'TEXT')
            if 'preliminary_answer' in ai_result:
                result['preliminary_answer'] = ai_result.get('preliminary_answer', '')
            if 'answer_reason' in ai_result:
                result['answer_reason'] = ai_result.get('answer_reason', '')
            
            logger.info(f"[BatchService] ✅ {index_str}: 处理成功, 总耗时={total_time:.2f}秒 (OCR={ocr_time:.2f}秒, AI={ai_result.get('time', 0):.2f}秒)")
        else:
            result['error'] = ai_result.get('error', '未知错误')
            logger.warning(f"[BatchService] ❌ {index_str}: 处理失败 - {result['error']}, 总耗时={total_time:.2f}秒")
        
        return result
    
    except Exception as e:
        total_time = time.time() - question_start_time
        error_type = type(e).__name__
        logger.error(f"[BatchService] ❌ {index_str}: 处理异常 - {error_type}: {str(e)}, 耗时={total_time:.2f}秒", exc_info=True)
        return {
            'success': False,
            'error': f'处理异常: {str(e)}',
            'ocr_time': 0,
            'ai_time': 0,
            'total_time': total_time
        }


def process_batch_concurrent(image_files: List, frontend_ocr_texts: List[str] = None, max_workers: int = 10, app=None, progress_callback=None) -> Dict:
    """
    并发批量处理多道题（每道题独立请求）
    
    Args:
        image_files: 图片文件对象或路径列表
        frontend_ocr_texts: 前端提供的OCR结果列表（可选，与image_files一一对应）
        max_workers: 并发数（推荐10-20，50题约2-3分钟）
        app: Flask 应用实例（必需，用于在并发线程中创建应用上下文）
        progress_callback: 进度更新回调函数 callback(completed, total, failed)
    
    Returns:
        Dict: {
            'results': List[Dict],  # 每道题的处理结果
            'total': int,
            'success_count': int,
            'failed_count': int,
            'total_time': float,
            'avg_time_per_question': float,
            'total_cost': float
        }
    """
    if app is None:
        # 尝试从 Flask 获取当前应用
        try:
            from flask import current_app
            app = current_app._get_current_object()
            logger.info("[BatchService] 从 Flask current_app 获取到 app 对象")
        except:
            logger.warning("[BatchService] 警告: 未提供 app 参数，重复检测功能将不可用")
    else:
        logger.info("[BatchService] ✅ 已提供 app 参数，重复检测功能可用")
    
    total_start = time.time()
    results = []
    total_cost = 0.0
    
    logger.info(f"[BatchService] ⚙️ 批量处理参数: {len(image_files)} 张图片, 并发数: {max_workers}, app: {app is not None}")
    
    # 处理前端OCR结果列表
    if frontend_ocr_texts is None:
        frontend_ocr_texts = [None] * len(image_files)
    elif len(frontend_ocr_texts) < len(image_files):
        # 如果前端OCR结果数量不足，用None填充
        frontend_ocr_texts = frontend_ocr_texts + [None] * (len(image_files) - len(frontend_ocr_texts))
    else:
        # 如果前端OCR结果数量过多，截断
        frontend_ocr_texts = frontend_ocr_texts[:len(image_files)]
    
    logger.info(f"[BatchService] 开始批量处理 {len(image_files)} 道题，并发数: {max_workers}")
    if any(ocr for ocr in frontend_ocr_texts if ocr):
        logger.info(f"[BatchService] 其中 {sum(1 for ocr in frontend_ocr_texts if ocr)} 道题提供了前端OCR结果")
    
    # 检查数据库中的题目数量（用于去重检测）
    try:
        if app:
            with app.app_context():
                from models_v2 import Question
                db_question_count = Question.query.count()
                logger.info(f"[BatchService] 📊 数据库状态: 现有 {db_question_count} 道题目，将进行去重检测")
        else:
            logger.warning(f"[BatchService] ⚠️ 未提供 app 参数，无法检查数据库状态，去重检测可能不可用")
    except Exception as e:
        logger.warning(f"[BatchService] ⚠️ 检查数据库状态失败: {e}，去重检测可能受影响")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务（传递 app 参数）
        future_to_idx = {
            executor.submit(process_single_question, img_file, idx, frontend_ocr_texts[idx], app=app): idx
            for idx, img_file in enumerate(image_files)
        }
        
        # 处理结果
        completed = 0
        failed = 0
        processed_count = 0  # 已处理的总数（成功+失败）
        
        logger.info(f"[BatchService] 📋 开始处理 {len(image_files)} 道题目...")
        
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                result = future.result()
                result['index'] = idx
                results.append(result)
                processed_count += 1
                
                if result.get('success'):
                    total_cost += result.get('cost', 0)
                    completed += 1
                    logger.info(
                        f"[BatchService] ✅ 题目{idx+1}/{len(image_files)}: "
                        f"成功 (总耗时:{result.get('total_time', 0):.2f}秒, "
                        f"OCR:{result.get('ocr_time', 0):.2f}秒, "
                        f"AI:{result.get('ai_time', 0):.2f}秒, "
                        f"费用:¥{result.get('cost', 0):.6f})"
                    )
                else:
                    failed += 1
                    logger.warning(
                        f"[BatchService] ❌ 题目{idx+1}/{len(image_files)}: "
                        f"失败 - {result.get('error', 'unknown')}"
                    )
                
                # 更新进度（每次完成一道题后立即更新）
                if progress_callback:
                    try:
                        progress_callback(completed, len(image_files), failed)
                        logger.debug(f"[BatchService] 📊 已调用进度回调: completed={completed}, total={len(image_files)}, failed={failed}")
                    except Exception as e:
                        logger.error(f"[BatchService] ❌ 进度更新回调失败: {e}", exc_info=True)
                else:
                    logger.debug(f"[BatchService] ⚠️ 进度回调函数未提供")
            
            except Exception as e:
                processed_count += 1
                failed += 1
                results.append({
                    'success': False,
                    'index': idx,
                    'error': f'处理异常: {str(e)}',
                    'ocr_time': 0,
                    'ai_time': 0,
                    'total_time': 0
                })
                logger.error(f"[BatchService] ❌ 题目{idx+1}/{len(image_files)}: 异常 - {str(e)}", exc_info=True)
                
                # 更新进度
                if progress_callback:
                    try:
                        progress_callback(completed, len(image_files), failed)
                        logger.debug(f"[BatchService] 📊 已调用进度回调(异常): completed={completed}, total={len(image_files)}, failed={failed}")
                    except Exception as e2:
                        logger.error(f"[BatchService] ❌ 进度更新回调失败(异常): {e2}", exc_info=True)
        
        logger.info(f"[BatchService] 📊 所有题目处理完成: 总计={processed_count}, 成功={completed}, 失败={failed}")
    
    # 按索引排序，保持原始顺序
    results.sort(key=lambda x: x.get('index', 0))
    
    # 🔍 同一批次内的去重检测（处理完成后，检测结果中的重复题目）
    logger.info(f"[BatchService] 🔍 开始检测同一批次内的重复题目...")
    batch_duplicate_count = 0
    
    # 使用与 question_service_v2 相同的文本相似度算法
    from difflib import SequenceMatcher
    
    def normalize_text(text):
        """标准化文本（与 question_service_v2 保持一致）"""
        if not text:
            return ""
        normalized = text.strip().replace('\n', '').replace('\r', '').replace(' ', '')
        normalized = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '', normalized)
        return normalized.lower()
    
    # 处理所有成功的结果
    success_results = [(i, r) for i, r in enumerate(results) if r.get('success')]
    
    if len(success_results) > 1:
        for i, (idx1, result1) in enumerate(success_results):
            if result1.get('is_batch_duplicate'):
                continue  # 已经标记为重复，跳过
            
            question_text1 = result1.get('question_text', '').strip()
            if not question_text1 or len(question_text1) < 10:
                continue
            
            normalized1 = normalize_text(question_text1)
            
            # 与之前的所有题目比较
            for j, (idx2, result2) in enumerate(success_results[:i]):
                if result2.get('is_batch_duplicate'):
                    continue
                
                question_text2 = result2.get('question_text', '').strip()
                if not question_text2 or len(question_text2) < 10:
                    continue
                
                normalized2 = normalize_text(question_text2)
                
                # 使用 SequenceMatcher 计算相似度（与数据库去重方法一致）
                similarity = SequenceMatcher(None, normalized1, normalized2).ratio()
                
                # 相似度阈值 0.85（与数据库去重保持一致）
                if similarity >= 0.85:
                    result1['is_batch_duplicate'] = True
                    result1['duplicate_of_index'] = idx2  # 原始索引（从0开始）
                    result1['duplicate_similarity'] = similarity
                    batch_duplicate_count += 1
                    logger.warning(
                        f"[BatchService] ⚠️ 检测到批次内重复: "
                        f"题目#{idx1+1} 与题目#{idx2+1} 重复 "
                        f"(相似度={similarity:.3f}, 阈值=0.85)"
                    )
                    break  # 找到一个重复即可，跳出内层循环
            else:
                # 没有找到重复，标记为非重复
                result1['is_batch_duplicate'] = False
    
    # 确保所有结果都有 is_batch_duplicate 字段
    for r in results:
        if 'is_batch_duplicate' not in r:
            r['is_batch_duplicate'] = False
    
    if batch_duplicate_count > 0:
        logger.warning(f"[BatchService] ⚠️ 批次内检测到 {batch_duplicate_count} 道重复题目")
    else:
        logger.info(f"[BatchService] ✅ 批次内未发现重复题目")
    
    # 移除index字段
    for r in results:
        if 'index' in r:
            del r['index']
    
    # 统计
    total_time = time.time() - total_start
    success_count = len([r for r in results if r.get('success')])
    failed_count = len(results) - success_count
    
    # 计算平均时间
    success_results = [r for r in results if r.get('success')]
    avg_time = sum([r.get('total_time', 0) for r in success_results]) / success_count if success_count > 0 else 0
    
    # 统计去重信息
    batch_duplicate_info = []
    database_cache_count = 0
    for r in results:
        if r.get('success'):
            if r.get('is_duplicate'):
                database_cache_count += 1
            if r.get('is_batch_duplicate'):
                dup_idx = r.get('duplicate_of_index', -1)
                dup_sim = r.get('duplicate_similarity', 0.0)
                batch_duplicate_info.append(f"题目#{dup_idx+1}重复")
    
    logger.info(f"[BatchService] ✅ 批量处理完成:")
    logger.info(f"   总耗时: {total_time:.1f}秒 ({total_time/60:.1f}分钟)")
    logger.info(f"   成功: {success_count}/{len(results)}")
    logger.info(f"   失败: {failed_count}/{len(results)}")
    logger.info(f"   平均每题: {avg_time:.1f}秒")
    logger.info(f"   总费用: ¥{total_cost:.6f}")
    if database_cache_count > 0:
        logger.info(f"   💾 数据库缓存命中: {database_cache_count} 道题（节省费用和时间）")
    if batch_duplicate_count > 0:
        logger.info(f"   🔍 批次内重复: {batch_duplicate_count} 道题")
    
    # 返回数据结构：包含 results 和 statistics
    return {
        'results': results,
        'total': len(results),
        'success_count': success_count,
        'failed_count': failed_count,
        'total_time': total_time,
        'avg_time_per_question': avg_time,
        'total_cost': total_cost,
        # 同时保留 statistics 字段（兼容文档格式）
        'statistics': {
            'total': len(results),
            'success_count': success_count,
            'failed_count': failed_count,
            'total_time': total_time,
            'avg_time_per_question': avg_time,
            'total_cost': total_cost
        }
    }
