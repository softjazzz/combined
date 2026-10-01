from __future__ import annotations

from app.services import custom_qc_workspace_service as workspace_service
import pytest


@pytest.mark.parametrize("documents", [[], [
    {"document_id": "admission-001", "content": "当前正文已经修改", "sections": []},
], [
    {"document_id": "admission-001", "content": "正文一", "sections": []},
    {"document_id": "admission-001", "content": "正文二", "sections": []},
]])
def test_saved_evidence_excerpt_is_not_replaced_by_current_body(monkeypatch, documents) -> None:
    source_ref = workspace_service.build_customer_safe_source_ref("admission-001")
    monkeypatch.setattr(workspace_service, "load_bundle_documents", lambda **kwargs: {
        "documents": documents,
    })
    evidence = {"source_type": "admission_record", "source_ref": source_ref,
                "evidence_excerpt": "已保存的原文证据", "excerpt_kind": "字段级依据"}
    items = [{"evidence": [evidence]}]
    workspace_service.attach_authorized_evidence_excerpts(items, institute_id="H1", patient_id="P1", visit_id="V1")
    assert evidence["evidence_excerpt"] == "已保存的原文证据"
    assert evidence["excerpt_kind"] == "字段级依据"


def test_authorized_evidence_excerpt_requires_exact_source_ref(monkeypatch) -> None:
    surgery_document_id = "surgery-001"
    source_ref = workspace_service.build_customer_safe_source_ref(surgery_document_id)
    monkeypatch.setattr(
        workspace_service,
        "load_bundle_documents",
        lambda **_: {
            "documents": [
                {
                    "document_id": surgery_document_id,
                    "content": "手术经过：置入人工关节假体，术中情况平稳。",
                    "sections": [],
                },
                {
                    "document_id": "unrelated-002",
                    "content": "无关文书，不可按标题或正文猜测引用。",
                    "sections": [],
                },
            ]
        },
    )
    items = [
        {
            "evidence": [
                {"source_type": "surgery_record", "source_ref": source_ref},
                {"source_type": "surgery_record", "source_ref": "src_000000000000000000000000"},
            ]
        }
    ]

    workspace_service.attach_authorized_evidence_excerpts(
        items,
        institute_id="hospital",
        patient_id="patient",
        visit_id="visit",
    )

    assert items[0]["evidence"][0]["evidence_excerpt"] == "手术经过：置入人工关节假体，术中情况平稳。"
    assert items[0]["evidence"][0]["excerpt_kind"] == "文书级依据"
    assert "evidence_excerpt" not in items[0]["evidence"][1]


def test_authorized_evidence_excerpt_prefers_exact_field_section(monkeypatch) -> None:
    admission_document_id = "admission-001"
    source_ref = workspace_service.build_customer_safe_source_ref(admission_document_id)
    monkeypatch.setattr(
        workspace_service,
        "load_bundle_documents",
        lambda **_: {
            "documents": [
                {
                    "document_id": admission_document_id,
                    "content": "完整入院记录正文",
                    "sections": [
                        {
                            "source_field": "chief_complaint",
                            "text": "反复咳嗽、咳痰、气促10余年，加重1天。",
                        }
                    ],
                }
            ]
        },
    )
    items = [
        {
            "evidence": [
                {
                    "source_type": "admission_record",
                    "source_ref": source_ref,
                    "field_path": "chief_complaint",
                }
            ]
        }
    ]

    workspace_service.attach_authorized_evidence_excerpts(
        items,
        institute_id="hospital",
        patient_id="patient",
        visit_id="visit",
    )

    evidence = items[0]["evidence"][0]
    assert evidence["evidence_excerpt"] == "反复咳嗽、咳痰、气促10余年，加重1天。"
    assert evidence["excerpt_kind"] == "字段级依据"
