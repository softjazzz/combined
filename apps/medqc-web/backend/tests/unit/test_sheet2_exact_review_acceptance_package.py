import importlib.util
from pathlib import Path


def _load_script_module(script_name: str):
    script_path = Path(__file__).resolve().parents[2] / "scripts" / script_name
    spec = importlib.util.spec_from_file_location(script_name.replace(".py", ""), script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_sheet2_exact_review_acceptance_package_should_bucket_blocked_rows():
    module = _load_script_module("build_sheet2_exact_review_acceptance_package.py")

    payload = module.build_acceptance_package()
    buckets = {
        item["category"]: item["count"]
        for item in payload["blocked_backlog_breakdown"]
    }

    assert payload["status_breakdown"]["needs_exact_review"] == 0
    assert payload["status_breakdown"]["exact_confirmed"] == 155
    assert payload["status_breakdown"]["blocked_with_reason"] == 103
    assert payload["status_breakdown"]["skip"] == 25
    assert buckets == {
        "可补规则": 12,
        "需补源文书": 34,
        "人工问题过宽/不可判": 48,
        "需客户确认口径": 9,
    }


def test_sheet2_exact_review_regression_guard_should_pass_current_baseline():
    module = _load_script_module("check_sheet2_exact_review_regression.py")

    result = module.evaluate_regression_guard()

    assert result["passed"] is True
    assert result["failures"] == []


def test_sheet2_exact_review_acceptance_api_should_point_to_generated_package():
    from app.routers import qc_sample_pools

    package_path = qc_sample_pools._SHEET2_EXACT_REVIEW_ACCEPTANCE_JSON

    assert package_path.exists()
    assert package_path.parts[-4:] == (
        "docs",
        "0418",
        "QC",
        "sheet2_exact_review_acceptance_package.json",
    )


def test_sheet2_evidence_gap_recheck_should_not_promote_bundle_coverage_to_exact():
    module = _load_script_module("run_sheet2_evidence_gap_backlog_recheck.py")
    audit_tables = {
        "first_course_record": {
            "local_total_rows": 1,
            "missing_visit_ids_in_local": [],
            "persistent_bundle_coverage": {"bundle_status": "covered"},
        }
    }

    result = module._evaluate_row(
        {
            "sheet2_row_id": "Sheet2-RTEST",
            "visit_id": "V1",
            "patient_name": "测试",
            "primary_rule_id": "SC-023",
            "issue_family": "首次病程诊断依据/鉴别诊断/诊疗计划缺陷",
            "backlog_category": "需补源文书",
            "blocked_reason_type": "证据链不足",
            "manual_issue_text": "首次病程记录中鉴别诊断不全面。",
        },
        audit_tables=audit_tables,
        use_verified_bundle_coverage=False,
    )

    assert result["coverage_status"] == "evidence_chain_recovered"
    assert result["target_exact_review_status"] == "blocked_with_reason"
    assert result["target_backlog_category"] == "可补规则"
