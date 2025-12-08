"""
演示批量并行处理的速度优势 - 几秒钟提取一张
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
print("🚀 批量并行处理速度演示 - 几秒钟提取一张")
print("="*70)

# 加载测试图片
ceshi_dir = 'uploads/ceshi'
test_images = []
for file in os.listdir(ceshi_dir):
    if file.lower().endswith(('.png', '.jpg', '.jpeg')):
        test_images.append(os.path.join(ceshi_dir, file))
        if len(test_images) >= 5:
            break

if not test_images:
    print("❌ 未找到测试图片")
    sys.exit(1)

print(f"📷 测试图片数: {len(test_images)}\n")

# 准备图片数据
images_base64 = []
for img_path in test_images:
    with open(img_path, 'rb') as f:
        image_data = f.read()
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        images_base64.append(image_base64)

# 测试1：单张处理（顺序）
print("="*70)
print("📊 测试1：单张顺序处理")
print("="*70)
single_times = []
for i, img_base64 in enumerate(images_base64[:3]):  # 只测试3张
    print(f"  处理图片 {i+1}/3...", end=' ', flush=True)
    data = {
        'questions': [{
            'image': img_base64,
            'question_type': 'TEXT',
            'force_reanalyze': True
        }]
    }
    start = time.time()
    try:
        response = requests.post(
            f'{BASE_URL}/api/questions/analyze/batch',
            json=data,
            headers={'Content-Type': 'application/json'},
            timeout=60
        )
        elapsed = time.time() - start
        single_times.append(elapsed)
        if response.status_code == 200:
            result = response.json()
            success = result.get('success_count', 0)
            print(f"✅ {elapsed:.2f}秒 - 成功: {success}/1")
        else:
            print(f"❌ {elapsed:.2f}秒")
    except:
        elapsed = time.time() - start
        single_times.append(elapsed)
        print(f"❌ {elapsed:.2f}秒")

if single_times:
    single_total = sum(single_times)
    single_avg = mean(single_times)
    print(f"\n📈 单张处理统计:")
    print(f"  总时间: {single_total:.2f}秒（{len(single_times)}张）")
    print(f"  平均每张: {single_avg:.2f}秒")

# 测试2：批量并行处理
print(f"\n{'='*70}")
print("📊 测试2：批量并行处理（5张）")
print("="*70)

questions = [
    {
        'image': img_base64,
        'question_type': 'TEXT',
        'force_reanalyze': True
    }
    for img_base64 in images_base64[:5]
]

data = {'questions': questions}

parallel_times = []
for i in range(3):
    print(f"  第 {i+1}/3 次批量处理（5张并行）...", end=' ', flush=True)
    start = time.time()
    try:
        response = requests.post(
            f'{BASE_URL}/api/questions/analyze/batch',
            json=data,
            headers={'Content-Type': 'application/json'},
            timeout=120
        )
        elapsed = time.time() - start
        parallel_times.append(elapsed)
        if response.status_code == 200:
            result = response.json()
            total = result.get('total', 0)
            success = result.get('success_count', 0)
            print(f"✅ {elapsed:.2f}秒 - 成功: {success}/{total}")
        else:
            print(f"❌ {elapsed:.2f}秒")
    except:
        elapsed = time.time() - start
        parallel_times.append(elapsed)
        print(f"❌ {elapsed:.2f}秒")

if parallel_times:
    parallel_avg = mean(parallel_times)
    parallel_per_image = parallel_avg / 5
    print(f"\n📈 批量并行处理统计:")
    print(f"  平均总时间: {parallel_avg:.2f}秒（5张）")
    print(f"  平均每张:   {parallel_per_image:.2f}秒")

# 对比
print(f"\n{'='*70}")
print("📊 速度对比")
print("="*70)
if single_times and parallel_times:
    print(f"单张顺序处理: {single_avg:.2f}秒/张")
    print(f"批量并行处理: {parallel_per_image:.2f}秒/张")
    speedup = single_avg / parallel_per_image if parallel_per_image > 0 else 0
    print(f"速度提升: {speedup:.1f}倍")
    print(f"\n✅ 结论: 使用批量并行处理可以达到 {parallel_per_image:.1f}秒/张！")
    if parallel_per_image < 10:
        print(f"🎉 成功达到几秒钟的目标！")
    else:
        print(f"⚠️ 还需要进一步优化才能达到几秒钟")

print(f"\n{'='*70}")

