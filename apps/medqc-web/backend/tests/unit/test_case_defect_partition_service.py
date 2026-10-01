from __future__ import annotations

from app.services.case_defect_partition_service import build_case_defect_partitions
from app.services import scoring_service


CASE = {"institute_id": "H-1", "patient_id": "P-1", "visit_id": "V-1"}


class Workspace:
    def __init__(self, state: str = "ready") -> None:
        self.dto = {
            "state": state,
            "job_id": "job-1",
            "rule_set_key": "luxian_0609_qc_v1",
            "items": [
                {"rule_id": "LX0609-001", "is_confirmed_issue": True},
                {"rule_id": "LX0609-002", "is_confirmed_issue": False},
            ],
        }

    def build_latest_single_record_result_dto(self, **_kwargs):
        return self.dto


def test_partitions_only_move_owner_results_and_expose_sources():
    workspace = Workspace()

    def scorer(**kwargs):
        pinned = kwargs["workspace_factory"]().build_latest_single_record_result_dto(**CASE)
        assert pinned is workspace.dto
        return {
            "status": scoring_service.STATE_SCORED,
            "job_id": "job-1",
            "standard_name": "住院默认标准",
            "deductions": [
                {"rule_id": "LX0609-001", "is_veto": False},
                {"rule_id": "LX0609-002", "is_veto": True},
            ],
        }

    result = build_case_defect_partitions(
        **CASE,
        scene="running",
        workspace=workspace,
        scorer=scorer,
        projector=lambda items: list(items),
    )

    assert {key: result[key] for key in CASE} == CASE
    assert result["job_id"] == "job-1"
    assert result["confirmed"] == {
        "status": "ready",
        "source": "luxian_0609_canonical_projection",
        "rule_ids": ["LX0609-001"],
        "reason_code": None,
    }
    assert result["veto"] == {
        "status": "ready",
        "source": "scoring_deductions",
        "rule_ids": ["LX0609-002"],
        "standard_name": "住院默认标准",
        "reason_code": None,
    }
    assert result["core"] == {
        "status": "not_integrated",
        "source": "core_system_classification",
        "reason_code": "core_system_classification_missing",
    }


def test_no_standard_is_not_reported_as_empty_veto_partition():
    result = build_case_defect_partitions(
        **CASE,
        scene="final",
        workspace=Workspace(),
        scorer=lambda **_kwargs: {"status": scoring_service.STATE_NO_STANDARD},
        projector=lambda items: list(items),
    )

    assert result["veto"]["status"] == "no_standard"
    assert result["veto"]["rule_ids"] == []
    assert result["veto"]["source"] == "scoring_deductions"


def test_not_ready_result_keeps_partitions_unavailable_instead_of_zero():
    result = build_case_defect_partitions(
        **CASE,
        scene="running",
        workspace=Workspace(state="not_found"),
    )

    assert result["state"] == "not_found"
    assert result["confirmed"]["status"] == "unavailable"
    assert result["veto"]["status"] == "unavailable"
    assert result["confirmed"]["reason_code"] == "result_not_ready"


def test_ready_result_without_job_identity_is_unavailable():
    workspace = Workspace()
    workspace.dto["job_id"] = ""

    result = build_case_defect_partitions(
        **CASE,
        scene="running",
        workspace=workspace,
        projector=lambda items: list(items),
    )

    assert result["state"] == "technical_error"
    assert result["job_id"] == ""
    assert result["confirmed"]["status"] == "unavailable"
    assert result["confirmed"]["reason_code"] == "result_identity_missing"
    assert result["veto"]["reason_code"] == "result_identity_missing"


def test_scoring_result_without_job_identity_cannot_become_veto_partition():
    result = build_case_defect_partitions(
        **CASE,
        scene="running",
        workspace=Workspace(),
        scorer=lambda **_kwargs: {
            "status": scoring_service.STATE_SCORED,
            "job_id": "",
            "deductions": [{"rule_id": "LX0609-001", "is_veto": True}],
        },
        projector=lambda items: list(items),
    )

    assert result["veto"]["status"] == "unavailable"
    assert result["veto"]["rule_ids"] == []
    assert result["veto"]["reason_code"] == "result_changed"


def test_owner_failure_is_partition_local_and_does_not_guess_results():
    def fail_projection(_items):
        raise RuntimeError("private canonical detail")

    def fail_score(**_kwargs):
        raise RuntimeError("private scoring detail")

    result = build_case_defect_partitions(
        **CASE,
        scene="running",
        workspace=Workspace(),
        scorer=fail_score,
        projector=fail_projection,
    )

    assert result["confirmed"]["status"] == "unavailable"
    assert result["confirmed"]["rule_ids"] == []
    assert result["veto"]["status"] == "unavailable"
    assert result["veto"]["rule_ids"] == []
