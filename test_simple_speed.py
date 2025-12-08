"""
简单速度测试 - 只测试单张图片
"""
import requests
import json
import base64
import sys
import os
import time

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

image_path = test_images[0]
print(f"📷 测试图片: {os.path.basename(image_path)}")
print(f"图片大小: {os.path.getsize(image_path) / 1024:.2f} KB\n")

# 读取图片
with open(image_path, 'rb') as f:
    image_data = f.read()
    image_base64 = base64.b64encode(image_data).decode('utf-8')

data = {
    'questions': [{
        'image': image_base64,
        'question_type': 'TEXT',
        'force_reanalyze': True
    }]
}

print("🚀 发送请求（超时60秒）...")
start_time = time.time()

try:
    response = requests.post(
        f'{BASE_URL}/api/questions/analyze/batch',
        json=data,
        headers={'Content-Type': 'application/json'},
        timeout=60
    )
    elapsed = time.time() - start_time
    
    print(f"\n✅ 请求完成，耗时: {elapsed:.2f}秒\n")
    
    if response.status_code == 200:
        result = response.json()
        print("="*70)
        print("📋 响应结果:")
        print("="*70)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        if result.get('success_count', 0) > 0:
            question = result.get('results', [{}])[0].get('question', {})
            print(f"\n✅ 提取成功!")
            print(f"  提取方法: {question.get('extraction_method', 'unknown')}")
            print(f"  题干: {question.get('question_text', '')[:100]}...")
            print(f"  选项数: {len(question.get('options', []))}")
        else:
            error = result.get('results', [{}])[0].get('error', {})
            print(f"\n❌ 提取失败: {error.get('message', '未知错误')}")
    else:
        print(f"❌ HTTP错误: {response.status_code}")
        print(f"响应: {response.text[:500]}")
        
except requests.exceptions.Timeout:
    elapsed = time.time() - start_time
    print(f"\n⏱️ 请求超时（{elapsed:.2f}秒）")
    print("可能原因：")
    print("1. 快速OCR初始化时间过长（首次使用PaddleOCR需要下载模型）")
    print("2. AI OCR响应时间过长")
    print("3. 服务可能卡住")
    
except Exception as e:
    elapsed = time.time() - start_time
    print(f"\n❌ 请求失败（{elapsed:.2f}秒）: {e}")
    import traceback
    traceback.print_exc()

