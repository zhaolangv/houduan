# Supabase 部署指南

本指南将帮助您将这个Flask项目部署到生产环境，使用Supabase作为数据库和存储服务。

## 📋 目录

1. [概述](#概述)
2. [Supabase配置](#supabase配置)
3. [选择部署平台](#选择部署平台)
4. [部署步骤](#部署步骤)
5. [环境变量配置](#环境变量配置)
6. [数据库迁移](#数据库迁移)
7. [验证部署](#验证部署)
8. [常见问题](#常见问题)

---

## 概述

### 架构说明

由于Supabase Edge Functions只支持Deno/TypeScript，不支持Python，我们需要：

1. **Supabase服务**（数据库 + 存储）
   - PostgreSQL数据库：存储题目和答案数据
   - Storage：存储图片文件

2. **Flask应用**（部署到其他平台）
   - 部署到支持Python的平台（Railway、Render、Fly.io等）
   - 通过环境变量连接Supabase服务

### 部署流程图

```
┌─────────────────┐
│  Flask应用      │  ← 部署到 Railway/Render/Fly.io
│  (Python)       │
└────────┬────────┘
         │
         │ 通过环境变量连接
         │
    ┌────┴────┐
    │         │
┌───▼───┐ ┌──▼──────┐
│数据库 │ │ Storage │
│PostgreSQL│ │ 图片存储 │
└────────┘ └─────────┘
    ↑           ↑
    └───────────┘
    Supabase 服务
```

---

## Supabase配置

### 步骤1: 创建Supabase项目

1. 访问 [Supabase官网](https://supabase.com)
2. 注册/登录账号
3. 点击 "New Project"
4. 填写项目信息：
   - **Name**: 项目名称（如：gongkao-backend）
   - **Database Password**: 设置数据库密码（**重要：请保存此密码**）
   - **Region**: 选择离您最近的区域（如：Northeast Asia (Seoul)）
5. 点击 "Create new project"
6. 等待项目创建完成（约2分钟）

### 步骤2: 获取数据库连接字符串

1. 在Supabase Dashboard中，进入 **Settings** → **Database**
2. 找到 **Connection string** 部分
3. 选择 **Session pooler** 模式（推荐，支持高并发）
4. 复制连接字符串，格式类似：
   ```
   postgresql://postgres.[PROJECT-REF]:[YOUR-PASSWORD]@aws-1-ap-northeast-2.pooler.supabase.com:5432/postgres
   ```
5. **重要**：将 `[YOUR-PASSWORD]` 替换为步骤1中设置的数据库密码

### 步骤3: 配置Storage存储桶

1. 在Supabase Dashboard中，进入 **Storage**
2. 点击 **New bucket**
3. 填写信息：
   - **Name**: `question-images`（或自定义名称）
   - **Public bucket**: ✅ 勾选（允许公开访问图片）
4. 点击 **Create bucket**

### 步骤4: 获取API密钥

1. 在Supabase Dashboard中，进入 **Settings** → **API**
2. 复制以下信息：
   - **Project URL**: `https://[PROJECT-REF].supabase.co`
   - **anon public key**: 用于客户端访问
   - **service_role key**: 用于服务端管理（可选，更安全）

---

## 选择部署平台

### 推荐平台对比

| 平台 | 免费额度 | 优点 | 缺点 |
|------|---------|------|------|
| **Railway** | $5/月免费额度 | 部署简单，自动HTTPS | 免费额度有限 |
| **Render** | 免费计划（有限制） | 免费计划可用 | 冷启动慢 |
| **Fly.io** | 免费计划 | 全球CDN，性能好 | 配置稍复杂 |
| **Heroku** | 已取消免费计划 | 成熟稳定 | 需要付费 |
| **Vercel** | 不支持Flask | - | 不支持Python后端 |

### 推荐：Railway（最简单）

Railway提供：
- ✅ 自动HTTPS证书
- ✅ 自动部署（连接GitHub）
- ✅ 环境变量管理
- ✅ 日志查看
- ✅ $5/月免费额度

---

## 部署步骤

### 方案A: 使用Railway部署（推荐）

#### 1. 准备代码仓库

确保代码已推送到GitHub：

```bash
# 如果还没有Git仓库
git init
git add .
git commit -m "Initial commit"

# 推送到GitHub
git remote add origin https://github.com/yourusername/your-repo.git
git push -u origin main
```

#### 2. 创建Railway项目

1. 访问 [Railway官网](https://railway.app)
2. 使用GitHub账号登录
3. 点击 **New Project**
4. 选择 **Deploy from GitHub repo**
5. 选择您的代码仓库
6. Railway会自动检测到Flask应用

#### 3. 配置环境变量

在Railway项目设置中，添加以下环境变量：

```env
# 数据库配置
DATABASE_URL=postgresql://postgres.[PROJECT-REF]:[PASSWORD]@aws-1-ap-northeast-2.pooler.supabase.com:5432/postgres

# Supabase Storage配置
SUPABASE_URL=https://[PROJECT-REF].supabase.co
SUPABASE_ANON_KEY=你的anon public key
SUPABASE_STORAGE_BUCKET=question-images

# AI配置（DeepSeek）
AI_PROVIDER=deepseek
AI_API_KEY=你的DeepSeek API Key
AI_API_BASE=https://api.deepseek.com/v1
AI_MODEL=deepseek-chat

# 可选：火山引擎OCR配置
VOLCENGINE_ACCESS_KEY_ID=你的access key
VOLCENGINE_SECRET_ACCESS_KEY=你的secret key
VOLCENGINE_REGION=cn-north-1
VOLCENGINE_USE_VISION_MODEL=true
VOLCENGINE_VISION_MODEL=doubao-lite-vision-32k
```

#### 4. 配置启动命令

在Railway项目设置中，设置启动命令：

```bash
python app.py
```

或者使用gunicorn（推荐生产环境）：

```bash
gunicorn -w 4 -b 0.0.0.0:$PORT app:app
```

**注意**：如果使用gunicorn，需要在`requirements.txt`中添加：
```
gunicorn>=21.2.0
```

#### 5. 部署

Railway会自动：
- 检测Python项目
- 安装依赖（从`requirements.txt`）
- 启动应用
- 分配HTTPS域名

部署完成后，您会获得一个类似 `https://your-app.railway.app` 的URL。

---

### 方案B: 使用Render部署

#### 1. 创建Render服务

1. 访问 [Render官网](https://render.com)
2. 使用GitHub账号登录
3. 点击 **New** → **Web Service**
4. 选择您的GitHub仓库
5. 配置服务：
   - **Name**: 服务名称
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn -w 4 -b 0.0.0.0:$PORT app:app`

#### 2. 配置环境变量

在Render Dashboard中，进入 **Environment** 标签，添加所有环境变量（同Railway）。

#### 3. 部署

Render会自动部署，完成后会提供 `https://your-app.onrender.com` 的URL。

**注意**：免费计划有冷启动延迟（约30秒），首次请求会较慢。

---

### 方案C: 使用Fly.io部署

#### 1. 安装Fly CLI

```bash
# macOS/Linux
curl -L https://fly.io/install.sh | sh

# Windows (使用PowerShell)
iwr https://fly.io/install.ps1 -useb | iex
```

#### 2. 登录Fly.io

```bash
fly auth login
```

#### 3. 初始化项目

```bash
fly launch
```

按照提示：
- 选择应用名称
- 选择区域
- 选择PostgreSQL（可选，我们使用Supabase）

#### 4. 创建fly.toml配置

创建 `fly.toml` 文件：

```toml
app = "your-app-name"
primary_region = "nrt"  # 东京区域

[build]

[env]
  PORT = "8080"

[http_service]
  internal_port = 8080
  force_https = true
  auto_stop_machines = false
  auto_start_machines = true
  min_machines_running = 1

[[services]]
  protocol = "tcp"
  internal_port = 8080
```

#### 5. 配置环境变量

```bash
fly secrets set DATABASE_URL="postgresql://..."
fly secrets set SUPABASE_URL="https://..."
# ... 其他环境变量
```

#### 6. 部署

```bash
fly deploy
```

---

## 环境变量配置

### 必需的环境变量

创建 `.env.production` 文件（或直接在部署平台配置）：

```env
# ========== 数据库配置 ==========
# Supabase PostgreSQL连接字符串（Session pooler模式）
DATABASE_URL=postgresql://postgres.[PROJECT-REF]:[PASSWORD]@aws-1-ap-northeast-2.pooler.supabase.com:5432/postgres

# ========== Supabase Storage配置 ==========
SUPABASE_URL=https://[PROJECT-REF].supabase.co
SUPABASE_ANON_KEY=你的anon public key
SUPABASE_STORAGE_BUCKET=question-images

# ========== AI配置 ==========
# 方式1: DeepSeek（推荐，性价比高）
AI_PROVIDER=deepseek
AI_API_KEY=sk-你的DeepSeek API Key
AI_API_BASE=https://api.deepseek.com/v1
AI_MODEL=deepseek-chat

# 方式2: OpenAI（可选）
# AI_PROVIDER=openai
# AI_API_KEY=sk-你的OpenAI API Key
# AI_API_BASE=https://api.openai.com/v1
# AI_MODEL=gpt-4-vision-preview

# ========== OCR配置（可选）==========
# 火山引擎OCR（推荐，50万tokens免费）
VOLCENGINE_ACCESS_KEY_ID=你的access key
VOLCENGINE_SECRET_ACCESS_KEY=你的secret key
VOLCENGINE_REGION=cn-north-1
VOLCENGINE_USE_VISION_MODEL=true
VOLCENGINE_VISION_MODEL=doubao-lite-vision-32k

# 百度OCR（可选，每月1000次免费）
# BAIDU_OCR_APP_ID=你的app id
# BAIDU_OCR_API_KEY=你的api key
# BAIDU_OCR_SECRET_KEY=你的secret key

# ========== 其他配置 ==========
# OCR预加载（可选，默认true）
PRELOAD_OCR=true

# OCR测试（可选，默认false）
PRELOAD_OCR_TEST=false
```

### 环境变量说明

| 变量名 | 必需 | 说明 |
|--------|------|------|
| `DATABASE_URL` | ✅ | Supabase PostgreSQL连接字符串 |
| `SUPABASE_URL` | ✅ | Supabase项目URL |
| `SUPABASE_ANON_KEY` | ✅ | Supabase匿名密钥 |
| `SUPABASE_STORAGE_BUCKET` | ⚠️ | 存储桶名称（默认：question-images） |
| `AI_PROVIDER` | ✅ | AI提供商（deepseek/openai） |
| `AI_API_KEY` | ✅ | AI API密钥 |
| `AI_API_BASE` | ✅ | AI API基础URL |
| `AI_MODEL` | ✅ | AI模型名称 |

---

## 数据库迁移

### 方法1: 使用Flask应用自动创建（推荐）

部署后，首次访问应用会自动创建数据库表。

或者手动触发：

```bash
# 在本地或通过Railway CLI
python init_db_v2.py
```

### 方法2: 使用SQL脚本

1. 在Supabase Dashboard中，进入 **SQL Editor**
2. 运行以下SQL创建表：

```sql
-- 创建questions表
CREATE TABLE IF NOT EXISTS questions (
    id VARCHAR(36) PRIMARY KEY,
    screenshot VARCHAR(500),
    raw_text TEXT,
    question_text TEXT,
    question_type VARCHAR(20) NOT NULL,
    options TEXT,
    correct_answer VARCHAR(10),
    explanation TEXT,
    tags TEXT,
    knowledge_points TEXT,
    source VARCHAR(200),
    source_url VARCHAR(500),
    encountered_date DATE,
    difficulty INTEGER,
    priority VARCHAR(10),
    ocr_confidence FLOAT,
    similar_questions TEXT,
    question_hash VARCHAR(64),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建answer_versions表
CREATE TABLE IF NOT EXISTS answer_versions (
    id VARCHAR(36) PRIMARY KEY,
    question_id VARCHAR(36) NOT NULL,
    source_name VARCHAR(50) NOT NULL,
    source_type VARCHAR(20) NOT NULL,
    answer VARCHAR(10) NOT NULL,
    explanation TEXT,
    confidence FLOAT,
    is_user_preferred BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_questions_hash ON questions(question_hash);
CREATE INDEX IF NOT EXISTS idx_answer_versions_question_id ON answer_versions(question_id);
```

---

## 验证部署

### 1. 健康检查

访问健康检查接口：

```bash
curl https://your-app.railway.app/api/health
```

应该返回：

```json
{
  "status": "healthy",
  "timestamp": "2025-01-07T...",
  "service": "公考题库分析服务",
  "checks": {
    "database": {
      "status": "connected",
      "type": "postgresql"
    },
    "upload_folder": {
      "status": "available"
    }
  }
}
```

### 2. 测试接口

```bash
curl https://your-app.railway.app/api/test
```

### 3. 测试题目分析

```bash
curl -X POST https://your-app.railway.app/api/questions/analyze \
  -F "image=@test_image.jpg"
```

### 4. 检查数据库

在Supabase Dashboard中：
1. 进入 **Table Editor**
2. 查看 `questions` 和 `answer_versions` 表
3. 确认数据已正确存储

### 5. 检查Storage

在Supabase Dashboard中：
1. 进入 **Storage** → `question-images`
2. 查看上传的图片文件
3. 确认可以访问公开URL

---

## 常见问题

### Q1: 数据库连接失败

**错误信息**：
```
password authentication failed for user "postgres"
```

**解决方法**：
1. 检查 `DATABASE_URL` 中的用户名格式：必须是 `postgres.[PROJECT-REF]`，不是 `postgres`
2. 确认密码已正确替换（不是 `[YOUR-PASSWORD]`）
3. 检查是否使用了 **Session pooler** 模式的连接字符串

### Q2: Storage上传失败

**错误信息**：
```
Storage bucket not found
```

**解决方法**：
1. 确认存储桶名称正确（默认：`question-images`）
2. 在Supabase Dashboard中检查存储桶是否存在
3. 确认存储桶是公开的（Public bucket）

### Q3: 应用启动失败

**错误信息**：
```
ModuleNotFoundError: No module named 'xxx'
```

**解决方法**：
1. 检查 `requirements.txt` 是否包含所有依赖
2. 确认部署平台正确安装了依赖
3. 查看部署日志，确认安装过程

### Q4: 请求超时

**可能原因**：
- 免费计划有资源限制
- OCR服务初始化慢
- AI API响应慢

**解决方法**：
1. 升级到付费计划
2. 设置 `PRELOAD_OCR=true` 预加载OCR服务
3. 使用异步接口 `/api/questions/extract/batch/async`

### Q5: CORS跨域问题

如果前端和API不在同一域名，需要配置CORS：

在 `app.py` 中添加：

```python
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # 允许所有来源
# 或指定来源
# CORS(app, origins=["https://your-frontend.com"])
```

并在 `requirements.txt` 中添加：
```
flask-cors>=4.0.0
```

---

## 生产环境优化建议

### 1. 使用Gunicorn

生产环境使用Gunicorn而不是Flask开发服务器：

```bash
# 启动命令
gunicorn -w 4 -b 0.0.0.0:$PORT --timeout 120 app:app
```

### 2. 配置日志

使用环境变量控制日志级别：

```env
LOG_LEVEL=INFO  # 生产环境使用INFO，开发环境使用DEBUG
```

### 3. 数据库连接池

已在代码中配置，确保：
- `pool_size=20`
- `max_overflow=30`
- `pool_recycle=300`

### 4. 监控和告警

- 使用Railway/Render的监控功能
- 配置健康检查告警
- 监控API响应时间

### 5. 备份

- Supabase自动备份数据库
- 定期导出数据（可选）

---

## 下一步

部署完成后，您可以：

1. ✅ 配置自定义域名（Railway/Render都支持）
2. ✅ 设置CI/CD自动部署
3. ✅ 配置监控和告警
4. ✅ 优化性能（缓存、CDN等）
5. ✅ 添加认证和授权（如需要）

---

## 相关文档

- [Supabase官方文档](https://supabase.com/docs)
- [Railway文档](https://docs.railway.app)
- [Render文档](https://render.com/docs)
- [Fly.io文档](https://fly.io/docs)

---

## 支持

如果遇到问题，请：

1. 查看部署平台的日志
2. 检查环境变量配置
3. 参考本文档的"常见问题"部分
4. 查看项目中的其他文档（如 `Supabase配置步骤详解.md`）

---

**祝部署顺利！** 🚀
