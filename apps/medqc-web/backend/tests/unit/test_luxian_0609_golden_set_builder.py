from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "build_luxian_0609_real_golden_set.py"
spec = importlib.util.spec_from_file_location("build_luxian_0609_real_golden_set", SCRIPT_PATH)
assert spec is not None
builder = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(builder)


def test_classify_rule_family_should_cover_required_luxian_groups():
    assert builder.classify_rule_family({"qc_point_id": "LX0609-001", "customer_text": "入院记录24小时"}) == "时限"
    assert builder.classify_rule_family({"qc_point_id": "LX0609-008", "customer_text": "病重患者查房"}) == "查房/病重病危"
    assert builder.classify_rule_family({"qc_point_id": "LX0609-012", "customer_text": "MRI阳性报告"}) == "检查检验"
    assert builder.classify_rule_family({"qc_point_id": "LX0609-021", "customer_text": "会诊目的"}) == "会诊"
    assert builder.classify_rule_family({"qc_point_id": "LX0609-032", "customer_text": "手术安全核查"}) == "手术麻醉"
    assert builder.classify_rule_family({"qc_point_id": "LX0609-043", "customer_text": "输血前检查"}) == "输血"
    assert builder.classify_rule_family({"qc_point_id": "LX0609-013", "customer_text": "病理提示胃癌"}) == "肿瘤病理/化疗"


def test_build_outputs_should_generate_annotation_and_comparison_framework(tmp_path):
    source = tmp_path / "review.csv"
    fieldnames = [
        "review_id",
        "qc_point_id",
        "customer_text",
        "accepted_case_type",
        "visit_id",
        "patient_name",
        "department",
        "manual_issue_text",
        "evidence_status",
        "priority_score",
        "priority_reasons",
        "document_inventory",
        "evidence_snippets",
    ]
    rows = [
        ("r1", "LX0609-001", "入院记录24小时", "positive", "V001", "甲", "内科"),
        ("r2", "LX0609-008", "病重患者查房", "positive", "V002", "乙", "ICU"),
        ("r3", "LX0609-012", "MRI阳性报告", "positive", "V003", "丙", "骨科"),
        ("r4", "LX0609-021", "会诊目的", "positive", "V004", "丁", "外科"),
        ("r5", "LX0609-032", "手术安全核查", "positive", "V005", "戊", "外科"),
        ("r6", "LX0609-043", "输血前检查", "positive", "V006", "己", "血液科"),
        ("r7", "LX0609-013", "病理提示胃癌", "positive", "V007", "庚", "肿瘤科"),
    ]
    with source.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for review_id, rule_id, text, case_type, visit_id, patient, department in rows:
            writer.writerow(
                {
                    "review_id": review_id,
                    "qc_point_id": rule_id,
                    "customer_text": text,
                    "accepted_case_type": case_type,
                    "visit_id": visit_id,
                    "patient_name": patient,
                    "department": department,
                    "manual_issue_text": text,
                    "evidence_status": "ready",
                    "priority_score": "100",
                    "priority_reasons": "unit-test",
                    "document_inventory": "文书清单",
                    "evidence_snippets": "短证据片段",
                }
            )

    payload = builder.build_outputs(source, tmp_path, target_size=7, coverage_path=tmp_path / "missing-coverage.json")

    assert payload["candidate_count"] == 7
    assert payload["accuracy_statement"] == "未完成人工标注前，不计算真实样本准确率。"
    assert {
        "时限",
        "查房/病重病危",
        "检查检验",
        "会诊",
        "手术麻醉",
        "输血",
        "肿瘤病理/化疗",
    }.issubset(set(payload["family_counts"]))

    annotation_csv = tmp_path / "泸县0609真实样本GoldenSet标注表.csv"
    comparison_csv = tmp_path / "泸县0609真实样本GoldenSet系统人工对比表.csv"
    candidate_json = tmp_path / "luxian_0609_real_golden_candidates.json"
    report = tmp_path / "泸县0609真实样本GoldenSet候选报告.md"
    assert annotation_csv.exists()
    assert comparison_csv.exists()
    assert candidate_json.exists()
    assert report.exists()

    annotation_rows = list(csv.DictReader(annotation_csv.open("r", encoding="utf-8")))
    assert annotation_rows[0]["system_status"] == "pending_system_run"
    assert annotation_rows[0]["human_status"] == "pending"
    assert annotation_rows[0]["is_match"] == "pending"
    assert annotation_rows[0]["evidence_ok"] == "pending"

    loaded = json.loads(candidate_json.read_text(encoding="utf-8"))
    assert loaded["rule_set_key"] == "luxian_0609_qc_v1"
    assert "不计算真实样本准确率" in loaded["accuracy_statement"]
    assert "不声明真实样本准确率" in report.read_text(encoding="utf-8")
