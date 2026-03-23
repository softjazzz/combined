import importlib.util
import json
from pathlib import Path


def _load_compare_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "compare_frontpage_input_modes.py"
    spec = importlib.util.spec_from_file_location("compare_frontpage_input_modes", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_load_dataset_filters_invalid_items(tmp_path):
    mod = _load_compare_module()
    dataset_path = tmp_path / "dataset.json"
    dataset_path.write_text(
        json.dumps(
            [
                {"case_id": "c1", "medical_text": "病历A", "expected": {"main_diagnosis_text": "A"}},
                {"case_id": "c2", "medical_text": "   "},
                "invalid",
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    rows = mod.load_dataset(dataset_path)
    assert isinstance(rows, list)
    assert len(rows) == 1
    assert rows[0]["case_id"] == "c1"


def test_build_mode_metrics_skip_unlabeled_missing_fields():
    mod = _load_compare_module()
    records = [
        {
            "case_id": "c1",
            "mode": "full",
            "elapsed_ms": 100.0,
            "expected": {
                "main_diagnosis_text": "冠心病",
                "missing_diagnoses": ["不稳定型心绞痛"],
                "missing_procedures": ["支架植入术"],
            },
            "pred_main_diagnosis": "冠状动脉粥样硬化性心脏病",
            "detected_missing_diagnoses": ["不稳定型心绞痛"],
            "detected_missing_procedures": [],
        },
        {
            "case_id": "c2",
            "mode": "full",
            "elapsed_ms": 220.0,
            "expected": {},
            "pred_main_diagnosis": "高血压",
            "detected_missing_diagnoses": [],
            "detected_missing_procedures": [],
        },
    ]

    metrics = mod.build_mode_metrics(records)
    assert metrics["case_count"] == 2
    assert metrics["main_labeled_count"] == 1
    assert metrics["diagnosis_missing_labeled_count"] == 1
    assert metrics["procedure_missing_labeled_count"] == 1
    assert metrics["diagnosis_missing_recall"] == 1.0
    assert metrics["procedure_missing_recall"] == 0.0
