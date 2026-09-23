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
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.database.models.cdm import (
    AdmissionRecord,
    DischargeRecord,
    InpatRegistration,
    MedicalRecordFrontpage,
)
from app.services import custom_qc_workspace_service as workspace_module
from app.services import custom_qc_sample_pool_service as sample_pool_module
from app.services import sichuan_qc_service
from app.services import sichuan_workspace_batch_worker as batch_worker
from app.services import sample_programmatic_evidence
from app.routers import qc_sample_pools, qc_sichuan
from app.services.custom_qc_sample_pool_service import CustomQCSamplePoolService
from app.services.custom_qc_workspace_service import CustomQCWorkspaceService
from app.services.luxian_0609 import execution as luxian_execution
from app.services.luxian_0609.ct_order_course_consistency import SCHEMA_VERSION as CT_SCHEMA_VERSION
from app.services.luxian_0609.evidence_snapshot_provider import SnapshotSourceRows
from app.services.luxian_0609.handbook_exam_lab import ORDER_SOURCE
from app.services.luxian_0609.native_exam_lab_execution import (
    EXAM_LAB_RULE_IDS,
    EXECUTABLE_EXAM_LAB_RULE_IDS,
)
from app.services.luxian_0609_rule_catalog import LUXIAN_0609_RULE_SET_KEY
from tests.integration.test_luxian_0609_consultation_api_entry_flow import (
    _api_app,
    _envelope_customer_projection,
    _install_sample_pool_sqlite,
    _read_saved_envelope,
    _wait_for_terminal_job,
)


_ASGI_EXPECTED_OUTCOMES = {
    rule_id: ("compliant", "requirement_satisfied")
    for rule_id in EXAM_LAB_RULE_IDS
}
_ASGI_EXPECTED_OUTCOMES.update(
    {
        # CT一致性fixture没有本次事件的可用医嘱关联。
        "LX0609-06-01-01": ("data_gap", "required_field_missing"),
        # 入口测试的脱敏 fixture 有已执行检查但没有正式影像报告。
        "LX0609-06-01-03": ("data_gap", "target_report_missing"),
        # 微生物 fixture 缺少可唯一关联主记录与报告的业务键。
        "LX0609-06-03-02": ("data_gap", "association_failed"),
    }
)


RULE_ID = "LX0609-06-01-05"
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
        LUXIAN_0609_FAMILY_MAX_CONCURRENCY=4,
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


class _DeterministicExamLabFactClient:
    """仅替代受控语义响应；prepare、engine、worker 与持久化仍为正式实现。"""

    def __init__(self, rule_id: str) -> None:
        self.rule_id = rule_id
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> dict[str, object]:
        self.prompts.append(prompt)
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "schema_version": "lx0609-exam-lab-text-facts-v3",
                                "facts": [
                                    {
                                        "rule_id": self.rule_id,
                                        "applicability": "applicable",
                                        "semantic_state": "present",
                                        "positive_state": (
                                            "positive"
                                            if self.rule_id
                                            in {"LX0609-06-01-05", "LX0609-06-03-04"}
                                            else "not_relevant"
                                        ),
                                        "course_doc_positions": [
                                            1
                                            if self.rule_id == "LX0609-06-01-02"
                                            else 2
                                        ],
                                    }
                                ],
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 10,
                "total_tokens": 110,
            },
            "_api_time": 0.2,
        }


class _DeterministicCtFactClient:
    """仅固定 CT 语义事实，保留正式执行和 Token 统计。"""

    def __init__(self, record_state: str) -> None:
        self.record_state = record_state
        self.prompts: list[str] = []

    async def generate(self, prompt: str, *, allow_length_retry: bool = False) -> dict[str, object]:
        assert allow_length_retry is False
        self.prompts.append(prompt)
        return {
            "content": json.dumps({
                "schema_version": CT_SCHEMA_VERSION,
                "events": [{
                    "event_position": 1,
                    "order_position": 1,
                    "record_state": self.record_state,
                    "clause_ids": ["C1"],
                }],
                "unmatched_current_clause_ids": [],
            }, ensure_ascii=False),
            "usage": {"prompt_tokens": 100, "completion_tokens": 20},
            "_api_time": 0.01,
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
                    if rule_id in {"LX0609-06-01-05", "LX0609-06-03-04"}
                    else "not_relevant"
                ),
                "course_doc_positions": [1 if rule_id == "LX0609-06-01-02" else 2],
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
    assert context.unified_engine_used is True
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
    assert "LX0609-06-01-02" not in dict(context.customer_display_facts)

    expected_facts = {
        rule_id: {
            "verification_kind": "exam_lab_requirement_checked",
            "subject": (
                "ct_mri"
                if rule_id in {"LX0609-06-01-04", "LX0609-06-01-05"}
                else "culture_susceptibility"
            ),
            "requirement": (
                "positive_result_analysis_within_24h"
                if rule_id in {"LX0609-06-01-05", "LX0609-06-03-04"}
                else "result_recording_within_24h"
            ),
            "event_phase": "report",
            "checked_sources": ["exam_lab_report", "course_record"],
            "applicable": True,
            "requirement_met": True,
            "positive_state": (
                "positive"
                if rule_id in {"LX0609-06-01-05", "LX0609-06-03-04"}
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
        for rule_id in ("LX0609-06-01-04", "LX0609-06-01-05", "LX0609-06-03-03", "LX0609-06-03-04")
    }
    expected_evidence_coordinates = {
        "LX0609-06-01-02": [
            (
                "exam_master",
                f"EXAM-REPORT-{_RECORD_A['visit_id']}",
                "exam_conclusion",
                "2026-07-02 08:00:00",
            )
        ],
        "LX0609-06-01-04": [
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
        "LX0609-06-01-05": [],
        "LX0609-06-03-03": [
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
        "LX0609-06-03-04": [],
    }
    expected_evidence_coordinates["LX0609-06-01-05"] = list(
        expected_evidence_coordinates["LX0609-06-01-04"]
    )
    expected_evidence_coordinates["LX0609-06-03-04"] = list(
        expected_evidence_coordinates["LX0609-06-03-03"]
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
        # customer_evidence 的批准合同是去重后的证据坐标集合；数组位置不
        # 表示证据优先级。数量与坐标必须完全等价，不能丢失或增加文书。
        expected_coordinates = expected_evidence_coordinates[item["rule_id"]]
        assert len(evidence_coordinates) == len(expected_coordinates)
        assert set(evidence_coordinates) == set(expected_coordinates)
        if item["rule_id"] == "LX0609-06-01-02":
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


def _ct_evidence_session_builder(monkeypatch: pytest.MonkeyPatch, *, course_body: str) -> None:
    """以完整医嘱、检查主记录、正式报告和病程运行正式快照会话。"""

    original = luxian_execution.build_luxian_0609_evidence_read_session

    def read_fixture(**kwargs: Any) -> SnapshotSourceRows:
        source_key = str(kwargs["source_key"])
        visit_id = str(kwargs["visit_id"])
        assert visit_id in {_RECORD_A["visit_id"], _RECORD_B["visit_id"]}
        rows: list[dict[str, str]] = []
        if source_key == ORDER_SOURCE:
            rows = [{"order_id": "ORDER-001", "order_name": "左膝CT", "order_status": "新开"}]
        elif source_key == "exam_master":
            rows = [{"exam_id": "EXAM-001", "order_id": "ORDER-001"}]
        elif source_key == "exam_item_report":
            rows = [{
                "exam_id": "EXAM-001", "description": "左膝骨折。",
                "report_time": "2026-07-02T09:00:00+08:00",
            }]
        elif source_key == "daily_course_record":
            rows = [{"document_id": f"COURSE-{visit_id}", "record_content": course_body}]
        elif source_key in {"evaluation_context.horizon", "inpat_registration.discharge_horizon"}:
            rows = _rows_for_source(source_key=source_key, visit_id=visit_id, explicit_course=True)
        return SnapshotSourceRows.create(
            source_key=source_key, rows=rows, truncated=False, limit_rows=50
        )

    def build_with_fixture_reader(**kwargs: Any) -> Any:
        return original(**kwargs, row_reader=read_fixture)

    monkeypatch.setattr(
        luxian_execution, "build_luxian_0609_evidence_read_session", build_with_fixture_reader
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

    for model in (
        MedicalRecordFrontpage,
        AdmissionRecord,
        DischargeRecord,
        InpatRegistration,
    ):
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


def _create_ready_exam_lab_sample_pool(
    *, engine: sa.Engine, service: CustomQCSamplePoolService
) -> tuple[str, str]:
    """通过正式样本池服务建立只含脱敏三坐标的可运行样本。"""

    pool = service.create_pool_with_items(
        name="检查检验 API 入口隔离样本",
        source_file="isolated-exam-lab-fixture.xlsx",
        source_sheet="Sheet1",
        created_by="api-entry-test-user",
        scene="final",
        rows=[
            {
                "row_no": 1,
                "patient_name": "脱敏患者",
                "manual_issue_text": "检查检验结果记录完整性核验",
            }
        ],
    )
    pool_id = str(pool["id"])
    with Session(engine) as session:
        item_id = session.execute(
            sa.select(service._item_table.c.id).where(
                service._item_table.c.pool_id == pool_id
            )
        ).scalar_one()
        session.execute(
            sa.update(service._item_table)
            .where(service._item_table.c.id == item_id)
            .values(
                matched_institute_id=_RECORD_A["institute_id"],
                matched_patient_id=_RECORD_A["patient_id"],
                matched_visit_id=_RECORD_A["visit_id"],
                match_status="matched",
                sync_status="synced",
                bundle_status="ready",
            )
        )
        session.commit()
    return pool_id, str(item_id)


def _job_filters(
    *,
    rule_id: str,
    record_refs: list[dict[str, str]],
    sample_pool_id: str = "",
) -> dict[str, Any]:
    filters: dict[str, Any] = {
        "rule_ids": [rule_id],
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
        "scoped_customer_rule_ids": [rule_id],
        "selected_rule_ids": [rule_id],
        "record_rule_map": {
            f"{item['institute_id']}::{item['patient_id']}::{item['visit_id']}": [
                rule_id
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
    rule_id: str,
    record_refs: list[dict[str, str]],
    execution_mode: str,
    run_mode: str,
    sample_pool_id: str = "",
) -> dict[str, Any]:
    job = workspace.create_batch_job(
        draft={
            "id": f"EXAM-{name}",
            "rule_code": rule_id,
            "name": "CT/MRI阳性结果分析",
            "scene": "final",
        },
        created_by="exam-lab-isolated-test",
        scope="final",
        filters=_job_filters(
            rule_id=rule_id,
            record_refs=record_refs,
            sample_pool_id=sample_pool_id,
        ),
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


def _canonical_saved_item(
    job: dict[str, Any], *, visit_id: str, rule_id: str
) -> dict[str, Any]:
    items = [
        item
        for item in list(job.get("items") or [])
        if str(item.get("visit_id") or "") == visit_id
        and str(item.get("rule_id") or "") == rule_id
    ]
    assert len(items) == 1
    return items[0]


def _canonical_projection(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": item.get("status"),
        "reason_code": item.get("reason_code"),
        "customer_display_facts": item.get("customer_display_facts"),
        "criterion_results": item.get("criterion_results"),
    }


def _customer_evidence_coordinate_set(item: dict[str, Any]) -> set[tuple[str, str, str, str]]:
    """证据数组排序不表达优先级；只冻结可定位的坐标集合。"""

    return {
        (
            str(evidence.get("source_type") or ""),
            str(
                evidence.get("source_document_id")
                or evidence.get("source_ref")
                or ""
            ),
            str(evidence.get("field_path") or ""),
            str(evidence.get("record_time") or ""),
        )
        for evidence in list(item.get("customer_evidence") or [])
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("rule_id", EXAM_LAB_RULE_IDS)
async def test_exam_lab_formal_worker_is_consistent_across_three_business_entries(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, rule_id: str
) -> None:
    """每条检查检验规则均经三入口走 exam_lab 并保存同一 Canonical 结果。"""

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
    service.adjudicator_client = _DeterministicExamLabFactClient(rule_id)

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
        name=f"single-rule-{rule_id}",
        rule_id=rule_id,
        record_refs=[_RECORD_A],
        execution_mode="single",
        run_mode="serial",
    )
    pool_batch_job = await _run_formal_job(
        workspace=workspace,
        service=service,
        name=f"record-pool-batch-{rule_id}",
        rule_id=rule_id,
        record_refs=[_RECORD_A, _RECORD_B],
        execution_mode="multi",
        run_mode="parallel",
    )
    sample_leaf_job = await _run_formal_job(
        workspace=workspace,
        service=service,
        name=f"sample-validation-leaf-{rule_id}",
        rule_id=rule_id,
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
        item = _canonical_saved_item(
            job, visit_id=_RECORD_A["visit_id"], rule_id=rule_id
        )
        assert item["status"] == "compliant"
        assert item["reason_code"] == "requirement_satisfied"
        assert (item.get("metadata") or {}).get("executor_key") == "exam_lab"
        assert not item.get("llm_fallback")
        assert not item.get("pack_fallback")
        assert not (item.get("metadata") or {}).get("bundle_fallback")
        assert "legacy" not in str(item.get("metadata") or {}).lower()
        assert list(item.get("customer_evidence") or [])

    single_item = _canonical_saved_item(
        single_job, visit_id=_RECORD_A["visit_id"], rule_id=rule_id
    )
    pool_item = _canonical_saved_item(
        pool_batch_job, visit_id=_RECORD_A["visit_id"], rule_id=rule_id
    )
    sample_item = _canonical_saved_item(
        sample_leaf_job, visit_id=_RECORD_A["visit_id"], rule_id=rule_id
    )
    assert _canonical_projection(single_item) == _canonical_projection(pool_item)
    assert _canonical_projection(single_item) == _canonical_projection(sample_item)
    assert _customer_evidence_coordinate_set(single_item)
    assert _customer_evidence_coordinate_set(single_item) == _customer_evidence_coordinate_set(
        pool_item
    ) == _customer_evidence_coordinate_set(sample_item)

    latest = workspace.get_latest_luxian_0609_record_result(
        institute_id=_RECORD_A["institute_id"],
        patient_id=_RECORD_A["patient_id"],
        visit_id=_RECORD_A["visit_id"],
        expected_rule_ids=[rule_id],
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


@pytest.mark.integration
@pytest.mark.parametrize("rule_id", EXECUTABLE_EXAM_LAB_RULE_IDS)
def test_exam_lab_asgi_entries_create_same_selection_and_dispatch_formal_worker(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, rule_id: str
) -> None:
    """每条检查检验规则均经三条实际创建路由保存同一 Canonical 结果。"""

    workspace = _install_isolated_sqlite(monkeypatch, tmp_path)
    engine = workspace_module.engine
    sample_pool_service = _install_sample_pool_sqlite(monkeypatch, engine=engine)
    _fixture_evidence_session_builder(monkeypatch)
    settings = _formal_settings()
    monkeypatch.setattr(batch_worker, "get_settings", lambda: settings)
    monkeypatch.setattr(sichuan_qc_service, "get_settings", lambda: settings)
    monkeypatch.setattr(qc_sichuan, "get_settings", lambda: settings)
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
    monkeypatch.setattr(
        sample_pool_module,
        "get_settings",
        lambda: SimpleNamespace(JWT_SECRET="isolated-api-entry-test-secret"),
    )
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(qc_sample_pools, "_workspace_service", lambda: workspace)
    monkeypatch.setattr(qc_sample_pools, "_service", lambda: sample_pool_service)

    service = sichuan_qc_service.SichuanQCService(
        {
            "provider_code": "isolated-test",
            "model": "controlled-stub",
            "allow_mock_when_unconfigured": True,
            "source": "exam-lab-api-entry-isolated",
        }
    )
    service.adjudicator_client = _DeterministicExamLabFactClient(rule_id)

    async def provide_qc_service() -> Any:
        return service

    # 路由注入与 detached worker 都使用同一受控服务；派发函数保持生产实现。
    monkeypatch.setattr(qc_sichuan, "get_qc_service", provide_qc_service)
    native_phase_events: list[tuple[str, dict[str, Any]]] = []
    unified_execution_calls: list[tuple[tuple[str, tuple[str, ...]], ...]] = []
    original_update_progress = workspace.update_batch_job_progress
    original_unified_execute = luxian_execution.Luxian0609ExecutionEngine.execute

    async def capture_unified_execute(
        engine: luxian_execution.Luxian0609ExecutionEngine, *args: Any, **kwargs: Any
    ) -> Any:
        unified_execution_calls.append(
            tuple(
                (str(executor_key), tuple(rule_ids))
                for executor_key, rule_ids in tuple(
                    kwargs.get("executor_batches") or ()
                )
            )
        )
        return await original_unified_execute(engine, *args, **kwargs)

    monkeypatch.setattr(
        luxian_execution.Luxian0609ExecutionEngine,
        "execute",
        capture_unified_execute,
    )

    def capture_update_progress(**kwargs: Any) -> None:
        stream_state = dict(
            (kwargs.get("summary_patch") or {}).get("stream_state") or {}
        )
        if stream_state.get("kind") == "native_executor_phase":
            native_phase_events.append((str(kwargs.get("job_id") or ""), stream_state))
        original_update_progress(**kwargs)

    monkeypatch.setattr(workspace, "update_batch_job_progress", capture_update_progress)
    pool_id, sample_item_id = _create_ready_exam_lab_sample_pool(
        engine=engine, service=sample_pool_service
    )
    app = _api_app(service=service)

    def create_workspace_job(record_refs: list[dict[str, str]]) -> str:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/qc/sichuan/workspace/batch-jobs",
                json={
                    "rule_set_key": LUXIAN_0609_RULE_SET_KEY,
                    "rule_ids": [rule_id],
                    "scope": "final",
                    "record_refs": record_refs,
                    "run_mode": "serial",
                },
            )
        assert response.status_code == 200, response.text
        assert response.json()["success"] is True
        return str(response.json()["data"]["id"])

    single_job_id = create_workspace_job([_RECORD_A])
    single_job = _wait_for_terminal_job(workspace=workspace, job_id=single_job_id)
    single_item = _canonical_saved_item(
        single_job, visit_id=_RECORD_A["visit_id"], rule_id=rule_id
    )
    single_envelope = _read_saved_envelope(
        app=app,
        job_id=single_job_id,
        task_item=single_item,
        record=_RECORD_A,
        expected_rule_ids=[rule_id],
    )

    pool_job_id = create_workspace_job([_RECORD_A, _RECORD_B])
    pool_job = _wait_for_terminal_job(workspace=workspace, job_id=pool_job_id)
    pool_item = _canonical_saved_item(
        pool_job, visit_id=_RECORD_A["visit_id"], rule_id=rule_id
    )
    pool_envelope = _read_saved_envelope(
        app=app,
        job_id=pool_job_id,
        task_item=pool_item,
        record=_RECORD_A,
        expected_rule_ids=[rule_id],
    )

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/qc/sample-pools/{pool_id}/run",
            json={
                "validation_mode": "customer",
                "rule_set_key": LUXIAN_0609_RULE_SET_KEY,
                "selected_rule_ids": [rule_id],
                "sample_item_ids": [sample_item_id],
                "record_refs": [_RECORD_A],
                "group_by_luxian_family": False,
            },
        )
    assert response.status_code == 200, response.text
    assert response.json()["success"] is True
    sample_job_id = str(response.json()["data"]["job_id"])
    sample_job = _wait_for_terminal_job(workspace=workspace, job_id=sample_job_id)
    sample_item = _canonical_saved_item(
        sample_job, visit_id=_RECORD_A["visit_id"], rule_id=rule_id
    )
    sample_envelope = _read_saved_envelope(
        app=app,
        job_id=sample_job_id,
        task_item=sample_item,
        record=_RECORD_A,
        expected_rule_ids=[rule_id],
    )

    record_a_key = json.dumps(
        [_RECORD_A["institute_id"], _RECORD_A["patient_id"], _RECORD_A["visit_id"]],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    record_b_key = json.dumps(
        [_RECORD_B["institute_id"], _RECORD_B["patient_id"], _RECORD_B["visit_id"]],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    for job, expected_record_keys in (
        (single_job, {record_a_key}),
        (pool_job, {record_a_key, record_b_key}),
        (sample_job, {record_a_key}),
    ):
        assert job["status"] == "completed", job.get("error_message")
        assert not list(job.get("failed_records") or [])
        filters = dict(job.get("filters") or {})
        assert filters.get("rule_set_key") == LUXIAN_0609_RULE_SET_KEY
        assert filters.get("rule_ids") == [rule_id]
        assert filters.get("selected_rule_ids") == [rule_id]
        assert filters.get("scoped_customer_rule_ids") == [rule_id]
        assert filters.get("record_rule_map") == {
            record_key: [rule_id] for record_key in expected_record_keys
        }
        assert any(
            event_job_id == job["id"]
            and event.get("event") == "completed"
            and event.get("executor_key") == "exam_lab"
            for event_job_id, event in native_phase_events
        )

    for item in (single_item, pool_item, sample_item):
        assert (item["status"], item["reason_code"]) == _ASGI_EXPECTED_OUTCOMES[
            rule_id
        ]
        assert (item.get("metadata") or {}).get("executor_key") == "exam_lab"
        assert not item.get("llm_fallback")
        assert not item.get("pack_fallback")
        assert not (item.get("metadata") or {}).get("bundle_fallback")
        assert "legacy" not in str(item.get("metadata") or {}).lower()

    assert _canonical_projection(single_item) == _canonical_projection(pool_item)
    assert _canonical_projection(single_item) == _canonical_projection(sample_item)
    assert _customer_evidence_coordinate_set(single_item)
    assert _customer_evidence_coordinate_set(single_item) == _customer_evidence_coordinate_set(
        pool_item
    ) == _customer_evidence_coordinate_set(sample_item)
    assert _envelope_customer_projection(single_envelope) == _envelope_customer_projection(
        pool_envelope
    ) == _envelope_customer_projection(sample_envelope)
    assert len(unified_execution_calls) == 4
    assert all(
        batches == (("exam_lab", (rule_id,)),)
        for batches in unified_execution_calls
    )


@pytest.mark.integration
@pytest.mark.parametrize(
    "record_state,course_body,expected_status,expected_reason",
    [
        (
            "consistent_description", "ORDER-001左膝CT完成。",
            "compliant", "requirement_satisfied",
        ),
        (
            "contradictory_description", "ORDER-001实际为右膝CT，与医嘱左膝不一致。",
            "non_compliant", "requirement_violated",
        ),
    ],
)
def test_ct_semantic_decision_survives_three_asgi_entries_and_latest_read(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    record_state: str,
    course_body: str,
    expected_status: str,
    expected_reason: str,
) -> None:
    """CT 语义判定经工作台、病历池、样本池写入并从公开 latest 读回。"""

    rule_id = "LX0609-06-01-01"
    workspace = _install_isolated_sqlite(monkeypatch, tmp_path)
    engine = workspace_module.engine
    sample_pool_service = _install_sample_pool_sqlite(monkeypatch, engine=engine)
    _ct_evidence_session_builder(monkeypatch, course_body=course_body)
    # 本用例只验收冻结资料/SQLite；旧timeline回退不得访问医院数据库。
    monkeypatch.setattr(sample_programmatic_evidence, "engine", None)
    settings = _formal_settings()
    monkeypatch.setattr(batch_worker, "get_settings", lambda: settings)
    monkeypatch.setattr(sichuan_qc_service, "get_settings", lambda: settings)
    monkeypatch.setattr(qc_sichuan, "get_settings", lambda: settings)
    monkeypatch.setattr(batch_worker, "get_product_activation_service", lambda: _ActivationStub())
    monkeypatch.setattr(
        sichuan_qc_service, "build_adjudicator_runtime_config", lambda config: dict(config or {})
    )
    monkeypatch.setattr(
        batch_worker,
        "load_running_final_bundle",
        lambda *, institute_id, patient_id, visit_id, **_kwargs: _bundle_for_record(
            visit_id=str(visit_id), patient_id=str(patient_id)
        ),
    )
    monkeypatch.setattr(
        sample_pool_module, "get_settings",
        lambda: SimpleNamespace(JWT_SECRET="isolated-api-entry-test-secret"),
    )
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(qc_sample_pools, "_workspace_service", lambda: workspace)
    monkeypatch.setattr(qc_sample_pools, "_service", lambda: sample_pool_service)
    service = sichuan_qc_service.SichuanQCService({
        "provider_code": "isolated-test", "model": "controlled-stub",
        "allow_mock_when_unconfigured": True, "source": "ct-api-entry-isolated",
    })
    fact_client = _DeterministicCtFactClient(record_state)
    service.adjudicator_client = fact_client

    async def provide_qc_service() -> Any:
        return service

    monkeypatch.setattr(qc_sichuan, "get_qc_service", provide_qc_service)
    pool_id, sample_item_id = _create_ready_exam_lab_sample_pool(
        engine=engine, service=sample_pool_service
    )
    app = _api_app(service=service)

    def create_workspace_job(record_refs: list[dict[str, str]]) -> str:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/qc/sichuan/workspace/batch-jobs",
                json={
                    "rule_set_key": LUXIAN_0609_RULE_SET_KEY,
                    "rule_ids": [rule_id], "scope": "final",
                    "record_refs": record_refs, "run_mode": "serial",
                },
            )
        assert response.status_code == 200, response.text
        assert response.json()["success"] is True
        return str(response.json()["data"]["id"])

    single_job_id = create_workspace_job([_RECORD_A])
    single_job = _wait_for_terminal_job(workspace=workspace, job_id=single_job_id)
    assert single_job["status"] == "completed", single_job
    single_item = _canonical_saved_item(
        single_job, visit_id=_RECORD_A["visit_id"], rule_id=rule_id
    )
    single_envelope = _read_saved_envelope(
        app=app, job_id=single_job_id, task_item=single_item,
        record=_RECORD_A, expected_rule_ids=[rule_id],
    )
    pool_job_id = create_workspace_job([_RECORD_A, _RECORD_B])
    pool_job = _wait_for_terminal_job(workspace=workspace, job_id=pool_job_id)
    pool_item = _canonical_saved_item(
        pool_job, visit_id=_RECORD_A["visit_id"], rule_id=rule_id
    )
    pool_envelope = _read_saved_envelope(
        app=app, job_id=pool_job_id, task_item=pool_item,
        record=_RECORD_A, expected_rule_ids=[rule_id],
    )
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/qc/sample-pools/{pool_id}/run",
            json={
                "validation_mode": "customer", "rule_set_key": LUXIAN_0609_RULE_SET_KEY,
                "selected_rule_ids": [rule_id], "sample_item_ids": [sample_item_id],
                "record_refs": [_RECORD_A], "group_by_luxian_family": False,
            },
        )
    assert response.status_code == 200, response.text
    assert response.json()["success"] is True
    sample_job_id = str(response.json()["data"]["job_id"])
    sample_job = _wait_for_terminal_job(workspace=workspace, job_id=sample_job_id)
    sample_item = _canonical_saved_item(
        sample_job, visit_id=_RECORD_A["visit_id"], rule_id=rule_id
    )
    items = [single_item, pool_item, sample_item]
    assert all(job["status"] == "completed" and not job.get("failed_records")
               for job in (single_job, pool_job, sample_job))
    assert len(fact_client.prompts) == 4
    for item in items:
        assert (item["status"], item["reason_code"]) == (expected_status, expected_reason)
        assert (item.get("metadata") or {}).get("executor_key") == "exam_lab"
        facts = item["customer_display_facts"]
        assert len(facts["order_results"]) == 1
        order = facts["order_results"][0]
        assert order["status"] == expected_status
        assert order["order_reference_positions"]
        assert len(order["course_locations"]) == 1
        assert order["course_locations"][0]["clause_id"] == "C1"
        assert _customer_evidence_coordinate_set(item)
    assert _canonical_projection(items[0]) == _canonical_projection(items[1]) == _canonical_projection(items[2])
    assert _customer_evidence_coordinate_set(items[0]) == _customer_evidence_coordinate_set(items[1]) == _customer_evidence_coordinate_set(items[2])

    envelope = _read_saved_envelope(
        app=app, job_id=sample_job_id, task_item=sample_item,
        record=_RECORD_A, expected_rule_ids=[rule_id],
    )
    assert _envelope_customer_projection(single_envelope) == _envelope_customer_projection(pool_envelope) == _envelope_customer_projection(envelope)
    assert (envelope["status"], envelope["reason_code"]) == (expected_status, expected_reason)
    assert envelope["customer_display_facts"] == items[2]["customer_display_facts"]
    order = envelope["customer_display_facts"]["order_results"][0]
    evidence = list(envelope["evidence"])
    positions = set(order["order_reference_positions"])
    assert any(positions <= set(row["decision_reference_positions"]) for row in evidence)
    location = order["course_locations"][0]
    assert any(
        row["source_type"] == "daily_course_record"
        and location["reference_position"] in row["decision_reference_positions"]
        and re.fullmatch(r"src_[0-9a-f]{24}", row["source_ref"])
        and "source_document_id" not in row
        for row in evidence
    )
    assert course_body[location["start"]:location["end"]] == course_body
