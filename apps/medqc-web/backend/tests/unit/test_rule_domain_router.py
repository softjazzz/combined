from __future__ import annotations

from app.services.rule_domain_router import route_rule_to_domain


def test_route_rule_to_domain_should_align_course_extended_docs():
    decision = route_rule_to_domain(
        {
            "rule_id": "SC-X01",
            "applicable_documents": ["医嘱"],
        }
    )
    assert decision.execution_domain == "course"
    assert decision.primary_doc_types[0] == "medical_order"


def test_route_rule_to_domain_should_align_surgery_risk_assessment():
    decision = route_rule_to_domain(
        {
            "rule_id": "SC-X02",
            "applicable_documents": ["手术风险评估"],
        }
    )
    assert decision.execution_domain == "surgery"
    assert decision.primary_doc_types[0] == "surgery_risk_assessment"


def test_route_rule_to_domain_should_keep_consult_discussion_for_handover():
    decision = route_rule_to_domain(
        {
            "rule_id": "SC-X03",
            "applicable_documents": ["交接班记录"],
        }
    )
    assert decision.execution_domain == "consult_discussion"
    assert decision.primary_doc_types[0] in {"handoff_record", "handover_record"}
