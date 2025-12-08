"""
题目服务 V2：只接收图片，AI自动提取所有信息
"""
import os
import hashlib
import json
import logging
import base64
from datetime import datetime, date
from models_v2 import db, Question, AnswerVersion
import re
from ai_service import AIService
import uuid
from supabase_storage_service import get_supabase_storage_service
from difflib import SequenceMatcher
import imagehash
from PIL import Image
import io

logger = logging.getLogger(__name__)


class QuestionService:
    """题目服务类"""
    
    def __init__(self):
        self.ai_service = AIService()
        # 简单的内存缓存（LRU，最多100条）
        self._cache = {}
        self._cache_max_size = 100
    
    def calculate_question_hash(self, question_text, options):
        """
        计算题目哈希值（用于去重）
        
        Args:
            question_text: 题干
            options: 选项列表
            
        Returns:
            str: 哈希值
        """
        # 标准化题目文本（去除空格、换行等）
        normalized_text = question_text.strip().replace('\n', '').replace('\r', '').replace(' ', '')
        
        # 标准化选项
        normalized_options = []
        if isinstance(options, list):
            for opt in options:
                if isinstance(opt, str):
                    normalized_options.append(opt.strip())
        elif isinstance(options, str):
            # 如果是JSON字符串，解析
            try:
                options_list = json.loads(options)
                normalized_options = [str(opt).strip() for opt in options_list]
            except:
                normalized_options = [options.strip()]
        
        # 组合文本
        combined = normalized_text + '|' + '|'.join(sorted(normalized_options))
        
        # 计算MD5哈希
        return hashlib.md5(combined.encode('utf-8')).hexdigest()
    
    def find_duplicate_question(self, question_hash):
        """
        查找重复题目（基于完整题干哈希）
        
        Args:
            question_hash: 题目哈希值
            
        Returns:
            Question对象或None
        """
        return Question.query.filter_by(question_hash=question_hash).first()
    
    def find_duplicate_by_text_similarity(self, partial_text, threshold=0.85):
        """
        基于文字相似度查找重复题目（用于前端OCR不完整的情况）
        
        Args:
            partial_text: 部分文字（前端OCR结果）
            threshold: 相似度阈值（0-1），默认0.85
            
        Returns:
            tuple: (Question对象, 相似度分数) 或 (None, 0.0)
        """
        if not partial_text or len(partial_text.strip()) < 10:
            return None, 0.0
        
        # 标准化输入文本
        normalized_input = self._normalize_text(partial_text)
        
        # 获取所有题目的raw_text（优化：限制查询数量，避免查询过多数据）
        # 只查询最近1000条，提高查询速度
        questions = Question.query.filter(
            Question.raw_text.isnot(None),
            Question.raw_text != ''
        ).order_by(Question.created_at.desc()).limit(1000).all()
        
        best_match = None
        best_similarity = 0.0
        
        for question in questions:
            if not question.raw_text:
                continue
            
            # 标准化题目文本
            normalized_question = self._normalize_text(question.raw_text)
            
            # 计算相似度（使用SequenceMatcher）
            similarity = SequenceMatcher(None, normalized_input, normalized_question).ratio()
            
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = question
            
            # 如果找到高相似度匹配，提前返回
            if similarity >= threshold:
                logger.info(f"[QuestionService] 文字相似度匹配: {similarity:.3f} >= {threshold}")
                return question, similarity
        
        if best_similarity >= threshold:
            logger.info(f"[QuestionService] 文字相似度匹配: {best_similarity:.3f} >= {threshold}")
            return best_match, best_similarity
        
        return None, 0.0
    
    def find_duplicate_by_image_hash(self, image_file):
        """
        基于图片哈希查找重复题目
        
        注意：当前实现简化，主要依赖文字相似度和完整题干哈希
        图片哈希检查可以后续扩展（需要添加image_hash字段到数据库）
        
        Args:
            image_file: 图片文件对象
            
        Returns:
            Question对象或None
        """
        # TODO: 实现图片哈希检查
        # 需要：
        # 1. 在Question模型中添加image_hash字段（MD5）
        # 2. 在Question模型中添加image_phash字段（感知哈希）
        # 3. 保存题目时计算并存储这些哈希值
        # 4. 在这里查询匹配的题目
        
        # 当前简化实现：返回None，依赖其他检查方法
        return None
    
    def _normalize_text(self, text):
        """
        标准化文本（用于相似度比较）
        
        Args:
            text: 原始文本
            
        Returns:
            str: 标准化后的文本
        """
        if not text:
            return ""
        
        # 去除空格、换行、标点符号
        normalized = text.strip().replace('\n', '').replace('\r', '').replace(' ', '')
        # 只保留中文字符、数字、字母
        normalized = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '', normalized)
        return normalized.lower()
    
    def save_image(self, image_file, upload_folder='uploads'):
        """
        保存图片文件
        优先使用Supabase Storage，如果不可用则保存到本地
        
        Args:
            image_file: 上传的文件对象
            upload_folder: 本地上传目录（Supabase不可用时使用）
            
        Returns:
            str: 图片路径或URL
                - 如果使用Supabase: 返回公开URL
                - 如果使用本地: 返回相对路径（如 /uploads/2025/12/04/q1234.png）
        """
        # 优先尝试使用Supabase Storage
        from supabase_storage_service import get_supabase_storage_service
        storage_service = get_supabase_storage_service()
        
        if storage_service.is_available():
            logger.info("[QuestionService] 使用Supabase Storage上传图片...")
            success, file_path, public_url = storage_service.upload_image(image_file)
            
            if success and public_url:
                logger.info(f"[QuestionService] ✅ 图片已上传到Supabase: {public_url}")
                return public_url
            else:
                logger.warning("[QuestionService] Supabase上传失败，降级到本地存储")
        
        # 降级到本地存储
        logger.info("[QuestionService] 使用本地存储保存图片...")
        # 创建日期目录
        today = datetime.now()
        date_folder = os.path.join(upload_folder, str(today.year), f"{today.month:02d}", f"{today.day:02d}")
        os.makedirs(date_folder, exist_ok=True)
        
        # 获取文件名和扩展名（兼容BytesIO对象）
        image_file.seek(0)  # 重置文件指针
        image_data = image_file.read()
        image_file.seek(0)  # 再次重置，供后续使用
        
        # 尝试从filename或name属性获取扩展名
        filename_for_ext = None
        if hasattr(image_file, 'filename') and image_file.filename:
            filename_for_ext = image_file.filename
        elif hasattr(image_file, 'name') and image_file.name:
            filename_for_ext = image_file.name
        
        # 从文件名或文件内容检测扩展名
        if filename_for_ext:
            ext = os.path.splitext(filename_for_ext)[1]
        else:
            ext = None
        
        # 如果无法从文件名获取，从文件内容检测
        if not ext:
            if image_data[:2] == b'\xff\xd8':
                ext = '.jpg'
            elif image_data[:8] == b'\x89PNG\r\n\x1a\n':
                ext = '.png'
            elif image_data[:6] in (b'GIF87a', b'GIF89a'):
                ext = '.gif'
            elif image_data[:2] == b'BM':
                ext = '.bmp'
            else:
                ext = '.png'  # 默认使用PNG
        
        # 生成唯一文件名
        filename = f"q{uuid.uuid4().hex[:8]}{ext}"
        filepath = os.path.join(date_folder, filename)
        
        # 保存文件（兼容BytesIO和FileStorage对象）
        image_file.seek(0)  # 重置文件指针
        if hasattr(image_file, 'save'):
            # Flask FileStorage对象，使用save方法
            image_file.save(filepath)
        else:
            # BytesIO对象或其他，使用文件写入
            with open(filepath, 'wb') as f:
                f.write(image_data)
        
        # 返回相对路径（用于URL）
        return f"/{filepath.replace(os.sep, '/')}"
    
    def image_to_base64(self, image_file, return_format='data_uri'):
        """
        将图片文件转换为base64编码
        
        Args:
            image_file: 文件对象
            return_format: 返回格式
                - 'data_uri': 返回完整的数据URI (data:image/jpeg;base64,xxx)
                - 'base64_only': 只返回base64字符串（不含前缀）
            
        Returns:
            str: base64编码的图片数据
        """
        image_file.seek(0)  # 确保从文件开头读取
        image_data = image_file.read()
        base64_data = base64.b64encode(image_data).decode('utf-8')
        
        if return_format == 'base64_only':
            return base64_data
        
        # 检测图片格式
        if image_data[:2] == b'\xff\xd8':
            mime_type = 'image/jpeg'
        elif image_data[:8] == b'\x89PNG\r\n\x1a\n':
            mime_type = 'image/png'
        else:
            mime_type = 'image/jpeg'  # 默认
        
        return f"data:{mime_type};base64,{base64_data}"
    
    def _get_cache_key(self, question_hash=None, raw_text=None, question_text=None):
        """
        生成缓存键
        
        Args:
            question_hash: 题目哈希值
            raw_text: 原始文本
            question_text: 题干文本
            
        Returns:
            str: 缓存键
        """
        if question_hash:
            return f"hash:{question_hash}"
        elif question_text:
            normalized = self._normalize_text(question_text)
            return f"text:{hashlib.md5(normalized.encode('utf-8')).hexdigest()}"
        elif raw_text:
            normalized = self._normalize_text(raw_text)
            return f"raw:{hashlib.md5(normalized.encode('utf-8')).hexdigest()}"
        return None
    
    def _get_from_cache(self, cache_key):
        """
        从缓存获取数据
        
        Args:
            cache_key: 缓存键
            
        Returns:
            dict或None
        """
        if cache_key and cache_key in self._cache:
            logger.info(f"[QuestionService] 💾 从缓存获取: {cache_key}")
            return self._cache[cache_key]
        return None
    
    def _set_to_cache(self, cache_key, data):
        """
        存入缓存
        
        Args:
            cache_key: 缓存键
            data: 数据
        """
        if not cache_key:
            return
        
        # LRU策略：如果缓存已满，删除最旧的
        if len(self._cache) >= self._cache_max_size:
            # 删除第一个（最旧的）
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
            logger.debug(f"[QuestionService] 🗑️ 缓存已满，删除最旧项: {oldest_key}")
        
        self._cache[cache_key] = data
        logger.info(f"[QuestionService] 💾 存入缓存: {cache_key}")
    
    def analyze_question_from_image(self, image_file, frontend_raw_text=None,
                                     frontend_question_text=None, frontend_options=None,
                                     question_type='TEXT', force_reanalyze=False):
        """
        从图片分析题目（优化版本）
        
        流程：
        1. 利用前端提供的数据计算哈希，检查缓存和数据库
        2. 如果找到重复题且不强制重新分析，返回缓存（不调用AI）
        3. 否则调用AI分析，存入数据库和缓存
        
        Args:
            image_file: 图片文件
            frontend_raw_text: 前端OCR原始文本（可选）
            frontend_question_text: 前端提取的题干（可选，可能不准确）
            frontend_options: 前端提取的选项（可选，列表）
            question_type: 题目类型（默认"TEXT"）
            force_reanalyze: 是否强制重新AI分析（默认False）
            
        Returns:
            dict: 完整的题目数据，包含：
            - from_cache: 是否来自缓存
            - is_duplicate: 是否是重复题
            - saved_to_db: 是否存入数据库
            - similarity_score: 相似度分数
        """
        logger.info("")
        logger.info("[QuestionService] ========== 开始从图片分析题目 ==========")
        
        if frontend_raw_text:
            logger.info(f"[QuestionService] 📝 收到前端OCR原始文本: {frontend_raw_text[:100]}...")
        if frontend_question_text:
            logger.info(f"[QuestionService] 📝 收到前端提取题干: {frontend_question_text[:100]}...")
        if frontend_options:
            logger.info(f"[QuestionService] 📝 收到前端提取选项: {len(frontend_options)}个")
        
        if force_reanalyze:
            logger.info("[QuestionService] 🔄 强制重新AI分析（用户要求）")
        
        # ========== 第一步：利用前端数据快速去重检查 ==========
        existing_question = None
        similarity_score = 0.0
        cache_key = None
        
        # 1.1 如果前端提供了题干和选项，计算哈希并检查缓存/数据库
        if frontend_question_text and frontend_options and not force_reanalyze:
            logger.info("[QuestionService] 🔍 第一步：利用前端数据检查...")
            
            # 计算题目哈希
            question_hash = self.calculate_question_hash(frontend_question_text, frontend_options)
            logger.info(f"[QuestionService]    - 题目哈希值: {question_hash}")
            
            # 生成缓存键
            cache_key = self._get_cache_key(question_hash=question_hash)
            
            # 先检查内存缓存
            cached_data = self._get_from_cache(cache_key)
            if cached_data:
                logger.info(f"[QuestionService] ✅ 从缓存获取数据")
                cached_data['from_cache'] = True
                cached_data['saved_to_db'] = False
                return cached_data
            
            # 检查数据库（完整题干哈希匹配）
            existing_question = self.find_duplicate_question(question_hash)
            if existing_question:
                logger.info(f"[QuestionService] ✅ 数据库中找到重复题目（完整题干匹配）")
                logger.info(f"[QuestionService]    - 题目ID: {existing_question.id}")
                similarity_score = 1.0  # 完全匹配
        
        # 1.2 如果前端只提供了原始文本，使用文字相似度检查
        elif frontend_raw_text and not force_reanalyze:
            logger.info("[QuestionService] 🔍 第一步：文字相似度检查...")
            existing_question, similarity_score = self.find_duplicate_by_text_similarity(
                frontend_raw_text,
                threshold=0.85
            )
            if existing_question:
                logger.info(f"[QuestionService] ✅ 文字相似度匹配成功: {similarity_score:.3f}")
                logger.info(f"[QuestionService]    - 题目ID: {existing_question.id}")
                # 生成缓存键
                cache_key = self._get_cache_key(raw_text=frontend_raw_text)
        
        # ========== 第二步：如果找到重复题且不强制重新分析，返回缓存 ==========
        if existing_question and not force_reanalyze:
            logger.info(f"[QuestionService] ✅ 找到重复题目，返回缓存结果（不调用OCR）")
            response = self._format_question_content_response(existing_question)
            response['from_cache'] = True
            response['is_duplicate'] = True
            response['saved_to_db'] = False  # 来自数据库，不是新存入
            response['similarity_score'] = similarity_score if similarity_score > 0 else 1.0
            response['matched_question_id'] = str(existing_question.id)  # 匹配的题目ID
            
            # 存入内存缓存（如果还没有）
            if cache_key:
                self._set_to_cache(cache_key, response)
            
            return response
        
        # ========== 第三步：调用AI分析（新题或强制重新分析）==========
        logger.info("[QuestionService] 🤖 调用AI分析图片（提取题干、选项、解析等）...")
        
        # 3.1 保存图片
        logger.info("[QuestionService] 💾 保存图片...")
        image_file.seek(0)
        screenshot_path = self.save_image(image_file)
        logger.info(f"[QuestionService]    - 图片路径: {screenshot_path}")
        
        # 3.2 提取题目内容（支持多种方案）
        image_file.seek(0)
        # 根据环境变量选择方案（用于测试对比）
        ocr_method = os.getenv('OCR_METHOD', 'auto')  # auto, vision, ocr_ai, ocr_rule
        
        if ocr_method == 'vision':
            # 强制使用Vision模型
            ocr_result = self._extract_question_content_with_volcengine(image_file, screenshot_path, force_vision=True)
        elif ocr_method == 'ocr_ai':
            # 强制使用OCR API + 文本AI
            ocr_result = self._extract_question_content_with_volcengine(image_file, screenshot_path, force_ocr_ai=True)
        elif ocr_method == 'ocr_rule':
            # 强制使用OCR API + 规则过滤
            ocr_result = self._extract_question_content_fast(image_file, screenshot_path)
        else:
            # 自动选择（当前默认：Vision模型）
            ocr_result = self._extract_question_content_with_volcengine(image_file, screenshot_path)
        
        # 3.4 从OCR结果中提取信息（OCR的结果优先于前端数据）
        question_text = ocr_result.get('question_text', '') or frontend_question_text or ''
        options_list = ocr_result.get('options', []) or frontend_options or []
        ai_question_type = ocr_result.get('question_type', question_type)
        raw_text = ocr_result.get('raw_text', '') or frontend_raw_text or ''
        ocr_confidence = ocr_result.get('ocr_confidence', 0.95)
        extraction_method = ocr_result.get('extraction_method', 'volcengine_vision')  # 提取方法
        
        logger.info(f"[QuestionService]    - AI提取的题干: {question_text[:100]}...")
        logger.info(f"[QuestionService]    - AI提取的选项数: {len(options_list)}")
        logger.info(f"[QuestionService]    - AI判断的题目类型: {ai_question_type}")
        
        # 3.5 计算题目哈希值（用于去重）
        question_hash = self.calculate_question_hash(question_text, options_list)
        logger.info(f"[QuestionService] 🔑 题目哈希值: {question_hash}")
        
        # 3.6 再次检查数据库（AI提取后可能更准确）
        if not force_reanalyze:
            logger.info("[QuestionService] 🔍 再次检查数据库（AI提取后）...")
            existing_question = self.find_duplicate_question(question_hash)
            if existing_question:
                # 检查已有题目是否有有效的解析（不是失败记录）
                has_valid_answer = (
                    existing_question.correct_answer and 
                    existing_question.explanation and 
                    not existing_question.explanation.startswith('AI解析失败')
                )
                
                logger.info(f"[QuestionService] ✅ 找到重复题目（OCR提取后匹配），返回数据库结果")
                logger.info(f"[QuestionService]    - 题目ID: {existing_question.id}")
                response = self._format_question_content_response(existing_question)
                response['from_cache'] = False  # 来自数据库，不是缓存
                response['is_duplicate'] = True
                response['saved_to_db'] = False  # 不是新存入
                response['similarity_score'] = 1.0  # 完全匹配
                response['matched_question_id'] = str(existing_question.id)  # 匹配的题目ID
                
                # 存入内存缓存
                cache_key = self._get_cache_key(question_hash=question_hash)
                if cache_key:
                    self._set_to_cache(cache_key, response)
                
                return response
        
        # 3.7 如果force_reanalyze=true且之前找到了重复题，更新已有题目（只更新题目内容）
        if force_reanalyze and existing_question:
            logger.info(f"[QuestionService] 🔄 强制重新分析，更新已有题目内容: {existing_question.id}")
            
            # 只更新题目内容，不更新答案和解析（答案和解析由detail接口提供）
            existing_question.screenshot = screenshot_path
            existing_question.raw_text = raw_text
            existing_question.question_text = question_text
            existing_question.question_type = ai_question_type
            existing_question.options = options_list
            existing_question.question_hash = question_hash
            existing_question.ocr_confidence = ocr_confidence
            existing_question.updated_at = datetime.utcnow()
            
            db.session.commit()
            logger.info(f"[QuestionService] ✅ 题目内容已更新到数据库")
            logger.info(f"[QuestionService]    - 题目ID: {existing_question.id}")
            
            # 格式化响应（只返回题目内容）
            response = self._format_question_content_response(existing_question)
            response['from_cache'] = False
            response['is_duplicate'] = True
            response['saved_to_db'] = True  # 更新了数据库
            response['similarity_score'] = similarity_score if similarity_score > 0 else 1.0
            response['matched_question_id'] = str(existing_question.id)
            
            # 更新缓存
            cache_key = self._get_cache_key(question_hash=question_hash)
            if cache_key:
                self._set_to_cache(cache_key, response)
            
            return response
        
        # ========== 第四步：新题目，存入数据库 ==========
        logger.info("[QuestionService] ✨ 新题目，保存到数据库")
        
        # 4.1 创建题目记录（只保存题目内容，不保存答案和解析）
        question = Question(
            screenshot=screenshot_path,
            raw_text=raw_text,
            question_text=question_text,
            question_type=ai_question_type,  # 使用OCR判断的类型
            options=options_list,
            question_hash=question_hash,
            encountered_date=date.today(),
            ocr_confidence=ocr_confidence,
            tags=None,  # 不保存标签（由detail接口提供）
            knowledge_points=None,  # 不保存知识点（由detail接口提供）
            difficulty=None,  # 不保存难度（由detail接口提供）
            priority='中',
            correct_answer=None,  # 不保存答案（由detail接口提供）
            explanation=None  # 不保存解析（由detail接口提供）
        )
        db.session.add(question)
        db.session.flush()  # 获取question.id
        
        # 注意：不创建答案版本，答案和解析由detail接口提供
        
        db.session.commit()
        logger.info(f"[QuestionService] ✅ 题目内容已保存到数据库")
        logger.info(f"[QuestionService]    - 题目ID: {question.id}")
        logger.info("[QuestionService] ======================================")
        logger.info("")
        
        # 格式化响应（只返回题目内容，不返回答案和解析）
        response = self._format_question_content_response(question)
        response['from_cache'] = False
        response['is_duplicate'] = False
        response['saved_to_db'] = True  # 新存入数据库
        response['similarity_score'] = None
        response['matched_question_id'] = None  # 新题，没有匹配
        
        # 存入内存缓存
        cache_key = self._get_cache_key(question_hash=question_hash)
        if cache_key:
            self._set_to_cache(cache_key, response)
        
        return response
    
    def _extract_question_content_fast(self, image_file, image_path):
        """
        快速提取题目内容（混合方案）
        1. 先用快速OCR（PaddleOCR/Tesseract）识别文字（1-3秒）
        2. 用规则过滤提取题目内容（去除界面元素）
        3. 如果规则过滤失败或结果不完整，fallback到AI（火山引擎vision）
        
        Args:
            image_file: 图片文件对象
            image_path: 图片路径
            
        Returns:
            dict: OCR结果（包含题干、选项、raw_text等）
        """
        logger.info("[QuestionService]    - 使用快速OCR+规则过滤提取题目内容...")
        
        # 第一步：尝试快速OCR（PaddleOCR/Tesseract）
        try:
            from ocr_service import get_ocr_service
            ocr_service = get_ocr_service()
            
            if ocr_service.ocr_engine:
                logger.info("[QuestionService]    - 使用快速OCR识别文字...")
                
                # 保存临时文件用于OCR
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
                    image_file.seek(0)
                    tmp_file.write(image_file.read())
                    tmp_path = tmp_file.name
                
                try:
                    # 使用OCR提取文字
                    raw_text = ocr_service.extract_text(tmp_path)
                    
                    if raw_text and len(raw_text.strip()) > 10:  # 降低阈值，尝试更多情况
                        logger.info(f"[QuestionService]    - OCR识别成功，文字长度: {len(raw_text)}")
                        
                        # 第二步：使用规则过滤提取题目内容
                        from fast_ocr_extractor import get_fast_extractor
                        extractor = get_fast_extractor()
                        result = extractor.extract_question_from_text(raw_text)
                        
                        # 第三步：评估结果，决定是否使用AI（降低阈值，提高快速OCR使用率）
                        if result['is_complete'] and result['confidence'] >= 0.5:  # 降低置信度阈值
                            logger.info(f"[QuestionService]    - ✅ 规则过滤成功，置信度: {result['confidence']:.2f}")
                            logger.info(f"[QuestionService]    - 题干: {result['question_text'][:50]}...")
                            logger.info(f"[QuestionService]    - 选项数: {len(result['options'])}")
                            
                            # 格式化返回结果
                            return {
                                'question_text': result['question_text'],
                                'options': result['options'],
                                'raw_text': result['raw_text'],
                                'question_type': 'TEXT',  # 默认文字题
                                'ocr_confidence': result['confidence'],
                                'extraction_method': 'fast_ocr_rule'
                            }
                        else:
                            logger.info(f"[QuestionService]    - ⚠️ 规则过滤结果不完整，置信度: {result['confidence']:.2f}")
                            logger.info(f"[QuestionService]    - Fallback到AI提取...")
                    else:
                        logger.info("[QuestionService]    - OCR识别文字太少，Fallback到AI提取...")
                finally:
                    # 清理临时文件
                    try:
                        import os
                        os.unlink(tmp_path)
                    except:
                        pass
            else:
                logger.info("[QuestionService]    - 快速OCR不可用，直接使用AI提取...")
        except Exception as e:
            logger.warning(f"[QuestionService]    - 快速OCR失败: {e}，Fallback到AI提取...")
        
        # Fallback：使用AI提取（火山引擎vision）
        logger.info("[QuestionService]    - 使用AI（火山引擎vision）提取题目内容...")
        image_file.seek(0)
        return self._extract_question_content_with_volcengine(image_file, image_path)
    
    def _extract_question_content_with_volcengine(self, image_file, image_path):
        """
        使用火山引擎OCR提取题目内容（只提取题干和选项，不分析答案）
        
        Args:
            image_file: 图片文件对象
            image_path: 图片路径
            
        Returns:
            dict: OCR结果（包含题干、选项、raw_text等，不包含答案和解析）
        """
        # 构建提示词，只提取题目内容（题干和选项），不分析答案
        # 明确要求返回JSON格式，不返回其他内容
        prompt = """请从图片中提取题目内容，只返回JSON格式，不要返回其他文字说明。

要求：
1. 提取完整的题干内容
2. 提取所有选项（A、B、C、D等）
3. 只返回JSON格式，格式如下：

{
    "question_text": "完整的题干内容",
    "options": ["A. 选项A内容", "B. 选项B内容", "C. 选项C内容", "D. 选项D内容"],
    "raw_text": "图片中的原始文字内容"
}

注意：只返回JSON，不要有其他文字说明。"""
        
        try:
            logger.info("[QuestionService]    - 使用火山引擎OCR提取题目内容...")
            
            from volcengine_ocr_service import VolcengineOCRService
            volcengine_ocr = VolcengineOCRService()
            
            if not volcengine_ocr.is_available:
                raise Exception("火山引擎OCR服务不可用")
            
            # 获取图片路径
            local_image_path = None
            if image_path and os.path.exists(image_path):
                local_image_path = image_path
            elif image_file:
                # 保存临时文件用于OCR
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
                    image_file.seek(0)
                    tmp_file.write(image_file.read())
                    local_image_path = tmp_file.name
            
            if not local_image_path:
                raise Exception("无法获取图片路径")
            
            logger.info(f"[QuestionService]    - 使用火山引擎OCR分析图片: {local_image_path}")
            
            # 调用火山引擎vision模型
            image_data = volcengine_ocr._read_image(local_image_path)
            if not image_data:
                raise Exception("无法读取图片数据")
            
            vision_result = volcengine_ocr._call_vision_model(image_data, prompt)
            if not vision_result:
                raise Exception("火山引擎vision模型调用失败")
            
            # 解析vision模型的返回结果
            content = ''
            if 'output' in vision_result:
                output_data = vision_result['output']
                if isinstance(output_data, list) and len(output_data) > 0:
                    # 找到最后一个type='message'的项
                    for item in reversed(output_data):
                        if isinstance(item, dict) and item.get('type') == 'message':
                            content_list = item.get('content', [])
                            if isinstance(content_list, list):
                                for content_item in content_list:
                                    if isinstance(content_item, dict) and content_item.get('type') == 'output_text':
                                        content = content_item.get('text', '')
                                        break
                            if content:
                                break
                    if not content:
                        last_item = output_data[-1]
                        if isinstance(last_item, str):
                            content = last_item
                        elif isinstance(last_item, dict):
                            content = last_item.get('text', '') or last_item.get('content', '')
            
            if not content:
                raise Exception("无法从vision模型响应中提取内容")
            
            # 记录原始内容（用于调试）
            logger.debug(f"[QuestionService] vision模型返回内容预览: {content[:200]}...")
            
            # 解析JSON（增强：支持多行JSON和嵌套JSON）
            import re
            parsed = None
            
            # 尝试1: 直接查找JSON块（最外层的大括号）
            json_patterns = [
                r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',  # 简单嵌套JSON
                r'\{[\s\S]*?\}',  # 非贪婪匹配
                r'\{.*\}',  # 贪婪匹配（最后尝试）
            ]
            
            for pattern in json_patterns:
                json_match = re.search(pattern, content, re.DOTALL)
                if json_match:
                    try:
                        parsed = json.loads(json_match.group())
                        logger.info(f"[QuestionService] ✅ 成功解析JSON（使用模式: {pattern[:30]}...）")
                        break
                    except json.JSONDecodeError as e:
                        logger.debug(f"[QuestionService] JSON解析失败（模式: {pattern[:30]}）: {e}")
                        continue
            
            # 尝试2: 如果还是找不到，尝试从reasoning中提取（降级处理）
            if not parsed and 'output' in vision_result:
                output_data = vision_result['output']
                # 查找reasoning中的summary_text
                for item in output_data:
                    if isinstance(item, dict) and item.get('type') == 'reasoning':
                        summary_list = item.get('summary', [])
                        if summary_list:
                            for summary_item in summary_list:
                                if isinstance(summary_item, dict) and summary_item.get('type') == 'summary_text':
                                    reasoning_text = summary_item.get('text', '')
                                    # 尝试从推理文本中提取JSON
                                    for pattern in json_patterns:
                                        json_match = re.search(pattern, reasoning_text, re.DOTALL)
                                        if json_match:
                                            try:
                                                parsed = json.loads(json_match.group())
                                                logger.info(f"[QuestionService] ✅ 从reasoning中成功解析JSON")
                                                break
                                            except json.JSONDecodeError:
                                                continue
                                    if parsed:
                                        break
                        if parsed:
                            break
            
            # 尝试3: 如果还是找不到JSON，尝试从文本中提取题目信息（降级处理）
            if not parsed:
                logger.warning(f"[QuestionService] ⚠️ 无法找到JSON格式，尝试从文本中提取题目信息...")
                # 使用正则表达式从文本中提取题干和选项
                question_text_match = re.search(r'(?:题干|题目|问题)[:：]?\s*(.+?)(?:\n|选项|$)', content, re.DOTALL)
                question_text = question_text_match.group(1).strip() if question_text_match else ''
                
                # 提取选项
                options = []
                option_patterns = [
                    r'([A-Z])[\.、。:\s\uFF0E]+\s*([^A-Z\n]+?)(?=\n|$|[A-Z][\.、。:\s\uFF0E])',
                    r'选项([A-Z])[:：]?\s*([^\n]+)',
                ]
                for pattern in option_patterns:
                    matches = re.findall(pattern, content)
                    if matches:
                        for match in matches:
                            if isinstance(match, tuple) and len(match) >= 2:
                                letter = match[0]
                                opt_text = match[1].strip()
                                if opt_text:
                                    options.append(f"{letter}. {opt_text}")
                        if options:
                            break
                
                if question_text or options:
                    parsed = {
                        'question_text': question_text or '无法提取题干',
                        'options': options or [],
                        'raw_text': content
                    }
                    logger.info(f"[QuestionService] ⚠️ 使用降级方案提取题目信息（题干: {len(question_text)}字符, 选项数: {len(options)}）")
            
            if not parsed:
                # 记录详细的错误信息
                logger.error(f"[QuestionService] ❌ 无法解析vision模型返回内容")
                logger.error(f"[QuestionService] 返回内容预览（前500字符）: {content[:500]}")
                logger.error(f"[QuestionService] 返回内容长度: {len(content)}字符")
                
                # 尝试从reasoning中提取原始OCR文本作为raw_text
                raw_text_fallback = ''
                if 'output' in vision_result:
                    output_data = vision_result['output']
                    for item in output_data:
                        if isinstance(item, dict) and item.get('type') == 'reasoning':
                            summary_list = item.get('summary', [])
                            if summary_list:
                                for summary_item in summary_list:
                                    if isinstance(summary_item, dict) and summary_item.get('type') == 'summary_text':
                                        raw_text_fallback = summary_item.get('text', '')[:1000]  # 取前1000字符
                                        break
                
                raise Exception(f"vision模型返回的不是有效JSON格式。返回内容类型: {type(content).__name__}, 内容长度: {len(content)}字符。建议：使用本地OCR+DeepSeek方案（/api/questions/extract/batch接口）")
            
            # 格式化选项
            options = parsed.get('options', [])
            formatted_options = []
            for i, opt in enumerate(options):
                opt_str = str(opt).strip()
                # 处理重复前缀
                match = re.match(r'^([A-Z])[\.、。:\s\uFF0E]+([A-Z])[\.、。:\s\uFF0E]+(.+)', opt_str)
                if match:
                    letter = match.group(2)
                    content_part = match.group(3).strip()
                    formatted_options.append(f"{letter}. {content_part}")
                else:
                    match = re.match(r'^([A-Z])[\.、。:\s\uFF0E]+(.+)', opt_str)
                    if match:
                        letter = match.group(1)
                        content_part = match.group(2).strip()
                        content_match = re.match(r'^([A-Z])[\.、。:\s\uFF0E]+(.+)', content_part)
                        if content_match:
                            letter = content_match.group(1)
                            content_part = content_match.group(2).strip()
                        formatted_options.append(f"{letter}. {content_part}")
                    else:
                        option_label = chr(65 + i)
                        formatted_options.append(f"{option_label}. {opt_str}")
            
            # 返回OCR结果（只包含题目内容，不包含答案和解析）
            result = {
                'raw_text': parsed.get('raw_text', content),
                'question_text': parsed.get('question_text', ''),
                'options': formatted_options,
                'question_type': parsed.get('question_type', 'TEXT'),
                'ocr_confidence': 0.95,  # 火山引擎OCR置信度
                'extraction_method': 'volcengine_vision'  # 标记使用AI OCR
            }
            
            logger.info(f"[QuestionService]    - ✅ 火山引擎OCR识别成功！")
            logger.info(f"[QuestionService]    - 题干: {result.get('question_text', '')[:100]}...")
            logger.info(f"[QuestionService]    - 选项数: {len(result.get('options', []))}")
            
            # 清理临时文件
            if image_file and local_image_path != image_path:
                try:
                    os.unlink(local_image_path)
                except:
                    pass
            
            return result
            
        except ImportError:
            logger.error("[QuestionService]    - ❌ 火山引擎OCR服务不可用")
            raise Exception("火山引擎OCR服务不可用，请检查配置")
        except Exception as e:
            logger.error(f"[QuestionService]    - ❌ 火山引擎OCR失败: {e}")
            raise Exception(f"火山引擎OCR失败: {e}")
    
    def _format_question_response(self, question):
        """
        格式化题目响应数据
        
        Args:
            question: Question对象
            
        Returns:
            dict: 格式化的响应数据
        """
        # 获取所有答案版本
        answer_versions_data = []
        for ans in question.answer_versions:
            answer_versions_data.append({
                'id': str(ans.id),
                'source_name': ans.source_name,
                'source_type': ans.source_type,
                'answer': ans.answer,
                'explanation': ans.explanation,
                'confidence': ans.confidence,
                'is_user_preferred': ans.is_user_preferred,
                'created_at': ans.created_at.strftime('%Y-%m-%d') if ans.created_at else None,
                'updated_at': ans.updated_at.strftime('%Y-%m-%d') if ans.updated_at else None
            })
        
        # 如果没有答案版本，创建一个默认的
        if not answer_versions_data:
            answer_versions_data.append({
                'id': f'ans_{question.id}',
                'source_name': 'AI',
                'source_type': 'AI',
                'answer': question.correct_answer or '',
                'explanation': question.explanation or '',
                'confidence': 0.7,
                'is_user_preferred': True,
                'created_at': question.created_at.strftime('%Y-%m-%d') if question.created_at else None,
                'updated_at': question.updated_at.strftime('%Y-%m-%d') if question.updated_at else None
            })
        
        # 格式化日期
        created_at_str = question.created_at.strftime('%Y-%m-%d') if question.created_at else None
        updated_at_str = question.updated_at.strftime('%Y-%m-%d') if question.updated_at else None
        encountered_date_str = question.encountered_date.strftime('%Y-%m-%d') if question.encountered_date else None
        
        return {
            'id': str(question.id),
            'screenshot': question.screenshot,
            'raw_text': question.raw_text,
            'question_text': question.question_text,  # 添加完整题干字段
            'question_type': question.question_type,
            'options': question.options if isinstance(question.options, list) else json.loads(question.options) if isinstance(question.options, str) else [],
            'answer_versions': answer_versions_data,
            'correct_answer': question.correct_answer,
            'explanation': question.explanation,
            'tags': question.tags if isinstance(question.tags, list) else json.loads(question.tags) if isinstance(question.tags, str) else [],
            'knowledge_points': question.knowledge_points if isinstance(question.knowledge_points, list) else json.loads(question.knowledge_points) if isinstance(question.knowledge_points, str) else [],
            'source': question.source,
            'source_url': question.source_url,
            'encountered_date': encountered_date_str,
            'difficulty': question.difficulty,
            'priority': question.priority,
            'ocr_confidence': question.ocr_confidence,
            'similar_questions': question.similar_questions if isinstance(question.similar_questions, list) else json.loads(question.similar_questions) if isinstance(question.similar_questions, str) else [],
            'created_at': created_at_str,
            'updated_at': updated_at_str
        }
    
    def _format_question_content_response(self, question):
        """
        格式化题目内容响应数据（只返回题目内容，不返回答案和解析）
        用于 /api/questions/analyze 接口
        
        Args:
            question: Question对象
            
        Returns:
            dict: 格式化的响应数据（只包含题目内容）
        """
        result = {
            'id': str(question.id),
            'screenshot': question.screenshot,
            'raw_text': question.raw_text or '',
            'question_text': question.question_text or '',
            'question_type': question.question_type or 'TEXT',
            'options': question.options if isinstance(question.options, list) else json.loads(question.options) if isinstance(question.options, str) else [],
            'ocr_confidence': question.ocr_confidence,
            'matched_question_id': None,  # 默认新题没有匹配ID，重复题会在逻辑中设置
            'extraction_method': 'volcengine_vision'  # 默认值，会在调用处覆盖
        }
        return result
    
    def analyze_question_detail(self, question_id):
        """
        分析题目详情（答案、解析、标签等）
        使用DeepSeek进行详细分析
        
        Args:
            question_id: 题目ID
            
        Returns:
            dict: 包含答案、解析、标签等详细信息
        """
        logger.info("")
        logger.info(f"[QuestionService] ========== 开始分析题目详情: {question_id} ==========")
        
        # 从数据库获取题目
        question = Question.query.filter_by(id=question_id).first()
        if not question:
            raise Exception(f"题目不存在: {question_id}")
        
        logger.info(f"[QuestionService]    - 题目ID: {question_id}")
        logger.info(f"[QuestionService]    - 题干: {question.question_text[:100] if question.question_text else 'None'}...")
        
        # 检查是否已有答案版本
        existing_answers = AnswerVersion.query.filter_by(question_id=question_id).all()
        if existing_answers and len(existing_answers) > 0:
            # 检查是否有有效的AI答案
            has_valid_ai_answer = any(
                ans.source_type == 'AI' and 
                ans.answer and 
                ans.explanation and 
                not ans.explanation.startswith('AI解析失败')
                for ans in existing_answers
            )
            
            if has_valid_ai_answer:
                logger.info(f"[QuestionService] ✅ 题目已有答案，返回已有数据")
                return self._format_question_detail_response(question)
        
        # 使用DeepSeek进行详细分析
        logger.info("[QuestionService] 🤖 调用DeepSeek进行详细分析...")
        
        # 构建题目文本
        question_text = question.question_text or ''
        options_text = ''
        if question.options:
            if isinstance(question.options, list):
                options_text = '\n'.join(question.options)
            elif isinstance(question.options, str):
                try:
                    options_list = json.loads(question.options)
                    options_text = '\n'.join(options_list)
                except:
                    options_text = question.options
        
        full_question_text = f"{question_text}\n\n选项:\n{options_text}"
        
        # 调用DeepSeek分析（优化：精简prompt，减少token数量，加快响应速度）
        analysis_prompt = f"""分析题目，给出答案和解析。

题目：
{full_question_text}

标签：行测(言语:语句衔接/排序/逻辑填空/阅读理解;数量:算数/比例/工程/概率/排列;判断:逻辑/图形/定义;资料:表格/图形/速算;常识:政治/经济/历史地理科技法律) 申论(题材:生态/城市/教育/医疗/乡村/经济;能力:材料解读/提炼/对策/论证/公文;风格:简明/数据/政策;评分:观点/逻辑/方案/语言;错因:论点/对策/表述)

返回JSON：
{{
    "correct_answer": "B",
    "explanation": "详细解析",
    "tags": ["行测-数量关系-比例与比率"],
    "knowledge_points": ["比率与比例"],
    "difficulty": 3,
    "answer_versions": [{{"source_name": "AI", "source_type": "AI", "answer": "B", "explanation": "解析", "confidence": 0.8}}]
}}"""
        
        try:
            response = self.ai_service.client.chat.completions.create(
                model=self.ai_service.default_model,
                messages=[
                    {
                        "role": "user",
                        "content": analysis_prompt
                    }
                ],
                temperature=0.7,
                max_tokens=2000  # 优化：减少max_tokens，加快响应速度（从3000降到2000）
            )
            ai_response = response.choices[0].message.content
            
            # 解析JSON
            import re
            json_match = re.search(r'\{[\s\S]*\}', ai_response, re.DOTALL)
            if json_match:
                analysis_dict = json.loads(json_match.group(0))
            else:
                raise Exception("AI返回的不是有效JSON格式")
            
            # 更新题目信息
            question.correct_answer = analysis_dict.get('correct_answer')
            question.explanation = analysis_dict.get('explanation')
            question.tags = analysis_dict.get('tags', [])
            question.knowledge_points = analysis_dict.get('knowledge_points', [])
            question.difficulty = analysis_dict.get('difficulty', 3)
            question.updated_at = datetime.utcnow()
            
            # 创建或更新答案版本
            answer_versions_data = analysis_dict.get('answer_versions', [])
            if not answer_versions_data:
                # 如果没有answer_versions，创建一个默认的
                answer_versions_data = [{
                    'source_name': 'AI',
                    'source_type': 'AI',
                    'answer': analysis_dict.get('correct_answer', ''),
                    'explanation': analysis_dict.get('explanation', ''),
                    'confidence': 0.8,
                    'is_user_preferred': False
                }]
            
            # 删除旧的AI答案版本
            AnswerVersion.query.filter_by(
                question_id=question_id,
                source_type='AI'
            ).delete()
            
            # 创建新的答案版本
            for ans_data in answer_versions_data:
                answer_version = AnswerVersion(
                    question_id=question.id,
                    source_name=ans_data.get('source_name', 'AI'),
                    source_type=ans_data.get('source_type', 'AI'),
                    answer=ans_data.get('answer'),
                    explanation=ans_data.get('explanation'),
                    confidence=ans_data.get('confidence', 0.8),
                    is_user_preferred=ans_data.get('is_user_preferred', False)
                )
                db.session.add(answer_version)
            
            db.session.commit()
            logger.info(f"[QuestionService] ✅ 题目详情已保存到数据库")
            logger.info(f"[QuestionService]    - 正确答案: {question.correct_answer}")
            logger.info(f"[QuestionService]    - 答案版本数: {len(answer_versions_data)}")
            logger.info("[QuestionService] ======================================")
            logger.info("")
            
            return self._format_question_detail_response(question)
            
        except Exception as e:
            logger.error(f"[QuestionService] ❌ DeepSeek分析失败: {e}")
            raise Exception(f"DeepSeek分析失败: {e}")
    
    def _format_question_detail_response(self, question):
        """
        格式化题目详情响应数据（包含答案、解析、标签等）
        用于 /api/questions/{question_id}/detail 接口
        
        Args:
            question: Question对象
            
        Returns:
            dict: 格式化的响应数据（包含完整详情）
        """
        # 获取所有答案版本
        answer_versions_data = []
        for ans in question.answer_versions:
            answer_versions_data.append({
                'id': str(ans.id),
                'source_name': ans.source_name,
                'source_type': ans.source_type,
                'answer': ans.answer,
                'explanation': ans.explanation,
                'confidence': ans.confidence,
                'is_user_preferred': ans.is_user_preferred,
                'created_at': ans.created_at.strftime('%Y-%m-%d') if ans.created_at else None,
                'updated_at': ans.updated_at.strftime('%Y-%m-%d') if ans.updated_at else None
            })
        
        # 如果没有答案版本，创建一个默认的
        if not answer_versions_data:
            answer_versions_data.append({
                'id': f'ans_{question.id}',
                'source_name': 'AI',
                'source_type': 'AI',
                'answer': question.correct_answer or '',
                'explanation': question.explanation or '',
                'confidence': 0.7,
                'is_user_preferred': True,
                'created_at': question.created_at.strftime('%Y-%m-%d') if question.created_at else None,
                'updated_at': question.updated_at.strftime('%Y-%m-%d') if question.updated_at else None
            })
        
        # 格式化日期
        created_at_str = question.created_at.strftime('%Y-%m-%d') if question.created_at else None
        updated_at_str = question.updated_at.strftime('%Y-%m-%d') if question.updated_at else None
        encountered_date_str = question.encountered_date.strftime('%Y-%m-%d') if question.encountered_date else None
        
        return {
            'id': str(question.id),
            'question_id': str(question.id),
            'answer_versions': answer_versions_data,
            'correct_answer': question.correct_answer,
            'explanation': question.explanation,
            'tags': question.tags if isinstance(question.tags, list) else json.loads(question.tags) if isinstance(question.tags, str) else [],
            'knowledge_points': question.knowledge_points if isinstance(question.knowledge_points, list) else json.loads(question.knowledge_points) if isinstance(question.knowledge_points, str) else [],
            'source': question.source,
            'source_url': question.source_url,
            'similar_questions': question.similar_questions if isinstance(question.similar_questions, list) else json.loads(question.similar_questions) if isinstance(question.similar_questions, str) else [],
            'encountered_date': encountered_date_str,
            'difficulty': question.difficulty,
            'priority': question.priority,
            'created_at': created_at_str,
            'updated_at': updated_at_str
        }

