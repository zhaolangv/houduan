"""
优化OCR服务：提高识别完整性和准确率
"""
import os
import re
import logging
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import numpy as np

logger = logging.getLogger(__name__)

class OptimizedOCRService:
    """优化OCR服务：多种预处理 + 高精度OCR（优先使用百度OCR）"""
    
    def __init__(self):
        self.ocr_service = None
        self.baidu_ocr_service = None
        self._init_ocr()
    
    def _init_ocr(self):
        """初始化OCR服务（优先百度OCR，备选本地OCR）"""
        # 优先尝试百度OCR
        try:
            from baidu_ocr_service import get_baidu_ocr_service
            self.baidu_ocr_service = get_baidu_ocr_service()
            if self.baidu_ocr_service and self.baidu_ocr_service.is_available:
                logger.info("[OptimizedOCR] 使用百度OCR服务（高精度）")
                return
        except Exception as e:
            logger.debug(f"[OptimizedOCR] 百度OCR不可用: {e}")
        
        # 备选：本地OCR
        try:
            from ocr_service import get_ocr_service
            self.ocr_service = get_ocr_service()
            if self.ocr_service and self.ocr_service.ocr_engine:
                logger.info("[OptimizedOCR] 使用本地OCR服务（PaddleOCR）")
            else:
                logger.warning("[OptimizedOCR] OCR服务不可用")
        except Exception as e:
            logger.error(f"[OptimizedOCR] OCR服务初始化失败: {e}")
    
    def preprocess_image_advanced(self, image_path):
        """
        高级图片预处理：多种策略提高OCR准确率
        
        Args:
            image_path: 图片路径
            
        Returns:
            list: 多个预处理后的图片（尝试不同策略）
        """
        try:
            original = Image.open(image_path).convert('RGB')
            processed_images = []
            
            # 策略1: 基础增强（对比度+锐度）
            img1 = original.copy()
            enhancer = ImageEnhance.Contrast(img1)
            img1 = enhancer.enhance(1.8)
            enhancer = ImageEnhance.Sharpness(img1)
            img1 = enhancer.enhance(1.5)
            processed_images.append(('enhanced', img1))
            
            # 策略2: 二值化（适合文字清晰的图片）
            img2 = original.copy()
            # 转为灰度
            if img2.mode != 'L':
                img2 = img2.convert('L')
            # 增强对比度后二值化
            enhancer = ImageEnhance.Contrast(img2)
            img2 = enhancer.enhance(2.0)
            # 二值化
            threshold = 128
            img2 = img2.point(lambda x: 255 if x > threshold else 0, mode='1')
            img2 = img2.convert('RGB')
            processed_images.append(('binary', img2))
            
            # 策略3: 去噪+增强（适合有噪点的图片）
            img3 = original.copy()
            img3 = img3.filter(ImageFilter.MedianFilter(size=3))
            enhancer = ImageEnhance.Contrast(img3)
            img3 = enhancer.enhance(1.6)
            enhancer = ImageEnhance.Brightness(img3)
            img3 = enhancer.enhance(1.1)
            processed_images.append(('denoised', img3))
            
            # 策略4: 高分辨率（如果原图较小，放大）
            width, height = original.size
            if width < 1000 or height < 1000:
                img4 = original.copy()
                # 放大2倍
                new_width = width * 2
                new_height = height * 2
                img4 = img4.resize((new_width, new_height), Image.Resampling.LANCZOS)
                # 增强
                enhancer = ImageEnhance.Contrast(img4)
                img4 = enhancer.enhance(1.5)
                processed_images.append(('upscaled', img4))
            
            # 策略5: 原始图片（作为备选）
            processed_images.append(('original', original.copy()))
            
            logger.info(f"[OptimizedOCR] 生成了 {len(processed_images)} 种预处理图片")
            return processed_images
            
        except Exception as e:
            logger.error(f"[OptimizedOCR] 图片预处理失败: {e}")
            return [('original', Image.open(image_path).convert('RGB'))]
    
    def extract_text_multi_strategy(self, image_path):
        """
        多策略OCR提取：尝试多种预处理，选择最佳结果
        
        Args:
            image_path: 图片路径
            
        Returns:
            str: 最佳OCR结果
        """
        if not self.ocr_service or not self.ocr_service.ocr_engine:
            logger.warning("[OptimizedOCR] OCR服务不可用")
            return ""
        
        processed_images = self.preprocess_image_advanced(image_path)
        results = []
        
        import tempfile
        
        for strategy_name, processed_img in processed_images:
            try:
                # 保存到临时文件
                with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
                    tmp_path = tmp_file.name
                    processed_img.save(tmp_path, 'JPEG', quality=95)
                
                try:
                    # OCR识别
                    if hasattr(self.ocr_service.ocr_engine, 'ocr'):
                        try:
                            ocr_result = self.ocr_service.ocr_engine.ocr(tmp_path, cls=True)
                        except TypeError:
                            ocr_result = self.ocr_service.ocr_engine.ocr(tmp_path)
                        
                        if ocr_result and ocr_result[0]:
                            # 提取文字
                            if isinstance(ocr_result[0], dict):
                                texts = ocr_result[0].get('rec_texts', [])
                            else:
                                texts = [line[1][0] for line in ocr_result[0]]
                            
                            text = '\n'.join(texts)
                            text_length = len(text)
                            
                            if text:
                                results.append({
                                    'strategy': strategy_name,
                                    'text': text,
                                    'length': text_length,
                                    'line_count': len(texts)
                                })
                                logger.info(f"[OptimizedOCR] 策略 '{strategy_name}': 提取到 {text_length} 字符, {len(texts)} 行")
                    
                finally:
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
                        
            except Exception as e:
                logger.warning(f"[OptimizedOCR] 策略 '{strategy_name}' 失败: {e}")
                continue
        
        if not results:
            logger.warning("[OptimizedOCR] 所有策略都失败")
            return ""
        
        # 选择最佳结果：优先选择文字最长的
        best_result = max(results, key=lambda x: x['length'])
        logger.info(f"[OptimizedOCR] 选择最佳策略: {best_result['strategy']}, 长度: {best_result['length']} 字符")
        
        return best_result['text']
    
    def extract_question_and_options_optimized(self, image_path):
        """
        优化版：提取题干和选项（优先百度OCR，备选本地OCR）
        
        Args:
            image_path: 图片路径
            
        Returns:
            dict: {
                'question_text': str,
                'options': list,
                'raw_text': str,
                'confidence': float
            }
        """
        # 优先使用百度OCR（如果可用）
        if self.baidu_ocr_service and self.baidu_ocr_service.is_available:
            logger.info("[OptimizedOCR] 使用百度OCR提取题干和选项...")
            result = self.baidu_ocr_service.extract_text_with_regions(image_path)
            
            if result and result.get('raw_text'):
                # 计算置信度（百度OCR通常更准确）
                confidence = 0.9
                if result.get('question_text'):
                    confidence += 0.05
                if len(result.get('options', [])) >= 2:
                    confidence += 0.05
                
                result['confidence'] = min(confidence, 1.0)
                logger.info(f"[OptimizedOCR] 百度OCR提取成功: {len(result['raw_text'])} 字符, {len(result.get('options', []))} 选项")
                return result
            else:
                logger.warning("[OptimizedOCR] 百度OCR提取失败，尝试本地OCR")
        
        # 备选：本地OCR多策略
        raw_text = self.extract_text_multi_strategy(image_path)
        
        if not raw_text:
            return {
                'question_text': '',
                'options': [],
                'raw_text': '',
                'confidence': 0.0
            }
        
        # 智能分割题干和选项
        result = self._split_question_and_options_advanced(raw_text)
        result['raw_text'] = raw_text
        
        return result
    
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
    
    def _split_question_and_options_advanced(self, raw_text):
        """
        高级分割：更智能的题干和选项识别
        """
        lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
        
        if not lines:
            return {
                'question_text': '',
                'options': [],
                'confidence': 0.0
            }
        
        question_lines = []
        options = []
        found_options = False
        
        # 选项模式（更全面）
        option_patterns = [
            re.compile(r'^[A-Z][\.、。]\s*'),  # A. A、A。
            re.compile(r'^\([A-Z]\)\s*'),  # (A)
            re.compile(r'^[A-Z]\s+'),  # A 后面跟空格
            re.compile(r'^[A-Z][:：]\s*'),  # A: A：
        ]
        
        # 第一遍：识别选项位置
        option_indices = []
        for i, line in enumerate(lines):
            for pattern in option_patterns:
                if pattern.match(line):
                    option_indices.append(i)
                    found_options = True
                    break
        
        if option_indices:
            # 有选项，题干在选项之前
            first_option_idx = min(option_indices)
            question_lines = lines[:first_option_idx]
            
            # 提取选项
            for i in option_indices:
                line = lines[i]
                # 提取选项标记和内容
                for pattern in option_patterns:
                    match = pattern.match(line)
                    if match:
                        option_content = pattern.sub('', line).strip()
                        if option_content:
                            options.append(line)  # 保留完整格式
                        break
        else:
            # 没有找到有前缀的选项，尝试识别无前缀的选项
            # 查找题干结束标记（如"填入"、"选择"、"最恰当的一项是"等）
            question_end_markers = [
                '填入', '填入画', '填入横线', '填入划横线', '填入画横线',
                '选择', '选出', '最恰当的一项是', '最合适的一项是',
                '正确的是', '错误的是', '不正确的是'
            ]
            
            question_end_idx = -1
            for i, line in enumerate(lines):
                line_stripped = line.strip()
                for marker in question_end_markers:
                    if marker in line_stripped:
                        question_end_idx = i
                        break
                if question_end_idx >= 0:
                    break
            
            # 如果找到题干结束标记，后面的行可能是选项
            if question_end_idx >= 0 and question_end_idx < len(lines) - 1:
                # 题干结束标记之后的行
                potential_options = lines[question_end_idx + 1:]
                
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
                        found_options = True
                
                # 如果找到了选项，题干就是前面的部分
                if options:
                    question_lines = lines[:question_end_idx + 1]
                else:
                    # 没找到选项，所有行都作为题干
                    question_lines = lines
            else:
                # 没有找到题干结束标记，尝试其他方法
                # 方法1: 查找常见的选项格式（如 "A. 选项A B. 选项B" 在同一行）
                for line in lines:
                    # 查找多个选项标记
                    matches = re.findall(r'([A-Z][\.、。]\s*[^A-Z]+)', line)
                    if len(matches) >= 2:
                        # 可能是多个选项在一行
                        options.extend(matches)
                        found_options = True
                    elif re.search(r'\b[A-Z][\.、。]\s+', line):
                        # 单个选项
                        options.append(line)
                        found_options = True
                
                if not found_options:
                    # 所有行都作为题干
                    question_lines = lines
        
        # 合并题干
        question_text = '\n'.join(question_lines)
        
        # 如果题干为空，使用所有非选项行
        if not question_text and options:
            # 选项之前的行都是题干
            for line in lines:
                is_option_line = False
                for opt in options:
                    if line.startswith(opt.split()[0] if opt.split() else ''):
                        is_option_line = True
                        break
                if not is_option_line:
                    question_lines.append(line)
            question_text = '\n'.join(question_lines)
        
        # 后处理：修复横杠识别问题
        question_text = self._fix_underscores(question_text)
        
        # 计算置信度
        confidence = 0.3
        if question_text:
            confidence += 0.3
            if len(question_text) > 50:
                confidence += 0.2
        if len(options) >= 2:
            confidence += 0.2
        if len(options) >= 4:
            confidence += 0.1
        
        return {
            'question_text': question_text,
            'options': options,
            'confidence': min(confidence, 1.0)
        }
    
    def analyze_with_deepseek_optimized(self, image_path):
        """
        优化版完整流程：多策略OCR + DeepSeek分析
        """
        # 1. 多策略OCR提取
        ocr_result = self.extract_question_and_options_optimized(image_path)
        
        if not ocr_result['raw_text']:
            raise Exception("OCR未提取到任何文字")
        
        logger.info(f"[OptimizedOCR] OCR提取结果:")
        logger.info(f"  原始文字长度: {len(ocr_result['raw_text'])} 字符")
        logger.info(f"  题干长度: {len(ocr_result['question_text'])} 字符")
        logger.info(f"  选项数: {len(ocr_result['options'])}")
        
        # 提取选项中的关键词，帮助DeepSeek补全题干
        option_keywords = []
        for opt in ocr_result.get('options', []):
            # 提取选项中的实词（去除A. B.等标记）
            words = re.findall(r'[^\sA-Z\.、。]+', opt)
            option_keywords.extend(words)
        option_keywords = list(set(option_keywords))[:15]  # 去重，最多15个
        
        # 2. 构建详细的提示词
        prompt = f"""请仔细分析以下OCR识别结果，完整提取题干和所有选项，并给出正确答案和详细解析。

OCR识别结果（原始文本，可能不完整）：
{ocr_result['raw_text']}

选项中的关键词（帮助补全题干）：
{', '.join(option_keywords) if option_keywords else '无'}

重要提示：
1. **OCR结果可能不完整或被截断**，请根据以下信息推断完整题干：
   - 选项内容（选项中的关键词通常对应题干中缺失的部分）
   - 选项中的关键词：{', '.join(option_keywords) if option_keywords else '无'}
   - 常见题目格式和语言习惯
   - 上下文逻辑关系
   
2. **题干补全策略（非常重要）**：
   - 如果看到下划线（_____）或省略号（...），说明OCR识别不完整
   - **关键**：根据选项中的词语推断题干中缺失的部分
   - 例如：如果选项有"推脱"、"承载"、"制约"，题干中应该有对应的位置
   - 确保题干语法完整、逻辑通顺
   - 题干应该是一个完整的句子或段落
   - **不要保留下划线或省略号，必须补全为完整文字**
   - **题干中的每个下划线（_____）都必须替换为具体的词语**
   
3. **选项识别**：
   - 仔细识别所有选项（A、B、C、D等）
   - 确保选项格式正确
   - 选项内容要完整
   
4. **补全示例**：
   - OCR显示："尽管环境保护任务艰巨，但迫在眉睫，不容______。"
   - 选项中有"推脱"、"推托"
   - 完整题干应该是："尽管环境保护任务艰巨，但迫在眉睫，不容推脱。"
   
5. **特别注意**：
   - 题干中的下划线（_____）必须替换为具体的词语
   - 根据选项中的词语和上下文逻辑，推断最合适的词语
   - 确保补全后的题干语义完整、逻辑通顺
   - **不要返回包含下划线的题干**

请返回完整的JSON格式：
{{
  "question_text": "完整的题干内容（必须完整，所有下划线都要替换为具体词语，不要省略）",
  "options": ["A. 选项A的完整内容", "B. 选项B的完整内容", "C. 选项C的完整内容", "D. 选项D的完整内容"],
  "correct_answer": "B",
  "explanation": "详细的解析过程，包括为什么选择这个答案"
}}"""
        
        # 3. 发送给DeepSeek
        try:
            from ai_service import AIService
            ai_service = AIService()
            
            if not ai_service.client:
                raise Exception("AI服务不可用")
            
            response = ai_service.client.chat.completions.create(
                model=ai_service.default_model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # 降低温度，提高准确性
                max_tokens=3000
            )
            
            ai_response = response.choices[0].message.content
            
            # 4. 解析JSON响应
            import json
            json_str = ai_response.strip()
            
            # 提取JSON
            if '```json' in json_str:
                json_match = re.search(r'```json\s*(.*?)\s*```', json_str, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1).strip()
            elif '```' in json_str:
                json_match = re.search(r'```\s*(.*?)\s*```', json_str, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1).strip()
            
            # 提取JSON对象
            json_match = re.search(r'\{.*\}', json_str, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            
            result = json.loads(json_str)
            
            # 合并OCR结果
            result['raw_text'] = ocr_result['raw_text']
            result['ocr_confidence'] = ocr_result['confidence']
            result['ocr_question_text'] = ocr_result['question_text']
            result['ocr_options'] = ocr_result['options']
            
            return result
            
        except Exception as e:
            logger.error(f"[OptimizedOCR] DeepSeek分析失败: {e}", exc_info=True)
            raise


# 全局服务实例
_optimized_ocr_service = None

def get_optimized_ocr_service():
    """获取优化OCR服务实例（单例模式）"""
    global _optimized_ocr_service
    if _optimized_ocr_service is None:
        _optimized_ocr_service = OptimizedOCRService()
    return _optimized_ocr_service

