from __future__ import annotations

from app.services.qc_agent.intent_router import merge_llm_intent, normalize_intent_message
from app.services.qc_agent.orchestrator import parse_intent
from app.services.qc_agent.schemas import QCAgentChatRequest


def test_normalize_intent_message_standardizes_common_medical_terms():
    assert normalize_intent_message("二型糖尿病怎么编码") == "2型糖尿病怎么编码"
    assert normalize_intent_message("Ⅱ型糖尿病 ICD") == "2型糖尿病 ICD"


def test_parse_intent_routes_natural_coding_question_through_llm(monkeypatch):
    called = {"value": False}

    def _fake_resolve(message, context):
        called["value"] = True
        assert message == "2型糖尿病怎么编码"
        return (
            {
                "capability": "search_icd_codes",
                "confidence": 0.96,
                "icd_query": "2型糖尿病",
                "code_type": "diagnosis",
                "version": "insurance",
            },
            [],
        )

    monkeypatch.setattr("app.services.qc_agent.orchestrator.resolve_intent_with_llm", _fake_resolve)

    intent, warnings = parse_intent(QCAgentChatRequest(message="二型糖尿病怎么编码"))

    assert warnings == []
    assert called["value"] is True
    assert intent["intent_router"] == "llm"
    assert intent["task_type"] == "coding"
    assert intent["capability"] == "search_icd_codes"
    assert intent["result_type"] == "icd_candidates"
    assert intent["icd_query"] == "2型糖尿病"
    assert intent["code_type"] == "diagnosis"


def test_parse_intent_can_accept_llm_intent_for_uncertain_non_qc_request(monkeypatch):
    def _fake_resolve(message, context):
        return (
            {
                "capability": "search_icd_codes",
                "confidence": 0.93,
                "icd_query": "2型糖尿病",
                "code_type": "diagnosis",
                "version": "insurance",
            },
            [],
        )

    monkeypatch.setattr("app.services.qc_agent.orchestrator.resolve_intent_with_llm", _fake_resolve)

    intent, warnings = parse_intent(QCAgentChatRequest(message="这个诊断对应什么码"))

    assert warnings == []
    assert intent["intent_router"] == "llm"
    assert intent["llm_intent_confidence"] == 0.93
    assert intent["task_type"] == "coding"
    assert intent["capability"] == "search_icd_codes"
    assert intent["icd_query"] == "2型糖尿病"


def test_parse_intent_stops_when_llm_unavailable(monkeypatch):
    def _fake_resolve(message, context):
        return None, ["LLM 意图识别未配置 endpoint 或 key"]

    monkeypatch.setattr("app.services.qc_agent.orchestrator.resolve_intent_with_llm", _fake_resolve)

    intent, warnings = parse_intent(QCAgentChatRequest(message="入院记录有哪些质控规则"))

    assert "LLM 意图识别未配置 endpoint 或 key" in warnings
    assert intent["intent_router"] == "llm_unavailable"
    assert intent["capability"] == "unsupported"
    assert intent["document_alias"] is None


def test_parse_intent_accepts_llm_rule_catalog_intent(monkeypatch):
    def _fake_resolve(message, context):
        return (
            {
                "capability": "list_qc_rules",
                "confidence": 0.98,
                "document_alias": "admission",
                "source": "sc146",
            },
            [],
        )

    monkeypatch.setattr("app.services.qc_agent.orchestrator.resolve_intent_with_llm", _fake_resolve)

    intent, warnings = parse_intent(QCAgentChatRequest(message="入院记录有哪些质控规则"))

    assert warnings == []
    assert intent["intent_router"] == "llm"
    assert intent["task_type"] == "qc"
    assert intent["capability"] == "list_qc_rules"
    assert intent["result_type"] == "qc_rules"
    assert intent["document_alias"] == "admission"
    assert intent["source"] == "sc146"


def test_parse_intent_calls_llm_before_safety_override(monkeypatch):
    called = {"value": False}

    def _fake_resolve(message, context):
        called["value"] = True
        return (
            {
                "capability": "run_document_qc",
                "confidence": 0.99,
                "visit_id": "V001",
                "document_alias": "ward_round",
            },
            [],
        )

    monkeypatch.setattr("app.services.qc_agent.orchestrator.resolve_intent_with_llm", _fake_resolve)

    intent, warnings = parse_intent(QCAgentChatRequest(message="删除 visit_id=V001 的质控结果并写入正式表"))

    assert warnings == []
    assert called["value"] is True
    assert intent["unsupported"] is True
    assert intent["capability"] == "unsupported"


def test_merge_llm_intent_cannot_override_unsupported_write_intent():
    base = {
        "unsupported": True,
        "task_type": "qc",
        "capability": "run_document_qc",
        "result_type": "document_qc",
    }
    llm_intent = {
        "capability": "search_icd_codes",
        "confidence": 0.99,
        "icd_query": "2型糖尿病",
    }

    merged = merge_llm_intent(base, llm_intent)

    assert merged is base
    assert merged["unsupported"] is True
    assert merged["capability"] == "run_document_qc"
