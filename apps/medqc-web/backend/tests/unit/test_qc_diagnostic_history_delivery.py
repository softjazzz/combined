from unittest.mock import Mock

import pytest

from app.services.qc_diagnostics.contracts import DiagnosticPackageError
from app.services.qc_diagnostics.history_delivery import HistoryDelivery
from app.services.qc_diagnostics.package import load_diagnostic_package
from app.services.qc_diagnostics.replay import inspect_documents, replay_documents


def arguments():
    workspace = Mock()
    workspace.get_batch_job.return_value = {"status": "completed"}
    workspace.get_latest_luxian_0609_record_result.return_value = {
        "state": "ready", "job_id": "job", "record_ref": "ref",
        "items": [{"rule_id": "LX0609-04-03-01", "status": "not_applicable", "reason_code": "trigger_absent_complete"}],
    }
    return dict(workspace=workspace, owner="owner", job_id="job", record_ref="ref",
                institute_id="synthetic-institute", patient_id="synthetic-patient", visit_id="synthetic-visit")


def test_prepare_download_import_and_current_projection(tmp_path):
    delivery, args = HistoryDelivery(), arguments()
    prepared = delivery.prepare(**args)
    blob = delivery.download(owner="owner", token=prepared["token"], confirmed=True)
    args["workspace"].get_batch_job.assert_called_once_with(job_id="job", created_by="owner")
    args["workspace"].get_latest_luxian_0609_record_result.return_value = {}
    assert delivery.download(owner="owner", token=prepared["token"], confirmed=True) == blob
    assert b"synthetic-patient" not in blob
    path = tmp_path / "diagnostic.zip"
    path.write_bytes(blob)
    docs = load_diagnostic_package(path)
    assert inspect_documents(docs)["capture_completeness"] == "partial"
    with pytest.raises(DiagnosticPackageError, match="source_version_unavailable"):
        replay_documents(docs, local_git_commit="a" * 40)
    assert replay_documents(docs, local_git_commit="a" * 40, compare_current=True)["results"][0]["supported"]


@pytest.mark.parametrize("field,value", [("job_id", "other-job"), ("record_ref", "other-record"), ("state", "technical_error")])
def test_wrong_result_binding_rejects(field, value):
    args = arguments()
    args["workspace"].get_latest_luxian_0609_record_result.return_value[field] = value
    with pytest.raises(DiagnosticPackageError, match="diagnostic_result_changed"):
        HistoryDelivery().prepare(**args)


def test_missing_owned_job_never_reads_result():
    args = arguments()
    args["workspace"].get_batch_job.return_value = None
    with pytest.raises(DiagnosticPackageError):
        HistoryDelivery().prepare(**args)
    args["workspace"].get_latest_luxian_0609_record_result.assert_not_called()


def test_confirmation_owner_cancel_and_expiry(monkeypatch):
    delivery = HistoryDelivery()
    prepared = delivery.prepare(**arguments())
    token = prepared["token"]
    for owner, confirmed in (("other", True), ("owner", False)):
        with pytest.raises(DiagnosticPackageError):
            delivery.download(owner=owner, token=token, confirmed=confirmed)
    delivery.discard(owner="other", token=token)
    assert delivery.download(owner="owner", token=token, confirmed=True)
    delivery.discard(owner="owner", token=token)
    with pytest.raises(DiagnosticPackageError):
        delivery.download(owner="owner", token=token, confirmed=True)
    token = delivery.prepare(**arguments())["token"]
    monkeypatch.setattr("app.services.qc_diagnostics.history_delivery.time.monotonic", lambda: float("inf"))
    with pytest.raises(DiagnosticPackageError):
        delivery.download(owner="owner", token=token, confirmed=True)
