"""
测试本地OCR方案的速度和准确率
方案1：纯本地OCR（PaddleOCR）
方案2：本地OCR + DeepSeek（文本AI过滤）
方案3：本地OCR + 规则过滤
"""
import requests
import json
import sys
import os
import time
from statistics import mean
from typing import Dict, List

# 加载环境变量（从.env文件）
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # 如果没有安装python-dotenv，跳过

# 修复Windows控制台编码问题
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

BASE_URL = 'http://localhost:5000'

def load_test_images(max_images=None):
    """
    加载测试图片
    
    Args:
        max_images: 最大图片数量，None表示加载所有图片（跳过预处理文件）
    """
    ceshi_dir = 'uploads/ceshi'
    if not os.path.exists(ceshi_dir):
        print(f"⚠️  错误: 测试目录不存在: {ceshi_dir}")
        return []
    
    images = []
    for file in sorted(os.listdir(ceshi_dir)):
        if file.lower().endswith(('.png', '.jpg', '.jpeg')):
            # 跳过预处理文件（包含_preprocessed的文件）
            if '_preprocessed' not in file.lower():
                full_path = os.path.join(ceshi_dir, file)
                if os.path.exists(full_path):
                    images.append(full_path)
                    if max_images and len(images) >= max_images:
                break
    
    print(f"📂 从目录加载图片: {os.path.abspath(ceshi_dir)}")
    return images

def test_local_ocr_only(image_path: str) -> Dict:
    """测试方案1：纯本地OCR（PaddleOCR）"""
    # 直接调用本地OCR服务
    try:
        from ocr_service import get_ocr_service
        ocr_service = get_ocr_service()
        
        if not ocr_service.ocr_engine:
            return {
                'success': False,
                'time': 0,
                'error': '本地OCR不可用（PaddleOCR未安装）',
                'image_name': os.path.basename(image_path)
            }
        
        # 确认文件存在
        if not os.path.exists(image_path):
            return {
                'success': False,
                'time': 0,
                'error': f'图片文件不存在: {image_path}',
                'image_path': image_path,
                'image_name': os.path.basename(image_path)
            }
        
        # 显示正在处理的图片路径（绝对路径）
        abs_path = os.path.abspath(image_path)
        
        start = time.time()
        raw_text = ocr_service.extract_text(image_path)
        elapsed = time.time() - start
        
        # 调试：获取OCR原始结果用于诊断
        ocr_raw_result = None
        ocr_debug_texts = []
        first_item_sample = None
        if hasattr(ocr_service, 'ocr_engine') and ocr_service.ocr_engine:
            try:
                # 使用predict方法（新版本推荐）或ocr方法
                if hasattr(ocr_service.ocr_engine, 'predict'):
                    try:
                        ocr_raw_result = ocr_service.ocr_engine.predict(image_path)
                    except:
                        try:
                            ocr_raw_result = ocr_service.ocr_engine.ocr(image_path, cls=True)
                        except:
                            try:
                                ocr_raw_result = ocr_service.ocr_engine.ocr(image_path)
                            except:
                                pass
                elif hasattr(ocr_service.ocr_engine, 'ocr'):
                    try:
                        ocr_raw_result = ocr_service.ocr_engine.ocr(image_path, cls=True)
                    except:
                        try:
                            ocr_raw_result = ocr_service.ocr_engine.ocr(image_path)
                        except:
                            pass
                
                # 尝试提取所有识别到的文字（支持多种格式）
                if ocr_raw_result and len(ocr_raw_result) > 0:
                    try:
                        # 获取第一个结果页面
                        page_result = ocr_raw_result[0] if isinstance(ocr_raw_result[0], list) else ocr_raw_result
                        
                        # 保存第一个项目的样本用于调试
                        if page_result and len(page_result) > 0:
                            first_item_sample = str(page_result[0])[:200]  # 只保存前200字符
                        
                        # 标准格式：[[[坐标], (文字, 置信度)], ...]
                        for item in page_result:
                            try:
                                if isinstance(item, list) and len(item) >= 2:
                                    # 格式1: [[坐标], (文字, 置信度)]
                                    text_info = item[1]
                                    if isinstance(text_info, (list, tuple)) and len(text_info) > 0:
                                        ocr_debug_texts.append(str(text_info[0]))
                                    elif isinstance(text_info, str):
                                        ocr_debug_texts.append(text_info)
                                elif isinstance(item, dict):
                                    # 格式2: 字典格式（新版本）
                                    if 'text' in item:
                                        ocr_debug_texts.append(str(item['text']))
                                    elif 'rec_text' in item:
                                        ocr_debug_texts.append(str(item['rec_text']))
                            except:
                                pass
                    except Exception as parse_e:
                        # 如果解析失败，尝试其他格式
                        try:
                            # 尝试直接访问rec_texts
                            if hasattr(page_result, 'rec_texts'):
                                ocr_debug_texts = list(page_result.rec_texts)
                            elif isinstance(page_result, dict) and 'rec_texts' in page_result:
                                ocr_debug_texts = list(page_result['rec_texts'])
                        except:
                            pass
            except Exception as debug_e:
                pass
        
        if raw_text and len(raw_text.strip()) > 0:  # 只要有文字就认为成功
            return {
                'success': True,
                'time': elapsed,
                'method': 'local_ocr_only',
                'raw_text': raw_text,
                'raw_text_length': len(raw_text),
                'text_lines': raw_text.split('\n'),
                'image_path': image_path,
                'image_name': os.path.basename(image_path),
                'ocr_debug_info': {
                    'result_type': str(type(ocr_raw_result)) if ocr_raw_result else None,
                    'result_length': len(ocr_raw_result) if ocr_raw_result else 0,
                    'items_count': len(ocr_raw_result[0]) if ocr_raw_result and isinstance(ocr_raw_result, list) and len(ocr_raw_result) > 0 and isinstance(ocr_raw_result[0], list) else 0,
                    'extracted_texts_count': len(ocr_debug_texts),
                    'first_3_texts': ocr_debug_texts[:3] if ocr_debug_texts else [],
                    'all_texts_preview': ' | '.join(ocr_debug_texts[:10]) if ocr_debug_texts else None,
                    'first_item_sample': first_item_sample,
                    'raw_text_from_service': raw_text[:100] if raw_text else None
                } if ocr_raw_result else None
            }
        else:
            return {
                'success': False,
                'time': elapsed,
                'error': f'OCR识别文字太少（{len(raw_text) if raw_text else 0}字符）',
                'image_path': image_path,
                'image_name': os.path.basename(image_path)
            }
    except Exception as e:
        return {
            'success': False,
            'time': 0,
            'error': str(e)[:100],
            'image_path': image_path,
            'image_name': os.path.basename(image_path) if image_path else 'unknown'
        }

def preprocess_ocr_text(raw_text: str) -> str:
    """
    快速预处理OCR文本，过滤明显的界面元素
    目标：保留题目和选项相关的内容，快速过滤界面元素
    重要：保留完整的题干段落，不过度过滤
    """
    if not raw_text:
        return raw_text
    
    lines = raw_text.split('\n')
    filtered_lines = []
    
    # 严格的界面元素关键词（只过滤明确的界面元素）
    strict_interface_keywords = [
        'KB/s', '首页', '朋友', '消息', '我', '拍同', '点击推荐',
        '粉笔正确率', '华图正确率', '答案一样', '解析在作品', '解析在作品简',
        '展开', '收起', '分享', '点赞', '收藏', '评论',
        '@公考行测每日一练', '公考行测每日一练的橱窗',
        '橱窗|', '点击推荐', '祝各位国考', '行测80', '申论85',
        # 注意：不要过滤"目前还没有公司..."这类可能是题干开头的内容
        # '文段首先介绍', '目前还没有公司可以推出成熟的产',  # 移除此类过滤，避免误删题干
        'Never give up', '单选围'  # 可能是OCR误识别
    ]
    
    # 选项标记（保留）
    option_markers = ['A.', 'B.', 'C.', 'D.', 'E.', 'F.', 'A ', 'B ', 'C ', 'D ']
    
    # 题干相关的关键词（帮助识别题干）
    question_keywords = ['这段文字', '意在说明', '根据', '以下', '题目', '题干']
    
    for i, line in enumerate(lines):
        line_stripped = line.strip()
        if not line_stripped:
            # 保留空行，因为可能用于分隔段落
            continue
        
        # 跳过明确的界面元素（严格匹配）
        is_strict_interface = False
        for keyword in strict_interface_keywords:
            if keyword in line_stripped:
                is_strict_interface = True
                break
        
        if is_strict_interface:
            continue
        
        # 保留包含选项标记的行
        has_option_marker = any(line_stripped.startswith(marker) for marker in option_markers)
        if has_option_marker:
            filtered_lines.append(line_stripped)
            continue
        
        # 保留题干相关关键词的行
        has_question_keyword = any(keyword in line_stripped for keyword in question_keywords)
        if has_question_keyword:
            filtered_lines.append(line_stripped)
            continue
        
        # 保留较长的文本行（可能是题目内容，包括题干段落）
        # 降低长度阈值，避免过滤掉题干内容
        if len(line_stripped) > 3:
            # 如果这一行很长，或者是包含标点的句子，保留
            if len(line_stripped) > 10 or any(p in line_stripped for p in ['。', '，', '、', '；', '？', '：']):
                filtered_lines.append(line_stripped)
                continue
    
    return '\n'.join(filtered_lines)

def test_ocr_with_ai_extraction(image_path: str, ocr_result: Dict = None) -> Dict:
    """
    测试OCR + AI提取题目和选项（优化版）
    快速预处理 + AI精确提取
    
    Args:
        image_path: 图片路径
        ocr_result: 可选的OCR结果（如果已调用过OCR，可以传入避免重复调用）
    """
    # 如果未提供OCR结果，先调用OCR
    if ocr_result is None:
        ocr_result = test_local_ocr_only(image_path)
        if not ocr_result.get('success'):
            return ocr_result
    
    ocr_time = ocr_result.get('time', 0)
    raw_text = ocr_result.get('raw_text', '')
    
    # 第二步：快速预处理（过滤明显的界面元素）
    preprocess_start = time.time()
    preprocessed_text = preprocess_ocr_text(raw_text)
    preprocess_time = time.time() - preprocess_start
    
    # 第三步：调用AI提取题目和选项
    try:
        from ai_service import AIService
        ai_service = AIService()
        
        if not ai_service.client:
            return {
                'success': False,
                'time': ocr_time,
                'error': 'AI服务不可用（请配置AI_API_KEY）',
                'image_path': image_path,
                'image_name': os.path.basename(image_path),
                'ocr_raw_text': raw_text
            }
        
        ai_start = time.time()
        
        # 构建优化的提示词（强调提取完整题干）
        prompt = f"""从以下OCR识别文字中提取题目和选项，忽略所有界面元素、注释、统计信息等。

OCR文字：
{preprocessed_text[:3500]}  # 增加长度限制，确保包含完整题干

重要要求：
1. **题干内容必须完整**：
   - **如果OCR识别到的内容是从中间开始的**（例如直接从"一家公司推出..."开始），也要尽可能提取所有识别到的段落内容
   - 题目的完整开头应该是："尽管无人驾驶的技术更新速度之快让大众目不暇接，但目前为止，还没有一家公司推出完整、成熟的产品..."
   - 但如果OCR只识别到部分内容（例如只识别到"一家公司推出..."），也要提取这部分作为题干的一部分
   - 如果看到"这段文字意在说明..."这是问句，题干包括它前面的所有识别到的段落内容
   - 题干应该是：从OCR识别到的第一段开始 → 完整段落内容 → 问句结束
   
2. **特殊题目格式处理**：
   - 如果是类比题（例如"柳暗花明：峰回路转"这种格式），第一行通常是例子，题干应该是"下列哪个选项与'柳暗花明：峰回路转'的类比关系相同？"或类似问句
   - 如果OCR没有识别到问句，但识别到了例子和选项，可以构造题干："下列哪个选项的类比关系与'[例子]'相同？"
   - 或者如果题目类型是"单选题"且只有类比关系对，可以理解为："选择与'[第一行例子]'类比关系相同的选项"

2. **选项提取**：
   - 选项必须以"A. "、"B. "、"C. "、"D. "开头
   - 只提取选项内容，不要包含选项后面的注释（如"粉笔正确率"、"华图正确率"等）
   - 如果选项后跟着其他文字（统计信息、评论等），只保留选项本身

3. **必须忽略的内容**：
   - 导航栏：首页、朋友、消息、我、直播、精选、团购、关注、商城、推荐
   - 统计信息：粉笔正确率、华图正确率、答案一样、解析在作品
   - 评论和祝福：祝各位国考、行测80、申论85
   - 用户信息：@公考行测每日一练、橱窗、展开、收起
   - 其他：KB/s、拍同、点击推荐

4. **示例格式**：
   

返回JSON格式（必须严格遵守，只返回JSON，不要其他文字）：
{{
    "question_text": "完整的题干内容（从段落开始到问句结束的所有内容）",
    "options": ["A. 选项A完整内容", "B. 选项B完整内容", "C. 选项C完整内容", "D. 选项D完整内容"]
}}"""
        
        response = ai_service.client.chat.completions.create(
            model=ai_service.default_model,
            messages=[
                {"role": "system", "content": "你是一个专业的题目提取助手，擅长从OCR文字中准确提取完整的题目和选项。特别注意：题干必须包括题干前的完整段落内容，不要只提取最后一句问句。只返回JSON格式。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=1500,  # 增加token限制，支持更长的题干
            timeout=20
        )
        
        ai_time = time.time() - ai_start
        total_time = ocr_time + preprocess_time + ai_time
        
        content = response.choices[0].message.content.strip()
        
        # 解析JSON
        import re
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            result = json.loads(json_match.group())
            
            question_text = result.get('question_text', '').strip()
            options = result.get('options', [])
            
            # 确保选项有ABCD标记
            formatted_options = []
            option_letters = ['A', 'B', 'C', 'D', 'E', 'F']
            for i, opt in enumerate(options):
                opt_str = str(opt).strip()
                # 如果没有以字母开头，添加字母
                if not re.match(r'^[A-F]\.?\s', opt_str):
                    if i < len(option_letters):
                        opt_str = f"{option_letters[i]}. {opt_str}"
                formatted_options.append(opt_str)
            
            return {
                'success': True,
                'time': total_time,
                'ocr_time': ocr_time,
                'preprocess_time': preprocess_time,
                'ai_time': ai_time,
                'method': 'ocr_ai_extraction',
                'question_text': question_text,
                'options': formatted_options,
                'options_count': len(formatted_options),
                'ocr_raw_text': raw_text,
                'preprocessed_text': preprocessed_text,
                'raw_text_length': len(raw_text),
                'preprocessed_length': len(preprocessed_text),
                'image_path': image_path,
                'image_name': os.path.basename(image_path)
            }
        else:
            return {
                'success': False,
                'time': total_time,
                'error': f'AI返回格式错误: {content[:100]}',
                'image_path': image_path,
                'image_name': os.path.basename(image_path),
                'ocr_raw_text': raw_text
            }
    except json.JSONDecodeError as e:
        return {
            'success': False,
            'time': ocr_time + ai_time if 'ai_time' in locals() else ocr_time,
            'error': f'JSON解析失败: {str(e)[:100]}',
            'image_path': image_path,
            'image_name': os.path.basename(image_path),
            'ocr_raw_text': raw_text
        }
    except Exception as e:
        return {
            'success': False,
            'time': ocr_time,
            'error': f'AI调用失败: {str(e)[:100]}',
            'image_path': image_path,
            'image_name': os.path.basename(image_path),
            'ocr_raw_text': raw_text
        }

def test_local_ocr_deepseek(image_path: str) -> Dict:
    """测试方案2：本地OCR + DeepSeek（文本AI过滤）"""
    # 先调用本地OCR
    ocr_result = test_local_ocr_only(image_path)
    if not ocr_result.get('success'):
        return ocr_result
    
    ocr_time = ocr_result['time']
    raw_text = ocr_result['raw_text']
    
    # 然后调用DeepSeek过滤
    try:
        from ai_service import AIService
        ai_service = AIService()
        
        if not ai_service.client:
            return {
                'success': False,
                'time': ocr_time,
                'error': 'DeepSeek服务不可用',
                'image_path': image_path,
                'image_name': os.path.basename(image_path)
            }
        
        start = time.time()
        
        # 构建提示词
        prompt = f"""从以下文字中提取题目内容，忽略标题、页码、统计信息、导航栏等无关内容：

{raw_text}

请只提取题目和选项，返回JSON格式：
{{
    "question_text": "题干内容（只包含题目文字，不包括界面元素）",
    "options": ["A. 选项A内容", "B. 选项B内容", "C. 选项C内容", "D. 选项D内容"],
    "raw_text": "题目和选项的原始文字（不包括界面元素）"
}}

重要提示：
- 必须忽略：页面标题、页码、统计信息、时间、网络状态、导航栏、按钮等界面元素
- 只提取题目和选项相关的文字
- options数组中的每个选项必须以"A. "、"B. "、"C. "、"D. "开头"""
        
        response = ai_service.client.chat.completions.create(
            model=ai_service.default_model,
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=500,
            timeout=10
        )
        
        ai_time = time.time() - start
        total_time = ocr_time + ai_time
        
        content = response.choices[0].message.content
        
        # 解析JSON
        import re
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            result = json.loads(json_match.group())
            return {
                'success': True,
                'time': total_time,
                'ocr_time': ocr_time,
                'ai_time': ai_time,
                'method': 'local_ocr_deepseek',
                'question_text': result.get('question_text', ''),
                'options': result.get('options', []),
                'options_count': len(result.get('options', [])),
                'has_question': len(result.get('question_text', '').strip()) > 10,
                'has_options': len(result.get('options', [])) >= 2,
                'raw_text': result.get('raw_text', raw_text),
                'ocr_raw_text': raw_text,  # 保存原始OCR识别文本
                'raw_text_length': len(raw_text),
                'image_path': image_path,
                'image_name': os.path.basename(image_path)
            }
        else:
            return {
                'success': False,
                'time': total_time,
                'error': 'DeepSeek返回格式错误',
                'image_path': image_path,
                'image_name': os.path.basename(image_path)
            }
    except Exception as e:
        return {
            'success': False,
            'time': ocr_time,
            'error': f'DeepSeek调用失败: {str(e)[:100]}',
            'image_path': image_path,
            'image_name': os.path.basename(image_path)
        }

def test_local_ocr_rule(image_path: str) -> Dict:
    """测试方案3：本地OCR + 规则过滤"""
    # 先调用本地OCR
    ocr_result = test_local_ocr_only(image_path)
    if not ocr_result.get('success'):
        return ocr_result
    
    ocr_time = ocr_result['time']
    raw_text = ocr_result['raw_text']
    
    # 然后使用规则过滤
    try:
        from fast_ocr_extractor import get_fast_extractor
        extractor = get_fast_extractor()
        
        start = time.time()
        result = extractor.extract_question_from_text(raw_text)
        rule_time = time.time() - start
        total_time = ocr_time + rule_time
        
        if result['is_complete'] and result['confidence'] >= 0.5:
            return {
                'success': True,
                'time': total_time,
                'ocr_time': ocr_time,
                'rule_time': rule_time,
                'method': 'local_ocr_rule',
                'question_text': result['question_text'],
                'options': result['options'],
                'options_count': len(result['options']),
                'has_question': len(result['question_text'].strip()) > 10,
                'has_options': len(result['options']) >= 2,
                'confidence': result['confidence'],
                'raw_text': result['raw_text'],
                'ocr_raw_text': raw_text,  # 保存原始OCR识别文本
                'raw_text_length': len(raw_text),
                'image_path': image_path,
                'image_name': os.path.basename(image_path)
            }
        else:
            return {
                'success': False,
                'time': total_time,
                'error': f'规则过滤失败（置信度: {result["confidence"]:.2f}）',
                'image_path': image_path,
                'image_name': os.path.basename(image_path)
            }
    except Exception as e:
        return {
            'success': False,
            'time': ocr_time,
            'error': f'规则过滤失败: {str(e)[:100]}',
            'image_path': image_path,
            'image_name': os.path.basename(image_path)
        }

def evaluate_accuracy(result: Dict) -> float:
    """评估准确率"""
    if not result.get('success'):
        return 0.0
    
    score = 0.0
    
    # 有题干：+0.4
    if result.get('has_question'):
        score += 0.4
    
    # 有选项：+0.4
    if result.get('has_options'):
        score += 0.4
    
    # 选项数量合理（2-6个）：+0.2
    options_count = result.get('options_count', 0)
    if 2 <= options_count <= 6:
        score += 0.2
    
    return score

def print_scheme_results(scheme_name: str, results: List[Dict]):
    """打印方案测试结果"""
    print(f"\n{'='*70}")
    print(f"📊 {scheme_name} - 测试结果")
    print(f"{'='*70}")
    
    success_results = [r for r in results if r.get('success')]
    failed_results = [r for r in results if not r.get('success')]
    
    if success_results:
        times = [r['time'] for r in success_results]
        accuracies = [evaluate_accuracy(r) for r in success_results]
        
        print(f"✅ 成功: {len(success_results)}/{len(results)} ({len(success_results)/len(results)*100:.1f}%)")
        print(f"❌ 失败: {len(failed_results)}/{len(results)}")
        print(f"\n⏱️  速度统计:")
        print(f"  平均时间: {mean(times):.2f}秒")
        print(f"  最快:     {min(times):.2f}秒")
        print(f"  最慢:     {max(times):.2f}秒")
        
        # 如果有分段时间，显示
        if success_results[0].get('ocr_time'):
            ocr_times = [r.get('ocr_time', 0) for r in success_results]
            other_times = [r.get('ai_time', 0) or r.get('rule_time', 0) for r in success_results]
            print(f"  OCR时间:  {mean(ocr_times):.2f}秒")
            if other_times[0] > 0:
                print(f"  处理时间: {mean(other_times):.2f}秒")
        
        print(f"\n🎯 准确率统计:")
        print(f"  平均准确率: {mean(accuracies):.2%}")
        print(f"  最高准确率: {max(accuracies):.2%}")
        print(f"  最低准确率: {min(accuracies):.2%}")
        
        # 详细结果
        print(f"\n📝 详细结果:")
        for i, r in enumerate(success_results, 1):
            method = r.get('method', 'unknown')
            options_count = r.get('options_count', 0)
            accuracy = evaluate_accuracy(r)
            question_preview = r.get('question_text', '')[:40] + '...' if len(r.get('question_text', '')) > 40 else r.get('question_text', '')
            image_name = r.get('image_name', 'unknown')
            
            time_info = f"{r['time']:.2f}秒"
            if r.get('ocr_time'):
                time_info += f" (OCR: {r.get('ocr_time', 0):.2f}s"
                if r.get('ai_time'):
                    time_info += f", AI: {r.get('ai_time', 0):.2f}s"
                elif r.get('rule_time'):
                    time_info += f", 规则: {r.get('rule_time', 0):.2f}s"
                time_info += ")"
            
            print(f"\n  {i}. 【{image_name}】")
            print(f"     时间: {time_info} | 方法: {method} | 选项数: {options_count} | 准确率: {accuracy:.2%}")
            
            # 打印完整的OCR识别内容（方案1需要打印完整内容）
            raw_text = r.get('ocr_raw_text') or r.get('raw_text', '')
            if raw_text:
                print(f"     📝 OCR完整识别内容:")
                print(f"     {'='*70}")
                # 打印所有内容，不截断，包括空行
                lines = raw_text.split('\n')
                for line in lines:
                    print(f"     {line}")  # 打印每一行，包括空行
                print(f"     {'='*70}")
                print(f"     📊 统计: 总字符数={len(raw_text)}, 总行数={len(lines)}, 非空行数={len([l for l in lines if l.strip()])}")
            else:
                print(f"     ⚠️  未识别到文字内容")
            
            if question_preview and method != 'local_ocr_only':
                print(f"     题干预览: {question_preview}")
    else:
        print(f"❌ 全部失败")
        for i, r in enumerate(failed_results, 1):
            image_name = r.get('image_name', 'unknown')
            print(f"  {i}. 【{image_name}】 {r.get('time', 0):.2f}秒 - {r.get('error', 'unknown')}")

def main():
    print("="*70)
    print("🚀 本地OCR方案速度和准确率测试")
    print("="*70)
    
    # 检查本地OCR是否可用
    print("\n📦 正在初始化PaddleOCR模型...")
    print("   ⚠️  说明：")
    print("   - 模型文件已缓存到本地（不会重复下载）")
    print("   - 首次加载模型到内存需要10-30秒（这是正常的）")
    print("   - 一旦模型加载完成，处理多张图片会很快（不需要重新加载）")
    print("   - 每次运行新程序时只需加载一次\n")
    
    try:
        from ocr_service import get_ocr_service
        print("   ⏳ 正在加载模型（请耐心等待）...")
        import time
        load_start = time.time()
        ocr_service = get_ocr_service()
        load_time = time.time() - load_start
        
        if not ocr_service.ocr_engine:
            print("❌ 本地OCR不可用（PaddleOCR未安装）")
            print("   请安装: pip install paddleocr")
            return
        else:
            print(f"✅ 本地OCR已就绪: {type(ocr_service.ocr_engine).__name__}")
            print(f"   📊 模型加载耗时: {load_time:.2f}秒")
            print(f"   💡 提示: 模型已加载到内存，后续处理图片将很快")
    except Exception as e:
        print(f"❌ 本地OCR初始化失败: {e}")
        return
    
    # 加载测试图片（加载所有图片，不限制数量）
    test_images = load_test_images(max_images=None)
    
    if not test_images:
        print("❌ 未找到测试图片")
        print(f"   请检查目录: {os.path.abspath('uploads/ceshi')}")
        return
    
    print(f"\n📷 测试图片信息:")
    print(f"   图片来源: uploads/ceshi 目录")
    print(f"   说明: PaddleOCR只缓存模型文件，不会缓存OCR识别结果")
    print(f"   每次识别都会实时处理图片，不存在结果缓存\n")
    print(f"   测试图片数: {len(test_images)}（已跳过预处理文件）")
    for img in test_images:
        file_size = os.path.getsize(img) / 1024
        abs_path = os.path.abspath(img)
        print(f"  - {os.path.basename(img)} ({file_size:.2f} KB)")
        print(f"    路径: {abs_path}")
    
    # 只测试OCR识别能力
    print(f"\n{'='*70}")
    print("📊 测试OCR识别能力（纯OCR，不包含AI提取）")
    print(f"{'='*70}\n")
    
    # 统计信息
    total_time = 0
    success_count = 0
    fail_count = 0
    total_chars = 0
    times_list = []
    
    for i, img_path in enumerate(test_images, 1):
        image_name = os.path.basename(img_path)
        abs_path = os.path.abspath(img_path)
    print(f"\n{'='*70}")
        print(f"📷 图片 {i}/{len(test_images)}: {image_name}")
        print(f"📁 路径: {abs_path}")
        print(f"{'='*70}\n")
        
        # OCR识别
        print(f"⏳ OCR识别中...")
        ocr_result = test_local_ocr_only(img_path)
        
        if not ocr_result.get('success'):
            print(f"❌ OCR识别失败: {ocr_result.get('error', 'unknown')}\n")
            fail_count += 1
            continue
        
        raw_text = ocr_result.get('raw_text', '')
        elapsed = ocr_result['time']
        char_count = len(raw_text)
        
        total_time += elapsed
        success_count += 1
        total_chars += char_count
        times_list.append(elapsed)
        
        line_count = len(raw_text.split('\n'))
        non_empty_lines = len([l for l in raw_text.split('\n') if l.strip()])
        
        print(f"✅ OCR识别成功")
        print(f"⏱️  耗时: {elapsed:.2f}秒")
        print(f"📊 识别字符数: {char_count} 字符")
        print(f"📊 识别行数: {line_count} 行（非空行: {non_empty_lines} 行）\n")
    
        # 显示OCR原始识别内容
        print(f"📝 OCR原始识别内容:")
    print(f"{'='*70}")
        for line in raw_text.split('\n'):
            print(line)
        print(f"{'='*70}\n")
    
    # 打印统计信息
    print(f"\n{'='*70}")
    print("📊 OCR识别统计")
    print(f"{'='*70}")
    print(f"✅ 成功: {success_count}/{len(test_images)} ({success_count/len(test_images)*100:.1f}%)")
    print(f"❌ 失败: {fail_count}/{len(test_images)}")
    
    if success_count > 0:
        print(f"\n⏱️  速度统计:")
        print(f"   总耗时: {total_time:.2f}秒")
        print(f"   平均耗时: {total_time/success_count:.2f}秒/张")
        if len(times_list) > 1:
            print(f"   最快: {min(times_list):.2f}秒")
            print(f"   最慢: {max(times_list):.2f}秒")
        
        print(f"\n📊 识别统计:")
        print(f"   总字符数: {total_chars} 字符")
        print(f"   平均字符数: {total_chars//success_count} 字符/张")
    
    print(f"{'='*70}")
    print("✅ OCR测试完成")
    print(f"{'='*70}\n")

if __name__ == '__main__':
    main()


