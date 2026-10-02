"""纯预览拒绝不完整前置，确认不触发任何业务写入。"""
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.services.qc_agent import business_actions as actions
from app.services.qc_agent.business_schemas import BusinessContext


@pytest.fixture
def inputs():
    ref = actions.ActionRecordRef(institute_id="H", patient_id="P", visit_id="V")
    # 由实际权威交付范围选择可执行规则，不用第二份发布清单。
    active, _ = actions.partition_luxian_0609_rule_scope(actions.get_luxian_0609_customer_delivery_rule_ids())
    accepted = set(actions.get_luxian_0609_acceptance_only_rule_ids())
    rule = next(item for item in active if item not in accepted)
    now = datetime(2026, 10, 2, tzinfo=timezone.utc)
    return dict(
        request=actions.ActionRequest(operation="single_recheck", record_refs=(ref,), rule_ids=(rule,)),
        context=BusinessContext(view="doctor", **ref.model_dump(), care_phase="discharged"),
        owner_id="doctor", session_id="session", authorized_record_refs=(ref,),
        material_versions=(actions.MaterialVersion(record_ref=ref, version="source-v1", synchronization_verified=True),),
        expires_at=now + timedelta(minutes=5), now=now,
    )


def confirm(preview, inputs, **changes):
    args = {key: value for key, value in inputs.items() if key not in {"request", "expires_at"}}
    args.update(changes)
    return actions.validate_confirmation(preview, actions.ActionConfirmation(
        confirmed=True, confirmation_hash=preview.confirmation_hash), **args)


def test_formal_contract_and_repeat_confirmation_are_pure(inputs):
    preview = actions.build_action_preview(**inputs)
    assert preview.allowed
    first = confirm(preview, inputs)
    assert first == confirm(preview, inputs)
    assert first.model_dump(mode="json") == {
        "rule_set_key": "luxian_0609_qc_v1", "rule_ids": list(inputs["request"].rule_ids),
        "record_refs": [inputs["request"].record_refs[0].model_dump()], "scope": "final",
    }
    assert "job_id" not in preview.model_dump()


@pytest.mark.parametrize("kind", ["unauthorized", "unsynced", "missing", "duplicate", "unknown_rule", "doctor_batch", "missing_phase"])
def test_blocked_preview_cannot_confirm(inputs, kind):
    if kind == "unauthorized":
        inputs["authorized_record_refs"] = ()
    elif kind == "unsynced":
        inputs["material_versions"] = (inputs["material_versions"][0].model_copy(update={"synchronization_verified": False}),)
    elif kind == "missing":
        inputs["material_versions"] = ()
    elif kind == "duplicate":
        inputs["request"] = inputs["request"].model_copy(update={"record_refs": inputs["request"].record_refs * 2})
    elif kind == "unknown_rule":
        inputs["request"] = inputs["request"].model_copy(update={"rule_ids": ("LX0609-99-99-99",)})
    elif kind == "doctor_batch":
        inputs["request"] = inputs["request"].model_copy(update={"operation": "specialist_batch"})
    else:
        inputs["context"] = inputs["context"].model_copy(update={"care_phase": None})
    preview = actions.build_action_preview(**inputs)
    assert not preview.allowed and preview.formal_request is None and preview.blocked_reasons
    with pytest.raises(ValueError):
        confirm(preview, inputs)


@pytest.mark.parametrize("change", ["owner", "session", "expiry", "authorization", "material", "context", "catalog", "tamper"])
def test_confirmation_rechecks_frozen_inputs(inputs, monkeypatch, change):
    preview = actions.build_action_preview(**inputs)
    changes = {}
    if change == "owner":
        changes["owner_id"] = "other"
    elif change == "session":
        changes["session_id"] = "other"
    elif change == "expiry":
        changes["now"] = inputs["expires_at"]
    elif change == "authorization":
        changes["authorized_record_refs"] = ()
    elif change == "material":
        changes["material_versions"] = (inputs["material_versions"][0].model_copy(update={"version": "source-v2"}),)
    elif change == "context":
        changes["context"] = inputs["context"].model_copy(update={"care_phase": "inpatient"})
    elif change == "catalog":
        monkeypatch.setattr(actions, "LUXIAN_0609_RULE_MASTER_VERSION", "changed")
    else:
        preview = preview.model_copy(update={"owner_id": "tampered"})
        changes["owner_id"] = "tampered"
    with pytest.raises(ValueError):
        confirm(preview, inputs, **changes)


def test_confirm_rejects_client_parameters_and_false_confirmation():
    with pytest.raises(ValidationError):
        actions.ActionConfirmation(confirmed=False, confirmation_hash="a" * 64)
    with pytest.raises(ValidationError):
        actions.ActionConfirmation(confirmed=True, confirmation_hash="a" * 64, rule_ids=["other"])


def test_manager_scope_and_phase(inputs):
    inputs["context"] = BusinessContext(view="manager", institute_id="H", department="D", care_phase="inpatient", completed_from="2026-09-01", completed_to="2026-09-30")
    inputs["request"] = inputs["request"].model_copy(update={"operation": "specialist_batch"})
    preview = actions.build_action_preview(**inputs)
    assert preview.allowed and confirm(preview, inputs).scope == "running"
    assert "start_date" not in preview.formal_request.model_dump()
    inputs["context"] = inputs["context"].model_copy(update={"department": None})
    assert not actions.build_action_preview(**inputs).allowed


def test_paused_rule_and_duplicate_material_versions_are_blocked(inputs):
    _, pending = actions.partition_luxian_0609_rule_scope(actions.get_luxian_0609_customer_delivery_rule_ids())
    assert pending, "真实目录应有暂停范围反例"
    inputs["request"] = inputs["request"].model_copy(update={"rule_ids": (pending[0],)})
    preview = actions.build_action_preview(**inputs)
    assert not preview.allowed
    assert any("未正式执行" in note or "待验收" in note for note in preview.blocked_reasons)
    inputs["material_versions"] *= 2
    assert any("冲突" in note for note in actions.build_action_preview(**inputs).blocked_reasons)


def test_confirm_hash_must_match_server_preview(inputs):
    preview = actions.build_action_preview(**inputs)
    args = {key: value for key, value in inputs.items() if key not in {"request", "expires_at"}}
    with pytest.raises(ValueError, match="不一致"):
        actions.validate_confirmation(preview, actions.ActionConfirmation(
            confirmed=True, confirmation_hash="0" * 64), **args)
