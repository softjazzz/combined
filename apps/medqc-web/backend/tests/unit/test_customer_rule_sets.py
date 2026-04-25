from app.constants.doc_types import DOC_TYPE_FULL_MAP
from app.services.customer_rule_sets import (
    CUSTOMER_LUXIAN_RULE_SET_KEY,
    get_customer_luxian_rule_set,
    load_customer_luxian_rules,
)
from app.services.sichuan_qc_service import SichuanQCService


def test_customer_luxian_rule_set_should_use_fixed_customer_pack():
    rule_set = get_customer_luxian_rule_set()

    assert rule_set.key == CUSTOMER_LUXIAN_RULE_SET_KEY
    assert rule_set.name == "客户专项规则包 v1"
    assert rule_set.version == "2026-04-26"
    assert rule_set.scope == "running"
    assert rule_set.execution_strategy == "fast_screen"
    assert rule_set.quality_profile == "throughput_v1"
    assert rule_set.bucket_strategy == "fixed_packs"
    assert rule_set.enable_selective_refine is False
    assert rule_set.max_refine_candidates == 0
    assert len(rule_set.rule_ids) == 272
    assert rule_set.rule_ids[0] == "CL-001"
    assert rule_set.rule_ids[-1] == "CL-272"


def test_customer_luxian_rules_should_have_required_fields_and_valid_documents():
    rules = load_customer_luxian_rules()
    valid_doc_types = set(DOC_TYPE_FULL_MAP.keys()) | {
        "exam_attention_report",
        "lab_attention_report",
    }

    assert len(rules) == 272

    seen_ids = set()
    for expected_index, rule in enumerate(rules, start=1):
        rule_id = str(rule.get("rule_id") or "").strip()
        assert rule_id == f"CL-{expected_index:03d}"
        assert rule_id not in seen_ids
        seen_ids.add(rule_id)

        assert str(rule.get("rule_code") or "").strip() == rule_id
        assert str(rule.get("name") or "").strip()
        assert str(rule.get("description") or "").strip()
        assert str(rule.get("category") or "").strip()
        assert str(rule.get("problem_domain") or "").strip()
        assert str(rule.get("defect_level") or "").strip()
        assert str(rule.get("custom_prompt") or "").strip()
        assert "{medical_text}" in str(rule.get("custom_prompt") or "")
        assert "{description}" in str(rule.get("custom_prompt") or "")
        assert rule.get("executor_type") == "llm"
        assert rule.get("doc_scope") == "primary"
        assert rule.get("allow_selective_refine") is False
        assert isinstance(rule.get("applicable_documents"), list)
        assert rule.get("applicable_documents")
        for doc_type in rule["applicable_documents"]:
            assert doc_type in valid_doc_types


def test_customer_luxian_rules_should_cover_representative_customer_problem_domains():
    rules = load_customer_luxian_rules()
    descriptions = [str(rule.get("description") or "") for rule in rules]
    domains = {str(rule.get("problem_domain") or "").strip() for rule in rules}

    assert {"病历内容", "检查检验", "流程时效", "真实性规范"}.issubset(domains)

    representative_keywords = [
        "动脉粥样硬化",
        "危急值",
        "输血",
        "复制粘贴",
        "24小时",
        "会诊",
        "剂量",
    ]
    for keyword in representative_keywords:
        assert any(keyword in description for description in descriptions), keyword


def test_customer_rules_should_be_resolvable_from_sichuan_qc_service():
    service = SichuanQCService()

    rule = service.get_rule_by_id("CL-010")

    assert rule is not None
    assert rule["rule_id"] == "CL-010"
    assert "危急值" in str(rule.get("description") or "")

