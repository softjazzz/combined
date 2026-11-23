"""
病案首页形式质控引擎

功能：对病案首页进行字段级的完整性、规范性审核。
规则来源：基于 settlementQC.ts 的 126 条四川省医保结算清单质控规则，
         适配为病案首页字段结构。

分类：
  - required: 必填项检查
  - format:   格式校验（ICD编码、身份证、日期等）
  - logic:    值域/逻辑校验
  - consistency: 跨字段一致性校验
"""
import math
import re
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


# ============================================================
# 枚举和数据类
# ============================================================

class Severity(str, Enum):
    ERROR = "error"       # 强制/严重
    WARNING = "warning"   # 提示
    INFO = "info"         # 信息


class Category(str, Enum):
    REQUIRED = "required"         # 必填
    FORMAT = "format"             # 格式
    LOGIC = "logic"               # 值域/逻辑
    CONSISTENCY = "consistency"   # 一致性


@dataclass
class QCRule:
    """单条质控规则定义。"""
    rule_id: str
    field_name: str
    rule_name: str
    description: str
    severity: Severity
    category: Category
    validate: Callable[[dict], bool]
    message: Callable[[dict], str]


@dataclass
class QCResult:
    """单条规则的校验结果。"""
    rule_id: str
    field_name: str
    rule_name: str
    passed: bool
    message: str
    severity: Severity
    category: Category


@dataclass
class QCReport:
    """质控校验报告。"""
    total_rules: int
    passed: int
    failed: int
    results: List[QCResult] = field(default_factory=list)


# ============================================================
# 辅助函数
# ============================================================

def _not_empty(value: Any) -> bool:
    """检查字段非空。"""
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    return True


def _to_float(value: Any) -> Optional[float]:
    """安全转为有限浮点数（排除 bool、NaN、inf）。"""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        num = float(value)
    except (ValueError, TypeError):
        return None
    return num if math.isfinite(num) else None


def _to_int_code(value: Any) -> Optional[int]:
    """将数字或数字字符串安全转为整数编码（如 '1' -> 1, 1 -> 1）。"""
    num = _to_float(value)
    if num is None or not num.is_integer():
        return None
    return int(num)


def _valid_number(value: Any) -> bool:
    """检查合法有限数字。"""
    return _to_float(value) is not None


def _valid_icd10(code: str) -> bool:
    """校验 ICD-10 编码格式 (A00-Z99.xxx)。"""
    if not code:
        return False
    return bool(re.match(r'^[A-UZ]\d{2}(\.\d{1,4})?$', code.strip(), re.IGNORECASE))


def _valid_icd9cm3(code: str) -> bool:
    """校验 ICD-9-CM-3 手术编码格式。"""
    if not code:
        return False
    return bool(re.match(r'^\d{2}\.\d{2,4}$', code.strip()))


def _valid_id_card(id_card: str) -> bool:
    """校验 18 位身份证号码格式。"""
    if not id_card:
        return False
    return bool(re.match(
        r'^[1-9]\d{5}(19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[\dXx]$',
        id_card.strip()
    ))


def _parse_datetime(s: Any) -> Optional[datetime]:
    """解析日期时间字符串。"""
    if not s or not isinstance(s, str) or not s.strip():
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            continue
    return None


def _get_diagnoses(fp: dict) -> list:
    """获取诊断列表。"""
    return fp.get("diagnoses") or []


def _get_primary_diagnosis(fp: dict) -> Optional[dict]:
    """获取主诊断。"""
    diags = _get_diagnoses(fp)
    return diags[0] if diags else None


def _get_surgeries(fp: dict) -> list:
    """获取手术列表。"""
    return fp.get("surgeries") or []


def _get_sex_code(fp: dict) -> Optional[int]:
    """性别转数字 (1=男, 2=女)。"""
    sex = fp.get("sex")
    if isinstance(sex, str):
        sex = sex.strip()
    if sex in ("男", 1, "1"):
        return 1
    if sex in ("女", 2, "2"):
        return 2
    return None


# ============================================================
# 规则定义
# ============================================================

def _build_rules() -> List[QCRule]:
    """构建全部形式质控规则。"""
    rules: List[QCRule] = []

    # ========================================
    # 必填校验 (required) — 强制
    # ========================================

    rules.append(QCRule(
        rule_id="FQ-001", field_name="patient_name",
        rule_name="患者姓名非空性",
        description="患者姓名不能为空",
        severity=Severity.ERROR, category=Category.REQUIRED,
        validate=lambda fp: _not_empty(fp.get("patient_name")),
        message=lambda fp: "患者姓名不能为空",
    ))

    rules.append(QCRule(
        rule_id="FQ-002", field_name="sex",
        rule_name="性别非空性",
        description="性别不能为空",
        severity=Severity.ERROR, category=Category.REQUIRED,
        validate=lambda fp: _not_empty(fp.get("sex")),
        message=lambda fp: "性别不能为空",
    ))

    rules.append(QCRule(
        rule_id="FQ-003", field_name="age",
        rule_name="年龄非空性",
        description="年龄(岁)或年龄(天)至少填写一项",
        severity=Severity.ERROR, category=Category.REQUIRED,
        validate=lambda fp: (
            _valid_number(fp.get("age")) or
            _valid_number(fp.get("age_in_days"))
        ),
        message=lambda fp: "年龄(岁)或年龄(天)至少填写一项",
    ))

    rules.append(QCRule(
        rule_id="FQ-004", field_name="id_card",
        rule_name="身份证号非空性",
        description="患者身份证号不能为空",
        severity=Severity.ERROR, category=Category.REQUIRED,
        validate=lambda fp: _not_empty(fp.get("id_card")),
        message=lambda fp: "身份证号不能为空",
    ))

    rules.append(QCRule(
        rule_id="FQ-005", field_name="admission_datetime",
        rule_name="入院时间非空性",
        description="入院时间不能为空",
        severity=Severity.ERROR, category=Category.REQUIRED,
        validate=lambda fp: _not_empty(fp.get("admission_datetime")),
        message=lambda fp: "入院时间不能为空",
    ))

    rules.append(QCRule(
        rule_id="FQ-006", field_name="discharge_datetime",
        rule_name="出院时间非空性",
        description="出院时间不能为空",
        severity=Severity.ERROR, category=Category.REQUIRED,
        validate=lambda fp: _not_empty(fp.get("discharge_datetime")),
        message=lambda fp: "出院时间不能为空",
    ))

    rules.append(QCRule(
        rule_id="FQ-007", field_name="admission_dept",
        rule_name="入院科室非空性",
        description="入院科室不能为空",
        severity=Severity.ERROR, category=Category.REQUIRED,
        validate=lambda fp: _not_empty(fp.get("admission_dept")),
        message=lambda fp: "入院科室不能为空",
    ))

    rules.append(QCRule(
        rule_id="FQ-008", field_name="discharge_dept",
        rule_name="出院科室非空性",
        description="出院科室不能为空",
        severity=Severity.ERROR, category=Category.REQUIRED,
        validate=lambda fp: _not_empty(fp.get("discharge_dept")),
        message=lambda fp: "出院科室不能为空",
    ))

    rules.append(QCRule(
        rule_id="FQ-009", field_name="discharge_method",
        rule_name="离院方式非空性",
        description="离院方式不能为空",
        severity=Severity.ERROR, category=Category.REQUIRED,
        validate=lambda fp: _valid_number(fp.get("discharge_method")),
        message=lambda fp: "离院方式不能为空",
    ))

    rules.append(QCRule(
        rule_id="FQ-010", field_name="diagnosis",
        rule_name="主诊断非空性",
        description="必须有至少一个诊断",
        severity=Severity.ERROR, category=Category.REQUIRED,
        validate=lambda fp: len(_get_diagnoses(fp)) > 0,
        message=lambda fp: "必须有至少一个诊断",
    ))

    rules.append(QCRule(
        rule_id="FQ-011", field_name="diagnosis_code",
        rule_name="主诊断编码非空性",
        description="主诊断编码不能为空",
        severity=Severity.ERROR, category=Category.REQUIRED,
        validate=lambda fp: (
            _not_empty(_get_primary_diagnosis(fp).get("diagnosis_code"))
            if _get_primary_diagnosis(fp) else False
        ),
        message=lambda fp: "主诊断编码不能为空",
    ))

    rules.append(QCRule(
        rule_id="FQ-012", field_name="diagnosis_name",
        rule_name="主诊断名称非空性",
        description="主诊断名称不能为空",
        severity=Severity.ERROR, category=Category.REQUIRED,
        validate=lambda fp: (
            _not_empty(_get_primary_diagnosis(fp).get("diagnosis_name"))
            if _get_primary_diagnosis(fp) else False
        ),
        message=lambda fp: "主诊断名称不能为空",
    ))

    rules.append(QCRule(
        rule_id="FQ-013", field_name="attending_physician",
        rule_name="主诊医师非空性",
        description="主诊医师姓名不能为空",
        severity=Severity.ERROR, category=Category.REQUIRED,
        validate=lambda fp: _not_empty(fp.get("attending_physician")),
        message=lambda fp: "主诊医师姓名不能为空",
    ))

    rules.append(QCRule(
        rule_id="FQ-014", field_name="nationality",
        rule_name="国籍非空性",
        description="国籍不能为空",
        severity=Severity.ERROR, category=Category.REQUIRED,
        validate=lambda fp: _not_empty(fp.get("nationality")),
        message=lambda fp: "国籍不能为空",
    ))

    rules.append(QCRule(
        rule_id="FQ-015", field_name="admission_condition",
        rule_name="入院病情非空性",
        description="主诊断的入院病情代码不能为空",
        severity=Severity.WARNING, category=Category.REQUIRED,
        validate=lambda fp: (
            _not_empty(_get_primary_diagnosis(fp).get("admission_condition"))
            if _get_primary_diagnosis(fp) else True
        ),
        message=lambda fp: "主诊断的入院病情建议填写",
    ))

    rules.append(QCRule(
        rule_id="FQ-016", field_name="admission_route",
        rule_name="入院途径非空性",
        description="入院途径不能为空",
        severity=Severity.WARNING, category=Category.REQUIRED,
        validate=lambda fp: _valid_number(fp.get("admission_route")),
        message=lambda fp: "入院途径建议填写",
    ))

    # 新生儿相关必填
    rules.append(QCRule(
        rule_id="FQ-017", field_name="newborn_birth_weight",
        rule_name="新生儿出生体重非空性",
        description="新生儿(天龄<29天)入院时，出生体重必须填写",
        severity=Severity.ERROR, category=Category.REQUIRED,
        validate=lambda fp: (
            _valid_number(fp.get("newborn_birth_weight"))
            if (_to_float(fp.get("age_in_days")) is not None
                and _to_float(fp.get("age_in_days")) < 29)
            else True
        ),
        message=lambda fp: "新生儿(天龄<29天)入院时，出生体重必须填写",
    ))

    # 手术相关必填
    rules.append(QCRule(
        rule_id="FQ-018", field_name="surgeon_name",
        rule_name="术者姓名非空性",
        description="有手术时术者姓名不能为空",
        severity=Severity.ERROR, category=Category.REQUIRED,
        validate=lambda fp: (
            all(_not_empty(s.get("surgeon_name")) for s in _get_surgeries(fp)
                if _not_empty(s.get("surgery_code")))
            if _get_surgeries(fp) else True
        ),
        message=lambda fp: "有手术操作时，术者姓名不能为空",
    ))

    # ========================================
    # 格式校验 (format) — 强制
    # ========================================

    rules.append(QCRule(
        rule_id="FQ-020", field_name="id_card",
        rule_name="身份证号格式校验",
        description="身份证号应为 18 位标准格式",
        severity=Severity.ERROR, category=Category.FORMAT,
        validate=lambda fp: (
            _valid_id_card(fp.get("id_card"))
            if _not_empty(fp.get("id_card")) else True
        ),
        message=lambda fp: "身份证号格式不正确（应为18位）",
    ))

    rules.append(QCRule(
        rule_id="FQ-021", field_name="diagnosis_code",
        rule_name="主诊断编码格式校验",
        description="主诊断应符合 ICD-10 编码格式",
        severity=Severity.ERROR, category=Category.FORMAT,
        validate=lambda fp: (
            _valid_icd10(_get_primary_diagnosis(fp).get("diagnosis_code"))
            if _get_primary_diagnosis(fp)
               and _not_empty(_get_primary_diagnosis(fp).get("diagnosis_code"))
            else True
        ),
        message=lambda fp: "主诊断编码格式不正确（应为ICD-10格式）",
    ))

    rules.append(QCRule(
        rule_id="FQ-022", field_name="other_diagnosis_code",
        rule_name="其他诊断编码格式校验",
        description="其他诊断应符合 ICD-10 编码格式",
        severity=Severity.ERROR, category=Category.FORMAT,
        validate=lambda fp: all(
            _valid_icd10(d.get("diagnosis_code"))
            for d in _get_diagnoses(fp)[1:]
            if _not_empty(d.get("diagnosis_code"))
        ),
        message=lambda fp: "其他诊断编码格式不正确（应为ICD-10格式）",
    ))

    rules.append(QCRule(
        rule_id="FQ-023", field_name="surgery_code",
        rule_name="主手术编码格式校验",
        description="主手术应符合 ICD-9-CM-3 编码格式",
        severity=Severity.ERROR, category=Category.FORMAT,
        validate=lambda fp: (
            _valid_icd9cm3(_get_surgeries(fp)[0].get("surgery_code"))
            if _get_surgeries(fp)
               and _not_empty(_get_surgeries(fp)[0].get("surgery_code"))
            else True
        ),
        message=lambda fp: "主手术编码格式不正确（应为ICD-9-CM-3格式）",
    ))

    rules.append(QCRule(
        rule_id="FQ-024", field_name="discharge_method",
        rule_name="离院方式规范性",
        description="离院方式应为标准代码 1-5 或 9",
        severity=Severity.ERROR, category=Category.FORMAT,
        validate=lambda fp: (
            _to_int_code(fp.get("discharge_method")) in (1, 2, 3, 4, 5, 9)
            if _valid_number(fp.get("discharge_method")) else True
        ),
        message=lambda fp: "离院方式代码不正确（应为1-5或9）",
    ))

    rules.append(QCRule(
        rule_id="FQ-025", field_name="diagnosis_code_range",
        rule_name="诊断编码范围合理性",
        description="诊断编码不应使用外因编码(V/W/X/Y开头)",
        severity=Severity.ERROR, category=Category.FORMAT,
        validate=lambda fp: all(
            d.get("diagnosis_code", "")[0].upper() not in ('V', 'W', 'X', 'Y')
            for d in _get_diagnoses(fp)
            if _not_empty(d.get("diagnosis_code"))
        ),
        message=lambda fp: "诊断编码不应使用外因编码(V/W/X/Y开头)",
    ))

    # ========================================
    # 逻辑校验 (logic) — 提示
    # ========================================

    rules.append(QCRule(
        rule_id="FQ-030", field_name="age",
        rule_name="年龄(岁)(天)互斥性",
        description="年龄(岁)和年龄(天)不能同时有值",
        severity=Severity.ERROR, category=Category.LOGIC,
        validate=lambda fp: not (
            _valid_number(fp.get("age")) and
            _valid_number(fp.get("age_in_days"))
        ),
        message=lambda fp: "年龄(岁)和年龄(天)不能同时有值",
    ))

    rules.append(QCRule(
        rule_id="FQ-031", field_name="newborn_birth_weight",
        rule_name="新生儿出生体重合理性",
        description="新生儿出生体重应在 500-6000g 之间",
        severity=Severity.WARNING, category=Category.LOGIC,
        validate=lambda fp: (
            500 <= _to_float(fp.get("newborn_birth_weight")) <= 6000
            if _to_float(fp.get("newborn_birth_weight")) is not None
            else True
        ),
        message=lambda fp: "新生儿出生体重应在500-6000g之间",
    ))

    # ========================================
    # 一致性校验 (consistency) — 强制
    # ========================================

    rules.append(QCRule(
        rule_id="FQ-040", field_name="admission_discharge_time",
        rule_name="入院出院时间逻辑",
        description="入院时间应早于出院时间",
        severity=Severity.ERROR, category=Category.CONSISTENCY,
        validate=lambda fp: (
            _parse_datetime(fp.get("admission_datetime")) <
            _parse_datetime(fp.get("discharge_datetime"))
            if (_parse_datetime(fp.get("admission_datetime"))
                and _parse_datetime(fp.get("discharge_datetime")))
            else True
        ),
        message=lambda fp: "入院时间应早于出院时间",
    ))

    rules.append(QCRule(
        rule_id="FQ-041", field_name="los_days",
        rule_name="住院天数逻辑",
        description="住院天数应等于出院日期 - 入院日期",
        severity=Severity.ERROR, category=Category.CONSISTENCY,
        validate=lambda fp: _check_los_days(fp),
        message=lambda fp: "住院天数与入院出院日期不一致",
    ))

    rules.append(QCRule(
        rule_id="FQ-042", field_name="diagnosis_sex",
        rule_name="主诊断与性别一致性",
        description="诊断编码应与患者性别相符",
        severity=Severity.ERROR, category=Category.CONSISTENCY,
        validate=lambda fp: _check_diagnosis_sex(fp),
        message=lambda fp: "主诊断与患者性别不符",
    ))

    rules.append(QCRule(
        rule_id="FQ-043", field_name="other_diagnosis_sex",
        rule_name="其他诊断与性别一致性",
        description="其他诊断编码应与患者性别相符",
        severity=Severity.ERROR, category=Category.CONSISTENCY,
        validate=lambda fp: _check_other_diagnosis_sex(fp),
        message=lambda fp: "其他诊断与患者性别不符",
    ))

    rules.append(QCRule(
        rule_id="FQ-044", field_name="diagnosis_age",
        rule_name="主诊断与年龄一致性",
        description="新生儿疾病编码(P)需要年龄<1岁",
        severity=Severity.ERROR, category=Category.CONSISTENCY,
        validate=lambda fp: _check_diagnosis_age(fp),
        message=lambda fp: "主诊断与患者年龄不符",
    ))

    rules.append(QCRule(
        rule_id="FQ-045", field_name="diagnosis_duplicate",
        rule_name="诊断编码重复检查",
        description="诊断编码不应重复",
        severity=Severity.ERROR, category=Category.CONSISTENCY,
        validate=lambda fp: _check_diagnosis_duplicate(fp),
        message=lambda fp: "存在重复的诊断编码",
    ))

    rules.append(QCRule(
        rule_id="FQ-046", field_name="z_code_primary",
        rule_name="Z码主诊断合理性",
        description="Z码(健康状况因素)一般不应作为主诊断",
        severity=Severity.ERROR, category=Category.CONSISTENCY,
        validate=lambda fp: _check_z_code_primary(fp),
        message=lambda fp: "主诊断选择可能不当（Z码通常不作为主诊断）",
    ))

    rules.append(QCRule(
        rule_id="FQ-047", field_name="delivery_outcome",
        rule_name="分娩结局编码检查",
        description="分娩诊断需要有Z37分娩结局编码",
        severity=Severity.ERROR, category=Category.CONSISTENCY,
        validate=lambda fp: _check_delivery_outcome(fp),
        message=lambda fp: "分娩诊断缺少分娩结局编码(Z37)",
    ))

    rules.append(QCRule(
        rule_id="FQ-048", field_name="surgery_sex",
        rule_name="主手术与性别一致性",
        description="手术应与患者性别相符",
        severity=Severity.ERROR, category=Category.CONSISTENCY,
        validate=lambda fp: _check_surgery_sex(fp),
        message=lambda fp: "主手术与患者性别不符",
    ))

    rules.append(QCRule(
        rule_id="FQ-049", field_name="death_diagnosis_discharge",
        rule_name="死亡诊断与离院方式一致性",
        description="死亡相关诊断的离院方式应为死亡",
        severity=Severity.ERROR, category=Category.CONSISTENCY,
        validate=lambda fp: _check_death_discharge(fp),
        message=lambda fp: '死亡相关诊断的离院方式应为"死亡"',
    ))

    # 糖尿病联合编码检查
    rules.append(QCRule(
        rule_id="FQ-050", field_name="diabetes_joint_code",
        rule_name="糖尿病联合编码检查",
        description="糖尿病伴并发症应使用联合编码",
        severity=Severity.WARNING, category=Category.CONSISTENCY,
        validate=lambda fp: _check_diabetes_joint_code(fp),
        message=lambda fp: "存在需要联合诊断的情况，建议使用联合编码",
    ))

    # ========================================
    # 补充必填校验 — 提示级 (warning)
    # ========================================

    _warning_required = [
        ("FQ-051", "ethnicity", "民族非空性", "民族建议填写"),
        ("FQ-052", "marital_status", "婚姻状况非空性", "婚姻状况建议填写"),
        ("FQ-053", "allergy_flag", "过敏标志非空性", "药物过敏标志建议填写"),
        ("FQ-054", "blood_type", "血型非空性", "血型建议填写"),
        ("FQ-055", "rh_blood_type", "Rh血型非空性", "Rh血型建议填写"),
        ("FQ-056", "contact_name", "联系人姓名非空性", "联系人姓名建议填写"),
        ("FQ-057", "contact_phone", "联系人电话非空性", "联系人电话建议填写"),
        ("FQ-058", "contact_relation", "联系人关系非空性", "联系人与患者关系建议填写"),
        ("FQ-059", "contact_address", "联系人地址非空性", "联系人地址建议填写"),
        ("FQ-060", "treatment_category", "治疗类别非空性", "治疗类别建议填写"),
        ("FQ-061", "readmission_plan", "再住院计划非空性", "是否有31天内再住院计划建议填写"),
        ("FQ-062", "pathology_diagnosis", "病理诊断非空性", "如有病理检查，建议填写病理诊断"),
        ("FQ-063", "admission_condition_other", "其他诊断入院病情非空性",
         "其他诊断的入院病情建议填写"),
        ("FQ-064", "autopsy_flag", "尸检标志非空性", "死亡病例尸检标志建议填写"),
        ("FQ-065", "current_address", "现住址非空性", "现住址建议填写"),
        ("FQ-066", "birth_place", "出生地非空性", "出生地建议填写"),
        ("FQ-067", "native_place", "籍贯非空性", "籍贯建议填写"),
        ("FQ-068", "los_days", "住院天数非空性", "住院天数建议填写"),
        ("FQ-069", "total_cost", "总费用非空性", "总费用建议填写"),
        ("FQ-070", "self_pay_amount", "自付金额非空性", "自付金额建议填写"),
    ]
    for rid, fname, rname, msg in _warning_required:
        rules.append(QCRule(
            rule_id=rid, field_name=fname,
            rule_name=rname, description=msg,
            severity=Severity.WARNING, category=Category.REQUIRED,
            validate=(lambda fn: lambda fp: _not_empty(fp.get(fn)))(fname),
            message=(lambda m: lambda fp: m)(msg),
        ))

    # ========================================
    # 补充格式校验
    # ========================================

    rules.append(QCRule(
        rule_id="FQ-071", field_name="other_surgery_code",
        rule_name="其他手术编码格式校验",
        description="其他手术应符合 ICD-9-CM-3 编码格式",
        severity=Severity.ERROR, category=Category.FORMAT,
        validate=lambda fp: all(
            _valid_icd9cm3(s.get("surgery_code"))
            for s in _get_surgeries(fp)[1:]
            if _not_empty(s.get("surgery_code"))
        ),
        message=lambda fp: "其他手术编码格式不正确（应为ICD-9-CM-3格式）",
    ))

    rules.append(QCRule(
        rule_id="FQ-072", field_name="admission_route",
        rule_name="入院途径规范性",
        description="入院途径应为标准代码 1-4",
        severity=Severity.WARNING, category=Category.FORMAT,
        validate=lambda fp: (
            _to_int_code(fp.get("admission_route")) in (1, 2, 3, 4)
            if _valid_number(fp.get("admission_route")) else True
        ),
        message=lambda fp: "入院途径代码不正确（应为1=急诊/2=门诊/3=其他/4=转入）",
    ))

    rules.append(QCRule(
        rule_id="FQ-073", field_name="sex",
        rule_name="性别规范性",
        description="性别应为标准值",
        severity=Severity.ERROR, category=Category.FORMAT,
        validate=lambda fp: (
            _get_sex_code(fp) in (1, 2)
            if _not_empty(fp.get("sex")) else True
        ),
        message=lambda fp: '性别应为"男"或"女"',
    ))

    rules.append(QCRule(
        rule_id="FQ-074", field_name="admission_condition",
        rule_name="入院病情规范性",
        description="入院病情代码应为 1-4",
        severity=Severity.WARNING, category=Category.FORMAT,
        validate=lambda fp: (
            _get_primary_diagnosis(fp).get("admission_condition") in
            ("1", "2", "3", "4", 1, 2, 3, 4)
            if (_get_primary_diagnosis(fp)
                and _not_empty(_get_primary_diagnosis(fp).get("admission_condition")))
            else True
        ),
        message=lambda fp: "入院病情代码应为1=有/2=临床未确定/3=情况不明/4=无",
    ))

    rules.append(QCRule(
        rule_id="FQ-075", field_name="newborn_admission_type",
        rule_name="新生儿入院类型规范性",
        description="新生儿入院类型应为 1-2",
        severity=Severity.WARNING, category=Category.FORMAT,
        validate=lambda fp: (
            fp.get("newborn_admission_type") in ("1", "2", 1, 2)
            if _not_empty(fp.get("newborn_admission_type")) else True
        ),
        message=lambda fp: "新生儿入院类型应为1(正常)/2(患病)",
    ))

    # ========================================
    # 补充逻辑校验
    # ========================================

    rules.append(QCRule(
        rule_id="FQ-076", field_name="newborn_admission_weight",
        rule_name="新生儿入院体重合理性",
        description="新生儿入院体重应在 500-6000g 之间",
        severity=Severity.WARNING, category=Category.LOGIC,
        validate=lambda fp: (
            500 <= _to_float(fp.get("newborn_admission_weight")) <= 6000
            if _to_float(fp.get("newborn_admission_weight")) is not None
            else True
        ),
        message=lambda fp: "新生儿入院体重应在500-6000g之间",
    ))

    rules.append(QCRule(
        rule_id="FQ-077", field_name="age",
        rule_name="年龄合理性",
        description="年龄应在 0-150 岁之间",
        severity=Severity.WARNING, category=Category.LOGIC,
        validate=lambda fp: (
            0 <= _to_float(fp.get("age")) <= 150
            if _to_float(fp.get("age")) is not None else True
        ),
        message=lambda fp: "年龄超出合理范围(0-150岁)",
    ))

    rules.append(QCRule(
        rule_id="FQ-078", field_name="los_days",
        rule_name="住院天数合理性",
        description="住院天数应在 0-365 天之间",
        severity=Severity.WARNING, category=Category.LOGIC,
        validate=lambda fp: (
            0 <= _to_float(fp.get("los_days")) <= 365
            if _to_float(fp.get("los_days")) is not None else True
        ),
        message=lambda fp: "住院天数超出合理范围(0-365天)",
    ))

    rules.append(QCRule(
        rule_id="FQ-079", field_name="total_cost",
        rule_name="总费用合理性",
        description="总费用应 > 0",
        severity=Severity.WARNING, category=Category.LOGIC,
        validate=lambda fp: (
            _to_float(fp.get("total_cost")) > 0
            if _to_float(fp.get("total_cost")) is not None else True
        ),
        message=lambda fp: "总费用应大于0",
    ))

    # ========================================
    # 补充一致性校验
    # ========================================

    rules.append(QCRule(
        rule_id="FQ-080", field_name="other_diagnosis_age",
        rule_name="其他诊断与年龄一致性",
        description="其他诊断的新生儿编码(P)需要年龄<1岁",
        severity=Severity.ERROR, category=Category.CONSISTENCY,
        validate=lambda fp: _check_other_diagnosis_age(fp),
        message=lambda fp: "其他诊断与患者年龄不符",
    ))

    rules.append(QCRule(
        rule_id="FQ-081", field_name="newborn_primary_diag_weight",
        rule_name="主诊断与新生儿出生体重一致性",
        description="低体重/巨大儿编码应与出生体重匹配",
        severity=Severity.ERROR, category=Category.CONSISTENCY,
        validate=lambda fp: _check_newborn_weight(fp),
        message=lambda fp: "主诊断与新生儿出生体重不符",
    ))

    rules.append(QCRule(
        rule_id="FQ-082", field_name="other_surgery_sex",
        rule_name="其他手术与性别一致性",
        description="其他手术应与患者性别相符",
        severity=Severity.ERROR, category=Category.CONSISTENCY,
        validate=lambda fp: _check_other_surgery_sex(fp),
        message=lambda fp: "其他手术与患者性别不符",
    ))

    rules.append(QCRule(
        rule_id="FQ-083", field_name="surgery_diagnosis_match",
        rule_name="手术与诊断一致性",
        description="有手术编码时应有对应手术诊断",
        severity=Severity.WARNING, category=Category.CONSISTENCY,
        validate=lambda fp: (
            len(_get_diagnoses(fp)) > 0
            if any(_not_empty(s.get("surgery_code")) for s in _get_surgeries(fp))
            else True
        ),
        message=lambda fp: "有手术操作但缺少诊断",
    ))

    rules.append(QCRule(
        rule_id="FQ-084", field_name="coma_brain_injury",
        rule_name="昏迷时间与颅脑损伤一致性",
        description="有昏迷时间时须有颅脑损伤诊断",
        severity=Severity.ERROR, category=Category.CONSISTENCY,
        validate=lambda fp: _check_coma_brain_injury(fp),
        message=lambda fp: "有昏迷时间但无颅脑损伤相关诊断",
    ))

    rules.append(QCRule(
        rule_id="FQ-085", field_name="anesthesia_surgeon",
        rule_name="麻醉与术者一致性",
        description="有麻醉方式时须有麻醉医师",
        severity=Severity.ERROR, category=Category.CONSISTENCY,
        validate=lambda fp: all(
            _not_empty(s.get("anesthesiologist_name"))
            for s in _get_surgeries(fp)
            if _not_empty(s.get("anesthesia_method"))
        ),
        message=lambda fp: "有麻醉方式时，麻醉医师姓名不能为空",
    ))

    # ========================================
    # 最终补充 — 各诊断入院病情 / 手术 / 费用等
    # ========================================

    _final_rules = [
        ("FQ-086", "work_unit", "工作单位非空性", "在职患者工作单位建议填写",
         Severity.WARNING, Category.REQUIRED),
        ("FQ-087", "work_address", "工作地址非空性", "有工作单位时地址建议填写",
         Severity.WARNING, Category.REQUIRED),
        ("FQ-088", "surgery_date", "手术日期非空性", "有手术时手术日期建议填写",
         Severity.WARNING, Category.REQUIRED),
        ("FQ-089", "anesthesia_method", "麻醉方式非空性", "有手术时麻醉方式建议填写",
         Severity.WARNING, Category.REQUIRED),
        ("FQ-090", "drug_allergy_name", "过敏药物名称非空性",
         "有药物过敏时过敏药物名称建议填写",
         Severity.WARNING, Category.REQUIRED),
        ("FQ-091", "health_card_no", "健康卡号非空性", "健康卡号建议填写",
         Severity.WARNING, Category.REQUIRED),
        ("FQ-092", "payment_type", "医疗付款方式非空性", "医疗付款方式建议填写",
         Severity.WARNING, Category.REQUIRED),
        ("FQ-093", "quality_control_doctor", "质控医师非空性", "质控医师建议填写",
         Severity.WARNING, Category.REQUIRED),
        ("FQ-094", "quality_control_nurse", "质控护士非空性", "质控护士建议填写",
         Severity.WARNING, Category.REQUIRED),
        ("FQ-095", "quality_control_date", "质控日期非空性", "质控日期建议填写",
         Severity.WARNING, Category.REQUIRED),
    ]
    for rid, fname, rname, msg, sev, cat in _final_rules:
        rules.append(QCRule(
            rule_id=rid, field_name=fname,
            rule_name=rname, description=msg,
            severity=sev, category=cat,
            validate=(lambda fn: lambda fp: _not_empty(fp.get(fn)))(fname),
            message=(lambda m: lambda fp: m)(msg),
        ))

    return rules


# ============================================================
# 一致性校验辅助函数
# ============================================================

def _check_los_days(fp: dict) -> bool:
    """住院天数 = 出院日期 - 入院日期。"""
    adm = _parse_datetime(fp.get("admission_datetime"))
    dis = _parse_datetime(fp.get("discharge_datetime"))
    los = _to_float(fp.get("los_days"))
    if adm and dis and los is not None:
        expected = (dis.date() - adm.date()).days
        return abs(los - expected) <= 1  # 允许 1 天误差
    return True


def _check_diagnosis_sex(fp: dict) -> bool:
    """主诊断与性别一致性。"""
    sex = _get_sex_code(fp)
    primary = _get_primary_diagnosis(fp)
    if not sex or not primary:
        return True
    code = (primary.get("diagnosis_code") or "").upper()
    if not code:
        return True
    # 男性不能有妇产科诊断
    if sex == 1:
        if re.match(r'^O', code):
            return False
        if re.match(r'^N[78]\d|^N9[0-8]', code):
            return False
    # 女性不能有男性特有诊断
    if sex == 2:
        if re.match(r'^N4\d|^N5[01]', code):
            return False
    return True


def _check_other_diagnosis_sex(fp: dict) -> bool:
    """其他诊断与性别一致性。"""
    sex = _get_sex_code(fp)
    diags = _get_diagnoses(fp)
    if not sex or len(diags) <= 1:
        return True
    for diag in diags[1:]:
        code = (diag.get("diagnosis_code") or "").upper()
        if not code:
            continue
        if sex == 1 and re.match(r'^O|^N[78]\d|^N9[0-8]', code):
            return False
        if sex == 2 and re.match(r'^N4\d|^N5[01]', code):
            return False
    return True


def _check_diagnosis_age(fp: dict) -> bool:
    """主诊断与年龄一致性 — P 码需要年龄 <1 岁。"""
    primary = _get_primary_diagnosis(fp)
    if not primary:
        return True
    code = (primary.get("diagnosis_code") or "").upper()
    if not code or not code.startswith("P"):
        return True
    age = _to_float(fp.get("age"))
    age_days = _to_float(fp.get("age_in_days"))
    if age is not None and age >= 1:
        return False
    if age_days is not None and age_days >= 365:
        return False
    return True


def _check_diagnosis_duplicate(fp: dict) -> bool:
    """诊断编码不应重复。"""
    codes = [
        d.get("diagnosis_code")
        for d in _get_diagnoses(fp)
        if _not_empty(d.get("diagnosis_code"))
    ]
    return len(codes) == len(set(codes))


def _check_z_code_primary(fp: dict) -> bool:
    """Z 码不应作为主诊断（排除 Z37/Z38）。"""
    primary = _get_primary_diagnosis(fp)
    if not primary:
        return True
    code = (primary.get("diagnosis_code") or "").upper()
    if not code:
        return True
    if re.match(r'^Z\d{2}', code) and not re.match(r'^Z3[78]', code):
        return False
    return True


def _check_delivery_outcome(fp: dict) -> bool:
    """分娩诊断需要 Z37 结局编码。"""
    codes = [
        (d.get("diagnosis_code") or "").upper()
        for d in _get_diagnoses(fp)
        if _not_empty(d.get("diagnosis_code"))
    ]
    has_delivery = any(re.match(r'^O8[0-4]', c) for c in codes)
    has_abortion = any(re.match(r'^O0[0-8]', c) for c in codes)
    has_outcome = any(re.match(r'^Z37', c) for c in codes)
    if has_delivery and not has_abortion and not has_outcome:
        return False
    return True


def _check_surgery_sex(fp: dict) -> bool:
    """主手术与性别一致性。"""
    sex = _get_sex_code(fp)
    surgeries = _get_surgeries(fp)
    if not sex or not surgeries:
        return True
    code = (surgeries[0].get("surgery_code") or "")
    if not code:
        return True
    # 男性不能有妇产科手术 (68-75)
    if sex == 1 and re.match(r'^6[89]|^7[0-5]', code):
        return False
    # 女性不能有男性特有手术 (60-64)
    if sex == 2 and re.match(r'^6[0-4]', code):
        return False
    return True


def _check_death_discharge(fp: dict) -> bool:
    """死亡诊断与离院方式一致性。"""
    primary = _get_primary_diagnosis(fp)
    if not primary:
        return True
    code = (primary.get("diagnosis_code") or "").upper()
    method = _to_int_code(fp.get("discharge_method"))
    if not code:
        return True
    is_death = bool(re.match(r'^R99|^I46\.1', code))
    if is_death and method != 5:
        return False
    return True


def _check_other_diagnosis_age(fp: dict) -> bool:
    """其他诊断与年龄一致性 — P 码需要年龄 <1 岁。"""
    diags = _get_diagnoses(fp)
    if len(diags) <= 1:
        return True
    age = _to_float(fp.get("age"))
    age_days = _to_float(fp.get("age_in_days"))
    for diag in diags[1:]:
        code = (diag.get("diagnosis_code") or "").upper()
        if not code or not code.startswith("P"):
            continue
        if age is not None and age >= 1:
            return False
        if age_days is not None and age_days >= 365:
            return False
    return True


def _check_newborn_weight(fp: dict) -> bool:
    """主诊断与新生儿出生体重一致性。"""
    birth_weight = _to_float(fp.get("newborn_birth_weight"))
    primary = _get_primary_diagnosis(fp)
    if birth_weight is None or birth_weight <= 0 or not primary:
        return True
    code = (primary.get("diagnosis_code") or "").upper()
    if not code:
        return True
    # 极低出生体重 P07.0 (体重<1000g)
    if re.match(r'^P07\.0', code) and birth_weight >= 1000:
        return False
    # 低出生体重 P07.1 (体重1000-2499g)
    if re.match(r'^P07\.1', code) and (birth_weight < 1000 or birth_weight >= 2500):
        return False
    # 巨大儿 P08.0 (体重>=4000g)
    if re.match(r'^P08\.0', code) and birth_weight < 4000:
        return False
    return True


def _check_other_surgery_sex(fp: dict) -> bool:
    """其他手术与性别一致性。"""
    sex = _get_sex_code(fp)
    surgeries = _get_surgeries(fp)
    if not sex or len(surgeries) <= 1:
        return True
    for surg in surgeries[1:]:
        code = (surg.get("surgery_code") or "")
        if not code:
            continue
        if sex == 1 and re.match(r'^6[89]|^7[0-5]', code):
            return False
        if sex == 2 and re.match(r'^6[0-4]', code):
            return False
    return True


def _check_coma_brain_injury(fp: dict) -> bool:
    """昏迷时间与颅脑损伤一致性。"""
    coma_hours = (_to_float(fp.get("coma_hours_before")) or 0.0) + (
        _to_float(fp.get("coma_hours_after")) or 0.0
    )
    if coma_hours > 0:
        codes = [
            (d.get("diagnosis_code") or "").upper()
            for d in _get_diagnoses(fp)
            if _not_empty(d.get("diagnosis_code"))
        ]
        has_brain = any(re.match(r'^S0[0-9]', c) for c in codes)
        return has_brain
    return True


def _check_diabetes_joint_code(fp: dict) -> bool:
    """糖尿病联合编码检查。"""
    codes = [
        (d.get("diagnosis_code") or "").upper()
        for d in _get_diagnoses(fp)
        if _not_empty(d.get("diagnosis_code"))
    ]
    has_diabetes = any(re.match(r'^E1[0-4]', c) for c in codes)
    has_complication = any(
        re.match(r'^H36\.0|^H28\.0|^G63\.2|^N08\.3', c) for c in codes
    )
    if has_diabetes and has_complication:
        has_joint = any(re.match(r'^E1[0-4]\.[3-7]', c) for c in codes)
        return has_joint
    return True


# ============================================================
# 引擎主类
# ============================================================

class FrontpageFormalQC:
    """病案首页形式质控引擎。"""

    def __init__(self):
        self.rules = _build_rules()

    def validate(
        self,
        frontpage: dict,
        categories: Optional[List[Category]] = None,
        severities: Optional[List[Severity]] = None,
    ) -> QCReport:
        """
        对首页数据执行形式质控。

        Args:
            frontpage: 首页数据字典
            categories: 可选，只执行指定类别的规则
            severities: 可选，只执行指定严重度的规则

        Returns:
            QCReport 包含所有规则的执行结果
        """
        results: List[QCResult] = []
        rules_to_run = self.rules

        if categories:
            rules_to_run = [r for r in rules_to_run if r.category in categories]
        if severities:
            rules_to_run = [r for r in rules_to_run if r.severity in severities]

        for rule in rules_to_run:
            exec_error_msg: Optional[str] = None
            try:
                passed = bool(rule.validate(frontpage))
            except Exception as e:
                logger.warning("规则 %s 执行异常: %s", rule.rule_id, type(e).__name__)
                passed = False
                exec_error_msg = f"规则 {rule.rule_id} 校验执行异常（{type(e).__name__}），未通过校验"

            if exec_error_msg is not None:
                msg = exec_error_msg
            else:
                msg = "" if passed else rule.message(frontpage)
            results.append(QCResult(
                rule_id=rule.rule_id,
                field_name=rule.field_name,
                rule_name=rule.rule_name,
                passed=passed,
                message=msg,
                severity=rule.severity,
                category=rule.category,
            ))

        passed_count = sum(1 for r in results if r.passed)
        failed_count = sum(1 for r in results if not r.passed)

        return QCReport(
            total_rules=len(results),
            passed=passed_count,
            failed=failed_count,
            results=results,
        )

    def get_stats(self) -> dict:
        """获取规则统计。"""
        by_category: Dict[str, int] = {}
        by_severity: Dict[str, int] = {}

        for rule in self.rules:
            cat = rule.category.value
            sev = rule.severity.value
            by_category[cat] = by_category.get(cat, 0) + 1
            by_severity[sev] = by_severity.get(sev, 0) + 1

        return {
            "total": len(self.rules),
            "by_category": by_category,
            "by_severity": by_severity,
        }

    def get_rule_coverage_report(self) -> dict:
        """获取病案首页规则覆盖注册表。"""
        from .qc_rule_coverage import (
            build_frontpage_rule_coverage_items,
            summarize_rule_coverage,
        )

        items = build_frontpage_rule_coverage_items(self.rules)
        return {
            "summary": summarize_rule_coverage(items),
            "items": [item.to_dict() for item in items],
        }


class FrontpageFormalQCEngine(FrontpageFormalQC):
    """
    兼容旧调用方的别名。
    旧代码使用 FrontpageFormalQCEngine().run(frontpage) 接口，
    这里保留同名类与 run 方法以避免导入/调用中断。
    """

    def run(self, frontpage: dict):
        return self.validate(frontpage)
