from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.services import defect_rectification_service as service


def test_canonical_source_locks_same_case_and_rejects_changed_round(monkeypatch):
    from app.services import appeal_workspace_target_service as targets
    from app.services.qc_workspace import canonical_result_store as store
    locks = Mock()
    monkeypatch.setattr(store, "lock_case_result_mutations", locks)
    data = {"institute_id": "H1", "patient_id": "P1", "visit_id": "V1", "scene": "running",
            "target_kind": "canonical_defect", "target_id": "R1", "root_job_id": "J1", "envelope_id": "E1"}
    monkeypatch.setattr(targets, "resolve_workspace_appeal_target", lambda **kwargs: data)
    session = Mock()
    assert service._source(session, data) == data
    assert locks.call_args.args[0] is session
    assert tuple(locks.call_args.args[1][0]) == ("H1", "P1", "V1")
    assert locks.call_args.kwargs["rule_set_key"]
    monkeypatch.setattr(targets, "resolve_workspace_appeal_target", lambda **kwargs: {**data, "envelope_id": "new"})
    with pytest.raises(service.RectificationError):
        service._source(session, data)


@pytest.mark.parametrize("visible,allowed", [(False, {"R1"}), (True, set())])
def test_visibility_uses_both_frozen_config_and_safe_result_flag(monkeypatch, visible, allowed):
    from app.services import doctor_rule_visibility_service as visibility
    monkeypatch.setattr(visibility, "visible_rule_ids", lambda **kwargs: allowed)
    with pytest.raises(service.RectificationError):
        service._visible({"target_kind": "canonical_defect", "target_id": "R1", "rule_set_key": "K",
                          "rule_set_version": "V", "_can_show_to_doctor": visible},
                         {"institute_id": "H1", "department": "内科"})


@pytest.mark.parametrize("status", ["pending", "urged", "rejected"])
def test_manual_source_requires_locked_approved_target(monkeypatch, status):
    from app.services import appeal_manual_target_service as targets

    data = {"institute_id": "H1", "patient_id": "P1", "visit_id": "V1", "scene": "running",
            "target_kind": "task_manual_defect", "target_id": "D1", "root_job_id": "J1", "envelope_id": "E1"}
    loader = Mock(return_value=data)
    monkeypatch.setattr(targets, "resolve_task_manual_defect_target", loader)
    session = Mock()
    session.execute.return_value.scalar_one.return_value = SimpleNamespace(
        manual_review_status="approved", status=status,
    )
    assert service._source(session, data) == data
    assert loader.call_args.kwargs["lock"] is True
    assert loader.call_args.kwargs["session"] is session
    assert loader.call_args.kwargs["defect_id"] == "D1"


@pytest.mark.parametrize("review,status", [("pending", "pending"), ("rejected", "pending"),
                                         ("approved", "resolved"), ("approved", "withdrawn")])
def test_manual_source_rejects_unapproved_or_inactive_defect(monkeypatch, review, status):
    from app.services import appeal_manual_target_service as targets

    data = {"institute_id": "H1", "patient_id": "P1", "visit_id": "V1", "scene": "running",
            "target_kind": "task_manual_defect", "target_id": "D1", "root_job_id": "J1", "envelope_id": "E1"}
    monkeypatch.setattr(targets, "resolve_task_manual_defect_target", lambda **kwargs: data)
    session = Mock()
    session.execute.return_value.scalar_one.return_value = SimpleNamespace(
        manual_review_status=review, status=status,
    )
    with pytest.raises(service.RectificationError) as error:
        service._source(session, data)
    assert error.value.status == 409


@pytest.mark.parametrize("key", ["institute_id", "patient_id", "visit_id", "scene", "target_kind",
                                 "target_id", "root_job_id", "envelope_id"])
def test_manual_source_rejects_any_frozen_identity_mismatch(monkeypatch, key):
    from app.services import appeal_manual_target_service as targets

    data = {"institute_id": "H1", "patient_id": "P1", "visit_id": "V1", "scene": "running",
            "target_kind": "task_manual_defect", "target_id": "D1", "root_job_id": "J1", "envelope_id": "E1"}
    monkeypatch.setattr(targets, "resolve_task_manual_defect_target", lambda **kwargs: {**data, key: "changed"})
    session = Mock()
    session.execute.return_value.scalar_one.return_value = SimpleNamespace(
        manual_review_status="approved", status="pending",
    )
    with pytest.raises(service.RectificationError) as error:
        service._source(session, data)
    assert error.value.status == 409
