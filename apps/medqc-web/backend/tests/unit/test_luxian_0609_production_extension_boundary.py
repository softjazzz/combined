"""LX0609 生产规则扩展的现状门禁与既有主链回归。

076/077 已作为真实生产规则进入目录。本文件继续用下一顺位 078/079 验证
master 声明式扩容边界，并固定既有发布规则的真实链路。
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.luxian_0609 import execution as execution_module
from app.services.luxian_0609.customer_rule_package import LUXIAN_0609_RULE_SET_KEY
from app.services.luxian_0609.evidence_material import Luxian0609EvidenceReadSession
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.execution import (
    aggregate_luxian_0609_orchestrated_results,
    prepare_luxian_0609_execution,
)
from app.services.luxian_0609 import phase_scope as phase_scope_module
from app.services import luxian_0609_rule_catalog as rule_catalog_module
from app.services.qc_workspace.canonical_result_store import envelope_item_from_rule_result
from app.services import luxian_0609_rule_master as rule_master_module


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_production_master_loader_accepts_declarative_078_079_extension(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """最外层 master 声明扩容后，不存在固定规则数量阻断。"""

    payload = json.loads(rule_master_module._MASTER_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload["rules"], list)
    for rule_id in ("LX0609-078", "LX0609-079"):
        copied = dict(payload["rules"][-1])
        copied["rule_id"] = rule_id
        payload["rules"].append(copied)
    extension_path = tmp_path / "rule-master-with-078-079.json"
    _write_json(extension_path, payload)

    monkeypatch.setattr(rule_master_module, "_MASTER_PATH", extension_path)
    rule_master_module.load_luxian_0609_rule_master.cache_clear()
    try:
        entries = rule_master_module.load_luxian_0609_rule_master()
    finally:
        rule_master_module.load_luxian_0609_rule_master.cache_clear()

    assert tuple(entry.rule_id for entry in entries[-2:]) == (
        "LX0609-078",
        "LX0609-079",
    )


def test_production_phase_loader_accepts_master_declared_078_079_extension(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """phase 只从 master 投影，不再维护第二份固定规则数量。"""

    master_payload = json.loads(
        rule_master_module._MASTER_PATH.read_text(encoding="utf-8")
    )
    assert isinstance(master_payload["rules"], list)
    for rule_id in ("LX0609-078", "LX0609-079"):
        master_entry = dict(master_payload["rules"][-1])
        master_entry["rule_id"] = rule_id
        master_payload["rules"].append(master_entry)
    master_extension_path = tmp_path / "rule-master-with-078-079.json"
    _write_json(master_extension_path, master_payload)

    monkeypatch.setattr(rule_master_module, "_MASTER_PATH", master_extension_path)
    rule_master_module.load_luxian_0609_rule_master.cache_clear()
    phase_scope_module.load_luxian_0609_phase_scope.cache_clear()
    try:
        entries = phase_scope_module.load_luxian_0609_phase_scope()
    finally:
        rule_master_module.load_luxian_0609_rule_master.cache_clear()
        phase_scope_module.load_luxian_0609_phase_scope.cache_clear()

    assert tuple(entry.rule_id for entry in entries[-2:]) == (
        "LX0609-078",
        "LX0609-079",
    )


def test_incomplete_wrapper_catalog_fails_closed_after_master_and_phase_accept_078(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """目录扩容不等于规则可执行；缺少 wrapper 时不得进入执行目录。"""

    master_payload = json.loads(
        rule_master_module._MASTER_PATH.read_text(encoding="utf-8")
    )
    assert isinstance(master_payload["rules"], list)
    master_payload["rules"].append(
        {**master_payload["rules"][-1], "rule_id": "LX0609-078"}
    )
    master_extension_path = tmp_path / "rule-master-with-078.json"
    _write_json(master_extension_path, master_payload)

    monkeypatch.setattr(rule_master_module, "_MASTER_PATH", master_extension_path)
    rule_master_module.load_luxian_0609_rule_master.cache_clear()
    phase_scope_module.load_luxian_0609_phase_scope.cache_clear()
    rule_catalog_module.load_luxian_0609_rules.cache_clear()
    try:
        assert tuple(
            entry.rule_id
            for entry in rule_master_module.load_luxian_0609_rule_master()
        )[-1] == "LX0609-078"
        assert (
            phase_scope_module.load_luxian_0609_phase_scope()[-1].rule_id
            == "LX0609-078"
        )
        with pytest.raises(ValueError, match="execution catalog drifted"):
            rule_catalog_module.load_luxian_0609_rules()
    finally:
        rule_master_module.load_luxian_0609_rule_master.cache_clear()
        phase_scope_module.load_luxian_0609_phase_scope.cache_clear()
        rule_catalog_module.load_luxian_0609_rules.cache_clear()


def _production_evidence_session() -> Luxian0609EvidenceReadSession:
    rows_by_source = {
        "inpat_registration": [
            {"admission_datetime": "2026-07-15 13:48:49"},
        ],
        "admission_record": [
            {
                "document_id": "admission-001",
                "document_title": "入院记录",
                "record_time": "2026-07-15 14:30:00",
                "record_content": "患者因腹痛入院，已完成病史采集与诊疗计划。",
            },
        ],
        "daily_course_record": [],
        "senior_course_record": [
            {
                "document_id": "upper-round-006",
                "document_title": "上级医师查房记录",
                "record_time": "2026-07-16 10:30:02",
                "record_content": "今日彭中主任医师联合神经疾病相关专业医师查房。",
            },
        ],
    }

    def read_rows(**kwargs: object) -> SnapshotSourceRows:
        source_key = str(kwargs["source_key"])
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows_by_source.get(source_key, []),
            truncated=False,
            limit_rows=50,
        )

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-001", "LX0609-006"),
        institute_id="extension-test-institute",
        patient_id="extension-test-patient",
        visit_id="extension-test-visit",
        source_schema=None,
        created_at="2026-07-20T12:00:00+08:00",
        evaluation_as_of_date="2026-07-20",
        row_reader=read_rows,
        additional_source_keys=(
            "admission_record",
            "daily_course_record",
            "inpat_registration",
            "senior_course_record",
        ),
    )


class _ControlledSemanticClient:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def generate(self, prompt: str, **_kwargs: object) -> dict[str, object]:
        self.prompts.append(prompt)
        return {
            "content": (
                '{"schema_version":"lx0609-006-round-role-v1",'
                '"documents":[{"position":1,"role":"senior",'
                '"physician_name":"彭中","physician_title":"主任医师",'
                '"evidence_quote":"今日彭中主任医师联合神经疾病"}]}'
            ),
            "usage": {
                "prompt_tokens": 40,
                "completion_tokens": 12,
                "total_tokens": 52,
            },
            "response_time": 0.2,
        }


def _production_settings() -> SimpleNamespace:
    return SimpleNamespace(
        LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED=True,
        LUXIAN_0609_TRIGGER_GATE_ENABLED=False,
        LUXIAN_0609_LLM_TRIGGER_GATE_ENABLED=False,
        LUXIAN_0609_EVIDENCE_FORMATTER_ENABLED=False,
        LUXIAN_0609_NATIVE_EXECUTION_ENABLED=True,
        LUXIAN_0609_NATIVE_BASIC_TIMELINESS_ENABLED=True,
        LUXIAN_0609_NATIVE_CONSULTATION_ENABLED=True,
        LUXIAN_0609_NATIVE_EXAM_LAB_ENABLED=True,
        LUXIAN_0609_NATIVE_TRANSFUSION_ENABLED=True,
        LUXIAN_0609_NATIVE_TUMOR_PATHOLOGY_ENABLED=True,
        LUXIAN_0609_NATIVE_COURSE_QUALITY_ENABLED=True,
        LUXIAN_0609_NATIVE_SURGERY_GATE_ENABLED=True,
        LUXIAN_0609_NATIVE_SURGERY_DOCUMENT_ENABLED=True,
        LUXIAN_0609_NATIVE_MDT_040_ENABLED=True,
        LUXIAN_0609_NATIVE_EXTENDED_DOCUMENT_ENABLED=True,
        LUXIAN_0609_EVIDENCE_SNAPSHOT_SIDECAR_ENABLED=True,
        LUXIAN_0609_UNIFIED_ENGINE_ENABLED=True,
        LUXIAN_0609_RULE_DECISION_BASIC_TIMELINESS_ENABLED=True,
    )


async def _run_production_selection(
    monkeypatch: pytest.MonkeyPatch,
    selected_rule_ids: tuple[str, ...],
) -> tuple[object, list[dict[str, object]], _ControlledSemanticClient]:
    session = _production_evidence_session()
    client = _ControlledSemanticClient()

    def build_session(**kwargs: object) -> Luxian0609EvidenceReadSession:
        assert tuple(kwargs["selected_rule_ids"]) == selected_rule_ids
        return session

    # 这是受控病例资料注入；不替换规则/计划/Binding/renderer 的生产 loader。
    monkeypatch.setattr(
        execution_module,
        "build_luxian_0609_evidence_read_session",
        build_session,
    )
    executable, context = await prepare_luxian_0609_execution(
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        prepared_rules=[],
        visit_id="extension-test-visit",
        medical_text="",
        evidence_payload=None,
        llm_client=client,
        settings=_production_settings(),
        institute_id="extension-test-institute",
        patient_id="extension-test-patient",
        selected_customer_rule_ids=selected_rule_ids,
        evaluation_as_of_date="2026-07-20",
    )
    assert executable == []

    orchestrated = {
        "results": [],
        "total_tokens": 0,
        "total_prompt_tokens": 0,
        "total_completion_tokens": 0,
    }
    aggregate_luxian_0609_orchestrated_results(
        orchestrated=orchestrated,
        context=context,
        visit_id="extension-test-visit",
        model_name="controlled-semantic-test",
        evidence_payload=None,
    )
    return context, list(orchestrated["results"]), client


def _normalized_canonical_item(result: dict[str, object]) -> dict[str, object]:
    """忽略签名 source_ref，仅比较 Canonical 可见的稳定语义与定位。"""

    envelope = envelope_item_from_rule_result(result)
    return {
        "rule_id": envelope["rule_id"],
        "status": envelope["status"],
        "result_status": envelope["result_status"],
        "is_compliant": envelope["is_compliant"],
        "reason_code": envelope["reason_code"],
        "customer_display_facts": envelope.get("customer_display_facts"),
        "evidence": [
            {
                "source_type": item["source_type"],
                "record_time": item["record_time"],
                "field_path": item["field_path"],
            }
            for item in envelope.get("evidence", [])
        ],
    }


@pytest.mark.asyncio
async def test_existing_native_and_semantic_rules_use_production_plan_binding_and_renderer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """001/006 经真实 loader、plan、prepare、engine、Binding 和 renderer。"""

    context, results, client = await _run_production_selection(
        monkeypatch,
        ("LX0609-001", "LX0609-006"),
    )
    assert context.package_plan is not None
    assert context.package_plan.native_executor_batches == (
        ("basic_timeliness", ("LX0609-001", "LX0609-006")),
    )
    assert context.package_plan.compatibility_rule_ids == ()
    assert context.package_plan.compatibility_execution_rule_ids == ()
    assert context.legacy_wrapper_rules == []
    assert context.native_results == []
    assert [
        item.to_safe_dict() for item in context.native_usage_attributions
    ] == [
        {
            "executor_key": "basic_timeliness",
            "llm_call_count": 1,
            "prompt_tokens": 40,
            "completion_tokens": 12,
            "total_tokens": 52,
            "covered_customer_rule_ids": ["LX0609-001", "LX0609-006"],
            "latency_ms": 200.0,
        }
    ]
    assert [item.rule_id for item in context.reduced_decisions] == [
        "LX0609-001",
        "LX0609-006",
    ]
    assert [item.final_state.value for item in context.reduced_decisions] == [
        "compliant",
        "compliant",
    ]
    assert all(item.fact_refs for item in context.reduced_decisions)
    assert len(client.prompts) == 1
    assert context.native_llm_call_count == 1
    assert context.native_total_tokens == 52
    assert [item["rule_id"] for item in results] == [
        "LX0609-001",
        "LX0609-006",
    ]
    assert [item["status"] for item in results] == [
        "compliant",
        "compliant",
    ]
    assert all(item["reason_code"] == "requirement_within_threshold" for item in results)
    assert [
        (
            evidence["source_type"],
            evidence["source_document_id"],
            evidence["field_path"],
            evidence["record_time"],
        )
        for item in results
        for evidence in item["customer_evidence"]
    ] == [
        ("admission_record", "admission-001", "record_content", "2026-07-15 14:30:00"),
        ("senior_course_record", "upper-round-006", "record_content", "2026-07-16 10:30:02"),
    ]


@pytest.mark.asyncio
async def test_single_rule_and_combined_selection_keep_canonical_and_semantic_input_stable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """组合计划只合并 batch，不能改变任一规则的交付或 006 的受控输入。"""

    context_001, results_001, client_001 = await _run_production_selection(
        monkeypatch,
        ("LX0609-001",),
    )
    context_006, results_006, client_006 = await _run_production_selection(
        monkeypatch,
        ("LX0609-006",),
    )
    context_both, results_both, client_both = await _run_production_selection(
        monkeypatch,
        ("LX0609-001", "LX0609-006"),
    )

    assert [
        item.to_safe_dict()["executor_key"]
        for context in (context_001, context_006, context_both)
        for item in context.native_usage_attributions
    ] == ["basic_timeliness", "basic_timeliness", "basic_timeliness"]
    assert client_001.prompts == []
    assert client_006.prompts == client_both.prompts
    assert len(client_006.prompts) == 1
    assert context_001.native_llm_call_count == 0
    assert context_001.native_prompt_tokens == 0
    assert context_006.native_llm_call_count == context_both.native_llm_call_count == 1
    assert context_006.native_prompt_tokens == context_both.native_prompt_tokens == 40
    assert context_006.native_total_tokens == context_both.native_total_tokens == 52

    canonical_001 = _normalized_canonical_item(results_001[0])
    canonical_006 = _normalized_canonical_item(results_006[0])
    canonical_both = {
        item["rule_id"]: _normalized_canonical_item(item) for item in results_both
    }
    assert canonical_both == {
        "LX0609-001": canonical_001,
        "LX0609-006": canonical_006,
    }
