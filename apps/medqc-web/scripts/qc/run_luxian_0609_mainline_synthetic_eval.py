from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
DOCS_DIR = ROOT / "docs" / "0602"
RUNTIME_DIR = ROOT / ".runtime-logs" / "qc-pack-poc"
SYNTHETIC_CASES_PATH = DOCS_DIR / "luxian_0609_synthetic_cases_v1.json"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.luxian_0609.rule_contracts import (  # noqa: E402
    load_luxian_0609_rule_contracts,
)


V1_VISIT_PREFIX = "LX0609_SYN_"
V2_VISIT_PREFIX = "LX0609_0426_SYN_V2_"
V3_VISIT_PREFIX = "LX0609_0426_SYN_V3_"
SYNTHETIC_INSTITUTE_BY_VISIT_PREFIX = {
    V1_VISIT_PREFIX: "LX0609_SYN",
    V2_VISIT_PREFIX: "LX0609_0426_SYN",
    V3_VISIT_PREFIX: "LX0609_0426_SYN_V3",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_env_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"env file not found: {path}")
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
            continue
        os.environ.setdefault(key, value)


def _provider_code() -> str:
    provider = safe_text(os.environ.get("LLM_DEFAULT_PROVIDER") or "alibaba").lower()
    return provider or "alibaba"


def _llm_key_candidates(provider: str) -> list[str]:
    key_candidates = ["LLM_API_KEY", "SICHUAN_API_KEY"]
    if provider == "alibaba":
        key_candidates.insert(0, "DASHSCOPE_API_KEY")
    elif provider == "deepseek":
        key_candidates.insert(0, "DEEPSEEK_API_KEY")
    elif provider == "siliconflow":
        key_candidates.insert(0, "SILICONFLOW_API_KEY")
    elif provider == "ollama":
        return []
    return key_candidates


def runtime_env_diagnostics() -> dict[str, Any]:
    provider = _provider_code()
    key_candidates = _llm_key_candidates(provider)
    mock_allowed = safe_text(os.environ.get("LLM_ALLOW_MOCK_WHEN_UNCONFIGURED")).lower() in {"1", "true", "yes"}
    return {
        "database_url_set": bool(safe_text(os.environ.get("DATABASE_URL"))),
        "jwt_secret_set": bool(safe_text(os.environ.get("JWT_SECRET"))),
        "provider": provider,
        "llm_model": safe_text(os.environ.get("LLM_MODEL") or os.environ.get("SICHUAN_MODEL") or "qwen3.5-35b-a3b"),
        "llm_key_candidates": key_candidates,
        "llm_key_set": bool(any(safe_text(os.environ.get(name)) for name in key_candidates)) if key_candidates else True,
        "mock_allowed": mock_allowed,
    }


def validate_runtime_env() -> None:
    os.environ.setdefault("JWT_SECRET", "test-secret")
    diagnostics = runtime_env_diagnostics()
    if diagnostics["llm_key_set"]:
        return
    if safe_text(os.environ.get("LLM_ALLOW_MOCK_WHEN_UNCONFIGURED")).lower() in {"1", "true", "yes"}:
        return
    raise RuntimeError(
        "LLM API key 未配置；请通过环境变量或 --env-file 注入 "
        f"{'/'.join(diagnostics['llm_key_candidates'])} 后重跑。"
    )


def safe_text(value: Any) -> str:
    return str(value or "").strip()


def strip_sensitive(value: Any) -> Any:
    sensitive_keys = {
        "raw_response",
        "raw_output",
        "llm_raw_output",
        "prompt",
        "embedding",
        "medical_text",
        "documents",
        "bundle",
        "record_content",
        "internal_data",
    }
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if str(key).lower() in sensitive_keys:
                continue
            result[key] = strip_sensitive(item)
        return result
    if isinstance(value, list):
        return [strip_sensitive(item) for item in value]
    return value


def iter_visit_ids(data: dict[str, Any]) -> list[str]:
    visits = []
    for item in data.get("visits") or []:
        if not isinstance(item, dict):
            continue
        visit_id = safe_text(item.get("visit_id"))
        if visit_id.startswith("LX0609_SYN_"):
            visits.append(visit_id)
    return sorted(set(visits))


def select_visit_ids(all_visit_ids: list[str], args: argparse.Namespace) -> list[str]:
    selected = list(all_visit_ids)
    if args.visit_id:
        requested = {safe_text(item) for item in args.visit_id if safe_text(item)}
        selected = [item for item in selected if item in requested]
    if args.limit:
        selected = selected[: max(0, int(args.limit))]
    return selected


def defined_rule_ids() -> frozenset[str]:
    return frozenset(
        contract.rule_id
        for contract in load_luxian_0609_rule_contracts()
        if contract.phase_status != "pending_definition"
    )


def resolve_synthetic_institute_id(visit_id: str, configured: str = "") -> str:
    explicit = safe_text(configured)
    if explicit:
        return explicit
    for prefix, institute_id in SYNTHETIC_INSTITUTE_BY_VISIT_PREFIX.items():
        if visit_id.startswith(prefix):
            return institute_id
    raise ValueError(
        f"无法从 synthetic visit_id 识别院区：{visit_id}；请显式传入 --institute-id"
    )


def load_validation_matrix(
    path: Path, *, defined_only: bool = False
) -> dict[str, dict[str, str]]:
    """读取 v3 黄金验收矩阵；同一规则可绑定多个受控状态病例。"""
    grouped: dict[str, dict[str, str]] = {}
    allowed_rule_ids = defined_rule_ids() if defined_only else None
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            visit_id = safe_text(row.get("visit_id"))
            rule_id = safe_text(row.get("rule_id"))
            expected_status = safe_text(row.get("expected_status"))
            if not visit_id or not rule_id or not expected_status:
                raise ValueError("validation matrix contains an incomplete row")
            if allowed_rule_ids is not None and rule_id not in allowed_rule_ids:
                continue
            visit_rules = grouped.setdefault(visit_id, {})
            if rule_id in visit_rules:
                raise ValueError(f"validation matrix duplicates {rule_id}")
            visit_rules[rule_id] = expected_status
    return grouped


def summarize_validation_matrix(
    validation_matrix: dict[str, dict[str, str]],
) -> dict[str, int]:
    unique_rule_ids = {
        rule_id
        for visit_rules in validation_matrix.values()
        for rule_id in visit_rules
    }
    return {
        "visit_count": len(validation_matrix),
        "unique_rule_count": len(unique_rule_ids),
        "assertion_count": sum(len(visit_rules) for visit_rules in validation_matrix.values()),
    }


def inspect_pg_synthetic_cases() -> dict[str, Any]:
    database_url = safe_text(os.environ.get("DATABASE_URL"))
    if not database_url:
        return {"ok": False, "error": "DATABASE_URL 未配置"}
    try:
        from sqlalchemy import create_engine, text
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"SQLAlchemy 不可用: {type(exc).__name__}: {exc}"}
    engine = create_engine(database_url)
    try:
        with engine.connect() as conn:
            item_columns = {
                str(row[0])
                for row in conn.execute(
                    text(
                        "select column_name from information_schema.columns "
                        "where table_schema='qc' and table_name='manual_problem_sample_pool_items'"
                    )
                ).fetchall()
            }
            pool_column = "pool_id" if "pool_id" in item_columns else "sample_pool_id"
            pool = conn.execute(
                text(
                    "select id, name, total_items, ready_items "
                    "from qc.manual_problem_sample_pools "
                    "where id = 'luxian-0609-synthetic-v1'"
                )
            ).mappings().first()
            item_count = conn.execute(
                text(
                    "select count(*) from qc.manual_problem_sample_pool_items "
                    f"where {pool_column} = 'luxian-0609-synthetic-v1'"
                )
            ).scalar_one()
            mr_count = conn.execute(
                text("select count(*) from mr where visit_id like 'LX0609_SYN_%'")
            ).scalar_one()
            admission_count = conn.execute(
                text("select count(*) from admission_record where visit_id like 'LX0609_SYN_%'")
            ).scalar_one()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    finally:
        engine.dispose()
    return {
        "ok": bool(pool and int(item_count or 0) == 30 and int(mr_count or 0) == 30),
        "pool": dict(pool) if pool else None,
        "item_count": int(item_count or 0),
        "mr_count": int(mr_count or 0),
        "admission_record_count": int(admission_count or 0),
    }


def build_preflight(args: argparse.Namespace) -> dict[str, Any]:
    data = load_json(Path(args.synthetic_cases))
    visit_ids = iter_visit_ids(data)
    golden_count = sum(
        len(item.get("golden_answers") or [])
        for item in data.get("visits") or []
        if isinstance(item, dict)
    )
    env = runtime_env_diagnostics()
    pg = inspect_pg_synthetic_cases() if env["database_url_set"] else {"ok": False, "error": "DATABASE_URL 未配置"}
    checks = {
        "synthetic_json_30_visits": len(visit_ids) == 30,
        "synthetic_json_105_golden": golden_count == 105,
        "pg_synthetic_pool_ready": bool(pg.get("ok")),
        "llm_key_or_mock_ready": bool(env.get("llm_key_set") or env.get("mock_allowed")),
    }
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "synthetic_cases": {
            "path": str(Path(args.synthetic_cases)),
            "visit_count": len(visit_ids),
            "golden_count": golden_count,
            "first_visit_id": visit_ids[0] if visit_ids else "",
            "last_visit_id": visit_ids[-1] if visit_ids else "",
        },
        "environment": env,
        "pg": pg,
        "checks": checks,
        "ok": all(checks.values()),
    }


def build_report(
    *,
    visit_id: str,
    elapsed_ms: int,
    result: dict[str, Any],
    error: str = "",
) -> dict[str, Any]:
    rows = list(result.get("parsed_evaluation_results") or []) if isinstance(result, dict) else []
    summary = result.get("evaluation_summary") if isinstance(result, dict) else {}
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source": "mainline",
        "dry_run": False,
        "visit_id": visit_id,
        "rule_set_key": "luxian_0609_qc_v1",
        "elapsed_ms": elapsed_ms,
        "error": error,
        "execution": {
            "trigger_gate_customer_results": strip_sensitive(rows),
            "baseline_customer_results": [],
            "mainline_summary": strip_sensitive(summary or {}),
            "bundle_metadata": strip_sensitive(result.get("bundle_metadata") or {}) if isinstance(result, dict) else {},
            "luxian_0609_summary": strip_sensitive(result.get("luxian_0609_summary") or {}) if isinstance(result, dict) else {},
        },
    }


def write_report(report: dict[str, Any], *, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    visit_id = safe_text(report.get("visit_id"))
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = output_dir / f"luxian_0609_trigger_gate_mainline_{stamp}_{visit_id}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


async def run_one_visit(
    *,
    visit_id: str,
    output_dir: Path,
    schema: str,
    use_execution_cache: bool,
    institute_id: str = "LX0609_SYN",
    rule_ids: list[str] | None = None,
) -> dict[str, Any]:
    from app.services.qc_input_adapters.running_final_bundle_runtime import evaluate_running_final_bundle
    from app.services.qc_rule_sets import get_sichuan_rule_set
    from app.services.sichuan_qc_service import SichuanQCService

    rule_set = get_sichuan_rule_set("luxian_0609_qc_v1")
    if not rule_set:
        raise RuntimeError("未找到规则集 luxian_0609_qc_v1")

    qc_service = SichuanQCService()
    start = time.perf_counter()
    error = ""
    result: dict[str, Any] = {}
    try:
        result = await evaluate_running_final_bundle(
            qc_service=qc_service,
            scene="running",
            institute_id=institute_id,
            patient_id=f"P-{visit_id}",
            visit_id=visit_id,
            schema=schema,
            rule_ids=list(rule_ids or rule_set.rule_ids),
            bucket_strategy=rule_set.bucket_strategy,
            quality_profile=rule_set.quality_profile,
            batch_output_mode=rule_set.batch_output_mode,
            enable_selective_refine=rule_set.enable_selective_refine,
            refine_confidence_threshold=rule_set.refine_confidence_threshold,
            max_refine_candidates=rule_set.max_refine_candidates,
            use_execution_cache=use_execution_cache,
            rule_set_key=rule_set.key,
        )
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    report = build_report(
        visit_id=visit_id,
        elapsed_ms=elapsed_ms,
        result=result,
        error=error,
    )
    path = write_report(report, output_dir=output_dir)
    actual_statuses = {
        safe_text(item.get("qc_point_id") or item.get("rule_id")): safe_text(
            item.get("result_status") or item.get("status")
        )
        for item in report["execution"]["trigger_gate_customer_results"]
        if isinstance(item, dict)
    }
    return {
        "visit_id": visit_id,
        "path": str(path),
        "elapsed_ms": elapsed_ms,
        "error": error,
        "result_count": len(report["execution"]["trigger_gate_customer_results"]),
        "actual_statuses": actual_statuses,
    }


async def run_all(args: argparse.Namespace) -> int:
    for env_path in args.env_file or []:
        load_env_file(Path(env_path))
    if args.preflight:
        report = build_preflight(args)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["ok"] else 2
    if not os.environ.get("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL 未配置，无法读取 PG 合成样本")
    validate_runtime_env()
    validation_matrix = (
        load_validation_matrix(
            Path(args.validation_matrix), defined_only=bool(args.defined_only)
        )
        if args.validation_matrix
        else {}
    )
    matrix_scope = summarize_validation_matrix(validation_matrix)
    if validation_matrix:
        all_visit_ids = sorted(validation_matrix)
    else:
        data = load_json(Path(args.synthetic_cases))
        all_visit_ids = iter_visit_ids(data)
    visit_ids = select_visit_ids(all_visit_ids, args)
    if not visit_ids:
        raise RuntimeError("没有选中任何 LX0609_SYN_* 样本")

    output_dir = Path(args.output_dir)
    print(
        f"[mainline] selected_visits={len(visit_ids)} "
        f"unique_rules={matrix_scope['unique_rule_count']} "
        f"assertions={matrix_scope['assertion_count']} output_dir={output_dir}"
    )
    rows: list[dict[str, Any]] = []
    for index, visit_id in enumerate(visit_ids, start=1):
        print(f"[mainline] {index}/{len(visit_ids)} running {visit_id}")
        row = await run_one_visit(
            visit_id=visit_id,
            output_dir=output_dir,
            schema=str(args.schema),
            use_execution_cache=not bool(args.no_cache),
            institute_id=resolve_synthetic_institute_id(
                visit_id, safe_text(args.institute_id)
            ),
            rule_ids=list(validation_matrix.get(visit_id, {})) or None,
        )
        expected_statuses = validation_matrix.get(visit_id, {})
        actual_statuses = row.pop("actual_statuses", {})
        mismatches = [
            {
                "rule_id": rule_id,
                "expected_status": expected_status,
                "actual_status": actual_statuses.get(rule_id, "missing"),
            }
            for rule_id, expected_status in expected_statuses.items()
            if actual_statuses.get(rule_id) != expected_status
        ]
        row["expected_count"] = len(expected_statuses)
        row["matched_count"] = len(expected_statuses) - len(mismatches)
        row["mismatches"] = mismatches
        rows.append(row)
        status = "OK" if not row.get("error") and not mismatches else "ERROR"
        print(
            f"[mainline] {visit_id} {status} "
            f"results={row.get('result_count')} elapsed_ms={row.get('elapsed_ms')} "
            f"path={row.get('path')}"
        )

    failed = [row for row in rows if row.get("error") or row.get("mismatches")]
    summary_path = output_dir / f"luxian_0609_mainline_run_{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    summary_path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "selected_count": len(visit_ids),
                "failed_count": len(failed),
                "unique_rule_count": matrix_scope["unique_rule_count"],
                "assertion_count": matrix_scope["assertion_count"],
                "expected_count": sum(int(row.get("expected_count") or 0) for row in rows),
                "matched_count": sum(int(row.get("matched_count") or 0) for row in rows),
                "rows": rows,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"[mainline] summary={summary_path}")
    return 1 if failed and not args.allow_errors else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="用正式主干链路运行泸县0609合成样本，并输出评估器兼容报告")
    parser.add_argument("--visit-id", action="append", default=[], help="只运行指定 synthetic visit，可重复传入")
    parser.add_argument("--limit", type=int, default=0, help="按 visit_id 排序后只运行前 N 份")
    parser.add_argument("--schema", default="public")
    parser.add_argument(
        "--institute-id",
        default="",
        help="默认按 synthetic visit 前缀识别；仅非标准样本需要显式指定",
    )
    parser.add_argument("--synthetic-cases", default=str(SYNTHETIC_CASES_PATH))
    parser.add_argument(
        "--validation-matrix",
        default="",
        help="按 CSV 中 visit_id/rule_id/expected_status 仅运行并核对绑定规则",
    )
    parser.add_argument(
        "--defined-only",
        action="store_true",
        help="仅运行规则合同中非 pending_definition 的规则（当前为66条）",
    )
    parser.add_argument("--output-dir", default=str(RUNTIME_DIR))
    parser.add_argument("--env-file", action="append", default=[], help="加载本地 env 文件；不会打印密钥内容")
    parser.add_argument("--preflight", action="store_true", help="只检查样本、PG 和 LLM 前置条件，不调用模型")
    parser.add_argument("--no-cache", action="store_true", help="关闭执行缓存")
    parser.add_argument("--allow-errors", action="store_true", help="即使某些样本失败也返回 0")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return asyncio.run(run_all(args))


if __name__ == "__main__":
    raise SystemExit(main())
