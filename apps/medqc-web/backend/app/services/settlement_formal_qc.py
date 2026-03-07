"""
医保结算清单形式质控引擎

基于《湖南省区域DRG付费医保基金结算清单质控规则（2023版）》136 条规则，
结合《医疗保障基金结算清单填写规范》国家标准。

规则分类：
- 完整性（~30条）：必填项校验
- 规范性（~25条）：值域/格式校验
- 合理性（~70条）：逻辑一致性校验
- 逻辑质控（~11条）：复杂跨字段交叉校验
"""
import re
import logging
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ============================================================
# 数据结构（复用 frontpage_formal_qc 的模式）
# ============================================================

class Severity:
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

class Category:
    REQUIRED = "required"       # 完整性
    FORMAT = "format"           # 规范性
    LOGIC = "logic"             # 合理性
    CONSISTENCY = "consistency" # 逻辑质控

@dataclass
class SettlementQCRule:
    """单条结算清单质控规则。"""
    rule_id: str                    # 对应湖南省规则序号
    field_name: str                 # 数据采集项
    rule_name: str                  # 规则名称
    description: str                # 违规提示语
    severity: str                   # error / warning / info
    category: str                   # required / format / logic / consistency
    affects_grouping: bool          # 是否影响入组
    validate: Callable[[dict], bool]  # 校验函数（True=通过）
    message: Callable[[dict], str]    # 违规消息生成函数

@dataclass
class SettlementQCResult:
    """单条规则校验结果。"""
    rule_id: str
    field_name: str
    rule_name: str
    passed: bool
    message: str
    severity: str
    category: str
    affects_grouping: bool

@dataclass
class SettlementQCReport:
    """结算清单质控报告。"""
    total_rules: int = 0
    passed: int = 0
    failed: int = 0
    results: List[SettlementQCResult] = field(default_factory=list)


# ============================================================
# 辅助函数
# ============================================================

def _ne(value: Any) -> bool:
    """非空判断。"""
    if value is None:
        return False
    if isinstance(value, str) and not value.strip():
        return False
    if isinstance(value, (list, dict)) and len(value) == 0:
        return False
    return True

def _is_number(value: Any) -> bool:
    """是否为数字。"""
    if value is None:
        return False
    try:
        float(str(value))
        return True
    except (ValueError, TypeError):
        return False

def _to_num(value: Any) -> Optional[float]:
    """转数字。"""
    try:
        return float(str(value))
    except (ValueError, TypeError):
        return None

def _parse_dt(s: Any) -> Optional[datetime]:
    """解析日期时间。"""
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(str(s).strip(), fmt)
        except ValueError:
            continue
    return None

def _valid_id_card(id_card: str) -> bool:
    """15/18 位身份证正则。"""
    if not id_card:
        return False
    id_card = str(id_card).strip()
    return bool(re.match(r'^\d{15}$', id_card) or re.match(r'^\d{17}[\dXx]$', id_card))

def _valid_phone(phone: str) -> bool:
    """电话号码正则。"""
    if not phone:
        return False
    return bool(re.match(r'^[\d\-+() ]{7,20}$', str(phone).strip()))

def _valid_icd10(code: str) -> bool:
    """ICD-10 编码格式。"""
    if not code:
        return False
    return bool(re.match(r'^[A-Za-z]\d{2}(\.\d{1,4})?(x\d{3})?$', str(code).strip()))

def _valid_icd9(code: str) -> bool:
    """ICD-9-CM-3 编码格式。"""
    if not code:
        return False
    return bool(re.match(r'^\d{2}\.\d{2,4}(x\d{3})?$', str(code).strip()))

def _get_val(fp: dict, *keys) -> Any:
    """从嵌套字典取值，支持多级 key。"""
    val = fp
    for k in keys:
        if isinstance(val, dict):
            val = val.get(k)
        else:
            return None
    return val

def _get_diagnoses(fp: dict) -> list:
    return fp.get("diagnoses") or []

def _get_primary_diag(fp: dict) -> dict:
    diags = _get_diagnoses(fp)
    return diags[0] if diags else {}

def _get_other_diags(fp: dict) -> list:
    diags = _get_diagnoses(fp)
    return diags[1:] if len(diags) > 1 else []

def _get_surgeries(fp: dict) -> list:
    return fp.get("surgeries") or []

def _get_primary_surgery(fp: dict) -> dict:
    surgs = _get_surgeries(fp)
    return surgs[0] if surgs else {}

def _get_sex(fp: dict) -> str:
    """性别编码 1=男 2=女。"""
    s = fp.get("sex") or fp.get("gender") or ""
    s = str(s).strip()
    if s in ("1", "男"):
        return "1"
    if s in ("2", "女"):
        return "2"
    return s

def _diag_code(d: dict) -> str:
    return str(d.get("code") or d.get("icd_code") or "").strip().upper()

def _diag_name(d: dict) -> str:
    return str(d.get("name") or d.get("diagnosis_name") or "").strip()

def _surg_code(s: dict) -> str:
    return str(s.get("code") or s.get("operation_code") or "").strip()

def _surg_name(s: dict) -> str:
    return str(s.get("name") or s.get("operation_name") or "").strip()


# ============================================================
# 性别-诊断 专用编码列表 (规则 #135/#136)
# ============================================================

MALE_ONLY_DIAG_PREFIXES = [
    "B26.0", "C60", "C61", "C62", "C63",
    "D07.4", "D07.5", "D07.6", "D17.6", "D29", "D40",
    "E29", "E89.5", "F52.4", "I86.1", "L29.1",
    "N40", "N41", "N42", "N43", "N44", "N45", "N46", "N47", "N48", "N49", "N50", "N51",
    "Q53", "Q54", "Q55", "R86", "S31.2", "S31.3", "Z12.5",
]
MALE_ONLY_NAME_KEYWORDS = [
    "前列腺", "输精管", "精囊", "阴茎", "精子", "睾丸",
    "附睾", "阴囊", "尿道球腺", "射精管", "包皮", "海绵体",
]

FEMALE_ONLY_DIAG_PREFIXES = [
    "A34", "B37.3",
    "C51", "C52", "C53", "C54", "C55", "C56", "C57", "C58", "C79.6",
    "D06", "D07.0", "D07.1", "D07.2", "D07.3",
    "D25", "D26", "D27", "D28", "D39",
    "E28", "E89.4", "F52.5", "F53", "I86.3", "L29.2", "L70.5",
    "M80.0", "M80.1", "M81.0", "M81.1", "M83.0",
    "N70", "N71", "N72", "N73", "N74", "N75", "N76", "N77", "N78", "N79",
    "N80", "N81", "N82", "N83", "N84", "N85", "N86", "N87", "N88", "N89",
    "N90", "N91", "N92", "N93", "N94", "N95", "N96", "N97", "N98",
    "N99.2", "N99.3",
    "O", "P54.6",
    "Q50", "Q51", "Q52", "R87", "S31.4", "S37.4", "S37.5", "S37.6",
    "T19.2", "T19.3", "T83.3",
    "Z01.4", "Z12.4", "Z30.1", "Z30.3", "Z30.5", "Z31.1", "Z31.2",
    "Z32", "Z33", "Z34", "Z35", "Z36", "Z37", "Z38", "Z39",
    "Z43.7", "Z87.5", "Z97.5",
]
FEMALE_ONLY_NAME_KEYWORDS = [
    "阴道", "子宫", "宫颈", "宫腔", "输卵管", "卵巢",
    "会阴", "阴唇", "阴蒂", "处女膜", "妊娠", "外阴",
]

# ICU 类型值域 (规则 #99)
ICU_TYPES = {"1", "2", "3", "4", "5", "6", "7", "9",
             "CCU", "NICU", "EICU", "SICU", "PICU", "RICU", "ICU"}

# 入院病情值域
ADMISSION_CONDITION_VALUES = {"1", "2", "3", "4"}

# 离院方式值域
DISCHARGE_WAY_VALUES = {"1", "2", "3", "4", "5", "9"}

# 新生儿入院类型值域
NEWBORN_TYPES = {"1", "2", "3", "4", "9"}

# 输血品种代码
TRANSFUSION_CODES = {
    "1", "11", "12", "13", "14", "15", "16", "17",
    "2", "21", "22", "23",
    "3", "31", "32", "33", "34",
    "4", "41", "42", "43", "44", "45", "46",
    "5", "51", "6", "9"
}


def _check_sex_diag_match(sex: str, code: str, name: str) -> Optional[str]:
    """检查性别与诊断编码/名称是否矛盾。"""
    code_upper = code.upper()
    if sex == "1":  # 男性
        for prefix in FEMALE_ONLY_DIAG_PREFIXES:
            if code_upper.startswith(prefix):
                return f"性别为男，诊断编码 {code} 与性别不符"
        for kw in FEMALE_ONLY_NAME_KEYWORDS:
            if kw in name and "男" not in name:
                return f"性别为男，诊断 '{name}' 与性别不符"
    elif sex == "2":  # 女性
        for prefix in MALE_ONLY_DIAG_PREFIXES:
            if code_upper.startswith(prefix):
                return f"性别为女，诊断编码 {code} 与性别不符"
        for kw in MALE_ONLY_NAME_KEYWORDS:
            if kw in name and "女" not in name:
                return f"性别为女，诊断 '{name}' 与性别不符"
    return None


# ============================================================
# 规则构建
# ============================================================

def _build_rules() -> List[SettlementQCRule]:
    """构建全部 136 条医保结算清单质控规则。"""
    rules: List[SettlementQCRule] = []

    def R(rule_id, field_name, rule_name, desc, severity, category,
          affects, validate_fn, message_fn=None):
        rules.append(SettlementQCRule(
            rule_id=str(rule_id),
            field_name=field_name,
            rule_name=rule_name,
            description=desc,
            severity=severity,
            category=category,
            affects_grouping=affects,
            validate=validate_fn,
            message=message_fn or (lambda fp: desc),
        ))

    # ============ 完整性规则 ============

    R("3", "病案号", "病案号必填", "病案号，为必填项",
      Severity.ERROR, Category.REQUIRED, False,
      lambda fp: _ne(fp.get("medical_record_no")))

    R("4", "出生日期", "出生日期必填", "出生日期，为必填项",
      Severity.ERROR, Category.REQUIRED, False,
      lambda fp: _ne(fp.get("birth_date")))

    R("10", "出院时间", "出院时间必填", "出院时间为必填项",
      Severity.ERROR, Category.REQUIRED, False,
      lambda fp: _ne(fp.get("discharge_datetime")))

    R("21", "国籍", "国籍必填", "国籍为必填项",
      Severity.ERROR, Category.REQUIRED, False,
      lambda fp: _ne(fp.get("nationality")))

    R("29", "证件号码", "证件号码必填", "证件号码不能为空",
      Severity.ERROR, Category.REQUIRED, False,
      lambda fp: _ne(fp.get("id_number")))

    R("31", "证件类别", "证件类别必填", "患者证件类别，为必填项",
      Severity.ERROR, Category.REQUIRED, False,
      lambda fp: _ne(fp.get("id_type")))

    R("35", "总费用", "总费用必填", "总费用，为必填项",
      Severity.ERROR, Category.REQUIRED, True,
      lambda fp: _ne(fp.get("total_cost")))

    R("39", "离院方式", "离院方式必填", "离院方式编码，不能为空",
      Severity.ERROR, Category.REQUIRED, False,
      lambda fp: _ne(fp.get("leaving_hospital_way")))

    R("47", "民族", "民族必填", "民族名称，为必填项",
      Severity.ERROR, Category.REQUIRED, False,
      lambda fp: _ne(fp.get("ethnicity")))

    R("51", "年龄", "年龄必填", "年龄为必填项",
      Severity.ERROR, Category.REQUIRED, True,
      lambda fp: _ne(fp.get("age") or fp.get("age_years")))

    R("54", "入院病情", "入院病情必填", "入院病情编码不能为空",
      Severity.ERROR, Category.REQUIRED, False,
      lambda fp: _ne(fp.get("admission_condition")))

    R("56", "入院科别", "入院科室必填", "入院科室名称，为必填项",
      Severity.ERROR, Category.REQUIRED, False,
      lambda fp: _ne(fp.get("admission_dept")))

    R("59", "入院时间", "入院时间必填", "入院时间为必填项",
      Severity.ERROR, Category.REQUIRED, False,
      lambda fp: _ne(fp.get("admission_datetime")))

    R("61", "入院途径", "入院途径必填", "入院途径编码，为必填项",
      Severity.ERROR, Category.REQUIRED, False,
      lambda fp: _ne(fp.get("admission_way")))

    R("64", "住院天数", "住院天数必填", "实际住院天数为必填项",
      Severity.ERROR, Category.REQUIRED, True,
      lambda fp: _ne(fp.get("actual_hospital_days")))

    R("85", "性别", "性别必填", "性别编码，为必填项",
      Severity.ERROR, Category.REQUIRED, True,
      lambda fp: _ne(fp.get("sex") or fp.get("gender")))

    R("86", "姓名", "姓名必填", "病人姓名，为必填项",
      Severity.ERROR, Category.REQUIRED, False,
      lambda fp: _ne(fp.get("patient_name")))

    R("88", "医保支付方式", "医保支付方式必填", "医保支付方式编码，为必填项",
      Severity.ERROR, Category.REQUIRED, True,
      lambda fp: _ne(fp.get("payment_method")))

    R("95", "职业", "职业必填", "职业名称，为必填项",
      Severity.ERROR, Category.REQUIRED, False,
      lambda fp: _ne(fp.get("occupation")))

    R("97", "治疗类别", "治疗类别必填", "治疗类别，为必填项",
      Severity.ERROR, Category.REQUIRED, False,
      lambda fp: _ne(fp.get("treatment_type")))

    R("106", "主诊医师代码", "主诊医师代码必填", "主诊医师代码，为必填项",
      Severity.ERROR, Category.REQUIRED, False,
      lambda fp: _ne(fp.get("attending_physician_code")))

    R("107", "主诊医师姓名", "主诊医师姓名必填", "主诊医师姓名，为必填项",
      Severity.ERROR, Category.REQUIRED, False,
      lambda fp: _ne(fp.get("attending_physician")))

    R("91", "责任护士代码", "责任护士代码必填", "责任护士代码，为必填项",
      Severity.WARNING, Category.REQUIRED, False,
      lambda fp: _ne(fp.get("responsible_nurse_code")))

    R("92", "责任护士名称", "责任护士名称必填", "责任护士名称，为必填项",
      Severity.WARNING, Category.REQUIRED, False,
      lambda fp: _ne(fp.get("responsible_nurse")))

    R("133", "票据代码", "票据代码必填", "票据代码不为空",
      Severity.WARNING, Category.REQUIRED, False,
      lambda fp: _ne(fp.get("ticket_code")))

    R("134", "票据号", "票据号必填", "票据号不为空",
      Severity.WARNING, Category.REQUIRED, False,
      lambda fp: _ne(fp.get("ticket_no")))

    R("13", "联系人地址", "联系人地址必填", "联系人地址，为必填项",
      Severity.WARNING, Category.REQUIRED, False,
      lambda fp: _ne(fp.get("contact_address")))

    R("14", "联系人电话", "联系人电话必填", "联系人电话，为必填项",
      Severity.WARNING, Category.REQUIRED, False,
      lambda fp: _ne(fp.get("contact_phone")))

    R("18", "联系人关系", "联系人关系必填", "与联系人关系，为必填项",
      Severity.WARNING, Category.REQUIRED, False,
      lambda fp: _ne(fp.get("contact_relation")))

    R("40", "联系人姓名", "联系人姓名必填", "联系人姓名，为必填项",
      Severity.WARNING, Category.REQUIRED, False,
      lambda fp: _ne(fp.get("contact_name")))

    R("72", "现住址", "现住址必填", "现住址，为必填项",
      Severity.WARNING, Category.REQUIRED, False,
      lambda fp: _ne(fp.get("current_address")))

    # ============ 规范性规则 ============

    R("26", "证件号码", "身份证格式", "证件类别为居民身份证，证件号码不符合填写规范",
      Severity.ERROR, Category.FORMAT, False,
      lambda fp: (fp.get("id_type") not in ("1", "居民身份证") or _valid_id_card(fp.get("id_number") or "")))

    R("48", "年龄", "年龄为数字", "年龄必须是数字",
      Severity.ERROR, Category.FORMAT, True,
      lambda fp: (not _ne(fp.get("age"))) or _is_number(fp.get("age") or fp.get("age_years")))

    R("62", "住院天数", "住院天数正整数", "实际住院天数为大于0的整数",
      Severity.ERROR, Category.FORMAT, True,
      lambda fp: (not _ne(fp.get("actual_hospital_days"))) or
                 (_is_number(fp.get("actual_hospital_days")) and _to_num(fp.get("actual_hospital_days")) > 0))

    R("84", "性别", "性别值域", "性别编码，不在值域范围内",
      Severity.ERROR, Category.FORMAT, True,
      lambda fp: (not _ne(_get_sex(fp))) or _get_sex(fp) in ("0", "1", "2", "9"))

    R("38", "离院方式", "离院方式值域", "出院方式编码，不在值域范围内",
      Severity.ERROR, Category.FORMAT, False,
      lambda fp: (not _ne(fp.get("leaving_hospital_way"))) or
                 str(fp.get("leaving_hospital_way")).strip() in DISCHARGE_WAY_VALUES)

    R("53", "入院病情", "入院病情值域", "入院病情编码不在值域范围内",
      Severity.ERROR, Category.FORMAT, False,
      lambda fp: (not _ne(fp.get("admission_condition"))) or
                 str(fp.get("admission_condition")).strip() in ADMISSION_CONDITION_VALUES)

    R("90", "邮编", "邮编格式", "邮政编码须为6位数字",
      Severity.WARNING, Category.FORMAT, False,
      lambda fp: (not _ne(fp.get("zipcode"))) or bool(re.match(r'^\d{6}$', str(fp.get("zipcode")).strip())))

    R("15", "联系人电话", "电话格式", "联系人电话不符合电话号码填写规范",
      Severity.WARNING, Category.FORMAT, False,
      lambda fp: (not _ne(fp.get("contact_phone"))) or _valid_phone(fp.get("contact_phone")))

    R("73", "新生儿出生体重", "新生儿体重为数字", "新生儿出生体重必须是数字",
      Severity.ERROR, Category.FORMAT, True,
      lambda fp: (not _ne(fp.get("newborn_birth_weight"))) or _is_number(fp.get("newborn_birth_weight")))

    R("78", "新生儿入院体重", "新生儿入院体重为数字", "新生儿入院体重必须是数字",
      Severity.WARNING, Category.FORMAT, False,
      lambda fp: (not _ne(fp.get("newborn_admission_weight"))) or _is_number(fp.get("newborn_admission_weight")))

    R("119", "诊断代码", "诊断编码范围", "诊断编码不包括V/W/X/Y开头的编码",
      Severity.ERROR, Category.FORMAT, True,
      lambda fp: all(not _diag_code(d).startswith(c) for d in _get_diagnoses(fp) for c in "VWXY"
                     if _diag_code(d)))

    # ============ 合理性规则 ============

    # 时间逻辑
    R("7", "出院时间", "出院时间>出生日期", "出院时间必须大于出生日期",
      Severity.ERROR, Category.LOGIC, False,
      lambda fp: (not (_parse_dt(fp.get("discharge_datetime")) and _parse_dt(fp.get("birth_date"))))
                 or _parse_dt(fp.get("discharge_datetime")) > _parse_dt(fp.get("birth_date")))

    R("8", "出院时间", "出院时间>入院时间", "出院时间必须大于入院时间",
      Severity.ERROR, Category.LOGIC, False,
      lambda fp: (not (_parse_dt(fp.get("discharge_datetime")) and _parse_dt(fp.get("admission_datetime"))))
                 or _parse_dt(fp.get("discharge_datetime")) >= _parse_dt(fp.get("admission_datetime")))

    R("57", "入院时间", "入院时间≤出院时间", "入院时间必须小于等于出院时间",
      Severity.ERROR, Category.LOGIC, False,
      lambda fp: (not (_parse_dt(fp.get("admission_datetime")) and _parse_dt(fp.get("discharge_datetime"))))
                 or _parse_dt(fp.get("admission_datetime")) <= _parse_dt(fp.get("discharge_datetime")))

    R("58", "入院时间", "入院时间≥出生日期", "入院时间必须大于等于出生日期",
      Severity.ERROR, Category.LOGIC, False,
      lambda fp: (not (_parse_dt(fp.get("admission_datetime")) and _parse_dt(fp.get("birth_date"))))
                 or _parse_dt(fp.get("admission_datetime")) >= _parse_dt(fp.get("birth_date")))

    # 年龄逻辑
    R("49", "年龄", "年龄范围", "年龄大于等于0，小于200",
      Severity.ERROR, Category.LOGIC, True,
      lambda fp: (not _is_number(fp.get("age"))) or (0 <= _to_num(fp.get("age")) < 200))

    R("34", "总费用", "总费用>0", "金额合计费用必须大于0",
      Severity.ERROR, Category.LOGIC, True,
      lambda fp: (not _ne(fp.get("total_cost"))) or (_is_number(fp.get("total_cost")) and _to_num(fp.get("total_cost")) > 0))

    # 新生儿体重范围
    R("74", "新生儿出生体重", "体重范围200-9999", "新生儿出生体重（克）范围：200-9999克",
      Severity.ERROR, Category.LOGIC, True,
      lambda fp: (not _is_number(fp.get("newborn_birth_weight"))) or
                 (200 <= _to_num(fp.get("newborn_birth_weight")) < 10000))

    R("79", "新生儿入院体重", "入院体重范围200-9999", "新生儿入院体重必须大于200，小于10000",
      Severity.WARNING, Category.LOGIC, False,
      lambda fp: (not _is_number(fp.get("newborn_admission_weight"))) or
                 (200 <= _to_num(fp.get("newborn_admission_weight")) < 10000))

    # 诊断逻辑
    R("11", "出院诊断", "诊断重复", "西医主要诊断与其他诊断不能出现重复的诊断名称或编码",
      Severity.WARNING, Category.LOGIC, True,
      lambda fp: _check_diag_duplicate(fp))

    R("52", "其他诊断", "诊断名有编码", "填写了出院其他诊断名称，出院其他诊断编码不能为空",
      Severity.ERROR, Category.LOGIC, True,
      lambda fp: all(_ne(_diag_code(d)) for d in _get_other_diags(fp) if _ne(_diag_name(d))))

    R("45", "门诊诊断代码", "门诊诊断联动", "填写了门急诊诊断名称，门急诊诊断编码不能为空",
      Severity.WARNING, Category.LOGIC, False,
      lambda fp: (not _ne(fp.get("ed_diagnosis_name"))) or _ne(fp.get("ed_diagnosis_code")))

    # 手术逻辑
    R("67", "手术代码", "主手术代码必填", "主要手术及操作代码不能为空",
      Severity.ERROR, Category.LOGIC, True,
      lambda fp: (not (_get_surgeries(fp) or _ne(_surg_name(_get_primary_surgery(fp)))))
                 or _ne(_surg_code(_get_primary_surgery(fp))))

    R("100", "主要手术", "主手术名称必填", "主要手术及操作名称不能为空",
      Severity.ERROR, Category.LOGIC, True,
      lambda fp: (not (_get_surgeries(fp) or _ne(_surg_code(_get_primary_surgery(fp)))))
                 or _ne(_surg_name(_get_primary_surgery(fp))))

    R("101", "主要手术", "单一主手术", "一个患者只能有一个主要手术",
      Severity.ERROR, Category.LOGIC, True,
      lambda fp: sum(1 for s in _get_surgeries(fp) if s.get("is_main")) <= 1)

    R("71", "手术名称", "手术重复", "手术操作重复",
      Severity.WARNING, Category.LOGIC, False,
      lambda fp: _check_surgery_duplicate(fp))

    # 手术时间范围
    R("9", "出院时间", "手术在出入院间", "出院时间不能早于手术操作日期",
      Severity.WARNING, Category.LOGIC, False,
      lambda fp: _check_surgery_in_range(fp))

    # ICU 逻辑
    R("98", "重症监护", "ICU四项联动", "重症监护四项应同时为空或同时不为空",
      Severity.WARNING, Category.LOGIC, False,
      lambda fp: _check_icu_completeness(fp))

    R("36", "进ICU时间", "进ICU≤出ICU", "进重症监护室时间不能晚于出重症监护室时间",
      Severity.WARNING, Category.LOGIC, False,
      lambda fp: _check_icu_time_order(fp))

    R("37", "进ICU时间", "进ICU在入出院间", "进重症监护室时间应在出入院时间范围内",
      Severity.WARNING, Category.LOGIC, False,
      lambda fp: _check_icu_in_range(fp, "icu_enter_time"))

    R("12", "出ICU时间", "出ICU在入出院间", "出重症监护室时间应在出入院时间范围内",
      Severity.WARNING, Category.LOGIC, False,
      lambda fp: _check_icu_in_range(fp, "icu_leave_time"))

    R("99", "ICU类型", "ICU类型值域", "重症监护病房类型不在值域范围内",
      Severity.WARNING, Category.LOGIC, False,
      lambda fp: (not _ne(fp.get("icu_type"))) or str(fp.get("icu_type")).strip() in ICU_TYPES)

    # 再住院逻辑
    R("5", "再住院计划", "再住院目的联动", "有出院31日内再住院计划时必填目的",
      Severity.WARNING, Category.LOGIC, False,
      lambda fp: (str(fp.get("rehospital_plan")).strip() != "2") or _ne(fp.get("rehospital_purpose")))

    R("65", "再住院计划", "目的有则计划为有", "目的不为空时，是否再住院计划应为'2'",
      Severity.WARNING, Category.LOGIC, False,
      lambda fp: (not _ne(fp.get("rehospital_purpose"))) or str(fp.get("rehospital_plan")).strip() == "2")

    # 身份证交叉验证
    R("27", "证件号码", "身份证出生日期一致", "身份证号码的出生日期与填写的出生日期不一致",
      Severity.WARNING, Category.LOGIC, False,
      lambda fp: _check_id_birthday(fp))

    # 性别-诊断一致性 (最复杂的规则)
    R("135", "性别", "男性诊断性别校验", "性别为男，诊断编码与性别不符",
      Severity.ERROR, Category.CONSISTENCY, True,
      lambda fp: _check_all_diag_sex(fp, "1"))

    R("136", "性别", "女性诊断性别校验", "性别为女，诊断编码与性别不符",
      Severity.ERROR, Category.CONSISTENCY, True,
      lambda fp: _check_all_diag_sex(fp, "2"))

    R("113", "性别", "身份证性别校验女", "性别（女）与身份证校验不符",
      Severity.ERROR, Category.LOGIC, True,
      lambda fp: _check_id_sex(fp))

    # 分娩结局
    R("122", "诊断代码", "分娩需Z37结局", "分娩诊断应有Z37结局编码",
      Severity.ERROR, Category.LOGIC, True,
      lambda fp: _check_delivery_z37(fp))

    # 新生儿逻辑
    R("75", "新生儿出生体重", "新生儿体重必填", "不足1周岁28天内，新生儿出生体重不能为空",
      Severity.ERROR, Category.LOGIC, True,
      lambda fp: _check_newborn_weight_required(fp))

    R("77", "新生儿入院类型", "非新生儿无需填", "非新生儿不需要填写新生儿入院类型",
      Severity.WARNING, Category.LOGIC, False,
      lambda fp: (not _ne(fp.get("newborn_type"))) or _to_num(fp.get("age") or 999) == 0)

    R("80", "新生儿入院体重", "新生儿入院体重联动", "入院新生儿应填写新生儿入院体重",
      Severity.WARNING, Category.LOGIC, False,
      lambda fp: (not _ne(fp.get("newborn_type"))) or _ne(fp.get("newborn_admission_weight")))

    R("118", "诊断代码", "产妇Z37需新生儿体重",
      "产妇诊断含Z37编码时必填新生儿出生体重",
      Severity.ERROR, Category.LOGIC, True,
      lambda fp: _check_z37_newborn_weight(fp))

    # 住院医疗类型
    R("108", "住院医疗类型", "日间手术须有手术", "住院医疗类型为日间手术应填写手术操作",
      Severity.WARNING, Category.LOGIC, False,
      lambda fp: (str(fp.get("medical_type")).strip() != "2") or len(_get_surgeries(fp)) > 0)

    R("111", "住院医疗类型", "日间手术天数", "住院天数大于2时不应填写日间手术",
      Severity.WARNING, Category.LOGIC, False,
      lambda fp: (str(fp.get("medical_type")).strip() != "2") or
                 (not _is_number(fp.get("actual_hospital_days"))) or
                 _to_num(fp.get("actual_hospital_days")) <= 2)

    # 转院逻辑
    R("89", "转院机构", "转院须填机构", "离院方式为医嘱转院患者，必填拟接收机构名称",
      Severity.WARNING, Category.LOGIC, False,
      lambda fp: (str(fp.get("leaving_hospital_way")).strip() != "2") or
                 _ne(fp.get("transfer_hospital")))

    # 呼吸机
    R("23", "呼吸机使用时间", "呼吸机需护理级别", "使用了呼吸机的患者需填写对应护理级别天数",
      Severity.WARNING, Category.LOGIC, False,
      lambda fp: (not _ne(fp.get("ventilation_hours"))) or
                 _ne(fp.get("special_care_days")) or _ne(fp.get("first_level_care_days")))

    # 输血
    R("130", "输血品种", "输血品种值域", "输血品种不在代码表范围内",
      Severity.WARNING, Category.FORMAT, False,
      lambda fp: (not _ne(fp.get("transfusion_type"))) or
                 str(fp.get("transfusion_type")).strip() in TRANSFUSION_CODES)

    R("131", "输血量", "输血量联动", "填写输血品种时必须有输血量且>0",
      Severity.WARNING, Category.LOGIC, False,
      lambda fp: (not _ne(fp.get("transfusion_type"))) or
                 (_is_number(fp.get("transfusion_amount")) and _to_num(fp.get("transfusion_amount")) > 0))

    # P10-P15 年龄校验
    R("120", "诊断代码", "围产期诊断年龄", "诊断编码P10-P15，入院日期减出生日期必须小于365天",
      Severity.ERROR, Category.LOGIC, True,
      lambda fp: _check_perinatal_age(fp))

    return rules


# ============================================================
# 复杂校验辅助函数
# ============================================================

def _check_diag_duplicate(fp: dict) -> bool:
    """诊断编码/名称不应重复。"""
    diags = _get_diagnoses(fp)
    codes = [_diag_code(d) for d in diags if _diag_code(d)]
    names = [_diag_name(d) for d in diags if _diag_name(d)]
    return len(codes) == len(set(codes)) and len(names) == len(set(names))

def _check_surgery_duplicate(fp: dict) -> bool:
    """手术编码/名称不应重复。"""
    surgs = _get_surgeries(fp)
    codes = [_surg_code(s) for s in surgs if _surg_code(s)]
    names = [_surg_name(s) for s in surgs if _surg_name(s)]
    return len(codes) == len(set(codes)) and len(names) == len(set(names))

def _check_surgery_in_range(fp: dict) -> bool:
    """手术日期应在入院-1天到出院之间。"""
    admit = _parse_dt(fp.get("admission_datetime"))
    discharge = _parse_dt(fp.get("discharge_datetime"))
    if not admit or not discharge:
        return True
    for s in _get_surgeries(fp):
        sdt = _parse_dt(s.get("date") or s.get("start_time"))
        if sdt:
            from datetime import timedelta
            if sdt < admit - timedelta(days=1) or sdt > discharge:
                return False
    return True

def _check_icu_completeness(fp: dict) -> bool:
    """ICU 四项同时为空或同时不为空。"""
    fields = [fp.get("icu_type"), fp.get("icu_enter_time"),
              fp.get("icu_leave_time"), fp.get("icu_total_hours")]
    filled = [_ne(f) for f in fields]
    return all(filled) or not any(filled)

def _check_icu_time_order(fp: dict) -> bool:
    """进ICU时间 ≤ 出ICU时间。"""
    enter = _parse_dt(fp.get("icu_enter_time"))
    leave = _parse_dt(fp.get("icu_leave_time"))
    if not enter or not leave:
        return True
    return enter <= leave

def _check_icu_in_range(fp: dict, time_field: str) -> bool:
    """ICU 时间应在入出院范围内。"""
    t = _parse_dt(fp.get(time_field))
    if not t:
        return True
    admit = _parse_dt(fp.get("admission_datetime"))
    discharge = _parse_dt(fp.get("discharge_datetime"))
    if admit and t < admit:
        return False
    if discharge and t > discharge:
        return False
    return True

def _check_id_birthday(fp: dict) -> bool:
    """身份证出生日期与填写出生日期一致。"""
    id_card = str(fp.get("id_number") or "").strip()
    birth = str(fp.get("birth_date") or "").strip().replace("-", "")
    if len(id_card) == 18 and birth:
        return id_card[6:14] == birth[:8]
    if len(id_card) == 15 and birth:
        return "19" + id_card[6:12] == birth[:8]
    return True

def _check_id_sex(fp: dict) -> bool:
    """身份证性别与填写性别一致。"""
    id_card = str(fp.get("id_number") or "").strip()
    sex = _get_sex(fp)
    if not sex or not id_card:
        return True
    if len(id_card) == 18:
        id_sex = "1" if int(id_card[16]) % 2 == 1 else "2"
        return id_sex == sex
    if len(id_card) == 15:
        id_sex = "1" if int(id_card[14]) % 2 == 1 else "2"
        return id_sex == sex
    return True

def _check_all_diag_sex(fp: dict, target_sex: str) -> bool:
    """全部诊断与性别一致性。"""
    sex = _get_sex(fp)
    if sex != target_sex:
        return True
    for d in _get_diagnoses(fp):
        code = _diag_code(d)
        name = _diag_name(d)
        if code or name:
            msg = _check_sex_diag_match(sex, code, name)
            if msg:
                return False
    return True

def _check_delivery_z37(fp: dict) -> bool:
    """分娩诊断 O80-O84 需要 Z37 结局编码。"""
    codes = [_diag_code(d) for d in _get_diagnoses(fp)]
    has_delivery = any(c[:3] in ("O80", "O81", "O82", "O83", "O84") for c in codes if len(c) >= 3)
    has_abortion = any(c[0] == "O" and c[1:3].isdigit() and int(c[1:3]) <= 8 for c in codes if len(c) >= 3)
    if not has_delivery or has_abortion:
        return True
    return any(c.startswith("Z37") for c in codes)

def _check_newborn_weight_required(fp: dict) -> bool:
    """新生儿28天内需填出生体重。"""
    age = _to_num(fp.get("age") or fp.get("age_years"))
    day_age = _to_num(fp.get("age_days"))
    if age is not None and age == 0 and day_age is not None and 0 < day_age <= 28:
        return _ne(fp.get("newborn_birth_weight"))
    return True

def _check_z37_newborn_weight(fp: dict) -> bool:
    """诊断含 Z37 时需填新生儿出生体重。"""
    codes = [_diag_code(d) for d in _get_diagnoses(fp)]
    z37_codes = ["Z37.0", "Z37.2", "Z37.3", "Z37.5", "Z37.6"]
    has_z37 = any(any(c.startswith(z) for z in z37_codes) for c in codes)
    if not has_z37:
        return True
    return _ne(fp.get("newborn_birth_weight"))

def _check_perinatal_age(fp: dict) -> bool:
    """P10-P15 编码需年龄<1岁。"""
    codes = [_diag_code(d) for d in _get_diagnoses(fp)]
    has_p10_15 = any(c[:3] in ("P10", "P11", "P12", "P13", "P14", "P15") for c in codes if len(c) >= 3)
    if not has_p10_15:
        return True
    admit = _parse_dt(fp.get("admission_datetime"))
    birth = _parse_dt(fp.get("birth_date"))
    if admit and birth:
        return (admit - birth).days < 365
    return True


# ============================================================
# 引擎主类
# ============================================================

class SettlementFormalQCEngine:
    """医保结算清单形式质控引擎。"""

    def __init__(self):
        self.rules = _build_rules()
        logger.info(f"SettlementFormalQCEngine 初始化: {len(self.rules)} 条规则")

    def check(self, settlement: dict) -> SettlementQCReport:
        """
        对结算清单数据执行全量形式质控。

        Args:
            settlement: 结算清单数据字典

        Returns:
            SettlementQCReport
        """
        report = SettlementQCReport(total_rules=len(self.rules))
        for rule in self.rules:
            try:
                passed = rule.validate(settlement)
            except Exception as e:
                logger.warning(f"规则 {rule.rule_id} 执行异常: {e}")
                passed = True  # 异常时不误报

            msg = "" if passed else rule.message(settlement)
            result = SettlementQCResult(
                rule_id=rule.rule_id,
                field_name=rule.field_name,
                rule_name=rule.rule_name,
                passed=passed,
                message=msg,
                severity=rule.severity,
                category=rule.category,
                affects_grouping=rule.affects_grouping,
            )
            report.results.append(result)
            if passed:
                report.passed += 1
            else:
                report.failed += 1

        logger.info(
            f"结算清单质控完成: {report.total_rules} 条规则, "
            f"{report.passed} 通过, {report.failed} 不通过"
        )
        return report

    def get_rules_summary(self) -> dict:
        """返回规则摘要。"""
        categories = {}
        for r in self.rules:
            categories.setdefault(r.category, []).append({
                "rule_id": r.rule_id,
                "field": r.field_name,
                "name": r.rule_name,
                "affects_grouping": r.affects_grouping,
            })
        return {
            "total": len(self.rules),
            "by_category": {k: len(v) for k, v in categories.items()},
            "rules": categories,
        }
