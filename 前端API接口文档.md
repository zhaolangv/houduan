# 前端API接口文档

## 📋 概述

本文档提供公考题库分析服务的完整API接口文档，包括所有接口的请求格式、参数说明、响应格式和示例代码。

**基础URL**: `http://localhost:5000` (本地) 或您的服务器地址

**内容类型**: 
- 文件上传接口: `multipart/form-data`
- JSON接口: `application/json`

---

## 🚀 快速开始

### 1. 测试服务状态

**接口**: `GET /api/test`

**说明**: 快速检查服务是否正常运行

**请求示例**:
```bash
curl http://localhost:5000/api/test
```

**响应示例**:
```json
{
  "success": true,
  "message": "服务运行正常",
  "timestamp": "2025-12-07 13:03:24",
  "service": "公考题库分析服务",
  "version": "2.0",
  "status": "online",
  "endpoints": {
    "test": "/api/test",
    "health": "/api/health",
    "stats": "/api/stats",
    "analyze": "/api/questions/analyze",
    "analyze_batch": "/api/questions/analyze/batch",
    "extract_batch": "/api/questions/extract/batch",
    "detail": "/api/questions/<question_id>/detail",
    "upload": "/api/upload"
  }
}
```

---

### 2. 健康检查

**接口**: `GET /api/health`

**说明**: 检查服务健康状态，包括数据库连接状态

**请求示例**:
```bash
curl http://localhost:5000/api/health
```

**响应示例**:
```json
{
  "status": "healthy",
  "timestamp": "2025-12-07T13:03:24",
  "service": "公考题库分析服务",
  "checks": {
    "database": {
      "status": "connected",
      "type": "sqlite"
    },
    "upload_folder": {
      "status": "available",
      "path": "uploads"
    }
  }
}
```

---

## 📤 核心接口

### 1. 上传图片

**接口**: `POST /api/upload`

**说明**: 上传单张图片文件到服务器

**Content-Type**: `multipart/form-data`

#### 请求参数

| 参数名 | 类型 | 必需 | 说明 |
|--------|------|------|------|
| `file` | File | ✅ | 图片文件（支持 jpg/png/gif/bmp） |

#### 响应格式

**成功 (200)**:
```json
{
  "success": true,
  "data": {
    "image_url": "file:///path/to/uploads/xxx.jpg",
    "filename": "xxx.jpg",
    "path": "uploads/xxx.jpg"
  }
}
```

**失败 (400/500)**:
```json
{
  "success": false,
  "error": "错误信息"
}
```

#### 前端示例

```javascript
// 使用 FormData
const formData = new FormData();
formData.append('file', fileInput.files[0]);

fetch('http://localhost:5000/api/upload', {
  method: 'POST',
  body: formData
})
.then(response => response.json())
.then(data => {
  console.log('上传成功:', data.data.image_url);
})
.catch(error => console.error('上传失败:', error));
```

---

### 2. 题目内容分析（单个）

**接口**: `POST /api/questions/analyze`

**说明**: 分析单道题目，提取题干和选项（不返回答案和解析）

**Content-Type**: `multipart/form-data`

**特点**:
- ✅ 支持前端提供OCR结果
- ✅ 自动检测重复题目
- ✅ 如果找到重复题，直接从题库提取（瞬间完成）
- ✅ 存入数据库，后续可获取详情

#### 请求参数

| 参数名 | 类型 | 必需 | 说明 |
|--------|------|------|------|
| `image` | File | ✅ | 题目图片文件 |
| `raw_text` | String | ❌ | 前端OCR识别的原始文本 |
| `question_text` | String | ❌ | 前端提取的题干（可能不完整） |
| `options` | String/Array | ❌ | 前端提取的选项（JSON字符串或数组） |
| `question_type` | String | ❌ | 题目类型，默认 "TEXT" |
| `force_reanalyze` | Boolean | ❌ | 是否强制重新分析，默认 false |

#### 响应格式

**成功 (200)**:
```json
{
  "id": "a361db81-d4ba-4b50-a891-0cd6d17897ee",
  "screenshot": "https://...",
  "raw_text": "OCR识别的完整文本",
  "question_text": "完整的题干内容",
  "question_type": "TEXT",
  "options": [
    "A. 选项A",
    "B. 选项B",
    "C. 选项C",
    "D. 选项D"
  ],
  "ocr_confidence": 0.95,
  "from_cache": false,
  "is_duplicate": false,
  "saved_to_db": true
}
```

**如果是重复题**:
```json
{
  "id": "existing-question-id",
  "question_text": "...",
  "options": [...],
  "from_cache": true,
  "is_duplicate": true,
  "similarity_score": 0.92,
  "matched_question_id": "existing-question-id",
  "saved_to_db": false
}
```

#### 前端示例

```javascript
const formData = new FormData();
formData.append('image', fileInput.files[0]);
formData.append('raw_text', frontendOCRResult); // 可选：前端OCR结果
formData.append('question_text', extractedQuestionText); // 可选
formData.append('options', JSON.stringify(['A. ...', 'B. ...'])); // 可选
formData.append('question_type', 'TEXT');
formData.append('force_reanalyze', 'false');

fetch('http://localhost:5000/api/questions/analyze', {
  method: 'POST',
  body: formData
})
.then(response => response.json())
.then(data => {
  console.log('题目ID:', data.id);
  console.log('题干:', data.question_text);
  console.log('选项:', data.options);
  console.log('是否重复:', data.is_duplicate);
  
  // 如果找到重复题，可以立即使用
  if (data.is_duplicate) {
    console.log('✅ 发现重复题，直接从题库提取');
  }
})
.catch(error => console.error('分析失败:', error));
```

---

### 3. 快速批量提取题目和选项

**接口**: `POST /api/questions/extract/batch`

**说明**: 快速批量提取题目和选项，使用本地OCR + DeepSeek AI

**特点**:
- ✅ 使用本地OCR（免费、快速）
- ✅ 使用DeepSeek AI提取（费用最低 ¥0.000117/次）
- ✅ 高并发处理（默认10个并发，50题约2-3分钟）
- ✅ **支持前端提供OCR结果**
- ✅ **自动检测重复题目，从题库直接提取**
- ✅ 包含题目分类和初步答案
- ✅ 不存入数据库（仅提取）

#### 请求格式

支持两种格式：

##### 格式1: multipart/form-data

**Content-Type**: `multipart/form-data`

| 参数名 | 类型 | 必需 | 说明 |
|--------|------|------|------|
| `images[]` | File[] | ✅ | 多个图片文件 |
| `ocr_texts[]` | String[] | ❌ | 前端OCR结果数组（JSON字符串，与images[]一一对应） |
| `max_workers` | Integer | ❌ | 并发数，默认10，范围3-20 |

**示例**:
```javascript
const formData = new FormData();

// 添加图片文件
files.forEach(file => {
  formData.append('images[]', file);
});

// 添加前端OCR结果（如果有）
const ocrTexts = ['OCR文本1', 'OCR文本2', ...];
formData.append('ocr_texts[]', JSON.stringify(ocrTexts));

// 设置并发数
formData.append('max_workers', '10');

fetch('http://localhost:5000/api/questions/extract/batch', {
  method: 'POST',
  body: formData
})
.then(response => response.json())
.then(data => {
  console.log('批量提取完成:', data.statistics);
  data.results.forEach((result, index) => {
    if (result.success) {
      console.log(`题目${index+1}:`, result.question_text);
      console.log('选项:', result.options);
      console.log('是否重复:', result.is_duplicate);
      console.log('题目类型:', result.question_type);
      console.log('初步答案:', result.preliminary_answer);
    }
  });
});
```

##### 格式2: application/json

**Content-Type**: `application/json`

**请求体**:
```json
{
  "images": [
    {
      "filename": "image1.jpg",
      "data": "base64编码的图片数据",
      "ocr_text": "前端OCR结果（可选）"
    },
    {
      "filename": "image2.jpg",
      "data": "base64编码的图片数据",
      "ocr_text": "前端OCR结果（可选）"
    }
  ],
  "max_workers": 10
}
```

**前端示例**:
```javascript
// 将图片转换为base64
async function convertToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

// 批量提取
async function batchExtract(files, frontendOCRTexts = []) {
  const imagesData = await Promise.all(
    files.map(async (file, index) => ({
      filename: file.name,
      data: await convertToBase64(file),
      ocr_text: frontendOCRTexts[index] || null
    }))
  );

  const response = await fetch('http://localhost:5000/api/questions/extract/batch', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      images: imagesData,
      max_workers: 10
    })
  });

  return response.json();
}
```

#### 响应格式

```json
{
  "success": true,
  "results": [
    {
      "success": true,
      "question_text": "完整的题干内容",
      "options": [
        "A. 选项A",
        "B. 选项B",
        "C. 选项C",
        "D. 选项D"
      ],
      "raw_text": "OCR原始文本",
      "question_type": "行测-言语理解",
      "preliminary_answer": "B",
      "answer_reason": "根据文段内容...",
      "question_id": "题目ID（如果是重复题）",
      "is_duplicate": false,
      "similarity": 0.0,
      "ocr_time": 6.5,
      "ai_time": 7.2,
      "total_time": 13.7,
      "input_tokens": 345,
      "output_tokens": 197,
      "total_tokens": 542,
      "cost": 0.000117,
      "extraction_method": "local_ocr_ai"
    },
    {
      "success": true,
      "question_text": "...",
      "options": [...],
      "is_duplicate": true,
      "similarity": 0.92,
      "question_id": "existing-id",
      "ocr_time": 0,
      "ai_time": 0,
      "total_time": 0.01,
      "cost": 0.0,
      "extraction_method": "database_cache"
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

#### 字段说明

**结果字段**:
- `is_duplicate`: 是否检测到重复题
- `similarity`: 相似度分数（0-1）
- `question_id`: 如果是从题库提取的重复题，包含题目ID
- `extraction_method`: 提取方式
  - `"local_ocr_ai"`: 使用本地OCR+AI提取
  - `"database_cache"`: 从题库直接提取（重复题）

#### 性能说明

- **并发10**: 50题约2-3分钟
- **并发20**: 50题约1-2分钟
- **重复题**: 几乎瞬间完成（0.01秒）
- **费用**: 每道题约 ¥0.000117（仅新题，重复题免费）

---

### 4. 批量题目分析（存入数据库）

**接口**: `POST /api/questions/analyze/batch`

**说明**: 批量分析题目并存入数据库，支持前端提供OCR结果

**Content-Type**: `multipart/form-data` 或 `application/json`

**特点**:
- ✅ 支持前端提供OCR结果
- ✅ 自动检测重复题目
- ✅ 存入数据库
- ✅ 后续可获取详情（答案、解析等）

#### 请求格式

##### multipart/form-data

| 参数名 | 类型 | 必需 | 说明 |
|--------|------|------|------|
| `images[]` | File[] | ✅ | 多个图片文件 |
| `raw_texts[]` | String[] | ❌ | 前端OCR原始文本数组（JSON字符串） |
| `question_texts[]` | String[] | ❌ | 前端提取的题干数组（JSON字符串） |
| `options_array[]` | Array[] | ❌ | 前端提取的选项数组（JSON字符串） |
| `question_types[]` | String[] | ❌ | 题目类型数组（JSON字符串） |
| `force_reanalyze` | Boolean | ❌ | 是否强制重新分析，默认 false |

##### application/json

```json
{
  "questions": [
    {
      "image": "base64编码的图片数据",
      "raw_text": "前端OCR结果（可选）",
      "question_text": "题干（可选）",
      "options": ["A. ...", "B. ..."],
      "question_type": "TEXT",
      "force_reanalyze": false
    }
  ]
}
```

#### 响应格式

```json
{
  "results": [
    {
      "success": true,
      "question": {
        "id": "题目ID",
        "question_text": "题干",
        "options": ["A. ...", "B. ..."],
        "is_duplicate": false
      },
      "error": null
    }
  ],
  "total": 2,
  "success_count": 2,
  "failed_count": 0
}
```

---

### 5. 获取题目详情

**接口**: `GET /api/questions/<question_id>/detail`

**说明**: 获取题目的完整详情，包括答案、解析、标签等

#### 请求参数

| 参数名 | 类型 | 位置 | 必需 | 说明 |
|--------|------|------|------|------|
| `question_id` | String | 路径 | ✅ | 题目ID |

#### 响应格式

```json
{
  "id": "题目ID",
  "question_id": "题目ID",
  "correct_answer": "A",
  "explanation": "详细解析...",
  "tags": ["行测-言语理解-阅读理解"],
  "knowledge_points": ["阅读理解"],
  "answer_versions": [
    {
      "id": "答案版本ID",
      "source_name": "AI",
      "source_type": "AI",
      "answer": "A",
      "explanation": "解析内容",
      "confidence": 0.8,
      "is_user_preferred": false
    }
  ],
  "similar_questions": [],
  "difficulty": 3,
  "priority": "中"
}
```

#### 前端示例

```javascript
const questionId = 'a361db81-d4ba-4b50-a891-0cd6d17897ee';

fetch(`http://localhost:5000/api/questions/${questionId}/detail`)
  .then(response => response.json())
  .then(data => {
    console.log('正确答案:', data.correct_answer);
    console.log('解析:', data.explanation);
    console.log('标签:', data.tags);
    console.log('答案版本数:', data.answer_versions.length);
  });
```

---

### 6. 获取统计信息

**接口**: `GET /api/stats`

**说明**: 获取题库统计信息

#### 响应格式

```json
{
  "success": true,
  "data": {
    "questions": 1234,
    "answer_versions": 5678
  }
}
```

---

## 🔍 重复检测功能

### 工作原理

1. **前端提供OCR结果**（可选）:
   - 如果前端已进行OCR识别，可以将结果一起发送
   - 后端会先使用OCR结果检测重复
   - 如果找到重复题（相似度≥85%），直接从题库提取，无需OCR和AI

2. **本地OCR结果检测**:
   - 如果前端未提供OCR结果，后端会先进行OCR识别
   - 使用OCR结果检测重复
   - 找到重复题则直接提取，否则继续AI处理

3. **相似度阈值**: 默认0.85（85%），可配置

### 优势

- ✅ **速度快**: 重复题几乎瞬间完成（0.01秒）
- ✅ **零费用**: 重复题无需调用AI，完全免费
- ✅ **节省资源**: 减少OCR和AI调用
- ✅ **智能匹配**: 即使OCR结果不完整也能匹配

### 响应字段说明

如果检测到重复题，响应中会包含：

```json
{
  "is_duplicate": true,
  "similarity": 0.92,
  "question_id": "existing-question-id",
  "extraction_method": "database_cache",
  "ocr_time": 0,
  "ai_time": 0,
  "total_time": 0.01,
  "cost": 0.0
}
```

---

## 📊 完整工作流程

### 场景1: 前端已做OCR

```
1. 前端OCR识别图片 → 得到OCR文本
2. 前端调用批量提取接口，传递：
   - 图片文件
   - OCR文本（ocr_text字段）
3. 后端：
   - 先检测重复（使用前端OCR文本）
   - 如果重复 → 直接从题库提取（瞬间完成）
   - 如果不重复 → 使用前端OCR文本进行AI提取
```

### 场景2: 前端未做OCR

```
1. 前端直接发送图片
2. 后端：
   - 本地OCR识别
   - 检测重复（使用本地OCR结果）
   - 如果重复 → 从题库提取
   - 如果不重复 → AI提取题目和选项
```

---

## 💡 最佳实践

### 1. 优先提供前端OCR结果

如果前端有能力进行OCR识别，建议：

```javascript
// 前端先做OCR（使用 Tesseract.js 等）
const ocrText = await performOCR(imageFile);

// 然后调用批量提取接口
const formData = new FormData();
formData.append('images[]', imageFile);
formData.append('ocr_texts[]', JSON.stringify([ocrText]));

// 后端会先检测重复，如果重复则瞬间返回
const result = await fetch('/api/questions/extract/batch', {
  method: 'POST',
  body: formData
});
```

**优势**:
- 重复题检测更快（无需等待后端OCR）
- 如果找到重复题，瞬间返回（无需AI调用）
- 节省后端资源

### 2. 批量处理建议

```javascript
// 推荐：批量大小 20-50 题
const BATCH_SIZE = 30;
const MAX_WORKERS = 10; // 并发数

// 分批处理大量题目
for (let i = 0; i < allImages.length; i += BATCH_SIZE) {
  const batch = allImages.slice(i, i + BATCH_SIZE);
  const ocrBatch = ocrTexts.slice(i, i + BATCH_SIZE);
  
  const result = await batchExtract(batch, ocrBatch, MAX_WORKERS);
  
  // 处理结果
  result.results.forEach(question => {
    if (question.success) {
      // 显示题目
      displayQuestion(question);
    }
  });
}
```

### 3. 错误处理

```javascript
try {
  const response = await fetch('/api/questions/extract/batch', {
    method: 'POST',
    body: formData,
    timeout: 300000 // 5分钟超时（50题可能需要）
  });
  
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  
  const data = await response.json();
  
  if (!data.success) {
    console.error('批量提取失败:', data.error);
    return;
  }
  
  // 处理成功和失败的结果
  data.results.forEach((result, index) => {
    if (result.success) {
      console.log(`✅ 题目${index+1}成功`);
    } else {
      console.error(`❌ 题目${index+1}失败:`, result.error);
    }
  });
  
  console.log('统计:', data.statistics);
} catch (error) {
  console.error('请求失败:', error);
}
```

---

## 📝 完整示例代码

### Vue/React 示例

```javascript
// 批量提取题目
async function extractQuestions(files, frontendOCRTexts = []) {
  const formData = new FormData();
  
  // 添加图片
  files.forEach(file => {
    formData.append('images[]', file);
  });
  
  // 添加前端OCR结果（如果有）
  if (frontendOCRTexts.length > 0) {
    formData.append('ocr_texts[]', JSON.stringify(frontendOCRTexts));
  }
  
  // 设置并发数
  formData.append('max_workers', '10');
  
  try {
    const response = await fetch('http://localhost:5000/api/questions/extract/batch', {
      method: 'POST',
      body: formData
    });
    
    const data = await response.json();
    
    if (!data.success) {
      throw new Error(data.error || '批量提取失败');
    }
    
    return {
      results: data.results,
      statistics: data.statistics
    };
  } catch (error) {
    console.error('批量提取错误:', error);
    throw error;
  }
}

// 使用示例
const files = [...]; // 图片文件列表
const ocrTexts = [...]; // 前端OCR结果（可选）

extractQuestions(files, ocrTexts).then(result => {
  console.log('成功:', result.statistics.success_count);
  console.log('失败:', result.statistics.failed_count);
  console.log('总耗时:', result.statistics.total_time, '秒');
  console.log('总费用:', '¥' + result.statistics.total_cost);
  
  // 处理每道题的结果
  result.results.forEach((question, index) => {
    if (question.success) {
      console.log(`题目${index+1}:`, question.question_text);
      console.log('选项:', question.options);
      console.log('题目类型:', question.question_type);
      console.log('初步答案:', question.preliminary_answer);
      
      if (question.is_duplicate) {
        console.log('✅ 这是重复题，直接从题库提取');
      }
    }
  });
});
```

---

## ⚠️ 注意事项

1. **批量大小限制**:
   - `/api/questions/extract/batch`: 最多100题
   - `/api/questions/analyze/batch`: 最多20题

2. **超时设置**:
   - 批量处理可能需要较长时间，建议设置超时时间：
     - 10题: 60秒
     - 50题: 300秒（5分钟）

3. **并发数建议**:
   - 默认10个并发（平衡速度和稳定性）
   - 可以根据服务器性能调整（范围3-20）

4. **前端OCR结果**:
   - 如果提供前端OCR结果，建议至少包含部分题干内容
   - OCR文本长度建议≥10字符，否则可能无法检测重复

5. **重复检测**:
   - 相似度阈值: 85%
   - 如果相似度≥85%，认为是重复题
   - 重复题会瞬间返回，无需OCR和AI处理

---

## 🔗 相关文档

- `批量处理API接口集成.md` - 批量处理详细说明
- `前端集成文档.md` - 前端集成指南
- `功能增强说明.md` - 最新功能说明

---

## 📞 技术支持

如有问题，请检查：
1. 服务是否正常启动（`GET /api/health`）
2. 图片格式是否正确（支持 jpg/png/gif/bmp）
3. 请求格式是否正确
4. 查看服务器日志获取详细错误信息
