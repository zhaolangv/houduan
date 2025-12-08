"""
测试 API v2 接口 - 测试所有接口
"""
import requests
import json
import os
import sys

# 设置控制台编码为UTF-8（Windows）
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

API_BASE_URL = 'http://localhost:5000'

def test_analyze_question(image_path, raw_text=None, question_text=None, options=None, 
                          question_type='TEXT', force_reanalyze=False):
    """
    测试题目内容分析接口（只返回题目内容，不返回答案和解析）
    
    Args:
        image_path: 图片路径
        raw_text: 前端OCR原始文本（可选）
        question_text: 前端提取的题干（可选）
        options: 前端提取的选项（可选，列表）
        question_type: 题目类型（默认TEXT）
        force_reanalyze: 是否强制重新分析（默认False）
    """
    url = f'{API_BASE_URL}/api/questions/analyze'
    
    # 检查图片文件是否存在
    if not os.path.exists(image_path):
        print(f"❌ 图片文件不存在: {image_path}")
        return None
    
    # 准备表单数据
    files = {
        'image': (os.path.basename(image_path), open(image_path, 'rb'), 'image/jpeg')
    }
    
    data = {
        'question_type': question_type,
        'force_reanalyze': str(force_reanalyze).lower()
    }
    
    if raw_text:
        data['raw_text'] = raw_text
    if question_text:
        data['question_text'] = question_text
    if options:
        if isinstance(options, list):
            data['options'] = json.dumps(options)
        else:
            data['options'] = options
    
    print(f"\n{'='*60}")
    print(f"【测试1】题目内容分析接口 (POST /api/questions/analyze)")
    print(f"{'='*60}")
    print(f"图片: {image_path}")
    if raw_text:
        print(f"前端OCR文本: {raw_text[:100]}...")
    if question_text:
        print(f"前端题干: {question_text[:100]}...")
    if options:
        print(f"前端选项: {options}")
    print(f"题目类型: {question_type}")
    print(f"强制重新分析: {force_reanalyze}")
    print(f"\n发送请求到: {url}")
    
    try:
        response = requests.post(url, files=files, data=data, timeout=180)
        files['image'][1].close()  # 关闭文件
        
        print(f"\n响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ 请求成功！")
            print(f"\n题目ID: {result.get('id')}")
            print(f"题干: {result.get('question_text', '')[:200]}...")
            print(f"选项数: {len(result.get('options', []))}")
            if result.get('options'):
                print("选项:")
                for opt in result.get('options', [])[:4]:
                    print(f"  - {opt}")
            print(f"OCR置信度: {result.get('ocr_confidence')}")
            print(f"\n状态信息:")
            print(f"  - 来自缓存: {result.get('from_cache')}")
            print(f"  - 是重复题: {result.get('is_duplicate')}")
            print(f"  - 存入数据库: {result.get('saved_to_db')}")
            if result.get('similarity_score') is not None:
                print(f"  - 相似度: {result.get('similarity_score'):.3f}")
            if result.get('matched_question_id'):
                print(f"  - 匹配题目ID: {result.get('matched_question_id')}")
            
            # 注意：此接口不返回答案和解析
            if 'correct_answer' in result:
                print(f"\n⚠️ 警告：此接口不应返回答案和解析，但响应中包含: correct_answer={result.get('correct_answer')}")
            if 'explanation' in result:
                print(f"⚠️ 警告：此接口不应返回答案和解析，但响应中包含: explanation")
            
            return result
        else:
            print(f"\n❌ 请求失败！")
            print(f"错误信息: {response.text}")
            return None
            
    except requests.exceptions.Timeout:
        print(f"\n❌ 请求超时（超过180秒）")
        return None
    except requests.exceptions.ConnectionError:
        print(f"\n❌ 连接失败，请确保Flask服务正在运行: {API_BASE_URL}")
        return None
    except Exception as e:
        print(f"\n❌ 请求出错: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_get_question_detail(question_id):
    """
    测试获取题目详情接口（返回答案、解析、标签等）
    
    Args:
        question_id: 题目ID
    """
    url = f'{API_BASE_URL}/api/questions/{question_id}/detail'
    
    print(f"\n{'='*60}")
    print(f"【测试2】获取题目详情接口 (GET /api/questions/{question_id}/detail)")
    print(f"{'='*60}")
    print(f"题目ID: {question_id}")
    print(f"\n发送请求到: {url}")
    
    try:
        response = requests.get(url, timeout=60)
        
        print(f"\n响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ 请求成功！")
            print(f"\n题目ID: {result.get('id')}")
            print(f"正确答案: {result.get('correct_answer')}")
            print(f"解析: {result.get('explanation', '')[:200]}...")
            print(f"标签: {result.get('tags', [])}")
            print(f"知识点: {result.get('knowledge_points', [])}")
            print(f"难度: {result.get('difficulty')}")
            print(f"\n答案版本数: {len(result.get('answer_versions', []))}")
            if result.get('answer_versions'):
                for i, ans in enumerate(result.get('answer_versions', [])[:3], 1):
                    print(f"\n答案版本 {i}:")
                    print(f"  来源: {ans.get('source_name')} ({ans.get('source_type')})")
                    print(f"  答案: {ans.get('answer')}")
                    print(f"  置信度: {ans.get('confidence')}")
                    print(f"  解析: {ans.get('explanation', '')[:150]}...")
            
            return result
        else:
            print(f"\n❌ 请求失败！")
            print(f"错误信息: {response.text}")
            return None
            
    except requests.exceptions.Timeout:
        print(f"\n❌ 请求超时（超过60秒）")
        return None
    except requests.exceptions.ConnectionError:
        print(f"\n❌ 连接失败，请确保Flask服务正在运行: {API_BASE_URL}")
        return None
    except Exception as e:
        print(f"\n❌ 请求出错: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_stats():
    """测试统计接口"""
    url = f'{API_BASE_URL}/api/stats'
    print(f"\n{'='*60}")
    print(f"【测试3】统计接口 (GET /api/stats)")
    print(f"{'='*60}")
    print(f"发送请求到: {url}")
    
    try:
        response = requests.get(url, timeout=10)
        print(f"\n响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ 请求成功！")
            print(f"\n统计信息:")
            for key, value in result.items():
                print(f"  {key}: {value}")
            return result
        else:
            print(f"\n❌ 请求失败！")
            print(f"错误信息: {response.text}")
            return None
            
    except requests.exceptions.ConnectionError:
        print(f"\n❌ 连接失败，请确保Flask服务正在运行: {API_BASE_URL}")
        return None
    except Exception as e:
        print(f"\n❌ 请求出错: {e}")
        return None

def test_upload_image(image_path):
    """
    测试上传图片接口
    
    Args:
        image_path: 图片路径
    """
    url = f'{API_BASE_URL}/api/upload'
    
    if not os.path.exists(image_path):
        print(f"❌ 图片文件不存在: {image_path}")
        return None
    
    print(f"\n{'='*60}")
    print(f"【测试4】上传图片接口 (POST /api/upload)")
    print(f"{'='*60}")
    print(f"图片: {image_path}")
    print(f"\n发送请求到: {url}")
    
    try:
        files = {
            'file': (os.path.basename(image_path), open(image_path, 'rb'), 'image/jpeg')
        }
        
        response = requests.post(url, files=files, timeout=30)
        files['file'][1].close()  # 关闭文件
        
        print(f"\n响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ 请求成功！")
            if result.get('success'):
                print(f"图片URL: {result.get('data', {}).get('image_url')}")
                print(f"文件名: {result.get('data', {}).get('filename')}")
            else:
                print(f"错误: {result.get('error')}")
            return result
        else:
            print(f"\n❌ 请求失败！")
            print(f"错误信息: {response.text}")
            return None
            
    except requests.exceptions.ConnectionError:
        print(f"\n❌ 连接失败，请确保Flask服务正在运行: {API_BASE_URL}")
        return None
    except Exception as e:
        print(f"\n❌ 请求出错: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_clear():
    """测试清空接口"""
    url = f'{API_BASE_URL}/api/clear'
    print(f"\n{'='*60}")
    print(f"【测试5】清空接口 (POST /api/clear)")
    print(f"{'='*60}")
    print(f"发送请求到: {url}")
    
    try:
        response = requests.post(url, timeout=10)
        print(f"\n响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ 请求成功！")
            print(f"结果: {result}")
            return result
        else:
            print(f"\n❌ 请求失败！")
            print(f"错误信息: {response.text}")
            return None
            
    except requests.exceptions.ConnectionError:
        print(f"\n❌ 连接失败，请确保Flask服务正在运行: {API_BASE_URL}")
        return None
    except Exception as e:
        print(f"\n❌ 请求出错: {e}")
        return None

def main():
    """主函数 - 测试所有接口"""
    print("="*60)
    print("API v2 完整测试脚本")
    print("="*60)
    
    # 查找测试图片
    test_images = [
        'uploads/ceshi/90a9659945b66d6f5937ad5cc36b726.jpg',
        'uploads/ceshi/8dc054a6a22466641906e1fab93a61e.jpg',
        'uploads/2025/12/05/8dc054a6a22466641906e1fab93a61e.jpg',
    ]
    
    test_image = None
    for img_path in test_images:
        if os.path.exists(img_path):
            test_image = img_path
            break
    
    if not test_image:
        # 查找uploads目录下的任何图片
        uploads_dir = 'uploads'
        if os.path.exists(uploads_dir):
            for root, dirs, files in os.walk(uploads_dir):
                for file in files:
                    if file.lower().endswith(('.jpg', '.jpeg', '.png')):
                        test_image = os.path.join(root, file)
                        break
                if test_image:
                    break
    
    # 如果提供了命令行参数，使用它作为图片路径
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        if os.path.exists(image_path):
            test_image = image_path
    
    if not test_image:
        print("\n⚠️ 未找到测试图片，请手动指定图片路径")
        print("用法: python test_api_v2.py [图片路径]")
        return
    
    print(f"\n使用测试图片: {test_image}")
    
    # ========== 测试1: 统计接口 ==========
    print("\n" + "="*60)
    print("开始测试所有接口...")
    print("="*60)
    stats_result = test_stats()
    
    # ========== 测试2: 题目内容分析接口 ==========
    analyze_result = test_analyze_question(
        image_path=test_image,
        question_type='TEXT',
        force_reanalyze=False
    )
    
    if not analyze_result:
        print("\n❌ 题目分析失败，无法继续测试详情接口")
        return
    
    question_id = analyze_result.get('id')
    if not question_id:
        print("\n❌ 未获取到题目ID，无法继续测试详情接口")
        return
    
    # ========== 测试3: 获取题目详情接口 ==========
    detail_result = test_get_question_detail(question_id)
    
    # ========== 测试4: 上传图片接口 ==========
    upload_result = test_upload_image(test_image)
    
    # ========== 测试5: 清空接口（可选，谨慎使用）==========
    # 注释掉，避免清空数据
    # clear_result = test_clear()
    
    # ========== 测试总结 ==========
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    print(f"✅ 统计接口: {'成功' if stats_result else '失败'}")
    print(f"✅ 题目内容分析接口: {'成功' if analyze_result else '失败'}")
    print(f"✅ 题目详情接口: {'成功' if detail_result else '失败'}")
    print(f"✅ 上传图片接口: {'成功' if upload_result else '失败'}")
    print("\n" + "="*60)
    
    # 验证接口响应格式
    if analyze_result:
        print("\n【验证】题目内容分析接口响应格式:")
        required_fields = ['id', 'question_text', 'options', 'from_cache', 'is_duplicate', 'saved_to_db']
        missing_fields = [f for f in required_fields if f not in analyze_result]
        if missing_fields:
            print(f"  ⚠️ 缺少字段: {missing_fields}")
        else:
            print(f"  ✅ 所有必需字段都存在")
        
        # 检查不应包含的字段
        should_not_have = ['correct_answer', 'explanation', 'answer_versions']
        has_forbidden = [f for f in should_not_have if f in analyze_result and analyze_result.get(f)]
        if has_forbidden:
            print(f"  ⚠️ 不应包含的字段: {has_forbidden}")
        else:
            print(f"  ✅ 未包含答案相关字段（符合规范）")
    
    if detail_result:
        print("\n【验证】题目详情接口响应格式:")
        required_fields = ['id', 'question_id', 'answer_versions', 'correct_answer', 'explanation']
        missing_fields = [f for f in required_fields if f not in detail_result]
        if missing_fields:
            print(f"  ⚠️ 缺少字段: {missing_fields}")
        else:
            print(f"  ✅ 所有必需字段都存在")

if __name__ == '__main__':
    main()

