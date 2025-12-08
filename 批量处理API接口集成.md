# 批量处理API接口集成方案

## 📋 需求

用户需要处理50道题，担心一次发送一道题处理太慢。需要：
1. ✅ 使用本地OCR + DeepSeek（已验证准确率1.00）
2. ✅ 高并发处理（10-20个并发，50题约2-3分钟）
3. ✅ 集成到现有API接口中，前端可直接调用

---

## 🎯 解决方案

### 新增API接口：`/api/questions/extract/batch`

专门用于快速批量提取题目和选项（不存入数据库，只提取内容）

**特点**：
- ✅ 使用本地OCR + DeepSeek
- ✅ 高并发处理（默认10个并发，可配置）
- ✅ 一次发送一道题（错误隔离好）
- ✅ 实时返回进度和结果

---

## 📝 接口文档

### 接口地址
```
POST /api/questions/extract/batch
```

### 请求格式

支持两种格式：

#### 格式1：multipart/form-data（推荐）

```
Content-Type: multipart/form-data

images[]: 图片文件1
images[]: 图片文件2
...
images[]: 图片文件50

max_workers: 10  (可选，默认10，并发数)
```

#### 格式2：application/json

```json
{
  "images": [
    {
      "filename": "image1.jpg",
      "data": "base64编码的图片数据"
    },
    ...
  ],
  "max_workers": 10  // 可选，默认10
}
```

### 响应格式

```json
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
    },
    {
      "success": false,
      "error": "错误信息",
      "ocr_time": 0,
      "ai_time": 0,
      "total_time": 0
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
```

---

## 🔧 实现代码

### 1. 在 app.py 中添加新接口

```python
from batch_question_service import process_batch_concurrent

@app.route('/api/questions/extract/batch', methods=['POST'])
def extract_questions_batch():
    """
    快速批量提取题目和选项接口（使用本地OCR + DeepSeek）
    
    特点：
    - 使用本地OCR（免费、快速）
    - 使用DeepSeek提取（费用最低、准确率高）
    - 高并发处理（默认10个并发，50题约2-3分钟）
    - 每道题独立请求（错误隔离好）
    
    请求格式1（multipart/form-data）：
    - images[]: 多个图片文件（必需）
    - max_workers: 并发数（可选，默认10，范围3-20）
    
    请求格式2（application/json）：
    {
        "images": [
            {"filename": "image1.jpg", "data": "base64编码"},
            ...
        ],
        "max_workers": 10
    }
    
    返回：
    {
        "success": true,
        "results": [...],
        "statistics": {...}
    }
    """
    try:
        logger.info("=" * 60)
        logger.info("[API] ========== 收到批量提取请求 ==========")
        
        # 批量大小限制
        MAX_BATCH_SIZE = 100
        MAX_WORKERS_DEFAULT = 10
        MAX_WORKERS_MAX = 20
        
        # 判断请求格式
        content_type = request.content_type or ''
        is_json = 'application/json' in content_type
        
        image_files = []
        
        if is_json:
            # JSON格式
            logger.info("[API] 📦 请求格式: application/json")
            data = request.get_json()
            
            if not data or 'images' not in data:
                return jsonify({
                    'success': False,
                    'error': '请求格式错误：缺少images字段',
                    'code': 400
                }), 400
            
            images_data = data.get('images', [])
            if len(images_data) == 0:
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
            for img_data in images_data:
                if 'data' not in img_data:
                    continue
                
                try:
                    image_base64 = img_data['data']
                    if ',' in image_base64:
                        image_base64 = image_base64.split(',', 1)[1]
                    
                    image_bytes = base64.b64decode(image_base64)
                    image_file = BytesIO(image_bytes)
                    image_file.name = img_data.get('filename', 'image.jpg')
                    image_files.append(image_file)
                except Exception as e:
                    logger.warning(f"[API] 图片解码失败: {e}")
                    continue
        
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
        
        logger.info(f"[API] 📊 批量大小: {len(image_files)}, 并发数: {max_workers}")
        
        # 调用批量处理服务
        batch_result = process_batch_concurrent(image_files, max_workers=max_workers)
        
        # 格式化响应
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
        logger.error(f"[API] ❌ 批量提取接口出错: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e),
            'code': 500
        }), 500
```

---

## 📊 性能预期（50道题）

| 并发数 | 处理时间 | 用户体验 |
|--------|---------|---------|
| 串行 | ~20分钟 | ❌ 太慢 |
| 并发5 | ~4-5分钟 | ⚠️ 可接受 |
| **并发10** | **~2-3分钟** | ✅ **推荐** |
| 并发20 | ~1-2分钟 | ✅ 最快 |

**推荐配置**：并发10，50题约2-3分钟

---

## 🔌 前端调用示例

### JavaScript示例

```javascript
// 方式1：上传文件
async function extractBatchQuestions(imageFiles, maxWorkers = 10) {
  const formData = new FormData();
  
  // 添加所有图片文件
  imageFiles.forEach(file => {
    formData.append('images[]', file);
  });
  formData.append('max_workers', maxWorkers.toString());
  
  const response = await fetch('/api/questions/extract/batch', {
    method: 'POST',
    body: formData
  });
  
  const result = await response.json();
  
  if (result.success) {
    console.log(`处理完成: ${result.statistics.success_count}/${result.statistics.total}`);
    console.log(`总耗时: ${result.statistics.total_time.toFixed(1)}秒`);
    console.log(`总费用: ¥${result.statistics.total_cost.toFixed(6)}`);
    
    // 处理结果
    result.results.forEach((item, index) => {
      if (item.success) {
        console.log(`题目${index+1}:`, item.question_text);
        console.log(`选项:`, item.options);
      } else {
        console.error(`题目${index+1}失败:`, item.error);
      }
    });
  }
  
  return result;
}

// 方式2：使用base64
async function extractBatchQuestionsBase64(imagesBase64, maxWorkers = 10) {
  const response = await fetch('/api/questions/extract/batch', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      images: imagesBase64.map((base64, index) => ({
        filename: `image${index+1}.jpg`,
        data: base64
      })),
      max_workers: maxWorkers
    })
  });
  
  return await response.json();
}
```

---

## ✅ 实施步骤

1. ✅ 创建 `batch_question_service.py`（已完成）
2. ⏳ 在 `app.py` 中添加新接口 `/api/questions/extract/batch`
3. ⏳ 测试接口功能
4. ⏳ 前端集成

---

## 📝 完整代码

见下一节：在 `app.py` 中添加接口代码
