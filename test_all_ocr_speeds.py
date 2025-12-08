"""
测试所有OCR方案的速度和准确率
找出最快的方案
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

def test_ocr_method(image_path, method_name, rounds=3):
    """测试特定OCR方法"""
    print(f"\n{'='*70}")
    print(f"📊 测试方案: {method_name}")
    print(f"{'='*70}")
    
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
    has_content_count = 0
    
    for i in range(rounds):
        print(f"  第 {i+1}/{rounds} 次...", end=' ', flush=True)
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
                if result.get('success_count', 0) > 0:
                    success_count += 1
                    question = result.get('results', [{}])[0].get('question', {})
                    if question.get('question_text'):
                        has_content_count += 1
                    print(f"✅ {elapsed:.2f}秒")
                else:
                    print(f"❌ {elapsed:.2f}秒 - 失败")
            else:
                print(f"❌ {elapsed:.2f}秒 - HTTP {response.status_code}")
        except Exception as e:
            elapsed = time.time() - start_time
            times.append(elapsed)
            print(f"❌ {elapsed:.2f}秒 - {str(e)[:30]}")
    
    if times:
        avg_time = mean(times)
        min_time = min(times)
        max_time = max(times)
        success_rate = success_count / rounds * 100
        content_rate = has_content_count / rounds * 100
        
        print(f"\n📈 统计:")
        print(f"  平均时间: {avg_time:.2f}秒")
        print(f"  最快: {min_time:.2f}秒")
        print(f"  最慢: {max_time:.2f}秒")
        print(f"  成功率: {success_rate:.1f}%")
        print(f"  有内容率: {content_rate:.1f}%")
        
        return {
            'method': method_name,
            'avg_time': avg_time,
            'min_time': min_time,
            'max_time': max_time,
            'success_rate': success_rate,
            'content_rate': content_rate
        }
    return None

def test_paddleocr_direct(image_path):
    """直接测试PaddleOCR速度（不经过API）"""
    print(f"\n{'='*70}")
    print(f"📊 测试方案: PaddleOCR直接调用")
    print(f"{'='*70}")
    
    times = []
    success_count = 0
    
    for i in range(3):
        print(f"  第 {i+1}/3 次...", end=' ', flush=True)
        start_time = time.time()
        
        try:
            from ocr_service import get_ocr_service
            ocr_service = get_ocr_service()
            
            if ocr_service.ocr_engine:
                text = ocr_service.extract_text(image_path)
                elapsed = time.time() - start_time
                times.append(elapsed)
                
                if text and len(text.strip()) > 20:
                    success_count += 1
                    print(f"✅ {elapsed:.2f}秒 - 文字长度: {len(text)}")
                else:
                    print(f"⚠️ {elapsed:.2f}秒 - 文字太少: {len(text) if text else 0}")
            else:
                print(f"❌ OCR引擎不可用")
                return None
        except Exception as e:
            elapsed = time.time() - start_time
            times.append(elapsed)
            print(f"❌ {elapsed:.2f}秒 - {str(e)[:30]}")
    
    if times:
        avg_time = mean(times)
        print(f"\n📈 统计:")
        print(f"  平均时间: {avg_time:.2f}秒")
        print(f"  成功率: {success_count/3*100:.1f}%")
        return {
            'method': 'PaddleOCR直接',
            'avg_time': avg_time,
            'success_rate': success_count/3*100
        }
    return None

def main():
    """主函数"""
    print("="*70)
    print("🚀 OCR速度全面测试 - 找出最快方案")
    print("="*70)
    
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
    test_images = []
    for file in os.listdir(ceshi_dir):
        if file.lower().endswith(('.png', '.jpg', '.jpeg')):
            test_images.append(os.path.join(ceshi_dir, file))
            break
    
    if not test_images:
        print("❌ 未找到测试图片")
        return
    
    image_path = test_images[0]
    print(f"\n📷 测试图片: {os.path.basename(image_path)}")
    print(f"图片大小: {os.path.getsize(image_path) / 1024:.2f} KB")
    
    results = []
    
    # 测试1: 当前方案（混合方案，会fallback到AI）
    result1 = test_ocr_method(image_path, "当前方案（AI OCR）", rounds=2)
    if result1:
        results.append(result1)
    
    # 测试2: PaddleOCR直接调用
    result2 = test_paddleocr_direct(image_path)
    if result2:
        results.append(result2)
    
    # 汇总对比
    print(f"\n{'='*70}")
    print("📊 速度对比汇总")
    print(f"{'='*70}")
    print(f"{'方案':<20} {'平均时间':<12} {'最快':<12} {'成功率':<10}")
    print(f"{'-'*70}")
    
    for r in results:
        print(f"{r['method']:<20} {r['avg_time']:<12.2f} {r.get('min_time', r['avg_time']):<12.2f} {r.get('success_rate', 0):<10.1f}%")
    
    # 找出最快方案
    if results:
        fastest = min(results, key=lambda x: x['avg_time'])
        print(f"\n🏆 最快方案: {fastest['method']}")
        print(f"   平均时间: {fastest['avg_time']:.2f}秒")
        print(f"   成功率: {fastest.get('success_rate', 0):.1f}%")
    
    print(f"\n{'='*70}")

if __name__ == '__main__':
    main()

