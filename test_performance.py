"""
性能测试脚本 - 测试AI处理速度
"""
import requests
import json
import base64
import sys
import os
import time
from datetime import datetime
from statistics import mean, median

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

def test_single_question_speed(image_path):
    """测试单个题目处理速度"""
    print(f"\n{'='*60}")
    print(f"测试1: 单个题目处理速度")
    print(f"{'='*60}")
    print(f"图片: {os.path.basename(image_path)}")
    
    # 读取图片并编码为base64
    with open(image_path, 'rb') as f:
        image_data = f.read()
        image_base64 = base64.b64encode(image_data).decode('utf-8')
    
    data = {
        'questions': [{
            'image': image_base64,
            'question_type': 'TEXT',
            'force_reanalyze': False
        }]
    }
    
    # 测试3次，取平均值
    times = []
    for i in range(3):
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
                success = result.get('success_count', 0) > 0
                print(f"  第{i+1}次: {elapsed:.2f}秒 - {'✅ 成功' if success else '❌ 失败'}")
            else:
                print(f"  第{i+1}次: {elapsed:.2f}秒 - ❌ HTTP {response.status_code}")
        except Exception as e:
            end_time = time.time()
            elapsed = end_time - start_time
            times.append(elapsed)
            print(f"  第{i+1}次: {elapsed:.2f}秒 - ❌ 错误: {str(e)[:50]}")
    
    if times:
        avg_time = mean(times)
        median_time = median(times)
        min_time = min(times)
        max_time = max(times)
        print(f"\n📊 统计结果:")
        print(f"  平均时间: {avg_time:.2f}秒")
        print(f"  中位数: {median_time:.2f}秒")
        print(f"  最快: {min_time:.2f}秒")
        print(f"  最慢: {max_time:.2f}秒")
        return avg_time
    return None

def test_batch_speed(image_paths, batch_sizes=[1, 3, 5]):
    """测试批量处理速度"""
    print(f"\n{'='*60}")
    print(f"测试2: 批量处理速度对比")
    print(f"{'='*60}")
    
    # 准备所有图片的base64数据
    images_base64 = []
    for img_path in image_paths:
        with open(img_path, 'rb') as f:
            image_data = f.read()
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            images_base64.append(image_base64)
    
    results = {}
    
    for batch_size in batch_sizes:
        if batch_size > len(images_base64):
            continue
        
        print(f"\n📦 批量大小: {batch_size}")
        
        # 准备批量数据
        questions = [
            {
                'image': img_base64,
                'question_type': 'TEXT',
                'force_reanalyze': False
            }
            for img_base64 in images_base64[:batch_size]
        ]
        
        data = {'questions': questions}
        
        # 测试3次
        times = []
        success_count = 0
        
        for i in range(3):
            start_time = time.time()
            try:
                response = requests.post(
                    f'{BASE_URL}/api/questions/analyze/batch',
                    json=data,
                    headers={'Content-Type': 'application/json'},
                    timeout=180
                )
                end_time = time.time()
                elapsed = end_time - start_time
                times.append(elapsed)
                
                if response.status_code == 200:
                    result = response.json()
                    success = result.get('success_count', 0)
                    success_count += success
                    print(f"  第{i+1}次: {elapsed:.2f}秒 - 成功: {success}/{batch_size}")
                else:
                    print(f"  第{i+1}次: {elapsed:.2f}秒 - ❌ HTTP {response.status_code}")
            except Exception as e:
                end_time = time.time()
                elapsed = end_time - start_time
                times.append(elapsed)
                print(f"  第{i+1}次: {elapsed:.2f}秒 - ❌ 错误: {str(e)[:50]}")
        
        if times:
            avg_time = mean(times)
            avg_per_image = avg_time / batch_size
            results[batch_size] = {
                'total_time': avg_time,
                'per_image': avg_per_image,
                'success_rate': success_count / (3 * batch_size) if success_count > 0 else 0
            }
            print(f"  📊 平均总时间: {avg_time:.2f}秒")
            print(f"  📊 平均每张: {avg_per_image:.2f}秒")
            print(f"  📊 成功率: {results[batch_size]['success_rate']*100:.1f}%")
    
    return results

def test_parallel_efficiency(image_paths):
    """测试并行处理效率"""
    print(f"\n{'='*60}")
    print(f"测试3: 并行处理效率分析")
    print(f"{'='*60}")
    
    if len(image_paths) < 5:
        print("⚠️ 图片数量不足，跳过并行效率测试")
        return
    
    # 准备5张图片
    images_base64 = []
    for img_path in image_paths[:5]:
        with open(img_path, 'rb') as f:
            image_data = f.read()
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            images_base64.append(image_base64)
    
    # 测试1：顺序处理（模拟）
    print(f"\n📊 顺序处理（模拟）:")
    single_times = []
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
                timeout=120
            )
            elapsed = time.time() - start_time
            single_times.append(elapsed)
            print(f"  图片{i+1}: {elapsed:.2f}秒")
        except Exception as e:
            elapsed = time.time() - start_time
            single_times.append(elapsed)
            print(f"  图片{i+1}: {elapsed:.2f}秒 - ❌ 错误")
    
    sequential_total = sum(single_times)
    sequential_avg = mean(single_times) if single_times else 0
    
    # 测试2：批量并行处理
    print(f"\n📊 批量并行处理:")
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
        start_time = time.time()
        try:
            response = requests.post(
                f'{BASE_URL}/api/questions/analyze/batch',
                json=data,
                headers={'Content-Type': 'application/json'},
                timeout=180
            )
            elapsed = time.time() - start_time
            parallel_times.append(elapsed)
            if response.status_code == 200:
                result = response.json()
                success = result.get('success_count', 0)
                print(f"  第{i+1}次: {elapsed:.2f}秒 - 成功: {success}/{len(images_base64)}")
            else:
                print(f"  第{i+1}次: {elapsed:.2f}秒 - ❌ HTTP {response.status_code}")
        except Exception as e:
            elapsed = time.time() - start_time
            parallel_times.append(elapsed)
            print(f"  第{i+1}次: {elapsed:.2f}秒 - ❌ 错误")
    
    if parallel_times:
        parallel_avg = mean(parallel_times)
        speedup = sequential_total / parallel_avg if parallel_avg > 0 else 0
        efficiency = speedup / len(images_base64) * 100 if speedup > 0 else 0
        
        print(f"\n📊 效率对比:")
        print(f"  顺序处理总时间: {sequential_total:.2f}秒")
        print(f"  顺序处理平均: {sequential_avg:.2f}秒/张")
        print(f"  并行处理平均: {parallel_avg:.2f}秒")
        print(f"  并行处理平均: {parallel_avg/len(images_base64):.2f}秒/张")
        print(f"  加速比: {speedup:.2f}x")
        print(f"  并行效率: {efficiency:.1f}%")

def test_api_response_time():
    """测试API响应时间"""
    print(f"\n{'='*60}")
    print(f"测试4: API响应时间测试")
    print(f"{'='*60}")
    
    endpoints = [
        ('/api/test', 'GET', None),
        ('/api/stats', 'GET', None),
        ('/api/health', 'GET', None),
    ]
    
    for endpoint, method, data in endpoints:
        times = []
        for i in range(5):
            start_time = time.time()
            try:
                if method == 'GET':
                    response = requests.get(f'{BASE_URL}{endpoint}', timeout=10)
                else:
                    response = requests.post(f'{BASE_URL}{endpoint}', json=data, timeout=10)
                elapsed = time.time() - start_time
                times.append(elapsed)
            except Exception as e:
                elapsed = time.time() - start_time
                times.append(elapsed)
        
        if times:
            avg_time = mean(times)
            print(f"{endpoint}: 平均 {avg_time*1000:.1f}ms (最快: {min(times)*1000:.1f}ms, 最慢: {max(times)*1000:.1f}ms)")

def generate_report(results):
    """生成性能报告"""
    print(f"\n{'='*60}")
    print(f"📊 性能测试报告")
    print(f"{'='*60}")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\n批量处理性能:")
    
    if results:
        print(f"{'批量大小':<10} {'总时间(秒)':<15} {'每张(秒)':<15} {'成功率':<10}")
        print(f"{'-'*60}")
        for batch_size, data in sorted(results.items()):
            print(f"{batch_size:<10} {data['total_time']:<15.2f} {data['per_image']:<15.2f} {data['success_rate']*100:<10.1f}%")
    
    print(f"\n{'='*60}")

def main():
    """主函数"""
    print("="*60)
    print("AI处理速度性能测试")
    print("="*60)
    print(f"API地址: {BASE_URL}")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
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
    
    print(f"✅ 找到 {len(test_images)} 张测试图片")
    
    # 运行测试
    results = {}
    
    # 测试1：单个题目速度
    if test_images:
        single_time = test_single_question_speed(test_images[0])
        if single_time:
            results[1] = {
                'total_time': single_time,
                'per_image': single_time,
                'success_rate': 1.0
            }
    
    # 测试2：批量处理速度
    if len(test_images) >= 5:
        batch_results = test_batch_speed(test_images, batch_sizes=[1, 3, 5])
        results.update(batch_results)
    
    # 测试3：并行效率
    if len(test_images) >= 5:
        test_parallel_efficiency(test_images)
    
    # 测试4：API响应时间
    test_api_response_time()
    
    # 生成报告
    generate_report(results)
    
    print(f"\n{'='*60}")
    print("✅ 性能测试完成!")
    print(f"{'='*60}")

if __name__ == '__main__':
    main()

