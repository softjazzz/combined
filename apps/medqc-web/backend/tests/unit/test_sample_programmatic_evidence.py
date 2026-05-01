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
    assert "入院时间：2026-01-24 20:42:25" in payload["primary_document_text"]


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
