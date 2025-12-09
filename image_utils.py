"""
图片处理工具：用于图推题的识别和去重
结合Perceptual Hash和深度模型Embedding两种方法
"""
import hashlib
import requests
from io import BytesIO
from PIL import Image
import imagehash
import numpy as np
import logging

# 可选导入：如果embedding_service不可用，embedding功能将不可用
try:
    from embedding_service import get_embedding_service
    EMBEDDING_AVAILABLE = True
except ImportError:
    EMBEDDING_AVAILABLE = False
    get_embedding_service = None

# 配置日志
logger = logging.getLogger(__name__)


def calculate_image_hash(image_path_or_url):
    """
    计算图片的MD5哈希值（用于快速识别完全相同的图片）
    
    Args:
        image_path_or_url: 图片路径或URL
        
    Returns:
        str: MD5哈希值
    """
    if image_path_or_url.startswith('http://') or image_path_or_url.startswith('https://'):
        # 从URL下载图片
        response = requests.get(image_path_or_url)
        image_data = response.content
    elif image_path_or_url.startswith('file://'):
        # 处理file://协议
        file_path = image_path_or_url[7:]  # 移除file://前缀
        with open(file_path, 'rb') as f:
            image_data = f.read()
    else:
        # 从本地路径读取
        with open(image_path_or_url, 'rb') as f:
            image_data = f.read()
    
    return hashlib.md5(image_data).hexdigest()


def calculate_perceptual_hash(image_path_or_url):
    """
    计算图片的感知哈希值（用于识别相似图片，即使有轻微差异也能识别为同一题）
    
    Args:
        image_path_or_url: 图片路径或URL
        
    Returns:
        str: 感知哈希值（16进制字符串）
    """
    if image_path_or_url.startswith('http://') or image_path_or_url.startswith('https://'):
        # 从URL下载图片
        response = requests.get(image_path_or_url)
        image = Image.open(BytesIO(response.content))
    elif image_path_or_url.startswith('file://'):
        # 处理file://协议
        file_path = image_path_or_url[7:]  # 移除file://前缀
        image = Image.open(file_path)
    else:
        # 从本地路径读取
        image = Image.open(image_path_or_url)
    
    # 使用感知哈希算法（pHash）
    phash = imagehash.phash(image)
    return str(phash)


def calculate_image_hashes(image_path_or_url):
    """
    同时计算MD5哈希和感知哈希
    
    Args:
        image_path_or_url: 图片路径或URL
        
    Returns:
        tuple: (md5_hash, perceptual_hash)
    """
    md5_hash = calculate_image_hash(image_path_or_url)
    phash = calculate_perceptual_hash(image_path_or_url)
    return md5_hash, phash


def calculate_image_embedding(image_path_or_url):
    """
    计算图片的Embedding特征向量
    
    Args:
        image_path_or_url: 图片路径或URL
        
    Returns:
        numpy.ndarray: 特征向量（归一化后的向量），如果失败返回None
    """
    if not EMBEDDING_AVAILABLE:
        logger.warning("[IMAGE] Embedding功能不可用（torch未安装）")
        return None
    
    logger.info(f"[IMAGE] 开始提取Embedding: {image_path_or_url[:80]}...")
    try:
        embedding_service = get_embedding_service()
        if embedding_service is None:
            return None
        embedding = embedding_service.extract_embedding(image_path_or_url)
        if embedding is not None:
            logger.info(f"[IMAGE] Embedding提取成功: shape={embedding.shape}, dtype={embedding.dtype}")
        else:
            logger.warning("[IMAGE] Embedding提取返回None")
        return embedding
    except Exception as e:
        logger.error(f"[IMAGE] Embedding提取出错: {e}", exc_info=True)
        return None


def calculate_all_features(image_path_or_url):
    """
    计算图片的所有特征（MD5、感知哈希、Embedding）
    
    Args:
        image_path_or_url: 图片路径或URL
        
    Returns:
        dict: {
            'md5_hash': MD5哈希值,
            'phash': 感知哈希值,
            'embedding': Embedding向量（列表格式，用于存储）
        }
    """
    md5_hash, phash = calculate_image_hashes(image_path_or_url)
    embedding = calculate_image_embedding(image_path_or_url)
    
    # 将embedding转换为列表格式
    embedding_list = None
    if embedding is not None and EMBEDDING_AVAILABLE:
        try:
            embedding_service = get_embedding_service()
            if embedding_service is not None:
                embedding_list = embedding_service.embedding_to_list(embedding)
        except Exception as e:
            logger.warning(f"[IMAGE] 转换embedding到列表失败: {e}")
    
    return {
        'md5_hash': md5_hash,
        'phash': phash,
        'embedding': embedding_list
    }


def find_similar_image_by_phash(phash, threshold=5, db_session=None, Question=None):
    """
    根据感知哈希查找相似的图片（用于图推题去重）
    
    Args:
        phash: 当前图片的感知哈希值
        threshold: 哈希差异阈值，默认5（越小越严格）
        db_session: 数据库会话
        Question: Question模型类
        
    Returns:
        Question对象或None
    """
    if not db_session or not Question:
        return None
    
    # 获取所有有感知哈希的题目
    questions = db_session.query(Question).filter(
        Question.image_phash.isnot(None)
    ).all()
    
    current_hash = imagehash.hex_to_hash(phash)
    
    for question in questions:
        if question.image_phash:
            stored_hash = imagehash.hex_to_hash(question.image_phash)
            # 计算哈希差异
            hamming_distance = current_hash - stored_hash
            
            # 如果差异在阈值内，认为是同一道题
            if hamming_distance <= threshold:
                return question
    
    return None


def find_similar_image_by_embedding(embedding, similarity_threshold=0.85, db_session=None, Question=None):
    """
    根据Embedding特征向量查找相似的图片（用于图推题去重）
    
    Args:
        embedding: 当前图片的Embedding向量（numpy数组或列表）
        similarity_threshold: 相似度阈值，默认0.85（0-1之间，越大越严格）
        db_session: 数据库会话
        Question: Question模型类
        
    Returns:
        tuple: (Question对象, 相似度分数) 或 (None, 0.0)
    """
    logger.debug(f"[IMAGE] find_similar_image_by_embedding: embedding type={type(embedding)}, is None={embedding is None}")
    if not db_session or not Question:
        logger.debug("[IMAGE] db_session或Question为None，返回")
        return None, 0.0
    if embedding is None:
        logger.debug("[IMAGE] embedding为None，返回")
        return None, 0.0
    
    if not EMBEDDING_AVAILABLE:
        logger.warning("[IMAGE] Embedding功能不可用，无法查找相似图片")
        return None, 0.0
    
    logger.info(f"[IMAGE] embedding类型: {type(embedding)}, shape={embedding.shape if hasattr(embedding, 'shape') else 'N/A'}")
    try:
        embedding_service = get_embedding_service()
        if embedding_service is None:
            return None, 0.0
    except Exception as e:
        logger.warning(f"[IMAGE] 获取embedding服务失败: {e}")
        return None, 0.0
    
    # 获取所有有Embedding的题目
    questions = db_session.query(Question).filter(
        Question.image_embedding.isnot(None)
    ).all()
    
    best_match = None
    best_similarity = 0.0
    
    logger.info(f"[IMAGE] 开始查找相似图片，共{len(questions)}个题目")
    for i, question in enumerate(questions):
        if question.image_embedding is not None:  # 修复：不能直接用if判断
            logger.debug(f"[IMAGE] 检查题目 {i+1}/{len(questions)}: ID={question.id}, embedding type={type(question.image_embedding)}")
            try:
                # question.image_embedding可能是列表（从JSONType读取），需要转换为numpy数组
                stored_embedding = question.image_embedding
                if isinstance(stored_embedding, list):
                    stored_embedding = np.array(stored_embedding)
                    logger.debug(f"[IMAGE] 将存储的embedding从列表转换为numpy数组: shape={stored_embedding.shape}")
                
                # 计算余弦相似度
                similarity = embedding_service.cosine_similarity(
                    embedding, 
                    stored_embedding
                )
                logger.debug(f"[IMAGE] 题目 {question.id} 相似度: {similarity:.4f}")
                
                if similarity > best_similarity and similarity >= similarity_threshold:
                    best_similarity = similarity
                    best_match = question
                    logger.info(f"[IMAGE] 找到更匹配的题目: ID={question.id}, 相似度={similarity:.4f}")
            except Exception as e:
                logger.error(f"[IMAGE] 计算相似度出错 (题目 {question.id}): {e}", exc_info=True)
                continue
    
    logger.info(f"[IMAGE] 查找完成: best_match={'找到' if best_match else '未找到'}, similarity={best_similarity:.4f}")
    return best_match, best_similarity


def find_similar_image(phash=None, embedding=None, phash_threshold=5, embedding_threshold=0.85, 
                       db_session=None, Question=None, use_both=True):
    """
    综合使用Perceptual Hash和Embedding两种方法查找相似的图片
    
    策略：
    1. 先尝试Perceptual Hash（快速）
    2. 如果没找到且use_both=True，再尝试Embedding（更准确但更慢）
    3. 如果两种方法都找到，优先返回相似度更高的
    
    Args:
        phash: 当前图片的感知哈希值
        embedding: 当前图片的Embedding向量
        phash_threshold: 感知哈希差异阈值
        embedding_threshold: Embedding相似度阈值
        db_session: 数据库会话
        Question: Question模型类
        use_both: 是否同时使用两种方法
        
    Returns:
        Question对象或None
    """
    logger.info(f"[IMAGE] find_similar_image: phash={phash is not None}, embedding={embedding is not None}, use_both={use_both}")
    if not db_session or not Question:
        logger.debug("[IMAGE] db_session或Question为None")
        return None
    
    result_phash = None
    result_embedding = None
    embedding_similarity = 0.0
    
    # 方法1：使用Perceptual Hash查找
    if phash:
        logger.info("[IMAGE] 开始Perceptual Hash查找")
        result_phash = find_similar_image_by_phash(
            phash, 
            threshold=phash_threshold,
            db_session=db_session,
            Question=Question
        )
        logger.info(f"[IMAGE] Perceptual Hash查找结果: {'找到' if result_phash else '未找到'}")
    
    # 方法2：使用Embedding查找（如果Perceptual Hash没找到，或者use_both=True）
    if embedding is not None and (not result_phash or use_both):  # 修复：不能直接用if embedding判断
        logger.info("[IMAGE] 开始Embedding查找")
        result_embedding, embedding_similarity = find_similar_image_by_embedding(
            embedding,
            similarity_threshold=embedding_threshold,
            db_session=db_session,
            Question=Question
        )
        logger.info(f"[IMAGE] Embedding查找结果: {'找到' if result_embedding else '未找到'}, 相似度={embedding_similarity:.4f}")
    
    # 如果两种方法都找到了，优先返回Embedding的结果（通常更准确）
    if result_embedding is not None and embedding_similarity >= embedding_threshold:  # 修复：不能直接用if判断
        logger.info(f"[IMAGE] 返回Embedding结果: ID={result_embedding.id}")
        return result_embedding
    
    # 返回Perceptual Hash的结果
    if result_phash:
        logger.info(f"[IMAGE] 返回Perceptual Hash结果: ID={result_phash.id}")
        return result_phash
    
    logger.info("[IMAGE] 未找到匹配的题目")
    return None

