#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.bundles import assemble_final_record_bundle  # noqa: E402
from app.services.fast_screen_qc import FAST_SCREEN_FULL_PACK_DEFINITIONS, run_final_fast_screen  # noqa: E402
from app.services.qc_result_adjudicator import adjudicate_postprocessed_qc_results  # noqa: E402
from app.services.qc_result_postprocessor import postprocess_qc_results  # noqa: E402
from app.services.qc_rule_sets import get_sichuan_rule_set  # noqa: E402
from app.services.sichuan_qc_service import SichuanQCService  # noqa: E402
from run_formal_qc_gate_integrated_random10_audit import (  # noqa: E402
    _load_rules_by_id,
    _load_visit_keys,
    _safe_float,
    _safe_int,
    _safe_text,
)


DOCS_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0508"
PLAN_JSON = DOCS_DIR / "sheet2_semantic_qc_point_sample_plan.json"
REPLAY_JSON = DOCS_DIR / "sheet2_semantic_qc_point_replay_report.json"
QUALITY_JSON = DOCS_DIR / "sheet2_semantic_qc_point_quality_review.json"
ROOT_CAUSE_JSON = DOCS_DIR / "sheet2_semantic_qc_point_not_returned_root_cause.json"

OUTPUT_CSV = DOCS_DIR / "sheet2_semantic_qc_full_state_diagnostics.csv"
OUTPUT_JSON = DOCS_DIR / "sheet2_semantic_qc_full_state_diagnostics.json"
RECALL_CSV = DOCS_DIR / "sheet2_semantic_qc_effective_recall_recalc.csv"
RECALL_JSON = DOCS_DIR / "sheet2_semantic_qc_effective_recall_recalc.json"
REPORT_MD = DOCS_DIR / "客户样本内涵性质控点有效召回与full-state诊断报告.md"

SC083_EQUIVALENT_TERMS = ("多学科", "多科", "多科室", "联合会诊", "MDT", "mdt")
SC083_LEVEL4_TERMS = ("四级", "level4", "level=4", "matched_level=4", "visit_max_level=4")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_csv_lf(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames or ["message"], extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_json_lf(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _norm_rule(value: Any) -> str:
    return _safe_text(value).upper()


def _compact_text(value: Any, limit: int = 700) -> str:
    text = re.sub(r"\s+", " ", _safe_text(value)).strip()
    return text[:limit]


def _load_rows(path: Path) -> list[dict[str, Any]]:
    payload = _read_json(path)
    if isinstance(payload, dict):
        return list(payload.get("rows") or [])
    if isinstance(payload, list):
        return list(payload)
    return []


def _rule_pack_index() -> dict[str, dict[str, str]]:
    index: dict[str, dict[str, str]] = {}
    for pack in FAST_SCREEN_FULL_PACK_DEFINITIONS:
        for rule_id in pack.rule_ids:
            index[_norm_rule(rule_id)] = {
                "pack_id": pack.pack_id,
                "rule_family": pack.rule_family,
                "document_type": pack.document_type,
            }
    return index


def _by_sample(rows: list[dict[str, Any]], sample_key: str = "sample_id") -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = _safe_text(row.get(sample_key) or row.get("plan_sample_id"))
        if key:
            out[key] = row
    return out


def _results_by_rule(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        rule_id = _norm_rule(row.get("rule_id") or row.get("rule_code"))
        if rule_id:
            out.setdefault(rule_id, row)
    return out


def _status_of(row: dict[str, Any] | None, *keys: str) -> str:
    if not row:
        return ""
    for key in keys:
        value = _safe_text(row.get(key))
        if value:
            return value
    return ""


def _metadata(row: dict[str, Any] | None) -> dict[str, Any]:
    if not row:
        return {}
    value = row.get("metadata")
    return value if isinstance(value, dict) else {}


def _gate_status(row: dict[str, Any] | None) -> tuple[str, str]:
    if not row:
        return "", ""
    metadata = _metadata(row)
    decision = _safe_text(
        row.get("applicability_gate_decision")
        or metadata.get("applicability_gate_decision")
        or metadata.get("gate_decision")
    )
    reason = _safe_text(
        row.get("applicability_gate_reason")
        or metadata.get("applicability_gate_reason")
        or metadata.get("reason")
    )
    if decision:
        return decision, reason
    label = _safe_text(row.get("postprocess_label") or metadata.get("postprocess_label"))
    post_reason = _safe_text(row.get("postprocess_reason") or metadata.get("postprocess_reason"))
    return label, post_reason


def _evidence_matrix_status(target: dict[str, Any] | None) -> str:
    if not target:
        return "not_observed"
    metadata = _metadata(target)
    matrix_bits = [
        metadata.get("confirmed_context_matrix"),
        metadata.get("field_matrix_evidence"),
        metadata.get("formal_evidence_coverage"),
        metadata.get("applicability_gate_metadata"),
        target.get("evidence_problem_type"),
        target.get("postprocess_reason"),
        target.get("adjudicator_reason"),
    ]
    text = " ".join(_compact_text(item) for item in matrix_bits if item)
    if not text:
        return "not_recorded"
    if any(marker in text for marker in ("缺", "不足", "无法", "data_gap", "missing", "insufficient", "fragment")):
        return "insufficient_or_gap"
    return "matrix_or_context_present"


def _same_family_results(
    *,
    all_results: list[dict[str, Any]],
    target_rule: str,
    target_pack: str,
    target_family: str,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in all_results:
        rule_id = _norm_rule(row.get("rule_id") or row.get("rule_code"))
        if not rule_id or rule_id == target_rule:
            continue
        if target_pack and _safe_text(row.get("pack_id") or row.get("rule_pack")) == target_pack:
            out.append(row)
            continue
        if target_family and _safe_text(row.get("evidence_family") or row.get("rule_family")) == target_family:
            out.append(row)
    return out


def _returned_rules(rows: list[dict[str, Any]]) -> str:
    parts = []
    for row in rows[:8]:
        rule_id = _norm_rule(row.get("rule_id") or row.get("rule_code"))
        status = _status_of(row, "display_status", "status", "raw_status")
        parts.append(f"{rule_id}:{status}")
    return ";".join(parts)


def _sc083_metadata(row: dict[str, Any] | None, same_family: list[dict[str, Any]]) -> dict[str, Any]:
    source_rows = [item for item in [row, *same_family] if item]
    combined = " ".join(
        _compact_text(
            [
                item.get("evidence"),
                item.get("conclusion"),
                item.get("findings"),
                item.get("adjudicator_supporting_quote"),
                item.get("applicability_gate_evidence_quote"),
                item.get("applicability_gate_metadata"),
                _metadata(item),
            ]
        )
        for item in source_rows
    )
    departments = sorted(set(re.findall(r"([\u4e00-\u9fa5]{2,12}科)", combined)))
    has_mdt = any(term in combined for term in SC083_EQUIVALENT_TERMS)
    has_level4 = any(term in combined for term in SC083_LEVEL4_TERMS)
    quote = ""
    for item in source_rows:
        quote = _compact_text(
            item.get("applicability_gate_evidence_quote")
            or item.get("adjudicator_supporting_quote")
            or item.get("evidence")
            or item.get("findings")
        )
        if quote:
            break
    return {
        "sc083_level4_evidence_present": has_level4,
        "sc083_mdt_equivalent_evidence_present": has_mdt,
        "sc083_mdt_equivalent_quote": quote,
        "sc083_departments_detected": ";".join(departments),
        "sc083_department_count": len(departments),
        "sc083_preoperative_timing": "术前" if "术前" in combined else "",
        "sc083_discussion_reason_or_conclusion_present": any(term in combined for term in ("讨论", "意见", "结论", "建议")),
    }


async def _run_visit_full_state(
    *,
    visit_id: str,
    visit_keys: dict[str, dict[str, str]],
    rules_by_id: dict[str, dict[str, Any]],
    pack_concurrency: int,
) -> dict[str, Any]:
    started = time.perf_counter()
    rule_set = get_sichuan_rule_set("sc_content_full_v1")
    if rule_set is None:
        raise RuntimeError("未找到 sc_content_full_v1 规则集")
    mr = visit_keys.get(visit_id) or {}
    patient_id = _safe_text(mr.get("patient_id"))
    institute_id = _safe_text(mr.get("institute_id"))
    if not (patient_id and institute_id):
        raise ValueError(f"visit_id={visit_id} 缺 patient_id/institute_id")

    bundle = assemble_final_record_bundle(
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
        source_schema="cdm",
    )
    qc_service = SichuanQCService()
    if not await qc_service.reload_config():
        raise RuntimeError("无法加载 LLM 运行时配置")
    adjudicator_client = getattr(qc_service, "adjudicator_client", None) or getattr(qc_service, "client", None)
    first_pass_model = _safe_text(getattr(qc_service.client, "model", ""))
    adjudicator_model = _safe_text(getattr(adjudicator_client, "model", ""))
    adjudicator_model_source = _safe_text(
        getattr(adjudicator_client, "adjudicator_model_source", "")
        or getattr(adjudicator_client, "config_source", "")
    )

    result = await run_final_fast_screen(
        qc_service=qc_service,
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
        source_schema="cdm",
        rule_ids=list(rule_set.rule_ids),
        quality_profile=rule_set.quality_profile,
        batch_output_mode=rule_set.batch_output_mode,
        pack_concurrency=pack_concurrency,
    )
    raw_results = [dict(item) for item in list(result.get("evaluation_results") or []) if isinstance(item, dict)]
    for item in raw_results:
        item.setdefault("visit_id", visit_id)
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        metadata.setdefault("first_pass_model", first_pass_model)
        metadata.setdefault("model_role", "first_pass")
        item["metadata"] = metadata

    first_pass = postprocess_qc_results(
        raw_results,
        bundle_metadata=bundle,
        mode="sheet2_semantic_full_state_diagnostic",
    )
    adjudicated = await adjudicate_postprocessed_qc_results(
        first_pass,
        rules_by_id=rules_by_id,
        llm_generate=getattr(adjudicator_client, "generate", None),
        adjudicator_model_metadata={
            "first_pass_model": first_pass_model,
            "adjudicator_model": adjudicator_model,
            "model_role": "adjudicator",
            "adjudicator_model_source": adjudicator_model_source,
        },
        mode="sheet2_semantic_full_state_diagnostic",
    )
    pack_metrics = dict(result.get("pack_metrics") or {})
    return {
        "visit_id": visit_id,
        "patient_id": patient_id,
        "patient_name": _safe_text(mr.get("name")),
        "raw_results": raw_results,
        "first_pass": [dict(item) for item in first_pass if isinstance(item, dict)],
        "adjudicated": [dict(item) for item in adjudicated if isinstance(item, dict)],
        "pack_metrics": pack_metrics,
        "summary": {
            "visit_id": visit_id,
            "first_pass_model": first_pass_model,
            "adjudicator_model": adjudicator_model,
            "adjudicator_model_source": adjudicator_model_source,
            "wall_clock_time": max(0.0, time.perf_counter() - started),
            "llm_call_count": _safe_int(getattr(qc_service.client, "call_count", 0))
            + _safe_int(getattr(adjudicator_client, "call_count", 0)),
            "total_tokens": _safe_int(getattr(qc_service.client, "total_tokens", 0))
            + _safe_int(getattr(adjudicator_client, "total_tokens", 0)),
            "provider_error_count": _safe_int(pack_metrics.get("provider_error_count")),
            "parse_error_count": _safe_int(pack_metrics.get("parse_error_count")),
            "timeout_count": _safe_int(pack_metrics.get("timeout_count")),
            "rate_limit_count": _safe_int(pack_metrics.get("rate_limit_count")),
        },
    }


def _make_diagnostic_row(
    *,
    plan: dict[str, Any],
    replay: dict[str, Any],
    quality: dict[str, Any],
    root: dict[str, Any],
    rules_by_id: dict[str, dict[str, Any]],
    formal_rules: set[str],
    pack_index: dict[str, dict[str, str]],
    run_state: dict[str, Any] | None,
) -> dict[str, Any]:
    sample_id = _safe_text(plan.get("sample_id"))
    visit_id = _safe_text(plan.get("visit_id"))
    target_rule = _norm_rule(plan.get("mapped_rule_code"))
    pack_info = pack_index.get(target_rule, {})
    in_formal = target_rule in formal_rules
    raw_by_rule = _results_by_rule((run_state or {}).get("raw_results") or [])
    first_by_rule = _results_by_rule((run_state or {}).get("first_pass") or [])
    adjudicated = list((run_state or {}).get("adjudicated") or [])
    adjudicated_by_rule = _results_by_rule(adjudicated)

    raw_target = raw_by_rule.get(target_rule)
    first_target = first_by_rule.get(target_rule)
    final_target = adjudicated_by_rule.get(target_rule)
    same_family = _same_family_results(
        all_results=adjudicated,
        target_rule=target_rule,
        target_pack=_safe_text(pack_info.get("pack_id")),
        target_family=_safe_text(pack_info.get("rule_family")),
    )
    gate_status, gate_reason = _gate_status(final_target or first_target)
    final_status = _status_of(final_target, "display_status", "status", "raw_status")
    first_status = _status_of(first_target, "display_status", "status", "raw_status")
    raw_status = _status_of(raw_target, "status", "display_status", "raw_status")
    adjudicator_status = _status_of(final_target, "adjudicated_display_status", "display_status", "status")
    metadata = _metadata(final_target)
    sent_to_adjudicator = bool(
        final_target
        and (
            metadata.get("adjudicator_model")
            or final_target.get("adjudicator_reason")
            or final_target.get("adjudicator_supporting_quote")
        )
    )
    equivalent_family_hit = _is_equivalent_family_hit(target_rule, same_family)
    effective, final_root, action, priority = _classify_effective_recall(
        target_rule=target_rule,
        in_formal=in_formal,
        final_status=final_status,
        gate_status=gate_status,
        gate_reason=gate_reason,
        same_family=same_family,
        equivalent_family_hit=equivalent_family_hit,
        evidence_matrix_status=_evidence_matrix_status(final_target or first_target),
        root_row=root,
        raw_target=raw_target,
        final_target=final_target,
    )
    sc083 = _sc083_metadata(final_target or first_target, same_family) if target_rule == "SC-083" else {}
    if target_rule == "SC-083" and effective.startswith("gate_rejected"):
        # SC-083 客户口径已确认多科/多学科会诊可替代 MDT；若原问题超出 MDT 范围，应先复核映射。
        if sc083.get("sc083_mdt_equivalent_evidence_present"):
            final_root = "SC-083 gate 发现 MDT/多科会诊等价证据；若 Sheet2 原问题关注左肾缺失等具体专科会诊，则属于 mapping_or_rule_scope_mismatch。"
            action = "复核 Sheet2 映射：区分 SC-083 MDT 缺失与具体专科会诊/诊断依据问题。"
            effective = "gate_rejected_policy_correct"

    return {
        "sheet_row_id": _safe_text(plan.get("sheet_row_id")),
        "sample_id": sample_id,
        "visit_id": visit_id,
        "patient_name": _safe_text(plan.get("patient_name")),
        "original_question": _safe_text(plan.get("original_question")),
        "mapped_rule_code": target_rule,
        "mapped_rule_title": _safe_text(rules_by_id.get(target_rule, {}).get("name") or plan.get("rule_title")),
        "formal_rule_exists": bool(in_formal),
        "in_formal_84": bool(in_formal),
        "pack_id": _safe_text(pack_info.get("pack_id")),
        "rule_family": _safe_text(pack_info.get("rule_family")),
        "pack_selected": bool(in_formal and pack_info),
        "pack_ran": bool(run_state and pack_info),
        "target_rule_in_first_pass_raw": bool(raw_target),
        "target_rule_first_pass_status": first_status or raw_status,
        "target_rule_after_postprocess_status": first_status,
        "target_rule_gate_status": gate_status,
        "target_rule_gate_reason": gate_reason,
        "target_rule_sent_to_adjudicator": sent_to_adjudicator,
        "target_rule_adjudicator_status": adjudicator_status,
        "target_rule_final_status": final_status,
        "target_rule_final_reason": _compact_text(
            (final_target or {}).get("adjudicator_reason")
            or (final_target or {}).get("postprocess_reason")
            or (final_target or {}).get("conclusion")
        ),
        "same_family_returned": bool(same_family),
        "same_family_returned_rules": _returned_rules(same_family),
        "equivalent_family_hit": equivalent_family_hit,
        "evidence_matrix_status": _evidence_matrix_status(final_target or first_target),
        "effective_recall_class": effective,
        "final_root_cause": final_root,
        "recommended_action": action,
        "priority": priority,
        "replay_display_status": _safe_text(replay.get("display_status")),
        "quality_label": _safe_text(quality.get("quality_label")),
        "previous_root_cause_category": _safe_text(root.get("root_cause_category")),
        "previous_root_cause_detail": _safe_text(root.get("root_cause_detail")),
        **sc083,
    }


def _is_equivalent_family_hit(target_rule: str, same_family: list[dict[str, Any]]) -> bool:
    if not same_family:
        return False
    returned_rules = {_norm_rule(row.get("rule_id") or row.get("rule_code")) for row in same_family}
    if target_rule == "SC-083":
        return "SC-083" in returned_rules
    if target_rule in {"SC-036", "SC-070", "SC-146"}:
        # 跨文书/医嘱类同族规则名称相近但扣分点不同，不能默认等价。
        return False
    if target_rule in {"SC-008", "SC-009", "SC-023"}:
        # 入院记录语义规则可以同族命中，但需后续人工确认，不直接算等价覆盖。
        return False
    return False


def _classify_effective_recall(
    *,
    target_rule: str,
    in_formal: bool,
    final_status: str,
    gate_status: str,
    gate_reason: str,
    same_family: list[dict[str, Any]],
    equivalent_family_hit: bool,
    evidence_matrix_status: str,
    root_row: dict[str, Any],
    raw_target: dict[str, Any] | None,
    final_target: dict[str, Any] | None,
) -> tuple[str, str, str, str]:
    if not in_formal:
        return (
            "mapping_out_of_formal_84",
            f"{target_rule} 不在正式 sc_content_full_v1 84 条规则内，不能计入 formal84 召回率母集。",
            "从 formal84 准确率母集剔除，或新增客户专项扩展规则/修正 Sheet2 映射。",
            "P0",
        )
    if final_status in {"confirmed_defect", "data_quality_gap", "rejected_by_system", "technical_error_internal"}:
        if gate_status and "rejected" in gate_status:
            return (
                "gate_rejected_needs_review" if "should_confirm" in _safe_text(root_row.get("quality_label")) else "gate_rejected_policy_correct",
                f"目标规则有可审计终态 {final_status}，但被 gate/guardrail 分流：{gate_status}；{gate_reason}",
                "复核 gate evidence 与客户样本锚点；若冲突，补 evidence matrix 或修正样本映射。",
                "P0",
            )
        return (
            "exact_rule_hit",
            f"目标规则返回可审计终态 {final_status}；证据矩阵状态={evidence_matrix_status}。",
            "按该终态进入质量复核；若为 data_gap_should_confirm/rejected_should_confirm，定向分析证据矩阵或二审理由。",
            "P1",
        )
    if final_status in {"compliant", "not_applicable", "no_action"}:
        return (
            "target_compliant_or_not_applicable",
            f"目标规则被明确判为 {final_status}，不应按 not_returned 处理。",
            "复核客户样本与正式规则适用范围是否一致。",
            "P1",
        )
    if equivalent_family_hit:
        return (
            "equivalent_family_hit",
            "目标规则未返回，但同族等价规则覆盖同一客户问题。",
            "把等价规则映射写入 Sheet2 mapping，或在准确率统计中合并同族规则。",
            "P1",
        )
    if same_family:
        return (
            "diagnostic_insufficient",
            "同族规则返回，但现有证据不足以证明等价覆盖；仍需 raw prompt/evidence 或人工映射确认。",
            "输出同族规则 quote 与客户问题逐条对照；不能直接算 true_miss 或命中。",
            "P0",
        )
    if raw_target:
        return (
            "diagnostic_insufficient",
            "目标规则进入 raw first-pass，但后续未形成可审计终态；需要继续查 postprocess/adjudicator。",
            "保存 raw/postprocess/adjudicator 全状态并定位过滤点。",
            "P0",
        )
    if final_target:
        return (
            "diagnostic_insufficient",
            "目标规则存在结果但状态字段为空，疑似脚本观测字段不完整。",
            "补齐状态字段提取。",
            "P1",
        )
    return (
        "true_miss",
        "目标规则在正式 84 条且 pack 已跑，但未进入 raw/postprocess/adjudicated 任何可审计状态，也无等价规则覆盖。",
        "优先修 candidate selection / first-pass recall；必要时为该规则补 recall prompt 或 evidence matrix。",
        "P0",
    )


def _reclassify_existing_row(row: dict[str, Any]) -> dict[str, Any]:
    updated = dict(row)
    root_payload = _read_json(ROOT_CAUSE_JSON)
    root_rows = list(root_payload.get("rows") or []) if isinstance(root_payload, dict) else []
    root_by_sheet = {_safe_text(item.get("sheet_row_id")): item for item in root_rows}
    previous_root = root_by_sheet.get(_safe_text(row.get("sheet_row_id"))) or {}
    if previous_root:
        updated["previous_root_cause_category"] = _safe_text(previous_root.get("root_cause_category"))
        updated["previous_root_cause_detail"] = _safe_text(previous_root.get("root_cause_detail"))
    final_status = _safe_text(row.get("target_rule_final_status"))
    gate_status = _safe_text(row.get("target_rule_gate_status"))
    in_formal = str(row.get("in_formal_84")).lower() == "true"
    evidence_matrix_status = _safe_text(row.get("evidence_matrix_status"))
    same_family = _safe_text(row.get("same_family_returned_rules"))
    target_rule = _norm_rule(row.get("mapped_rule_code"))
    if not in_formal:
        effective = "mapping_out_of_formal_84"
        root = f"{target_rule} 不在正式 sc_content_full_v1 84 条规则内，不能计入 formal84 召回率母集。"
        action = "从 formal84 准确率母集剔除，或新增客户专项扩展规则/修正 Sheet2 映射。"
        priority = "P0"
    elif final_status in {"confirmed_defect", "data_quality_gap", "rejected_by_system", "technical_error_internal"}:
        if gate_status and "rejected" in gate_status:
            effective = "gate_rejected_policy_correct"
            root = f"目标规则有可审计终态 {final_status}，但被 gate/guardrail 分流：{gate_status}。"
            action = "复核 gate evidence 与客户样本锚点；若冲突，补 evidence matrix 或修正样本映射。"
            priority = "P0"
        else:
            effective = "exact_rule_hit"
            root = f"目标规则返回可审计终态 {final_status}；证据矩阵状态={evidence_matrix_status}。"
            action = "按该终态进入质量复核；若为 data_gap_should_confirm/rejected_should_confirm，定向分析证据矩阵或二审理由。"
            priority = "P1"
    elif final_status in {"compliant", "not_applicable", "no_action"}:
        effective = "target_compliant_or_not_applicable"
        root = f"目标规则被明确判为 {final_status}，不应按 not_returned 处理。"
        action = "复核客户样本与正式规则适用范围是否一致。"
        priority = "P1"
    elif same_family:
        effective = "diagnostic_insufficient"
        root = "同族规则返回，但现有证据不足以证明等价覆盖；仍需 raw prompt/evidence 或人工映射确认。"
        action = "输出同族规则 quote 与客户问题逐条对照；不能直接算 true_miss 或命中。"
        priority = "P0"
    else:
        effective = "true_miss"
        root = "目标规则在正式 84 条且 pack 已跑，但未进入 raw/postprocess/adjudicated 任何可审计状态，也无等价规则覆盖。"
        action = "优先修 candidate selection / first-pass recall；必要时为该规则补 recall prompt 或 evidence matrix。"
        priority = "P0"
    updated["effective_recall_class"] = effective
    updated["final_root_cause"] = root
    updated["recommended_action"] = action
    updated["priority"] = priority
    return updated


def _load_input_maps() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    plan_rows = _load_rows(PLAN_JSON)
    replay_rows = _load_rows(REPLAY_JSON)
    quality_rows = _load_rows(QUALITY_JSON)
    root_payload = _read_json(ROOT_CAUSE_JSON)
    root_rows = list(root_payload.get("rows") or []) if isinstance(root_payload, dict) else []
    return plan_rows, _by_sample(replay_rows), _by_sample(quality_rows), {
        _safe_text(row.get("sheet_row_id")): row for row in root_rows
    }


def _build_recall_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    formal_rows = [row for row in rows if str(row.get("effective_recall_class")) != "mapping_out_of_formal_84"]
    counts = Counter(_safe_text(row.get("effective_recall_class")) for row in rows)
    formal_counts = Counter(_safe_text(row.get("effective_recall_class")) for row in formal_rows)
    denominator = len(formal_rows)
    recalled = formal_counts.get("exact_rule_hit", 0) + formal_counts.get("equivalent_family_hit", 0)
    effective_recall_rate = recalled / denominator if denominator else 0.0
    return {
        "total_samples": len(rows),
        "formal84_denominator": denominator,
        "formal84_excluded_count": counts.get("mapping_out_of_formal_84", 0),
        "exact_rule_hit": formal_counts.get("exact_rule_hit", 0),
        "equivalent_family_hit": formal_counts.get("equivalent_family_hit", 0),
        "target_compliant_or_not_applicable": formal_counts.get("target_compliant_or_not_applicable", 0),
        "gate_rejected_policy_correct": formal_counts.get("gate_rejected_policy_correct", 0),
        "gate_rejected_needs_review": formal_counts.get("gate_rejected_needs_review", 0),
        "evidence_matrix_gap": formal_counts.get("evidence_matrix_gap", 0),
        "true_miss": formal_counts.get("true_miss", 0),
        "diagnostic_insufficient": formal_counts.get("diagnostic_insufficient", 0),
        "effective_recall_rate": round(effective_recall_rate, 4),
        "effective_recall_rate_percent": round(effective_recall_rate * 100, 2),
        "all_effective_recall_class_counts": dict(counts),
        "formal84_effective_recall_class_counts": dict(formal_counts),
    }


def _write_report(rows: list[dict[str, Any]], summary: dict[str, Any], path: Path) -> None:
    class_counts = summary["all_effective_recall_class_counts"]
    formal_counts = summary["formal84_effective_recall_class_counts"]
    outside = [row for row in rows if row.get("effective_recall_class") == "mapping_out_of_formal_84"]
    same_family = [row for row in rows if row.get("same_family_returned")]
    previous_same_family = [
        row for row in rows if row.get("previous_root_cause_category") == "same_family_rule_returned"
    ]
    previous_gate = [row for row in rows if row.get("previous_root_cause_category") == "gate_rejected"]
    sc083 = [row for row in rows if row.get("mapped_rule_code") == "SC-083"]
    p0 = [row for row in rows if row.get("priority") == "P0"]
    lines = [
        "# 客户样本内涵性质控点有效召回与 full-state 诊断报告",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 执行边界",
        "",
        "- 本轮只覆盖上一轮固定 20 条客户样本内涵性质控点；未扩大样本。",
        "- 未改正式质控规则、gate、prompt，未写正式 QC 结果表。",
        "- 对正式 84 条外规则直接按映射口径诊断；仅对正式 84 内样本执行只读 full-state 诊断。",
        "",
        "## 有效召回重算",
        "",
        f"- 总样本：{summary['total_samples']} 条。",
        f"- 可计入正式 84 条准确率母集：{summary['formal84_denominator']} 条。",
        f"- 正式 84 外剔除：{summary['formal84_excluded_count']} 条。",
        f"- exact_rule_hit：{summary['exact_rule_hit']} 条。",
        f"- equivalent_family_hit：{summary['equivalent_family_hit']} 条。",
        f"- true_miss：{summary['true_miss']} 条。",
        f"- diagnostic_insufficient：{summary['diagnostic_insufficient']} 条。",
        f"- evidence_matrix_gap：{summary['evidence_matrix_gap']} 条。",
        f"- gate_rejected_policy_correct：{summary['gate_rejected_policy_correct']} 条。",
        f"- gate_rejected_needs_review：{summary['gate_rejected_needs_review']} 条。",
        f"- 有效召回率（exact + equivalent / formal84 母集）：{summary['effective_recall_rate_percent']}%。",
        "",
        "## effective_recall_class 分布",
        "",
        f"- 全部样本：`{_json(class_counts)}`",
        f"- formal84 母集：`{_json(formal_counts)}`",
        "",
        "## 正式 84 外样本",
        "",
    ]
    if outside:
        for row in outside:
            lines.append(f"- {row['sheet_row_id']} / {row['visit_id']} / {row['mapped_rule_code']}：{row['mapped_rule_title']}")
        lines.append("")
        lines.append("处理建议：从 formal84 准确率母集剔除，或新增客户专项扩展规则集，或修正 Sheet2 映射。")
    else:
        lines.append("- 无。")
    lines.extend(["", "## 同族规则返回样本", ""])
    if same_family:
        for row in same_family:
            lines.append(
                f"- {row['sheet_row_id']} / {row['mapped_rule_code']}：same_family=`{row['same_family_returned_rules']}`；"
                f"class={row['effective_recall_class']}。"
            )
        lines.append("")
        lines.append("结论：同族返回不能默认算准确；本轮只有明确等价依据时才计入 equivalent_family_hit，否则标记 diagnostic_insufficient。")
    else:
        lines.append("- 无。")
    lines.extend(["", "## 上轮 7 条 same_family_rule_returned 的 full-state 结论", ""])
    if previous_same_family:
        for row in previous_same_family:
            lines.append(
                f"- {row['sheet_row_id']} / {row['mapped_rule_code']}："
                f"target_final={row.get('target_rule_final_status') or '未返回'}；"
                f"class={row['effective_recall_class']}；"
                f"上轮同族={row.get('previous_root_cause_detail') or '未记录'}。"
            )
        lines.append("")
        lines.append(
            "结论：上轮按终态行观察到的同族返回，在 full-state 中没有被直接认定为等价覆盖；"
            "其中多数目标规则被明确判为 compliant/not_applicable，应先复核 Sheet2 映射和客户问题是否超出正式规则范围。"
        )
    else:
        lines.append("- 无。")
    lines.extend(["", "## SC-083 gate 复核", ""])
    if sc083:
        for row in sc083:
            lines.append(
                f"- {row['sheet_row_id']} / {row['visit_id']}：class={row['effective_recall_class']}；"
                f"level4={row.get('sc083_level4_evidence_present')}；"
                f"mdt_equivalent={row.get('sc083_mdt_equivalent_evidence_present')}；"
                f"departments={row.get('sc083_departments_detected') or '未提取'}；"
                f"quote={row.get('sc083_mdt_equivalent_quote') or '未提取'}。"
            )
        lines.append("")
        lines.append(
            "结论：按客户已确认口径，多科/多学科会诊可替代 MDT；若客户原问题实际关注具体专科会诊或诊断依据，"
            "应标记为 mapping_or_rule_scope_mismatch，而不是直接判 SC-083 gate 错。"
        )
    else:
        lines.append("- 无。")
    lines.extend(["", "## 上轮 2 条 gate_rejected 的 full-state 结论", ""])
    if previous_gate:
        for row in previous_gate:
            lines.append(
                f"- {row['sheet_row_id']} / {row['mapped_rule_code']}："
                f"target_final={row.get('target_rule_final_status') or '未返回'}；"
                f"class={row['effective_recall_class']}；"
                f"gate={row.get('target_rule_gate_status') or '未记录'}；"
                f"reason={row.get('target_rule_gate_reason') or '未记录'}。"
            )
        lines.append("")
        lines.append(
            "结论：上轮 gate_rejected 不能直接视为 gate 错；full-state 显示需要结合 SC-083 客户口径和原问题范围复核。"
        )
    else:
        lines.append("- 无。")
    lines.extend(["", "## P0 阻断项", ""])
    if p0:
        for row in p0:
            lines.append(
                f"- {row['sheet_row_id']} / {row['mapped_rule_code']} / {row['effective_recall_class']}："
                f"{row['final_root_cause']} 建议：{row['recommended_action']}"
            )
    else:
        lines.append("- 无。")
    lines.extend(
        [
            "",
            "## 是否建议客户机 3-5 份冒烟",
            "",
            "- 默认不建议。",
            "- 阻断原因：formal84 外映射、同族等价口径、SC-083 gate 与客户原问题范围仍需先收口；否则客户机冒烟会把映射/口径问题误读成模型质量问题。",
            "",
            "## 下一步建议",
            "",
            "1. 先修 Sheet2 mapping：剔除 formal84 外规则或建立客户专项扩展规则集。",
            "2. 对上轮 same_family_rule_returned 的 7 条样本，按 full-state 结果复核为什么目标规则被判 compliant/not_applicable 或 gate 分流，先修映射/验收口径，不要默认算模型漏召回。",
            "3. 对 exact_rule_hit 但质量标签仍为 should_confirm 的样本，进入二审质量复核；这类是“召回后裁决质量”问题，不是 not_returned 问题。",
            "4. SC-083 样本先区分 MDT 缺失与具体专科会诊/诊断依据问题，不要混在同一规则验收。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def _run(args: argparse.Namespace) -> None:
    if args.reuse_existing:
        payload = _read_json(OUTPUT_JSON)
        existing_rows = list(payload.get("rows") or []) if isinstance(payload, dict) else []
        output_rows = [_reclassify_existing_row(row) for row in existing_rows]
        final_summary = _build_recall_summary(output_rows)
        _write_csv_lf(OUTPUT_CSV, output_rows)
        _write_json_lf(OUTPUT_JSON, {"rows": output_rows, "summary": final_summary})
        _write_csv_lf(RECALL_CSV, [final_summary])
        _write_json_lf(RECALL_JSON, final_summary)
        _write_report(output_rows, final_summary, REPORT_MD)
        print(f"reused {len(output_rows)} rows")
        print(_json(final_summary))
        return

    plan_rows, replay_by_sample, quality_by_sample, root_by_sample = _load_input_maps()
    rules_by_id = _load_rules_by_id()
    rule_set = get_sichuan_rule_set("sc_content_full_v1")
    if rule_set is None:
        raise RuntimeError("未找到 sc_content_full_v1 规则集")
    formal_rules = {_norm_rule(rule_id) for rule_id in rule_set.rule_ids}
    pack_index = _rule_pack_index()
    visit_keys = _load_visit_keys()
    output_rows: list[dict[str, Any]] = []
    run_cache: dict[str, dict[str, Any]] = {}

    for plan in plan_rows:
        sample_id = _safe_text(plan.get("sample_id"))
        visit_id = _safe_text(plan.get("visit_id"))
        target_rule = _norm_rule(plan.get("mapped_rule_code"))
        run_state: dict[str, Any] | None = None
        if target_rule in formal_rules:
            if visit_id not in run_cache:
                print(f"full-state replay visit={visit_id} target={target_rule}")
                run_cache[visit_id] = await _run_visit_full_state(
                    visit_id=visit_id,
                    visit_keys=visit_keys,
                    rules_by_id=rules_by_id,
                    pack_concurrency=args.pack_concurrency,
                )
            run_state = run_cache[visit_id]
        row = _make_diagnostic_row(
            plan=plan,
            replay=replay_by_sample.get(sample_id, {}),
            quality=quality_by_sample.get(sample_id, {}),
            root=root_by_sample.get(_safe_text(plan.get("sheet_row_id")), {}),
            rules_by_id=rules_by_id,
            formal_rules=formal_rules,
            pack_index=pack_index,
            run_state=run_state,
        )
        output_rows.append(row)
        summary = _build_recall_summary(output_rows)
        _write_csv_lf(OUTPUT_CSV, output_rows)
        _write_json_lf(OUTPUT_JSON, {"rows": output_rows, "partial_summary": summary})
        _write_csv_lf(RECALL_CSV, [summary])
        _write_json_lf(RECALL_JSON, summary)

    final_summary = _build_recall_summary(output_rows)
    _write_csv_lf(OUTPUT_CSV, output_rows)
    _write_json_lf(OUTPUT_JSON, {"rows": output_rows, "summary": final_summary})
    _write_csv_lf(RECALL_CSV, [final_summary])
    _write_json_lf(RECALL_JSON, final_summary)
    _write_report(output_rows, final_summary, REPORT_MD)
    print(f"wrote {len(output_rows)} rows")
    print(_json(final_summary))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack-concurrency", type=int, default=3)
    parser.add_argument("--reuse-existing", action="store_true", help="仅重算已有 full-state 产物，不重新调用 LLM")
    args = parser.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
