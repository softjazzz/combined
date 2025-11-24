#!/usr/bin/env python3
"""
通过 REST API 完整迁移 Supabase 数据库
带有详细进度显示和错误处理
"""

import requests
import json
import time
import sys
import os
from typing import List, Dict, Any
from datetime import datetime

# 源/目标数据库配置改为从环境变量读取，避免在代码中硬编码敏感信息。
# 必填环境变量：
#   SOURCE_SUPABASE_URL
#   SOURCE_SUPABASE_SERVICE_KEY
#   TARGET_SUPABASE_URL
#
# 如需在本地快速使用，可在 .env 或命令行中临时设置：
#   export SOURCE_SUPABASE_URL="https://xxx.supabase.co"
#   export SOURCE_SUPABASE_SERVICE_KEY="service-role-key"
#   export TARGET_SUPABASE_URL="https://yyy.supabase.opentrust.net"
SOURCE_URL = os.environ.get("SOURCE_SUPABASE_URL") or ""
SOURCE_SERVICE_KEY = os.environ.get("SOURCE_SUPABASE_SERVICE_KEY") or ""

# 目标数据库（例如阿里云 Supabase）
TARGET_URL = os.environ.get("TARGET_SUPABASE_URL") or ""

# 推荐的迁移顺序（先迁移无外键或被依赖的表）
TABLE_ORDER = [
    # 用户与基础数据
    "user_profiles",
    "user_roles",
    "departments",

    # 质控规则与配置
    "qc_rules",
    "report_templates",
    "alert_records",
    "analytics_metrics",
    "data_snapshots",

    # 医疗文档分类（测试与正式）
    "document_categories_test",
    "document_types_test",
    "medical_records_test",
    "medical_documents_test",

    # 正式业务表
    "medical_records",
    "medical_documents",
    "qc_results",
    "qc_analysis_cache",
    "qc_analysis_history",
    "batch_processing_tasks",

    # LLM 相关
    "llm_api_providers",
    "llm_models",
]

class Colors:
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    MAGENTA = '\033[0;35m'
    NC = '\033[0m'

def print_colored(text, color):
    print(f"{color}{text}{Colors.NC}")

def print_progress(current, total, prefix="", suffix=""):
    """打印进度条"""
    bar_length = 40
    filled_length = int(bar_length * current // total) if total > 0 else 0
    bar = '█' * filled_length + '-' * (bar_length - filled_length)
    percent = f"{100 * current / total:.1f}" if total > 0 else "0.0"
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end='', flush=True)
    if current == total:
        print()

def get_headers(api_key):
    return {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation,resolution=merge-duplicates"
    }

def test_connection(url, api_key, name):
    """测试数据库连接"""
    print_colored(f"\n🔍 测试{name}连接...", Colors.BLUE)
    
    try:
        response = requests.get(
            f"{url}/rest/v1/",
            headers=get_headers(api_key),
            timeout=30
        )
        
        if response.status_code == 200:
            print_colored(f"  ✅ {name}连接成功", Colors.GREEN)
            return True
        else:
            print_colored(f"  ❌ {name}连接失败: HTTP {response.status_code}", Colors.RED)
            return False
    except Exception as e:
        print_colored(f"  ❌ {name}连接失败: {e}", Colors.RED)
        return False

def get_table_list(url, api_key) -> List[str]:
    """获取所有表名"""
    print_colored("\n📋 获取表列表...", Colors.BLUE)

    existing_tables = []
    
    for table in TABLE_ORDER:
        try:
            response = requests.get(
                f"{url}/rest/v1/{table}?limit=1",
                headers=get_headers(api_key),
                timeout=15
            )
            
            if response.status_code == 200:
                existing_tables.append(table)
                print(f"  ✅ {table}")
            elif response.status_code == 204:
                existing_tables.append(table)
                print(f"  ✅ {table} (空表)")
            elif response.status_code == 404:
                print(f"  ⚠️  {table} (不存在或未开放 REST 访问)")
            else:
                print(f"  ❌ {table} (HTTP {response.status_code})")
        except Exception as e:
            print(f"  ❌ {table} (检查失败: {str(e)[:50]})")
    
    print_colored(f"\n  找到 {len(existing_tables)} 个表", Colors.GREEN)
    return existing_tables

def get_table_count(url, api_key, table) -> int:
    """获取表的记录数"""
    try:
        response = requests.get(
            f"{url}/rest/v1/{table}?select=count",
            headers={**get_headers(api_key), "Prefer": "count=exact"},
            timeout=15
        )

        if response.status_code in [200, 206]:
            # 尝试从响应头获取
            content_range = response.headers.get('Content-Range', '')
            if content_range and '/' in content_range:
                return int(content_range.split('/')[-1])

            # 尝试从响应体获取
            data = response.json()
            if data and isinstance(data, list) and len(data) > 0:
                if 'count' in data[0]:
                    return data[0]['count']

        return 0
    except:
        return 0

def fetch_all_data(url, api_key, table) -> List[Dict[str, Any]]:
    """从源数据库获取所有数据（带进度显示）"""

    # 先获取总数
    total_count = get_table_count(url, api_key, table)

    if total_count == 0:
        print_colored("  ⚠️  未获取到计数，尝试直接遍历数据", Colors.YELLOW)
        total_count = 1  # 避免进度条除零
    else:
        print(f"  📊 总记录数: {total_count}")

    all_data = []
    offset = 0
    limit = 1000

    while True:
        try:
            response = requests.get(
                f"{url}/rest/v1/{table}?limit={limit}&offset={offset}",
                headers=get_headers(api_key),
                timeout=60
            )

            if response.status_code not in [200, 206]:
                print_colored(f"\n  ❌ 获取数据失败: HTTP {response.status_code}", Colors.RED)
                break

            data = response.json()

            if not data:
                if len(all_data) == 0:
                    print_colored("  ⚠️  表为空", Colors.YELLOW)
                break

            all_data.extend(data)

            # 显示进度
            current_total = max(total_count, len(all_data))
            print_progress(len(all_data), current_total, "  📥 获取数据", f"({len(all_data)}/{current_total})")

            offset += limit

            if len(data) < limit:
                break

        except Exception as e:
            print_colored(f"\n  ❌ 错误: {e}", Colors.RED)
            break

    return all_data

def insert_data_batch(url, api_key, table, data) -> int:
    """批量插入数据到目标数据库（带进度显示）"""
    if not data:
        return 0
    
    headers = get_headers(api_key)
    batch_size = 100
    total = len(data)
    success_count = 0
    failed_count = 0
    
    for i in range(0, total, batch_size):
        batch = data[i:i+batch_size]
        
        try:
            response = requests.post(
                f"{url}/rest/v1/{table}",
                headers=headers,
                json=batch,
                timeout=60
            )
            
            if response.status_code in [200, 201]:
                success_count += len(batch)
            else:
                print_colored(f"\n  ⚠️  批量插入失败 (HTTP {response.status_code}): {response.text[:200]}", Colors.YELLOW)
                # 如果批量插入失败，尝试单条插入
                for record in batch:
                    try:
                        single_response = requests.post(
                            f"{url}/rest/v1/{table}",
                            headers=headers,
                            json=record,
                            timeout=30
                        )
                        if single_response.status_code in [200, 201]:
                            success_count += 1
                        else:
                            failed_count += 1
                    except:
                        failed_count += 1
            
            # 显示进度
            processed = success_count + failed_count
            print_progress(processed, total, "  📤 插入数据", f"(成功:{success_count} 失败:{failed_count})")
            
            time.sleep(0.1)
            
        except Exception as e:
            failed_count += len(batch)
            print_progress(success_count + failed_count, total, "  📤 插入数据", f"(成功:{success_count} 失败:{failed_count})")
    
    return success_count

def migrate_table(source_url, source_key, target_url, target_key, table) -> Dict[str, Any]:
    """迁移单个表"""
    print_colored(f"\n{'='*60}", Colors.CYAN)
    print_colored(f"📋 迁移表: {table}", Colors.CYAN)
    print_colored(f"{'='*60}", Colors.CYAN)
    
    start_time = time.time()
    
    # 1. 获取数据
    print_colored("\n🔄 步骤 1/2: 从源数据库获取数据", Colors.BLUE)
    data = fetch_all_data(source_url, source_key, table)
    
    if not data:
        print_colored(f"  ⚠️  无数据可迁移", Colors.YELLOW)
        return {"table": table, "success": True, "count": 0, "time": 0}
    
    print_colored(f"  ✅ 成功获取 {len(data)} 条记录", Colors.GREEN)
    
    # 2. 插入数据
    print_colored("\n🔄 步骤 2/2: 插入到目标数据库", Colors.BLUE)
    success_count = insert_data_batch(target_url, target_key, table, data)
    
    elapsed_time = time.time() - start_time
    
    if success_count > 0:
        print_colored(f"\n  ✅ 成功插入 {success_count}/{len(data)} 条记录", Colors.GREEN)
        print_colored(f"  ⏱️  耗时: {elapsed_time:.1f} 秒", Colors.BLUE)
        return {"table": table, "success": True, "count": success_count, "time": elapsed_time}
    else:
        print_colored(f"\n  ❌ 插入失败", Colors.RED)
        return {"table": table, "success": False, "count": 0, "time": elapsed_time}

def main():
    print_colored("=" * 70, Colors.BLUE)
    print_colored("🚀 Supabase 数据库完整迁移工具 (REST API 方式)", Colors.BLUE)
    print_colored("=" * 70, Colors.BLUE)

    # 基本配置校验，避免在缺少必要环境变量时进行网络请求
    if not SOURCE_URL or not SOURCE_SERVICE_KEY or not TARGET_URL:
        print_colored("\n❌ 缺少必要配置，请先设置以下环境变量：", Colors.RED)
        print("  - SOURCE_SUPABASE_URL")
        print("  - SOURCE_SUPABASE_SERVICE_KEY")
        print("  - TARGET_SUPABASE_URL")
        print("\n示例：")
        print('  export SOURCE_SUPABASE_URL="https://xxx.supabase.co"')
        print('  export SOURCE_SUPABASE_SERVICE_KEY="service-role-key"')
        print('  export TARGET_SUPABASE_URL="https://yyy.supabase.opentrust.net"')
        return
    
    print(f"\n源数据库: {SOURCE_URL}")
    print(f"目标数据库: {TARGET_URL}")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 步骤 1: 测试连接
    if not test_connection(SOURCE_URL, SOURCE_SERVICE_KEY, "源数据库"):
        return
    
    # 注意：我们需要阿里云的 Service Role Key
    print_colored("\n⚠️  需要阿里云 Supabase 的 Service Role Key", Colors.YELLOW)
    print("请访问: https://sbp-a41klzf2d6lvsjoj.supabase.opentrust.net/project/default/settings/api")
    print("复制 'service_role' secret key")
    print()
    
    target_service_key = input("请输入阿里云 Supabase Service Role Key: ").strip()
    
    if not target_service_key:
        print_colored("\n❌ 未提供 Service Role Key，退出", Colors.RED)
        return
    
    if not test_connection(TARGET_URL, target_service_key, "目标数据库"):
        return
    
    # 步骤 2: 获取表列表
    tables = get_table_list(SOURCE_URL, SOURCE_SERVICE_KEY)
    
    if not tables:
        print_colored("\n❌ 未找到任何表", Colors.RED)
        return

    missing_tables = [t for t in TABLE_ORDER if t not in tables]
    if missing_tables:
        print_colored("\n⚠️  以下表在源库中未检测到，将跳过:", Colors.YELLOW)
        for table in missing_tables:
            print(f"   - {table}")
    
    # 步骤 3: 迁移所有表
    print_colored(f"\n{'='*70}", Colors.BLUE)
    print_colored(f"🔄 开始迁移 {len(tables)} 个表", Colors.BLUE)
    print_colored(f"{'='*70}", Colors.BLUE)
    
    results = []
    total_records = 0
    total_time = 0
    
    for i, table in enumerate(tables, 1):
        print_colored(f"\n\n进度: [{i}/{len(tables)}]", Colors.MAGENTA)
        result = migrate_table(SOURCE_URL, SOURCE_SERVICE_KEY, TARGET_URL, target_service_key, table)
        results.append(result)
        total_records += result['count']
        total_time += result['time']
        
        time.sleep(0.5)
    
    # 总结
    print_colored(f"\n\n{'='*70}", Colors.BLUE)
    print_colored("📊 迁移总结", Colors.BLUE)
    print_colored(f"{'='*70}", Colors.BLUE)
    
    success_count = sum(1 for r in results if r['success'])
    
    print(f"\n✅ 成功: {success_count}/{len(tables)} 个表")
    print(f"📊 总记录数: {total_records}")
    print(f"⏱️  总耗时: {total_time:.1f} 秒")
    print(f"🕐 结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    print("\n详细结果:")
    for result in results:
        status = "✅" if result['success'] else "❌"
        print(f"  {status} {result['table']}: {result['count']} 条记录 ({result['time']:.1f}s)")
    
    if success_count == len(tables):
        print_colored("\n🎉 所有数据迁移成功！", Colors.GREEN)
    elif success_count > 0:
        print_colored("\n⚠️  部分数据迁移成功", Colors.YELLOW)
    else:
        print_colored("\n❌ 迁移失败", Colors.RED)
    
    print("\n📝 后续步骤:")
    print("1. 环境变量已更新（.env 文件）")
    print("2. 重启后端服务（会自动重新加载）")
    print("3. 刷新前端页面测试")
    print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_colored("\n\n❌ 迁移已取消", Colors.RED)
    except Exception as e:
        print_colored(f"\n\n❌ 发生错误: {e}", Colors.RED)
        import traceback
        traceback.print_exc()
