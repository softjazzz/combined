from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from types import ModuleType
from typing import Any, Iterable, Sequence


ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.luxian_0609_rule_master import (  # noqa: E402
    Luxian0609RuleMasterEntry,
    load_luxian_0609_rule_master,
)
from app.services.luxian_0609.rule_contracts import (  # noqa: E402
    load_luxian_0609_rule_contracts,
)
from scripts.luxian_0609_v3_controlled_evidence import (  # noqa: E402
    RULE_NUMBERS_BY_CASE,
    apply_controlled_evidence,
    build_gold_acceptance_contracts,  # noqa: F401
    expected_status_for_case,
    normalize_v3_stay_timeline,
)


SOURCE_POOL_NAME = "0426"
TARGET_POOL_ID = "luxian-0609-0426-syn-v3"
TARGET_POOL_NAME = "泸县0609真实结构合成验证集 v3（38）"
TARGET_SOURCE_FILE = "derived://0426/luxian_0609_0426_synthetic_v3"
TARGET_SOURCE_SHEET = "0426-derived-v3"
TARGET_INSTITUTE_ID = "LX0609_0426_SYN_V3"
TARGET_VISIT_PREFIX = "LX0609_0426_SYN_V3_"
TARGET_MR_PREFIX = "LX0609V3-"
TARGET_ITEM_PREFIX = "lx0609-v3"
BUNDLE_POLICY_VERSION = "luxian_0609_0426_syn_v3"
DEFAULT_OUTPUT_DIR = ROOT / "tmp-lx0609-0426-synthetic-v3"

_V3_ADMISSION_CONTEXT: dict[str, tuple[str, str, str]] = {
    "时限": (
        "发热伴咳嗽3天",
        "患者因发热伴咳嗽3天入院，现病史及入院查体已记录。",
        "结合发热、咳嗽及入院查体，形成当前住院第一诊断。",
    ),
    "查房/病重病危": (
        "发热、咳嗽伴气促2天",
        "患者因发热、咳嗽伴气促2天入院，入院时精神差，需动态观察病情。",
        "结合发热、咳嗽、气促及肺部阳性体征，形成当前住院第一诊断。",
    ),
    "检查检验": (
        "腰痛伴右下肢麻木1周",
        "患者因腰痛伴右下肢麻木1周入院，活动后疼痛加重。",
        "结合腰痛、下肢麻木及神经根受压体征，形成当前住院第一诊断。",
    ),
    "会诊": (
        "右上腹疼痛伴发热2天",
        "患者因右上腹疼痛伴发热2天入院，伴食欲下降和乏力。",
        "结合右上腹疼痛、发热及胆道相关体征，形成当前住院第一诊断。",
    ),
    "手术麻醉": (
        "右下肢疼痛、肿胀伴活动受限1天",
        "患者因右下肢疼痛、肿胀伴活动受限1天入院，患肢负重困难。",
        "结合外伤史、局部疼痛肿胀及影像学表现，形成当前住院第一诊断。",
    ),
    "输血": (
        "乏力、心悸伴面色苍白1个月",
        "患者因乏力、心悸伴面色苍白1个月入院，活动后症状明显。",
        "结合贫血症状、血红蛋白变化及原发病情况，形成当前住院第一诊断。",
    ),
    "肿瘤病理/化疗": (
        "上腹部不适伴食欲下降1月",
        "患者因上腹部不适伴食欲下降1月入院，近期体重下降。",
        "结合上腹部症状、影像及病理相关资料，形成当前住院第一诊断。",
    ),
    "出院死亡": (
        "发热、咳嗽3天",
        "患者因发热、咳嗽3天入院，入院后完成相关检查和治疗。",
        "结合主诉、查体及入院辅助检查，形成当前住院第一诊断。",
    ),
    "抗菌药物/医嘱": (
        "发热伴咳痰3天",
        "患者因发热伴咳痰3天入院，伴乏力和食欲下降。",
        "结合感染症状、查体和实验室检查，形成当前住院第一诊断。",
    ),
    "交接转科": (
        "头晕伴左侧肢体乏力6小时",
        "患者因头晕伴左侧肢体乏力6小时入院，症状突然出现。",
        "结合神经系统症状、查体及影像学资料，形成当前住院第一诊断。",
    ),
}


FAMILY_RULE_NUMBERS: dict[str, tuple[int, ...]] = {
    "时限": (1, 2, 4, 5, 6),
    "查房/病重病危": (7, 8, 9, 16, 17, 18),
    "检查检验": (10, 11, 12, 14, 15, 52, 53),
    "会诊": (20, 21, 22, 23, 69),
    "手术麻醉": (3, 24, 25, *range(28, 41), 64, 65, 66, 75),
    "输血": (*range(41, 50), 70),
    "肿瘤病理/化疗": (13, 19, 26, 27),
    "出院死亡": (50, 51, 60, 61, 62, 63, 67, 68),
    "抗菌药物/医嘱": (*range(54, 60),),
    "交接转科": (71, 72, 73, 74),
}

FAMILY_QUOTAS: dict[str, int] = {
    "时限": 4,
    "查房/病重病危": 4,
    "检查检验": 4,
    "会诊": 4,
    "手术麻醉": 6,
    "输血": 5,
    "肿瘤病理/化疗": 3,
    "出院死亡": 3,
    "抗菌药物/医嘱": 2,
    "交接转科": 3,
}

FAMILY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "时限": ("入院记录", "首次病程", "48小时", "24小时", "8小时", "时限", "超时"),
    "查房/病重病危": ("查房", "病重", "病危", "病程记录", "复制", "重复"),
    "检查检验": ("CT", "MRI", "检查", "检验", "培养", "阳性", "报告", "危急值", "PL", "PH"),
    "会诊": ("会诊", "会诊申请", "会诊记录", "会诊意见"),
    "手术麻醉": ("手术", "麻醉", "术前", "术后", "安全核查", "知情同意"),
    "输血": ("输血", "红细胞", "血浆", "配血", "输血同意", "血型"),
    "肿瘤病理/化疗": ("肿瘤", "病理", "化疗", "癌", "恶性", "取材"),
    "出院死亡": ("出院", "死亡", "死亡讨论", "带药", "出院诊断"),
    "抗菌药物/医嘱": ("抗菌", "抗生素", "美罗培南", "亚胺培南", "万古霉素", "医嘱"),
    "交接转科": ("交班", "接班", "交接班", "转科", "转入", "转出", "补充诊断"),
}

FAMILY_KEYWORD_ORDER = (
    "输血",
    "肿瘤病理/化疗",
    "手术麻醉",
    "会诊",
    "出院死亡",
    "交接转科",
    "抗菌药物/医嘱",
    "查房/病重病危",
    "检查检验",
    "时限",
)


def _load_v2_module() -> ModuleType:
    path = Path(__file__).with_name("build_luxian_0609_0426_synthetic_v2.py")
    module_name = "build_luxian_0609_0426_synthetic_v2_for_v3"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载 LX0609 0426 v2 兼容构建器")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


V2 = _load_v2_module()


def build_master_family_rule_ids(
    entries: Sequence[Luxian0609RuleMasterEntry] | None = None,
    *,
    statuses: Iterable[str] | None = None,
) -> dict[str, list[str]]:
    master = tuple(entries or load_luxian_0609_rule_master())
    entries_by_id = {entry.rule_id: entry for entry in master}
    all_family_ids = tuple(
        f"LX0609-{number:03d}"
        for numbers in FAMILY_RULE_NUMBERS.values()
        for number in numbers
    )
    if len(all_family_ids) != len(set(all_family_ids)):
        raise ValueError("LX0609 v3 validation families contain duplicate rules")
    if set(all_family_ids) != set(entries_by_id):
        raise ValueError("LX0609 v3 validation families drifted from the 75-rule master")

    wanted_statuses = set(statuses or ())
    return {
        family: [
            rule_id
            for number in numbers
            if (
                (rule_id := f"LX0609-{number:03d}")
                and (not wanted_statuses or entries_by_id[rule_id].implementation_status in wanted_statuses)
            )
        ]
        for family, numbers in FAMILY_RULE_NUMBERS.items()
    }


def _configure_v2_compatibility() -> None:
    V2.TARGET_POOL_ID = TARGET_POOL_ID
    V2.TARGET_POOL_NAME = TARGET_POOL_NAME
    V2.TARGET_SOURCE_FILE = TARGET_SOURCE_FILE
    V2.TARGET_SOURCE_SHEET = TARGET_SOURCE_SHEET
    V2.TARGET_INSTITUTE_ID = TARGET_INSTITUTE_ID
    V2.TARGET_VISIT_PREFIX = TARGET_VISIT_PREFIX
    V2.TARGET_MR_PREFIX = TARGET_MR_PREFIX
    V2.TARGET_ITEM_PREFIX = TARGET_ITEM_PREFIX
    V2.BUNDLE_POLICY_VERSION = BUNDLE_POLICY_VERSION
    V2.TARGET_SCENE = "final"
    V2.FAMILY_QUOTAS = dict(FAMILY_QUOTAS)
    V2.FAMILY_RULE_IDS = build_master_family_rule_ids(statuses={"active"})
    V2.FAMILY_KEYWORDS = dict(FAMILY_KEYWORDS)
    V2.FAMILY_KEYWORD_ORDER = FAMILY_KEYWORD_ORDER


def _assign_full_validation_family_scope(cases: Sequence[Any]) -> list[Any]:
    validation_rules = build_master_family_rule_ids()
    return [
        replace(case, selected_rule_ids=list(validation_rules[case.family]))
        for case in cases
    ]


def _assign_full_active_family_scope(cases: Sequence[Any]) -> list[Any]:
    active_rules = build_master_family_rule_ids(statuses={"active"})
    return [
        replace(case, selected_rule_ids=list(active_rules[case.family]))
        for case in cases
    ]


_EXAM_LAB_RULE_IDS = tuple(
    f"LX0609-{number:03d}" for number in (10, 11, 12, 14, 15, 52, 53)
)
_EXAM_LAB_SCENARIO_BY_INDEX = {
    9: "all_compliant",
    10: "all_missing",
    11: "recorded_without_analysis_with_unhandled_critical",
    12: "all_compliant_with_handled_critical",
}


def _exam_lab_expected_statuses(scenario: str) -> dict[str, str]:
    if scenario == "all_missing":
        return {
            **{rule_id: "non_compliant" for rule_id in _EXAM_LAB_RULE_IDS[:5]},
            "LX0609-052": "not_applicable",
            "LX0609-053": "not_applicable",
        }
    if scenario == "recorded_without_analysis_with_unhandled_critical":
        return {
            "LX0609-010": "compliant",
            "LX0609-011": "compliant",
            "LX0609-012": "non_compliant",
            "LX0609-014": "compliant",
            "LX0609-015": "non_compliant",
            "LX0609-052": "non_compliant",
            "LX0609-053": "non_compliant",
        }
    critical_status = "compliant" if scenario == "all_compliant_with_handled_critical" else "not_applicable"
    return {
        **{rule_id: "compliant" for rule_id in _EXAM_LAB_RULE_IDS[:5]},
        "LX0609-052": critical_status,
        "LX0609-053": critical_status,
    }


def build_acceptance_fixture_bindings() -> list[dict[str, str]]:
    """返回与 v3 构建器实际生成内容一致的受控状态绑定。"""

    bindings: list[dict[str, str]] = []
    for case_index, rule_numbers in RULE_NUMBERS_BY_CASE.items():
        for number in rule_numbers:
            rule_id = f"LX0609-{number:03d}"
            binding = {
                    "rule_id": rule_id,
                    "fixture_ref": f"0426-v3:case-{case_index:03d}",
                    "expected_status": expected_status_for_case(case_index, rule_id),
                }
            if number in {1, 2, 4, 5, 6} and case_index in {1, 2, 4}:
                binding["time_boundary"] = {
                    1: "before_threshold",
                    2: "after_threshold",
                    4: "at_threshold",
                }[case_index]
            bindings.append(binding)
    for case_index, scenario in _EXAM_LAB_SCENARIO_BY_INDEX.items():
        for rule_id, expected_status in _exam_lab_expected_statuses(scenario).items():
            bindings.append(
                {
                    "rule_id": rule_id,
                    "fixture_ref": f"0426-v3:case-{case_index:03d}",
                    "expected_status": expected_status,
                }
            )

    unique: dict[tuple[str, str, str], dict[str, str]] = {}
    for binding in bindings:
        key = (
            binding["rule_id"],
            binding["fixture_ref"],
            binding["expected_status"],
        )
        unique[key] = binding
    return sorted(
        unique.values(),
        key=lambda item: (
            item["rule_id"], item["expected_status"], item["fixture_ref"]
        ),
    )


def _replace_target_rows(
    rows_by_table: dict[str, list[dict[str, Any]]],
    *,
    table_names: Sequence[str],
    visit_ids: set[str],
) -> None:
    for table_name in table_names:
        rows_by_table[table_name] = [
            row
            for row in rows_by_table.get(table_name, [])
            if str(row.get("visit_id") or "") not in visit_ids
        ]


def _append_exam_lab_first_course(
    rows_by_table: dict[str, list[dict[str, Any]]],
    case: Any,
) -> None:
    base = V2._case_base_row(case)
    record_time = V2._dt_for_case(case, 0, 16, 0)
    document_id = f"{case.target_visit_id}-first-course-controlled"
    V2._append_row(
        rows_by_table,
        "first_course_record",
        {
            **base,
            "document_id": document_id,
            "document_title": "首次病程记录",
            "document_status": "Submitted",
            "submitter": "陈某医师",
            "submitter_id": "DEID",
            "submit_datetime": record_time,
            "record_time": record_time,
            "case_characteristic": "患者因腰痛伴右下肢麻木入院，活动后加重，查体腰椎活动受限，右下肢直腿抬高试验阳性。",
            "diagnose_based_on": "结合症状及神经根受压体征，初步考虑腰椎间盘突出症。",
            "differential_diagnosis": "需与腰椎管狭窄、周围神经病变及骨质疏松性压缩骨折鉴别。",
            "treatment_plan": "予止痛、营养神经和康复指导，根据后续辅助检查调整诊疗计划。",
            "record_content": "患者因腰痛伴右下肢麻木入院，当前先予对症治疗并动态观察神经系统体征。",
            "physician_sign": "陈某医师",
            "physician_sign_datetime": record_time,
            "last_modified_datetime": record_time,
            "update_time": record_time,
        },
    )
    V2._append_row(
        rows_by_table,
        "first_course_record_diagnosis",
        {
            **base,
            "document_id": document_id,
            "diagnosis_id": f"{document_id}-diagnosis",
            "diagnosis_main": "1",
            "diagnosis_type": "初步诊断",
            "diagnosis_no": "1",
            "diagnosis_name": "腰椎间盘突出症",
            "diagnosis_code": "M51.202",
            "diagnosis_source": "controlled_exam_lab_v3",
            "diagnosis_time": record_time,
            "record_time": record_time,
            "update_time": record_time,
        },
    )


def _append_course_row(
    rows_by_table: dict[str, list[dict[str, Any]]],
    case: Any,
    *,
    suffix: str,
    record_time: datetime,
    content: str,
) -> None:
    base = V2._case_base_row(case)
    V2._append_row(
        rows_by_table,
        "daily_course_record",
        {
            **base,
            "document_id": f"{case.target_visit_id}-course-{suffix}",
            "document_title": "日常病程记录",
            "document_status": "Submitted",
            "submitter": "陈某医师",
            "submitter_id": "DEID",
            "submit_datetime": record_time,
            "record_time": record_time,
            "record_content": content,
            "last_modified_datetime": record_time,
            "update_time": record_time,
        },
    )


def _append_exam_report_pair(
    rows_by_table: dict[str, list[dict[str, Any]]],
    case: Any,
) -> None:
    base = V2._case_base_row(case)
    exams = (
        {
            "suffix": "mri",
            "exam_type": "MRI",
            "exam_name": "腰椎MRI平扫",
            "request_time": V2._dt_for_case(case, 1, 8, 0),
            "exam_time": V2._dt_for_case(case, 1, 10, 0),
            "report_time": V2._dt_for_case(case, 1, 14, 0),
            "reason": "腰痛伴右下肢麻木，评估椎间盘及神经根受压情况。",
            "findings": "腰椎生理曲度变直，L4/5椎间盘向右后方突出，硬膜囊及右侧神经根受压。",
            "conclusion": "阳性：L4/5椎间盘突出并右侧神经根受压。",
        },
        {
            "suffix": "ultrasound",
            "exam_type": "超声",
            "exam_name": "泌尿系彩色多普勒超声",
            "request_time": V2._dt_for_case(case, 1, 8, 20),
            "exam_time": V2._dt_for_case(case, 1, 11, 0),
            "report_time": V2._dt_for_case(case, 1, 13, 0),
            "reason": "排除泌尿系结石及梗阻相关腰痛。",
            "findings": "双肾形态大小正常，集合系统未见分离，输尿管未见明显扩张。",
            "conclusion": "双肾及输尿管未见明显异常。",
        },
    )
    for number, exam in enumerate(exams, start=1):
        exam_id = f"EX-V3-{case.target_index:03d}-{number:02d}"
        V2._append_row(
            rows_by_table,
            "exam_master",
            {
                **base,
                "exam_id": exam_id,
                "order_id": f"ORDER-{exam_id}",
                "exam_type": exam["exam_type"],
                "exam_reason": exam["reason"],
                "clinic_sympton": "腰痛伴右下肢麻木",
                "request_dept": base["dept_name"],
                "request_physician": "陈某医师",
                "performed_dept": "医学影像科",
                "request_time": exam["request_time"],
                "schedule_time": exam["exam_time"],
                "received_time": exam["exam_time"],
                "exam_time": exam["exam_time"],
                "report_time": exam["report_time"],
                "reporter": "影像医师甲",
                "verifier": "影像医师乙",
                "exam_result_status": "Final",
                "record_content": f"{exam['exam_name']}申请：{exam['reason']}",
                "record_time": exam["request_time"],
                "last_modified_time": exam["report_time"],
                "update_time": exam["report_time"],
            },
        )
        V2._append_row(
            rows_by_table,
            "exam_item_report",
            {
                **base,
                "document_id": f"{case.target_visit_id}-exam-{exam['suffix']}",
                "document_title": f"{exam['exam_name']}检查报告",
                "document_status": "Submitted",
                "submitter": "影像医师乙",
                "submitter_id": "DEID-IMG",
                "submit_datetime": exam["report_time"],
                "record_time": exam["report_time"],
                "exam_no": exam_id,
                "exam_id": exam_id,
                "item_no": "1",
                "item_id": f"ITEM-{exam_id}",
                "item_code": exam["suffix"].upper(),
                "item_name": exam["exam_name"],
                "exam_name": exam["exam_name"],
                "exam_item_name": exam["exam_name"],
                "exam_type": exam["exam_type"],
                "exam_result": exam["findings"],
                "exam_findings": exam["findings"],
                "exam_impression": exam["conclusion"],
                "exam_conclusion": exam["conclusion"],
                "record_content": f"检查所见：{exam['findings']}\n诊断意见：{exam['conclusion']}",
                "report_time": exam["report_time"],
                "last_modified_datetime": exam["report_time"],
                "update_time": exam["report_time"],
            },
        )


def _lab_panels(case: Any, scenario: str) -> tuple[dict[str, Any], ...]:
    wbc = ("1.0", "PL") if scenario == "recorded_without_analysis_with_unhandled_critical" else ("6.8", "")
    potassium = ("6.8", "PH") if scenario == "all_compliant_with_handled_critical" else ("4.2", "")
    return (
        {
            "subject": "血常规检验报告",
            "specimen": "静脉全血",
            "request_time": V2._dt_for_case(case, 0, 8, 0),
            "collection_time": V2._dt_for_case(case, 0, 8, 20),
            "report_time": V2._dt_for_case(case, 0, 13, 0),
            "items": (
                ("WBC", "白细胞计数", *wbc, "3.5-9.5", "10^9/L"),
                ("RBC", "红细胞计数", "4.32", "", "3.8-5.1", "10^12/L"),
                ("HGB", "血红蛋白", "128", "", "115-150", "g/L"),
                ("PLT", "血小板计数", "226", "", "125-350", "10^9/L"),
                ("NEUT", "中性粒细胞百分比", "68.2", "", "40-75", "%"),
                ("LYMPH", "淋巴细胞百分比", "23.6", "", "20-50", "%"),
            ),
        },
        {
            "subject": "肝肾功能及电解质检验报告",
            "specimen": "血清",
            "request_time": V2._dt_for_case(case, 0, 8, 0),
            "collection_time": V2._dt_for_case(case, 0, 8, 25),
            "report_time": V2._dt_for_case(case, 0, 13, 30),
            "items": (
                ("ALT", "丙氨酸氨基转移酶", "35", "", "7-40", "U/L"),
                ("AST", "天门冬氨酸氨基转移酶", "28", "", "13-35", "U/L"),
                ("ALB", "白蛋白", "38.5", "", "35-55", "g/L"),
                ("CREA", "肌酐", "72", "", "41-81", "μmol/L"),
                ("UREA", "尿素", "5.6", "", "2.6-7.5", "mmol/L"),
                ("K", "钾", *potassium, "3.5-5.3", "mmol/L"),
                ("NA", "钠", "140", "", "137-147", "mmol/L"),
                ("GLU", "葡萄糖", "5.4", "", "3.9-6.1", "mmol/L"),
            ),
        },
        {
            "subject": "凝血功能检验报告",
            "specimen": "枸橼酸钠抗凝血浆",
            "request_time": V2._dt_for_case(case, 0, 8, 0),
            "collection_time": V2._dt_for_case(case, 0, 8, 30),
            "report_time": V2._dt_for_case(case, 0, 14, 0),
            "items": (
                ("PT", "凝血酶原时间", "12.1", "", "9.8-13.8", "s"),
                ("APTT", "活化部分凝血活酶时间", "31.0", "", "25-37", "s"),
                ("INR", "国际标准化比值", "1.02", "", "0.8-1.2", ""),
                ("FIB", "纤维蛋白原", "3.2", "", "2.0-4.0", "g/L"),
                ("DD", "D-二聚体", "0.82", "H", "0-0.55", "mg/L"),
            ),
        },
        {
            "subject": "尿培养及药敏检验报告",
            "specimen": "中段尿",
            "request_time": V2._dt_for_case(case, 0, 9, 0),
            "collection_time": V2._dt_for_case(case, 0, 9, 30),
            "report_time": V2._dt_for_case(case, 2, 10, 30),
            "items": (
                ("CULTURE", "培养结果", "培养阳性：检出大肠埃希菌", "阳性", "", ""),
                ("CFU", "菌落计数", ">10^5", "H", "<10^3", "CFU/mL"),
                ("CRO", "头孢曲松", "敏感", "S", "", ""),
                ("LEV", "左氧氟沙星", "耐药", "R", "", ""),
                ("MEM", "美罗培南", "敏感", "S", "", ""),
                ("TZP", "哌拉西林/他唑巴坦", "敏感", "S", "", ""),
            ),
        },
    )


def _append_lab_reports(
    rows_by_table: dict[str, list[dict[str, Any]]],
    case: Any,
    scenario: str,
) -> None:
    base = V2._case_base_row(case)
    for panel_index, panel in enumerate(_lab_panels(case, scenario), start=1):
        test_id = f"LAB-V3-{case.target_index:03d}-{panel_index:02d}"
        V2._append_row(
            rows_by_table,
            "labtest_master",
            {
                **base,
                "test_id": test_id,
                "order_id": f"ORDER-{test_id}",
                "labtest_subject": panel["subject"],
                "labtest_cause": "入院评估及病情复核",
                "specimen": panel["specimen"],
                "request_dept": base["dept_name"],
                "request_physician": "陈某医师",
                "request_datetime": panel["request_time"],
                "report_datetime": panel["report_time"],
                "reporter": "检验医师甲",
                "verifier": "检验医师乙",
                "labtest_result_status": "Final",
                "record_content": f"{panel['subject']}，标本：{panel['specimen']}；申请时间：{panel['request_time']}；采样时间：{panel['collection_time']}；报告时间：{panel['report_time']}；共{len(panel['items'])}项。",
                "last_modified_datetime": panel["report_time"],
                "update_time": panel["report_time"],
            },
        )
        for item_index, (code, name, result, flag, reference, unit) in enumerate(panel["items"], start=1):
            V2._append_row(
                rows_by_table,
                "labtest_item_report",
                {
                    **base,
                    "document_id": f"{test_id}-{code}",
                    "document_title": panel["subject"],
                    "document_status": "Submitted",
                    "submitter": "检验医师乙",
                    "submitter_id": "DEID-LAB",
                    "submit_datetime": panel["report_time"],
                    "record_time": panel["report_time"],
                    "test_no": test_id,
                    "test_id": test_id,
                    "item_no": str(item_index),
                    "item_id": f"{test_id}-{item_index:02d}",
                    "item_code": code,
                    "item_name": name,
                    "item_abbreviation": code,
                    "result": result,
                    "unit": unit,
                    "abnormal_indicator": flag,
                    "reference_range": reference,
                    "record_content": f"{name}：{result}{(' ' + unit) if unit else ''}；提示：{flag or '正常'}；参考范围：{reference or '-'}",
                    "report_time": panel["report_time"],
                    "last_modified_datetime": panel["report_time"],
                    "update_time": panel["report_time"],
                },
            )


def _append_exam_lab_orders(
    rows_by_table: dict[str, list[dict[str, Any]]],
    case: Any,
) -> None:
    base = V2._case_base_row(case)
    for suffix, name, prescribed_time in (
        ("mri", "腰椎MRI平扫", V2._dt_for_case(case, 1, 8, 0)),
        ("culture", "尿培养及药敏", V2._dt_for_case(case, 1, 8, 10)),
    ):
        V2._append_row(
            rows_by_table,
            "inpat_nondrug_order",
            {
                **base,
                "order_id": f"{case.target_visit_id}-order-{suffix}",
                "order_type": "检查检验",
                "order_name": name,
                "quantity": "1",
                "quantity_unit": "次",
                "frequency": "一次",
                "prescribed_datetime": prescribed_time,
                "prescribed_doctor": "陈某医师",
                "order_status": "执行中",
                "record_content": f"检查检验医嘱：{name}",
                "last_modified_datetime": prescribed_time,
                "update_time": prescribed_time,
            },
        )


def _append_exam_lab_scenario_courses(
    rows_by_table: dict[str, list[dict[str, Any]]],
    case: Any,
    scenario: str,
) -> None:
    if scenario == "all_missing":
        return
    _append_course_row(
        rows_by_table,
        case,
        suffix="pre-exam-reason",
        record_time=V2._dt_for_case(case, 1, 7, 0),
        content="患者腰痛伴右下肢放射性麻木，为明确腰椎神经受压部位及程度，拟行腰椎MRI检查。",
    )
    if scenario == "recorded_without_analysis_with_unhandled_critical":
        _append_course_row(
            rows_by_table,
            case,
            suffix="exam-result-only",
            record_time=V2._dt_for_case(case, 1, 18, 0),
            content="已查看腰椎MRI报告，报告提示L4/5椎间盘突出并右侧神经根受压。",
        )
        _append_course_row(
            rows_by_table,
            case,
            suffix="culture-result-only",
            record_time=V2._dt_for_case(case, 2, 15, 0),
            content="已查看尿培养报告，结果为大肠埃希菌阳性，药敏结果已回报。",
        )
        return
    _append_course_row(
        rows_by_table,
        case,
        suffix="exam-analysis",
        record_time=V2._dt_for_case(case, 1, 18, 0),
        content="已查看腰椎MRI报告，L4/5椎间盘突出并右侧神经根受压，与右下肢放射痛及直腿抬高试验阳性相符，结合症状分析考虑当前神经根受压明确，继续营养神经并请脊柱专科评估。",
    )
    _append_course_row(
        rows_by_table,
        case,
        suffix="culture-analysis",
        record_time=V2._dt_for_case(case, 2, 15, 0),
        content="已查看尿培养及药敏报告，大肠埃希菌阳性，对头孢曲松敏感、左氧氟沙星耐药；结合尿路刺激征考虑泌尿系感染，根据药敏停用左氧氟沙星并改用头孢曲松。",
    )


def _append_handled_critical_value(
    rows_by_table: dict[str, list[dict[str, Any]]],
    case: Any,
) -> None:
    base = V2._case_base_row(case)
    record_time = V2._dt_for_case(case, 0, 15, 30)
    V2._append_row(
        rows_by_table,
        "crisis_value_record",
        {
            **base,
            "document_id": f"{case.target_visit_id}-critical-value-k",
            "document_title": "危急值处理记录",
            "document_status": "Submitted",
            "submitter": "陈某医师",
            "submitter_id": "DEID",
            "submit_datetime": record_time,
            "record_datetime": record_time,
            "record_time": record_time,
            "dept_name": base["dept_name"],
            "record_content": "14:00接检验科危急值报告：血钾6.8mmol/L（PH）。立即复核标本并行心电监护，停用补钾药物，予降钾处理，通知上级医师，计划2小时后复查电解质。",
            "last_modified_datetime": record_time,
            "update_time": record_time,
        },
    )


def upgrade_exam_lab_evidence(
    rows_by_table: dict[str, list[dict[str, Any]]],
    cases: Sequence[Any],
) -> dict[str, Any]:
    target_cases = [case for case in cases if case.family == "检查检验"]
    visit_ids = {case.target_visit_id for case in target_cases}
    _replace_target_rows(
        rows_by_table,
        table_names=(
            "exam_master",
            "exam_item_report",
            "labtest_master",
            "labtest_item_report",
            "daily_course_record",
            "senior_course_record",
            "crisis_value_record",
            "first_course_record",
            "first_course_record_diagnosis",
        ),
        visit_ids=visit_ids,
    )
    # 受控病例不继承原病例的海量医嘱，避免新增 MRI/培养医嘱在
    # Evidence Snapshot 的 limit+1 边界之外形成伪数据缺口。
    rows_by_table["inpat_nondrug_order"] = [
        row
        for row in rows_by_table.get("inpat_nondrug_order", [])
        if str(row.get("visit_id") or "") not in visit_ids
    ]

    scenario_counts: Counter[str] = Counter()
    for case in target_cases:
        scenario = _EXAM_LAB_SCENARIO_BY_INDEX.get(
            int(case.target_index), "all_compliant"
        )
        scenario_counts[scenario] += 1
        _append_exam_lab_first_course(rows_by_table, case)
        _append_exam_lab_orders(rows_by_table, case)
        _append_exam_report_pair(rows_by_table, case)
        _append_lab_reports(rows_by_table, case, scenario)
        _append_exam_lab_scenario_courses(rows_by_table, case, scenario)
        if scenario == "all_compliant_with_handled_critical":
            _append_handled_critical_value(rows_by_table, case)
        expected_statuses = _exam_lab_expected_statuses(scenario)
        case.source_item["synthetic_golden_answers"] = [
            {
                "qc_point_id": rule_id,
                "expected_status": expected_statuses[rule_id],
                "expected_hit": expected_statuses[rule_id] == "non_compliant",
                "review_status": "pending",
                "human_reason": f"v3检查检验受控场景：{scenario}",
                "trigger_facts": [scenario],
            }
            for rule_id in _EXAM_LAB_RULE_IDS
        ]

    return {
        "case_count": len(target_cases),
        "scenario_counts": dict(scenario_counts),
        "exam_master_count": sum(
            1 for row in rows_by_table.get("exam_master", []) if row.get("visit_id") in visit_ids
        ),
        "exam_report_count": sum(
            1 for row in rows_by_table.get("exam_item_report", []) if row.get("visit_id") in visit_ids
        ),
        "lab_master_count": sum(
            1 for row in rows_by_table.get("labtest_master", []) if row.get("visit_id") in visit_ids
        ),
        "lab_item_count": sum(
            1 for row in rows_by_table.get("labtest_item_report", []) if row.get("visit_id") in visit_ids
        ),
        "critical_value_count": sum(
            1
            for row in rows_by_table.get("labtest_item_report", [])
            if row.get("visit_id") in visit_ids and row.get("abnormal_indicator") in {"PL", "PH"}
        ),
        "critical_disposition_count": sum(
            1 for row in rows_by_table.get("crisis_value_record", []) if row.get("visit_id") in visit_ids
        ),
    }


def refresh_exam_lab_supplement_audit(
    clone_audit: dict[str, Any],
    cases: Sequence[Any],
) -> None:
    """让样本项审计只描述 v3 当前真实写入的检查检验证据。"""
    target_cases = [case for case in cases if int(case.target_index) in _EXAM_LAB_SCENARIO_BY_INDEX]
    target_visit_ids = {case.target_visit_id for case in target_cases}
    retained = [
        dict(item)
        for item in clone_audit.get("supplemental_evidence_rows") or []
        if str(item.get("target_visit_id") or "") not in target_visit_ids
    ]
    for case in target_cases:
        retained.append(
            {
                "target_visit_id": case.target_visit_id,
                "source_visit_id": str(case.source_item.get("matched_visit_id") or ""),
                "rule_family": case.family,
                "table": "exam_item_report+labtest_item_report",
                "reason": "v3_controlled_exam_lab_report_set",
            }
        )
    clone_audit["supplemental_evidence_rows"] = retained


def upgrade_full_validation_evidence(
    rows_by_table: dict[str, list[dict[str, Any]]],
    cases: Sequence[Any],
) -> dict[str, Any]:
    exam_lab_audit = upgrade_exam_lab_evidence(rows_by_table, cases)
    rule_titles = {
        entry.rule_id: entry.qc_point for entry in load_luxian_0609_rule_master()
    }
    controlled_audit = apply_controlled_evidence(
        rows_by_table,
        cases,
        v2=V2,
        rule_titles=rule_titles,
    )
    admission_record_audit = ensure_v3_admission_record_evidence(rows_by_table, cases)
    timeline_audit = normalize_v3_stay_timeline(
        rows_by_table,
        cases,
        v2=V2,
    )
    return {
        **controlled_audit,
        "exam_lab": exam_lab_audit,
        "admission_record": admission_record_audit,
        "timeline": timeline_audit,
    }


def _admission_context_from_diagnosis(
    case: Any,
    diagnosis_name: str,
) -> tuple[str, str, str]:
    """按当前住院第一诊断选择相互一致的合成入院语境。

    v3 是验证资料，不应把规则族名称当作临床诊断的替代品。仅在已有入院
    记录缺失时补写资料；此处根据同一病例已有的入院诊断选择自然主诉，避免
    018 的“主诉能否导出第一诊断”被无关的族级模板污染。
    """

    diagnosis = str(diagnosis_name or "").strip()
    primary_diagnosis = re.split(r"[，,；;。]", diagnosis, maxsplit=1)[0].strip()
    primary_diagnosis = re.sub(r"^\s*\d+\s*[、.．:]?\s*", "", primary_diagnosis)
    diagnosis = primary_diagnosis or diagnosis
    if any(token in diagnosis for token in ("骨折", "关节", "半月板", "颈椎", "腰椎")):
        return (
            "患处疼痛、肿胀伴活动受限1天",
            f"患者因患处疼痛、肿胀伴活动受限1天入院，结合影像学检查考虑{diagnosis}。",
            f"结合患处症状、查体及影像学表现，支持当前住院第一诊断{diagnosis}。",
        )
    if any(token in diagnosis for token in ("阑尾", "腹膜炎", "肠梗阻", "腹痛", "大便", "痔", "肛裂")):
        return (
            "右下腹疼痛伴恶心1天",
            f"患者因右下腹疼痛伴恶心1天入院，结合腹部查体及辅助检查考虑{diagnosis}。",
            f"结合腹痛、腹部查体及辅助检查，支持当前住院第一诊断{diagnosis}。",
        )
    if any(token in diagnosis for token in ("癌", "肿瘤", "白血病", "恶性")):
        return (
            "发现肿块伴乏力1月",
            f"患者因发现肿块伴乏力1月入院，结合影像及病理资料考虑{diagnosis}。",
            f"结合肿块、乏力及影像病理资料，支持当前住院第一诊断{diagnosis}。",
        )
    if any(token in diagnosis for token in ("肺炎", "肺病", "呼吸衰竭", "肺栓塞", "感染")):
        return (
            "发热、咳嗽伴气促2天",
            f"患者因发热、咳嗽伴气促2天入院，结合胸部检查考虑{diagnosis}。",
            f"结合发热、咳嗽、气促及胸部检查，支持当前住院第一诊断{diagnosis}。",
        )
    if any(token in diagnosis for token in ("心肌梗死", "冠心病", "心脏", "心房颤动")):
        return (
            "胸闷、胸痛伴活动后气促1天",
            f"患者因胸闷、胸痛伴活动后气促1天入院，结合心电图及化验考虑{diagnosis}。",
            f"结合胸闷胸痛、心电图及化验结果，支持当前住院第一诊断{diagnosis}。",
        )
    if any(token in diagnosis for token in ("脑梗", "脑卒中", "头晕", "面瘫", "椎动脉")):
        return (
            "头晕伴一侧肢体乏力6小时",
            f"患者因头晕伴一侧肢体乏力6小时入院，结合神经系统查体及影像考虑{diagnosis}。",
            f"结合神经系统症状、查体及影像学资料，支持当前住院第一诊断{diagnosis}。",
        )
    if any(token in diagnosis for token in ("肾", "输尿管", "泌尿", "结石")):
        return (
            "腰部疼痛伴尿频2天",
            f"患者因腰部疼痛伴尿频2天入院，结合泌尿系检查考虑{diagnosis}。",
            f"结合腰痛、排尿症状及泌尿系检查，支持当前住院第一诊断{diagnosis}。",
        )
    if any(token in diagnosis for token in ("胆", "肝硬化", "肝衰竭", "腹水")):
        return (
            "右上腹疼痛伴乏力2天",
            f"患者因右上腹疼痛伴乏力2天入院，结合肝胆检查考虑{diagnosis}。",
            f"结合右上腹症状及肝胆相关检查，支持当前住院第一诊断{diagnosis}。",
        )
    if any(token in diagnosis for token in ("贫血", "营养不良")):
        return (
            "乏力、心悸伴面色苍白1个月",
            f"患者因乏力、心悸伴面色苍白1个月入院，结合血常规考虑{diagnosis}。",
            f"结合乏力、心悸、面色苍白及血常规，支持当前住院第一诊断{diagnosis}。",
        )
    if any(token in diagnosis for token in ("妊娠", "胎膜", "孕", "子宫", "阴道", "宫内")):
        return (
            "下腹坠胀伴阴道流液1天",
            f"患者因下腹坠胀伴阴道流液1天入院，结合妇科检查考虑{diagnosis}。",
            f"结合下腹症状、妇科查体及超声资料，支持当前住院第一诊断{diagnosis}。",
        )
    if any(token in diagnosis for token in ("耳", "听力", "鼓膜")):
        return (
            "耳闷伴听力下降1周",
            f"患者因耳闷伴听力下降1周入院，结合耳科检查考虑{diagnosis}。",
            f"结合耳部症状、查体及听力检查，支持当前住院第一诊断{diagnosis}。",
        )
    if any(token in diagnosis for token in ("疱疹", "蛇串疮")):
        return (
            "皮疹伴局部灼痛1周",
            f"患者因皮疹伴局部灼痛1周入院，结合皮肤及神经查体考虑{diagnosis}。",
            f"结合皮疹、灼痛及专科查体，支持当前住院第一诊断{diagnosis}。",
        )
    return _V3_ADMISSION_CONTEXT.get(
        str(case.family),
        (
            "不适伴症状加重",
            f"患者因不适伴症状加重入院，结合入院查体及辅助检查考虑{diagnosis}。",
            f"结合主诉、查体及入院辅助检查，支持当前住院第一诊断{diagnosis}。",
        ),
    )


def ensure_v3_admission_record_evidence(
    rows_by_table: dict[str, list[dict[str, Any]]],
    cases: Sequence[Any],
) -> dict[str, int]:
    """为每份 v3 病例补齐当前住院入院记录和主诉。

    018 的验证资料合同要求入院记录中的主诉。只在已有记录缺失或主诉为空时
    补写，不改变已有受控时限病例的记录时间，也不生成第二份资料链。
    """

    added = 0
    replaced_shell = 0
    diagnosis_added = 0
    for case in cases:
        visit_id = str(case.target_visit_id)
        stay_start = V2._dt_for_case(case, 0, 8, 0)
        stay_end = V2._dt_for_case(case, 12, 18, 0)

        def _has_current_record_time(row: dict[str, Any]) -> bool:
            for field in (
                "record_time",
                "record_datetime",
                "submit_datetime",
                "last_modified_datetime",
                "update_time",
            ):
                value = row.get(field)
                if isinstance(value, datetime):
                    parsed = value
                elif isinstance(value, str):
                    try:
                        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
                    except ValueError:
                        continue
                    parsed = parsed.replace(tzinfo=None)
                else:
                    continue
                if stay_start <= parsed <= stay_end:
                    return True
            return False

        existing = [
            row
            for row in rows_by_table.get("admission_record", [])
            if str(row.get("visit_id") or "") == visit_id
        ]
        admission_time = V2._dt_for_case(case, 0, 10, 0)
        has_chief_complaint = any(
            str(row.get("chief_complaint") or "").strip()
            and _has_current_record_time(row)
            for row in existing
        )
        if not has_chief_complaint:
            if existing:
                rows_by_table["admission_record"] = [
                    row
                    for row in rows_by_table.get("admission_record", [])
                    if str(row.get("visit_id") or "") != visit_id
                ]
                replaced_shell += len(existing)
            diagnosis_rows = [
                row
                for row in rows_by_table.get("admission_record_diagnosis", [])
                if str(row.get("visit_id") or "") == visit_id
                and str(row.get("diagnosis_type") or "").strip()
                in {"初步诊断", "入院诊断"}
                and str(row.get("diagnosis_name") or "").strip()
            ]
            diagnosis_name = str(
                next(
                    (
                        row.get("diagnosis_name")
                        for row in diagnosis_rows
                        if str(row.get("diagnosis_main") or "") == "1"
                    ),
                    diagnosis_rows[0].get("diagnosis_name")
                    if diagnosis_rows
                    else V2._family_diagnosis(case)[0],
                )
            )
            complaint, record_content, diagnosis_basis = _admission_context_from_diagnosis(
                case,
                diagnosis_name,
            )
            V2._append_row(
                rows_by_table,
                "admission_record",
                {
                    **V2._case_base_row(case),
                    "document_id": f"{visit_id}-admission-record-v3-contract",
                    "document_title": "入院记录",
                    "document_status": "completed",
                    "record_content": record_content,
                    "record_time": admission_time,
                    "record_datetime": admission_time,
                    "submit_datetime": admission_time,
                    "last_modified_datetime": admission_time,
                    "update_time": admission_time,
                    "submitter": "陈某医师",
                    "submitter_id": "DEID",
                    "admission_datetime": V2._dt_for_case(case, 0, 8, 0),
                    "chief_complaint": complaint,
                    "history_of_present_illness": "现病史已在入院记录中完整记录。",
                    "checkup": "入院查体已记录。",
                    "diagnose_based_on": diagnosis_basis,
                },
            )
            added += 1
        diagnosis_rows = [
            row
            for row in rows_by_table.get("admission_record_diagnosis", [])
            if str(row.get("visit_id") or "") == visit_id
            and str(row.get("diagnosis_type") or "").strip() in {"初步诊断", "入院诊断"}
            and str(row.get("diagnosis_name") or "").strip()
        ]
        if not diagnosis_rows:
            diagnosis_name, diagnosis_code = V2._family_diagnosis(case)
            diagnosis_id = f"{visit_id}-admission-diagnosis-v3-contract"
            V2._append_row(
                rows_by_table,
                "admission_record_diagnosis",
                {
                    **V2._case_base_row(case),
                    "document_id": f"{visit_id}-admission-record-v3-contract",
                    "diagnosis_id": diagnosis_id,
                    "diagnosis_main": "1",
                    "diagnosis_type": "入院诊断",
                    "diagnosis_no": 1,
                    "diagnosis_name": diagnosis_name,
                    "diagnosis_code": diagnosis_code,
                    "diagnosis_source": "v3_admission_record_contract",
                    "diagnosis_time": admission_time,
                    "record_time": admission_time,
                    "update_time": admission_time,
                },
            )
            diagnosis_added += 1
    return {
        "added": added,
        "replaced_shell": replaced_shell,
        "diagnosis_added": diagnosis_added,
    }


def build_coverage_ledger(
    cases: Sequence[Any],
    entries: Sequence[Luxian0609RuleMasterEntry] | None = None,
) -> list[dict[str, Any]]:
    master = tuple(entries or load_luxian_0609_rule_master())
    family_by_rule_id = {
        rule_id: family
        for family, rule_ids in build_master_family_rule_ids(master).items()
        for rule_id in rule_ids
    }
    cases_by_family: dict[str, list[Any]] = defaultdict(list)
    for case in cases:
        cases_by_family[case.family].append(case)

    ledger: list[dict[str, Any]] = []
    for entry in master:
        family = family_by_rule_id[entry.rule_id]
        family_cases = cases_by_family.get(family, [])
        assigned_cases = [
            case
            for case in family_cases
            if entry.rule_id in set(case.selected_rule_ids)
        ]
        if entry.implementation_status == "active":
            coverage_status = "assigned_pending_golden_review" if assigned_cases else "coverage_gap"
            candidate_cases = assigned_cases
            required_variants = ["compliant", "non_compliant"]
        elif entry.implementation_status == "contract_ready":
            coverage_status = (
                "candidate_family_available_executor_inactive"
                if family_cases
                else "candidate_family_gap_executor_inactive"
            )
            candidate_cases = family_cases
            required_variants = ["compliant", "non_compliant"]
        else:
            coverage_status = "blocked_definition"
            candidate_cases = []
            required_variants = []
        ledger.append(
            {
                "rule_id": entry.rule_id,
                "source_document": entry.source_document,
                "qc_point": entry.qc_point,
                "implementation_status": entry.implementation_status,
                "validation_family": family,
                "coverage_status": coverage_status,
                "required_variants": required_variants,
                "candidate_visit_ids": [case.target_visit_id for case in candidate_cases],
                "definition_note": entry.definition_note,
            }
        )
    return ledger


def _write_coverage_csv(path: Path, ledger: Sequence[dict[str, Any]]) -> None:
    fields = (
        "rule_id",
        "source_document",
        "qc_point",
        "implementation_status",
        "validation_family",
        "coverage_status",
        "required_variants",
        "candidate_visit_ids",
        "definition_note",
    )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in ledger:
            writer.writerow(
                {
                    **row,
                    "required_variants": "、".join(row["required_variants"]),
                    "candidate_visit_ids": "、".join(row["candidate_visit_ids"]),
                }
            )


def build_validation_matrix(cases: Sequence[Any]) -> list[dict[str, Any]]:
    matrix: list[dict[str, Any]] = []
    for case in cases:
        for answer in case.source_item.get("synthetic_golden_answers") or []:
            matrix.append(
                {
                    "rule_id": str(answer.get("qc_point_id") or ""),
                    "acceptance_tier": str(answer.get("acceptance_tier") or ""),
                    "definition_version": str(answer.get("definition_version") or ""),
                    "case_index": int(case.target_index),
                    "visit_id": case.target_visit_id,
                    "patient_name": case.target_patient_name,
                    "rule_family": case.family,
                    "expected_status": str(answer.get("expected_status") or ""),
                    "evidence_refs": json.dumps(answer.get("evidence_refs") or [], ensure_ascii=False),
                    "expected_fact": str(answer.get("human_reason") or ""),
                }
            )
    matrix.sort(key=lambda row: (row["rule_id"], row["expected_status"], row["case_index"]))
    rule_ids = {row["rule_id"] for row in matrix}
    if len(rule_ids) != 75:
        raise ValueError("v3 validation matrix must contain every rule")
    fixture_keys = {
        (row["rule_id"], row["expected_status"], row["case_index"])
        for row in matrix
    }
    if len(fixture_keys) != len(matrix):
        raise ValueError("v3 validation matrix contains duplicate rule/status fixtures")
    return matrix


def _write_validation_matrix(path: Path, matrix: Sequence[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(matrix[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(matrix)


def _render_report(
    *,
    source_pool: dict[str, Any],
    cases: Sequence[Any],
    selection_summary: dict[str, Any],
    clone_audit: dict[str, Any],
    forbidden_hits: dict[str, int],
    ledger: Sequence[dict[str, Any]],
    validation_matrix: Sequence[dict[str, Any]],
    write_summary: dict[str, Any] | None,
) -> str:
    coverage_counts = Counter(row["coverage_status"] for row in ledger)
    implementation_counts = Counter(row["implementation_status"] for row in ledger)
    definition_phase_by_rule = {
        contract.rule_id: contract.phase_status
        for contract in load_luxian_0609_rule_contracts()
    }
    definition_counts = Counter(definition_phase_by_rule.values())
    acceptance_tier_by_rule = {
        row["rule_id"]: row["acceptance_tier"] for row in validation_matrix
    }
    acceptance_counts = Counter(acceptance_tier_by_rule.values())
    defined_rule_ids = {
        rule_id
        for rule_id, phase_status in definition_phase_by_rule.items()
        if phase_status != "pending_definition"
    }
    defined_assertion_count = sum(
        row["rule_id"] in defined_rule_ids for row in validation_matrix
    )
    lines = [
        "# LX0609 0426 派生合成验证集 v3 构建报告",
        "",
        f"- 目标标识：`{TARGET_POOL_ID}` / {TARGET_POOL_NAME}",
        f"- 源样本池：`{source_pool.get('id')}` / {source_pool.get('name')}",
        f"- 候选病历：{len(cases)} 份",
        f"- 写库状态：{'已写入' if write_summary else 'dry-run，未写数据库'}",
        (
            f"- 黄金答案：75条规则共 {len(validation_matrix)} 个多状态受控断言；"
            f"标准层级为 {acceptance_counts['formal']} 条正式、"
            f"{acceptance_counts['provisional']} 条临时"
        ),
        (
            f"- 本阶段收敛范围：{len(defined_rule_ids)} 条规则、"
            f"{defined_assertion_count} 个断言；"
            f"另有 {definition_counts['pending_definition']} 条待确认规则不计入本轮验收"
        ),
        "",
        "## 唯一规则总表口径",
        "",
        f"- 总规则：{len(ledger)}",
        f"- 当前启用：{implementation_counts['active']}",
        f"- 合同就绪、执行器未启用：{implementation_counts['contract_ready']}",
        f"- 执行器尚未实现：{implementation_counts['pending_definition']}",
        f"- 定义完整：{definition_counts['phase_1_target']}",
        f"- 部分定义：{definition_counts['phase_1_partial']}",
        f"- 待客户确认：{definition_counts['pending_definition']}",
        f"- 已分配候选、待黄金复核：{coverage_counts['assigned_pending_golden_review']}",
        f"- 当前启用规则覆盖缺口：{coverage_counts['coverage_gap']}",
        "",
        "## 分层抽样",
        "",
        "| 规则族 | 配额 | 已选 |",
        "|---|---:|---:|",
    ]
    selected_counts = Counter(case.family for case in cases)
    for family, quota in FAMILY_QUOTAS.items():
        lines.append(f"| {family} | {quota} | {selected_counts[family]} |")
    lines.extend(
        [
            "",
            "## 数据质量边界",
            "",
            f"- 禁止词命中：`{json.dumps(forbidden_hits, ensure_ascii=False)}`",
            f"- 空壳核心文书过滤：{len(clone_audit.get('skipped_shell_documents') or [])} 条",
            f"- 派生证据补全：{len(clone_audit.get('supplemental_evidence_rows') or [])} 条",
            f"- 检查报告：{int((clone_audit.get('exam_lab_upgrade') or {}).get('exam_report_count') or 0)} 份",
            f"- 检验报告组：{int((clone_audit.get('exam_lab_upgrade') or {}).get('lab_master_count') or 0)} 组，明细 {int((clone_audit.get('exam_lab_upgrade') or {}).get('lab_item_count') or 0)} 项",
            f"- 危急值场景：{int((clone_audit.get('exam_lab_upgrade') or {}).get('critical_value_count') or 0)} 个，其中已处置 {int((clone_audit.get('exam_lab_upgrade') or {}).get('critical_disposition_count') or 0)} 个",
            f"- 已覆盖规则：{int((clone_audit.get('full_validation_upgrade') or {}).get('rule_count') or 0)} 条",
            f"- 验收口径：`{json.dumps((clone_audit.get('full_validation_upgrade') or {}).get('tier_counts') or {}, ensure_ascii=False)}`",
            f"- 来源配额缺口：`{json.dumps(selection_summary.get('source_gaps') or {}, ensure_ascii=False)}`",
            "",
            "## 使用限制",
            "",
            "- `assigned_pending_golden_review` 只表示已分配真实结构候选，不表示规则已通过验证。",
            "- `contract_ready` 规则不得加入当前执行请求，直到执行器接入并完成回归。",
            "- `pending_definition` 规则不生成占位结果，也不计入完成率。",
            "- 未使用 `--write-db` 时仅生成审计产物；确认后可显式写入本机验证库。",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the master-driven LX0609 0426 synthetic validation set v3 (dry-run only)."
    )
    parser.add_argument("--source-pool", default=SOURCE_POOL_NAME)
    parser.add_argument("--target-size", type=int, default=sum(FAMILY_QUOTAS.values()))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--write-db", action="store_true", help="Write audited v3 rows and sample pool items to local DB.")
    parser.add_argument("--replace-items", action="store_true", help="Replace existing v3 rows and sample pool items.")
    args = parser.parse_args(argv)
    if args.target_size < sum(FAMILY_QUOTAS.values()):
        raise ValueError(f"v3 target-size must be at least {sum(FAMILY_QUOTAS.values())}")

    _configure_v2_compatibility()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    source_pool, source_items = V2.load_source_pool_items(args.source_pool)
    raw_cases, selection_summary = V2.build_selection(
        source_pool=source_pool,
        source_items=source_items,
        target_size=args.target_size,
    )
    cases = _assign_full_validation_family_scope(raw_cases)
    rows_by_table, clone_audit = V2.build_clone_rows(cases)
    clone_audit["full_validation_upgrade"] = upgrade_full_validation_evidence(rows_by_table, cases)
    clone_audit["exam_lab_upgrade"] = clone_audit["full_validation_upgrade"]["exam_lab"]
    refresh_exam_lab_supplement_audit(clone_audit, cases)
    forbidden_hits = V2.forbidden_token_hits(rows_by_table)
    ledger = build_coverage_ledger(cases)
    validation_matrix = build_validation_matrix(cases)
    write_summary = None
    if args.write_db:
        write_summary = V2.write_pool_and_items(
            source_pool=source_pool,
            cases=cases,
            rows_by_table=rows_by_table,
            supplemental_rows=clone_audit.get("supplemental_evidence_rows") or [],
            replace_items=bool(args.replace_items),
        )

    V2.write_selection_csv(output_dir / "selection.csv", cases)
    _write_validation_matrix(output_dir / "validation-matrix.csv", validation_matrix)
    V2.write_text_lf(
        output_dir / "deid-audit.json",
        json.dumps(
            {
                "selection_summary": selection_summary,
                "clone_audit": clone_audit,
                "forbidden_token_hits": forbidden_hits,
                "write_summary": write_summary,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
        + "\n",
    )
    V2.write_text_lf(
        output_dir / "rule-coverage-ledger.json",
        json.dumps(ledger, ensure_ascii=False, indent=2) + "\n",
    )
    _write_coverage_csv(output_dir / "rule-coverage-ledger.csv", ledger)
    V2.write_text_lf(
        output_dir / "validation-report.md",
        _render_report(
            source_pool=source_pool,
            cases=cases,
            selection_summary=selection_summary,
            clone_audit=clone_audit,
            forbidden_hits=forbidden_hits,
            ledger=ledger,
            validation_matrix=validation_matrix,
            write_summary=write_summary,
        ),
    )

    coverage_counts = Counter(row["coverage_status"] for row in ledger)
    print(f"selected={len(cases)}")
    print(f"selected_counts={dict(Counter(case.family for case in cases))}")
    print(f"master_rules={len(ledger)}")
    print(f"coverage_counts={dict(coverage_counts)}")
    print(f"forbidden_token_hits={forbidden_hits}")
    print(f"wrote={output_dir}")
    print(f"db_write={'yes' if args.write_db else 'no'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
