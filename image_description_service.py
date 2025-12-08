"""
图片描述服务：使用CLIP模型生成图片的文字描述
用于DeepSeek等不支持图片输入的AI模型
"""
import os
import logging
import requests
from io import BytesIO
from PIL import Image
import os

logger = logging.getLogger(__name__)

class ImageDescriptionService:
    """图片描述服务类"""
    
    def __init__(self):
        self.model = None
        self.processor = None
        self._init_model()
    
    def _init_model(self):
        """初始化图片描述模型"""
        try:
            # 使用BLIP模型（轻量级，效果好）
            from transformers import BlipProcessor, BlipForConditionalGeneration
            model_name = "Salesforce/blip-image-captioning-base"
            self.processor = BlipProcessor.from_pretrained(model_name)
            self.model = BlipForConditionalGeneration.from_pretrained(model_name)
            logger.info(f"[ImageDesc] 加载BLIP模型: {model_name}")
        except ImportError:
            logger.warning("[ImageDesc] transformers未安装，无法使用图片描述功能")
        except Exception as e:
            logger.warning(f"[ImageDesc] 模型加载失败: {e}")
            self.model = None
    
    def describe_image(self, image_path_or_url):
        """
        生成图片的文字描述
        
        Args:
            image_path_or_url: 图片路径或URL
            
        Returns:
            str: 图片描述文字
        """
        if not self.model:
            return "这是一张图片，但无法生成详细描述（模型未加载）"
        
        try:
            # 处理HTTP/HTTPS URL
            if image_path_or_url.startswith('http://') or image_path_or_url.startswith('https://'):
                logger.info(f"[ImageDesc] 从URL加载图片: {image_path_or_url[:50]}...")
                try:
                    response = requests.get(image_path_or_url, timeout=10)
                    response.raise_for_status()
                    image = Image.open(BytesIO(response.content)).convert('RGB')
                except Exception as e:
                    logger.error(f"[ImageDesc] 从URL加载图片失败: {e}")
                    return f"无法从URL加载图片: {str(e)}"
            # 处理file://协议
            elif image_path_or_url.startswith('file://'):
                image_path = image_path_or_url[7:]
                if not os.path.exists(image_path):
                    logger.error(f"[ImageDesc] 图片文件不存在: {image_path}")
                    return "图片文件不存在"
                image = Image.open(image_path).convert('RGB')
            # 处理本地路径
            else:
                image_path = image_path_or_url
                if not os.path.exists(image_path):
                    logger.error(f"[ImageDesc] 图片文件不存在: {image_path}")
                    return "图片文件不存在"
                image = Image.open(image_path).convert('RGB')
            
            # 生成描述
            inputs = self.processor(image, return_tensors="pt")
            out = self.model.generate(**inputs, max_length=50)
            description = self.processor.decode(out[0], skip_special_tokens=True)
            
            logger.info(f"[ImageDesc] 生成描述: {description}")
            return description
            
        except Exception as e:
            logger.error(f"[ImageDesc] 生成描述失败: {e}", exc_info=True)
            return f"图片描述生成失败: {str(e)}"


# 全局服务实例
_image_desc_service = None

def get_image_description_service():
    """获取图片描述服务实例（单例模式）"""
    global _image_desc_service
    if _image_desc_service is None:
        _image_desc_service = ImageDescriptionService()
    return _image_desc_service

