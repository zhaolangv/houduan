"""
数据库模型定义 V2 - 适配新的API规范
"""
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import Text, TypeDecorator, String, Float, Boolean, Integer, ForeignKey
import json
import os
import uuid as uuid_lib

# 根据数据库类型选择字段类型
try:
    from sqlalchemy.dialects.postgresql import TEXT, JSONB, UUID
    HAS_POSTGRES = True
except ImportError:
    HAS_POSTGRES = False

# 检测是否使用SQLite（更准确的检测）
def _is_sqlite():
    db_url = os.getenv('DATABASE_URL', '')
    if not db_url:
        return True  # 默认使用SQLite
    return db_url.startswith('sqlite')

USE_SQLITE = _is_sqlite()

# 根据数据库类型选择TEXT类型
if USE_SQLITE or not HAS_POSTGRES:
    DB_TEXT = Text
    DB_JSON = Text  # SQLite使用Text存储JSON
    # SQLite使用String存储UUID，但需要确保default返回字符串
    DB_UUID = String(36)  # SQLite使用String存储UUID
else:
    DB_TEXT = TEXT
    DB_JSON = JSONB
    # PostgreSQL使用UUID类型，但as_uuid=False确保存储为字符串
    DB_UUID = String(36)  # 统一使用String(36)存储UUID字符串，避免类型问题

db = SQLAlchemy()


class JSONType(TypeDecorator):
    """自定义类型：自动处理JSON序列化/反序列化（用于SQLite）"""
    impl = Text
    cache_ok = True
    
    def process_bind_param(self, value, dialect):
        """保存到数据库时：将Python对象转换为JSON字符串"""
        if value is None:
            return None
        if isinstance(value, (list, dict)):
            return json.dumps(value, ensure_ascii=False)
        return value
    
    def process_result_value(self, value, dialect):
        """从数据库读取时：将JSON字符串转换为Python对象"""
        if value is None:
            return None
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        return value


def generate_uuid():
    """生成UUID字符串"""
    return str(uuid_lib.uuid4())


class Question(db.Model):
    """题目表"""
    __tablename__ = 'questions'
    
    id = db.Column(DB_UUID, primary_key=True, default=generate_uuid)
    screenshot = db.Column(String(500), comment='图片路径')
    raw_text = db.Column(DB_TEXT, comment='OCR识别的原始文本')
    question_text = db.Column(DB_TEXT, comment='题干（经过简单处理）')
    question_type = db.Column(String(20), nullable=False, comment='题目类型：TEXT（文字题）或GRAPHIC（图推题）')
    options = db.Column(JSONType(), comment='选项（JSON数组）')
    correct_answer = db.Column(String(10), comment='正确答案')
    explanation = db.Column(DB_TEXT, comment='解析说明')
    tags = db.Column(JSONType(), comment='标签（JSON数组）')
    knowledge_points = db.Column(JSONType(), comment='知识点（JSON数组）')
    source = db.Column(String(200), comment='来源')
    source_url = db.Column(String(500), comment='来源URL')
    encountered_date = db.Column(db.Date, comment='遇到日期')
    difficulty = db.Column(Integer, comment='难度（1-5）')
    priority = db.Column(String(10), comment='优先级：高、中、低')
    ocr_confidence = db.Column(Float, comment='OCR置信度')
    similar_questions = db.Column(JSONType(), comment='相似题目ID列表（JSON数组）')
    question_hash = db.Column(String(64), index=True, comment='题目文本哈希值（用于去重）')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关联关系
    answer_versions = db.relationship('AnswerVersion', backref='question', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Question {self.id}: {self.question_type}>'


class AnswerVersion(db.Model):
    """答案版本表"""
    __tablename__ = 'answer_versions'
    
    id = db.Column(DB_UUID, primary_key=True, default=generate_uuid)
    question_id = db.Column(DB_UUID, ForeignKey('questions.id'), nullable=False, index=True)
    source_name = db.Column(String(50), nullable=False, comment='来源名称：粉笔、华图、AI等')
    source_type = db.Column(String(20), nullable=False, comment='来源类型：机构、AI')
    answer = db.Column(String(10), nullable=False, comment='答案')
    explanation = db.Column(DB_TEXT, comment='解析')
    confidence = db.Column(Float, comment='置信度（0-1）')
    is_user_preferred = db.Column(Boolean, default=False, comment='用户偏好')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<AnswerVersion {self.id}: {self.source_name}>'

