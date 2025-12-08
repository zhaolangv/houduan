"""快速测试AI配置是否正确"""
import os
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ 已加载 .env 文件")
except ImportError:
    print("⚠️  未安装 python-dotenv，将使用系统环境变量")
except Exception as e:
    print(f"⚠️  加载 .env 文件时出错: {e}")

api_key = os.getenv('AI_API_KEY', '')
provider = os.getenv('AI_PROVIDER', 'deepseek')
model = os.getenv('AI_MODEL', 'deepseek-chat')

print(f"\n📊 当前配置:")
print(f"   AI_API_KEY: {'已设置 (长度: ' + str(len(api_key)) + ')' if api_key else '❌ 未设置'}")
print(f"   AI_PROVIDER: {provider}")
print(f"   AI_MODEL: {model}")

if api_key:
    print(f"\n✅ AI服务已配置，可以运行 test_local_ocr.py")
    print(f"   运行命令: python test_local_ocr.py")
else:
    print(f"\n❌ AI_API_KEY 未设置")
    print(f"   请在 .env 文件中设置 AI_API_KEY=sk-...")
