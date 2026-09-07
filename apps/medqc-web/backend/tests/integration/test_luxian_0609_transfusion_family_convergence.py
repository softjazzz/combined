"""阶段 1-C 本地三入口草案：输血 041–049 必须走正式 unified 主链。

本文件复用 exam/lab 已验证的隔离 SQLite 安装器，以及 consultation 的 API
挂载、worker 等待和 Canonical 回读辅助件；它们是入口基础设施，不复用任何
检查检验资料夹具或判定逻辑。输血资料、受控语义响应和断言均在本文件定义。

固定夹具是脱敏合成资料，不是客户真实病例。测试不访问 .env、PostgreSQL 或
真实模型，但保留正式路由、detached worker、prepare、统一引擎、transfusion
executor、Binding、保存和 Canonical API 回读。
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database.models.cdm import InpatRegistration
from app.routers import qc_sample_pools, qc_sichuan
from app.services import custom_qc_sample_pool_service as sample_pool_module
from app.services import custom_qc_workspace_service as workspace_module
from app.services import sichuan_qc_service
from app.services import sichuan_workspace_batch_worker as batch_worker
from app.services.custom_qc_sample_pool_service import CustomQCSamplePoolService
from app.services.luxian_0609 import execution as luxian_execution
from app.services.luxian_0609.evidence_snapshot_provider import SnapshotSourceRows
from app.services.luxian_0609.native_transfusion_execution import (
    EXECUTOR_KEY,
    TRANSFUSION_RULE_IDS,
    execute_luxian_0609_native_transfusion_rules,
)
from app.services.luxian_0609_rule_catalog import LUXIAN_0609_RULE_SET_KEY
from tests.integration.test_luxian_0609_consultation_api_entry_flow import (
    _api_app,
    _envelope_customer_projection,
    _install_sample_pool_sqlite,
    _read_saved_envelope,
    _wait_for_terminal_job,
)
from tests.integration.test_luxian_0609_exam_lab_family_convergence import (
    _install_isolated_sqlite,
)


RULE_SET_VERSION = "2026-06-09"
RULE_IDS_041_048 = tuple(rule_id for rule_id in TRANSFUSION_RULE_IDS if rule_id != "LX0609-049")
# 041/042 在当前客户运行策略中明确排除；不能在隔离测试中改常量伪造客户入口。
CUSTOMER_ENTRY_RULE_IDS = tuple(rule_id for rule_id in RULE_IDS_041_048 if rule_id not in {"LX0609-041", "LX0609-042"})
_RECORD_A = {"institute_id": "TX-HOSPITAL", "patient_id": "TX-PATIENT-A", "visit_id": "TX-VISIT-A"}
_RECORD_B = {"institute_id": "TX-HOSPITAL", "patient_id": "TX-PATIENT-B", "visit_id": "TX-VISIT-B"}


def _formal_settings() -> SimpleNamespace:
    return SimpleNamespace(
        LUXIAN_0609_MAINLINE_RULE_DECISION_ENABLED=True,
        LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED=True,
        LUXIAN_0609_NATIVE_EXECUTION_ENABLED=True,
        LUXIAN_0609_NATIVE_TRANSFUSION_ENABLED=True,
        LUXIAN_0609_UNIFIED_ENGINE_ENABLED=True,
        LUXIAN_0609_RULE_DECISION_TRANSFUSION_ENABLED=True,
        LUXIAN_0609_TRIGGER_GATE_ENABLED=False,
        LUXIAN_0609_LLM_TRIGGER_GATE_ENABLED=False,
        LUXIAN_0609_EVIDENCE_FORMATTER_ENABLED=False,
        LUXIAN_0609_RUNTIME_SHADOW_ENABLED=False,
    )


class _ActivationStub:
    def enforce(self) -> None:
        return None


class _RecordingTransfusionClient:
    """仅返回受控 JSON，记录正式 executor 发出的裁剪 Prompt 和用量。"""

    def __init__(self) -> None:
        self.prompts: list[str] = []
        self.usages: list[tuple[int, int, int]] = []

    async def generate(self, prompt: str) -> dict[str, Any]:
        self.prompts.append(prompt)
        self.usages.append((100, 10, 110))
        if "application_ref:" in prompt:
            payload: dict[str, str] = {
                "reason_state": "present",
                "evidence_quote": "因血红蛋白65g/L申请输注",
                "application_ref": "TX-APP",
            }
        else:
            payload = {
                "assertion": "explicit",
                "component_text": "悬红",
                "quote": "输入悬红2U",
                "document_ref": "TX-BLOOD",
            }
        return {
            "choices": [{"message": {"content": json.dumps(payload, ensure_ascii=False)}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110},
            "_api_time": 0.1,
        }


def _record_for_visit(visit_id: str) -> dict[str, str]:
    return _RECORD_B if visit_id == _RECORD_B["visit_id"] else _RECORD_A


def _rows_for_source(*, source_key: str, visit_id: str) -> list[dict[str, Any]]:
    record = _record_for_visit(visit_id)
    common = {**record, "record_time": "2026-08-20 18:30:00"}
    blood_text = (
        "输血指征：血红蛋白65g/L。2026-08-20 16:00开始输入悬红2U，2026-08-20 18:00输血完毕。"
        "输血过程中生命体征平稳，未见发热、皮疹等输血不良反应。"
    )
    rows = {
        "mr_bloodtrans": [{**common, "transfution_datetime": "2026-08-20 16:00:00"}],
        "bloodtrans_record": [{**common, "document_id": "TX-BLOOD", "record_content": blood_text}],
        "consent_form": [{**common, "document_id": "TX-CONSENT", "record_content": "输血知情同意书，患者签名：脱敏患者，医师签名：脱敏医师，签署日期2026-08-20。"}],
        "blood_application": [{**common, "application_id": "TX-APP", "request_datetime": "2026-08-20 14:00:00", "reason_for_blood": "", "hemoglobin": "", "patient_bloodtype_abo": "A", "patient_bloodtype_rhd": "阳性", "record_content": "因血红蛋白65g/L申请输注悬浮红细胞2U。"}],
        "daily_course_record": [{**common, "document_id": "TX-COURSE", "record_time": "2026-08-20 19:00:00", "record_content": "输血后疗效评价：患者精神改善，复查血红蛋白上升，无不良反应。"}],
        "labtest_master": [{**common, "document_id": "TX-LAB", "report_time": "2026-08-20 13:00:00", "result": "乙肝表面抗原阴性，乙肝表面抗体阳性，乙肝e抗原阴性，乙肝e抗体阳性，乙肝核心抗体阳性，丙肝抗体阴性，艾滋病抗体阴性，梅毒抗体阴性，谷丙转氨酶20U/L。"}],
        "labtest_item_report": [
            {
                **common,
                "document_id": "TX-LAB",
                "item_name": item_name,
                "report_time": "2026-08-20 13:00:00",
                "result": "阴性",
            }
            for item_name in (
                "乙肝表面抗原",
                "乙肝表面抗体",
                "乙肝e抗原",
                "乙肝e抗体",
                "乙肝核心抗体",
                "丙肝抗体",
                "艾滋病抗体",
                "梅毒抗体",
                "谷丙转氨酶",
            )
        ],
        "surgery_record": [{**common, "document_id": "TX-SURGERY", "record_content": "术中输注悬浮红细胞2U。"}],
        "anesthesia_record": [{**common, "document_id": "TX-ANES", "record_content": "麻醉期间输注悬浮红细胞2U。"}],
        "postsurg_firstcourse_record": [{**common, "document_id": "TX-POST", "record_content": "术后首次病程记录：术中输注悬浮红细胞2U。"}],
        "inpat_nondrug_order": [{**common, "order_id": "TX-ORDER", "order_name": "输注悬浮红细胞2U"}],
        "medical_order": [{**common, "order_id": "TX-ORDER", "order_name": "输注悬浮红细胞2U"}],
        "inpat_bill_item": [{**common, "bill_id": "TX-BILL", "item_name": "悬浮红细胞2U"}],
    }
    return list(rows.get(source_key, []))


def _install_fixture_evidence_reader(monkeypatch: pytest.MonkeyPatch) -> None:
    original = luxian_execution.build_luxian_0609_evidence_read_session

    def reader(**kwargs: Any) -> SnapshotSourceRows:
        return SnapshotSourceRows.create(
            source_key=str(kwargs["source_key"]),
            rows=_rows_for_source(source_key=str(kwargs["source_key"]), visit_id=str(kwargs["visit_id"])),
            truncated=False,
            limit_rows=50,
        )

    monkeypatch.setattr(
        luxian_execution,
        "build_luxian_0609_evidence_read_session",
        lambda **kwargs: original(**kwargs, row_reader=reader),
    )


def _bundle_for_record(*, visit_id: str, patient_id: str) -> dict[str, Any]:
    return {
        "scene": "final", **_record_for_visit(visit_id), "patient_id": patient_id,
        "medical_text": "脱敏输血资料摘要", "structured_context": {}, "document_hits": {},
        "data_quality_flags": [], "source_doc_priority": [], "text_available": True,
        "documents": [{"id": f"PRIMARY-{visit_id}", "document_type": "输血记录", "content": "脱敏输血资料摘要"}],
    }


def _create_ready_sample_pool(*, engine: Any, service: CustomQCSamplePoolService) -> tuple[str, str]:
    pool = service.create_pool_with_items(
        name="输血三入口隔离样本", source_file="isolated-transfusion-fixture.xlsx",
        source_sheet="Sheet1", created_by="api-entry-test-user", scene="final",
        rows=[{"row_no": 1, "patient_name": "脱敏患者", "manual_issue_text": "输血记录完整性核验"}],
    )
    pool_id = str(pool["id"])
    with Session(engine) as session:
        item_id = session.execute(service._item_table.select().with_only_columns(service._item_table.c.id).where(service._item_table.c.pool_id == pool_id)).scalar_one()
        session.execute(service._item_table.update().where(service._item_table.c.id == item_id).values(
            matched_institute_id=_RECORD_A["institute_id"], matched_patient_id=_RECORD_A["patient_id"],
            matched_visit_id=_RECORD_A["visit_id"], match_status="matched", sync_status="synced", bundle_status="ready",
        ))
        session.commit()
    return pool_id, str(item_id)


def _seed_registration_projection(*, engine: Any) -> None:
    """工作台创建路由会读取住院登记投影；这是路由真实依赖，不是判定资料 mock。"""
    InpatRegistration.__table__.create(bind=engine, checkfirst=True)
    with Session(engine) as session:
        for record in (_RECORD_A, _RECORD_B):
            session.add(
                InpatRegistration(
                    **record,
                    inpat_no=f"IP-{record['visit_id']}",
                    admission_datetime=datetime(2026, 8, 20, 8, 0, 0),
                    discharge_datetime=datetime(2026, 8, 21, 12, 0, 0),
                )
            )
        session.commit()


def _item(job: dict[str, Any], *, rule_id: str) -> dict[str, Any]:
    matches = [item for item in list(job.get("items") or []) if item.get("visit_id") == _RECORD_A["visit_id"] and item.get("rule_id") == rule_id]
    assert len(matches) == 1
    return matches[0]


def _projection(item: dict[str, Any]) -> dict[str, Any]:
    return {key: item.get(key) for key in ("status", "reason_code", "customer_display_facts", "criterion_results")}


def _evidence_coordinates(item: dict[str, Any]) -> set[tuple[str, str, str, str]]:
    return {
        (str(e.get("source_type") or ""), str(e.get("source_document_id") or e.get("source_ref") or ""), str(e.get("field_path") or ""), str(e.get("record_time") or ""))
        for e in list(item.get("customer_evidence") or [])
    }


_EXPECTED_ACTIVE_OUTCOMES = {
    rule_id: ("compliant", "requirement_satisfied")
    for rule_id in CUSTOMER_ENTRY_RULE_IDS
}
_EXPECTED_EVIDENCE_DOCUMENT_IDS = {
    "LX0609-043": {"TX-BLOOD", "TX-LAB"},
    "LX0609-044": {"TX-BLOOD", "TX-APP"},
    "LX0609-045": {"TX-BLOOD"},
    "LX0609-046": {"TX-BLOOD"},
    "LX0609-047": {"TX-BLOOD", "TX-COURSE"},
    "LX0609-048": {"TX-BLOOD", "TX-SURGERY", "TX-ANES", "TX-POST"},
}


@pytest.mark.asyncio
async def test_transfusion_049_native_executor_no_trigger_is_not_applicable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """049 当前被任务 phase 暂停；此处只核验实际 executor 的无触发不适用语义。"""
    original = luxian_execution.build_luxian_0609_evidence_read_session

    def reader(**kwargs: Any) -> SnapshotSourceRows:
        source_key = str(kwargs["source_key"])
        return SnapshotSourceRows.create(
            source_key=source_key, rows=[], truncated=False, limit_rows=50
        )

    session = original(
        selected_rule_ids=("LX0609-049",),
        institute_id=_RECORD_A["institute_id"],
        patient_id=_RECORD_A["patient_id"],
        visit_id=_RECORD_A["visit_id"],
        source_schema=None,
        created_at="2026-08-21T12:00:00+08:00",
        evaluation_as_of_date="2026-08-21",
        row_reader=reader,
    )
    result = await execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-049",),
        wrapper_rules=[],
        evidence_payload=None,
        institute_id=_RECORD_A["institute_id"],
        patient_id=_RECORD_A["patient_id"],
        visit_id=_RECORD_A["visit_id"],
        source_schema=None,
        llm_client=None,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-049",),
    )
    assert result.results == ()
    assert len(result.decisions) == 1
    decision = result.decisions[0]
    assert decision.reason_code == "trigger_absent_complete"
    assert decision.applicability.value == "not_applicable"


@pytest.mark.asyncio
async def test_transfusion_049_prepare_partitions_phase_without_unified_engine_dispatch() -> None:
    """prepare 层保留049的 phase not_executed 语义；正式客户入口另有 scope 拒绝。"""
    prepared_rule = next(
        dict(rule)
        for rule in luxian_execution.load_luxian_0609_rules()
        if str(rule.get("rule_id") or "").strip().upper() == "LX0609-049"
    )
    executable_rules, context = await luxian_execution.prepare_luxian_0609_execution(
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        prepared_rules=[prepared_rule],
        visit_id=_RECORD_A["visit_id"],
        medical_text="脱敏输血资料摘要",
        evidence_payload=None,
        llm_client=None,
        settings=_formal_settings(),
        institute_id=_RECORD_A["institute_id"],
        patient_id=_RECORD_A["patient_id"],
        selected_customer_rule_ids=("LX0609-049",),
        evaluation_as_of_date="2026-08-21",
    )
    assert context.package_plan is not None
    assert context.package_plan.not_executed_rule_ids == ("LX0609-049",)
    assert context.package_plan.native_executor_batches == ()
    assert context.unified_engine_used is False
    assert context.delivery_mode == "canonical_straight_through"
    assert executable_rules == []
    assert len(context.native_results) == 1
    pending = context.native_results[0]
    assert pending["rule_id"] == "LX0609-049"
    assert pending["status"] == pending["result_status"] == "not_executed"
    assert pending["schema_version"] == "lx0609-customer-result-v2"
    assert pending["rule_set_key"] == LUXIAN_0609_RULE_SET_KEY
    assert pending["metadata"] == {
        "execution_source": "lx0609_phase_gate",
        "executor_type": "programmatic",
        "reason_code": "policy_definition_pending",
        "pending_reason_code": "charging_source_unavailable_customer_scope",
    }


@pytest.mark.parametrize("rule_id", ("LX0609-041", "LX0609-042"))
def test_transfusion_customer_entry_rejects_policy_excluded_rules_without_engine_dispatch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, rule_id: str
) -> None:
    """041/042 被客户运行策略排除，入口必须在创建任务前拒绝。"""
    workspace = _install_isolated_sqlite(monkeypatch, tmp_path)
    _seed_registration_projection(engine=workspace_module.engine)
    settings = _formal_settings()
    for module in (batch_worker, sichuan_qc_service, qc_sichuan):
        monkeypatch.setattr(module, "get_settings", lambda: settings)
    monkeypatch.setattr(
        batch_worker, "get_product_activation_service", lambda: _ActivationStub()
    )
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    service = sichuan_qc_service.SichuanQCService(
        {"provider_code": "isolated-test", "allow_mock_when_unconfigured": True}
    )

    async def provide_service() -> Any:
        return service

    monkeypatch.setattr(qc_sichuan, "get_qc_service", provide_service)
    engine_batches: list[tuple[tuple[str, tuple[str, ...]], ...]] = []
    original_engine_execute = luxian_execution.Luxian0609ExecutionEngine.execute

    async def capture_engine_execute(engine_instance: Any, *args: Any, **kwargs: Any) -> Any:
        engine_batches.append(
            tuple(
                (str(key), tuple(ids))
                for key, ids in tuple(kwargs.get("executor_batches") or ())
            )
        )
        return await original_engine_execute(engine_instance, *args, **kwargs)

    monkeypatch.setattr(
        luxian_execution.Luxian0609ExecutionEngine,
        "execute",
        capture_engine_execute,
    )
    with TestClient(_api_app(service=service)) as api:
        response = api.post(
            "/api/v1/qc/sichuan/workspace/batch-jobs",
            json={
                "rule_set_key": LUXIAN_0609_RULE_SET_KEY,
                "rule_ids": [rule_id],
                "scope": "final",
                "record_refs": [_RECORD_A],
                "run_mode": "serial",
            },
        )
    assert response.status_code == 422, response.text
    assert "当前客户运行范围" in response.json()["detail"]
    assert engine_batches == []


def test_transfusion_049_customer_entry_is_excluded_before_task_creation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """当前客户入口会先排除049，不能伪称它已产生 phase not_executed 任务项。"""
    workspace = _install_isolated_sqlite(monkeypatch, tmp_path)
    engine = workspace_module.engine
    _seed_registration_projection(engine=engine)
    _install_fixture_evidence_reader(monkeypatch)
    settings = _formal_settings()
    for module in (batch_worker, sichuan_qc_service, qc_sichuan):
        monkeypatch.setattr(module, "get_settings", lambda: settings)
    monkeypatch.setattr(
        batch_worker, "get_product_activation_service", lambda: _ActivationStub()
    )
    monkeypatch.setattr(
        batch_worker,
        "load_running_final_bundle",
        lambda *, institute_id, patient_id, visit_id, **_: _bundle_for_record(
            visit_id=str(visit_id), patient_id=str(patient_id)
        ),
    )
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    service = sichuan_qc_service.SichuanQCService(
        {"provider_code": "isolated-test", "allow_mock_when_unconfigured": True}
    )

    async def provide_service() -> Any:
        return service

    monkeypatch.setattr(qc_sichuan, "get_qc_service", provide_service)
    engine_batches: list[tuple[tuple[str, tuple[str, ...]], ...]] = []
    original_engine_execute = luxian_execution.Luxian0609ExecutionEngine.execute

    async def capture_engine_execute(engine_instance: Any, *args: Any, **kwargs: Any) -> Any:
        engine_batches.append(
            tuple(
                (str(key), tuple(ids))
                for key, ids in tuple(kwargs.get("executor_batches") or ())
            )
        )
        return await original_engine_execute(engine_instance, *args, **kwargs)

    monkeypatch.setattr(
        luxian_execution.Luxian0609ExecutionEngine,
        "execute",
        capture_engine_execute,
    )
    with TestClient(_api_app(service=service)) as api:
        response = api.post(
            "/api/v1/qc/sichuan/workspace/batch-jobs",
            json={
                "rule_set_key": LUXIAN_0609_RULE_SET_KEY,
                "rule_ids": ["LX0609-049"],
                "scope": "final",
                "record_refs": [_RECORD_A],
                "run_mode": "serial",
            },
        )
    assert response.status_code == 422, response.text
    assert "rule_ids" in response.json()["detail"]
    assert engine_batches == []


@pytest.mark.integration
@pytest.mark.parametrize("rule_id", CUSTOMER_ENTRY_RULE_IDS)
def test_transfusion_asgi_entries_use_unified_engine_and_persist_same_canonical_result(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, rule_id: str
) -> None:
    """单病历、两病历批量和客户样本均由真实 detached worker 执行。"""
    workspace = _install_isolated_sqlite(monkeypatch, tmp_path)
    engine = workspace_module.engine
    _seed_registration_projection(engine=engine)
    sample_service = _install_sample_pool_sqlite(monkeypatch, engine=engine)
    _install_fixture_evidence_reader(monkeypatch)
    settings = _formal_settings()
    for module in (batch_worker, sichuan_qc_service, qc_sichuan):
        monkeypatch.setattr(module, "get_settings", lambda: settings)
    monkeypatch.setattr(batch_worker, "get_product_activation_service", lambda: _ActivationStub())
    monkeypatch.setattr(sichuan_qc_service, "build_adjudicator_runtime_config", lambda config: dict(config or {}))
    monkeypatch.setattr(batch_worker, "load_running_final_bundle", lambda *, institute_id, patient_id, visit_id, **_: _bundle_for_record(visit_id=str(visit_id), patient_id=str(patient_id)))
    monkeypatch.setattr(sample_pool_module, "get_settings", lambda: SimpleNamespace(JWT_SECRET="transfusion-entry-test"))
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(qc_sample_pools, "_workspace_service", lambda: workspace)
    monkeypatch.setattr(qc_sample_pools, "_service", lambda: sample_service)

    service = sichuan_qc_service.SichuanQCService({"provider_code": "isolated-test", "model": "controlled-transfusion-stub", "allow_mock_when_unconfigured": True})
    client = _RecordingTransfusionClient()
    service.adjudicator_client = client

    async def provide_service() -> Any:
        return service

    monkeypatch.setattr(qc_sichuan, "get_qc_service", provide_service)
    phase_events: list[tuple[str, dict[str, Any]]] = []
    engine_batches: list[tuple[tuple[str, tuple[str, ...]], ...]] = []
    original_progress = workspace.update_batch_job_progress
    original_engine_execute = luxian_execution.Luxian0609ExecutionEngine.execute

    async def capture_engine_execute(engine_instance: Any, *args: Any, **kwargs: Any) -> Any:
        batches = tuple((str(key), tuple(ids)) for key, ids in tuple(kwargs.get("executor_batches") or ()))
        assert batches == ((EXECUTOR_KEY, (rule_id,)),)
        engine_batches.append(batches)
        return await original_engine_execute(engine_instance, *args, **kwargs)

    def capture_progress(**kwargs: Any) -> None:
        state = dict((kwargs.get("summary_patch") or {}).get("stream_state") or {})
        if state.get("kind") == "native_executor_phase":
            phase_events.append((str(kwargs.get("job_id") or ""), state))
        original_progress(**kwargs)

    monkeypatch.setattr(luxian_execution.Luxian0609ExecutionEngine, "execute", capture_engine_execute)
    monkeypatch.setattr(workspace, "update_batch_job_progress", capture_progress)
    app = _api_app(service=service)
    pool_id, sample_item_id = _create_ready_sample_pool(engine=engine, service=sample_service)

    def create_workspace_job(records: list[dict[str, str]]) -> str:
        with TestClient(app) as api:
            response = api.post("/api/v1/qc/sichuan/workspace/batch-jobs", json={"rule_set_key": LUXIAN_0609_RULE_SET_KEY, "rule_ids": [rule_id], "scope": "final", "record_refs": records, "run_mode": "serial"})
        assert response.status_code == 200, response.text
        return str(response.json()["data"]["id"])

    single_id = create_workspace_job([_RECORD_A])
    single_job = _wait_for_terminal_job(workspace=workspace, job_id=single_id)
    single_item = _item(single_job, rule_id=rule_id)
    single_envelope = _read_saved_envelope(app=app, job_id=single_id, task_item=single_item, record=_RECORD_A, expected_rule_ids=[rule_id])
    batch_id = create_workspace_job([_RECORD_A, _RECORD_B])
    batch_job = _wait_for_terminal_job(workspace=workspace, job_id=batch_id)
    batch_item = _item(batch_job, rule_id=rule_id)
    batch_envelope = _read_saved_envelope(app=app, job_id=batch_id, task_item=batch_item, record=_RECORD_A, expected_rule_ids=[rule_id])
    with TestClient(app) as api:
        response = api.post(f"/api/v1/qc/sample-pools/{pool_id}/run", json={"validation_mode": "customer", "rule_set_key": LUXIAN_0609_RULE_SET_KEY, "selected_rule_ids": [rule_id], "sample_item_ids": [sample_item_id], "record_refs": [_RECORD_A], "group_by_luxian_family": False})
    assert response.status_code == 200, response.text
    sample_id = str(response.json()["data"]["job_id"])
    sample_job = _wait_for_terminal_job(workspace=workspace, job_id=sample_id)
    sample_item = _item(sample_job, rule_id=rule_id)
    sample_envelope = _read_saved_envelope(app=app, job_id=sample_id, task_item=sample_item, record=_RECORD_A, expected_rule_ids=[rule_id])

    for job, item in ((single_job, single_item), (batch_job, batch_item), (sample_job, sample_item)):
        assert job["status"] == "completed", job.get("error_message")
        assert not list(job.get("failed_records") or [])
        assert (item.get("metadata") or {}).get("executor_key") == EXECUTOR_KEY
        assert (item.get("status"), item.get("reason_code")) == _EXPECTED_ACTIVE_OUTCOMES[rule_id]
        assert not item.get("llm_fallback") and not item.get("pack_fallback")
        assert "legacy" not in str(item.get("metadata") or {}).lower()
        assert any(job_id == job["id"] and event.get("event") == "completed" and event.get("executor_key") == EXECUTOR_KEY for job_id, event in phase_events)

    assert _projection(single_item) == _projection(batch_item) == _projection(sample_item)
    assert _evidence_coordinates(single_item) == _evidence_coordinates(batch_item) == _evidence_coordinates(sample_item)
    assert _evidence_coordinates(single_item)
    evidence_document_ids = {
        document_id
        for _source_type, document_id, _field_path, _record_time in _evidence_coordinates(single_item)
    }
    assert _EXPECTED_EVIDENCE_DOCUMENT_IDS[rule_id].issubset(evidence_document_ids)
    assert _envelope_customer_projection(single_envelope) == _envelope_customer_projection(batch_envelope) == _envelope_customer_projection(sample_envelope)
    if rule_id in {"LX0609-044", "LX0609-046"}:
        assert len(client.prompts) == 4
        assert client.prompts == [client.prompts[0]] * 4
        assert client.usages == [(100, 10, 110)] * 4
        assert all("脱敏输血资料摘要" not in prompt for prompt in client.prompts)
    else:
        assert client.prompts == []
        assert client.usages == []
    if rule_id == "LX0609-047":
        facts = dict(single_item.get("customer_display_facts") or {})
        assert facts["transfusion_end_time"] == "2026-08-20 18:00:00"
        assert facts["evaluation_time"] == "2026-08-20 19:00:00"
        assert facts["elapsed_hours"] == 1.0

    assert len(engine_batches) == 4
    assert engine_batches == [((EXECUTOR_KEY, (rule_id,)),)] * 4
