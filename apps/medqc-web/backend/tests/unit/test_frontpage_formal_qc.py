"""
病案首页形式质控引擎 — 单元测试

TDD RED 阶段：测试先行
基于 settlementQC.ts 的 126 条规则，适配为后端 Python 版
"""
import pytest
from app.services.frontpage_formal_qc import (
    FrontpageFormalQC,
    QCRule,
    QCReport,
    Severity,
    Category,
)


# ============================================================
# Fixtures
# ============================================================

def _make_frontpage(**overrides) -> dict:
    """构造一份最简合法首页数据（所有必填字段有值）。"""
    base = {
        "patient_name": "张三",
        "sex": "男",
        "age": 45,
        "age_in_days": None,
        "id_card": "510521198001011234",
        "nationality": "中国",
        "ethnicity": "汉族",
        "occupation": "工人",
        "marital_status": "已婚",
        "admission_datetime": "2025-12-01 10:00:00",
        "discharge_datetime": "2025-12-10 09:00:00",
        "los_days": 9,
        "admission_dept": "心内科",
        "discharge_dept": "心内科",
        "admission_route": 1,  # 1=急诊
        "discharge_method": 1,  # 1=医嘱离院
        "attending_physician": "李医生",
        "diagnoses": [
            {
                "diagnosis_name": "急性心肌梗死",
                "diagnosis_code": "I21.0",
                "diagnosis_type": "主诊断",
                "admission_condition": "1",  # 1=有明确诊断
            }
        ],
        "surgeries": [],
        "newborn_birth_weight": None,
        "newborn_admission_weight": None,
    }
    base.update(overrides)
    return base


# ============================================================
# 1. 引擎基本功能
# ============================================================

class TestEngineBasics:
    """引擎创建和报告基本结构。"""

    def test_engine_creates_with_rules(self):
        engine = FrontpageFormalQC()
        assert len(engine.rules) > 0, "引擎应包含至少一条规则"

    def test_validate_returns_report(self):
        engine = FrontpageFormalQC()
        fp = _make_frontpage()
        report = engine.validate(fp)
        assert isinstance(report, QCReport)
        assert hasattr(report, "total_rules")
        assert hasattr(report, "passed")
        assert hasattr(report, "failed")
        assert hasattr(report, "results")

    def test_rule_exception_does_not_become_passed_result(self):
        engine = FrontpageFormalQC()

        def fail_rule(_frontpage):
            raise RuntimeError("rule unavailable")

        engine.rules = [QCRule(
            rule_id="FQ-EXCEPTION",
            field_name="patient_name",
            rule_name="测试异常规则",
            description="测试异常不得伪装通过",
            severity=Severity.ERROR,
            category=Category.REQUIRED,
            validate=fail_rule,
            message=lambda _frontpage: "缺少患者姓名",
        )]

        with pytest.raises(RuntimeError, match="rule unavailable"):
            engine.validate(_make_frontpage())

    def test_legacy_main_diagnosis_object_executes_rules(self):
        engine = FrontpageFormalQC()
        report = engine.validate({
            "patient_name": "张三",
            "diagnoses": {
                "discharge_main_diagnosis_text": "肺炎",
                "discharge_main_icd": "J18.9",
            },
        })
        assert report.total_rules == len(engine.rules)

    def test_unknown_diagnosis_object_does_not_pass_silently(self):
        with pytest.raises(ValueError, match="诊断数据必须是列表"):
            FrontpageFormalQC().validate({"diagnoses": {"unknown": "value"}})

    def test_valid_frontpage_passes_all(self):
        """一份合法首页应该通过绝大多数规则（至少通过必填类规则）。"""
        engine = FrontpageFormalQC()
        fp = _make_frontpage()
        report = engine.validate(fp)
        required_failures = [
            r for r in report.results
            if not r.passed and r.category == Category.REQUIRED
            and r.severity == Severity.ERROR
        ]
        assert len(required_failures) == 0, (
            f"合法首页不应有强制必填类失败: "
            f"{[r.rule_id for r in required_failures]}"
        )


# ============================================================
# 2. 必填校验 (required)
# ============================================================

class TestRequiredRules:
    """必填字段为空时应报错。"""

    def test_missing_patient_name(self):
        engine = FrontpageFormalQC()
        fp = _make_frontpage(patient_name="")
        report = engine.validate(fp)
        failed_ids = [r.rule_id for r in report.results if not r.passed]
        assert any("name" in rid.lower() or "FQ" in rid for rid in failed_ids), \
            "患者姓名为空应触发必填规则"

    def test_missing_admission_datetime(self):
        engine = FrontpageFormalQC()
        fp = _make_frontpage(admission_datetime="")
        report = engine.validate(fp)
        failed_ids = [r.rule_id for r in report.results if not r.passed]
        assert any("admission" in rid.lower() or "FQ" in rid for rid in failed_ids), \
            "入院时间为空应触发必填规则"

    def test_missing_discharge_datetime(self):
        engine = FrontpageFormalQC()
        fp = _make_frontpage(discharge_datetime="")
        report = engine.validate(fp)
        failed_ids = [r.rule_id for r in report.results if not r.passed]
        assert any("discharge" in rid.lower() or "FQ" in rid for rid in failed_ids), \
            "出院时间为空应触发必填规则"

    def test_missing_primary_diagnosis(self):
        engine = FrontpageFormalQC()
        fp = _make_frontpage(diagnoses=[])
        report = engine.validate(fp)
        failed_ids = [r.rule_id for r in report.results if not r.passed]
        assert len(failed_ids) > 0, "无诊断应触发必填规则"


# ============================================================
# 3. 格式校验 (format)
# ============================================================

class TestFormatRules:
    """格式错误应被检出。"""

    def test_invalid_icd10_code(self):
        engine = FrontpageFormalQC()
        fp = _make_frontpage(diagnoses=[{
            "diagnosis_name": "测试",
            "diagnosis_code": "INVALID",
            "diagnosis_type": "主诊断",
            "admission_condition": "1",
        }])
        report = engine.validate(fp)
        failed = [r for r in report.results if not r.passed and r.category == Category.FORMAT]
        assert len(failed) > 0, "非法 ICD-10 编码应触发格式校验"

    def test_valid_icd10_code(self):
        engine = FrontpageFormalQC()
        fp = _make_frontpage()  # I21.0 是合法的
        report = engine.validate(fp)
        format_failures = [
            r for r in report.results
            if not r.passed and r.category == Category.FORMAT
            and "编码" in r.message
        ]
        assert len(format_failures) == 0, "合法 ICD-10 编码不应触发格式校验"

    def test_invalid_id_card(self):
        engine = FrontpageFormalQC()
        fp = _make_frontpage(id_card="12345")
        report = engine.validate(fp)
        failed = [r for r in report.results if not r.passed and "身份证" in r.message]
        assert len(failed) > 0, "非法身份证号应触发格式校验"

    def test_invalid_discharge_method(self):
        engine = FrontpageFormalQC()
        fp = _make_frontpage(discharge_method=99)
        report = engine.validate(fp)
        failed = [r for r in report.results if not r.passed and "离院" in r.message]
        assert len(failed) > 0, "非法离院方式应触发格式校验"


# ============================================================
# 4. 逻辑一致性 (consistency)
# ============================================================

class TestConsistencyRules:
    """逻辑矛盾应被检出。"""

    def test_admission_after_discharge(self):
        engine = FrontpageFormalQC()
        fp = _make_frontpage(
            admission_datetime="2025-12-15 10:00:00",
            discharge_datetime="2025-12-10 09:00:00",
        )
        report = engine.validate(fp)
        failed = [
            r for r in report.results
            if not r.passed and r.category == Category.CONSISTENCY
        ]
        assert len(failed) > 0, "入院时间晚于出院时间应触发逻辑校验"

    def test_male_with_obstetric_diagnosis(self):
        """男性患者不应有妇产科诊断（O 开头）。"""
        engine = FrontpageFormalQC()
        fp = _make_frontpage(
            sex="男",
            diagnoses=[{
                "diagnosis_name": "分娩",
                "diagnosis_code": "O80.0",
                "diagnosis_type": "主诊断",
                "admission_condition": "1",
            }]
        )
        report = engine.validate(fp)
        failed = [r for r in report.results if not r.passed and "性别" in r.message]
        assert len(failed) > 0, "男性患者有妇产科诊断应触发性别校验"

    def test_duplicate_diagnosis_codes(self):
        """诊断编码不应重复。"""
        engine = FrontpageFormalQC()
        fp = _make_frontpage(diagnoses=[
            {"diagnosis_name": "心梗", "diagnosis_code": "I21.0",
             "diagnosis_type": "主诊断", "admission_condition": "1"},
            {"diagnosis_name": "心梗2", "diagnosis_code": "I21.0",
             "diagnosis_type": "次诊断", "admission_condition": "1"},
        ])
        report = engine.validate(fp)
        failed = [r for r in report.results if not r.passed and "重复" in r.message]
        assert len(failed) > 0, "重复诊断编码应触发校验"

    def test_los_days_mismatch(self):
        """住院天数应 = 出院日期 - 入院日期。"""
        engine = FrontpageFormalQC()
        fp = _make_frontpage(los_days=100)  # 实际为 9 天
        report = engine.validate(fp)
        failed = [r for r in report.results if not r.passed and "住院天数" in r.message]
        assert len(failed) > 0, "住院天数与日期不一致应触发校验"


# ============================================================
# 5. 规则过滤
# ============================================================

class TestRuleFiltering:
    """引擎应支持按类别过滤执行。"""

    def test_run_only_required(self):
        engine = FrontpageFormalQC()
        fp = _make_frontpage()
        report = engine.validate(fp, categories=[Category.REQUIRED])
        for r in report.results:
            assert r.category == Category.REQUIRED

    def test_run_only_errors(self):
        engine = FrontpageFormalQC()
        fp = _make_frontpage()
        report = engine.validate(fp, severities=[Severity.ERROR])
        for r in report.results:
            assert r.severity == Severity.ERROR

    def test_get_stats(self):
        engine = FrontpageFormalQC()
        stats = engine.get_stats()
        assert "total" in stats
        assert "by_category" in stats
        assert "by_severity" in stats
        assert stats["total"] >= 80, \
            f"PRD 要求 ≥80 条规则，实际 {stats['total']} 条"
