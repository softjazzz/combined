#!/usr/bin/env python3
"""
测试API密钥加载
验证从数据库中加载的API密钥是否正确
"""

import os
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client
import base64

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# 加载环境变量
load_dotenv(project_root / '.env')
load_dotenv(project_root / 'backend' / '.env')

# Supabase配置
SUPABASE_URL = os.getenv('SUPABASE_URL') or os.getenv('VITE_SUPABASE_URL')
SUPABASE_ANON_KEY = os.getenv('SUPABASE_ANON_KEY') or os.getenv('VITE_SUPABASE_ANON_KEY')

async def test_api_key_loading():
    """测试API密钥加载"""
    print("🧪 测试API密钥加载...")
    
    # 初始化Supabase客户端
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    
    try:
        # 查询默认配置
        response = supabase.table('user_llm_configs').select('''
            *,
            provider:llm_api_providers(*),
            model:llm_models(*)
        ''').is_('user_id', 'null').eq('config_name', 'default').execute()
        
        if not response.data:
            print("❌ 未找到默认配置")
            return False
        
        config = response.data[0]
        print("✅ 找到默认配置:")
        print(f"   提供商: {config['provider']['provider_name']}")
        print(f"   模型: {config['model']['model_name']}")
        print(f"   端点: {config['provider']['base_endpoint']}")
        
        # 测试API密钥解密
        encrypted_key = config.get('api_key_encrypted')
        if encrypted_key:
            print(f"   加密密钥: {encrypted_key[:20]}...")
            
            # 尝试base64解码
            try:
                decrypted_key = base64.b64decode(encrypted_key.encode()).decode()
                print(f"   解密密钥: {decrypted_key[:10]}...")
                
                # 验证是否是正确的API密钥格式
                if decrypted_key.startswith('sk-'):
                    print("✅ API密钥格式正确")
                    return True
                else:
                    print("❌ API密钥格式不正确")
                    return False
                    
            except Exception as e:
                print(f"❌ 解密失败: {e}")
                return False
        else:
            print("❌ 未找到加密的API密钥")
            return False
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

async def main():
    """主函数"""
    print("=" * 50)
    print("🔧 API密钥加载测试")
    print("=" * 50)
    
    success = await test_api_key_loading()
    
    if success:
        print("\n✅ 测试通过！API密钥已正确保存和加载")
        print("\n📋 下一步:")
        print("1. 打开前端LLM配置页面")
        print("2. 页面应该自动加载阿里云配置")
        print("3. API密钥字段应该自动填充")
        print("4. 点击'测试连接'应该成功")
    else:
        print("\n❌ 测试失败，请检查配置")

if __name__ == "__main__":
    asyncio.run(main())
