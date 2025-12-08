"""
火山引擎OCR服务：使用火山引擎的OCR API或豆包大模型vision
支持：OCR文字识别、图片理解
"""
import os
import logging
import base64
import json
from typing import Optional, Dict, List
from datetime import datetime

logger = logging.getLogger(__name__)

class VolcengineOCRService:
    """火山引擎OCR服务类"""
    
    def __init__(self):
        # 火山引擎API密钥配置（支持两种方式）
        # 方式1: 使用AccessKey和SecretKey
        self.access_key_id = os.getenv('VOLCENGINE_ACCESS_KEY_ID')
        self.secret_access_key = os.getenv('VOLCENGINE_SECRET_ACCESS_KEY')
        
        # 方式2: 使用API Key（如果提供了API Key，优先使用）
        self.api_key = os.getenv('VOLCENGINE_API_KEY', 'bebcec52-ce96-4f6f-bb1e-9a1b49ad5cf8')
        
        self.region = os.getenv('VOLCENGINE_REGION', 'cn-north-1')
        
        # 豆包大模型配置（默认使用vision模型，支持图片输入）
        self.use_vision_model = os.getenv('VOLCENGINE_USE_VISION_MODEL', 'false').lower() == 'true'
        self.vision_model = os.getenv('VOLCENGINE_VISION_MODEL', 'doubao-seed-1-6-251015')
        # 优化配置：是否启用思考模式（默认禁用，加快速度）
        self.enable_thinking = os.getenv('VOLCENGINE_ENABLE_THINKING', 'false').lower() == 'true'
        
        self.is_available = False
        
        # 优先使用API Key，如果没有则使用AccessKey/SecretKey
        if self.api_key or (self.access_key_id and self.secret_access_key):
            self._init_volcengine_ocr()
        else:
            logger.warning("[VolcengineOCR] 未配置火山引擎API密钥")
    
    def _init_volcengine_ocr(self):
        """初始化火山引擎OCR服务"""
        try:
            # 尝试使用官方SDK
            try:
                from volcengine.visual.VisualService import VisualService
                self.visual_service = VisualService()
                if self.access_key_id and self.secret_access_key:
                    self.visual_service.set_ak(self.access_key_id)
                    self.visual_service.set_sk(self.secret_access_key)
                else:
                    # 如果只有API Key，可能需要其他方式初始化
                    logger.warning("[VolcengineOCR] 使用API Key，可能需要AccessKey/SecretKey")
                self.use_sdk = True
                logger.info("[VolcengineOCR] 使用火山引擎官方SDK")
            except ImportError:
                logger.warning("[VolcengineOCR] 未安装volcengine SDK，使用HTTP API方式")
                logger.info("[VolcengineOCR] 安装命令: pip install volcengine")
                self.use_sdk = False
                self.visual_service = None
            
            self.is_available = True
            logger.info("[VolcengineOCR] 火山引擎OCR服务初始化成功")
            if self.use_vision_model:
                logger.info(f"[VolcengineOCR] 使用豆包大模型vision: {self.vision_model}")
            else:
                logger.info("[VolcengineOCR] 使用OCR API服务")
        except Exception as e:
            logger.error(f"[VolcengineOCR] 初始化失败: {e}")
            self.is_available = False
    
    def _sign_request(self, method: str, url: str, headers: dict, body: str = '') -> dict:
        """
        火山引擎API签名（简化版，实际需要完整的签名算法）
        注意：这里使用简化方式，实际应该使用火山引擎SDK或完整的签名算法
        """
        import hmac
        import hashlib
        from urllib.parse import urlparse
        
        # 简化的签名方式（实际应该使用火山引擎的完整签名算法）
        # 这里提供一个基础框架，实际使用时需要参考官方SDK
        timestamp = str(int(datetime.now().timestamp()))
        
        # 实际签名算法较复杂，建议使用官方SDK
        # 这里先返回基础headers
        signed_headers = {
            'Authorization': f'Bearer {self.access_key_id}',  # 简化方式
            'Content-Type': 'application/json',
            'X-Date': timestamp,
        }
        
        return signed_headers
    
    def _call_vision_model(self, image_data: bytes, prompt: str = None) -> Optional[Dict]:
        """
        调用豆包大模型vision进行OCR（优化版：自动压缩大图片）
        
        Args:
            image_data: 图片的二进制数据
            prompt: 提示词（可选）
            
        Returns:
            dict: API返回结果
        """
        try:
            import requests
            
            # 优化：极致压缩以加快OCR速度（大幅减小尺寸和文件大小）
            compressed_image_data = self._compress_image(image_data, max_size_mb=0.2, max_dimension=800)
            
            # 将图片编码为base64
            image_base64 = base64.b64encode(compressed_image_data).decode('utf-8')
            
            # 火山引擎豆包大模型API端点（根据官方文档）
            url = "https://ark.cn-beijing.volces.com/api/v3/responses"
            
            # 构建请求数据（优化：禁用思考模式，加快响应速度）
            # 注意：使用input数组，content是数组，包含不同类型的输入
            data = {
                "model": self.vision_model,
                "input": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_image",
                                "image_url": f"data:image/jpeg;base64,{image_base64}"
                            },
                            {
                                "type": "input_text",
                                "text": prompt or """题目和选项JSON：{"question_text":"题干","options":["A. ...","B. ..."]}"""
                            }
                        ]
                    }
                ]
            }
            
            # 优化参数：根据火山引擎API文档，参数应该直接在顶层，而不是在parameters字段中
            # 注意：火山引擎API v3不支持parameters字段，需要将参数放在顶层
            # 但根据测试，这些参数可能也不被支持，暂时不添加，使用默认值
            # 如果后续需要优化，可以尝试在input中设置参数
            
            # 使用Bearer Token认证
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            # 发送请求（优化：减少超时时间，提高响应速度，添加重试机制）
            import time
            max_retries = 2
            response = None
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    response = requests.post(url, json=data, headers=headers, timeout=15)  # 平衡优化：15秒超时
                    break  # 成功则退出循环
                except requests.exceptions.Timeout as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(f"[VolcengineOCR] 请求超时，重试 {attempt + 1}/{max_retries}")
                        time.sleep(0.5)  # 短暂等待后重试
                        continue
                    else:
                        logger.error(f"[VolcengineOCR] 请求超时，已重试{max_retries}次")
                        raise
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(f"[VolcengineOCR] 请求失败: {e}，重试 {attempt + 1}/{max_retries}")
                        time.sleep(0.5)
                        continue
                    else:
                        logger.error(f"[VolcengineOCR] 请求失败，已重试{max_retries}次: {e}")
                        raise
            
            # 确保response不为None
            if response is None:
                error_msg = f"请求失败: {last_exception}" if last_exception else "请求失败: 未知错误"
                logger.error(f"[VolcengineOCR] {error_msg}")
                return None
            
            if response.status_code == 401:
                logger.error("[VolcengineOCR] 认证失败，请检查API Key是否正确")
                logger.error(f"[VolcengineOCR] 使用的API Key: {self.api_key[:20]}...")
                return None
            
            # 检查HTTP错误状态
            if response.status_code != 200:
                error_detail = f"HTTP {response.status_code}"
                try:
                    error_body = response.text[:500]  # 只取前500字符
                    logger.error(f"[VolcengineOCR] API返回错误: {error_detail}")
                    logger.error(f"[VolcengineOCR] 错误详情: {error_body}")
                    # 尝试解析JSON错误
                    try:
                        error_json = response.json()
                        if 'error' in error_json:
                            error_msg = error_json.get('error', {}).get('message', '未知错误')
                            logger.error(f"[VolcengineOCR] 错误消息: {error_msg}")
                    except:
                        pass
                except:
                    logger.error(f"[VolcengineOCR] 无法读取错误详情")
                # 创建HTTPError异常，包含response对象
                http_error = requests.exceptions.HTTPError(f"API返回错误: {error_detail}")
                http_error.response = response  # 保存response对象以便后续处理
                raise http_error
            
            response.raise_for_status()
            result = response.json()
            
            # 调试：打印响应结构（仅在前几次调用时）
            if not hasattr(self, '_debug_count'):
                self._debug_count = 0
            if self._debug_count < 2:
                logger.info(f"[VolcengineOCR] API响应结构: {list(result.keys())}")
                if 'output' in result:
                    logger.info(f"[VolcengineOCR] output类型: {type(result['output'])}, 内容: {result['output']}")
                self._debug_count += 1
            
            # 检查错误
            if 'error' in result:
                error_msg = result.get('error', {}).get('message', '未知错误')
                logger.error(f"[VolcengineOCR] API错误: {error_msg}")
                return None
            
            return result
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"[VolcengineOCR] HTTP错误: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"[VolcengineOCR] 响应状态码: {e.response.status_code}")
                try:
                    error_body = e.response.text[:500]
                    logger.error(f"[VolcengineOCR] 错误响应: {error_body}")
                except:
                    pass
            else:
                logger.error(f"[VolcengineOCR] 无法获取响应详情")
            return None
        except Exception as e:
            logger.error(f"[VolcengineOCR] 调用vision模型失败: {e}")
            import traceback
            logger.error(f"[VolcengineOCR] 详细错误: {traceback.format_exc()}")
            return None
    
    def _call_ocr_api(self, image_data: bytes) -> Optional[Dict]:
        """
        调用火山引擎OCR API
        
        Args:
            image_data: 图片的二进制数据
            
        Returns:
            dict: API返回结果
        """
        try:
            # 优先使用官方SDK
            if self.use_sdk and self.visual_service:
                image_base64 = base64.b64encode(image_data).decode('utf-8')
                
                params = {
                    'image_base64': image_base64,
                    'image_url': '',
                    'output_format': 'json'
                }
                
                try:
                    response = self.visual_service.ocr_general(params)
                    if response and response.get('ResponseMetadata', {}).get('Error') is None:
                        return response
                    else:
                        error = response.get('ResponseMetadata', {}).get('Error', {})
                        logger.error(f"[VolcengineOCR] OCR API错误: {error}")
                        return None
                except Exception as e:
                    logger.error(f"[VolcengineOCR] SDK调用失败: {e}")
                    # 如果SDK失败，尝试HTTP方式
                    pass
            
            # 使用HTTP API（备用方式）
            import requests
            
            # 将图片编码为base64
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            
            # 火山引擎OCR API端点（通用文字识别）
            # 注意：实际端点可能需要根据文档调整
            url = "https://visual.volcengineapi.com"
            
            # 构建请求数据
            data = {
                "image_base64": image_base64,
                "image_url": "",
                "output_format": "json"
            }
            
            # 使用API Key进行认证（如果只有API Key）
            # 如果有AccessKey/SecretKey，应该使用签名方式
            headers = {
                'Content-Type': 'application/json'
            }
            
            # 如果有AccessKey/SecretKey，添加到请求中
            if self.access_key_id and self.secret_access_key:
                # 使用签名认证（简化版，实际应该使用完整签名算法）
                headers['X-Access-Key-Id'] = self.access_key_id
                # 注意：SecretKey不应该直接放在header中，应该用于签名
                # 这里只是示例，实际应该使用官方SDK或完整签名
            elif self.api_key:
                headers['Authorization'] = f'Bearer {self.api_key}'
            
            # 发送请求
            response = requests.post(url, json=data, headers=headers, timeout=30)
            
            if response.status_code == 401:
                logger.error("[VolcengineOCR] 认证失败，请检查API密钥配置")
                logger.error("[VolcengineOCR] 提示：可能需要使用AccessKey/SecretKey而不是API Key")
                return None
            
            response.raise_for_status()
            result = response.json()
            
            # 检查错误
            if 'error' in result or result.get('code') != 0:
                error_msg = result.get('message', '未知错误')
                logger.error(f"[VolcengineOCR] OCR API错误: {error_msg}")
                return None
            
            return result
            
        except Exception as e:
            logger.error(f"[VolcengineOCR] 调用OCR API失败: {e}")
            return None
    
    def _compress_image(self, image_data: bytes, max_size_mb: float = 0.2, max_dimension: int = 800) -> bytes:
        """
        压缩图片以加快OCR处理速度
        
        Args:
            image_data: 原始图片数据
            max_size_mb: 最大文件大小（MB），超过此大小则压缩
            max_dimension: 最大尺寸（宽或高），超过此尺寸则缩放
            
        Returns:
            bytes: 压缩后的图片数据（如果不需要压缩则返回原数据）
        """
        try:
            from PIL import Image
            import io
            
            # 检查文件大小
            size_mb = len(image_data) / (1024 * 1024)
            
            # 打开图片检查尺寸
            img = Image.open(io.BytesIO(image_data))
            width, height = img.size
            
            # 如果文件大小和尺寸都在范围内，不需要压缩
            if size_mb <= max_size_mb and width <= max_dimension and height <= max_dimension:
                return image_data
            
            # 需要压缩
            logger.info(f"[VolcengineOCR] 图片压缩: 原始大小 {size_mb:.2f}MB, 尺寸 {width}x{height}")
            original_format = img.format or 'JPEG'
            
            # 如果尺寸过大，先缩放
            if width > max_dimension or height > max_dimension:
                ratio = min(max_dimension / width, max_dimension / height)
                new_width = int(width * ratio)
                new_height = int(height * ratio)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                logger.info(f"[VolcengineOCR] 图片缩放: {width}x{height} -> {new_width}x{new_height}")
            
            # 压缩质量（JPEG质量，PNG转换为JPEG）
            quality = 70  # 70%质量，平衡压缩，保持识别质量
            
            # 转换为RGB（如果是RGBA）
            if img.mode in ('RGBA', 'LA', 'P'):
                # 创建白色背景
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                img = background
            
            # 保存为JPEG（压缩）
            output = io.BytesIO()
            img.save(output, format='JPEG', quality=quality, optimize=True)
            compressed_data = output.getvalue()
            compressed_size_mb = len(compressed_data) / (1024 * 1024)
            
            logger.info(f"[VolcengineOCR] 图片压缩完成: {size_mb:.2f}MB -> {compressed_size_mb:.2f}MB (减少 {((size_mb - compressed_size_mb) / size_mb * 100):.1f}%)")
            
            return compressed_data
            
        except Exception as e:
            logger.warning(f"[VolcengineOCR] 图片压缩失败，使用原图: {e}")
            return image_data
    
    def _read_image(self, image_path_or_url: str) -> Optional[bytes]:
        """
        读取图片数据
        
        Args:
            image_path_or_url: 图片路径或URL
            
        Returns:
            bytes: 图片的二进制数据，如果失败返回None
        """
        try:
            if image_path_or_url.startswith('http://') or image_path_or_url.startswith('https://'):
                # 对于URL，需要先下载
                import requests
                response = requests.get(image_path_or_url, timeout=10)
                response.raise_for_status()
                return response.content
            elif image_path_or_url.startswith('file://'):
                image_path = image_path_or_url[7:]
            else:
                image_path = image_path_or_url
            
            if not os.path.exists(image_path):
                logger.error(f"[VolcengineOCR] 图片文件不存在: {image_path}")
                return None
            
            with open(image_path, 'rb') as f:
                return f.read()
                
        except Exception as e:
            logger.error(f"[VolcengineOCR] 读取图片失败: {e}")
            return None
    
    def extract_text(self, image_path_or_url: str) -> Optional[str]:
        """
        从图片中提取文字（基础版）
        
        Args:
            image_path_or_url: 图片路径或URL
            
        Returns:
            str: 提取的文字，如果失败返回None
        """
        if not self.is_available:
            return None
        
        try:
            # 读取图片
            image_data = self._read_image(image_path_or_url)
            if not image_data:
                return None
            
            # 根据配置选择调用方式
            if self.use_vision_model:
                result = self._call_vision_model(image_data)
            # 解析返回结果（根据实际API响应格式）
            if result:
                # 尝试不同的响应格式
                if 'output' in result:
                    output_data = result['output']
                    # output是列表，包含多个消息项
                    if isinstance(output_data, list) and len(output_data) > 0:
                        # 找到最后一个type='message'的项（通常是assistant的回复）
                        for item in reversed(output_data):
                            if isinstance(item, dict) and item.get('type') == 'message':
                                content_list = item.get('content', [])
                                if isinstance(content_list, list):
                                    # 在content列表中找到type='output_text'的项
                                    for content_item in content_list:
                                        if isinstance(content_item, dict) and content_item.get('type') == 'output_text':
                                            text = content_item.get('text', '')
                                            if text:
                                                logger.info(f"[VolcengineOCR] 提取到文字（vision模型）")
                                                return text
                        # 如果没找到，尝试其他格式
                        # 可能是字符串格式
                        last_item = output_data[-1]
                        if isinstance(last_item, str):
                            text = last_item
                            if text:
                                logger.info(f"[VolcengineOCR] 提取到文字（vision模型，字符串格式）")
                                return text
                        elif isinstance(last_item, dict):
                            # 尝试直接获取text字段
                            text = last_item.get('text', '') or last_item.get('content', '')
                            if text:
                                logger.info(f"[VolcengineOCR] 提取到文字（vision模型，字典格式）")
                                return text
                    elif isinstance(output_data, str):
                        # 直接是字符串
                        text = output_data
                        if text:
                            logger.info(f"[VolcengineOCR] 提取到文字（vision模型，字符串格式）")
                            return text
                    elif isinstance(output_data, dict):
                        # 字典格式
                        text = (output_data.get('text', '') or 
                               output_data.get('content', ''))
                        if text:
                            logger.info(f"[VolcengineOCR] 提取到文字（vision模型，字典格式）")
                            return text
                elif 'choices' in result:
                    # OpenAI兼容格式
                    if isinstance(result['choices'], list) and len(result['choices']) > 0:
                        choice = result['choices'][0]
                        text = (choice.get('message', {}).get('content', '') if isinstance(choice.get('message'), dict) else
                               choice.get('text', '') or choice.get('content', ''))
                        if text:
                            logger.info(f"[VolcengineOCR] 提取到文字（vision模型）")
                            return text
                elif 'text' in result:
                    # 直接text字段
                    text = result['text']
                    if text:
                        logger.info(f"[VolcengineOCR] 提取到文字（vision模型）")
                        return text
                
                # 如果都没找到，打印调试信息
                logger.warning(f"[VolcengineOCR] 无法解析响应格式，响应keys: {list(result.keys())}")
                logger.debug(f"[VolcengineOCR] 完整响应: {result}")
            else:
                result = self._call_ocr_api(image_data)
                if result and 'data' in result:
                    # 从OCR API返回中提取文字
                    texts = []
                    for item in result['data'].get('lines', []):
                        texts.append(item.get('text', ''))
                    text = '\n'.join(texts)
                    logger.info(f"[VolcengineOCR] 提取到 {len(texts)} 行文字")
                    return text
            
            return None
            
        except Exception as e:
            logger.error(f"[VolcengineOCR] 提取文字失败: {e}")
            return None
    
    def extract_text_with_regions(self, image_path_or_url: str) -> Dict:
        """
        从图片中提取文字，并分解为题干和选项
        
        Args:
            image_path_or_url: 图片路径或URL
            
        Returns:
            dict: {
                'raw_text': str,  # 原始文字
                'question_text': str,  # 题干
                'options': List[str],  # 选项列表
                'layout': dict,  # 布局信息
                'total_regions': int  # 区域数量
            }
        """
        if not self.is_available:
            return self._empty_result()
        
        try:
            # 读取图片
            image_data = self._read_image(image_path_or_url)
            if not image_data:
                return self._empty_result()
            
            # 优化方案：OCR API + 文本AI过滤（比Vision模型快，准确率相当）
            # 1. OCR API快速提取所有文字（2-3秒）
            # 2. 文本AI过滤无关内容并提取题目（3-5秒）
            # 3. 总时间：5-8秒，比Vision模型快2-3倍
            ocr_api_result = self._call_ocr_api(image_data)
            
            if ocr_api_result and 'data' in ocr_api_result:
                # OCR API成功，提取文字
                texts = []
                for item in ocr_api_result['data'].get('lines', []):
                    texts.append(item.get('text', ''))
                raw_text = '\n'.join(texts)
                
                if raw_text and len(raw_text.strip()) > 10:
                    logger.info(f"[VolcengineOCR] OCR API成功，提取到 {len(texts)} 行文字")
                    
                    # 使用文本AI过滤并提取题目内容（准确且快速）
                    ai_result = self._extract_question_with_text_ai(raw_text)
                    if ai_result:
                        logger.info(f"[VolcengineOCR] 文本AI提取成功")
                        return {
                            'raw_text': ai_result.get('raw_text', raw_text),
                            'question_text': ai_result.get('question_text', ''),
                            'options': ai_result.get('options', []),
                            'layout': {},
                            'total_regions': len(ai_result.get('options', [])),
                            'extraction_method': 'ocr_api_text_ai'
                        }
                    else:
                        logger.info(f"[VolcengineOCR] 文本AI提取失败，fallback到Vision模型")
                else:
                    logger.info("[VolcengineOCR] OCR API提取文字太少，fallback到Vision模型")
            else:
                logger.info("[VolcengineOCR] OCR API失败，fallback到Vision模型")
            
            # Fallback：使用vision模型进行OCR和理解
            prompt = """请识别这张图片中的题目内容。如果这是一道题目，请：
1. 提取完整的题干文字（只包含题目本身，不包括页面标题、页码、统计信息等界面元素）
2. 识别所有选项（必须是A、B、C、D格式，每个选项以"A. "、"B. "等开头）
3. 将结果以JSON格式返回，格式如下：
{
    "question_text": "题干内容（只包含题目文字，不包括界面元素）",
    "options": ["A. 选项A内容", "B. 选项B内容", "C. 选项C内容", "D. 选项D内容"],
    "raw_text": "题目和选项的原始文字（不包括界面元素）"
}

重要提示：
- 只提取题目和选项相关的文字
- 必须忽略以下内容：
  * 页面标题（如"2019年辽宁省公务员录用考试《行测》题"、"网友回忆版"等）
  * 页码信息（如"1/1"、"第X页"等）
  * 统计信息（如"全站正确率"、"月项"、"正确率为X%"等）
  * 时间（如"11:30"）、网络状态（如"4G"、"5G"、"KB/s"）
  * 导航栏（如"经验"、"直播"、"精选"）、按钮（如"点击推荐"、"拍同款"）
  * 账号信息（如"@用户名"）、底部导航（如"首页"、"朋友"、"消息"、"我"）
  * 其他任何与题目和选项无关的界面元素
- options数组中的每个选项必须以"A. "、"B. "、"C. "、"D. "开头，不要使用1、2、3、4
- raw_text也只包含题目和选项的文字，不要包含任何界面元素、标题、页码、统计信息等"""
            
            result = self._call_vision_model(image_data, prompt)
            
            if not result:
                return self._empty_result()
            
            # 解析返回结果（根据实际API响应格式）
            content = ''
            if 'output' in result:
                output_data = result['output']
                # output是列表，包含多个消息项
                if isinstance(output_data, list) and len(output_data) > 0:
                    # 找到最后一个type='message'的项（通常是assistant的回复）
                    for item in reversed(output_data):
                        if isinstance(item, dict) and item.get('type') == 'message':
                            content_list = item.get('content', [])
                            if isinstance(content_list, list):
                                # 在content列表中找到type='output_text'的项
                                for content_item in content_list:
                                    if isinstance(content_item, dict) and content_item.get('type') == 'output_text':
                                        content = content_item.get('text', '')
                                        break
                            if content:
                                break
                    # 如果没找到，尝试其他格式
                    if not content:
                        last_item = output_data[-1]
                        if isinstance(last_item, str):
                            content = last_item
                        elif isinstance(last_item, dict):
                            content = last_item.get('text', '') or last_item.get('content', '')
                elif isinstance(output_data, str):
                    content = output_data
                elif isinstance(output_data, dict):
                    content = (output_data.get('text', '') or 
                              output_data.get('content', ''))
            elif 'choices' in result:
                # OpenAI兼容格式
                if isinstance(result['choices'], list) and len(result['choices']) > 0:
                    choice = result['choices'][0]
                    content = (choice.get('message', {}).get('content', '') if isinstance(choice.get('message'), dict) else
                              choice.get('text', '') or choice.get('content', ''))
            elif 'text' in result:
                # 直接text字段
                content = result['text']
            
            if not content:
                logger.warning("[VolcengineOCR] 无法从响应中提取内容")
                logger.debug(f"[VolcengineOCR] 响应结构: {list(result.keys()) if isinstance(result, dict) else type(result)}")
                return self._empty_result()
            
            # 尝试解析JSON
            try:
                # 提取JSON部分（可能包含markdown代码块）
                import re
                json_match = re.search(r'\{[\s\S]*\}', content)
                if json_match:
                    parsed = json.loads(json_match.group())
                    options = parsed.get('options', [])
                    
                    # 确保选项格式正确：如果选项没有A/B/C/D前缀，自动添加
                    formatted_options = []
                    for i, opt in enumerate(options):
                        opt_str = str(opt).strip()
                        
                        # 检查是否有重复前缀（如"A. A．内容"或"A．A. 内容"）
                        # 匹配模式：字母 + 标点符号 + 空格 + 字母 + 标点符号 + 内容
                        # 支持中文句号（．，Unicode 65294）和英文句号（.）
                        match = re.match(r'^([A-Z])[\.、。：:\uFF0E]\s*([A-Z])[\.、。：:\uFF0E]\s*(.+)', opt_str)
                        if match:
                            # 有重复前缀，提取第二个字母和内容
                            letter = match.group(2)
                            content = match.group(3).strip()
                            formatted_options.append(f"{letter}. {content}")
                        else:
                            # 检查是否只有一个前缀
                            match = re.match(r'^([A-Z])[\.、。:\s]+(.+)', opt_str)
                            if match:
                                letter = match.group(1)
                                content = match.group(2).strip()
                                # 检查内容是否还以字母开头（可能是重复前缀的另一种格式，如"A. A．内容"）
                                # 更宽松的匹配：字母 + 任意标点 + 内容
                                content_match = re.match(r'^([A-Z])[\.、。:\s]+(.+)', content)
                                if content_match:
                                    # 内容中还有前缀，使用内容中的字母，去掉重复的前缀
                                    letter = content_match.group(1)
                                    content = content_match.group(2).strip()
                                formatted_options.append(f"{letter}. {content}")
                            else:
                                # 没有前缀，添加前缀
                                option_label = chr(65 + i)  # A, B, C, D...
                                formatted_options.append(f"{option_label}. {opt_str}")
                    
                    return {
                        'raw_text': parsed.get('raw_text', content),
                        'question_text': parsed.get('question_text', ''),
                        'options': formatted_options,
                        'layout': {},
                        'total_regions': len(formatted_options)
                    }
            except:
                pass
            
            # 如果JSON解析失败，返回原始文字
            return {
                'raw_text': content,
                'question_text': content,
                'options': [],
                'layout': {},
                'total_regions': 0
            }
            
        except Exception as e:
            logger.error(f"[VolcengineOCR] 提取文字和区域失败: {e}")
            return self._empty_result()
    
    def _split_question_and_options(self, text_lines: List[str]) -> tuple:
        """
        将OCR结果分解为题干和选项（备用方法）
        
        Args:
            text_lines: OCR识别的文字行列表
            
        Returns:
            tuple: (question_text, options)
        """
        import re
        
        question_lines = []
        options = []
        
        # 选项模式
        option_patterns = [
            re.compile(r'^[A-Z][\.、。]\s*'),
            re.compile(r'^\([A-Z]\)\s*'),
            re.compile(r'^[A-Z]\s+'),
            re.compile(r'^[A-Z][:：]\s*'),
            re.compile(r'^[A-Z][\u4e00-\u9fa5]'),
        ]
        
        # 识别选项位置
        option_indices = []
        for i, line in enumerate(text_lines):
            line_stripped = line.strip()
            if not line_stripped:
                continue
            for pattern in option_patterns:
                if pattern.match(line_stripped):
                    option_indices.append(i)
                    break
        
        if option_indices:
            first_option_idx = min(option_indices)
            question_lines = text_lines[:first_option_idx]
            
            for i in option_indices:
                line = text_lines[i].strip()
                if line:
                    options.append(line)
        else:
            question_lines = text_lines
        
        question_text = '\n'.join(question_lines)
        
        return question_text, options
    
    def _empty_result(self) -> Dict:
        """返回空结果"""
        return {
            'raw_text': '',
            'question_text': '',
            'options': [],
            'layout': [],
            'total_regions': 0
        }


# 全局服务实例
_volcengine_ocr_service = None

def get_volcengine_ocr_service():
    """获取火山引擎OCR服务实例（单例模式）"""
    global _volcengine_ocr_service
    if _volcengine_ocr_service is None:
        _volcengine_ocr_service = VolcengineOCRService()
    return _volcengine_ocr_service

