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
    assert builder.classify_rule_family({"qc_point_id": "LX0609-01-01-01", "customer_text": "入院记录24小时"}) == "时限"
    assert builder.classify_rule_family({"qc_point_id": "LX0609-02-01-04", "customer_text": "病重患者查房"}) == "查房/病重病危"
    assert builder.classify_rule_family({"qc_point_id": "LX0609-06-01-05", "customer_text": "MRI阳性报告"}) == "检查检验"
    assert builder.classify_rule_family({"qc_point_id": "LX0609-03-01-02", "customer_text": "会诊目的"}) == "会诊"
    assert builder.classify_rule_family({"qc_point_id": "LX0609-04-03-01", "customer_text": "手术安全核查"}) == "手术麻醉"
    assert builder.classify_rule_family({"qc_point_id": "LX0609-07-01-01", "customer_text": "输血前检查"}) == "输血"
    assert builder.classify_rule_family({"qc_point_id": "LX0609-06-02-03", "customer_text": "病理提示胃癌"}) == "肿瘤病理/化疗"


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
        ("r1", "LX0609-01-01-01", "入院记录24小时", "positive", "V001", "甲", "内科"),
        ("r2", "LX0609-02-01-04", "病重患者查房", "positive", "V002", "乙", "ICU"),
        ("r3", "LX0609-06-01-05", "MRI阳性报告", "positive", "V003", "丙", "骨科"),
        ("r4", "LX0609-03-01-02", "会诊目的", "positive", "V004", "丁", "外科"),
        ("r5", "LX0609-04-03-01", "手术安全核查", "positive", "V005", "戊", "外科"),
        ("r6", "LX0609-07-01-01", "输血前检查", "positive", "V006", "己", "血液科"),
        ("r7", "LX0609-06-02-03", "病理提示胃癌", "positive", "V007", "庚", "肿瘤科"),
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

    payload = builder.build_outputs(
        source,
        tmp_path,
        target_size=7,
        coverage_path=tmp_path / "missing-coverage.json",
        review_queue_path=tmp_path / "missing-review-queue.csv",
        rule_catalog_path=tmp_path / "missing-catalog.json",
    )

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
    assert annotation_rows[0]["candidate_status"] == "candidate"
    assert annotation_rows[0]["data_source"] == source.name
    assert annotation_rows[0]["pending_rule"] == annotation_rows[0]["qc_point_id"]

    loaded = json.loads(candidate_json.read_text(encoding="utf-8"))
    assert loaded["rule_set_key"] == "luxian_0609_qc_v1"
    assert all(item["coverage_status"] == "candidate_ready" for item in loaded["family_coverage"])
    assert "不计算真实样本准确率" in loaded["accuracy_statement"]
    assert "不声明真实样本准确率" in report.read_text(encoding="utf-8")


def test_build_outputs_should_mark_missing_required_family_as_sample_gap(tmp_path):
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
        ("r1", "LX0609-01-01-01", "入院记录24小时", "positive", "V001", "甲", "内科"),
        ("r2", "LX0609-02-01-04", "病重患者查房", "positive", "V002", "乙", "ICU"),
        ("r4", "LX0609-03-01-02", "会诊目的", "positive", "V004", "丁", "外科"),
        ("r5", "LX0609-04-03-01", "手术安全核查", "positive", "V005", "戊", "外科"),
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
    coverage = tmp_path / "coverage.json"
    coverage.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "qc_point_id": "LX0609-06-01-05",
                        "customer_text": "MRI阳性报告",
                        "candidate_coverage_status": "no_candidates",
                        "sample_visit_ids": [],
                        "sample_review_ids": [],
                        "next_action": "当前没有可复核候选，需先从样本池发现阳性、阴性和边界样本。",
                        "implementation_status": "needs_data_linkage",
                        "evidence_ready": 0,
                    },
                    {
                        "qc_point_id": "LX0609-07-01-01",
                        "customer_text": "输血前检查",
                        "candidate_coverage_status": "no_candidates",
                        "sample_visit_ids": [],
                        "sample_review_ids": [],
                        "next_action": "当前没有可复核候选，需先从样本池发现阳性、阴性和边界样本。",
                        "implementation_status": "needs_data_linkage",
                        "evidence_ready": 0,
                    },
                    {
                        "qc_point_id": "LX0609-06-02-03",
                        "customer_text": "病理提示胃癌",
                        "candidate_coverage_status": "no_candidates",
                        "sample_visit_ids": [],
                        "sample_review_ids": [],
                        "next_action": "当前没有可复核候选，需先从样本池发现阳性、阴性和边界样本。",
                        "implementation_status": "needs_cross_document",
                        "evidence_ready": 0,
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    catalog = tmp_path / "catalog.json"
    catalog.write_text(
        json.dumps(
            [
                {"qc_point_id": "LX0609-06-01-05", "customer_text": "MRI阳性报告", "gap": "样本池无影像阳性候选"},
                {"qc_point_id": "LX0609-07-01-01", "customer_text": "输血前检查", "gap": "样本池无输血候选"},
                {"qc_point_id": "LX0609-06-02-03", "customer_text": "病理提示胃癌", "gap": "样本池无病理肿瘤候选"},
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    payload = builder.build_outputs(
        source,
        tmp_path,
        target_size=7,
        coverage_path=coverage,
        review_queue_path=tmp_path / "missing-review-queue.csv",
        rule_catalog_path=catalog,
    )

    assert payload["candidate_count"] == 7
    assert payload["missing_family_gaps"] == ["检查检验", "输血", "肿瘤病理/化疗"]
    sample_gap_families = {
        item["rule_family"]
        for item in payload["candidates"]
        if item["candidate_status"] == "sample_gap"
    }
    assert sample_gap_families == {"检查检验", "输血", "肿瘤病理/化疗"}
    family_coverage = {item["rule_family"]: item for item in payload["family_coverage"]}
    assert family_coverage["检查检验"]["coverage_status"] == "sample_gap"
    assert family_coverage["检查检验"]["candidate_visit_ids"] == []
    assert "LX0609-06-01-05" in "、".join(family_coverage["检查检验"]["pending_rules"])

    annotation_rows = list(csv.DictReader((tmp_path / "泸县0609真实样本GoldenSet标注表.csv").open("r", encoding="utf-8")))
    gap_rows = [row for row in annotation_rows if row["candidate_status"] == "sample_gap"]
    assert len(gap_rows) == 3
    assert all(row["visit_id"] == "" for row in gap_rows)
    assert all(row["system_status"] == "sample_gap" for row in gap_rows)
    report_text = (tmp_path / "泸县0609真实样本GoldenSet候选报告.md").read_text(encoding="utf-8")
    assert "`sample_gap`" in report_text
    assert "样本池无输血候选" in report_text
