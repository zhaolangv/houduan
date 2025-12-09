# Android 版本验证API调用指南

## 📱 完整集成示例

本指南提供Android应用的完整版本验证API调用代码。

---

## 🔑 核心步骤

1. **获取设备ID**（Android ID）
2. **调用版本验证API**（`/api/version`）
3. **处理响应**（检查是否需要更新）
4. **下载APK**（如果需要更新）

---

## 📦 依赖配置

在 `build.gradle` (Module: app) 中添加：

```gradle
dependencies {
    implementation 'com.squareup.okhttp3:okhttp:4.12.0'
}
```

---

## 💻 完整代码示例

### VersionChecker.kt

```kotlin
package com.yourpackage.app

import android.app.Activity
import android.app.DownloadManager
import android.content.Context
import android.content.SharedPreferences
import android.net.Uri
import android.os.Environment
import android.provider.Settings
import android.util.Log
import okhttp3.*
import org.json.JSONObject
import java.io.IOException
import java.util.UUID

class VersionChecker(private val context: Context) {
    private val client = OkHttpClient()
    private val apiBaseUrl = "https://your-api.com" // 替换为你的API地址
    private val TAG = "VersionChecker"
    
    /**
     * 获取设备ID（Android ID或UUID）
     */
    private fun getDeviceId(): String {
        return try {
            // 优先使用Android ID（推荐）
            Settings.Secure.getString(
                context.contentResolver,
                Settings.Secure.ANDROID_ID
            ) ?: run {
                // 如果Android ID不可用，使用本地存储的UUID
                val prefs = context.getSharedPreferences("app_prefs", Context.MODE_PRIVATE)
                var deviceId = prefs.getString("device_id", null)
                if (deviceId == null) {
                    deviceId = UUID.randomUUID().toString()
                    prefs.edit().putString("device_id", deviceId).apply()
                }
                deviceId
            }
        } catch (e: Exception) {
            Log.e(TAG, "获取设备ID失败", e)
            UUID.randomUUID().toString()
        }
    }
    
    /**
     * 检查版本并处理更新
     * 
     * @param onUpdateRequired 需要更新时的回调
     * @param onNoUpdate 不需要更新时的回调（可选）
     * @param onError 错误时的回调（可选）
     */
    fun checkVersion(
        onUpdateRequired: (latestVersion: String, downloadUrl: String, releaseNotes: String) -> Unit,
        onNoUpdate: () -> Unit = {},
        onError: (error: String) -> Unit = {}
    ) {
        val deviceId = getDeviceId()
        val appVersion = BuildConfig.VERSION_NAME // 如 "1.0.0"
        
        // 构建请求URL
        val url = "$apiBaseUrl/api/version?client_version=$appVersion"
        
        Log.d(TAG, "开始检查版本: deviceId=$deviceId, appVersion=$appVersion")
        
        // 创建请求
        val request = Request.Builder()
            .url(url)
            .addHeader("X-Device-ID", deviceId)
            .addHeader("X-App-Version", appVersion)
            .get()
            .build()
        
        // 发送请求
        client.newCall(request).enqueue(object : Callback {
            override fun onResponse(call: Call, response: Response) {
                try {
                    if (!response.isSuccessful) {
                        val errorMsg = "HTTP ${response.code}: ${response.message}"
                        Log.e(TAG, errorMsg)
                        (context as? Activity)?.runOnUiThread {
                            onError(errorMsg)
                        }
                        return
                    }
                    
                    val responseBody = response.body?.string() ?: ""
                    val json = JSONObject(responseBody)
                    
                    if (!json.optBoolean("success", false)) {
                        val errorMsg = json.optString("error", "未知错误")
                        Log.e(TAG, "版本检查失败: $errorMsg")
                        (context as? Activity)?.runOnUiThread {
                            onError(errorMsg)
                        }
                        return
                    }
                    
                    // 解析版本信息
                    val versionInfo = json.getJSONObject("version")
                    val updateInfo = json.getJSONObject("update")
                    
                    val serverVersion = versionInfo.getString("app_version")
                    val requiresUpdate = updateInfo.getBoolean("required")
                    val latestVersion = updateInfo.getString("latest_version")
                    val downloadUrl = updateInfo.getString("download_url")
                    val releaseNotes = updateInfo.optString("release_notes", "")
                    
                    Log.d(TAG, "版本检查完成: 客户端=$appVersion, 服务端=$serverVersion, 需要更新=$requiresUpdate")
                    
                    // 在主线程处理结果
                    (context as? Activity)?.runOnUiThread {
                        if (requiresUpdate) {
                            // 需要更新
                            onUpdateRequired(latestVersion, downloadUrl, releaseNotes)
                        } else {
                            // 不需要更新
                            onNoUpdate()
                        }
                    }
                    
                } catch (e: Exception) {
                    Log.e(TAG, "解析响应失败", e)
                    (context as? Activity)?.runOnUiThread {
                        onError("解析响应失败: ${e.message}")
                    }
                }
            }
            
            override fun onFailure(call: Call, e: IOException) {
                Log.e(TAG, "版本检查失败", e)
                (context as? Activity)?.runOnUiThread {
                    onError("网络错误: ${e.message}")
                }
            }
        })
    }
    
    /**
     * 下载APK
     * 
     * @param downloadUrl APK下载URL（相对路径或完整URL）
     * @param filename 保存的文件名（可选）
     */
    fun downloadAPK(downloadUrl: String, filename: String? = null) {
        try {
            // 构建完整URL
            val fullUrl = if (downloadUrl.startsWith("http")) {
                downloadUrl
            } else {
                "$apiBaseUrl$downloadUrl"
            }
            
            val finalFilename = filename ?: "app-update.apk"
            
            Log.d(TAG, "开始下载APK: $fullUrl")
            
            val request = DownloadManager.Request(Uri.parse(fullUrl))
            request.setDestinationInExternalPublicDir(
                Environment.DIRECTORY_DOWNLOADS,
                finalFilename
            )
            request.setNotificationVisibility(
                DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED
            )
            request.setTitle("应用更新")
            request.setDescription("正在下载新版本...")
            request.setAllowedOverMetered(true) // 允许使用移动数据
            request.setAllowedOverRoaming(true) // 允许漫游时下载
            
            val downloadManager = context.getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager
            val downloadId = downloadManager.enqueue(request)
            
            Log.d(TAG, "APK下载已开始，下载ID: $downloadId")
        } catch (e: Exception) {
            Log.e(TAG, "下载APK失败", e)
        }
    }
}
```

---

## 🚀 使用示例

### MainActivity.kt

```kotlin
package com.yourpackage.app

import android.app.AlertDialog
import android.os.Bundle
import android.util.Log
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity

class MainActivity : AppCompatActivity() {
    private lateinit var versionChecker: VersionChecker
    private val TAG = "MainActivity"
    
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        
        versionChecker = VersionChecker(this)
        
        // 应用启动时检查版本
        checkVersionOnStartup()
    }
    
    /**
     * 应用启动时检查版本
     */
    private fun checkVersionOnStartup() {
        versionChecker.checkVersion(
            onUpdateRequired = { latestVersion, downloadUrl, releaseNotes ->
                // 显示更新对话框
                showUpdateDialog(latestVersion, downloadUrl, releaseNotes)
            },
            onNoUpdate = {
                Log.d(TAG, "应用已是最新版本")
                // 可以显示提示或什么都不做
            },
            onError = { error ->
                Log.e(TAG, "版本检查失败: $error")
                // 可以选择忽略错误，不影响应用使用
                // 或者显示错误提示
                // Toast.makeText(this, "版本检查失败，请稍后重试", Toast.LENGTH_SHORT).show()
            }
        )
    }
    
    /**
     * 显示更新对话框
     */
    private fun showUpdateDialog(version: String, downloadUrl: String, releaseNotes: String) {
        val message = if (releaseNotes.isNotEmpty()) {
            releaseNotes
        } else {
            "新版本 $version 已发布，建议立即更新"
        }
        
        AlertDialog.Builder(this)
            .setTitle("发现新版本 $version")
            .setMessage(message)
            .setPositiveButton("立即更新") { _, _ ->
                // 下载APK
                versionChecker.downloadAPK(downloadUrl, "app-v$version.apk")
                Toast.makeText(this, "开始下载更新...", Toast.LENGTH_SHORT).show()
            }
            .setNegativeButton("稍后", null)
            .setCancelable(true) // 允许取消（非强制更新）
            .show()
    }
    
    /**
     * 强制更新对话框（可选）
     */
    private fun showForceUpdateDialog(version: String, downloadUrl: String, releaseNotes: String) {
        val message = if (releaseNotes.isNotEmpty()) {
            releaseNotes
        } else {
            "新版本 $version 已发布，必须更新才能继续使用"
        }
        
        AlertDialog.Builder(this)
            .setTitle("发现新版本 $version")
            .setMessage(message)
            .setPositiveButton("立即更新") { _, _ ->
                // 下载APK
                versionChecker.downloadAPK(downloadUrl, "app-v$version.apk")
                Toast.makeText(this, "开始下载更新...", Toast.LENGTH_SHORT).show()
            }
            .setCancelable(false) // 不允许取消（强制更新）
            .show()
    }
}
```

---

## 🔧 配置说明

### 1. 修改API地址

在 `VersionChecker.kt` 中修改：

```kotlin
private val apiBaseUrl = "https://your-api.com" // 替换为你的实际API地址
```

**示例**：
- 开发环境：`http://localhost:5000`
- 生产环境：`https://your-app.railway.app`

### 2. 获取应用版本号

确保 `BuildConfig.VERSION_NAME` 已正确配置：

在 `build.gradle` (Module: app) 中：

```gradle
android {
    defaultConfig {
        versionCode 1
        versionName "1.0.0" // 版本号
    }
}
```

---

## 📋 完整调用流程

```
1. 应用启动（MainActivity.onCreate）
   ↓
2. 创建VersionChecker实例
   ↓
3. 调用checkVersion()
   ↓
4. 获取设备ID（Android ID）
   ↓
5. 发送HTTP请求到 /api/version
   ↓
6. 服务器返回版本信息和更新提示
   ↓
7. 如果 requiresUpdate=true
   ↓
8. 显示更新对话框
   ↓
9. 用户点击"立即更新"
   ↓
10. 使用DownloadManager下载APK
```

---

## 🎯 最佳实践

### 1. 应用启动时检查

```kotlin
override fun onCreate(savedInstanceState: Bundle?) {
    super.onCreate(savedInstanceState)
    setContentView(R.layout.activity_main)
    
    // 立即检查版本（不阻塞UI）
    versionChecker.checkVersion(...)
}
```

### 2. 定期检查（可选）

```kotlin
// 使用AlarmManager或WorkManager定期检查
// 例如：每天检查一次
```

### 3. 错误处理

```kotlin
onError = { error ->
    // 静默失败，不影响应用使用
    Log.e(TAG, "版本检查失败: $error")
    // 不显示错误提示给用户，避免影响体验
}
```

### 4. 强制更新（可选）

如果需要强制更新，可以：

```kotlin
if (requiresUpdate && isForceUpdate) {
    // 显示不可取消的对话框
    showForceUpdateDialog(...)
    // 或者直接下载
    versionChecker.downloadAPK(downloadUrl)
}
```

---

## 🔒 权限配置

在 `AndroidManifest.xml` 中添加：

```xml
<!-- 网络权限 -->
<uses-permission android:name="android.permission.INTERNET" />

<!-- 下载权限（Android 10+需要） -->
<uses-permission android:name="android.permission.WRITE_EXTERNAL_STORAGE" 
    android:maxSdkVersion="28" />
<uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE" 
    android:maxSdkVersion="28" />

<!-- 安装APK权限（Android 8.0+需要） -->
<uses-permission android:name="android.permission.REQUEST_INSTALL_PACKAGES" />
```

---

## 📥 下载完成后自动安装（可选）

如果需要下载完成后自动安装，可以监听下载完成事件：

```kotlin
// 在MainActivity中
private val downloadCompleteReceiver = object : BroadcastReceiver() {
    override fun onReceive(context: Context?, intent: Intent?) {
        val downloadId = intent?.getLongExtra(DownloadManager.EXTRA_DOWNLOAD_ID, -1)
        if (downloadId != -1) {
            // 检查下载是否成功
            val downloadManager = getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager
            val query = DownloadManager.Query().setFilterById(downloadId)
            val cursor = downloadManager.query(query)
            
            if (cursor.moveToFirst()) {
                val status = cursor.getInt(cursor.getColumnIndex(DownloadManager.COLUMN_STATUS))
                if (status == DownloadManager.STATUS_SUCCESSFUL) {
                    val uri = cursor.getString(cursor.getColumnIndex(DownloadManager.COLUMN_LOCAL_URI))
                    // 安装APK
                    installAPK(Uri.parse(uri))
                }
            }
            cursor.close()
        }
    }
}

override fun onResume() {
    super.onResume()
    registerReceiver(downloadCompleteReceiver, IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE))
}

override fun onPause() {
    super.onPause()
    unregisterReceiver(downloadCompleteReceiver)
}

private fun installAPK(uri: Uri) {
    val intent = Intent(Intent.ACTION_VIEW).apply {
        setDataAndType(uri, "application/vnd.android.package-archive")
        flags = Intent.FLAG_ACTIVITY_NEW_TASK
        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    }
    startActivity(intent)
}
```

---

## ✅ 快速集成（最小代码）

最简单的集成方式：

```kotlin
// 1. 在Application或MainActivity中
val versionChecker = VersionChecker(this)

// 2. 应用启动时检查
versionChecker.checkVersion(
    onUpdateRequired = { version, url, notes ->
        AlertDialog.Builder(this)
            .setTitle("发现新版本 $version")
            .setMessage(notes)
            .setPositiveButton("更新") { _, _ ->
                versionChecker.downloadAPK(url)
            }
            .show()
    }
)
```

---

## 🧪 测试

### 测试版本检查

```kotlin
// 在测试环境中，可以手动触发版本检查
button.setOnClickListener {
    versionChecker.checkVersion(
        onUpdateRequired = { version, url, notes ->
            Log.d(TAG, "需要更新到版本: $version")
            // 显示对话框或直接下载
        }
    )
}
```

### 测试API调用

```bash
# 使用curl测试（模拟Android请求）
curl -H "X-Device-ID: test-device-123" \
     -H "X-App-Version: 1.0.0" \
     "http://localhost:5000/api/version?client_version=1.0.0"
```

---

## 📝 注意事项

1. **设备ID稳定性**
   - Android ID在应用卸载重装后可能变化
   - 建议结合SharedPreferences存储的UUID作为备选

2. **网络错误处理**
   - 版本检查失败不应该阻止应用使用
   - 建议静默失败，只记录日志

3. **下载权限**
   - Android 10+需要特殊处理文件下载
   - 考虑使用FileProvider共享文件

4. **HTTPS**
   - 生产环境必须使用HTTPS
   - 确保API地址使用 `https://`

---

## 🎉 完成！

现在你的Android应用可以：
- ✅ 自动检查版本
- ✅ 提示用户更新
- ✅ 下载最新APK
- ✅ 自动记录用户活动（用于留存率统计）

**详细的前端集成指南请查看**: `前端版本验证集成指南.md`
