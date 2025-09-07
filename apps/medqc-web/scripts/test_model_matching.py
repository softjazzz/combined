#!/usr/bin/env python3
"""
测试模型匹配问题
验证前端选择的模型代码是否能在数据库中找到对应的记录
"""

import os
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# 加载环境变量
load_dotenv(project_root / '.env')
load_dotenv(project_root / 'backend' / '.env')

# Supabase配置
SUPABASE_URL = os.getenv('SUPABASE_URL') or os.getenv('VITE_SUPABASE_URL')
SUPABASE_ANON_KEY = os.getenv('SUPABASE_ANON_KEY') or os.getenv('VITE_SUPABASE_ANON_KEY')

# 前端配置文件中的阿里云模型列表
FRONTEND_MODELS = [
    'qwen-turbo',
    'qwen-plus', 
    'qwen-max',
    'qwen3-235b-a22b-instruct-2507',
    'qwen-doc-turbo',
    'qwen2.5-7b-1m',
    'qwen-flash-2025-07-28',
    'qwen3-4b',
    'qwen3-8b',
    'qwen3-14b',
    'qwen3-30b-a3b-instruct-2507',
    'qwen2.5-32b-instruct',
    'qwen2.5-14b-instruct'
]

async def test_model_matching():
    """测试模型匹配"""
    print("🧪 测试模型匹配...")
    
    # 初始化Supabase客户端
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    
    try:
        # 获取阿里云提供商ID
        provider_response = supabase.table('llm_api_providers').select('*').eq('provider_code', 'alibaba').execute()
        if not provider_response.data:
            print("❌ 未找到阿里云提供商")
            return False
        
        provider_id = provider_response.data[0]['id']
        print(f"✅ 找到阿里云提供商: {provider_id}")
        
        # 获取数据库中的所有阿里云模型
        models_response = supabase.table('llm_models').select('*').eq('provider_id', provider_id).execute()
        db_models = {model['model_code']: model for model in models_response.data}
        
        print(f"📊 数据库中的阿里云模型数量: {len(db_models)}")
        print("数据库中的模型代码:")
        for model_code in sorted(db_models.keys()):
            print(f"  - {model_code}")
        
        print(f"\n📊 前端配置中的模型数量: {len(FRONTEND_MODELS)}")
        print("前端配置中的模型代码:")
        for model_code in FRONTEND_MODELS:
            print(f"  - {model_code}")
        
        # 检查匹配情况
        print("\n🔍 匹配检查:")
        all_matched = True
        
        for frontend_model in FRONTEND_MODELS:
            if frontend_model in db_models:
                db_model = db_models[frontend_model]
                status = "✅ 匹配" if db_model['is_active'] else "⚠️ 匹配但未激活"
                print(f"  {frontend_model}: {status}")
            else:
                print(f"  {frontend_model}: ❌ 未找到")
                all_matched = False
        
        # 检查数据库中有但前端配置中没有的模型
        missing_in_frontend = set(db_models.keys()) - set(FRONTEND_MODELS)
        if missing_in_frontend:
            print(f"\n📋 数据库中有但前端配置中缺少的模型 ({len(missing_in_frontend)}个):")
            for model_code in sorted(missing_in_frontend):
                print(f"  - {model_code}")
        
        return all_matched
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

async def test_save_config_simulation():
    """模拟保存配置的过程"""
    print("\n🔧 模拟保存配置过程...")
    
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    
    try:
        # 获取阿里云提供商
        providers = supabase.table('llm_api_providers').select('*').eq('provider_code', 'alibaba').execute()
        provider = providers.data[0] if providers.data else None
        
        if not provider:
            print("❌ 未找到阿里云提供商")
            return False
        
        # 获取该提供商下的模型
        models = supabase.table('llm_models').select('*').eq('provider_id', provider['id']).execute()
        models_dict = {model['model_code']: model for model in models.data}
        
        # 测试几个关键模型的保存
        test_models = ['qwen-plus', 'qwen-turbo', 'qwen-max', 'qwen2.5-14b-instruct']
        
        for model_code in test_models:
            print(f"\n测试模型: {model_code}")
            
            # 模拟前端的查找逻辑
            model = models_dict.get(model_code)
            if model:
                print(f"  ✅ 找到模型: {model['model_name']}")
                print(f"  📋 模型ID: {model['id']}")
                print(f"  🔄 激活状态: {model['is_active']}")
                
                # 这里可以模拟保存配置的过程
                # 但为了安全起见，我们只是验证查找逻辑
                print(f"  ✅ 模拟保存成功")
            else:
                print(f"  ❌ 未找到模型 - 这会导致保存失败")
        
        return True
        
    except Exception as e:
        print(f"❌ 模拟测试失败: {e}")
        return False

async def main():
    """主函数"""
    print("=" * 60)
    print("🔧 模型匹配问题诊断工具")
    print("=" * 60)
    
    # 测试模型匹配
    match_success = await test_model_matching()
    
    # 模拟保存配置
    save_success = await test_save_config_simulation()
    
    print("\n" + "=" * 60)
    print("📊 测试结果总结:")
    print(f"  模型匹配测试: {'✅ 通过' if match_success else '❌ 失败'}")
    print(f"  保存配置模拟: {'✅ 通过' if save_success else '❌ 失败'}")
    
    if match_success and save_success:
        print("\n🎉 所有测试通过！模型匹配问题应该已经解决。")
        print("\n📋 建议:")
        print("1. 重新加载前端页面")
        print("2. 选择不同的阿里云模型进行测试")
        print("3. 尝试保存配置，应该不会再出现'未找到所选模型'错误")
    else:
        print("\n⚠️ 仍有问题需要解决，请检查上述输出信息")

if __name__ == "__main__":
    asyncio.run(main())
