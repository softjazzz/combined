"""LX0609 会诊规则族的三业务入口隔离验收。

该测试刻意不连接 .env、PostgreSQL 或真实模型：

* 工作台任务、任务进度与 Canonical Envelope 写入临时 SQLite；
* 正式 worker、Running/Final 稳定门面、prepare 和会诊 episode executor 均不替换；
* 仅以固定的脱敏 source fixture 代替医院资料读取，以保证可重复。

这不是对旧链的模拟完成测试。若正式主链不能在 SQLite 隔离环境中形成可保存的
会诊结果，测试必须失败，不允许以伪造的 complete_batch_job 代替执行。
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
from types import SimpleNamespace
from typing import Any

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.database.models.cdm import AdmissionRecord, DischargeRecord, MedicalRecordFrontpage
from app.services import custom_qc_workspace_service as workspace_module
from app.services import sichuan_qc_service
from app.services import sichuan_workspace_batch_worker as batch_worker
from app.services.custom_qc_workspace_service import CustomQCWorkspaceService
from app.services.luxian_0609 import execution as luxian_execution
from app.services.luxian_0609.evidence_snapshot_provider import SnapshotSourceRows
from app.services.luxian_0609_rule_catalog import LUXIAN_0609_RULE_SET_KEY


RULE_ID = "LX0609-022"
RULE_SET_VERSION = "2026-06-09"
_RECORD_A = {"institute_id": "B3-HOSPITAL", "patient_id": "B3-PATIENT-A", "visit_id": "B3-VISIT-A"}
_RECORD_B = {"institute_id": "B3-HOSPITAL", "patient_id": "B3-PATIENT-B", "visit_id": "B3-VISIT-B"}


def _formal_settings() -> SimpleNamespace:
    """只提供正式 Native 会诊链实际读取的配置，禁止从 .env 取设置。"""

    return SimpleNamespace(
        LUXIAN_0609_MAINLINE_RULE_DECISION_ENABLED=True,
        LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED=True,
        LUXIAN_0609_NATIVE_EXECUTION_ENABLED=True,
        LUXIAN_0609_NATIVE_CONSULTATION_ENABLED=True,
        LUXIAN_0609_CONSULTATION_EXECUTION_LINK_ENABLED=True,
        LUXIAN_0609_UNIFIED_ENGINE_ENABLED=True,
        LUXIAN_0609_RULE_DECISION_CONSULTATION_ENABLED=True,
        LUXIAN_0609_TRIGGER_GATE_ENABLED=False,
        LUXIAN_0609_LLM_TRIGGER_GATE_ENABLED=False,
        LUXIAN_0609_EVIDENCE_FORMATTER_ENABLED=False,
        LUXIAN_0609_RUNTIME_SHADOW_ENABLED=False,
    )


class _ActivationStub:
    def enforce(self) -> None:
        return None


def _consultation_row(*, visit_id: str) -> dict[str, str]:
    return {
        "institute_id": _RECORD_A["institute_id"],
        "patient_id": _RECORD_A["patient_id"],
        "visit_id": visit_id,
        "document_id": f"DOC-{visit_id}",
        "document_title": "会诊记录单",
        "record_time": "2026-07-02 09:30:00",
        "record_content": "感染科医师会诊后指出：考虑既往感染，继续保肝治疗，我科随访。",
    }


def _fixture_evidence_session_builder(monkeypatch: pytest.MonkeyPatch) -> None:
    """保留正式 session builder，只将物理 source reader 换为脱敏 fixture。"""

    original = luxian_execution.build_luxian_0609_evidence_read_session

    def read_fixture(**kwargs: Any) -> SnapshotSourceRows:
        source_key = str(kwargs["source_key"])
        visit_id = str(kwargs["visit_id"])
        assert visit_id in {_RECORD_A["visit_id"], _RECORD_B["visit_id"]}
        return SnapshotSourceRows.create(
            source_key=source_key,
            # consultation_quality 还会请求其历史执行器材料 daily_course_record；
            # 它并非本例 022 的判定来源，因此以真实的“零行已读取”表达。
            rows=[_consultation_row(visit_id=visit_id)] if source_key == "consultation_record" else [],
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
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> tuple[sa.Engine, CustomQCWorkspaceService]:
    database_path = tmp_path / "lx0609-consultation-b3.sqlite3"
    database_url = f"sqlite+pysqlite:///{database_path.as_posix()}"
    # 显式防呆：B3 不得因环境变量或默认连接误连任何 PG 数据库。
    if not database_url.startswith("sqlite"):
        raise RuntimeError("B3 integration test only permits a SQLite database URL")

    engine = sa.create_engine(database_url, future=True)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    # 工作台服务导入时绑定了连接对象；测试必须同时替换并清除表定义缓存。
    monkeypatch.setattr(workspace_module, "engine", engine)
    monkeypatch.setattr(workspace_module, "SessionLocal", session_local)
    monkeypatch.setattr(workspace_module, "DB_SCHEMA_MODE", "single")
    workspace_module._drafts_table.cache_clear()
    workspace_module._batch_jobs_table.cache_clear()
    workspace_module._record_result_envelopes_table.cache_clear()
    # SQLite 不支持 PostgreSQL 的 ADD COLUMN IF NOT EXISTS；完整表定义已由本测试创建。
    monkeypatch.setattr(workspace_module, "_sync_batch_job_parent_columns", lambda **_kwargs: None)

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
                    discharge_datetime=datetime(2026, 7, 3, 8, 0, 0),
                    admission_dept_name="内科",
                    discharge_dept_name="内科",
                    attending_physician_sign="脱敏医师",
                    record_content="脱敏病历摘要",
                )
            )
        session.commit()

    workspace = CustomQCWorkspaceService()
    workspace._record_result_envelope_table.create(bind=engine, checkfirst=True)
    return engine, workspace


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
                "document_type": "会诊记录",
                "content": "脱敏病历摘要",
            }
        ],
    }


def _job_filters(*, record_refs: list[dict[str, str]], sample_pool_id: str = "") -> dict[str, Any]:
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
            f"{item['institute_id']}::{item['patient_id']}::{item['visit_id']}": [RULE_ID]
            for item in record_refs
        },
    }
    if sample_pool_id:
        filters.update(
            {
                "sample_pool_id": sample_pool_id,
                "source": "manual_problem_sample_pool",
                "selected_sample_item_ids": ["B3-SAMPLE-1"],
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
    job_kind: str = "leaf",
    sample_pool_id: str = "",
) -> dict[str, Any]:
    job = workspace.create_batch_job(
        draft={
            "id": f"B3-{name}",
            "rule_code": RULE_ID,
            "name": "会诊意见明确性",
            "scene": "final",
        },
        created_by="b3-isolated-test",
        scope="final",
        filters=_job_filters(record_refs=record_refs, sample_pool_id=sample_pool_id),
        record_ids=[item["visit_id"] for item in record_refs],
        record_refs=record_refs,
        total_records=len(record_refs),
        execution_mode=execution_mode,
        run_mode=run_mode,
        rule_count=1,
        job_kind=job_kind,
        family_key="consultation_quality" if sample_pool_id else None,
        family_name="会诊质量" if sample_pool_id else None,
    )

    async def provide_service() -> Any:
        return service

    await batch_worker.run_sichuan_workspace_batch_job(
        str(job["id"]),
        workspace=workspace,
        qc_service_provider=provide_service,
    )
    persisted = workspace.get_batch_job_for_processing(job_id=str(job["id"]))
    assert persisted is not None
    return persisted


def _canonical_saved_item(job: dict[str, Any], *, visit_id: str) -> dict[str, Any]:
    items = [
        item
        for item in list(job.get("items") or [])
        if str(item.get("visit_id") or "") == visit_id and str(item.get("rule_id") or "") == RULE_ID
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


def _evidence_coordinates(item: dict[str, Any], *, envelope: bool) -> list[dict[str, str]]:
    """按交付层合同比较证据坐标，不将任务内原始文书 ID 泄露到 Envelope。"""

    evidence_key = "evidence" if envelope else "customer_evidence"
    return [
        {
            "source_type": str(evidence.get("source_type") or ""),
            "field_path": str(evidence.get("field_path") or ""),
            "record_time": str(evidence.get("record_time") or ""),
        }
        for evidence in list(item.get(evidence_key) or [])
        if isinstance(evidence, dict)
    ]


def _assert_safe_envelope_evidence(
    *,
    envelope_item: dict[str, Any],
    task_item: dict[str, Any],
) -> None:
    """Envelope 只允许安全引用，坐标必须与任务内原始证据等价。"""

    envelope_evidence = list(envelope_item.get("evidence") or [])
    task_evidence = list(task_item.get("customer_evidence") or [])
    assert envelope_evidence
    # Envelope 同时允许保存调试辅助证据；只要求任务 customer_evidence 的每个
    # 文书坐标均被安全投影，不能把额外的非客户展示辅助事实误判为不一致。
    envelope_coordinates = _evidence_coordinates(envelope_item, envelope=True)
    task_coordinates = _evidence_coordinates(task_item, envelope=False)
    assert task_coordinates
    assert {
        (row["source_type"], row["field_path"], row["record_time"])
        for row in task_coordinates
    }.issubset(
        {
            (row["source_type"], row["field_path"], row["record_time"])
            for row in envelope_coordinates
        }
    )
    original_document_ids = {
        str(row.get("source_document_id") or "")
        for row in task_evidence
        if isinstance(row, dict) and str(row.get("source_document_id") or "")
    }
    assert original_document_ids
    for evidence in envelope_evidence:
        assert isinstance(evidence, dict)
        source_ref = str(evidence.get("source_ref") or "")
        assert re.fullmatch(r"src_[0-9a-f]{24}", source_ref)
        assert "source_document_id" not in evidence
        assert all(document_id not in source_ref for document_id in original_document_ids)


@pytest.mark.asyncio
async def test_consultation_quality_formal_worker_is_consistent_across_three_business_entries(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """同一会诊资料经三入口均走 Native episode executor 并保存同一 Canonical 结果。"""

    _engine, workspace = _install_isolated_sqlite(monkeypatch, tmp_path)
    _fixture_evidence_session_builder(monkeypatch)
    settings = _formal_settings()
    monkeypatch.setattr(batch_worker, "get_settings", lambda: settings)
    monkeypatch.setattr(sichuan_qc_service, "get_settings", lambda: settings)
    monkeypatch.setattr(batch_worker, "get_product_activation_service", lambda: _ActivationStub())
    # 服务构造时使用同一受控配置，禁止测试透过二审配置加载器触碰 .env。
    monkeypatch.setattr(
        sichuan_qc_service,
        "build_adjudicator_runtime_config",
        lambda config: dict(config or {}),
    )
    monkeypatch.setattr(
        batch_worker,
        "load_running_final_bundle",
        lambda *, institute_id, patient_id, visit_id, **_kwargs: _bundle_for_record(
            visit_id=str(visit_id),
            patient_id=str(patient_id),
        ),
    )

    controlled_llm_config = {
        "provider_code": "isolated-test",
        "model": "controlled-stub",
        "allow_mock_when_unconfigured": True,
        "source": "b3-isolated",
    }
    service = sichuan_qc_service.SichuanQCService(controlled_llm_config)

    # 不改写 worker；仅旁路观察其真实的持久化进度调用，验证任务确实报告了
    # consultation_quality 的 Native 阶段，而不是只在最终 items 中伪造状态。
    native_phase_events: list[tuple[str, dict[str, Any]]] = []
    original_update_progress = workspace.update_batch_job_progress

    def capture_update_progress(**kwargs: Any) -> None:
        stream_state = dict((kwargs.get("summary_patch") or {}).get("stream_state") or {})
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
        job_kind="leaf",
        sample_pool_id="B3-POOL",
    )

    for job in (single_job, pool_batch_job, sample_leaf_job):
        assert any(
            event_job_id == job["id"]
            and event.get("event") == "completed"
            and event.get("executor_key") == "consultation_quality"
            for event_job_id, event in native_phase_events
        )

    for job in (single_job, pool_batch_job, sample_leaf_job):
        assert job["status"] == "completed"
        assert not list(job.get("failed_records") or [])
        assert (job.get("summary") or {}).get("rule_set_key") == LUXIAN_0609_RULE_SET_KEY
        # Worker 完成时会用最终汇总覆盖 stream_state；完整 Native 阶段事件已由
        # 上方真实的 update_batch_job_progress 调用观察，不能误读此最终进度快照。
        trace = ((job.get("summary") or {}).get("stream_state") or {})
        assert trace.get("processed_records") == job["total_records"]

        for item in list(job.get("items") or []):
            assert item["status"] == "compliant"
            assert item["reason_code"] == "requirement_satisfied"
            metadata = dict(item.get("metadata") or {})
            assert metadata.get("executor_key") == "consultation_quality"
            assert not item.get("llm_fallback")
            assert not item.get("pack_fallback")
            assert not (item.get("metadata") or {}).get("bundle_fallback")
            assert "legacy" not in str(item.get("metadata") or {}).lower()
            assert list(item.get("customer_evidence") or [])
            assert all(
                str(evidence.get("source_type") or "") == "consultation_record"
                and str(evidence.get("source_document_id") or "")
                and str(evidence.get("record_time") or "")
                for evidence in list(item.get("customer_evidence") or [])
            )

    single_item = _canonical_saved_item(single_job, visit_id=_RECORD_A["visit_id"])
    pool_item = _canonical_saved_item(pool_batch_job, visit_id=_RECORD_A["visit_id"])
    sample_item = _canonical_saved_item(sample_leaf_job, visit_id=_RECORD_A["visit_id"])
    assert _canonical_projection(single_item) == _canonical_projection(pool_item)
    assert _canonical_projection(single_item) == _canonical_projection(sample_item)

    # 结果不仅存在于任务 JSON，还必须已经写入单病历 Canonical Envelope。
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
    assert latest["result_rule_count"] == 1
    envelope_item = latest["items"][0]
    assert {
        key: envelope_item.get(key)
        for key in ("status", "reason_code", "customer_display_facts", "criterion_results")
    } == {
        key: sample_item.get(key)
        for key in ("status", "reason_code", "customer_display_facts", "criterion_results")
    }
    _assert_safe_envelope_evidence(
        envelope_item=envelope_item,
        task_item=sample_item,
    )
