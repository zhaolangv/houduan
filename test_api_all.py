"""
测试所有API接口 - 模拟前端请求
"""
import os
import sys
import requests
import json
import base64
from pathlib import Path
import time
from typing import List, Dict

# 配置
API_BASE = 'http://localhost:5000'
TEST_IMAGE_DIR = 'uploads/ceshi'

def load_test_images() -> List[str]:
    """加载测试图片路径"""
    if not os.path.exists(TEST_IMAGE_DIR):
        print(f"❌ 测试图片目录不存在: {TEST_IMAGE_DIR}")
        return []
    
    image_files = []
    for ext in ['jpg', 'jpeg', 'png', 'bmp']:
        image_files.extend(Path(TEST_IMAGE_DIR).glob(f'*.{ext}'))
        image_files.extend(Path(TEST_IMAGE_DIR).glob(f'*.{ext.upper()}'))
    
    # 过滤掉预处理文件
    image_files = [str(f) for f in image_files if '_preprocessed' not in str(f)]
    
    print(f"📷 找到 {len(image_files)} 张测试图片")
    return image_files[:5]  # 限制为5张用于测试


def image_to_base64(image_path: str) -> str:
    """将图片转换为base64编码"""
    with open(image_path, 'rb') as f:
        image_data = f.read()
        base64_data = base64.b64encode(image_data).decode('utf-8')
        return f"data:image/jpeg;base64,{base64_data}"


def test_health_check():
    """测试健康检查接口"""
    print("\n" + "=" * 60)
    print("1️⃣  测试健康检查接口: GET /api/health")
    print("=" * 60)
    
    try:
        response = requests.get(f"{API_BASE}/api/health", timeout=5)
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 服务状态: {data.get('status')}")
            print(f"📊 检查项:")
            for check_name, check_data in data.get('checks', {}).items():
                print(f"   - {check_name}: {check_data.get('status')}")
            return True
        else:
            print(f"❌ 请求失败: {response.text}")
            return False
    except Exception as e:
        print(f"❌ 请求异常: {e}")
        return False


def test_upload_image(image_path: str):
    """测试图片上传接口"""
    print("\n" + "=" * 60)
    print("2️⃣  测试图片上传接口: POST /api/upload")
    print("=" * 60)
    
    try:
        with open(image_path, 'rb') as f:
            files = {'file': (os.path.basename(image_path), f, 'image/jpeg')}
            response = requests.post(f"{API_BASE}/api/upload", files=files, timeout=30)
        
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print(f"✅ 上传成功")
                print(f"📁 文件名: {data.get('data', {}).get('filename')}")
                print(f"📂 路径: {data.get('data', {}).get('path')}")
                return data.get('data', {}).get('path')
            else:
                print(f"❌ 上传失败: {data.get('error')}")
                return None
        else:
            print(f"❌ 请求失败: {response.text}")
            return None
    except Exception as e:
        print(f"❌ 请求异常: {e}")
        return None


def test_analyze_question(image_path: str):
    """测试题目分析接口"""
    print("\n" + "=" * 60)
    print("3️⃣  测试题目分析接口: POST /api/questions/analyze")
    print("=" * 60)
    
    try:
        with open(image_path, 'rb') as f:
            files = {'image': (os.path.basename(image_path), f, 'image/jpeg')}
            data = {
                'question_type': 'TEXT',
                'force_reanalyze': 'false'
            }
            response = requests.post(
                f"{API_BASE}/api/questions/analyze",
                files=files,
                data=data,
                timeout=60
            )
        
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 分析成功")
            print(f"📝 题目ID: {result.get('id')}")
            print(f"📄 题干: {result.get('question_text', '')[:100]}...")
            print(f"📋 选项数: {len(result.get('options', []))}")
            print(f"🏷️  类型: {result.get('question_type', 'TEXT')}")
            print(f"💾 来自缓存: {result.get('from_cache', False)}")
            
            if result.get('options'):
                for opt in result.get('options', [])[:4]:
                    print(f"   {opt}")
            
            return result.get('id')
        else:
            print(f"❌ 请求失败: {response.text[:200]}")
            return None
    except Exception as e:
        print(f"❌ 请求异常: {e}")
        return None


def test_extract_batch(image_paths: List[str], max_workers: int = 3):
    """测试批量提取接口（使用本地OCR+DeepSeek）"""
    print("\n" + "=" * 60)
    print(f"4️⃣  测试批量提取接口: POST /api/questions/extract/batch (并发数: {max_workers})")
    print("=" * 60)
    
    try:
        files = []
        for img_path in image_paths:
            with open(img_path, 'rb') as f:
                files.append(('images[]', (os.path.basename(img_path), f.read(), 'image/jpeg')))
        
        data = {'max_workers': str(max_workers)}
        
        start_time = time.time()
        response = requests.post(
            f"{API_BASE}/api/questions/extract/batch",
            files=files,
            data=data,
            timeout=300  # 5分钟超时
        )
        elapsed = time.time() - start_time
        
        print(f"状态码: {response.status_code}")
        print(f"⏱️  总耗时: {elapsed:.1f}秒")
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                stats = result.get('statistics', {})
                print(f"✅ 批量提取成功")
                print(f"📊 统计信息:")
                print(f"   - 总数: {stats.get('total')}")
                print(f"   - 成功: {stats.get('success_count')}")
                print(f"   - 失败: {stats.get('failed_count')}")
                print(f"   - 总耗时: {stats.get('total_time', 0):.1f}秒")
                print(f"   - 平均每题: {stats.get('avg_time_per_question', 0):.1f}秒")
                print(f"   - 总费用: ¥{stats.get('total_cost', 0):.6f}")
                
                # 显示每个结果
                print(f"\n📝 详细结果:")
                for idx, item in enumerate(result.get('results', []), 1):
                    if item.get('success'):
                        print(f"\n   题目{idx}: ✅ 成功")
                        print(f"   题干: {item.get('question_text', '')[:80]}...")
                        print(f"   类型: {item.get('question_type', 'TEXT')}")
                        if item.get('preliminary_answer'):
                            print(f"   初步答案: {item.get('preliminary_answer')}")
                        if item.get('answer_reason'):
                            print(f"   理由: {item.get('answer_reason', '')[:50]}...")
                        print(f"   耗时: {item.get('total_time', 0):.1f}秒 (OCR: {item.get('ocr_time', 0):.1f}秒, AI: {item.get('ai_time', 0):.1f}秒)")
                        print(f"   费用: ¥{item.get('cost', 0):.6f}")
                    else:
                        print(f"\n   题目{idx}: ❌ 失败 - {item.get('error', 'unknown')}")
                
                return True
            else:
                print(f"❌ 批量提取失败: {result.get('error')}")
                return False
        else:
            print(f"❌ 请求失败: {response.text[:500]}")
            return False
    except Exception as e:
        print(f"❌ 请求异常: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_extract_batch_json(image_paths: List[str], max_workers: int = 3):
    """测试批量提取接口（JSON格式，base64编码）"""
    print("\n" + "=" * 60)
    print(f"5️⃣  测试批量提取接口（JSON格式）: POST /api/questions/extract/batch")
    print("=" * 60)
    
    try:
        images_data = []
        for img_path in image_paths:
            base64_data = image_to_base64(img_path)
            images_data.append({
                'filename': os.path.basename(img_path),
                'data': base64_data
            })
        
        payload = {
            'images': images_data,
            'max_workers': max_workers
        }
        
        start_time = time.time()
        response = requests.post(
            f"{API_BASE}/api/questions/extract/batch",
            json=payload,
            timeout=300
        )
        elapsed = time.time() - start_time
        
        print(f"状态码: {response.status_code}")
        print(f"⏱️  总耗时: {elapsed:.1f}秒")
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                stats = result.get('statistics', {})
                print(f"✅ 批量提取成功（JSON格式）")
                print(f"📊 成功: {stats.get('success_count')}/{stats.get('total')}")
                return True
            else:
                print(f"❌ 批量提取失败: {result.get('error')}")
                if result.get('details'):
                    print(f"   错误详情: {result.get('details')}")
                return False
        else:
            print(f"❌ 请求失败 (状态码: {response.status_code})")
            try:
                error_data = response.json()
                print(f"   错误信息: {error_data.get('error', '未知错误')}")
                if error_data.get('details'):
                    print(f"   错误详情: {error_data.get('details')}")
            except:
                print(f"   响应内容: {response.text[:500]}")
            return False
    except Exception as e:
        print(f"❌ 请求异常: {e}")
        return False


def test_get_question_detail(question_id: str):
    """测试获取题目详情接口"""
    print("\n" + "=" * 60)
    print(f"6️⃣  测试题目详情接口: GET /api/questions/{question_id}/detail")
    print("=" * 60)
    
    if not question_id:
        print("❌ 没有题目ID，跳过此测试")
        return False
    
    try:
        response = requests.get(
            f"{API_BASE}/api/questions/{question_id}/detail",
            timeout=60
        )
        
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 获取详情成功")
            print(f"📝 题目ID: {result.get('id')}")
            print(f"✅ 正确答案: {result.get('correct_answer')}")
            print(f"📚 答案版本数: {len(result.get('answer_versions', []))}")
            print(f"🏷️  标签: {result.get('tags', [])}")
            
            if result.get('answer_versions'):
                for ans in result.get('answer_versions', []):
                    print(f"\n   答案版本:")
                    print(f"   - 来源: {ans.get('source_name')} ({ans.get('source_type')})")
                    print(f"   - 答案: {ans.get('answer')}")
                    print(f"   - 置信度: {ans.get('confidence')}")
                    print(f"   - 解析: {ans.get('explanation', '')[:100]}...")
            
            return True
        else:
            print(f"❌ 请求失败: {response.text[:200]}")
            return False
    except Exception as e:
        print(f"❌ 请求异常: {e}")
        return False


def test_analyze_batch(image_paths: List[str]):
    """测试批量分析接口（存入数据库）"""
    print("\n" + "=" * 60)
    print("7️⃣  测试批量分析接口: POST /api/questions/analyze/batch")
    print("=" * 60)
    
    try:
        files = []
        for img_path in image_paths:
            with open(img_path, 'rb') as f:
                files.append(('images[]', (os.path.basename(img_path), f.read(), 'image/jpeg')))
        
        data = {
            'question_types': json.dumps(['TEXT'] * len(image_paths)),
            'force_reanalyze': 'false'
        }
        
        start_time = time.time()
        response = requests.post(
            f"{API_BASE}/api/questions/analyze/batch",
            files=files,
            data=data,
            timeout=300
        )
        elapsed = time.time() - start_time
        
        print(f"状态码: {response.status_code}")
        print(f"⏱️  总耗时: {elapsed:.1f}秒")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 批量分析成功")
            print(f"📊 成功: {result.get('success_count')}/{result.get('total')}")
            
            return True
        else:
            print(f"❌ 请求失败 (状态码: {response.status_code})")
            try:
                error_data = response.json()
                print(f"   错误信息: {error_data.get('error', '未知错误')}")
                if error_data.get('details'):
                    print(f"   错误详情: {error_data.get('details')}")
            except:
                print(f"   响应内容: {response.text[:500]}")
            return False
    except Exception as e:
        print(f"❌ 请求异常: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试流程"""
    print("=" * 60)
    print("🚀 API接口测试 - 模拟前端请求")
    print("=" * 60)
    print(f"API地址: {API_BASE}")
    
    # 1. 健康检查
    if not test_health_check():
        print("\n❌ 服务不可用，请先启动服务: python app.py")
        return
    
    # 2. 加载测试图片
    image_paths = load_test_images()
    if not image_paths:
        print("\n❌ 没有找到测试图片")
        return
    
    # 3. 测试上传接口
    uploaded_path = None
    if image_paths:
        uploaded_path = test_upload_image(image_paths[0])
    
    # 4. 测试分析接口
    question_id = None
    if image_paths:
        question_id = test_analyze_question(image_paths[0])
    
    # 5. 测试批量提取接口（文件上传）
    if len(image_paths) >= 2:
        test_extract_batch(image_paths[:2], max_workers=2)
    
    # 6. 测试批量提取接口（JSON格式）
    if len(image_paths) >= 2:
        test_extract_batch_json(image_paths[:2], max_workers=2)
    
    # 7. 测试题目详情接口
    if question_id:
        test_get_question_detail(question_id)
    
    # 8. 测试批量分析接口
    if len(image_paths) >= 2:
        test_analyze_batch(image_paths[:2])
    
    print("\n" + "=" * 60)
    print("✅ 所有接口测试完成！")
    print("=" * 60)


if __name__ == '__main__':
    main()
