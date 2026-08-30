import json

from scripts.audit_luxian_0609_case_rule_chain import (
    audit_case_rule_chain,
    merge_domain_bundles,
    resolve_schema_defaults,
    _resolve_bundle_domain_mapping,
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
    def __init__(self, source_keys=("admission_record",)):
        self.snapshot_schema_version = "snap-v1"
        self.snapshot_hash = "s" * 64
        self.observations = tuple(FakeObservation(source_key=key) for key in source_keys)
        self.facts = ()


class FakeSession:
    def __init__(self, source_keys=("admission_record",)):
        self.snapshot = FakeSnapshot(source_keys)
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


def test_missing_expected_source_observation_is_source_gap():
    report = audit_case_rule_chain(
        institute_id="i",
        patient_id="p",
        visit_id="v",
        rule_id="LX0609-029",
        evidence_session=FakeSession(),
        rule_contract={
            "family_key": "surgery_anesthesia",
            "applicable_documents": ("surgery_record",),
        },
        bundle={
            "bundle_schema_version": "bundle-v6",
            "document_hits": {"surgery_record": True},
            "data_quality_flags": [],
        },
        envelope={"schema_version": "lx0609-record-result-envelope-v1", "items": []},
    )
    assert report["checks"] == {
        "status": "blocked",
        "reason_code": "source_observation_missing",
        "failure_stage": "source",
    }
    assert "surgery_record" in report["cross_layer"]["missing_source_keys"]


def _exam_lab_audit_bundle() -> dict:
    source_keys = (
        "inpat_nondrug_order.exam_lab_order",
        "exam_master",
        "exam_item_report",
        "daily_course_record",
        "first_course_record",
        "rescue_record",
        "senior_course_record",
    )
    return {
        "bundle_schema_version": "bundle-v6",
        "document_hits": {key: True for key in source_keys},
        "data_quality_flags": [],
        "structured_context": {
            "source_table_coverage": {
                key: {"row_count": 1} for key in source_keys
            }
        },
    }


def _exam_lab_audit_contract() -> dict:
    source_keys = (
        "inpat_nondrug_order.exam_lab_order",
        "exam_master",
        "exam_item_report",
        "daily_course_record",
        "first_course_record",
        "rescue_record",
        "senior_course_record",
    )
    return {
        "family_key": "exam_lab",
        "source_keys": source_keys,
        "bundle_source_keys": source_keys,
    }


def _compliant_envelope(rule_id: str) -> dict:
    return {
        "schema_version": "lx0609-record-result-envelope-v1",
        "items": [
            {
                "rule_id": rule_id,
                "status": "compliant",
                "result_status": "compliant",
                "is_compliant": True,
                "reason_code": "ok",
                "evidence": [],
            }
        ],
    }


def test_derived_source_marker_does_not_block_physical_exam_sources():
    session = FakeSession(
        (
            "medical_order",
            "inpat_nondrug_order.exam_lab_order",
            "exam_master",
            "exam_item_report",
            "daily_course_record",
            "first_course_record",
            "rescue_record",
            "senior_course_record",
        )
    )
    observations = list(session.snapshot.observations)
    marker = next(item for item in observations if item.source_key == "medical_order")
    marker.query_state = "unavailable"
    marker.completeness = "unproven"
    marker.record_count = None
    session.snapshot.observations = tuple(observations)

    report = audit_case_rule_chain(
        institute_id="i",
        patient_id="p",
        visit_id="v",
        rule_id="LX0609-010",
        evidence_session=session,
        rule_contract=_exam_lab_audit_contract(),
        bundle=_exam_lab_audit_bundle(),
        envelope=_compliant_envelope("LX0609-010"),
    )

    assert report["checks"] == {
        "status": "ready",
        "reason_code": "ready",
        "failure_stage": "canonical_envelope",
    }
    assert "medical_order" in report["cross_layer"]["ignored_source_keys"]


def test_physical_exam_source_gap_still_blocks_with_derived_marker():
    session = FakeSession(
        (
            "medical_order",
            "inpat_nondrug_order.exam_lab_order",
            "exam_master",
            "exam_item_report",
            "daily_course_record",
            "first_course_record",
            "rescue_record",
            "senior_course_record",
        )
    )
    observations = list(session.snapshot.observations)
    for item in observations:
        if item.source_key in {
            "medical_order",
            "inpat_nondrug_order.exam_lab_order",
        }:
            item.query_state = "unavailable"
            item.completeness = "unproven"
            item.record_count = None
    session.snapshot.observations = tuple(observations)

    report = audit_case_rule_chain(
        institute_id="i",
        patient_id="p",
        visit_id="v",
        rule_id="LX0609-010",
        evidence_session=session,
        rule_contract=_exam_lab_audit_contract(),
        bundle=_exam_lab_audit_bundle(),
        envelope=_compliant_envelope("LX0609-010"),
    )

    assert report["checks"] == {
        "status": "blocked",
        "reason_code": "data_gap",
        "failure_stage": "source",
    }
    assert "inpat_nondrug_order.exam_lab_order" in report["source"]["blocked_keys"]


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
        bundle={
            "bundle_schema_version": "bundle-v6",
            "document_hits": {"admission_record": True},
            "data_quality_flags": [],
            "structured_context": {
                "source_table_coverage": {"admission_record": {"row_count": 1}}
            },
        },
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
        evidence_session=FakeSession(("inpat_drug_order", "daily_course_record")),
        rule_contract={"family_key": "extended_document"},
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
        bundle={
            "bundle_schema_version": "bundle-v6",
            "document_hits": {"admission_record": True},
            "structured_context": {
                "source_table_coverage": {"admission_record": {"row_count": 1}}
            },
        },
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


def test_multi_domain_bundles_are_merged_for_rule_coverage():
    merged = merge_domain_bundles(
        {
            "course": {
                "bundle_schema_version": "bundle-v6",
                "document_hits": {"daily_course_record": True},
                "data_quality_flags": [],
                "structured_context": {
                    "source_table_coverage": {
                        "daily_course_record": {"row_count": 1},
                    }
                },
            },
            "consult_discussion": {
                "bundle_schema_version": "bundle-v6",
                "document_hits": {"consultation_record": True},
                "data_quality_flags": [],
                "structured_context": {
                    "source_table_coverage": {
                        "consultation_record": {"row_count": 1},
                    }
                },
            },
        }
    )
    report = audit_case_rule_chain(
        institute_id="i",
        patient_id="p",
        visit_id="v",
        rule_id="LX0609-020",
        evidence_session=FakeSession(("consultation_record", "daily_course_record")),
        rule_contract={
            "family_key": "consultation_quality",
            "applicable_documents": ("consultation_record", "daily_course_record"),
            "source_keys": ("consultation_record", "daily_course_record"),
        },
        bundle=merged,
        envelope={
            "schema_version": "lx0609-record-result-envelope-v1",
            "items": [
                {
                    "rule_id": "LX0609-020",
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
        "status": "ready",
        "reason_code": "ready",
        "failure_stage": "canonical_envelope",
    }
    assert set(report["bundle"]["domains"]) == {"course", "consult_discussion"}


def test_unknown_applicable_document_blocks_with_domain_mapping_error():
    report = audit_case_rule_chain(
        institute_id="i",
        patient_id="p",
        visit_id="v",
        rule_id="LX0609-001",
        evidence_session=FakeSession(("unknown_document",)),
        rule_contract={
            "family_key": "basic_timeliness",
            "applicable_documents": ("admission_record", "unknown_document"),
        },
        bundle=None,
        envelope=None,
    )
    assert report["checks"] == {
        "status": "technical_error",
        "reason_code": "domain_mapping_unavailable",
        "failure_stage": "bundle",
    }
    assert report["cross_layer"]["bundle_domains"] == ["admission"]
    assert report["cross_layer"]["unmapped_bundle_documents"] == [
        "unknown_document"
    ]
    # 不应把映射失败伪装成 Bundle 行缺失。
    assert report["checks"]["reason_code"] != "bundle_missing"


def test_derived_documents_map_to_parent_bundle_domain():
    domains, unmapped, reason = _resolve_bundle_domain_mapping(
        {
            "applicable_documents": (
                "daily_course_record",
                "exam_attention_report",
                "lab_attention_report",
                "senior_course_record",
            )
        }
    )
    assert domains == ("course",)
    assert unmapped == ()
    assert reason is None


def test_conflicting_duplicate_bundle_coverage_is_not_ready():
    merged = merge_domain_bundles(
        {
            "course": {
                "bundle_schema_version": "bundle-v6",
                "document_hits": {"daily_course_record": True},
                "structured_context": {
                    "source_table_coverage": {
                        "daily_course_record": {"row_count": 1}
                    }
                },
            },
            "consult_discussion": {
                "bundle_schema_version": "bundle-v6",
                "document_hits": {"daily_course_record": True},
                "structured_context": {
                    "source_table_coverage": {
                        "daily_course_record": {"row_count": 2}
                    }
                },
            },
        }
    )
    report = audit_case_rule_chain(
        institute_id="i",
        patient_id="p",
        visit_id="v",
        rule_id="LX0609-020",
        evidence_session=FakeSession(("consultation_record", "daily_course_record")),
        rule_contract={
            "family_key": "consultation_quality",
            "applicable_documents": ("consultation_record", "daily_course_record"),
            "source_keys": ("consultation_record", "daily_course_record"),
        },
        bundle=merged,
        envelope={
            "schema_version": "lx0609-record-result-envelope-v1",
            "items": [
                {
                    "rule_id": "LX0609-020",
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
        "reason_code": "bundle_coverage_conflict",
        "failure_stage": "bundle",
    }


def test_missing_required_domain_bundle_is_not_ready():
    merged = merge_domain_bundles(
        {
            "course": {
                "bundle_schema_version": "bundle-v6",
                "document_hits": {"daily_course_record": True},
                "structured_context": {
                    "source_table_coverage": {
                        "daily_course_record": {"row_count": 1}
                    }
                },
            },
            "consult_discussion": None,
        }
    )
    report = audit_case_rule_chain(
        institute_id="i",
        patient_id="p",
        visit_id="v",
        rule_id="LX0609-020",
        evidence_session=FakeSession(("daily_course_record",)),
        rule_contract={
            "family_key": "consultation_quality",
            "applicable_documents": ("daily_course_record", "consultation_record"),
            "source_keys": ("daily_course_record",),
        },
        bundle=merged,
        envelope=_compliant_envelope("LX0609-020"),
    )
    assert report["checks"] == {
        "status": "technical_error",
        "reason_code": "bundle_domain_missing",
        "failure_stage": "bundle",
    }
    assert report["bundle"]["missing_domains"] == ["consult_discussion"]
