"""
百度OCR服务：使用百度AI开放平台的OCR API
优点：准确率高，每月1000次免费
"""
import os
import logging
import base64
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

class BaiduOCRService:
    """百度OCR服务类"""
    
    def __init__(self):
        self.app_id = os.getenv('BAIDU_OCR_APP_ID')
        self.api_key = os.getenv('BAIDU_OCR_API_KEY')
        self.secret_key = os.getenv('BAIDU_OCR_SECRET_KEY')
        self.access_token = None
        self.is_available = False
        
        if self.app_id and self.api_key and self.secret_key:
            self._init_baidu_ocr()
        else:
            logger.warning("[BaiduOCR] 未配置百度OCR API密钥，将使用本地OCR")
    
    def _init_baidu_ocr(self):
        """初始化百度OCR服务"""
        try:
            # 获取access_token
            self.access_token = self._get_access_token()
            if self.access_token:
                self.is_available = True
                logger.info("[BaiduOCR] 百度OCR服务初始化成功")
            else:
                logger.warning("[BaiduOCR] 无法获取access_token，百度OCR不可用")
        except Exception as e:
            logger.error(f"[BaiduOCR] 初始化失败: {e}")
            self.is_available = False
    
    def _get_access_token(self) -> Optional[str]:
        """
        获取百度OCR的access_token
        
        Returns:
            str: access_token，如果失败返回None
        """
        try:
            import requests
            
            url = "https://aip.baidubce.com/oauth/2.0/token"
            params = {
                "grant_type": "client_credentials",
                "client_id": self.api_key,
                "client_secret": self.secret_key
            }
            
            response = requests.post(url, params=params, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            if 'access_token' in result:
                logger.info("[BaiduOCR] 成功获取access_token")
                return result['access_token']
            else:
                logger.error(f"[BaiduOCR] 获取access_token失败: {result}")
                return None
                
        except Exception as e:
            logger.error(f"[BaiduOCR] 获取access_token异常: {e}")
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
            
            # 调用百度OCR API
            result = self._call_baidu_ocr_api(image_data)
            
            if result and 'words_result' in result:
                texts = [item['words'] for item in result['words_result']]
                text = '\n'.join(texts)
                logger.info(f"[BaiduOCR] 提取到 {len(texts)} 行文字")
                return text
            else:
                logger.warning("[BaiduOCR] 未识别到文字")
                return None
                
        except Exception as e:
            logger.error(f"[BaiduOCR] 提取文字失败: {e}")
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
                'options': list,  # 选项列表
                'layout': list,  # 布局信息（包含坐标）
                'total_regions': int  # 区域总数
            }
        """
        if not self.is_available:
            return self._empty_result()
        
        try:
            # 读取图片
            image_data = self._read_image(image_path_or_url)
            if not image_data:
                return self._empty_result()
            
            # 调用百度OCR API（使用高精度版）
            result = self._call_baidu_ocr_api(image_data, use_accurate=True)
            
            if not result or 'words_result' not in result:
                logger.warning("[BaiduOCR] 未识别到文字")
                return self._empty_result()
            
            # 提取文字和坐标
            words_result = result['words_result']
            raw_text_lines = []
            layout = []
            
            for item in words_result:
                words = item.get('words', '')
                location = item.get('location', {})
                raw_text_lines.append(words)
                
                # 保存布局信息（坐标）
                layout.append({
                    'text': words,
                    'location': location
                })
            
            raw_text = '\n'.join(raw_text_lines)
            
            # 分解题干和选项
            question_text, options = self._split_question_and_options(raw_text_lines)
            
            return {
                'raw_text': raw_text,
                'question_text': question_text,
                'options': options,
                'layout': layout,
                'total_regions': len(words_result)
            }
            
        except Exception as e:
            logger.error(f"[BaiduOCR] 提取文字失败: {e}", exc_info=True)
            return self._empty_result()
    
    def _read_image(self, image_path_or_url: str) -> Optional[bytes]:
        """
        读取图片数据
        
        Args:
            image_path_or_url: 图片路径或URL
            
        Returns:
            bytes: 图片的二进制数据
        """
        try:
            # 处理file://协议
            if image_path_or_url.startswith('file://'):
                image_path = image_path_or_url[7:]
            elif image_path_or_url.startswith('http://') or image_path_or_url.startswith('https://'):
                # 下载网络图片
                import requests
                response = requests.get(image_path_or_url, timeout=10)
                response.raise_for_status()
                return response.content
            else:
                image_path = image_path_or_url
            
            # 读取本地文件
            if not os.path.exists(image_path):
                logger.error(f"[BaiduOCR] 图片文件不存在: {image_path}")
                return None
            
            with open(image_path, 'rb') as f:
                return f.read()
                
        except Exception as e:
            logger.error(f"[BaiduOCR] 读取图片失败: {e}")
            return None
    
    def _call_baidu_ocr_api(self, image_data: bytes, use_accurate: bool = False) -> Optional[Dict]:
        """
        调用百度OCR API
        
        Args:
            image_data: 图片的二进制数据
            use_accurate: 是否使用高精度版（更准确但更慢）
            
        Returns:
            dict: API返回结果
        """
        if not self.access_token:
            logger.error("[BaiduOCR] access_token未获取")
            return None
        
        try:
            import requests
            
            # 选择API端点
            if use_accurate:
                # 高精度版（更准确）
                url = "https://aip.baidubce.com/rest/2.0/ocr/v1/accurate_basic"
            else:
                # 标准版（更快）
                url = "https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic"
            
            # 将图片编码为base64
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            
            # 构建请求
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            data = {
                'access_token': self.access_token,
                'image': image_base64
            }
            
            # 发送请求
            response = requests.post(url, headers=headers, data=data, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            
            # 检查错误
            if 'error_code' in result:
                error_msg = result.get('error_msg', '未知错误')
                logger.error(f"[BaiduOCR] API错误: {error_msg} (code: {result['error_code']})")
                return None
            
            return result
            
        except Exception as e:
            logger.error(f"[BaiduOCR] 调用API失败: {e}")
            return None
    
    def _split_question_and_options(self, text_lines: List[str]) -> tuple:
        """
        将OCR结果分解为题干和选项
        
        Args:
            text_lines: OCR识别的文字行列表
            
        Returns:
            tuple: (question_text, options)
        """
        import re
        
        question_lines = []
        options = []
        found_options = False
        
        # 选项模式（更宽松的匹配）
        option_patterns = [
            re.compile(r'^[A-Z][\.、。]\s*'),  # A. A、A。
            re.compile(r'^\([A-Z]\)\s*'),  # (A)
            re.compile(r'^[A-Z]\s+'),  # A 后面跟空格
            re.compile(r'^[A-Z][:：]\s*'),  # A: A：
            re.compile(r'^[A-Z][推承制]'),  # A推、A承、A制（中文选项，如"A推脫承受抑制"）
            re.compile(r'^[A-Z][\u4e00-\u9fa5]'),  # A后面直接跟中文字符
        ]
        
        # 识别选项位置（有前缀的选项）
        option_indices = []
        for i, line in enumerate(text_lines):
            line_stripped = line.strip()
            if not line_stripped:
                continue
            for pattern in option_patterns:
                if pattern.match(line_stripped):
                    option_indices.append(i)
                    found_options = True
                    break
        
        if option_indices:
            # 有选项，题干在选项之前
            first_option_idx = min(option_indices)
            question_lines = text_lines[:first_option_idx]
            
            # 提取选项
            for i in option_indices:
                line = text_lines[i].strip()
                if line:
                    options.append(line)
        else:
            # 没有找到有前缀的选项，尝试识别无前缀的选项
            # 查找题干结束标记（如"填入"、"选择"、"最恰当的一项是"等）
            question_end_markers = [
                '填入', '填入画', '填入横线', '填入划横线', '填入画横线',
                '选择', '选出', '最恰当的一项是', '最合适的一项是',
                '正确的是', '错误的是', '不正确的是'
            ]
            
            question_end_idx = -1
            for i, line in enumerate(text_lines):
                line_stripped = line.strip()
                for marker in question_end_markers:
                    if marker in line_stripped:
                        question_end_idx = i
                        break
                if question_end_idx >= 0:
                    break
            
            # 如果找到题干结束标记，后面的行可能是选项
            if question_end_idx >= 0 and question_end_idx < len(text_lines) - 1:
                # 题干结束标记之后的行
                potential_options = text_lines[question_end_idx + 1:]
                
                # 过滤掉明显不是选项的行（太短、包含特殊字符等）
                for line in potential_options:
                    line_stripped = line.strip()
                    if not line_stripped:
                        continue
                    
                    # 选项特征：
                    # 1. 长度在2-20个字符之间（常见成语、短语长度）
                    # 2. 主要是中文字符
                    # 3. 不包含明显的题干特征（如"："、"。"等句末标点）
                    chinese_char_count = len(re.findall(r'[\u4e00-\u9fa5]', line_stripped))
                    total_char_count = len(line_stripped)
                    
                    # 如果主要是中文（>70%），且长度合适，且没有明显的题干特征
                    if (chinese_char_count > 0 and 
                        chinese_char_count / max(total_char_count, 1) > 0.7 and
                        2 <= total_char_count <= 20 and
                        not re.search(r'[：。，、]$', line_stripped)):  # 不以题干常见标点结尾
                        options.append(line_stripped)
                
                # 如果找到了选项，题干就是前面的部分
                if options:
                    question_lines = text_lines[:question_end_idx + 1]
                else:
                    # 没找到选项，所有行都作为题干
                    question_lines = text_lines
            else:
                # 没有找到题干结束标记，所有行都作为题干
                question_lines = text_lines
        
        question_text = '\n'.join(question_lines)
        
        # 后处理：修复横杠识别问题
        # OCR可能将横杠识别为 _、___、, 等，尝试识别并补全
        question_text = self._fix_underscores(question_text)
        
        return question_text, options
    
    def _fix_underscores(self, text: str) -> str:
        """
        修复OCR识别的横杠问题
        OCR可能将横杠识别为 _、___、, 等，尝试识别并补全为合适的横线
        """
        import re
        
        # 常见的横杠模式
        # 1. 单个下划线 _（可能是横杠的一部分）
        # 2. 多个下划线 ___（已经是横杠，保持不变）
        # 3. 逗号 ,（可能是横杠被误识别）
        
        # 策略1: 在"填入"、"横线"等关键词后的单个下划线或逗号
        text = re.sub(r'(填入[^。，：]*?画?横线?[^。，：]*?)([_,])([^。，：]*?[。，：，]?)', r'\1______\3', text)
        # 策略1b: 在"填入"、"横线"等关键词后的单个下划线（后面是逗号或冒号）
        text = re.sub(r'(填入[^。，：]*?画?横线?[^。，：]*?[：:])([_,])([,，])', r'\1______\3', text)
        
        # 策略2: 在题干中的单个下划线或逗号（前后都是中文）
        # 匹配：中文 + 单个下划线/逗号 + 中文/句号
        text = re.sub(r'([\u4e00-\u9fa5])([_,])([\u4e00-\u9fa5。])', r'\1______\3', text)
        
        # 策略3: 在句末的逗号或下划线（可能是横杠）
        # 匹配：中文 + 逗号/下划线 + 句号/换行/结束
        text = re.sub(r'([\u4e00-\u9fa5])([_,])([。\n]|$)', r'\1______\3', text)
        
        # 策略4: 在"的"、"是"等词后的逗号或下划线（很可能是横杠）
        text = re.sub(r'([的是])([_,])([的为])', r'\1______\3', text)
        
        # 策略5: 在"不容"、"不能"等词后的单个下划线（很可能是横杠）
        text = re.sub(r'(不容|不能|不可|不会)([_,])([的为是])', r'\1______\3', text)
        
        return text
    
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
_baidu_ocr_service = None

def get_baidu_ocr_service():
    """获取百度OCR服务实例（单例模式）"""
    global _baidu_ocr_service
    if _baidu_ocr_service is None:
        _baidu_ocr_service = BaiduOCRService()
    return _baidu_ocr_service

