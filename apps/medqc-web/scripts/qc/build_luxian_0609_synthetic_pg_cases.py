from __future__ import annotations

import argparse
import json
import sys
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.database.connection import DB_SCHEMA_MODE, engine  # noqa: E402
from backend.app.database.connection import Base  # noqa: E402
from backend.app.database.models import cdm as _cdm_models  # noqa: F401,E402


DOCS_DIR = ROOT / "docs" / "0602"
RUNTIME_DIR = ROOT / ".runtime-logs" / "qc-synthetic"
CATALOG_PATH = DOCS_DIR / "luxian_0609_formal_rule_catalog.json"
SYNTHETIC_CASES_PATH = DOCS_DIR / "luxian_0609_synthetic_cases_v1.json"

SYNTHETIC_PREFIX = "LX0609_SYN_"
POOL_NAME = "泸县0609合成质控样本 v1"
POOL_ID = "luxian-0609-synthetic-v1"
INSTITUTE_ID = "LX0609_SYN"
VISIT_TYPE = "住院"

ALLOWED_STATUSES = {"non_compliant", "compliant", "not_applicable", "data_gap", "uncertain"}


@dataclass(frozen=True)
class EvidenceField:
    table: str
    field: str
    value: str | None = None
    quote: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"table": self.table, "field": self.field}
        if self.value is not None:
            data["value"] = self.value
        if self.quote is not None:
            data["quote"] = self.quote
        return data


@dataclass(frozen=True)
class GoldenAnswer:
    qc_point_id: str
    expected_status: str
    expected_hit: bool
    trigger_facts: list[str]
    evidence_fields: list[EvidenceField]
    human_reason: str
    case_type: str = "positive"

    def to_dict(self, case_id: str, visit_id: str) -> dict[str, Any]:
        return {
            "case_id": case_id,
            "visit_id": visit_id,
            "expected_status": self.expected_status,
            "expected_hit": self.expected_hit,
            "trigger_facts": self.trigger_facts,
            "evidence_fields": [item.to_dict() for item in self.evidence_fields],
            "evidence_expectation": "；".join(
                [
                    *(self.trigger_facts or []),
                    *[
                        item.quote or item.value or f"{item.table}.{item.field}"
                        for item in self.evidence_fields
                    ],
                ]
            ),
            "human_reason": self.human_reason,
            "source": "synthetic_pg_fixture",
        }


@dataclass
class SyntheticVisit:
    visit_id: str
    patient_name: str
    sex: str
    age: int
    dept_name: str
    admission_time: datetime
    discharge_time: datetime
    main_diagnosis: str
    other_diagnoses: list[str]
    description: str
    rows: dict[str, list[dict[str, Any]]] = field(default_factory=lambda: defaultdict(list))
    golden_answers: list[GoldenAnswer] = field(default_factory=list)

    @property
    def patient_id(self) -> str:
        return f"P-{self.visit_id}"

    @property
    def inpat_no(self) -> str:
        return self.visit_id

    @property
    def mr_no(self) -> str:
        return self.visit_id


def dt(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M")


def d(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def now() -> datetime:
    return datetime(2026, 6, 13, 9, 0)


def common_identity(visit: SyntheticVisit) -> dict[str, Any]:
    return {
        "institute_id": INSTITUTE_ID,
        "patient_id": visit.patient_id,
        "visit_id": visit.visit_id,
        "visit_type": VISIT_TYPE,
        "inpat_no": visit.inpat_no,
        "mr_no": visit.mr_no,
        "name": visit.patient_name,
        "sex": visit.sex,
        "age_year": str(visit.age),
        "age": f"{visit.age}岁",
        "dept_name": visit.dept_name,
        "update_time": now(),
        "last_modified_datetime": now(),
    }


def add_row(visit: SyntheticVisit, table: str, row: dict[str, Any]) -> None:
    visit.rows[table].append({k: v for k, v in row.items() if v is not None})


def doc_id(visit: SyntheticVisit, suffix: str) -> str:
    return f"{visit.visit_id}-{suffix}"


def doc_row(
    visit: SyntheticVisit,
    table: str,
    suffix: str,
    title: str,
    content: str,
    *,
    submit_time: datetime | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    row = {
        **common_identity(visit),
        "document_id": doc_id(visit, suffix),
        "document_title": title,
        "document_status": "已提交",
        "submitter": "测试医师",
        "submitter_id": "SYN-DOCTOR",
        "submit_datetime": submit_time or visit.admission_time,
        "record_content": content.strip(),
    }
    if extra:
        row.update(extra)
    add_row(visit, table, row)


def add_core_rows(visit: SyntheticVisit) -> None:
    birth_year = visit.admission_time.year - visit.age
    patient_content = f"姓名：{visit.patient_name}；性别：{visit.sex}；年龄：{visit.age}岁；住院号：{visit.inpat_no}。"
    add_row(
        visit,
        "patient_information",
        {
            "institute_id": INSTITUTE_ID,
            "patient_id": visit.patient_id,
            "name": visit.patient_name,
            "sex": visit.sex,
            "birthday": date(birth_year, 1, 10),
            "id_card_type": "居民身份证",
            "id_card_no": f"510521{birth_year}0110{visit.visit_id[-3:]}X",
            "ethnicity": "汉族",
            "nationality": "中国",
            "marital_status": "已婚",
            "contact_number": f"1390000{visit.visit_id[-4:]}",
            "currentaddress": "四川省泸州市泸县合成测试地址",
            "contact_name": f"{visit.patient_name}家属",
            "contact_relationship": "配偶",
            "contact_telephone": f"1380000{visit.visit_id[-4:]}",
            "record_content": patient_content,
            "update_time": now(),
        },
    )
    add_row(
        visit,
        "inpat_registration",
        {
            **common_identity(visit),
            "visit_cnt": "1",
            "birthday": date(birth_year, 1, 10),
            "charge_type": "城镇职工基本医疗保险",
            "insurance_type": "医保",
            "admission_dept_name": visit.dept_name,
            "discharge_dept_name": visit.dept_name,
            "admission_datetime": visit.admission_time,
            "discharge_datetime": visit.discharge_time,
            "record_content": f"{patient_content}入院科室：{visit.dept_name}；出院科室：{visit.dept_name}。",
        },
    )
    add_row(
        visit,
        "mr",
        {
            **common_identity(visit),
            "document_id": doc_id(visit, "MR"),
            "institute_code": "H51052100267",
            "institute_county_desc": "泸县人民医院",
            "visit_cnt": "1",
            "birthday": date(birth_year, 1, 10),
            "nationality": "中国",
            "ethnicity": "汉族",
            "marital_status": "已婚",
            "admission_route": "1",
            "admission_datetime": visit.admission_time,
            "admission_condition": "1",
            "admission_dept_name": visit.dept_name,
            "discharge_datetime": visit.discharge_time,
            "discharge_dept_name": visit.dept_name,
            "hospital_duration": str(max((visit.discharge_time.date() - visit.admission_time.date()).days, 1)),
            "resident_physician_sign": "住院医师A",
            "attending_physician_sign": "主治医师B",
            "chief_physician_sign": "主任医师C",
            "mr_datetime": visit.discharge_time,
            "record_content": f"合成病案首页：{visit.patient_name}，主要诊断：{visit.main_diagnosis}。",
        },
    )
    diagnoses = [("1", "出院主要诊断", visit.main_diagnosis), *[
        (str(index + 2), "出院其他诊断", name)
        for index, name in enumerate(visit.other_diagnoses)
    ]]
    for diagnosis_no, diagnosis_type, diagnosis_name in diagnoses:
        add_row(
            visit,
            "diagnosis",
            {
                **common_identity(visit),
                "document_id": doc_id(visit, "DIAG"),
                "diagnosis_id": f"{visit.visit_id}-D{diagnosis_no}",
                "diagnosis_type": diagnosis_type,
                "diagnosis_no": diagnosis_no,
                "diagnosis_name": diagnosis_name,
                "diagnosis_code": "",
                "admission_condition": "1",
                "diagnosis_source": "synthetic_fixture",
                "diagnosis_datetime": visit.discharge_time,
            },
        )
    add_row(
        visit,
        "mr_cost",
        {
            **common_identity(visit),
            "document_id": doc_id(visit, "COST"),
            "total_cost": "18500.00",
            "self_pay": "3200.00",
            "laboratory_diagnostic_fee": "720.00",
            "imaging_diagnostic_fee": "980.00",
            "surgery_treatment_fee": "4500.00",
            "anesthesia_fee": "1200.00",
            "blood_fee": "0.00",
            "settle_datetime": visit.discharge_time,
        },
    )


def add_standard_admission(
    visit: SyntheticVisit,
    *,
    submit_offset_hours: float,
    chief: str,
    first_course_offset_hours: float,
    first_course_text: str | None = None,
) -> None:
    admission_submit = visit.admission_time + timedelta(hours=submit_offset_hours)
    admission_text = f"""
入院记录
记录时间：{admission_submit:%Y-%m-%d %H:%M}
患者{visit.patient_name}，{visit.sex}，{visit.age}岁，因“{chief}”入院。
现病史：患者入院前出现相关症状，入院后完善体格检查及辅助检查。
既往史：否认特殊传染病史。
体格检查：生命体征平稳，专科查体见阳性体征。
初步诊断：{visit.main_diagnosis}。
住院医师：测试医师。
"""
    add_row(
        visit,
        "admission_record",
        {
            **common_identity(visit),
            "document_id": doc_id(visit, "ADM"),
            "document_title": "入院记录",
            "document_status": "已提交",
            "submitter": "测试医师",
            "submit_datetime": admission_submit,
            "admission_datetime": visit.admission_time,
            "dept_name": visit.dept_name,
            "chief_complaint": chief,
            "history_of_present_illness": "入院前出现相关症状，入院后完善检查。",
            "past_history": "否认特殊传染病史。",
            "checkup": "生命体征平稳，专科查体见阳性体征。",
            "record_content": admission_text.strip(),
            "resident_physician_sign": "测试医师",
        },
    )
    first_time = visit.admission_time + timedelta(hours=first_course_offset_hours)
    doc_row(
        visit,
        "first_course_record",
        "FIRST",
        "首次病程记录",
        first_course_text
        or f"""
首次病程记录
记录时间：{first_time:%Y-%m-%d %H:%M}
病例特点：患者因“{chief}”入院，初步诊断考虑{visit.main_diagnosis}。
诊断依据：结合症状、体征及辅助检查。
诊疗计划：完善相关检查，予以对症治疗。
记录医师：测试医师。
""",
        submit_time=first_time,
        extra={"record_datetime": first_time, "physician_sign": "测试医师"},
    )


def golden(
    qc_point_id: str,
    status: str,
    hit: bool,
    facts: list[str],
    evidence: list[tuple[str, str, str]],
    reason: str,
    *,
    case_type: str | None = None,
) -> GoldenAnswer:
    if status not in ALLOWED_STATUSES:
        raise ValueError(f"Unsupported status: {status}")
    return GoldenAnswer(
        qc_point_id=qc_point_id,
        expected_status=status,
        expected_hit=hit,
        trigger_facts=facts,
        evidence_fields=[
            EvidenceField(table=table, field=field, quote=value)
            for table, field, value in evidence
        ],
        human_reason=reason,
        case_type=case_type or ("positive" if hit else "negative"),
    )


def build_visit_001() -> SyntheticVisit:
    visit = SyntheticVisit(
        visit_id="LX0609_SYN_001",
        patient_name="时限缺陷一",
        sex="男",
        age=66,
        dept_name="神经内科",
        admission_time=dt("2026-06-01 08:00"),
        discharge_time=dt("2026-06-08 10:00"),
        main_diagnosis="脑梗死",
        other_diagnoses=["高血压病3级"],
        description="基础时限缺陷样本：入院记录、首次病程、48/72小时查房均超时或缺失。",
    )
    add_core_rows(visit)
    add_standard_admission(
        visit,
        submit_offset_hours=26.5,
        chief="右侧肢体乏力5小时",
        first_course_offset_hours=10.5,
    )
    doc_row(
        visit,
        "senior_course_record",
        "ROUND-LATE",
        "主任医师查房记录",
        """
主任医师查房记录
记录时间：2026-06-04 13:30
主任医师查房后认为患者目前诊断脑梗死明确，继续抗血小板及改善循环治疗。
""",
        submit_time=dt("2026-06-04 13:30"),
    )
    doc_row(
        visit,
        "discharge_record",
        "DIS",
        "出院记录",
        "出院记录\n诊疗经过：患者经治疗后症状改善。\n出院诊断：脑梗死；高血压病3级。",
        submit_time=visit.discharge_time,
    )
    visit.golden_answers.extend(
        [
            golden("LX0609-001", "non_compliant", True, ["入院时间为2026-06-01 08:00", "入院记录提交时间为2026-06-02 10:30，超过24小时"], [("admission_record", "submit_datetime", "2026-06-02 10:30")], "入院记录超过入院后24小时完成。"),
            golden("LX0609-002", "non_compliant", True, ["首次病程记录时间为2026-06-01 18:30", "距离入院10.5小时"], [("first_course_record", "record_datetime", "2026-06-01 18:30")], "首次病程记录未在入院后8小时内完成。"),
            golden("LX0609-005", "non_compliant", True, ["入院后48小时内未见主治医师首次查房记录"], [("senior_course_record", "record_content", "主任医师查房记录")], "48小时内缺少主治医师首次查房记录。"),
            golden("LX0609-006", "non_compliant", True, ["主任医师查房记录在入院后77.5小时出现"], [("senior_course_record", "submit_datetime", "2026-06-04 13:30")], "72小时内未完成高级职称医师首次查房记录。"),
        ]
    )
    return visit


def build_visit_002() -> SyntheticVisit:
    visit = SyntheticVisit(
        visit_id="LX0609_SYN_002",
        patient_name="时限合规二",
        sex="女",
        age=58,
        dept_name="消化内科",
        admission_time=dt("2026-06-02 09:00"),
        discharge_time=dt("2026-06-07 11:00"),
        main_diagnosis="急性胃炎",
        other_diagnoses=["低钾血症"],
        description="基础时限合规样本：关键文书均按时完成。",
    )
    add_core_rows(visit)
    add_standard_admission(
        visit,
        submit_offset_hours=3,
        chief="上腹痛伴恶心1天",
        first_course_offset_hours=2.5,
    )
    doc_row(
        visit,
        "senior_course_record",
        "ATTENDING",
        "主治医师查房记录",
        "主治医师查房记录\n记录时间：2026-06-03 08:30\n主治医师查房后同意目前诊断和治疗方案。",
        submit_time=dt("2026-06-03 08:30"),
    )
    doc_row(
        visit,
        "senior_course_record",
        "CHIEF",
        "主任医师查房记录",
        "主任医师查房记录\n记录时间：2026-06-04 08:00\n主任医师查房后指导继续完善检查并调整治疗。",
        submit_time=dt("2026-06-04 08:00"),
    )
    doc_row(visit, "daily_course_record", "D1", "日常病程记录", "日常病程记录\n患者腹痛较前缓解，继续抑酸补液治疗。", submit_time=dt("2026-06-03 10:00"))
    doc_row(visit, "discharge_record", "DIS", "出院记录", "出院记录\n诊疗经过：患者经治疗后腹痛缓解。\n出院医嘱：清淡饮食，门诊随访。", submit_time=visit.discharge_time)
    visit.golden_answers.extend(
        [
            golden("LX0609-001", "compliant", False, ["入院记录在入院后3小时完成"], [("admission_record", "submit_datetime", "2026-06-02 12:00")], "入院记录时限合规。", case_type="negative"),
            golden("LX0609-002", "compliant", False, ["首次病程记录在入院后2.5小时完成"], [("first_course_record", "record_datetime", "2026-06-02 11:30")], "首次病程时限合规。", case_type="negative"),
            golden("LX0609-005", "compliant", False, ["48小时内有主治医师查房记录"], [("senior_course_record", "record_content", "主治医师查房记录")], "48小时主治医师查房合规。", case_type="negative"),
            golden("LX0609-006", "compliant", False, ["72小时内有主任医师查房记录"], [("senior_course_record", "record_content", "主任医师查房记录")], "72小时高级职称查房合规。", case_type="negative"),
        ]
    )
    return visit


def build_visit_003() -> SyntheticVisit:
    visit = SyntheticVisit(
        visit_id="LX0609_SYN_003",
        patient_name="病重查房三",
        sex="女",
        age=76,
        dept_name="呼吸与危重症医学科",
        admission_time=dt("2026-06-09 07:50"),
        discharge_time=dt("2026-06-15 09:30"),
        main_diagnosis="重症肺炎",
        other_diagnoses=["慢性阻塞性肺疾病急性加重"],
        description="病重患者查房缺陷样本。",
    )
    add_core_rows(visit)
    add_standard_admission(visit, submit_offset_hours=4, chief="咳嗽咳痰伴气促3天", first_course_offset_hours=3)
    add_row(
        visit,
        "inpat_nondrug_order",
        {
            **common_identity(visit),
            "order_id": doc_id(visit, "ORD-CRIT-SERIOUS"),
            "order_type": "护理",
            "order_name": "病重",
            "prescribed_datetime": dt("2026-06-09 08:20"),
            "prescribed_doctor": "测试医师",
            "order_status": "执行中",
            "record_content": "2026-06-09 08:20 下达病重医嘱，持续执行。",
        },
    )
    doc_row(visit, "daily_course_record", "D-0909", "日常病程记录", "日常病程记录\n记录时间：2026-06-09 10:00\n患者咳嗽咳痰，予抗感染及吸氧治疗。", submit_time=dt("2026-06-09 10:00"))
    doc_row(visit, "daily_course_record", "D-0612", "日常病程记录", "日常病程记录\n记录时间：2026-06-12 09:30\n患者仍气促，继续抗感染治疗，复查胸部CT。", submit_time=dt("2026-06-12 09:30"))
    doc_row(visit, "discharge_record", "DIS", "出院记录", "出院记录\n患者肺部感染较前吸收，出院后呼吸科随访。", submit_time=visit.discharge_time)
    visit.golden_answers.extend(
        [
            golden("LX0609-008", "non_compliant", True, ["2026-06-09 08:20下达病重医嘱", "2026-06-10、2026-06-11未见查房病程记录"], [("inpat_nondrug_order", "order_name", "病重"), ("daily_course_record", "record_content", "2026-06-12 09:30")], "病重患者2天内缺少查房病程记录。"),
            golden("LX0609-009", "not_applicable", False, ["未下达病危医嘱"], [("inpat_nondrug_order", "order_name", "病重")], "该样本只有病重医嘱，不适用于病危每日记录规则。", case_type="boundary"),
            golden("LX0609-007", "not_applicable", False, ["患者存在病重医嘱，不属于病情稳定患者"], [("inpat_nondrug_order", "record_content", "下达病重医嘱")], "病情稳定3天查房规则不适用。", case_type="boundary"),
        ]
    )
    return visit


def build_visit_004() -> SyntheticVisit:
    visit = SyntheticVisit(
        visit_id="LX0609_SYN_004",
        patient_name="抢救记录四",
        sex="男",
        age=69,
        dept_name="急诊医学科",
        admission_time=dt("2026-06-05 06:30"),
        discharge_time=dt("2026-06-10 10:00"),
        main_diagnosis="急性心力衰竭",
        other_diagnoses=["心律失常"],
        description="抢救记录超6小时样本。",
    )
    add_core_rows(visit)
    add_standard_admission(visit, submit_offset_hours=2, chief="胸闷气促2小时", first_course_offset_hours=2)
    doc_row(
        visit,
        "rescue_record",
        "RESCUE",
        "抢救记录",
        """
抢救记录
抢救开始时间：2026-06-05 08:10
抢救结束时间：2026-06-05 12:00
记录时间：2026-06-05 20:30
患者突发呼吸困难，经吸氧、利尿、强心等处理后症状缓解。
""",
        submit_time=dt("2026-06-05 20:30"),
    )
    doc_row(visit, "discharge_record", "DIS", "出院记录", "出院记录\n治疗后心衰症状改善，嘱心内科随访。", submit_time=visit.discharge_time)
    visit.golden_answers.extend(
        [
            golden("LX0609-004", "non_compliant", True, ["抢救结束时间2026-06-05 12:00", "抢救记录记录时间2026-06-05 20:30"], [("rescue_record", "record_content", "抢救结束时间：2026-06-05 12:00"), ("rescue_record", "submit_datetime", "2026-06-05 20:30")], "抢救记录超过抢救结束后6小时完成。"),
            golden("LX0609-001", "compliant", False, ["入院记录入院后2小时完成"], [("admission_record", "submit_datetime", "2026-06-05 08:30")], "入院记录时限合规。", case_type="negative"),
            golden("LX0609-002", "compliant", False, ["首次病程入院后2小时完成"], [("first_course_record", "record_datetime", "2026-06-05 08:30")], "首次病程时限合规。", case_type="negative"),
        ]
    )
    return visit


def build_visit_005() -> SyntheticVisit:
    visit = SyntheticVisit(
        visit_id="LX0609_SYN_005",
        patient_name="检查培养五",
        sex="女",
        age=64,
        dept_name="骨科",
        admission_time=dt("2026-06-03 09:00"),
        discharge_time=dt("2026-06-09 09:30"),
        main_diagnosis="腰椎间盘突出症",
        other_diagnoses=["尿路感染"],
        description="CT/MRI阳性结果和细菌培养阳性结果未及时分析样本。",
    )
    add_core_rows(visit)
    add_standard_admission(visit, submit_offset_hours=2, chief="腰痛伴右下肢麻木半月", first_course_offset_hours=2)
    add_row(visit, "exam_master", {**common_identity(visit), "exam_id": doc_id(visit, "EXAM-MRI"), "exam_no": doc_id(visit, "EXAM-MRI"), "exam_name": "腰椎MRI", "request_datetime": dt("2026-06-03 10:00"), "report_datetime": dt("2026-06-03 14:20"), "record_content": "腰椎MRI申请与报告。"})
    doc_row(
        visit,
        "exam_item_report",
        "MRI",
        "腰椎MRI检查报告",
        "腰椎MRI报告\n报告时间：2026-06-03 14:20\n所见：L4/5椎间盘向右后方突出，压迫右侧神经根。\n结论：L4/5椎间盘突出并右侧神经根受压。",
        submit_time=dt("2026-06-03 14:20"),
        extra={"exam_no": doc_id(visit, "EXAM-MRI"), "exam_id": doc_id(visit, "EXAM-MRI"), "exam_name": "腰椎MRI", "exam_type": "MRI", "exam_conclusion": "L4/5椎间盘突出并右侧神经根受压", "report_time": dt("2026-06-03 14:20")},
    )
    add_row(visit, "labtest_master", {**common_identity(visit), "test_id": doc_id(visit, "LAB-CULTURE"), "labtest_subject": "尿培养", "specimen": "尿液", "request_datetime": dt("2026-06-03 11:00"), "report_datetime": dt("2026-06-04 09:10"), "labtest_result_status": "已报告", "record_content": "尿培养申请。"})
    doc_row(
        visit,
        "labtest_item_report",
        "CULTURE",
        "尿培养报告",
        "尿培养报告\n报告时间：2026-06-04 09:10\n结果：大肠埃希菌生长，菌落计数>10^5 CFU/ml，药敏提示头孢曲松敏感。",
        submit_time=dt("2026-06-04 09:10"),
        extra={"test_id": doc_id(visit, "LAB-CULTURE"), "item_name": "尿培养", "result": "大肠埃希菌生长", "abnormal_indicator": "阳性", "report_time": dt("2026-06-04 09:10")},
    )
    doc_row(visit, "daily_course_record", "D-0603", "日常病程记录", "日常病程记录\n记录时间：2026-06-03 19:00\n患者仍诉腰痛，右下肢麻木同前。已完善腰椎MRI检查，继续予止痛、营养神经治疗。", submit_time=dt("2026-06-03 19:00"))
    doc_row(visit, "daily_course_record", "D-0604", "日常病程记录", "日常病程记录\n记录时间：2026-06-04 18:00\n患者腰痛稍缓解，继续卧床休息及对症治疗，尿频较前减轻。", submit_time=dt("2026-06-04 18:00"))
    doc_row(visit, "discharge_record", "DIS", "出院记录", "出院记录\n出院诊断：腰椎间盘突出症；尿路感染。出院后骨科门诊复查。", submit_time=visit.discharge_time)
    visit.golden_answers.extend(
        [
            golden("LX0609-010", "non_compliant", True, ["行腰椎MRI检查前未见说明检查必要性的病程记录"], [("exam_item_report", "record_content", "腰椎MRI报告"), ("daily_course_record", "record_content", "已完善腰椎MRI检查")], "MRI检查前缺少有针对性的病程记录说明。"),
            golden("LX0609-012", "non_compliant", True, ["2026-06-03 14:20腰椎MRI阳性报告", "报告后24小时内病程未分析阳性结果与症状、诊断或治疗方案关系"], [("exam_item_report", "exam_conclusion", "L4/5椎间盘突出并右侧神经根受压"), ("daily_course_record", "record_content", "继续予止痛、营养神经治疗")], "MRI阳性结果未在24小时内进行临床分析。"),
            golden("LX0609-014", "non_compliant", True, ["2026-06-04 09:10尿培养阳性", "24小时内病程未针对阳性菌和药敏调整治疗进行分析"], [("labtest_item_report", "result", "大肠埃希菌生长"), ("daily_course_record", "record_content", "尿频较前减轻")], "细菌培养阳性结果未在病程中及时分析。"),
        ]
    )
    return visit


def build_visit_006() -> SyntheticVisit:
    visit = SyntheticVisit(
        visit_id="LX0609_SYN_006",
        patient_name="复制逻辑六",
        sex="男",
        age=45,
        dept_name="普通外科",
        admission_time=dt("2026-06-06 08:20"),
        discharge_time=dt("2026-06-12 10:10"),
        main_diagnosis="急性阑尾炎",
        other_diagnoses=["腹痛待查"],
        description="复制病历和主诉诊断逻辑缺陷样本。",
    )
    add_core_rows(visit)
    repeated = "患者一般情况尚可，生命体征平稳，腹部查体较前无明显变化，继续目前治疗方案。"
    add_standard_admission(
        visit,
        submit_offset_hours=3,
        chief="不适3天",
        first_course_offset_hours=3,
        first_course_text=f"首次病程记录\n记录时间：2026-06-06 11:20\n病例特点：{repeated}\n拟诊讨论：患者主诉较笼统，第一诊断依据记录不足。\n诊疗计划：完善检查。",
    )
    doc_row(visit, "daily_course_record", "D1", "日常病程记录", f"日常病程记录\n记录时间：2026-06-07 09:00\n{repeated}", submit_time=dt("2026-06-07 09:00"))
    doc_row(visit, "daily_course_record", "D2", "日常病程记录", f"日常病程记录\n记录时间：2026-06-08 09:00\n{repeated}", submit_time=dt("2026-06-08 09:00"))
    doc_row(visit, "discharge_record", "DIS", "出院记录", "出院记录\n诊疗经过：完善检查后考虑急性阑尾炎，予抗感染治疗后症状缓解。", submit_time=visit.discharge_time)
    visit.golden_answers.extend(
        [
            golden("LX0609-016", "non_compliant", True, ["首次病程与连续日常病程存在高度重复段落"], [("first_course_record", "record_content", repeated), ("daily_course_record", "record_content", repeated)], "多份病程记录核心描述高度重复，存在复制病历风险。"),
            golden("LX0609-017", "non_compliant", True, ["主诉为“不适3天”，不能导出第一诊断急性阑尾炎"], [("admission_record", "chief_complaint", "不适3天"), ("diagnosis", "diagnosis_name", "急性阑尾炎")], "主诉过于笼统，无法支撑第一诊断。"),
            golden("LX0609-018", "non_compliant", True, ["首次病程拟诊讨论未充分说明第一诊断依据"], [("first_course_record", "record_content", "第一诊断依据记录不足")], "首次病程诊断分析不足。"),
        ]
    )
    return visit


def build_visit_007() -> SyntheticVisit:
    visit = SyntheticVisit(
        visit_id="LX0609_SYN_007",
        patient_name="会诊质量七",
        sex="女",
        age=71,
        dept_name="心血管内科",
        admission_time=dt("2026-06-04 09:10"),
        discharge_time=dt("2026-06-12 09:00"),
        main_diagnosis="冠状动脉粥样硬化性心脏病",
        other_diagnoses=["2型糖尿病"],
        description="会诊目的、会诊意见与执行记录缺陷样本。",
    )
    add_core_rows(visit)
    add_standard_admission(visit, submit_offset_hours=2, chief="胸闷伴活动后气促1周", first_course_offset_hours=3)
    doc_row(
        visit,
        "consultation_record",
        "CONS",
        "内分泌科会诊记录",
        """
会诊申请
申请时间：2026-06-05 09:00
会诊目的：请会诊。
会诊意见：建议完善相关检查，继续目前治疗，必要时调整用药。
会诊医师：会诊医师A。
""",
        submit_time=dt("2026-06-05 11:00"),
    )
    doc_row(visit, "daily_course_record", "D-CONS", "日常病程记录", "日常病程记录\n记录时间：2026-06-06 10:00\n建议完善相关检查，继续目前治疗，必要时调整用药。", submit_time=dt("2026-06-06 10:00"))
    doc_row(visit, "discharge_record", "DIS", "出院记录", "出院记录\n患者胸闷改善，嘱心内科、内分泌科门诊随访。", submit_time=visit.discharge_time)
    visit.golden_answers.extend(
        [
            golden("LX0609-020", "non_compliant", True, ["会诊目的仅写“请会诊”"], [("consultation_record", "record_content", "会诊目的：请会诊")], "会诊申请未明确会诊目的。"),
            golden("LX0609-021", "non_compliant", True, ["会诊意见笼统，缺少针对性诊疗建议"], [("consultation_record", "record_content", "建议完善相关检查，继续目前治疗")], "会诊意见过于笼统，不具备可执行性。"),
            golden("LX0609-022", "non_compliant", True, ["后续病程照抄会诊意见，未记录执行情况"], [("daily_course_record", "record_content", "建议完善相关检查，继续目前治疗")], "病程记录未说明会诊意见执行情况。"),
        ]
    )
    return visit


def build_visit_008() -> SyntheticVisit:
    visit = SyntheticVisit(
        visit_id="LX0609_SYN_008",
        patient_name="手术麻醉八",
        sex="男",
        age=62,
        dept_name="肝胆外科",
        admission_time=dt("2026-06-01 08:30"),
        discharge_time=dt("2026-06-09 10:00"),
        main_diagnosis="胆囊结石伴慢性胆囊炎急性发作",
        other_diagnoses=["胆总管结石"],
        description="手术、术前讨论、麻醉和安全核查缺陷样本。",
    )
    add_core_rows(visit)
    add_standard_admission(visit, submit_offset_hours=2, chief="右上腹痛3小时", first_course_offset_hours=3)
    add_row(
        visit,
        "mr_surgery",
        {
            **common_identity(visit),
            "document_id": doc_id(visit, "MR-SURG"),
            "surgery_id": doc_id(visit, "SURG-01"),
            "surgery_name": "腹腔镜胆囊切除术",
            "surgery_code": "",
            "surgical_level": "三级",
            "anesthesia_method": "全身麻醉",
            "surgery_begin_datetime": dt("2026-06-03 09:00"),
            "surgery_end_datetime": dt("2026-06-03 10:40"),
            "surgeon": "手术医师A",
            "first_assistant": "助手B",
            "anesthesiologist": "麻醉医师C",
            "main_surgery_sign": "1",
        },
    )
    add_row(visit, "surgery_application", {**common_identity(visit), "application_id": doc_id(visit, "SURG-APP"), "order_id": doc_id(visit, "ORD-SURG"), "surgery_name": "腹腔镜胆囊切除术", "surgery_level": "三级", "anesthesia_method": "全身麻醉", "surgeon": "手术医师A", "request_surgery_datetime": dt("2026-06-02 15:00"), "record_content": "申请行腹腔镜胆囊切除术。"})
    doc_row(visit, "presurg_summary", "PRESUM", "术前小结", "术前小结\n患者胆囊结石伴慢性胆囊炎急性发作，拟行腹腔镜胆囊切除术。", submit_time=dt("2026-06-02 16:00"))
    doc_row(visit, "presurg_discussion", "PREDISC", "术前讨论记录", "术前讨论记录\n讨论意见：拟行腹腔镜胆囊切除术。未记录替代方案、主要风险和参会人员具体意见。", submit_time=dt("2026-06-02 17:00"))
    doc_row(visit, "surgery_safecheck_record", "SAFE", "手术安全核查记录", "手术安全核查记录\n患者身份、手术部位、术式核查记录不完整，麻醉前核查项未签名。", submit_time=dt("2026-06-03 08:50"))
    doc_row(visit, "anesthesia_record", "ANE", "麻醉记录", "麻醉记录\n麻醉方式：全身麻醉。麻醉开始时间：2026-06-03 08:50。术中生命体征记录间断，出室评分未填写。", submit_time=dt("2026-06-03 11:00"))
    doc_row(visit, "surgery_record", "SURG", "手术记录", "手术记录\n手术时间：2026-06-03 09:00-10:40。手术名称：腹腔镜胆囊切除术。手术经过顺利。记录时间：2026-06-04 14:00。", submit_time=dt("2026-06-04 14:00"))
    doc_row(visit, "postsurg_firstcourse_record", "POST", "术后首次病程记录", "术后首次病程记录\n患者术后安返病房，切口敷料干燥。", submit_time=dt("2026-06-03 13:00"))
    doc_row(visit, "surgery_inform_consent", "CONSENT", "手术知情同意书", "手术知情同意书\n拟行腹腔镜胆囊切除术，患者签名，手术医师签名。", submit_time=dt("2026-06-02 15:30"))
    doc_row(visit, "discharge_record", "DIS", "出院记录", "出院记录\n患者术后恢复可，出院后普通外科门诊随访。", submit_time=visit.discharge_time)
    visit.golden_answers.extend(
        [
            golden("LX0609-003", "non_compliant", True, ["手术结束2026-06-03 10:40", "手术记录提交2026-06-04 14:00"], [("surgery_record", "submit_datetime", "2026-06-04 14:00")], "手术记录超过术后24小时完成。"),
            golden("LX0609-039", "non_compliant", True, ["术前讨论未记录替代方案、主要风险和参会人员具体意见"], [("presurg_discussion", "record_content", "未记录替代方案、主要风险")], "术前讨论内容不完整。"),
            golden("LX0609-032", "non_compliant", True, ["手术安全核查记录不完整，麻醉前核查项未签名"], [("surgery_safecheck_record", "record_content", "麻醉前核查项未签名")], "手术安全核查记录存在缺项。"),
            golden("LX0609-038", "non_compliant", True, ["麻醉记录生命体征记录间断，出室评分未填写"], [("anesthesia_record", "record_content", "出室评分未填写")], "麻醉记录填写不完整。"),
        ]
    )
    return visit


def build_visit_009() -> SyntheticVisit:
    visit = SyntheticVisit(
        visit_id="LX0609_SYN_009",
        patient_name="肿瘤化疗九",
        sex="女",
        age=59,
        dept_name="胃肠外科",
        admission_time=dt("2026-06-02 08:00"),
        discharge_time=dt("2026-06-16 09:00"),
        main_diagnosis="胃恶性肿瘤",
        other_diagnoses=["贫血"],
        description="恶性肿瘤、病理、化疗和出院后治疗计划样本。",
    )
    add_core_rows(visit)
    add_standard_admission(visit, submit_offset_hours=3, chief="上腹部隐痛伴消瘦2月", first_course_offset_hours=4)
    add_row(visit, "mr_surgery", {**common_identity(visit), "document_id": doc_id(visit, "MR-SURG"), "surgery_id": doc_id(visit, "SURG-01"), "surgery_name": "腹腔镜远端胃癌根治术", "surgical_level": "四级", "surgery_begin_datetime": dt("2026-06-06 09:00"), "surgery_end_datetime": dt("2026-06-06 13:30"), "surgeon": "手术医师A", "main_surgery_sign": "1"})
    doc_row(visit, "presurg_discussion", "PREDISC", "术前讨论记录", "术前讨论记录\n患者拟行四级手术腹腔镜远端胃癌根治术，未见MDT多学科讨论记录。", submit_time=dt("2026-06-05 16:00"))
    doc_row(visit, "surgery_record", "SURG", "手术记录", "手术记录\n手术名称：腹腔镜远端胃癌根治术。术中切除胃远端病灶，记录未明确淋巴结清扫范围及送检组数。", submit_time=dt("2026-06-06 16:00"))
    add_row(visit, "pathology_exam_master", {**common_identity(visit), "pathology_exam_id": doc_id(visit, "PATH"), "pathology_id": "P-LX0609-009", "clinical_history": "胃恶性肿瘤术后", "surgery_name": "腹腔镜远端胃癌根治术", "specimen_name": "胃远端及淋巴结", "request_datetime": dt("2026-06-06 14:00"), "record_content": "胃远端及淋巴结病理申请。"})
    add_row(visit, "pathology_exam_report", {**common_identity(visit), "pathology_exam_id": doc_id(visit, "PATH"), "pathology_id": "P-LX0609-009", "specimen_name": "胃远端及淋巴结", "diagnosis": "胃腺癌，中分化，浸润至浆膜下层。淋巴结转移情况待补充。", "report_status": "已审核", "report_datetime": dt("2026-06-10 10:00"), "record_content": "病理诊断：胃腺癌，中分化，浸润至浆膜下层。"})
    add_row(visit, "inpat_drug_order", {**common_identity(visit), "order_id": doc_id(visit, "ORD-CHEMO"), "drug_type": "化疗药", "generic_name": "奥沙利铂", "drug_apply_method": "静脉滴注", "prescribed_datetime": dt("2026-06-12 09:00"), "prescribed_doctor": "肿瘤医师A", "order_status": "执行", "record_content": "奥沙利铂静脉滴注化疗医嘱。"})
    doc_row(visit, "daily_course_record", "D-CHEMO", "日常病程记录", "日常病程记录\n记录时间：2026-06-12 18:00\n患者术后恢复可，继续补液、护胃、营养支持治疗。", submit_time=dt("2026-06-12 18:00"))
    doc_row(
        visit,
        "discharge_record",
        "DIS",
        "出院记录",
        "出院记录\n住院经过：患者行腹腔镜远端胃癌根治术，术后恢复可。\n出院医嘱：注意休息，保持切口清洁，1周后门诊复查拆线，如有不适随诊。",
        submit_time=visit.discharge_time,
        extra={"discharge_order": "注意休息，保持切口清洁，1周后门诊复查拆线，如有不适随诊。"},
    )
    visit.golden_answers.extend(
        [
            golden("LX0609-013", "non_compliant", True, ["病理报告提示胃腺癌", "病程和首页未充分记录病理诊断分析"], [("pathology_exam_report", "diagnosis", "胃腺癌，中分化")], "恶性肿瘤病理信息未充分进入病程/首页质控证据链。"),
            golden("LX0609-019", "non_compliant", True, ["胃癌根治术记录未明确淋巴结清扫范围及送检组数"], [("surgery_record", "record_content", "未明确淋巴结清扫范围及送检组数")], "恶性肿瘤手术记录未体现淋巴结清扫关键信息。"),
            golden("LX0609-040", "non_compliant", True, ["四级手术术前讨论未见MDT记录"], [("presurg_discussion", "record_content", "未见MDT多学科讨论记录")], "四级手术缺少MDT或高级别术前讨论支撑。"),
            golden("LX0609-027", "non_compliant", True, ["出院医嘱未包含肿瘤科复诊、辅助化疗评估或病理回看计划"], [("discharge_record", "discharge_order", "注意休息，保持切口清洁")], "恶性肿瘤出院后治疗计划不完整。"),
        ]
    )
    return visit


def build_visit_010() -> SyntheticVisit:
    visit = SyntheticVisit(
        visit_id="LX0609_SYN_010",
        patient_name="输血质控十",
        sex="男",
        age=54,
        dept_name="骨科",
        admission_time=dt("2026-06-07 08:00"),
        discharge_time=dt("2026-06-15 09:00"),
        main_diagnosis="股骨干骨折",
        other_diagnoses=["失血性贫血"],
        description="输血申请、记录、费用和评价缺陷样本。",
    )
    add_core_rows(visit)
    add_standard_admission(visit, submit_offset_hours=3, chief="外伤后右大腿疼痛活动受限2小时", first_course_offset_hours=4)
    add_row(visit, "blood_application", {**common_identity(visit), "application_id": doc_id(visit, "BLOOD-APP"), "patient_bloodtype_abo": "A型", "patient_bloodtype_rhd": "阳性", "transfuse_variety": "红细胞悬液", "transfuse_volume": "2", "transfuse_volume_unit": "U", "request_datetime": dt("2026-06-08 10:00"), "physician_name": "测试医师", "record_content": "申请输注红细胞悬液2U，未见完整输血风险告知记录。"})
    add_row(visit, "inpat_nondrug_order", {**common_identity(visit), "order_id": doc_id(visit, "ORD-BLOOD"), "order_type": "输血", "order_name": "输注红细胞悬液2U", "prescribed_datetime": dt("2026-06-08 10:10"), "prescribed_doctor": "测试医师", "order_status": "执行", "record_content": "输注红细胞悬液2U。"})
    doc_row(visit, "bloodtrans_record", "BLOOD-REC", "输血记录", "输血记录\n输血开始时间：2026-06-08 14:00\n输血品种：红细胞悬液2U。\n输血过程顺利。记录未见输血后疗效评价及不良反应观察结论。", submit_time=dt("2026-06-08 17:00"))
    doc_row(visit, "daily_course_record", "D-BLOOD", "日常病程记录", "日常病程记录\n记录时间：2026-06-08 18:00\n患者术前准备中，已申请输血支持，继续补液及止痛治疗。", submit_time=dt("2026-06-08 18:00"))
    add_row(visit, "inpat_bill_item", {**common_identity(visit), "bill_item_id": doc_id(visit, "BILL-BLOOD"), "order_id": doc_id(visit, "ORD-BLOOD"), "item_type": "血费", "medical_catalog_name": "红细胞悬液", "quantity": "4", "quantity_unit": "U", "cost": "1800.00", "charge": "1800.00", "billing_datetime": dt("2026-06-08 17:30"), "record_content": "红细胞悬液收费4U。"})
    doc_row(visit, "discharge_record", "DIS", "出院记录", "出院记录\n患者骨折术后恢复可，贫血较前改善，出院后骨科门诊随访。", submit_time=visit.discharge_time)
    visit.golden_answers.extend(
        [
            golden("LX0609-041", "non_compliant", True, ["存在输血申请和输血医嘱", "未见完整输血知情同意记录"], [("blood_application", "record_content", "未见完整输血风险告知记录")], "输血前知情同意资料不完整。"),
            golden("LX0609-043", "non_compliant", True, ["存在输血申请和输血医嘱", "未见乙肝、丙肝、梅毒、HIV等输血前常规检查结果"], [("blood_application", "record_content", "申请输注红细胞悬液2U")], "输血前常规检查资料不完整。"),
            golden("LX0609-047", "non_compliant", True, ["输血记录未见输血后疗效评价及不良反应观察结论"], [("bloodtrans_record", "record_content", "未见输血后疗效评价")], "输血后评价记录不完整。"),
            golden("LX0609-049", "non_compliant", True, ["医嘱输血2U", "费用明细收费4U"], [("inpat_nondrug_order", "order_name", "输注红细胞悬液2U"), ("inpat_bill_item", "record_content", "红细胞悬液收费4U")], "输血医嘱与收费数量不一致。"),
        ]
    )
    return visit


def build_visits() -> list[SyntheticVisit]:
    visits = [
        build_visit_001(),
        build_visit_002(),
        build_visit_003(),
        build_visit_004(),
        build_visit_005(),
        build_visit_006(),
        build_visit_007(),
        build_visit_008(),
        build_visit_009(),
        build_visit_010(),
    ]
    for visit in visits:
        add_sample_pool_rows(visit)
    return visits


def add_sample_pool_rows(visit: SyntheticVisit) -> None:
    raw_payload = {
        "source": "synthetic_pg_fixture",
        "visit_id": visit.visit_id,
        "patient_id": visit.patient_id,
        "institute_id": INSTITUTE_ID,
        "description": visit.description,
        "golden_qc_points": [item.qc_point_id for item in visit.golden_answers],
    }
    add_row(
        visit,
        "manual_problem_sample_pool_items",
        {
            "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"{POOL_ID}:{visit.visit_id}")),
            "pool_id": POOL_ID,
            "row_no": int(visit.visit_id.rsplit("_", 1)[-1]),
            "department": visit.dept_name,
            "patient_name": visit.patient_name,
            "mr_no": visit.mr_no,
            "manual_issue_text": visit.description,
            "normalized_issue_text": visit.description,
            "doctor_name": "测试医师",
            "qc_date": date(2026, 6, 13),
            "qc_user": "synthetic",
            "coverage_type": "llm_intrinsic",
            "issue_category": "泸县0609合成样本",
            "expected_scene": "running",
            "candidate_rule_ids_json": json.dumps(
                [item.qc_point_id for item in visit.golden_answers],
                ensure_ascii=False,
            ),
            "include_in_batch_1": True,
            "exclude_reason": "",
            "matched_institute_id": INSTITUTE_ID,
            "matched_patient_id": visit.patient_id,
            "matched_visit_id": visit.visit_id,
            "match_status": "matched",
            "sync_status": "synthetic_seeded",
            "bundle_status": "ready",
            "latest_match_status": "matched",
            "raw_payload_json": json.dumps(raw_payload, ensure_ascii=False),
            "created_at": now(),
            "updated_at": now(),
        },
    )


def build_pool_row(total_items: int) -> dict[str, Any]:
    return {
        "id": POOL_ID,
        "name": POOL_NAME,
        "source_file": "synthetic://luxian_0609_synthetic_cases_v1",
        "source_sheet": "synthetic",
        "scene": "running",
        "description": "泸县0609质控点合成 PG 一致样本池，仅用于规则验证，不混入真实生产病历。",
        "created_by": "synthetic",
        "created_at": now(),
        "updated_at": now(),
        "total_items": total_items,
        "llm_intrinsic_items": total_items,
        "programmatic_items": 0,
        "unsupported_items": 0,
        "matched_items": total_items,
        "ambiguous_items": 0,
        "unmatched_items": 0,
        "ready_items": total_items,
        "latest_job_status": "ready",
    }


def collect_rows(visits: list[SyntheticVisit]) -> dict[str, list[dict[str, Any]]]:
    rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    rows["manual_problem_sample_pools"].append(build_pool_row(len(visits)))
    for visit in visits:
        for table, table_rows in visit.rows.items():
            rows[table].extend(table_rows)
    return dict(rows)


MANUAL_TABLE_SPECS: dict[str, dict[str, Any]] = {
    "manual_problem_sample_pools": {
        "columns": [
            "id",
            "name",
            "source_file",
            "source_sheet",
            "scene",
            "description",
            "created_by",
            "created_at",
            "updated_at",
            "total_items",
            "llm_intrinsic_items",
            "programmatic_items",
            "unsupported_items",
            "matched_items",
            "ambiguous_items",
            "unmatched_items",
            "ready_items",
            "latest_job_id",
            "latest_job_status",
        ],
        "primary_key": ["id"],
        "schema": "qc" if DB_SCHEMA_MODE == "split" else None,
    },
    "manual_problem_sample_pool_items": {
        "columns": [
            "id",
            "pool_id",
            "row_no",
            "department",
            "patient_name",
            "mr_no",
            "manual_issue_text",
            "normalized_issue_text",
            "doctor_name",
            "qc_date",
            "qc_user",
            "coverage_type",
            "issue_category",
            "expected_scene",
            "candidate_rule_ids_json",
            "include_in_batch_1",
            "exclude_reason",
            "matched_institute_id",
            "matched_patient_id",
            "matched_visit_id",
            "match_status",
            "sync_status",
            "bundle_status",
            "latest_job_id",
            "latest_match_status",
            "raw_payload_json",
            "created_at",
            "updated_at",
        ],
        "primary_key": ["id"],
        "schema": "qc" if DB_SCHEMA_MODE == "split" else None,
    },
    "exam_master": {
        "columns": [
            "institute_id",
            "patient_id",
            "visit_id",
            "visit_type",
            "exam_id",
            "exam_no",
            "inpat_no",
            "name",
            "sex",
            "age_year",
            "dept_name",
            "exam_name",
            "exam_type",
            "request_datetime",
            "report_datetime",
            "record_content",
            "update_time",
        ],
        "primary_key": ["institute_id", "patient_id", "visit_id", "exam_id"],
        "schema": None,
    },
}


def table_specs() -> dict[str, dict[str, Any]]:
    specs: dict[str, dict[str, Any]] = {}
    for table in Base.metadata.sorted_tables:
        specs[table.name] = {
            "columns": [column.name for column in table.columns],
            "primary_key": [column.name for column in table.primary_key.columns],
            "schema": table.schema,
        }
    specs.update(MANUAL_TABLE_SPECS)
    return specs


def filtered_rows(rows: dict[str, list[dict[str, Any]]]) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    specs = table_specs()
    errors: list[str] = []
    result: dict[str, list[dict[str, Any]]] = {}
    for table, table_rows in rows.items():
        spec = specs.get(table)
        if not spec:
            errors.append(f"未找到表规格: {table}")
            continue
        allowed = set(spec["columns"])
        filtered: list[dict[str, Any]] = []
        for row in table_rows:
            cleaned = {key: value for key, value in row.items() if key in allowed}
            missing_pk = [key for key in spec["primary_key"] if cleaned.get(key) in (None, "")]
            if missing_pk:
                errors.append(f"{table} 缺少主键字段: {', '.join(missing_pk)}")
            filtered.append(cleaned)
        result[table] = filtered
    return result, errors


def sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, datetime):
        return "'" + value.strftime("%Y-%m-%d %H:%M:%S") + "'"
    if isinstance(value, date):
        return "'" + value.isoformat() + "'"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value).replace("'", "''")
    return f"'{text}'"


def qident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def qtable(table: str, schema: str | None = None) -> str:
    return f"{qident(schema)}.{qident(table)}" if schema else qident(table)


def make_delete_sql(table: str, spec: dict[str, Any]) -> list[str]:
    target = qtable(table, spec.get("schema"))
    if table == "manual_problem_sample_pool_items":
        return [f"DELETE FROM {target} WHERE matched_visit_id LIKE '{SYNTHETIC_PREFIX}%';"]
    if table == "manual_problem_sample_pools":
        return [f"DELETE FROM {target} WHERE id = {sql_literal(POOL_ID)} OR name = {sql_literal(POOL_NAME)};"]
    if "visit_id" in spec["columns"]:
        return [f"DELETE FROM {target} WHERE visit_id LIKE '{SYNTHETIC_PREFIX}%';"]
    return []


def make_insert_sql(table: str, spec: dict[str, Any], rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        return []
    target = qtable(table, spec.get("schema"))
    columns = sorted({key for row in rows for key in row.keys()})
    values_sql = []
    for row in rows:
        values_sql.append("(" + ", ".join(sql_literal(row.get(column)) for column in columns) + ")")
    conflict_columns = spec["primary_key"]
    sql = [
        f"INSERT INTO {target} ({', '.join(qident(column) for column in columns)})",
        "VALUES",
        ",\n".join(values_sql),
    ]
    if conflict_columns:
        update_columns = [column for column in columns if column not in conflict_columns]
        if update_columns:
            sql.append(
                "ON CONFLICT ("
                + ", ".join(qident(column) for column in conflict_columns)
                + ") DO UPDATE SET "
                + ", ".join(f"{qident(column)} = EXCLUDED.{qident(column)}" for column in update_columns)
            )
        else:
            sql.append("ON CONFLICT DO NOTHING")
    sql.append(";")
    return ["\n".join(sql)]


def build_sql_preview(rows: dict[str, list[dict[str, Any]]]) -> str:
    specs = table_specs()
    lines = [
        "-- 泸县0609合成质控样本 SQL preview",
        "-- 默认仅作为人工复核，不会由 dry-run 自动执行。",
        "BEGIN;",
        "",
    ]
    for table in sorted(rows):
        spec = specs[table]
        lines.extend(make_delete_sql(table, spec))
    lines.append("")
    for table in sorted(rows):
        spec = specs[table]
        lines.extend(make_insert_sql(table, spec, rows[table]))
        lines.append("")
    lines.append("COMMIT;")
    return "\n".join(lines) + "\n"


def build_synthetic_cases_json(visits: list[SyntheticVisit], rows: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    return {
        "version": "2026-06-13",
        "pool": {
            "id": POOL_ID,
            "name": POOL_NAME,
            "visit_prefix": SYNTHETIC_PREFIX,
            "mode": "dry-run-first",
        },
        "summary": {
            "visit_count": len(visits),
            "table_count": len(rows),
            "row_count": sum(len(items) for items in rows.values()),
            "golden_answer_count": sum(len(visit.golden_answers) for visit in visits),
        },
        "visits": [
            {
                "visit_id": visit.visit_id,
                "patient_id": visit.patient_id,
                "patient_name": visit.patient_name,
                "sex": visit.sex,
                "age": visit.age,
                "department": visit.dept_name,
                "description": visit.description,
                "golden_answers": [
                    answer.to_dict(
                        f"{visit.visit_id}-{answer.qc_point_id}-{index:02d}",
                        visit.visit_id,
                    )
                    | {"qc_point_id": answer.qc_point_id, "case_type": answer.case_type}
                    for index, answer in enumerate(visit.golden_answers, start=1)
                ],
            }
            for visit in visits
        ],
        "rows": {
            table: [json_ready(row) for row in table_rows]
            for table, table_rows in sorted(rows.items())
        },
    }


def build_golden_patch(visits: list[SyntheticVisit]) -> dict[str, Any]:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    by_rule: dict[str, dict[str, Any]] = {
        item["qc_point_id"]: {
            "qc_point_id": item["qc_point_id"],
            "source_index": item.get("source_index"),
            "customer_text": item.get("customer_text"),
            "implementation_status": item.get("implementation_status"),
            "cases": {"positive": [], "negative": [], "boundary": []},
        }
        for item in catalog
    }
    for visit in visits:
        for index, answer in enumerate(visit.golden_answers, start=1):
            rule = by_rule.setdefault(
                answer.qc_point_id,
                {
                    "qc_point_id": answer.qc_point_id,
                    "cases": {"positive": [], "negative": [], "boundary": []},
                },
            )
            case_type = answer.case_type if answer.case_type in {"positive", "negative", "boundary"} else "boundary"
            case = answer.to_dict(
                f"{visit.visit_id}-{answer.qc_point_id}-{index:02d}",
                visit.visit_id,
            )
            rule["cases"][case_type].append(case)
    return {
        "version": "2026-06-13",
        "description": "泸县0609合成 PG 样本生成的 golden case patch；dry-run 产物，不自动覆盖正式 golden cases。",
        "rules": [by_rule[key] for key in sorted(by_rule)],
    }


def json_ready(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_ready(item) for item in value]
    return value


def validate(visits: list[SyntheticVisit], rows: dict[str, list[dict[str, Any]]]) -> list[str]:
    errors: list[str] = []
    catalog_ids = {str(item.get("qc_point_id")) for item in json.loads(CATALOG_PATH.read_text(encoding="utf-8"))}
    visit_ids = [visit.visit_id for visit in visits]
    if len(visits) != 10:
        errors.append(f"样本数应为10，实际为{len(visits)}。")
    duplicate_ids = [item for item, count in Counter(visit_ids).items() if count > 1]
    if duplicate_ids:
        errors.append(f"visit_id 重复: {', '.join(duplicate_ids)}")
    for visit in visits:
        if not visit.visit_id.startswith(SYNTHETIC_PREFIX):
            errors.append(f"{visit.visit_id} 不符合合成样本前缀。")
        for required in ("patient_information", "inpat_registration", "mr", "diagnosis"):
            if not any(row.get("visit_id") == visit.visit_id or row.get("patient_id") == visit.patient_id for row in rows.get(required, [])):
                errors.append(f"{visit.visit_id} 缺少 {required} 数据。")
        if len(visit.golden_answers) < 3:
            errors.append(f"{visit.visit_id} golden answer 少于3条。")
        for answer in visit.golden_answers:
            if answer.qc_point_id not in catalog_ids:
                errors.append(f"{visit.visit_id} 引用不存在的质控点 {answer.qc_point_id}。")
            if answer.expected_status not in ALLOWED_STATUSES:
                errors.append(f"{visit.visit_id} {answer.qc_point_id} 状态非法: {answer.expected_status}。")
            for evidence in answer.evidence_fields:
                matching_rows = rows.get(evidence.table) or []
                if not matching_rows:
                    errors.append(f"{visit.visit_id} {answer.qc_point_id} 证据表不存在或无数据: {evidence.table}。")
                    continue
                if not any(row.get("visit_id") == visit.visit_id for row in matching_rows if "visit_id" in row):
                    errors.append(f"{visit.visit_id} {answer.qc_point_id} 证据表缺少当前 visit 数据: {evidence.table}。")
                if not any(evidence.field in row for row in matching_rows):
                    errors.append(f"{visit.visit_id} {answer.qc_point_id} 证据字段不存在: {evidence.table}.{evidence.field}。")
    _, row_errors = filtered_rows(rows)
    errors.extend(row_errors)
    return errors


def build_report(visits: list[SyntheticVisit], rows: dict[str, list[dict[str, Any]]], errors: list[str], outputs: dict[str, str]) -> str:
    status_counts = Counter(answer.expected_status for visit in visits for answer in visit.golden_answers)
    rule_counts = Counter(answer.qc_point_id for visit in visits for answer in visit.golden_answers)
    table_counts = {table: len(table_rows) for table, table_rows in sorted(rows.items())}
    lines = [
        "# 泸县0609合成质控样本 dry-run 报告",
        "",
        f"- 样本池：{POOL_NAME}",
        f"- 样本数：{len(visits)}",
        f"- 表数量：{len(rows)}",
        f"- 行数量：{sum(table_counts.values())}",
        f"- Golden answer：{sum(status_counts.values())}",
        f"- 校验错误：{len(errors)}",
        "",
        "## 输出文件",
        "",
    ]
    for label, path in outputs.items():
        lines.append(f"- {label}: `{path}`")
    lines.extend(["", "## 状态分布", ""])
    for status in sorted(status_counts):
        lines.append(f"- `{status}`: {status_counts[status]}")
    lines.extend(["", "## 样本清单", "", "| visit_id | 科室 | 说明 | Golden |", "|---|---|---|---|"])
    for visit in visits:
        qids = ", ".join(answer.qc_point_id for answer in visit.golden_answers)
        lines.append(f"| `{visit.visit_id}` | {visit.dept_name} | {visit.description} | {qids} |")
    lines.extend(["", "## 表行数", ""])
    for table, count in table_counts.items():
        lines.append(f"- `{table}`: {count}")
    lines.extend(["", "## 覆盖质控点", ""])
    for qid in sorted(rule_counts):
        lines.append(f"- `{qid}`: {rule_counts[qid]}")
    if errors:
        lines.extend(["", "## 校验错误", ""])
        for error in errors:
            lines.append(f"- {error}")
    return "\n".join(lines) + "\n"


def write_outputs(visits: list[SyntheticVisit], rows: dict[str, list[dict[str, Any]]], errors: list[str]) -> dict[str, Path]:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    sql_path = RUNTIME_DIR / f"luxian_0609_synthetic_pg_preview_{timestamp}.sql"
    md_path = RUNTIME_DIR / f"luxian_0609_synthetic_pg_preview_{timestamp}.md"
    json_path = RUNTIME_DIR / f"luxian_0609_synthetic_pg_preview_{timestamp}.json"
    golden_patch_path = RUNTIME_DIR / f"luxian_0609_golden_patch_{timestamp}.json"

    synthetic_json = build_synthetic_cases_json(visits, rows)
    golden_patch = build_golden_patch(visits)

    SYNTHETIC_CASES_PATH.write_text(
        json.dumps(synthetic_json, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    sql_path.write_text(build_sql_preview(rows), encoding="utf-8")
    json_path.write_text(
        json.dumps(
            {
                "summary": synthetic_json["summary"],
                "validation_errors": errors,
                "synthetic_cases_path": str(SYNTHETIC_CASES_PATH),
                "golden_patch_path": str(golden_patch_path),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    golden_patch_path.write_text(json.dumps(golden_patch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = build_report(
        visits,
        rows,
        errors,
        {
            "synthetic_cases": str(SYNTHETIC_CASES_PATH),
            "sql_preview": str(sql_path),
            "json_report": str(json_path),
            "golden_patch": str(golden_patch_path),
        },
    )
    md_path.write_text(report, encoding="utf-8")
    return {
        "synthetic_cases": SYNTHETIC_CASES_PATH,
        "sql_preview": sql_path,
        "json_report": json_path,
        "md_report": md_path,
        "golden_patch": golden_patch_path,
    }


def reflected_table(table_name: str, metadata: sa.MetaData) -> sa.Table | None:
    if engine is None:
        raise RuntimeError("DATABASE_URL is not configured; cannot write synthetic cases.")
    if table_name == "manual_problem_sample_pools":
        from backend.app.services.custom_qc_sample_pool_service import _sample_pools_table

        return _sample_pools_table()
    if table_name == "manual_problem_sample_pool_items":
        from backend.app.services.custom_qc_sample_pool_service import _sample_pool_items_table

        return _sample_pool_items_table()
    try:
        return sa.Table(table_name, metadata, autoload_with=engine)
    except Exception:
        return None


def write_database(rows: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    if engine is None:
        raise RuntimeError("DATABASE_URL is not configured; cannot write synthetic cases.")
    metadata = sa.MetaData()
    write_summary: dict[str, Any] = {"deleted_tables": [], "inserted": {}, "skipped_tables": []}
    with engine.begin() as conn:
        for table_name in sorted(rows):
            table = reflected_table(table_name, metadata)
            if table is None:
                write_summary["skipped_tables"].append(table_name)
                continue
            if table_name == "manual_problem_sample_pool_items":
                conn.execute(table.delete().where(table.c.matched_visit_id.like(f"{SYNTHETIC_PREFIX}%")))
            elif table_name == "manual_problem_sample_pools":
                conn.execute(table.delete().where(sa.or_(table.c.id == POOL_ID, table.c.name == POOL_NAME)))
            elif "visit_id" in table.c:
                conn.execute(table.delete().where(table.c.visit_id.like(f"{SYNTHETIC_PREFIX}%")))
            write_summary["deleted_tables"].append(table_name)

        for table_name in sorted(rows):
            table = reflected_table(table_name, metadata)
            if table is None:
                continue
            allowed_columns = set(table.c.keys())
            cleaned_rows = [
                {key: value for key, value in row.items() if key in allowed_columns}
                for row in rows[table_name]
            ]
            if not cleaned_rows:
                continue
            insert_columns = sorted({key for row in cleaned_rows for key in row.keys()})
            cleaned_rows = [
                {column: row.get(column) for column in insert_columns}
                for row in cleaned_rows
            ]
            pk_columns = [column.name for column in table.primary_key.columns]
            statement = pg_insert(table).values(cleaned_rows)
            update_columns = [
                column
                for column in cleaned_rows[0].keys()
                if column not in pk_columns
            ]
            if pk_columns and update_columns:
                statement = statement.on_conflict_do_update(
                    index_elements=pk_columns,
                    set_={column: getattr(statement.excluded, column) for column in update_columns},
                )
            elif pk_columns:
                statement = statement.on_conflict_do_nothing(index_elements=pk_columns)
            conn.execute(statement)
            write_summary["inserted"][table_name] = len(cleaned_rows)
    return write_summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Luxian 0609 PG-consistent synthetic QC cases.")
    parser.add_argument("--write", action="store_true", help="write synthetic cases into PostgreSQL; dry-run by default")
    parser.add_argument("--allow-errors", action="store_true", help="write outputs even when validation errors exist")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    visits = build_visits()
    rows, row_errors = filtered_rows(collect_rows(visits))
    errors = validate(visits, rows)
    for error in row_errors:
        if error not in errors:
            errors.append(error)
    outputs = write_outputs(visits, rows, errors)
    print(f"synthetic_cases={outputs['synthetic_cases']}")
    print(f"sql_preview={outputs['sql_preview']}")
    print(f"md_report={outputs['md_report']}")
    print(f"golden_patch={outputs['golden_patch']}")
    print(f"visits={len(visits)} rows={sum(len(items) for items in rows.values())} errors={len(errors)}")
    if errors and not args.allow_errors:
        for error in errors[:30]:
            print(f"ERROR: {error}")
        if len(errors) > 30:
            print(f"... {len(errors) - 30} more errors")
        return 1
    if args.write:
        summary = write_database(rows)
        print(json.dumps(json_ready(summary), ensure_ascii=False, indent=2))
    else:
        print("dry_run=true; database not modified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
