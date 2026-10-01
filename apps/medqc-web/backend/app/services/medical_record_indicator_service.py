"""病案管理 27 项指标报表。

这里只聚合已有 owner 的结果，不重新判定病历事实。当前可展示的两项均明确标为
“出院队列已核实子集”，国家指标官方率在完整分母和来源合同补齐前保持空值。
"""

from __future__ import annotations

import csv
import io
from collections import Counter
from dataclasses import dataclass
from datetime import date
from typing import Any, Mapping

from . import record_quality_report_service as base_report

MAX_PAGE_SIZE = 100
DIMENSIONS = {"department", "doctor"}
STATES = {"compliant", "non_compliant", "not_applicable", "unknown"}


class MedicalRecordIndicatorInvalid(ValueError):
    """查询参数不符合合同。"""


class MedicalRecordIndicatorUnavailable(RuntimeError):
    """权威来源不可读取。"""


@dataclass(frozen=True)
class IndicatorDefinition:
    code: str
    name: str
    formula: str
    numerator: str
    denominator: str
    data_source: str
    availability: str
    blocker: str | None = None
    rule_id: str | None = None


DEFINITIONS = (
    IndicatorDefinition("MER-HR-01", "住院病案管理人员月均负担出院患者病历数", "出院患者病历总数 / 同期住院病案管理人员实际工作总月数", "出院患者病历总数", "同期住院病案管理人员实际工作总月数", "无", "blocked", "缺住院病案管理人员实际工作月数"),
    IndicatorDefinition("MER-HR-02", "门诊病案管理人员月均负担门诊患者病历数", "门诊患者病历总数 / 同期门诊病案管理人员实际工作总月数", "门诊患者病历总数（按同期门诊实际诊疗人次计算）", "同期门诊病案管理人员实际工作总月数", "无", "blocked", "缺门诊诊疗人次及人员实际工作月数"),
    IndicatorDefinition("MER-HR-03", "病案编码人员月均负担出院患者病历数", "出院患者病历总数 / 同期病案编码人员实际工作总月数", "出院患者病历总数", "同期病案编码人员实际工作总月数", "无", "blocked", "缺编码人员实际工作月数"),
    IndicatorDefinition("MER-TL-01", "入院记录24小时内完成率", "入院记录在患者入院24小时内完成的住院患者病历数 / 同期住院患者病历总数 × 100%", "入院记录在患者入院24小时内完成的住院患者病历数", "同期住院患者病历总数", "Canonical LX0609-001 客户安全投影；当前产品队列按出院日期筛选", "partial", "当前仅能给出出院队列已核实子集率；未知病例不能按通过处理", "LX0609-001"),
    IndicatorDefinition("MER-TL-02", "手术记录24小时内完成率", "手术记录在术后24小时内完成的住院患者病历数 / 同期住院手术患者病历总数 × 100%", "手术记录在术后24小时内完成的住院患者病历数", "同期住院手术患者病历总数", "Canonical LX0609-003 客户安全投影；当前产品队列按出院日期筛选", "partial", "当前仅能给出出院队列已核实子集率", "LX0609-003"),
    IndicatorDefinition("MER-TL-03", "出院记录24小时内完成率", "出院记录在患者出院后24小时内完成的病历数 / 同期出院患者病历总数 × 100%", "出院记录在患者出院后24小时内完成的病历数", "同期出院患者病历总数", "discharge_record 仅有记录/提交时间字段", "blocked", "仓库未证明 record_datetime/submit_datetime 等同业务完成或签署时间"),
    IndicatorDefinition("MER-TL-04", "病案首页24小时内完成率", "病案首页在患者出院后24小时内完成的病历数 / 同期出院患者病历总数 × 100%", "病案首页在患者出院后24小时内完成的病历数", "同期出院患者病历总数", "mr.mr_datetime（字段注释为病案提交时间）", "blocked", "未证明 mr_datetime 等同病案首页完成时间"),
    IndicatorDefinition("MER-ME-01", "CT/MRI检查记录符合率", "CT/MRI检查医嘱、报告单、病程记录相对应的住院患者病历数 / 同期接受CT/MRI检查的住院患者病历总数 × 100%", "CT/MRI检查医嘱、报告单、病程记录相对应的住院患者病历数", "同期接受CT/MRI检查的住院患者病历总数", "LX0609 仅覆盖部分检查记录规则", "blocked", "缺完整适用人群和三类记录整体符合结论"),
    IndicatorDefinition("MER-ME-02", "病理检查记录符合率", "手术记录、病理检查报告单、病程记录相对应的住院患者病历数 / 同期开展病理检查的住院患者病历总数 × 100%", "手术记录、病理检查报告单、病程记录相对应的住院患者病历数", "同期开展病理检查的住院患者病历总数", "LX0609 局部规则", "blocked", "缺完整适用人群和整体符合结论"),
    IndicatorDefinition("MER-ME-03", "细菌培养检查记录符合率", "细菌培养检查的医嘱、报告单、病程记录相对应的住院患者病历数 / 同期开展细菌培养检查的住院患者病历总数 × 100%", "细菌培养检查的医嘱、报告单、病程记录相对应的住院患者病历数", "同期开展细菌培养检查的住院患者病历总数", "LX0609 局部规则", "blocked", "缺完整适用人群和整体符合结论"),
    IndicatorDefinition("MER-D&T-01", "抗菌药物使用记录符合率", "抗菌药物使用医嘱、病程记录相对应的住院患者病历数 / 同期使用抗菌药物的住院患者病历总数 × 100%", "抗菌药物使用医嘱、病程记录相对应的住院患者病历数", "同期使用抗菌药物的住院患者病历总数", "局部规则/医嘱资料", "blocked", "缺抗菌药物完整适用人群及整体符合结论"),
    IndicatorDefinition("MER-D&T-02", "恶性肿瘤化学治疗记录符合率", "恶性肿瘤化学治疗医嘱、病程记录相对应的住院患者病历数 / 同期接受恶性肿瘤化学治疗的住院患者病历总数 × 100%", "恶性肿瘤化学治疗医嘱、病程记录相对应的住院患者病历数", "同期接受恶性肿瘤化学治疗的住院患者病历总数", "LX0609 局部规则", "blocked", "缺化疗完整适用人群及整体符合结论"),
    IndicatorDefinition("MER-D&T-03", "恶性肿瘤放射治疗记录符合率", "恶性肿瘤放射治疗医嘱（治疗单）、病程记录相对应的住院患者病历数 / 同期开展恶性肿瘤放射治疗的住院患者病历总数 × 100%", "恶性肿瘤放射治疗医嘱（治疗单）、病程记录相对应的住院患者病历数", "同期开展恶性肿瘤放射治疗的住院患者病历总数", "无完整执行结果", "blocked", "缺放疗适用人群及整体符合结论"),
    IndicatorDefinition("MER-D&T-04", "手术相关记录完整率", "手术相关记录完整的住院手术患者病历数 / 同期住院手术患者病历总数 × 100%", "手术相关记录完整的住院手术患者病历数", "同期住院手术患者病历总数", "LX0609 多条局部手术规则", "blocked", "局部规则不能替代完整性整体结论"),
    IndicatorDefinition("MER-D&T-05", "植入物相关记录符合率", "植入物相关记录符合的住院患者病历数 / 同期使用植入物的住院患者病历总数 × 100%", "植入物相关记录符合的住院患者病历数", "同期使用植入物的住院患者病历总数", "LX0609 局部规则", "blocked", "缺植入物完整适用人群及条码整体事实"),
    IndicatorDefinition("MER-D&T-06", "临床用血相关记录符合率", "临床用血相关记录符合的住院患者病历数 / 同期存在临床用血的住院患者病历总数 × 100%", "临床用血相关记录符合的住院患者病历数", "同期存在临床用血的住院患者病历总数", "LX0609 局部规则", "blocked", "缺三类内容整体符合结论"),
    IndicatorDefinition("MER-D&T-07", "医师查房记录完整率", "医师查房记录完整的住院患者病历数 / 同期住院患者病历总数 × 100%", "医师查房记录完整的住院患者病历数", "同期住院患者病历总数", "LX0609 局部规则", "blocked", "缺完整性整体结论"),
    IndicatorDefinition("MER-D&T-08", "患者抢救记录及时完成率", "抢救记录及时完成的住院患者病历数 / 同期接受抢救的住院患者病历总数 × 100%", "抢救记录及时完成的住院患者病历数", "同期接受抢救的住院患者病历总数", "LX0609-004 只覆盖6小时时限", "blocked", "国家说明同时要求书写时限和内容符合规范，现有单规则缺内容整体符合结论"),
    IndicatorDefinition("MER-TQ-01", "出院患者病历2日归档率", "2个工作日内完成归档的出院患者病历数 / 同期出院患者病历总数 × 100%", "2个工作日内完成归档的出院患者病历数", "同期出院患者病历总数", "无权威归档时间来源", "blocked", "缺归档时间和工作日历；不得用出院时间代替归档时间"),
    IndicatorDefinition("MER-TQ-02", "出院患者病历归档完整率", "归档内容完整病例数 / 同期出院患者病历总数 × 100%", "归档病历内容完整病例", "同期出院患者病历总数", "无权威归档完整性结果", "blocked", "缺归档状态和归档内容完整性 owner"),
    IndicatorDefinition("MER-TQ-03", "主要诊断填写正确率", "病案首页中主要诊断填写正确的出院患者病历数 / 同期出院患者病历总数 × 100%", "病案首页中主要诊断填写正确的出院患者病历数", "同期出院患者病历总数", "首页/编码质控仅局部结果", "blocked", "缺全量主要诊断填写正确性结论"),
    IndicatorDefinition("MER-TQ-04", "主要诊断编码正确率", "病案首页中主要诊断编码正确的出院患者病历数 / 同期出院患者病历总数 × 100%", "病案首页中主要诊断编码正确的出院患者病历数", "同期出院患者病历总数", "coding_qc 仅已执行子集", "blocked", "缺全量编码执行覆盖和该指标专属结论"),
    IndicatorDefinition("MER-TQ-05", "主要手术填写正确率", "病案首页中主要手术填写正确的出院患者病历数 / 同期出院手术患者病历总数 × 100%", "病案首页中主要手术填写正确的出院患者病历数", "同期出院手术患者病历总数", "首页质控局部结果", "blocked", "缺主要手术填写正确性专属结论"),
    IndicatorDefinition("MER-TQ-06", "主要手术编码正确率", "病案首页中主要手术编码正确的出院患者病历数 / 同期出院手术患者病历总数 × 100%", "病案首页中主要手术编码正确的出院患者病历数", "同期出院手术患者病历总数", "coding_qc 仅已执行子集", "blocked", "缺全量编码执行覆盖和该指标专属结论"),
    IndicatorDefinition("MER-TQ-07", "不合理复制病历发生率", "出现不合理复制病历内容的出院患者病历数 / 同期出院患者病历总数 × 100%", "出现不合理复制病历内容的出院患者病历数", "同期出院患者病历总数", "LX0609-016/017 仅覆盖其中两类", "blocked", "国家口径含四类情形，现有规则只覆盖部分，不能拼成完整指标"),
    IndicatorDefinition("MER-TQ-08", "知情同意书规范签署率", "规范签署知情同意书的出院患者病历数 / 同期存在知情同意书签署的出院患者病历总数 × 100%", "规范签署知情同意书的出院患者病历数", "同期存在知情同意书签署的出院患者病历总数", "LX0609 仅覆盖部分同意书", "blocked", "缺全部同意书类型适用人群和整体签署结论"),
    IndicatorDefinition("MER-TQ-09", "甲级病历率", "甲级出院患者病历数 / 同期出院患者病历总数 × 100%", "甲级出院患者病历数", "同期出院患者病历总数", "mr.medicalrecord_quality / scoring_service 均未形成官方等级映射合同", "blocked", "medicalrecord_quality 值域/来源未证实；评分标准等级名称可自定义，不能假设名为“甲”即官方甲级病历"),
)

DEFINITION_BY_CODE = {item.code: item for item in DEFINITIONS}


def _text(value: Any, default: str = "") -> str:
    return default if value is None else (str(value).strip() or default)


def _state_for(definition: IndicatorDefinition, row: base_report.CaseRow | None) -> str:
    if row is None:
        return "unknown"
    if definition.rule_id:
        status = row.rule_statuses.get(definition.rule_id, "")
        return status if status in {"compliant", "non_compliant", "not_applicable"} else "unknown"
    return "unknown"


def _record_item(
    ctx: base_report.ReportContext,
    rows: Mapping[tuple[str, str, str], base_report.CaseRow],
    identity: tuple[str, str, str],
    definition: IndicatorDefinition,
) -> dict[str, Any]:
    row = rows.get(identity)
    source = ctx.scope_records.get(identity, {})
    return {
        "institute_id": identity[0], "patient_id": identity[1], "visit_id": identity[2],
        "patient_name": _text(source.get("patient_name")),
        "department": _text(source.get("department"), "未分科室"),
        "doctor": _text(source.get("attending_physician"), "未登记主治医师"),
        "indicator_code": definition.code,
        "indicator_name": definition.name,
        "state": _state_for(definition, row),
        "source_value": None,
        "qc_completed_at": row.completed_at if row else None,
    }


def _metric(definition: IndicatorDefinition, items: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(item["state"] for item in items)
    eligible = counts["compliant"] + counts["non_compliant"]
    verified_rate = round(counts["compliant"] * 100 / eligible, 2) if eligible else None
    return {
        **definition.__dict__,
        "cohort_total": len(items),
        "eligible_total": eligible,
        "numerator_total": counts["compliant"],
        "not_applicable_total": counts["not_applicable"],
        "unknown_total": counts["unknown"],
        "verified_subset_rate": verified_rate,
        "official_rate": None,
        "calculation_status": "partial" if eligible else "unavailable",
    }


def build_report_context(
    *, department: str | None = None, doctor: str | None = None,
    discharged_from: date | None = None, discharged_to: date | None = None,
) -> base_report.ReportContext:
    if discharged_from and discharged_to and discharged_from > discharged_to:
        raise MedicalRecordIndicatorInvalid("discharged_from 不能晚于 discharged_to")
    try:
        from .workstation.luxian_0609_result_analysis_service import _load_current_workstation_records

        def scope_loader(**kwargs: Any) -> list[dict[str, str]]:
            return _load_current_workstation_records(
                **kwargs, start_date=discharged_from, end_date=discharged_to, date_field="discharge",
            )

        return base_report.build_report_context(
            scene="final", department=department, doctor=doctor,
            scope_loader=scope_loader,
            review_loader=lambda _anchors: {},
            manual_loader=lambda _identities: [],
            standard_loader=lambda _scene: None,
            rule_meta_loader=lambda: {},
        )
    except (base_report.RecordQualityReportInvalid, base_report.RecordQualityReportTooLarge) as exc:
        raise MedicalRecordIndicatorInvalid(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - 对外由路由脱敏
        raise MedicalRecordIndicatorUnavailable("病案指标来源暂不可用") from exc


def summarize(ctx: base_report.ReportContext) -> dict[str, Any]:
    identities = sorted(ctx.scope_records)
    rows = {row.identity: row for row in ctx.rows}
    items_by_code = {
        definition.code: [_record_item(ctx, rows, identity, definition) for identity in identities]
        for definition in DEFINITIONS if definition.rule_id
    }
    indicators = [
        _metric(definition, items_by_code.get(definition.code, [])) if definition.code in items_by_code
        else {**definition.__dict__, "cohort_total": len(identities), "eligible_total": 0,
              "numerator_total": 0, "not_applicable_total": 0, "unknown_total": len(identities),
              "verified_subset_rate": None, "official_rate": None, "calculation_status": "blocked"}
        for definition in DEFINITIONS
    ]
    return {
        "scope": {
            "basis": "discharged_case_cohort",
            "description": "按出院日期筛选的病历队列；部分指标原文分母并非出院队列，故只展示已核实子集率",
            "department": ctx.scope.get("department"), "doctor": ctx.scope.get("doctor"),
            "archive_status": "unverified",
        },
        "summary": {"indicator_total": 27, "partial_total": 2, "blocked_total": 25, "cohort_total": len(identities)},
        "indicators": indicators,
    }


def breakdown(ctx: base_report.ReportContext, *, indicator_code: str, dimension: str) -> dict[str, Any]:
    definition = DEFINITION_BY_CODE.get(_text(indicator_code).upper())
    if definition is None:
        raise MedicalRecordIndicatorInvalid("indicator_code 不存在")
    if dimension not in DIMENSIONS:
        raise MedicalRecordIndicatorInvalid("dimension 必须为 department 或 doctor")
    groups: dict[str, list[dict[str, Any]]] = {}
    rows = {row.identity: row for row in ctx.rows}
    for identity in sorted(ctx.scope_records):
        item = _record_item(ctx, rows, identity, definition)
        groups.setdefault(item[dimension], []).append(item)
    return {"indicator": definition.__dict__, "dimension": dimension,
            "items": [{**_metric(definition, rows), "name": name} for name, rows in sorted(groups.items())]}


def cases_page(
    ctx: base_report.ReportContext, *, indicator_code: str, state: str | None = None,
    page: int = 1, page_size: int = 20,
) -> dict[str, Any]:
    definition = DEFINITION_BY_CODE.get(_text(indicator_code).upper())
    if definition is None:
        raise MedicalRecordIndicatorInvalid("indicator_code 不存在")
    if state is not None and state not in STATES:
        raise MedicalRecordIndicatorInvalid("state 值无效")
    if page < 1 or not 1 <= page_size <= MAX_PAGE_SIZE:
        raise MedicalRecordIndicatorInvalid("分页参数无效")
    rows = {row.identity: row for row in ctx.rows}
    items = [_record_item(ctx, rows, identity, definition) for identity in sorted(ctx.scope_records)]
    if state:
        items = [item for item in items if item["state"] == state]
    start = (page - 1) * page_size
    return {"total": len(items), "page": page, "page_size": page_size, "items": items[start:start + page_size]}


def export_csv(
    ctx: base_report.ReportContext, *, kind: str = "indicators",
    indicator_code: str | None = None, dimension: str = "department", state: str | None = None,
) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    if kind == "indicators":
        writer.writerow(["指标编码", "指标名称", "可计算性", "已核实分子", "已核实分母", "未知病例", "已核实子集率", "官方率", "缺口"])
        for item in summarize(ctx)["indicators"]:
            writer.writerow([item["code"], item["name"], item["calculation_status"], item["numerator_total"],
                             item["eligible_total"], item["unknown_total"], item["verified_subset_rate"], "未知",
                             base_report._csv_cell(item.get("blocker") or "")])
    elif kind == "breakdown":
        result = breakdown(ctx, indicator_code=indicator_code or "", dimension=dimension)
        writer.writerow(["维度", "已核实分子", "已核实分母", "不适用", "未知", "已核实子集率"])
        for item in result["items"]:
            writer.writerow([base_report._csv_cell(item["name"]), item["numerator_total"], item["eligible_total"],
                             item["not_applicable_total"], item["unknown_total"], item["verified_subset_rate"]])
    elif kind == "cases":
        definition = DEFINITION_BY_CODE.get(_text(indicator_code).upper())
        if definition is None:
            raise MedicalRecordIndicatorInvalid("indicator_code 不存在")
        rows = {row.identity: row for row in ctx.rows}
        items = [_record_item(ctx, rows, identity, definition) for identity in sorted(ctx.scope_records)]
        if state:
            if state not in STATES:
                raise MedicalRecordIndicatorInvalid("state 值无效")
            items = [item for item in items if item["state"] == state]
        writer.writerow(["机构", "患者ID", "就诊ID", "姓名", "科室", "医生", "指标状态", "来源值", "质控完成时间"])
        for item in items:
            writer.writerow([base_report._csv_cell(item[key]) for key in ("institute_id", "patient_id", "visit_id", "patient_name", "department", "doctor", "state", "source_value", "qc_completed_at")])
    else:
        raise MedicalRecordIndicatorInvalid("kind 必须为 indicators、breakdown 或 cases")
    return output.getvalue().encode("utf-8-sig")
