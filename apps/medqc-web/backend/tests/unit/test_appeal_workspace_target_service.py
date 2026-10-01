"""现代申诉 workspace 目标解析合同。"""

from __future__ import annotations

import pytest

from app.services import appeal_workspace_target_service as target_service
from app.services import record_review_service
from app.services.case_identity import CaseRef
from app.services.qc_workspace.canonical_result_store import (
    customer_safe_projection_key,
    keyed_ref,
)


SOURCE = {
    "institute_id": "H-1", "patient_id": "P-1", "visit_id": "V-1",
    "scene": "running", "root_job_id": "job-1", "envelope_id": "env-1",
    "rule_set_key": record_review_service.LUXIAN_0609_RULE_SET_KEY,
    "rule_set_version": "2026.09.28",
    "items": [{"rule_id": "LX0609-001"}],
}


def record_ref(identity=("H-1", "P-1", "V-1")):
    return keyed_ref(
        "rec", CaseRef(*identity).as_key(), hmac_key=customer_safe_projection_key(),
    )


@pytest.fixture
def source(monkeypatch):
    calls = []

    def resolve(**kwargs):
        calls.append(kwargs)
        return dict(SOURCE)

    monkeypatch.setattr(record_review_service, "resolve_workspace_result_reference", resolve)
    monkeypatch.setattr(
        target_service, "project_customer_items",
        lambda items: [
            {"rule_id": item["rule_id"], "is_confirmed_issue": item.get("confirmed", True)}
            for item in items
        ],
    )
    return calls


def resolve(kind="canonical_defect", **kwargs):
    rule_id = kwargs.pop(
        "rule_id", "lx0609-001" if kind == "canonical_defect" else None,
    )
    return target_service.resolve_workspace_appeal_target(
        target_kind=kind, institute_id="H-1", patient_id="P-1", visit_id="V-1",
        expected_job_id="job-1", expected_envelope_id="env-1",
        rule_id=rule_id,
        **kwargs,
    )


def test_canonical_defect_returns_exact_frozen_reference(source):
    session = object()
    result = resolve(session=session)
    assert result == {
        "_can_show_to_doctor": False,
        "target_kind": "canonical_defect", "target_id": "LX0609-001",
        "institute_id": "H-1", "patient_id": "P-1", "visit_id": "V-1",
        "scene": "running", "root_job_id": "job-1", "envelope_id": "env-1",
        "rule_set_key": record_review_service.LUXIAN_0609_RULE_SET_KEY,
        "rule_set_version": "2026.09.28",
    }
    assert source[0]["session"] is session


def test_score_returns_reference_and_customer_items_without_scoring(source):
    result = resolve("score")
    assert result["target_id"] == "env-1"
    assert result["customer_items"] == [
        {"rule_id": "LX0609-001", "is_confirmed_issue": True},
    ]
    assert "score" not in result and "standard_id" not in result


@pytest.mark.parametrize("kind", ["", "defect", None])
def test_bad_target_kind_fails_before_source_read(source, kind):
    with pytest.raises(target_service.AppealWorkspaceTargetInvalid):
        resolve(kind)
    assert source == []


def test_missing_duplicate_and_non_confirmed_rule_fail_closed(source, monkeypatch):
    with pytest.raises(target_service.AppealWorkspaceTargetNotFound):
        resolve(rule_id="LX0609-999")

    monkeypatch.setattr(
        target_service, "project_customer_items",
        lambda _items: [
            {"rule_id": "LX0609-001", "is_confirmed_issue": True},
            {"rule_id": "LX0609-001", "is_confirmed_issue": True},
        ],
    )
    with pytest.raises(target_service.AppealWorkspaceTargetConflict, match="不唯一"):
        resolve()

    monkeypatch.setattr(
        target_service, "project_customer_items",
        lambda _items: [{"rule_id": "LX0609-001", "is_confirmed_issue": False}],
    )
    with pytest.raises(target_service.AppealWorkspaceTargetConflict, match="不是已确认"):
        resolve()


def test_source_and_projection_errors_are_sanitized(source, monkeypatch):
    def changed(**_kwargs):
        raise record_review_service.RecordReviewConflict("result_changed", "结果已变化")

    monkeypatch.setattr(record_review_service, "resolve_workspace_result_reference", changed)
    with pytest.raises(target_service.AppealWorkspaceTargetConflict, match="结果已变化"):
        resolve()

    monkeypatch.setattr(record_review_service, "resolve_workspace_result_reference", lambda **_kwargs: dict(SOURCE))
    monkeypatch.setattr(target_service, "project_customer_items", lambda _items: 1 / 0)
    with pytest.raises(target_service.AppealWorkspaceTargetUnavailable) as exc:
        resolve("score")
    assert "division" not in str(exc.value).lower()


def test_public_result_wrapper_reuses_current_anchor_and_caller_session(monkeypatch):
    dto = {
        "state": "ready", "job_id": "job-1", "root_job_id": "job-1",
        "envelope_id": "env-1", "rule_set_key": record_review_service.LUXIAN_0609_RULE_SET_KEY,
        "rule_set_version": "2026.09.28", "record_ref": record_ref(),
        "items": [{"rule_id": "LX0609-001"}],
    }
    calls = []
    monkeypatch.setattr(record_review_service, "SessionLocal", None)
    monkeypatch.setattr(record_review_service, "_read_case_dto", lambda identity, factory: dto)
    monkeypatch.setattr(record_review_service, "_envelope_ids", lambda *args, **kwargs: ["env-1"])
    monkeypatch.setattr(
        record_review_service, "_workspace_review_scene",
        lambda session, *, job_id, identity: calls.append((session, job_id, identity)) or "final",
    )
    session = object()
    result = record_review_service.resolve_workspace_result_reference(
        institute_id="H-1", patient_id="P-1", visit_id="V-1",
        expected_job_id="job-1", expected_envelope_id="env-1",
        workspace_factory=lambda: object(), session=session,
    )
    assert result["scene"] == "final" and result["items"] == dto["items"]
    assert calls == [(session, "job-1", ("H-1", "P-1", "V-1"))]


@pytest.mark.parametrize(
    ("job_id", "envelope_id"), [("job-old", "env-1"), ("job-1", "env-old")],
)
def test_public_result_wrapper_rejects_stale_anchor_before_scene(monkeypatch, job_id, envelope_id):
    dto = {
        "state": "ready", "job_id": "job-1", "root_job_id": "job-1",
        "envelope_id": "env-1", "rule_set_key": record_review_service.LUXIAN_0609_RULE_SET_KEY,
        "rule_set_version": "v1", "record_ref": record_ref(), "items": [],
    }
    monkeypatch.setattr(record_review_service, "_require_session", lambda: None)
    monkeypatch.setattr(record_review_service, "_read_case_dto", lambda identity, factory: dto)
    monkeypatch.setattr(record_review_service, "_envelope_ids", lambda *args, **kwargs: ["env-1"])
    monkeypatch.setattr(
        record_review_service, "_workspace_review_scene",
        lambda *_args, **_kwargs: pytest.fail("stale anchor must fail before scene query"),
    )
    with pytest.raises(record_review_service.RecordReviewConflict) as exc:
        record_review_service.resolve_workspace_result_reference(
            institute_id="H-1", patient_id="P-1", visit_id="V-1",
            expected_job_id=job_id, expected_envelope_id=envelope_id,
            workspace_factory=lambda: object(), session=object(),
        )
    assert exc.value.code == "result_changed"
