"""
调试OCR失败原因
"""
import requests
import json
import base64
import sys
import os

# 修复Windows控制台编码问题
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

BASE_URL = 'http://localhost:5000'

# 加载一张测试图片
ceshi_dir = 'uploads/ceshi'
test_images = []
for file in os.listdir(ceshi_dir):
    if file.lower().endswith(('.png', '.jpg', '.jpeg')):
        test_images.append(os.path.join(ceshi_dir, file))
        break

if not test_images:
    print("❌ 未找到测试图片")
    sys.exit(1)

print(f"📷 使用测试图片: {test_images[0]}")
print(f"图片大小: {os.path.getsize(test_images[0]) / 1024:.2f} KB\n")

# 读取图片并编码为base64
with open(test_images[0], 'rb') as f:
    image_data = f.read()
    image_base64 = base64.b64encode(image_data).decode('utf-8')

data = {
    'questions': [{
        'image': image_base64,
        'question_type': 'TEXT',
        'force_reanalyze': True
    }]
}

print("🚀 发送OCR请求...")
try:
    response = requests.post(
        f'{BASE_URL}/api/questions/analyze/batch',
        json=data,
        headers={'Content-Type': 'application/json'},
        timeout=60
    )
    
    print(f"状态码: {response.status_code}")
    print(f"响应头: {dict(response.headers)}\n")
    
    if response.status_code == 200:
        result = response.json()
        print("=" * 70)
        print("📋 完整响应:")
        print("=" * 70)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("=" * 70)
        
        # 分析结果
        total = result.get('total', 0)
        success_count = result.get('success_count', 0)
        failed_count = result.get('failed_count', 0)
        
        print(f"\n📊 统计:")
        print(f"  总数: {total}")
        print(f"  成功: {success_count}")
        print(f"  失败: {failed_count}")
        
        if result.get('results'):
            first_result = result['results'][0]
            print(f"\n📝 第一个结果:")
            print(f"  成功: {first_result.get('success', False)}")
            
            if first_result.get('error'):
                error = first_result['error']
                print(f"  错误代码: {error.get('code')}")
                print(f"  错误信息: {error.get('message')}")
            
            if first_result.get('question'):
                question = first_result['question']
                print(f"  题目ID: {question.get('id')}")
                print(f"  题干: {question.get('question_text', '')[:100]}...")
                print(f"  选项数: {len(question.get('options', []))}")
    else:
        print(f"❌ HTTP错误: {response.status_code}")
        print(f"响应内容: {response.text[:500]}")
        
except Exception as e:
    print(f"❌ 请求失败: {e}")
    import traceback
    traceback.print_exc()

