"""LX0609 检查检验规则族的行为冻结与三业务入口验收。

测试不连接 .env、PostgreSQL 或真实模型：

* 正式 prepare、统一执行引擎、exam_lab executor、聚合器与 worker 不替换；
* 固定脱敏 source fixture 只替代医院资料读取；
* 工作台任务和 Canonical Envelope 写入临时 SQLite；
* 语义测试使用可记录 Prompt/Token 的确定性 client，不断言摘要或 SHA。

禁止用旧链、fallback 或伪造完成结果替代正式执行。
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
from types import SimpleNamespace
from typing import Any

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.database.models.cdm import (
    AdmissionRecord,
    DischargeRecord,
    MedicalRecordFrontpage,
)
from app.services import custom_qc_workspace_service as workspace_module
from app.services import sichuan_qc_service
from app.services import sichuan_workspace_batch_worker as batch_worker
from app.services.custom_qc_workspace_service import CustomQCWorkspaceService
from app.services.luxian_0609 import execution as luxian_execution
from app.services.luxian_0609.evidence_snapshot_provider import SnapshotSourceRows
from app.services.luxian_0609.native_exam_lab_execution import EXAM_LAB_RULE_IDS
from app.services.luxian_0609_rule_catalog import LUXIAN_0609_RULE_SET_KEY


RULE_ID = "LX0609-012"
RULE_SET_VERSION = "2026-06-09"
_RECORD_A = {
    "institute_id": "EXAM-HOSPITAL",
    "patient_id": "EXAM-PATIENT-A",
    "visit_id": "EXAM-VISIT-A",
}
_RECORD_B = {
    "institute_id": "EXAM-HOSPITAL",
    "patient_id": "EXAM-PATIENT-B",
    "visit_id": "EXAM-VISIT-B",
}


def _formal_settings() -> SimpleNamespace:
    """只提供检查检验 Native 正式链读取的开关。"""

    return SimpleNamespace(
        LUXIAN_0609_MAINLINE_RULE_DECISION_ENABLED=True,
        LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED=True,
        LUXIAN_0609_NATIVE_EXECUTION_ENABLED=True,
        LUXIAN_0609_NATIVE_EXAM_LAB_ENABLED=True,
        LUXIAN_0609_UNIFIED_ENGINE_ENABLED=True,
        LUXIAN_0609_RULE_DECISION_EXAM_LAB_ENABLED=True,
        LUXIAN_0609_TRIGGER_GATE_ENABLED=False,
        LUXIAN_0609_LLM_TRIGGER_GATE_ENABLED=False,
        LUXIAN_0609_EVIDENCE_FORMATTER_ENABLED=False,
        LUXIAN_0609_RUNTIME_SHADOW_ENABLED=False,
    )


class _ActivationStub:
    def enforce(self) -> None:
        return None


class _RecordingClient:
    """记录正式 executor 的最小 Prompt 和固定用量，不访问模型。"""

    def __init__(self, *responses: dict[str, object]) -> None:
        self._responses = list(responses)
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> dict[str, object]:
        self.prompts.append(prompt)
        response = self._responses.pop(0)
        return {
            "choices": [
                {"message": {"content": json.dumps(response, ensure_ascii=False)}}
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 10,
                "total_tokens": 110,
            },
            "_api_time": 0.2,
        }


def _patient_id_for_visit(visit_id: str) -> str:
    return (
        _RECORD_B["patient_id"]
        if visit_id == _RECORD_B["visit_id"]
        else _RECORD_A["patient_id"]
    )


def _exam_row(visit_id: str) -> dict[str, str]:
    return {
        "institute_id": _RECORD_A["institute_id"],
        "patient_id": _patient_id_for_visit(visit_id),
        "visit_id": visit_id,
        "document_id": f"EXAM-REPORT-{visit_id}",
        "exam_id": f"EXAM-{visit_id}",
        "exam_name": "胸部CT",
        "exam_time": "2026-07-02 08:00:00",
        "report_time": "2026-07-02 12:00:00",
        "exam_conclusion": "阳性：右肺占位，考虑恶性。",
    }


def _culture_row(visit_id: str) -> dict[str, str]:
    return {
        "institute_id": _RECORD_A["institute_id"],
        "patient_id": _patient_id_for_visit(visit_id),
        "visit_id": visit_id,
        "document_id": f"CULTURE-REPORT-{visit_id}",
        "labtest_id": f"CULTURE-{visit_id}",
        "labtest_subject": "血培养及药敏",
        "report_time": "2026-07-02 12:00:00",
        "result": "培养阳性，药敏结果已报告。",
    }


def _course_rows(visit_id: str, *, explicit: bool) -> list[dict[str, str]]:
    return [
        {
            "institute_id": _RECORD_A["institute_id"],
            "patient_id": _patient_id_for_visit(visit_id),
            "visit_id": visit_id,
            "document_id": f"COURSE-BEFORE-{visit_id}",
            "record_time": "2026-07-02 07:00:00",
            "record_content": ("因持续咳嗽伴胸痛，拟行胸部CT明确肺部病变；" "同时送血培养及药敏以明确感染病原。"),
        },
        {
            "institute_id": _RECORD_A["institute_id"],
            "patient_id": _patient_id_for_visit(visit_id),
            "visit_id": visit_id,
            "document_id": f"COURSE-AFTER-{visit_id}",
            "record_time": "2026-07-02 13:00:00",
            "record_content": (
                "影像报告提示右肺占位，结合病史考虑肺部肿瘤，计划进一步检查；" "培养检出大肠埃希菌且对头孢类敏感，改用头孢曲松。"
                if explicit
                else "相关检查检验结果已处理。"
            ),
        },
    ]


def _rows_for_source(
    *, source_key: str, visit_id: str, explicit_course: bool
) -> list[dict[str, str]]:
    if source_key == "exam_master":
        return [_exam_row(visit_id)]
    if source_key == "labtest_master":
        return [_culture_row(visit_id)]
    if source_key == "daily_course_record":
        return _course_rows(visit_id, explicit=explicit_course)
    if source_key == "evaluation_context.horizon":
        return [
            {"horizon_datetime": "2026-07-05 12:00:00", "horizon_date": "2026-07-05"}
        ]
    if source_key == "inpat_registration.discharge_horizon":
        return [{"discharge_datetime": "2026-07-05 12:00:00"}]
    return []


def _build_evidence_session(
    *, selected_rule_ids: tuple[str, ...], explicit_course: bool, visit_id: str
):
    def read_fixture(**kwargs: Any) -> SnapshotSourceRows:
        source_key = str(kwargs["source_key"])
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=_rows_for_source(
                source_key=source_key,
                visit_id=visit_id,
                explicit_course=explicit_course,
            ),
            truncated=False,
            limit_rows=50,
        )

    return luxian_execution.build_luxian_0609_evidence_read_session(
        selected_rule_ids=selected_rule_ids,
        institute_id=_RECORD_A["institute_id"],
        patient_id=_RECORD_A["patient_id"],
        visit_id=visit_id,
        source_schema=None,
        created_at="2026-07-05T12:00:00+08:00",
        evaluation_as_of_date="2026-07-05",
        row_reader=read_fixture,
    )


def _fact_response() -> dict[str, object]:
    return {
        "schema_version": "lx0609-exam-lab-text-facts-v3",
        "facts": [
            {
                "rule_id": rule_id,
                "applicability": "applicable",
                "semantic_state": "present",
                "positive_state": (
                    "positive"
                    if rule_id in {"LX0609-012", "LX0609-015"}
                    else "not_relevant"
                ),
                "course_doc_positions": [1 if rule_id == "LX0609-010" else 2],
            }
            for rule_id in EXAM_LAB_RULE_IDS
        ],
    }


async def _run_formal_chain(
    monkeypatch: pytest.MonkeyPatch, *, client: _RecordingClient
) -> tuple[luxian_execution.Luxian0609ExecutionContext, dict[str, Any]]:
    session = _build_evidence_session(
        selected_rule_ids=EXAM_LAB_RULE_IDS,
        explicit_course=False,
        visit_id=_RECORD_A["visit_id"],
    )
    monkeypatch.setattr(
        luxian_execution,
        "build_luxian_0609_evidence_read_session",
        lambda **_kwargs: session,
    )
    executable_rules, context = await luxian_execution.prepare_luxian_0609_execution(
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        prepared_rules=[],
        visit_id=_RECORD_A["visit_id"],
        medical_text="FULL_CHART_MUST_NOT_REACH_PROMPT",
        evidence_payload=None,
        llm_client=client,
        settings=_formal_settings(),
        institute_id=_RECORD_A["institute_id"],
        patient_id=_RECORD_A["patient_id"],
        selected_customer_rule_ids=EXAM_LAB_RULE_IDS,
        evaluation_as_of_date="2026-07-05",
    )
    assert executable_rules == []
    delivered = luxian_execution.aggregate_luxian_0609_orchestrated_results(
        orchestrated={"results": []},
        context=context,
        visit_id=_RECORD_A["visit_id"],
        model_name="recording-stub",
        evidence_payload={},
    )
    return context, delivered


@pytest.mark.asyncio
async def test_exam_lab_family_freezes_canonical_facts_evidence_and_prompt_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """五条规则走正式统一链，冻结 Canonical 合同、证据与一次语义调用。"""

    client = _RecordingClient(_fact_response())
    context, delivered = await _run_formal_chain(monkeypatch, client=client)

    assert [item.rule_id for item in context.reduced_decisions] == list(
        EXAM_LAB_RULE_IDS
    )
    assert [item.final_state.value for item in context.reduced_decisions] == [
        "compliant"
    ] * 5
    assert [item.reason_code for item in context.reduced_decisions] == [
        "requirement_satisfied"
    ] * 5
    assert context.native_llm_call_count == 1
    assert (
        context.native_prompt_tokens,
        context.native_completion_tokens,
        context.native_total_tokens,
    ) == (100, 10, 110)
    assert len(client.prompts) == 1
    assert "FULL_CHART_MUST_NOT_REACH_PROMPT" not in client.prompts[0]
    assert all(rule_id in client.prompts[0] for rule_id in EXAM_LAB_RULE_IDS)

    results = list(delivered["results"])
    assert [
        (item["rule_id"], item["status"], item["reason_code"]) for item in results
    ] == [
        (rule_id, "compliant", "requirement_satisfied") for rule_id in EXAM_LAB_RULE_IDS
    ]
    assert (
        delivered["total_prompt_tokens"],
        delivered["total_completion_tokens"],
        delivered["total_tokens"],
    ) == (100, 10, 110)
    assert delivered["executor_breakdown"] == {"llm": 1}
    assert all(item.fact_refs for item in context.reduced_decisions)
    assert "LX0609-010" not in dict(context.customer_display_facts)

    expected_facts = {
        rule_id: {
            "verification_kind": "exam_lab_requirement_checked",
            "subject": (
                "ct_mri"
                if rule_id in {"LX0609-011", "LX0609-012"}
                else "culture_susceptibility"
            ),
            "requirement": (
                "positive_result_analysis_within_24h"
                if rule_id in {"LX0609-012", "LX0609-015"}
                else "result_recording_within_24h"
            ),
            "event_phase": "report",
            "checked_sources": ["exam_lab_report", "course_record"],
            "applicable": True,
            "requirement_met": True,
            "positive_state": (
                "positive"
                if rule_id in {"LX0609-012", "LX0609-015"}
                else "not_relevant"
            ),
            "report_time": "2026-07-02 12:00:00",
            "response_record_time": "2026-07-02 13:00:00",
            "threshold_hours": 24,
            "response_record_count": 1,
            "interval_hours": 1.0,
            "reviewed_record_scope": "首次病程记录及后续病程记录",
            "event_count": 1,
            "event_position": 1,
        }
        for rule_id in ("LX0609-011", "LX0609-012", "LX0609-014", "LX0609-015")
    }
    expected_evidence_coordinates = {
        "LX0609-010": [
            (
                "exam_master",
                f"EXAM-REPORT-{_RECORD_A['visit_id']}",
                "exam_conclusion",
                "2026-07-02 08:00:00",
            )
        ],
        "LX0609-011": [
            (
                "daily_course_record",
                f"COURSE-AFTER-{_RECORD_A['visit_id']}",
                "record_content",
                "2026-07-02 13:00:00",
            ),
            (
                "exam_master",
                f"EXAM-REPORT-{_RECORD_A['visit_id']}",
                "exam_conclusion",
                "2026-07-02 08:00:00",
            ),
        ],
        "LX0609-012": [],
        "LX0609-014": [
            (
                "daily_course_record",
                f"COURSE-AFTER-{_RECORD_A['visit_id']}",
                "record_content",
                "2026-07-02 13:00:00",
            ),
            (
                "labtest_master",
                f"CULTURE-REPORT-{_RECORD_A['visit_id']}",
                "result",
                "2026-07-02 12:00:00",
            ),
        ],
        "LX0609-015": [],
    }
    expected_evidence_coordinates["LX0609-012"] = list(
        expected_evidence_coordinates["LX0609-011"]
    )
    expected_evidence_coordinates["LX0609-015"] = list(
        expected_evidence_coordinates["LX0609-014"]
    )
    for item in results:
        evidence_coordinates = [
            (
                evidence.get("source_type"),
                evidence.get("source_document_id"),
                evidence.get("field_path"),
                evidence.get("record_time"),
            )
            for evidence in item["customer_evidence"]
        ]
        assert evidence_coordinates == expected_evidence_coordinates[item["rule_id"]]
        if item["rule_id"] == "LX0609-010":
            # 冻结迁移前 Canonical 行为：010 的合规事实只存在于执行上下文，
            # 当前聚合结果不重复保存 customer_display_facts。
            assert "customer_display_facts" not in item
            continue
        facts = dict(item["customer_display_facts"])
        assert facts == expected_facts[item["rule_id"]]
        assert "sha" not in repr(facts).lower()

    rerun_client = _RecordingClient(_fact_response())
    _, rerun_delivered = await _run_formal_chain(monkeypatch, client=rerun_client)
    assert client.prompts == rerun_client.prompts
    assert [
        {
            key: item.get(key)
            for key in (
                "status",
                "reason_code",
                "customer_display_facts",
                "customer_evidence",
            )
        }
        for item in results
    ] == [
        {
            key: item.get(key)
            for key in (
                "status",
                "reason_code",
                "customer_display_facts",
                "customer_evidence",
            )
        }
        for item in rerun_delivered["results"]
    ]


def _fixture_evidence_session_builder(monkeypatch: pytest.MonkeyPatch) -> None:
    original = luxian_execution.build_luxian_0609_evidence_read_session

    def read_fixture(**kwargs: Any) -> SnapshotSourceRows:
        source_key = str(kwargs["source_key"])
        visit_id = str(kwargs["visit_id"])
        assert visit_id in {_RECORD_A["visit_id"], _RECORD_B["visit_id"]}
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=_rows_for_source(
                source_key=source_key,
                visit_id=visit_id,
                explicit_course=True,
            ),
            truncated=False,
            limit_rows=50,
        )

    def build_with_fixture_reader(**kwargs: Any):
        return original(**kwargs, row_reader=read_fixture)

    monkeypatch.setattr(
        luxian_execution,
        "build_luxian_0609_evidence_read_session",
        build_with_fixture_reader,
    )


def _install_isolated_sqlite(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> CustomQCWorkspaceService:
    database_path = tmp_path / "lx0609-exam-lab-convergence.sqlite3"
    database_url = f"sqlite+pysqlite:///{database_path.as_posix()}"
    engine = sa.create_engine(database_url, future=True)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    monkeypatch.setattr(workspace_module, "engine", engine)
    monkeypatch.setattr(workspace_module, "SessionLocal", session_local)
    monkeypatch.setattr(workspace_module, "DB_SCHEMA_MODE", "single")
    workspace_module._drafts_table.cache_clear()
    workspace_module._batch_jobs_table.cache_clear()
    workspace_module._record_result_envelopes_table.cache_clear()
    monkeypatch.setattr(
        workspace_module, "_sync_batch_job_parent_columns", lambda **_kwargs: None
    )

    for model in (MedicalRecordFrontpage, AdmissionRecord, DischargeRecord):
        model.__table__.create(bind=engine, checkfirst=True)
    with Session(engine) as session:
        for ref in (_RECORD_A, _RECORD_B):
            session.add(
                MedicalRecordFrontpage(
                    **ref,
                    name="脱敏患者",
                    inpat_no=f"IP-{ref['visit_id']}",
                    admission_datetime=datetime(2026, 7, 1, 8, 0, 0),
                    discharge_datetime=datetime(2026, 7, 5, 12, 0, 0),
                    admission_dept_name="内科",
                    discharge_dept_name="内科",
                    attending_physician_sign="脱敏医师",
                    record_content="脱敏病历摘要",
                )
            )
        session.commit()

    workspace = CustomQCWorkspaceService()
    workspace._record_result_envelope_table.create(bind=engine, checkfirst=True)
    return workspace


def _bundle_for_record(*, visit_id: str, patient_id: str) -> dict[str, Any]:
    return {
        "scene": "final",
        "institute_id": _RECORD_A["institute_id"],
        "patient_id": patient_id,
        "visit_id": visit_id,
        "medical_text": "脱敏病历摘要",
        "structured_context": {},
        "document_hits": {},
        "data_quality_flags": [],
        "source_doc_priority": [],
        "text_available": True,
        "documents": [
            {
                "id": f"PRIMARY-{visit_id}",
                "document_type": "检查记录",
                "content": "脱敏病历摘要",
            }
        ],
    }


def _job_filters(
    *, record_refs: list[dict[str, str]], sample_pool_id: str = ""
) -> dict[str, Any]:
    filters: dict[str, Any] = {
        "rule_ids": [RULE_ID],
        "rule_set_key": LUXIAN_0609_RULE_SET_KEY,
        "rule_set_name": "泸县0609质控",
        "rule_set_version": RULE_SET_VERSION,
        "validation_mode": "programmatic",
        "query_scope": "final",
        "execution_strategy": "default",
        "quality_profile": "throughput_v1",
        "bucket_strategy": "domain_family",
        "batch_output_mode": "full",
        "record_refs": record_refs,
        "scoped_customer_rule_ids": [RULE_ID],
        "selected_rule_ids": [RULE_ID],
        "record_rule_map": {
            f"{item['institute_id']}::{item['patient_id']}::{item['visit_id']}": [
                RULE_ID
            ]
            for item in record_refs
        },
    }
    if sample_pool_id:
        filters.update(
            {
                "sample_pool_id": sample_pool_id,
                "source": "manual_problem_sample_pool",
                "selected_sample_item_ids": ["EXAM-SAMPLE-1"],
            }
        )
    return filters


async def _run_formal_job(
    *,
    workspace: CustomQCWorkspaceService,
    service: Any,
    name: str,
    record_refs: list[dict[str, str]],
    execution_mode: str,
    run_mode: str,
    sample_pool_id: str = "",
) -> dict[str, Any]:
    job = workspace.create_batch_job(
        draft={
            "id": f"EXAM-{name}",
            "rule_code": RULE_ID,
            "name": "CT/MRI阳性结果分析",
            "scene": "final",
        },
        created_by="exam-lab-isolated-test",
        scope="final",
        filters=_job_filters(record_refs=record_refs, sample_pool_id=sample_pool_id),
        record_ids=[item["visit_id"] for item in record_refs],
        record_refs=record_refs,
        total_records=len(record_refs),
        execution_mode=execution_mode,
        run_mode=run_mode,
        rule_count=1,
        job_kind="leaf",
        family_key="exam_lab" if sample_pool_id else None,
        family_name="检查检验" if sample_pool_id else None,
    )

    async def provide_service() -> Any:
        return service

    await batch_worker.run_sichuan_workspace_batch_job(
        str(job["id"]), workspace=workspace, qc_service_provider=provide_service
    )
    persisted = workspace.get_batch_job_for_processing(job_id=str(job["id"]))
    assert persisted is not None
    return persisted


def _canonical_saved_item(job: dict[str, Any], *, visit_id: str) -> dict[str, Any]:
    items = [
        item
        for item in list(job.get("items") or [])
        if str(item.get("visit_id") or "") == visit_id
        and str(item.get("rule_id") or "") == RULE_ID
    ]
    assert len(items) == 1
    return items[0]


def _canonical_projection(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": item.get("status"),
        "reason_code": item.get("reason_code"),
        "customer_display_facts": item.get("customer_display_facts"),
        "criterion_results": item.get("criterion_results"),
        "customer_evidence": item.get("customer_evidence"),
    }


@pytest.mark.asyncio
async def test_exam_lab_formal_worker_is_consistent_across_three_business_entries(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """同一检查资料经三入口均走 exam_lab executor 并保存同一 Canonical 结果。"""

    workspace = _install_isolated_sqlite(monkeypatch, tmp_path)
    _fixture_evidence_session_builder(monkeypatch)
    settings = _formal_settings()
    monkeypatch.setattr(batch_worker, "get_settings", lambda: settings)
    monkeypatch.setattr(sichuan_qc_service, "get_settings", lambda: settings)
    monkeypatch.setattr(
        batch_worker, "get_product_activation_service", lambda: _ActivationStub()
    )
    monkeypatch.setattr(
        sichuan_qc_service,
        "build_adjudicator_runtime_config",
        lambda config: dict(config or {}),
    )
    monkeypatch.setattr(
        batch_worker,
        "load_running_final_bundle",
        lambda *, institute_id, patient_id, visit_id, **_kwargs: _bundle_for_record(
            visit_id=str(visit_id), patient_id=str(patient_id)
        ),
    )
    service = sichuan_qc_service.SichuanQCService(
        {
            "provider_code": "isolated-test",
            "model": "controlled-stub",
            "allow_mock_when_unconfigured": True,
            "source": "exam-lab-isolated",
        }
    )

    native_phase_events: list[tuple[str, dict[str, Any]]] = []
    original_update_progress = workspace.update_batch_job_progress

    def capture_update_progress(**kwargs: Any) -> None:
        stream_state = dict(
            (kwargs.get("summary_patch") or {}).get("stream_state") or {}
        )
        if stream_state.get("kind") == "native_executor_phase":
            native_phase_events.append((str(kwargs.get("job_id") or ""), stream_state))
        original_update_progress(**kwargs)

    monkeypatch.setattr(workspace, "update_batch_job_progress", capture_update_progress)

    single_job = await _run_formal_job(
        workspace=workspace,
        service=service,
        name="single-rule",
        record_refs=[_RECORD_A],
        execution_mode="single",
        run_mode="serial",
    )
    pool_batch_job = await _run_formal_job(
        workspace=workspace,
        service=service,
        name="record-pool-batch",
        record_refs=[_RECORD_A, _RECORD_B],
        execution_mode="multi",
        run_mode="parallel",
    )
    sample_leaf_job = await _run_formal_job(
        workspace=workspace,
        service=service,
        name="sample-validation-leaf",
        record_refs=[_RECORD_A],
        execution_mode="multi",
        run_mode="parallel",
        sample_pool_id="EXAM-POOL",
    )

    for job in (single_job, pool_batch_job, sample_leaf_job):
        assert any(
            event_job_id == job["id"]
            and event.get("event") == "completed"
            and event.get("executor_key") == "exam_lab"
            for event_job_id, event in native_phase_events
        )
        assert job["status"] == "completed"
        assert not list(job.get("failed_records") or [])
        item = _canonical_saved_item(job, visit_id=_RECORD_A["visit_id"])
        assert item["status"] == "compliant"
        assert item["reason_code"] == "requirement_satisfied"
        assert (item.get("metadata") or {}).get("executor_key") == "exam_lab"
        assert not item.get("llm_fallback")
        assert not item.get("pack_fallback")
        assert not (item.get("metadata") or {}).get("bundle_fallback")
        assert "legacy" not in str(item.get("metadata") or {}).lower()
        assert list(item.get("customer_evidence") or [])

    single_item = _canonical_saved_item(single_job, visit_id=_RECORD_A["visit_id"])
    pool_item = _canonical_saved_item(pool_batch_job, visit_id=_RECORD_A["visit_id"])
    sample_item = _canonical_saved_item(sample_leaf_job, visit_id=_RECORD_A["visit_id"])
    assert _canonical_projection(single_item) == _canonical_projection(pool_item)
    assert _canonical_projection(single_item) == _canonical_projection(sample_item)

    latest = workspace.get_latest_luxian_0609_record_result(
        institute_id=_RECORD_A["institute_id"],
        patient_id=_RECORD_A["patient_id"],
        visit_id=_RECORD_A["visit_id"],
        expected_rule_ids=[RULE_ID],
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        rule_set_version=RULE_SET_VERSION,
    )
    assert latest["state"] == "ready"
    assert latest["job_id"] == sample_leaf_job["id"]
    envelope_item = latest["items"][0]
    assert {
        key: envelope_item.get(key)
        for key in (
            "status",
            "reason_code",
            "customer_display_facts",
            "criterion_results",
        )
    } == {
        key: sample_item.get(key)
        for key in (
            "status",
            "reason_code",
            "customer_display_facts",
            "criterion_results",
        )
    }
    envelope_evidence = list(envelope_item.get("evidence") or [])
    assert envelope_evidence
    assert all(
        re.fullmatch(r"src_[0-9a-f]{24}", str(item.get("source_ref") or ""))
        and "source_document_id" not in item
        for item in envelope_evidence
    )
