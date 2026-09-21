import pytest

from app.services import sample_programmatic_evidence as evidence_module
from app.services.luxian_0916.critical_value_018 import (
    build_critical_value_018_facts,
)
from app.services.sample_programmatic_evidence import build_programmatic_evidence_payload
from app.services.qc_input_adapters.running_final_bundle_adapter import (
    adapt_bundle_to_evidence_payload,
)


class _FakeRows:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None


class _FakeConnection:
    def __init__(self, rows_by_table):
        self._rows_by_table = rows_by_table
        self.source_query_limits = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def execute(self, statement, params):
        query = str(statement)
        if "cdm.inpat_registration" in query:
            return _FakeRows([])
        table_name = next(
            table_name
            for table_name in self._rows_by_table
            if f"cdm.{table_name}" in query
        )
        self.source_query_limits.append((table_name, params["limit"]))
        rows = self._rows_by_table[table_name]
        if isinstance(rows, Exception):
            raise rows
        if callable(rows):
            rows = rows(params)
        return _FakeRows(rows)


class _FakeEngine:
    def __init__(self, connection):
        self._connection = connection

    def connect(self):
        return self._connection


def test_build_programmatic_evidence_payload_should_flatten_structured_documents_and_render_titles():
    payload = build_programmatic_evidence_payload(
        bundle={
            "medical_text": "",
            "structured_context": {
                "documents": {
                    "first_course_record": [
                        {
                            "document_id": "F1",
                            "document_title": "首次病程记录",
                            "display_time": "2026-04-01 08:30:00",
                            "text_preview": "首次病程内容",
                        }
                    ],
                    "consultation_record": [
                        {
                            "document_id": "C1",
                            "document_title": "会诊记录",
                            "display_time": "2026-04-02 10:00:00",
                            "text_preview": "会诊申请时间：2026-04-02 08:00\n会诊意见：建议继续观察",
                        }
                    ],
                    "discharge_record": [
                        {
                            "document_id": "D1",
                            "document_title": "出院记录",
                            "display_time": "2026-04-05 09:00:00",
                            "text_preview": "医师签名：张医生",
                        }
                    ],
                },
                "discharge_datetime": "2026-04-05 08:00:00",
            },
        }
    )

    timeline = payload["programmatic_timeline"]

    assert timeline["documents"]["first_course_record"][0]["title"] == "首次病程记录"
    assert timeline["documents"]["consultation_record"][0]["request_at"] == "2026-04-02 08:00:00"
    assert payload["primary_document_text"].count("首次病程记录") == 1
    assert "记录时间：2026-04-01 08:30:00" in payload["primary_document_text"]
    assert "出院时间：2026-04-05 08:00:00" in payload["primary_document_text"]


def test_bundle_report_id_survives_evidence_projection_closed_loop(monkeypatch):
    """Bundle真实报告ID应贯穿适配器和程序化证据，不回退成合成ID。"""
    monkeypatch.setattr(
        evidence_module,
        "_fetch_source_table_fallback_items",
        lambda bundle_payload: ([], {}),
    )
    bundle = {
        "scene": "final",
        "visit_id": "VISIT-043",
        "source_doc_priority": ["admission_record", "labtest_item_report"],
        "source_documents": [
            {
                "source_table": "admission_record",
                "document_id": "ADMISSION-1",
                "document_title": "入院记录",
                "content": "主诉：腹痛。",
            },
            {
                "source_table": "labtest_item_report",
                "document_id": "LAB-009",
                "test_id": "LAB-009",
                "document_title": "尿培养报告",
                "record_time": "2026-08-20 10:00:00",
                "content": "尿培养：大肠埃希菌阳性。",
            },
        ],
        "structured_context": {},
    }

    adapted = adapt_bundle_to_evidence_payload(bundle)
    projected = build_programmatic_evidence_payload(bundle=bundle)

    assert adapted["supporting_documents"][0]["document_id"] == "LAB-009"
    lab_events = projected["programmatic_timeline"]["documents"]["labtest_item_report"]
    assert [event["document_id"] for event in lab_events] == ["LAB-009"]


def test_fallback_lab_event_merges_into_bundle_report_id(monkeypatch):
    """同一检验申请的 fallback 行必须复用 Bundle 的真实报告文书 ID。"""

    monkeypatch.setattr(
        evidence_module,
        "_fetch_source_table_fallback_items",
        lambda bundle_payload: (
            [
                {
                    "source_table": "labtest_item_report",
                    "document_id": "VISIT-labtest_item_report-supp-001",
                    "test_id": "TEST-001",
                    "test_no": "REQ-001",
                    "document_title": "尿培养报告（补充）",
                    "content": "尿培养结果：大肠埃希菌阳性，补充完整结果。",
                }
            ],
            {},
        ),
    )
    payload = build_programmatic_evidence_payload(
        bundle={
            "visit_id": "VISIT-043",
            "source_documents": [
                {
                    "source_table": "labtest_item_report",
                    "document_id": "LAB-009",
                    "test_id": "TEST-001",
                    "test_no": "REQ-001",
                    "document_title": "尿培养报告",
                    "content": "尿培养结果：大肠埃希菌阳性。",
                }
            ],
        }
    )

    events = payload["programmatic_timeline"]["documents"]["labtest_item_report"]
    assert len(events) == 1
    assert events[0]["document_id"] == "LAB-009"


def test_fallback_lab_events_with_different_business_keys_are_not_merged():
    bundle_item = {
        "source_table": "labtest_item_report",
        "document_id": "LAB-009",
        "test_id": "TEST-001",
        "test_no": "REQ-001",
        "content": "尿培养结果：大肠埃希菌阳性。",
    }
    fallback_item = {
        "source_table": "labtest_item_report",
        "document_id": "VISIT-labtest_item_report-supp-001",
        "test_id": "TEST-002",
        "test_no": "REQ-002",
        "content": "血常规结果：白细胞升高。",
    }

    merged = evidence_module._merge_fallback_items([bundle_item], [fallback_item])

    assert [item["document_id"] for item in merged] == [
        "LAB-009",
        "VISIT-labtest_item_report-supp-001",
    ]


def test_fallback_lab_event_matches_bundle_document_id_when_bundle_key_is_nested():
    """Bundle 仅保留真实报告 ID 时，仍应吸收同 ID 的 fallback 行。"""

    merged = evidence_module._merge_fallback_items(
        [
            {
                "source_table": "labtest_item_report",
                "document_id": "LAB-009",
                "report_items": [{"item_id": "LABITEM-009"}],
                "content": "尿培养结果：大肠埃希菌阳性。",
            }
        ],
        [
            {
                "source_table": "labtest_item_report",
                "document_id": "VISIT-labtest_item_report-supp-001",
                "test_id": "LAB-009",
                "test_no": "LAB-009",
                "content": "尿培养结果：大肠埃希菌阳性，补充完整结果。",
            }
        ],
    )

    assert len(merged) == 1
    assert merged[0]["document_id"] == "LAB-009"


def test_build_programmatic_evidence_payload_should_fallback_to_admission_record_timeline_record_time():
    payload = build_programmatic_evidence_payload(
        bundle={
            "timeline_facts": [
                {
                    "source_table": "admission_record",
                    "field": "record_time",
                    "value": "2026-01-24 20:42:25",
                }
            ],
            "structured_context": {
                "documents": {
                    "admission_record": [
                        {
                            "document_id": "A1",
                            "document_title": "入院记录",
                            "display_time": "2026-01-24 20:42:25",
                            "text_preview": "主诉：腹痛待诊。",
                        }
                    ]
                }
            },
        }
    )

    assert payload["programmatic_timeline"]["admission_time"] == "2026-01-24 20:42:25"
    assert payload["programmatic_timeline"]["admission_time_basis"] == "admission_record_record_time_fallback"
    assert payload["programmatic_timeline"]["admission_time_trusted"] is False
    assert "入院时间：2026-01-24 20:42:25" in payload["primary_document_text"]


def test_build_programmatic_evidence_payload_should_not_attest_structured_admission_anchor_without_provenance():
    payload = build_programmatic_evidence_payload(
        bundle={
            "structured_context": {
                "admission_datetime": "2026-01-24 08:00:00",
            }
        }
    )

    timeline = payload["programmatic_timeline"]
    assert timeline["admission_time"] == "2026-01-24 08:00:00"
    assert timeline["admission_time_basis"] == "structured_context_admission_datetime_unattested"
    assert timeline["admission_time_trusted"] is False


def test_build_programmatic_evidence_payload_should_not_attest_bundle_admission_anchor_without_provenance():
    payload = build_programmatic_evidence_payload(
        bundle={"admission_datetime": "2026-01-24 08:00:00"}
    )

    timeline = payload["programmatic_timeline"]
    assert timeline["admission_time"] == "2026-01-24 08:00:00"
    assert timeline["admission_time_basis"] == "bundle_admission_datetime_unattested"
    assert timeline["admission_time_trusted"] is False


def test_build_programmatic_evidence_payload_should_reject_external_fallback_meta_attestation(
    monkeypatch,
):
    monkeypatch.setattr(
        evidence_module,
        "_fetch_source_table_fallback_items",
        lambda bundle_payload: ([], {}),
    )

    payload = build_programmatic_evidence_payload(
        bundle={
            "_source_table_fallback_meta": {
                "admission_datetime": "2026-01-24 08:00:00",
            }
        }
    )

    timeline = payload["programmatic_timeline"]
    assert timeline["admission_time"] == ""
    assert timeline["admission_time_basis"] == "missing"
    assert timeline["admission_time_trusted"] is False


def test_fetch_source_table_fallback_items_should_report_readiness_without_changing_document_limit(
    monkeypatch,
):
    source_tables = (
        "first_course_record",
        "daily_course_record",
        "senior_course_record",
        "rescue_record",
    )
    connection = _FakeConnection(
        {
            "first_course_record": [
                {
                    "document_id": "F1",
                    "record_content": "首次病程记录",
                    "case_characteristic": "病例特点正文",
                },
            ],
            "daily_course_record": [
                {"document_id": "D1", "record_content": "日常病程 1"},
                {"document_id": "D2", "record_content": "日常病程 2"},
                {"document_id": "D3", "record_content": "日常病程 3"},
            ],
            "senior_course_record": RuntimeError("源表不可用"),
            "rescue_record": [],
        }
    )
    monkeypatch.setattr(evidence_module, "_SOURCE_TABLES", source_tables)
    monkeypatch.setattr(
        evidence_module,
        "_FALLBACK_DOC_FETCH_LIMITS",
        {
            "first_course_record": 2,
            "daily_course_record": 2,
            "senior_course_record": 2,
            "rescue_record": 2,
        },
    )
    monkeypatch.setattr(evidence_module, "engine", _FakeEngine(connection))
    bundle_payload = {
        "institute_id": "I1",
        "visit_id": "V1",
    }

    fallback_items, fallback_meta = evidence_module._fetch_source_table_fallback_items(
        bundle_payload
    )

    assert fallback_meta == {}
    assert [item["document_id"] for item in fallback_items] == ["F1", "D1", "D2"]
    assert fallback_items[0]["structured_sections"] == {
        "case_characteristic": "病例特点正文"
    }
    assert bundle_payload["_source_table_readiness"] == {
        "first_course_record": "complete",
        "daily_course_record": "partial",
        "senior_course_record": "unavailable",
        "rescue_record": "complete",
    }
    assert set(connection.source_query_limits) == {
        ("first_course_record", 3),
        ("daily_course_record", 3),
        ("senior_course_record", 3),
        ("rescue_record", 3),
    }


def test_build_programmatic_evidence_payload_projects_controlled_lab_rows(
    monkeypatch,
):
    rows_by_table = {
        "labtest_master": [
            {
                "test_id": "TEST-1",
                "report_datetime": "2026-09-16 08:00:00",
                "labtest_result_status": "已审核",
                "patient_name": "不应进入共享结构化投影",
            }
        ],
        "labtest_item_report": [
            {
                "test_id": "TEST-1",
                "test_no": "REPORT-1",
                "item_id": "ITEM-1",
                "item_name": "血钾",
                "result": "6.8",
                "unit": "mmol/L",
                "abnormal_indicator": "PH",
                "report_time": "2026-09-16 08:00:00",
                "patient_name": "不应进入共享结构化投影",
            }
        ],
    }
    monkeypatch.setattr(
        evidence_module,
        "_SOURCE_TABLES",
        ("labtest_master", "labtest_item_report"),
    )
    default_connection = _FakeConnection(rows_by_table)
    monkeypatch.setattr(evidence_module, "engine", _FakeEngine(default_connection))

    default_payload = build_programmatic_evidence_payload(
        bundle={"institute_id": "I1", "patient_id": "P1", "visit_id": "V1"}
    )

    assert evidence_module._FALLBACK_DOC_FETCH_LIMITS["labtest_master"] == 20
    assert evidence_module._FALLBACK_DOC_FETCH_LIMITS["labtest_item_report"] == 20
    assert set(default_connection.source_query_limits) == {
        ("labtest_master", 21),
        ("labtest_item_report", 21),
    }
    assert default_payload["programmatic_timeline"]["structured_source_rows"] == {}

    connection = _FakeConnection(rows_by_table)
    monkeypatch.setattr(evidence_module, "engine", _FakeEngine(connection))

    payload = build_programmatic_evidence_payload(
        bundle={"institute_id": "I1", "patient_id": "P1", "visit_id": "V1"},
        strict_structured_source_limits={
            "labtest_master": 100,
            "labtest_item_report": 400,
        },
    )

    timeline = payload["programmatic_timeline"]
    assert timeline["source_readiness"] == {
        "labtest_master": "complete",
        "labtest_item_report": "complete",
    }
    assert timeline["structured_source_readiness"] == {
        "labtest_master": "complete",
        "labtest_item_report": "complete",
    }
    assert timeline["structured_source_rows"]["labtest_item_report"][0][
        "abnormal_indicator"
    ] == "PH"
    assert (
        "patient_name"
        not in timeline["structured_source_rows"]["labtest_item_report"][0]
    )
    assert set(connection.source_query_limits) == {
        ("labtest_master", 101),
        ("labtest_item_report", 401),
    }


@pytest.mark.parametrize("weak_match", ("patient_visit", "visit_only"))
def test_strict_lab_projection_rejects_weak_identity_fallback(
    monkeypatch, weak_match
):
    weak_row = {
        "source_table": "labtest_item_report",
        "institute_id": "OTHER-I",
        "patient_id": "OTHER-P",
        "visit_id": "V1",
        "test_id": "TEST-WEAK",
        "test_no": "REPORT-WEAK",
        "item_id": "ITEM-WEAK",
        "item_name": "血钾",
        "result": "6.8",
        "unit": "mmol/L",
        "abnormal_indicator": "PH",
        "report_time": "2026-09-16 08:00:00",
    }

    def rows_for_query(params):
        identity_keys = frozenset(params) - {"limit"}
        if identity_keys == {"institute_id", "patient_id", "visit_id"}:
            return []
        if weak_match == "patient_visit" and identity_keys == {
            "patient_id",
            "visit_id",
        }:
            return [weak_row]
        if weak_match == "visit_only" and identity_keys == {"visit_id"}:
            return [weak_row]
        return []

    connection = _FakeConnection({"labtest_item_report": rows_for_query})
    monkeypatch.setattr(evidence_module, "_SOURCE_TABLES", ("labtest_item_report",))
    monkeypatch.setattr(evidence_module, "engine", _FakeEngine(connection))

    payload = build_programmatic_evidence_payload(
        bundle={
            "institute_id": "I1",
            "patient_id": "P1",
            "visit_id": "V1",
            "source_documents": [weak_row],
        },
        strict_structured_source_limits={"labtest_item_report": 400},
    )

    timeline = payload["programmatic_timeline"]
    assert timeline["source_readiness"]["labtest_item_report"] == "partial"
    assert (
        timeline["structured_source_readiness"]["labtest_item_report"]
        == "partial"
    )
    assert timeline["structured_source_rows"]["labtest_item_report"] == []
    assert connection.source_query_limits == [("labtest_item_report", 401)]
    result = build_critical_value_018_facts(bundle={}, evidence_payload=payload)
    assert result["event_facts"]["critical_values"] == []
    assert result["event_source_state_by_rule"]["LX0916-018"] == (
        "critical_value_source_partial"
    )


def test_build_programmatic_evidence_payload_should_ignore_external_source_readiness_and_project_controlled_values(
    monkeypatch,
):
    def fake_fetch_source_table_fallback_items(bundle_payload):
        assert "_source_table_readiness" not in bundle_payload
        bundle_payload["_source_table_readiness"] = {
            "first_course_record": "complete",
            "daily_course_record": "partial",
            "senior_course_record": "invalid",
            "unknown_table": "complete",
        }
        return [], {}

    monkeypatch.setattr(
        evidence_module,
        "_fetch_source_table_fallback_items",
        fake_fetch_source_table_fallback_items,
    )

    payload = build_programmatic_evidence_payload(
        bundle={
            "visit_id": "V1",
            "_source_table_readiness": {
                "first_course_record": "unavailable",
                "daily_course_record": "complete",
            },
        }
    )

    assert payload["programmatic_timeline"]["source_readiness"] == {
        "first_course_record": "complete",
        "daily_course_record": "partial",
    }


def test_build_programmatic_evidence_payload_should_not_attest_readiness_without_controlled_query(
    monkeypatch,
):
    monkeypatch.setattr(
        evidence_module,
        "_fetch_source_table_fallback_items",
        lambda bundle_payload: ([], {}),
    )

    payload = build_programmatic_evidence_payload(
        bundle={
            "_source_table_readiness": {
                "first_course_record": "complete",
            }
        }
    )

    assert payload["programmatic_timeline"]["source_readiness"] == {}


def test_build_programmatic_evidence_payload_should_project_first_course_structured_sections_without_expanding_shared_text(
    monkeypatch,
):
    monkeypatch.setattr(
        evidence_module,
        "_fetch_source_table_fallback_items",
        lambda bundle_payload: ([], {}),
    )

    payload = build_programmatic_evidence_payload(
        bundle={
            "source_documents": [
                {
                    "source_table": "first_course_record",
                    "document_id": "F1",
                    "record_time": "2026-09-16 08:00:00",
                    "case_characteristic": "病例特点正文",
                    "diagnose_based_on": "诊断依据正文",
                }
            ]
        }
    )

    event = payload["programmatic_timeline"]["documents"]["first_course_record"][0]
    assert event["structured_sections"] == {
        "case_characteristic": "病例特点正文",
        "diagnose_based_on": "诊断依据正文",
    }
    assert "病例特点正文" not in payload["primary_document_text"]


def test_build_programmatic_evidence_payload_should_attest_approved_primary_timeline_fact():
    payload = build_programmatic_evidence_payload(
        bundle={
            "timeline_facts": [
                {
                    "source_table": "inpat_registration",
                    "field": "admission_datetime",
                    "value": "2026-01-24 08:00:00",
                }
            ]
        }
    )

    timeline = payload["programmatic_timeline"]
    assert timeline["admission_time"] == "2026-01-24 08:00:00"
    assert timeline["admission_time_basis"] == "timeline_primary_admission_datetime"
    assert timeline["admission_time_trusted"] is True


def test_build_programmatic_evidence_payload_should_not_trust_text_or_unapproved_timeline_anchor():
    timeline_payload = build_programmatic_evidence_payload(
        bundle={
            "timeline_facts": [
                {
                    "source_table": "daily_course_record",
                    "field": "admission_datetime",
                    "value": "2026-01-24 08:00:00",
                }
            ],
            "medical_text": "入院时间：2026-01-24 09:00:00",
        }
    )

    timeline = timeline_payload["programmatic_timeline"]
    assert timeline["admission_time"] == "2026-01-24 09:00:00"
    assert timeline["admission_time_basis"] == "medical_text_label_fallback"
    assert timeline["admission_time_trusted"] is False


def test_build_programmatic_evidence_payload_should_not_trust_admission_document_label():
    payload = build_programmatic_evidence_payload(
        bundle={
            "source_documents": [
                {
                    "source_table": "admission_record",
                    "document_title": "入院记录",
                    "content": "入院时间：2026-01-24 08:00:00；主诉：不适。",
                }
            ]
        }
    )

    timeline = payload["programmatic_timeline"]
    assert timeline["admission_time"] == "2026-01-24 08:00:00"
    assert timeline["admission_time_basis"] == "admission_record_text_label_fallback"
    assert timeline["admission_time_trusted"] is False


def test_build_programmatic_evidence_payload_should_classify_course_round_roles_strictly():
    payload = build_programmatic_evidence_payload(
        bundle={
            "structured_context": {
                "documents": {
                    "senior_course_record": [
                        {
                            "document_id": "R1",
                            "document_title": "王标主治医师查房记录",
                            "display_time": "2026-04-14 08:03:17",
                            "text_preview": "今日王标主治医师查看病房后指出：病情稳定。",
                        },
                        {
                            "document_id": "R2",
                            "document_title": "王飞副主任医师查房记录",
                            "display_time": "2026-04-15 08:03:38",
                            "text_preview": "今日王飞副主任医师查看病房后指出：病情平稳。",
                        },
                        {
                            "document_id": "R3",
                            "document_title": "某某医疗组长查房记录",
                            "display_time": "2026-04-16 08:00:00",
                            "text_preview": "今日医疗组长查看病房后指出：继续观察。",
                        },
                    ]
                }
            }
        }
    )

    events = payload["programmatic_timeline"]["documents"]["senior_course_record"]
    assert events[0]["author_role"] == "attending"
    assert events[0]["author_title"] == "主治医师"
    assert events[1]["author_role"] == "senior"
    assert events[1]["author_title"] == "副主任医师"
    assert events[2]["author_role"] == ""


def test_build_programmatic_evidence_payload_should_not_misclassify_negated_or_department_risk_flags():
    payload = build_programmatic_evidence_payload(
        bundle={
            "medical_text": "患者由呼吸与危重症医学科会诊。社区获得性肺炎，非重症。今日停病重处理。",
            "structured_context": {},
        }
    )

    assert payload["programmatic_timeline"]["risk_flags"] == ["normal"]


def test_build_programmatic_evidence_payload_should_not_misclassify_acute_severe_risk_disclosure_as_serious():
    payload = build_programmatic_evidence_payload(
        bundle={
            "medical_text": "术中突然出现心律失常、心梗、心脑血管意外等急重症发作，暂停手术，抢救病人，病人甚至死亡等。",
            "structured_context": {},
        }
    )

    assert payload["programmatic_timeline"]["risk_flags"] == ["normal"]


def test_build_programmatic_evidence_payload_should_fallback_to_source_tables_when_bundle_documents_are_empty(monkeypatch):
    def fake_fetch_source_table_fallback_items(bundle_payload):
        return (
            [
                {
                    "source_table": "daily_course_record",
                    "document_type": "daily_course_record",
                    "document_id": "D1",
                    "document_title": "日常病程记录",
                    "record_time": "2026-02-03 12:26:23",
                    "display_time": "2026-02-03 12:26:23",
                    "submit_datetime": "",
                    "content": "患者病情稳定。",
                    "text_preview": "患者病情稳定。",
                },
                {
                    "source_table": "senior_course_record",
                    "document_type": "senior_course_record",
                    "document_id": "S1",
                    "document_title": "主任医师查房记录",
                    "record_time": "",
                    "display_time": "2026-02-08 09:00:00",
                    "submit_datetime": "",
                    "content": "今日主任医师查房，继续观察。",
                    "text_preview": "今日主任医师查房，继续观察。",
                },
            ],
            {
                "admission_datetime": "2026-01-22 10:00:00",
                "discharge_datetime": "2026-02-14 09:00:00",
            },
        )

    monkeypatch.setattr(
        evidence_module,
        "_fetch_source_table_fallback_items",
        fake_fetch_source_table_fallback_items,
    )

    payload = build_programmatic_evidence_payload(
        bundle={
            "institute_id": "I1",
            "patient_id": "P1",
            "visit_id": "V1",
            "structured_context": {
                "documents": {
                    "daily_course_record": [],
                    "senior_course_record": [],
                }
            },
        }
    )

    timeline = payload["programmatic_timeline"]
    assert timeline["admission_time"] == "2026-01-22 10:00:00"
    assert timeline["admission_time_basis"] == "cdm_inpat_registration_admission_datetime"
    assert timeline["admission_time_trusted"] is True
    assert timeline["discharge_time"] == "2026-02-14 09:00:00"
    assert len(timeline["documents"]["daily_course_record"]) == 1
    assert len(timeline["documents"]["senior_course_record"]) == 1
    assert timeline["documents"]["senior_course_record"][0]["authored_at"] == "2026-02-08 09:00:00"


def test_build_programmatic_evidence_payload_should_keep_distinct_fallback_documents_from_same_table(monkeypatch):
    monkeypatch.setattr(
        evidence_module,
        "_fetch_source_table_fallback_items",
        lambda bundle_payload: (
            [
                {
                    "source_table": "daily_course_record",
                    "document_type": "daily_course_record",
                    "document_id": "D2",
                    "document_title": "日常病程记录",
                    "record_time": "2026-02-04 09:00:00",
                    "content": "第二次查房：患者生命体征平稳，继续观察病情变化。",
                    "text_preview": "第二次查房：患者生命体征平稳，继续观察病情变化。",
                }
            ],
            {},
        ),
    )

    payload = build_programmatic_evidence_payload(
        bundle={
            "source_documents": [
                {
                    "source_table": "daily_course_record",
                    "document_type": "daily_course_record",
                    "document_id": "D1",
                    "document_title": "日常病程记录",
                    "record_time": "2026-02-03 09:00:00",
                    "content": "第一次查房：" + "患者一般情况稳定，继续当前治疗方案。" * 6,
                }
            ],
            "structured_context": {},
        }
    )

    documents = payload["programmatic_timeline"]["documents"]["daily_course_record"]
    assert [item["document_id"] for item in documents] == ["D1", "D2"]
    assert "第二次查房" in payload["primary_document_text"]


def test_build_programmatic_evidence_payload_should_deduplicate_same_document_id_and_keep_richer_copy(monkeypatch):
    monkeypatch.setattr(
        evidence_module,
        "_fetch_source_table_fallback_items",
        lambda bundle_payload: (
            [
                {
                    "source_table": "consultation_record",
                    "document_type": "consultation_record",
                    "document_id": "C1",
                    "document_title": "会诊记录",
                    "record_time": "2026-02-04 10:00:00",
                    "content": "会诊意见：患者目前病情平稳，建议继续抗感染治疗，并根据复查结果调整方案。",
                    "text_preview": "会诊意见：患者目前病情平稳，建议继续抗感染治疗，并根据复查结果调整方案。",
                }
            ],
            {},
        ),
    )

    payload = build_programmatic_evidence_payload(
        bundle={
            "source_documents": [
                {
                    "source_table": "consultation_record",
                    "document_type": "consultation_record",
                    "document_id": "C1",
                    "document_title": "会诊记录",
                    "record_time": "",
                    "content": "会诊意见：继续观察。",
                }
            ],
            "structured_context": {},
        }
    )

    documents = payload["programmatic_timeline"]["documents"]["consultation_record"]
    assert len(documents) == 1
    assert documents[0]["authored_at"] == "2026-02-04 10:00:00"
    assert "根据复查结果调整方案" in documents[0]["content"]
    assert payload["primary_document_text"].count("根据复查结果调整方案") == 1


def test_build_programmatic_evidence_payload_should_not_double_count_preview_when_choosing_richer_copy(monkeypatch):
    fallback_content = "乙" * 60
    monkeypatch.setattr(
        evidence_module,
        "_fetch_source_table_fallback_items",
        lambda bundle_payload: (
            [
                {
                    "source_table": "consultation_record",
                    "document_type": "consultation_record",
                    "document_id": "C2",
                    "document_title": "会诊记录",
                    "record_time": "2026-02-05 10:00:00",
                    "content": fallback_content,
                    "text_preview": fallback_content,
                }
            ],
            {},
        ),
    )

    complete_content = "甲" * 100
    payload = build_programmatic_evidence_payload(
        bundle={
            "source_documents": [
                {
                    "source_table": "consultation_record",
                    "document_type": "consultation_record",
                    "document_id": "C2",
                    "document_title": "会诊记录",
                    "record_time": "",
                    "content": complete_content,
                }
            ],
            "structured_context": {},
        }
    )

    document = payload["programmatic_timeline"]["documents"]["consultation_record"][0]
    assert document["content"] == complete_content
    assert document["authored_at"] == "2026-02-05 10:00:00"


def test_build_programmatic_evidence_payload_should_use_conservative_identity_when_document_id_is_missing(monkeypatch):
    monkeypatch.setattr(
        evidence_module,
        "_fetch_source_table_fallback_items",
        lambda bundle_payload: (
            [
                {
                    "source_table": "daily_course_record",
                    "document_type": "daily_course_record",
                    "document_title": "日常病程记录",
                    "record_time": "2026-02-03 09:00:00",
                    "content": "患者   病情稳定，继续观察。",
                    "text_preview": "患者   病情稳定，继续观察。",
                },
                {
                    "source_table": "daily_course_record",
                    "document_type": "daily_course_record",
                    "document_title": "日常病程记录",
                    "record_time": "2026-02-04 09:00:00",
                    "content": "患者出现发热，调整抗感染方案。",
                    "text_preview": "患者出现发热，调整抗感染方案。",
                },
            ],
            {},
        ),
    )

    payload = build_programmatic_evidence_payload(
        bundle={
            "source_documents": [
                {
                    "source_table": "daily_course_record",
                    "document_type": "daily_course_record",
                    "document_title": "日常病程记录",
                    "record_time": "2026-02-03 09:00:00",
                    "content": "患者 病情稳定，继续观察。",
                }
            ],
            "structured_context": {},
        }
    )

    documents = payload["programmatic_timeline"]["documents"]["daily_course_record"]
    assert len(documents) == 2
    assert [item["authored_at"] for item in documents] == [
        "2026-02-03 09:00:00",
        "2026-02-04 09:00:00",
    ]
    assert payload["primary_document_text"].count("患者出现发热") == 1


def test_build_programmatic_evidence_payload_should_fallback_to_detail_service_when_source_tables_are_empty(monkeypatch):
    monkeypatch.setattr(
        evidence_module,
        "_fetch_source_table_fallback_items",
        lambda bundle_payload: ([], {}),
    )
    monkeypatch.setattr(
        evidence_module,
        "get_documents",
        lambda visit_id: {
            "documents": [
                {
                    "type": "surgery_record",
                    "source_table": "surgery_record",
                    "label": "手术记录",
                    "has_content": True,
                    "content": "记录时间: \\n手术医生签名: \\n手术项目: 阑尾切除术",
                    "document_id": None,
                    "document_title": "手术记录",
                    "sort_time": "",
                    "record_time": "",
                    "submit_time": "",
                    "last_modified_time": "",
                }
            ]
        },
    )

    payload = build_programmatic_evidence_payload(
        bundle={
            "visit_id": "V100",
            "structured_context": {
                "documents": {
                    "surgery_record": [],
                }
            },
        }
    )

    timeline = payload["programmatic_timeline"]
    assert len(timeline["documents"]["surgery_record"]) == 1
    assert "手术医生签名" in payload["primary_document_text"]


def test_build_programmatic_evidence_payload_should_accept_bundle_document_type_field():
    payload = build_programmatic_evidence_payload(
        bundle={
            "source_documents": [
                {
                    "type": "first_course_record",
                    "label": "首次病程记录",
                    "document_id": "F1",
                    "record_time": "2026-06-10 08:26:37",
                    "content": "患者为70岁男性，起病缓，病程长。入院后完善相关检查，结合病史、体格检查和辅助检查拟定诊疗计划。",
                }
            ],
            "structured_context": {},
        }
    )

    first_courses = payload["programmatic_timeline"]["documents"]["first_course_record"]
    assert len(first_courses) == 1
    assert first_courses[0]["source_table"] == "first_course_record"
    assert "患者为70岁男性" in first_courses[0]["content"]


def test_build_programmatic_evidence_payload_should_explain_first_course_update_time_fallback():
    payload = build_programmatic_evidence_payload(
        bundle={
            "source_documents": [
                {
                    "type": "first_course_record",
                    "label": "首次病程记录",
                    "document_id": "F1",
                    "record_time": "",
                    "display_time": "",
                    "update_time": "2026-06-10 00:26:37+00",
                    "content": "患者为70岁男性，起病缓，病程长。入院后完善相关检查，结合病史拟定诊疗计划。",
                }
            ],
            "structured_context": {},
        }
    )

    first_course = payload["programmatic_timeline"]["documents"]["first_course_record"][0]
    assert first_course["authored_at"] == "2026-06-10 00:26:37"
    assert first_course["time_basis"] == "update_time_fallback"
    assert "源库未返回首程 record_time/submit_time" in first_course["time_note"]
    assert "记录时间（源库未返回，暂用更新时间）：2026-06-10 00:26:37" in payload["primary_document_text"]
    assert "暂以源库更新时间作为判定参考" in payload["primary_document_text"]


def test_build_programmatic_evidence_payload_should_use_first_course_submit_time_before_update_time():
    payload = build_programmatic_evidence_payload(
        bundle={
            "source_documents": [
                {
                    "type": "first_course_record",
                    "label": "首次病程记录",
                    "document_id": "F1",
                    "record_time": "",
                    "display_time": "",
                    "submit_time": "2026-05-29 03:45:59+00",
                    "update_time": "2026-06-10 00:26:37+00",
                    "content": "患者为70岁男性，起病缓，病程长。结合病史拟定诊疗计划。",
                }
            ],
            "structured_context": {},
        }
    )

    first_course = payload["programmatic_timeline"]["documents"]["first_course_record"][0]
    assert first_course["authored_at"] == "2026-05-29 03:45:59"
    assert first_course["time_basis"] == "submit_time_fallback"
    assert "使用提交时间作为记录时间" in first_course["time_note"]
    assert "记录时间（源库 record_time 为空，使用提交时间）：2026-05-29 03:45:59" in payload["primary_document_text"]
    assert "2026-06-10 00:26:37" not in payload["primary_document_text"]
