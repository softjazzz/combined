"""
主诊断规则裁决单元测试

测试用例覆盖：
1. 冠心病 + 支架植入 → 主诊断应与手术一致
2. 术后状态不应作为主诊断
3. 无需更换时保持不变
"""

import pytest
from app.services.main_diagnosis_rules import (
    apply_main_diagnosis_guideline_rules,
    _compute_procedure_alignment,
    _compute_resource_burden,
    _canonical_key,
)


class TestCanonicalKey:
    def test_strips_punctuation(self):
        assert _canonical_key("冠心病（冠状动脉粥样硬化性心脏病）") == "冠心病冠状动脉粥样硬化性心脏病"

    def test_lowercase(self):
        assert _canonical_key("PCI术后") == "pci术后"

    def test_empty(self):
        assert _canonical_key("") == ""
        assert _canonical_key(None) == ""


class TestProcedureAlignment:
    def test_stent_coronary(self):
        """支架植入 vs 冠状动脉粥样硬化性心脏病 → 1.0"""
        score = _compute_procedure_alignment(
            "冠状动脉粥样硬化性心脏病",
            "经皮冠状动脉支架植入术"
        )
        assert score == 1.0

    def test_stent_angina(self):
        """支架植入 vs 不稳定型心绞痛 → 1.0"""
        score = _compute_procedure_alignment(
            "不稳定型心绞痛",
            "经皮冠状动脉支架植入术"
        )
        assert score == 1.0

    def test_stent_hypertension(self):
        """支架植入 vs 高血压 → 0.0"""
        score = _compute_procedure_alignment(
            "高血压病3级",
            "经皮冠状动脉支架植入术"
        )
        assert score == 0.0

    def test_stent_diabetes(self):
        """支架植入 vs 糖尿病 → 0.0"""
        score = _compute_procedure_alignment(
            "2型糖尿病",
            "经皮冠状动脉支架植入术"
        )
        assert score == 0.0

    def test_no_procedure(self):
        """无手术 → 0.0"""
        assert _compute_procedure_alignment("冠心病", "") == 0.0

    def test_cholecystectomy(self):
        """胆囊切除 vs 胆囊炎 → 1.0"""
        score = _compute_procedure_alignment(
            "急性胆囊炎",
            "腹腔镜胆囊切除术"
        )
        assert score == 1.0


class TestResourceBurden:
    def test_with_treatment_lines(self):
        lines = [
            "入院后完善相关检查",
            "冠心病 急性心肌梗死 行急诊PCI术",
            "术后给予抗血小板治疗",
            "高血压 继续口服降压药",
        ]
        # 冠心病有 PCI/手术 关联 → 有资源消耗证据
        score_chd = _compute_resource_burden("冠心病", lines)
        score_htn = _compute_resource_burden("高血压", lines)
        assert score_chd > score_htn


class TestApplyRules:
    """验收用例"""

    def test_case1_stent_with_hypertension_diabetes(self):
        """
        用例：冠心病+高血压+糖尿病，主手术=支架植入
        LLM 错误地把高血压选为主诊断
        期望：规则裁决将主诊断更换为冠心病
        """
        medical_text = """
出院诊断：
1. 高血压病3级（极高危组）
2. 冠状动脉粥样硬化性心脏病
3. 不稳定型心绞痛
4. 2型糖尿病

病程记录：
患者因胸痛入院，行冠状动脉造影示前降支狭窄95%，于1月10日行经皮冠状动脉支架植入术。
术后给予双联抗血小板治疗，恢复良好。
高血压继续口服降压药控制。
糖尿病继续使用胰岛素。
        """
        diagnoses = {
            "discharge_main_diagnosis_text": "高血压病3级（极高危组）",
            "discharge_other_diagnoses_texts": [
                "冠状动脉粥样硬化性心脏病",
                "不稳定型心绞痛",
                "2型糖尿病",
            ],
            "discharge_main_icd": "I10.x02",
            "discharge_other_icds": ["I25.103", "I20.000", "E11.900"],
        }
        procedures = {
            "main_procedure_text": "经皮冠状动脉药物洗脱支架植入术",
        }

        result, trace = apply_main_diagnosis_guideline_rules(
            medical_text, diagnoses, procedures
        )

        # 主诊断应该被更换为冠心病/心绞痛相关（都与支架一致）
        new_main = result["discharge_main_diagnosis_text"]
        assert any(k in new_main for k in ["冠状动脉", "冠心病", "心绞痛"]), (
            f"主诊断应为冠心病/心绞痛相关，实际为: {new_main}"
        )
        # 高血压应该在其他诊断中
        assert "高血压" in str(result["discharge_other_diagnoses_texts"])
        # trace 应有 replaced 动作
        actions = [t.get("action") for t in trace if "action" in t]
        assert "replaced" in actions, f"应有替换动作，trace={trace}"

    def test_case2_status_not_main(self):
        """
        用例：术后状态不应作为主诊断
        """
        diagnoses = {
            "discharge_main_diagnosis_text": "冠状动脉支架植入后状态",
            "discharge_other_diagnoses_texts": [
                "冠状动脉粥样硬化性心脏病",
                "高血压病",
            ],
            "discharge_main_icd": None,
            "discharge_other_icds": [None, None],
        }
        procedures = {
            "main_procedure_text": "冠状动脉造影术",
        }

        result, trace = apply_main_diagnosis_guideline_rules(
            "术后复查，行冠状动脉造影，予调整用药。",
            diagnoses,
            procedures,
        )

        new_main = result["discharge_main_diagnosis_text"]
        # 术后状态应被降权
        assert "后状态" not in new_main, f"术后状态不应为主诊断，实际: {new_main}"

    def test_case3_no_change_needed(self):
        """
        用例：LLM 已正确选主诊断，无需更换
        """
        diagnoses = {
            "discharge_main_diagnosis_text": "急性阑尾炎",
            "discharge_other_diagnoses_texts": ["高血压病"],
            "discharge_main_icd": "K35.900",
            "discharge_other_icds": ["I10.x00"],
        }
        procedures = {
            "main_procedure_text": "腹腔镜阑尾切除术",
        }

        result, trace = apply_main_diagnosis_guideline_rules(
            "患者因右下腹痛入院，急诊行腹腔镜阑尾切除术。",
            diagnoses,
            procedures,
        )

        assert result["discharge_main_diagnosis_text"] == "急性阑尾炎"
        actions = [t.get("action") for t in trace if "action" in t]
        assert "kept" in actions
