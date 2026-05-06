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
    assert payload["status_breakdown"]["exact_confirmed"] == 152
    assert payload["status_breakdown"]["blocked_with_reason"] == 106
    assert payload["status_breakdown"]["skip"] == 25
    assert buckets == {
        "可补规则": 0,
        "需补源文书": 28,
        "人工问题过宽/不可判": 68,
        "需客户确认口径": 10,
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
