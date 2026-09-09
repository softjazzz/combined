"""逐病例冻结截止经真实服务入口进入证据快照，并可离线原样恢复。"""

import pytest

import app.services.luxian_0609.execution as execution
import app.services.luxian_0609.evidence_snapshot_provider as provider
from app.services.luxian_0609.evidence_snapshot_provider import SnapshotSourceRows
from app.services.luxian_0609_rule_catalog import LUXIAN_0609_RULE_SET_KEY
from app.services.qc_diagnostics.execution_inputs import freeze_execution_inputs
from app.services.qc_diagnostics.session_restore import restore_execution_session
from app.services.sichuan_qc_service import SichuanQCService
from tests.unit.test_luxian_0609_scene_bundle_invariance import _scene_bundle


FROZEN = {
    "institute_id": "I", "patient_id": "P", "visit_id": "V", "record_id": "V",
    "record_scene": "final", "admission_datetime": "2026-06-01 08:00:00",
    "discharge_datetime": "2026-06-10 09:30:00", "evaluation_horizon": "2026-06-10",
    "evaluation_basis": "discharge_datetime", "resolution_status": "resolved",
}
SOURCE = "inpat_registration.discharge_horizon"
DERIVED = "evaluation_context.horizon"


def _reader(*, source_key, **kwargs):
    rows = {
        "inpat_registration": [{"admission_datetime": "2026-06-01 08:00:00"}],
        SOURCE: [{"discharge_datetime": "2026-07-20 10:00:00"}],
    }
    return SnapshotSourceRows.create(
        source_key=source_key, rows=rows.get(source_key, ()), truncated=False, limit_rows=50,
    )


async def _entry(monkeypatch, frozen):
    real_build = provider.build_luxian_0609_evidence_read_session
    captured = []

    def build(**kwargs):
        session = real_build(**kwargs, row_reader=_reader)
        captured.append(session)
        return session

    async def no_model(*args, **kwargs):
        pytest.fail("冻结截止入口验证不得调用模型")

    from app.services.qc_llm_client import SichuanQCLLMClient
    monkeypatch.setattr(SichuanQCLLMClient, "generate", no_model)
    monkeypatch.setattr(execution, "build_luxian_0609_evidence_read_session", build)
    bundle = {**_scene_bundle(variant="short"), "scene": "final",
              "institute_id": "I", "patient_id": "P", "visit_id": "V"}
    if frozen is not None:
        bundle["evaluation_horizon_snapshot"] = frozen
    result = await SichuanQCService().evaluate_running_final_bundle_input(
        bundle=bundle, rule_ids=["LX0609-007"], rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        evaluation_horizon_policy="authoritative_discharge", use_execution_cache=False,
    )
    assert len(captured) == 1
    assert result["token_usage"]["total_tokens"] == 0
    return captured[0]


@pytest.mark.asyncio
async def test_frozen_discharge_survives_entry_and_offline_round_trip(monkeypatch):
    session = await _entry(monkeypatch, dict(FROZEN))
    horizon = session.materials.rows(DERIVED)[0]
    assert horizon["horizon_date"] == "2026-06-10"
    assert horizon["horizon_datetime"] == "2026-06-10T09:30:00"
    assert session.materials.rows(SOURCE)[0]["discharge_datetime"] == "2026-07-20 10:00:00"
    frozen = freeze_execution_inputs(
        session, selected_rule_ids=("LX0609-007",), evaluation_as_of_date=None,
        evaluation_horizon_policy="authoritative_discharge", horizon_unavailable_reason=None,
    )

    def forbidden(*args, **kwargs):
        pytest.fail("恢复冻结资料不应重建 Provider 或读取当前来源")

    monkeypatch.setattr(provider, "build_luxian_0609_evidence_read_session", forbidden)
    monkeypatch.setattr(provider, "read_luxian_0609_snapshot_source_rows", forbidden)
    restored = restore_execution_session(frozen, coordinates=("I", "P", "V"))
    assert restored.materials.rows(DERIVED) == session.materials.rows(DERIVED)
    assert restored.materials.rows(SOURCE) == session.materials.rows(SOURCE)
    assert restored.snapshot.snapshot_hash == session.snapshot.snapshot_hash


@pytest.mark.asyncio
@pytest.mark.parametrize("snapshot", [{**FROZEN, "discharge_datetime": ""}, {**FROZEN, "patient_id": "other-case"}])
async def test_missing_or_wrong_case_snapshot_never_falls_back_to_live_discharge(monkeypatch, snapshot):
    session = await _entry(monkeypatch, snapshot)
    assert not session.materials.rows(DERIVED)
    assert session.materials.rows(SOURCE)[0]["discharge_datetime"] == "2026-07-20 10:00:00"


@pytest.mark.asyncio
async def test_legacy_entry_without_frozen_snapshot_keeps_live_horizon(monkeypatch):
    session = await _entry(monkeypatch, None)
    assert session.materials.rows(DERIVED)[0]["horizon_date"] == "2026-07-20"
