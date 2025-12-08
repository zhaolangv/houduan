# ngrok 使用说明

## 当前状态

✅ **本地服务正常**：`http://localhost:5000/api/test` 返回正确响应

✅ **ngrok 隧道已建立**：`https://a5413eed8eb6.ngrok-free.app`

⚠️ **警告页面问题**：ngrok 免费版会显示警告页面，需要特殊处理

## 问题说明

当你访问 ngrok 免费版的 URL 时，会看到一个警告页面：
```
You are about to visit: http://localhost:5000
[Visit Site] 按钮
```

这是 ngrok 免费版的正常行为，目的是防止滥用。

## 解决方案

### 方案1：使用测试脚本（最简单）✅

我已经创建了专用测试脚本，会自动处理警告页面：

```powershell
# 进入项目目录
cd D:\BaiduNetdiskDownload\houduan

# 使用 ngrok 专用测试脚本
.\test_ngrok.ps1 https://a5413eed8eb6.ngrok-free.app
```

或者使用通用测试脚本：
```powershell
.\test_tunnel_public.bat https://a5413eed8eb6.ngrok-free.app
```

### 方案2：PowerShell 手动测试

```powershell
# 添加请求头跳过警告页面
$headers = @{'ngrok-skip-browser-warning'='true'}
$response = Invoke-WebRequest -Uri https://a5413eed8eb6.ngrok-free.app/api/test -Headers $headers
$response.Content | ConvertFrom-Json | ConvertTo-Json
```

### 方案3：浏览器首次访问

1. 在浏览器中打开：`https://a5413eed8eb6.ngrok-free.app`
2. 点击 "Visit Site" 按钮（仅首次需要）
3. 之后就可以正常使用 API

### 方案4：使用其他工具（推荐）

如果不想处理 ngrok 的警告页面，可以使用其他工具：

#### cpolar（国内，推荐）
- 国内服务，速度快
- 无警告页面
- 免费版可用

```powershell
# 下载 cpolar.exe 后
.\cpolar.exe http 5000
```

#### localtunnel（无需注册）
- 完全免费
- 无需注册
- 无警告页面

```powershell
npx localtunnel --port 5000
```

## 快速测试命令

### 测试本地服务
```powershell
.\test_api_simple.ps1
# 或
iwr http://localhost:5000/api/test
```

### 测试公网服务（ngrok）
```powershell
.\test_ngrok.ps1 https://a5413eed8eb6.ngrok-free.app
```

### 测试公网服务（其他工具）
```powershell
.\test_tunnel_public.bat https://xxxx.loca.lt
```

## API 端点

使用你的 ngrok URL 访问以下端点：

- **测试接口**：`https://a5413eed8eb6.ngrok-free.app/api/test`
- **分析题目**：`https://a5413eed8eb6.ngrok-free.app/api/questions/analyze`
- **题目详情**：`https://a5413eed8eb6.ngrok-free.app/api/questions/<id>/detail`
- **统计数据**：`https://a5413eed8eb6.ngrok-free.app/api/stats`
- **上传图片**：`https://a5413eed8eb6.ngrok-free.app/api/upload`

## 注意事项

1. **ngrok URL 会变化**：每次重启 ngrok，URL 都会改变（除非使用付费版固定域名）

2. **需要保持运行**：
   - Flask 服务必须运行：`python app.py`
   - ngrok 隧道必须运行：`ngrok http 5000`

3. **首次访问**：如果使用浏览器访问，需要先点击 "Visit Site" 按钮

4. **API 调用**：使用脚本或添加请求头可以跳过警告页面

## 验证内网穿透是否工作

运行以下命令验证：

```powershell
# 方法1：使用测试脚本（推荐）
.\test_ngrok.ps1 https://a5413eed8eb6.ngrok-free.app

# 方法2：手动测试
$headers = @{'ngrok-skip-browser-warning'='true'}
(iwr https://a5413eed8eb6.ngrok-free.app/api/test -Headers $headers).Content
```

如果看到 JSON 响应，说明内网穿透工作正常！

