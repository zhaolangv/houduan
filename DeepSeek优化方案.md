# DeepSeek 模型优化方案

## 📋 目录
1. [提示词优化](#提示词优化)
2. [批量处理策略](#批量处理策略)
3. [实施建议](#实施建议)

---

## 1. 提示词优化

### 当前提示词分析

**当前版本**（已测试，准确率1.00）：
```
从以下OCR识别文字中提取题目和选项，忽略所有界面元素。

OCR文字：
{preprocessed_text}

要求：
1. 只提取题目内容和选项
2. 题干必须完整，包括所有段落内容
3. 选项必须以"A. "、"B. "、"C. "、"D. "开头
4. 不要包含界面元素

返回JSON格式（只返回JSON，不要其他文字）：
{
    "question_text": "完整的题干内容",
    "options": ["A. 选项A", "B. 选项B", "C. 选项C", "D. 选项D"]
}
```

### ✅ 优化建议（可选微调）

**优化版本**（更精确，减少token）：
```python
prompt = f"""从OCR文字中提取题目和选项，忽略界面元素。

OCR文字：
{preprocessed_text}

提取规则：
1. 完整提取所有题干部落（不要截断）
2. 选项格式：A. 选项内容（必须有A. B. C. D.前缀）
3. 忽略：界面按钮、广告、用户信息、统计数字
4. 只返回JSON，格式：
{{
    "question_text": "题干全文",
    "options": ["A. 选项A", "B. 选项B", "C. 选项C", "D. 选项D"]
}}"""
```

**优化点**：
- ✅ 更简洁（减少约15% token）
- ✅ 更明确（用"规则"代替"要求"）
- ✅ 列出具体要忽略的内容

### 📝 推荐方案

**建议：保持当前提示词**
- ✅ 测试准确率已达到1.00
- ✅ 提示词清晰明确
- ✅ 无需修改（"如果没坏，就别修"）

**如果要优化，可以用简化版**（节省token，但准确率需要验证）

---

## 2. 批量处理策略

### 🎯 核心问题：一次发送一道题 vs 一次发送若干题

### 方案A：**一次发送一道题** ⭐ **推荐**

#### 优点
1. ✅ **错误隔离好**：一道题失败不影响其他题
2. ✅ **重试简单**：失败后只需重试这一道
3. ✅ **进度可控**：可以实时显示处理进度
4. ✅ **内存占用小**：不会因为批量过大导致问题
5. ✅ **符合API设计**：大多数API设计为单次调用
6. ✅ **灵活性强**：可以随时中断、跳过某题

#### 缺点
1. ❌ **API调用次数多**：每道题一次调用
2. ❌ **网络开销**：多次HTTP请求

#### 适用场景
- ✅ **实时处理**：用户上传一张处理一张
- ✅ **批量处理**：遍历图片列表，逐个处理
- ✅ **错误恢复**：需要精确知道哪道题失败

#### 实现方式
```python
# 推荐方式：一次处理一道题
for image_path in image_list:
    # 1. OCR识别
    ocr_result = get_ocr_text(image_path)
    
    # 2. AI提取（单题）
    ai_result = call_ai_model('deepseek', 'deepseek-chat', ocr_result['raw_text'])
    
    # 3. 处理结果
    if ai_result['success']:
        save_result(image_path, ai_result)
    else:
        log_error(image_path, ai_result['error'])
```

---

### 方案B：**一次发送若干题**（批量）

#### 优点
1. ✅ **API调用少**：减少HTTP请求次数
2. ✅ **可能更快**：如果API支持并行处理
3. ✅ **费用统计方便**：一次调用统计总费用

#### 缺点
1. ❌ **错误处理复杂**：一道题失败，整批失败
2. ❌ **Token限制**：批量过大可能超过上下文限制
3. ❌ **响应时间长**：批量处理总时间可能更长
4. ❌ **进度不可控**：无法知道具体进度
5. ❌ **内存占用大**：所有OCR文字都在内存中
6. ❌ **重试成本高**：失败需要重试整批

#### 适用场景
- ⚠️ **离线批量处理**：一次性处理大量题目
- ⚠️ **API限制严格**：有调用次数限制的情况

#### 实现方式
```python
# 批量方式（不推荐）
def batch_process(ocr_texts: List[str], batch_size: int = 5):
    """批量处理题目"""
    for i in range(0, len(ocr_texts), batch_size):
        batch = ocr_texts[i:i+batch_size]
        
        # 构建批量提示词
        batch_prompt = "从以下多道题的OCR文字中分别提取题目和选项：\n\n"
        for idx, text in enumerate(batch):
            batch_prompt += f"题目{idx+1}：\n{text}\n\n"
        
        batch_prompt += "返回JSON数组格式：[\n"
        batch_prompt += '  {"question_text": "...", "options": [...]},\n'
        batch_prompt += '  ...\n'
        batch_prompt += "]"
        
        # 调用API（一次性处理多题）
        result = call_ai_model('deepseek', 'deepseek-chat', batch_prompt)
        # 问题：如果失败，所有题目都需要重试
```

---

## 🎯 **最终推荐：一次发送一道题**

### 理由
1. **测试结果支持**：当前方案准确率1.00，说明单题处理效果好
2. **成本可接受**：DeepSeek费用极低（¥0.000117/次），批量处理节省有限
3. **稳定性优先**：单题处理错误隔离更好
4. **开发简单**：逻辑清晰，维护方便
5. **符合实际场景**：通常是一张图片一道题

### 优化建议

#### 1. **并发处理（推荐）**
```python
from concurrent.futures import ThreadPoolExecutor
import asyncio

# 并发处理多道题（单题单请求）
def process_questions_concurrent(image_paths: List[str], max_workers: int = 5):
    """并发处理多道题，每道题独立请求"""
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_single_question, path): path 
            for path in image_paths
        }
        
        for future in as_completed(futures):
            image_path = futures[future]
            try:
                result = future.result()
                if result['success']:
                    save_result(image_path, result)
            except Exception as e:
                log_error(image_path, str(e))

def process_single_question(image_path: str):
    """处理单道题"""
    # OCR识别
    ocr_result = get_ocr_text(image_path)
    if not ocr_result['success']:
        return {'success': False, 'error': ocr_result['error']}
    
    # AI提取
    ai_result = call_ai_model('deepseek', 'deepseek-chat', ocr_result['raw_text'])
    return ai_result
```

**优势**：
- ✅ 保持单题独立请求（错误隔离）
- ✅ 并发提升速度（5个并发 = 约5倍速度）
- ✅ 平衡速度和稳定性

#### 2. **重试机制**
```python
import time
from functools import wraps

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

# 使用
@retry_on_failure(max_retries=3, delay=1.0)
def call_ai_with_retry(ocr_text: str):
    return call_ai_model('deepseek', 'deepseek-chat', ocr_text)
```

#### 3. **进度追踪**
```python
from tqdm import tqdm

def process_with_progress(image_paths: List[str]):
    """带进度条的处理"""
    results = []
    
    with tqdm(total=len(image_paths), desc="处理题目") as pbar:
        for image_path in image_paths:
            result = process_single_question(image_path)
            results.append(result)
            pbar.update(1)
            
            if result['success']:
                pbar.set_postfix({'成功': len([r for r in results if r.get('success')])})
            else:
                pbar.set_postfix({'失败': len([r for r in results if not r.get('success')])})
    
    return results
```

---

## 3. 实施建议

### ✅ 推荐配置

```python
# 1. 使用优化的提示词（可选，当前版本已经很好）
PROMPT_TEMPLATE = """从OCR文字中提取题目和选项，忽略界面元素。

OCR文字：
{ocr_text}

提取规则：
1. 完整提取所有题干部落（不要截断）
2. 选项格式：A. 选项内容（必须有A. B. C. D.前缀）
3. 忽略：界面按钮、广告、用户信息、统计数字
4. 只返回JSON，格式：
{{
    "question_text": "题干全文",
    "options": ["A. 选项A", "B. 选项B", "C. 选项C", "D. 选项D"]
}}"""

# 2. 单题处理（推荐）
def process_question(image_path: str) -> Dict:
    """处理单道题"""
    # OCR
    ocr_result = get_ocr_text(image_path)
    if not ocr_result['success']:
        return {'success': False, 'error': 'OCR失败'}
    
    # AI提取（单题）
    ai_result = call_ai_model(
        provider='deepseek',
        model='deepseek-chat',
        ocr_text=ocr_result['raw_text']
    )
    return ai_result

# 3. 批量处理（并发，单题单请求）
def process_batch(image_paths: List[str], max_workers: int = 5) -> List[Dict]:
    """批量处理，使用并发提升速度"""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_path = {
            executor.submit(process_question, path): path 
            for path in image_paths
        }
        
        for future in as_completed(future_to_path):
            path = future_to_path[future]
            try:
                result = future.result()
                result['image_path'] = path
                results.append(result)
            except Exception as e:
                results.append({
                    'success': False,
                    'image_path': path,
                    'error': str(e)
                })
    
    return results
```

### 📊 性能对比

| 方案 | 速度 | 稳定性 | 错误处理 | 推荐度 |
|------|------|--------|----------|--------|
| **单题+并发5** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 单题+串行 | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| 批量5题 | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ |
| 批量10题 | ⭐⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐ |

---

## 📝 总结

1. **提示词**：当前版本已经很好（准确率1.00），**无需修改**，或可尝试简化版

2. **发送策略**：**一次发送一道题**（推荐）
   - ✅ 错误隔离好
   - ✅ 重试简单
   - ✅ 进度可控
   - ✅ 使用并发提升速度

3. **并发优化**：使用 `ThreadPoolExecutor` 并发处理多道题
   - 推荐并发数：**3-5个**
   - 可提升速度：**3-5倍**
   - 保持单题独立请求的优势

4. **实施步骤**：
   - 第一步：保持当前单题处理逻辑
   - 第二步：添加并发处理（可选，提升速度）
   - 第三步：添加重试机制（提高稳定性）

---

## 🔧 代码示例（完整实现）

见下一个文件：`deepseek_production_usage.py`
