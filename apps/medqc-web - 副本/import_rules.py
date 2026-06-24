#!/usr/bin/env python3
"""
导入146条四川省质控规则到Supabase数据库
"""
import os
import sys
import json
import uuid
from supabase import create_client, Client
from dotenv import load_dotenv

# 加载环境变量
load_dotenv('.env')

# 获取Supabase配置
SUPABASE_URL = os.getenv('VITE_SUPABASE_URL')
SUPABASE_KEY = os.getenv('VITE_SUPABASE_ANON_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ 错误：缺少Supabase配置")
    print("请确保.env文件中包含：")
    print("  VITE_SUPABASE_URL")
    print("  VITE_SUPABASE_ANON_KEY")
    sys.exit(1)

# 创建Supabase客户端
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def main():
    # 读取转换后的规则
    rules_file = 'sichuan_rules_146.json'

    try:
        with open(rules_file, 'r', encoding='utf-8') as f:
            rules = json.load(f)
    except FileNotFoundError:
        print(f"❌ 错误：找不到文件 {rules_file}")
        sys.exit(1)

    print(f"📋 准备导入 {len(rules)} 条四川省质控规则\n")

    # 1. 先删除旧的四川规则
    print("🗑️  删除旧规则...")
    try:
        # 删除rule_code匹配模式的规则
        result = supabase.table('qc_rules').delete().like('rule_code', '%.%').execute()
        print(f"✅ 已清理旧规则\n")
    except Exception as e:
        print(f"⚠️  清理旧规则时出错（可忽略）: {e}\n")

    # 2. 批量插入新规则
    print("📥 开始批量导入...\n")

    batch_size = 50  # 每批50条
    success_count = 0
    error_count = 0

    for i in range(0, len(rules), batch_size):
        batch = rules[i:i+batch_size]
        batch_data = []

        for rule in batch:
            # 构建数据库记录
            record = {
                'id': str(uuid.uuid4()),
                'rule_code': rule['original_id'],
                'name': rule['name'],
                'description': rule['description'],
                'category': rule['category'],
                'rule_type': 'semantic',
                'severity': rule['defect_level'],
                'max_score': 0,
                'weight': 1.0,
                'is_active': True,
                'check_logic': {
                    'complexity': rule['complexity'],
                    'score_deduction': rule['score_deduction']
                },
                'prompt_template': f"检查{rule['category']}中是否存在以下问题：{rule['name']}。要求：{rule['description']}",
                'version': '1.0',
                'applicable_documents': rule['applicable_documents']
            }
            batch_data.append(record)

        try:
            result = supabase.table('qc_rules').insert(batch_data).execute()
            success_count += len(batch)
            print(f"✅ 批次 {i//batch_size + 1}: 成功导入 {len(batch)} 条规则 (总计: {success_count}/{len(rules)})")
        except Exception as e:
            error_count += len(batch)
            print(f"❌ 批次 {i//batch_size + 1}: 导入失败 - {e}")

    print(f"\n{'='*60}")
    print(f"📊 导入结果统计:")
    print(f"  成功: {success_count} 条")
    print(f"  失败: {error_count} 条")
    print(f"  总计: {len(rules)} 条")
    print(f"{'='*60}\n")

    # 3. 验证导入结果
    print("🔍 验证导入结果...")
    try:
        result = supabase.table('qc_rules').select('category', count='exact').execute()
        print(f"✅ 数据库中共有 {result.count} 条规则")

        # 按类别统计
        for category in ['入院记录', '病程记录', '手术相关记录', '(死亡)出院记录', '知情同意书', '医嘱', '辅助检查']:
            count_result = supabase.table('qc_rules').select('*', count='exact').eq('category', category).execute()
            print(f"  {category}: {count_result.count} 条")

    except Exception as e:
        print(f"⚠️  验证时出错: {e}")

    print("\n✅ 导入完成！")

if __name__ == '__main__':
    main()
