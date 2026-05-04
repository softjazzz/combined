import importlib.util
import json
from pathlib import Path


def _load_seed_script_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "build_sheet2_verification_ledger_seed.py"
    spec = importlib.util.spec_from_file_location("build_sheet2_verification_ledger_seed", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _load_script_module(script_name: str):
    script_path = Path(__file__).resolve().parents[2] / "scripts" / script_name
    spec = importlib.util.spec_from_file_location(script_name.replace(".py", ""), script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_canonical_primary_rule_id_should_preserve_tail_issue_families():
    module = _load_seed_script_module()

    cases = [
        ("有创诊疗操作记录缺失/书写不规范", ["SC-045", "SC-046"], "患者行了骨髓穿刺，无有创操作记录", "SC-045"),
        ("有创诊疗操作记录缺失/书写不规范", ["SC-046", "SC-045"], "有创操作记录书写不规范", "SC-046"),
        ("转科记录缺失/书写不规范", ["SC-064"], "转入记录中未书写转入时间", "SC-064"),
        ("疑难病例讨论缺失/缺项", ["SC-056", "SC-057", "SC-058"], "入院超过3天未明确诊断", "SC-056"),
        ("输血记录链缺项", ["SC-074", "LX-018", "SC-073"], "输血后评价时间未书写", "SC-074"),
        ("围手术期术前评估/讨论/小结缺陷", ["SC-081", "SC-082", "SC-097"], "术前评估不充分", "SC-081"),
        ("既往史/用药史记录不全", ["SC-013", "SC-008"], "既往手术史未详细体现", "SC-013"),
        ("术前讨论结论/会诊意见未记入病历", ["SC-084", "SC-083", "SC-082"], "术前讨论无会诊科室意见", "SC-084"),
    ]

    for issue_family, candidate_rule_ids, manual_issue_text, expected_primary in cases:
        primary, secondary = module._canonical_primary_rule_id(
            issue_family=issue_family,
            candidate_rule_ids=candidate_rule_ids,
            manual_issue_text=manual_issue_text,
        )
        assert primary == expected_primary
        assert expected_primary not in secondary


def test_admission_reclassification_script_should_default_to_dry_run(tmp_path, monkeypatch):
    module = _load_script_module("run_admission_issue_family_reclassification.py")
    ledger = tmp_path / "ledger.csv"
    ledger.write_text(
        "sheet2_row_id,visit_id,patient_name,manual_issue_text,issue_family,primary_rule_id,secondary_rule_ids,evidence_summary\n"
        "Sheet2-R0001,V001,患者甲,体格检查缺体重,入院记录内容不完整/前后矛盾,SC-008,,原摘要\n",
        encoding="utf-8",
    )
    report_json = tmp_path / "report.json"
    report_csv = tmp_path / "report.csv"
    monkeypatch.setattr(module, "REPORT_JSON", report_json)
    monkeypatch.setattr(module, "REPORT_CSV", report_csv)
    monkeypatch.setattr(module, "build_admission_issue_family_bundle", lambda visit_id: {"visit_id": visit_id})
    monkeypatch.setattr(
        module,
        "_call_llm",
        lambda prompt, model: json.dumps(
            {
                "primary_rule_id": "SC-018",
                "recommended_rule_ids": ["SC-018"],
                "sub_items": [
                    {
                        "rule_id": "SC-018",
                        "item": "查体专科",
                        "status": "non_compliant",
                        "evidence": "体格检查缺体重",
                    }
                ],
                "overall_result": "hit",
                "qc_conclusion": "命中查体缺项",
                "confidence": 0.8,
            },
            ensure_ascii=False,
        ),
    )

    assert module.main(["--ledger", str(ledger)]) == 0

    assert "SC-008" in ledger.read_text(encoding="utf-8")
    report = json.loads(report_json.read_text(encoding="utf-8"))
    assert report["mode"] == "dry-run"
    assert report["row_count"] == 1
    assert report["results"][0]["primary_rule_id"] == "SC-018"


def test_admission_reclassification_script_writeback_requires_explicit_flag(tmp_path, monkeypatch):
    module = _load_script_module("run_admission_issue_family_reclassification.py")
    ledger = tmp_path / "ledger.csv"
    ledger.write_text(
        "sheet2_row_id,visit_id,patient_name,manual_issue_text,issue_family,primary_rule_id,secondary_rule_ids,evidence_summary\n"
        "Sheet2-R0001,V001,患者甲,体格检查缺体重,入院记录内容不完整/前后矛盾,SC-008,,原摘要\n",
        encoding="utf-8",
    )
    report_json = tmp_path / "report.json"
    report_csv = tmp_path / "report.csv"
    monkeypatch.setattr(module, "LEDGER_CSV", ledger)
    monkeypatch.setattr(module, "REPORT_JSON", report_json)
    monkeypatch.setattr(module, "REPORT_CSV", report_csv)
    monkeypatch.setattr(module, "build_admission_issue_family_bundle", lambda visit_id: {"visit_id": visit_id})
    monkeypatch.setattr(
        module,
        "_call_llm",
        lambda prompt, model: json.dumps(
            {
                "primary_rule_id": "SC-018",
                "recommended_rule_ids": ["SC-018"],
                "sub_items": [{"rule_id": "SC-018", "item": "查体专科", "status": "non_compliant"}],
                "overall_result": "hit",
                "qc_conclusion": "命中查体缺项",
                "confidence": 0.8,
            },
            ensure_ascii=False,
        ),
    )

    class _NoopModule:
        @staticmethod
        def main():
            return 0

    monkeypatch.setattr(module, "_load_script_module", lambda script_name: _NoopModule)

    assert module.main(["--ledger", str(ledger), "--writeback"]) == 0

    ledger_text = ledger.read_text(encoding="utf-8")
    assert "SC-018" in ledger_text
    assert "admission_reclassification_review_required" in ledger_text


def test_legacy_realign_admission_rule_ids_should_default_to_dry_run(tmp_path, monkeypatch):
    module = _load_script_module("realign_sheet2_admission_rule_ids.py")
    ledger = tmp_path / "ledger.csv"
    original = (
        "sheet2_row_id,visit_id,patient_name,manual_issue_text,issue_family,primary_rule_id,secondary_rule_ids\n"
        "Sheet2-R0001,V001,患者甲,体格检查缺体重,入院记录内容不完整/前后矛盾,SC-008,\n"
    )
    ledger.write_text(original, encoding="utf-8")
    report_json = tmp_path / "legacy_report.json"
    monkeypatch.setattr(module, "LEDGER_CSV", ledger)
    monkeypatch.setattr(module, "REPORT_JSON", report_json)

    assert module.main([]) == 0

    assert ledger.read_text(encoding="utf-8") == original
    report = json.loads(report_json.read_text(encoding="utf-8"))
    assert report["mode"] == "dry-run"


def test_apply_admission_manual_reviews_should_default_to_dry_run(tmp_path, monkeypatch):
    module = _load_script_module("apply_admission_issue_family_manual_reviews.py")
    ledger = tmp_path / "ledger.csv"
    ledger.write_text(
        "sheet2_row_id,visit_id,patient_name,manual_issue_text,issue_family,primary_rule_id,secondary_rule_ids,"
        "verification_status,job_id,evidence_status,evidence_summary,skip_reason,next_action\n"
        "Sheet2-R0103,V001,患者甲,主诉书写不完整,入院记录内容不完整/前后矛盾,SC-008,,same_family_hit,,,"
        "旧摘要,,旧动作\n",
        encoding="utf-8",
    )
    overrides = tmp_path / "overrides.csv"
    overrides.write_text(
        "sheet2_row_id,exact_review_status,exact_review_reason,blocked_reason_type,review_subgroup,decision_source\n"
        "Sheet2-R0103,blocked_with_reason,旧原因,证据链不足,旧分组,旧来源\n",
        encoding="utf-8",
    )
    review = tmp_path / "review.csv"
    review.write_text(
        "row_key,visit_id,patient_name,current_status,current_primary_rule,recommended_rules,manual_review_decision,"
        "final_primary_rule,final_secondary_rules,can_writeback,keep_exact_status,review_conclusion,next_action\n"
        "Sheet2-R0103,V001,患者甲,blocked_with_reason,SC-008,SC-008|SC-009,partial_writeback_keep_blocked,"
        "SC-008,SC-009,partial,blocked_with_reason,入院记录部分成立但查体冲突,保留 blocked\n",
        encoding="utf-8",
    )
    empty_review = tmp_path / "empty.csv"
    empty_review.write_text(
        "row_key,visit_id,patient_name,source_bucket,llm_overall_result,llm_primary_rule,manual_review_decision,"
        "final_primary_rule,final_secondary_rules,can_writeback,keep_exact_status,review_conclusion,next_action\n",
        encoding="utf-8",
    )
    report_json = tmp_path / "report.json"
    report_csv = tmp_path / "report.csv"
    monkeypatch.setattr(module, "LEDGER_CSV", ledger)
    monkeypatch.setattr(module, "OVERRIDE_CSV", overrides)
    monkeypatch.setattr(module, "MANUAL_REVIEW_CSV", review)
    monkeypatch.setattr(module, "BLOCKED_REVIEW_CSV", empty_review)
    monkeypatch.setattr(module, "REPORT_JSON", report_json)
    monkeypatch.setattr(module, "REPORT_CSV", report_csv)

    assert module.main([]) == 0

    assert "旧摘要" in ledger.read_text(encoding="utf-8")
    report = json.loads(report_json.read_text(encoding="utf-8"))
    assert report["mode"] == "dry-run"
    assert report["changed_row_count"] == 1
    assert report["changes"][0]["after"]["secondary_rule_ids"] == "SC-009"


def test_apply_admission_manual_reviews_writeback_keeps_partial_blocked(tmp_path, monkeypatch):
    module = _load_script_module("apply_admission_issue_family_manual_reviews.py")
    ledger = tmp_path / "ledger.csv"
    ledger.write_text(
        "sheet2_row_id,visit_id,patient_name,manual_issue_text,issue_family,primary_rule_id,secondary_rule_ids,"
        "verification_status,job_id,evidence_status,evidence_summary,skip_reason,next_action\n"
        "Sheet2-R0103,V001,患者甲,主诉书写不完整,入院记录内容不完整/前后矛盾,SC-008,,same_family_hit,,,"
        "旧摘要,,旧动作\n",
        encoding="utf-8",
    )
    overrides = tmp_path / "overrides.csv"
    overrides.write_text(
        "sheet2_row_id,exact_review_status,exact_review_reason,blocked_reason_type,review_subgroup,decision_source\n",
        encoding="utf-8",
    )
    review = tmp_path / "review.csv"
    review.write_text(
        "row_key,visit_id,patient_name,current_status,current_primary_rule,recommended_rules,manual_review_decision,"
        "final_primary_rule,final_secondary_rules,can_writeback,keep_exact_status,review_conclusion,next_action\n"
        "Sheet2-R0103,V001,患者甲,blocked_with_reason,SC-008,SC-008|SC-009,partial_writeback_keep_blocked,"
        "SC-008,SC-009,partial,blocked_with_reason,主诉成立但右手查体与原文冲突,保留 blocked\n",
        encoding="utf-8",
    )
    empty_review = tmp_path / "empty.csv"
    empty_review.write_text(
        "row_key,visit_id,patient_name,source_bucket,llm_overall_result,llm_primary_rule,manual_review_decision,"
        "final_primary_rule,final_secondary_rules,can_writeback,keep_exact_status,review_conclusion,next_action\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "LEDGER_CSV", ledger)
    monkeypatch.setattr(module, "OVERRIDE_CSV", overrides)
    monkeypatch.setattr(module, "MANUAL_REVIEW_CSV", review)
    monkeypatch.setattr(module, "BLOCKED_REVIEW_CSV", empty_review)
    monkeypatch.setattr(module, "REPORT_JSON", tmp_path / "report.json")
    monkeypatch.setattr(module, "REPORT_CSV", tmp_path / "report.csv")
    monkeypatch.setattr(module, "_refresh_outputs", lambda update_baseline: None)

    assert module.main(["--writeback"]) == 0

    ledger_text = ledger.read_text(encoding="utf-8")
    override_text = overrides.read_text(encoding="utf-8")
    assert "admission_part_only_keep_blocked" in ledger_text
    assert "SC-008,SC-009" in ledger_text
    assert "blocked_with_reason" in override_text
    assert "exact_confirmed" not in override_text


def test_admission_family_stats_should_bucket_non_writeback_rows(tmp_path, monkeypatch):
    module = _load_script_module("apply_admission_issue_family_manual_reviews.py")
    ledger = tmp_path / "ledger.csv"
    ledger.write_text(
        "sheet2_row_id,issue_family,admission_manual_review_bucket\n"
        "Sheet2-R0001,入院记录内容不完整/前后矛盾,admission_part_only_keep_blocked\n"
        "Sheet2-R0002,入院记录内容不完整/前后矛盾,\n"
        "Sheet2-R0003,入院记录内容不完整/前后矛盾,\n"
        "Sheet2-R0004,入院记录内容不完整/前后矛盾,\n",
        encoding="utf-8",
    )
    matrix = tmp_path / "sheet2_exact_review_matrix.csv"
    matrix.write_text(
        "sheet2_row_id,issue_family,exact_review_status\n"
        "Sheet2-R0001,入院记录内容不完整/前后矛盾,blocked_with_reason\n"
        "Sheet2-R0002,入院记录内容不完整/前后矛盾,blocked_with_reason\n"
        "Sheet2-R0003,入院记录内容不完整/前后矛盾,exact_confirmed\n"
        "Sheet2-R0004,入院记录内容不完整/前后矛盾,skip\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "LEDGER_CSV", ledger)
    monkeypatch.setattr(module, "QC_DIR", tmp_path)

    stats = module._family_stats()

    assert stats["total"] == 4
    assert stats["writeback_bucket_total"] == 4
    assert stats["writeback_bucket_unclassified_count"] == 0
    assert stats["writeback_bucket_breakdown"]["admission_part_only_keep_blocked"] == 1
    assert stats["writeback_bucket_breakdown"]["legacy_or_other_blocked"] == 1
    assert stats["writeback_bucket_breakdown"]["legacy_or_other_exact"] == 1
    assert stats["writeback_bucket_breakdown"]["skip"] == 1
