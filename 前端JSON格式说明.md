# 前端JSON格式说明 - 批量提取接口

## 📋 批量提取接口 JSON 格式要求

### 接口地址
`POST /api/questions/extract/batch`

### Content-Type
`application/json`

---

## ✅ 正确的JSON格式

### 基本结构

```json
{
  "images": [
    {
      "filename": "题目1.jpg",
      "data": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEAYABgAAD..."
    },
    {
      "filename": "题目2.jpg",
      "data": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEAYABgAAD..."
    }
  ],
  "max_workers": 10
}
```

### 字段说明

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `images` | Array | ✅ | 图片数组 |
| `images[].filename` | String | ✅ | 文件名 |
| `images[].data` | String | ✅ | Base64编码的图片数据（必须包含 `data:image/...;base64,` 前缀） |
| `images[].ocr_text` | String | ❌ | 前端OCR结果（可选） |
| `max_workers` | Integer | ❌ | 并发数，默认10，范围3-20 |

---

## 📝 前端实现示例

### JavaScript/TypeScript

```javascript
// 方法1: 使用 FileReader（推荐）
async function convertImageToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result); // 结果格式: "data:image/jpeg;base64,/9j/4AAQ..."
    reader.onerror = reject;
    reader.readAsDataURL(file); // 关键：使用 readAsDataURL，不要用 readAsArrayBuffer
  });
}

// 批量提取
async function batchExtract(files) {
  // 1. 将所有图片转换为base64
  const imagesData = await Promise.all(
    files.map(async (file) => ({
      filename: file.name,
      data: await convertImageToBase64(file) // 完整的data URL格式
    }))
  );
  
  // 2. 构建请求数据
  const payload = {
    images: imagesData,
    max_workers: 10
  };
  
  // 3. 发送请求
  const response = await fetch('http://localhost:5000/api/questions/extract/batch', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
  });
  
  const result = await response.json();
  return result;
}
```

### React 示例

```jsx
import React, { useState } from 'react';

function BatchExtract() {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(false);
  
  // 转换图片为base64
  const convertToBase64 = (file) => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  };
  
  // 批量提取
  const handleBatchExtract = async () => {
    if (files.length === 0) return;
    
    setLoading(true);
    try {
      // 1. 转换所有图片
      const imagesData = await Promise.all(
        files.map(async (file) => ({
          filename: file.name,
          data: await convertToBase64(file)
        }))
      );
      
      // 2. 发送请求
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
      
      const result = await response.json();
      
      if (result.success) {
        console.log('提取成功！', result.statistics);
        result.results.forEach((item, index) => {
          if (item.success) {
            console.log(`题目${index + 1}:`, item.question_text);
          }
        });
      } else {
        console.error('提取失败:', result.error);
      }
    } catch (error) {
      console.error('请求失败:', error);
    } finally {
      setLoading(false);
    }
  };
  
  return (
    <div>
      <input
        type="file"
        multiple
        accept="image/*"
        onChange={(e) => setFiles(Array.from(e.target.files))}
      />
      <button onClick={handleBatchExtract} disabled={loading || files.length === 0}>
        {loading ? '处理中...' : '批量提取'}
      </button>
    </div>
  );
}
```

### Vue 示例

```vue
<template>
  <div>
    <input
      type="file"
      multiple
      accept="image/*"
      @change="handleFileChange"
    />
    <button @click="batchExtract" :disabled="loading || files.length === 0">
      {{ loading ? '处理中...' : '批量提取' }}
    </button>
  </div>
</template>

<script>
export default {
  data() {
    return {
      files: [],
      loading: false
    };
  },
  methods: {
    handleFileChange(e) {
      this.files = Array.from(e.target.files);
    },
    
    convertToBase64(file) {
      return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = reject;
        reader.readAsDataURL(file);
      });
    },
    
    async batchExtract() {
      if (this.files.length === 0) return;
      
      this.loading = true;
      try {
        // 1. 转换所有图片
        const imagesData = await Promise.all(
          this.files.map(async (file) => ({
            filename: file.name,
            data: await this.convertToBase64(file)
          }))
        );
        
        // 2. 发送请求
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
        
        const result = await response.json();
        
        if (result.success) {
          console.log('提取成功！', result.statistics);
        } else {
          console.error('提取失败:', result.error);
        }
      } catch (error) {
        console.error('请求失败:', error);
      } finally {
        this.loading = false;
      }
    }
  }
};
</script>
```

---

## ❌ 常见错误格式

### 错误1: data字段缺失或格式不对

```json
// ❌ 错误：缺少data字段
{
  "images": [
    {
      "filename": "题目1.jpg"
      // 缺少 data 字段！
    }
  ]
}

// ✅ 正确
{
  "images": [
    {
      "filename": "题目1.jpg",
      "data": "data:image/jpeg;base64,/9j/4AAQ..."
    }
  ]
}
```

### 错误2: data不是完整的data URL

```json
// ❌ 错误：只有base64数据，没有前缀
{
  "images": [
    {
      "filename": "题目1.jpg",
      "data": "/9j/4AAQSkZJRg..." // 缺少 "data:image/jpeg;base64," 前缀
    }
  ]
}

// ✅ 正确：完整的data URL格式
{
  "images": [
    {
      "filename": "题目1.jpg",
      "data": "data:image/jpeg;base64,/9j/4AAQSkZJRg..." // 完整格式
    }
  ]
}
```

### 错误3: images不是数组

```json
// ❌ 错误：images不是数组
{
  "images": "题目1.jpg" // 应该是数组
}

// ✅ 正确
{
  "images": [
    {
      "filename": "题目1.jpg",
      "data": "data:image/jpeg;base64,/9j/4AAQ..."
    }
  ]
}
```

### 错误4: 数组元素不是对象

```json
// ❌ 错误：数组元素是字符串
{
  "images": [
    "data:image/jpeg;base64,/9j/4AAQ...", // 应该是对象
    "data:image/jpeg;base64,/9j/4AAQ..."
  ]
}

// ✅ 正确：数组元素是对象
{
  "images": [
    {
      "filename": "题目1.jpg",
      "data": "data:image/jpeg;base64,/9j/4AAQ..."
    },
    {
      "filename": "题目2.jpg",
      "data": "data:image/jpeg;base64,/9j/4AAQ..."
    }
  ]
}
```

---

## 🔍 调试技巧

### 1. 检查数据格式

```javascript
// 发送请求前，先检查数据格式
const imagesData = await Promise.all(
  files.map(async (file) => ({
    filename: file.name,
    data: await convertToBase64(file)
  }))
);

// 打印检查
console.log('发送的数据:', {
  images: imagesData.map(img => ({
    filename: img.filename,
    dataLength: img.data.length,
    dataPrefix: img.data.substring(0, 30), // 查看前缀
    hasDataPrefix: img.data.startsWith('data:image')
  }))
});

// 确保每个图片都有data字段
imagesData.forEach((img, index) => {
  if (!img.data) {
    console.error(`图片${index + 1}缺少data字段`);
  }
  if (!img.data.startsWith('data:image')) {
    console.error(`图片${index + 1}的data格式不对，应该是data:image/...;base64,格式`);
  }
});
```

### 2. 查看服务器错误响应

```javascript
const response = await fetch('http://localhost:5000/api/questions/extract/batch', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify(payload)
});

if (!response.ok) {
  const errorData = await response.json();
  console.error('错误信息:', errorData.error);
  console.error('错误详情:', errorData.details);
}
```

---

## ✅ 完整示例

### 完整的工作示例

```javascript
// 完整的批量提取函数
async function batchExtractQuestions(files, options = {}) {
  const {
    maxWorkers = 10,
    frontendOCRTexts = [],
    apiBase = 'http://localhost:5000'
  } = options;
  
  // 1. 转换图片为base64
  console.log('开始转换图片...');
  const imagesData = await Promise.all(
    files.map(async (file, index) => {
      const base64 = await convertImageToBase64(file);
      
      // 验证格式
      if (!base64.startsWith('data:image')) {
        throw new Error(`图片 ${file.name} 的base64格式不正确`);
      }
      
      return {
        filename: file.name,
        data: base64,
        ocr_text: frontendOCRTexts[index] || null
      };
    })
  );
  
  console.log(`已转换 ${imagesData.length} 张图片`);
  
  // 2. 构建请求数据
  const payload = {
    images: imagesData,
    max_workers: maxWorkers
  };
  
  // 3. 发送请求
  console.log('发送批量提取请求...');
  const response = await fetch(`${apiBase}/api/questions/extract/batch`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
  });
  
  // 4. 处理响应
  const result = await response.json();
  
  if (!response.ok || !result.success) {
    const errorMsg = result.error || '批量提取失败';
    const details = result.details || [];
    
    console.error('批量提取失败:', errorMsg);
    if (details.length > 0) {
      console.error('错误详情:', details);
    }
    
    throw new Error(errorMsg);
  }
  
  console.log('批量提取成功！');
  console.log('统计信息:', result.statistics);
  
  return result;
}

// 辅助函数：转换图片为base64
function convertImageToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error(`读取文件 ${file.name} 失败`));
    reader.readAsDataURL(file);
  });
}

// 使用示例
const files = document.querySelector('input[type="file"]').files;
batchExtractQuestions(Array.from(files), {
  maxWorkers: 10,
  frontendOCRTexts: [] // 如果有前端OCR结果，传入数组
})
  .then(result => {
    console.log('提取成功！', result);
  })
  .catch(error => {
    console.error('提取失败:', error);
  });
```

---

## 📞 问题排查

如果遇到"缺少data字段"错误，请检查：

1. ✅ `images` 是否是数组
2. ✅ 数组中每个元素是否是对象
3. ✅ 每个对象是否有 `data` 字段
4. ✅ `data` 字段的值是否是完整的data URL格式（`data:image/...;base64,...`）
5. ✅ 是否使用了 `FileReader.readAsDataURL()` 而不是 `readAsArrayBuffer()`

---

## 🔗 相关文档

- `前端API接口文档.md` - 完整的API接口文档
- `功能增强说明.md` - 功能说明
