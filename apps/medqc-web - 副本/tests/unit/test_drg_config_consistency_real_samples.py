import json
from pathlib import Path

from backend.app.services.drg_config_store import DRGConfigStore


def test_consistency_check_requires_expected_group_and_reports_reasons(tmp_path: Path):
    store = DRGConfigStore(tmp_path / "drg_grouper_config_store.json")
    version = store.publish(operator="tester", change_summary="publish for consistency")

    report = store.run_consistency_check(
        samples=[
            {"case_key": "A-1", "actual_group": "DRG-A", "expected_group": "DRG-A"},
            {"case_key": "A-2", "predicted_group": "DRG-B", "expected_drg": "DRG-C"},
            {"case_key": "A-3", "hospital_group": "DIP-A", "expected_dip": "DIP-A"},
            {"case_key": "A-4", "hospital_group": "DIP-B"},
        ],
        operator="tester",
        version_id=version["version_id"],
    )

    assert report["summary"]["valid_count"] == 3
    assert report["summary"]["matched_count"] == 2
    assert report["summary"]["difference_count"] == 1
    assert report["summary"]["invalid_count"] == 1
    assert report["differences"][0]["case_key"] == "A-2"
    assert report["differences"][0]["expected_group"] == "DRG-C"
    assert report["differences"][0]["mismatch_reason"] == "院内模拟分组与预期医保分组不一致"
    assert report["invalid_samples"][0]["case_key"] == "A-4"
    assert report["invalid_samples"][0]["mismatch_reason"] == "缺少院内模拟分组或预期医保分组"


def test_consistency_check_acceptance_samples_reach_95_percent(tmp_path: Path):
    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "grouper_consistency_acceptance_samples.json"
    samples = json.loads(fixture.read_text(encoding="utf-8"))
    store = DRGConfigStore(tmp_path / "drg_grouper_config_store.json")
    version = store.publish(operator="tester", change_summary="publish for acceptance samples")

    report = store.run_consistency_check(
        samples=samples,
        operator="tester",
        version_id=version["version_id"],
    )

    assert report["summary"]["valid_count"] == 20
    assert report["summary"]["consistency_rate"] >= 95
    assert report["summary"]["difference_count"] == 0
    assert report["version_id"] == version["version_id"]
