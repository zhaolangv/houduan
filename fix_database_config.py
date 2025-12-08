"""
快速修复数据库配置脚本

用于检查和修复 Supabase 连接字符串配置
"""
import os
import re
from pathlib import Path
from dotenv import load_dotenv

def print_header(text):
    """打印标题"""
    print("\n" + "="*70)
    print(f"  {text}")
    print("="*70)

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

def update_env_file(content, key, value):
    """更新环境变量"""
    lines = content.split('\n')
    updated = False
    
    for i, line in enumerate(lines):
        if line.strip().startswith(f'{key}='):
            lines[i] = f"{key}={value}"
            updated = True
            break
    
    if not updated:
        if content and not content.endswith('\n'):
            content += '\n'
        content += f"{key}={value}\n"
        return content
    
    return '\n'.join(lines)

def check_database_url(db_url):
    """检查数据库连接字符串格式"""
    issues = []
    
    if not db_url:
        issues.append("❌ DATABASE_URL 未配置")
        return False, issues
    
    # 检查是否包含密码占位符
    if '[YOUR-PASSWORD]' in db_url:
        issues.append("❌ 密码未替换：连接字符串中仍包含 [YOUR-PASSWORD]")
        issues.append("   请在连接字符串中替换 [YOUR-PASSWORD] 为实际密码")
    
    # 检查用户名格式（Supabase）
    if 'supabase' in db_url.lower():
        # 检查是否是错误的用户名格式
        if re.search(r'postgresql://postgres:[^@]+@', db_url) and 'postgres.' not in db_url:
            issues.append("❌ 用户名格式错误：应该是 postgres.项目标识，不是 postgres")
            issues.append("   正确的用户名格式：postgres.jhursbbnelxthwezcetg")
    
    # 检查是否包含 pooler（连接池模式）
    if 'supabase' in db_url.lower() and 'pooler' not in db_url.lower():
        issues.append("⚠️  可能使用了直连模式，建议使用连接池模式（pooler.supabase.com）")
    
    return len(issues) == 0, issues

def fix_database_url():
    """修复数据库连接字符串"""
    print_header("修复 Supabase 数据库配置")
    
    # 读取当前配置
    env_content = read_env_file()
    load_dotenv()
    current_url = os.getenv('DATABASE_URL', '')
    
    if current_url:
        print(f"\n📋 当前配置的 DATABASE_URL:")
        # 隐藏密码显示
        if '@' in current_url:
            display_url = current_url.split('@')[0].split(':')[-1] + '@' + current_url.split('@')[1]
            print(f"   {display_url}")
        else:
            print(f"   {current_url}")
        
        # 检查配置
        is_ok, issues = check_database_url(current_url)
        
        if not is_ok:
            print("\n⚠️  发现以下问题：")
            for issue in issues:
                print(f"   {issue}")
            
            print("\n" + "="*70)
            print("🔧 修复步骤")
            print("="*70)
            
            print("\n步骤 1: 从 Supabase 页面复制连接字符串")
            print("   1. 打开 Supabase Dashboard")
            print("   2. 进入 Project Settings → Connect to your project")
            print("   3. 选择 'Session pooler' 模式")
            print("   4. 复制连接字符串")
            print("\n   连接字符串应该类似：")
            print("   postgresql://postgres.jhursbbnelxthwezcetg:[YOUR-PASSWORD]@aws-1-xxx.pooler.supabase.com:5432/postgres")
            
            print("\n步骤 2: 替换密码并配置")
            print("   将 [YOUR-PASSWORD] 替换为实际密码")
            
            new_url = input("\n请输入修复后的连接字符串（包含密码）: ").strip()
            
            if new_url:
                # 验证格式
                if not new_url.startswith('postgresql://'):
                    print("❌ 连接字符串格式错误，应以 postgresql:// 开头")
                    return False
                
                if '[YOUR-PASSWORD]' in new_url:
                    print("❌ 请先替换 [YOUR-PASSWORD] 为实际密码")
                    return False
                
                # 检查用户名格式
                if 'supabase' in new_url.lower():
                    if re.search(r'postgresql://postgres:[^\.@]+@', new_url):
                        print("❌ 用户名格式错误：应该是 postgres.项目标识")
                        print("   例如：postgres.jhursbbnelxthwezcetg")
                        confirm = input("是否仍要继续？(yes/no): ").strip().lower()
                        if confirm not in ['yes', 'y']:
                            return False
                
                # 更新配置
                env_content = update_env_file(env_content, 'DATABASE_URL', new_url)
                write_env_file(env_content)
                
                print("\n✅ 配置已更新！")
                
                # 测试连接
                test_now = input("\n是否现在测试连接？(yes/no): ").strip().lower()
                if test_now in ['yes', 'y']:
                    test_connection(new_url)
                
                return True
        else:
            print("\n✅ 配置看起来正确！")
            
            # 测试连接
            test_now = input("\n是否测试连接？(yes/no): ").strip().lower()
            if test_now in ['yes', 'y']:
                test_connection(current_url)
            
            return True
    else:
        print("\n⚠️  未找到 DATABASE_URL 配置")
        print("\n请按以下步骤配置：")
        print("   1. 从 Supabase 页面复制连接字符串")
        print("   2. 替换 [YOUR-PASSWORD] 为实际密码")
        print("   3. 运行: python setup_database.py")
        
        return False

def write_env_file(content):
    """写入 .env 文件"""
    env_file = get_env_file_path()
    with open(env_file, 'w', encoding='utf-8') as f:
        f.write(content)

def test_connection(db_url):
    """测试数据库连接"""
    print_header("测试数据库连接")
    
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
        
        return True
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ 数据库连接失败: {error_msg}")
        
        if 'password authentication failed' in error_msg.lower():
            print("\n💡 密码认证失败，可能的原因：")
            print("   1. 用户名格式错误（应该是 postgres.项目标识）")
            print("   2. 密码不正确")
            print("   3. 密码中的 [YOUR-PASSWORD] 未替换")
            
            if 'postgres' in error_msg and 'postgres.' not in db_url:
                print("\n⚠️  检测到用户名格式可能错误")
                print("   Supabase 的用户名应该是：postgres.项目标识")
                print("   例如：postgres.jhursbbnelxthwezcetg")
        
        return False

def main():
    """主函数"""
    print_header("Supabase 数据库配置修复工具")
    
    print("\n这个工具将帮助您：")
    print("   1. 检查当前数据库配置")
    print("   2. 发现配置问题")
    print("   3. 修复连接字符串格式")
    print("   4. 测试数据库连接")
    
    try:
        success = fix_database_url()
        
        if success:
            print("\n" + "="*70)
            print("✅ 配置修复完成！")
            print("="*70)
            print("\n下一步：")
            print("   1. 运行检查: python check_database.py")
            print("   2. 运行迁移: python migrate_database.py（如果有 SQLite 数据）")
            print("   3. 启动应用: python app.py")
        else:
            print("\n" + "="*70)
            print("⚠️  配置未完成")
            print("="*70)
            print("\n请按照提示手动配置，或运行: python setup_database.py")
    
    except KeyboardInterrupt:
        print("\n\n❌ 用户取消操作")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
