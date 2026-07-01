from __future__ import annotations

from app.routers.qc_sichuan import _build_record_status_counts
from app.services.luxian_0609_result_aggregator import aggregate_luxian_0609_results, summarize_luxian_0609_results
from app.services.luxian_0609_evidence_formatter import format_luxian_0609_evidence
from app.services.luxian_0609_programmatic_rules import evaluate_luxian_0609_programmatic_rules
from app.services.luxian_0609_result_schema import apply_luxian_0609_result_schema
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


def test_trigger_gate_absent_should_override_customer_programmatic_gap():
    rules = [
        _wrapper(
            "LX0609-041",
            name="输血知情同意书：无输血知情同意书",
            mapped_rule_ids=["SC-133"],
            trigger_condition="存在输血事件时检查输血知情同意记录。",
            data_dependencies=["输血记录", "输血医嘱"],
            dependency_type="跨表联查",
        )
    ]
    decisions = {
        "LX0609-041": Luxian0609GateDecision(
            rule_id="LX0609-041",
            status=TRIGGER_ABSENT,
            reason="病历文本和证据中未发现transfusion相关触发事实",
        )
    }

    aggregated = aggregate_luxian_0609_results(
        wrapper_rules=rules,
        execution_results=[
            {
                "rule_id": "LX0609-041",
                "status": "data_gap",
                "is_compliant": False,
                "findings": "已发现触发事件，但缺少输血记录。",
                "evidence": "数据缺口：输血记录",
                "suggestion": "补齐输血记录。",
            }
        ],
        gate_decisions=decisions,
    )

    assert aggregated[0]["status"] == "not_applicable"
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
    assert "缺失字段" in aggregated[0]["evidence"]
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


def test_aggregator_should_not_show_lx0609_003_positive_time_result_as_defect():
    rules = [
        _wrapper(
            "LX0609-003",
            name="手术记录：手术后24小时内是否完成",
            mapped_rule_ids=["SC-096"],
            trigger_condition="手术记录应在术后24小时内完成。",
        )
    ]

    aggregated = aggregate_luxian_0609_results(
        wrapper_rules=rules,
        execution_results=[
            {
                "rule_id": "SC-096",
                "rule_name": "手术记录时限",
                "status": "non_compliant",
                "is_compliant": False,
                "findings": "手术记录在术后43分钟完成，未超过24小时，但缺少麻醉记录无法通过麻醉记录交叉验证。",
                "evidence": "执行证据：手术结束时间2026-06-01 10:00；手术记录时间2026-06-01 10:43。",
                "suggestion": "补充麻醉记录。",
                "confidence": 0.88,
                "metadata": {},
            }
        ],
        gate_decisions={},
    )

    assert aggregated[0]["status"] == "data_gap"
    assert aggregated[0]["is_compliant"] is False
    assert "未超过术后24小时" in aggregated[0]["findings"]
    assert "缺少麻醉记录" in aggregated[0]["findings"]
    assert aggregated[0]["metadata"]["customer_display_guard"] == "lx0609_003_positive_time_result"


def test_aggregator_should_not_show_recorded_pathology_specimen_as_defect_for_019_and_024():
    rules = [
        _wrapper(
            "LX0609-019",
            name="病理检查：取材情况未在病程记录或手术记录中进行记录",
            mapped_rule_ids=["SC-099"],
            trigger_condition="病理取材情况应在手术记录或病程中记录。",
        ),
        _wrapper(
            "LX0609-024",
            name="恶性肿瘤手术记录未书写淋巴结清扫情况",
            mapped_rule_ids=["SC-099"],
            trigger_condition="恶性肿瘤手术记录应书写淋巴结清扫情况。",
        ),
    ]

    aggregated = aggregate_luxian_0609_results(
        wrapper_rules=rules,
        execution_results=[
            {
                "rule_id": "SC-099",
                "rule_name": "术中取材和病理结果记录",
                "status": "non_compliant",
                "is_compliant": False,
                "findings": "手术记录已记录术中取材及冰冻病理结果。",
                "evidence": "执行证据：手术记录：送检肿物及第7组淋巴结，冰冻病理提示恶性。",
                "suggestion": "人工复核。",
                "confidence": 0.9,
                "metadata": {},
            }
        ],
        gate_decisions={},
    )

    by_id = {item["rule_id"]: item for item in aggregated}
    for rule_id in ["LX0609-019", "LX0609-024"]:
        assert by_id[rule_id]["status"] == "compliant"
        assert by_id[rule_id]["is_compliant"] is True
        assert "未形成缺陷" in by_id[rule_id]["findings"]
        assert by_id[rule_id]["metadata"]["customer_display_guard"] == "pathology_specimen_positive_recorded"


def test_aggregator_should_not_map_final_pathology_gap_to_specimen_or_lymph_defect():
    rules = [
        _wrapper(
            "LX0609-019",
            name="病理检查：取材情况未在病程记录或手术记录中进行记录",
            mapped_rule_ids=["SC-099"],
            trigger_condition="病理取材情况应在手术记录或病程中记录。",
        ),
        _wrapper(
            "LX0609-024",
            name="恶性肿瘤手术记录未书写淋巴结清扫情况",
            mapped_rule_ids=["SC-099"],
            trigger_condition="恶性肿瘤手术记录应书写淋巴结清扫情况。",
        ),
    ]

    aggregated = aggregate_luxian_0609_results(
        wrapper_rules=rules,
        execution_results=[
            {
                "rule_id": "SC-099",
                "rule_name": "术中取材和病理结果记录",
                "status": "non_compliant",
                "is_compliant": False,
                "findings": "手术记录记录了术中冰冻病理结果，但未记录术后石蜡病理最终结果。",
                "evidence": (
                    "执行证据：【手术记录】楔形切除左肺上叶结节，检查切缘无出血，"
                    "家属看过标本后送检。术中冰冻病理提示浸润性腺癌。"
                ),
                "suggestion": "补充术后石蜡病理最终诊断结果。",
                "confidence": 0.95,
                "metadata": {},
            }
        ],
        gate_decisions={},
    )

    by_id = {item["rule_id"]: item for item in aggregated}
    for rule_id in ["LX0609-019", "LX0609-024"]:
        assert by_id[rule_id]["status"] == "compliant"
        assert by_id[rule_id]["is_compliant"] is True
        assert by_id[rule_id]["metadata"]["customer_display_guard"] == "pathology_specimen_positive_recorded"


def test_aggregator_should_keep_specimen_detail_absence_as_non_compliant():
    rules = [
        _wrapper(
            "LX0609-019",
            name="病理检查：取材情况未在病程记录或手术记录中进行记录",
            mapped_rule_ids=["SC-099"],
            trigger_condition="病理取材情况应在手术记录或病程中记录。",
        )
    ]

    aggregated = aggregate_luxian_0609_results(
        wrapper_rules=rules,
        execution_results=[
            {
                "rule_id": "SC-099",
                "rule_name": "术中取材和病理结果记录",
                "status": "non_compliant",
                "is_compliant": False,
                "findings": "手术记录仅笼统描述送检组织，未详细记录取材部位、切缘及淋巴结分组。",
                "evidence": "执行证据：【手术记录】标本处理：远端胃及胃周组织送病理检查。",
                "suggestion": "补充记录各切缘及淋巴结分组的取材详情。",
                "confidence": 0.92,
                "metadata": {},
            }
        ],
        gate_decisions={},
    )

    assert aggregated[0]["status"] == "non_compliant"
    assert aggregated[0]["is_compliant"] is False
    assert "未详细记录取材部位" in aggregated[0]["findings"]


def test_aggregator_should_make_lx0609_017_unstructured_uncertain_customer_readable():
    rules = [
        _wrapper(
            "LX0609-017",
            name="不合理复制病历：2次以上病程记录完全相同",
            mapped_rule_ids=["CL-273"],
            trigger_condition="两次以上病程记录相似度大于70%时需复核。",
        )
    ]

    aggregated = aggregate_luxian_0609_results(
        wrapper_rules=rules,
        execution_results=[
            {
                "rule_id": "CL-273",
                "rule_name": "病程记录重复",
                "status": "uncertain",
                "is_compliant": False,
                "findings": "LLM 返回非结构化结果，请查看原始输出。",
                "evidence": "LLM 返回了非结构化结果，请查看原始输出。",
                "suggestion": "查看原始输出。",
                "confidence": 0.2,
                "metadata": {},
            }
        ],
        gate_decisions={},
    )

    assert aggregated[0]["status"] == "uncertain"
    assert "病程记录重复度未形成可靠自动结论" in aggregated[0]["findings"]
    assert "LLM" not in aggregated[0]["findings"]
    assert "原始输出" not in aggregated[0]["evidence"]
    assert aggregated[0]["metadata"]["customer_display_guard"] == "customer_readable_uncertain"


def test_aggregator_should_not_show_lx0609_017_single_course_vs_admission_as_defect():
    rules = [
        _wrapper(
            "LX0609-017",
            name="不合理复制病历：2次以上病程记录完全相同",
            mapped_rule_ids=["CL-275"],
            trigger_condition="两次以上病程记录相似度大于70%时需复核。",
        )
    ]

    aggregated = aggregate_luxian_0609_results(
        wrapper_rules=rules,
        execution_results=[
            {
                "rule_id": "CL-275",
                "rule_name": "病程记录重复",
                "status": "non_compliant",
                "is_compliant": False,
                "findings": "当前病程记录（2026-06-01）与入院记录、首次病程记录中的辅助检查数据及初步诊断思路高度重复。",
                "evidence": "执行证据：【日常病程记录】查房内容：患者存在腹泻症状。",
                "suggestion": "补充病情变化描述。",
                "confidence": 0.8,
                "metadata": {},
            }
        ],
        gate_decisions={},
    )

    assert aggregated[0]["status"] == "uncertain"
    assert "病程记录重复度未形成可靠自动结论" in aggregated[0]["findings"]
    assert aggregated[0]["metadata"]["customer_display_guard"] == "copy_rule_requires_two_course_records"


def test_aggregator_should_not_show_positive_consultation_execution_as_defect():
    rules = [
        _wrapper(
            "LX0609-020",
            name="会诊记录：有会诊记录单无请会诊执行记录",
            mapped_rule_ids=["CL-250"],
            trigger_condition="存在会诊记录时，病程应记录会诊意见执行情况。",
        )
    ]

    aggregated = aggregate_luxian_0609_results(
        wrapper_rules=rules,
        execution_results=[
            {
                "rule_id": "CL-250",
                "rule_name": "会诊执行情况",
                "status": "non_compliant",
                "is_compliant": False,
                "findings": "会诊记录已包含执行情况，未违反规则。",
                "evidence": "执行证据：病程记录已写明按会诊意见调整治疗。",
                "suggestion": "无需整改。",
                "confidence": 0.8,
                "metadata": {},
            }
        ],
        gate_decisions={},
    )

    assert aggregated[0]["status"] == "compliant"
    assert aggregated[0]["is_compliant"] is True
    assert "未形成缺陷" in aggregated[0]["findings"]
    assert aggregated[0]["metadata"]["customer_display_guard"] == "consultation_execution_positive_recorded"


def test_aggregator_should_not_show_consultation_signature_only_as_execution_defect():
    rules = [
        _wrapper(
            "LX0609-023",
            name="会诊记录：请会诊执行记录不规范",
            mapped_rule_ids=["CL-248"],
            trigger_condition="会诊执行记录应具体记录执行措施。",
        )
    ]

    aggregated = aggregate_luxian_0609_results(
        wrapper_rules=rules,
        execution_results=[
            {
                "rule_id": "CL-248",
                "rule_name": "会诊执行记录",
                "status": "non_compliant",
                "is_compliant": False,
                "findings": "会诊记录中缺少申请会诊医师签名。",
                "evidence": "执行证据：【会诊记录】患者有会诊指征，医生签名：",
                "suggestion": "补充申请医师签名。",
                "confidence": 0.8,
                "metadata": {},
            }
        ],
        gate_decisions={},
    )

    assert aggregated[0]["status"] == "uncertain"
    assert "未能确认会诊意见执行情况缺陷" in aggregated[0]["findings"]
    assert aggregated[0]["metadata"]["customer_display_guard"] == "consultation_signature_only_not_execution_defect"


def test_aggregator_should_make_any_unstructured_uncertain_customer_readable():
    rules = [
        _wrapper(
            "LX0609-040",
            name="术前多学科讨论记录",
            mapped_rule_ids=["SC-083"],
            trigger_condition="四级手术术前讨论应进行多学科讨论。",
        )
    ]

    aggregated = aggregate_luxian_0609_results(
        wrapper_rules=rules,
        execution_results=[
            {
                "rule_id": "SC-083",
                "rule_name": "术前多学科讨论",
                "status": "uncertain",
                "is_compliant": False,
                "findings": "LLM 返回了非结构化结果，请查看原始输出。",
                "evidence": "LLM 返回了非结构化结果，请查看原始输出。",
                "suggestion": "查看原始输出。",
                "confidence": 0.2,
                "metadata": {},
            }
        ],
        gate_decisions={},
    )

    assert aggregated[0]["status"] == "uncertain"
    assert "本质控点未形成可靠自动结论" in aggregated[0]["findings"]
    assert "LLM" not in aggregated[0]["findings"]
    assert "原始输出" not in aggregated[0]["evidence"]
    assert aggregated[0]["metadata"]["customer_display_guard"] == "customer_readable_uncertain"


def test_aggregator_should_not_mark_copy_rule_non_compliant_when_first_course_is_empty():
    rules = [
        _wrapper(
            "LX0609-016",
            name="不合理复制病历",
            mapped_rule_ids=["SC-COPY"],
            trigger_condition="首次病程记录病例特点与入院记录、现病史完全相同。",
        )
    ]
    execution_results = [
        {
            "rule_id": "SC-COPY",
            "rule_name": "复制病历",
            "status": "non_compliant",
            "is_compliant": False,
            "findings": "首次病程与入院记录完全相同。",
            "evidence": "首次病程记录复制入院记录。",
            "suggestion": "重写首次病程。",
            "confidence": 0.9,
            "metadata": {},
        }
    ]

    aggregated = aggregate_luxian_0609_results(
        wrapper_rules=rules,
        execution_results=execution_results,
        gate_decisions={},
        audit_context={
            "evidence_payload": {
                "programmatic_timeline": {
                    "documents": {
                        "first_course_record": [
                            {
                                "title": "首次病程记录",
                                "content_preview": "首次病程记录",
                            }
                        ],
                        "admission_record": [
                            {
                                "title": "入院记录",
                                "content_preview": "腰背部疼痛伴活动受限3天。",
                            }
                        ],
                    }
                }
            }
        },
    )

    assert aggregated[0]["status"] == "data_gap"
    assert "首次病程记录缺失或正文为空" in aggregated[0]["findings"]
    assert aggregated[0]["metadata"]["copy_rule_priority_guard"] == "first_course_missing"


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


def test_filter_executable_rules_should_skip_direct_customer_rule_when_gate_terminal():
    wrappers = [
        _wrapper(
            "LX0609-016",
            name="不合理复制病历",
            mapped_rule_ids=["CL-273"],
            trigger_condition="首次病程记录病例特点与入院记录、现病史完全相同。",
        )
    ]
    decisions = evaluate_luxian_0609_trigger_gates(
        rules=wrappers,
        medical_text="入院记录：腰背部疼痛伴活动受限3天。",
        evidence_payload={},
    )
    executable = [
        {"rule_id": "LX0609-016", "name": "不合理复制病历"},
        {"rule_id": "LX0609-017", "name": "病程记录重复"},
    ]

    assert filter_executable_rules_by_gate(
        executable_rules=executable,
        wrapper_rules=wrappers,
        decisions=decisions,
    ) == [{"rule_id": "LX0609-017", "name": "病程记录重复"}]


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
    assert "触发状态" not in formatted["evidence"]
    assert "触发说明" not in formatted["evidence"]
    assert "trigger_status" not in formatted["evidence"]
    assert formatted["metadata"]["evidence_template_family"] == "输血类"


def test_luxian_evidence_formatter_should_hide_internal_unknown_gate_status():
    rule = _wrapper(
        "LX0609-012",
        name="CT/MRI检查结果24小时内分析",
        mapped_rule_ids=["SC-036"],
        trigger_condition="CT/MRI影像报告结果出具后24小时内阳性结果未进行分析。",
    )
    result = {
        "rule_id": "LX0609-012",
        "status": "non_compliant",
        "is_compliant": False,
        "findings": "影像阳性结果未在病程中分析。",
        "evidence": "腰椎MRI检查报告：L4/5椎间盘突出。",
        "suggestion": "",
        "metadata": {},
    }
    gate = Luxian0609GateDecision(
        rule_id="LX0609-012",
        status="unknown",
        reason="未识别到可安全门控的触发族，进入常规执行",
    )

    formatted = format_luxian_0609_evidence(
        result=result,
        wrapper_rule=rule,
        gate_decision=gate,
    )

    assert "判定依据" in formatted["evidence"]
    assert "来源文书/表字段" in "、".join(formatted["metadata"]["evidence_template_slots"])
    assert "触发状态" not in formatted["evidence"]
    assert "触发说明" not in formatted["evidence"]
    assert "unknown" not in formatted["evidence"]


def test_luxian_result_schema_should_not_expose_internal_evidence_template_as_fallback_quote():
    rule = _wrapper(
        "LX0609-018",
        name="主诉能导出第一诊断",
        mapped_rule_ids=["SC-008", "LX-001"],
        trigger_condition="主诉应能导出第一诊断。",
    )
    result = {
        "rule_id": "LX0609-018",
        "status": "non_compliant",
        "is_compliant": False,
        "findings": "主诉与第一诊断逻辑链条不完整。",
        "evidence": (
            "证据模板：通用质控\n"
            "质控点：LX0609-018 主诉能导出第一诊断\n"
            "映射执行规则：SC-008、LX-001\n"
            "应包含证据要素：触发事实、来源文书、判定依据\n"
            "执行证据：【入院记录】纳差3天，腹泻1天"
        ),
        "suggestion": "请补充主诉与主要诊断之间的逻辑依据。",
        "metadata": {},
    }

    normalized = apply_luxian_0609_result_schema(result=result, wrapper_rule=rule)

    assert normalized["source_document"] == "质控结果"
    assert normalized["source_field"] == "关键证据"
    assert normalized["quote"] == "【入院记录】纳差3天，腹泻1天"
    assert "证据模板" not in normalized["quote"]
    assert "映射执行规则" not in normalized["quote"]


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


def test_aggregator_should_add_schema_fields_for_non_compliant_result():
    rules = [
        _wrapper(
            "LX0609-017",
            name="不合理复制病历：2次以上病程记录完全相同",
            mapped_rule_ids=["CL-275"],
            trigger_condition="当存在多篇日常病程记录时检查相似度。",
            dependency_type="同域多文书文本相似度",
        )
    ]
    execution_results = [
        {
            "rule_id": "CL-275",
            "status": "non_compliant",
            "is_compliant": False,
            "findings": "2次以上病程记录高度重复。",
            "evidence": "2026-06-03 日常病程记录与 2026-06-04 日常病程记录重复片段：患者一般情况尚可。",
            "suggestion": "请补充每日病情变化分析。",
            "confidence": 0.93,
            "metadata": {"executor_type": "cross_document", "document_type": "日常病程记录"},
        }
    ]

    aggregated = aggregate_luxian_0609_results(
        wrapper_rules=rules,
        execution_results=execution_results,
        gate_decisions={},
        audit_context={"visit_id": "2313364", "model_name": "unit-test-model"},
    )

    row = aggregated[0]
    assert row["qc_point_id"] == "LX0609-017"
    assert row["rule_set_key"] == "luxian_0609_qc_v1"
    assert row["rule_set_version"] == "2026-06-09"
    assert row["result_status"] == "non_compliant"
    assert row["executor_type"] == "cross_document"
    assert row["trigger"]["applicable"] is True
    assert row["dependencies"]["source_coverage_level"] in {"full", "unknown"}
    assert row["evidence_items"][0]["source_document_type"] == "日常病程记录"
    assert "重复片段" in row["evidence_items"][0]["quote"]
    assert row["trigger_facts"] == row["trigger"]["trigger_facts"]
    assert row["missing_sources"] == row["dependencies"]["missing_sources"]
    assert row["source_document"] == "日常病程记录"
    assert "重复片段" in row["quote"]
    assert row["threshold"] == "当存在多篇日常病程记录时检查相似度。"
    assert "重复片段" in row["actual_value"]
    assert row["decision"]["is_violation"] is True
    assert row["review"]["review_status"] == "pending"
    assert row["review_status"] == "pending"
    assert row["audit"]["visit_id"] == "2313364"
    assert row["audit"]["model_name"] == "unit-test-model"


def test_aggregator_should_add_schema_fields_for_data_gap_result():
    rules = [
        _wrapper(
            "LX0609-008",
            name="病重患者2天内无查房病程记录",
            mapped_rule_ids=["SC-051"],
            trigger_condition="当存在病重医嘱时检查2天内查房病程记录。",
            data_dependencies=["病重医嘱起止时间", "记录时间轴"],
            dependency_type="跨表联查",
        )
    ]
    gate = Luxian0609GateDecision(
        rule_id="LX0609-008",
        status=TRIGGER_DATA_GAP,
        reason="已发现病重触发事实，但缺少医嘱起止时间",
        data_gap_fields=("病重医嘱起止时间",),
        matched_keywords=("病重",),
    )

    aggregated = aggregate_luxian_0609_results(
        wrapper_rules=rules,
        execution_results=[],
        gate_decisions={"LX0609-008": gate},
    )

    row = aggregated[0]
    assert row["status"] == "data_gap"
    assert row["result_status"] == "data_gap"
    assert row["trigger"]["applicable"] is True
    assert row["trigger"]["trigger_facts"][0]["fact_value"] == "病重"
    assert row["dependencies"]["source_coverage_level"] == "partial"
    assert row["dependencies"]["missing_sources"][0]["source_name"] == "病重医嘱起止时间"
    assert "病重医嘱起止时间" in row["dependencies"]["data_gap_reason"]
    assert row["review"]["review_status"] == "pending"


def test_aggregator_should_add_schema_fields_for_not_applicable_result():
    rules = [
        _wrapper(
            "LX0609-049",
            name="输血医嘱与收费不一致",
            mapped_rule_ids=["SC-146"],
            trigger_condition="当存在输血记录时检查医嘱与费用一致性。",
            data_dependencies=["输血医嘱", "费用明细"],
            dependency_type="跨表联查",
        )
    ]
    gate = Luxian0609GateDecision(
        rule_id="LX0609-049",
        status=TRIGGER_ABSENT,
        reason="病历文本和证据中未发现transfusion相关触发事实",
    )

    aggregated = aggregate_luxian_0609_results(
        wrapper_rules=rules,
        execution_results=[],
        gate_decisions={"LX0609-049": gate},
    )

    row = aggregated[0]
    assert row["status"] == "not_applicable"
    assert row["result_status"] == "not_applicable"
    assert row["trigger"]["applicable"] is False
    assert "未发现" in row["trigger"]["not_applicable_reason"]
    assert row["dependencies"]["missing_sources"] == []
    assert row["review"]["review_status"] == "not_required"


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


def test_aggregator_should_prioritize_data_gap_over_uncertain():
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
            "status": "uncertain",
            "is_compliant": False,
            "findings": "证据边界不清，需人工复核",
            "confidence": 0.95,
            "metadata": {},
        },
        {
            "rule_id": "LXE-52",
            "status": "data_gap",
            "is_compliant": False,
            "findings": "缺少输血费用明细，无法判断一致性",
            "evidence": "输血记录存在，但费用数据缺失",
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
    assert aggregated[0]["metadata"]["aggregation_source"] == "mapped_data_gap"


def test_luxian_0609_summary_should_use_canonical_statuses_and_exclude_not_applicable_denominator():
    summary = summarize_luxian_0609_results(
        [
            {"status": "compliant", "is_compliant": True},
            {"status": "not_applicable", "is_compliant": True},
            {"status": "data_gap", "is_compliant": False},
            {"status": "uncertain", "is_compliant": False},
            {"status": "technical_error_internal", "is_compliant": False},
        ]
    )

    assert summary["status_counts"] == {
        "non_compliant": 0,
        "compliant": 1,
        "not_applicable": 1,
        "data_gap": 1,
        "uncertain": 1,
        "not_executed": 0,
        "technical_error": 1,
    }
    assert summary["compliant_count"] == 1
    assert summary["not_applicable_count"] == 1
    assert summary["data_gap_count"] == 1
    assert summary["technical_error_count"] == 1
    assert summary["compliance_denominator"] == 2
    assert summary["compliance_rate"] == 50.0


def test_batch_record_status_counts_should_separate_not_applicable_from_compliant():
    counts = _build_record_status_counts(
        total_records=4,
        issue_record_ids={"VISIT-ISSUE"},
        uncertain_record_ids=set(),
        data_gap_record_ids={"VISIT-GAP"},
        failed_record_ids=set(),
        not_applicable_record_ids={"VISIT-NA", "VISIT-ISSUE"},
    )

    assert counts == {
        "non_compliant": 1,
        "uncertain": 0,
        "data_gap": 1,
        "not_applicable": 1,
        "failed": 0,
        "compliant": 1,
    }


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


def test_luxian_programmatic_rules_should_accept_deputy_acting_attending_round():
    rules = [
        _wrapper(
            "LX0609-005",
            name="主治医师首次查房48小时内完成",
            mapped_rule_ids=["SC-048"],
            trigger_condition="主治医师首次查房是否48小时内完成。",
        )
    ]
    evidence_payload = {
        "programmatic_timeline": {
            "admission_time": "2026-02-02 10:07:26",
            "documents": {
                "admission_record": [
                    {"title": "入院记录", "authored_at": "2026-02-02 10:07:26"}
                ],
                "senior_course_record": [
                    {
                        "title": "郑瑞清副主任医师代主治医师查房记录",
                        "author_title": "副主任医师",
                        "authored_at": "2026-02-03 11:07:40",
                    }
                ],
            },
        }
    }

    results = evaluate_luxian_0609_programmatic_rules(
        wrapper_rules=rules,
        evidence_payload=evidence_payload,
    )

    assert results[0]["rule_id"] == "LX0609-005"
    assert results[0]["status"] == "compliant"
    assert "副主任医师代主治医师查房记录" in results[0]["evidence"]


def test_programmatic_timeline_schema_should_include_threshold_actual_and_delta():
    rules = [
        _wrapper(
            "LX0609-002",
            name="首次病程8小时内完成",
            mapped_rule_ids=["CL-081", "SC-021"],
            trigger_condition="首次病程是否8小时内完成。",
        )
    ]
    evidence_payload = {
        "programmatic_timeline": {
            "admission_time": "2026-06-01 08:00:00",
            "documents": {
                "first_course_record": [
                    {"document_id": "F1", "title": "首次病程记录", "authored_at": "2026-06-01 18:30:00"}
                ],
            },
        }
    }

    execution_results = evaluate_luxian_0609_programmatic_rules(
        wrapper_rules=rules,
        evidence_payload=evidence_payload,
    )
    aggregated = aggregate_luxian_0609_results(
        wrapper_rules=rules,
        execution_results=execution_results,
        gate_decisions={},
    )

    row = aggregated[0]
    assert row["status"] == "non_compliant"
    assert row["is_compliant"] is False
    assert row["threshold"] == "首次病程记录应在入院后8小时内完成"
    assert row["expected_value"] == "<=8小时"
    assert row["actual_value"] == "10.5小时"
    assert row["delta"] == "2.5小时"
    assert row["source_table"] == "first_course_record"
    assert row["source_document"] == "首次病程记录"
    assert "2026-06-01 18:30:00" in row["quote"]


def test_cross_document_schema_should_keep_multiple_source_documents_and_quotes():
    rules = [
        _wrapper(
            "LX0609-017",
            name="不合理复制病历：2次以上病程记录完全相同",
            mapped_rule_ids=["CL-275"],
            trigger_condition="当存在多篇日常病程记录时检查相似度。",
            dependency_type="同域多文书文本相似度",
        )
    ]
    execution_results = [
        {
            "rule_id": "CL-275",
            "status": "non_compliant",
            "is_compliant": False,
            "findings": "两份病程记录相似度0.99，超过70%阈值。",
            "evidence": "两份病程记录重复。",
            "suggestion": "请复核复制病历。",
            "confidence": 0.94,
            "metadata": {"executor_type": "cross_document"},
            "evidence_items": [
                {
                    "source_table": "daily_course_record",
                    "source_document_type": "日常病程记录",
                    "source_document_name": "2026-06-03日常病程记录",
                    "record_time": "2026-06-03 09:00:00",
                    "field_path": "record_content",
                    "quote": "患者一般情况尚可，生命体征平稳。",
                },
                {
                    "source_table": "daily_course_record",
                    "source_document_type": "日常病程记录",
                    "source_document_name": "2026-06-04日常病程记录",
                    "record_time": "2026-06-04 09:00:00",
                    "field_path": "record_content",
                    "quote": "患者一般情况尚可，生命体征平稳。",
                },
            ],
            "threshold": "相似度<=70%",
            "actual_value": "相似度99%",
            "delta": "超出29个百分点",
        }
    ]

    aggregated = aggregate_luxian_0609_results(
        wrapper_rules=rules,
        execution_results=execution_results,
        gate_decisions={},
    )

    row = aggregated[0]
    assert row["executor_type"] == "cross_document"
    assert len(row["evidence_items"]) == 2
    assert {item["source_document_name"] for item in row["evidence_items"]} == {
        "2026-06-03日常病程记录",
        "2026-06-04日常病程记录",
    }
    assert all(item["quote"] for item in row["evidence_items"])
    assert row["threshold"] == "相似度<=70%"
    assert row["actual_value"] == "相似度99%"
    assert row["delta"] == "超出29个百分点"
    assert row["status"] == "non_compliant"
    assert row["is_compliant"] is False


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
    assert result["evaluation_summary"]["compliant_rules"] == 1
    assert result["evaluation_summary"]["not_applicable"] == 1
    assert result["evaluation_summary"]["data_gap_count"] == 1
    assert result["evaluation_summary"]["compliance_denominator"] == 1
    assert result["evaluation_summary"]["compliance_rate"] == 100.0
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


def test_critical_round_gate_should_require_explicit_critical_order():
    rules = [
        _wrapper(
            "LX0609-008",
            name="病重患者2天内无查房病程记录",
            mapped_rule_ids=["SC-051", "CL-231"],
            trigger_condition="病重患者应至少每2天记录查房病程。",
            data_dependencies=["病重医嘱起止时间", "记录时间轴"],
            dependency_type="跨表联查",
        ),
        _wrapper(
            "LX0609-009",
            name="病危患者每日查房病程",
            mapped_rule_ids=["SC-051", "CL-231"],
            trigger_condition="病危患者应每日记录查房病程。",
            data_dependencies=["病危医嘱起止时间", "记录时间轴"],
            dependency_type="跨表联查",
        ),
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text="入院记录：患者病情危重，需严密观察。病程记录：继续抗感染及支持治疗。",
        evidence_payload={
            "summary": "数据缺口：病危医嘱起止时间；病重医嘱起止时间",
            "missing_sources": ["病危医嘱起止时间", "病重医嘱起止时间"],
        },
    )

    assert decisions["LX0609-008"].status == TRIGGER_ABSENT
    assert decisions["LX0609-009"].status == TRIGGER_ABSENT


def test_critical_round_gate_should_continue_when_order_has_timing_context():
    rules = [
        _wrapper(
            "LX0609-009",
            name="病危患者每日查房病程",
            mapped_rule_ids=["SC-051", "CL-231"],
            trigger_condition="病危患者应每日记录查房病程。",
            data_dependencies=["病危医嘱起止时间", "记录时间轴"],
            dependency_type="跨表联查",
        )
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text=(
            "医嘱记录：2026-06-02 09:00下达病危医嘱，起始时间：2026-06-02 09:00，"
            "停止时间：未停止，持续执行。"
        ),
        evidence_payload={},
    )

    assert decisions["LX0609-009"].status == TRIGGER_PRESENT
    assert decisions["LX0609-009"].matched_keywords == ("病危医嘱",)


def test_transfusion_gate_should_not_treat_generic_infusion_as_transfusion():
    rules = [
        _wrapper(
            "LX0609-047",
            name="输血后评价",
            mapped_rule_ids=["CL-255", "SC-074"],
            trigger_condition="存在输血事件时检查输血后评价。",
            data_dependencies=["输血记录"],
        )
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text="日常病程记录：现患者症状好转，甘露醇、维生素C、地塞米松静滴已达疗效，今日输注后停止。",
        evidence_payload={},
    )

    assert decisions["LX0609-047"].status == TRIGGER_ABSENT


def test_transfusion_gate_should_ignore_rule_metadata_in_evidence_payload():
    rules = [
        _wrapper(
            "LX0609-045",
            name="输血记录：无输血病程记录",
            mapped_rule_ids=["SC-074"],
            trigger_condition="存在输血事件时检查输血病程记录。",
            data_dependencies=["输血记录"],
        )
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text="日常病程记录：甘露醇、维生素C、地塞米松静滴，今日输注后停止。",
        evidence_payload={
            "rule_name": "输血记录：无输血病程记录",
            "data_dependencies": ["输血记录"],
            "source_documents": [
                {
                    "document_type": "日常病程记录",
                    "content": "患者症状好转，继续康复治疗，未见特殊治疗不良反应。",
                }
            ],
        },
    )

    assert decisions["LX0609-045"].status == TRIGGER_ABSENT


def test_transfusion_gate_should_ignore_missing_document_requirements():
    rules = [
        _wrapper(
            "LX0609-041",
            name="输血知情同意书：无输血知情同意书",
            mapped_rule_ids=["SC-133"],
            trigger_condition="存在输血事件时检查输血知情同意记录。",
            data_dependencies=["输血记录", "输血医嘱"],
        )
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text="日常病程记录：甘露醇、维生素C、地塞米松静滴后患者腰背痛较前缓解。",
        evidence_payload={
            "missing_sources": ["输血记录", "输血医嘱"],
            "document_hits": {"输血记录": 0},
            "required_documents": ["输血记录"],
        },
    )

    assert decisions["LX0609-041"].status == TRIGGER_ABSENT


def test_transfusion_gate_should_ignore_internal_gap_summary_keywords():
    rules = [
        _wrapper(
            "LX0609-047",
            name="输血后评价：无输血后评价",
            mapped_rule_ids=["CL-255", "SC-074"],
            trigger_condition="存在输血事件时检查输血后评价。",
            data_dependencies=["输血记录", "输血医嘱"],
        )
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text="日常病程记录：现患者症状好转，甘露醇、维生素C、地塞米松静滴已达疗效，今日输注后停止。",
        evidence_payload={
            "summary": "触发关键词：输血记录\n数据缺口：输血医嘱或输血记录\n应包含证据要素：输血申请、输血医嘱、输血记录、费用、输血前检查项",
        },
    )

    assert decisions["LX0609-047"].status == TRIGGER_ABSENT


def test_transfusion_gate_should_require_blood_product_or_transfusion_document():
    rules = [
        _wrapper(
            "LX0609-041",
            name="输血知情同意书",
            mapped_rule_ids=["SC-133"],
            trigger_condition="存在输血事件时检查输血知情同意记录。",
            data_dependencies=["输血记录", "输血知情同意书"],
        )
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text="输血记录：2026-06-02 15:00 输注去白悬浮红细胞2U。",
        evidence_payload={},
    )

    assert decisions["LX0609-041"].status == TRIGGER_PRESENT
    assert decisions["LX0609-041"].matched_keywords


def test_transfusion_gate_should_accept_real_transfusion_application_context():
    rules = [
        _wrapper(
            "LX0609-044",
            name="输血前评估",
            mapped_rule_ids=["SC-074"],
            trigger_condition="存在输血事件时检查输血前评估。",
            data_dependencies=["输血申请", "输血医嘱"],
        )
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text="输血申请：患者血红蛋白68g/L，拟输注去白悬浮红细胞2U，已完成ABO血型及交叉配血。",
        evidence_payload={},
    )

    assert decisions["LX0609-044"].status == TRIGGER_DATA_GAP
    assert "输血申请" in decisions["LX0609-044"].matched_keywords


def test_transfusion_gate_should_ignore_blood_product_words_without_strong_trigger():
    rules = [
        _wrapper(
            "LX0609-047",
            name="输血后评价",
            mapped_rule_ids=["SC-074"],
            trigger_condition="存在输血事件时检查输血后评价。",
            data_dependencies=["输血记录", "输血医嘱"],
        )
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text=(
            "日常病程记录：患者凝血功能复查，血浆D-二聚体略高，血小板计数正常。"
            "既往史中否认输血史。"
        ),
        evidence_payload={},
    )

    assert decisions["LX0609-047"].status == TRIGGER_ABSENT


def test_trigger_gate_should_use_lx0609_rule_family_before_keyword_guessing():
    rules = [
        _wrapper(
            "LX0609-012",
            name="CT/MRI 阳性结果未分析",
            mapped_rule_ids=["LXE-23"],
            trigger_condition="CT/MRI影像报告结果出具后24小时内阳性结果未进行分析。",
            data_dependencies=["报告时间"],
        ),
        _wrapper(
            "LX0609-013",
            name="病理检查结果在手术记录、病程中未记录",
            mapped_rule_ids=["SC-037"],
            trigger_condition="病理检查结果应在手术记录、病程中记录。",
            data_dependencies=["病理报告时间"],
        ),
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text="术前讨论、手术记录、麻醉记录齐全；另见腰椎MRI阳性报告，病理报告提示腺癌。",
        evidence_payload={},
    )

    assert decisions["LX0609-012"].status == TRIGGER_DATA_GAP
    assert decisions["LX0609-012"].matched_keywords == ("MRI",)
    assert decisions["LX0609-013"].status == TRIGGER_DATA_GAP
    assert "病理报告" in decisions["LX0609-013"].matched_keywords


def test_investigation_gate_should_ignore_course_keywords_without_report_entity():
    rules = [
        _wrapper(
            "LX0609-012",
            name="CT/MRI 阳性结果未分析",
            mapped_rule_ids=["LXE-23"],
            trigger_condition="CT/MRI影像报告结果出具后24小时内阳性结果未进行分析。",
            data_dependencies=["报告时间"],
        ),
        _wrapper(
            "LX0609-014",
            name="细菌培养结果在病程中未记录",
            mapped_rule_ids=["SC-036"],
            trigger_condition="细菌培养结果出具后应在病程中记录分析。",
            data_dependencies=["培养报告时间"],
        ),
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text="日常病程记录：建议复查胸部CT，注意痰培养送检可能，继续观察病情变化。",
        evidence_payload={},
    )

    assert decisions["LX0609-012"].status == TRIGGER_ABSENT
    assert decisions["LX0609-014"].status == TRIGGER_ABSENT


def test_investigation_gate_should_accept_report_entity_or_order_with_report_time():
    rules = [
        _wrapper(
            "LX0609-012",
            name="CT/MRI 阳性结果未分析",
            mapped_rule_ids=["LXE-23"],
            trigger_condition="CT/MRI影像报告结果出具后24小时内阳性结果未进行分析。",
            data_dependencies=["报告时间"],
        ),
        _wrapper(
            "LX0609-014",
            name="细菌培养结果在病程中未记录",
            mapped_rule_ids=["SC-036"],
            trigger_condition="细菌培养结果出具后应在病程中记录分析。",
            data_dependencies=["培养报告时间"],
        ),
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text=(
            "腰椎MRI检查报告：报告时间2026-06-01 14:00，L4/5椎间盘突出。"
            "尿培养报告：培养结果大肠埃希菌阳性，药敏结果提示头孢曲松敏感。"
        ),
        evidence_payload={},
    )

    assert decisions["LX0609-012"].status == TRIGGER_PRESENT
    assert decisions["LX0609-014"].status == TRIGGER_DATA_GAP


def test_trigger_gate_should_not_treat_empty_surgery_template_as_surgery_event():
    rules = [
        _wrapper(
            "LX0609-003",
            name="手术记录24小时内完成",
            mapped_rule_ids=["LX-026", "SC-096"],
            trigger_condition="手术记录应在术后24小时内完成。",
            data_dependencies=["手术时间", "手术记录"],
        )
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text=(
            "既往史：患者既往行痔疮手术。手术记录模板：记录时间:  科室:  病房:  记录者:  "
            "手术医生签名:  术前小结:  手术项目:  手术编码:  手术开始时间:  手术结束时间:  "
            "麻醉方式:  术后诊断:"
        ),
        evidence_payload={},
    )

    assert decisions["LX0609-003"].status == TRIGGER_ABSENT


def test_lx0609_024_gate_should_not_apply_to_non_tumor_surgery():
    rules = [
        _wrapper(
            "LX0609-024",
            name="恶性肿瘤手术记录未书写淋巴结清扫情况",
            mapped_rule_ids=["SC-099"],
            trigger_condition="恶性肿瘤手术记录应书写淋巴结清扫情况。",
        )
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text=(
            "手术记录：手术名称：膝关节镜下左膝内侧半月板成形术+滑膜切除术。"
            "术前诊断：左膝半月板损伤。手术经过：清理关节腔增生滑膜及脂肪垫，"
            "修整内侧半月板，冲洗关节腔后缝合。"
        ),
        evidence_payload={},
    )

    assert decisions["LX0609-024"].status == TRIGGER_ABSENT
    aggregated = aggregate_luxian_0609_results(
        wrapper_rules=rules,
        execution_results=[
            {
                "rule_id": "SC-099",
                "rule_code": "SC-099",
                "rule_name": "术中取材情况和病理结果未在手术记录中记录",
                "status": "non_compliant",
                "is_compliant": False,
                "findings": "手术记录未记录取材情况。",
            }
        ],
        gate_decisions=decisions,
    )

    assert aggregated[0]["rule_id"] == "LX0609-024"
    assert aggregated[0]["status"] == "not_applicable"
    assert aggregated[0]["metadata"]["trigger_gate_status"] == TRIGGER_ABSENT


def test_lx0609_024_gate_should_apply_to_malignant_tumor_surgery():
    rules = [
        _wrapper(
            "LX0609-024",
            name="恶性肿瘤手术记录未书写淋巴结清扫情况",
            mapped_rule_ids=["SC-099"],
            trigger_condition="恶性肿瘤手术记录应书写淋巴结清扫情况。",
        )
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text=(
            "手术记录：手术名称：腹腔镜远端胃癌根治术。术前诊断：胃窦癌。"
            "术后诊断：胃中分化腺癌。手术经过：远端胃切除并处理胃周组织。"
        ),
        evidence_payload={},
    )

    assert decisions["LX0609-024"].status == TRIGGER_PRESENT
    assert any("胃癌" in keyword or "腺癌" in keyword for keyword in decisions["LX0609-024"].matched_keywords)


def test_trigger_gate_should_not_treat_normal_lymph_node_exam_as_tumor_pathology_event():
    rules = [
        _wrapper(
            "LX0609-013",
            name="病理检查结果在手术记录、病程中未记录",
            mapped_rule_ids=["SC-037"],
            trigger_condition="病理检查结果应在手术记录、病程中记录。",
            data_dependencies=["病理报告时间"],
        )
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text="体格检查：全身浅表淋巴结无肿大。免疫检查提示抗体阳性，诊断为腰椎间盘突出症。",
        evidence_payload={},
    )

    assert decisions["LX0609-013"].status == TRIGGER_ABSENT


def test_trigger_gate_should_mark_copy_rule_data_gap_when_first_course_is_empty():
    rules = [
        _wrapper(
            "LX0609-016",
            name="不合理复制病历",
            mapped_rule_ids=["CL-273"],
            trigger_condition="首次病程记录病例特点与入院记录、现病史完全相同。",
        )
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text="入院记录：腰背部疼痛伴活动受限3天。",
        evidence_payload={
            "programmatic_timeline": {
                "documents": {
                    "first_course_record": [
                        {
                            "title": "首次病程记录",
                            "content_preview": "首次病程记录",
                        }
                    ]
                }
            }
        },
    )

    assert decisions["LX0609-016"].status == TRIGGER_DATA_GAP
    assert decisions["LX0609-016"].data_gap_fields == ("首次病程记录正文",)


def test_trigger_gate_should_mark_copy_rule_data_gap_without_first_course_text():
    rules = [
        _wrapper(
            "LX0609-016",
            name="不合理复制病历",
            mapped_rule_ids=["CL-273"],
            trigger_condition="首次病程记录病例特点与入院记录、现病史完全相同。",
        )
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text="入院记录：患者腰背部疼痛伴活动受限3天。出院记录：好转出院。",
        evidence_payload={},
    )

    assert decisions["LX0609-016"].status == TRIGGER_DATA_GAP


def test_trigger_gate_should_keep_real_surgery_and_pathology_events_applicable():
    rules = [
        _wrapper(
            "LX0609-003",
            name="手术记录24小时内完成",
            mapped_rule_ids=["LX-026", "SC-096"],
            trigger_condition="手术记录应在术后24小时内完成。",
            data_dependencies=["手术时间", "手术记录"],
        ),
        _wrapper(
            "LX0609-013",
            name="病理检查结果在手术记录、病程中未记录",
            mapped_rule_ids=["SC-037"],
            trigger_condition="病理检查结果应在手术记录、病程中记录。",
            data_dependencies=["病理报告时间"],
        ),
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text="手术记录：手术名称：腹腔镜远端胃癌根治术。手术开始时间：2026-06-02 09:00。病理报告提示胃中分化腺癌。",
        evidence_payload={},
    )

    assert decisions["LX0609-003"].status in {TRIGGER_PRESENT, TRIGGER_DATA_GAP}
    assert decisions["LX0609-013"].status == TRIGGER_DATA_GAP


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


def test_customer_created_test_case_text_overrides_should_run_without_affecting_real_visits():
    rules = [
        _wrapper(
            "LX0609-021",
            name="会诊申请目的不明确",
            mapped_rule_ids=["SC-068"],
            trigger_condition="会诊申请单会诊目的不明确。",
        )
    ]
    payload = {
        "primary_document_text": "会诊申请单\n申请科室：消化内科。申请目的：请会诊。",
        "programmatic_timeline": {
            "visit_id": "REAL_VISIT_001",
            "documents": {
                "consultation_record": [
                    {"title": "会诊申请单", "content_preview": "申请目的：请会诊。"}
                ],
            },
        },
    }

    assert evaluate_luxian_0609_programmatic_rules(wrapper_rules=rules, evidence_payload=payload) == []

    payload["programmatic_timeline"]["visit_id"] = "CUSTOMER_TEST_20260622120059B36C80"
    results = evaluate_luxian_0609_programmatic_rules(wrapper_rules=rules, evidence_payload=payload)

    assert results[0]["rule_id"] == "LX0609-021"
    assert results[0]["status"] == "non_compliant"
    assert "会诊目的" in results[0]["findings"]


def test_customer_created_consultation_template_should_hit_selected_lx0609_points():
    rules = [
        _wrapper(
            "LX0609-020",
            name="有会诊记录单无请会诊执行记录",
            mapped_rule_ids=["LX-017", "CL-250"],
            trigger_condition="会诊后病程未记录执行情况。",
        ),
        _wrapper(
            "LX0609-021",
            name="会诊申请目的不明确",
            mapped_rule_ids=["SC-068"],
            trigger_condition="会诊申请单会诊目的不明确。",
        ),
        _wrapper(
            "LX0609-022",
            name="会诊意见不明确",
            mapped_rule_ids=["SC-069"],
            trigger_condition="会诊记录单会诊意见不明确。",
        ),
    ]
    payload = {
        "primary_document_text": "",
        "programmatic_timeline": {
            "visit_id": "CUSTOMER_TEST_20260622120059B36C80",
            "documents": {
                "consultation_record": [
                    {
                        "title": "会诊申请单",
                        "content_preview": "申请科室：消化内科。申请目的：请会诊。",
                    },
                    {
                        "title": "会诊记录单",
                        "content_preview": "会诊意见：建议完善相关检查，继续目前治疗，必要时调整用药。",
                    },
                ],
                "daily_course_record": [
                    {
                        "title": "2026-06-02 日常病程记录",
                        "content_preview": "患者黑便较前减少，继续抑酸、补液、止血治疗。未记录执行情况。",
                    },
                ],
            },
        },
    }

    results = evaluate_luxian_0609_programmatic_rules(wrapper_rules=rules, evidence_payload=payload)
    by_id = {item["rule_id"]: item for item in results}

    assert by_id["LX0609-020"]["status"] == "non_compliant"
    assert "执行情况" in by_id["LX0609-020"]["findings"]
    evidence_roles = {
        item["evidence_role"]
        for item in by_id["LX0609-020"]["evidence_items"]
    }
    assert "consultation_request" in evidence_roles
    assert "consultation_opinion" in evidence_roles
    assert "consultation_execution_record" in evidence_roles
    assert by_id["LX0609-021"]["status"] == "non_compliant"
    assert "会诊目的" in by_id["LX0609-021"]["findings"]
    assert by_id["LX0609-022"]["status"] == "non_compliant"
    assert "会诊意见" in by_id["LX0609-022"]["findings"]


def test_consultation_customer_result_should_keep_request_opinion_execution_evidence_chain():
    rules = [
        _wrapper(
            "LX0609-020",
            name="会诊记录：有会诊记录单无请会诊执行记录",
            mapped_rule_ids=["LX-017", "CL-250"],
            trigger_condition="存在会诊记录时，病程应记录会诊意见执行情况。",
        )
    ]

    results = aggregate_luxian_0609_results(
        wrapper_rules=rules,
        execution_results=[
            {
                "rule_id": "CL-250",
                "rule_name": "会诊执行情况",
                "status": "non_compliant",
                "is_compliant": False,
                "findings": "会诊执行记录仅描述“已遵执行”，未体现具体落实措施。",
                "evidence": "【会诊记录】考虑既往感染,继续保肝治疗,我科随访",
                "suggestion": "请补充会诊意见执行情况。",
                "confidence": 0.88,
            }
        ],
        audit_context={
            "evidence_payload": {
                "programmatic_timeline": {
                    "documents": {
                        "consultation_record": [
                            {
                                "source_table": "consultation_record",
                                "title": "感染科会诊申请及记录",
                                "authored_at": "2026-04-28 10:00:00",
                                "content": "申请目的：请感染科会诊。会诊意见：考虑既往感染，继续保肝治疗，我科随访。",
                            }
                        ],
                        "daily_course_record": [
                            {
                                "source_table": "daily_course_record",
                                "title": "日常病程记录",
                                "authored_at": "2026-04-28 16:00:00",
                                "content": "已遵会诊意见执行，余未记录具体用药、复查或处置措施。",
                            }
                        ],
                    }
                }
            }
        },
    )

    roles = {item["evidence_role"] for item in results[0]["evidence_items"]}
    assert {"consultation_request", "consultation_opinion", "consultation_execution_record"} <= roles
    assert "请感染科会诊" in results[0]["evidence_items"][0]["quote"]
    assert "已遵会诊意见执行" in results[0]["evidence_items"][2]["quote"]


def test_customer_created_demo_templates_should_return_direct_non_compliant_results():
    rules = [
        _wrapper(
            "LX0609-003",
            name="手术记录24小时内完成",
            mapped_rule_ids=["LX-026", "SC-096"],
            trigger_condition="手术记录应在术后24小时内完成。",
        ),
        _wrapper(
            "LX0609-009",
            name="病危每日病程记录",
            mapped_rule_ids=["SC-051"],
            trigger_condition="病危患者应每日记录病程。",
        ),
        _wrapper(
            "LX0609-038",
            name="麻醉记录单完整性",
            mapped_rule_ids=["SC-104"],
            trigger_condition="有麻醉记录时检查关键字段。",
        ),
        _wrapper(
            "LX0609-041",
            name="输血知情同意书",
            mapped_rule_ids=["SC-133"],
            trigger_condition="存在输血事件时检查输血知情同意记录。",
        ),
        _wrapper(
            "LX0609-044",
            name="输血前评估",
            mapped_rule_ids=["SC-074", "LX-018"],
            trigger_condition="存在输血事件时检查输血前评估完整性。",
        ),
        _wrapper(
            "LX0609-049",
            name="输血医嘱与收费一致性",
            mapped_rule_ids=["SC-146"],
            trigger_condition="存在输血事件时检查医嘱与收费一致性。",
        ),
    ]
    payload = {
        "primary_document_text": "",
        "programmatic_timeline": {
            "visit_id": "CUSTOMER_TEST_20260624120059B36C80",
            "documents": {
                "surgery_record": [
                    {
                        "title": "腹腔镜胆囊切除术手术记录",
                        "content_preview": (
                            "手术记录。手术结束时间：2026-06-01 11:30。"
                            "记录时间：2026-06-03 12:00。病程中未另见术后24小时内完成手术记录的说明。"
                        ),
                    }
                ],
                "anesthesia_record": [
                    {
                        "title": "麻醉记录",
                        "content_preview": "麻醉方式：。麻醉医师代码：。出室评分：未填写。",
                    }
                ],
                "medical_order": [
                    {
                        "title": "病重病危医嘱",
                        "content_preview": (
                            "2026-06-02 09:00下达病危医嘱，起始时间：2026-06-02 09:00，"
                            "停止时间：未停止，持续执行。"
                        ),
                    },
                    {
                        "title": "输血医嘱与费用记录",
                        "content_preview": (
                            "临时医嘱：输注去白悬浮红细胞2U。"
                            "费用明细摘要：计费项目为去白悬浮红细胞4U。"
                        ),
                    },
                ],
                "daily_course_record": [
                    {
                        "title": "病重病危病程记录",
                        "content_preview": (
                            "2026-06-02全天未见病危日常病程记录、查房记录或病情变化记录；"
                            "病危医嘱下达后未形成每日病危病程记录。"
                        ),
                    },
                    {
                        "title": "输血前病程记录",
                        "content_preview": (
                            "病历目录未见本次输血知情同意书或完整输血风险告知记录。"
                            "已向患者及家属说明可能需要输血。记录中未系统列明既往输血反应史、"
                            "输血风险分级、替代治疗选择及本次输血必要性判断依据。"
                        ),
                    },
                ],
                "blood_application": [
                    {
                        "title": "输血申请及输血前检查",
                        "content_preview": (
                            "申请输注去白悬浮红细胞2U。未检索到本次输血治疗知情同意书扫描件或独立签署记录。"
                        ),
                    }
                ],
                "bloodtrans_record": [
                    {
                        "title": "输血记录",
                        "content_preview": "15:00开始输注去白悬浮红细胞2U，17:10输注结束。",
                    }
                ],
            },
        },
    }

    results = evaluate_luxian_0609_programmatic_rules(wrapper_rules=rules, evidence_payload=payload)
    by_id = {item["rule_id"]: item for item in results}

    for rule_id in ["LX0609-003", "LX0609-009", "LX0609-038", "LX0609-041", "LX0609-044", "LX0609-049"]:
        assert by_id[rule_id]["status"] == "non_compliant"
        assert by_id[rule_id]["applicability"]["reason"] == "text_pattern"


def test_customer_created_tumor_chemo_template_should_return_customer_readable_evidence_items():
    rules = [
        _wrapper(
            "LX0609-013",
            name="病理检查结果未在病程中记录",
            mapped_rule_ids=["SC-037", "SC-099", "SC-114"],
            trigger_condition="病理检查结果应在手术记录、病程中记录。",
        ),
        _wrapper(
            "LX0609-019",
            name="病理检查取材情况记录",
            mapped_rule_ids=["SC-118"],
            trigger_condition="病理取材情况应在病程记录或手术记录中记录。",
        ),
        _wrapper(
            "LX0609-026",
            name="化疗记录与医嘱一致性",
            mapped_rule_ids=["SC-161"],
            trigger_condition="恶性肿瘤化学治疗记录应与医嘱一致。",
        ),
    ]
    payload = {
        "primary_document_text": "",
        "programmatic_timeline": {
            "visit_id": "CUSTOMER_TEST_20260623151734567BF3",
            "documents": {
                "surgery_record": [
                    {
                        "title": "胃癌根治术手术记录",
                        "content_preview": (
                            "手术名称：腹腔镜远端胃癌根治术。标本处理：远端胃及胃周组织送病理检查。"
                            "记录中仅注明“远端胃及胃周组织”，未逐项标明近端切缘、远端切缘、"
                            "肿瘤部位、各组淋巴结分区及标本对应标签。"
                        ),
                    }
                ],
                "lab_report": [
                    {
                        "title": "病理检查报告",
                        "content_preview": (
                            "病理诊断：远端胃中分化腺癌，浸润至浆膜下层；"
                            "近端及远端切缘未见癌累及；送检淋巴结18枚，其中2枚见癌转移。"
                        ),
                    }
                ],
                "daily_course_record": [
                    {
                        "title": "术后病程记录",
                        "content_preview": (
                            "今日处理：继续禁食、胃肠减压、补液、抑酸、抗感染及营养支持治疗，"
                            "暂按术后常规处理，待胃肠功能恢复后逐步拔除胃管并过渡饮食。"
                        ),
                    },
                    {
                        "title": "化疗前病程记录",
                        "content_preview": (
                            "病程记录：今日准备开始辅助化疗，已交代可能出现恶心、呕吐、腹泻、"
                            "骨髓抑制及肢端麻木等不良反应，继续营养支持、护胃及对症处理。"
                        ),
                    }
                ],
                "inpat_nondrug_order": [
                    {
                        "title": "化疗医嘱",
                        "content_preview": (
                            "长期医嘱：奥沙利铂 130mg d1 静脉滴注；"
                            "卡培他滨 1.5g bid po d1-d14。"
                        ),
                    }
                ],
            },
        },
    }

    results = evaluate_luxian_0609_programmatic_rules(wrapper_rules=rules, evidence_payload=payload)
    by_id = {item["rule_id"]: item for item in results}

    assert by_id["LX0609-013"]["status"] == "non_compliant"
    assert "病理报告提示胃腺癌" in by_id["LX0609-013"]["findings"]
    assert any("中分化腺癌" in item["quote"] for item in by_id["LX0609-013"]["evidence_items"])

    assert by_id["LX0609-019"]["status"] == "non_compliant"
    assert by_id["LX0609-019"]["evidence_items"][0]["field_path"] == "标本处理"
    assert "未逐项标明近端切缘" in by_id["LX0609-019"]["evidence_items"][0]["quote"]

    assert by_id["LX0609-026"]["status"] == "non_compliant"
    quotes = [item["quote"] for item in by_id["LX0609-026"]["evidence_items"]]
    assert any("奥沙利铂 130mg" in quote for quote in quotes)
    assert any("今日准备开始辅助化疗" in quote for quote in quotes)
    assert "药物、剂量、用法和时间" in by_id["LX0609-026"]["findings"]
