"""
AI处理速度测试脚本 - 专门测试优化后的OCR速度
重点测试火山引擎OCR（已禁用思考模式）的处理速度
"""
import requests
import json
import base64
import sys
import os
import time
from statistics import mean, median, stdev
from datetime import datetime

# 修复Windows控制台编码问题
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# API基础URL
BASE_URL = 'http://localhost:5000'

def load_test_images(count=5):
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

def test_single_ocr_speed(image_path, rounds=5):
    """测试单张图片OCR处理速度（多次测试取平均值）"""
    print(f"\n{'='*70}")
    print(f"📊 单张图片OCR速度测试")
    print(f"{'='*70}")
    print(f"图片: {os.path.basename(image_path)}")
    print(f"测试轮数: {rounds}次")
    print(f"强制重新分析: 是（测试完整OCR流程）")
    print(f"{'-'*70}")
    
    # 读取图片并编码为base64
    with open(image_path, 'rb') as f:
        image_data = f.read()
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        image_size_mb = len(image_data) / (1024 * 1024)
    
    print(f"图片大小: {image_size_mb:.2f} MB")
    print(f"Base64长度: {len(image_base64)} 字符\n")
    
    data = {
        'questions': [{
            'image': image_base64,
            'question_type': 'TEXT',
            'force_reanalyze': True  # 强制重新分析，确保每次都调用OCR
        }]
    }
    
    times = []
    success_count = 0
    
    for i in range(rounds):
        print(f"第 {i+1}/{rounds} 次测试...", end=' ', flush=True)
        start_time = time.time()
        
        try:
            response = requests.post(
                f'{BASE_URL}/api/questions/analyze/batch',
                json=data,
                headers={'Content-Type': 'application/json'},
                timeout=60
            )
            end_time = time.time()
            elapsed = end_time - start_time
            times.append(elapsed)
            
            if response.status_code == 200:
                result = response.json()
                success = result.get('success_count', 0) > 0
                if success:
                    success_count += 1
                    question = result.get('results', [{}])[0].get('question', {})
                    has_text = bool(question.get('question_text'))
                    print(f"✅ {elapsed:.2f}秒 - 成功" + (" (有内容)" if has_text else " (无内容)"))
                else:
                    print(f"❌ {elapsed:.2f}秒 - 处理失败")
            else:
                print(f"❌ {elapsed:.2f}秒 - HTTP {response.status_code}")
        except requests.exceptions.Timeout:
            elapsed = time.time() - start_time
            times.append(elapsed)
            print(f"⏱️ {elapsed:.2f}秒 - 超时")
        except Exception as e:
            elapsed = time.time() - start_time
            times.append(elapsed)
            print(f"❌ {elapsed:.2f}秒 - 错误: {str(e)[:40]}")
    
    # 统计结果
    if times:
        avg_time = mean(times)
        median_time = median(times)
        min_time = min(times)
        max_time = max(times)
        std_dev = stdev(times) if len(times) > 1 else 0
        
        print(f"\n{'='*70}")
        print(f"📈 统计结果:")
        print(f"{'='*70}")
        print(f"  平均时间: {avg_time:.2f}秒")
        print(f"  中位数:   {median_time:.2f}秒")
        print(f"  最快:     {min_time:.2f}秒")
        print(f"  最慢:     {max_time:.2f}秒")
        print(f"  标准差:   {std_dev:.2f}秒")
        print(f"  成功率:   {success_count}/{rounds} ({success_count/rounds*100:.1f}%)")
        print(f"{'='*70}\n")
        
        return {
            'avg': avg_time,
            'median': median_time,
            'min': min_time,
            'max': max_time,
            'std': std_dev,
            'success_rate': success_count / rounds
        }
    return None

def test_batch_ocr_speed(image_paths, batch_sizes=[1, 3, 5]):
    """测试批量OCR处理速度"""
    print(f"\n{'='*70}")
    print(f"📊 批量OCR处理速度测试")
    print(f"{'='*70}")
    print(f"测试图片数: {len(image_paths)}")
    print(f"批量大小: {batch_sizes}")
    print(f"强制重新分析: 否（利用缓存）")
    print(f"{'-'*70}\n")
    
    # 准备所有图片的base64数据
    images_base64 = []
    total_size_mb = 0
    
    for img_path in image_paths:
        with open(img_path, 'rb') as f:
            image_data = f.read()
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            images_base64.append(image_base64)
            total_size_mb += len(image_data) / (1024 * 1024)
    
    print(f"总图片大小: {total_size_mb:.2f} MB\n")
    
    results = {}
    
    for batch_size in batch_sizes:
        if batch_size > len(images_base64):
            continue
        
        print(f"{'='*70}")
        print(f"📦 批量大小: {batch_size}")
        print(f"{'='*70}")
        
        # 准备批量数据
        questions = [
            {
                'image': img_base64,
                'question_type': 'TEXT',
                'force_reanalyze': False  # 不强制，测试缓存和并行效果
            }
            for img_base64 in images_base64[:batch_size]
        ]
        
        data = {'questions': questions}
        
        # 测试3次取平均值
        times = []
        success_counts = []
        
        for i in range(3):
            print(f"第 {i+1}/3 次测试...", end=' ', flush=True)
            start_time = time.time()
            
            try:
                response = requests.post(
                    f'{BASE_URL}/api/questions/analyze/batch',
                    json=data,
                    headers={'Content-Type': 'application/json'},
                    timeout=120
                )
                end_time = time.time()
                elapsed = end_time - start_time
                times.append(elapsed)
                
                if response.status_code == 200:
                    result = response.json()
                    total = result.get('total', 0)
                    success = result.get('success_count', 0)
                    failed = result.get('failed_count', 0)
                    success_counts.append(success)
                    print(f"✅ {elapsed:.2f}秒 - 成功: {success}/{total}, 失败: {failed}")
                else:
                    print(f"❌ {elapsed:.2f}秒 - HTTP {response.status_code}")
            except requests.exceptions.Timeout:
                elapsed = time.time() - start_time
                times.append(elapsed)
                print(f"⏱️ {elapsed:.2f}秒 - 超时")
            except Exception as e:
                elapsed = time.time() - start_time
                times.append(elapsed)
                print(f"❌ {elapsed:.2f}秒 - 错误: {str(e)[:40]}")
        
        if times:
            avg_time = mean(times)
            avg_success = mean(success_counts) if success_counts else 0
            avg_per_image = avg_time / batch_size
            
            results[batch_size] = {
                'total_time': avg_time,
                'per_image': avg_per_image,
                'success_rate': avg_success / batch_size if batch_size > 0 else 0
            }
            
            print(f"\n📈 统计结果:")
            print(f"  平均总时间: {avg_time:.2f}秒")
            print(f"  平均每张:   {avg_per_image:.2f}秒")
            print(f"  成功率:     {avg_success/batch_size*100:.1f}%")
            print()
    
    return results

def compare_sequential_vs_parallel(image_paths, count=5):
    """对比顺序处理 vs 并行处理的效率"""
    if len(image_paths) < count:
        print(f"⚠️ 图片数量不足（需要{count}张，实际{len(image_paths)}张），跳过对比测试")
        return
    
    print(f"\n{'='*70}")
    print(f"📊 顺序处理 vs 并行处理效率对比")
    print(f"{'='*70}")
    print(f"测试图片数: {count}")
    print(f"{'-'*70}\n")
    
    # 准备图片数据
    images_base64 = []
    for img_path in image_paths[:count]:
        with open(img_path, 'rb') as f:
            image_data = f.read()
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            images_base64.append(image_base64)
    
    # 顺序处理（模拟）
    print("🔄 顺序处理测试（逐个处理）...")
    sequential_times = []
    
    for i, img_base64 in enumerate(images_base64):
        data = {
            'questions': [{
                'image': img_base64,
                'question_type': 'TEXT',
                'force_reanalyze': False
            }]
        }
        start_time = time.time()
        try:
            response = requests.post(
                f'{BASE_URL}/api/questions/analyze/batch',
                json=data,
                headers={'Content-Type': 'application/json'},
                timeout=60
            )
            elapsed = time.time() - start_time
            sequential_times.append(elapsed)
            status = "✅" if response.status_code == 200 else "❌"
            print(f"  图片{i+1}: {elapsed:.2f}秒 {status}")
        except Exception as e:
            elapsed = time.time() - start_time
            sequential_times.append(elapsed)
            print(f"  图片{i+1}: {elapsed:.2f}秒 ❌")
    
    sequential_total = sum(sequential_times)
    sequential_avg = mean(sequential_times) if sequential_times else 0
    
    print(f"\n📈 顺序处理统计:")
    print(f"  总时间: {sequential_total:.2f}秒")
    print(f"  平均每张: {sequential_avg:.2f}秒")
    
    # 并行处理
    print(f"\n⚡ 并行处理测试（批量处理）...")
    questions = [
        {
            'image': img_base64,
            'question_type': 'TEXT',
            'force_reanalyze': False
        }
        for img_base64 in images_base64
    ]
    data = {'questions': questions}
    
    parallel_times = []
    for i in range(3):
        print(f"  第{i+1}/3次...", end=' ', flush=True)
        start_time = time.time()
        try:
            response = requests.post(
                f'{BASE_URL}/api/questions/analyze/batch',
                json=data,
                headers={'Content-Type': 'application/json'},
                timeout=120
            )
            elapsed = time.time() - start_time
            parallel_times.append(elapsed)
            if response.status_code == 200:
                result = response.json()
                success = result.get('success_count', 0)
                print(f"✅ {elapsed:.2f}秒 - 成功: {success}/{count}")
            else:
                print(f"❌ {elapsed:.2f}秒 - HTTP {response.status_code}")
        except Exception as e:
            elapsed = time.time() - start_time
            parallel_times.append(elapsed)
            print(f"❌ {elapsed:.2f}秒 - 错误")
    
    if parallel_times:
        parallel_avg = mean(parallel_times)
        parallel_per_image = parallel_avg / count
        speedup = sequential_total / parallel_avg if parallel_avg > 0 else 0
        efficiency = (speedup / count * 100) if speedup > 0 else 0
        
        print(f"\n📈 并行处理统计:")
        print(f"  平均总时间: {parallel_avg:.2f}秒")
        print(f"  平均每张:   {parallel_per_image:.2f}秒")
        
        print(f"\n📊 效率对比:")
        print(f"  顺序总时间: {sequential_total:.2f}秒")
        print(f"  并行总时间: {parallel_avg:.2f}秒")
        print(f"  加速比:     {speedup:.2f}x")
        print(f"  并行效率:   {efficiency:.1f}%")
        print(f"  时间节省:   {sequential_total - parallel_avg:.2f}秒 ({((sequential_total - parallel_avg) / sequential_total * 100):.1f}%)")

def generate_summary_report(single_result, batch_results):
    """生成测试总结报告"""
    print(f"\n{'='*70}")
    print(f"📋 测试总结报告")
    print(f"{'='*70}")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"API地址: {BASE_URL}")
    
    if single_result:
        print(f"\n📊 单张图片OCR性能:")
        print(f"  平均处理时间: {single_result['avg']:.2f}秒")
        print(f"  最快处理时间: {single_result['min']:.2f}秒")
        print(f"  成功率: {single_result['success_rate']*100:.1f}%")
    
    if batch_results:
        print(f"\n📊 批量处理性能:")
        print(f"{'批量大小':<10} {'总时间(秒)':<15} {'每张(秒)':<15} {'成功率':<10}")
        print(f"{'-'*60}")
        for batch_size in sorted(batch_results.keys()):
            data = batch_results[batch_size]
            print(f"{batch_size:<10} {data['total_time']:<15.2f} {data['per_image']:<15.2f} {data['success_rate']*100:<10.1f}%")
    
    print(f"\n{'='*70}")
    print(f"✅ 测试完成！")
    print(f"{'='*70}\n")

def main():
    """主函数"""
    print("="*70)
    print("🚀 AI处理速度测试 - 火山引擎OCR优化版")
    print("="*70)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
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
    test_images = load_test_images(10)
    if not test_images:
        print("❌ 未找到测试图片")
        return
    
    print(f"✅ 找到 {len(test_images)} 张测试图片\n")
    
    # 运行测试
    single_result = None
    batch_results = {}
    
    # 测试1：单张图片OCR速度
    if test_images:
        single_result = test_single_ocr_speed(test_images[0], rounds=5)
    
    # 测试2：批量处理速度
    if len(test_images) >= 5:
        batch_results = test_batch_ocr_speed(test_images, batch_sizes=[1, 3, 5])
    
    # 测试3：顺序 vs 并行对比
    if len(test_images) >= 5:
        compare_sequential_vs_parallel(test_images, count=5)
    
    # 生成总结报告
    generate_summary_report(single_result, batch_results)

if __name__ == '__main__':
    main()

