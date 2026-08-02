from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any, Sequence


PROVISIONAL_RULE_IDS = frozenset(
    {
        "LX0609-050",
        "LX0609-054",
        "LX0609-055",
        "LX0609-056",
        "LX0609-057",
        "LX0609-059",
        "LX0609-063",
        "LX0609-075",
    }
)

# 每条规则只绑定一份权威验收病例。其余同族病例仍可用于人工探索，但不再
# 自动生成 pending 黄金答案。
RULE_NUMBERS_BY_CASE: dict[int, tuple[int, ...]] = {
    1: (1, 2, 4, 5, 6),
    2: (1, 2, 4, 5, 6),
    4: (1, 2, 4, 5, 6),
    5: (7, 16, 18),
    6: (8, 17),
    7: (9,),
    10: (10, 11),
    11: (12, 52, 53),
    12: (14, 15),
    13: (20, 21, 22, 23, 69),
    17: (3, 24, 25, 28, 31),
    18: (29, 30, 32, 33),
    19: (34, 35, 36, 37, 38),
    20: (39, 40),
    21: (64, 65, 66),
    22: (75,),
    23: (41, 42, 43, 44, 45, 46, 47, 48, 49, 70),
    28: (13, 19, 26, 27),
    31: (61, 62, 63, 67, 68),
    32: (50,),
    33: (51, 60),
    34: (54, 55, 56, 57, 58, 59),
    36: (71, 72, 73, 74),
}

NON_COMPLIANT_RULE_IDS = frozenset(
    {
        "LX0609-010",
        "LX0609-011",
        "LX0609-012",
        "LX0609-050",
        "LX0609-052",
        "LX0609-053",
    }
)

_NON_COMPLIANT_RULE_IDS_BY_CASE = {
    2: frozenset(
        {"LX0609-001", "LX0609-002", "LX0609-004", "LX0609-005", "LX0609-006"}
    ),
}


def expected_status_for_case(case_index: int, rule_id: str) -> str:
    if rule_id in _NON_COMPLIANT_RULE_IDS_BY_CASE.get(case_index, frozenset()):
        return "non_compliant"
    return "non_compliant" if rule_id in NON_COMPLIANT_RULE_IDS else "compliant"


def _rule_id(number: int) -> str:
    return f"LX0609-{number:03d}"


def _clear_visit_rows(
    rows_by_table: dict[str, list[dict[str, Any]]],
    case: Any,
    *table_names: str,
) -> None:
    for table_name in table_names:
        rows_by_table[table_name] = [
            row
            for row in rows_by_table.get(table_name, [])
            if str(row.get("visit_id") or "") != case.target_visit_id
        ]


def _append_document(
    rows_by_table: dict[str, list[dict[str, Any]]],
    case: Any,
    v2: Any,
    *,
    table_name: str,
    suffix: str,
    title: str,
    record_time: datetime,
    content: str,
    **extra: Any,
) -> str:
    document_id = f"{case.target_visit_id}-{suffix}"
    row = {
        **v2._case_base_row(case),
        "document_id": document_id,
        "document_title": title,
        "document_status": "completed",
        "record_content": content,
        "record_time": record_time,
        "record_datetime": record_time,
        "submit_datetime": record_time,
        "last_modified_datetime": record_time,
        "update_time": record_time,
        "submitter": "陈某医师",
        "submitter_id": "DEID",
        **extra,
    }
    v2._append_row(rows_by_table, table_name, row)
    return document_id


def _append_order(
    rows_by_table: dict[str, list[dict[str, Any]]],
    case: Any,
    v2: Any,
    *,
    table_name: str,
    suffix: str,
    prescribed_time: datetime,
    content: str,
    **extra: Any,
) -> str:
    order_id = f"{case.target_visit_id}-{suffix}"
    v2._append_row(
        rows_by_table,
        table_name,
        {
            **v2._case_base_row(case),
            "order_id": order_id,
            "order_status": "执行中",
            "prescribed_datetime": prescribed_time,
            "prescribed_doctor": "陈某医师",
            "record_content": content,
            "last_modified_datetime": prescribed_time,
            "update_time": prescribed_time,
            **extra,
        },
    )
    return order_id


def _append_registration(
    rows_by_table: dict[str, list[dict[str, Any]]], case: Any, v2: Any,
    *, discharge_time: datetime | None = None,
) -> str:
    admission_time = v2._dt_for_case(case, 0, 8, 0)
    _clear_visit_rows(rows_by_table, case, "inpat_registration")
    ref = f"{case.target_visit_id}-registration"
    v2._append_row(
        rows_by_table,
        "inpat_registration",
        {
            **v2._case_base_row(case),
            "admission_datetime": admission_time,
            "discharge_datetime": discharge_time,
            "admission_dept_name": "普通外科",
            "discharge_dept_name": "普通外科" if discharge_time else "",
            "admission_reason": "按受控质控场景收入院",
            "record_content": f"入院时间：{admission_time:%Y-%m-%d %H:%M:%S}",
        },
    )
    return ref


def _build_timeliness(
    rows: dict[str, list[dict[str, Any]]],
    case: Any,
    v2: Any,
    *,
    mode: str = "before_threshold",
) -> list[str]:
    _clear_visit_rows(
        rows, case, "admission_record", "first_course_record", "rescue_record", "senior_course_record"
    )
    refs = [_append_registration(rows, case, v2)]
    if mode == "after_threshold":
        admission_record_time = v2._dt_for_case(case, 1, 10)
        first_course_time = v2._dt_for_case(case, 0, 18)
        rescue_record_time = v2._dt_for_case(case, 1, 17)
        attending_round_time = v2._dt_for_case(case, 2, 9)
        chief_round_time = v2._dt_for_case(case, 3, 9)
    elif mode == "at_threshold":
        admission_record_time = v2._dt_for_case(case, 1, 8)
        first_course_time = v2._dt_for_case(case, 0, 16)
        rescue_record_time = v2._dt_for_case(case, 1, 16)
        attending_round_time = v2._dt_for_case(case, 2, 8)
        chief_round_time = v2._dt_for_case(case, 3, 8)
    else:
        admission_record_time = v2._dt_for_case(case, 0, 10)
        first_course_time = v2._dt_for_case(case, 0, 12)
        rescue_record_time = v2._dt_for_case(case, 1, 12)
        attending_round_time = v2._dt_for_case(case, 1, 9)
        chief_round_time = v2._dt_for_case(case, 2, 9)
    refs.append(_append_document(
        rows, case, v2, table_name="admission_record", suffix="admission-record",
        title="入院记录", record_time=admission_record_time,
        content="入院记录已完成。主诉发热伴咳嗽3天，初步诊断社区获得性肺炎。",
        admission_datetime=v2._dt_for_case(case, 0, 8), chief_complaint="发热伴咳嗽3天",
    ))
    refs.append(_append_document(
        rows, case, v2, table_name="first_course_record", suffix="first-course",
        title="首次病程记录", record_time=first_course_time,
        content="病例特点、诊断依据、鉴别诊断及诊疗计划记录完整。",
        case_characteristic="发热、咳嗽，肺部湿啰音。", diagnosis_discussion="考虑社区获得性肺炎。",
        treatment_plan="完善检查并抗感染治疗。", physician_sign="陈某医师",
        physician_sign_datetime=v2._dt_for_case(case, 0, 12),
    ))
    rescue_end_time = v2._dt_for_case(case, 1, 10)
    refs.append(_append_document(
        rows, case, v2, table_name="rescue_record", suffix="rescue",
        title="抢救记录", record_time=rescue_record_time,
        content=(
            f"抢救开始时间：{v2._dt_for_case(case, 1, 9):%Y-%m-%d %H:%M:%S}；"
            f"抢救结束时间：{rescue_end_time:%Y-%m-%d %H:%M:%S}；"
            f"记录时间：{rescue_record_time:%Y-%m-%d %H:%M:%S}。"
        ),
    ))
    refs.append(_append_document(
        rows, case, v2, table_name="senior_course_record", suffix="attending-round",
        title="主治医师首次查房记录", record_time=attending_round_time,
        content="主治医师首次查房，核对诊断并调整诊疗计划。主治医师陈某签名。",
    ))
    refs.append(_append_document(
        rows, case, v2, table_name="senior_course_record", suffix="chief-round",
        title="主任医师首次查房记录", record_time=chief_round_time,
        content="主任医师首次查房，复核病情并明确后续治疗方案。主任医师李某签名。",
    ))
    return refs


def _build_course(rows: dict[str, list[dict[str, Any]]], case: Any, v2: Any, *, mode: str) -> list[str]:
    _clear_visit_rows(rows, case, "admission_record", "admission_record_diagnosis", "first_course_record", "daily_course_record", "senior_course_record", "inpat_nondrug_order")
    refs = [_append_registration(rows, case, v2)]
    refs.append(_append_document(
        rows, case, v2, table_name="admission_record", suffix="admission-course",
        title="入院记录", record_time=v2._dt_for_case(case, 0, 10),
        content="主诉咳嗽伴发热3天。现病史、查体和第一诊断记录完整。",
        chief_complaint="咳嗽伴发热3天", history_of_present_illness="3天前出现咳嗽发热，逐渐加重。",
    ))
    diagnosis_id = f"{case.target_visit_id}-admission-diagnosis"
    v2._append_row(rows, "admission_record_diagnosis", {
        **v2._case_base_row(case), "document_id": f"{case.target_visit_id}-admission-course",
        "diagnosis_id": diagnosis_id, "diagnosis_main": "1", "diagnosis_no": 1,
        "diagnosis_name": "重症肺炎", "diagnosis_code": "J18.900",
        "diagnosis_time": v2._dt_for_case(case, 0, 10),
    })
    refs.append(diagnosis_id)
    refs.append(_append_document(
        rows, case, v2, table_name="first_course_record", suffix="first-course-quality",
        title="首次病程记录", record_time=v2._dt_for_case(case, 0, 12),
        content="病例特点为老年患者急性发热咳嗽，肺部湿啰音；诊断考虑重症肺炎，拟抗感染及监测。",
        case_characteristic="老年患者，急性发热咳嗽，肺部湿啰音。",
    ))
    if mode == "stable":
        days = (1, 3, 5, 7)
    elif mode == "severe":
        _append_order(
            rows, case, v2, table_name="inpat_nondrug_order", suffix="severe-order",
            prescribed_time=v2._dt_for_case(case, 0, 11), content="下达病重医嘱",
            order_type="病情", order_name="病重护理", frequency="持续",
        )
        days = (1, 2, 4, 6)
    else:
        _append_order(
            rows, case, v2, table_name="inpat_nondrug_order", suffix="critical-order",
            prescribed_time=v2._dt_for_case(case, 0, 11), content="下达病危医嘱",
            order_type="病情", order_name="病危护理", frequency="持续",
        )
        days = (1, 2, 3, 4, 5, 6, 7)
    for day in days:
        refs.append(_append_document(
            rows, case, v2, table_name="daily_course_record", suffix=f"course-{day}",
            title="日常病程记录", record_time=v2._dt_for_case(case, day, 9),
            content=f"住院第{day}日查房：症状、生命体征、检查结果及治疗计划均已记录，内容与前次记录不同。",
        ))
    return refs


def _build_consultation(rows: dict[str, list[dict[str, Any]]], case: Any, v2: Any) -> list[str]:
    _clear_visit_rows(
        rows, case, "consultation_record", "daily_course_record",
        "inpat_drug_order", "inpat_nondrug_order", "exam_master",
        "labtest_master", "surgery_record",
    )
    refs = [_append_registration(rows, case, v2)]
    consultation_id = f"{case.target_visit_id}-consultation"
    request_time = v2._dt_for_case(case, 1, 8)
    refs.append(_append_document(
        rows, case, v2, table_name="consultation_record", suffix="consult-request",
        title="会诊申请单", record_time=request_time,
        content="会诊目的：患者胆管炎伴梗阻，申请消化内科评估ERCP适应证并提出明确抗感染和引流方案。",
        consultation_id=consultation_id, application_id=consultation_id,
        request_time=request_time, request_datetime=request_time,
    ))
    refs.append(_append_document(
        rows, case, v2, table_name="consultation_record", suffix="consult-opinion",
        title="会诊记录单", record_time=v2._dt_for_case(case, 1, 14),
        content="会诊意见：诊断胆总管结石伴胆管炎，建议今日完善凝血后行ERCP取石引流，继续头孢曲松治疗。",
        consultation_id=consultation_id, application_id=consultation_id,
        request_time=request_time, request_datetime=request_time,
    ))
    refs.append(_append_document(
        rows, case, v2, table_name="daily_course_record", suffix="consult-execution",
        title="请会诊执行记录", record_time=v2._dt_for_case(case, 1, 17),
        content="已归纳消化内科会诊意见，完善凝血检查并预约ERCP，按建议继续头孢曲松，已向患者说明。",
    ))
    refs.append(_append_order(
        rows, case, v2, table_name="inpat_nondrug_order", suffix="consult-execution-order",
        prescribed_time=v2._dt_for_case(case, 1, 16),
        content="执行会诊意见：完善凝血检查并预约ERCP取石引流。",
        order_type="治疗", order_name="ERCP取石引流术前准备",
    ))
    return refs


def _build_surgery(rows: dict[str, list[dict[str, Any]]], case: Any, v2: Any, *, mode: str) -> list[str]:
    tables = (
        "surgery_application", "inpat_nondrug_order", "surgery_record", "presurg_summary",
        "inpat_drug_order",
        "surgery_safecheck_record", "surgery_inform_consent", "anesthesia_record",
        "consent_form",
        "preane_surveil_record", "postane_surveil_record", "presurg_discussion",
        "postsurg_firstcourse_record", "daily_course_record", "senior_course_record",
    )
    _clear_visit_rows(rows, case, *tables)
    refs = [_append_registration(rows, case, v2)]
    surgery_time = v2._dt_for_case(case, 2, 10)
    if mode != "procedure":
        application_id = f"{case.target_visit_id}-surgery-app"
        refs.append(_append_order(
            rows, case, v2, table_name="inpat_nondrug_order", suffix="surgery-order",
            prescribed_time=v2._dt_for_case(case, 1, 8), content="拟行四级胃癌根治术",
            order_type="手术", order_name="胃癌根治术", application_id=application_id,
        ))
        v2._append_row(rows, "surgery_application", {
            **v2._case_base_row(case), "application_id": application_id,
            "order_id": f"{case.target_visit_id}-surgery-order", "surgery_name": "胃癌根治术",
            "surgery_code": "43.9900", "surgery_level": "四级", "anesthesia_method": "全身麻醉",
            "surgeon": "陈某医师", "request_physician": "陈某医师",
            "request_surgery_datetime": surgery_time, "record_content": "申请四级胃癌根治术，非急诊抢救手术。",
        })
        refs.append(_append_document(
            rows, case, v2, table_name="surgery_record", suffix="surgery-record",
            title="手术记录", record_time=v2._dt_for_case(case, 2, 15),
            content="实施四级胃癌根治术，II类切口，完成D2淋巴结清扫；植入可吸收止血材料1片，规格5cm×8cm。术者陈某，签名医生陈某。",
            surgery_name="胃癌根治术", surgeon="陈某医师",
            surgery_begin_time=f"{surgery_time:%Y-%m-%d %H:%M:%S}+08",
            surgery_end_time=f"{v2._dt_for_case(case, 2, 14):%Y-%m-%d %H:%M:%S}+08",
            anesthesia_method="全身麻醉",
            surgery_process="完成D2淋巴结清扫，植入可吸收止血材料1片，规格5cm×8cm。",
        ))
    if mode == "record":
        refs.append(_append_order(
            rows, case, v2, table_name="inpat_drug_order", suffix="cefazolin-prophylaxis",
            prescribed_time=v2._dt_for_case(case, 2, 9),
            content="II类切口术前预防使用头孢唑林，持续24小时后停用。",
            generic_name="头孢唑林", drug_type="抗菌药物", drug_apply_method="静脉滴注",
            drug_frequency="q8h", medication_duration="24小时",
        ))
        refs.append(_append_document(
            rows, case, v2, table_name="daily_course_record", suffix="prophylaxis-course",
            title="抗菌药物使用记录", record_time=v2._dt_for_case(case, 3, 9),
            content="本次为II类切口，术前预防使用头孢唑林，术后24小时按计划停用，无延长使用指征。",
        ))
    if mode == "presence":
        refs.extend([
            _append_document(rows, case, v2, table_name="presurg_summary", suffix="presurg-summary", title="术前小结", record_time=v2._dt_for_case(case, 1, 12), content="术前诊断胃癌，手术指征明确，拟行胃癌根治术。"),
            _append_document(rows, case, v2, table_name="surgery_safecheck_record", suffix="safecheck", title="手术安全核查表", record_time=v2._dt_for_case(case, 2, 9), content="麻醉实施前、手术开始前、患者离室前三方核查完整。"),
            _append_document(rows, case, v2, table_name="surgery_inform_consent", suffix="surgery-consent", title="手术知情同意书", record_time=v2._dt_for_case(case, 1, 14), content="患者及术者已签名，签署时间精确到分钟。", patient_sign="已签名", surgeon_sign="陈某医师"),
        ])
    elif mode == "anesthesia":
        refs.extend([
            _append_document(rows, case, v2, table_name="anesthesia_record", suffix="anesthesia", title="麻醉记录单", record_time=v2._dt_for_case(case, 2, 9), content="静吸复合全麻，麻醉开始09:30，结束14:30，生命体征平稳。"),
            _append_document(rows, case, v2, table_name="consent_form", suffix="anesthesia-consent", title="麻醉知情同意书", record_time=v2._dt_for_case(case, 1, 15), content="患者和麻醉医生均已签名，签署时间精确到分钟。", consent_type="anesthesia", patient_sign="患者已签名", physician_sign="麻醉医师已签名", patient_sign_datetime=v2._dt_for_case(case, 1, 15), physician_sign_datetime=v2._dt_for_case(case, 1, 15)),
            _append_document(rows, case, v2, table_name="preane_surveil_record", suffix="preane", title="麻醉术前访视记录", record_time=v2._dt_for_case(case, 1, 16), content="术前评估、ASA分级、气道及麻醉计划记录完整。", anesthetist_sign="麻醉医师陈某"),
            _append_document(rows, case, v2, table_name="postane_surveil_record", suffix="postane", title="麻醉术后访视记录", record_time=v2._dt_for_case(case, 3, 9), content="术后清醒，呼吸循环稳定，无麻醉并发症。", anesthetist_sign="麻醉医师陈某"),
        ])
    elif mode == "discussion":
        refs.append(_append_document(
            rows, case, v2, table_name="presurg_discussion", suffix="presurg-discussion",
            title="四级手术术前多学科讨论记录", record_time=v2._dt_for_case(case, 1, 15),
            content="外科、麻醉科、影像科参加四级手术讨论，术者陈某参加并发言，排除急诊抢救手术。",
            discuss_staff="术者陈某、麻醉医师李某、影像医师王某", host_name="陈某医师",
        ))
    elif mode == "postop":
        refs.append(_append_document(rows, case, v2, table_name="postsurg_firstcourse_record", suffix="postop-first", title="术后首次病程记录", record_time=v2._dt_for_case(case, 2, 16), content="术后患者返回病房，记录手术经过、输血、引流及后续计划。"))
        for day in (3, 4, 5):
            refs.append(_append_document(rows, case, v2, table_name="daily_course_record", suffix=f"postop-course-{day}", title="术后查房记录", record_time=v2._dt_for_case(case, day, 9), content=f"术后第{day-2}日连续查房，切口、引流、饮食及治疗计划记录完整。术者陈某医师查房。", physician_sign="陈某医师"))
        refs.append(_append_document(rows, case, v2, table_name="senior_course_record", suffix="postop-senior", title="术后三天内上级医师查房记录", record_time=v2._dt_for_case(case, 4, 10), content="上级医师术后三天内查看患者并明确后续方案。"))
    elif mode == "procedure":
        refs.append(_append_order(rows, case, v2, table_name="inpat_nondrug_order", suffix="central-line-order", prescribed_time=v2._dt_for_case(case, 1, 8), content="中心静脉置管术医嘱", order_type="有创操作", order_name="中心静脉置管术"))
        refs.append(_append_document(rows, case, v2, table_name="daily_course_record", suffix="central-line-record", title="中心静脉置管操作记录", record_time=v2._dt_for_case(case, 1, 10), content="在无菌操作下完成右颈内静脉置管，过程顺利，无并发症，操作者签名。"))
    return refs


def _build_transfusion(rows: dict[str, list[dict[str, Any]]], case: Any, v2: Any) -> list[str]:
    _clear_visit_rows(rows, case, "blood_application", "bloodtrans_record", "inpat_drug_order", "inpat_nondrug_order", "inpat_bill_item", "labtest_master", "labtest_item_report", "daily_course_record", "surgery_record", "anesthesia_record", "postsurg_firstcourse_record", "consent_form")
    refs = [_append_registration(rows, case, v2)]
    request_time = v2._dt_for_case(case, 1, 10)
    transfusion_time = v2._dt_for_case(case, 1, 14)
    application_id = f"{case.target_visit_id}-blood-app"
    v2._append_row(rows, "blood_application", {**v2._case_base_row(case), "application_id": application_id, "request_datetime": request_time, "transfuse_variety": "悬浮红细胞", "transfuse_volume": 2, "transfuse_volume_unit": "U", "physician_name": "陈某医师", "record_content": "因血红蛋白65g/L申请输注悬浮红细胞2U。"})
    refs.append(application_id)
    consent_time = v2._dt_for_case(case, 1, 9)
    refs.append(_append_document(
        rows, case, v2, table_name="consent_form", suffix="blood-consent",
        title="输血知情同意书", record_time=consent_time,
        content="诊断：重度贫血；输血指征为重度贫血，拟输注悬浮红细胞2U；已说明输血目的、风险、可能不良反应和替代方案，患者同意输血。",
        consent_type="blood_transfusion", patient_sign="患者已签名",
        physician_sign="陈某医师", patient_sign_datetime=consent_time,
        physician_sign_datetime=consent_time,
    ))
    test_id = f"{case.target_visit_id}-pretransfusion-nine"
    v2._append_row(rows, "labtest_master", {**v2._case_base_row(case), "test_id": test_id, "labtest_subject": "输血前九项", "specimen": "静脉血", "request_datetime": v2._dt_for_case(case, 0, 10), "report_datetime": v2._dt_for_case(case, 1, 8), "record_content": "输血前九项检查"})
    nine = (("HBsAg","乙肝表面抗原","阴性"),("HBsAb","乙肝表面抗体","阳性"),("HBeAg","乙肝e抗原","阴性"),("HBeAb","乙肝e抗体","阴性"),("HBcAb","乙肝核心抗体","阴性"),("HIV","艾滋抗体","阴性"),("HCV","丙肝抗体","阴性"),("TP","梅毒抗体","阴性"),("ALT","谷丙转氨酶","18"))
    for index, (code, name, result) in enumerate(nine, start=1):
        item_id = f"{test_id}-{index:02d}"
        v2._append_row(rows, "labtest_item_report", {**v2._case_base_row(case), "document_id": item_id, "document_title": "输血前九项检验报告", "document_status": "Submitted", "test_no": test_id, "test_id": test_id, "item_no": str(index), "item_id": item_id, "item_code": code, "item_name": name, "item_abbreviation": code, "result": result, "report_time": v2._dt_for_case(case, 1, 8), "record_time": v2._dt_for_case(case, 1, 8), "record_content": f"{name}：{result}"})
        refs.append(item_id)
    order_id = _append_order(rows, case, v2, table_name="inpat_nondrug_order", suffix="blood-order", prescribed_time=request_time, content="输注悬浮红细胞2U", order_type="输血", order_name="悬浮红细胞2U", quantity=2, quantity_unit="U")
    refs.append(order_id)
    v2._append_row(rows, "inpat_bill_item", {**v2._case_base_row(case), "bill_item_id": f"{case.target_visit_id}-blood-bill", "order_id": order_id, "medical_catalog_name": "悬浮红细胞", "quantity": 2, "quantity_unit": "U", "billing_datetime": transfusion_time, "record_content": "悬浮红细胞2U收费"})
    refs.append(_append_document(rows, case, v2, table_name="bloodtrans_record", suffix="blood-course", title="输血病程记录", record_time=transfusion_time, content="输血前评估：Hb 65g/L，有输血指征；核对血型后输注悬浮红细胞2U，过程无不良反应。输血后评价：症状改善，复查Hb 82g/L。"))
    refs.append(_append_document(rows, case, v2, table_name="daily_course_record", suffix="blood-daily-course", title="输血病程记录", record_time=transfusion_time, content="输血前评估Hb 65g/L且有症状，输注悬浮红细胞2U；输血过程无不良反应，输血后症状改善，复查Hb 82g/L。"))
    for table, suffix, title in (("surgery_record","surgery-blood","手术记录"),("anesthesia_record","anesthesia-blood","麻醉记录单"),("postsurg_firstcourse_record","postop-blood","术后首次病程记录")):
        refs.append(_append_document(rows, case, v2, table_name=table, suffix=suffix, title=title, record_time=v2._dt_for_case(case, 1, 16), content="术中输注悬浮红细胞2U，无输血不良反应。"))
    return refs


def _build_tumor(rows: dict[str, list[dict[str, Any]]], case: Any, v2: Any) -> list[str]:
    _clear_visit_rows(rows, case, "pathology_exam_master", "pathology_exam_report", "surgery_record", "daily_course_record", "inpat_drug_order", "discharge_record", "diagnosis", "discharge_record_diagnosis")
    refs = [_append_registration(rows, case, v2, discharge_time=v2._dt_for_case(case, 8, 10))]
    pathology_id = f"{case.target_visit_id}-pathology"
    v2._append_row(rows, "pathology_exam_master", {**v2._case_base_row(case), "pathology_exam_id": pathology_id, "pathology_id": pathology_id, "specimen_name": "胃大部切除标本及淋巴结", "request_datetime": v2._dt_for_case(case, 2, 14), "record_content": "胃癌手术标本送病理"})
    v2._append_row(rows, "pathology_exam_report", {**v2._case_base_row(case), "pathology_exam_id": pathology_id, "pathology_id": pathology_id, "specimen_name": "胃大部切除标本及淋巴结", "diagnosis": "胃腺癌，淋巴结2/18枚转移", "report_datetime": v2._dt_for_case(case, 5, 10), "record_content": "病理结果：胃腺癌，淋巴结2/18枚转移。"})
    refs.append(pathology_id)
    refs.append(_append_document(rows, case, v2, table_name="surgery_record", suffix="tumor-surgery", title="手术记录", record_time=v2._dt_for_case(case, 2, 16), content="行胃癌根治术，取胃大部切除标本及18枚淋巴结送病理检查。"))
    refs.append(_append_document(rows, case, v2, table_name="daily_course_record", suffix="pathology-course", title="病程记录", record_time=v2._dt_for_case(case, 5, 14), content="病理报告胃腺癌、淋巴结2/18枚转移，结合分期拟行奥沙利铂联合卡培他滨化疗。"))
    refs.append(_append_order(rows, case, v2, table_name="inpat_drug_order", suffix="oxaliplatin", prescribed_time=v2._dt_for_case(case, 6, 9), content="奥沙利铂130mg/m²静滴，第1天", generic_name="奥沙利铂", single_dose=130, single_dose_unit="mg/m²", drug_apply_method="静脉滴注"))
    refs.append(_append_document(rows, case, v2, table_name="daily_course_record", suffix="chemo-course", title="化疗病程记录", record_time=v2._dt_for_case(case, 6, 10), content="今日给予奥沙利铂130mg/m²静脉滴注，第1天，与医嘱一致，观察不良反应。"))
    refs.append(_append_document(rows, case, v2, table_name="discharge_record", suffix="tumor-discharge", title="出院记录", record_time=v2._dt_for_case(case, 8, 9), content="出院诊断胃腺癌。出院后肿瘤治疗计划：三周后返院继续奥沙利铂联合卡培他滨方案并复查血常规、肝肾功能。", discharge_date=v2._dt_for_case(case, 8, 10), discharge_time=v2._dt_for_case(case, 8, 10)))
    diagnosis_id = f"{case.target_visit_id}-tumor-diagnosis"
    v2._append_row(rows, "diagnosis", {**v2._case_base_row(case), "document_id": f"{case.target_visit_id}-frontpage", "diagnosis_id": diagnosis_id, "diagnosis_type": "出院诊断", "diagnosis_no": 1, "diagnosis_name": "胃腺癌", "diagnosis_code": "C16.900", "diagnosis_datetime": v2._dt_for_case(case, 8, 9), "diagnosis_source": "病案首页"})
    v2._append_row(rows, "discharge_record_diagnosis", {**v2._case_base_row(case), "document_id": f"{case.target_visit_id}-tumor-discharge", "diagnosis_id": f"{diagnosis_id}-record", "diagnosis_main": "1", "diagnosis_no": 1, "diagnosis_name": "胃腺癌", "diagnosis_code": "C16.900", "diagnosis_time": v2._dt_for_case(case, 8, 9)})
    refs.extend((diagnosis_id, f"{diagnosis_id}-record"))
    return refs


def _build_discharge(rows: dict[str, list[dict[str, Any]]], case: Any, v2: Any, *, mode: str) -> list[str]:
    _clear_visit_rows(rows, case, "diagnosis", "discharge_record", "discharge_record_diagnosis", "daily_course_record", "senior_course_record", "death_record", "death_discussion", "diffcase_discussion_record")
    discharge_time = v2._dt_for_case(case, 8, 10)
    refs = [_append_registration(rows, case, v2, discharge_time=discharge_time)]
    if mode == "uncertain":
        refs.append(_append_document(rows, case, v2, table_name="daily_course_record", suffix="uncertain-diagnosis", title="第7日病程记录", record_time=v2._dt_for_case(case, 7, 9), content="入院第7天，发热原因待查，感染性质待定，目前诊断仍不明确。"))
        return refs
    if mode == "death":
        refs.append(_append_document(rows, case, v2, table_name="death_record", suffix="death-record", title="死亡记录", record_time=v2._dt_for_case(case, 8, 11), content="患者于2026-06-09 10:00因感染性休克死亡，死亡诊断记录完整。"))
        refs.append(_append_document(rows, case, v2, table_name="death_discussion", suffix="death-discussion", title="死亡病例讨论记录", record_time=v2._dt_for_case(case, 10, 9), content="患者死亡后2日完成死亡病例讨论，分析死亡原因和诊疗经验。"))
        return refs
    refs.append(_append_document(rows, case, v2, table_name="daily_course_record", suffix="predischarge-course", title="出院前病程记录", record_time=v2._dt_for_case(case, 7, 9), content="患者病情稳定，今日复查无明显异常，拟明日出院。"))
    refs.append(_append_document(rows, case, v2, table_name="senior_course_record", suffix="discharge-approval", title="上级医师查房记录", record_time=v2._dt_for_case(case, 7, 10), content="上级医师查看患者，同意明日出院。"))
    refs.append(_append_document(rows, case, v2, table_name="discharge_record", suffix="discharge-record", title="出院记录", record_time=v2._dt_for_case(case, 8, 9), content="出院诊断：社区获得性肺炎。出院带药：药品名称阿莫西林胶囊；用药剂量0.5g；给药途径口服；用药时间每日3次，共5天。", discharge_date=discharge_time, discharge_time=discharge_time, discharge_order="药品名称：阿莫西林胶囊；用药剂量：0.5g；给药途径：口服；用药时间：每日3次，共5天"))
    diagnosis_id = f"{case.target_visit_id}-discharge-diagnosis"
    v2._append_row(rows, "discharge_record_diagnosis", {**v2._case_base_row(case), "document_id": f"{case.target_visit_id}-discharge-record", "diagnosis_id": diagnosis_id, "diagnosis_main": "1", "diagnosis_no": 1, "diagnosis_name": "社区获得性肺炎", "diagnosis_code": "J18.900", "diagnosis_time": v2._dt_for_case(case, 8, 9)})
    refs.append(diagnosis_id)
    v2._append_row(rows, "diagnosis", {**v2._case_base_row(case), "document_id": f"{case.target_visit_id}-frontpage", "diagnosis_id": f"{diagnosis_id}-frontpage", "diagnosis_type": "出院诊断", "diagnosis_no": 1, "diagnosis_name": "社区获得性肺炎", "diagnosis_code": "J18.900", "diagnosis_datetime": v2._dt_for_case(case, 8, 9), "diagnosis_source": "病案首页"})
    refs.append(f"{diagnosis_id}-frontpage")
    return refs


def _build_antimicrobial(rows: dict[str, list[dict[str, Any]]], case: Any, v2: Any) -> list[str]:
    _clear_visit_rows(rows, case, "inpat_drug_order", "daily_course_record", "consultation_record", "labtest_master", "labtest_item_report")
    refs = [_append_registration(rows, case, v2)]
    culture_id = f"{case.target_visit_id}-culture"
    v2._append_row(rows, "labtest_master", {**v2._case_base_row(case), "test_id": culture_id, "labtest_subject": "血培养及药敏", "specimen": "静脉血", "request_datetime": v2._dt_for_case(case, 0, 9), "report_datetime": v2._dt_for_case(case, 2, 9), "record_content": "用药前采集血培养"})
    v2._append_row(rows, "labtest_item_report", {**v2._case_base_row(case), "document_id": f"{culture_id}-01", "document_title": "血培养及药敏检验报告", "document_status": "Submitted", "test_no": culture_id, "test_id": culture_id, "item_no": "1", "item_id": f"{culture_id}-01", "item_code": "CULTURE", "item_name": "培养结果", "item_abbreviation": "CULTURE", "result": "培养阳性：检出肺炎克雷伯菌", "report_time": v2._dt_for_case(case, 2, 9), "record_time": v2._dt_for_case(case, 2, 9), "record_content": "培养阳性：检出肺炎克雷伯菌；美罗培南敏感。"})
    refs.append(culture_id)
    for suffix, name, hour in (("meropenem","美罗培南",10),("vancomycin","万古霉素",11)):
        refs.append(_append_order(rows, case, v2, table_name="inpat_drug_order", suffix=suffix, prescribed_time=v2._dt_for_case(case, 0, hour), content=f"经验性启用{name}抗感染，重症感染需覆盖耐药菌，培养前已留取标本。", generic_name=name, drug_apply_method="静脉滴注", drug_frequency="q8h" if name == "美罗培南" else "q12h"))
    refs.append(_append_document(rows, case, v2, table_name="daily_course_record", suffix="antimicrobial-reason", title="抗菌药物使用记录", record_time=v2._dt_for_case(case, 0, 12), content="患者重症感染，已在用药前留取血培养。经验性联合美罗培南和万古霉素覆盖耐药菌，记录启用及联合用药理由。"))
    refs.append(_append_document(rows, case, v2, table_name="consultation_record", suffix="expert-consult", title="感染专家会诊记录", record_time=v2._dt_for_case(case, 0, 15), content="感染专家会诊同意特殊级抗菌药物方案，并建议根据培养结果及时降阶梯。"))
    refs.append(_append_document(rows, case, v2, table_name="daily_course_record", suffix="antimicrobial-evaluation", title="抗菌药物72小时效果评价", record_time=v2._dt_for_case(case, 3, 9), content="用药72小时后体温下降、白细胞和CRP降低，培养提示肺炎克雷伯菌且美罗培南敏感，停用万古霉素并继续美罗培南。"))
    return refs


def _build_transfer(rows: dict[str, list[dict[str, Any]]], case: Any, v2: Any) -> list[str]:
    _clear_visit_rows(rows, case, "inpat_nondrug_order", "handoff_record", "handover_record", "transfer_out_record", "transfer_in_record", "daily_course_record", "diagnosis")
    refs = [_append_registration(rows, case, v2)]
    refs.append(_append_document(rows, case, v2, table_name="handoff_record", suffix="handoff", title="交班记录", record_time=v2._dt_for_case(case, 2, 8), content="交班前完成交班记录，说明当前诊断、治疗和注意事项。"))
    refs.append(_append_document(rows, case, v2, table_name="handover_record", suffix="handover", title="接班记录", record_time=v2._dt_for_case(case, 2, 14), content="接班后6小时完成接班记录，复核诊断及后续计划。"))
    refs.append(_append_order(rows, case, v2, table_name="inpat_nondrug_order", suffix="transfer-order", prescribed_time=v2._dt_for_case(case, 3, 8), content="转入呼吸内科", order_type="转科", order_name="转科医嘱"))
    refs.append(_append_document(rows, case, v2, table_name="transfer_out_record", suffix="transfer-out", title="转出记录", record_time=v2._dt_for_case(case, 3, 9), content="转出前完成记录，说明病情、诊疗经过和转科目的。", transferout_department="普通外科", transferin_department="呼吸内科", transfer_date=v2._dt_for_case(case, 3, 10)))
    refs.append(_append_document(rows, case, v2, table_name="transfer_in_record", suffix="transfer-in", title="转入记录", record_time=v2._dt_for_case(case, 3, 16), content="转入后6小时完成记录，复核患者情况并制定治疗计划。", transferout_department="普通外科", transferin_department="呼吸内科", transfer_date=v2._dt_for_case(case, 3, 10)))
    refs.append(_append_document(rows, case, v2, table_name="daily_course_record", suffix="diagnosis-revision", title="病程记录", record_time=v2._dt_for_case(case, 4, 9), content="根据培养结果补充诊断细菌性肺炎，记录修改理由及诊断依据。"))
    for index, (name, when) in enumerate((("肺部感染", v2._dt_for_case(case, 0, 10)), ("细菌性肺炎", v2._dt_for_case(case, 4, 8))), start=1):
        diagnosis_id = f"{case.target_visit_id}-diagnosis-{index}"
        v2._append_row(rows, "diagnosis", {**v2._case_base_row(case), "document_id": f"{case.target_visit_id}-course-diagnosis-revision", "diagnosis_id": diagnosis_id, "diagnosis_type": "住院诊断", "diagnosis_no": index, "diagnosis_name": name, "diagnosis_code": "J18.900", "diagnosis_datetime": when, "diagnosis_source": "病程记录"})
        refs.append(diagnosis_id)
    return refs


def apply_controlled_evidence(
    rows_by_table: dict[str, list[dict[str, Any]]],
    cases: Sequence[Any],
    *,
    v2: Any,
    rule_titles: dict[str, str],
) -> dict[str, Any]:
    case_by_index = {int(case.target_index): case for case in cases}
    refs_by_case: dict[int, list[str]] = {}
    builders = {
        1: lambda case: _build_timeliness(rows_by_table, case, v2),
        2: lambda case: _build_timeliness(
            rows_by_table, case, v2, mode="after_threshold"
        ),
        4: lambda case: _build_timeliness(
            rows_by_table, case, v2, mode="at_threshold"
        ),
        5: lambda case: _build_course(rows_by_table, case, v2, mode="stable"),
        6: lambda case: _build_course(rows_by_table, case, v2, mode="severe"),
        7: lambda case: _build_course(rows_by_table, case, v2, mode="critical"),
        13: lambda case: _build_consultation(rows_by_table, case, v2),
        17: lambda case: _build_surgery(rows_by_table, case, v2, mode="record"),
        18: lambda case: _build_surgery(rows_by_table, case, v2, mode="presence"),
        19: lambda case: _build_surgery(rows_by_table, case, v2, mode="anesthesia"),
        20: lambda case: _build_surgery(rows_by_table, case, v2, mode="discussion"),
        21: lambda case: _build_surgery(rows_by_table, case, v2, mode="postop"),
        22: lambda case: _build_surgery(rows_by_table, case, v2, mode="procedure"),
        23: lambda case: _build_transfusion(rows_by_table, case, v2),
        28: lambda case: _build_tumor(rows_by_table, case, v2),
        31: lambda case: _build_discharge(rows_by_table, case, v2, mode="alive"),
        32: lambda case: _build_discharge(rows_by_table, case, v2, mode="uncertain"),
        33: lambda case: _build_discharge(rows_by_table, case, v2, mode="death"),
        34: lambda case: _build_antimicrobial(rows_by_table, case, v2),
        36: lambda case: _build_transfer(rows_by_table, case, v2),
    }
    for case_index, builder in builders.items():
        refs_by_case[case_index] = builder(case_by_index[case_index])

    # 检查检验四份病例由主构建器先完成；这里绑定其稳定文书/报告 ID。
    refs_by_case.update(
        {
            9: [f"EX-V3-009-01", f"LAB-V3-009-04"],
            10: [f"EX-V3-010-01", f"LAB-V3-010-04"],
            11: [f"EX-V3-011-01", f"LAB-V3-011-01", f"LAB-V3-011-04"],
            12: [f"EX-V3-012-01", f"LAB-V3-012-04", f"{case_by_index[12].target_visit_id}-critical-value"],
        }
    )

    existing_answers_by_case = {
        int(case.target_index): list(
            case.source_item.get("synthetic_golden_answers") or []
        )
        for case in cases
    }
    for case in cases:
        case.source_item["synthetic_golden_answers"] = []
    covered: set[str] = set()
    tier_counts: Counter[str] = Counter()
    for case_index, numbers in RULE_NUMBERS_BY_CASE.items():
        case = case_by_index[case_index]
        evidence_refs = list(dict.fromkeys(refs_by_case[case_index]))
        answers = list(existing_answers_by_case.get(case_index) or [])
        for number in numbers:
            rule_id = _rule_id(number)
            tier = "provisional" if rule_id in PROVISIONAL_RULE_IDS else "formal"
            status = expected_status_for_case(case_index, rule_id)
            answers.append(
                {
                    "qc_point_id": rule_id,
                    "expected_status": status,
                    "expected_hit": status == "non_compliant",
                    "review_status": "controlled",
                    "acceptance_tier": tier,
                    "definition_version": "lx0609-v3-formal-2026-08-02" if tier == "formal" else "lx0609-v3-provisional-2026-08-02",
                    "human_reason": rule_titles[rule_id],
                    "trigger_facts": [f"controlled_case_{case_index:03d}"],
                    "evidence_refs": evidence_refs,
                }
            )
        normalized_answers = []
        seen_answer_keys: set[tuple[str, str]] = set()
        for answer in answers:
            rule_id = str(answer.get("qc_point_id") or "")
            status = str(answer.get("expected_status") or "")
            key = (rule_id, status)
            if not rule_id or not status or key in seen_answer_keys:
                continue
            seen_answer_keys.add(key)
            tier = "provisional" if rule_id in PROVISIONAL_RULE_IDS else "formal"
            normalized_answers.append(
                {
                    **answer,
                    "review_status": "controlled",
                    "acceptance_tier": tier,
                    "definition_version": (
                        "lx0609-v3-formal-2026-08-02"
                        if tier == "formal"
                        else "lx0609-v3-provisional-2026-08-02"
                    ),
                    "evidence_refs": list(
                        dict.fromkeys(answer.get("evidence_refs") or evidence_refs)
                    ),
                }
            )
            if rule_id not in covered:
                covered.add(rule_id)
                tier_counts[tier] += 1
        case.source_item["synthetic_golden_answers"] = normalized_answers
    for case_index, existing_answers in existing_answers_by_case.items():
        if case_index in RULE_NUMBERS_BY_CASE or not existing_answers:
            continue
        case = case_by_index[case_index]
        evidence_refs = list(dict.fromkeys(refs_by_case.get(case_index) or []))
        normalized_answers = []
        for answer in existing_answers:
            rule_id = str(answer.get("qc_point_id") or "")
            tier = "provisional" if rule_id in PROVISIONAL_RULE_IDS else "formal"
            normalized_answers.append(
                {
                    **answer,
                    "review_status": "controlled",
                    "acceptance_tier": tier,
                    "definition_version": (
                        "lx0609-v3-formal-2026-08-02"
                        if tier == "formal"
                        else "lx0609-v3-provisional-2026-08-02"
                    ),
                    "evidence_refs": list(
                        dict.fromkeys(answer.get("evidence_refs") or evidence_refs)
                    ),
                }
            )
            if rule_id not in covered:
                covered.add(rule_id)
                tier_counts[tier] += 1
        case.source_item["synthetic_golden_answers"] = normalized_answers
    if len(covered) != 75:
        raise ValueError("v3 controlled evidence must cover all 75 rules exactly once")
    return {
        "rule_count": len(covered),
        "case_count": len(refs_by_case),
        "tier_counts": dict(tier_counts),
        "controlled_row_count": sum(len(rows) for rows in rows_by_table.values()),
    }
