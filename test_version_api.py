"""
测试版本接口
"""
import requests
import json

def test_version_api(base_url='http://localhost:5000'):
    """测试版本接口"""
    url = f"{base_url}/api/version"
    
    print("=" * 60)
    print("测试版本接口")
    print("=" * 60)
    print(f"URL: {url}")
    print()
    
    try:
        response = requests.get(url, timeout=5)
        print(f"状态码: {response.status_code}")
        print()
        
        if response.status_code == 200:
            data = response.json()
            print("✅ 接口调用成功！")
            print()
            print("版本信息:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            print()
            
            # 验证返回的数据结构
            if 'success' in data and data['success']:
                print("✅ success字段: True")
            else:
                print("❌ success字段: False或不存在")
            
            if 'version' in data:
                version = data['version']
                print(f"✅ 应用版本: {version.get('app_version', 'N/A')}")
                print(f"✅ API版本: {version.get('api_version', 'N/A')}")
                print(f"✅ Python版本: {version.get('python_version', 'N/A')}")
                print(f"✅ Flask版本: {version.get('flask_version', 'N/A')}")
                
                if 'commit' in version:
                    print(f"✅ Git Commit: {version['commit']}")
                if 'branch' in version:
                    print(f"✅ Git Branch: {version['branch']}")
            else:
                print("❌ version字段不存在")
            
            return True
        else:
            print(f"❌ 接口调用失败，状态码: {response.status_code}")
            print(f"响应内容: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到服务器")
        print("   请确保Flask应用正在运行: python app.py")
        return False
    except requests.exceptions.Timeout:
        print("❌ 请求超时")
        return False
    except Exception as e:
        print(f"❌ 发生错误: {e}")
        return False

if __name__ == '__main__':
    import sys
    
    # 可以从命令行参数获取URL
    base_url = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:5000'
    
    success = test_version_api(base_url)
    
    print()
    print("=" * 60)
    if success:
        print("✅ 测试通过！")
    else:
        print("❌ 测试失败！")
    print("=" * 60)
    
    sys.exit(0 if success else 1)
