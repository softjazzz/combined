import json

from scripts.audit_luxian_0609_case_rule_chain import (
    audit_case_rule_chain,
    resolve_schema_defaults,
)


class FakeObservation:
    def __init__(self, source_key="admission_record", query_state="available", completeness="complete", record_count=1, snapshot_ref="sha256:a"):
        self.source_key = source_key
        self.query_state = query_state
        self.completeness = completeness
        self.record_count = record_count
        self.snapshot_ref = snapshot_ref
        self.query_version = "q1"


class FakeSnapshot:
    def __init__(self):
        self.snapshot_schema_version = "snap-v1"
        self.snapshot_hash = "s" * 64
        self.observations = (FakeObservation(),)
        self.facts = ()


class FakeSession:
    def __init__(self):
        self.snapshot = FakeSnapshot()
        self.materials = object()


def test_report_does_not_leak_sensitive_values_and_hash_is_stable():
    report = audit_case_rule_chain(
        institute_id="INST-SECRET", patient_id="PAT-SECRET", visit_id="VIS-SECRET", rule_id="LX0609-001",
        evidence_session=FakeSession(),
        rule_contract={"family_key": "basic_timeliness", "rule_version": "v1"},
        bundle={"bundle_schema_version": "bundle-v6", "document_hits": {"admission_record": 1}, "data_quality_flags": []},
        envelope={"schema_version": "lx0609-record-result-envelope-v1", "items": [{"rule_id": "LX0609-001", "status": "compliant", "result_status": "compliant", "is_compliant": True, "reason_code": "ok", "evidence": []}]},
        git_commit="abc",
    )
    encoded = json.dumps(report, ensure_ascii=False)
    assert "INST-SECRET" not in encoded and "PAT-SECRET" not in encoded and "VIS-SECRET" not in encoded
    assert report["case_ref"].startswith("sha256:")
    again = audit_case_rule_chain(
        institute_id="INST-SECRET", patient_id="PAT-SECRET", visit_id="VIS-SECRET", rule_id="LX0609-001",
        evidence_session=FakeSession(), rule_contract={"family_key": "basic_timeliness", "rule_version": "v1"},
        bundle={"bundle_schema_version": "bundle-v6", "document_hits": {"admission_record": 1}, "data_quality_flags": []},
        envelope={"schema_version": "lx0609-record-result-envelope-v1", "items": [{"rule_id": "LX0609-001", "status": "compliant", "result_status": "compliant", "is_compliant": True, "reason_code": "ok", "evidence": []}]}, git_commit="abc")
    assert report["case_ref"] == again["case_ref"]
    assert report["source"]["hash"] == again["source"]["hash"]


def test_source_gap_blocks_and_envelope_mismatch_is_technical_error():
    session = FakeSession()
    session.snapshot.observations = (FakeObservation(query_state="unavailable", completeness="unproven", record_count=None),)
    report = audit_case_rule_chain(
        institute_id="i", patient_id="p", visit_id="v", rule_id="LX0609-001", evidence_session=session,
        rule_contract={"family_key": "basic_timeliness"}, bundle={"bundle_schema_version": "bundle-v6", "document_hits": {}, "data_quality_flags": []},
        envelope=None,
    )
    assert report["checks"]["status"] == "blocked"
    assert report["checks"]["reason_code"] == "data_gap"
    session.snapshot.observations = (FakeObservation(),)
    report = audit_case_rule_chain(
        institute_id="i", patient_id="p", visit_id="v", rule_id="LX0609-001", evidence_session=session,
        rule_contract={"family_key": "basic_timeliness"}, bundle={"bundle_schema_version": "bundle-v6", "document_hits": {}, "data_quality_flags": []},
        envelope={"schema_version": "wrong", "items": []},
    )
    assert report["checks"]["status"] == "technical_error"


def test_split_schema_defaults_follow_runtime_search_path():
    assert resolve_schema_defaults("split") == {
        "source": "cdm",
        "bundle": "public",
        "canonical": "qc",
    }
    assert resolve_schema_defaults("single") == {
        "source": "public",
        "bundle": "public",
        "canonical": "public",
    }


def test_source_and_bundle_count_mismatch_is_blocked_as_technical_error():
    report = audit_case_rule_chain(
        institute_id="i",
        patient_id="p",
        visit_id="v",
        rule_id="LX0609-001",
        evidence_session=FakeSession(),
        rule_contract={"family_key": "basic_timeliness"},
        bundle={
            "bundle_schema_version": "bundle-v6",
            "document_hits": {"admission_record": True},
            "data_quality_flags": [],
            "structured_context": {
                "source_table_coverage": {
                    "admission_record": {"row_count": 0},
                }
            },
        },
        envelope={
            "schema_version": "lx0609-record-result-envelope-v1",
            "items": [
                {
                    "rule_id": "LX0609-001",
                    "status": "compliant",
                    "result_status": "compliant",
                    "is_compliant": True,
                    "reason_code": "ok",
                    "evidence": [],
                }
            ],
        },
    )
    assert report["checks"] == {
        "status": "technical_error",
        "reason_code": "bundle_source_count_mismatch",
        "failure_stage": "bundle",
    }
    assert report["cross_layer"]["bundle_source_count_mismatches"] == [
        {"source_key": "admission_record", "source_count": 1, "bundle_count": 0}
    ]


def test_api_non_ready_is_api_gap_after_canonical_ready():
    report = audit_case_rule_chain(
        institute_id="i", patient_id="p", visit_id="v", rule_id="LX0609-001",
        evidence_session=FakeSession(), rule_contract={"family_key": "basic_timeliness"},
        bundle={"bundle_schema_version": "bundle-v6", "document_hits": {"admission_record": True}, "data_quality_flags": []},
        envelope={"schema_version": "lx0609-record-result-envelope-v1", "items": [{"rule_id": "LX0609-001", "status": "compliant", "result_status": "compliant", "is_compliant": True, "reason_code": "ok", "evidence": []}]},
        api_summary={"status": "pending", "ready": False},
    )
    assert report["checks"] == {"status": "blocked", "reason_code": "api_gap", "failure_stage": "api"}


def test_empty_source_observations_are_blocked_source_gap():
    session = FakeSession()
    session.snapshot.observations = ()
    report = audit_case_rule_chain(
        institute_id="i", patient_id="p", visit_id="v", rule_id="LX0609-001",
        evidence_session=session, rule_contract={"family_key": "basic_timeliness"},
        bundle={"bundle_schema_version": "bundle-v6", "document_hits": {"admission_record": True}},
        envelope={"schema_version": "lx0609-record-result-envelope-v1", "items": []},
    )
    assert report["checks"] == {"status": "blocked", "reason_code": "source_gap", "failure_stage": "source"}


def test_expected_bundle_document_coverage_is_required():
    report = audit_case_rule_chain(
        institute_id="i", patient_id="p", visit_id="v", rule_id="LX0609-054",
        evidence_session=FakeSession(), rule_contract={"family_key": "extended_document"},
        bundle={"bundle_schema_version": "bundle-v6", "document_hits": {"discharge_record": True}},
        envelope={"schema_version": "lx0609-record-result-envelope-v1", "items": []},
    )
    assert report["checks"] == {
        "status": "technical_error",
        "reason_code": "bundle_source_coverage_missing",
        "failure_stage": "bundle",
    }
    assert "inpat_drug_order" in report["cross_layer"]["missing_bundle_keys"]


def test_canonical_envelope_identity_must_match_requested_job_and_record():
    envelope = {
        "schema_version": "lx0609-record-result-envelope-v1",
        "job_id": "other-job",
        "record_id": "other-record",
        "items": [{"rule_id": "LX0609-001", "status": "compliant", "result_status": "compliant", "is_compliant": True, "reason_code": "ok", "evidence": []}],
    }
    report = audit_case_rule_chain(
        institute_id="i", patient_id="p", visit_id="v", rule_id="LX0609-001",
        evidence_session=FakeSession(), rule_contract={"family_key": "basic_timeliness"},
        bundle={"bundle_schema_version": "bundle-v6", "document_hits": {"admission_record": True}},
        envelope=envelope, expected_job_id="requested-job", expected_record_id="v",
    )
    assert report["checks"] == {
        "status": "technical_error",
        "reason_code": "canonical_envelope_identity_mismatch",
        "failure_stage": "canonical_envelope",
    }


def test_cli_scope_explicitly_excludes_api_and_ui():
    report = audit_case_rule_chain(
        institute_id="i", patient_id="p", visit_id="v", rule_id="LX0609-001",
        evidence_session=FakeSession(), rule_contract={"family_key": "basic_timeliness"},
        bundle={"bundle_schema_version": "bundle-v6", "document_hits": {"admission_record": True}},
        envelope={"schema_version": "lx0609-record-result-envelope-v1", "items": [{"rule_id": "LX0609-001", "status": "compliant", "result_status": "compliant", "is_compliant": True, "reason_code": "ok", "evidence": []}]},
    )
    assert report["verification_scope"]["api"] == "not_verified_by_cli"
    assert report["verification_scope"]["ui"] == "not_verified_by_cli"
