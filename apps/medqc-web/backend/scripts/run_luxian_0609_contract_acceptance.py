"""生成并校验 LX0609 当前生产规则的合同验收矩阵。

本脚本只读取规则合同和受控合成病例元数据，不连接数据库、不调用模型，也不执行
客户质控任务。矩阵中的 ``covered`` 表示已绑定受控 fixture，不表示引擎结果已经通过。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.settings import get_settings  # noqa: E402
from app.services.luxian_0609.native_package import (  # noqa: E402
    load_luxian_0609_dependency_inventory,
)
from app.services.luxian_0609.rule_contracts import (  # noqa: E402
    ALLOWED_FINAL_STATES,
    load_luxian_0609_rule_contracts,
)
from app.services.luxian_0609_rule_catalog import load_luxian_0609_rules  # noqa: E402
from app.services.luxian_0609_rule_master import (  # noqa: E402
    LUXIAN_0609_RULE_MASTER_VERSION,
    load_luxian_0609_rule_master,
)
from scripts.build_luxian_0609_runtime_manifest import (  # noqa: E402
    SCHEMA_VERSION as RUNTIME_MANIFEST_SCHEMA_VERSION,
    build_runtime_manifest,
)
from scripts.build_luxian_0609_0426_synthetic_v3 import (  # noqa: E402
    build_acceptance_fixture_bindings,
)
from scripts.luxian_0609_v3_controlled_evidence import (  # noqa: E402
    PROVISIONAL_RULE_IDS,
)


SCHEMA_VERSION = "lx0609-acceptance-matrix-v1"
MATRIX_PATH = BACKEND_ROOT / "app" / "data" / "luxian_0609_acceptance_matrix.json"
REPORT_PATH = PROJECT_ROOT / "docs" / "reports" / "luxian-0609-rule-acceptance-status.md"
SLOT_KEYS = ("compliant", "confirmed_issue", "not_applicable", "data_insufficient")
COVERAGE_STATES = frozenset({"covered", "missing", "not_required", "pending_definition"})

_TIME_LIMIT_PATTERN = re.compile(r"(?:\d+\s*(?:小时|天)|每天|三天|48\s*[-—–~至]\s*72\s*小时)")
_APPLICABILITY_TERMS = (
    "病情稳定",
    "病重",
    "病危",
    "CT/MRI",
    "病理",
    "细菌培养",
    "会诊",
    "恶性肿瘤",
    "手术",
    "麻醉",
    "输血",
    "死亡",
    "危急值",
    "抗菌药物",
    "经治医师发生变更",
    "转科",
    "有创操作",
)

# v3 病例用于跨文书端到端场景；互斥状态由现有 Native 单规则用例提供受控夹具。
# 这里仅登记真实断言最终状态的测试节点，不以“存在测试文件”推断覆盖。
_NATIVE_FIXTURE_SPECS = (
    ("LX0609-003", "non_compliant", "test_luxian_0609_native_surgery_gate_execution.py", "test_typed_003_preserves_time_and_source_boundaries"),
    ("LX0609-007", "non_compliant", "test_luxian_0609_native_course_quality_execution.py", "test_course_007_typed_truth_table_is_python_only_and_fail_closed"),
    ("LX0609-008", "non_compliant", "test_luxian_0609_native_course_quality_execution.py", "test_course_008_009_typed_natural_day_truth_table_requires_009_semantic_client"),
    ("LX0609-009", "non_compliant", "test_luxian_0609_native_course_quality_execution.py", "test_course_008_009_typed_natural_day_truth_table_requires_009_semantic_client"),
    ("LX0609-016", "non_compliant", "test_luxian_0609_native_course_quality_execution.py", "test_typed_016_distinguishes_absent_unavailable_and_structured_comparable_bodies"),
    ("LX0609-018", "non_compliant", "test_luxian_0609_native_course_quality_execution.py", "test_typed_018_combines_length_and_diagnostic_direction"),
    ("LX0609-024", "non_compliant", "test_luxian_0609_surgery_text_fact_contract.py", "test_024_uses_available_current_surgery_material_without_strict_time"),
    ("LX0609-025", "non_compliant", "test_luxian_0609_native_surgery_gate_execution.py", "test_025_actual_implant_field_contract_is_python_owned"),
    ("LX0609-029", "non_compliant", "test_luxian_0609_native_surgery_document_execution.py", "test_typed_029_blank_or_placeholder_summary_is_non_compliant_without_llm"),
    ("LX0609-030", "non_compliant", "test_luxian_0609_shadow_execution.py", "test_real_nonzero_030_order_trigger_target_empty_is_non_compliant"),
    ("LX0609-031", "non_compliant", "test_luxian_0609_native_surgery_gate_execution.py", "test_031_rejects_non_surgeon_signature"),
    ("LX0609-032", "non_compliant", "test_luxian_0609_native_execution.py", "test_native_032_formal_surgery_record_with_shell_safecheck_is_non_compliant"),
    ("LX0609-033", "non_compliant", "test_luxian_0609_native_surgery_gate_execution.py", "test_033_complete_readiness_with_empty_source_is_non_compliant_without_model"),
    ("LX0609-034", "non_compliant", "test_luxian_0609_native_surgery_document_execution.py", "test_typed_anesthesia_missing_documents_emit_controlled_customer_facts"),
    ("LX0609-035", "non_compliant", "test_luxian_0609_native_surgery_document_execution.py", "test_typed_035_incomplete_consent_is_non_compliant_with_exact_missing_fields"),
    ("LX0609-036", "non_compliant", "test_luxian_0609_native_surgery_document_execution.py", "test_typed_anesthesia_missing_documents_emit_controlled_customer_facts"),
    ("LX0609-037", "non_compliant", "test_luxian_0609_native_surgery_document_execution.py", "test_typed_037_incomplete_visits_report_exact_missing_fields"),
    ("LX0609-038", "non_compliant", "test_luxian_0609_native_surgery_document_execution.py", "test_typed_038_uses_independent_nonlocal_anesthesia_trigger_for_missing_record"),
    ("LX0609-039", "non_compliant", "test_luxian_0609_native_surgery_document_execution.py", "test_typed_039_is_non_compliant_when_known_surgeon_is_not_in_discussion"),
    ("LX0609-040", "non_compliant", "test_luxian_0609_native_mdt_execution.py", "test_missing_mdt_document_is_programmatic_non_compliant"),
    ("LX0609-050", "compliant", "test_luxian_0609_native_extended_document_execution.py", "test_050_uncertain_diagnosis_with_discussion_is_compliant"),
    ("LX0609-051", "non_compliant", "test_luxian_0609_native_extended_document_execution.py", "test_051_death_discussion_uses_seven_day_threshold"),
    ("LX0609-060", "non_compliant", "test_luxian_0609_native_extended_document_execution.py", "test_060_death_patient_without_death_record_is_non_compliant"),
    ("LX0609-061", "non_compliant", "test_luxian_0609_native_extended_document_execution.py", "test_061_discharge_record_uses_24_hour_threshold"),
    ("LX0609-062", "non_compliant", "test_luxian_0609_native_extended_document_execution.py", "test_062_incomplete_discharge_medication_is_non_compliant"),
    ("LX0609-063", "non_compliant", "test_luxian_0609_native_extended_document_execution.py", "test_063_mismatched_discharge_diagnoses_are_non_compliant"),
    ("LX0609-064", "non_compliant", "test_luxian_0609_native_extended_document_execution.py", "test_064_missing_postoperative_day_is_non_compliant"),
    ("LX0609-065", "non_compliant", "test_luxian_0609_native_extended_document_execution.py", "test_065_missing_postoperative_senior_round_is_non_compliant"),
    ("LX0609-066", "non_compliant", "test_luxian_0609_native_extended_document_execution.py", "test_066_missing_postoperative_first_course_is_non_compliant"),
    ("LX0609-067", "non_compliant", "test_luxian_0609_native_extended_document_execution.py", "test_067_missing_predischarge_course_is_non_compliant"),
    ("LX0609-068", "non_compliant", "test_luxian_0609_native_extended_document_execution.py", "test_068_missing_senior_discharge_opinion_exposes_checked_dates"),
    ("LX0609-070", "non_compliant", "test_luxian_0609_native_extended_document_execution.py", "test_070_rejects_nine_tests_reported_after_transfusion"),
)

_PRODUCTION_EXTENSION_FIXTURE_SPECS = (
    ("LX0609-076", "compliant", "test_076_runs_as_a_real_native_rule_and_never_uses_record_time"),
    ("LX0609-076", "non_compliant", "test_076_runs_as_a_real_native_rule_and_never_uses_record_time"),
    ("LX0609-076", "not_applicable", "test_076_does_not_duplicate_060_when_death_record_is_absent"),
    ("LX0609-076", "data_gap", "test_076_source_unavailable_is_data_gap"),
    ("LX0609-077", "compliant", "test_077_runs_one_controlled_semantic_call_on_the_formal_native_family"),
    ("LX0609-077", "non_compliant", "test_077_runs_one_controlled_semantic_call_on_the_formal_native_family"),
    ("LX0609-077", "data_gap", "test_077_missing_inputs_are_data_gap_without_calling_model"),
)

# 仅登记确有适用性门控的规则；fixture 断言客户结果必须写明排除事实，
# 不能使用“本次不适用”一类无依据的通用文案。
_NOT_APPLICABLE_FIXTURE_RULE_IDS = (
    "LX0609-003",
    "LX0609-007",
    "LX0609-008",
    "LX0609-009",
    "LX0609-011",
    "LX0609-012",
    "LX0609-013",
    "LX0609-014",
    "LX0609-015",
    "LX0609-019",
    "LX0609-027",
    "LX0609-029",
    "LX0609-030",
    "LX0609-031",
    "LX0609-032",
    "LX0609-033",
    "LX0609-034",
    "LX0609-036",
    "LX0609-037",
    "LX0609-038",
    "LX0609-039",
    "LX0609-040",
    "LX0609-041",
    "LX0609-042",
    "LX0609-043",
    "LX0609-044",
    "LX0609-045",
    "LX0609-046",
    "LX0609-047",
    "LX0609-048",
    "LX0609-051",
    "LX0609-058",
    "LX0609-060",
    "LX0609-063",
    "LX0609-070",
    "LX0609-072",
    "LX0609-073",
    "LX0609-076",
)


def _runtime_manifest() -> dict[str, Any]:
    return build_runtime_manifest(
        git_head="0" * 40,
        settings=get_settings(),
        rule_catalog=load_luxian_0609_rules(),
        generated_at="2026-08-02T00:00:00Z",
    )


def _stable_runtime_contract_hash(rules: Sequence[Mapping[str, Any]]) -> str:
    stable_fields = [
        {
            "rule_id": item["rule_id"],
            "family_key": item["family_key"],
            "executor_key": item["executor_key"],
            "decision_authority": item["decision_authority"],
            "max_llm_calls_per_rule": item["max_llm_calls_per_rule"],
            "phase_status": item["phase_status"],
            "definition_version": item["definition_version"],
        }
        for item in rules
    ]
    encoded = json.dumps(
        stable_fields, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _fixture_bindings() -> dict[str, list[dict[str, str]]]:
    bindings: dict[str, list[dict[str, str]]] = {}
    for binding in build_acceptance_fixture_bindings():
        bindings.setdefault(binding["rule_id"], []).append(binding)
    for rule_id, expected_status, filename, test_name in _NATIVE_FIXTURE_SPECS:
        bindings.setdefault(rule_id, []).append(
            {
                "rule_id": rule_id,
                "expected_status": expected_status,
                "fixture_ref": f"native-unit:tests/unit/{filename}::{test_name}",
            }
        )
    for rule_id, expected_status, test_name in _PRODUCTION_EXTENSION_FIXTURE_SPECS:
        bindings.setdefault(rule_id, []).append(
            {
                "rule_id": rule_id,
                "expected_status": expected_status,
                "fixture_ref": (
                    "native-integration:tests/integration/"
                    "test_luxian_0609_real_production_rules_076_077.py::"
                    f"{test_name}"
                ),
            }
        )
    for contract in load_luxian_0609_rule_contracts():
        if contract.phase_status == "pending_definition":
            continue
        bindings.setdefault(contract.rule_id, []).append(
            {
                "rule_id": contract.rule_id,
                "expected_status": "data_gap",
                "fixture_ref": (
                    "contract-unit:tests/unit/test_luxian_0609_customer_renderer.py::"
                    "test_each_defined_rule_data_gap_names_customer_visible_missing_material"
                    f"[{contract.rule_id}]"
                ),
            }
        )
    for rule_id in _NOT_APPLICABLE_FIXTURE_RULE_IDS:
        bindings.setdefault(rule_id, []).append(
            {
                "rule_id": rule_id,
                "expected_status": "not_applicable",
                "fixture_ref": (
                    "contract-unit:tests/unit/test_luxian_0609_customer_renderer.py::"
                    "test_each_gated_rule_not_applicable_names_the_excluding_fact"
                    f"[{rule_id}]"
                ),
            }
        )
    return bindings


def _validate_pytest_fixture_ref(fixture_ref: str) -> str | None:
    prefix = next(
        (
            candidate
            for candidate in (
                "native-unit:",
                "native-integration:",
                "contract-unit:",
            )
            if fixture_ref.startswith(candidate)
        ),
        "",
    )
    if not prefix:
        return None
    node_id = fixture_ref.removeprefix(prefix)
    relative_path, separator, test_name = node_id.partition("::")
    if not separator or not relative_path or not test_name:
        return f"invalid pytest fixture ref: {fixture_ref}"
    test_path = (BACKEND_ROOT / relative_path).resolve()
    try:
        test_path.relative_to(BACKEND_ROOT.resolve())
    except ValueError:
        return f"pytest fixture escapes backend root: {fixture_ref}"
    if not test_path.is_file():
        return f"pytest fixture file does not exist: {fixture_ref}"
    function_name = test_name.split("[", 1)[0]
    pattern = re.compile(rf"^(?:async\s+)?def\s+{re.escape(function_name)}\s*\(", re.MULTILINE)
    if not pattern.search(test_path.read_text(encoding="utf-8")):
        return f"pytest fixture test does not exist: {fixture_ref}"
    return None


def _slot(*, required: bool, phase_status: str) -> dict[str, Any]:
    if not required:
        return {"coverage": "not_required", "fixture_refs": []}
    coverage = "pending_definition" if phase_status == "pending_definition" else "missing"
    return {"coverage": coverage, "fixture_refs": []}


def build_acceptance_matrix(
    runtime_manifest: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """从 Runtime Manifest 生成骨架，再补充权威合同和 v3 fixture 绑定。"""

    manifest = dict(runtime_manifest or _runtime_manifest())
    runtime_rules = list(manifest.get("rules") or [])
    contracts = load_luxian_0609_rule_contracts()
    dependencies = load_luxian_0609_dependency_inventory()
    master = load_luxian_0609_rule_master()
    bindings = _fixture_bindings()
    contract_by_id = {item.rule_id: item for item in contracts}
    dependency_by_id = {item.rule_id: item for item in dependencies}
    master_by_id = {item.rule_id: item for item in master}

    rules: list[dict[str, Any]] = []
    for runtime_rule in runtime_rules:
        rule_id = str(runtime_rule["rule_id"])
        contract = contract_by_id[rule_id]
        dependency = dependency_by_id[rule_id]
        master_entry = master_by_id[rule_id]
        definition_status = "temporary" if rule_id in PROVISIONAL_RULE_IDS else "formal"
        has_applicability_gate = any(
            term in master_entry.qc_point for term in _APPLICABILITY_TERMS
        )
        cases = {
            "compliant": _slot(required=True, phase_status=contract.phase_status),
            "confirmed_issue": _slot(required=True, phase_status=contract.phase_status),
            "not_applicable": _slot(
                required=has_applicability_gate, phase_status=contract.phase_status
            ),
            "data_insufficient": _slot(required=True, phase_status=contract.phase_status),
        }
        rule_bindings = (
            [] if contract.phase_status == "pending_definition" else bindings.get(rule_id, [])
        )
        for binding in rule_bindings:
            slot_key = (
                "confirmed_issue"
                if binding["expected_status"] == "non_compliant"
                else (
                    "not_applicable"
                    if binding["expected_status"] == "not_applicable"
                    else "data_insufficient"
                    if binding["expected_status"] == "data_gap"
                    else "compliant"
                )
            )
            existing_refs = list(cases[slot_key].get("fixture_refs") or [])
            cases[slot_key] = {
                "coverage": "covered",
                "fixture_refs": list(dict.fromkeys([*existing_refs, binding["fixture_ref"]])),
                "expected_status": binding["expected_status"],
            }

        time_boundaries: dict[str, dict[str, Any]] | None = None
        if _TIME_LIMIT_PATTERN.search(master_entry.qc_point):
            time_boundaries = {
                boundary: _slot(required=True, phase_status=contract.phase_status)
                for boundary in ("before_threshold", "at_threshold", "after_threshold")
            }

        semantic_contract: dict[str, Any] | None = None
        if contract.decision_authority == "program_then_optional_llm":
            semantic_contract = {
                "minimal_input": {
                    "documents": list(contract.applicable_documents),
                    "facts": list(contract.data_dependencies),
                },
                "controlled_status_enum": list(ALLOWED_FINAL_STATES),
                "max_llm_calls_per_rule": contract.max_llm_calls_per_rule,
            }

        rule = {
            "rule_id": rule_id,
            "title": master_entry.title,
            "definition_status": definition_status,
            "definition_phase": contract.phase_status,
            "definition_version": contract.definition_version,
            "family_key": runtime_rule["family_key"],
            "cases": cases,
            "required_facts": list(dependency.data_dependencies),
            "required_evidence": list(dependency.applicable_documents),
            "expected_executor": runtime_rule["executor_key"],
            "decision_authority": runtime_rule["decision_authority"],
            "max_llm_calls_per_rule": runtime_rule["max_llm_calls_per_rule"],
        }
        if time_boundaries is not None:
            for binding in rule_bindings:
                boundary = binding.get("time_boundary")
                if boundary in time_boundaries:
                    existing_refs = list(
                        time_boundaries[boundary].get("fixture_refs") or []
                    )
                    time_boundaries[boundary] = {
                        "coverage": "covered",
                        "fixture_refs": list(
                            dict.fromkeys([*existing_refs, binding["fixture_ref"]])
                        ),
                    }
            rule["time_boundaries"] = time_boundaries
        if semantic_contract is not None:
            rule["semantic_contract"] = semantic_contract
        rules.append(rule)

    return {
        "schema_version": SCHEMA_VERSION,
        "rule_set_key": manifest["rule_set"]["key"],
        "rule_master_version": LUXIAN_0609_RULE_MASTER_VERSION,
        "generated_from": {
            "runtime_manifest_schema": RUNTIME_MANIFEST_SCHEMA_VERSION,
            "runtime_contract_hash": _stable_runtime_contract_hash(runtime_rules),
            "synthetic_fixture_set": "0426-derived-v3",
        },
        "coverage_semantics": {
            "covered": "已绑定受控fixture；不代表引擎执行已经通过",
            "missing": "规则定义明确，但尚无对应受控fixture",
            "not_required": "该规则没有此状态语义，不计入覆盖分母",
            "pending_definition": "当前规则定义合同尚未收口，fixture验收暂停",
        },
        "rules": rules,
    }


def validate_acceptance_matrix(
    payload: Mapping[str, Any],
    runtime_manifest: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    manifest = dict(runtime_manifest or _runtime_manifest())
    expected_rules = list(manifest.get("rules") or [])
    rules = list(payload.get("rules") or [])
    errors: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("matrix schema_version mismatch")
    expected_ids = [str(item["rule_id"]) for item in expected_rules]
    actual_ids = [str(item.get("rule_id") or "") for item in rules]
    if actual_ids != expected_ids:
        errors.append("matrix rule ids/order do not match Runtime Manifest")
    runtime_by_id = {str(item["rule_id"]): item for item in expected_rules}
    fixture_refs: list[str] = []
    slot_counts: Counter[str] = Counter()
    tier_counts: Counter[str] = Counter()
    boundary_counts: Counter[str] = Counter()

    for rule in rules:
        rule_id = str(rule.get("rule_id") or "")
        runtime_rule = runtime_by_id.get(rule_id)
        if runtime_rule is None:
            continue
        tier_counts[str(rule.get("definition_status") or "")] += 1
        for field in ("expected_executor", "decision_authority", "max_llm_calls_per_rule"):
            runtime_field = "executor_key" if field == "expected_executor" else field
            if rule.get(field) != runtime_rule.get(runtime_field):
                errors.append(f"{rule_id} {field} mismatch")
        if not rule.get("required_facts") or not rule.get("required_evidence"):
            errors.append(f"{rule_id} is missing fact/evidence contract")
        cases = rule.get("cases")
        if not isinstance(cases, Mapping) or tuple(cases) != SLOT_KEYS:
            errors.append(f"{rule_id} has invalid case slots")
            continue
        for slot_key, slot in cases.items():
            coverage = str(slot.get("coverage") or "") if isinstance(slot, Mapping) else ""
            refs = list(slot.get("fixture_refs") or []) if isinstance(slot, Mapping) else []
            if coverage not in COVERAGE_STATES:
                errors.append(f"{rule_id}/{slot_key} has invalid coverage")
            if coverage == "covered" and not refs:
                errors.append(f"{rule_id}/{slot_key} covered without fixture")
            if coverage != "covered" and refs:
                errors.append(f"{rule_id}/{slot_key} has fixture without coverage")
            slot_counts[coverage] += 1
            for fixture_ref in refs:
                fixture_error = _validate_pytest_fixture_ref(str(fixture_ref))
                if fixture_error:
                    errors.append(fixture_error)
            fixture_refs.extend(str(ref) for ref in refs)
        for boundary in (rule.get("time_boundaries") or {}).values():
            boundary_counts[str(boundary.get("coverage") or "")] += 1
        semantic = rule.get("semantic_contract")
        if runtime_rule["decision_authority"] == "program_then_optional_llm":
            if not isinstance(semantic, Mapping):
                errors.append(f"{rule_id} is missing semantic contract")
            elif semantic.get("max_llm_calls_per_rule") != runtime_rule["max_llm_calls_per_rule"]:
                errors.append(f"{rule_id} semantic LLM budget mismatch")
        elif semantic is not None:
            errors.append(f"{rule_id} program-only rule has semantic contract")

    expected_hash = _stable_runtime_contract_hash(expected_rules)
    observed_hash = (payload.get("generated_from") or {}).get("runtime_contract_hash")
    if observed_hash != expected_hash:
        errors.append("matrix runtime contract hash is stale")
    expected_tier_counts = Counter(
        "temporary" if rule_id in PROVISIONAL_RULE_IDS else "formal"
        for rule_id in expected_ids
    )
    if tier_counts != expected_tier_counts:
        errors.append("definition tier split does not match the current rule scope")
    if errors:
        raise ValueError("; ".join(errors))
    return {
        "rule_count": len(rules),
        "definition_tiers": dict(tier_counts),
        "case_slots": dict(slot_counts),
        "time_boundaries": dict(boundary_counts),
        "bound_fixture_count": len(fixture_refs),
        "semantic_rule_count": sum(
            bool(rule.get("semantic_contract")) for rule in rules
        ),
        "pending_definition_rule_count": sum(
            rule.get("definition_phase") == "pending_definition" for rule in rules
        ),
    }


def render_report(payload: Mapping[str, Any], summary: Mapping[str, Any]) -> str:
    rules = list(payload["rules"])
    coverage_labels = {
        "covered": "已覆盖",
        "missing": "待补案例",
        "pending_definition": "定义待确认",
        "not_required": "无需覆盖",
    }
    phase_labels = {
        "phase_1_target": "定义明确",
        "phase_1_partial": "部分定义明确",
        "pending_definition": "定义待确认",
    }
    lines = [
        "# LX0609 规则验收覆盖状态",
        "",
        "> 本报告衡量的是“规则 × 状态槽位”的受控 fixture 覆盖，不以病例数量代替覆盖率。",
        "> `covered` 仅表示 fixture 已绑定，不代表引擎执行已经通过；实际结果需在后续规则族验收中验证。",
        "",
        "## 当前结论",
        "",
        (
            f"- 规则总数：{summary['rule_count']}（正式 "
            f"{summary['definition_tiers'].get('formal', 0)}，临时 "
            f"{summary['definition_tiers'].get('temporary', 0)}）"
        ),
        f"- 已绑定受控 fixture：{summary['bound_fixture_count']} 个规则状态引用",
        f"- 语义规则：{summary['semantic_rule_count']} 条",
        f"- 当前定义合同仍为 Pending：{summary['pending_definition_rule_count']} 条",
        "- 当前只统计真实生成的 Golden 状态；未绑定槽位继续显示待补，不能据此宣称全部规则已经完整验收。",
        "",
        "## 状态槽位覆盖",
        "",
        "| 覆盖状态 | 数量 |",
        "| --- | ---: |",
    ]
    for key in ("covered", "missing", "pending_definition", "not_required"):
        lines.append(f"| {coverage_labels[key]} | {summary['case_slots'].get(key, 0)} |")
    lines.extend(
        [
            "",
            "## 时限边界覆盖",
            "",
            "| 覆盖状态 | 数量 |",
            "| --- | ---: |",
        ]
    )
    for key in ("covered", "missing", "pending_definition"):
        lines.append(
            f"| {coverage_labels[key]} | {summary['time_boundaries'].get(key, 0)} |"
        )

    for tier, title in (
        ("formal", f"正式 {summary['definition_tiers'].get('formal', 0)} 条"),
        ("temporary", f"临时 {summary['definition_tiers'].get('temporary', 0)} 条"),
    ):
        lines.extend(
            [
                "",
                f"## {title}",
                "",
                "| 规则与质控点 | 当前受控 fixture | 合规槽 | 问题槽 | 不适用槽 | 数据不足槽 | 定义阶段 |",
                "| --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for rule in rules:
            if rule["definition_status"] != tier:
                continue
            cases = rule["cases"]
            bound = next(
                (
                    refs[0]
                    for slot in cases.values()
                    if (refs := slot.get("fixture_refs") or [])
                ),
                "—",
            )
            lines.append(
                "| {rule_id} | {bound} | {compliant} | {issue} | {na} | {gap} | {phase} |".format(
                    rule_id=f"{rule['rule_id']} {rule['title']}",
                    bound=bound,
                    compliant=coverage_labels[cases["compliant"]["coverage"]],
                    issue=coverage_labels[cases["confirmed_issue"]["coverage"]],
                    na=coverage_labels[cases["not_applicable"]["coverage"]],
                    gap=coverage_labels[cases["data_insufficient"]["coverage"]],
                    phase=phase_labels[rule["definition_phase"]],
                )
            )
    lines.extend(
        [
            "",
            "## 使用方式",
            "",
            "```powershell",
            "python backend/scripts/run_luxian_0609_contract_acceptance.py",
            "python backend/scripts/run_luxian_0609_contract_acceptance.py --require-complete",
            "```",
            "",
            "默认命令验证矩阵与当前 Runtime Manifest 是否一致；`--require-complete` 用于后续发布门禁，当前存在真实覆盖缺口时会失败。",
            "",
        ]
    )
    return "\n".join(lines)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验 LX0609 当前生产规则验收矩阵")
    parser.add_argument("--write", action="store_true", help="按当前合同重建矩阵和报告")
    parser.add_argument("--require-complete", action="store_true", help="存在必需槽位缺口时返回失败")
    args = parser.parse_args(argv)
    if args.write:
        payload = build_acceptance_matrix()
        summary = validate_acceptance_matrix(payload)
        _write_json(MATRIX_PATH, payload)
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(render_report(payload, summary), encoding="utf-8", newline="\n")
    else:
        payload = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
        summary = validate_acceptance_matrix(payload)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.require_complete:
        incomplete = summary["case_slots"].get("missing", 0) + summary["case_slots"].get("pending_definition", 0)
        incomplete += summary["time_boundaries"].get("missing", 0) + summary["time_boundaries"].get("pending_definition", 0)
        if incomplete:
            print(f"acceptance matrix incomplete: {incomplete} required slots", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
