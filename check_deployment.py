"""
部署前检查脚本
用于验证Supabase配置和部署准备
"""
import os
import sys
from dotenv import load_dotenv

def check_env_file():
    """检查.env文件是否存在"""
    if not os.path.exists('.env'):
        print("❌ .env文件不存在")
        print("   请复制 env.example 为 .env 并配置")
        return False
    print("✅ .env文件存在")
    return True

def check_database_config():
    """检查数据库配置"""
    load_dotenv()
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        print("❌ DATABASE_URL未配置")
        return False
    
    # 检查是否是Supabase连接字符串
    if 'supabase' not in database_url.lower():
        print("⚠️  DATABASE_URL不是Supabase连接字符串")
        print("   当前值:", database_url[:50] + "...")
        return False
    
    # 检查用户名格式
    if 'postgres.' in database_url:
        print("✅ DATABASE_URL格式正确（包含项目标识）")
    else:
        print("⚠️  DATABASE_URL用户名格式可能不正确")
        print("   应该是: postgres.[PROJECT-REF]")
    
    # 检查是否包含密码占位符
    if '[YOUR-PASSWORD]' in database_url:
        print("❌ DATABASE_URL包含密码占位符，请替换为实际密码")
        return False
    
    print("✅ DATABASE_URL已配置")
    return True

def check_supabase_storage():
    """检查Supabase Storage配置"""
    load_dotenv()
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_ANON_KEY')
    
    if not supabase_url:
        print("❌ SUPABASE_URL未配置")
        return False
    
    if '[PROJECT-REF]' in supabase_url:
        print("❌ SUPABASE_URL包含占位符，请替换为实际项目URL")
        return False
    
    if not supabase_key:
        print("❌ SUPABASE_ANON_KEY未配置")
        return False
    
    if '你的' in supabase_key or '[PROJECT-REF]' in supabase_key:
        print("❌ SUPABASE_ANON_KEY包含占位符，请替换为实际密钥")
        return False
    
    print("✅ Supabase Storage配置已设置")
    return True

def check_ai_config():
    """检查AI配置"""
    load_dotenv()
    ai_provider = os.getenv('AI_PROVIDER')
    ai_api_key = os.getenv('AI_API_KEY')
    
    if not ai_provider:
        print("❌ AI_PROVIDER未配置")
        return False
    
    if ai_provider not in ['deepseek', 'openai']:
        print(f"⚠️  未知的AI提供商: {ai_provider}")
    
    if not ai_api_key:
        print("❌ AI_API_KEY未配置")
        return False
    
    if 'your' in ai_api_key.lower() or 'sk-' not in ai_api_key:
        print("⚠️  AI_API_KEY可能未正确配置")
    
    print(f"✅ AI配置已设置（提供商: {ai_provider}）")
    return True

def check_requirements():
    """检查requirements.txt"""
    if not os.path.exists('requirements.txt'):
        print("❌ requirements.txt不存在")
        return False
    
    with open('requirements.txt', 'r', encoding='utf-8') as f:
        content = f.read()
    
    required_packages = [
        'flask',
        'flask-sqlalchemy',
        'psycopg2-binary',
        'supabase',
        'python-dotenv'
    ]
    
    missing = []
    for pkg in required_packages:
        if pkg not in content:
            missing.append(pkg)
    
    if missing:
        print(f"⚠️  requirements.txt可能缺少: {', '.join(missing)}")
    else:
        print("✅ requirements.txt包含必需依赖")
    
    return True

def check_app_file():
    """检查app.py是否存在"""
    if not os.path.exists('app.py'):
        print("❌ app.py不存在")
        return False
    print("✅ app.py存在")
    return True

def check_database_connection():
    """测试数据库连接"""
    try:
        load_dotenv()
        database_url = os.getenv('DATABASE_URL')
        
        if not database_url:
            print("⚠️  跳过数据库连接测试（DATABASE_URL未配置）")
            return True
        
        from sqlalchemy import create_engine, text
        
        # 转换postgres://为postgresql://
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        
        engine = create_engine(database_url, connect_args={'connect_timeout': 5})
        
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        
        print("✅ 数据库连接成功")
        return True
    except Exception as e:
        print(f"❌ 数据库连接失败: {str(e)[:100]}")
        return False

def main():
    """主检查流程"""
    print("=" * 60)
    print("部署前检查")
    print("=" * 60)
    print()
    
    checks = [
        ("环境文件", check_env_file),
        ("应用文件", check_app_file),
        ("依赖文件", check_requirements),
        ("数据库配置", check_database_config),
        ("Supabase Storage配置", check_supabase_storage),
        ("AI配置", check_ai_config),
        ("数据库连接", check_database_connection),
    ]
    
    results = []
    for name, check_func in checks:
        print(f"[检查] {name}...")
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ 检查失败: {e}")
            results.append((name, False))
        print()
    
    # 总结
    print("=" * 60)
    print("检查总结")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status} - {name}")
    
    print()
    print(f"总计: {passed}/{total} 项检查通过")
    
    if passed == total:
        print()
        print("🎉 所有检查通过！可以开始部署了。")
        print()
        print("下一步：")
        print("1. 将代码推送到GitHub")
        print("2. 在Railway/Render/Fly.io创建项目")
        print("3. 配置环境变量")
        print("4. 部署应用")
        print()
        print("详细步骤请参考: Supabase部署指南.md")
        return 0
    else:
        print()
        print("⚠️  部分检查未通过，请修复后重试")
        print()
        print("常见问题：")
        print("1. 检查.env文件中的配置是否正确")
        print("2. 确认所有占位符已替换为实际值")
        print("3. 验证数据库连接字符串格式")
        return 1

if __name__ == '__main__':
    sys.exit(main())
