#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API调用超时测试 - 诊断阿里云DashScope API问题
"""

import requests
import json
import time
from typing import Dict, Any

def test_api_call():
    """测试API调用，添加详细的错误诊断"""
    
    print("🔧 开始API连接诊断...")
    
    # 配置
    api_key = "sk-f1fa15b00fb042a9a80943a40e142daf"
    base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    model = "qwen-turbo-latest"
    
    # 测试数据
    test_prompt = "请简单回答：1+1等于几？"
    
    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": model,
        "messages": [
            {
                "role": "user", 
                "content": test_prompt
            }
        ],
        "max_tokens": 100,
        "temperature": 0.1,
        "stream": False
    }
    
    print(f"📡 API端点: {url}")
    print(f"🔑 API Key: {api_key[:10]}...")
    print(f"🤖 模型: {model}")
    print(f"💬 测试提示: {test_prompt}")
    
    # 分步测试
    try:
        print("\n⏱️  开始API调用 (超时设置: 10秒)...")
        start_time = time.time()
        
        response = requests.post(
            url, 
            headers=headers, 
            json=data, 
            timeout=10  # 10秒超时
        )
        
        elapsed = time.time() - start_time
        print(f"✅ API调用完成，耗时: {elapsed:.2f}秒")
        
        print(f"📊 HTTP状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("🎉 API调用成功！")
            print(f"📝 响应内容: {json.dumps(result, ensure_ascii=False, indent=2)}")
            
            # 提取回答
            if "choices" in result and len(result["choices"]) > 0:
                answer = result["choices"][0]["message"]["content"]
                print(f"🤖 LLM回答: {answer}")
            
        else:
            print(f"❌ API调用失败")
            print(f"📄 错误响应: {response.text}")
            
    except requests.exceptions.Timeout:
        print("⏰ API调用超时 (10秒)")
        print("💡 可能原因:")
        print("   1. 网络延迟过高")
        print("   2. API服务器响应慢")
        print("   3. 模型推理时间过长")
        
    except requests.exceptions.ConnectionError as e:
        print(f"🌐 网络连接错误: {e}")
        print("💡 可能原因:")
        print("   1. DNS解析失败")
        print("   2. 网络不可达")
        print("   3. 防火墙阻止")
        
    except requests.exceptions.RequestException as e:
        print(f"📡 请求异常: {e}")
        
    except Exception as e:
        print(f"💥 未知错误: {e}")

if __name__ == "__main__":
    test_api_call()

