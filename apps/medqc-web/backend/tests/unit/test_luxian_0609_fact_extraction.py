from __future__ import annotations

import pytest

from app.services.luxian_0609_fact_extraction import (
    build_luxian_0609_fact_prompt,
    evaluate_luxian_0609_gates_from_facts,
    extract_luxian_0609_facts,
    extract_luxian_0609_facts_with_llm,
    extract_luxian_0609_structured_facts,
    extract_luxian_0609_unified_fact_table,
    merge_luxian_0609_facts,
    Luxian0609Fact,
    render_luxian_0609_fact_context,
)
from app.services.luxian_0609_trigger_gate import TRIGGER_ABSENT, TRIGGER_DATA_GAP, TRIGGER_PRESENT


def _wrapper(
    rule_id: str,
    *,
    name: str,
    mapped_rule_ids: list[str] | None = None,
    trigger_condition: str = "",
    data_dependencies: list[str] | None = None,
) -> dict:
    return {
        "rule_id": rule_id,
        "name": name,
        "rule_name": name,
        "mapped_rule_ids": mapped_rule_ids or [rule_id],
        "primary_execution_rule_id": (mapped_rule_ids or [rule_id])[0],
        "trigger_condition": trigger_condition,
        "data_dependencies": data_dependencies or [],
    }


class _FakeLLMFactClient:
    def __init__(self, content: str):
        self.content = content
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> dict:
        self.prompts.append(prompt)
        return {"choices": [{"message": {"content": self.content}}]}


def test_extract_luxian_0609_facts_should_capture_surgery_and_implant_sources():
    documents = [
        {
            "source_table": "operation_record",
            "document_id": "op-1",
            "record_time": "2026-06-01 09:30:00",
            "content": (
                "手术记录：手术名称：腹股沟疝无张力修补术。"
                "术中置入聚丙烯补片，补片型号M-01，条码BC123。"
                "术前讨论：患者同意手术方案。"
            ),
        }
    ]

    facts = extract_luxian_0609_facts(documents, families=["surgery_anesthesia"])
    fact_types = {fact.fact_type for fact in facts}

    assert {"surgery_fact", "implant_fact", "surgical_discussion"}.issubset(fact_types)
    assert all(fact.source_document_id == "op-1" for fact in facts)
    assert any("补片" in fact.quote and "条码" in fact.quote for fact in facts)


def test_extract_luxian_0609_facts_should_capture_pathology_and_chemo_sources():
    documents = [
        {
            "source_table": "pathology_report",
            "document_id": "path-1",
            "record_time": "2026-06-03 10:00:00",
            "content": "病理检查报告：标本胃窦组织，病理诊断胃中分化腺癌，报告时间2026-06-03。",
        },
        {
            "source_table": "order",
            "document_id": "order-1",
            "record_time": "2026-06-04 08:00:00",
            "content": "化疗医嘱：奥沙利铂静滴，卡培他滨口服，按XELOX方案执行。",
        },
    ]

    facts = extract_luxian_0609_facts(documents, families=["tumor_pathology"])
    fact_types = {fact.fact_type for fact in facts}

    assert "pathology_report" in fact_types
    assert "chemo_fact" in fact_types
    assert any("胃中分化腺癌" in fact.quote for fact in facts)


def test_fact_gate_should_not_trigger_chemo_rule_without_chemo_fact():
    rules = [
        _wrapper(
            "LX0609-026",
            name="恶性肿瘤化学治疗记录",
            trigger_condition="化疗医嘱与病程化疗记录应一致。",
        )
    ]
    documents = [
        {
            "source_table": "pathology_report",
            "document_id": "path-1",
            "record_time": "2026-06-03 10:00:00",
            "content": "病理检查报告：标本胃窦组织，病理诊断胃中分化腺癌，报告时间2026-06-03。",
        }
    ]

    facts = extract_luxian_0609_facts(documents, families=["tumor_pathology"])
    evaluation = evaluate_luxian_0609_gates_from_facts(
        rules=rules,
        facts=facts,
        families=["tumor_pathology"],
    )

    assert evaluation.decisions["LX0609-026"].status == TRIGGER_ABSENT
    assert "未发现明确化疗医嘱或化疗记录" in evaluation.decisions["LX0609-026"].reason


def test_fact_gate_should_trigger_pathology_specimen_rule_from_surgery_specimen_fact():
    rules = [
        _wrapper(
            "LX0609-019",
            name="病理检查取材情况记录",
            mapped_rule_ids=["SC-099"],
            trigger_condition="病理取材情况应在病程记录或手术记录中记录。",
        )
    ]
    documents = [
        {
            "source_table": "operation_record",
            "document_id": "op-1",
            "record_time": "2026-06-01 11:00:00",
            "content": "手术记录：切除阑尾从脐部trocar口取出，阑尾向患者家属展示后送病检。",
        }
    ]

    facts = extract_luxian_0609_facts(documents, families=["tumor_pathology"])
    evaluation = evaluate_luxian_0609_gates_from_facts(
        rules=rules,
        facts=facts,
        families=["tumor_pathology"],
    )

    assert any(fact.fact_type == "pathology_specimen_sent" for fact in facts)
    assert evaluation.decisions["LX0609-019"].status == TRIGGER_PRESENT


def test_fact_gate_should_mark_antibiotic_rule_data_gap_when_stop_time_missing():
    rules = [
        _wrapper(
            "LX0609-028",
            name="I类、II类切口预防使用抗菌药物时间超过24小时",
            trigger_condition="I类、II类切口手术预防使用抗菌药物需核对医嘱起止时间。",
        )
    ]
    documents = [
        {
            "source_table": "operation_record",
            "document_id": "op-1",
            "record_time": "2026-06-01 09:00:00",
            "content": "手术记录：患者行腹股沟疝修补术，I类切口，手术经过顺利。",
        },
        {
            "source_table": "order",
            "document_id": "order-1",
            "record_time": "2026-06-01 08:30:00",
            "content": "医嘱：术前30分钟给予头孢呋辛预防感染。",
        },
    ]

    facts = extract_luxian_0609_facts(documents, families=["surgery_anesthesia"])
    evaluation = evaluate_luxian_0609_gates_from_facts(
        rules=rules,
        facts=facts,
        families=["surgery_anesthesia"],
    )

    assert evaluation.decisions["LX0609-028"].status == TRIGGER_DATA_GAP
    assert "抗菌药物医嘱停止时间" in evaluation.decisions["LX0609-028"].data_gap_fields


def test_fact_gate_should_not_trigger_antibiotic_rule_without_antibiotic_fact():
    rules = [
        _wrapper(
            "LX0609-028",
            name="I类、II类切口预防使用抗菌药物时间超过24小时",
            trigger_condition="I类、II类切口手术预防使用抗菌药物需核对医嘱起止时间。",
        )
    ]
    documents = [
        {
            "source_table": "operation_record",
            "document_id": "op-1",
            "record_time": "2026-06-01 09:00:00",
            "content": "手术记录：患者行腹股沟疝修补术，I类切口，手术经过顺利。",
        }
    ]

    facts = extract_luxian_0609_facts(documents, families=["surgery_anesthesia"])
    evaluation = evaluate_luxian_0609_gates_from_facts(
        rules=rules,
        facts=facts,
        families=["surgery_anesthesia"],
    )

    assert evaluation.decisions["LX0609-028"].status == TRIGGER_ABSENT
    assert "未发现抗菌药物医嘱" in evaluation.decisions["LX0609-028"].reason


def test_render_fact_context_and_prompt_should_not_mix_fact_extraction_with_compliance_judgement():
    facts = extract_luxian_0609_facts(
        [
            {
                "source_table": "pathology_report",
                "document_id": "path-1",
                "content": "病理检查报告：病理诊断胃中分化腺癌。",
            }
        ],
        families=["tumor_pathology"],
    )
    context = render_luxian_0609_fact_context(facts, families=["tumor_pathology"])
    prompt = build_luxian_0609_fact_prompt(family="tumor_pathology", documents_text="病理检查报告：病理诊断胃中分化腺癌。")

    assert "结构化事实摘要" in context
    assert "病理检查报告" in context
    assert "不是判定合规/不合规" in prompt


@pytest.mark.asyncio
async def test_extract_luxian_0609_facts_with_llm_should_parse_source_grounded_json():
    client = _FakeLLMFactClient(
        """```json
        {
          "facts": [
            {
              "fact_type": "pathology_specimen_sent",
              "source_document_type": "手术记录",
              "source_document_id": "op-1",
              "record_time": "2026-06-01 11:00:00",
              "quote": "阑尾向患者家属展示后送病检",
              "confidence": 0.91
            },
            {
              "fact_type": "chemo_fact",
              "source_document_type": "既往史",
              "source_document_id": "admission-1",
              "record_time": "",
              "quote": "既往曾行化疗",
              "confidence": 0.2
            }
          ]
        }
        ```"""
    )
    facts = await extract_luxian_0609_facts_with_llm(
        [
            {
                "source_table": "operation_record",
                "document_id": "op-1",
                "content": "手术记录：阑尾向患者家属展示后送病检。",
            }
        ],
        families=["tumor_pathology"],
        client=client,
    )

    assert len(facts) == 1
    assert facts[0].fact_type == "pathology_specimen_sent"
    assert facts[0].extractor == "llm"
    assert "不是判定合规/不合规" in client.prompts[0]


def test_extract_luxian_0609_structured_facts_should_prefer_typed_source_fields():
    documents = [
        {
            "source_table": "operation_record",
            "document_id": "op-1",
            "source_fields": {
                "operation_name": "腹腔镜胆囊切除术",
                "incision_type": "II类切口",
                "record_time": "2026-06-01 10:00:00",
            },
            "content": "术后病程摘要。",
        },
        {
            "source_table": "temporary_order",
            "document_id": "order-1",
            "source_fields": {
                "order_name": "头孢呋辛钠 1.5g 静滴",
                "start_time": "2026-06-01 09:20:00",
                "order_status": "新开",
            },
        },
    ]

    facts = extract_luxian_0609_structured_facts(documents, families=["surgery_anesthesia"])
    fact_types = {fact.fact_type for fact in facts}

    assert "surgery_fact" in fact_types
    assert "antibiotic_order" in fact_types
    assert all(fact.extractor == "structured" for fact in facts)
    assert any("operation_name" in fact.quote and "胆囊切除" in fact.quote for fact in facts)


def test_merge_luxian_0609_facts_should_keep_structured_over_llm_duplicate():
    structured = Luxian0609Fact(
        fact_type="pathology_report",
        family="tumor_pathology",
        source_document_type="pathology_report",
        source_document_id="path-1",
        quote="病理诊断：胃腺癌",
        confidence=0.94,
        extractor="structured",
    )
    llm_duplicate = Luxian0609Fact(
        fact_type="pathology_report",
        family="tumor_pathology",
        source_document_type="病理报告",
        source_document_id="path-1",
        quote="病理诊断：胃腺癌",
        confidence=0.99,
        extractor="llm",
    )

    merged = merge_luxian_0609_facts(([llm_duplicate], [structured]))

    assert len(merged) == 1
    assert merged[0].extractor == "structured"


@pytest.mark.asyncio
async def test_unified_fact_table_should_merge_structured_regex_and_qwen_next_llm_facts():
    client = _FakeLLMFactClient(
        """{
          "facts": [
            {
              "fact_type": "surgical_discussion",
              "source_document_type": "术前讨论",
              "source_document_id": "discussion-1",
              "record_time": "2026-06-01 08:00:00",
              "quote": "术前讨论记录：拟行腹腔镜胆囊切除术，已讨论麻醉和切口风险。",
              "confidence": 0.82
            }
          ]
        }"""
    )
    documents = [
        {
            "source_table": "operation_record",
            "document_id": "op-1",
            "record_time": "2026-06-01 10:00:00",
            "source_fields": {
                "operation_name": "腹腔镜胆囊切除术",
                "incision_type": "II类切口",
            },
            "content": "手术记录：取出胆囊标本后送病理检查。",
        },
        {
            "source_table": "pathology_report",
            "document_id": "path-1",
            "source_fields": {
                "pathology_diagnosis": "慢性胆囊炎伴胆固醇沉积",
                "report_time": "2026-06-02 09:30:00",
            },
        },
    ]

    table = await extract_luxian_0609_unified_fact_table(
        documents,
        families=["surgery_anesthesia", "tumor_pathology"],
        llm_client=client,
    )
    fact_types = {fact.fact_type for fact in table.facts}

    assert "surgery_fact" in fact_types
    assert "pathology_report" in fact_types
    assert "pathology_specimen_sent" in fact_types
    assert "surgical_discussion" in fact_types
    assert table.stats["llm_model"] == "qwen3-next-80b-a3b-instruct"
    assert table.stats["stage_counts"]["structured"] >= 2
    assert table.stats["stage_counts"]["regex"] >= 1
    assert table.stats["stage_counts"]["llm"] == 1
    assert table.stats["stage_counts"]["merged"] == len(table.facts)
