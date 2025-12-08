"""
Supabase存储服务：上传和管理图片
"""
import os
import logging
from typing import Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

class SupabaseStorageService:
    """Supabase存储服务类"""
    
    def __init__(self):
        self.client = None
        self.bucket_name = os.getenv('SUPABASE_STORAGE_BUCKET', 'question-images')
        self._init_client()
    
    def _init_client(self):
        """初始化Supabase客户端"""
        try:
            from supabase import create_client, Client
            
            supabase_url = os.getenv('SUPABASE_URL')
            supabase_key = os.getenv('SUPABASE_ANON_KEY') or os.getenv('SUPABASE_SERVICE_KEY')
            
            if not supabase_url or not supabase_key:
                logger.warning("[SupabaseStorage] 未配置SUPABASE_URL或SUPABASE_ANON_KEY，将使用本地存储")
                self.client = None
                return
            
            # 检查并清理API key（移除可能的非ASCII字符）
            if supabase_key:
                # 只保留ASCII字符
                supabase_key = ''.join(c for c in supabase_key if ord(c) < 128)
                # 检查是否是模板值
                if '你的' in supabase_key or '[PROJECT-REF]' in supabase_url:
                    logger.warning("[SupabaseStorage] 检测到模板值，请更新.env文件中的实际配置")
                    self.client = None
                    return
            
            self.client = create_client(supabase_url, supabase_key)
            logger.info(f"[SupabaseStorage] Supabase客户端初始化成功，存储桶: {self.bucket_name}")
            
            # 检查存储桶是否存在，如果不存在则创建
            self._ensure_bucket_exists()
            
        except ImportError:
            logger.warning("[SupabaseStorage] supabase-py未安装，将使用本地存储")
            logger.info("[SupabaseStorage] 安装命令: pip install supabase")
            self.client = None
        except Exception as e:
            logger.error(f"[SupabaseStorage] 初始化失败: {e}", exc_info=True)
            self.client = None
    
    def _ensure_bucket_exists(self):
        """确保存储桶存在"""
        if not self.client:
            return
        
        try:
            # 尝试列出存储桶
            buckets = self.client.storage.list_buckets()
            bucket_names = [b.name for b in buckets]
            
            if self.bucket_name not in bucket_names:
                logger.info(f"[SupabaseStorage] 存储桶 '{self.bucket_name}' 不存在，尝试创建...")
                # 注意：创建存储桶需要service key，如果使用anon key可能会失败
                try:
                    self.client.storage.create_bucket(
                        self.bucket_name,
                        options={"public": True}  # 公开存储桶，允许直接访问
                    )
                    logger.info(f"[SupabaseStorage] 存储桶 '{self.bucket_name}' 创建成功")
                except Exception as e:
                    logger.warning(f"[SupabaseStorage] 无法自动创建存储桶: {e}")
                    logger.info(f"[SupabaseStorage] 请在Supabase Dashboard中手动创建存储桶: {self.bucket_name}")
            else:
                logger.info(f"[SupabaseStorage] 存储桶 '{self.bucket_name}' 已存在")
        except Exception as e:
            logger.warning(f"[SupabaseStorage] 检查存储桶失败: {e}")
    
    def upload_image(self, image_file, folder: str = None) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        上传图片到Supabase Storage
        
        Args:
            image_file: 文件对象（有read()方法）
            folder: 文件夹路径（可选，如 '2025/12/05'）
            
        Returns:
            Tuple[bool, Optional[str], Optional[str]]: 
                (成功标志, 文件路径, 公开URL)
                如果失败或未配置Supabase，返回 (False, None, None)
        """
        if not self.client:
            logger.debug("[SupabaseStorage] Supabase客户端未初始化，跳过上传")
            return False, None, None
        
        try:
            # 生成唯一文件名
            import uuid
            filename = image_file.filename if hasattr(image_file, 'filename') else 'image.jpg'
            ext = os.path.splitext(filename)[1] or '.jpg'
            unique_filename = f"{uuid.uuid4().hex[:8]}{ext}"
            
            # 构建文件路径
            if folder:
                file_path = f"{folder}/{unique_filename}"
            else:
                # 使用日期作为文件夹
                today = datetime.now()
                file_path = f"{today.year}/{today.month:02d}/{today.day:02d}/{unique_filename}"
            
            # 读取文件内容
            image_file.seek(0)
            file_content = image_file.read()
            
            # 上传到Supabase
            logger.info(f"[SupabaseStorage] 上传图片到: {file_path}")
            response = self.client.storage.from_(self.bucket_name).upload(
                path=file_path,
                file=file_content,
                file_options={
                    "content-type": f"image/{ext[1:].lower()}" if ext else "image/jpeg",
                    "upsert": "false"  # 如果文件已存在，不覆盖
                }
            )
            
            # 获取公开URL
            public_url = self.get_public_url(file_path)
            
            logger.info(f"[SupabaseStorage] ✅ 上传成功: {file_path}")
            logger.info(f"[SupabaseStorage] 公开URL: {public_url}")
            
            return True, file_path, public_url
            
        except Exception as e:
            logger.error(f"[SupabaseStorage] 上传失败: {e}", exc_info=True)
            return False, None, None
    
    def get_public_url(self, file_path: str) -> str:
        """
        获取文件的公开URL
        
        Args:
            file_path: 文件在存储桶中的路径
            
        Returns:
            str: 公开URL
        """
        if not self.client:
            return ""
        
        try:
            response = self.client.storage.from_(self.bucket_name).get_public_url(file_path)
            return response
        except Exception as e:
            logger.error(f"[SupabaseStorage] 获取公开URL失败: {e}")
            return ""
    
    def delete_image(self, file_path: str) -> bool:
        """
        删除图片
        
        Args:
            file_path: 文件在存储桶中的路径
            
        Returns:
            bool: 是否删除成功
        """
        if not self.client:
            return False
        
        try:
            self.client.storage.from_(self.bucket_name).remove([file_path])
            logger.info(f"[SupabaseStorage] 删除成功: {file_path}")
            return True
        except Exception as e:
            logger.error(f"[SupabaseStorage] 删除失败: {e}")
            return False
    
    def is_available(self) -> bool:
        """检查Supabase存储是否可用"""
        return self.client is not None


# 全局服务实例（单例）
_supabase_storage_service = None

def get_supabase_storage_service():
    """获取Supabase存储服务实例（单例模式）"""
    global _supabase_storage_service
    if _supabase_storage_service is None:
        _supabase_storage_service = SupabaseStorageService()
    return _supabase_storage_service

