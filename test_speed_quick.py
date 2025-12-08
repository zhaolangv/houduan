"""
快速速度测试 - 只测试单张图片
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
print("="*70)
print("🚀 OCR速度快速测试（优化后）")
print("="*70)
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

print("测试3次，取平均值...\n")
times = []
success_count = 0

for i in range(3):
    print(f"第 {i+1}/3 次...", end=' ', flush=True)
    start_time = time.time()
    
    try:
        response = requests.post(
            f'{BASE_URL}/api/questions/analyze/batch',
            json=data,
            headers={'Content-Type': 'application/json'},
            timeout=60
        )
        elapsed = time.time() - start_time
        times.append(elapsed)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success_count', 0) > 0:
                success_count += 1
                question = result.get('results', [{}])[0].get('question', {})
                method = question.get('extraction_method', 'unknown')
                options_count = len(question.get('options', []))
                print(f"✅ {elapsed:.2f}秒 - {method}, {options_count}选项")
            else:
                print(f"❌ {elapsed:.2f}秒 - 失败")
        else:
            print(f"❌ {elapsed:.2f}秒 - HTTP {response.status_code}")
    except Exception as e:
        elapsed = time.time() - start_time
        times.append(elapsed)
        print(f"❌ {elapsed:.2f}秒 - {str(e)[:30]}")

if times:
    avg_time = sum(times) / len(times)
    min_time = min(times)
    max_time = max(times)
    
    print(f"\n{'='*70}")
    print("📊 测试结果:")
    print(f"{'='*70}")
    print(f"  平均时间: {avg_time:.2f}秒")
    print(f"  最快:     {min_time:.2f}秒")
    print(f"  最慢:     {max_time:.2f}秒")
    print(f"  成功率:   {success_count}/3 ({success_count/3*100:.1f}%)")
    print(f"{'='*70}")
    print(f"\n✅ 优化效果:")
    print(f"   相比之前50秒，提升了: {((50 - avg_time) / 50 * 100):.1f}%")
    print(f"   速度提升: {50/avg_time:.1f}倍")
    print(f"{'='*70}\n")

