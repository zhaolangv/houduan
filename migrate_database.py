"""
数据库迁移脚本：从 SQLite 迁移到 PostgreSQL/MySQL

使用方法：
1. 配置目标数据库（.env 文件中的 DATABASE_URL）
2. 运行脚本：python migrate_database.py
"""
import os
import sys
from datetime import datetime
from dotenv import load_dotenv
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv()

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, scoped_session
import json


def get_sqlite_url():
    """获取 SQLite 数据库 URL"""
    sqlite_path = os.getenv('SQLITE_DB_PATH', 'gongkao_test.db')
    if not os.path.exists(sqlite_path):
        logger.warning(f"⚠️ SQLite 数据库文件不存在: {sqlite_path}")
        logger.info("💡 提示: 可以设置环境变量 SQLITE_DB_PATH 指定 SQLite 数据库路径")
        return None
    return f'sqlite:///{sqlite_path}'


def get_target_db_url():
    """获取目标数据库 URL"""
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        logger.error("❌ 未配置 DATABASE_URL 环境变量")
        logger.info("💡 请在 .env 文件中配置目标数据库连接，例如：")
        logger.info("   PostgreSQL: postgresql://user:password@host:port/database")
        logger.info("   MySQL: mysql+pymysql://user:password@host:port/database")
        return None
    
    # 检查是否是 SQLite（不应该作为目标）
    if db_url.startswith('sqlite'):
        logger.error("❌ 目标数据库不能是 SQLite，请配置 PostgreSQL 或 MySQL")
        return None
    
    return db_url


def check_database_connection(engine, db_name):
    """检查数据库连接"""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info(f"✅ {db_name} 数据库连接成功")
        return True
    except Exception as e:
        logger.error(f"❌ {db_name} 数据库连接失败: {e}")
        return False


def get_table_row_count(engine, table_name):
    """获取表的行数"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
            count = result.scalar()
            return count
    except Exception as e:
        logger.warning(f"⚠️ 无法获取表 {table_name} 的行数: {e}")
        return 0


def migrate_questions(sqlite_session, target_session, Question):
    """迁移题目表"""
    logger.info("\n" + "="*70)
    logger.info("📦 开始迁移 questions 表...")
    
    # 获取所有题目
    questions = sqlite_session.query(Question).all()
    total_count = len(questions)
    
    if total_count == 0:
        logger.info("ℹ️ SQLite 中没有题目数据，跳过迁移")
        return 0
    
    logger.info(f"📊 找到 {total_count} 条题目记录")
    
    migrated = 0
    skipped = 0
    errors = 0
    
    for i, question in enumerate(questions, 1):
        try:
            # 检查目标数据库中是否已存在
            existing = target_session.query(Question).filter_by(id=question.id).first()
            
            if existing:
                logger.debug(f"⏭️  题目 {i}/{total_count} (ID: {question.id}) 已存在，跳过")
                skipped += 1
                continue
            
            # 处理 JSON 字段
            options = question.options
            if isinstance(options, str):
                try:
                    options = json.loads(options) if options else None
                except:
                    options = None
            
            tags = question.tags
            if isinstance(tags, str):
                try:
                    tags = json.loads(tags) if tags else None
                except:
                    tags = None
            
            knowledge_points = question.knowledge_points
            if isinstance(knowledge_points, str):
                try:
                    knowledge_points = json.loads(knowledge_points) if knowledge_points else None
                except:
                    knowledge_points = None
            
            similar_questions = question.similar_questions
            if isinstance(similar_questions, str):
                try:
                    similar_questions = json.loads(similar_questions) if similar_questions else None
                except:
                    similar_questions = None
            
            # 创建新题目记录
            new_question = Question(
                id=question.id,
                screenshot=question.screenshot,
                raw_text=question.raw_text,
                question_text=question.question_text,
                question_type=question.question_type or 'TEXT',
                options=options,
                correct_answer=question.correct_answer,
                explanation=question.explanation,
                tags=tags,
                knowledge_points=knowledge_points,
                source=question.source,
                source_url=question.source_url,
                encountered_date=question.encountered_date,
                difficulty=question.difficulty,
                priority=question.priority,
                ocr_confidence=question.ocr_confidence,
                similar_questions=similar_questions,
                question_hash=question.question_hash,
                created_at=question.created_at or datetime.utcnow(),
                updated_at=question.updated_at or datetime.utcnow()
            )
            
            target_session.add(new_question)
            
            if i % 10 == 0 or i == total_count:
                target_session.commit()
                logger.info(f"✅ 已迁移 {i}/{total_count} 条题目记录 (成功: {i - skipped - errors}, 跳过: {skipped}, 错误: {errors})")
            
            migrated += 1
            
        except Exception as e:
            errors += 1
            logger.error(f"❌ 迁移题目 {i}/{total_count} (ID: {question.id}) 失败: {e}")
            target_session.rollback()
            continue
    
    # 最终提交
    try:
        target_session.commit()
        logger.info(f"✅ questions 表迁移完成!")
        logger.info(f"   成功: {migrated}, 跳过: {skipped}, 错误: {errors}")
    except Exception as e:
        logger.error(f"❌ 提交失败: {e}")
        target_session.rollback()
    
    return migrated


def migrate_answer_versions(sqlite_session, target_session, AnswerVersion):
    """迁移答案版本表"""
    logger.info("\n" + "="*70)
    logger.info("📦 开始迁移 answer_versions 表...")
    
    # 获取所有答案版本
    answer_versions = sqlite_session.query(AnswerVersion).all()
    total_count = len(answer_versions)
    
    if total_count == 0:
        logger.info("ℹ️ SQLite 中没有答案版本数据，跳过迁移")
        return 0
    
    logger.info(f"📊 找到 {total_count} 条答案版本记录")
    
    migrated = 0
    skipped = 0
    errors = 0
    
    for i, answer_version in enumerate(answer_versions, 1):
        try:
            # 检查目标数据库中是否已存在
            existing = target_session.query(AnswerVersion).filter_by(id=answer_version.id).first()
            
            if existing:
                logger.debug(f"⏭️  答案版本 {i}/{total_count} (ID: {answer_version.id}) 已存在，跳过")
                skipped += 1
                continue
            
            # 创建新答案版本记录
            new_answer_version = AnswerVersion(
                id=answer_version.id,
                question_id=answer_version.question_id,
                source_name=answer_version.source_name,
                source_type=answer_version.source_type,
                answer=answer_version.answer,
                explanation=answer_version.explanation,
                confidence=answer_version.confidence,
                is_user_preferred=answer_version.is_user_preferred or False,
                created_at=answer_version.created_at or datetime.utcnow(),
                updated_at=answer_version.updated_at or datetime.utcnow()
            )
            
            target_session.add(new_answer_version)
            
            if i % 50 == 0 or i == total_count:
                target_session.commit()
                logger.info(f"✅ 已迁移 {i}/{total_count} 条答案版本记录 (成功: {i - skipped - errors}, 跳过: {skipped}, 错误: {errors})")
            
            migrated += 1
            
        except Exception as e:
            errors += 1
            logger.error(f"❌ 迁移答案版本 {i}/{total_count} (ID: {answer_version.id}) 失败: {e}")
            target_session.rollback()
            continue
    
    # 最终提交
    try:
        target_session.commit()
        logger.info(f"✅ answer_versions 表迁移完成!")
        logger.info(f"   成功: {migrated}, 跳过: {skipped}, 错误: {errors}")
    except Exception as e:
        logger.error(f"❌ 提交失败: {e}")
        target_session.rollback()
    
    return migrated


def create_tables_if_not_exist(target_engine):
    """在目标数据库中创建表（如果不存在）"""
    logger.info("\n" + "="*70)
    logger.info("📋 检查目标数据库表结构...")
    
    # 创建 Flask 应用上下文来初始化表
    from flask import Flask
    from models_v2 import db, Question, AnswerVersion
    
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # 根据数据库类型配置连接池
    if 'postgresql' in os.getenv('DATABASE_URL', '').lower():
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_pre_ping': True,
            'pool_recycle': 300,
            'pool_size': 10,
            'max_overflow': 10,
        }
    elif 'mysql' in os.getenv('DATABASE_URL', '').lower():
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_pre_ping': True,
            'pool_recycle': 300,
            'pool_size': 10,
            'max_overflow': 10,
        }
    
    db.init_app(app)
    
    with app.app_context():
        inspector = inspect(target_engine)
        existing_tables = inspector.get_table_names()
        
        if 'questions' in existing_tables and 'answer_versions' in existing_tables:
            logger.info("✅ 目标数据库表已存在，跳过创建")
        else:
            logger.info("📝 创建数据库表...")
            db.create_all()
            logger.info("✅ 数据库表创建完成")


def main():
    """主函数"""
    logger.info("="*70)
    logger.info("🚀 数据库迁移工具")
    logger.info("="*70)
    
    # 1. 获取 SQLite 数据库路径
    sqlite_url = get_sqlite_url()
    if not sqlite_url:
        logger.error("❌ 无法找到 SQLite 数据库，迁移终止")
        return
    
    # 2. 获取目标数据库 URL
    target_db_url = get_target_db_url()
    if not target_db_url:
        logger.error("❌ 目标数据库配置错误，迁移终止")
        return
    
    logger.info(f"\n📂 SQLite 数据库: {sqlite_url.replace('sqlite:///', '')}")
    logger.info(f"🎯 目标数据库: {target_db_url.split('@')[-1] if '@' in target_db_url else target_db_url}")
    
    # 3. 创建数据库引擎
    try:
        sqlite_engine = create_engine(sqlite_url, echo=False)
        target_engine = create_engine(target_db_url, echo=False)
    except Exception as e:
        logger.error(f"❌ 创建数据库引擎失败: {e}")
        return
    
    # 4. 检查连接
    if not check_database_connection(sqlite_engine, "SQLite"):
        return
    
    if not check_database_connection(target_engine, "目标数据库"):
        return
    
    # 5. 检查表是否存在
    sqlite_inspector = inspect(sqlite_engine)
    sqlite_tables = sqlite_inspector.get_table_names()
    
    if 'questions' not in sqlite_tables:
        logger.warning("⚠️ SQLite 数据库中不存在 questions 表")
        logger.info("💡 可能是新数据库，无需迁移")
        return
    
    # 6. 创建 Flask 应用和数据库会话
    from flask import Flask
    from models_v2 import db, Question, AnswerVersion
    
    # SQLite 应用
    sqlite_app = Flask(__name__)
    sqlite_app.config['SQLALCHEMY_DATABASE_URI'] = sqlite_url
    sqlite_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(sqlite_app)
    
    # 目标数据库应用
    target_app = Flask(__name__)
    target_app.config['SQLALCHEMY_DATABASE_URI'] = target_db_url
    target_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # 根据数据库类型配置连接池
    if 'postgresql' in target_db_url.lower():
        target_app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_pre_ping': True,
            'pool_recycle': 300,
            'pool_size': 10,
            'max_overflow': 10,
        }
    elif 'mysql' in target_db_url.lower():
        target_app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_pre_ping': True,
            'pool_recycle': 300,
            'pool_size': 10,
            'max_overflow': 10,
        }
    
    db.init_app(target_app)
    
    # 7. 在目标数据库中创建表
    with target_app.app_context():
        create_tables_if_not_exist(target_engine)
    
    # 8. 显示数据统计
    logger.info("\n" + "="*70)
    logger.info("📊 数据统计")
    logger.info("="*70)
    
    with sqlite_app.app_context():
        sqlite_session = db.session
        questions_count = get_table_row_count(sqlite_engine, 'questions')
        answer_versions_count = get_table_row_count(sqlite_engine, 'answer_versions')
        
        logger.info(f"SQLite questions: {questions_count} 条")
        logger.info(f"SQLite answer_versions: {answer_versions_count} 条")
    
    with target_app.app_context():
        target_session = db.session
        target_questions_count = get_table_row_count(target_engine, 'questions')
        target_answer_versions_count = get_table_row_count(target_engine, 'answer_versions')
        
        logger.info(f"目标数据库 questions: {target_questions_count} 条")
        logger.info(f"目标数据库 answer_versions: {target_answer_versions_count} 条")
    
    # 9. 确认迁移
    logger.info("\n" + "="*70)
    if questions_count == 0 and answer_versions_count == 0:
        logger.info("ℹ️ SQLite 数据库中没有数据，无需迁移")
        return
    
    logger.info("⚠️  准备开始迁移，这将复制 SQLite 数据到目标数据库")
    logger.info("   已存在的记录将被跳过（基于 ID）")
    
    confirm = input("\n是否继续？(yes/no): ").strip().lower()
    if confirm not in ['yes', 'y', '是']:
        logger.info("❌ 用户取消迁移")
        return
    
    # 10. 开始迁移
    logger.info("\n" + "="*70)
    logger.info("🚀 开始迁移数据...")
    logger.info("="*70)
    
    start_time = datetime.now()
    
    with sqlite_app.app_context():
        sqlite_session = db.session
        with target_app.app_context():
            target_session = db.session
            
            # 迁移题目
            questions_migrated = migrate_questions(sqlite_session, target_session, Question)
            
            # 迁移答案版本
            answer_versions_migrated = migrate_answer_versions(
                sqlite_session, target_session, AnswerVersion
            )
    
    end_time = datetime.now()
    elapsed = (end_time - start_time).total_seconds()
    
    # 11. 显示迁移结果
    logger.info("\n" + "="*70)
    logger.info("✅ 迁移完成!")
    logger.info("="*70)
    logger.info(f"📦 迁移题目: {questions_migrated} 条")
    logger.info(f"📦 迁移答案版本: {answer_versions_migrated} 条")
    logger.info(f"⏱️  总耗时: {elapsed:.2f} 秒")
    
    # 12. 验证迁移结果
    logger.info("\n" + "="*70)
    logger.info("🔍 验证迁移结果...")
    logger.info("="*70)
    
    with target_app.app_context():
        final_questions_count = get_table_row_count(target_engine, 'questions')
        final_answer_versions_count = get_table_row_count(target_engine, 'answer_versions')
        
        logger.info(f"目标数据库 questions: {final_questions_count} 条")
        logger.info(f"目标数据库 answer_versions: {final_answer_versions_count} 条")
    
    logger.info("\n✅ 迁移完成！现在可以更新 .env 文件中的 DATABASE_URL 并重启应用")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n\n❌ 用户中断迁移")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ 迁移过程中发生错误: {e}", exc_info=True)
        sys.exit(1)
