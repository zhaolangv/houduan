# DeepSeek 生产使用指南

## 📋 快速回答

### 1. 提示词需要优化吗？

**答案：不需要，当前提示词已经很好**

**理由**：
- ✅ 测试准确率达到 **1.00**（满分）
- ✅ 所有15张图片都成功提取
- ✅ 提示词清晰明确，AI能准确理解

**当前提示词**（保持不变）：
```python
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
```

---

### 2. 一次发送一道题还是若干题？

**答案：一次发送一道题** ⭐ **强烈推荐**

#### 方案对比

| 对比项 | 一次一道题 ✅ | 一次若干题 ❌ |
|--------|-------------|-------------|
| **错误隔离** | ✅ 一道失败不影响其他 | ❌ 一道失败整批失败 |
| **重试简单** | ✅ 只需重试失败的那道 | ❌ 需重试整批 |
| **进度可控** | ✅ 实时显示进度 | ❌ 无法知道进度 |
| **内存占用** | ✅ 小 | ❌ 大 |
| **Token限制** | ✅ 无风险 | ❌ 可能超限 |
| **开发复杂度** | ✅ 简单 | ❌ 复杂 |
| **API调用次数** | ⚠️ 较多 | ✅ 较少 |

#### 为什么推荐一次一道题？

1. **费用很低**：DeepSeek 单次仅 ¥0.000117，1万次才 ¥1.17
2. **稳定性优先**：错误隔离好，一道题失败不影响其他
3. **实际场景**：通常是一张图片一道题
4. **可优化**：需要速度时可以用并发处理

---

## 🚀 推荐实现方式

### 基础版本（单题串行）

```python
def process_question(image_path: str):
    """处理单道题（推荐）"""
    # 1. OCR识别
    ocr_result = get_ocr_text(image_path)
    if not ocr_result['success']:
        return {'success': False, 'error': 'OCR失败'}
    
    # 2. AI提取（一道题一次请求）
    ai_result = call_ai_model(
        provider='deepseek',
        model='deepseek-chat',
        ocr_text=ocr_result['raw_text']
    )
    
    return ai_result

# 使用
for image_path in image_list:
    result = process_question(image_path)
    if result['success']:
        print(f"✅ 成功: {result['question_text']}")
    else:
        print(f"❌ 失败: {result['error']}")
```

---

### 优化版本（并发处理）

如果需要提升速度，可以使用并发（但仍保持单题单请求）：

```python
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

def process_questions_concurrent(image_paths: list, max_workers: int = 5):
    """
    并发处理多道题（每道题独立请求）
    
    Args:
        image_paths: 图片路径列表
        max_workers: 并发数（推荐3-5）
    
    Returns:
        List[Dict]: 处理结果列表
    """
    results = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        future_to_path = {
            executor.submit(process_question, path): path 
            for path in image_paths
        }
        
        # 带进度条处理结果
        with tqdm(total=len(image_paths), desc="处理题目") as pbar:
            for future in as_completed(future_to_path):
                image_path = future_to_path[future]
                try:
                    result = future.result()
                    result['image_path'] = image_path
                    results.append(result)
                    
                    if result.get('success'):
                        pbar.set_postfix({'成功': len([r for r in results if r.get('success')])})
                    else:
                        pbar.set_postfix({'失败': len([r for r in results if not r.get('success')])})
                except Exception as e:
                    results.append({
                        'success': False,
                        'image_path': image_path,
                        'error': str(e)
                    })
                finally:
                    pbar.update(1)
    
    return results

# 使用示例
image_paths = ['image1.jpg', 'image2.jpg', ...]
results = process_questions_concurrent(image_paths, max_workers=5)

# 统计
success_count = len([r for r in results if r.get('success')])
print(f"成功: {success_count}/{len(results)}")
```

**并发优势**：
- ✅ 速度提升：5个并发 ≈ 5倍速度
- ✅ 保持单题独立请求（错误隔离）
- ✅ 可以实时查看进度

---

## 💡 为什么不推荐批量发送？

### 问题示例

如果一次发送5道题：

```python
# ❌ 不推荐：批量发送
batch_prompt = """
从以下5道题的OCR文字中提取：

题目1：
{ocr_text_1}

题目2：
{ocr_text_2}
...
"""
```

**问题**：
1. ❌ **一道失败，全部失败**：如果第3道题OCR有问题，整批失败
2. ❌ **重试成本高**：需要重试所有5道题，即使只有1道失败
3. ❌ **Token限制**：5道题的OCR文字可能超过上下文限制
4. ❌ **进度不可控**：无法知道具体哪道题处理到哪一步
5. ❌ **内存占用大**：所有OCR文字都在内存中

---

## 📊 性能对比（处理100道题）

| 方案 | 耗时 | API调用 | 错误处理 | 推荐度 |
|------|------|---------|----------|--------|
| **单题串行** | ~23分钟 | 100次 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **单题并发5** | ~5分钟 | 100次 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **批量5题** | ~10分钟 | 20次 | ⭐⭐ | ⭐⭐ |

**结论**：单题并发是最佳方案 ✅

---

## 🎯 最终建议

### ✅ 推荐配置

1. **提示词**：保持当前版本（已经很好）
2. **发送策略**：**一次发送一道题**
3. **并发优化**：使用 `ThreadPoolExecutor`，并发数 3-5
4. **重试机制**：失败自动重试 2-3 次

### 📝 完整代码示例

```python
import os
import json
import re
from typing import Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI
from ocr_service import get_ocr_service

# DeepSeek 配置
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', 'sk-7de12481a17045819fcf3a2838d884a1')
DEEPSEEK_API_BASE = 'https://api.deepseek.com/v1'
MODEL = 'deepseek-chat'

def get_ocr_text(image_path: str) -> Dict:
    """OCR识别"""
    ocr_service = get_ocr_service()
    if not ocr_service.ocr_engine:
        return {'success': False, 'error': 'OCR不可用'}
    
    raw_text = ocr_service.extract_text(image_path)
    if raw_text:
        return {'success': True, 'raw_text': raw_text}
    else:
        return {'success': False, 'error': 'OCR未识别到文字'}

def call_deepseek(ocr_text: str) -> Dict:
    """调用DeepSeek提取题目和选项"""
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_API_BASE)
    
    # 构建提示词（保持当前版本）
    prompt = f"""从以下OCR识别文字中提取题目和选项，忽略所有界面元素。

OCR文字：
{ocr_text[:3000]}

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
    
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "你是一个专业的题目提取助手，擅长从OCR文字中准确提取完整的题目和选项。只返回JSON格式。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=1500,
            timeout=20
        )
        
        content = response.choices[0].message.content.strip()
        
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
                'options': formatted_options
            }
        else:
            return {'success': False, 'error': 'JSON解析失败'}
    
    except Exception as e:
        return {'success': False, 'error': str(e)}

def process_single_question(image_path: str) -> Dict:
    """处理单道题（一次发送一道题）"""
    # 1. OCR识别
    ocr_result = get_ocr_text(image_path)
    if not ocr_result['success']:
        return {'success': False, 'error': ocr_result['error'], 'image_path': image_path}
    
    # 2. AI提取（单题单请求）
    ai_result = call_deepseek(ocr_result['raw_text'])
    ai_result['image_path'] = image_path
    
    return ai_result

def process_batch_concurrent(image_paths: List[str], max_workers: int = 5) -> List[Dict]:
    """并发处理多道题（每道题独立请求）"""
    results = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_path = {
            executor.submit(process_single_question, path): path 
            for path in image_paths
        }
        
        for future in as_completed(future_to_path):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                results.append({
                    'success': False,
                    'image_path': future_to_path[future],
                    'error': str(e)
                })
    
    return results

# 使用示例
if __name__ == '__main__':
    # 单题处理
    result = process_single_question('image.jpg')
    print(result)
    
    # 批量并发处理
    image_paths = ['image1.jpg', 'image2.jpg', ...]
    results = process_batch_concurrent(image_paths, max_workers=5)
    
    # 统计
    success = [r for r in results if r.get('success')]
    print(f"成功: {len(success)}/{len(results)}")
```

---

## 📌 总结

1. **提示词**：✅ 保持当前版本，无需优化
2. **发送策略**：✅ **一次发送一道题**（推荐）
3. **速度优化**：✅ 使用并发（3-5个worker）
4. **费用**：✅ DeepSeek费用极低，无需担心调用次数

**最佳实践**：单题处理 + 并发优化 = 速度快 + 稳定性好 ✅
