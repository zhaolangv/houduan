"""
测试优化后的OCR速度
"""
import requests
import json
import base64
import sys
import os
import time
from statistics import mean, median

# 修复Windows控制台编码问题
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

BASE_URL = 'http://localhost:5000'

def test_speed(image_path, rounds=5):
    """测试速度"""
    print("="*70)
    print("🚀 优化后的OCR速度测试")
    print("="*70)
    print(f"测试图片: {os.path.basename(image_path)}")
    print(f"图片大小: {os.path.getsize(image_path) / 1024:.2f} KB")
    print(f"测试轮数: {rounds}次\n")
    
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
    
    times = []
    success_count = 0
    
    for i in range(rounds):
        print(f"第 {i+1}/{rounds} 次...", end=' ', flush=True)
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
                    has_text = bool(question.get('question_text'))
                    print(f"✅ {elapsed:.2f}秒 - {method}, {options_count}选项, {'有内容' if has_text else '无内容'}")
                else:
                    print(f"❌ {elapsed:.2f}秒 - 失败")
            else:
                print(f"❌ {elapsed:.2f}秒 - HTTP {response.status_code}")
        except Exception as e:
            elapsed = time.time() - start_time
            times.append(elapsed)
            print(f"❌ {elapsed:.2f}秒 - {str(e)[:30]}")
    
    if times:
        print(f"\n{'='*70}")
        print("📊 统计结果:")
        print(f"{'='*70}")
        print(f"  平均时间: {mean(times):.2f}秒")
        print(f"  中位数:   {median(times):.2f}秒")
        print(f"  最快:     {min(times):.2f}秒")
        print(f"  最慢:     {max(times):.2f}秒")
        print(f"  成功率:   {success_count}/{rounds} ({success_count/rounds*100:.1f}%)")
        print(f"{'='*70}\n")
        
        return {
            'avg': mean(times),
            'median': median(times),
            'min': min(times),
            'max': max(times),
            'success_rate': success_count / rounds
        }
    return None

def main():
    # 加载测试图片
    ceshi_dir = 'uploads/ceshi'
    test_images = []
    for file in os.listdir(ceshi_dir):
        if file.lower().endswith(('.png', '.jpg', '.jpeg')):
            test_images.append(os.path.join(ceshi_dir, file))
            break
    
    if not test_images:
        print("❌ 未找到测试图片")
        return
    
    result = test_speed(test_images[0], rounds=5)
    
    if result:
        print("✅ 优化效果:")
        print(f"   平均速度: {result['avg']:.2f}秒/张")
        print(f"   最快速度: {result['min']:.2f}秒/张")
        print(f"   相比之前50秒，提升了: {((50 - result['avg']) / 50 * 100):.1f}%")

if __name__ == '__main__':
    main()

