"""
调试JSON请求格式问题
用于测试批量提取接口的JSON请求格式
"""
import requests
import json
import base64
import os
from pathlib import Path

API_BASE = 'http://localhost:5000'
TEST_IMAGE_DIR = 'uploads/ceshi'

def image_to_base64(image_path: str) -> str:
    """将图片转换为base64编码"""
    with open(image_path, 'rb') as f:
        image_data = f.read()
        base64_data = base64.b64encode(image_data).decode('utf-8')
        return f"data:image/jpeg;base64,{base64_data}"

def test_json_request():
    """测试JSON格式请求"""
    print("=" * 60)
    print("🔍 调试JSON请求格式")
    print("=" * 60)
    
    # 加载测试图片
    if not os.path.exists(TEST_IMAGE_DIR):
        print(f"❌ 测试图片目录不存在: {TEST_IMAGE_DIR}")
        return
    
    image_files = []
    for ext in ['jpg', 'jpeg', 'png', 'bmp']:
        image_files.extend(Path(TEST_IMAGE_DIR).glob(f'*.{ext}'))
        image_files.extend(Path(TEST_IMAGE_DIR).glob(f'*.{ext.upper()}'))
    
    image_files = [str(f) for f in image_files if '_preprocessed' not in str(f)]
    
    if len(image_files) == 0:
        print("❌ 没有找到测试图片")
        return
    
    # 只测试第一张图片
    test_image = image_files[0]
    print(f"📷 使用测试图片: {test_image}")
    
    # 构建JSON请求
    images_data = []
    base64_data = image_to_base64(test_image)
    
    print(f"\n📊 检查base64数据:")
    print(f"   - 总长度: {len(base64_data)} 字符")
    print(f"   - 前缀: {base64_data[:50]}...")
    print(f"   - 是否包含data:image: {'data:image' in base64_data}")
    
    images_data.append({
        'filename': os.path.basename(test_image),
        'data': base64_data
    })
    
    payload = {
        'images': images_data,
        'max_workers': 3
    }
    
    print(f"\n📦 请求payload结构:")
    print(f"   - images数组长度: {len(payload['images'])}")
    print(f"   - 第一个图片keys: {list(payload['images'][0].keys())}")
    print(f"   - max_workers: {payload['max_workers']}")
    
    # 验证JSON序列化
    try:
        json_str = json.dumps(payload)
        print(f"   - JSON序列化成功，长度: {len(json_str)} 字符")
    except Exception as e:
        print(f"   ❌ JSON序列化失败: {e}")
        return
    
    # 发送请求
    print(f"\n🚀 发送请求到: {API_BASE}/api/questions/extract/batch")
    
    try:
        response = requests.post(
            f"{API_BASE}/api/questions/extract/batch",
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=300
        )
        
        print(f"\n📥 响应信息:")
        print(f"   - 状态码: {response.status_code}")
        print(f"   - Content-Type: {response.headers.get('Content-Type', 'unknown')}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ 请求成功")
            print(f"   - success: {result.get('success')}")
            if result.get('statistics'):
                stats = result['statistics']
                print(f"   - 总数: {stats.get('total')}")
                print(f"   - 成功: {stats.get('success_count')}")
                print(f"   - 失败: {stats.get('failed_count')}")
        else:
            print(f"   ❌ 请求失败")
            try:
                error_data = response.json()
                print(f"   - 错误信息: {error_data.get('error', '未知错误')}")
                if error_data.get('details'):
                    print(f"   - 错误详情: {error_data.get('details')}")
            except:
                print(f"   - 响应文本: {response.text[:500]}")
    
    except Exception as e:
        print(f"   ❌ 请求异常: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_json_request()
