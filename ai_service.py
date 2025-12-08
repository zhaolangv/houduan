"""
AI解析服务：处理AI调用和缓存逻辑
"""
import os
import sys
import logging
from openai import OpenAI
from models_v2 import db, Question, AnswerVersion
from image_utils import calculate_all_features, find_similar_image
from embedding_service import get_embedding_service
from ocr_service import get_ocr_service
from image_description_service import get_image_description_service
import imagehash

# 配置日志
logger = logging.getLogger(__name__)


class AIService:
    """AI解析服务类"""
    
    def __init__(self):
        # 初始化AI客户端（支持OpenAI和DeepSeek）
        api_key = os.getenv('AI_API_KEY', os.getenv('OPENAI_API_KEY', ''))
        api_base = os.getenv('AI_API_BASE', os.getenv('OPENAI_API_BASE', ''))
        ai_provider = os.getenv('AI_PROVIDER', 'deepseek').lower()  # deepseek 或 openai
        
        # 如果没有配置，使用默认值
        if not api_key:
            logger.warning("[AI] 未配置AI_API_KEY，将使用模拟数据")
            self.client = None
        else:
            # 根据provider设置默认值
            if ai_provider == 'deepseek':
                if not api_base:
                    api_base = 'https://api.deepseek.com/v1'
                if not api_key.startswith('sk-'):
                    logger.warning("[AI] DeepSeek API key格式可能不正确")
                try:
                    self.client = OpenAI(api_key=api_key, base_url=api_base)
                    self.default_model = os.getenv('AI_MODEL', 'deepseek-chat')
                    logger.info(f"[AI] 使用DeepSeek API: {api_base}, model={self.default_model}")
                except Exception as e:
                    logger.error(f"[AI] DeepSeek客户端初始化失败: {e}")
                    self.client = None
            else:  # openai
                if not api_base:
                    api_base = 'https://api.openai.com/v1'
                try:
                    self.client = OpenAI(api_key=api_key, base_url=api_base)
                    self.default_model = os.getenv('AI_MODEL', 'gpt-4')
                    logger.info(f"[AI] 使用OpenAI API: {api_base}, model={self.default_model}")
                except Exception as e:
                    logger.error(f"[AI] OpenAI客户端初始化失败: {e}")
                    self.client = None
        
        self.ai_provider = ai_provider
    
    def analyze_question(self, question_type, question_content=None, image_url=None, question_id=None):
        """
        解析题目（带缓存机制）
        
        Args:
            question_type: 题目类型（如：图推、言语、判断等）
            question_content: 题目文本内容
            image_url: 图片URL（图推题）
            question_id: 题目唯一ID（如果有）
            
        Returns:
            dict: {
                'analysis': AI解析内容,
                'from_cache': 是否来自缓存,
                'question_id': 题目ID
            }
        """
        # 1. 尝试查找已存在的题目
        existing_question = None
        
        if question_id:
            # 如果有题目ID，直接用ID查找
            try:
                existing_question = Question.query.filter_by(id=question_id).first()
            except:
                existing_question = None
        
        if not existing_question and image_url:
            # 对于图推题，使用多种方法查找
            logger.info(f"[AI] 开始计算图片特征: {image_url[:80]}...")
            # 1. 先计算所有特征（MD5、感知哈希、Embedding）
            try:
                features = calculate_all_features(image_url)
                md5_hash = features['md5_hash']
                phash = features['phash']
                embedding = features['embedding']
                logger.info(f"[AI] 特征计算完成: md5={md5_hash[:16]}..., phash={phash}, embedding={'存在' if embedding is not None else 'None'}")
            except Exception as e:
                logger.error(f"[AI] 特征计算出错: {e}", exc_info=True)
                raise
            
            # 2. 先尝试用MD5哈希精确匹配（最快）
            existing_question = Question.query.filter_by(image_hash=md5_hash).first()
            
            # 3. 如果没找到，使用Perceptual Hash和Embedding综合查找
            if not existing_question:
                # 将embedding转换为numpy数组（如果存在）
                embedding_array = None
                logger.debug(f"[AI] 检查embedding: type={type(embedding)}, is None={embedding is None}")
                if embedding is not None:  # 修复：不能直接用if embedding判断数组
                    logger.info(f"[AI] embedding存在，开始转换: {type(embedding)}")
                    embedding_service = get_embedding_service()
                    embedding_array = embedding_service.list_to_embedding(embedding)
                    logger.info(f"[AI] embedding转换完成: type={type(embedding_array)}, shape={embedding_array.shape if hasattr(embedding_array, 'shape') else 'N/A'}")
                else:
                    logger.debug("[AI] embedding为None，跳过Embedding查找")
                
                existing_question = find_similar_image(
                    phash=phash,
                    embedding=embedding_array,
                    phash_threshold=5,
                    embedding_threshold=0.85,  # 85%相似度阈值
                    db_session=db.session,
                    Question=Question,
                    use_both=True  # 同时使用两种方法
                )
        
        # 注意：此方法已废弃，新的架构使用 question_service_v2.py
        # 保留此方法仅用于向后兼容，但不再保存到数据库
        logger.warning("[AI] analyze_question方法已废弃，请使用question_service_v2.QuestionService")
        
        # 2. 如果找到已存在的题目，检查是否有答案版本
        if existing_question and existing_question.answer_versions.count() > 0:
            # 获取第一个答案版本的解析
            first_answer = existing_question.answer_versions.first()
            return {
                'analysis': first_answer.explanation or '',
                'from_cache': True,
                'question_id': existing_question.id
            }
        
        # 3. 如果没有缓存，调用AI解析
        ai_response = self._call_ai(question_type, question_content, image_url)
        
        # 注意：不再保存到数据库，新的架构由question_service_v2处理
        logger.warning("[AI] 不再保存AI解析到数据库，请使用question_service_v2")
        
        return {
            'analysis': ai_response,
            'from_cache': False,
            'question_id': None  # 不再创建题目记录
        }
    
    def _call_ai(self, question_type, question_content=None, image_url=None):
        """
        调用AI接口解析题目
        
        Args:
            question_type: 题目类型
            question_content: 题目文本内容
            image_url: 图片URL
            
        Returns:
            str: AI解析内容
        """
        if not self.client:
            # 如果没有配置AI客户端，返回模拟数据
            return f"这是{question_type}题的AI解析（模拟数据）。实际使用时需要配置AI API。"
        
        # 构建提示词
        if question_content and len(question_content) > 500:
            # 如果question_content很长，说明是完整的提示词（包含图片描述等）
            prompt = question_content
        else:
            # 否则使用原来的方式
            prompt = f"请详细解析这道{question_type}题，包括：\n1. 题目类型和考点\n2. 解题思路\n3. 详细解答过程\n4. 注意事项"
            if question_content:
                prompt += f"\n\n题目内容：{question_content}"
        
        # 处理图片：DeepSeek不支持图片输入，需要转换为文字
        image_text_info = ""
        if image_url:
            logger.info(f"[AI] 检测到图片，开始分析图片类型: {image_url[:50]}...")
            
            # 步骤1: 分析图片类型（图推题 vs 文字题）
            ocr_service = get_ocr_service()
            image_analysis = None
            if ocr_service.ocr_engine:
                logger.info("[AI] 开始分析图片类型...")
                image_analysis = ocr_service.analyze_image_type(image_url)
                logger.info(f"[AI] 图片类型分析结果: {image_analysis['type']} (置信度: {image_analysis['confidence']:.2f})")
            
            # 步骤2: 根据图片类型提取信息
            is_graph_question = image_analysis and image_analysis['type'] == 'graph'
            
            if is_graph_question:
                # 图推题：优先使用图片描述，OCR文字作为补充
                logger.info("[AI] 判断为图推题，使用图片描述 + OCR文字")
                
                # 先尝试图片描述（描述图形特征）
                desc_service = get_image_description_service()
                if desc_service.model:
                    description = desc_service.describe_image(image_url)
                    image_text_info += f"\n\n【图片描述】（图推题）\n{description}"
                
                # OCR文字作为补充（如果有）
                if image_analysis and image_analysis['text']:
                    image_text_info += f"\n\n【图片中的文字】（补充信息）\n{image_analysis['text']}"
                
                # 添加图推题专用提示
                image_text_info += f"\n\n这是一道图形推理题。请重点分析：\n1. 图形的规律和模式\n2. 位置、数量、形状、颜色等变化\n3. 对称、旋转、叠加等关系\n4. 推理过程和答案选择"
            else:
                # 文字题：优先使用OCR文字
                logger.info("[AI] 判断为文字题，使用OCR文字")
                
                if image_analysis and image_analysis['text']:
                    image_text_info += f"\n\n【图片中的文字内容】\n{image_analysis['text']}"
                    image_text_info += f"\n\n这是一道文字类题目。请重点分析：\n1. 文字内容的语义理解\n2. 题目要求和选项分析\n3. 逻辑关系和推理过程"
                else:
                    # 如果OCR失败，尝试图片描述
                    logger.info("[AI] OCR未提取到文字，尝试生成图片描述...")
                    desc_service = get_image_description_service()
                    if desc_service.model:
                        description = desc_service.describe_image(image_url)
                        image_text_info += f"\n\n【图片描述】\n{description}"
                    else:
                        image_text_info += f"\n\n这是一道包含图片的{question_type}题。由于当前AI模型不支持直接查看图片，请根据{question_type}题的常见考点和解题思路进行分析。"
            
            prompt += image_text_info
        
        import time
        ai_start_time = time.time()
        
        # 记录API基础信息
        api_base_url = getattr(self.client._client, 'base_url', 'unknown') if self.client else 'unknown'
        logger.info(f"[AI] 🤖 准备调用AI API")
        logger.info(f"[AI] 📋 API信息: provider={self.ai_provider}, model={self.default_model}, base_url={api_base_url}")
        logger.info(f"[AI] 📝 Prompt信息: 长度={len(prompt)}字符, 题目类型={question_type}, 包含图片={'是' if image_url else '否'}")
        if len(prompt) > 0:
            logger.debug(f"[AI] 💬 Prompt内容预览（前300字符）:\n{prompt[:300]}...")
        
        try:
            # DeepSeek不支持图片输入，只能使用文本模式
            if image_url and self.ai_provider == 'deepseek':
                logger.info(f"[AI] 🚀 开始调用DeepSeek API (模型: {self.default_model})")
                logger.info(f"[AI] 📤 请求参数: model={self.default_model}, max_tokens=2000, temperature=0.7")
                
                request_start = time.time()
                try:
                    response = self.client.chat.completions.create(
                        model=self.default_model,
                        messages=[
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.7,
                        max_tokens=2000
                    )
                except Exception as api_error:
                    request_time = time.time() - request_start
                    total_time = time.time() - ai_start_time
                    error_type = type(api_error).__name__
                    logger.error(f"[AI] ❌ DeepSeek API请求失败: {error_type}: {str(api_error)}, 请求耗时={request_time:.2f}秒, 总计={total_time:.2f}秒")
                    raise
                
                request_time = time.time() - request_start
                
                # 解析响应
                response_content = response.choices[0].message.content if response.choices else None
                response_length = len(response_content) if response_content else 0
                
                # 提取token使用信息
                prompt_tokens = 0
                completion_tokens = 0
                total_tokens = 0
                if hasattr(response, 'usage') and response.usage:
                    usage = response.usage
                    prompt_tokens = getattr(usage, 'prompt_tokens', 0)
                    completion_tokens = getattr(usage, 'completion_tokens', 0)
                    total_tokens = getattr(usage, 'total_tokens', 0)
                
                # 计算费用（DeepSeek定价，示例）
                # 注意：实际定价可能不同，这里仅作参考
                cost = 0.0
                if total_tokens > 0:
                    # DeepSeek Chat定价示例（需要根据实际定价调整）
                    # 假设: 输入 $0.14/1M tokens, 输出 $0.28/1M tokens
                    cost = (prompt_tokens / 1_000_000 * 0.14) + (completion_tokens / 1_000_000 * 0.28)
                
                total_time = time.time() - ai_start_time
                logger.info(f"[AI] ✅ DeepSeek API调用成功")
                logger.info(f"[AI] ⏱️  耗时统计: API请求={request_time:.2f}秒, 总计={total_time:.2f}秒")
                logger.info(f"[AI] 📊 响应统计: 内容长度={response_length}字符, prompt_tokens={prompt_tokens}, completion_tokens={completion_tokens}, total_tokens={total_tokens}")
                if cost > 0:
                    logger.info(f"[AI] 💰 费用估算: ¥{cost:.6f} (仅供参考，实际费用以DeepSeek定价为准)")
                logger.debug(f"[AI] 📝 响应内容预览（前300字符）:\n{response_content[:300] if response_content else 'None'}...")
                
                return response_content
            # OpenAI支持图片（需要vision模型）
            elif image_url and self.ai_provider == 'openai':
                logger.info(f"[AI] 🚀 开始调用OpenAI API (模型: {self.default_model})")
                logger.info(f"[AI] 📤 请求参数: model={self.default_model}, 包含图片, max_tokens=2000, temperature=0.7")
                
                request_start = time.time()
                try:
                    response = self.client.chat.completions.create(
                        model=self.default_model,
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": prompt},
                                    {"type": "image_url", "image_url": {"url": image_url}}
                                ]
                            }
                        ]
                    )
                except Exception as api_error:
                    request_time = time.time() - request_start
                    total_time = time.time() - ai_start_time
                    error_type = type(api_error).__name__
                    logger.error(f"[AI] ❌ OpenAI API请求失败: {error_type}: {str(api_error)}, 请求耗时={request_time:.2f}秒, 总计={total_time:.2f}秒")
                    raise
                
                request_time = time.time() - request_start
                response_content = response.choices[0].message.content if response.choices else None
                response_length = len(response_content) if response_content else 0
                
                # 提取token使用信息
                prompt_tokens = getattr(response.usage, 'prompt_tokens', 0) if hasattr(response, 'usage') and response.usage else 0
                completion_tokens = getattr(response.usage, 'completion_tokens', 0) if hasattr(response, 'usage') and response.usage else 0
                total_tokens = getattr(response.usage, 'total_tokens', 0) if hasattr(response, 'usage') and response.usage else 0
                
                total_time = time.time() - ai_start_time
                logger.info(f"[AI] ✅ OpenAI API调用成功")
                logger.info(f"[AI] ⏱️  耗时统计: API请求={request_time:.2f}秒, 总计={total_time:.2f}秒")
                logger.info(f"[AI] 📊 响应统计: 内容长度={response_length}字符, total_tokens={total_tokens}")
                logger.debug(f"[AI] 📝 响应内容预览（前300字符）:\n{response_content[:300] if response_content else 'None'}...")
                
                return response_content
            else:
                # 纯文本题目
                logger.info(f"[AI] 🚀 开始调用AI API (provider: {self.ai_provider}, model: {self.default_model})")
                logger.info(f"[AI] 📤 请求参数: model={self.default_model}, max_tokens=2000, temperature=0.7")
                
                request_start = time.time()
                try:
                    response = self.client.chat.completions.create(
                        model=self.default_model,
                        messages=[
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.7,
                        max_tokens=2000
                    )
                except Exception as api_error:
                    request_time = time.time() - request_start
                    total_time = time.time() - ai_start_time
                    error_type = type(api_error).__name__
                    logger.error(f"[AI] ❌ AI API请求失败: {error_type}: {str(api_error)}, 请求耗时={request_time:.2f}秒, 总计={total_time:.2f}秒")
                    raise
                
                request_time = time.time() - request_start
                response_content = response.choices[0].message.content if response.choices else None
                response_length = len(response_content) if response_content else 0
                
                total_time = time.time() - ai_start_time
                logger.info(f"[AI] ✅ AI API调用成功")
                logger.info(f"[AI] ⏱️  耗时统计: API请求={request_time:.2f}秒, 总计={total_time:.2f}秒")
                logger.info(f"[AI] 📊 响应统计: 内容长度={response_length}字符")
                logger.debug(f"[AI] 📝 响应内容预览（前300字符）:\n{response_content[:300] if response_content else 'None'}...")
                
                return response_content
            
        except Exception as e:
            total_time = time.time() - ai_start_time
            error_type = type(e).__name__
            error_msg = str(e)
            logger.error(f"[AI] ❌ AI API调用失败: {error_type}: {error_msg}, 耗时={total_time:.2f}秒", exc_info=True)
            return f"AI解析出错：{str(e)}"

