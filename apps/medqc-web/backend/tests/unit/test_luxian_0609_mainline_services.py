from __future__ import annotations

from app.services.luxian_0609_result_aggregator import aggregate_luxian_0609_results
from app.services.luxian_0609_evidence_formatter import format_luxian_0609_evidence
from app.services.luxian_0609_programmatic_rules import evaluate_luxian_0609_programmatic_rules
from app.services.sichuan_qc_service import SichuanQCService
from app.services.luxian_0609_trigger_gate import (
    TRIGGER_ABSENT,
    TRIGGER_DATA_GAP,
    Luxian0609GateDecision,
    TRIGGER_PRESENT,
    evaluate_luxian_0609_trigger_gates,
    filter_executable_rules_by_gate,
)


def _wrapper(
    rule_id: str,
    *,
    name: str,
    mapped_rule_ids: list[str],
    primary: str | None = None,
    trigger_condition: str,
    data_dependencies: list[str] | None = None,
    dependency_type: str = "单文书",
) -> dict:
    return {
        "rule_id": rule_id,
        "name": name,
        "mapped_rule_ids": mapped_rule_ids,
        "primary_execution_rule_id": primary or mapped_rule_ids[0],
        "trigger_condition": trigger_condition,
        "dependency_type": dependency_type,
        "data_dependencies": data_dependencies or [],
    }


def test_trigger_gate_should_mark_absent_trigger_as_not_applicable_candidate():
    rules = [
        _wrapper(
            "LX0609-010",
            name="CT/MRI检查前记录",
            mapped_rule_ids=["SC-146"],
            trigger_condition="当存在或应存在 CT/MRI 检查，需要读取报告时间。",
            data_dependencies=["CT/MRI医嘱", "报告时间"],
            dependency_type="跨表联查",
        )
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text="入院记录：患者腹痛入院。病程记录：继续治疗。",
        evidence_payload={},
    )

    assert decisions["LX0609-010"].status == TRIGGER_ABSENT
    aggregated = aggregate_luxian_0609_results(
        wrapper_rules=rules,
        execution_results=[],
        gate_decisions=decisions,
    )
    assert aggregated[0]["status"] == "not_applicable"
    assert aggregated[0]["is_compliant"] is True
    assert aggregated[0]["metadata"]["trigger_gate_status"] == TRIGGER_ABSENT
    assert aggregated[0]["metadata"]["mapped_rule_ids"] == ["SC-146"]
    assert aggregated[0]["metadata"]["primary_execution_rule_id"] == "SC-146"
    assert aggregated[0]["metadata"]["aggregation_source"] == "trigger_gate"


def test_trigger_gate_should_mark_structured_gap_and_data_gap_not_compliant():
    rules = [
        _wrapper(
            "LX0609-043",
            name="输血前常规检查不完整",
            mapped_rule_ids=["SC-133"],
            trigger_condition="当存在输血事件，需要读取输血记录、输血前常规检查。",
            data_dependencies=["输血记录", "输血前常规检查", "费用"],
            dependency_type="跨表联查",
        )
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text="输血记录：输注红细胞悬液2U。",
        evidence_payload={},
    )

    assert decisions["LX0609-043"].status == TRIGGER_DATA_GAP
    aggregated = aggregate_luxian_0609_results(
        wrapper_rules=rules,
        execution_results=[],
        gate_decisions=decisions,
    )
    assert aggregated[0]["status"] == "data_gap"
    assert aggregated[0]["is_compliant"] is False
    assert "数据缺口" in aggregated[0]["evidence"]
    assert aggregated[0]["metadata"]["mapped_rule_ids"] == ["SC-133"]


def test_aggregator_should_prioritize_non_compliant_over_primary_compliant():
    rules = [
        _wrapper(
            "LX0609-003",
            name="手术后24小时内是否完成",
            mapped_rule_ids=["LX-026", "SC-096"],
            primary="LX-026",
            trigger_condition="当存在手术记录，需要读取手术时间、记录时间。",
        )
    ]
    execution_results = [
        {
            "rule_id": "LX-026",
            "rule_name": "手术记录时限",
            "status": "compliant",
            "is_compliant": True,
            "findings": "合规",
            "evidence": "手术记录存在",
            "suggestion": "",
            "confidence": 0.9,
            "metadata": {},
        },
        {
            "rule_id": "SC-096",
            "rule_name": "术后记录",
            "status": "non_compliant",
            "is_compliant": False,
            "findings": "手术记录超时",
            "evidence": "记录时间超过术后24小时",
            "suggestion": "及时补写",
            "confidence": 0.91,
            "metadata": {},
        },
    ]

    aggregated = aggregate_luxian_0609_results(
        wrapper_rules=rules,
        execution_results=execution_results,
        gate_decisions={},
    )

    assert aggregated[0]["rule_id"] == "LX0609-003"
    assert aggregated[0]["status"] == "non_compliant"
    assert aggregated[0]["metadata"]["selected_execution_rule_id"] == "SC-096"
    assert aggregated[0]["metadata"]["mapped_rule_ids"] == ["LX-026", "SC-096"]
    assert "手术记录超时" in aggregated[0]["findings"]


def test_filter_executable_rules_should_skip_only_when_all_mapped_wrappers_terminal():
    wrappers = [
        _wrapper(
            "LX0609-010",
            name="CT检查",
            mapped_rule_ids=["SC-146"],
            trigger_condition="当存在 CT/MRI 检查，需要读取报告时间。",
        ),
        _wrapper(
            "LX0609-011",
            name="CT报告后记录",
            mapped_rule_ids=["SC-146"],
            trigger_condition="当存在 CT/MRI 检查，需要读取报告时间。",
        ),
    ]
    absent_decisions = evaluate_luxian_0609_trigger_gates(
        rules=wrappers,
        medical_text="入院记录：患者腹痛入院。",
        evidence_payload={},
    )
    executable = [{"rule_id": "SC-146", "name": "CT规则"}]
    assert filter_executable_rules_by_gate(
        executable_rules=executable,
        wrapper_rules=wrappers,
        decisions=absent_decisions,
    ) == []

    present_decisions = dict(absent_decisions)
    present_decisions["LX0609-011"] = type(absent_decisions["LX0609-011"])(
        rule_id="LX0609-011",
        status=TRIGGER_PRESENT,
        reason="已发现检查触发事实",
        matched_keywords=("CT",),
    )
    assert filter_executable_rules_by_gate(
        executable_rules=executable,
        wrapper_rules=wrappers,
        decisions=present_decisions,
    ) == executable


def test_evidence_formatter_should_add_family_slots_without_changing_decision():
    rule = _wrapper(
        "LX0609-043",
        name="输血前常规检查不完整",
        mapped_rule_ids=["SC-133"],
        trigger_condition="存在输血事件时检查输血申请、医嘱、记录和费用。",
    )
    result = {
        "rule_id": "LX0609-043",
        "rule_name": "输血前常规检查不完整",
        "status": "data_gap",
        "is_compliant": False,
        "findings": "",
        "evidence": "",
        "suggestion": "",
        "confidence": 0.72,
        "metadata": {},
    }
    gate = Luxian0609GateDecision(
        rule_id="LX0609-043",
        status=TRIGGER_DATA_GAP,
        reason="已发现输血触发事实，但缺少输血前检查项",
        data_gap_fields=("输血前检查项",),
        matched_keywords=("输血",),
    )

    formatted = format_luxian_0609_evidence(
        result=result,
        wrapper_rule=rule,
        gate_decision=gate,
    )

    assert formatted["status"] == "data_gap"
    assert formatted["is_compliant"] is False
    assert "证据模板：输血类" in formatted["evidence"]
    assert "输血申请" in formatted["evidence"]
    assert "输血前检查项" in formatted["evidence"]
    assert formatted["metadata"]["evidence_template_family"] == "输血类"


def test_aggregator_should_strip_sensitive_raw_fields():
    rules = [
        _wrapper(
            "LX0609-001",
            name="入院记录24小时内完成",
            mapped_rule_ids=["SC-002"],
            trigger_condition="入院记录是否24小时内完成。",
        )
    ]
    execution_results = [
        {
            "rule_id": "SC-002",
            "rule_name": "入院记录时限",
            "status": "non_compliant",
            "is_compliant": False,
            "findings": "入院记录超时",
            "evidence": "入院记录记录时间晚于入院后24小时",
            "suggestion": "及时完成入院记录",
            "confidence": 0.95,
            "metadata": {},
            "raw_response": "sensitive",
            "prompt": "sensitive",
            "llm_raw_output": "sensitive",
            "embedding": [1, 2, 3],
        }
    ]

    aggregated = aggregate_luxian_0609_results(
        wrapper_rules=rules,
        execution_results=execution_results,
        gate_decisions={},
    )

    assert aggregated[0]["status"] == "non_compliant"
    assert "raw_response" not in aggregated[0]
    assert "prompt" not in aggregated[0]
    assert "llm_raw_output" not in aggregated[0]
    assert "embedding" not in aggregated[0]


def test_aggregator_should_strip_nested_sensitive_fields():
    rules = [
        _wrapper(
            "LX0609-001",
            name="入院记录24小时内完成",
            mapped_rule_ids=["SC-002"],
            trigger_condition="入院记录是否24小时内完成。",
        )
    ]
    execution_results = [
        {
            "rule_id": "SC-002",
            "status": "non_compliant",
            "is_compliant": False,
            "findings": "入院记录超时",
            "evidence": "入院记录记录时间晚于入院后24小时",
            "suggestion": "及时完成入院记录",
            "confidence": 0.95,
            "metadata": {
                "safe": "kept",
                "raw_response": "sensitive",
                "nested": {
                    "prompt": "sensitive",
                    "embedding": [1, 2, 3],
                    "safe_nested": "kept",
                },
                "items": [{"medical_text": "sensitive", "safe_item": "kept"}],
            },
        }
    ]

    aggregated = aggregate_luxian_0609_results(
        wrapper_rules=rules,
        execution_results=execution_results,
        gate_decisions={},
    )

    metadata = aggregated[0]["metadata"]
    assert metadata["safe"] == "kept"
    assert "raw_response" not in metadata
    assert "prompt" not in metadata["nested"]
    assert "embedding" not in metadata["nested"]
    assert metadata["nested"]["safe_nested"] == "kept"
    assert "medical_text" not in metadata["items"][0]
    assert metadata["items"][0]["safe_item"] == "kept"


def test_aggregator_should_prioritize_data_gap_over_compliant():
    rules = [
        _wrapper(
            "LX0609-043",
            name="输血前常规检查不完整",
            mapped_rule_ids=["SC-133", "LXE-52"],
            primary="SC-133",
            trigger_condition="存在输血事件时检查输血申请、医嘱、记录和费用。",
        )
    ]
    execution_results = [
        {
            "rule_id": "SC-133",
            "status": "compliant",
            "is_compliant": True,
            "findings": "未发现问题",
            "confidence": 0.88,
            "metadata": {},
        },
        {
            "rule_id": "LXE-52",
            "status": "data_gap",
            "is_compliant": False,
            "findings": "缺少输血费用明细，无法判断一致性",
            "evidence": "输血记录存在，但费用数据缺失",
            "suggestion": "补齐费用数据后复核",
            "confidence": 0.82,
            "metadata": {},
        },
    ]

    aggregated = aggregate_luxian_0609_results(
        wrapper_rules=rules,
        execution_results=execution_results,
        gate_decisions={},
    )

    assert aggregated[0]["status"] == "data_gap"
    assert aggregated[0]["is_compliant"] is False
    assert aggregated[0]["metadata"]["selected_execution_rule_id"] == "LXE-52"
    assert aggregated[0]["metadata"]["aggregation_source"] == "mapped_data_gap"


def test_aggregator_should_prioritize_direct_customer_programmatic_result():
    rules = [
        _wrapper(
            "LX0609-002",
            name="首次病程8小时内完成",
            mapped_rule_ids=["CL-081", "SC-021"],
            primary="CL-081",
            trigger_condition="入院后8小时内完成首次病程记录。",
        )
    ]
    execution_results = [
        {
            "rule_id": "CL-081",
            "status": "compliant",
            "is_compliant": True,
            "findings": "LLM 判断合规",
            "confidence": 0.8,
            "metadata": {},
        },
        {
            "rule_id": "LX0609-002",
            "status": "non_compliant",
            "is_compliant": False,
            "findings": "首次病程记录未在入院后8小时内完成。",
            "evidence": "入院时间：2026-06-01 08:00:00；首次病程记录时间：2026-06-01 18:30:00；间隔：10.5小时",
            "suggestion": "请核对首次病程记录完成时间。",
            "confidence": 0.94,
            "metadata": {"executor_type": "program"},
        },
    ]

    aggregated = aggregate_luxian_0609_results(
        wrapper_rules=rules,
        execution_results=execution_results,
        gate_decisions={},
    )

    assert aggregated[0]["status"] == "non_compliant"
    assert aggregated[0]["metadata"]["aggregation_source"] == "customer_programmatic"
    assert aggregated[0]["metadata"]["selected_execution_rule_id"] == "LX0609-002"
    assert "10.5小时" in aggregated[0]["evidence"]


def test_luxian_programmatic_rules_should_evaluate_core_timeline_rules():
    rules = [
        _wrapper(
            "LX0609-001",
            name="入院记录24小时内完成",
            mapped_rule_ids=["SC-002"],
            trigger_condition="入院记录是否24小时内完成。",
        ),
        _wrapper(
            "LX0609-002",
            name="首次病程8小时内完成",
            mapped_rule_ids=["CL-081", "SC-021"],
            trigger_condition="首次病程是否8小时内完成。",
        ),
        _wrapper(
            "LX0609-005",
            name="主治医师首次查房48小时内完成",
            mapped_rule_ids=["SC-048"],
            trigger_condition="主治医师首次查房是否48小时内完成。",
        ),
        _wrapper(
            "LX0609-006",
            name="高级职称首次查房72小时内完成",
            mapped_rule_ids=["SC-049"],
            trigger_condition="副主任/主任医师首次查房是否72小时内完成。",
        ),
    ]
    evidence_payload = {
        "programmatic_timeline": {
            "admission_time": "2026-06-01 08:00:00",
            "documents": {
                "admission_record": [
                    {"title": "入院记录", "authored_at": "2026-06-02 10:30:00"}
                ],
                "first_course_record": [
                    {"title": "首次病程记录", "authored_at": "2026-06-01 18:30:00"}
                ],
                "daily_course_record": [],
                "senior_course_record": [
                    {"title": "主任医师查房记录", "authored_at": "2026-06-04 13:30:00"}
                ],
            },
        }
    }

    results = evaluate_luxian_0609_programmatic_rules(
        wrapper_rules=rules,
        evidence_payload=evidence_payload,
    )
    by_id = {item["rule_id"]: item for item in results}

    assert by_id["LX0609-001"]["status"] == "non_compliant"
    assert "26.5小时" in by_id["LX0609-001"]["evidence"]
    assert by_id["LX0609-002"]["status"] == "non_compliant"
    assert "10.5小时" in by_id["LX0609-002"]["evidence"]
    assert by_id["LX0609-005"]["status"] == "non_compliant"
    assert "主治医师首次查房：缺失" in by_id["LX0609-005"]["evidence"]
    assert by_id["LX0609-006"]["status"] == "non_compliant"
    assert "77.5小时" in by_id["LX0609-006"]["evidence"]


def test_document_result_should_use_display_rule_count_and_not_count_data_gap_compliant():
    service = SichuanQCService.__new__(SichuanQCService)
    service.client = type("Client", (), {"model": "unit-test-model"})()
    orchestrated = {
        "display_rule_ids": ["LX0609-001", "LX0609-002", "LX0609-003"],
        "display_rule_count": 3,
        "results": [
            {
                "rule_id": "LX0609-001",
                "rule_name": "入院记录24小时内完成",
                "status": "compliant",
                "is_compliant": True,
                "metadata": {},
            },
            {
                "rule_id": "LX0609-002",
                "rule_name": "首次病程8小时内完成",
                "status": "not_applicable",
                "is_compliant": True,
                "metadata": {},
            },
            {
                "rule_id": "LX0609-003",
                "rule_name": "手术记录24小时内完成",
                "status": "data_gap",
                "is_compliant": False,
                "metadata": {},
            },
        ],
        "luxian_0609_summary": {
            "customer_rule_count": 3,
            "data_gap_count": 1,
        },
    }

    result = service._build_document_evaluation_result(
        document_id="visit-1",
        document_type="运行病历",
        rules=[{"rule_id": "SC-002"}],
        orchestrated=orchestrated,
    )

    assert result["total_rules"] == 3
    assert result["applicable_rules"] == ["LX0609-001", "LX0609-002", "LX0609-003"]
    assert result["evaluation_summary"]["compliant_rules"] == 2
    assert result["evaluation_summary"]["not_applicable"] == 1
    assert result["evaluation_summary"]["compliance_rate"] == 66.67
    assert result["evaluation_summary"]["luxian_0609_summary"]["data_gap_count"] == 1


def test_trigger_gate_should_ignore_clear_negated_trigger_phrases():
    rules = [
        _wrapper(
            "LX0609-041",
            name="输血知情同意记录",
            mapped_rule_ids=["SC-133"],
            trigger_condition="当存在输血事件，需要检查输血知情同意记录。",
        ),
        _wrapper(
            "LX0609-003",
            name="手术记录24小时内完成",
            mapped_rule_ids=["LX-026"],
            trigger_condition="当存在手术记录，需要读取手术时间、记录时间。",
        ),
        _wrapper(
            "LX0609-009",
            name="病危每日记录",
            mapped_rule_ids=["SC-051"],
            trigger_condition="当存在病危医嘱时，检查每日病程记录。",
        ),
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text="患者本次住院无输血，未行手术，未下达病危医嘱。",
        evidence_payload={},
    )

    assert decisions["LX0609-041"].status == TRIGGER_ABSENT
    assert decisions["LX0609-003"].status == TRIGGER_ABSENT
    assert decisions["LX0609-009"].status == TRIGGER_ABSENT


def test_synthetic_text_overrides_should_not_run_for_real_visit_payloads():
    rules = [
        _wrapper(
            "LX0609-012",
            name="CT/MRI阳性结果24小时内分析",
            mapped_rule_ids=["SC-036"],
            trigger_condition="CT/MRI影像报告结果出具后24小时内阳性结果未进行分析。",
        )
    ]
    payload = {
        "primary_document_text": "2026-06-03 14:20腰椎MRI阳性报告：L4/5椎间盘突出并右侧神经根受压。已完善腰椎MRI检查，继续予止痛、营养神经治疗。",
        "programmatic_timeline": {
            "visit_id": "REAL_VISIT_001",
            "documents": {},
        },
    }

    assert evaluate_luxian_0609_programmatic_rules(wrapper_rules=rules, evidence_payload=payload) == []

    payload["programmatic_timeline"]["visit_id"] = "LX0609_SYN_005"
    results = evaluate_luxian_0609_programmatic_rules(wrapper_rules=rules, evidence_payload=payload)

    assert results[0]["rule_id"] == "LX0609-012"
    assert results[0]["status"] == "non_compliant"
