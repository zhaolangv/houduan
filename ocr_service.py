"""
OCR服务：提取图片中的文字
支持多种OCR方式：PaddleOCR（推荐）、Tesseract（备选）
"""
import os
import logging
import threading
from PIL import Image, ImageEnhance, ImageFilter
import numpy as np

logger = logging.getLogger(__name__)

class OCRService:
    """OCR服务类"""
    
    def __init__(self):
        self.ocr_engine = None
        self._ocr_lock = threading.Lock()  # 添加线程锁，确保并发安全
        self._init_ocr()
    
    def _init_ocr(self):
        """初始化OCR引擎"""
        # 优先尝试PaddleOCR（中文识别效果好）
        try:
            from paddleocr import PaddleOCR
            # 简化参数，避免不兼容的参数导致初始化失败
            try:
                # 首先尝试使用基础参数
                self.ocr_engine = PaddleOCR(
                    use_angle_cls=True, 
                    lang='ch',
                    use_gpu=False,  # 如果False则使用CPU
                )
                logger.info("[OCR] 使用PaddleOCR引擎（基础参数）")
            except Exception as e:
                # 如果基础参数失败，使用最基础参数
                logger.warning(f"[OCR] PaddleOCR基础参数初始化失败: {e}，尝试最基础参数")
                self.ocr_engine = PaddleOCR(lang='ch')
                logger.info("[OCR] 使用PaddleOCR引擎（最基础参数）")
            return
        except ImportError:
            logger.debug("[OCR] PaddleOCR未安装，尝试Tesseract")
        except Exception as e:
            logger.warning(f"[OCR] PaddleOCR初始化失败: {e}")
            # 如果初始化失败，尝试使用默认参数
            try:
                from paddleocr import PaddleOCR
                self.ocr_engine = PaddleOCR(use_angle_cls=True, lang='ch')
                logger.info("[OCR] 使用PaddleOCR引擎（默认参数）")
                return
            except:
                pass
        
        # 备选：Tesseract
        try:
            import pytesseract
            # 检查tesseract是否安装
            try:
                pytesseract.get_tesseract_version()
                self.ocr_engine = 'tesseract'
                logger.info("[OCR] 使用Tesseract引擎")
                return
            except Exception:
                logger.warning("[OCR] Tesseract未正确安装")
        except ImportError:
            logger.debug("[OCR] pytesseract未安装")
        
        logger.warning("[OCR] 未找到可用的OCR引擎，将使用图片描述代替")
        self.ocr_engine = None
    
    def _preprocess_image(self, image_path):
        """
        预处理图片以提高OCR识别率
        特别优化顶部和边缘区域，提高小文字识别率
        
        Args:
            image_path: 图片路径
            
        Returns:
            str: 预处理后的图片路径（临时文件）
        """
        try:
            # 打开原始图片
            img = Image.open(image_path)
            
            # 转换为RGB模式（如果不是）
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            width, height = img.size
            
            # 1. 特别处理顶部区域（可能包含标题和小文字）
            # 提取顶部20%的区域进行额外增强
            top_region_height = int(height * 0.2)
            top_region = img.crop((0, 0, width, top_region_height))
            
            # 对顶部区域进行更强的对比度和锐化处理
            top_enhancer = ImageEnhance.Contrast(top_region)
            top_region = top_enhancer.enhance(1.5)  # 顶部增强50%
            
            top_enhancer = ImageEnhance.Sharpness(top_region)
            top_region = top_enhancer.enhance(1.4)  # 顶部锐化40%
            
            # 2. 整体图片处理
            # 增强对比度（提高文字与背景的对比）
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.4)  # 增强40%（提高）
            
            # 增强锐度（让文字边缘更清晰）
            enhancer = ImageEnhance.Sharpness(img)
            img = enhancer.enhance(1.3)  # 增强30%（提高）
            
            # 3. 将处理后的顶部区域贴回原图
            img.paste(top_region, (0, 0))
            
            # 4. 转换为灰度图再转回RGB（提高对比度）
            gray = img.convert('L')
            
            # 使用自适应阈值增强（提高小文字识别率）
            try:
                # 使用CLAHE算法增强对比度（如果可用）
                try:
                    import cv2
                    gray_array = np.array(gray)
                    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                    gray_array = clahe.apply(gray_array)
                    gray = Image.fromarray(gray_array)
                    logger.debug("[OCR] 使用CLAHE算法增强对比度")
                except ImportError:
                    # 如果OpenCV不可用，使用普通亮度增强
                    enhancer = ImageEnhance.Brightness(gray)
                    gray = enhancer.enhance(1.15)  # 增强15%
            except Exception as e:
                # 如果处理失败，使用普通亮度增强
                enhancer = ImageEnhance.Brightness(gray)
                gray = enhancer.enhance(1.15)  # 增强15%
                logger.debug(f"[OCR] CLAHE处理失败，使用普通增强: {e}")
            
            # 转回RGB
            img = gray.convert('RGB')
            
            # 5. 轻微去噪（保持文字清晰的同时减少噪点）
            # 使用更小的去噪滤波器，避免模糊小文字
            img = img.filter(ImageFilter.MedianFilter(size=3))
            
            # 保存预处理后的图片到临时文件
            import tempfile
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, f'ocr_preprocessed_{os.path.basename(image_path)}')
            img.save(temp_path, quality=100, optimize=False)  # 提高质量到100
            
            logger.debug(f"[OCR] 图片预处理完成: {temp_path}")
            return temp_path
            
        except Exception as e:
            logger.warning(f"[OCR] 图片预处理失败: {e}，使用原始图片")
            return image_path  # 如果预处理失败，返回原始路径
    
    def extract_text(self, image_path_or_url, use_preprocess=True):
        """
        从图片中提取文字
        
        Args:
            image_path_or_url: 图片路径或URL
            use_preprocess: 是否使用图片预处理（默认True，可提高识别率）
            
        Returns:
            str: 提取的文字，如果失败返回None
        """
        import time
        start_time = time.time()
        
        if not self.ocr_engine:
            logger.warning("[OCR] ⚠️ OCR引擎未初始化")
            return None
        
        preprocessed_path = None
        try:
            # 处理file://协议
            if image_path_or_url.startswith('file://'):
                image_path = image_path_or_url[7:]  # 移除file://
            else:
                image_path = image_path_or_url
            
            file_size = os.path.getsize(image_path) / 1024  # KB
            logger.info(f"[OCR] 🚀 开始OCR识别: {os.path.basename(image_path)}, 大小={file_size:.1f}KB, 预处理={'是' if use_preprocess else '否'}")
            
            # 确保文件存在
            if not os.path.exists(image_path):
                logger.error(f"[OCR] ❌ 图片文件不存在: {image_path}")
                return None
            
            # 预处理图片（提高识别率）
            preprocess_time = 0
            if use_preprocess:
                preprocess_start = time.time()
                logger.debug(f"[OCR] 📸 开始图片预处理...")
                preprocessed_path = self._preprocess_image(image_path)
                preprocess_time = time.time() - preprocess_start
                ocr_image_path = preprocessed_path
                logger.debug(f"[OCR] ✅ 图片预处理完成，耗时={preprocess_time:.2f}秒")
            else:
                ocr_image_path = image_path
                logger.debug(f"[OCR] ⏭️  跳过图片预处理")
            
            # 使用PaddleOCR（需要加锁防止并发冲突）
            if hasattr(self.ocr_engine, 'ocr'):
                ocr_start = time.time()
                logger.info(f"[OCR] 🔍 开始调用PaddleOCR引擎识别...")
                try:
                    # 使用锁确保OCR调用是串行的，避免并发问题（Windows下PaddleOCR可能有并发bug）
                    with self._ocr_lock:
                        logger.debug(f"[OCR] 🔒 已获取OCR锁，开始OCR识别...")
                        result = self.ocr_engine.ocr(ocr_image_path)
                        logger.debug(f"[OCR] 🔓 OCR识别完成，释放锁")
                except Exception as e:
                    ocr_time = time.time() - ocr_start
                    error_str = str(e)
                    logger.error(f"[OCR] ❌ PaddleOCR调用失败: {error_str}, 耗时={ocr_time:.2f}秒")
                    # 检查是否是Tensor内存错误或API不兼容
                    if 'Tensor' in error_str or 'memory' in error_str.lower() or 'unexpected keyword' in error_str.lower():
                        logger.warning(f"[OCR] ⚠️ 检测到错误（可能是并发或API兼容问题）: {error_str[:100]}")
                    result = None
                
                if result:
                    texts = []
                    
                    # 尝试解析新版本格式（字典格式）
                    if isinstance(result, list) and len(result) > 0:
                        # 检查第一个元素是否是字典（新版本格式）
                        if isinstance(result[0], dict):
                            # 新版本格式：可能是Result对象或字典
                            try:
                                # 尝试从json属性获取
                                if hasattr(result[0], 'json'):
                                    json_data = result[0].json
                                    if isinstance(json_data, dict):
                                        # 尝试从各种可能的字段提取文字
                                        if 'rec_texts' in json_data:
                                            texts = json_data['rec_texts']
                                        elif 'text' in json_data:
                                            texts = [json_data['text']]
                                        elif 'rec_res' in json_data:
                                            rec_res = json_data['rec_res']
                                            if isinstance(rec_res, list):
                                                texts = [item.get('text', '') if isinstance(item, dict) else str(item) for item in rec_res]
                            except:
                                pass
                            
                            # 如果还是没有提取到，尝试直接访问字典字段
                            if not texts and isinstance(result[0], dict):
                                # 尝试访问常见的OCR结果字段
                                if 'rec_texts' in result[0]:
                                    texts = result[0]['rec_texts'] if isinstance(result[0]['rec_texts'], list) else [result[0]['rec_texts']]
                                elif 'text' in result[0]:
                                    texts = [result[0]['text']]
                                elif 'ocr_res' in result[0]:
                                    ocr_res = result[0]['ocr_res']
                                    if isinstance(ocr_res, list):
                                        texts = []
                                        for item in ocr_res:
                                            if isinstance(item, dict) and 'text' in item:
                                                texts.append(item['text'])
                                            elif isinstance(item, (list, tuple)) and len(item) > 0:
                                                texts.append(str(item[0]))
                        
                        # 尝试解析旧版本格式（列表格式）
                        elif isinstance(result[0], list):
                            try:
                                # 旧版本格式：[[[坐标], (文字, 置信度)], ...]
                                for line in result[0]:
                                    if isinstance(line, (list, tuple)) and len(line) >= 2:
                                        text_info = line[1]
                                        if isinstance(text_info, (list, tuple)) and len(text_info) > 0:
                                            texts.append(str(text_info[0]))
                                        elif isinstance(text_info, str):
                                            texts.append(text_info)
                            except Exception as e:
                                logger.warning(f"[OCR] 解析旧版本格式失败: {e}")
                    
                    ocr_time = time.time() - ocr_start
                    
                    if texts:
                        text = '\n'.join([str(t) for t in texts if t])
                        text_length = len(text)
                        total_time = time.time() - start_time
                        logger.info(f"[OCR] ✅ OCR识别成功: 提取到 {len(texts)} 行文字，共 {text_length} 字符")
                        logger.info(f"[OCR] ⏱️  耗时统计: 预处理={preprocess_time:.2f}秒, OCR={ocr_time:.2f}秒, 总计={total_time:.2f}秒")
                        logger.debug(f"[OCR] 📝 提取的文字内容（前100字符）: {text[:100]}...")
                        return text
                    else:
                        logger.warning("[OCR] ⚠️ 未能从结果中提取文字，可能是格式不匹配")
                        logger.debug(f"[OCR] 结果类型: {type(result)}, 第一个元素类型: {type(result[0]) if result else None}")
                        ocr_time = time.time() - ocr_start
                        total_time = time.time() - start_time
                        logger.info(f"[OCR] ⏱️  耗时统计: 预处理={preprocess_time:.2f}秒, OCR={ocr_time:.2f}秒, 总计={total_time:.2f}秒")
                        return None
                else:
                    ocr_time = time.time() - ocr_start
                    total_time = time.time() - start_time
                    logger.info(f"[OCR] ⚠️ 未识别到文字")
                    logger.info(f"[OCR] ⏱️  耗时统计: 预处理={preprocess_time:.2f}秒, OCR={ocr_time:.2f}秒, 总计={total_time:.2f}秒")
                    return None
            
            # 使用Tesseract
            elif self.ocr_engine == 'tesseract':
                ocr_start = time.time()
                logger.info(f"[OCR] 🔍 开始调用Tesseract引擎识别...")
                import pytesseract
                from PIL import Image
                image = Image.open(image_path)
                # 支持中英文
                text = pytesseract.image_to_string(image, lang='chi_sim+eng')
                ocr_time = time.time() - ocr_start
                total_time = time.time() - start_time
                
                if text.strip():
                    text_length = len(text.strip())
                    logger.info(f"[OCR] ✅ OCR识别成功: 提取到 {text_length} 字符")
                    logger.info(f"[OCR] ⏱️  耗时统计: OCR={ocr_time:.2f}秒, 总计={total_time:.2f}秒")
                    logger.debug(f"[OCR] 📝 提取的文字内容（前100字符）: {text[:100]}...")
                    return text.strip()
                else:
                    logger.info(f"[OCR] ⚠️ 未识别到文字")
                    logger.info(f"[OCR] ⏱️  耗时统计: OCR={ocr_time:.2f}秒, 总计={total_time:.2f}秒")
                    return None
            
        except Exception as e:
            total_time = time.time() - start_time
            logger.error(f"[OCR] ❌ 文字提取失败: {e}, 耗时={total_time:.2f}秒", exc_info=True)
            return None
        finally:
            # 清理临时文件
            if preprocessed_path and preprocessed_path != image_path and os.path.exists(preprocessed_path):
                try:
                    os.remove(preprocessed_path)
                    logger.debug(f"[OCR] 已清理临时文件: {preprocessed_path}")
                except:
                    pass
    
    def extract_text_with_regions(self, image_path_or_url):
        """
        从图片中提取文字，并分解为题干和选项
        
        Args:
            image_path_or_url: 图片路径或URL
            
        Returns:
            dict: {
                'question_text': str,  # 题干内容
                'options': list,  # 选项列表，如 ['A. 选项A', 'B. 选项B', ...]
                'raw_text': str,  # 所有原始文字
                'regions': list,  # 区域信息，包含坐标和文字
                'layout': dict  # 布局信息
            }
        """
        import time
        start_time = time.time()
        
        if not self.ocr_engine or not hasattr(self.ocr_engine, 'ocr'):
            logger.warning("[OCR] ⚠️ OCR引擎未初始化或不支持区域提取")
            return {
                'question_text': '',
                'options': [],
                'raw_text': '',
                'regions': [],
                'layout': {}
            }
        
        try:
            # 处理file://协议
            if image_path_or_url.startswith('file://'):
                image_path = image_path_or_url[7:]
            else:
                image_path = image_path_or_url
            
            file_size = os.path.getsize(image_path) / 1024  # KB
            logger.info(f"[OCR] 🚀 开始OCR区域识别: {os.path.basename(image_path)}, 大小={file_size:.1f}KB")
            
            if not os.path.exists(image_path):
                logger.error(f"[OCR] ❌ 图片文件不存在: {image_path}")
                return {
                    'question_text': '',
                    'options': [],
                    'raw_text': '',
                    'regions': [],
                    'layout': {}
                }
            
            # 使用PaddleOCR获取带坐标的结果（使用锁确保线程安全）
            ocr_start = time.time()
            logger.info(f"[OCR] 🔍 开始调用PaddleOCR引擎进行区域识别...")
            try:
                # 使用锁确保OCR调用是串行的，避免并发问题（Windows下PaddleOCR可能有并发bug）
                with self._ocr_lock:
                    logger.debug(f"[OCR] 🔒 已获取OCR锁，开始区域识别...")
                    result = self.ocr_engine.ocr(image_path)
                    logger.debug(f"[OCR] 🔓 区域识别完成，释放锁")
            except Exception as e:
                ocr_time = time.time() - ocr_start
                total_time = time.time() - start_time
                logger.error(f"[OCR] ❌ PaddleOCR调用失败: {e}, OCR耗时={ocr_time:.2f}秒, 总计={total_time:.2f}秒")
                result = None
            
            if not result or not result[0]:
                logger.info("[OCR] 未识别到文字")
                return self._empty_result()
            
            # 调试：打印OCR结果的前几个元素
            logger.debug(f"[OCR] OCR结果类型: {type(result)}, 结果长度: {len(result) if result else 0}")
            if result and result[0]:
                if isinstance(result[0], dict):
                    logger.debug(f"[OCR] 新版本格式（字典），键: {list(result[0].keys())[:5]}")
                else:
                    logger.debug(f"[OCR] 旧版本格式（列表），第一行类型: {type(result[0][0]) if result[0] and len(result[0]) > 0 else None}")
            
            # 解析OCR结果
            # 新版本PaddleOCR返回格式：字典，包含 rec_texts, rec_scores, rec_polys
            # 旧版本格式：[[[x1,y1], [x2,y2], [x3,y3], [x4,y4]], (文字, 置信度)], ...]
            regions = []
            all_texts = []
            
            # 检查是否是新版本格式（字典）
            if isinstance(result[0], dict):
                rec_texts = result[0].get('rec_texts', [])
                rec_scores = result[0].get('rec_scores', [])
                rec_polys = result[0].get('rec_polys', [])
                
                logger.info(f"[OCR] 新版本格式：识别到 {len(rec_texts)} 个文字区域")
                logger.debug(f"[OCR] rec_texts数量: {len(rec_texts)}, rec_scores数量: {len(rec_scores)}, rec_polys数量: {len(rec_polys)}")
                
                for idx, (text, score, poly) in enumerate(zip(rec_texts, rec_scores, rec_polys)):
                    try:
                        # poly是numpy数组，shape=(4, 2)
                        try:
                            import numpy as np
                            if isinstance(poly, np.ndarray):
                                coordinates = poly.tolist()  # 转换为列表
                            else:
                                coordinates = poly
                        except ImportError:
                            # 如果没有numpy，尝试直接使用
                            coordinates = poly if isinstance(poly, list) else list(poly)
                        
                        if not coordinates or len(coordinates) < 4:
                            logger.debug(f"[OCR] 第{idx}个区域：坐标数量不足，coordinates={coordinates}")
                            continue
                        
                        # 计算文字框的中心点和边界
                        x_coords = [point[0] for point in coordinates if isinstance(point, (list, tuple)) and len(point) >= 2]
                        y_coords = [point[1] for point in coordinates if isinstance(point, (list, tuple)) and len(point) >= 2]
                        
                        if not x_coords or not y_coords:
                            continue
                        
                        center_x = sum(x_coords) / len(x_coords)
                        center_y = sum(y_coords) / len(y_coords)
                        min_y = min(y_coords)
                        max_y = max(y_coords)
                        min_x = min(x_coords)
                        max_x = max(x_coords)
                        
                        regions.append({
                            'text': text,
                            'confidence': float(score) if score is not None else 0.0,
                            'center': (center_x, center_y),
                            'bbox': {
                                'min_x': min_x,
                                'min_y': min_y,
                                'max_x': max_x,
                                'max_y': max_y,
                                'width': max_x - min_x,
                                'height': max_y - min_y
                            },
                            'coordinates': coordinates
                        })
                        
                        all_texts.append(text)
                    except Exception as e:
                        logger.warning(f"[OCR] 解析第{idx}个区域时出错: {e}")
                        continue
            else:
                # 旧版本格式
                for idx, line in enumerate(result[0]):
                    if not line:
                        continue
                    
                    try:
                        if isinstance(line, list) and len(line) >= 2:
                            coordinates = line[0]
                            text_info = line[1]
                            
                            if not isinstance(coordinates, list) or len(coordinates) < 4:
                                continue
                            
                            if not all(isinstance(point, (list, tuple)) and len(point) >= 2 for point in coordinates):
                                continue
                            
                            if not text_info or not isinstance(text_info, (list, tuple)) or len(text_info) < 1:
                                continue
                            
                            text = text_info[0] if isinstance(text_info, (list, tuple)) else str(text_info)
                            confidence = text_info[1] if isinstance(text_info, (list, tuple)) and len(text_info) > 1 else 0.0
                            
                            x_coords = [point[0] for point in coordinates if isinstance(point, (list, tuple)) and len(point) >= 2]
                            y_coords = [point[1] for point in coordinates if isinstance(point, (list, tuple)) and len(point) >= 2]
                            
                            if not x_coords or not y_coords:
                                continue
                            
                            center_x = sum(x_coords) / len(x_coords)
                            center_y = sum(y_coords) / len(y_coords)
                            min_y = min(y_coords)
                            max_y = max(y_coords)
                            min_x = min(x_coords)
                            max_x = max(x_coords)
                            
                            regions.append({
                                'text': text,
                                'confidence': confidence,
                                'center': (center_x, center_y),
                                'bbox': {
                                    'min_x': min_x,
                                    'min_y': min_y,
                                    'max_x': max_x,
                                    'max_y': max_y,
                                    'width': max_x - min_x,
                                    'height': max_y - min_y
                                },
                                'coordinates': coordinates
                            })
                            
                            all_texts.append(text)
                    except Exception as e:
                        logger.warning(f"[OCR] 解析第{idx}行时出错: {e}")
                        continue
            
            ocr_time = time.time() - ocr_start
            logger.info(f"[OCR] ✅ OCR区域识别完成: 识别到 {len(regions)} 个区域, OCR耗时={ocr_time:.2f}秒")
            
            # 按Y坐标排序（从上到下）
            regions.sort(key=lambda r: r['center'][1])
            
            # 分析布局，分离题干和选项
            layout_start = time.time()
            logger.debug(f"[OCR] 📐 开始分析布局，分离题干和选项...")
            question_text = ''
            options = []
            
            if regions:
                # 获取图片高度（用于判断位置）
                from PIL import Image
                img = Image.open(image_path)
                img_height = img.height
                
                # 方法1: 根据文字内容模式识别选项（A. B. C. D. 等）
                import re
                option_patterns = [
                    r'^[A-Z]\.',  # A. B. C. D.
                    r'^[A-Z]\s',  # A B C D
                    r'^[①②③④⑤⑥]',  # ①②③④
                    r'^[（(][A-Z][）)]',  # (A) (B)
                ]
                
                option_regions = []
                question_regions = []
                
                for region in regions:
                    text = region['text'].strip()
                    is_option = False
                    
                    # 检查是否符合选项模式
                    for pattern in option_patterns:
                        if re.match(pattern, text):
                            is_option = True
                            break
                    
                    if is_option:
                        option_regions.append(region)
                    else:
                        question_regions.append(region)
                
                # 方法2: 如果选项模式识别失败，根据位置判断
                # 通常选项在图片下方（Y坐标较大）
                if not option_regions and len(regions) > 3:
                    # 计算所有文字的平均Y坐标
                    avg_y = sum(r['center'][1] for r in regions) / len(regions)
                    
                    # 重新分组
                    option_regions = []
                    question_regions = []
                    
                    # 上半部分通常是题干，下半部分可能是选项
                    for region in regions:
                        if region['center'][1] < avg_y:
                            question_regions.append(region)
                        else:
                            # 检查是否可能是选项（短文本，且位置靠下）
                            text = region['text'].strip()
                            if len(text) < 50 and region['center'][1] > img_height * 0.6:
                                option_regions.append(region)
                            else:
                                question_regions.append(region)
                
                # 组合题干文字
                if question_regions:
                    question_text = '\n'.join([r['text'] for r in question_regions])
                
                # 组合选项文字
                if option_regions:
                    options = [r['text'] for r in option_regions]
                else:
                    # 如果没有识别到选项，尝试从所有文字中提取
                    # 通常选项是短文本，且位置靠下
                    for region in regions:
                        text = region['text'].strip()
                        if len(text) < 100 and region['center'][1] > img_height * 0.7:
                            options.append(text)
            
            raw_text = '\n'.join(all_texts)
            
            # 计算区域统计
            question_regions_count = len(question_regions) if 'question_regions' in locals() and question_regions else 0
            option_regions_count = len(option_regions) if 'option_regions' in locals() and option_regions else 0
            
            layout_time = time.time() - layout_start
            total_time = time.time() - start_time
            
            result = {
                'question_text': question_text,
                'options': options,
                'raw_text': raw_text,
                'regions': regions,
                'layout': {
                    'total_regions': len(regions),
                    'question_regions': question_regions_count,
                    'option_regions': option_regions_count
                }
            }
            
            logger.info(f"[OCR] ✅ 区域分解完成: 题干={len(question_text)}字符, 选项数={len(options)}")
            logger.info(f"[OCR] ⏱️  耗时统计: OCR={ocr_time:.2f}秒, 布局分析={layout_time:.2f}秒, 总计={total_time:.2f}秒")
            return result
            
        except Exception as e:
            logger.error(f"[OCR] 区域文字提取失败: {e}", exc_info=True)
            return self._empty_result()
    
    def _empty_result(self):
        """返回空结果（统一格式）"""
        return {
            'question_text': '',
            'options': [],
            'raw_text': '',
            'regions': [],
            'layout': {
                'total_regions': 0,
                'question_regions': 0,
                'option_regions': 0
            }
        }
    
    def analyze_image_type(self, image_path_or_url):
        """
        分析图片类型：判断是图推题（图形为主）还是文字题（文字为主）
        
        Args:
            image_path_or_url: 图片路径或URL
            
        Returns:
            dict: {
                'type': 'graph' 或 'text',  # graph=图推题, text=文字题
                'confidence': 0.0-1.0,  # 置信度
                'text': str,  # 提取的文字（如果有）
                'text_length': int,  # 文字长度
                'text_lines': int,  # 文字行数
                'reason': str  # 判断理由
            }
        """
        result = {
            'type': 'graph',  # 默认是图推题
            'confidence': 0.5,
            'text': None,
            'text_length': 0,
            'text_lines': 0,
            'reason': ''
        }
        
        try:
            # 1. 尝试OCR提取文字
            ocr_text = self.extract_text(image_path_or_url)
            
            if ocr_text:
                result['text'] = ocr_text
                result['text_length'] = len(ocr_text)
                result['text_lines'] = len(ocr_text.split('\n'))
                
                # 判断逻辑：
                # - 文字长度 > 100字符：很可能是文字题
                # - 文字行数 > 3行：很可能是文字题
                # - 文字长度 < 30字符：很可能是图推题
                # - 文字行数 <= 2行：可能是图推题（只有题目编号或选项）
                
                if result['text_length'] > 100:
                    result['type'] = 'text'
                    result['confidence'] = 0.9
                    result['reason'] = f'提取到大量文字（{result["text_length"]}字符，{result["text_lines"]}行），判断为文字题'
                elif result['text_length'] > 50:
                    result['type'] = 'text'
                    result['confidence'] = 0.7
                    result['reason'] = f'提取到较多文字（{result["text_length"]}字符，{result["text_lines"]}行），判断为文字题'
                elif result['text_length'] < 30:
                    result['type'] = 'graph'
                    result['confidence'] = 0.8
                    result['reason'] = f'提取到少量文字（{result["text_length"]}字符，{result["text_lines"]}行），判断为图推题'
                elif result['text_lines'] <= 2:
                    result['type'] = 'graph'
                    result['confidence'] = 0.7
                    result['reason'] = f'文字行数较少（{result["text_lines"]}行），判断为图推题'
                else:
                    # 中等长度，根据行数判断
                    if result['text_lines'] > 3:
                        result['type'] = 'text'
                        result['confidence'] = 0.6
                        result['reason'] = f'文字行数较多（{result["text_lines"]}行），判断为文字题'
                    else:
                        result['type'] = 'graph'
                        result['confidence'] = 0.6
                        result['reason'] = f'文字行数较少（{result["text_lines"]}行），判断为图推题'
            else:
                # 没有提取到文字，很可能是图推题
                result['type'] = 'graph'
                result['confidence'] = 0.85
                result['reason'] = '未提取到文字，判断为图推题（纯图形）'
            
            logger.info(f"[OCR] 图片类型分析: {result['type']} (置信度: {result['confidence']:.2f}), 理由: {result['reason']}")
            return result
            
        except Exception as e:
            logger.error(f"[OCR] 图片类型分析失败: {e}", exc_info=True)
            result['reason'] = f'分析失败: {str(e)}'
            return result


# 全局OCR服务实例（单例模式，确保模型只加载一次）
_ocr_service = None

def get_ocr_service():
    """获取OCR服务实例（单例模式）"""
    global _ocr_service
    if _ocr_service is None:
        logger.info("[OCR] 初始化OCR服务（首次调用，模型将加载到内存）")
        _ocr_service = OCRService()
        logger.info("[OCR] OCR服务初始化完成，后续调用将复用已加载的模型")
    return _ocr_service

