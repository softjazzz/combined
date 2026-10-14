"""首页质控 V2：规则目录。

编号与 docs/frontpage-qc-v2/rule-catalog-review.md 一致：
C-* 完整性（76 项必填），S-* 规范性（取值合法），L-* 逻辑一致性。
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple

from . import values as v
from .config import SOURCE_GAP_FIELDS, SOURCE_GAP_REASON
from .document import DiagnosisItem, FrontpageDoc, SurgeryItem
from .model import (
    Detail,
    Rule,
    RuleEval,
    Severity,
    data_gap,
    failed,
    not_applicable,
    passed,
)

BASIS_FILL = "填写说明（2016版）：必填栏不能为空，无内容时填“—”"
BASIS_CODE = "住院病案首页部分项目填写说明（2016版）"
NEED_FILL = "必填；无内容时填“-”"

_RULES: List[Rule] = []


def _add(rule: Rule) -> None:
    _RULES.append(rule)


def _disabled(rule_id: str, name: str, section: str, reason: str, score_item: Optional[str] = None) -> None:
    _add(
        Rule(
            rule_id=rule_id,
            name=name,
            group="completeness",
            section=section,
            severity=Severity.REQUIRED if score_item is None else Severity.DEDUCT,
            score_item=score_item,
            basis=BASIS_FILL,
            problem=f"{name}未填写",
            enabled=False,
            disabled_reason=reason,
        )
    )


# ---------------- 通用检查 ----------------


def _require_value(value: str, field_key: str, label: str) -> RuleEval:
    if v.is_filled(value):
        return passed()
    detail = Detail(label, value, NEED_FILL)
    if field_key in SOURCE_GAP_FIELDS:
        return data_gap(SOURCE_GAP_REASON, detail)
    return failed(detail)


def _require_basic(field_key: str, label: str) -> Callable[[FrontpageDoc], RuleEval]:
    return lambda doc: _require_value(doc.get(field_key), field_key, label)


def _basic_rule(
    rule_id: str,
    label: str,
    field_key: str,
    section: str,
    severity: Severity,
    score_item: Optional[str] = None,
) -> None:
    _add(
        Rule(
            rule_id=rule_id,
            name=f"{label}非空",
            group="completeness",
            section=section,
            severity=severity,
            score_item=score_item,
            basis=BASIS_FILL,
            problem=f"{label}未填写",
            check=_require_basic(field_key, label),
        )
    )


def _code_value_rule(
    rule_id: str,
    label: str,
    field_key: str,
    table: Dict[str, str],
    expected: str,
    section: str,
    score_item: Optional[str],
    severity: Severity = Severity.DEDUCT,
) -> None:
    def check(doc: FrontpageDoc) -> RuleEval:
        value = doc.get(field_key)
        if not v.has_content(value):
            return not_applicable("未填写，由完整性规则判断")
        if v.normalize_code(value, table) is None:
            return failed(Detail(label, value, expected))
        return passed()

    _add(
        Rule(
            rule_id=rule_id,
            name=f"{label}取值规范",
            group="specification",
            section=section,
            severity=severity,
            score_item=score_item,
            basis=BASIS_CODE,
            problem=f"{label}取值不符合填写说明",
            check=check,
        )
    )


def _diag_label(item: DiagnosisItem) -> str:
    return f"出院诊断第{item.index + 1}条（{item.name or '未命名'}）"


# ================= 一、完整性：患者基本信息 =================

_basic_rule("C-P01", "医疗付费方式", "medical_payment_method", "patient", Severity.DEDUCT, "payment")
_disabled("C-P02", "健康卡号", "patient", "库中无该字段；填写说明允许未发放健康卡地区不填")
_basic_rule("C-P03", "病案号", "mr_no", "patient", Severity.DEDUCT, "mr_no")
_basic_rule("C-P04", "患者姓名", "name", "patient", Severity.DEDUCT, "name")
_basic_rule("C-P05", "性别", "sex", "patient", Severity.DEDUCT, "sex")
_basic_rule("C-P06", "出生日期", "birthday", "patient", Severity.DEDUCT, "birthday")
_basic_rule("C-P07", "年龄", "age", "patient", Severity.DEDUCT, "age")
_basic_rule("C-P08", "国籍", "nationality", "patient", Severity.REQUIRED)
_disabled("C-P09", "出生地", "patient", "库中无该字段")
_disabled("C-P10", "籍贯", "patient", "本院不采集（真实首页填充率 0%）")
_basic_rule("C-P11", "民族", "ethnicity", "patient", Severity.DEDUCT, "ethnicity")
_basic_rule("C-P12", "身份证号", "id_card_no", "patient", Severity.DEDUCT, "id_card")
_disabled("C-P13", "职业", "patient", "本院不采集（真实首页填充率 1%）")
_basic_rule("C-P14", "婚姻状况", "marital_status", "patient", Severity.DEDUCT, "marital")
_basic_rule("C-P15", "现住址", "currentaddress", "patient", Severity.DEDUCT, "current_address")
_disabled("C-P16", "现住址电话", "patient", "无可确认的对应字段（contact_number 含义不明）")
_disabled("C-P17", "现住址邮编", "patient", "库中无该字段")
_disabled("C-P18", "户口地址", "patient", "库中无该字段")
_disabled("C-P19", "户口地址邮编", "patient", "库中无该字段")
_disabled("C-P20", "工作单位及地址", "patient", "本院不采集（真实首页填充率 0%）")
_disabled("C-P21", "工作单位电话", "patient", "库中无该字段")
_disabled("C-P22", "工作单位邮编", "patient", "库中无该字段")
_basic_rule("C-P23", "联系人姓名", "contact_name", "patient", Severity.DEDUCT, "contact_name")
_basic_rule("C-P24", "联系人关系", "contact_relationship", "patient", Severity.DEDUCT, "contact_relation")
_basic_rule("C-P25", "联系人地址", "contact_address", "patient", Severity.DEDUCT, "contact_address")
_basic_rule("C-P26", "联系人电话", "contact_telephone", "patient", Severity.DEDUCT, "contact_phone")
_disabled("C-P27", "新生儿出生体重", "patient", "库中无该字段", "newborn_birth_weight")
_disabled("C-P28", "新生儿入院体重", "patient", "库中无该字段", "newborn_admission_weight")

# ================= 一、完整性：住院过程信息 =================

def _check_institute(doc: FrontpageDoc) -> RuleEval:
    # 真实首页机构名称列为空，但机构号即机构名称（如“泸县人民医院”），两者有一即可
    value = doc.get("institute_county_desc") or doc.get("institute_id")
    return _require_value(value, "institute_county_desc", "医疗机构")


_add(
    Rule(
        rule_id="C-H01",
        name="医疗机构非空",
        group="completeness",
        section="hospitalization",
        severity=Severity.REQUIRED,
        score_item=None,
        basis=BASIS_FILL,
        problem="医疗机构未填写",
        check=_check_institute,
    )
)
_basic_rule("C-H02", "组织机构代码", "institute_code", "hospitalization", Severity.REQUIRED)
_basic_rule("C-H03", "第N次住院", "visit_cnt", "hospitalization", Severity.REQUIRED)
_basic_rule("C-H04", "入院途径", "admission_route", "hospitalization", Severity.DEDUCT, "admission_route")
_basic_rule("C-H05", "入院时间", "admission_datetime", "hospitalization", Severity.DEDUCT, "admission_time")
_basic_rule("C-H06", "入院科别", "admission_dept_name", "hospitalization", Severity.DEDUCT, "admission_dept")
_basic_rule("C-H07", "入院病房", "admission_ward_name", "hospitalization", Severity.REQUIRED)
_basic_rule("C-H08", "转科科别", "transfer_dept_name", "hospitalization", Severity.DEDUCT, "transfer_dept")
_basic_rule("C-H09", "出院时间", "discharge_datetime", "hospitalization", Severity.DEDUCT, "discharge_time")
_basic_rule("C-H10", "出院科别", "discharge_dept_name", "hospitalization", Severity.DEDUCT, "discharge_dept")
_basic_rule("C-H11", "出院病房", "discharge_ward_name", "hospitalization", Severity.REQUIRED)
_basic_rule("C-H12", "实际住院天数", "hospital_duration", "hospitalization", Severity.DEDUCT, "los")
_basic_rule("C-H13", "科主任", "deptdirector_sign", "hospitalization", Severity.REQUIRED)
_basic_rule("C-H14", "主任（副主任）医师", "chief_physician_sign", "hospitalization", Severity.REQUIRED)
_basic_rule("C-H15", "主治医师", "attending_physician_sign", "hospitalization", Severity.REQUIRED)
_basic_rule("C-H16", "住院医师", "resident_physician_sign", "hospitalization", Severity.REQUIRED)
_basic_rule("C-H17", "责任护士", "responsible_nurse_sign", "hospitalization", Severity.REQUIRED)
_basic_rule("C-H18", "编码员", "coder_sign", "hospitalization", Severity.REQUIRED)

_NO_SURGERY = "无手术或操作"


def looks_like_operation(surgery: SurgeryItem) -> bool:
    """手术级别和切口类别都未填写：多为操作（如导尿、喉镜检查），已确认只提示不扣分。"""
    return not v.is_filled(surgery.raw_level) and not v.is_filled(surgery.raw_incision)


_OPERATION_ONLY_HINT = "疑似操作（手术级别和切口均未填），由 C-D20/C-D27 提示核实"


def _main_surgery_field(attr: str, label: str, skip_for_operation: bool = False) -> Callable[[FrontpageDoc], RuleEval]:
    def check(doc: FrontpageDoc) -> RuleEval:
        surgery = doc.main_surgery
        if surgery is None:
            return not_applicable(_NO_SURGERY)
        value = getattr(surgery, attr)
        if skip_for_operation and not v.is_filled(value) and looks_like_operation(surgery):
            return not_applicable(_OPERATION_ONLY_HINT)
        if v.is_filled(value):
            return passed()
        return failed(Detail(f"主要手术（{surgery.name or surgery.code}）{label}", value, NEED_FILL, 0))

    return check


def _surgery_rule(
    rule_id: str,
    label: str,
    attr: str,
    severity: Severity,
    score_item: Optional[str],
    group: str = "completeness",
    skip_for_operation: bool = False,
) -> None:
    _add(
        Rule(
            rule_id=rule_id,
            name=f"主要手术{label}非空",
            group=group,
            section="hospitalization" if rule_id.startswith("C-H") else "diagnosis",
            severity=severity,
            score_item=score_item,
            basis=BASIS_FILL,
            problem=f"主要手术{label}未填写",
            check=_main_surgery_field(attr, label, skip_for_operation),
            condition="有手术或操作时",
        )
    )


_surgery_rule("C-H19", "日期", "begin_at_raw", Severity.DEDUCT, "surgery_date")
_surgery_rule("C-H20", "术者", "surgeon", Severity.DEDUCT, "surgeon")
_surgery_rule("C-H21", "Ⅰ助", "first_assistant", Severity.DEDUCT, "first_assistant", skip_for_operation=True)
_surgery_rule("C-H22", "Ⅱ助", "second_assistant", Severity.REQUIRED, None, skip_for_operation=True)

_LOCAL_ANESTHESIA_KEYWORDS = ("局部", "局麻", "表面麻醉", "浸润")


def _check_anesthesiologist(doc: FrontpageDoc) -> RuleEval:
    surgery = doc.main_surgery
    if surgery is None:
        return not_applicable(_NO_SURGERY)
    method = surgery.anesthesia_method
    if not v.is_filled(method) and looks_like_operation(surgery):
        return not_applicable(_OPERATION_ONLY_HINT)
    if not v.has_content(method) or any(key in method for key in _LOCAL_ANESTHESIA_KEYWORDS):
        return not_applicable("无麻醉或局部麻醉")
    if v.is_filled(surgery.anesthesiologist):
        return passed()
    return failed(Detail(f"主要手术（{surgery.name or surgery.code}）麻醉医师", surgery.anesthesiologist, NEED_FILL, 0))


_add(
    Rule(
        rule_id="C-H23",
        name="主要手术麻醉医师非空",
        group="completeness",
        section="hospitalization",
        severity=Severity.REQUIRED,
        score_item=None,
        basis=BASIS_FILL,
        problem="主要手术麻醉医师未填写",
        check=_check_anesthesiologist,
        condition="有手术且麻醉方式不是局部麻醉时",
    )
)
_basic_rule("C-H24", "离院方式", "leaving_hospital_way", "hospitalization", Severity.DEDUCT, "leaving_way")
_basic_rule("C-H25", "31天内再住院计划", "rehospital_with_month", "hospitalization", Severity.DEDUCT, "readmission")
_disabled("C-H26", "日常生活能力评定量表得分（入院）", "hospitalization", "库中无该字段")
_disabled("C-H27", "日常生活能力评定量表得分（出院）", "hospitalization", "库中无该字段")
_disabled("C-H28", "质控医师", "hospitalization", "已确认停用")
_disabled("C-H29", "质控护士", "hospitalization", "已确认停用")
_disabled("C-H30", "质控日期", "hospitalization", "已确认停用")

# ================= 一、完整性：诊疗信息 =================

_NO_DISCHARGE_DIAGNOSIS = "首页没有出院诊断记录"


def _check_outpatient_name(doc: FrontpageDoc) -> RuleEval:
    if any(v.is_filled(item.name) for item in doc.outpatient_diagnoses):
        return passed()
    return failed(Detail("门（急）诊诊断", "", NEED_FILL))


def _check_outpatient_code(doc: FrontpageDoc) -> RuleEval:
    if not doc.outpatient_diagnoses:
        return not_applicable("无门（急）诊诊断，由 C-D01 判断")
    missing = [item for item in doc.outpatient_diagnoses if not v.has_content(item.code)]
    if not missing:
        return passed()
    return failed(*(Detail(f"门（急）诊诊断（{item.name}）编码", item.code, "填写 ICD-10 编码") for item in missing))


def _with_main(check: Callable[[FrontpageDoc, DiagnosisItem], RuleEval]) -> Callable[[FrontpageDoc], RuleEval]:
    def wrapper(doc: FrontpageDoc) -> RuleEval:
        if not doc.discharge_diagnoses:
            return data_gap(_NO_DISCHARGE_DIAGNOSIS)
        main = doc.main_diagnosis
        if main is None:
            return not_applicable("未标记主要诊断，由 C-D03 判断")
        return check(doc, main)

    return wrapper


def _check_main_present(doc: FrontpageDoc) -> RuleEval:
    if not doc.discharge_diagnoses:
        return data_gap(_NO_DISCHARGE_DIAGNOSIS)
    main = doc.main_diagnosis
    if main is None:
        return failed(Detail("出院主要诊断", "", "出院诊断中须标记一条主要诊断"))
    if not v.has_content(main.name):
        return failed(Detail("出院主要诊断名称", main.name, "填写主要诊断名称", main.index))
    return passed()


def _main_field(attr: str, label: str, expected: str) -> Callable[[FrontpageDoc], RuleEval]:
    def check(doc: FrontpageDoc, main: DiagnosisItem) -> RuleEval:
        value = getattr(main, attr)
        if v.is_filled(value):
            return passed()
        return failed(Detail(f"主要诊断（{main.name}）{label}", value, expected, main.index))

    return _with_main(check)


def _other_field(attr: str, label: str, expected: str, need_content: bool) -> Callable[[FrontpageDoc], RuleEval]:
    def check(doc: FrontpageDoc) -> RuleEval:
        if not doc.discharge_diagnoses:
            return data_gap(_NO_DISCHARGE_DIAGNOSIS)
        others = doc.other_diagnoses
        if not others:
            return not_applicable("无其他诊断")
        test = v.has_content if need_content else v.is_filled
        missing = [item for item in others if not test(getattr(item, attr))]
        if not missing:
            return passed()
        return failed(*(Detail(f"{_diag_label(item)}{label}", getattr(item, attr), expected, item.index) for item in missing))

    return check


def _diag_rule(rule_id: str, name: str, check, severity: Severity, score_item: Optional[str], problem: str, condition: str = "") -> None:
    _add(
        Rule(
            rule_id=rule_id,
            name=name,
            group="completeness",
            section="diagnosis",
            severity=severity,
            score_item=score_item,
            basis=BASIS_FILL,
            problem=problem,
            check=check,
            condition=condition,
        )
    )


_diag_rule("C-D01", "门（急）诊诊断非空", _check_outpatient_name, Severity.DEDUCT, "outpatient_diag", "缺少门（急）诊诊断")
_diag_rule("C-D02", "门（急）诊诊断编码非空", _check_outpatient_code, Severity.DEDUCT, "outpatient_code", "门（急）诊诊断缺少编码")
_diag_rule("C-D03", "出院主要诊断非空", _check_main_present, Severity.DEDUCT, "main_diag_name", "缺少出院主要诊断")
_diag_rule(
    "C-D04",
    "主要诊断入院病情非空",
    _main_field("raw_admission_condition", "入院病情", "填写 1有/2临床未确定/3情况不明/4无"),
    Severity.DEDUCT,
    "admission_condition",
    "主要诊断入院病情未填写",
)
_diag_rule(
    "C-D05",
    "主要诊断出院情况非空",
    _main_field("raw_discharge_condition", "出院情况", "填写 1治愈/2好转/3未愈/4死亡/9其他"),
    Severity.REQUIRED,
    None,
    "主要诊断出院情况未填写",
)


def _check_main_code(doc: FrontpageDoc, main: DiagnosisItem) -> RuleEval:
    if v.has_content(main.code):
        return passed()
    return failed(Detail(f"主要诊断（{main.name}）编码", main.code, "填写 ICD-10 编码", main.index))


_diag_rule("C-D06", "主要诊断编码非空", _with_main(_check_main_code), Severity.DEDUCT, "main_diag_code", "主要诊断缺少编码")
_diag_rule("C-D07", "其他诊断名称非空", _other_field("name", "名称", "填写诊断名称", True), Severity.DEDUCT, "other_diag_name", "其他诊断缺少名称")
_diag_rule("C-D08", "其他诊断编码非空", _other_field("code", "编码", "填写 ICD-10 编码", True), Severity.DEDUCT, "other_diag_code", "其他诊断缺少编码")
_diag_rule(
    "C-D09",
    "其他诊断入院病情非空",
    _other_field("raw_admission_condition", "入院病情", "填写 1有/2临床未确定/3情况不明/4无", False),
    Severity.REQUIRED,
    None,
    "其他诊断入院病情未填写",
)


def _check_external_cause(doc: FrontpageDoc) -> RuleEval:
    injuries = [item for item in doc.discharge_diagnoses if v.icd10_head(item.code)[:1] in ("S", "T")]
    if not injuries:
        return not_applicable("无损伤、中毒诊断")
    if any(v.is_external_cause(item.code) for item in doc.discharge_diagnoses):
        return passed()
    first = injuries[0]
    detail = Detail(f"{_diag_label(first)}对应的外部原因", "", "有损伤、中毒诊断时，须填写 V01–Y98 外部原因编码", first.index)
    if "external_cause" in SOURCE_GAP_FIELDS:
        return data_gap(SOURCE_GAP_REASON, detail)
    return failed(detail)


_diag_rule(
    "C-D10",
    "损伤中毒外部原因及编码",
    _check_external_cause,
    Severity.DEDUCT,
    "external_cause",
    "有损伤、中毒诊断但缺少外部原因编码",
    condition="有 S/T 章诊断时",
)


def _check_pathology_no(doc: FrontpageDoc) -> RuleEval:
    if not doc.pathology_diagnoses:
        return not_applicable("无病理诊断")
    missing = [item for item in doc.pathology_diagnoses if not v.is_filled(item.pathology_no)]
    if not missing:
        return passed()
    details = [Detail(f"病理诊断（{item.name}）病理号", item.pathology_no, NEED_FILL) for item in missing]
    if "pathology_no" in SOURCE_GAP_FIELDS:
        return data_gap(SOURCE_GAP_REASON, *details)
    return failed(*details)


_diag_rule("C-D11", "病理号非空", _check_pathology_no, Severity.DEDUCT, "pathology_no", "病理诊断缺少病理号", condition="有病理诊断时")


def _pathology_fee(doc: FrontpageDoc) -> Optional[float]:
    if doc.cost is None:
        return None
    return v.parse_number(doc.cost.get("pathological_diagnostic_fee"))


def _check_pathology_diag(doc: FrontpageDoc) -> RuleEval:
    if doc.pathology_diagnoses:
        return passed()
    fee = _pathology_fee(doc)
    if fee is None or fee <= 0:
        return not_applicable("无病理诊断费用")
    return failed(Detail("病理诊断", "", f"有病理诊断费用（{fee:g} 元）时须填写病理诊断"))


_diag_rule(
    "C-D12",
    "病理诊断非空",
    _check_pathology_diag,
    Severity.HINT,
    None,
    "有病理诊断费用但缺少病理诊断（病理结果可能出院后才出，请核实）",
    condition="有病理诊断费用时",
)


def _check_pathology_code(doc: FrontpageDoc) -> RuleEval:
    if not doc.pathology_diagnoses:
        return not_applicable("无病理诊断")
    # 非肿瘤病理（如胆囊炎、前列腺增生）没有形态学编码，填“-”合规
    bad = [
        item
        for item in doc.pathology_diagnoses
        if not v.is_filled(item.code)
        or (v.has_content(item.code) and not (v.is_morphology(item.code) or v.is_icd10(item.code)))
    ]
    if not bad:
        return passed()
    return failed(*(Detail(f"病理诊断（{item.name}）编码", item.code, "肿瘤填写形态学 M 编码（如 M8140/3）；非肿瘤病理填“-”") for item in bad))


_diag_rule(
    "C-D13",
    "病理诊断编码",
    _check_pathology_code,
    Severity.DEDUCT,
    "pathology_code",
    "病理诊断编码缺失或格式不正确",
    condition="有病理诊断时",
)
_basic_rule("C-D14", "有无药物过敏", "allergy_sign", "diagnosis", Severity.DEDUCT, "allergy")
_basic_rule("C-D15", "ABO血型", "abo_blood_code", "diagnosis", Severity.DEDUCT, "blood")
_basic_rule("C-D16", "Rh血型", "rh_blood_code", "diagnosis", Severity.DEDUCT, "blood")


def _check_main_surgery_name(doc: FrontpageDoc) -> RuleEval:
    surgery = doc.main_surgery
    if surgery is None:
        return not_applicable(_NO_SURGERY)
    if v.has_content(surgery.name):
        return passed()
    return failed(Detail("主要手术名称", surgery.name, "填写手术或操作名称", 0))


def _check_main_surgery_code(doc: FrontpageDoc) -> RuleEval:
    surgery = doc.main_surgery
    if surgery is None:
        return not_applicable(_NO_SURGERY)
    if v.has_content(surgery.code):
        return passed()
    return failed(Detail(f"主要手术（{surgery.name}）编码", surgery.code, "填写 ICD-9-CM-3 编码", 0))


def _other_surgery_field(attr: str, label: str, expected: str) -> Callable[[FrontpageDoc], RuleEval]:
    def check(doc: FrontpageDoc) -> RuleEval:
        others = doc.other_surgeries
        if not others:
            return not_applicable("无其他手术或操作")
        missing = [item for item in others if not v.has_content(getattr(item, attr))]
        if not missing:
            return passed()
        return failed(
            *(Detail(f"手术第{item.index + 1}条（{item.name or item.code}）{label}", getattr(item, attr), expected, item.index) for item in missing)
        )

    return check


_diag_rule("C-D17", "主要手术名称非空", _check_main_surgery_name, Severity.DEDUCT, "main_surgery_name", "缺少主要手术名称", condition="有手术或操作时")
_diag_rule("C-D18", "主要手术编码非空", _check_main_surgery_code, Severity.DEDUCT, "main_surgery_code", "主要手术缺少编码", condition="有手术或操作时")
_diag_rule(
    "C-D19",
    "其他手术名称非空",
    _other_surgery_field("name", "名称", "填写手术或操作名称"),
    Severity.DEDUCT,
    "other_surgery_name",
    "其他手术缺少名称",
    condition="有多条手术或操作时",
)


def _check_surgery_level_present(doc: FrontpageDoc) -> RuleEval:
    surgery = doc.main_surgery
    if surgery is None:
        return not_applicable(_NO_SURGERY)
    value = surgery.raw_level
    if v.is_filled(value) and value not in v.SURGICAL_LEVEL_UNSET:
        return passed()
    return failed(Detail(f"主要手术（{surgery.name or surgery.code}）手术级别", value, "手术须填写 1–4 级；操作可填“-”", 0))


_diag_rule(
    "C-D20",
    "主要手术级别未填",
    _check_surgery_level_present,
    Severity.HINT,
    None,
    "主要手术级别为空或未定级（可能是操作，请核实）",
    condition="有手术或操作时",
)


def _check_incision_healing(doc: FrontpageDoc) -> RuleEval:
    surgery = doc.main_surgery
    if surgery is None:
        return not_applicable(_NO_SURGERY)
    incision = v.normalize_code(surgery.raw_incision, v.INCISION_CLASS)
    if incision in (None, "0"):
        return not_applicable("无切口或 0 类切口")
    if v.has_content(surgery.raw_healing):
        return passed()
    return failed(Detail(f"主要手术（{surgery.name or surgery.code}）切口愈合等级", surgery.raw_healing, "Ⅰ–Ⅲ类切口须填写愈合等级：甲/乙/丙/其他", 0))


_diag_rule(
    "C-D21",
    "切口愈合等级非空",
    _check_incision_healing,
    Severity.DEDUCT,
    "incision_heal",
    "Ⅰ–Ⅲ类切口缺少愈合等级",
    condition="主要手术为Ⅰ–Ⅲ类切口时",
)
_surgery_rule("C-D22", "麻醉方式", "anesthesia_method", Severity.DEDUCT, "anesthesia", skip_for_operation=True)
_disabled("C-D23", "颅脑损伤患者昏迷时间", "diagnosis", "库中无该字段", "coma_time")
_disabled("C-D24", "重症监护室名称及进出时间", "diagnosis", "库中无该字段")
_basic_rule("C-D25", "死亡患者尸检", "death_autopsy_sign", "diagnosis", Severity.DEDUCT, "autopsy")
_diag_rule(
    "C-D26",
    "其他手术编码非空",
    _other_surgery_field("code", "编码", "填写 ICD-9-CM-3 编码"),
    Severity.DEDUCT,
    "other_surgery_code",
    "其他手术缺少编码",
    condition="有多条手术或操作时",
)


def _check_incision_present(doc: FrontpageDoc) -> RuleEval:
    surgery = doc.main_surgery
    if surgery is None:
        return not_applicable(_NO_SURGERY)
    if v.is_filled(surgery.raw_incision):
        return passed()
    return failed(Detail(f"主要手术（{surgery.name or surgery.code}）切口类别", "", "手术须填写 0/Ⅰ/Ⅱ/Ⅲ 类；操作可填“-”", 0))


_diag_rule(
    "C-D27",
    "主要手术切口类别未填",
    _check_incision_present,
    Severity.HINT,
    None,
    "主要手术切口类别为空（可能是操作，请核实）",
    condition="有手术或操作时",
)

# ================= 一、完整性：费用信息 =================

_NO_COST = "首页没有费用记录"

FEE_CATEGORIES: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("综合医疗服务类", ("general_medical_service_fee", "general_treatment_fee", "nursing_care_fee", "other_service_fee")),
    ("诊断类", ("pathological_diagnostic_fee", "laboratory_diagnostic_fee", "imaging_diagnostic_fee", "clinical_diagnostic_fee")),
    ("治疗类", ("nonsurgical_treatment_fee", "surgery_treatment_fee")),
    ("康复类", ("rehabilitation_fee",)),
    ("西药类", ("western_medicine_fee",)),
    ("中药类", ("chinese_patent_medcine_fee", "chinese_herbal_medicine_fee")),
    ("血液和血液制品类", ("blood_fee",)),
    ("耗材类", ("treat_disposable_mat_fee", "exam_disposable_mat_fee", "surgery_disposable_mat_fee")),
    ("其他类", ("other_fee",)),
)
# 计入总费用的分项（“其中”项不重复相加：临床物理治疗、麻醉费、手术费、抗菌药物费）
FEE_SUM_COLUMNS = tuple(column for _label, columns in FEE_CATEGORIES for column in columns)


def _check_total_cost(doc: FrontpageDoc) -> RuleEval:
    if doc.cost is None:
        return data_gap(_NO_COST)
    value = doc.cost.get("total_cost", "")
    if v.parse_number(value) is not None:
        return passed()
    return failed(Detail("住院总费用", value, "填写金额"))


def _check_self_pay(doc: FrontpageDoc) -> RuleEval:
    if doc.cost is None:
        return data_gap(_NO_COST)
    return _require_value(doc.cost.get("self_pay", ""), "self_pay", "自付金额")


def _check_fee_items(doc: FrontpageDoc) -> RuleEval:
    if doc.cost is None:
        return data_gap(_NO_COST)
    missing = [
        (index, label)
        for index, (label, columns) in enumerate(FEE_CATEGORIES)
        if any(v.parse_number(doc.cost.get(column)) is None for column in columns)
    ]
    if not missing:
        return passed()
    return failed(*(Detail(f"费用分项：{label}", "", "填写金额，无费用填 0", index) for index, label in missing))


def _cost_rule(rule_id: str, name: str, check, severity: Severity, score_item: Optional[str], problem: str) -> None:
    _add(
        Rule(
            rule_id=rule_id,
            name=name,
            group="completeness",
            section="cost",
            severity=severity,
            score_item=score_item,
            basis=BASIS_FILL,
            problem=problem,
            check=check,
        )
    )


_cost_rule("C-F01", "住院总费用非空", _check_total_cost, Severity.DEDUCT, "total_cost", "住院总费用未填写")
_cost_rule("C-F02", "自付金额非空", _check_self_pay, Severity.REQUIRED, None, "自付金额未填写")
_cost_rule("C-F03", "费用分项非空", _check_fee_items, Severity.DEDUCT, "fee_items", "费用分项未填写")

# ================= 二、规范性 =================

_code_value_rule("S-01", "医疗付费方式", "medical_payment_method", v.PAYMENT_METHOD, "1–9 或对应名称", "patient", "payment")
_code_value_rule("S-02", "性别", "sex", v.SEX, "1男/2女/0未知/9未说明", "patient", "sex")


def _check_id_card(doc: FrontpageDoc) -> RuleEval:
    value = doc.get("id_card_no")
    if not v.has_content(value):
        return not_applicable("未填写，由完整性规则判断")
    if not v.is_id_card_type(doc.get("id_card_type")):
        return not_applicable("证件类型不是身份证")
    if v.is_valid_id_card(value):
        return passed()
    return failed(Detail("身份证号", value, "18 位且校验位正确"))


_add(Rule("S-03", "身份证号格式", "specification", "patient", Severity.DEDUCT, "id_card", BASIS_CODE, "身份证号格式或校验位不正确", _check_id_card))
_code_value_rule("S-04", "婚姻状况", "marital_status", v.MARITAL_STATUS, "1未婚/2已婚/3丧偶/4离婚/9其他", "patient", "marital")


def _check_relation(doc: FrontpageDoc) -> RuleEval:
    value = doc.get("contact_relationship")
    if not v.has_content(value):
        return not_applicable("未填写，由完整性规则判断")
    if v.is_valid_relation(value):
        return passed()
    return failed(Detail("联系人关系", value, "按 GB/T 4761 填写，如 配偶、子、女、父母；非家庭关系填“其他”"))


_add(Rule("S-05", "联系人关系取值规范", "specification", "patient", Severity.DEDUCT, "contact_relation", BASIS_CODE, "联系人关系不符合 GB/T 4761", _check_relation))
_code_value_rule("S-06", "入院途径", "admission_route", v.ADMISSION_ROUTE, "1急诊/2门诊/3其他医疗机构转入/9其他", "hospitalization", "admission_route")
_code_value_rule("S-07", "离院方式", "leaving_hospital_way", v.LEAVING_WAY, "1医嘱离院/2医嘱转院/3医嘱转社区或乡镇卫生院/4非医嘱离院/5死亡/9其他", "hospitalization", "leaving_way")


def _check_main_admission_condition_value(doc: FrontpageDoc, main: DiagnosisItem) -> RuleEval:
    value = main.raw_admission_condition
    if not v.has_content(value):
        return not_applicable("未填写，由完整性规则判断")
    if v.normalize_code(value, v.ADMISSION_CONDITION):
        return passed()
    return failed(Detail(f"主要诊断（{main.name}）入院病情", value, "1有/2临床未确定/3情况不明/4无", main.index))


_add(Rule("S-08", "主要诊断入院病情取值规范", "specification", "diagnosis", Severity.DEDUCT, "admission_condition", BASIS_CODE, "主要诊断入院病情取值不规范", _with_main(_check_main_admission_condition_value)))


def _diag_value_rule(attr: str, label: str, table: Dict[str, str], expected: str, main_only: bool = False) -> Callable[[FrontpageDoc], RuleEval]:
    def check(doc: FrontpageDoc) -> RuleEval:
        if not doc.discharge_diagnoses:
            return data_gap(_NO_DISCHARGE_DIAGNOSIS)
        items = doc.other_diagnoses if not main_only else doc.main_diagnoses
        bad = [item for item in items if v.has_content(getattr(item, attr)) and v.normalize_code(getattr(item, attr), table) is None]
        if not bad:
            return passed()
        return failed(*(Detail(f"{_diag_label(item)}{label}", getattr(item, attr), expected, item.index) for item in bad))

    return check


def _check_discharge_condition_values(doc: FrontpageDoc) -> RuleEval:
    if not doc.discharge_diagnoses:
        return data_gap(_NO_DISCHARGE_DIAGNOSIS)
    bad = [
        item
        for item in doc.discharge_diagnoses
        if v.has_content(item.raw_discharge_condition) and v.normalize_code(item.raw_discharge_condition, v.DISCHARGE_CONDITION) is None
    ]
    if not bad:
        return passed()
    return failed(*(Detail(f"{_diag_label(item)}出院情况", item.raw_discharge_condition, "1治愈/2好转/3未愈/4死亡/9其他", item.index) for item in bad))


_add(Rule("S-09", "出院情况取值规范", "specification", "diagnosis", Severity.REQUIRED, None, BASIS_CODE, "出院情况取值不规范", _check_discharge_condition_values))
_code_value_rule("S-10", "ABO血型", "abo_blood_code", v.ABO_BLOOD, "1A/2B/3O/4AB/5不详/6未查", "diagnosis", "blood")
_code_value_rule("S-11", "Rh血型", "rh_blood_code", v.RH_BLOOD, "1阴/2阳/3不详/4未查", "diagnosis", "blood")
_code_value_rule("S-12", "药物过敏", "allergy_sign", v.ALLERGY_FLAG, "1无/2有", "diagnosis", "allergy")


def _check_surgery_level_value(doc: FrontpageDoc) -> RuleEval:
    surgery = doc.main_surgery
    if surgery is None:
        return not_applicable(_NO_SURGERY)
    value = surgery.raw_level
    if not v.has_content(value) or value in v.SURGICAL_LEVEL_UNSET:
        return not_applicable("未填写，由 C-D20 提示")
    if v.normalize_code(value, v.SURGICAL_LEVEL):
        return passed()
    return failed(Detail(f"主要手术（{surgery.name or surgery.code}）手术级别", value, "1–4 或 一级至四级", 0))


_add(Rule("S-13", "手术级别取值规范", "specification", "diagnosis", Severity.DEDUCT, "surgery_level", BASIS_CODE, "手术级别取值不规范", _check_surgery_level_value, condition="有手术或操作时"))


def _check_incision_values(doc: FrontpageDoc) -> RuleEval:
    surgery = doc.main_surgery
    if surgery is None:
        return not_applicable(_NO_SURGERY)
    details = []
    if v.has_content(surgery.raw_incision) and v.normalize_code(surgery.raw_incision, v.INCISION_CLASS) is None:
        details.append(Detail("主要手术切口类别", surgery.raw_incision, "0/Ⅰ/Ⅱ/Ⅲ 类", 0))
    if v.has_content(surgery.raw_healing) and v.normalize_code(surgery.raw_healing, v.HEALING_GRADE) is None:
        details.append(Detail("主要手术愈合等级", surgery.raw_healing, "甲/乙/丙/其他", 0))
    return failed(*details) if details else passed()


_add(Rule("S-14", "切口类别与愈合等级取值规范", "specification", "diagnosis", Severity.DEDUCT, "incision_heal", BASIS_CODE, "切口类别或愈合等级取值不规范", _check_incision_values, condition="有手术或操作时"))


def _check_main_code_format(doc: FrontpageDoc, main: DiagnosisItem) -> RuleEval:
    if not v.has_content(main.code):
        return not_applicable("未填写，由 C-D06 判断")
    if not v.is_icd10(main.code):
        return failed(Detail(f"主要诊断（{main.name}）编码", main.code, "ICD-10 编码格式（兼容国临版扩展码）", main.index))
    if v.is_external_cause(main.code):
        return failed(Detail(f"主要诊断（{main.name}）编码", main.code, "外部原因编码（V–Y）不能作为主要诊断", main.index))
    return passed()


_add(Rule("S-15", "主要诊断编码格式", "specification", "diagnosis", Severity.DEDUCT, "main_diag_code", "填写规范第六条：疾病诊断编码使用 ICD-10", "主要诊断编码格式不正确", _with_main(_check_main_code_format)))


def _check_other_code_format(doc: FrontpageDoc) -> RuleEval:
    if not doc.discharge_diagnoses:
        return data_gap(_NO_DISCHARGE_DIAGNOSIS)
    bad = [item for item in doc.other_diagnoses if v.has_content(item.code) and not v.is_icd10(item.code)]
    if not bad:
        return passed()
    return failed(*(Detail(f"{_diag_label(item)}编码", item.code, "ICD-10 编码格式（兼容国临版扩展码）", item.index) for item in bad))


_add(Rule("S-16", "其他诊断编码格式", "specification", "diagnosis", Severity.DEDUCT, "other_diag_code", "填写规范第六条：疾病诊断编码使用 ICD-10", "其他诊断编码格式不正确", _check_other_code_format))


def _check_main_surgery_code_format(doc: FrontpageDoc) -> RuleEval:
    surgery = doc.main_surgery
    if surgery is None:
        return not_applicable(_NO_SURGERY)
    if not v.has_content(surgery.code):
        return not_applicable("未填写，由 C-D18 判断")
    if v.is_icd9cm3(surgery.code):
        return passed()
    return failed(Detail(f"主要手术（{surgery.name}）编码", surgery.code, "ICD-9-CM-3 编码格式（兼容国临版扩展码）", 0))


_add(Rule("S-17", "主要手术编码格式", "specification", "diagnosis", Severity.DEDUCT, "main_surgery_code", "填写规范第六条：手术操作编码使用 ICD-9-CM-3", "主要手术编码格式不正确", _check_main_surgery_code_format, condition="有手术或操作时"))


def _check_age_value(doc: FrontpageDoc) -> RuleEval:
    value = doc.get("age")
    if not v.has_content(value):
        return not_applicable("未填写，由完整性规则判断")
    years = v.parse_age_years(value)
    if years is None or not 0 <= years <= 150:
        return failed(Detail("年龄", value, "0–150 岁；不足 1 岁按月龄填写"))
    return passed()


_add(Rule("S-20", "年龄取值规范", "specification", "patient", Severity.DEDUCT, "age", BASIS_CODE, "年龄取值不规范", _check_age_value))


def _check_phone(doc: FrontpageDoc) -> RuleEval:
    value = doc.get("contact_telephone")
    if not v.has_content(value):
        return not_applicable("未填写，由完整性规则判断")
    if v.is_valid_phone(value):
        return passed()
    return failed(Detail("联系人电话", value, "11 位手机号或固定电话；无电话填“-”"))


_add(Rule("S-21", "联系人电话格式", "specification", "patient", Severity.DEDUCT, "contact_phone", BASIS_CODE, "联系人电话格式不正确", _check_phone))
_add(
    Rule(
        "S-22",
        "其他诊断入院病情取值规范",
        "specification",
        "diagnosis",
        Severity.REQUIRED,
        None,
        BASIS_CODE,
        "其他诊断入院病情取值不规范",
        _diag_value_rule("raw_admission_condition", "入院病情", v.ADMISSION_CONDITION, "1有/2临床未确定/3情况不明/4无"),
    )
)


def _check_other_surgery_code_format(doc: FrontpageDoc) -> RuleEval:
    bad = [item for item in doc.other_surgeries if v.has_content(item.code) and not v.is_icd9cm3(item.code)]
    if not doc.other_surgeries:
        return not_applicable("无其他手术或操作")
    if not bad:
        return passed()
    return failed(*(Detail(f"手术第{item.index + 1}条（{item.name}）编码", item.code, "ICD-9-CM-3 编码格式（兼容国临版扩展码）", item.index) for item in bad))


_add(Rule("S-23", "其他手术编码格式", "specification", "diagnosis", Severity.DEDUCT, "other_surgery_code", "填写规范第六条：手术操作编码使用 ICD-9-CM-3", "其他手术编码格式不正确", _check_other_surgery_code_format, condition="有多条手术或操作时"))


def _check_outpatient_code_format(doc: FrontpageDoc) -> RuleEval:
    bad = [item for item in doc.outpatient_diagnoses if v.has_content(item.code) and not v.is_icd10(item.code)]
    if not doc.outpatient_diagnoses:
        return not_applicable("无门（急）诊诊断")
    if not bad:
        return passed()
    return failed(*(Detail(f"门（急）诊诊断（{item.name}）编码", item.code, "ICD-10 编码格式（兼容国临版扩展码）") for item in bad))


_add(Rule("S-24", "门（急）诊诊断编码格式", "specification", "diagnosis", Severity.DEDUCT, "outpatient_code", "填写规范第六条：疾病诊断编码使用 ICD-10", "门（急）诊诊断编码格式不正确", _check_outpatient_code_format))


def _datetime_format_rule(rule_id: str, label: str, field_key: str, score_item: str) -> None:
    def check(doc: FrontpageDoc) -> RuleEval:
        value = doc.get(field_key)
        if not v.has_content(value):
            return not_applicable("未填写，由完整性规则判断")
        if v.parse_datetime(value) is None:
            return failed(Detail(label, value, "日期时间，精确到分钟"))
        return passed()

    _add(Rule(rule_id, f"{label}格式", "specification", "hospitalization", Severity.DEDUCT, score_item, "填写规范第八条：记录时间应当精确到分钟", f"{label}格式不正确", check))


_datetime_format_rule("S-25", "入院时间", "admission_datetime", "admission_time")
_datetime_format_rule("S-26", "出院时间", "discharge_datetime", "discharge_time")


def _check_los_value(doc: FrontpageDoc) -> RuleEval:
    value = doc.get("hospital_duration")
    if not v.has_content(value):
        return not_applicable("未填写，由完整性规则判断")
    days = v.parse_number(value)
    if days is None or days < 1 or days != int(days):
        return failed(Detail("实际住院天数", value, "不小于 1 的整数（入出院同日计 1 天）"))
    return passed()


_add(Rule("S-27", "实际住院天数取值规范", "specification", "hospitalization", Severity.DEDUCT, "los", "填写说明（十九）：入院日与出院日只计算一天", "实际住院天数取值不规范", _check_los_value))

# ================= 三、逻辑一致性 =================


def _dates_or_gap(doc: FrontpageDoc) -> Optional[RuleEval]:
    """入出院时间缺失时返回资料不足或不适用；都有时返回 None。"""
    missing = [
        key
        for key, parsed in (("admission_datetime", doc.admission_at), ("discharge_datetime", doc.discharge_at))
        if parsed is None
    ]
    if not missing:
        return None
    if any(key in SOURCE_GAP_FIELDS and not v.has_content(doc.get(key)) for key in missing):
        return data_gap("入院或出院时间缺失（首页同步未带入）")
    return not_applicable("入院或出院时间缺失或格式不正确，由完整性、规范性规则判断")


def _check_time_order(doc: FrontpageDoc) -> RuleEval:
    pending = _dates_or_gap(doc)
    if pending is not None:
        return pending
    if doc.discharge_at >= doc.admission_at:
        return passed()
    return failed(Detail("出院时间", doc.get("discharge_datetime"), f"不早于入院时间 {doc.get('admission_datetime')}"))


def _check_los_consistency(doc: FrontpageDoc) -> RuleEval:
    pending = _dates_or_gap(doc)
    if pending is not None:
        return pending
    days = v.parse_number(doc.get("hospital_duration"))
    if days is None:
        return not_applicable("实际住院天数未填写或格式不正确")
    expected = max(1, (doc.discharge_at.date() - doc.admission_at.date()).days)
    if int(days) == expected:
        return passed()
    return failed(Detail("实际住院天数", doc.get("hospital_duration"), f"按入出院日期应为 {expected} 天"))


def _check_age_consistency(doc: FrontpageDoc) -> RuleEval:
    birth = v.parse_datetime(doc.get("birthday"))
    years = v.parse_age_years(doc.get("age"))
    if birth is None or years is None:
        return not_applicable("出生日期或年龄缺失")
    reference = doc.admission_at or doc.discharge_at
    if reference is None:
        if any(key in SOURCE_GAP_FIELDS for key in ("admission_datetime", "discharge_datetime")):
            return data_gap("入院、出院时间都缺失，无法推算年龄（首页同步未带入）")
        return not_applicable("入院、出院时间都缺失")
    actual = v.full_years_between(birth.date(), reference.date())
    if actual < 1:
        return not_applicable("不足 1 岁按月龄填写，暂不核对")
    if abs(int(years) - actual) <= 1:
        return passed()
    return failed(Detail("年龄", doc.get("age"), f"按出生日期推算应为 {actual} 岁"))


def _check_single_main(doc: FrontpageDoc) -> RuleEval:
    mains = doc.main_diagnoses
    if not mains:
        return not_applicable("未标记主要诊断，由 C-D03 判断")
    if len(mains) == 1:
        return passed()
    return failed(*(Detail(f"{_diag_label(item)}", item.code, "出院诊断只能有一个主要诊断", item.index) for item in mains[1:]))


def _check_duplicate_codes(doc: FrontpageDoc) -> RuleEval:
    seen: Dict[str, DiagnosisItem] = {}
    duplicates = []
    for item in doc.discharge_diagnoses:
        key = v.icd10_head(item.code)
        if not v.has_content(item.code):
            continue
        if key in seen:
            duplicates.append(item)
        else:
            seen[key] = item
    if not duplicates:
        return passed()
    return failed(*(Detail(_diag_label(item), item.code, "出院诊断编码重复", item.index) for item in duplicates))


_FEMALE_DIAGNOSIS = (("O00", "O99"), ("C51", "C58"), ("N70", "N98"), ("D25", "D28"), ("Z32", "Z36"), ("Z39", "Z39"))
_MALE_DIAGNOSIS = (("C60", "C63"), ("N40", "N51"), ("D29", "D29"))


def _sex_code(doc: FrontpageDoc) -> Optional[str]:
    return v.normalize_code(doc.get("sex"), v.SEX)


def _check_sex_diagnosis(doc: FrontpageDoc) -> RuleEval:
    sex = _sex_code(doc)
    if sex not in ("1", "2"):
        return not_applicable("性别未知")
    if not doc.discharge_diagnoses:
        return data_gap(_NO_DISCHARGE_DIAGNOSIS)
    ranges, expected = (_FEMALE_DIAGNOSIS, "该编码仅用于女性") if sex == "1" else (_MALE_DIAGNOSIS, "该编码仅用于男性")
    bad = [item for item in doc.discharge_diagnoses if v.icd10_in_ranges(item.code, ranges)]
    if not bad:
        return passed()
    return failed(*(Detail(_diag_label(item), item.code, f"{expected}，与性别（{doc.get('sex')}）不符", item.index) for item in bad))


_FEMALE_SURGERY = range(65, 76)  # 卵巢、输卵管、子宫、阴道、外阴及产科操作
_MALE_SURGERY = range(60, 65)  # 前列腺、精囊、阴囊、睾丸、阴茎


def _check_sex_surgery(doc: FrontpageDoc) -> RuleEval:
    sex = _sex_code(doc)
    if sex not in ("1", "2"):
        return not_applicable("性别未知")
    if not doc.surgeries:
        return not_applicable(_NO_SURGERY)
    wrong = _FEMALE_SURGERY if sex == "1" else _MALE_SURGERY
    bad = [item for item in doc.surgeries if v.icd9_category(item.code) in wrong]
    if not bad:
        return passed()
    expected = "该编码仅用于女性" if sex == "1" else "该编码仅用于男性"
    return failed(*(Detail(f"手术第{item.index + 1}条（{item.name}）", item.code, f"{expected}，与性别（{doc.get('sex')}）不符", item.index) for item in bad))


def _leaving_code(doc: FrontpageDoc) -> Optional[str]:
    return v.normalize_code(doc.get("leaving_hospital_way"), v.LEAVING_WAY)


def _check_death_consistency(doc: FrontpageDoc) -> RuleEval:
    leaving = _leaving_code(doc)
    main = doc.main_diagnosis
    if leaving is None or main is None:
        return not_applicable("离院方式或主要诊断缺失")
    condition = v.normalize_code(main.raw_discharge_condition, v.DISCHARGE_CONDITION)
    if condition is None:
        return not_applicable("主要诊断出院情况缺失")
    if (leaving == "5") == (condition == "4"):
        return passed()
    if leaving == "5":
        return failed(Detail(f"主要诊断（{main.name}）出院情况", main.raw_discharge_condition, "离院方式为死亡时，主要诊断出院情况应为 4 死亡", main.index))
    return failed(Detail("离院方式", doc.get("leaving_hospital_way"), "主要诊断出院情况为死亡时，离院方式应为 5 死亡"))


def _check_autopsy(doc: FrontpageDoc) -> RuleEval:
    leaving = _leaving_code(doc)
    value = doc.get("death_autopsy_sign")
    if leaving is None or not v.is_filled(value):
        return not_applicable("离院方式或尸检未填写")
    autopsy = v.normalize_code(value, v.AUTOPSY)
    if leaving == "5":
        if autopsy is None:
            return failed(Detail("死亡患者尸检", value, "死亡患者须填写 1是/2否"))
        return passed()
    if v.has_content(value):
        return failed(Detail("死亡患者尸检", value, "非死亡患者填“-”"))
    return passed()


def _check_transfer_target(doc: FrontpageDoc) -> RuleEval:
    leaving = _leaving_code(doc)
    if leaving not in ("2", "3"):
        return not_applicable("离院方式不是转院或转社区")
    if v.has_content(doc.get("planned_transder_to")):
        return passed()
    return failed(Detail("拟接收医疗机构名称", doc.get("planned_transder_to"), "医嘱转院或转社区、乡镇卫生院时，须填写接收机构名称"))


def _check_readmission_purpose(doc: FrontpageDoc) -> RuleEval:
    plan = v.normalize_code(doc.get("rehospital_with_month"), v.YES_NO_PLAN)
    if plan != "2":
        return not_applicable("无 31 天内再住院计划")
    if v.has_content(doc.get("rehospital_with_month_purpose")):
        return passed()
    return failed(Detail("31天内再住院目的", doc.get("rehospital_with_month_purpose"), "有再住院计划时须填写目的"))


def _check_allergy_drug(doc: FrontpageDoc) -> RuleEval:
    flag = v.normalize_code(doc.get("allergy_sign"), v.ALLERGY_FLAG)
    drug = doc.get("allergy_history")
    if flag == "2":
        if v.has_content(drug):
            return passed()
        return failed(Detail("过敏药物", drug, "有药物过敏时须填写具体药物，如：青霉素"))
    if flag == "1":
        if v.has_content(drug) and not any(word in drug for word in ("否认", "无")):
            return failed(Detail("过敏药物", drug, "药物过敏为“无”时过敏药物填“-”"))
        return passed()
    return not_applicable("药物过敏未填写或取值不规范")


def _check_z37_main(doc: FrontpageDoc, main: DiagnosisItem) -> RuleEval:
    if v.icd10_head(main.code).startswith("Z37"):
        return failed(Detail(f"主要诊断（{main.name}）编码", main.code, "Z37 分娩结局编码不能作为主要诊断", main.index))
    return passed()


def _check_delivery_outcome(doc: FrontpageDoc) -> RuleEval:
    delivery = [item for item in doc.discharge_diagnoses if v.icd10_in_ranges(item.code, (("O80", "O84"),))]
    if not delivery:
        return not_applicable("无分娩诊断")
    if any(v.icd10_head(item.code).startswith("Z37") for item in doc.discharge_diagnoses):
        return passed()
    return failed(Detail(_diag_label(delivery[0]), delivery[0].code, "有分娩诊断时须有 Z37 分娩结局编码", delivery[0].index))


def _check_surgery_date_range(doc: FrontpageDoc) -> RuleEval:
    surgery = doc.main_surgery
    if surgery is None:
        return not_applicable(_NO_SURGERY)
    if surgery.begin_at is None:
        return not_applicable("手术日期缺失或格式不正确")
    pending = _dates_or_gap(doc)
    if pending is not None:
        return pending
    if doc.admission_at.date() <= surgery.begin_at.date() <= doc.discharge_at.date():
        return passed()
    return failed(Detail("主要手术日期", surgery.begin_at_raw, "应在入院与出院时间之间", 0))


def _check_fee_sum(doc: FrontpageDoc) -> RuleEval:
    if doc.cost is None:
        return data_gap(_NO_COST)
    total = v.parse_number(doc.cost.get("total_cost"))
    parts = [v.parse_number(doc.cost.get(column)) for column in FEE_SUM_COLUMNS]
    if total is None or any(part is None for part in parts):
        return not_applicable("总费用或分项缺失")
    subtotal = round(sum(parts), 2)
    if abs(subtotal - total) <= 1:
        return passed()
    return failed(Detail("费用分项合计", f"{subtotal:.2f}", f"应等于总费用 {total:.2f}（误差 1 元内）"))


def _check_self_pay_range(doc: FrontpageDoc) -> RuleEval:
    if doc.cost is None:
        return data_gap(_NO_COST)
    total = v.parse_number(doc.cost.get("total_cost"))
    self_pay = v.parse_number(doc.cost.get("self_pay"))
    if total is None or self_pay is None:
        return not_applicable("总费用或自付金额缺失")
    if 0 <= self_pay <= total:
        return passed()
    return failed(Detail("自付金额", doc.cost.get("self_pay"), f"不大于总费用 {total:.2f}"))


def _check_transfer_path(doc: FrontpageDoc) -> RuleEval:
    path = doc.get("transfer_dept_name")
    if not v.has_content(path):
        return not_applicable("无转科")
    steps = [step.strip() for step in path.replace("→", "->").split("->") if step.strip()]
    if len(steps) < 2:
        return not_applicable("转科路径只有一个科室")
    admission, discharge = doc.get("admission_dept_name"), doc.get("discharge_dept_name")
    details = []
    if v.has_content(admission) and steps[0] != admission:
        details.append(Detail("转科路径起点", steps[0], f"应与入院科别（{admission}）一致"))
    if v.has_content(discharge) and steps[-1] != discharge:
        details.append(Detail("转科路径终点", steps[-1], f"应与出院科别（{discharge}）一致"))
    return failed(*details) if details else passed()


def _logic(rule_id: str, name: str, section: str, severity: Severity, score_item: Optional[str], basis: str, problem: str, check, condition: str = "") -> None:
    _add(Rule(rule_id, name, "logic", section, severity, score_item, basis, problem, check, condition=condition))


_logic("L-01", "出院时间不早于入院时间", "hospitalization", Severity.DEDUCT, "discharge_time", "填写规范第八条", "出院时间早于入院时间", _check_time_order)
_logic("L-02", "实际住院天数与入出院日期一致", "hospitalization", Severity.DEDUCT, "los", "填写说明（十九）", "实际住院天数与入出院日期不符", _check_los_consistency)
_logic("L-03", "年龄与出生日期一致", "patient", Severity.DEDUCT, "age", "填写说明（六）：年龄为实足年龄", "年龄与出生日期推算不符", _check_age_consistency)
_logic("L-04", "主要诊断唯一", "diagnosis", Severity.DEDUCT, "main_diag_name", "填写说明（二十一）", "标记了多个主要诊断", _check_single_main)
_logic("L-05", "出院诊断编码不重复", "diagnosis", Severity.HINT, None, "编码规则", "出院诊断编码重复", _check_duplicate_codes)
_logic("L-06", "诊断编码与性别一致", "diagnosis", Severity.DEDUCT, "main_diag_code", "ICD-10 性别限定类目", "诊断编码与性别不符", _check_sex_diagnosis)
_logic("L-07", "手术编码与性别一致", "diagnosis", Severity.DEDUCT, "main_surgery_code", "ICD-9-CM-3 性别限定类目", "手术编码与性别不符", _check_sex_surgery, condition="有手术或操作时")
_logic("L-08", "死亡离院与出院情况一致", "hospitalization", Severity.DEDUCT, "leaving_way", "填写说明（三十四）", "离院方式与主要诊断出院情况矛盾", _check_death_consistency)
_logic("L-09", "尸检与离院方式一致", "diagnosis", Severity.DEDUCT, "autopsy", "填写说明（二十六）", "尸检填写与离院方式不符", _check_autopsy)
_logic("L-10", "转院须填接收机构", "hospitalization", Severity.DEDUCT, "leaving_way", "填写说明（三十四）", "转院或转社区未填写接收机构", _check_transfer_target, condition="离院方式为医嘱转院或转社区时")
_logic("L-11", "再住院计划须填目的", "hospitalization", Severity.DEDUCT, "readmission", "填写说明（三十五）", "有再住院计划但未填写目的", _check_readmission_purpose, condition="有 31 天内再住院计划时")
_logic("L-12", "药物过敏与过敏药物一致", "diagnosis", Severity.DEDUCT, "allergy", "填写说明（二十五）", "药物过敏标志与过敏药物不一致", _check_allergy_drug)
_logic("L-14", "Z37 不能作主要诊断", "diagnosis", Severity.DEDUCT, "main_diag_code", "ICD-10 编码规则", "Z37 分娩结局编码作为主要诊断", _with_main(_check_z37_main))
_logic("L-15", "分娩须有分娩结局编码", "diagnosis", Severity.DEDUCT, "other_diag_code", "ICD-10 编码规则", "分娩诊断缺少 Z37 分娩结局编码", _check_delivery_outcome, condition="有分娩诊断时")
_logic("L-17", "手术日期在住院期间", "diagnosis", Severity.DEDUCT, "surgery_date", "填写规范第八条", "主要手术日期不在住院期间", _check_surgery_date_range, condition="有手术或操作时")
_add(
    Rule(
        "L-18",
        "费用分项合计等于总费用",
        "logic",
        "cost",
        Severity.HINT,
        None,
        "填写说明（三十七）",
        "费用分项合计与总费用不一致",
        _check_fee_sum,
        enabled=False,
        disabled_reason="库中费用分项不全（缺中医类、血液制品等），合计无法核对",
    )
)
_logic("L-19", "自付金额不大于总费用", "cost", Severity.REQUIRED, None, "填写说明（三十七）", "自付金额大于总费用", _check_self_pay_range)
_logic("L-20", "转科路径与入出院科别一致", "hospitalization", Severity.HINT, None, "填写说明（十八）", "转科路径与入院、出院科别不一致", _check_transfer_path)

RULES: Tuple[Rule, ...] = tuple(_RULES)
RULES_BY_ID: Dict[str, Rule] = {rule.rule_id: rule for rule in RULES}

if len(RULES_BY_ID) != len(RULES):  # pragma: no cover - 编号重复是开发期错误
    raise RuntimeError("首页质控 V2 规则编号重复")
