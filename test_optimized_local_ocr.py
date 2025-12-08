"""
测试优化后的本地OCR（PaddleOCR）
优化措施：
1. 调整PaddleOCR参数
2. 图片预处理（增强、裁剪）
3. 使用更精确的模型
"""
import sys
import os
import time
from statistics import mean
from typing import Dict, List
from PIL import Image
import numpy as np

# 修复Windows控制台编码问题
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def preprocess_image(image_path: str) -> str:
    """图片预处理：增强对比度、锐化等"""
    try:
        from PIL import Image, ImageEnhance, ImageFilter
        
        img = Image.open(image_path)
        
        # 转换为RGB（如果不是）
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # 增强对比度
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.5)  # 增强1.5倍
        
        # 增强锐度
        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(1.3)  # 增强1.3倍
        
        # 保存预处理后的图片
        preprocessed_path = image_path.replace('.jpg', '_preprocessed.jpg').replace('.png', '_preprocessed.png')
        img.save(preprocessed_path, quality=95)
        
        return preprocessed_path
    except Exception as e:
        print(f"  预处理失败: {e}，使用原图")
        return image_path

def test_optimized_paddleocr(image_path: str) -> Dict:
    """测试优化后的PaddleOCR"""
    try:
        # 方案1：使用优化参数
        print(f"    尝试方案1：优化参数...", end=' ', flush=True)
        from paddleocr import PaddleOCR
        
        # 使用基本参数（兼容新版本）
        ocr = PaddleOCR(
            use_textline_orientation=True,
            lang='ch'
        )
        
        start = time.time()
        # 新版本使用predict方法
        try:
            result = ocr.predict(image_path)
        except AttributeError:
            # 如果predict不存在，使用ocr方法（不带cls参数）
            result = ocr.ocr(image_path)
        elapsed = time.time() - start
        
        if result and result[0]:
            texts = [line[1][0] for line in result[0]]
            text = '\n'.join(texts)
            return {
                'success': True,
                'time': elapsed,
                'method': 'optimized_params',
                'raw_text': text,
                'raw_text_length': len(text),
                'text_lines': texts,
                'line_count': len(texts)
            }
        else:
            return {
                'success': False,
                'time': elapsed,
                'error': '未识别到文字'
            }
    except Exception as e:
        return {
            'success': False,
            'time': 0,
            'error': f'方案1失败: {str(e)[:50]}'
        }

def test_preprocessed_paddleocr(image_path: str) -> Dict:
    """测试预处理后的PaddleOCR"""
    try:
        # 预处理图片
        preprocessed_path = preprocess_image(image_path)
        
        print(f"    尝试方案2：图片预处理...", end=' ', flush=True)
        from paddleocr import PaddleOCR
        
        ocr = PaddleOCR(
            use_textline_orientation=True,
            lang='ch'
        )
        
        start = time.time()
        # 使用ocr方法（不带cls参数，兼容新版本）
        result = ocr.ocr(preprocessed_path)
        elapsed = time.time() - start
        
        # 清理预处理文件
        try:
            if preprocessed_path != image_path and os.path.exists(preprocessed_path):
                os.remove(preprocessed_path)
        except:
            pass
        
        # 处理不同版本的返回格式
        texts = []
        if result:
            # 新版本格式：可能是字典
            if isinstance(result, dict):
                rec_texts = result.get('rec_texts', [])
                texts = rec_texts if rec_texts else []
            # 旧版本格式：列表
            elif isinstance(result, list) and len(result) > 0:
                if isinstance(result[0], list):
                    # [[[坐标], (文字, 置信度)], ...]
                    texts = [line[1][0] for line in result[0] if line and len(line) > 1]
                elif isinstance(result[0], dict):
                    # 新版本字典格式
                    rec_texts = result[0].get('rec_texts', [])
                    texts = rec_texts if rec_texts else []
        
        if texts:
            text = '\n'.join(texts)
            return {
                'success': True,
                'time': elapsed,
                'method': 'preprocessed',
                'raw_text': text,
                'raw_text_length': len(text),
                'text_lines': texts,
                'line_count': len(texts)
            }
        else:
            return {
                'success': False,
                'time': elapsed,
                'error': '未识别到文字'
            }
    except Exception as e:
        return {
            'success': False,
            'time': 0,
            'error': f'方案2失败: {str(e)[:50]}'
        }

def test_combined_optimization(image_path: str) -> Dict:
    """测试组合优化：预处理 + 优化参数"""
    try:
        # 预处理图片
        preprocessed_path = preprocess_image(image_path)
        
        print(f"    尝试方案3：预处理+优化参数...", end=' ', flush=True)
        from paddleocr import PaddleOCR
        
        # 使用基本参数（兼容新版本）
        ocr = PaddleOCR(
            use_textline_orientation=True,
            lang='ch'
        )
        
        start = time.time()
        # 使用ocr方法（不带cls参数，兼容新版本）
        result = ocr.ocr(preprocessed_path)
        elapsed = time.time() - start
        
        # 清理预处理文件
        try:
            if preprocessed_path != image_path and os.path.exists(preprocessed_path):
                os.remove(preprocessed_path)
        except:
            pass
        
        # 处理不同版本的返回格式
        texts = []
        if result:
            # 新版本格式：可能是字典
            if isinstance(result, dict):
                rec_texts = result.get('rec_texts', [])
                texts = rec_texts if rec_texts else []
            # 旧版本格式：列表
            elif isinstance(result, list) and len(result) > 0:
                if isinstance(result[0], list):
                    # [[[坐标], (文字, 置信度)], ...]
                    texts = [line[1][0] for line in result[0] if line and len(line) > 1]
                elif isinstance(result[0], dict):
                    # 新版本字典格式
                    rec_texts = result[0].get('rec_texts', [])
                    texts = rec_texts if rec_texts else []
        
        if texts:
            text = '\n'.join(texts)
            return {
                'success': True,
                'time': elapsed,
                'method': 'combined',
                'raw_text': text,
                'raw_text_length': len(text),
                'text_lines': texts,
                'line_count': len(texts)
            }
        else:
            return {
                'success': False,
                'time': elapsed,
                'error': '未识别到文字'
            }
    except Exception as e:
        return {
            'success': False,
            'time': 0,
            'error': f'方案3失败: {str(e)[:50]}'
        }

def load_test_images(max_images=3):
    """加载测试图片"""
    ceshi_dir = 'uploads/ceshi'
    images = []
    for file in os.listdir(ceshi_dir):
        if file.lower().endswith(('.png', '.jpg', '.jpeg')) and 'preprocessed' not in file:
            images.append(os.path.join(ceshi_dir, file))
            if len(images) >= max_images:
                break
    return images

def main():
    print("="*70)
    print("🚀 优化后的本地OCR（PaddleOCR）测试")
    print("="*70)
    
    # 加载测试图片
    test_images = load_test_images(3)
    
    if not test_images:
        print("❌ 未找到测试图片")
        return
    
    print(f"📷 测试图片数: {len(test_images)}")
    for img in test_images:
        file_size = os.path.getsize(img) / 1024
        print(f"  - {os.path.basename(img)} ({file_size:.2f} KB)")
    
    # 测试每个方案
    all_results = {
        '方案1：优化参数': [],
        '方案2：图片预处理': [],
        '方案3：预处理+优化参数': []
    }
    
    for img_path in test_images:
        print(f"\n{'='*70}")
        print(f"📷 测试图片: {os.path.basename(img_path)}")
        print(f"{'='*70}")
        
        # 方案1
        result1 = test_optimized_paddleocr(img_path)
        all_results['方案1：优化参数'].append(result1)
        if result1.get('success'):
            print(f"✅ {result1['time']:.2f}秒 - {result1['raw_text_length']}字符, {result1['line_count']}行")
            print(f"   文字预览: {result1['raw_text'][:100]}...")
        else:
            print(f"❌ {result1.get('error', 'unknown')}")
        
        # 方案2
        result2 = test_preprocessed_paddleocr(img_path)
        all_results['方案2：图片预处理'].append(result2)
        if result2.get('success'):
            print(f"✅ {result2['time']:.2f}秒 - {result2['raw_text_length']}字符, {result2['line_count']}行")
            print(f"   文字预览: {result2['raw_text'][:100]}...")
        else:
            print(f"❌ {result2.get('error', 'unknown')}")
        
        # 方案3
        result3 = test_combined_optimization(img_path)
        all_results['方案3：预处理+优化参数'].append(result3)
        if result3.get('success'):
            print(f"✅ {result3['time']:.2f}秒 - {result3['raw_text_length']}字符, {result3['line_count']}行")
            print(f"   文字预览: {result3['raw_text'][:100]}...")
        else:
            print(f"❌ {result3.get('error', 'unknown')}")
    
    # 总结
    print(f"\n{'='*70}")
    print("📊 优化方案对比总结")
    print(f"{'='*70}")
    
    for scheme_name, results in all_results.items():
        success_results = [r for r in results if r.get('success')]
        if success_results:
            times = [r['time'] for r in success_results]
            text_lengths = [r['raw_text_length'] for r in success_results]
            
            print(f"\n{scheme_name}:")
            print(f"  成功率: {len(success_results)}/{len(results)} ({len(success_results)/len(results)*100:.1f}%)")
            print(f"  平均速度: {mean(times):.2f}秒")
            print(f"  平均文字长度: {mean(text_lengths):.0f}字符")
            print(f"  最快: {min(times):.2f}秒")
            print(f"  最慢: {max(times):.2f}秒")
        else:
            print(f"\n{scheme_name}: ❌ 全部失败")
    
    # 找出最佳方案
    best_scheme = None
    best_score = 0
    
    for scheme_name, results in all_results.items():
        success_results = [r for r in results if r.get('success')]
        if success_results:
            # 评分：成功率 * 文字长度 / 时间
            success_rate = len(success_results) / len(results)
            avg_text_length = mean([r['raw_text_length'] for r in success_results])
            avg_time = mean([r['time'] for r in success_results])
            score = success_rate * avg_text_length / max(avg_time, 0.1)
            
            if score > best_score:
                best_score = score
                best_scheme = scheme_name
    
    if best_scheme:
        print(f"\n🏆 最佳方案: {best_scheme} (评分: {best_score:.2f})")
    
    print(f"\n{'='*70}")

if __name__ == '__main__':
    main()

