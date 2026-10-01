from __future__ import annotations

import csv
import io
from pathlib import Path

from app.services import medical_record_indicator_service as report
from app.services import record_quality_report_service as base


OFFICIAL_INDICATORS = (
    ("MER-HR-01", "住院病案管理人员月均负担出院患者病历数", "出院患者病历总数", "同期住院病案管理人员实际工作总月数"),
    ("MER-HR-02", "门诊病案管理人员月均负担门诊患者病历数", "门诊患者病历总数", "同期门诊病案管理人员实际工作总月数"),
    ("MER-HR-03", "病案编码人员月均负担出院患者病历数", "出院患者病历总数", "同期病案编码人员实际工作总月数"),
    ("MER-TL-01", "入院记录24小时内完成率", "入院记录在患者入院24小时内完成", "同期住院患者病历总数"),
    ("MER-TL-02", "手术记录24小时内完成率", "手术记录在术后24小时内完成", "同期住院手术患者病历总数"),
    ("MER-TL-03", "出院记录24小时内完成率", "出院记录在患者出院后24小时内完成", "同期出院患者病历总数"),
    ("MER-TL-04", "病案首页24小时内完成率", "病案首页在患者出院后24小时内完成", "同期出院患者病历总数"),
    ("MER-ME-01", "CT/MRI检查记录符合率", "CT/MRI检查医嘱、报告单、病程记录相对应", "同期接受CT/MRI检查"),
    ("MER-ME-02", "病理检查记录符合率", "手术记录、病理检查报告单、病程记录相对应", "同期开展病理检查"),
    ("MER-ME-03", "细菌培养检查记录符合率", "细菌培养检查的医嘱、报告单、病程记录相对应", "同期开展细菌培养检查"),
    ("MER-D&T-01", "抗菌药物使用记录符合率", "抗菌药物使用医嘱、病程记录相对应", "同期使用抗菌药物"),
    ("MER-D&T-02", "恶性肿瘤化学治疗记录符合率", "恶性肿瘤化学治疗医嘱、病程记录相对应", "同期接受恶性肿瘤化学治疗"),
    ("MER-D&T-03", "恶性肿瘤放射治疗记录符合率", "恶性肿瘤放射治疗医嘱", "同期开展恶性肿瘤放射治疗"),
    ("MER-D&T-04", "手术相关记录完整率", "手术相关记录完整", "同期住院手术患者病历总数"),
    ("MER-D&T-05", "植入物相关记录符合率", "植入物相关记录符合", "同期使用植入物"),
    ("MER-D&T-06", "临床用血相关记录符合率", "临床用血相关记录符合", "同期存在临床用血"),
    ("MER-D&T-07", "医师查房记录完整率", "医师查房记录完整", "同期住院患者病历总数"),
    ("MER-D&T-08", "患者抢救记录及时完成率", "抢救记录及时完成", "同期接受抢救"),
    ("MER-TQ-01", "出院患者病历2日归档率", "2个工作日内完成归档", "同期出院患者病历总数"),
    ("MER-TQ-02", "出院患者病历归档完整率", "归档病历内容完整", "同期出院患者病历总数"),
    ("MER-TQ-03", "主要诊断填写正确率", "病案首页中主要诊断填写正确", "同期出院患者病历总数"),
    ("MER-TQ-04", "主要诊断编码正确率", "病案首页中主要诊断编码正确", "同期出院患者病历总数"),
    ("MER-TQ-05", "主要手术填写正确率", "病案首页中主要手术填写正确", "同期出院手术患者病历总数"),
    ("MER-TQ-06", "主要手术编码正确率", "病案首页中主要手术编码正确", "同期出院手术患者病历总数"),
    ("MER-TQ-07", "不合理复制病历发生率", "出现不合理复制病历内容", "同期出院患者病历总数"),
    ("MER-TQ-08", "知情同意书规范签署率", "规范签署知情同意书", "同期存在知情同意书签署"),
    ("MER-TQ-09", "甲级病历率", "甲级出院患者病历数", "同期出院患者病历总数"),
)


def test_all_27_definitions_follow_official_source_order_name_and_formula_terms():
    source_path = (
        Path(__file__).resolve().parents[3]
        / "docs"
        / "0602"
        / "医疗机构病历书写规范（2026年版）_合并.md"
    )
    source = source_path.read_text(encoding="utf-8")
    section = source.split("# 病案管理质量控制指标（2021年版）", 1)[1].split(
        "# 门（急）诊诊疗信息页质量管理规定（试行）", 1
    )[0]
    compact_section = "".join(section.split())

    assert [(item.code, item.name) for item in report.DEFINITIONS] == [
        (code, name) for code, name, _, _ in OFFICIAL_INDICATORS
    ]
    positions = []
    for code, name, numerator_term, denominator_term in OFFICIAL_INDICATORS:
        heading = f"{name}（{code}）"
        positions.append(compact_section.index("".join(heading.split())))
        definition = report.DEFINITION_BY_CODE[code]
        assert name == definition.name
        assert numerator_term in definition.numerator
        assert denominator_term in definition.denominator
    assert positions == sorted(positions)


def test_luxian_002_and_003_are_not_swapped():
    catalog_path = (
        Path(__file__).resolve().parents[3]
        / "docs"
        / "0602"
        / "luxian_0609_formal_rule_catalog.csv"
    )
    with catalog_path.open(encoding="utf-8-sig", newline="") as stream:
        rows = {row["qc_point_id"]: row for row in csv.DictReader(stream)}
    assert "首次病程" in rows["LX0609-002"]["source_document"]
    assert "8 小时" in rows["LX0609-002"]["customer_text"]
    assert "手术记录" in rows["LX0609-003"]["source_document"]
    assert "24小时" in rows["LX0609-003"]["customer_text"]
    assert report.DEFINITION_BY_CODE["MER-TL-02"].rule_id == "LX0609-003"


def _context() -> base.ReportContext:
    identities = [("i", "p1", "v1"), ("i", "p2", "v2"), ("i", "p3", "v3")]
    records = {
        identity: {
            "patient_name": "=病例" if identity[1] == "p1" else f"病例{identity[1]}",
            "department": "内科" if identity[1] != "p3" else "外科",
            "attending_physician": "甲医生" if identity[1] != "p3" else "乙医生",
        }
        for identity in identities
    }
    rows = [
        base.CaseRow(
            identity=identities[0], patient_name="病例p1", department="内科", doctor="甲医生",
            completed_at="2026-09-01T00:00:00Z", auto_defect_rule_ids=[], score_status="scored", grade="甲",
            rule_statuses={"LX0609-001": "compliant", "LX0609-003": "not_applicable", "LX0609-004": "not_applicable"},
        ),
        base.CaseRow(
            identity=identities[1], patient_name="病例p2", department="内科", doctor="甲医生",
            completed_at="2026-09-02T00:00:00Z", auto_defect_rule_ids=["LX0609-001"], score_status="scored", grade="乙",
            rule_statuses={"LX0609-001": "non_compliant", "LX0609-003": "compliant", "LX0609-004": "unknown"},
        ),
    ]
    return base.ReportContext(
        scene="final", scope={"department": None, "doctor": None}, record_total=3,
        unavailable_total=0, rows=rows, standard=None, score_status="configured",
        review_status="available", manual_status="available", rule_meta={},
        department_record_totals={"内科": 2, "外科": 1},
        doctor_record_totals={"甲医生": 2, "乙医生": 1}, scope_records=records,
    )


def test_summary_keeps_27_contracts_and_does_not_turn_unknown_into_pass():
    result = report.summarize(_context())
    assert result["summary"] == {
        "indicator_total": 27, "partial_total": 2, "blocked_total": 25, "cohort_total": 3,
    }
    indicator = next(item for item in result["indicators"] if item["code"] == "MER-TL-01")
    assert indicator["numerator_total"] == 1
    assert indicator["eligible_total"] == 2
    assert indicator["unknown_total"] == 1
    assert indicator["verified_subset_rate"] == 50.0
    assert indicator["official_rate"] is None
    assert indicator["calculation_status"] == "partial"


def test_summary_builds_case_row_index_once():
    class CountingRows(list):
        iterations = 0

        def __iter__(self):
            self.iterations += 1
            return super().__iter__()

    ctx = _context()
    ctx.rows = CountingRows(ctx.rows)
    report.summarize(ctx)
    assert ctx.rows.iterations == 1


def test_blocked_archive_indicator_has_exact_missing_source():
    indicator = next(item for item in report.summarize(_context())["indicators"] if item["code"] == "MER-TQ-01")
    assert indicator["calculation_status"] == "blocked"
    assert "归档时间" in indicator["blocker"]
    assert "不得用出院时间代替" in indicator["blocker"]


def test_breakdown_cases_and_csv_share_the_same_three_coordinate_rows():
    ctx = _context()
    result = report.breakdown(ctx, indicator_code="MER-TL-01", dimension="department")
    inner = next(item for item in result["items"] if item["name"] == "内科")
    assert inner["eligible_total"] == 2 and inner["verified_subset_rate"] == 50.0
    page = report.cases_page(ctx, indicator_code="MER-TL-01", state="unknown")
    assert page["total"] == 1
    assert (page["items"][0]["institute_id"], page["items"][0]["patient_id"], page["items"][0]["visit_id"]) == ("i", "p3", "v3")
    rows = list(csv.reader(io.StringIO(report.export_csv(
        ctx, kind="cases", indicator_code="MER-TL-01",
    ).decode("utf-8-sig"))))
    assert len(rows) == 4
    assert rows[1][3].startswith("'=")


def test_grade_without_official_mapping_stays_blocked():
    indicator = next(item for item in report.summarize(_context())["indicators"] if item["code"] == "MER-TQ-09")
    assert indicator["calculation_status"] == "blocked"
    assert indicator["eligible_total"] == 0
    assert "等级名称可自定义" in indicator["blocker"]
    assert indicator["official_rate"] is None


def test_invalid_filters_fail_closed():
    ctx = _context()
    for callback in (
        lambda: report.breakdown(ctx, indicator_code="UNKNOWN", dimension="department"),
        lambda: report.breakdown(ctx, indicator_code="MER-TL-01", dimension="ward"),
        lambda: report.cases_page(ctx, indicator_code="MER-TL-01", state="passed"),
        lambda: report.export_csv(ctx, kind="unknown"),
    ):
        try:
            callback()
        except report.MedicalRecordIndicatorInvalid:
            pass
        else:
            raise AssertionError("应拒绝无效参数")
