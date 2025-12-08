"""
数据库配置助手 - 交互式配置向导

帮助用户一步步配置数据库连接
"""
import os
import sys
from pathlib import Path

def print_header(text):
    """打印标题"""
    print("\n" + "="*70)
    print(f"  {text}")
    print("="*70)

def print_step(step, text):
    """打印步骤"""
    print(f"\n📌 步骤 {step}: {text}")

def get_env_file_path():
    """获取 .env 文件路径"""
    return Path('.env')

def read_env_file():
    """读取 .env 文件内容"""
    env_file = get_env_file_path()
    if env_file.exists():
        with open(env_file, 'r', encoding='utf-8') as f:
            return f.read()
    return ""

def write_env_file(content):
    """写入 .env 文件"""
    env_file = get_env_file_path()
    with open(env_file, 'w', encoding='utf-8') as f:
        f.write(content)

def update_env_var(content, key, value):
    """更新环境变量"""
    lines = content.split('\n')
    updated = False
    
    for i, line in enumerate(lines):
        if line.strip().startswith(f'{key}='):
            lines[i] = f"{key}={value}"
            updated = True
            break
    
    if not updated:
        # 添加新行
        if content and not content.endswith('\n'):
            content += '\n'
        content += f"{key}={value}\n"
        return content
    
    return '\n'.join(lines)

def configure_supabase():
    """配置 Supabase PostgreSQL"""
    print_header("配置 Supabase PostgreSQL")
    
    print("\n📋 首先，您需要：")
    print("   1. 访问 https://supabase.com/")
    print("   2. 创建新项目")
    print("   3. 在 Settings → Database 获取连接字符串")
    print("   4. 选择 Connection pooling 模式（端口 6543）")
    
    print("\n💡 连接字符串格式：")
    print("   postgresql://postgres.xxxxx:[PASSWORD]@aws-0-xxx.pooler.supabase.com:6543/postgres")
    
    print_step(1, "输入 Supabase 连接字符串")
    db_url = input("连接字符串: ").strip()
    
    if not db_url:
        print("❌ 连接字符串不能为空")
        return False
    
    if not db_url.startswith('postgresql://'):
        print("❌ 连接字符串格式错误，应以 postgresql:// 开头")
        return False
    
    if ':6543' not in db_url:
        print("⚠️  警告: 连接字符串中未包含端口 6543")
        print("💡 提示: Supabase 必须使用 Connection pooling 模式（端口 6543）")
        confirm = input("是否继续？(yes/no): ").strip().lower()
        if confirm not in ['yes', 'y']:
            return False
    
    # 读取现有 .env 文件
    env_content = read_env_file()
    
    # 更新 DATABASE_URL
    env_content = update_env_var(env_content, 'DATABASE_URL', db_url)
    
    # 写入文件
    write_env_file(env_content)
    
    print("\n✅ 配置已保存到 .env 文件")
    
    # 检查依赖
    print_step(2, "检查依赖包")
    try:
        import psycopg2
        print("✅ psycopg2 已安装")
    except ImportError:
        print("⚠️  psycopg2 未安装")
        install = input("是否现在安装？(yes/no): ").strip().lower()
        if install in ['yes', 'y']:
            print("正在安装 psycopg2-binary...")
            os.system("pip install psycopg2-binary")
            print("✅ 安装完成")
        else:
            print("💡 稍后请运行: pip install psycopg2-binary")
    
    return True

def configure_local_postgresql():
    """配置本地 PostgreSQL"""
    print_header("配置本地 PostgreSQL")
    
    print_step(1, "输入数据库连接信息")
    
    host = input("数据库主机 (默认: localhost): ").strip() or "localhost"
    port = input("数据库端口 (默认: 5432): ").strip() or "5432"
    database = input("数据库名称 (默认: gongkao_db): ").strip() or "gongkao_db"
    username = input("数据库用户名 (默认: postgres): ").strip() or "postgres"
    password = input("数据库密码: ").strip()
    
    if not password:
        print("❌ 密码不能为空")
        return False
    
    db_url = f"postgresql://{username}:{password}@{host}:{port}/{database}"
    
    # 读取现有 .env 文件
    env_content = read_env_file()
    
    # 更新 DATABASE_URL
    env_content = update_env_var(env_content, 'DATABASE_URL', db_url)
    
    # 写入文件
    write_env_file(env_content)
    
    print("\n✅ 配置已保存到 .env 文件")
    
    # 检查依赖
    print_step(2, "检查依赖包")
    try:
        import psycopg2
        print("✅ psycopg2 已安装")
    except ImportError:
        print("⚠️  psycopg2 未安装")
        install = input("是否现在安装？(yes/no): ").strip().lower()
        if install in ['yes', 'y']:
            print("正在安装 psycopg2-binary...")
            os.system("pip install psycopg2-binary")
            print("✅ 安装完成")
        else:
            print("💡 稍后请运行: pip install psycopg2-binary")
    
    return True

def configure_mysql():
    """配置 MySQL"""
    print_header("配置 MySQL")
    
    print_step(1, "输入数据库连接信息")
    
    host = input("数据库主机 (默认: localhost): ").strip() or "localhost"
    port = input("数据库端口 (默认: 3306): ").strip() or "3306"
    database = input("数据库名称 (默认: gongkao_db): ").strip() or "gongkao_db"
    username = input("数据库用户名 (默认: root): ").strip() or "root"
    password = input("数据库密码: ").strip()
    
    if not password:
        print("❌ 密码不能为空")
        return False
    
    db_url = f"mysql+pymysql://{username}:{password}@{host}:{port}/{database}?charset=utf8mb4"
    
    # 读取现有 .env 文件
    env_content = read_env_file()
    
    # 更新 DATABASE_URL
    env_content = update_env_var(env_content, 'DATABASE_URL', db_url)
    
    # 写入文件
    write_env_file(env_content)
    
    print("\n✅ 配置已保存到 .env 文件")
    
    # 检查依赖
    print_step(2, "检查依赖包")
    try:
        import pymysql
        print("✅ pymysql 已安装")
    except ImportError:
        print("⚠️  pymysql 未安装")
        install = input("是否现在安装？(yes/no): ").strip().lower()
        if install in ['yes', 'y']:
            print("正在安装 pymysql...")
            os.system("pip install pymysql")
            print("✅ 安装完成")
        else:
            print("💡 稍后请运行: pip install pymysql")
    
    return True

def configure_sqlite():
    """配置 SQLite（保持现状）"""
    print_header("继续使用 SQLite")
    
    print("\n✅ 将继续使用 SQLite 数据库")
    print("💡 提示: 如果需要迁移到 PostgreSQL/MySQL，可以稍后运行迁移脚本")
    
    return True

def test_connection():
    """测试数据库连接"""
    print_header("测试数据库连接")
    
    from dotenv import load_dotenv
    load_dotenv()
    
    db_url = os.getenv('DATABASE_URL')
    
    if not db_url:
        print("❌ 未配置 DATABASE_URL")
        return False
    
    print(f"📍 数据库 URL: {db_url.split('@')[-1] if '@' in db_url else db_url}")
    
    try:
        from sqlalchemy import create_engine, text
        
        engine = create_engine(db_url, echo=False)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        
        print("✅ 数据库连接成功！")
        
        # 判断数据库类型
        if 'postgresql' in db_url.lower():
            print("📊 数据库类型: PostgreSQL")
        elif 'mysql' in db_url.lower():
            print("📊 数据库类型: MySQL")
        elif 'sqlite' in db_url.lower():
            print("📊 数据库类型: SQLite")
        
        return True
        
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        print("\n💡 请检查：")
        print("   1. 数据库服务是否正在运行")
        print("   2. 连接信息是否正确")
        print("   3. 网络连接是否正常")
        return False

def main():
    """主函数"""
    print_header("数据库配置助手")
    
    print("\n请选择要配置的数据库类型：")
    print("\n  1. Supabase PostgreSQL（推荐）⭐")
    print("     - 免费、云端、自动备份")
    print("     - 适合生产环境")
    print("\n  2. 本地 PostgreSQL")
    print("     - 完全控制、无网络延迟")
    print("     - 适合本地开发")
    print("\n  3. MySQL")
    print("     - 广泛使用、资源占用少")
    print("     - 适合已有 MySQL 环境")
    print("\n  4. 继续使用 SQLite")
    print("     - 保持现状，不迁移")
    
    choice = input("\n请选择 (1-4): ").strip()
    
    success = False
    
    if choice == '1':
        success = configure_supabase()
    elif choice == '2':
        success = configure_local_postgresql()
    elif choice == '3':
        success = configure_mysql()
    elif choice == '4':
        success = configure_sqlite()
    else:
        print("❌ 无效的选择")
        return
    
    if not success:
        print("\n❌ 配置失败")
        return
    
    # 测试连接
    if choice != '4':  # SQLite 不需要测试远程连接
        test_now = input("\n是否现在测试连接？(yes/no): ").strip().lower()
        if test_now in ['yes', 'y']:
            test_connection()
    
    # 总结
    print_header("配置完成")
    
    print("\n✅ 数据库配置已完成！")
    
    if choice != '4':
        print("\n📋 下一步：")
        print("   1. 运行检查脚本: python check_database.py")
        print("   2. 运行迁移脚本: python migrate_database.py")
        print("   3. 启动应用: python app.py")
    else:
        print("\n💡 提示: 如果将来需要迁移，可以运行:")
        print("   python setup_database.py")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ 用户取消配置")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 配置过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
