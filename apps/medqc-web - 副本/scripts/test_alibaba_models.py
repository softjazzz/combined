#!/usr/bin/env python3
"""
测试阿里云模型可用性
检查数据库中的每个阿里云模型是否在API中可用
"""

import os
import sys
import asyncio
import httpx
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client

# 加载环境变量
load_dotenv('.env')
load_dotenv('backend/.env')

SUPABASE_URL = os.getenv('SUPABASE_URL') or os.getenv('VITE_SUPABASE_URL')
SUPABASE_ANON_KEY = os.getenv('SUPABASE_ANON_KEY') or os.getenv('VITE_SUPABASE_ANON_KEY')
API_KEY = "sk-f1fa15b00fb042a9a80943a40e142daf"
API_ENDPOINT = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

async def test_model(model_code: str) -> dict:
    """测试单个模型"""
    headers = {
        'Authorization': f'Bearer {API_KEY}',
        'Content-Type': 'application/json'
    }
    
    request_body = {
        "model": model_code,
        "messages": [
            {
                "role": "user",
                "content": "测试"
            }
        ],
        "temperature": 0.1,
        "max_tokens": 10
    }
    
    try:
        timeout = httpx.Timeout(10.0, connect=10.0, read=30.0, write=10.0, pool=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(API_ENDPOINT, headers=headers, json=request_body)
            
            if response.status_code == 200:
                return {
                    'model': model_code,
                    'status': 'success',
                    'status_code': response.status_code,
                    'message': '✅ 可用'
                }
            else:
                error_info = response.text[:200] if response.text else 'No response body'
                return {
                    'model': model_code,
                    'status': 'error',
                    'status_code': response.status_code,
                    'message': f'❌ 错误: {response.status_code}',
                    'error': error_info
                }
                
    except Exception as e:
        return {
            'model': model_code,
            'status': 'exception',
            'status_code': None,
            'message': f'❌ 异常: {str(e)[:100]}',
            'error': str(e)
        }

async def test_all_models():
    """测试所有模型"""
    print("🧪 测试阿里云模型可用性...")
    print("=" * 80)
    
    # 获取数据库中的模型
    supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    response = supabase.table('llm_models').select('*').eq('provider_id', '4000612e-6c03-4ed0-8ba8-709c903513f8').order('sort_order').execute()
    
    models = response.data
    print(f"📊 数据库中共有 {len(models)} 个阿里云模型")
    print()
    
    # 测试每个模型
    results = []
    for i, model in enumerate(models, 1):
        model_code = model['model_code']
        model_name = model['model_name']
        
        print(f"{i:2d}. 测试 {model_code:30} ({model_name})")
        
        result = await test_model(model_code)
        results.append(result)
        
        print(f"    {result['message']}")
        if result['status'] != 'success':
            print(f"    详情: {result.get('error', 'Unknown error')[:100]}")
        print()
        
        # 避免请求过于频繁
        await asyncio.sleep(1)
    
    # 统计结果
    success_count = sum(1 for r in results if r['status'] == 'success')
    error_count = len(results) - success_count
    
    print("=" * 80)
    print("📊 测试结果统计:")
    print(f"  ✅ 可用模型: {success_count}")
    print(f"  ❌ 不可用模型: {error_count}")
    print()
    
    if success_count > 0:
        print("✅ 可用的模型:")
        for result in results:
            if result['status'] == 'success':
                print(f"  - {result['model']}")
        print()
    
    if error_count > 0:
        print("❌ 不可用的模型:")
        for result in results:
            if result['status'] != 'success':
                print(f"  - {result['model']} (状态码: {result['status_code']})")
        print()
    
    # 建议
    print("💡 建议:")
    if error_count > 0:
        print("1. 将不可用的模型在数据库中设置为 is_active = false")
        print("2. 或者从前端配置文件中移除这些模型")
        print("3. 检查模型名称是否正确（可能需要更新为最新的模型代码）")
    else:
        print("1. 所有模型都可用，配置正确！")
    
    return results

async def main():
    """主函数"""
    print("🔧 阿里云模型可用性测试工具")
    print("=" * 80)
    
    results = await test_all_models()
    
    # 可选：生成修复脚本
    error_models = [r for r in results if r['status'] != 'success']
    if error_models:
        print("\n🔧 自动修复脚本:")
        print("以下SQL可以禁用不可用的模型:")
        print()
        for result in error_models:
            print(f"UPDATE llm_models SET is_active = false WHERE model_code = '{result['model']}';")

if __name__ == "__main__":
    asyncio.run(main())
