"""
演示验收脚本 — 一键检查演示环境是否就绪

检查项：
  1. 6 个 QC 视图可查询且无报错
  2. 10 张 QC 业务表有 demo-seed 数据
  3. 关键 API 端点 200 且返回数据
  4. 输出验收报告

运行: python -m scripts.verify_demo_readiness [--api-base http://localhost:8001]
"""

import sys
import os
import argparse
import time
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
    ("qc_results", f"created_by = '{DEMO_SEED_MARKER}'"),
    ("qc_defects", f"result_id IN (SELECT id FROM qc_results WHERE created_by = '{DEMO_SEED_MARKER}')"),
    ("qc_tasks", f"creator_id = '{DEMO_SEED_MARKER}'"),
    ("qc_task_records", f"task_id IN (SELECT id FROM qc_tasks WHERE creator_id = '{DEMO_SEED_MARKER}')"),
    ("qc_appeals", f"appellant_id = '{DEMO_SEED_MARKER}'"),
    ("qc_remediation_tasks", f"assignee_id = '{DEMO_SEED_MARKER}'"),
    ("notifications", f"sender_id = '{DEMO_SEED_MARKER}'"),
    ("qc_coder_workload_daily", "coder_id LIKE 'demo-seed-%'"),
    ("scoring_rules", "id LIKE 'demo-seed-SR-%'"),
    ("scoring_config", f"updated_by = '{DEMO_SEED_MARKER}'"),
]

API_ENDPOINTS = [
    ("/api/v1/health", "系统健康"),
    ("/api/v1/tasks", "质控任务列表"),
    ("/api/v1/qc/defects", "缺陷列表"),
    ("/api/v1/appeals", "申诉列表"),
    ("/api/v1/remediation", "整改任务列表"),
    ("/api/v1/notifications", "通知列表"),
    ("/api/v1/scoring-rules", "评分规则"),
    ("/api/v1/staff-ranking", "质控员排名"),
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
                "status": "PASS",
                "detail": f"{row} 行",
            })
        except Exception as e:
            results.append({
                "check": f"视图 {view}",
                "status": "FAIL",
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
                "status": "PASS" if ok else "EMPTY",
                "detail": f"{row} 行 demo 数据",
            })
        except Exception as e:
            results.append({
                "check": f"表 {table}",
                "status": "FAIL",
                "detail": str(e)[:80],
            })
    return results


def check_api_endpoints(
    base_url: str,
    api_token: str = "",
    api_email: str = "",
    api_password: str = "",
) -> list:
    """检查关键 API 端点是否返回 200"""
    if not HAS_HTTPX:
        return [{"check": "API 检查", "status": "SKIP", "detail": "httpx 未安装"}]

    results = []
    client = httpx.Client(base_url=base_url, timeout=10, trust_env=False)
    headers = {}

    # Optional auth bootstrap: use provided token first, then email/password login.
    token = (api_token or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
        results.append({"check": "API 鉴权", "status": "PASS", "detail": "使用 --api-token"})
    elif api_email and api_password:
        login_ok = False
        for attempt in range(1, 4):
            try:
                login_resp = client.post(
                    "/api/v1/auth/login",
                    json={"email": api_email, "password": api_password},
                )
                if login_resp.status_code == 200:
                    payload = login_resp.json()
                    token = payload.get("access_token") or payload.get("data", {}).get("access_token")
                    if token:
                        headers["Authorization"] = f"Bearer {token}"
                        results.append({
                            "check": "API 鉴权",
                            "status": "PASS",
                            "detail": f"登录成功并获取 token（attempt={attempt}）",
                        })
                    else:
                        results.append({
                            "check": "API 鉴权",
                            "status": "WARN",
                            "detail": "登录成功但未返回 access_token",
                        })
                    login_ok = True
                    break
                if attempt == 3:
                    results.append({
                        "check": "API 鉴权",
                        "status": f"WARN {login_resp.status_code}",
                        "detail": "登录失败，继续无鉴权检查",
                    })
            except Exception as e:
                if attempt == 3:
                    results.append({
                        "check": "API 鉴权",
                        "status": "WARN",
                        "detail": f"登录异常: {str(e)[:80]}",
                    })
            if not login_ok:
                time.sleep(1.0)
    else:
        results.append({"check": "API 鉴权", "status": "SKIP", "detail": "未提供 token 或登录账号，按匿名检查"})

    for path, desc in API_ENDPOINTS:
        try:
            resp = client.get(path, headers=headers or None)
            ok = resp.status_code == 200
            detail = f"GET {path} -> {resp.status_code}"
            if resp.status_code in (401, 403):
                detail += " (鉴权限制)"
            results.append({
                "check": f"API {desc}",
                "status": "PASS" if ok else f"WARN {resp.status_code}",
                "detail": detail,
            })
        except Exception as e:
            results.append({
                "check": f"API {desc}",
                "status": "FAIL",
                "detail": str(e)[:80],
            })

    client.close()
    return results


# ==================== 报告 ====================

def print_report(all_results: list, allow_empty: bool = False):
    """输出验收报告"""
    print(f"\n{'='*60}")
    print(f"  MedQC 演示验收报告 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}\n")

    pass_count = 0
    fail_count = 0
    warn_count = 0
    skip_count = 0
    empty_count = 0

    for r in all_results:
        status = r["status"]
        print(f"  {status:12s}  {r['check']:35s}  {r['detail']}")
        if status.startswith("PASS"):
            pass_count += 1
        elif status.startswith("FAIL"):
            fail_count += 1
        elif status.startswith("EMPTY"):
            warn_count += 1
            empty_count += 1
        elif status.startswith("WARN"):
            warn_count += 1
        elif status.startswith("SKIP"):
            skip_count += 1

    total = len(all_results)
    print(f"\n{'='*60}")
    print(f"  合计: {total} 项 | PASS {pass_count} | WARN {warn_count} | FAIL {fail_count} | SKIP {skip_count}")

    if fail_count == 0 and warn_count == 0:
        print("  验收通过：演示环境就绪。")
    elif fail_count == 0 and empty_count > 0 and not allow_empty:
        print(f"  验收未通过：有 {empty_count} 项 EMPTY。演示数据未写入（可用 --allow-empty 放宽）。")
    elif fail_count == 0:
        print(f"  验收告警：有 {warn_count} 项警告，建议检查后再演示。")
    else:
        print(f"  验收失败：有 {fail_count} 项失败，需修复后才能演示。")

    print(f"{'='*60}\n")

    if fail_count > 0:
        return False
    if empty_count > 0 and not allow_empty:
        return False
    return True


# ==================== 入口 ====================

def main():
    parser = argparse.ArgumentParser(description="MedQC 演示验收脚本")
    parser.add_argument("--api-base", default="http://localhost:8001",
                        help="API 基地址（默认 http://localhost:8001）")
    parser.add_argument("--api-token", default=os.getenv("DEMO_API_TOKEN", ""),
                        help="可选：API Bearer token（优先于账号密码）")
    parser.add_argument("--api-email", default=os.getenv("DEMO_API_EMAIL", ""),
                        help="可选：登录邮箱（用于自动获取 token）")
    parser.add_argument("--api-password", default=os.getenv("DEMO_API_PASSWORD", ""),
                        help="可选：登录密码（用于自动获取 token）")
    parser.add_argument("--skip-api", action="store_true",
                        help="跳过 API 检查（仅检查 DB）")
    parser.add_argument("--allow-empty", action="store_true",
                        help="允许业务表 EMPTY（仅做结构联通检查）")
    args = parser.parse_args()

    print("开始演示验收检查...\n")

    # 初始化 DB（确保视图存在）
    init_db()

    all_results = []

    # 1. 视图检查
    print("检查视图...")
    with engine.connect() as conn:
        all_results.extend(check_views(conn))

    # 2. Demo 数据检查
    print("检查 demo 数据...")
    with engine.connect() as conn:
        all_results.extend(check_demo_data(conn))

    # 3. API 检查
    if not args.skip_api:
        print("检查 API 端点...")
        all_results.extend(
            check_api_endpoints(
                args.api_base,
                api_token=args.api_token,
                api_email=args.api_email,
                api_password=args.api_password,
            )
        )
    else:
        all_results.append({"check": "API 检查", "status": "SKIP", "detail": "用户跳过"})

    # 输出报告
    ok = print_report(all_results, allow_empty=args.allow_empty)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
