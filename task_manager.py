"""
任务管理器 - 用于异步批量处理任务
"""
import uuid
import time
import logging
import threading
from typing import Dict, Optional
from enum import Enum
from threading import Thread
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"      # 等待处理
    PROCESSING = "processing"  # 处理中
    COMPLETED = "completed"    # 已完成
    FAILED = "failed"          # 失败

class TaskManager:
    """任务管理器（内存存储，单机版本）"""
    
    def __init__(self):
        self.tasks: Dict[str, Dict] = {}
        self._cleanup_interval = 3600  # 1小时清理一次过期任务
        self._task_ttl = 7200  # 任务保留2小时
        self._lock = threading.Lock()  # 添加锁确保线程安全
        
    def create_task(self, task_type: str, params: Dict) -> str:
        """
        创建任务
        
        Args:
            task_type: 任务类型（如 'batch_extract'）
            params: 任务参数
        
        Returns:
            str: 任务ID
        """
        task_id = str(uuid.uuid4())
        task = {
            'id': task_id,
            'type': task_type,
            'status': TaskStatus.PENDING.value,
            'params': params,
            'result': None,
            'error': None,
            'progress': {
                'total': 0,
                'completed': 0,
                'failed': 0,
                'current_item': None
            },
            'created_at': datetime.now().isoformat(),
            'started_at': None,
            'completed_at': None,
            'total_time': None
        }
        
        self.tasks[task_id] = task
        logger.info(f"[TaskManager] 创建任务: {task_id}, 类型: {task_type}")
        return task_id
    
    def get_task(self, task_id: str) -> Optional[Dict]:
        """获取任务信息（线程安全）"""
        with self._lock:
            task = self.tasks.get(task_id)
            if task:
                # 返回任务的深拷贝，避免外部修改影响内部状态
                import copy
                return copy.deepcopy(task)
            return None
    
    def update_task_status(self, task_id: str, status: TaskStatus, **kwargs):
        """更新任务状态（线程安全）"""
        with self._lock:  # 使用锁确保线程安全
            if task_id not in self.tasks:
                logger.warning(f"[TaskManager] 任务不存在: {task_id}")
                return
            
            task = self.tasks[task_id]
            task['status'] = status.value
            
            if 'result' in kwargs:
                task['result'] = kwargs['result']
            if 'error' in kwargs:
                task['error'] = kwargs['error']
            if 'progress' in kwargs:
                # 更新进度信息
                progress_update = kwargs['progress']
                task['progress'].update(progress_update)
                # 记录进度更新日志
                progress_info = task['progress']
                logger.info(
                    f"[TaskManager] 📊 任务进度更新: {task_id[:8]}, "
                    f"状态={status.value}, "
                    f"进度={progress_info.get('completed', 0)}/{progress_info.get('total', 0)}, "
                    f"失败={progress_info.get('failed', 0)}"
                )
            
            if status == TaskStatus.PROCESSING and task['started_at'] is None:
                task['started_at'] = datetime.now().isoformat()
            elif status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                task['completed_at'] = datetime.now().isoformat()
                if task['started_at']:
                    started = datetime.fromisoformat(task['started_at'])
                    completed = datetime.fromisoformat(task['completed_at'])
                    task['total_time'] = (completed - started).total_seconds()
            
            logger.debug(f"[TaskManager] 更新任务状态: {task_id[:8]}, 状态: {status.value}")
    
    def cleanup_expired_tasks(self):
        """清理过期任务"""
        now = datetime.now()
        expired_tasks = []
        
        for task_id, task in self.tasks.items():
            created_at = datetime.fromisoformat(task['created_at'])
            if (now - created_at).total_seconds() > self._task_ttl:
                expired_tasks.append(task_id)
        
        for task_id in expired_tasks:
            del self.tasks[task_id]
            logger.info(f"[TaskManager] 清理过期任务: {task_id}")
    
    def get_task_summary(self, task_id: str) -> Dict:
        """获取任务摘要（用于状态查询，线程安全）"""
        with self._lock:
            task = self.tasks.get(task_id)
            if not task:
                return None
            
            # 直接访问任务字典，避免深拷贝开销
            progress = task.get('progress', {})
            return {
                'id': task['id'],
                'type': task['type'],
                'status': task['status'],
                'progress': {
                    'total': progress.get('total', 0),
                    'completed': progress.get('completed', 0),
                    'failed': progress.get('failed', 0),
                    'current_item': progress.get('current_item')
                },
                'created_at': task['created_at'],
                'started_at': task['started_at'],
                'completed_at': task['completed_at'],
                'total_time': task['total_time'],
                'has_result': task['result'] is not None,
                'has_error': task['error'] is not None
            }

# 全局任务管理器实例
_task_manager = None

def get_task_manager() -> TaskManager:
    """获取任务管理器实例（单例）"""
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager()
    return _task_manager
