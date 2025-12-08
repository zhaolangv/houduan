"""
图片Embedding特征向量提取服务
使用深度学习模型提取图片的语义特征向量
"""
import os
import numpy as np
from PIL import Image
from io import BytesIO
import requests
import torch
from sentence_transformers import SentenceTransformer
from functools import lru_cache


class EmbeddingService:
    """图片Embedding提取服务"""
    
    def __init__(self, model_name='clip-ViT-B-32'):
        """
        初始化Embedding服务
        
        Args:
            model_name: 使用的模型名称
                - 'clip-ViT-B-32': CLIP ViT-B/32（推荐，平衡速度和准确度）
                - 'clip-ViT-L-14': CLIP ViT-L/14（更准确但更慢）
        """
        self.model_name = model_name
        self.model = None
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self._load_model()
    
    def _load_model(self):
        """加载模型（延迟加载，只在需要时加载）"""
        if self.model is None:
            print(f"正在加载Embedding模型: {self.model_name} (设备: {self.device})")
            try:
                self.model = SentenceTransformer(self.model_name, device=self.device)
                print("✅ Embedding模型加载成功")
            except Exception as e:
                print(f"⚠️ 模型加载失败: {e}")
                print("将使用备用方法...")
                self.model = None
    
    def extract_embedding(self, image_path_or_url):
        """
        提取图片的Embedding特征向量
        
        Args:
            image_path_or_url: 图片路径或URL
            
        Returns:
            numpy.ndarray: 特征向量（归一化后的向量）
        """
        if self.model is None:
            self._load_model()
        
        if self.model is None:
            # 如果模型加载失败，返回None
            return None
        
        try:
            # 加载图片
            if image_path_or_url.startswith('http://') or image_path_or_url.startswith('https://'):
                response = requests.get(image_path_or_url, timeout=10)
                image = Image.open(BytesIO(response.content))
            elif image_path_or_url.startswith('file://'):
                # 处理file://协议
                file_path = image_path_or_url[7:]  # 移除file://前缀
                image = Image.open(file_path)
            else:
                image = Image.open(image_path_or_url)
            
            # 转换为RGB（如果图片是RGBA或其他格式）
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # 提取embedding
            embedding = self.model.encode(image, convert_to_numpy=True)
            
            # L2归一化（用于余弦相似度计算）
            embedding = embedding / np.linalg.norm(embedding)
            
            return embedding
        
        except Exception as e:
            print(f"提取Embedding失败: {e}")
            return None
    
    def embedding_to_list(self, embedding):
        """
        将numpy数组转换为列表（用于存储到数据库）
        
        Args:
            embedding: numpy数组
            
        Returns:
            list: Python列表
        """
        if embedding is None:
            return None
        return embedding.tolist()
    
    def list_to_embedding(self, embedding_list):
        """
        将列表转换为numpy数组（从数据库读取）
        
        Args:
            embedding_list: Python列表
            
        Returns:
            numpy.ndarray: numpy数组
        """
        if embedding_list is None:
            return None
        return np.array(embedding_list)
    
    def cosine_similarity(self, embedding1, embedding2):
        """
        计算两个embedding的余弦相似度
        
        Args:
            embedding1: 第一个embedding（numpy数组或列表）
            embedding2: 第二个embedding（numpy数组或列表）
            
        Returns:
            float: 余弦相似度（0-1之间，1表示完全相同）
        """
        if embedding1 is None or embedding2 is None:
            return 0.0
        
        # 转换为numpy数组
        if isinstance(embedding1, list):
            embedding1 = np.array(embedding1)
        if isinstance(embedding2, list):
            embedding2 = np.array(embedding2)
        
        # 确保是归一化的向量
        embedding1 = embedding1 / np.linalg.norm(embedding1)
        embedding2 = embedding2 / np.linalg.norm(embedding2)
        
        # 计算余弦相似度（点积，因为已经归一化）
        similarity = np.dot(embedding1, embedding2)
        
        return float(similarity)


# 全局单例
_embedding_service = None

def get_embedding_service():
    """获取Embedding服务单例"""
    global _embedding_service
    if _embedding_service is None:
        model_name = os.getenv('EMBEDDING_MODEL', 'clip-ViT-B-32')
        _embedding_service = EmbeddingService(model_name=model_name)
    return _embedding_service

