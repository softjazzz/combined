#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.core.supabase_client import get_supabase

supabase = get_supabase()
result = supabase.table('user_llm_configs').select('id, config_name, custom_parameters, updated_at').eq('config_name', 'default').eq('is_active', True).order('updated_at', desc=True).limit(1).execute()

if result.data:
    config = result.data[0]
    print('✅ 找到最新的配置记录：')
    print(f'  配置 ID: {config["id"]}')
    print(f'  更新时间: {config["updated_at"]}')
    custom_params = config.get('custom_parameters', {})
    print(f'  高级参数:')
    print(f'    - temperature: {custom_params.get("temperature", "N/A")}')
    print(f'    - top_p: {custom_params.get("top_p", "N/A")}')
    print(f'    - max_tokens: {custom_params.get("max_tokens", "N/A")}')
    if custom_params.get('temperature') == 0.5:
        print('\n🎉 确认：temperature 已成功保存为 0.5！')
    else:
        print(f'\n⚠️ temperature 的值是 {custom_params.get("temperature")}')
else:
    print('❌ 未找到配置记录')

