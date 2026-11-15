"""不适用审计回执经正式生成、服务投影、Worker装配、保存及读取的端到端回归。

1026 实际验收：Finalizer 已为不适用结果生成回执，但服务层
``_build_document_evaluation_result`` 与 Worker 结果装配均按固定字段白名单重建
结果，回执在保存前被剥离。本文件只用合成数据与隔离 SQLite，经同一正式链路
验证“生成→保存→读取”，不调用模型、不连接业务库。
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import update
from sqlalchemy.orm import Session

import app.services.custom_qc_workspace_service as workspace_module
from app.routers import qc_sichuan
from app.services.luxian_0609.applicability_receipt import SCHEMA_VERSION as RECEIPT_SCHEMA
from app.services.luxian_0609.decision_model import ApplicabilityState, EvidenceState, QcDirection, RuleDecision
from app.services.qc_workspace.canonical_result_store import CanonicalResultStore
from tests.unit.test_luxian_0609_formal_extension_chain import (
    TEST_RULE_ID,
    _run_test_only_rule_through_formal_chain,
)


def _not_applicable_decision(session: object, source_ref: str) -> RuleDecision:
    return RuleDecision(
        rule_id=TEST_RULE_ID,
        snapshot_hash=session.snapshot.snapshot_hash,
        applicability=ApplicabilityState.NOT_APPLICABLE,
        evidence_state=EvidenceState.SUFFICIENT,
        qc_direction=QcDirection.UNKNOWN,
        reason_code="trigger_absent_complete",
        fact_refs=(source_ref,),
        evaluator_version="extension-native-test-v1",
        confidence=1.0,
    )


def _assert_bound_receipt(item: dict, *, material: str) -> None:
    receipt = item.get("applicability_receipt")
    assert isinstance(receipt, dict), sorted(item)
    assert receipt["schema_version"] == RECEIPT_SCHEMA
    assert (receipt["rule_id"], receipt["status"], receipt["reason_code"]) == (
        TEST_RULE_ID, "not_applicable", "trigger_absent_complete",
    )
    assert receipt["material_fingerprint"] == material == item["case_material_fingerprint"]
    assert any(check["depended_on"] for check in receipt["source_checks"])


async def _run_not_applicable(monkeypatch, tmp_path, request) -> SimpleNamespace:
    chain = await _run_test_only_rule_through_formal_chain(
        monkeypatch, tmp_path, request, make_decision=_not_applicable_decision,
    )
    assert chain.job["status"] == "completed", chain.job.get("failed_records")
    assert len(chain.material_fingerprints) == 1
    return chain


@pytest.mark.asyncio
async def test_not_applicable_receipt_survives_service_worker_save_and_canonical_read(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, request: pytest.FixtureRequest,
) -> None:
    chain = await _run_not_applicable(monkeypatch, tmp_path, request)
    material = chain.material_fingerprints[0]

    # 1) 任务 items_json：Worker 装配后的持久结果。
    [saved] = chain.job["items"]
    assert saved["status"] == "not_applicable"
    _assert_bound_receipt(saved, material=material)

    # 2) Canonical Envelope：正式读取源。
    with Session(chain.engine) as db:
        loaded = CanonicalResultStore(chain.envelope_table).load_selected(
            db, root_job_id=chain.job_id, institute_id="I", patient_id="P", visit_id="V",
            rule_set_key=chain.filters["rule_set_key"], rule_set_version=chain.filters["rule_set_version"],
        )
    [enveloped] = loaded["items"]
    _assert_bound_receipt(enveloped, material=material)

    # 3) 客户 DTO：回执保留、标注已保留，不泄漏病例坐标。
    dto = workspace_module.project_customer_safe_result_item(
        enveloped, hmac_key=workspace_module.customer_safe_projection_key(),
    )
    assert dto["audit_evidence_status"] == "retained"
    assert dto["applicability_receipt"] == enveloped["applicability_receipt"]
    assert not {"patient_id", "visit_id", "institute_id"} & set(dto)

    # 4) 任务详情 HTTP 包络：结果在 data.items，顶层没有 items。
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: chain.workspace)
    response = await qc_sichuan.get_workspace_batch_job(
        request=SimpleNamespace(state=SimpleNamespace(trace_id="receipt-chain")),
        job_id=chain.job_id, current_user={"id": "tester"},
    )
    assert "items" not in response
    [api_item] = response["data"]["items"]
    assert api_item["audit_evidence_status"] == "retained"
    assert api_item["applicability_receipt"]["material_fingerprint"] == material


@pytest.mark.asyncio
async def test_partial_failed_task_reads_saved_items_with_receipts_through_controlled_contract(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, request: pytest.FixtureRequest,
) -> None:
    """同病例另一规则技术失败：任务详情只交付完整病例（0条），单病历读取交付已保存部分结果。"""

    chain = await _run_not_applicable(monkeypatch, tmp_path, request)
    material = chain.material_fingerprints[0]
    failed_rule = "LX0609-10-03-01"
    job = chain.job
    filters = {**job["filters"], "rule_ids": [TEST_RULE_ID, failed_rule]}
    filters["scoped_customer_rule_ids"] = [TEST_RULE_ID, failed_rule]
    filters["active_customer_rule_ids"] = [TEST_RULE_ID, failed_rule]
    if isinstance(filters.get("record_rule_map"), dict):
        filters["record_rule_map"] = {key: [TEST_RULE_ID, failed_rule] for key in filters["record_rule_map"]}
    failure = {
        "rule_id": failed_rule, "rule_code": failed_rule, "institute_id": "I", "patient_id": "P",
        "visit_id": "V", "record_id": "V", "error_phase": "result_status",
        "reason_code": "model_invalid_output", "retryable": False, "error": "model_invalid_output",
    }
    summary = {
        **job["summary"], "execution_status": "partial_failed",
        "failed_rule_ids": [failed_rule], "failed_rule_count": 1,
        "rule_results": [*job["summary"].get("rule_results", []), {"rule_id": failed_rule, "status": "failed"}],
    }
    # 合成“部分失败”终态：用正式完成入口写入，同一事务删除并按完整病例重建 Envelope。
    table = chain.workspace._batch_job_table
    with chain.engine.begin() as connection:
        connection.execute(update(table).where(table.c.id == chain.job_id).values(
            status="running", filters_json=json.dumps(filters, ensure_ascii=False),
            updated_at=datetime(2026, 9, 24, 13),
        ))
    chain.workspace.complete_batch_job(
        job_id=chain.job_id, summary={**summary, "success_count": 0, "failed_count": 1},
        items=job["items"], failed_records=[failure],
    )
    failed_job = chain.workspace.get_batch_job_for_processing(job_id=chain.job_id)
    assert failed_job["status"] == "failed"
    [saved] = failed_job["items"]
    _assert_bound_receipt(saved, material=material)

    # 任务详情：病例不完整、无 Envelope；按 job_id 只读本任务已保存成功项及回执。
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: chain.workspace)
    response = await qc_sichuan.get_workspace_batch_job(
        request=SimpleNamespace(state=SimpleNamespace(trace_id="receipt-partial")),
        job_id=chain.job_id, current_user={"id": "tester"},
    )
    [detail_item] = response["data"]["items"]
    assert detail_item["applicability_receipt"]["material_fingerprint"] == material
    assert response["data"]["summary"]["execution_status"] == "partial_failed"

    # 单病历读取：受控部分结果合同交付已保存成功项及回执，失败规则只暴露身份。
    record = chain.workspace.get_latest_luxian_0609_record_result(
        institute_id="I", patient_id="P", visit_id="V",
    )
    assert record["state"] == "ready", record
    assert record.get("execution_status") == "partial_failed"
    [partial] = record["items"]
    assert partial["status"] == "not_applicable"
    assert partial["audit_evidence_status"] == "retained"
    assert partial["applicability_receipt"]["material_fingerprint"] == material


def test_carry_rejects_receipt_whose_result_was_rewritten_after_generation() -> None:
    from app.services.history_evidence_audit import carry_retained_fields
    from tests.unit.test_history_audit_projection import _receipt_item

    source = _receipt_item()
    target = {"rule_id": source["rule_id"], "status": "compliant", "reason_code": "requirement_satisfied"}
    with pytest.raises(ValueError, match="applicability_receipt_result_mismatch"):
        carry_retained_fields(source, target)
    assert "applicability_receipt" not in target


def test_carry_never_fabricates_missing_receipt_and_history_reads_not_retained() -> None:
    from app.services.history_evidence_audit import carry_retained_fields, read_projection

    legacy = {"rule_id": TEST_RULE_ID, "status": "not_applicable", "reason_code": "trigger_absent_complete"}
    rebuilt = carry_retained_fields(legacy, dict(legacy))
    assert "applicability_receipt" not in rebuilt
    projected = read_projection(rebuilt)
    assert projected["audit_evidence_status"] == "not_retained"
    assert projected["audit_evidence_message"] == "本次不适用判定的审计依据当时未保留，原结论未改写。"


def test_not_applicable_rewritten_to_contract_failure_drops_receipt_and_isolates_one_rule() -> None:
    """复审发现：不适用结果事实合同失败改判技术错误后仍带回执，会使服务投影整例失败。"""
    from app.services.history_evidence_audit import carry_retained_fields
    from app.services.luxian_0609.canonical_result_finalizer import (
        finalize_luxian_0609_executor_customer_display_facts,
    )
    from tests.unit.test_history_audit_projection import _receipt_item

    na_result = _receipt_item()
    failed, handled = finalize_luxian_0609_executor_customer_display_facts(
        result=na_result, raw_facts=None, contract_failure=True,
    )
    assert handled is True
    assert (failed["status"], failed["reason_code"]) == ("technical_error", "model_invalid_output")
    assert "applicability_receipt" not in failed
    # 服务投影对该条只搬运材料指纹，不因回执不一致而抛出、不影响同病例其他规则。
    projected = carry_retained_fields(failed, {
        "rule_id": failed["rule_id"], "status": failed["status"], "reason_code": failed["reason_code"],
    })
    assert "applicability_receipt" not in projected
