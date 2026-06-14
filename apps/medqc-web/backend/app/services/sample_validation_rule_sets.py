from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .customer_rule_sets import CUSTOMER_LUXIAN_RULE_SET_KEY, get_customer_luxian_rule_set
from .qc_rule_sets import QCRuleSet, get_sichuan_rule_set


FORMAL_FAST_SCREEN_FULL_MODE = "formal_fast_screen_full"
FORMAL_FAST_SCREEN_FULL_RULE_SET_KEY = "sc_content_full_v1"
LUXIAN_0609_QC_RULE_SET_KEY = "luxian_0609_qc_v1"
SAMPLE_PROGRAMMATIC_RULE_SET_KEY = "sample_programmatic_gate_v1"
SAMPLE_PROGRAMMATIC_RULE_SET_NAME = "样本硬门槛程序规则包 v1"
SAMPLE_PROGRAMMATIC_RULE_SET_VERSION = "2026-04-27"
SAMPLE_PROGRAMMATIC_RULE_IDS: tuple[str, ...] = (
    "SC-021",
    "SC-022",
    "SC-048",
    "SC-049",
    "SC-067",
    "SC-071",
    "SC-080",
    "SC-082",
    "SC-095",
    "SC-096",
    "SC-098",
    "SC-116",
    "SC-117",
    "SC-118",
    "SC-126",
    "LXE-18",
    "LXE-35",
)

SAMPLE_VALIDATION_DRAFTS: dict[str, dict[str, str]] = {
    "customer": {
        "id": "customer-rule-library",
        "rule_code": "CUSTOMER-RULE-LIBRARY",
        "rule_set_key": get_customer_luxian_rule_set().key,
        "rule_set_name": get_customer_luxian_rule_set().name,
    },
    "sc": {
        "id": "sc-sample-rule-library",
        "rule_code": "SC-SAMPLE-RULE-LIBRARY",
        "rule_set_key": "",
        "rule_set_name": "SC样本规则模式",
    },
    "programmatic": {
        "id": "sample-programmatic-gate",
        "rule_code": "SAMPLE-PROGRAMMATIC-GATE",
        "rule_set_key": SAMPLE_PROGRAMMATIC_RULE_SET_KEY,
        "rule_set_name": SAMPLE_PROGRAMMATIC_RULE_SET_NAME,
    },
    FORMAL_FAST_SCREEN_FULL_MODE: {
        "id": "sample-formal-fast-screen-full",
        "rule_code": "FORMAL-FAST-SCREEN-FULL",
        "rule_set_key": FORMAL_FAST_SCREEN_FULL_RULE_SET_KEY,
        "rule_set_name": "内涵质控全量 v1",
    },
}

LUXIAN_0609_COVERAGE_SUMMARY: dict[str, int] = {
    "已达正式口径": 3,
    "数据缺口待补": 3,
    "证据待补强": 10,
    "跨文书待完善": 14,
    "跨表联查待接入": 15,
    "待实现规则": 4,
}

ROOT = Path(__file__).resolve().parents[3]
DOCS_0602_DIR = ROOT / "docs" / "0602"
LUXIAN_0609_RELEASE_GATE_PATH = DOCS_0602_DIR / "luxian_0609_release_gate.json"
LUXIAN_0609_EVAL_PATH = DOCS_0602_DIR / "luxian_0609_qc_eval.json"
LUXIAN_0609_WORK_PACKAGES_PATH = DOCS_0602_DIR / "luxian_0609_formal_launch_work_packages.json"
LUXIAN_0609_PAGE_EVIDENCE_PATH = DOCS_0602_DIR / "luxian_0609_customer_sample_page_evidence.json"


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _build_luxian_0609_release_meta() -> dict[str, Any]:
    gate = _read_json(LUXIAN_0609_RELEASE_GATE_PATH, {})
    evaluation = _read_json(LUXIAN_0609_EVAL_PATH, {})
    work_packages = _read_json(LUXIAN_0609_WORK_PACKAGES_PATH, {})
    page_evidence = _read_json(LUXIAN_0609_PAGE_EVIDENCE_PATH, {})

    gate_summary = gate.get("summary") if isinstance(gate, dict) else {}
    eval_summary = evaluation.get("summary") if isinstance(evaluation, dict) else {}
    work_summary = work_packages.get("summary") if isinstance(work_packages, dict) else {}
    page_summary = page_evidence.get("summary") if isinstance(page_evidence, dict) else {}
    if not isinstance(gate_summary, dict):
        gate_summary = {}
    if not isinstance(eval_summary, dict):
        eval_summary = {}
    if not isinstance(work_summary, dict):
        work_summary = {}
    if not isinstance(page_summary, dict):
        page_summary = {}

    implementation_status = work_summary.get("implementation_status")
    phase_counts = work_summary.get("phase_counts")
    if not isinstance(implementation_status, dict):
        implementation_status = {}
    if not isinstance(phase_counts, dict):
        phase_counts = {}

    coverage_summary = {
        "已达正式口径": int(implementation_status.get("formal_ready") or LUXIAN_0609_COVERAGE_SUMMARY["已达正式口径"]),
        "数据缺口待补": int(implementation_status.get("ready_with_data_gap") or LUXIAN_0609_COVERAGE_SUMMARY["数据缺口待补"]),
        "证据待补强": int(implementation_status.get("needs_evidence_hardening") or LUXIAN_0609_COVERAGE_SUMMARY["证据待补强"]),
        "跨文书待完善": int(implementation_status.get("needs_cross_document") or LUXIAN_0609_COVERAGE_SUMMARY["跨文书待完善"]),
        "跨表联查待接入": int(implementation_status.get("needs_data_linkage") or LUXIAN_0609_COVERAGE_SUMMARY["跨表联查待接入"]),
        "待实现规则": int(implementation_status.get("needs_rule_implementation") or LUXIAN_0609_COVERAGE_SUMMARY["待实现规则"]),
    }
    release_ready = bool(gate.get("release_ready")) if isinstance(gate, dict) else False
    passed = int(gate_summary.get("passed_checks") or 0)
    failed = int(gate_summary.get("failed_checks") or 0)
    unverified = int(gate_summary.get("unverified_checks") or 0)
    coverage_status = (
        "正式上线闸门已通过。"
        if release_ready
        else f"正式上线闸门未通过：通过 {passed} 项，失败 {failed} 项，未验证 {unverified} 项；"
        f"当前 {coverage_summary['已达正式口径']} 条达到 formal_ready，其余规则仍需补证据、跨文书或跨表执行链路。"
    )
    return {
        "coverage_summary": coverage_summary,
        "coverage_status": coverage_status,
        "release_gate_summary": {
            "release_ready": release_ready,
            "passed_checks": passed,
            "failed_checks": failed,
            "unverified_checks": unverified,
            "blocking_count": int(gate_summary.get("blocking_count") or 0),
        },
        "evaluation_summary": {
            "rule_count": int(eval_summary.get("rule_count") or 0),
            "rules_with_all_case_types": int(eval_summary.get("rules_with_all_case_types") or 0),
            "rules_missing_case_types": int(eval_summary.get("rules_missing_case_types") or 0),
            "hit_count": int(eval_summary.get("hit_count") or 0),
            "manual_confirmed_correct_count": int(eval_summary.get("manual_confirmed_correct_count") or 0),
            "false_positive_count": int(eval_summary.get("false_positive_count") or 0),
            "false_negative_count": int(eval_summary.get("false_negative_count") or 0),
            "unknown_count": int(eval_summary.get("unknown_count") or 0),
            "evidence_missing_count": int(eval_summary.get("evidence_missing_count") or 0),
            "launch_status": eval_summary.get("launch_status") if isinstance(eval_summary.get("launch_status"), dict) else {},
        },
        "work_package_summary": {
            "package_count": int(work_summary.get("package_count") or 0),
            "phase_counts": phase_counts,
            "priority_counts": work_summary.get("priority_counts") if isinstance(work_summary.get("priority_counts"), dict) else {},
        },
        "page_closure_summary": {
            "page_verified": bool(page_summary.get("page_verified")),
            "capability_count": int(page_summary.get("capability_count") or 0),
            "passed_capabilities": int(page_summary.get("passed_capabilities") or 0),
            "partial_capabilities": int(page_summary.get("partial_capabilities") or 0),
            "failed_capabilities": int(page_summary.get("failed_capabilities") or 0),
            "blocking_count": int(page_summary.get("blocking_count") or 0),
            "status_counts": page_summary.get("status_counts") if isinstance(page_summary.get("status_counts"), dict) else {},
        },
    }

SAMPLE_VALIDATION_DRAFT_IDS = frozenset(str(item["id"]) for item in SAMPLE_VALIDATION_DRAFTS.values())
WORKSPACE_BATCH_DRAFT_IDS = frozenset({"sichuan-rule-library", *SAMPLE_VALIDATION_DRAFT_IDS})


def get_sample_programmatic_rule_set() -> QCRuleSet:
    return QCRuleSet(
        key=SAMPLE_PROGRAMMATIC_RULE_SET_KEY,
        name=SAMPLE_PROGRAMMATIC_RULE_SET_NAME,
        version=SAMPLE_PROGRAMMATIC_RULE_SET_VERSION,
        scope="running",
        rule_ids=SAMPLE_PROGRAMMATIC_RULE_IDS,
        execution_strategy="fast_screen",
        quality_profile="throughput_v1",
        bucket_strategy="fixed_packs",
        enable_selective_refine=False,
        refine_confidence_threshold=0.0,
        batch_output_mode="minimal",
        max_refine_candidates=0,
        description="样本病历硬门槛程序规则首批规则包，仅用于样本验证批次，不写正式缺陷。",
    )


def list_sample_validation_rule_sets() -> list[dict[str, Any]]:
    luxian_rule_set = get_sichuan_rule_set(LUXIAN_0609_QC_RULE_SET_KEY)
    formal_rule_set = get_sichuan_rule_set(FORMAL_FAST_SCREEN_FULL_RULE_SET_KEY)
    legacy_rule_set = get_customer_luxian_rule_set()
    programmatic_rule_set = get_sample_programmatic_rule_set()
    items: list[dict[str, Any]] = []
    if luxian_rule_set:
        luxian_release_meta = _build_luxian_0609_release_meta()
        items.append(
            {
                **luxian_rule_set.to_dict(),
                "rule_set_name": "泸县0609质控点验证 v1",
                "name": "泸县0609质控点验证 v1",
                "version": luxian_rule_set.version,
                "validation_mode": "customer",
                "requires_synced": False,
                "advanced": False,
                "display_group": "main",
                **luxian_release_meta,
                "note": "客户第一批专项验证规则包；当前为验证版，未达到正式上线闸门。",
            }
        )
    if formal_rule_set:
        items.append(
            {
                **formal_rule_set.to_dict(),
                "rule_set_name": "SC 内涵质控全量 v1",
                "name": "SC 内涵质控全量 v1",
                "version": formal_rule_set.version,
                "validation_mode": FORMAL_FAST_SCREEN_FULL_MODE,
                "requires_synced": True,
                "advanced": False,
                "display_group": "main",
                "coverage_summary": {},
                "note": "正式终末内涵质控全量规则，用于与客户专项验证结果做基线对照。",
            }
        )
    items.extend(
        [
            {
                "rule_set_key": "",
                "rule_set_name": "SC 样本规则模式",
                "name": "SC 样本规则模式",
                "rule_set_version": "running-batch-1",
                "version": "running-batch-1",
                "scope": "running",
                "rule_ids": [],
                "rule_count": 0,
                "validation_mode": "sc",
                "requires_synced": False,
                "advanced": True,
                "display_group": "advanced",
                "coverage_summary": {},
                "description": "按样本行候选规则执行，主要用于历史样本复现排查。",
                "note": "高级模式：规则数量由选中样本的候选规则决定。",
            },
            {
                **programmatic_rule_set.to_dict(),
                "name": programmatic_rule_set.name,
                "version": programmatic_rule_set.version,
                "validation_mode": "programmatic",
                "requires_synced": True,
                "advanced": True,
                "display_group": "advanced",
                "coverage_summary": {},
                "note": "高级模式：固定硬门槛程序规则包。",
            },
            {
                "rule_set_key": legacy_rule_set.key,
                "rule_set_name": f"{legacy_rule_set.name}（历史）",
                "name": f"{legacy_rule_set.name}（历史）",
                "rule_set_version": legacy_rule_set.version,
                "version": legacy_rule_set.version,
                "scope": legacy_rule_set.scope,
                "rule_ids": list(legacy_rule_set.rule_ids),
                "rule_count": len(legacy_rule_set.rule_ids),
                "validation_mode": "customer",
                "requires_synced": False,
                "advanced": True,
                "display_group": "advanced",
                "coverage_summary": {},
                "description": legacy_rule_set.description,
                "note": "历史客户专项规则包，仅用于兼容旧样本复现。",
            },
        ]
    )
    return items


def resolve_sample_validation_rule_set_by_key(rule_set_key: Any) -> dict[str, Any]:
    normalized_key = str(rule_set_key or "").strip()
    if not normalized_key:
        raise ValueError("rule_set_key 不能为空")

    if normalized_key == LUXIAN_0609_QC_RULE_SET_KEY:
        rule_set = get_sichuan_rule_set(normalized_key)
        if not rule_set:
            raise ValueError(f"未知规则集: {normalized_key}")
        return {"validation_mode": "customer", "rule_set": rule_set}

    if normalized_key == FORMAL_FAST_SCREEN_FULL_RULE_SET_KEY:
        rule_set = get_sichuan_rule_set(normalized_key)
        if not rule_set:
            raise ValueError(f"未知规则集: {normalized_key}")
        return {"validation_mode": FORMAL_FAST_SCREEN_FULL_MODE, "rule_set": rule_set}

    if normalized_key == CUSTOMER_LUXIAN_RULE_SET_KEY:
        return {"validation_mode": "customer", "rule_set": get_customer_luxian_rule_set()}

    if normalized_key == SAMPLE_PROGRAMMATIC_RULE_SET_KEY:
        return {"validation_mode": "programmatic", "rule_set": get_sample_programmatic_rule_set()}

    raise ValueError(f"未知规则集: {normalized_key}")


def resolve_sample_validation_pseudo_draft(
    *,
    validation_mode: str,
    pool_name: str,
    rule_count: int,
    rule_set_key: str | None = None,
    rule_set_name: str | None = None,
) -> dict[str, Any]:
    draft = dict(SAMPLE_VALIDATION_DRAFTS.get(validation_mode) or SAMPLE_VALIDATION_DRAFTS["customer"])
    normalized_pool_name = str(pool_name or "样本验证").strip() or "样本验证"
    draft["name"] = f"{normalized_pool_name}样本验证任务({max(1, int(rule_count or 1))}条规则)"
    draft["scene"] = "final" if validation_mode == FORMAL_FAST_SCREEN_FULL_MODE else "running"
    if rule_set_key:
        draft["rule_set_key"] = rule_set_key
    if rule_set_name:
        draft["rule_set_name"] = rule_set_name
    return draft


def is_workspace_batch_draft_id(value: Any) -> bool:
    return str(value or "").strip() in WORKSPACE_BATCH_DRAFT_IDS


def apply_programmatic_rule_runtime_overrides(rule: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(rule or {})
    normalized["executor_type"] = "program"
    normalized["prompt_version"] = "programmatic-v1"
    return normalized
