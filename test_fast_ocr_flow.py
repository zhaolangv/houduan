"""
测试快速OCR完整流程
"""
import sys
import os

# 修复Windows控制台编码问题
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 测试图片
test_img = 'uploads/ceshi/24d3fbe709e8224ca229aa0a79f9ebe.jpg'

print("="*70)
print("测试快速OCR完整流程")
print("="*70)

# 1. 测试OCR提取
print("\n1️⃣ 测试OCR提取...")
from ocr_service import get_ocr_service
ocr_service = get_ocr_service()
print(f"   OCR引擎: {type(ocr_service.ocr_engine).__name__ if ocr_service.ocr_engine else None}")

raw_text = ocr_service.extract_text(test_img)
print(f"   文字长度: {len(raw_text) if raw_text else 0}")
print(f"   前200字符: {raw_text[:200] if raw_text else 'None'}...")

if not raw_text or len(raw_text.strip()) <= 20:
    print("   ❌ OCR识别文字太少，无法继续")
    sys.exit(1)

# 2. 测试规则过滤
print("\n2️⃣ 测试规则过滤...")
from fast_ocr_extractor import get_fast_extractor
extractor = get_fast_extractor()
result = extractor.extract_question_from_text(raw_text)

print(f"   题干长度: {len(result['question_text'])}")
print(f"   题干内容: {result['question_text'][:100]}...")
print(f"   选项数: {len(result['options'])}")
for i, opt in enumerate(result['options'][:4]):
    print(f"   选项{i+1}: {opt[:50]}...")
print(f"   置信度: {result['confidence']:.2f}")
print(f"   是否完整: {result['is_complete']}")

# 3. 评估
print("\n3️⃣ 评估结果...")
if result['is_complete'] and result['confidence'] >= 0.7:
    print("   ✅ 规则过滤成功，可以使用快速OCR")
    print(f"   提取方法: fast_ocr_rule")
else:
    print("   ⚠️ 规则过滤结果不完整，需要fallback到AI")
    print(f"   原因: 置信度={result['confidence']:.2f}, 完整={result['is_complete']}")

print("\n" + "="*70)

