from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

import pytest

from app.services import record_quality_report_service as report


def _case(institute: str, patient: str, visit: str = "same") -> dict:
    return {
        "institute_id": institute, "patient_id": patient, "visit_id": visit,
        "patient_name": f"病例{patient}", "department": "内科", "attending_physician": "甲医生",
    }


def _context(*, records=None, results=None, reviews=None, manual=None,
             standard_loader=None, projector=None, results_loader=None,
             manual_loader=None, **params):
    records = records if records is not None else [_case("a", "p1"), _case("b", "p2")]
    results = results if results is not None else {
        ("a", "p1", "same"): {
            "status": "ready", "completed_at": "2026-09-26T16:00:00Z",
            "root_job_id": "job-a", "envelope_id": "env-a",
            "items": [{"rule_id": "LX0609-001", "is_confirmed_issue": True}],
        },
        ("b", "p2", "same"): {
            "status": "ready", "completed_at": "2026-09-27T00:00:00+08:00",
            "root_job_id": "job-b", "envelope_id": "env-b", "items": [],
        },
    }
    reviews = reviews if reviews is not None else {
        ("a", "p1", "same"): "approved", ("b", "p2", "same"): "pending_review",
    }
    manual = manual if manual is not None else [
        {"identity": ("a", "p1", "same"), "rule_code": "LX0609-001", "review_status": "approved"},
        {"identity": ("b", "p2", "same"), "rule_code": "LX0609-002", "review_status": "rejected"},
    ]
    return report.build_report_context(
        scene="running", scope_loader=lambda **kwargs: records,
        results_loader=results_loader or (lambda refs: results),
        review_loader=lambda anchors: reviews,
        manual_loader=manual_loader or (lambda identities: manual),
        standard_loader=standard_loader or (lambda scene: None),
        projector=projector or (lambda items: list(items)),
        rule_meta_loader=lambda: {
            "LX0609-001": {"rule_name": "规则一", "document": "入院记录", "defect_level": "一般"},
        },
        **params,
    )


def test_final_reads_discharged_scope_and_marks_archive_unverified():
    """终末口径 B：已出院且有质控结果，报表范围显式标注归档未核验，不冒称已归档。"""
    called = []
    standard_scenes = []
    ctx = report.build_report_context(
        scene="final",
        scope_loader=lambda **kwargs: called.append(kwargs) or [_case("a", "p1")],
        results_loader=lambda refs: {("a", "p1", "same"): {
            "status": "ready", "completed_at": "2026-09-26T16:00:00Z",
            "root_job_id": "job-a", "envelope_id": "env-a", "items": [],
        }},
        review_loader=lambda anchors: {},
        manual_loader=lambda identities: [],
        standard_loader=lambda scene: standard_scenes.append(scene),
        projector=lambda items: list(items),
        rule_meta_loader=lambda: {},
    )
    assert called == [{"department": None, "doctor": None, "hospital_status": "discharged"}]
    assert standard_scenes == ["final"]
    assert ctx.scope["scope_basis"] == "discharged_with_qc_result"
    assert ctx.scope["archive_status"] == "unverified"
    assert ctx.scope["scope_label"] == "已出院病历（未核验归档）"
    assert report.summarize(ctx)["kpis"]["qc_ready_total"] == 1


def test_running_scope_has_no_archive_status():
    ctx = _context()
    assert ctx.scope["scope_basis"] == "inpatient_with_qc_result"
    assert ctx.scope["archive_status"] is None


def test_three_coordinate_identity_drilldown_and_csv_match():
    ctx = _context()
    assert ctx.scope["scope_label"] == "当前在院病历"
    summary = report.summarize(ctx)
    assert summary["kpis"]["qc_ready_total"] == 2
    assert summary["kpis"]["auto_defect_total"] == 1
    assert summary["kpis"]["manual_defect_total"] == 1
    page = report.records_page(ctx, rule_id="LX0609-001")
    assert page["total"] == 1
    assert page["items"][0]["institute_id"] == "a"
    exported = report.export_csv(ctx, sheet="records", rule_id="LX0609-001")
    assert exported.startswith(b"\xef\xbb\xbf")
    csv_rows = list(csv.DictReader(io.StringIO(exported.decode("utf-8-sig"))))
    assert len(csv_rows) == page["total"]
    assert csv_rows[0]["患者编号"] == page["items"][0]["patient_id"]


def test_duplicate_projected_rule_status_fails_closed_instead_of_last_write_wins():
    def duplicate_projector(items):
        return [
            {"rule_id": "LX0609-003", "status": "compliant", "is_confirmed_issue": False},
            {"rule_id": "LX0609-003", "status": "non_compliant", "is_confirmed_issue": True},
        ]

    ctx = _context(projector=duplicate_projector)
    assert ctx.rows[0].rule_statuses["LX0609-003"] == "unknown"


def test_mixed_timezone_bounds_are_normalized():
    ctx = _context(completed_from=datetime(2026, 9, 27, 0, 0),
                   completed_to=datetime(2026, 9, 26, 16, 0, tzinfo=timezone.utc))
    assert len(ctx.rows) == 2
    with pytest.raises(report.RecordQualityReportInvalid):
        _context(completed_from=datetime(2026, 9, 27, 1, 0),
                 completed_to=datetime(2026, 9, 26, 16, 0, tzinfo=timezone.utc))


def test_candidate_limit_fails_before_result_load(monkeypatch):
    monkeypatch.setattr(report, "MAX_REPORT_CASES", 1)
    called = []
    with pytest.raises(report.RecordQualityReportTooLarge):
        report.build_report_context(
            scene="running", scope_loader=lambda **kwargs: [_case("a", "p1"), _case("b", "p2")],
            results_loader=lambda refs: called.append(refs),
        )
    assert not called


def test_missing_reviews_and_manual_failure_are_not_zero():
    ctx = _context(reviews={}, manual=[])
    summary = report.summarize(ctx)
    assert summary["source_status"]["review"] == "unavailable"
    assert summary["kpis"]["review_approved_total"] is None
    ctx = _context(manual=[{"identity": ("a", "p1", "same"), "review_status": None}])
    summary = report.summarize(ctx)
    assert summary["source_status"]["manual_defect"] == "unavailable"
    assert summary["kpis"]["manual_defect_total"] is None
    with pytest.raises(report.RecordQualityReportUnavailable):
        report.records_page(ctx, has_defect=True)


def test_csv_formula_values_are_escaped():
    records = [_case("a", "p1")]
    records[0]["patient_name"] = "=HYPERLINK(\"x\")"
    ctx = _context(records=records)
    rows = list(csv.DictReader(io.StringIO(report.export_csv(ctx, sheet="records").decode("utf-8-sig"))))
    assert rows[0]["患者姓名"].startswith("'=")


def test_records_order_uses_instant_instead_of_iso_text():
    results = {
        ("a", "p1", "same"): {
            "status": "ready", "completed_at": "2026-09-27T00:30:00+08:00", "items": [],
        },
        ("b", "p2", "same"): {
            "status": "ready", "completed_at": "2026-09-26T17:00:00Z", "items": [],
        },
    }
    page = report.records_page(_context(results=results))
    assert [item["patient_id"] for item in page["items"]] == ["p2", "p1"]


def test_invalid_pagination_and_sheet():
    ctx = _context()
    with pytest.raises(report.RecordQualityReportInvalid):
        report.records_page(ctx, page_size=101)
    with pytest.raises(report.RecordQualityReportInvalid):
        report.export_csv(ctx, sheet="unknown")


def _standard():
    return {
        "id": "std", "name": "运行评分", "rule_set_key": report.LUXIAN_0609_RULE_SET_KEY,
        "base_score": 100, "veto_grade": "丙", "updated_at": "2026-09-27",
        "grade_bands": [
            {"name": "甲", "min_score": 90, "max_score": 100},
            {"name": "乙", "min_score": 75, "max_score": 90},
            {"name": "丙", "min_score": 0, "max_score": 75},
        ],
        "groups": [{"group_name": "病程", "max_deduction": None, "sort_order": 1}],
        "items": [{"group_name": "病程", "rule_id": "LX0609-001", "deduction": 1,
                   "is_veto": True, "enabled": True}],
    }


def test_real_scoring_veto_grade_and_distribution():
    ctx = _context(standard_loader=lambda scene: _standard())
    summary = report.summarize(ctx)
    assert summary["kpis"]["average_score"] == 99.5
    assert summary["kpis"]["veto_defect_total"] == 1
    assert summary["kpis"]["veto_record_total"] == 1
    assert {item["grade"]: item["count"] for item in summary["grade_distribution"]} == {"甲": 1, "乙": 0, "丙": 1}
    page = report.records_page(ctx, grade="丙")
    assert page["total"] == 1
    assert page["items"][0]["veto_hit"] is True


@pytest.mark.parametrize("scene", ["running", "final"])
def test_group_quality_metrics_and_selected_export_share_denominators(scene):
    ctx = _context(standard_loader=lambda _: _standard())
    ctx.scene = scene
    row = report.summarize(ctx)["department_rows"][0]
    assert row["defect_total"] == 2
    assert row["average_defect_total"] == 1
    assert row["reviewed_total"] == 1
    assert row["top_grade_total"] == 1
    assert row["grade_rates"] == {"甲": 0.5, "乙": 0, "丙": 0.5}
    columns = ["defect_total", "average_defect_total", "top_grade_total", "grade_rate:丙"]
    exported = list(csv.DictReader(io.StringIO(report.export_csv(ctx, columns=columns).decode("utf-8-sig"))))
    assert list(exported[0]) == ["名称", "缺陷总数", "平均缺陷数（每份已质控病历）", "最高等级病历数", "丙占比"]
    assert exported[0]["丙占比"] == "0.5"
    with pytest.raises(report.RecordQualityReportInvalid):
        report.export_csv(ctx, columns=["unknown"])


def test_group_quality_unknown_sources_do_not_become_zero():
    ctx = _context(manual_loader=lambda _: (_ for _ in ()).throw(RuntimeError("offline")))
    row = report.summarize(ctx)["department_rows"][0]
    assert row["defect_total"] is None
    assert row["average_defect_total"] is None
    assert row["top_grade_total"] is None
    auto = _context(defect_source="auto", manual_loader=lambda _: (_ for _ in ()).throw(RuntimeError("offline")))
    assert report.summarize(auto)["department_rows"][0]["average_defect_total"] == 0.5


def test_group_rates_preserve_configured_grade_names_and_partial_scores_are_unknown():
    standard = _standard()
    standard["grade_bands"][0]["name"] = "优秀"
    ctx = _context(standard_loader=lambda _: standard)
    assert "优秀" in report.summarize(ctx)["department_rows"][0]["grade_rates"]
    ctx.rows[0].score_status = "unavailable"
    row = report.summarize(ctx)["department_rows"][0]
    assert row["top_grade_total"] is None
    assert all(value is None for value in row["grade_rates"].values())


def test_report_scoring_consumes_exact_department_scope():
    standard = _standard()
    standard["items"][0].update({
        "department_scope_mode": "selected",
        "department_refs": [{"institute_id": "a", "department_name": "心内科"}],
    })
    ctx = _context(
        standard_loader=lambda scene: standard,
        department_loader=lambda identities: {
            ("a", "p1", "same"): "心内科", ("b", "p2", "same"): "心内科",
        },
    )
    rows = {row.identity: row for row in ctx.rows}
    assert rows[("a", "p1", "same")].score == 99.0
    assert rows[("b", "p2", "same")].score == 100.0


def test_report_department_loader_is_lazy_and_selected_failure_is_unavailable():
    calls = []

    def broken_loader(identities):
        calls.append(identities)
        raise RuntimeError("department unavailable")

    all_context = _context(standard_loader=lambda scene: _standard(), department_loader=broken_loader)
    assert all(row.score_status == "scored" for row in all_context.rows)
    assert calls == []

    standard = _standard()
    standard["items"][0].update({
        "department_scope_mode": "selected",
        "department_refs": [{"institute_id": "a", "department_name": "心内科"}],
    })
    selected_context = _context(
        standard_loader=lambda scene: standard,
        department_loader=broken_loader,
    )
    rows = {row.identity: row for row in selected_context.rows}
    assert rows[("a", "p1", "same")].score_status == "unavailable"
    assert rows[("a", "p1", "same")].score is None


def test_score_above_100_has_separate_distribution_bucket():
    standard = _standard()
    standard["base_score"] = 120
    standard["grade_bands"] = [{"name": "甲", "min_score": 0, "max_score": 120}]
    ctx = _context(standard_loader=lambda scene: standard)
    buckets = {item["bucket"]: item["count"] for item in report.summarize(ctx)["score_distribution"]}
    assert buckets["90-100"] == 0
    assert buckets[">100"] == 2


def test_failed_case_scoring_does_not_report_zero_veto():
    standard = _standard()
    standard["items"][0]["deduction"] = "invalid"
    ctx = _context(standard_loader=lambda scene: standard)
    summary = report.summarize(ctx)
    assert summary["kpis"]["scored_total"] == 1
    assert summary["kpis"]["veto_defect_total"] is None
    assert summary["kpis"]["veto_record_total"] is None
    assert summary["department_rows"][0]["veto_defect_total"] is None


@pytest.mark.parametrize("source,auto_total,manual_total,patient", [
    ("auto", 1, None, "p1"),
    ("manual", None, 1, "p1"),
])
def test_defect_source_consistent_across_summary_page_and_export(source, auto_total, manual_total, patient):
    ctx = _context(defect_source=source)
    summary = report.summarize(ctx)
    assert summary["kpis"]["auto_defect_total"] == auto_total
    assert summary["kpis"]["manual_defect_total"] == manual_total
    page = report.records_page(ctx, has_defect=True)
    assert [item["patient_id"] for item in page["items"]] == [patient]
    rows = list(csv.DictReader(io.StringIO(report.export_csv(
        ctx, sheet="records", has_defect=True,
    ).decode("utf-8-sig"))))
    assert [row["患者编号"] for row in rows] == [patient]


def test_projector_failure_counts_unavailable_without_inventing_result():
    def fail(items):
        raise ValueError("bad item")

    ctx = _context(projector=fail)
    summary = report.summarize(ctx)
    assert summary["kpis"]["qc_unavailable_total"] == 2
    assert summary["kpis"]["qc_ready_total"] == 0


def test_standard_failure_degrades_score_and_grade_filter_fails_closed():
    def fail(scene):
        raise RuntimeError("standard store unavailable")

    ctx = _context(standard_loader=fail)
    assert report.summarize(ctx)["score_standard"]["status"] == "unavailable"
    assert report.summarize(ctx)["kpis"]["average_score"] is None
    with pytest.raises(report.RecordQualityReportUnavailable):
        report.records_page(ctx, grade="甲")


def test_result_reader_failure_is_unavailable():
    def fail(refs):
        raise RuntimeError("result store unavailable")

    with pytest.raises(report.RecordQualityReportUnavailable):
        _context(results_loader=fail)


def test_manual_reader_failure_does_not_invent_zero():
    def fail(identities):
        raise RuntimeError("manual store unavailable")

    ctx = _context(manual_loader=fail)
    summary = report.summarize(ctx)
    assert summary["kpis"]["manual_defect_total"] is None
    assert summary["document_distribution"] is None


def test_unclassified_manual_rule_top_drills_into_same_case():
    ctx = _context(defect_source="manual", manual=[
        {"identity": ("a", "p1", "same"), "rule_code": "", "review_status": "approved"},
    ])
    top = report.summarize(ctx)["top_rules"][0]
    page = report.records_page(ctx, rule_id=top["rule_id"])
    assert top["defect_total"] == page["total"] == 1
    assert page["items"][0]["patient_id"] == "p1"
