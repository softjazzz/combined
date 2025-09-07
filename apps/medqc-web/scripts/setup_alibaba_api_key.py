#!/usr/bin/env python3
"""
固化阿里云API密钥到数据库
将阿里云通义千问的API密钥保存到数据库中，避免每次都需要输入
"""

import os
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client
import json
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

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    print("❌ 错误: 未找到Supabase配置")
    print(f"SUPABASE_URL: {SUPABASE_URL}")
    print(f"SUPABASE_ANON_KEY: {'***' + SUPABASE_ANON_KEY[-10:] if SUPABASE_ANON_KEY else 'None'}")
    sys.exit(1)

# 阿里云API密钥
ALIBABA_API_KEY = "sk-f1fa15b00fb042a9a80943a40e142daf"

# 加密密钥（在生产环境中应该使用环境变量）
ENCRYPTION_KEY = "medqc-llm-config-key-2024"

def encrypt_api_key(api_key: str) -> str:
    """加密API密钥 - 使用简单base64编码"""
    # 为了简化，先使用base64编码
    # 后续可以在前端修改解密逻辑来兼容
    return base64.b64encode(api_key.encode()).decode()

def decrypt_api_key(encrypted_key: str) -> str:
    """解密API密钥"""
    return base64.b64decode(encrypted_key.encode()).decode()

async def setup_alibaba_config():
    """设置阿里云配置"""
    print("🚀 开始设置阿里云API密钥...")
    
    # 初始化Supabase客户端
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    print(f"✅ Supabase客户端初始化成功: {SUPABASE_URL}")
    
    try:
        # 1. 确保阿里云提供商存在
        print("📝 检查阿里云提供商...")
        provider_response = supabase.table('llm_api_providers').select('*').eq('provider_code', 'alibaba').execute()
        
        if not provider_response.data:
            print("📝 创建阿里云提供商...")
            provider_data = {
                'provider_code': 'alibaba',
                'provider_name': '阿里通义千问',
                'base_endpoint': 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions',
                'request_format': 'openai',
                'requires_api_key': True,
                'description': '阿里云大模型服务，企业级可靠性，兼容OpenAI格式',
                'features': ['企业级', '高并发', '多模态', '中文优化'],
                'is_active': True,
                'sort_order': 1
            }
            provider_response = supabase.table('llm_api_providers').insert(provider_data).execute()
            print("✅ 阿里云提供商创建成功")
        else:
            print("✅ 阿里云提供商已存在")
        
        provider_id = provider_response.data[0]['id']
        
        # 2. 确保阿里云模型存在
        print("📝 检查阿里云模型...")
        models_to_create = [
            {
                'model_code': 'qwen-plus',
                'model_name': 'Qwen-Plus',
                'display_name': '通义千问Plus',
                'description': '平衡性能和成本的选择',
                'context_length': 32768,
                'pricing_tier': 'medium',
                'capabilities': ['平衡性能', '中等成本'],
                'is_default': True,
                'sort_order': 1
            },
            {
                'model_code': 'qwen-turbo',
                'model_name': 'Qwen-Turbo',
                'display_name': '通义千问Turbo',
                'description': '快速响应，适合简单任务',
                'context_length': 8192,
                'pricing_tier': 'low',
                'capabilities': ['快速响应', '成本低'],
                'is_default': False,
                'sort_order': 2
            },
            {
                'model_code': 'qwen-max',
                'model_name': 'Qwen-Max',
                'display_name': '通义千问Max',
                'description': '最强性能，适合复杂任务',
                'context_length': 32768,
                'pricing_tier': 'high',
                'capabilities': ['最强性能', '复杂推理'],
                'is_default': False,
                'sort_order': 3
            }
        ]
        
        for model_data in models_to_create:
            model_response = supabase.table('llm_models').select('*').eq('provider_id', provider_id).eq('model_code', model_data['model_code']).execute()
            
            if not model_response.data:
                model_data['provider_id'] = provider_id
                supabase.table('llm_models').insert(model_data).execute()
                print(f"✅ 模型 {model_data['model_code']} 创建成功")
            else:
                print(f"✅ 模型 {model_data['model_code']} 已存在")
        
        # 3. 获取默认模型ID
        default_model_response = supabase.table('llm_models').select('*').eq('provider_id', provider_id).eq('model_code', 'qwen-plus').execute()
        default_model_id = default_model_response.data[0]['id']
        
        # 4. 创建或更新默认配置（全局配置，带API密钥）
        print("📝 设置默认配置...")
        encrypted_api_key = encrypt_api_key(ALIBABA_API_KEY)
        
        config_data = {
            'user_id': None,  # 全局配置
            'config_name': 'default',
            'provider_id': provider_id,
            'model_id': default_model_id,
            'api_key_encrypted': encrypted_api_key,
            'custom_endpoint': None,
            'custom_parameters': {},
            'is_active': True
        }
        
        # 检查是否已存在默认配置
        existing_config = supabase.table('user_llm_configs').select('*').is_('user_id', 'null').eq('config_name', 'default').execute()
        
        if existing_config.data:
            # 更新现有配置
            supabase.table('user_llm_configs').update(config_data).eq('id', existing_config.data[0]['id']).execute()
            print("✅ 默认配置更新成功")
        else:
            # 创建新配置
            supabase.table('user_llm_configs').insert(config_data).execute()
            print("✅ 默认配置创建成功")
        
        # 5. 验证配置
        print("🔍 验证配置...")
        verification_response = supabase.table('user_llm_configs').select('''
            *,
            provider:llm_api_providers(*),
            model:llm_models(*)
        ''').is_('user_id', 'null').eq('config_name', 'default').execute()
        
        if verification_response.data:
            config = verification_response.data[0]
            print("✅ 配置验证成功:")
            print(f"   提供商: {config['provider']['provider_name']}")
            print(f"   模型: {config['model']['model_name']}")
            print(f"   API密钥: {'已设置' if config['api_key_encrypted'] else '未设置'}")
            print(f"   端点: {config['provider']['base_endpoint']}")
        else:
            print("❌ 配置验证失败")
            return False
        
        print("🎉 阿里云API密钥设置完成！")
        print("\n📋 使用说明:")
        print("1. 现在系统会自动使用阿里云通义千问作为默认LLM服务")
        print("2. 所有阿里云模型都会使用同一个API密钥")
        print("3. 在LLM配置页面中，阿里云的API密钥字段会自动填充")
        print("4. 您可以直接测试连接，无需手动输入API密钥")
        
        return True
        
    except Exception as e:
        print(f"❌ 设置失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """主函数"""
    print("=" * 60)
    print("🔧 阿里云API密钥固化工具")
    print("=" * 60)
    
    success = await setup_alibaba_config()
    
    if success:
        print("\n✅ 设置完成！现在您可以:")
        print("1. 打开前端LLM配置页面")
        print("2. 选择'阿里通义千问'提供商")
        print("3. 选择任意模型（推荐Qwen-Plus）")
        print("4. API密钥字段会自动填充")
        print("5. 点击'测试连接'验证")
        print("6. 点击'保存配置'完成设置")
    else:
        print("\n❌ 设置失败，请检查错误信息")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
