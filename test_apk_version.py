"""
测试APK版本更新功能
"""
import requests
import json
import os

def test_version_check(base_url='http://localhost:5000', client_version=None):
    """测试版本检查接口"""
    print("=" * 60)
    print("测试版本检查接口")
    print("=" * 60)
    
    url = f"{base_url}/api/version"
    if client_version:
        url += f"?client_version={client_version}"
    
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
            
            if 'update' in data:
                update = data['update']
                print(f"更新检查:")
                print(f"  - 需要更新: {update.get('required', False)}")
                print(f"  - 最新版本: {update.get('latest_version', 'N/A')}")
                print(f"  - 下载链接: {update.get('download_url', 'N/A')}")
                if update.get('release_notes'):
                    print(f"  - 更新说明: {update.get('release_notes')}")
            
            return True
        else:
            print(f"❌ 接口调用失败，状态码: {response.status_code}")
            print(f"响应内容: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 发生错误: {e}")
        return False


def test_apk_info(base_url='http://localhost:5000'):
    """测试APK信息查询接口"""
    print("=" * 60)
    print("测试APK信息查询接口")
    print("=" * 60)
    
    url = f"{base_url}/api/apk/info"
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
            print("APK信息:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            return True
        elif response.status_code == 404:
            print("⚠️  APK信息不存在（这是正常的，如果还没有上传APK）")
            return True
        else:
            print(f"❌ 接口调用失败，状态码: {response.status_code}")
            print(f"响应内容: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 发生错误: {e}")
        return False


def test_apk_download(base_url='http://localhost:5000', save_path='test_download.apk'):
    """测试APK下载接口"""
    print("=" * 60)
    print("测试APK下载接口")
    print("=" * 60)
    
    url = f"{base_url}/api/apk/download"
    print(f"URL: {url}")
    print()
    
    try:
        response = requests.get(url, timeout=30, stream=True)
        print(f"状态码: {response.status_code}")
        print()
        
        if response.status_code == 200:
            # 保存文件
            total_size = int(response.headers.get('content-length', 0))
            print(f"文件大小: {total_size / 1024 / 1024:.2f} MB")
            print(f"保存到: {save_path}")
            
            with open(save_path, 'wb') as f:
                downloaded = 0
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            print(f"\r下载进度: {percent:.1f}%", end='', flush=True)
            
            print("\n✅ APK下载成功！")
            return True
        elif response.status_code == 404:
            print("⚠️  APK文件不存在（这是正常的，如果还没有上传APK）")
            return True
        else:
            print(f"❌ 下载失败，状态码: {response.status_code}")
            print(f"响应内容: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 发生错误: {e}")
        return False


def test_apk_upload(base_url='http://localhost:5000', apk_path=None):
    """测试APK上传接口"""
    print("=" * 60)
    print("测试APK上传接口")
    print("=" * 60)
    
    if not apk_path or not os.path.exists(apk_path):
        print("⚠️  跳过APK上传测试（未提供APK文件路径）")
        print("   使用方法: python test_apk_version.py --upload /path/to/app.apk")
        return True
    
    url = f"{base_url}/api/apk/upload"
    print(f"URL: {url}")
    print(f"APK文件: {apk_path}")
    print()
    
    try:
        with open(apk_path, 'rb') as f:
            files = {'file': (os.path.basename(apk_path), f, 'application/vnd.android.package-archive')}
            data = {
                'version': '2.0.0',
                'release_notes': '测试版本，用于功能验证'
            }
            
            response = requests.post(url, files=files, data=data, timeout=60)
            print(f"状态码: {response.status_code}")
            print()
            
            if response.status_code == 200:
                result = response.json()
                print("✅ APK上传成功！")
                print()
                print("上传结果:")
                print(json.dumps(result, indent=2, ensure_ascii=False))
                return True
            else:
                print(f"❌ 上传失败，状态码: {response.status_code}")
                print(f"响应内容: {response.text}")
                return False
                
    except Exception as e:
        print(f"❌ 发生错误: {e}")
        return False


def main():
    import sys
    
    base_url = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:5000'
    apk_path = None
    
    # 检查是否有上传参数
    if '--upload' in sys.argv:
        idx = sys.argv.index('--upload')
        if idx + 1 < len(sys.argv):
            apk_path = sys.argv[idx + 1]
    
    print("\n" + "=" * 60)
    print("APK版本更新功能测试")
    print("=" * 60)
    print(f"API地址: {base_url}")
    print()
    
    results = []
    
    # 1. 测试版本检查（不带客户端版本）
    print("\n[测试1] 版本检查（不带客户端版本）")
    results.append(("版本检查（无客户端版本）", test_version_check(base_url)))
    
    # 2. 测试版本检查（带旧版本）
    print("\n[测试2] 版本检查（客户端版本: 1.0.0）")
    results.append(("版本检查（旧版本）", test_version_check(base_url, "1.0.0")))
    
    # 3. 测试版本检查（带最新版本）
    print("\n[测试3] 版本检查（客户端版本: 2.0.0）")
    results.append(("版本检查（最新版本）", test_version_check(base_url, "2.0.0")))
    
    # 4. 测试APK信息查询
    print("\n[测试4] APK信息查询")
    results.append(("APK信息查询", test_apk_info(base_url)))
    
    # 5. 测试APK上传（如果提供了APK文件）
    if apk_path:
        print("\n[测试5] APK上传")
        results.append(("APK上传", test_apk_upload(base_url, apk_path)))
    
    # 6. 测试APK下载
    print("\n[测试6] APK下载")
    results.append(("APK下载", test_apk_download(base_url)))
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status} - {name}")
    
    print()
    print(f"总计: {passed}/{total} 项测试通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！")
    else:
        print("\n⚠️  部分测试未通过，请检查")
    
    return 0 if passed == total else 1


if __name__ == '__main__':
    import sys
    sys.exit(main())
