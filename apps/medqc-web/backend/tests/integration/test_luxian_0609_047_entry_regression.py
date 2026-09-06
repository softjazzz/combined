"""LX0609-047 经正式入口、worker、保存后的评价窗口冻结。

本文件不替换 worker、unified engine 或保存层。仅用正式 evidence-session 的
``row_reader`` seam 提供脱敏资料，并在两个生产 route 的 horizon-builder seam
固定每例任务快照；这样可以稳定检验 worker 实际收到的逐例评价时点。
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database.models.cdm import InpatRegistration
from app.routers import qc_sample_pools, qc_sichuan
from app.services.case_identity import CaseRef
from app.services.custom_qc_workspace_service import build_customer_safe_source_ref
from app.services import custom_qc_sample_pool_service as sample_pool_module
from app.services import sichuan_qc_service
from app.services import sichuan_workspace_batch_worker as batch_worker
from app.services import custom_qc_workspace_service as workspace_module
from app.services.luxian_0609 import execution as luxian_execution
from app.services.luxian_0609.evidence_snapshot_provider import SnapshotSourceRows
from app.services.luxian_0609.native_transfusion_execution import EXECUTOR_KEY
from app.services.luxian_0609_rule_catalog import LUXIAN_0609_RULE_SET_KEY
from tests.integration.test_luxian_0609_consultation_api_entry_flow import (
    _api_app,
    _install_sample_pool_sqlite,
    _wait_for_terminal_job,
)
from tests.integration.test_luxian_0609_exam_lab_family_convergence import (
    _install_isolated_sqlite,
)
from tests.integration.test_luxian_0609_transfusion_family_convergence import (
    _ActivationStub,
    _RECORD_A,
    _RECORD_B,
    _bundle_for_record,
    _create_ready_sample_pool,
    _evidence_coordinates,
    _formal_settings,
    _item,
    _projection,
    _seed_registration_projection,
)


RULE_ID = "LX0609-047"
FROZEN_DATE = "2026-01-03"


@dataclass(frozen=True)
class _Scenario:
    name: str
    horizon_date: str | None
    bloodtrans_rows: tuple[dict[str, Any], ...]
    expected_state: tuple[str, str]
    expected_document_ids: frozenset[str] = frozenset()


_SCENARIOS = (
    _Scenario(
        name="mature_missing_evaluation",
        horizon_date=FROZEN_DATE,
        bloodtrans_rows=(
            {
                "document_id": "BT-MATURE-MISSING",
                "record_time": "2026-01-01 16:30:00",
                "record_content": "2026-01-01 16:00:00输血结束。",
            },
        ),
        # typed transfusion outcome 将内部缺评价语义统一归约为此公共原因。
        expected_state=("non_compliant", "requirement_violated"),
        expected_document_ids=frozenset({"BT-MATURE-MISSING"}),
    ),
    _Scenario(
        name="window_not_mature",
        horizon_date="2026-01-02",
        bloodtrans_rows=(
            {
                "document_id": "BT-WINDOW-OPEN",
                "record_time": "2026-01-01 16:30:00",
                "record_content": "2026-01-01 16:00:00输血结束。",
            },
        ),
        expected_state=("not_applicable", "evaluation_window_not_mature"),
    ),
    _Scenario(
        name="horizon_unavailable",
        horizon_date=None,
        bloodtrans_rows=(
            {
                "document_id": "BT-HORIZON-GAP",
                "record_time": "2026-01-01 16:30:00",
                "record_content": "2026-01-01 16:00:00输血结束。",
            },
        ),
        expected_state=("data_gap", "authoritative_time_missing"),
    ),
    _Scenario(
        name="transfusion_end_unavailable",
        horizon_date=FROZEN_DATE,
        bloodtrans_rows=(
            {
                "document_id": "BT-END-GAP",
                "record_time": "2026-01-01 16:30:00",
                "record_content": "输血结束，继续观察，未见输血不良反应。",
            },
        ),
        # 结束时点不能解析是原始内核原因；公共 typed reason 为资料字段缺口。
        expected_state=("data_gap", "required_field_missing"),
    ),
    _Scenario(
        name="earlier_mature_missing_not_hidden_by_later_unmatured",
        horizon_date=FROZEN_DATE,
        bloodtrans_rows=(
            {
                "document_id": "BT-EARLY-MATURE-MISSING",
                "record_time": "2026-01-01 10:30:00",
                "record_content": "2026-01-01 10:00:00输血结束。",
            },
            {
                "document_id": "BT-LATE-WINDOW-OPEN",
                "record_time": "2026-01-02 23:45:00",
                "record_content": "2026-01-02 23:30:00输血结束。",
            },
        ),
        expected_state=("non_compliant", "requirement_violated"),
        expected_document_ids=frozenset(
            {"BT-EARLY-MATURE-MISSING", "BT-LATE-WINDOW-OPEN"}
        ),
    ),
)


class _NoLlmClient:
    """047 是确定性规则；任何模型调用均为回归。"""

    def __init__(self) -> None:
        self.call_count = 0
        self.usages: list[tuple[int, int, int]] = []

    async def generate(self, prompt: str) -> dict[str, Any]:
        self.call_count += 1
        raise AssertionError(f"LX0609-047 must not call LLM: {prompt[:80]}")


def _scenario_rows(
    *, scenario: _Scenario, source_key: str, visit_id: str
) -> list[dict[str, Any]]:
    record = _RECORD_B if visit_id == _RECORD_B["visit_id"] else _RECORD_A
    common = {**record, "record_time": "2026-01-01 16:30:00"}
    if source_key == "mr_bloodtrans":
        return [{**common, "transfution_datetime": "2026-01-01 14:20:00"}]
    if source_key == "bloodtrans_record":
        return [{**common, **row} for row in scenario.bloodtrans_rows]
    if source_key == "daily_course_record":
        return []
    return []


def _install_scenario_evidence_reader(
    monkeypatch: pytest.MonkeyPatch, *, scenario: _Scenario
) -> None:
    original = luxian_execution.build_luxian_0609_evidence_read_session

    def reader(**kwargs: Any) -> SnapshotSourceRows:
        source_key = str(kwargs["source_key"])
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=_scenario_rows(
                scenario=scenario,
                source_key=source_key,
                visit_id=str(kwargs["visit_id"]),
            ),
            truncated=False,
            limit_rows=50,
        )

    monkeypatch.setattr(
        luxian_execution,
        "build_luxian_0609_evidence_read_session",
        lambda **kwargs: original(**kwargs, row_reader=reader),
    )


def _record_horizon_snapshot(
    *, records: list[dict[str, Any]], scenario: _Scenario
) -> list[dict[str, str]]:
    """固定逐病例快照；生产 route/worker 仍负责把它保存并传递。"""

    snapshots: list[dict[str, str]] = []
    for record in records:
        visit_id = str(record.get("visit_id") or record.get("record_id") or "").strip()
        assert visit_id
        common = {
            "record_id": visit_id,
            "record_scene": "running",
            "admission_datetime": "2026-01-01T08:00:00",
            "discharge_datetime": "",
            "institute_id": str(record.get("institute_id") or ""),
            "patient_id": str(record.get("patient_id") or ""),
            "visit_id": visit_id,
            "record_key": CaseRef.from_mapping(record).as_key(),
        }
        if scenario.horizon_date is None:
            snapshots.append(
                {
                    **common,
                    "evaluation_horizon": "",
                    "evaluation_basis": "",
                    "resolution_status": "authoritative_time_missing",
                }
            )
        else:
            snapshots.append(
                {
                    **common,
                    "evaluation_horizon": scenario.horizon_date,
                    "evaluation_basis": "task_frozen_date",
                    "resolution_status": "resolved",
                }
            )
    return snapshots


def _install_fixed_horizon_snapshot(
    monkeypatch: pytest.MonkeyPatch, *, scenario: _Scenario
) -> list[tuple[str, str, tuple[str, ...]]]:
    """两个入口各自调用 production builder，测试仅固定 builder 的输出时点。"""

    calls: list[tuple[str, str, tuple[str, ...]]] = []

    def builder_for(route_name: str):
        def builder(
            records: list[dict[str, Any]], *, task_frozen_date: str
        ) -> list[dict[str, str]]:
            assert task_frozen_date
            calls.append(
                (
                    route_name,
                    task_frozen_date,
                    tuple(str(record.get("visit_id") or "") for record in records),
                )
            )
            return _record_horizon_snapshot(records=records, scenario=scenario)

        return builder

    monkeypatch.setattr(
        qc_sichuan,
        "build_record_evaluation_horizon_snapshot",
        builder_for("workspace"),
    )
    monkeypatch.setattr(
        qc_sample_pools,
        "build_record_evaluation_horizon_snapshot",
        builder_for("sample_pool"),
    )
    return calls


def _set_running_fixture_scene(*, engine: Any, sample_service: Any, pool_id: str) -> None:
    """三种入口均使用 running 病历，冻结日期才是生产语义中的合法 horizon。"""

    with Session(engine) as session:
        session.execute(
            InpatRegistration.__table__.update().values(discharge_datetime=None)
        )
        session.execute(
            sample_service._pool_table.update()
            .where(sample_service._pool_table.c.id == pool_id)
            .values(scene="running")
        )
        session.commit()


def _running_bundle_for_record(*, visit_id: str, patient_id: str) -> dict[str, Any]:
    bundle = _bundle_for_record(visit_id=visit_id, patient_id=patient_id)
    bundle["scene"] = "running"
    return bundle


def _customer_projection(item: dict[str, Any]) -> dict[str, Any]:
    conclusion = next(
        (
            str(item.get(key) or "").strip()
            for key in ("conclusion", "customer_conclusion", "findings")
            if str(item.get(key) or "").strip()
        ),
        "",
    )
    return {
        **_projection(item),
        "conclusion": conclusion,
    }


def _coordinates(entries: list[dict[str, Any]]) -> set[tuple[str, str, str, str]]:
    return {
        (
            str(entry.get("source_type") or ""),
            str(entry.get("source_document_id") or entry.get("source_ref") or ""),
            str(entry.get("field_path") or ""),
            str(entry.get("record_time") or ""),
        )
        for entry in entries
    }


def _coordinate_shapes(entries: list[dict[str, Any]]) -> set[tuple[str, str, str]]:
    return {
        (
            str(entry.get("source_type") or ""),
            str(entry.get("field_path") or ""),
            str(entry.get("record_time") or ""),
        )
        for entry in entries
    }


def _read_saved_item(
    *,
    app: Any,
    job_id: str,
    task_item: dict[str, Any],
    record: dict[str, str],
) -> dict[str, Any]:
    """从实际 Canonical 表回读，包含资料缺口时允许坐标集合为空。"""

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
    matches = [
        item
        for item in list(latest["items"])
        if item.get("rule_id") == RULE_ID
    ]
    assert len(matches) == 1
    envelope_item = matches[0]
    assert _customer_projection(envelope_item) == _customer_projection(task_item)
    saved_evidence = list(envelope_item.get("evidence") or [])
    task_evidence = list(task_item.get("customer_evidence") or [])
    # 保存层按公共契约把原 document_id 变为 src_* 安全坐标；比较不可变的
    # source/field/time 三元组，三入口之间再比较完整安全坐标集合。
    assert _coordinate_shapes(saved_evidence) == _coordinate_shapes(task_evidence)
    raw_document_ids = {
        str(entry.get("source_document_id") or "")
        for entry in task_evidence
        if isinstance(entry, dict) and str(entry.get("source_document_id") or "")
    }
    safe_refs = set()
    for entry in saved_evidence:
        assert isinstance(entry, dict)
        source_ref = str(entry.get("source_ref") or "")
        assert re.fullmatch(r"src_[0-9a-f]{24}", source_ref)
        assert "source_document_id" not in entry
        safe_refs.add(source_ref)
    assert all(
        document_id not in safe_ref
        for document_id in raw_document_ids
        for safe_ref in safe_refs
    )
    if raw_document_ids:
        # 复用保存层同一公共 helper，而非在测试中自行实现 HMAC/哈希。
        assert {
            build_customer_safe_source_ref(document_id)
            for document_id in raw_document_ids
        }.issubset(safe_refs)
    return envelope_item


def _assert_saved_horizon_snapshot(
    *, job: dict[str, Any], scenario: _Scenario, visit_ids: tuple[str, ...]
) -> None:
    snapshots = list((job.get("filters") or {}).get("record_evaluation_snapshot") or [])
    by_visit = {str(item.get("visit_id") or ""): item for item in snapshots}
    assert set(by_visit) == set(visit_ids)
    for visit_id in visit_ids:
        snapshot = by_visit[visit_id]
        assert snapshot.get("record_scene") == "running"
        if scenario.horizon_date is None:
            assert (
                snapshot.get("evaluation_horizon"),
                snapshot.get("evaluation_basis"),
                snapshot.get("resolution_status"),
            ) == ("", "", "authoritative_time_missing")
        else:
            assert (
                snapshot.get("evaluation_horizon"),
                snapshot.get("evaluation_basis"),
                snapshot.get("resolution_status"),
            ) == (scenario.horizon_date, "task_frozen_date", "resolved")


@pytest.mark.integration
@pytest.mark.parametrize("scenario", _SCENARIOS, ids=lambda item: item.name)
def test_047_entries_preserve_canonical_window_state_and_saved_coordinates(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    scenario: _Scenario,
) -> None:
    """两类 route 的三种入口形状均走真实 worker，且回读同一 Canonical 结果。"""

    workspace = _install_isolated_sqlite(monkeypatch, tmp_path)
    engine = workspace_module.engine
    _seed_registration_projection(engine=engine)
    sample_service = _install_sample_pool_sqlite(monkeypatch, engine=engine)
    _install_scenario_evidence_reader(monkeypatch, scenario=scenario)
    route_horizon_builder_calls = _install_fixed_horizon_snapshot(
        monkeypatch, scenario=scenario
    )

    settings = _formal_settings()
    for module in (batch_worker, sichuan_qc_service, qc_sichuan):
        monkeypatch.setattr(module, "get_settings", lambda: settings)
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
        lambda *, institute_id, patient_id, visit_id, **_: _running_bundle_for_record(
            visit_id=str(visit_id), patient_id=str(patient_id)
        ),
    )
    monkeypatch.setattr(
        sample_pool_module,
        "get_settings",
        lambda: SimpleNamespace(JWT_SECRET="047-entry-regression"),
    )
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(qc_sample_pools, "_workspace_service", lambda: workspace)
    monkeypatch.setattr(qc_sample_pools, "_service", lambda: sample_service)

    service = sichuan_qc_service.SichuanQCService(
        {"provider_code": "isolated-047", "allow_mock_when_unconfigured": True}
    )
    no_llm = _NoLlmClient()
    service.adjudicator_client = no_llm
    horizon_calls: list[tuple[str | None, str | None, str | None]] = []
    original_evaluate = service.evaluate_running_final_bundle_input

    async def capture_evaluate(*args: Any, **kwargs: Any) -> dict[str, Any]:
        horizon_calls.append(
            (
                kwargs.get("evaluation_as_of_date"),
                kwargs.get("evaluation_horizon_policy"),
                kwargs.get("evaluation_horizon_unavailable_reason"),
            )
        )
        return await original_evaluate(*args, **kwargs)

    monkeypatch.setattr(service, "evaluate_running_final_bundle_input", capture_evaluate)

    async def provide_service() -> Any:
        return service

    monkeypatch.setattr(qc_sichuan, "get_qc_service", provide_service)
    engine_batches: list[tuple[tuple[str, tuple[str, ...]], ...]] = []
    original_engine_execute = luxian_execution.Luxian0609ExecutionEngine.execute

    async def capture_engine_execute(
        engine_instance: Any, *args: Any, **kwargs: Any
    ) -> Any:
        batches = tuple(
            (str(key), tuple(rule_ids))
            for key, rule_ids in tuple(kwargs.get("executor_batches") or ())
        )
        assert batches == ((EXECUTOR_KEY, (RULE_ID,)),)
        engine_batches.append(batches)
        return await original_engine_execute(engine_instance, *args, **kwargs)

    monkeypatch.setattr(
        luxian_execution.Luxian0609ExecutionEngine,
        "execute",
        capture_engine_execute,
    )
    app = _api_app(service=service)
    pool_id, sample_item_id = _create_ready_sample_pool(
        engine=engine, service=sample_service
    )
    _set_running_fixture_scene(
        engine=engine, sample_service=sample_service, pool_id=pool_id
    )

    def create_workspace_job(records: list[dict[str, str]]) -> str:
        with TestClient(app) as api:
            response = api.post(
                "/api/v1/qc/sichuan/workspace/batch-jobs",
                json={
                    "rule_set_key": LUXIAN_0609_RULE_SET_KEY,
                    "rule_ids": [RULE_ID],
                    "scope": "running",
                    "record_refs": records,
                    "run_mode": "serial",
                },
            )
        assert response.status_code == 200, response.text
        return str(response.json()["data"]["id"])

    single_id = create_workspace_job([_RECORD_A])
    single_job = _wait_for_terminal_job(workspace=workspace, job_id=single_id)
    single_item = _item(single_job, rule_id=RULE_ID)
    _assert_saved_horizon_snapshot(
        job=single_job, scenario=scenario, visit_ids=(_RECORD_A["visit_id"],)
    )
    single_envelope = _read_saved_item(
        app=app,
        job_id=single_id,
        task_item=single_item,
        record=_RECORD_A,
    )

    batch_id = create_workspace_job([_RECORD_A, _RECORD_B])
    batch_job = _wait_for_terminal_job(workspace=workspace, job_id=batch_id)
    batch_item = _item(batch_job, rule_id=RULE_ID)
    _assert_saved_horizon_snapshot(
        job=batch_job,
        scenario=scenario,
        visit_ids=(_RECORD_A["visit_id"], _RECORD_B["visit_id"]),
    )
    batch_envelope = _read_saved_item(
        app=app,
        job_id=batch_id,
        task_item=batch_item,
        record=_RECORD_A,
    )

    with TestClient(app) as api:
        response = api.post(
            f"/api/v1/qc/sample-pools/{pool_id}/run",
            json={
                "validation_mode": "customer",
                "rule_set_key": LUXIAN_0609_RULE_SET_KEY,
                "selected_rule_ids": [RULE_ID],
                "sample_item_ids": [sample_item_id],
                "record_refs": [_RECORD_A],
                "group_by_luxian_family": False,
            },
        )
    assert response.status_code == 200, response.text
    sample_id = str(response.json()["data"]["job_id"])
    sample_job = _wait_for_terminal_job(workspace=workspace, job_id=sample_id)
    sample_item = _item(sample_job, rule_id=RULE_ID)
    _assert_saved_horizon_snapshot(
        job=sample_job, scenario=scenario, visit_ids=(_RECORD_A["visit_id"],)
    )
    sample_envelope = _read_saved_item(
        app=app,
        job_id=sample_id,
        task_item=sample_item,
        record=_RECORD_A,
    )

    assert len({single_id, batch_id, sample_id}) == 3
    assert [
        (route_name, visit_ids)
        for route_name, _task_frozen_date, visit_ids in route_horizon_builder_calls
    ] == [
        ("workspace", (_RECORD_A["visit_id"],)),
        ("workspace", (_RECORD_A["visit_id"], _RECORD_B["visit_id"])),
        ("sample_pool", (_RECORD_A["visit_id"],)),
    ]

    entries = (
        (single_job, single_item),
        (batch_job, batch_item),
        (sample_job, sample_item),
    )
    for job, item in entries:
        assert job["status"] == "completed", job.get("error_message")
        assert not list(job.get("failed_records") or [])
        assert (item.get("metadata") or {}).get("executor_key") == EXECUTOR_KEY
        assert (item.get("status"), item.get("reason_code")) == scenario.expected_state
        assert not item.get("llm_fallback") and not item.get("pack_fallback")
        assert "legacy" not in str(item.get("metadata") or {}).lower()

    assert _customer_projection(single_item) == _customer_projection(batch_item)
    assert _customer_projection(single_item) == _customer_projection(sample_item)
    assert _evidence_coordinates(single_item) == _evidence_coordinates(batch_item)
    assert _evidence_coordinates(single_item) == _evidence_coordinates(sample_item)
    assert _customer_projection(single_envelope) == _customer_projection(batch_envelope)
    assert _customer_projection(single_envelope) == _customer_projection(sample_envelope)
    assert _coordinates(list(single_envelope.get("evidence") or [])) == _coordinates(
        list(batch_envelope.get("evidence") or [])
    )
    assert _coordinates(list(single_envelope.get("evidence") or [])) == _coordinates(
        list(sample_envelope.get("evidence") or [])
    )
    evidence_document_ids = {
        document_id
        for _source_type, document_id, _field_path, _record_time in _evidence_coordinates(
            single_item
        )
    }
    assert scenario.expected_document_ids.issubset(evidence_document_ids)
    assert no_llm.call_count == 0
    assert no_llm.usages == []
    assert engine_batches == [((EXECUTOR_KEY, (RULE_ID,)),)] * 4
    expected_horizon_call = (
        scenario.horizon_date,
        "frozen_task_date" if scenario.horizon_date else "disabled",
        None if scenario.horizon_date else "authoritative_time_missing",
    )
    assert horizon_calls == [expected_horizon_call] * 4
