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
    assert payload["status_breakdown"]["exact_confirmed"] == 139
    assert payload["status_breakdown"]["blocked_with_reason"] == 119
    assert payload["status_breakdown"]["skip"] == 25
    assert buckets == {
        "可补规则": 23,
        "需补源文书": 30,
        "人工问题过宽/不可判": 59,
        "需客户确认口径": 7,
    }


def test_sheet2_exact_review_regression_guard_should_pass_current_baseline():
    module = _load_script_module("check_sheet2_exact_review_regression.py")

    result = module.evaluate_regression_guard()

    assert result["passed"] is True
    assert result["failures"] == []
