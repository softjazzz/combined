"""LX0609 会诊族从真实 API 创建入口到正式 worker 的隔离验收。

本文件只替换外部资料读取和模型配置：规则目录、任务创建、脱离线程派发、
正式 worker 与 Canonical 保存均使用生产实现。它补足旧业务入口测试直接
``create_batch_job`` 后调用 worker、未经过路由创建与派发的问题。
"""

from __future__ import annotations

import time
from types import SimpleNamespace
from typing import Any

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import get_current_user
from app.routers import qc_sample_pools, qc_sichuan
from app.services import custom_qc_sample_pool_service as sample_pool_module
from app.services import custom_qc_workspace_service as workspace_module
from app.services import sichuan_qc_service
from app.services import sichuan_workspace_batch_worker as batch_worker
from app.services.custom_qc_sample_pool_service import CustomQCSamplePoolService
from app.services.luxian_0609 import execution as luxian_execution
from app.services.luxian_0609.evidence_snapshot_provider import SnapshotSourceRows
from app.services.product_activation import require_product_activation
from app.services.sichuan_workspace_batch_worker import run_sichuan_workspace_batch_job
from tests.integration.test_luxian_0609_consultation_business_entry_flow import (
    RULE_ID,
    _ActivationStub,
    _RECORD_A,
    _RECORD_B,
    _bundle_for_record,
    _canonical_projection,
    _canonical_saved_item,
    _assert_safe_envelope_evidence,
    _fixture_evidence_session_builder,
    _formal_settings,
    _install_isolated_sqlite,
)


# 路由在模块导入时已捕获这一依赖对象；worker 则在运行时读取
# ``qc_sichuan.get_qc_service`` 全局。保留旧对象用于 TestClient 的依赖覆盖。
_ROUTER_QC_SERVICE_DEPENDENCY = qc_sichuan.get_qc_service


def _install_sample_pool_sqlite(
    monkeypatch: pytest.MonkeyPatch,
    *,
    engine: sa.Engine,
) -> CustomQCSamplePoolService:
    """让实际样本池创建服务与工作台任务共用隔离 SQLite。"""

    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(sample_pool_module, "engine", engine)
    monkeypatch.setattr(sample_pool_module, "SessionLocal", session_local)
    monkeypatch.setattr(sample_pool_module, "DB_SCHEMA_MODE", "single")
    sample_pool_module._sample_pools_table.cache_clear()
    sample_pool_module._sample_pool_items_table.cache_clear()
    sample_pool_module._sample_pool_sync_jobs_table.cache_clear()
    sample_pool_module._sample_validation_batch_job_status_table.cache_clear()
    return CustomQCSamplePoolService()


@pytest.fixture
def _isolated_api_database(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
):
    """隔离数据库在每例 finally 清空模块表缓存并释放 SQLite 句柄。"""

    engine, workspace = _install_isolated_sqlite(monkeypatch, tmp_path)
    try:
        yield engine, workspace
    finally:
        sample_pool_module._sample_pools_table.cache_clear()
        sample_pool_module._sample_pool_items_table.cache_clear()
        sample_pool_module._sample_pool_sync_jobs_table.cache_clear()
        sample_pool_module._sample_validation_batch_job_status_table.cache_clear()
        workspace_module._drafts_table.cache_clear()
        workspace_module._batch_jobs_table.cache_clear()
        workspace_module._record_result_envelopes_table.cache_clear()
        engine.dispose()


def _create_ready_sample_pool(
    *,
    engine: sa.Engine,
    service: CustomQCSamplePoolService,
) -> tuple[str, str]:
    """用正式样本池服务建池，再写入已同步的脱敏三坐标。"""

    pool = service.create_pool_with_items(
        name="会诊 API 入口隔离样本",
        source_file="isolated-consultation-fixture.xlsx",
        source_sheet="Sheet1",
        created_by="api-entry-test-user",
        scene="final",
        rows=[
            {
                "row_no": 1,
                "patient_name": "脱敏患者",
                "manual_issue_text": "会诊意见记录完整性核验",
            }
        ],
    )
    pool_id = str(pool["id"])
    with Session(engine) as session:
        item_id = session.execute(
            sa.select(service._item_table.c.id).where(service._item_table.c.pool_id == pool_id)
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


def _wait_for_terminal_job(*, workspace: Any, job_id: str) -> dict[str, Any]:
    """等待真实 detached worker 落库，不伪造完成状态。"""

    deadline = time.monotonic() + 20
    last_job: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        current = workspace.get_batch_job_for_processing(job_id=job_id)
        if current:
            last_job = current
            if str(current.get("status") or "").lower() in {"completed", "failed", "canceled"}:
                return current
        time.sleep(0.05)
    raise AssertionError(f"detached worker did not finish: job_id={job_id}, last_job={last_job}")


def _saved_item(
    job: dict[str, Any],
    *,
    visit_id: str,
    rule_id: str,
) -> dict[str, Any]:
    """按病例三坐标中的 visit 与规则精确取正式 worker 保存项。"""

    matches = [
        item
        for item in list(job.get("items") or [])
        if item.get("visit_id") == visit_id and item.get("rule_id") == rule_id
    ]
    assert len(matches) == 1
    return matches[0]


def _assert_native_consultation_item(item: dict[str, Any]) -> None:
    """空资料也必须保留正式会诊执行器身份，不能夹带旧链回退标记。"""

    metadata = dict(item.get("metadata") or {})
    assert metadata.get("executor_key") == "consultation_quality"
    assert not item.get("llm_fallback")
    assert not item.get("pack_fallback")
    assert not metadata.get("bundle_fallback")
    assert "legacy" not in str(metadata).lower()


def _assert_native_executor_breakdown(job: dict[str, Any]) -> None:
    """正式 native 结果不得落入旧 program/llm 观测桶。"""

    items = list(job.get("items") or [])
    result_visit_ids = {
        str(item.get("visit_id") or "").strip()
        for item in items
        if str(item.get("visit_id") or "").strip()
    }
    breakdown = dict((job.get("summary") or {}).get("executor_breakdown") or {})
    assert job.get("job_kind") == "leaf"
    assert not job.get("parent_job_id")
    assert not list(job.get("child_job_ids") or [])
    assert (job.get("summary") or {}).get("total_records") == len(result_visit_ids)
    assert breakdown.get("native") == len(items)
    assert breakdown.get("llm") == 0


def _task_customer_conclusion(item: dict[str, Any]) -> str:
    """与 Canonical 映射一致：conclusion → customer_conclusion → findings。"""

    for key in ("conclusion", "customer_conclusion", "findings"):
        value = str(item.get(key) or "").strip()
        if value:
            return value
    return ""


def _envelope_customer_projection(item: dict[str, Any]) -> dict[str, Any]:
    """客户 Envelope 的可交付比较面，包含真实 conclusion 与准则结果。"""

    return {
        key: item.get(key)
        for key in (
            "status",
            "reason_code",
            "customer_display_facts",
            "criterion_results",
            "conclusion",
        )
    }


def _api_app(*, service: Any) -> FastAPI:
    """挂载生产 router；认证只替换为本地固定身份。"""

    app = FastAPI()
    app.include_router(qc_sichuan.router)
    app.include_router(qc_sample_pools.router)
    user = {"id": "api-entry-test-user", "roles": ["admin"]}

    async def current_user() -> dict[str, Any]:
        return user

    async def activated_user() -> dict[str, Any]:
        return user

    async def provide_qc_service() -> Any:
        return service

    # 路由在模块导入时已绑定依赖对象；worker 在运行时从 qc_sichuan 全局读取
    # get_qc_service，二者都指向同一个受控服务实例，避免读取 .env / 真实模型。
    app.dependency_overrides[get_current_user] = current_user
    app.dependency_overrides[require_product_activation] = activated_user
    app.dependency_overrides[_ROUTER_QC_SERVICE_DEPENDENCY] = provide_qc_service
    return app


def _empty_evidence_session_builder(monkeypatch: pytest.MonkeyPatch) -> None:
    """保留正式读取会话，只让脱敏夹具表达“各资料源均已成功读取且无会诊”。"""

    original = luxian_execution.build_luxian_0609_evidence_read_session

    def read_empty_fixture(**kwargs: Any) -> SnapshotSourceRows:
        return SnapshotSourceRows.create(
            source_key=str(kwargs["source_key"]),
            rows=[],
            truncated=False,
            limit_rows=50,
        )

    def build_with_empty_fixture_reader(**kwargs: Any) -> Any:
        return original(**kwargs, row_reader=read_empty_fixture)

    monkeypatch.setattr(
        luxian_execution,
        "build_luxian_0609_evidence_read_session",
        build_with_empty_fixture_reader,
    )


def _read_saved_envelope(
    *,
    app: FastAPI,
    job_id: str,
    task_item: dict[str, Any],
    record: dict[str, str],
    expected_rule_ids: list[str],
    evidence_required: bool = True,
) -> dict[str, Any]:
    """从实际 Canonical 表按本次 job 回读，避免只检查任务 JSON 投影。"""

    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/qc/sichuan/workspace/records/{record['visit_id']}/latest-result",
            params={
                "institute_id": record["institute_id"],
                "patient_id": record["patient_id"],
            },
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    latest = body["data"]
    assert latest["state"] == "ready"
    assert latest["job_id"] == job_id
    assert latest["result_rule_count"] == len(expected_rule_ids)
    envelope_items = list(latest["items"])
    matches = [item for item in envelope_items if item.get("rule_id") == task_item["rule_id"]]
    assert len(matches) == 1
    envelope_item = matches[0]
    task_conclusion = _task_customer_conclusion(task_item)
    assert task_conclusion
    assert str(envelope_item.get("conclusion") or "").strip()
    assert {
        key: envelope_item.get(key)
        for key in (
            "rule_id",
            "status",
            "reason_code",
            "customer_display_facts",
            "criterion_results",
        )
    } == {
        key: task_item.get(key)
        for key in (
            "rule_id",
            "status",
            "reason_code",
            "customer_display_facts",
            "criterion_results",
        )
    }
    assert envelope_item["conclusion"] == task_conclusion
    if evidence_required:
        _assert_safe_envelope_evidence(envelope_item=envelope_item, task_item=task_item)
    else:
        # “无会诊”无可投影的原始文书；需确认不会凭空写入不安全证据。
        assert not list(task_item.get("customer_evidence") or [])
        assert not list(envelope_item.get("evidence") or [])
    return envelope_item


@pytest.mark.integration
def test_consultation_api_entries_create_dispatch_and_persist_formal_worker(
    monkeypatch: pytest.MonkeyPatch,
    _isolated_api_database,
) -> None:
    """工作台单条、病历池批量、样本池入口都应抵达 consultation_quality worker。"""

    engine, workspace = _isolated_api_database
    sample_pool_service = _install_sample_pool_sqlite(monkeypatch, engine=engine)
    _fixture_evidence_session_builder(monkeypatch)
    settings = _formal_settings()
    monkeypatch.setattr(batch_worker, "get_settings", lambda: settings)
    monkeypatch.setattr(sichuan_qc_service, "get_settings", lambda: settings)
    monkeypatch.setattr(qc_sichuan, "get_settings", lambda: settings)
    monkeypatch.setattr(batch_worker, "get_product_activation_service", lambda: _ActivationStub())
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
    monkeypatch.setattr(
        sample_pool_module,
        "get_settings",
        lambda: SimpleNamespace(JWT_SECRET="isolated-api-entry-test-secret"),
    )
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(qc_sample_pools, "_workspace_service", lambda: workspace)
    monkeypatch.setattr(qc_sample_pools, "_service", lambda: sample_pool_service)

    controlled_service = sichuan_qc_service.SichuanQCService(
        {
            "provider_code": "isolated-test",
            "model": "controlled-stub",
            "allow_mock_when_unconfigured": True,
            "source": "api-entry-isolated",
        }
    )

    async def provide_qc_service() -> Any:
        return controlled_service

    # 保留真实派发函数；worker 调用时从该全局拿到与 API 注入相同的受控服务。
    monkeypatch.setattr(qc_sichuan, "get_qc_service", provide_qc_service)

    native_phase_events: list[tuple[str, dict[str, Any]]] = []
    original_update_progress = workspace.update_batch_job_progress

    def capture_update_progress(**kwargs: Any) -> None:
        stream_state = dict((kwargs.get("summary_patch") or {}).get("stream_state") or {})
        if stream_state.get("kind") == "native_executor_phase":
            native_phase_events.append((str(kwargs.get("job_id") or ""), stream_state))
        original_update_progress(**kwargs)

    monkeypatch.setattr(workspace, "update_batch_job_progress", capture_update_progress)
    pool_id, sample_item_id = _create_ready_sample_pool(engine=engine, service=sample_pool_service)
    app = _api_app(service=controlled_service)

    def create_workspace_job(record_refs: list[dict[str, str]]) -> str:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/qc/sichuan/workspace/batch-jobs",
                json={
                    "rule_set_key": "luxian_0609_qc_v1",
                    "rule_ids": [RULE_ID],
                    "scope": "final",
                    "record_refs": record_refs,
                    "run_mode": "serial",
                },
            )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["success"] is True
        return str(body["data"]["id"])

    # 同一实际创建路由覆盖工作台的单规则和病历池批量两个 UI 使用方式。
    # 每个入口完成后立即从 Canonical Envelope 回读，避免后续同病例任务覆盖
    # “最新结果”而使 job_id 与保存结果失去对应关系。
    single_job_id = create_workspace_job([_RECORD_A])
    single_job = _wait_for_terminal_job(workspace=workspace, job_id=single_job_id)
    single_item = _canonical_saved_item(single_job, visit_id=_RECORD_A["visit_id"])
    single_envelope_item = _read_saved_envelope(
        app=app,
        job_id=single_job_id,
        task_item=single_item,
        record=_RECORD_A,
        expected_rule_ids=[RULE_ID],
    )

    pool_batch_job_id = create_workspace_job([_RECORD_A, _RECORD_B])
    pool_batch_job = _wait_for_terminal_job(workspace=workspace, job_id=pool_batch_job_id)
    pool_batch_item = _canonical_saved_item(pool_batch_job, visit_id=_RECORD_A["visit_id"])
    pool_batch_envelope_item = _read_saved_envelope(
        app=app,
        job_id=pool_batch_job_id,
        task_item=pool_batch_item,
        record=_RECORD_A,
        expected_rule_ids=[RULE_ID],
    )

    with TestClient(app) as client:
        sample_response = client.post(
            f"/api/v1/qc/sample-pools/{pool_id}/run",
            json={
                "validation_mode": "customer",
                "rule_set_key": "luxian_0609_qc_v1",
                "selected_rule_ids": [RULE_ID],
                "sample_item_ids": [sample_item_id],
                "record_refs": [_RECORD_A],
                "group_by_luxian_family": False,
            },
        )
    assert sample_response.status_code == 200, sample_response.text
    sample_body = sample_response.json()
    assert sample_body["success"] is True
    sample_job_id = str(sample_body["data"]["job_id"])

    sample_job = _wait_for_terminal_job(workspace=workspace, job_id=sample_job_id)
    sample_item = _canonical_saved_item(sample_job, visit_id=_RECORD_A["visit_id"])
    sample_envelope_item = _read_saved_envelope(
        app=app,
        job_id=sample_job_id,
        task_item=sample_item,
        record=_RECORD_A,
        expected_rule_ids=[RULE_ID],
    )

    jobs = [single_job, pool_batch_job, sample_job]
    for job in jobs:
        assert job["status"] == "completed", job.get("error_message")
        assert not list(job.get("failed_records") or [])
        assert (job.get("filters") or {}).get("rule_set_key") == "luxian_0609_qc_v1"
        _assert_native_executor_breakdown(job)
        assert any(
            event_job_id == job["id"]
            and event.get("event") == "completed"
            and event.get("executor_key") == "consultation_quality"
            for event_job_id, event in native_phase_events
        )
        for item in list(job.get("items") or []):
            assert item["rule_id"] == RULE_ID
            assert item["status"] == "compliant"
            assert item["reason_code"] == "requirement_satisfied"
            assert (item.get("metadata") or {}).get("executor_key") == "consultation_quality"
            assert list(item.get("customer_evidence") or [])

    assert _canonical_projection(single_item) == _canonical_projection(pool_batch_item)
    assert _canonical_projection(single_item) == _canonical_projection(sample_item)
    assert _task_customer_conclusion(single_item) == _task_customer_conclusion(pool_batch_item)
    assert _task_customer_conclusion(single_item) == _task_customer_conclusion(sample_item)
    assert _envelope_customer_projection(single_envelope_item) == _envelope_customer_projection(
        pool_batch_envelope_item
    )
    assert _envelope_customer_projection(single_envelope_item) == _envelope_customer_projection(
        sample_envelope_item
    )

    # 直接调用 worker 不是本测试的成功条件；此断言只防止误把导入的符号当派发入口。
    assert run_sichuan_workspace_batch_job is batch_worker.run_sichuan_workspace_batch_job


@pytest.mark.integration
def test_consultation_rule_matrix_no_consultation_and_069_control(
    monkeypatch: pytest.MonkeyPatch,
    _isolated_api_database,
) -> None:
    """空会诊资料下逐条/组合走真实入口，069 不得误派到会诊执行器。"""

    engine, workspace = _isolated_api_database
    sample_pool_service = _install_sample_pool_sqlite(monkeypatch, engine=engine)
    _empty_evidence_session_builder(monkeypatch)
    settings = _formal_settings()
    # 069 是 extended_document 规则，不得再借 MDT-040 开关被放行。这里刻意
    # 关闭 MDT，同时启用 extended_document，以真实入口验证两族执行门已解耦。
    settings.LUXIAN_0609_NATIVE_MDT_040_ENABLED = False
    settings.LUXIAN_0609_NATIVE_EXTENDED_DOCUMENT_ENABLED = True
    monkeypatch.setattr(batch_worker, "get_settings", lambda: settings)
    monkeypatch.setattr(sichuan_qc_service, "get_settings", lambda: settings)
    monkeypatch.setattr(qc_sichuan, "get_settings", lambda: settings)
    monkeypatch.setattr(batch_worker, "get_product_activation_service", lambda: _ActivationStub())
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
    monkeypatch.setattr(
        sample_pool_module,
        "get_settings",
        lambda: SimpleNamespace(JWT_SECRET="isolated-api-entry-test-secret"),
    )
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(qc_sample_pools, "_workspace_service", lambda: workspace)
    monkeypatch.setattr(qc_sample_pools, "_service", lambda: sample_pool_service)

    controlled_service = sichuan_qc_service.SichuanQCService(
        {
            "provider_code": "isolated-test",
            "model": "controlled-stub",
            "allow_mock_when_unconfigured": True,
            "source": "api-entry-empty-consultation",
        }
    )

    async def fail_if_legacy_or_llm_path_is_called(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("空会诊资料不得触发 LLM 或旧通用规则引擎")

    # 正式 package 会在进入 SichuanQCService 的旧通用评估前移走 020-023。
    # 因此这里不以成功 stub 兜底：一旦 LLM/adjudicator 或旧 rule_engine 被调用，
    # 真实 detached worker 必须失败，才能证明空资料由 Native 会诊包直接处理。
    monkeypatch.setattr(
        sichuan_qc_service.SichuanQCLLMClient,
        "generate",
        fail_if_legacy_or_llm_path_is_called,
    )
    monkeypatch.setattr(
        controlled_service.rule_engine,
        "evaluate",
        fail_if_legacy_or_llm_path_is_called,
    )
    monkeypatch.setattr(
        controlled_service.rule_engine,
        "evaluate_batch_compact",
        fail_if_legacy_or_llm_path_is_called,
    )

    async def provide_qc_service() -> Any:
        return controlled_service

    monkeypatch.setattr(qc_sichuan, "get_qc_service", provide_qc_service)
    native_phase_events: list[tuple[str, dict[str, Any]]] = []
    original_update_progress = workspace.update_batch_job_progress

    def capture_update_progress(**kwargs: Any) -> None:
        stream_state = dict((kwargs.get("summary_patch") or {}).get("stream_state") or {})
        if stream_state.get("kind") == "native_executor_phase":
            native_phase_events.append((str(kwargs.get("job_id") or ""), stream_state))
        original_update_progress(**kwargs)

    monkeypatch.setattr(workspace, "update_batch_job_progress", capture_update_progress)
    pool_id, sample_item_id = _create_ready_sample_pool(engine=engine, service=sample_pool_service)
    app = _api_app(service=controlled_service)
    consultation_rules = ["LX0609-020", "LX0609-021", "LX0609-022", "LX0609-023"]

    def create_workspace_job(rule_ids: list[str], record_refs: list[dict[str, str]]) -> str:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/qc/sichuan/workspace/batch-jobs",
                json={
                    "rule_set_key": "luxian_0609_qc_v1",
                    "rule_ids": rule_ids,
                    "scope": "final",
                    "record_refs": record_refs,
                    "run_mode": "serial",
                },
            )
        assert response.status_code == 200, response.text
        return str(response.json()["data"]["id"])

    # 四条规则各自经实际创建入口执行，避免“组合绿了”掩盖单条目录/派发错误。
    for rule_id in consultation_rules:
        job_id = create_workspace_job([rule_id], [_RECORD_A])
        job = _wait_for_terminal_job(workspace=workspace, job_id=job_id)
        assert job["status"] == "completed", job.get("error_message")
        _assert_native_executor_breakdown(job)
        item = _saved_item(job, visit_id=_RECORD_A["visit_id"], rule_id=rule_id)
        assert (item["status"], item["reason_code"]) == (
            "not_applicable",
            "trigger_absent_complete",
        )
        _assert_native_consultation_item(item)
        assert any(
            event_job_id == job_id and event.get("executor_key") == "consultation_quality"
            for event_job_id, event in native_phase_events
        )

    # 组合与三种业务入口使用相同“无会诊”事实；各入口完成后立即从真实
    # GET 最新结果接口回读，避免后续任务覆盖该病例的 latest 根任务。
    single_job_id = create_workspace_job(consultation_rules, [_RECORD_A])
    single_job = _wait_for_terminal_job(workspace=workspace, job_id=single_job_id)
    single_items = {
        rule_id: _saved_item(single_job, visit_id=_RECORD_A["visit_id"], rule_id=rule_id)
        for rule_id in consultation_rules
    }
    single_envelopes = {
        rule_id: _read_saved_envelope(
            app=app,
            job_id=single_job_id,
            task_item=item,
            record=_RECORD_A,
            expected_rule_ids=consultation_rules,
            evidence_required=False,
        )
        for rule_id, item in single_items.items()
    }

    pool_job_id = create_workspace_job(consultation_rules, [_RECORD_A, _RECORD_B])
    pool_job = _wait_for_terminal_job(workspace=workspace, job_id=pool_job_id)
    pool_items = {
        rule_id: _saved_item(pool_job, visit_id=_RECORD_A["visit_id"], rule_id=rule_id)
        for rule_id in consultation_rules
    }
    pool_envelopes = {
        rule_id: _read_saved_envelope(
            app=app,
            job_id=pool_job_id,
            task_item=item,
            record=_RECORD_A,
            expected_rule_ids=consultation_rules,
            evidence_required=False,
        )
        for rule_id, item in pool_items.items()
    }

    with TestClient(app) as client:
        sample_response = client.post(
            f"/api/v1/qc/sample-pools/{pool_id}/run",
            json={
                "validation_mode": "customer",
                "rule_set_key": "luxian_0609_qc_v1",
                "selected_rule_ids": consultation_rules,
                "sample_item_ids": [sample_item_id],
                "record_refs": [_RECORD_A],
                "group_by_luxian_family": False,
            },
        )
    assert sample_response.status_code == 200, sample_response.text
    sample_job_id = str(sample_response.json()["data"]["job_id"])
    sample_job = _wait_for_terminal_job(workspace=workspace, job_id=sample_job_id)
    sample_items = {
        rule_id: _saved_item(sample_job, visit_id=_RECORD_A["visit_id"], rule_id=rule_id)
        for rule_id in consultation_rules
    }
    sample_envelopes = {
        rule_id: _read_saved_envelope(
            app=app,
            job_id=sample_job_id,
            task_item=item,
            record=_RECORD_A,
            expected_rule_ids=consultation_rules,
            evidence_required=False,
        )
        for rule_id, item in sample_items.items()
    }

    for rule_id in consultation_rules:
        _assert_native_consultation_item(single_items[rule_id])
        _assert_native_consultation_item(pool_items[rule_id])
        _assert_native_consultation_item(sample_items[rule_id])
        assert _canonical_projection(single_items[rule_id]) == _canonical_projection(
            pool_items[rule_id]
        )
        assert _canonical_projection(single_items[rule_id]) == _canonical_projection(
            sample_items[rule_id]
        )
        assert _task_customer_conclusion(single_items[rule_id]) == _task_customer_conclusion(
            pool_items[rule_id]
        ) == _task_customer_conclusion(sample_items[rule_id])
        assert _envelope_customer_projection(
            single_envelopes[rule_id]
        ) == _envelope_customer_projection(
            pool_envelopes[rule_id]
        ) == _envelope_customer_projection(sample_envelopes[rule_id])

    for job in (single_job, pool_job, sample_job):
        _assert_native_executor_breakdown(job)
        assert (job.get("summary") or {}).get("total_tokens") == 0

    # 069 作为目录路由对照：即使 MDT-040 已关闭，只要扩展文书包显式启用，
    # 也必须抵达 extended_document，绝不能借会诊或 surgery_mdt 阶段蒙混。
    before_069_events = len(native_phase_events)
    with TestClient(app) as client:
        rule_069_response = client.post(
            "/api/v1/qc/sichuan/workspace/batch-jobs",
            json={
                "rule_set_key": "luxian_0609_qc_v1",
                "rule_ids": ["LX0609-069"],
                "scope": "final",
                "record_refs": [_RECORD_A],
                "run_mode": "serial",
            },
        )
    assert rule_069_response.status_code == 200, rule_069_response.text
    rule_069_job_id = str(rule_069_response.json()["data"]["id"])
    rule_069_job = _wait_for_terminal_job(workspace=workspace, job_id=rule_069_job_id)
    assert rule_069_job["status"] == "completed", rule_069_job.get("error_message")
    rule_069_item = _saved_item(
        rule_069_job,
        visit_id=_RECORD_A["visit_id"],
        rule_id="LX0609-069",
    )
    assert (rule_069_item["status"], rule_069_item["reason_code"]) == (
        "not_applicable",
        "trigger_absent_complete",
    )
    assert (rule_069_item.get("metadata") or {}).get("executor_key") == "extended_document"
    rule_069_envelope = _read_saved_envelope(
        app=app,
        job_id=rule_069_job_id,
        task_item=rule_069_item,
        record=_RECORD_A,
        expected_rule_ids=["LX0609-069"],
        evidence_required=False,
    )
    assert _envelope_customer_projection(rule_069_envelope) == {
        "status": rule_069_item["status"],
        "reason_code": rule_069_item["reason_code"],
        "customer_display_facts": rule_069_item.get("customer_display_facts"),
        "criterion_results": rule_069_item.get("criterion_results"),
        "conclusion": _task_customer_conclusion(rule_069_item),
    }
    assert any(
        event_job_id == rule_069_job_id
        and event.get("event") == "completed"
        and event.get("executor_key") == "extended_document"
        for event_job_id, event in native_phase_events[before_069_events:]
    )
    assert not any(
        event.get("executor_key") == "consultation_quality"
        for _event_job_id, event in native_phase_events[before_069_events:]
    )
    assert not any(
        event.get("executor_key") == "surgery_mdt"
        for _event_job_id, event in native_phase_events[before_069_events:]
    )

    # 扩展文书包关闭时，正式创建入口必须同步拒绝。不能先建任务、派发 worker
    # 再让它掉回旧通用引擎，否则客户会看到“已发起”的伪成功任务。
    settings.LUXIAN_0609_NATIVE_EXTENDED_DOCUMENT_ENABLED = False
    jobs_before_rejection = 0
    with Session(engine) as session:
        jobs_before_rejection = int(
            session.execute(
                sa.select(sa.func.count()).select_from(workspace._batch_job_table)
            ).scalar_one()
        )
    phases_before_rejection = len(native_phase_events)
    with TestClient(app) as client:
        disabled_069_response = client.post(
            "/api/v1/qc/sichuan/workspace/batch-jobs",
            json={
                "rule_set_key": "luxian_0609_qc_v1",
                "rule_ids": ["LX0609-069"],
                "scope": "final",
                "record_refs": [_RECORD_A],
                "run_mode": "serial",
            },
        )
    assert disabled_069_response.status_code == 503, disabled_069_response.text
    with Session(engine) as session:
        assert (
            int(
                session.execute(
                    sa.select(sa.func.count()).select_from(workspace._batch_job_table)
                ).scalar_one()
            )
            == jobs_before_rejection
        )
    assert len(native_phase_events) == phases_before_rejection
