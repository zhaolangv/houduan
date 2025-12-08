"""
数据库连接检查脚本

用于在迁移前检查：
1. SQLite 数据库是否存在
2. 目标数据库连接是否正常
3. 数据统计信息
"""
import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, inspect
import logging

logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()


def check_sqlite():
    """检查 SQLite 数据库"""
    logger.info("="*70)
    logger.info("📂 检查 SQLite 数据库")
    logger.info("="*70)
    
    sqlite_path = os.getenv('SQLITE_DB_PATH', 'gongkao_test.db')
    
    if not os.path.exists(sqlite_path):
        logger.warning(f"❌ SQLite 数据库文件不存在: {sqlite_path}")
        logger.info("💡 提示: 可以设置环境变量 SQLITE_DB_PATH 指定路径")
        return False, None
    
    logger.info(f"✅ SQLite 数据库文件存在: {sqlite_path}")
    
    sqlite_url = f'sqlite:///{sqlite_path}'
    
    try:
        engine = create_engine(sqlite_url, echo=False)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        
        logger.info("✅ SQLite 数据库连接成功")
        
        # 检查表
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        logger.info(f"📊 数据库表: {', '.join(tables) if tables else '无'}")
        
        # 统计数据
        if 'questions' in tables:
            with engine.connect() as conn:
                result = conn.execute(text("SELECT COUNT(*) FROM questions"))
                count = result.scalar()
                logger.info(f"📦 questions 表: {count} 条记录")
        
        if 'answer_versions' in tables:
            with engine.connect() as conn:
                result = conn.execute(text("SELECT COUNT(*) FROM answer_versions"))
                count = result.scalar()
                logger.info(f"📦 answer_versions 表: {count} 条记录")
        
        return True, sqlite_url
        
    except Exception as e:
        logger.error(f"❌ SQLite 数据库连接失败: {e}")
        return False, None


def check_target_database():
    """检查目标数据库"""
    logger.info("\n" + "="*70)
    logger.info("🎯 检查目标数据库")
    logger.info("="*70)
    
    db_url = os.getenv('DATABASE_URL')
    
    if not db_url:
        logger.error("❌ 未配置 DATABASE_URL 环境变量")
        logger.info("\n💡 请在 .env 文件中配置目标数据库连接：")
        logger.info("   PostgreSQL: DATABASE_URL=postgresql://user:password@host:port/database")
        logger.info("   MySQL: DATABASE_URL=mysql+pymysql://user:password@host:port/database")
        return False, None
    
    # 检查是否是 SQLite
    if db_url.startswith('sqlite'):
        logger.warning("⚠️  目标数据库是 SQLite")
        logger.info("💡 迁移目标应该是 PostgreSQL 或 MySQL")
        return False, None
    
    # 隐藏密码显示
    if '@' in db_url:
        display_url = db_url.split('@')[-1]
    else:
        display_url = db_url
    
    logger.info(f"📍 数据库位置: {display_url}")
    
    # 判断数据库类型
    if 'postgresql' in db_url.lower():
        db_type = "PostgreSQL"
        logger.info("📊 数据库类型: PostgreSQL")
    elif 'mysql' in db_url.lower():
        db_type = "MySQL"
        logger.info("📊 数据库类型: MySQL")
    else:
        db_type = "未知"
        logger.warning(f"⚠️  未知数据库类型: {db_url.split('://')[0]}")
    
    try:
        engine = create_engine(db_url, echo=False)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        
        logger.info("✅ 目标数据库连接成功")
        
        # 检查表
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        if tables:
            logger.info(f"📊 已存在的表: {', '.join(tables)}")
            
            # 统计数据
            if 'questions' in tables:
                with engine.connect() as conn:
                    result = conn.execute(text("SELECT COUNT(*) FROM questions"))
                    count = result.scalar()
                    logger.info(f"📦 questions 表: {count} 条记录")
            
            if 'answer_versions' in tables:
                with engine.connect() as conn:
                    result = conn.execute(text("SELECT COUNT(*) FROM answer_versions"))
                    count = result.scalar()
                    logger.info(f"📦 answer_versions 表: {count} 条记录")
        else:
            logger.info("📊 数据库为空（表不存在，迁移时会自动创建）")
        
        return True, db_url, db_type
        
    except Exception as e:
        logger.error(f"❌ 目标数据库连接失败: {e}")
        logger.info("\n💡 请检查：")
        logger.info("   1. DATABASE_URL 配置是否正确")
        logger.info("   2. 数据库服务是否运行")
        logger.info("   3. 网络连接是否正常")
        logger.info("   4. 用户名和密码是否正确")
        
        # PostgreSQL 特殊提示
        if 'postgresql' in db_url.lower():
            logger.info("\n💡 PostgreSQL 提示：")
            logger.info("   - 如果使用 Supabase，确保使用端口 6543（连接池模式）")
            logger.info("   - 如果使用本地 PostgreSQL，确保服务已启动")
        
        # MySQL 特殊提示
        if 'mysql' in db_url.lower():
            logger.info("\n💡 MySQL 提示：")
            logger.info("   - 确保 MySQL 服务已启动")
            logger.info("   - 确保已安装 pymysql: pip install pymysql")
        
        return False, None, None


def check_dependencies():
    """检查依赖包"""
    logger.info("\n" + "="*70)
    logger.info("📦 检查依赖包")
    logger.info("="*70)
    
    db_url = os.getenv('DATABASE_URL', '')
    
    if 'postgresql' in db_url.lower():
        try:
            import psycopg2
            logger.info("✅ psycopg2 已安装")
        except ImportError:
            logger.warning("⚠️  psycopg2 未安装")
            logger.info("💡 安装命令: pip install psycopg2-binary")
            return False
    
    if 'mysql' in db_url.lower():
        try:
            import pymysql
            logger.info("✅ pymysql 已安装")
        except ImportError:
            logger.warning("⚠️  pymysql 未安装")
            logger.info("💡 安装命令: pip install pymysql")
            return False
    
    return True


def main():
    """主函数"""
    logger.info("="*70)
    logger.info("🔍 数据库连接检查工具")
    logger.info("="*70)
    
    all_ok = True
    
    # 检查 SQLite
    sqlite_ok, sqlite_url = check_sqlite()
    if not sqlite_ok:
        all_ok = False
    
    # 检查目标数据库
    target_ok, target_url, db_type = check_target_database()
    if not target_ok:
        all_ok = False
    
    # 检查依赖
    deps_ok = check_dependencies()
    if not deps_ok:
        all_ok = False
    
    # 总结
    logger.info("\n" + "="*70)
    logger.info("📋 检查结果总结")
    logger.info("="*70)
    
    if all_ok:
        logger.info("✅ 所有检查通过！可以开始迁移")
        logger.info("\n💡 下一步：运行迁移脚本")
        logger.info("   python migrate_database.py")
    else:
        logger.warning("⚠️  部分检查未通过，请修复问题后重试")
    
    logger.info("="*70)
    
    return 0 if all_ok else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logger.info("\n\n❌ 用户中断检查")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ 检查过程中发生错误: {e}", exc_info=True)
        sys.exit(1)
