"""
OCR速度快速测试脚本
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

def quick_test():
    """快速测试OCR速度"""
    print("="*60)
    print("OCR速度快速测试")
    print("="*60)
    
    # 检查服务
    try:
        response = requests.get(f'{BASE_URL}/api/test', timeout=5)
        if response.status_code != 200:
            print("❌ 服务未运行")
            return
    except:
        print("❌ 无法连接到服务")
        return
    
    # 加载测试图片
    ceshi_dir = 'uploads/ceshi'
    if not os.path.exists(ceshi_dir):
        print(f"❌ 测试图片目录不存在: {ceshi_dir}")
        return
    
    test_images = []
    for file in os.listdir(ceshi_dir):
        if file.lower().endswith(('.png', '.jpg', '.jpeg')):
            test_images.append(os.path.join(ceshi_dir, file))
            if len(test_images) >= 3:
                break
    
    if not test_images:
        print("❌ 未找到测试图片")
        return
    
    print(f"✅ 找到 {len(test_images)} 张测试图片\n")
    
    # 测试单张图片
    print("📊 测试单张图片处理速度:")
    print("-" * 60)
    
    with open(test_images[0], 'rb') as f:
        image_data = f.read()
        image_base64 = base64.b64encode(image_data).decode('utf-8')
    
    data = {
        'questions': [{
            'image': image_base64,
            'question_type': 'TEXT',
            'force_reanalyze': True  # 强制重新分析，测试完整流程
        }]
    }
    
    times = []
    for i in range(3):
        start = time.time()
        try:
            response = requests.post(
                f'{BASE_URL}/api/questions/analyze/batch',
                json=data,
                headers={'Content-Type': 'application/json'},
                timeout=60
            )
            elapsed = time.time() - start
            
            if response.status_code == 200:
                result = response.json()
                success = result.get('success_count', 0) > 0
                times.append(elapsed)
                status = "✅" if success else "❌"
                print(f"  第{i+1}次: {elapsed:.2f}秒 {status}")
            else:
                print(f"  第{i+1}次: {elapsed:.2f}秒 ❌ HTTP {response.status_code}")
        except Exception as e:
            elapsed = time.time() - start
            print(f"  第{i+1}次: {elapsed:.2f}秒 ❌ {str(e)[:50]}")
    
    if times:
        avg = mean(times)
        print(f"\n📊 平均处理时间: {avg:.2f}秒")
        print(f"📊 最快: {min(times):.2f}秒")
        print(f"📊 最慢: {max(times):.2f}秒")
    
    # 测试批量处理
    if len(test_images) >= 3:
        print(f"\n📊 测试批量处理速度 ({len(test_images)}张):")
        print("-" * 60)
        
        questions = []
        for img_path in test_images:
            with open(img_path, 'rb') as f:
                image_data = f.read()
                image_base64 = base64.b64encode(image_data).decode('utf-8')
                questions.append({
                    'image': image_base64,
                    'question_type': 'TEXT',
                    'force_reanalyze': False  # 不强制，测试缓存效果
                })
        
        data = {'questions': questions}
        
        start = time.time()
        try:
            response = requests.post(
                f'{BASE_URL}/api/questions/analyze/batch',
                json=data,
                headers={'Content-Type': 'application/json'},
                timeout=120
            )
            elapsed = time.time() - start
            
            if response.status_code == 200:
                result = response.json()
                total = result.get('total', 0)
                success = result.get('success_count', 0)
                failed = result.get('failed_count', 0)
                
                print(f"  总时间: {elapsed:.2f}秒")
                print(f"  成功: {success}/{total}")
                print(f"  失败: {failed}/{total}")
                print(f"  平均每张: {elapsed/total:.2f}秒" if total > 0 else "")
            else:
                print(f"  ❌ HTTP {response.status_code}")
        except Exception as e:
            elapsed = time.time() - start
            print(f"  ❌ 错误: {str(e)[:50]}")
    
    print("\n" + "="*60)
    print("✅ 测试完成!")
    print("="*60)

if __name__ == '__main__':
    quick_test()

