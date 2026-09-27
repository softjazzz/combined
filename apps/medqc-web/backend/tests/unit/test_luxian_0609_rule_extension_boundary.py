from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import csv
import json
from app.services.qc_workspace.export_service import CUSTOMER_EXPORT_HEADERS
from app.services.qc_workspace.canonical_result_store import safe_criterion_results
from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import Session

import app.services.custom_qc_workspace_service as workspace_module
import app.services.luxian_0609_rule_catalog as catalog_module
from app.services.qc_workspace.canonical_result_store import (
    CanonicalResultStore, envelope_item_from_rule_result,
)
from typing import Any

import pytest

from app.services.luxian_0609 import customer_renderer, decision_binding
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.decision_model import (
    ApplicabilityState,
    CriterionResult,
    CriterionStatus,
    EvidenceState,
    QcDirection,
    RuleDecision,
)
from app.services.luxian_0609.engine import (
    FamilyExecutionContext,
    FamilyExecutionSuccess,
    Luxian0609ExecutionEngine,
)
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.execution_contract import FamilyExecutionEnvelope
from app.services.luxian_0609.executor_registry import (
    ExecutorRegistration,
    Luxian0609ExecutorRegistry,
)
from app.services.luxian_0609.rule_contracts import (
    ALLOWED_FINAL_STATES,
    Luxian0609RuleContract,
    RuleCriterionContract,
)
from app.services.luxian_0609_result_aggregator import (
    aggregate_luxian_0609_results,
)


_NATIVE_RULE_ID = "LX0609-99-99-01"
_SEMANTIC_RULE_ID = "LX0609-99-99-02"
_SOURCE_KEY = "admission_record"
_SEMANTIC_PROMPT = (
    "判断受控事实中的症状与诊断是否具有明确医学指向关系；"
    "只返回 satisfied、defect 或 unknown。"
)


def _contract(
    *, rule_id: str, executor_key: str, semantic: bool, criterion_kind: str = "semantic_relation"
) -> Luxian0609RuleContract:
    shape = {
        "semantic_relation": {"left_fact": "symptom", "right_fact": "diagnosis"},
        "consistency": {"left_fact": "symptom", "right_fact": "diagnosis", "operator": "eq"},
        "presence": {"source_fact": "document", "operator": "present", "unit": "boolean"},
        "timeliness": {"source_fact": "interval", "operator": "lte", "unit": "hour"},
        "coverage": {"source_fact": "recorded_days", "operator": "covers", "unit": "day"},
        "completeness": {"source_fact": "fields", "operator": "complete", "unit": "boolean"},
        "text_length": {"source_fact": "text", "operator": "lte", "unit": "character", "expected": 20},
    }[criterion_kind]
    criteria = (RuleCriterionContract(criterion_id="controlled_check", label="测试受控核查",
                kind=criterion_kind, failure_reason_code="requirement_violated", **shape),) if semantic else ()
    return Luxian0609RuleContract(
        rule_id=rule_id,
        contract_version="extension-boundary-test-v1",
        family_key=executor_key,
        executor_key=executor_key,
        execution_mode="controlled_semantic" if semantic else "native",
        decision_authority=(
            "program_then_optional_llm" if semantic else "program_only"
        ),
        max_llm_calls_per_rule=1 if semantic else 0,
        source_contract_state="typed_shadow_v1",
        allowed_final_states=ALLOWED_FINAL_STATES,
        result_contract_version="lx0609-result-v1",
        privacy_contract_version="lx0609-privacy-v1",
        golden_gate_state="pending",
        applicable_documents=("入院记录",),
        data_dependencies=(_SOURCE_KEY,),
        rule_version="extension-boundary-test-v1",
        prompt_version="extension-boundary-test-v1",
        phase_status="phase_1_target",
        definition_version="extension-boundary-test-v1",
        criteria=criteria,
    )


def _session():
    rows = (
        {
            "document_id": "ADM-EXT-1",
            "document_title": "入院记录",
            "record_time": "2026-09-04 08:30:00",
            "chief_complaint": "受控症状摘要",
        },
    )

    def read_rows(**kwargs):
        source_key = kwargs["source_key"]
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows if source_key == _SOURCE_KEY else (),
            truncated=False,
            limit_rows=10,
        )

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-01-01-01",),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-09-04T09:00:00+08:00",
        evaluation_as_of_date="2026-09-04",
        row_reader=read_rows,
        additional_source_keys=(_SOURCE_KEY,),
    )


def _source_ref(context: FamilyExecutionContext) -> str:
    observation = next(
        item for item in context.snapshot.observations if item.source_key == _SOURCE_KEY
    )
    return observation.snapshot_ref.removeprefix("sha256:")


@dataclass
class _NativeExtensionExecutor:
    async def evaluate(
        self, context: FamilyExecutionContext
    ) -> FamilyExecutionEnvelope:
        decision = RuleDecision(
            rule_id=_NATIVE_RULE_ID,
            snapshot_hash=context.snapshot.snapshot_hash,
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.SUFFICIENT,
            qc_direction=QcDirection.SATISFIED,
            reason_code="requirement_satisfied",
            fact_refs=(_source_ref(context),),
            evaluator_version="extension-native-test-v1",
            confidence=1.0,
        )
        return FamilyExecutionEnvelope(
            results=(),
            planned_rule_ids=context.selected_rule_ids,
            decisions=(decision,),
        )


@dataclass
class _ControlledSemanticStub:
    calls: list[str] = field(default_factory=list)

    async def classify(self, prompt: str) -> dict[str, Any]:
        self.calls.append(prompt)
        return {
            "state": "defect",
            "prompt_tokens": 12,
            "completion_tokens": 3,
        }


@dataclass
class _SemanticExtensionExecutor:
    model: _ControlledSemanticStub

    async def evaluate(
        self, context: FamilyExecutionContext
    ) -> FamilyExecutionEnvelope:
        output = await self.model.classify(_SEMANTIC_PROMPT)
        direction = {
            "satisfied": QcDirection.SATISFIED,
            "defect": QcDirection.DEFECT,
            "unknown": QcDirection.UNKNOWN,
        }[output["state"]]
        decision = RuleDecision(
            rule_id=_SEMANTIC_RULE_ID,
            snapshot_hash=context.snapshot.snapshot_hash,
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.SUFFICIENT,
            qc_direction=direction,
            reason_code=(
                "requirement_violated"
                if direction is QcDirection.DEFECT
                else "requirement_satisfied"
            ),
            fact_refs=(_source_ref(context),),
            evaluator_version="extension-semantic-test-v1",
            criterion_results=(CriterionResult(criterion_id="controlled_check", status=CriterionStatus.FAILED,
                               reason_code="requirement_violated", fact_refs=(_source_ref(context),)),),
            confidence=1.0,
        )
        return FamilyExecutionEnvelope(
            results=(),
            planned_rule_ids=context.selected_rule_ids,
            decisions=(decision,),
            llm_call_count=1,
            prompt_tokens=output["prompt_tokens"],
            completion_tokens=output["completion_tokens"],
            total_tokens=output["prompt_tokens"] + output["completion_tokens"],
            api_time=0.01,
        )


def test_unknown_criterion_kind_is_not_deliverable():
    assert safe_criterion_results({"criterion_results": [{
        "criterion_id": "controlled_check", "kind": "unknown_kind",
        "status": "failed", "reason_code": "requirement_violated",
    }]}) == []


def test_rule_decision_format_allows_future_ids_but_rejects_zero():
    snapshot = _session().snapshot

    with pytest.raises(ValueError, match="invalid rule_id"):
        RuleDecision(
            rule_id="LX0609-000",
            snapshot_hash=snapshot.snapshot_hash,
            applicability=ApplicabilityState.ERROR,
            evidence_state=EvidenceState.TECHNICAL_ERROR,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="decision_contract_violation",
            fact_refs=(),
            evaluator_version="extension-contract-test-v1",
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("criterion_kind", ["text_length", "semantic_relation", "completeness", "presence", "timeliness", "coverage", "consistency"])
async def test_two_test_only_rule_contracts_cross_existing_extension_boundary(
    monkeypatch, criterion_kind,
):
    session = _session()
    semantic_stub = _ControlledSemanticStub()
    contracts = (
        _contract(
            rule_id=_NATIVE_RULE_ID,
            executor_key="extension_native_test",
            semantic=False,
        ),
        _contract(
            rule_id=_SEMANTIC_RULE_ID,
            executor_key="extension_semantic_test",
            semantic=True, criterion_kind=criterion_kind,
        ),
    )
    registry = Luxian0609ExecutorRegistry(
        (
            ExecutorRegistration(
                executor_key="extension_native_test",
                executor=_NativeExtensionExecutor(),
            ),
            ExecutorRegistration(
                executor_key="extension_semantic_test",
                executor=_SemanticExtensionExecutor(semantic_stub),
            ),
        )
    )

    report = await Luxian0609ExecutionEngine(registry=registry).execute(
        executor_batches=(
            ("extension_native_test", (_NATIVE_RULE_ID,)),
            ("extension_semantic_test", (_SEMANTIC_RULE_ID,)),
        ),
        snapshot=session.snapshot,
        contracts=contracts,
        default_deadline_seconds=1.0,
        max_concurrency=2,
    )

    assert all(isinstance(item, FamilyExecutionSuccess) for item in report.outcomes)
    assert semantic_stub.calls == [_SEMANTIC_PROMPT]
    assert [item.envelope.llm_call_count for item in report.outcomes] == [0, 1]
    assert [item.envelope.total_tokens for item in report.outcomes] == [0, 15]

    decisions = tuple(
        decision
        for outcome in report.outcomes
        for decision in outcome.envelope.decisions
    )
    monkeypatch.setattr(
        decision_binding,
        "_allowed_source_keys",
        lambda _rule_id: frozenset({_SOURCE_KEY}),
    )
    monkeypatch.setattr(
        decision_binding,
        "resolve_luxian_0609_rule_sources",
        lambda rule_ids: {rule_id: () for rule_id in rule_ids},
    )
    monkeypatch.setattr(
        decision_binding,
        "load_luxian_0609_rule_contracts",
        lambda: contracts,
    )
    rule_names = {
        _NATIVE_RULE_ID: "测试专用确定性规则",
        _SEMANTIC_RULE_ID: "测试专用受控语义规则",
    }
    monkeypatch.setattr(
        customer_renderer,
        "get_luxian_0609_rule",
        lambda rule_id: {
            "rule_id": rule_id,
            "name": rule_names[rule_id],
            "rule_version": "extension-boundary-test-v1",
        },
    )
    monkeypatch.setattr(
        customer_renderer,
        "load_luxian_0609_rule_contracts",
        lambda: contracts,
    )
    existing_catalog = catalog_module.load_luxian_0609_rules()
    monkeypatch.setattr(catalog_module, "load_luxian_0609_rules", lambda: [
        *existing_catalog, *[{"rule_id": rule_id, "name": name, "rule_version": "extension-boundary-test-v1"}
                            for rule_id, name in rule_names.items()],
    ])
    monkeypatch.setattr(workspace_module, "load_luxian_0609_rules", catalog_module.load_luxian_0609_rules)
    # 生产中目录必须等于总表 active 集合；测试规则进入目录的同时也须登记总表，
    # 历史结果身份校验以总表为准。
    from app.services import luxian_0609_rule_master as master_module
    from app.services.qc_workspace import canonical_result_store as store_module

    existing_master = master_module.load_luxian_0609_rule_master()
    extended_master = (*existing_master, *(
        master_module.Luxian0609RuleMasterEntry(
            rule_id=rule_id, source_document="测试专用文书", qc_point=name,
            implementation_status="active", policy_sources=("customer_confirmed",),
            policy_summary="测试专用扩展边界规则",
        )
        for rule_id, name in rule_names.items()
    ))
    for module in (workspace_module, store_module):
        monkeypatch.setattr(module, "load_luxian_0609_rule_master", lambda: extended_master)
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=decisions,
        expected_rule_ids=(_NATIVE_RULE_ID, _SEMANTIC_RULE_ID),
        snapshot=session.snapshot,
    )
    results = aggregate_luxian_0609_results(
        wrapper_rules=[
            {"rule_id": _NATIVE_RULE_ID, "rule_name": "测试专用确定性规则"},
            {"rule_id": _SEMANTIC_RULE_ID, "rule_name": "测试专用受控语义规则"},
        ],
        execution_results=[],
        reduced_decisions=reduced,
        customer_display_facts=(),
        format_evidence=False,
        audit_context={
            "evidence_snapshot": session.snapshot,
            "evidence_materials": session.materials,
        },
    )

    assert [(item["status"], item["reason_code"]) for item in results] == [
        ("compliant", "requirement_satisfied"),
        ("non_compliant", "requirement_violated"),
    ]
    assert [
        [
            (
                evidence.get("source_type"),
                evidence.get("source_document_id"),
                evidence.get("field_path"),
                evidence.get("record_time"),
            )
            for evidence in item.get("customer_evidence") or []
        ]
        for item in results
    ] == [
        [(_SOURCE_KEY, "ADM-EXT-1", "chief_complaint", "2026-09-04 08:30:00")],
        [(_SOURCE_KEY, "ADM-EXT-1", "chief_complaint", "2026-09-04 08:30:00")],
    ]


    # 延长真实交付链：新规则只在测试目录/执行器声明，不为保存或DTO增加规则分支。
    table = workspace_module._record_result_envelopes_table().to_metadata(MetaData(), schema=None)
    engine = create_engine("sqlite://")
    table.metadata.create_all(engine)
    store = CanonicalResultStore(table)
    source_items = [{**item, "institute_id": "I", "patient_id": "P", "visit_id": "V", "record_id": "V"}
                    for item in results]
    filters = {"rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "extension-boundary-test-v1"}
    try:
        with Session(engine) as db:
            store.replace_for_job(
                db, job_row={"id": "EXT-JOB", "created_by": "reviewer", "filters_json": json.dumps(filters)},
                items=source_items, now=datetime(2026, 9, 24, 12),
                projector=lambda raw: envelope_item_from_rule_result(raw, hmac_key="extension-test-key"),
                projection_key="extension-test-key",
            )
            db.commit()
            loaded = store.load_selected(
                db, root_job_id="EXT-JOB", institute_id="I", patient_id="P", visit_id="V", **filters,
            )
        public_items = loaded["items"]
        assert [(item["rule_id"], item["status"], item["reason_code"]) for item in public_items] == [
            (item["rule_id"], item["status"], item["reason_code"]) for item in results
        ]
        assert public_items[1]["criterion_results"] == results[1]["criterion_results"]
        for item in public_items:
            dto = workspace_module.project_customer_safe_result_item(item, hmac_key="extension-test-key")
            assert dto["rule_id"] == item["rule_id"]
            assert dto["status"] == item["status"]
            assert dto["reason_code"] == item["reason_code"]
            assert len(dto["evidence"]) == 1
            assert dto["evidence"][0]["source_type"] == _SOURCE_KEY
            assert dto["evidence"][0]["field_path"] == "chief_complaint"
            # 公开 DTO 省略空字符串字段，已发布的非空判定内容不得丢失。
            expected_criteria = [
                {key: value for key, value in criterion.items() if value != ""}
                for criterion in item.get("criterion_results", [])
            ]
            assert dto.get("criterion_results", []) == expected_criteria
        exported = workspace_module._export_customer_safe_csv(
            {"id": "EXT-JOB", "filters": filters, "items": public_items}, hmac_key="extension-test-key",
        )
        csv_rows = list(csv.reader(exported.getvalue().lstrip("\ufeff").splitlines()))
        header_index = csv_rows.index(CUSTOMER_EXPORT_HEADERS)
        rows = [dict(zip(CUSTOMER_EXPORT_HEADERS, row)) for row in csv_rows[header_index + 1:]]
        assert [row["质控点编码"] for row in rows] == [_NATIVE_RULE_ID, _SEMANTIC_RULE_ID]
        assert [row["原因码"] for row in rows] == ["requirement_satisfied", "requirement_violated"]
        assert [row["判定结果"] for row in rows] == ["合规", "不合规"]
        assert semantic_stub.calls == [_SEMANTIC_PROMPT]
    finally:
        engine.dispose()
