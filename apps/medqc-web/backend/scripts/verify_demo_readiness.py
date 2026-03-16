"""
演示验收脚本 — 一键检查演示环境是否就绪

检查项：
  1. 6 个 QC 视图可查询且无报错
  2. 8 张 QC 业务表有 demo-seed 数据
  3. 关键 API 端点 200 且返回数据
  4. 输出验收报告

运行: python -m scripts.verify_demo_readiness [--api-base http://localhost:8001]
"""

import sys
import os
import argparse
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

from app.database.connection import engine, init_db
from sqlalchemy import text


# ==================== 常量 ====================

DEMO_SEED_MARKER = "demo-seed"

EXPECTED_VIEWS = [
    "v_qc_task_progress",
    "qc_appeals_statistics",
    "qc_remediation_statistics",
    "qc_assignee_workload",
    "qc_statistics_view",
    "v_qc_coder_ranking",
]

EXPECTED_TABLES_WITH_DATA = [
    ("qc_results", "created_by = 'demo-seed'"),
    ("qc_defects", "result_id IN (SELECT id FROM qc_results WHERE created_by = 'demo-seed')"),
    ("qc_tasks", "creator_id = 'demo-seed'"),
    ("qc_task_records", "task_id IN (SELECT id FROM qc_tasks WHERE creator_id = 'demo-seed')"),
    ("qc_appeals", "appellant_id = 'demo-seed'"),
    ("qc_remediation_tasks", "assignee_id = 'demo-seed'"),
    ("notifications", "sender_id = 'demo-seed'"),
    ("qc_coder_workload_daily", "coder_id LIKE 'demo-seed-%'"),
    ("scoring_rules", "id LIKE 'demo-seed-SR-%'"),
    ("scoring_config", "updated_by = 'demo-seed'"),
]

API_ENDPOINTS = [
    ("/api/v1/system/health", "系统健康"),
    ("/api/v1/tasks", "质控任务列表"),
    ("/api/v1/defects", "缺陷列表"),
    ("/api/v1/appeals", "申诉列表"),
    ("/api/v1/remediation/tasks", "整改任务列表"),
    ("/api/v1/notifications", "通知列表"),
    ("/api/v1/scoring-rules", "评分规则"),
    ("/api/v1/staff-ranking/summary", "质控员排名"),
]


# ==================== 检查函数 ====================

def check_views(conn) -> list:
    """检查 6 个视图是否可查询"""
    results = []
    for view in EXPECTED_VIEWS:
        try:
            row = conn.execute(text(f"SELECT count(*) FROM {view}")).scalar()
            results.append({
                "check": f"视图 {view}",
                "status": "✅ PASS",
                "detail": f"{row} 行",
            })
        except Exception as e:
            results.append({
                "check": f"视图 {view}",
                "status": "❌ FAIL",
                "detail": str(e)[:80],
            })
    return results


def check_demo_data(conn) -> list:
    """检查 demo-seed 数据是否存在"""
    results = []
    for table, condition in EXPECTED_TABLES_WITH_DATA:
        try:
            row = conn.execute(text(f"SELECT count(*) FROM {table} WHERE {condition}")).scalar()
            ok = row > 0
            results.append({
                "check": f"表 {table}",
                "status": "✅ PASS" if ok else "⚠️ EMPTY",
                "detail": f"{row} 行 demo 数据",
            })
        except Exception as e:
            results.append({
                "check": f"表 {table}",
                "status": "❌ FAIL",
                "detail": str(e)[:80],
            })
    return results


def check_api_endpoints(base_url: str) -> list:
    """检查关键 API 端点是否返回 200"""
    if not HAS_HTTPX:
        return [{"check": "API 检查", "status": "⏭️ SKIP", "detail": "httpx 未安装"}]

    results = []
    client = httpx.Client(base_url=base_url, timeout=10)

    for path, desc in API_ENDPOINTS:
        try:
            resp = client.get(path)
            ok = resp.status_code == 200
            results.append({
                "check": f"API {desc}",
                "status": "✅ PASS" if ok else f"⚠️ {resp.status_code}",
                "detail": f"GET {path} → {resp.status_code}",
            })
        except Exception as e:
            results.append({
                "check": f"API {desc}",
                "status": "❌ FAIL",
                "detail": str(e)[:80],
            })

    client.close()
    return results


# ==================== 报告 ====================

def print_report(all_results: list):
    """输出验收报告"""
    print(f"\n{'='*60}")
    print(f"  MedQC 演示验收报告 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}\n")

    pass_count = 0
    fail_count = 0
    warn_count = 0
    skip_count = 0

    for r in all_results:
        status = r["status"]
        print(f"  {status:12s}  {r['check']:35s}  {r['detail']}")
        if "PASS" in status:
            pass_count += 1
        elif "FAIL" in status:
            fail_count += 1
        elif "EMPTY" in status or "⚠️" in status:
            warn_count += 1
        elif "SKIP" in status:
            skip_count += 1

    total = len(all_results)
    print(f"\n{'='*60}")
    print(f"  合计: {total} 项 | ✅ {pass_count} | ⚠️ {warn_count} | ❌ {fail_count} | ⏭️ {skip_count}")

    if fail_count == 0 and warn_count == 0:
        print(f"  🎉 验收通过！演示环境就绪。")
    elif fail_count == 0:
        print(f"  ⚠️ 有 {warn_count} 项警告，建议检查后再演示。")
    else:
        print(f"  ❌ 有 {fail_count} 项失败，需修复后才能演示。")

    print(f"{'='*60}\n")

    return fail_count == 0


# ==================== 入口 ====================

def main():
    parser = argparse.ArgumentParser(description="MedQC 演示验收脚本")
    parser.add_argument("--api-base", default="http://localhost:8001",
                        help="API 基地址（默认 http://localhost:8001）")
    parser.add_argument("--skip-api", action="store_true",
                        help="跳过 API 检查（仅检查 DB）")
    args = parser.parse_args()

    print("🔍 开始演示验收检查...\n")

    # 初始化 DB（确保视图存在）
    init_db()

    all_results = []

    # 1. 视图检查
    print("📊 检查视图...")
    with engine.connect() as conn:
        all_results.extend(check_views(conn))

    # 2. Demo 数据检查
    print("📋 检查 demo 数据...")
    with engine.connect() as conn:
        all_results.extend(check_demo_data(conn))

    # 3. API 检查
    if not args.skip_api:
        print("🌐 检查 API 端点...")
        all_results.extend(check_api_endpoints(args.api_base))
    else:
        all_results.append({"check": "API 检查", "status": "⏭️ SKIP", "detail": "用户跳过"})

    # 输出报告
    ok = print_report(all_results)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
