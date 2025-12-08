"""
DeepSeek 生产使用示例
- 一次发送一道题（推荐）
- 支持并发处理提升速度
- 包含重试机制
"""
import os
import json
import re
import time
from typing import Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import wraps
from openai import OpenAI

# DeepSeek 配置
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', 'sk-7de12481a17045819fcf3a2838d884a1')
DEEPSEEK_API_BASE = 'https://api.deepseek.com/v1'
MODEL = 'deepseek-chat'

def retry_on_failure(max_retries: int = 3, delay: float = 1.0):
    """重试装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    result = func(*args, **kwargs)
                    if result.get('success'):
                        return result
                    # 如果失败，等待后重试
                    if attempt < max_retries - 1:
                        time.sleep(delay * (attempt + 1))  # 指数退避
                except Exception as e:
                    if attempt == max_retries - 1:
                        return {'success': False, 'error': str(e)}
                    time.sleep(delay * (attempt + 1))
            return {'success': False, 'error': '达到最大重试次数'}
        return wrapper
    return decorator

def get_ocr_text(image_path: str) -> Dict:
    """OCR识别（复用现有服务）"""
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
            'time': elapsed
        }
    else:
        return {'success': False, 'error': 'OCR未识别到文字', 'time': elapsed}

@retry_on_failure(max_retries=3, delay=1.0)
def call_deepseek_extract(ocr_text: str) -> Dict:
    """
    调用DeepSeek提取题目和选项
    使用当前已验证的提示词（准确率1.00）
    """
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_API_BASE)
    
    # 预处理OCR文本（可选，根据需要调整）
    preprocessed_text = ocr_text[:3000]  # 限制长度
    
    # 提示词（保持当前版本，已验证准确率1.00）
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
    
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system", 
                "content": "你是一个专业的题目提取助手，擅长从OCR文字中准确提取完整的题目和选项。只返回JSON格式。"
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.1,
        max_tokens=1500,
        timeout=20
        # 注意：deepseek-chat 不需要禁用思考模式，只有 deepseek-reasoner 需要
    )
    
    elapsed = time.time() - start_time
    content = response.choices[0].message.content.strip()
    
    # 统计token和费用
    input_tokens = response.usage.prompt_tokens if hasattr(response, 'usage') else 0
    output_tokens = response.usage.completion_tokens if hasattr(response, 'usage') else 0
    total_tokens = input_tokens + output_tokens
    cost = (input_tokens / 1000 * 0.00014) + (output_tokens / 1000 * 0.00056)
    
    # 解析JSON
    json_match = re.search(r'\{[\s\S]*\}', content)
    if json_match:
        try:
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
                'total_tokens': total_tokens,
                'cost': cost
            }
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

def process_single_question(image_path: str) -> Dict:
    """
    处理单道题（一次发送一道题）
    
    流程：
    1. OCR识别
    2. AI提取（一道题一次请求）
    
    优点：
    - 错误隔离好
    - 重试简单
    - 进度可控
    """
    # 1. OCR识别
    ocr_result = get_ocr_text(image_path)
    if not ocr_result['success']:
        return {
            'success': False,
            'error': f"OCR失败: {ocr_result.get('error')}",
            'image_path': image_path,
            'ocr_time': ocr_result.get('time', 0)
        }
    
    # 2. AI提取（单题单请求）
    ai_result = call_deepseek_extract(ocr_result['raw_text'])
    
    # 合并结果
    result = {
        'success': ai_result.get('success', False),
        'image_path': image_path,
        'ocr_time': ocr_result.get('time', 0),
        'ai_time': ai_result.get('time', 0),
        'total_time': ocr_result.get('time', 0) + ai_result.get('time', 0)
    }
    
    if ai_result.get('success'):
        result.update({
            'question_text': ai_result.get('question_text', ''),
            'options': ai_result.get('options', []),
            'input_tokens': ai_result.get('input_tokens', 0),
            'output_tokens': ai_result.get('output_tokens', 0),
            'total_tokens': ai_result.get('total_tokens', 0),
            'cost': ai_result.get('cost', 0)
        })
    else:
        result['error'] = ai_result.get('error', '未知错误')
    
    return result

def process_batch_concurrent(image_paths: List[str], max_workers: int = 5) -> List[Dict]:
    """
    并发处理多道题（每道题独立请求）
    
    Args:
        image_paths: 图片路径列表
        max_workers: 并发数（推荐3-5）
    
    Returns:
        List[Dict]: 处理结果列表
    
    优点：
    - 保持单题独立请求（错误隔离）
    - 并发提升速度（3-5倍）
    - 实时进度追踪
    """
    results = []
    total_cost = 0.0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        future_to_path = {
            executor.submit(process_single_question, path): path 
            for path in image_paths
        }
        
        # 处理结果
        for future in as_completed(future_to_path):
            image_path = future_to_path[future]
            try:
                result = future.result()
                results.append(result)
                
                if result.get('success'):
                    total_cost += result.get('cost', 0)
                    print(f"✅ {os.path.basename(image_path)}: 成功 (耗时:{result.get('total_time', 0):.2f}秒, 费用:¥{result.get('cost', 0):.6f})")
                else:
                    print(f"❌ {os.path.basename(image_path)}: 失败 - {result.get('error', 'unknown')}")
            
            except Exception as e:
                results.append({
                    'success': False,
                    'image_path': image_path,
                    'error': f'处理异常: {str(e)}'
                })
                print(f"❌ {os.path.basename(image_path)}: 异常 - {str(e)}")
    
    # 统计
    success_count = len([r for r in results if r.get('success')])
    avg_time = sum([r.get('total_time', 0) for r in results if r.get('success')]) / success_count if success_count > 0 else 0
    
    print(f"\n📊 处理完成:")
    print(f"   成功: {success_count}/{len(results)}")
    print(f"   平均耗时: {avg_time:.2f}秒")
    print(f"   总费用: ¥{total_cost:.6f}")
    
    return results

def process_batch_serial(image_paths: List[str]) -> List[Dict]:
    """
    串行处理多道题（每道题独立请求）
    
    适用于：
    - 对速度要求不高
    - 需要严格控制API调用频率
    """
    results = []
    total_cost = 0.0
    
    for idx, image_path in enumerate(image_paths, 1):
        print(f"[{idx}/{len(image_paths)}] 处理: {os.path.basename(image_path)}")
        
        result = process_single_question(image_path)
        results.append(result)
        
        if result.get('success'):
            total_cost += result.get('cost', 0)
            print(f"  ✅ 成功 (耗时:{result.get('total_time', 0):.2f}秒, 费用:¥{result.get('cost', 0):.6f})")
        else:
            print(f"  ❌ 失败: {result.get('error', 'unknown')}")
    
    # 统计
    success_count = len([r for r in results if r.get('success')])
    print(f"\n📊 处理完成: {success_count}/{len(results)} 成功, 总费用: ¥{total_cost:.6f}")
    
    return results

# 使用示例
if __name__ == '__main__':
    import glob
    
    # 获取所有测试图片
    image_paths = glob.glob('uploads/ceshi/*.jpg') + glob.glob('uploads/ceshi/*.png')
    image_paths = [p for p in image_paths if '_preprocessed' not in p]
    
    if not image_paths:
        print("未找到测试图片")
    else:
        print(f"找到 {len(image_paths)} 张图片\n")
        
        # 方式1：并发处理（推荐，速度快）
        print("="*70)
        print("方式1: 并发处理（推荐）")
        print("="*70)
        results = process_batch_concurrent(image_paths, max_workers=5)
        
        # 方式2：串行处理（速度慢但更稳定）
        # print("="*70)
        # print("方式2: 串行处理")
        # print("="*70)
        # results = process_batch_serial(image_paths)
        
        # 保存结果
        output_file = 'extraction_results.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n结果已保存到: {output_file}")
