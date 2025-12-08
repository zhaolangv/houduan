"""
测试批量处理速度（最终优化版）
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

def test_batch_speed(batch_sizes=[1, 3, 5]):
    """测试批量处理速度"""
    print("="*70)
    print("🚀 批量处理速度测试（优化后）")
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
        return
    
    print(f"测试图片数: {len(test_images)}\n")
    
    # 准备图片数据
    images_base64 = []
    for img_path in test_images:
        with open(img_path, 'rb') as f:
            image_data = f.read()
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            images_base64.append(image_base64)
    
    results = {}
    
    for batch_size in batch_sizes:
        if batch_size > len(images_base64):
            continue
        
        print(f"{'='*70}")
        print(f"📦 批量大小: {batch_size}")
        print(f"{'='*70}")
        
        questions = [
            {
                'image': img_base64,
                'question_type': 'TEXT',
                'force_reanalyze': True
            }
            for img_base64 in images_base64[:batch_size]
        ]
        
        data = {'questions': questions}
        
        times = []
        success_counts = []
        
        for i in range(3):
            print(f"  第 {i+1}/3 次...", end=' ', flush=True)
            start_time = time.time()
            
            try:
                response = requests.post(
                    f'{BASE_URL}/api/questions/analyze/batch',
                    json=data,
                    headers={'Content-Type': 'application/json'},
                    timeout=120
                )
                elapsed = time.time() - start_time
                times.append(elapsed)
                
                if response.status_code == 200:
                    result = response.json()
                    total = result.get('total', 0)
                    success = result.get('success_count', 0)
                    success_counts.append(success)
                    print(f"✅ {elapsed:.2f}秒 - 成功: {success}/{total}")
                else:
                    print(f"❌ {elapsed:.2f}秒 - HTTP {response.status_code}")
            except Exception as e:
                elapsed = time.time() - start_time
                times.append(elapsed)
                print(f"❌ {elapsed:.2f}秒 - {str(e)[:30]}")
        
        if times:
            avg_time = mean(times)
            avg_success = mean(success_counts) if success_counts else 0
            avg_per_image = avg_time / batch_size
            
            results[batch_size] = {
                'total_time': avg_time,
                'per_image': avg_per_image,
                'success_rate': avg_success / batch_size if batch_size > 0 else 0
            }
            
            print(f"\n📈 统计:")
            print(f"  平均总时间: {avg_time:.2f}秒")
            print(f"  平均每张:   {avg_per_image:.2f}秒")
            print(f"  成功率:     {avg_success/batch_size*100:.1f}%")
            print()
    
    # 汇总
    print(f"{'='*70}")
    print("📊 批量处理性能汇总")
    print(f"{'='*70}")
    print(f"{'批量大小':<10} {'总时间(秒)':<15} {'每张(秒)':<15} {'成功率':<10}")
    print(f"{'-'*60}")
    for batch_size in sorted(results.keys()):
        data = results[batch_size]
        print(f"{batch_size:<10} {data['total_time']:<15.2f} {data['per_image']:<15.2f} {data['success_rate']*100:<10.1f}%")
    
    print(f"\n{'='*70}")
    print("✅ 测试完成！")
    print(f"{'='*70}\n")

if __name__ == '__main__':
    test_batch_speed([1, 3, 5])

