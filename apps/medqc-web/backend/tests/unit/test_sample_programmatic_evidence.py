from app.services import sample_programmatic_evidence as evidence_module
from app.services.sample_programmatic_evidence import build_programmatic_evidence_payload


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
