"""
初始化数据库 V2 - 创建新版本的数据库表
"""
import os
from dotenv import load_dotenv
from app import app, db
from models_v2 import Question, AnswerVersion

load_dotenv()

def init_database():
    """初始化数据库"""
    with app.app_context():
        try:
            # 测试数据库连接
            db.engine.connect()
            print("✅ 数据库连接成功！")
            
            # 删除旧表（如果存在）
            print("🗑️  删除旧表（如果存在）...")
            db.drop_all()
            print("✅ 旧表已删除")
            
            # 创建新表
            print("📝 创建新表...")
            db.create_all()
            print("✅ 数据库表已创建！")
            
            # 显示表信息
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            print(f"\n📊 已创建表: {', '.join(tables)}")
            
        except Exception as e:
            print(f"❌ 数据库初始化失败：{e}")
            import traceback
            traceback.print_exc()
            exit(1)

if __name__ == '__main__':
    init_database()

