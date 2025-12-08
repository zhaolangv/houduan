# AI处理速度优化方案

## 当前性能瓶颈分析

### 1. OCR处理（火山引擎）
- **当前方式**：每张图片单独调用API
- **耗时**：每次调用约1-3秒
- **瓶颈**：网络延迟、API响应时间

### 2. AI分析（DeepSeek）
- **当前方式**：每个题目单独调用
- **耗时**：每次调用约2-5秒
- **瓶颈**：API响应时间、token处理

### 3. 数据库查询
- **当前方式**：多次查询（去重检查、保存等）
- **耗时**：每次查询约10-50ms
- **瓶颈**：查询次数多、索引可能不足

### 4. 图片处理
- **当前方式**：保存图片、计算哈希等
- **耗时**：每次约100-500ms
- **瓶颈**：I/O操作

## 优化方案

### 方案1：OCR批量处理优化 ⚡

**问题**：当前每张图片单独调用OCR API

**优化**：
1. **批量OCR调用**（如果API支持）
2. **OCR结果缓存**（相同图片不重复调用）
3. **异步OCR处理**（不阻塞主流程）

```python
# 优化前：顺序调用
for image in images:
    ocr_result = volcengine_service.extract_text(image)  # 每次1-3秒

# 优化后：并行调用
from concurrent.futures import ThreadPoolExecutor
with ThreadPoolExecutor(max_workers=5) as executor:
    ocr_results = executor.map(volcengine_service.extract_text, images)
```

**预期提升**：5倍速度（5并发）

### 方案2：AI分析优化 🚀

**问题**：AI分析是串行的，且每次都要等待完整响应

**优化**：
1. **流式响应**（如果支持）：边生成边返回
2. **更快的模型**：使用更快的API端点
3. **减少token数量**：优化prompt，减少输入长度
4. **批量AI调用**（如果API支持）

```python
# 优化前：完整等待
response = ai_client.chat.completions.create(...)  # 等待完整响应

# 优化后：流式响应
stream = ai_client.chat.completions.create(..., stream=True)
for chunk in stream:
    # 边生成边处理
    ...
```

**预期提升**：2-3倍速度

### 方案3：数据库优化 💾

**问题**：多次数据库查询，可能没有索引

**优化**：
1. **批量查询**：一次查询多个题目
2. **添加索引**：question_hash, raw_text等
3. **连接池优化**：减少连接开销
4. **查询缓存**：Redis缓存热点数据

```python
# 优化前：多次查询
for hash in question_hashes:
    question = Question.query.filter_by(question_hash=hash).first()

# 优化后：批量查询
questions = Question.query.filter(Question.question_hash.in_(question_hashes)).all()
question_dict = {q.question_hash: q for q in questions}
```

**预期提升**：2-5倍速度

### 方案4：缓存优化 🗄️

**问题**：缓存命中率可能不高

**优化**：
1. **多级缓存**：内存缓存 + Redis缓存
2. **预加载**：提前加载常用数据
3. **智能缓存**：根据访问频率调整缓存策略

```python
# 多级缓存
# L1: 内存缓存（最快，但容量小）
# L2: Redis缓存（较快，容量大）
# L3: 数据库（最慢，但持久化）
```

**预期提升**：10-100倍速度（缓存命中时）

### 方案5：异步处理 ⚡

**问题**：同步处理，用户需要等待

**优化**：
1. **异步任务队列**：Celery + Redis
2. **后台处理**：立即返回，后台处理
3. **WebSocket推送**：实时推送处理结果

```python
# 优化前：同步处理
result = analyze_question(image)  # 用户等待5-10秒
return result

# 优化后：异步处理
task_id = celery.send_task('analyze_question', args=[image])
return {'task_id': task_id, 'status': 'processing'}
# 用户立即返回，后台处理完成后通过WebSocket推送
```

**预期提升**：用户体验提升（响应时间从5-10秒降到<1秒）

## 推荐优化顺序

### 阶段1：快速优化（1-2天）✅
1. ✅ **批量接口并行处理**（已完成）
2. **OCR并行调用**（5并发）
3. **数据库批量查询**
4. **添加数据库索引**

### 阶段2：中期优化（3-5天）🚀
1. **AI流式响应**
2. **Redis缓存层**
3. **优化prompt长度**

### 阶段3：长期优化（1-2周）⚡
1. **异步任务队列**
2. **WebSocket实时推送**
3. **CDN加速图片**

## 具体实现建议

### 1. OCR并行处理（立即实施）

在 `question_service_v2.py` 中优化批量OCR调用：

```python
from concurrent.futures import ThreadPoolExecutor

def batch_extract_ocr(images, max_workers=5):
    """批量OCR提取（并行）"""
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(
            lambda img: self._extract_question_content_with_volcengine(img[0], img[1]),
            images
        ))
    return results
```

### 2. 数据库索引优化

```sql
-- 添加索引
CREATE INDEX idx_question_hash ON questions(question_hash);
CREATE INDEX idx_raw_text ON questions(raw_text(100));  -- 前100字符索引
CREATE INDEX idx_created_at ON questions(created_at);
```

### 3. Redis缓存层

```python
import redis
redis_client = redis.Redis(host='localhost', port=6379, db=0)

def get_cached_question(question_hash):
    """从Redis获取缓存"""
    cache_key = f"question:{question_hash}"
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)
    return None

def set_cached_question(question_hash, data, ttl=3600):
    """设置Redis缓存"""
    cache_key = f"question:{question_hash}"
    redis_client.setex(cache_key, ttl, json.dumps(data))
```

## 性能目标

| 场景 | 当前耗时 | 优化后目标 | 提升倍数 |
|------|---------|-----------|---------|
| 单张图片（新题） | 5-10秒 | 2-3秒 | 2-3倍 |
| 批量10张（新题） | 50-100秒 | 5-10秒 | 5-10倍 |
| 单张图片（缓存） | 0.1秒 | 0.05秒 | 2倍 |
| 批量10张（部分缓存） | 20-50秒 | 2-5秒 | 5-10倍 |

## 注意事项

1. **API限流**：注意火山引擎和DeepSeek的API限流
2. **并发控制**：不要设置过高的并发数
3. **错误处理**：并行处理时注意错误隔离
4. **资源消耗**：注意内存和CPU使用

