"""
批量题目分析接口测试脚本
"""
import requests
import json
import base64
import sys
import os

# 修复Windows控制台编码问题
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# API基础URL
BASE_URL = 'http://localhost:5000'

def test_batch_multipart():
    """测试multipart/form-data格式的批量接口"""
    print("=" * 60)
    print("测试1: multipart/form-data 格式批量接口")
    print("=" * 60)
    
    # 检查是否有测试图片
    test_images = []
    ceshi_dir = 'uploads/ceshi'
    if os.path.exists(ceshi_dir):
        for file in os.listdir(ceshi_dir):
            if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                test_images.append(os.path.join(ceshi_dir, file))
                if len(test_images) >= 3:  # 最多3张测试图片
                    break
    
    if not test_images:
        print("⚠️ 未找到测试图片，跳过multipart测试")
        print("提示：在uploads/ceshi目录中放置一些图片文件")
        return
    
    print(f"找到 {len(test_images)} 张测试图片")
    
    # 准备multipart数据
    files = []
    for img_path in test_images:
        files.append(('images[]', (os.path.basename(img_path), open(img_path, 'rb'), 'image/png')))
    
    data = {
        'force_reanalyze': 'false'
    }
    
    try:
        print(f"\n发送请求到: {BASE_URL}/api/questions/analyze/batch")
        print(f"图片数量: {len(test_images)}")
        
        response = requests.post(
            f'{BASE_URL}/api/questions/analyze/batch',
            files=files,
            data=data,
            timeout=120  # 批量处理可能需要更长时间
        )
        
        # 关闭文件
        for _, file_tuple in files:
            if hasattr(file_tuple[1], 'close'):
                file_tuple[1].close()
        
        print(f"\n状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ 批量处理成功!")
            print(f"总数: {result.get('total', 0)}")
            print(f"成功: {result.get('success_count', 0)}")
            print(f"失败: {result.get('failed_count', 0)}")
            
            print("\n详细结果:")
            for idx, r in enumerate(result.get('results', []), 1):
                if r['success']:
                    q = r['question']
                    print(f"\n题目 {idx}: ✅ 成功")
                    print(f"  - ID: {q.get('id')}")
                    print(f"  - 题干: {q.get('question_text', '')[:50]}...")
                    print(f"  - 选项数: {len(q.get('options', []))}")
                    print(f"  - 来自缓存: {q.get('from_cache', False)}")
                else:
                    err = r['error']
                    print(f"\n题目 {idx}: ❌ 失败")
                    print(f"  - 错误: {err.get('message', '未知错误')}")
        else:
            print(f"\n❌ 请求失败")
            print(f"响应: {response.text}")
    
    except Exception as e:
        print(f"\n❌ 测试出错: {e}")
        import traceback
        traceback.print_exc()


def test_batch_json():
    """测试JSON格式的批量接口"""
    print("\n" + "=" * 60)
    print("测试2: application/json 格式批量接口")
    print("=" * 60)
    
    # 检查是否有测试图片
    test_images = []
    ceshi_dir = 'uploads/ceshi'
    if os.path.exists(ceshi_dir):
        for file in os.listdir(ceshi_dir):
            if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                test_images.append(os.path.join(ceshi_dir, file))
                if len(test_images) >= 2:  # 最多2张测试图片
                    break
    
    if not test_images:
        print("⚠️ 未找到测试图片，跳过JSON测试")
        print("提示：在uploads/ceshi目录中放置一些图片文件")
        return
    
    print(f"找到 {len(test_images)} 张测试图片")
    
    # 准备JSON数据（base64编码图片）
    questions = []
    for img_path in test_images:
        try:
            with open(img_path, 'rb') as f:
                image_data = f.read()
                image_base64 = base64.b64encode(image_data).decode('utf-8')
                
                questions.append({
                    'image': image_base64,
                    'question_type': 'TEXT',
                    'force_reanalyze': False
                })
        except Exception as e:
            print(f"⚠️ 读取图片失败 {img_path}: {e}")
            continue
    
    if not questions:
        print("⚠️ 没有可用的图片数据")
        return
    
    data = {
        'questions': questions
    }
    
    try:
        print(f"\n发送请求到: {BASE_URL}/api/questions/analyze/batch")
        print(f"题目数量: {len(questions)}")
        
        response = requests.post(
            f'{BASE_URL}/api/questions/analyze/batch',
            json=data,
            headers={'Content-Type': 'application/json'},
            timeout=120
        )
        
        print(f"\n状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ 批量处理成功!")
            print(f"总数: {result.get('total', 0)}")
            print(f"成功: {result.get('success_count', 0)}")
            print(f"失败: {result.get('failed_count', 0)}")
            
            print("\n详细结果:")
            for idx, r in enumerate(result.get('results', []), 1):
                if r['success']:
                    q = r['question']
                    print(f"\n题目 {idx}: ✅ 成功")
                    print(f"  - ID: {q.get('id')}")
                    print(f"  - 题干: {q.get('question_text', '')[:50]}...")
                    print(f"  - 选项数: {len(q.get('options', []))}")
                else:
                    err = r['error']
                    print(f"\n题目 {idx}: ❌ 失败")
                    print(f"  - 错误: {err.get('message', '未知错误')}")
        else:
            print(f"\n❌ 请求失败")
            print(f"响应: {response.text}")
    
    except Exception as e:
        print(f"\n❌ 测试出错: {e}")
        import traceback
        traceback.print_exc()


def test_batch_error_cases():
    """测试错误情况"""
    print("\n" + "=" * 60)
    print("测试3: 错误情况测试")
    print("=" * 60)
    
    # 测试1: 缺少图片
    print("\n[测试3.1] 缺少图片文件")
    try:
        response = requests.post(
            f'{BASE_URL}/api/questions/analyze/batch',
            data={'force_reanalyze': 'false'},
            timeout=10
        )
        print(f"状态码: {response.status_code}")
        if response.status_code == 400:
            print("✅ 正确返回400错误")
        else:
            print(f"⚠️ 预期400，实际{response.status_code}")
    except Exception as e:
        print(f"❌ 请求出错: {e}")
    
    # 测试2: 批量大小超限
    print("\n[测试3.2] 批量大小超限（模拟）")
    # 这里不实际发送21个文件，只测试逻辑
    print("提示：实际测试需要准备21+张图片")
    
    # 测试3: JSON格式错误
    print("\n[测试3.3] JSON格式错误")
    try:
        response = requests.post(
            f'{BASE_URL}/api/questions/analyze/batch',
            json={'invalid': 'data'},
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        print(f"状态码: {response.status_code}")
        if response.status_code == 400:
            print("✅ 正确返回400错误")
        else:
            print(f"⚠️ 预期400，实际{response.status_code}")
    except Exception as e:
        print(f"❌ 请求出错: {e}")


def main():
    """主函数"""
    print("批量题目分析接口测试")
    print("=" * 60)
    print(f"API地址: {BASE_URL}")
    print("=" * 60)
    
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
    
    # 运行测试
    test_batch_multipart()
    test_batch_json()
    test_batch_error_cases()
    
    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)


if __name__ == '__main__':
    main()

