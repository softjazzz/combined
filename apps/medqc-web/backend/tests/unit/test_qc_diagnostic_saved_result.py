"""正式提交结果旁路，只使用合成资料和事务替身。"""

import json
from types import SimpleNamespace

import pytest

from app.services.qc_diagnostics.capture import capture_scope, capture_committed_results
from test_qc_diagnostic_execution_inputs import session_fixture, record


def receipt(*, job="child", root="root", visit="V"):
    return (("I", "P", visit), json.dumps({"job_id": job, "root_job_id": root,
        "record_ref": "rec_test", "items": [{"rule_id": "LX0609-03-01-01", "status": "data_gap"}]}))


@pytest.fixture
def observed(monkeypatch):
    from app.services import llm_observability
    monkeypatch.setattr(llm_observability, "current_llm_observation_context", lambda:
        SimpleNamespace(root_job_id="root", record_key_hash="case", executor_key="test"))


def test_committed_envelope_exact_and_not_complete(observed):
    session, _ = session_fixture()
    with capture_scope(job_id="child") as capture:
        record(session)
        capture_committed_results((receipt(),))
        assert capture.read_internal()["saved_result"] == json.loads(receipt()[1])
        assert "final_result_not_captured" not in capture.summary()["missing_reasons"]
        assert capture.summary()["capture_completeness"] == "partial"
        capture_committed_results((receipt(),))
        assert "duplicate_saved_result" in capture.summary()["missing_reasons"]
    assert capture.summary()["retained_bytes"] == 0


@pytest.mark.parametrize("wrong", [receipt(job="other"), receipt(root="other"), receipt(visit="other")])
def test_reject_other_job_or_case(observed, wrong):
    session, _ = session_fixture()
    with capture_scope(job_id="child") as capture:
        record(session)
        capture_committed_results((wrong,))
        assert capture.read_internal()["saved_result"] is None
        assert "saved_result_not_matched" in capture.summary()["missing_reasons"]


def test_off_does_not_iterate_results():
    class Unsafe:
        def __iter__(self):
            pytest.fail("capture is off")
    capture_committed_results(Unsafe())


def test_missing_job_binding_does_not_guess(observed):
    session, _ = session_fixture()
    with capture_scope() as capture:
        record(session)
        capture_committed_results((receipt(),))
        assert capture.read_internal()["saved_result"] is None
        assert "saved_result_binding_unavailable" in capture.summary()["missing_reasons"]


@pytest.mark.parametrize("fail_commit, rowcount", [(False, 1), (True, 1), (False, 0)])
def test_transaction_owner_only_notifies_after_success(monkeypatch, fail_commit, rowcount):
    from unittest.mock import Mock
    from app.services import custom_qc_workspace_service as module
    events = []
    db = Mock()
    db.execute.side_effect = [SimpleNamespace(mappings=lambda: SimpleNamespace(first=lambda:
        {"id": "child", "parent_job_id": "root", "status": "running"})), SimpleNamespace(rowcount=rowcount)]
    def commit():
        events.append("commit")
        if fail_commit:
            raise RuntimeError("synthetic transaction failure")
    db.commit.side_effect = commit
    monkeypatch.setattr(module, "_session", lambda: db)
    service = module.CustomQCWorkspaceService()
    receipts = (receipt(),)
    monkeypatch.setattr(service, "_write_record_result_envelopes", lambda *args, **kwargs: receipts)
    monkeypatch.setattr(service, "refresh_parent_batch_job", lambda **kwargs: events.append("refresh"))
    monkeypatch.setattr(module, "capture_committed_results", lambda value: events.append(("capture", value)))
    if fail_commit:
        with pytest.raises(RuntimeError):
            service.complete_batch_job(job_id="child", summary={}, items=[], failed_records=[])
        db.rollback.assert_called_once()
    else:
        service.complete_batch_job(job_id="child", summary={}, items=[], failed_records=[])
    captured = [event for event in events if isinstance(event, tuple)]
    assert captured == ([] if fail_commit or rowcount == 0 else [("capture", receipts)])
    if captured:
        assert events.index("commit") < events.index(captured[0])


@pytest.mark.parametrize("enabled", [False, True])
def test_store_receipt_is_exact_json_written_without_reprojection(enabled):
    from datetime import datetime
    from contextlib import nullcontext
    from app.services.custom_qc_workspace_service import CustomQCWorkspaceService
    statements = []
    db = SimpleNamespace(execute=lambda statement: statements.append(statement))
    item = {"record_id": "V", "visit_id": "V", "institute_id": "I", "patient_id": "P",
            "rule_id": "LX0609-01-01-01", "status": "data_gap", "result_status": "data_gap",
            "display_status": "data_gap", "is_compliant": None}
    with capture_scope(job_id="child") if enabled else nullcontext():
        receipts = CustomQCWorkspaceService()._write_record_result_envelopes(db,
            job_row={"id": "child", "created_by": "owner", "filters_json": "{}"},
            items=[item], now=datetime(2026, 9, 8))
    assert len(statements) == 2
    assert len(receipts) == (1 if enabled else 0)
    if enabled:
        assert receipts[0][1] == statements[-1].compile().params["envelope_json"]


def test_saved_result_shares_capture_quota(observed):
    session, _ = session_fixture()
    with capture_scope() as capture:
        record(session)
        size = capture.summary()["retained_bytes"]
    with capture_scope(job_id="child", max_bytes=size) as capture:
        record(session)
        capture_committed_results((receipt(),))
        assert capture.read_internal()["saved_result"] is None
        assert "capacity_exceeded" in capture.summary()["missing_reasons"]


def test_duplicate_matching_receipts_are_not_accepted(observed):
    session, _ = session_fixture()
    with capture_scope(job_id="child") as capture:
        record(session)
        capture_committed_results((receipt(), receipt()))
        assert capture.read_internal()["saved_result"] is None
        assert "saved_result_not_matched" in capture.summary()["missing_reasons"]


def test_precommit_receipt_overflow_does_not_abort_storage(monkeypatch):
    from datetime import datetime
    from app.services import custom_qc_workspace_service as module
    statements = []
    db = SimpleNamespace(execute=lambda statement: statements.append(statement))
    service = module.CustomQCWorkspaceService()
    item = {"record_id": "V", "visit_id": "V", "institute_id": "I", "patient_id": "P",
            "rule_id": "LX0609-01-01-01", "status": "data_gap", "result_status": "data_gap",
            "display_status": "data_gap", "is_compliant": None}
    monkeypatch.setattr(service, "_envelope_item_from_rule_result", lambda value:
        {**value, "findings": "x" * (4 * 1024 * 1024)})
    with capture_scope(job_id="child"):
        receipts = service._write_record_result_envelopes(db,
            job_row={"id": "child", "created_by": "owner", "filters_json": "{}"},
            items=[item], now=datetime(2026, 9, 8))
    assert len(statements) == 2
    assert receipts == ()
