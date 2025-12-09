# APK版本更新功能说明

## 📱 功能概述

实现了应用版本检查和APK自动下载功能。当前端版本与后端版本不一致时，可以自动提示用户下载最新版本的APK。

---

## 🔌 API接口

### 1. 版本检查接口

**接口**: `GET /api/version`

**请求参数**（可选）:
- `client_version`: 客户端版本号（如 "1.0.0"）

**示例请求**:
```bash
# 不检查版本（只获取服务端版本信息）
curl http://localhost:5000/api/version

# 检查版本（传入客户端版本）
curl "http://localhost:5000/api/version?client_version=1.0.0"
```

**返回示例**:
```json
{
  "success": true,
  "version": {
    "app_version": "2.0.0",
    "api_version": "2.0",
    "build_time": "2025-01-07T12:00:00",
    "python_version": "3.11.0",
    "flask_version": "3.0.0"
  },
  "update": {
    "required": true,
    "latest_version": "2.0.0",
    "download_url": "/api/apk/download",
    "release_notes": "修复了若干bug，优化了性能"
  },
  "service": "公考题库分析服务",
  "status": "online"
}
```

**字段说明**:
- `update.required`: `true` 表示需要更新，`false` 表示不需要
- `update.latest_version`: 最新版本号
- `update.download_url`: APK下载链接
- `update.release_notes`: 更新说明

---

### 2. APK下载接口

**接口**: `GET /api/apk/download`

**功能**: 下载最新的APK文件

**示例请求**:
```bash
curl -O http://localhost:5000/api/apk/download
```

**返回**: APK文件（二进制流）

---

### 3. APK上传接口（管理员用）

**接口**: `POST /api/apk/upload`

**请求格式**: `multipart/form-data`

**请求参数**:
- `file`: APK文件（必需）
- `version`: 版本号（如 "2.0.0"）（必需）
- `release_notes`: 更新说明（可选）

**示例请求**:
```bash
curl -X POST \
  -F "file=@app-v2.0.0.apk" \
  -F "version=2.0.0" \
  -F "release_notes=修复了若干bug，优化了性能" \
  http://localhost:5000/api/apk/upload
```

**返回示例**:
```json
{
  "success": true,
  "message": "APK上传成功",
  "version": "2.0.0",
  "filename": "app-v2.0.0.apk",
  "file_size": 12345678
}
```

---

### 4. APK信息查询接口

**接口**: `GET /api/apk/info`

**功能**: 获取当前APK的版本信息和下载链接

**示例请求**:
```bash
curl http://localhost:5000/api/apk/info
```

**返回示例**:
```json
{
  "success": true,
  "apk": {
    "version": "2.0.0",
    "filename": "app-v2.0.0.apk",
    "release_notes": "修复了若干bug，优化了性能",
    "upload_time": "2025-01-07T12:00:00",
    "file_size": 12345678,
    "download_url": "/api/apk/download"
  }
}
```

---

## 📱 前端集成示例

### React/React Native 示例

```javascript
// 检查版本并下载APK
async function checkVersionAndUpdate() {
  const clientVersion = '1.0.0'; // 从应用配置中获取
  
  try {
    const response = await fetch(
      `https://your-api.com/api/version?client_version=${clientVersion}`
    );
    const data = await response.json();
    
    if (data.update && data.update.required) {
      // 显示更新提示
      const shouldUpdate = confirm(
        `发现新版本 ${data.update.latest_version}\n\n` +
        `${data.update.release_notes}\n\n` +
        `是否立即更新？`
      );
      
      if (shouldUpdate) {
        // 下载APK
        window.location.href = data.update.download_url;
        // 或使用fetch下载
        // downloadAPK(data.update.download_url);
      }
    }
  } catch (error) {
    console.error('版本检查失败:', error);
  }
}

// 下载APK文件
async function downloadAPK(downloadUrl) {
  try {
    const response = await fetch(downloadUrl);
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'app.apk';
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  } catch (error) {
    console.error('APK下载失败:', error);
  }
}
```

### Android 原生示例（Kotlin）

```kotlin
// 检查版本
fun checkVersion() {
    val clientVersion = BuildConfig.VERSION_NAME // 如 "1.0.0"
    
    val url = "https://your-api.com/api/version?client_version=$clientVersion"
    
    val request = Request.Builder()
        .url(url)
        .build()
    
    client.newCall(request).enqueue(object : Callback {
        override fun onResponse(call: Call, response: Response) {
            val json = JSONObject(response.body?.string() ?: "")
            val update = json.getJSONObject("update")
            
            if (update.getBoolean("required")) {
                // 在主线程显示更新对话框
                runOnUiThread {
                    showUpdateDialog(
                        update.getString("latest_version"),
                        update.getString("release_notes"),
                        update.getString("download_url")
                    )
                }
            }
        }
        
        override fun onFailure(call: Call, e: IOException) {
            Log.e("VersionCheck", "检查失败", e)
        }
    })
}

// 显示更新对话框并下载
fun showUpdateDialog(version: String, notes: String, downloadUrl: String) {
    AlertDialog.Builder(this)
        .setTitle("发现新版本 $version")
        .setMessage(notes)
        .setPositiveButton("立即更新") { _, _ ->
            downloadAPK(downloadUrl)
        }
        .setNegativeButton("稍后", null)
        .show()
}

// 下载APK
fun downloadAPK(downloadUrl: String) {
    val request = DownloadManager.Request(Uri.parse(downloadUrl))
    request.setDestinationInExternalPublicDir(
        Environment.DIRECTORY_DOWNLOADS,
        "app-update.apk"
    )
    request.setNotificationVisibility(
        DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED
    )
    
    val downloadManager = getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager
    downloadManager.enqueue(request)
}
```

---

## 🔧 管理员操作

### 上传新版本APK

1. **准备APK文件**
   - 确保APK文件已签名
   - 建议文件名包含版本号，如 `app-v2.0.0.apk`

2. **上传APK**
   ```bash
   curl -X POST \
     -F "file=@app-v2.0.0.apk" \
     -F "version=2.0.0" \
     -F "release_notes=修复了若干bug，优化了性能" \
     https://your-api.com/api/apk/upload
   ```

3. **验证上传**
   ```bash
   # 检查APK信息
   curl https://your-api.com/api/apk/info
   
   # 测试下载
   curl -O https://your-api.com/api/apk/download
   ```

---

## 📁 文件结构

上传APK后，会在服务器上创建以下文件结构：

```
项目根目录/
├── apk/
│   ├── app-v2.0.0.apk          # APK文件
│   └── version.json            # 版本信息文件
```

`version.json` 内容示例：
```json
{
  "version": "2.0.0",
  "filename": "app-v2.0.0.apk",
  "release_notes": "修复了若干bug，优化了性能",
  "upload_time": "2025-01-07T12:00:00",
  "file_size": 12345678
}
```

---

## 🔒 安全建议

1. **APK上传接口应该添加认证**
   - 建议添加API密钥或JWT认证
   - 只有管理员才能上传APK

2. **APK文件验证**
   - 验证APK文件签名
   - 检查文件大小限制
   - 扫描恶意软件

3. **HTTPS**
   - 生产环境必须使用HTTPS
   - 防止APK文件被篡改

---

## 🚀 部署到Supabase Storage（可选）

如果需要将APK存储在Supabase Storage中，可以修改代码：

1. 上传APK时，同时上传到Supabase Storage
2. 下载APK时，从Supabase Storage获取公开URL
3. 这样可以节省服务器存储空间

---

## 📝 版本号格式

建议使用语义化版本号（Semantic Versioning）：
- 格式：`主版本号.次版本号.修订号`（如 `2.0.0`）
- 主版本号：不兼容的API修改
- 次版本号：向下兼容的功能性新增
- 修订号：向下兼容的问题修正

---

## ✅ 测试清单

- [ ] 上传APK文件
- [ ] 检查版本接口（不带客户端版本）
- [ ] 检查版本接口（带旧版本号，应该提示更新）
- [ ] 检查版本接口（带最新版本号，不应该提示更新）
- [ ] 下载APK文件
- [ ] 查询APK信息

---

## 🆘 常见问题

### Q1: 上传APK后，版本检查仍然显示不需要更新

**原因**：版本号比较逻辑可能有问题

**解决**：
1. 检查 `version.json` 文件中的版本号是否正确
2. 确认客户端传入的版本号格式正确（如 "1.0.0"）

### Q2: APK下载失败

**原因**：
1. APK文件不存在
2. 文件权限问题

**解决**：
1. 检查 `apk/` 目录中是否有APK文件
2. 检查文件权限
3. 查看服务器日志

### Q3: 如何支持多个APK版本？

当前实现只支持一个最新版本的APK。如果需要支持多个版本，可以：
1. 修改版本信息文件，支持版本列表
2. 下载接口添加版本参数
3. 根据版本号返回对应的APK文件

---

**功能已就绪！** 🎉
