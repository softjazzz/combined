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
