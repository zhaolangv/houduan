# 配置 Supabase 连接 - 快速指南

## ⚠️ 重要提示

**Session pooler 和 Connection pooling 都可以使用，但需要注意用户名格式**

### Supabase 的两种连接池模式：

1. **Session pooler**（端口 5432）
   - ✅ 支持 IPv4 网络
   - ✅ 用户名格式：`postgres.项目标识`
   - ✅ 适合大多数应用场景

2. **Connection pooling / Transaction pooler**（端口 6543）
   - ✅ 更高性能的事务处理
   - ✅ 用户名格式：`postgres.项目标识`
   - ✅ 适合高并发事务

**关键点**：
- ❌ 不能使用 `postgres` 作为用户名
- ✅ 必须使用 `postgres.xxxxx` 格式（包含项目标识）

---

## 📋 获取连接字符串步骤

### 步骤 1: 切换到连接池模式

在 Supabase 的连接字符串页面：

1. 找到 **"Method"** 下拉菜单
2. 选择 **"Connection pooling"** 或 **"Session Pooler"**
3. 不要选择 **"Direct connection"**（这是直连模式，端口 5432）

### 步骤 2: 确认连接字符串格式

#### Session Pooler 模式（端口 5432）

```
postgresql://postgres.xxxxx:[YOUR-PASSWORD]@aws-1-xxx.pooler.supabase.com:5432/postgres
```

**关键特征**：
- ✅ 包含 `pooler.supabase.com`
- ✅ 端口是 **5432**
- ✅ 用户名是 `postgres.xxxxx`（**必须包含项目标识**，不能只是 `postgres`）

#### Connection Pooling 模式（端口 6543）

```
postgresql://postgres.xxxxx:[YOUR-PASSWORD]@aws-0-xxx.pooler.supabase.com:6543/postgres
```

**关键特征**：
- ✅ 包含 `pooler.supabase.com`
- ✅ 端口是 **6543**
- ✅ 用户名是 `postgres.xxxxx`（**必须包含项目标识**）

**重要**：用户名必须是 `postgres.项目标识` 格式，不能只是 `postgres`

### 步骤 3: 替换密码

1. 点击连接字符串中的 `[YOUR-PASSWORD]`
2. 替换为您的数据库密码（在创建项目时设置的密码）
3. 或点击 "View parameters" 查看详细参数

### 步骤 4: 复制连接字符串

点击连接字符串右侧的复制按钮 📋

---

## 🔧 配置到应用

### 方式 1: 使用配置助手（推荐）

```bash
python setup_database.py
```

选择选项 1（Supabase PostgreSQL），然后粘贴连接字符串。

### 方式 2: 手动配置

编辑 `.env` 文件，添加：

```env
DATABASE_URL=postgresql://postgres.xxxxx:your_password@aws-0-xxx.pooler.supabase.com:6543/postgres
```

**注意**：将 `your_password` 替换为实际密码。

---

## ✅ 验证配置

### 1. 检查配置

```bash
python check_database.py
```

应该看到：
```
✅ 目标数据库连接成功
📊 数据库类型: PostgreSQL
```

### 2. 测试连接池

启动应用：

```bash
python app.py
```

查看日志，应该看到：
```
✅ 数据库连接成功！
✅ 数据库表已就绪！
```

### 3. 健康检查

```bash
curl http://localhost:5000/api/health
```

应该返回：
```json
{
  "status": "healthy",
  "checks": {
    "database": {
      "status": "connected",
      "type": "postgresql"
    }
  }
}
```

---

## 🔍 连接字符串对比

### ❌ 错误（直连模式）

```
postgresql://postgres:[PASSWORD]@db.xxxxx.supabase.co:5432/postgres
```

特征：
- 端口：5432
- 域名：`db.xxx.supabase.co`
- 用户名：`postgres`（没有项目标识）
- **不支持连接池**

### ✅ 正确（Session Pooler - 端口 5432）

```
postgresql://postgres.jhursbbnelxthwezcetg:[PASSWORD]@aws-1-xxx.pooler.supabase.com:5432/postgres
```

特征：
- 端口：5432
- 域名：`xxx.pooler.supabase.com`
- 用户名：`postgres.xxxxx`（**必须包含项目标识**）
- **支持连接池，IPv4 兼容**

### ✅ 正确（Connection Pooling - 端口 6543）

```
postgresql://postgres.xxxxx:[PASSWORD]@aws-0-xxx.pooler.supabase.com:6543/postgres
```

特征：
- 端口：6543
- 域名：`xxx.pooler.supabase.com`
- 用户名：`postgres.xxxxx`（**必须包含项目标识**）
- **支持连接池，高并发事务**

---

## ⚙️ Supabase 连接池设置

在 Supabase Dashboard → Settings → Database 中：

- **Pool Size**: 建议设置为 20（与我们的优化配置匹配）
- **Max Client Connections**: 200（固定，足够使用）

---

## 📝 完整配置示例

`.env` 文件：

```env
# Supabase PostgreSQL（连接池模式）
DATABASE_URL=postgresql://postgres.xxxxx:your_password@aws-0-xxx.pooler.supabase.com:6543/postgres

# AI API 配置
AI_PROVIDER=deepseek
AI_API_KEY=your_api_key

# OCR 预加载
PRELOAD_OCR=true
```

---

## 🚀 下一步

配置完成后：

1. ✅ 运行检查：`python check_database.py`
2. ✅ 运行迁移（如果有 SQLite 数据）：`python migrate_database.py`
3. ✅ 启动应用：`python app.py`

---

## ❓ 常见问题

### Q: 找不到 "Connection pooling" 选项？

**A**: 
- 可能显示为 "Session Pooler"
- 或者在 "Method" 下拉菜单中查找

### Q: 密码认证失败 "password authentication failed"？

**A**: 
1. **检查用户名格式**：必须使用 `postgres.项目标识`，不能只是 `postgres`
   - ✅ 正确：`postgresql://postgres.jhursbbnelxthwezcetg:password@...`
   - ❌ 错误：`postgresql://postgres:password@...`
2. 检查密码是否正确（创建项目时设置的数据库密码）
3. 如果忘记密码，可以在 Supabase Dashboard → Settings → Database 重置密码

### Q: Session Pooler 使用端口 5432 可以吗？

**A**: 
- ✅ 可以！Session Pooler 使用端口 5432 是正常的
- ✅ 它已经提供了连接池功能，并且支持 IPv4
- ✅ 如果您的网络支持 IPv4，Session Pooler（端口 5432）和 Connection Pooling（端口 6543）都可以使用

### Q: 连接失败怎么办？

**A**: 
1. 检查密码是否正确
2. 确保使用了连接池模式（端口 6543）
3. 运行 `python check_database.py` 查看详细错误

---

## 📄 相关文档

- `数据库配置指南.md` - 详细配置说明
- `快速迁移指南.md` - 数据迁移步骤
- `数据库连接池优化说明.md` - 连接池优化详情
