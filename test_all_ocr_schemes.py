"""
测试不同OCR方案的速度和准确率
对比：
1. Vision模型（当前方案）
2. OCR API + 文本AI过滤
3. OCR API + 规则过滤
"""
import requests
import json
import sys
import os
import time
from statistics import mean
from typing import Dict, List

# 修复Windows控制台编码问题
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

BASE_URL = 'http://localhost:5000'

def load_test_images(max_images=5):
    """加载测试图片"""
    ceshi_dir = 'uploads/ceshi'
    images = []
    for file in os.listdir(ceshi_dir):
        if file.lower().endswith(('.png', '.jpg', '.jpeg')):
            images.append(os.path.join(ceshi_dir, file))
            if len(images) >= max_images:
                break
    return images

def test_vision_model(image_path: str, test_name: str = "Vision模型") -> Dict:
    """测试Vision模型方案"""
    start = time.time()
    try:
        with open(image_path, 'rb') as f:
            files = {'image': (os.path.basename(image_path), f, 'image/jpeg')}
            data = {
                'question_type': 'TEXT',
                'force_reanalyze': 'true'
            }
            response = requests.post(
                f'{BASE_URL}/api/questions/analyze',
                files=files,
                data=data,
                timeout=60
            )
        elapsed = time.time() - start
        
        if response.status_code == 200:
            result = response.json()
            return {
                'success': True,
                'time': elapsed,
                'method': result.get('extraction_method', 'unknown'),
                'question_text': result.get('question_text', ''),
                'options': result.get('options', []),
                'options_count': len(result.get('options', [])),
                'has_question': len(result.get('question_text', '').strip()) > 10,
                'has_options': len(result.get('options', [])) >= 2
            }
        else:
            return {
                'success': False,
                'time': elapsed,
                'error': f'HTTP {response.status_code}'
            }
    except Exception as e:
        elapsed = time.time() - start
        return {
            'success': False,
            'time': elapsed,
            'error': str(e)[:50]
        }

def test_ocr_api_text_ai(image_path: str) -> Dict:
    """测试OCR API + 文本AI过滤方案"""
    # 设置环境变量强制使用OCR API + 文本AI
    import os
    original_method = os.environ.get('OCR_METHOD')
    os.environ['OCR_METHOD'] = 'ocr_ai'
    
    start = time.time()
    try:
        with open(image_path, 'rb') as f:
            files = {'image': (os.path.basename(image_path), f, 'image/jpeg')}
            data = {
                'question_type': 'TEXT',
                'force_reanalyze': 'true'
            }
            response = requests.post(
                f'{BASE_URL}/api/questions/analyze',
                files=files,
                data=data,
                timeout=60
            )
        elapsed = time.time() - start
        
        # 恢复环境变量
        if original_method:
            os.environ['OCR_METHOD'] = original_method
        elif 'OCR_METHOD' in os.environ:
            del os.environ['OCR_METHOD']
        
        if response.status_code == 200:
            result = response.json()
            return {
                'success': True,
                'time': elapsed,
                'method': result.get('extraction_method', 'unknown'),
                'question_text': result.get('question_text', ''),
                'options': result.get('options', []),
                'options_count': len(result.get('options', [])),
                'has_question': len(result.get('question_text', '').strip()) > 10,
                'has_options': len(result.get('options', [])) >= 2
            }
        else:
            return {
                'success': False,
                'time': elapsed,
                'error': f'HTTP {response.status_code}'
            }
    except Exception as e:
        elapsed = time.time() - start
        # 恢复环境变量
        if original_method:
            os.environ['OCR_METHOD'] = original_method
        elif 'OCR_METHOD' in os.environ:
            del os.environ['OCR_METHOD']
        return {
            'success': False,
            'time': elapsed,
            'error': str(e)[:50]
        }

def test_ocr_api_rule(image_path: str) -> Dict:
    """测试OCR API + 规则过滤方案"""
    # 设置环境变量强制使用OCR API + 规则过滤
    import os
    original_method = os.environ.get('OCR_METHOD')
    os.environ['OCR_METHOD'] = 'ocr_rule'
    
    start = time.time()
    try:
        with open(image_path, 'rb') as f:
            files = {'image': (os.path.basename(image_path), f, 'image/jpeg')}
            data = {
                'question_type': 'TEXT',
                'force_reanalyze': 'true'
            }
            response = requests.post(
                f'{BASE_URL}/api/questions/analyze',
                files=files,
                data=data,
                timeout=60
            )
        elapsed = time.time() - start
        
        # 恢复环境变量
        if original_method:
            os.environ['OCR_METHOD'] = original_method
        elif 'OCR_METHOD' in os.environ:
            del os.environ['OCR_METHOD']
        
        if response.status_code == 200:
            result = response.json()
            return {
                'success': True,
                'time': elapsed,
                'method': result.get('extraction_method', 'unknown'),
                'question_text': result.get('question_text', ''),
                'options': result.get('options', []),
                'options_count': len(result.get('options', [])),
                'has_question': len(result.get('question_text', '').strip()) > 10,
                'has_options': len(result.get('options', [])) >= 2
            }
        else:
            return {
                'success': False,
                'time': elapsed,
                'error': f'HTTP {response.status_code}'
            }
    except Exception as e:
        elapsed = time.time() - start
        # 恢复环境变量
        if original_method:
            os.environ['OCR_METHOD'] = original_method
        elif 'OCR_METHOD' in os.environ:
            del os.environ['OCR_METHOD']
        return {
            'success': False,
            'time': elapsed,
            'error': str(e)[:50]
        }

def evaluate_accuracy(result: Dict) -> float:
    """评估准确率（简单评估）"""
    score = 0.0
    
    # 有题干：+0.4
    if result.get('has_question'):
        score += 0.4
    
    # 有选项：+0.4
    if result.get('has_options'):
        score += 0.4
    
    # 选项数量合理（2-6个）：+0.2
    options_count = result.get('options_count', 0)
    if 2 <= options_count <= 6:
        score += 0.2
    
    return score

def print_result(test_name: str, results: List[Dict]):
    """打印测试结果"""
    print(f"\n{'='*70}")
    print(f"📊 {test_name} - 测试结果")
    print(f"{'='*70}")
    
    success_results = [r for r in results if r.get('success')]
    failed_results = [r for r in results if not r.get('success')]
    
    if success_results:
        times = [r['time'] for r in success_results]
        accuracies = [evaluate_accuracy(r) for r in success_results]
        
        print(f"✅ 成功: {len(success_results)}/{len(results)} ({len(success_results)/len(results)*100:.1f}%)")
        print(f"❌ 失败: {len(failed_results)}/{len(results)}")
        print(f"\n⏱️  速度统计:")
        print(f"  平均时间: {mean(times):.2f}秒")
        print(f"  最快:     {min(times):.2f}秒")
        print(f"  最慢:     {max(times):.2f}秒")
        print(f"\n🎯 准确率统计:")
        print(f"  平均准确率: {mean(accuracies):.2%}")
        print(f"  最高准确率: {max(accuracies):.2%}")
        print(f"  最低准确率: {min(accuracies):.2%}")
        
        # 详细结果
        print(f"\n📝 详细结果:")
        for i, r in enumerate(success_results, 1):
            method = r.get('method', 'unknown')
            options_count = r.get('options_count', 0)
            accuracy = evaluate_accuracy(r)
            question_preview = r.get('question_text', '')[:30] + '...' if len(r.get('question_text', '')) > 30 else r.get('question_text', '')
            print(f"  {i}. {r['time']:.2f}秒 - {method}, {options_count}选项, 准确率{accuracy:.2%}")
            if question_preview:
                print(f"     题干: {question_preview}")
    else:
        print(f"❌ 全部失败")
        for i, r in enumerate(failed_results, 1):
            print(f"  {i}. {r.get('time', 0):.2f}秒 - {r.get('error', 'unknown')}")

def main():
    print("="*70)
    print("🚀 OCR方案速度和准确率对比测试")
    print("="*70)
    
    # 加载测试图片
    test_images = load_test_images(3)  # 测试3张图片
    
    if not test_images:
        print("❌ 未找到测试图片")
        return
    
    print(f"📷 测试图片数: {len(test_images)}")
    for img in test_images:
        file_size = os.path.getsize(img) / 1024
        print(f"  - {os.path.basename(img)} ({file_size:.2f} KB)")
    
    # 测试方案1：Vision模型（当前方案）
    print(f"\n{'='*70}")
    print("📊 测试方案1：Vision模型（当前方案）")
    print(f"{'='*70}")
    vision_results = []
    for i, img_path in enumerate(test_images, 1):
        print(f"  测试图片 {i}/{len(test_images)}...", end=' ', flush=True)
        result = test_vision_model(img_path, "Vision模型")
        vision_results.append(result)
        if result.get('success'):
            print(f"✅ {result['time']:.2f}秒")
        else:
            print(f"❌ {result.get('error', 'unknown')}")
    
    print_result("方案1：Vision模型", vision_results)
    
    # 测试方案2：OCR API + 文本AI
    print(f"\n{'='*70}")
    print("📊 测试方案2：OCR API + 文本AI过滤")
    print(f"{'='*70}")
    ocr_ai_results = []
    for i, img_path in enumerate(test_images, 1):
        print(f"  测试图片 {i}/{len(test_images)}...", end=' ', flush=True)
        result = test_ocr_api_text_ai(img_path)
        ocr_ai_results.append(result)
        if result.get('success'):
            print(f"✅ {result['time']:.2f}秒")
        else:
            print(f"❌ {result.get('error', 'unknown')}")
    
    print_result("方案2：OCR API + 文本AI", ocr_ai_results)
    
    # 测试方案3：OCR API + 规则过滤
    print(f"\n{'='*70}")
    print("📊 测试方案3：OCR API + 规则过滤")
    print(f"{'='*70}")
    ocr_rule_results = []
    for i, img_path in enumerate(test_images, 1):
        print(f"  测试图片 {i}/{len(test_images)}...", end=' ', flush=True)
        result = test_ocr_api_rule(img_path)
        ocr_rule_results.append(result)
        if result.get('success'):
            print(f"✅ {result['time']:.2f}秒")
        else:
            print(f"❌ {result.get('error', 'unknown')}")
    
    print_result("方案3：OCR API + 规则过滤", ocr_rule_results)
    
    # 总结对比
    print(f"\n{'='*70}")
    print("📊 方案对比总结")
    print(f"{'='*70}")
    
    schemes = [
        ("方案1：Vision模型", vision_results),
        ("方案2：OCR API + 文本AI", ocr_ai_results),
        ("方案3：OCR API + 规则过滤", ocr_rule_results)
    ]
    
    summary_data = []
    for name, results in schemes:
        success_results = [r for r in results if r.get('success')]
        if success_results:
            times = [r['time'] for r in success_results]
            accuracies = [evaluate_accuracy(r) for r in success_results]
            
            summary_data.append({
                'name': name,
                'avg_time': mean(times),
                'min_time': min(times),
                'max_time': max(times),
                'avg_accuracy': mean(accuracies),
                'success_rate': len(success_results) / len(results) * 100,
                'success_count': len(success_results),
                'total_count': len(results)
            })
    
    # 打印对比表
    print(f"\n{'方案':<30} {'平均速度':<12} {'速度范围':<15} {'平均准确率':<12} {'成功率':<10}")
    print(f"{'-'*70}")
    for data in summary_data:
        time_range = f"{data['min_time']:.1f}-{data['max_time']:.1f}秒"
        print(f"{data['name']:<30} {data['avg_time']:>6.2f}秒    {time_range:<15} {data['avg_accuracy']:>8.2%}    {data['success_count']}/{data['total_count']} ({data['success_rate']:.1f}%)")
    
    # 找出最快的方案
    if summary_data:
        fastest = min(summary_data, key=lambda x: x['avg_time'])
        most_accurate = max(summary_data, key=lambda x: x['avg_accuracy'])
        
        print(f"\n🏆 最快方案: {fastest['name']} ({fastest['avg_time']:.2f}秒)")
        print(f"🎯 最准确方案: {most_accurate['name']} ({most_accurate['avg_accuracy']:.2%})")
        
        # 推荐方案
        best_balanced = min(summary_data, key=lambda x: x['avg_time'] / max(x['avg_accuracy'], 0.01))
        print(f"⭐ 推荐方案: {best_balanced['name']} (速度{best_balanced['avg_time']:.2f}秒, 准确率{best_balanced['avg_accuracy']:.2%})")
    
    print(f"\n{'='*70}")

if __name__ == '__main__':
    main()

