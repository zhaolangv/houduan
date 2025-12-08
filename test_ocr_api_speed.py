"""
测试OCR API速度（专门的OCR服务 vs Vision模型）
"""
import requests
import json
import base64
import sys
import os
import time
from statistics import mean

# 修复Windows控制台编码问题
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

BASE_URL = 'http://localhost:5000'

print("="*70)
print("🚀 OCR API速度测试 - 专门的OCR服务 vs Vision模型")
print("="*70)

# 加载测试图片
ceshi_dir = 'uploads/ceshi'
test_image = None
for file in os.listdir(ceshi_dir):
    if file.lower().endswith(('.png', '.jpg', '.jpeg')):
        test_image = os.path.join(ceshi_dir, file)
        break

if not test_image:
    print("❌ 未找到测试图片")
    sys.exit(1)

print(f"📷 测试图片: {test_image}")
file_size = os.path.getsize(test_image) / 1024
print(f"图片大小: {file_size:.2f} KB\n")

# 准备图片数据
with open(test_image, 'rb') as f:
    image_data = f.read()
    image_base64 = base64.b64encode(image_data).decode('utf-8')

# 测试：使用优化后的接口（优先OCR API）
print("="*70)
print("📊 测试：优化后的接口（优先OCR API，失败fallback到Vision）")
print("="*70)

times = []
for i in range(3):
    print(f"  第 {i+1}/3 次...", end=' ', flush=True)
    data = {
        'image': image_base64,
        'question_type': 'TEXT',
        'force_reanalyze': True
    }
    start = time.time()
    try:
        response = requests.post(
            f'{BASE_URL}/api/questions/analyze',
            json=data,
            headers={'Content-Type': 'application/json'},
            timeout=60
        )
        elapsed = time.time() - start
        times.append(elapsed)
        if response.status_code == 200:
            result = response.json()
            extraction_method = result.get('extraction_method', 'unknown')
            question_text = result.get('question_text', '')
            options = result.get('options', [])
            print(f"✅ {elapsed:.2f}秒 - {extraction_method}, {len(options)}选项")
            if question_text:
                print(f"     题干: {question_text[:50]}...")
        else:
            print(f"❌ {elapsed:.2f}秒 - HTTP {response.status_code}")
    except Exception as e:
        elapsed = time.time() - start
        times.append(elapsed)
        print(f"❌ {elapsed:.2f}秒 - {str(e)[:50]}")

if times:
    avg_time = mean(times)
    min_time = min(times)
    max_time = max(times)
    print(f"\n📈 统计:")
    print(f"  平均时间: {avg_time:.2f}秒")
    print(f"  最快:     {min_time:.2f}秒")
    print(f"  最慢:     {max_time:.2f}秒")
    
    if avg_time < 10:
        print(f"\n🎉 成功！平均速度 {avg_time:.1f}秒，达到几秒钟的目标！")
    elif avg_time < 15:
        print(f"\n✅ 不错！平均速度 {avg_time:.1f}秒，比之前快很多")
    else:
        print(f"\n⚠️ 还需要优化，当前平均速度 {avg_time:.1f}秒")

print(f"\n{'='*70}")

