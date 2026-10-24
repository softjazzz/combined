"""病案首页统计分析服务：读取器全部注入，不访问数据库。"""

from __future__ import annotations

import csv
import io
from datetime import datetime

import pytest

from app.services import frontpage_quality_report_service as report
from app.services.modern_case_qc_result_service import SchemaUnavailable


@pytest.fixture(autouse=True)
def report_actor_scope(monkeypatch):
    # 本文件只验证聚合，持久账号机构范围另有真实 SQLite 合同。
    monkeypatch.setattr(report, "authorized_report_institute", lambda actor_id: None)


def _latest(source, patient, *, date="2026-09-20T02:00:00", defects=()):
    return {
        "source_key": source, "institute_id": "LX", "patient_id": patient, "visit_id": "v1",
        "result": {"id": f"{source}-{patient}", "analysis_date": date},
        "defects": [
            {"rule_code": code, "rule_name": f"规则{code}", "severity": severity, "category": category}
            for code, severity, category in defects
        ],
    }


def _pool(patient, department="内科", doctor="甲医生"):
    return {
        "institute_id": "LX", "patient_id": patient, "visit_id": "v1",
        "patient_name": f"病例{patient}", "department": department, "attending_physician": doctor,
    }


LATEST = [
    _latest("frontpage_formal_qc", "p1", defects=[("FP-1", "error", "required"), ("FP-2", "warning", "format")]),
    _latest("coding_qc", "p1", defects=[("CR-1", "error", "format")]),
    _latest("frontpage_formal_qc", "p2"),
    _latest("coding_qc", "p3", defects=[("CR-1", "warning", "semantic")]),
]
POOL = [_pool("p1"), _pool("p2", department="外科"), _pool("p3")]


def _context(latest=LATEST, pool=POOL, **params):
    calls = []

    def scope_loader(**kwargs):
        calls.append(kwargs)
        return [
            item for item in pool
            if (not kwargs.get("department") or item["department"] == kwargs["department"])
        ]

    ctx = report.build_report_context(
        scope_loader=scope_loader, latest_loader=lambda sources: latest, **params,
    )
    return ctx, calls


def test_kpis_split_coding_and_noncoding_by_source_owner():
    ctx, calls = _context()
    kpis = report.summarize(ctx)["kpis"]
    assert kpis == {
        "case_total": 3,
        "problem_case_total": 2,
        "problem_rate": 0.6667,
        "frontpage_case_total": 2,
        "coding_case_total": 2,
        "noncoding_defect_total": 2,
        "coding_defect_total": 2,
        "noncoding_problem_case_total": 1,
        "coding_problem_case_total": 2,
    }
    assert calls == [{"department": None, "doctor": None}]


def test_distributions_top_rules_and_department_rows():
    summary = report.summarize(_context()[0])
    coding = next(item for item in summary["sources"] if item["source_key"] == "coding_qc")
    assert coding["top_rules"] == [{"rule_code": "CR-1", "defect_total": 2, "rule_name": "规则CR-1"}]
    assert {item["severity"]: item["defect_total"] for item in coding["severity_distribution"]} == {
        "error": 1, "warning": 1,
    }
    rows = {row["department"]: row for row in summary["department_rows"]}
    assert rows["内科"]["case_total"] == 2 and rows["内科"]["problem_case_total"] == 2
    assert rows["外科"]["problem_case_total"] == 0 and rows["外科"]["problem_rate"] == 0.0
    assert summary["department_rows"][0]["department"] == "内科"


def test_window_applies_to_latest_result_without_falling_back():
    latest = [
        _latest("frontpage_formal_qc", "p1", date="2026-09-10T00:00:00", defects=[("FP-1", "error", "required")]),
        _latest("coding_qc", "p1", date="2026-09-25T00:00:00"),
    ]
    ctx, _ = _context(latest=latest, analyzed_from=datetime(2026, 9, 20), analyzed_to=datetime(2026, 9, 30))
    kpis = report.summarize(ctx)["kpis"]
    # 首页最新结果不在窗口内：该来源不计入，也不回退更早结果。
    assert kpis["case_total"] == 1 and kpis["frontpage_case_total"] == 0
    assert kpis["problem_case_total"] == 0


def test_cases_outside_pool_are_unassigned_or_excluded_when_filtering():
    latest = [*LATEST, _latest("frontpage_formal_qc", "p9", defects=[("FP-9", "error", "required")])]
    ctx, _ = _context(latest=latest)
    assert {row.department for row in ctx.rows if row.identity[1] == "p9"} == {report.UNASSIGNED_DEPARTMENT}
    filtered, calls = _context(latest=latest, department="内科")
    assert [row.identity[1] for row in filtered.rows] == ["p1", "p3"]
    assert calls == [{"department": "内科", "doctor": None}]


def test_records_drilldown_filters_and_unknown_is_not_zero():
    ctx, _ = _context()
    page = report.records_page(ctx, source="coding", rule_code="cr-1")
    assert [item["patient_id"] for item in page["items"]] == ["p1", "p3"]
    p3 = page["items"][1]
    assert p3["frontpage_defect_total"] is None and p3["coding_defect_total"] == 1
    problem = report.records_page(ctx, problem_only=True)
    assert problem["total"] == 2
    with pytest.raises(report.FrontpageQualityReportInvalid):
        report.records_page(ctx, source="settlement")


def test_csv_matches_page_scope_and_guards_formulas():
    pool = [_pool("p1", department="=HYPERLINK(1)"), *POOL[1:]]
    ctx, _ = _context(pool=pool)
    content = report.export_csv(ctx, sheet="records", source="coding")
    assert content.startswith(b"\xef\xbb\xbf")
    rows = list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
    assert [row["患者ID"] for row in rows] == ["p1", "p3"]
    assert rows[0]["科室"] == "'=HYPERLINK(1)"
    assert rows[1]["非编码缺陷数"] == "未质控"
    departments = list(csv.DictReader(io.StringIO(
        report.export_csv(ctx, sheet="departments").decode("utf-8-sig")
    )))
    assert {row["科室"] for row in departments} == {"'=HYPERLINK(1)", "外科", "内科"}


def test_schema_unavailable_and_read_failures_are_distinct():
    def missing(_sources):
        raise SchemaUnavailable("qc.qc_results missing modern identity columns")

    with pytest.raises(report.FrontpageQualityReportSchemaUnavailable):
        report.build_report_context(scope_loader=lambda **_: [], latest_loader=missing)

    def broken(_sources):
        raise RuntimeError("patient P001 SQL")

    with pytest.raises(report.FrontpageQualityReportUnavailable):
        report.build_report_context(scope_loader=lambda **_: [], latest_loader=broken)


def test_no_results_skips_pool_read_and_reports_zero_cases():
    ctx, calls = _context(latest=[])
    assert report.summarize(ctx)["kpis"]["case_total"] == 0
    assert calls == []


def test_range_limit_and_window_order_are_enforced(monkeypatch):
    monkeypatch.setattr(report, "MAX_REPORT_CASES", 1)
    with pytest.raises(report.FrontpageQualityReportTooLarge):
        _context()
    with pytest.raises(report.FrontpageQualityReportInvalid):
        _context(analyzed_from=datetime(2026, 9, 30), analyzed_to=datetime(2026, 9, 1))
