"""
直接测试火山引擎API调用
"""
import os
import requests
import base64
import json
import logging

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# 读取环境变量
api_key = os.getenv('VOLCENGINE_API_KEY', 'bebcec52-ce96-4f6f-bb1e-9a1b49ad5cf8')
vision_model = os.getenv('VOLCENGINE_VISION_MODEL', 'doubao-seed-1-6-251015')

print(f"API Key: {api_key[:20]}...")
print(f"Vision Model: {vision_model}\n")

# 读取一张测试图片
test_image_path = 'uploads/ceshi/24d3fbe709e8224ca229aa0a79f9ebe.jpg'
with open(test_image_path, 'rb') as f:
    image_data = f.read()
    image_base64 = base64.b64encode(image_data).decode('utf-8')

print(f"图片大小: {len(image_data) / 1024:.2f} KB")
print(f"Base64长度: {len(image_base64)} 字符\n")

# 构建请求
url = "https://ark.cn-beijing.volces.com/api/v3/responses"

data = {
    "model": vision_model,
    "input": [
        {
            "role": "user",
            "content": [
                {
                    "type": "input_image",
                    "image_url": f"data:image/jpeg;base64,{image_base64}"
                },
                {
                    "type": "input_text",
                    "text": "提取题目和选项文字，忽略界面元素。只返回题干和选项（A/B/C/D格式），不要包含标题、页码、统计信息。"
                }
            ]
        }
    ],
    # 注意：火山引擎API可能不支持parameters字段，参数应该直接在顶层
    # "temperature": 0.1,
    # "max_tokens": 2000,
    # "top_p": 0.9
}

headers = {
    'Authorization': f'Bearer {api_key}',
    'Content-Type': 'application/json'
}

print("🚀 发送请求到火山引擎API...")
print(f"URL: {url}")
print(f"Headers: {dict(headers)}\n")

try:
    response = requests.post(url, json=data, headers=headers, timeout=30)
    
    print(f"状态码: {response.status_code}")
    print(f"响应头: {dict(response.headers)}\n")
    
    if response.status_code == 200:
        result = response.json()
        print("✅ 请求成功!")
        print(f"响应结构: {list(result.keys())}")
        if 'output' in result:
            print(f"Output类型: {type(result['output'])}")
            print(f"Output内容: {result['output']}")
    else:
        print(f"❌ 请求失败: HTTP {response.status_code}")
        print(f"响应内容: {response.text[:1000]}")
        
except requests.exceptions.Timeout:
    print("❌ 请求超时")
except requests.exceptions.RequestException as e:
    print(f"❌ 请求异常: {e}")
    if hasattr(e, 'response') and e.response is not None:
        print(f"响应状态码: {e.response.status_code}")
        print(f"响应内容: {e.response.text[:1000]}")
except Exception as e:
    print(f"❌ 其他错误: {e}")
    import traceback
    traceback.print_exc()

