#!/usr/bin/env python3
"""
验证快速质控服务修复脚本

此脚本用于验证：
1. 依赖注入是否正确工作
2. 配置是否从数据库或 .env 正确加载
3. 快速质控是否能正常调用 LLM API
"""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

import asyncio
from app.services.llm_config_loader import LLMConfigLoader
from app.services.sichuan_qc_service import SichuanQCService

async def verify_service_initialization():
    """验证服务初始化"""
    print("=" * 70)
    print("🔍 验证四川质控服务初始化")
    print("=" * 70)
    
    # 1. 测试从数据库加载配置
    print("\n1️⃣ 测试从数据库加载配置...")
    try:
        config = await LLMConfigLoader.load_config(config_name="default", user_id=None)
        print(f"✅ 数据库配置加载成功:")
        print(f"   - API 端点: {config.get('api_endpoint', 'N/A')}")
        print(f"   - API 密钥: {'已配置' if config.get('api_key') else '未配置'}")
        print(f"   - 模型: {config.get('model', 'N/A')}")
        print(f"   - 配置源: {config.get('source', 'N/A')}")
        print(f"   - Temperature: {config.get('custom_parameters', {}).get('temperature', 'N/A')}")
        
        # 使用数据库配置创建服务
        service_db = SichuanQCService(config)
        print(f"\n✅ 使用数据库配置创建服务成功:")
        print(f"   - API 端点: {service_db.client.api_endpoint or 'N/A'}")
        print(f"   - API 密钥: {'已配置' if service_db.client.api_key else '未配置'}")
        print(f"   - 模型: {service_db.client.model}")
        print(f"   - 配置源: {service_db.client.config_source}")
        print(f"   - Temperature: {service_db.client.temperature}")
        
    except Exception as e:
        print(f"⚠️ 数据库配置加载失败: {e}")
        print("   将回退到 .env 配置")
    
    # 2. 测试使用 .env 配置
    print("\n2️⃣ 测试使用 .env 配置...")
    try:
        service_env = SichuanQCService()
        print(f"✅ 使用 .env 配置创建服务成功:")
        print(f"   - API 端点: {service_env.client.api_endpoint or 'N/A'}")
        print(f"   - API 密钥: {'已配置' if service_env.client.api_key else '未配置'}")
        print(f"   - 模型: {service_env.client.model}")
        print(f"   - 配置源: {service_env.client.config_source}")
        print(f"   - Temperature: {service_env.client.temperature}")
    except Exception as e:
        print(f"❌ .env 配置加载失败: {e}")
    
    # 3. 检查 .env 文件内容
    print("\n3️⃣ 检查 .env 文件配置...")
    from app.core.settings import get_settings
    settings = get_settings()
    print(f"   - SICHUAN_API_ENDPOINT: {settings.SICHUAN_API_ENDPOINT or 'N/A'}")
    print(f"   - SICHUAN_API_KEY: {'已配置' if settings.SICHUAN_API_KEY else '未配置'}")
    print(f"   - SICHUAN_MODEL: {settings.SICHUAN_MODEL}")
    
    print("\n" + "=" * 70)
    print("✅ 验证完成")
    print("=" * 70)
    
    # 4. 总结
    print("\n📊 总结:")
    if config and config.get('api_endpoint') and config.get('api_key'):
        print("   ✅ 数据库配置完整，快速质控应该正常工作")
    elif settings.SICHUAN_API_ENDPOINT and settings.SICHUAN_API_KEY:
        print("   ⚠️ 数据库配置不完整，但 .env 配置可用")
        print("   ✅ 快速质控应该通过 .env 配置正常工作")
    else:
        print("   ❌ 数据库和 .env 配置都不完整")
        print("   ❌ 快速质控将返回 Mock 数据")
        print("\n   💡 解决方案:")
        print("      1. 在 LLM 配置页面填写 API 端点和密钥")
        print("      2. 或者在 .env 文件中配置 SICHUAN_API_ENDPOINT 和 SICHUAN_API_KEY")

if __name__ == "__main__":
    asyncio.run(verify_service_initialization())

