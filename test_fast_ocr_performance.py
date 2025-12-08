"""
测试快速OCR混合方案的速度和正确率
对比：快速OCR+规则过滤 vs AI OCR
"""
import requests
import json
import base64
import sys
import os
import time
from statistics import mean, median
from datetime import datetime

# 修复Windows控制台编码问题
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

BASE_URL = 'http://localhost:5000'

def load_test_images(count=10):
    """加载测试图片"""
    test_images = []
    ceshi_dir = 'uploads/ceshi'
    
    if not os.path.exists(ceshi_dir):
        print(f"❌ 测试图片目录不存在: {ceshi_dir}")
        return []
    
    for file in os.listdir(ceshi_dir):
        if file.lower().endswith(('.png', '.jpg', '.jpeg')):
            test_images.append(os.path.join(ceshi_dir, file))
            if len(test_images) >= count:
                break
    
    return test_images

def test_single_image(image_path, force_reanalyze=True):
    """测试单张图片"""
    with open(image_path, 'rb') as f:
        image_data = f.read()
        image_base64 = base64.b64encode(image_data).decode('utf-8')
    
    data = {
        'questions': [{
            'image': image_base64,
            'question_type': 'TEXT',
            'force_reanalyze': force_reanalyze
        }]
    }
    
    start_time = time.time()
    try:
        response = requests.post(
            f'{BASE_URL}/api/questions/analyze/batch',
            json=data,
            headers={'Content-Type': 'application/json'},
            timeout=120
        )
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success_count', 0) > 0:
                question = result.get('results', [{}])[0].get('question', {})
                return {
                    'success': True,
                    'time': elapsed,
                    'question_text': question.get('question_text', ''),
                    'options_count': len(question.get('options', [])),
                    'has_content': bool(question.get('question_text')),
                    'extraction_method': question.get('extraction_method', 'unknown')
                }
            else:
                error = result.get('results', [{}])[0].get('error', {})
                return {
                    'success': False,
                    'time': elapsed,
                    'error': error.get('message', '未知错误')
                }
        else:
            return {
                'success': False,
                'time': elapsed,
                'error': f'HTTP {response.status_code}'
            }
    except Exception as e:
        elapsed = time.time() - start_time
        return {
            'success': False,
            'time': elapsed,
            'error': str(e)
        }

def test_fast_ocr_vs_ai(test_images, rounds=3):
    """对比快速OCR和AI OCR"""
    print("="*70)
    print("📊 快速OCR混合方案 vs AI OCR 性能对比测试")
    print("="*70)
    print(f"测试图片数: {len(test_images)}")
    print(f"每张图片测试轮数: {rounds}")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    results = {
        'fast_ocr': [],  # 快速OCR+规则过滤的结果
        'ai_ocr': [],    # AI OCR的结果
        'mixed': []      # 混合方案的实际结果
    }
    
    for idx, image_path in enumerate(test_images):
        print(f"\n{'='*70}")
        print(f"📷 测试图片 {idx+1}/{len(test_images)}: {os.path.basename(image_path)}")
        print(f"{'='*70}")
        
        image_size = os.path.getsize(image_path) / 1024
        print(f"图片大小: {image_size:.2f} KB")
        
        # 测试混合方案（实际使用）
        print(f"\n🔄 测试混合方案（自动选择最优方案）...")
        mixed_times = []
        mixed_success = 0
        mixed_methods = {'fast_ocr_rule': 0, 'volcengine_vision': 0, 'unknown': 0}
        
        for round_num in range(rounds):
            print(f"  第 {round_num+1}/{rounds} 次...", end=' ', flush=True)
            result = test_single_image(image_path, force_reanalyze=True)
            mixed_times.append(result['time'])
            
            if result['success']:
                mixed_success += 1
                method = result.get('extraction_method', 'unknown')
                mixed_methods[method] = mixed_methods.get(method, 0) + 1
                status = "✅"
                info = f"方法: {method}, 选项数: {result['options_count']}"
            else:
                status = "❌"
                info = result.get('error', '未知错误')[:40]
            
            print(f"{status} {result['time']:.2f}秒 - {info}")
        
        avg_time = mean(mixed_times)
        success_rate = mixed_success / rounds * 100
        
        print(f"\n📈 混合方案统计:")
        print(f"  平均时间: {avg_time:.2f}秒")
        print(f"  成功率: {success_rate:.1f}%")
        print(f"  方法分布: {dict(mixed_methods)}")
        
        results['mixed'].append({
            'image': os.path.basename(image_path),
            'times': mixed_times,
            'avg_time': avg_time,
            'success_rate': success_rate,
            'methods': mixed_methods
        })
    
    # 汇总统计
    print(f"\n{'='*70}")
    print("📊 汇总统计")
    print(f"{'='*70}")
    
    all_mixed_times = []
    all_fast_ocr_times = []
    all_ai_ocr_times = []
    total_fast_ocr_count = 0
    total_ai_ocr_count = 0
    total_success = 0
    
    for result in results['mixed']:
        all_mixed_times.extend(result['times'])
        if 'fast_ocr_rule' in result['methods']:
            total_fast_ocr_count += result['methods']['fast_ocr_rule']
            # 估算快速OCR时间（假设1-3秒）
            all_fast_ocr_times.extend([t for t in result['times'] if t < 5])
        if 'volcengine_vision' in result['methods']:
            total_ai_ocr_count += result['methods']['volcengine_vision']
            # 估算AI OCR时间（假设15-25秒）
            all_ai_ocr_times.extend([t for t in result['times'] if t >= 5])
        
        if result['success_rate'] > 0:
            total_success += 1
    
    print(f"\n📈 混合方案总体性能:")
    if all_mixed_times:
        print(f"  平均处理时间: {mean(all_mixed_times):.2f}秒")
        print(f"  最快: {min(all_mixed_times):.2f}秒")
        print(f"  最慢: {max(all_mixed_times):.2f}秒")
        print(f"  中位数: {median(all_mixed_times):.2f}秒")
    
    print(f"\n📈 方法使用统计:")
    print(f"  快速OCR+规则: {total_fast_ocr_count} 次")
    print(f"  AI OCR: {total_ai_ocr_count} 次")
    if total_fast_ocr_count + total_ai_ocr_count > 0:
        fast_ocr_ratio = total_fast_ocr_count / (total_fast_ocr_count + total_ai_ocr_count) * 100
        print(f"  快速OCR使用率: {fast_ocr_ratio:.1f}%")
    
    if all_fast_ocr_times:
        print(f"\n📈 快速OCR性能（估算）:")
        print(f"  平均时间: {mean(all_fast_ocr_times):.2f}秒")
        print(f"  最快: {min(all_fast_ocr_times):.2f}秒")
        print(f"  最慢: {max(all_fast_ocr_times):.2f}秒")
    
    if all_ai_ocr_times:
        print(f"\n📈 AI OCR性能（估算）:")
        print(f"  平均时间: {mean(all_ai_ocr_times):.2f}秒")
        print(f"  最快: {min(all_ai_ocr_times):.2f}秒")
        print(f"  最慢: {max(all_ai_ocr_times):.2f}秒")
    
    print(f"\n📈 成功率:")
    print(f"  成功图片数: {total_success}/{len(test_images)}")
    if len(test_images) > 0:
        print(f"  总体成功率: {total_success/len(test_images)*100:.1f}%")
    
    # 性能提升计算
    if all_fast_ocr_times and all_ai_ocr_times:
        fast_avg = mean(all_fast_ocr_times)
        ai_avg = mean(all_ai_ocr_times)
        speedup = ai_avg / fast_avg if fast_avg > 0 else 0
        print(f"\n📈 性能提升:")
        print(f"  快速OCR比AI快: {speedup:.1f}倍")
        print(f"  时间节省: {ai_avg - fast_avg:.2f}秒 ({((ai_avg - fast_avg) / ai_avg * 100):.1f}%)")
    
    print(f"\n{'='*70}")
    print("✅ 测试完成！")
    print(f"{'='*70}\n")
    
    return results

def main():
    """主函数"""
    print("="*70)
    print("🚀 快速OCR混合方案性能测试")
    print("="*70)
    print(f"API地址: {BASE_URL}")
    print()
    
    # 检查服务是否运行
    try:
        response = requests.get(f'{BASE_URL}/api/test', timeout=5)
        if response.status_code == 200:
            print("✅ 服务运行正常\n")
        else:
            print("⚠️ 服务响应异常\n")
    except Exception as e:
        print(f"❌ 无法连接到服务: {e}")
        print("请确保Flask服务正在运行: python app.py")
        return
    
    # 加载测试图片
    print("📷 加载测试图片...")
    test_images = load_test_images(5)  # 测试5张图片
    if not test_images:
        print("❌ 未找到测试图片")
        return
    
    print(f"✅ 找到 {len(test_images)} 张测试图片\n")
    
    # 运行测试
    results = test_fast_ocr_vs_ai(test_images, rounds=2)  # 每张图片测试2次
    
    # 生成报告
    print("\n" + "="*70)
    print("📋 测试报告")
    print("="*70)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"测试图片数: {len(test_images)}")
    print(f"每张图片测试次数: 2")
    print("\n详细结果请查看上方统计信息。")

if __name__ == '__main__':
    main()

