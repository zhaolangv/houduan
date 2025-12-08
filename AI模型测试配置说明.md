# AI模型测试配置说明

## 测试脚本
`test_ai_models_comparison.py` - 测试多个AI服务的各种模型提取题目和选项

## 配置说明

### 1. 阿里云（通义千问）

已配置以下模型：
- `qwen-turbo` - 速度快，成本低
- `qwen-plus` - 平衡版
- `qwen-max` - 最强性能
- `qwen-max-longcontext` - 长文本版

API Key已在脚本中配置。

### 2. DeepSeek

已配置以下模型：
- `deepseek-chat` - 标准版
- `deepseek-reasoner` - 推理版

API Key已在脚本中配置。

### 3. 火山引擎（豆包大模型）

**重要**：火山引擎文本模型需要通过**接入点ID（ep-xxxxxx）**调用，而不是模型名称。

#### 配置步骤：

1. **登录火山引擎控制台**
   - 访问：https://www.volcengine.com/
   - 完成注册和实名认证

2. **开通豆包大模型服务**
   - 在控制台搜索"火山方舟"
   - 开通服务

3. **创建推理接入点**
   - 进入"模型推理" → "在线推理"
   - 点击"创建推理接入点"
   - 选择模型（如：doubao-seed-1.6）
   - 创建完成后，获取接入点ID（格式：`ep-xxxxxx`）

4. **配置环境变量**
   ```bash
   # 单个接入点
   VOLCENGINE_ENDPOINT_IDS=ep-123456
   
   # 多个接入点（用逗号分隔）
   VOLCENGINE_ENDPOINT_IDS=ep-123456,ep-789012
   ```

5. **或者直接在.env文件中配置**
   ```
   VOLCENGINE_ENDPOINT_IDS=ep-123456,ep-789012
   ```

## 测试流程

1. **统一使用本地OCR**：所有图片先用PaddleOCR识别文字
2. **发送给各AI模型**：将OCR文字发送给各个AI模型提取题目和选项
3. **统计指标**：
   - 准确率（基于提取结果质量评分）
   - 速度（OCR时间 + AI时间）
   - Token数量（输入+输出）
   - 费用（根据定价计算）

## 注意事项

- 火山引擎如果没有配置接入点ID，将自动跳过测试
- 所有AI调用都不使用思考模式，只提取题目和选项
- OCR结果会进行预处理，过滤界面元素
