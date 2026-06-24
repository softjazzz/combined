from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.services.sc_rule_family_ab import (
    build_ab_summary,
    build_review_queue,
    build_rule_level_diff,
    classify_scene_bundle_cohort,
    run_sc_rule_family_ab_experiment,
    select_manifest_entries,
    summarize_arm_round,
)


def test_classify_scene_bundle_cohort_should_route_running_and_final():
    assert (
        classify_scene_bundle_cohort(
            scene="running",
            document_hits={"surgery_record": True},
            source_doc_priority=[],
        )
        == "running_surgery"
    )
    assert (
        classify_scene_bundle_cohort(
            scene="running",
            document_hits={"consultation_record": True},
            source_doc_priority=[],
        )
        == "running_consult_or_discussion"
    )
    assert (
        classify_scene_bundle_cohort(
            scene="final",
            document_hits={"discharge_record": True},
            source_doc_priority=[],
        )
        == "final_terminal"
    )


def test_select_manifest_entries_should_fill_from_donor_cohort():
    candidates: list[dict[str, Any]] = []
    for index in range(1, 4):
        candidates.append(
            {
                "institute_id": "H1",
                "patient_id": f"P-A-{index}",
                "visit_id": f"V-A-{index}",
                "scene": "running",
                "cohort_tag": "running_admission_course",
                "document_hits": {"admission_record": True},
                "source_doc_priority": ["admission_record"],
                "bundle_updated_at": f"2026-04-17T10:00:0{index}Z",
            }
        )
    for index in range(1, 4):
        candidates.append(
            {
                "institute_id": "H1",
                "patient_id": f"P-C-{index}",
                "visit_id": f"V-C-{index}",
                "scene": "running",
                "cohort_tag": "running_consult_or_discussion",
                "document_hits": {"consultation_record": True},
                "source_doc_priority": ["consultation_record"],
                "bundle_updated_at": f"2026-04-17T11:00:0{index}Z",
            }
        )
    for index in range(1, 3):
        candidates.append(
            {
                "institute_id": "H1",
                "patient_id": f"P-S-{index}",
                "visit_id": f"V-S-{index}",
                "scene": "running",
                "cohort_tag": "running_surgery",
                "document_hits": {"surgery_record": True},
                "source_doc_priority": ["surgery_record"],
                "bundle_updated_at": f"2026-04-17T12:00:0{index}Z",
            }
        )
    for index in range(1, 3):
        candidates.append(
            {
                "institute_id": "H1",
                "patient_id": f"P-F-{index}",
                "visit_id": f"V-F-{index}",
                "scene": "final",
                "cohort_tag": "final_terminal",
                "document_hits": {"discharge_record": True},
                "source_doc_priority": ["discharge_record"],
                "bundle_updated_at": f"2026-04-17T13:00:0{index}Z",
            }
        )

    manifest = select_manifest_entries(candidates, cohort_size=2)

    assert len(manifest) == 8
    assert sum(1 for item in manifest if item["cohort_tag"] == "running_surgery") == 2
    assert sum(1 for item in manifest if item["cohort_tag"] == "final_terminal") == 2


def test_summarize_and_diff_should_compute_expected_metrics():
    manifest = [
        {
            "institute_id": "H1",
            "patient_id": "P1",
            "visit_id": "V1",
            "scene": "final",
            "cohort_tag": "final_terminal",
        }
    ]
    rule_ids = ["SC-001", "SC-002"]
    record_outputs = [
        {
            "manifest_entry": manifest[0],
            "result": {
                "evaluation_results": [
                    {
                        "rule_id": "SC-001",
                        "rule_name": "规则1",
                        "status": "non_compliant",
                        "is_compliant": False,
                        "findings": "发现问题",
                        "evidence": "证据A",
                        "suggestion": "建议A",
                        "confidence": 0.9,
                        "metadata": {
                            "execution_domain": "terminal",
                            "doc_scope": "primary",
                            "rule_family": "presence_required",
                            "bucket_strategy": "domain_only",
                            "bucket_key": "terminal::primary",
                            "pack_id": "p1",
                            "pack_size": 5,
                            "prompt_strategy": "batch_compact_v1",
                        },
                    },
                    {
                        "rule_id": "SC-002",
                        "rule_name": "规则2",
                        "status": "uncertain",
                        "is_compliant": False,
                        "findings": "待复核",
                        "evidence": "证据B",
                        "suggestion": "建议B",
                        "confidence": 0.3,
                        "metadata": {
                            "execution_domain": "terminal",
                            "doc_scope": "primary",
                            "rule_family": "timeliness",
                            "bucket_strategy": "domain_only",
                            "bucket_key": "terminal::primary",
                            "pack_id": "p1",
                            "pack_size": 5,
                            "prompt_strategy": "batch_compact_v1",
                        },
                    },
                ],
                "evidence_payload": {"primary_document_text": "主文书摘要"},
                "token_usage": {"total_tokens": 100},
                "api_time": 1.2,
                "_wall_clock_time": 2.4,
                "pack_metrics": {
                    "total_packs": 1,
                    "avg_pack_size": 5,
                    "fallback_packs": 0,
                    "single_rule_retries": 0,
                    "bucket_count": 1,
                    "pack_parse_error_count": 0,
                    "missing_rule_items": 0,
                    "selected_pack_size_by_bucket": {"terminal::primary": 5},
                },
            },
        }
    ]

    arm_a_summary = summarize_arm_round(
        manifest=manifest,
        rule_ids=rule_ids,
        record_outputs=record_outputs,
        round_index=1,
        arm_name="A",
        bucket_strategy="domain_only",
        sc_source="pg_governance",
        model_version="model-a",
    )
    arm_b_summary = summarize_arm_round(
        manifest=manifest,
        rule_ids=rule_ids,
        record_outputs=record_outputs,
        round_index=1,
        arm_name="B",
        bucket_strategy="domain_family",
        sc_source="pg_governance",
        model_version="model-a",
    )
    arm_b_rows = [dict(item) for item in arm_b_summary["observed_rows"]]
    arm_b_rows[1]["status"] = "compliant"
    arm_b_rows[1]["bucket_key"] = "terminal::primary::timeliness"

    diff_rows = build_rule_level_diff(
        arm_a_rows=arm_a_summary["observed_rows"],
        arm_b_rows=arm_b_rows,
    )
    review_queue = build_review_queue(diff_rows, limit=40)
    summary = build_ab_summary(
        manifest=manifest,
        rule_ids=rule_ids,
        arm_round_summaries={"A": [arm_a_summary], "B": [arm_b_summary]},
        diff_rows=diff_rows,
        sc_source="pg_governance",
        model_version="model-a",
    )

    assert arm_a_summary["rule_coverage"] == 100.0
    assert arm_a_summary["non_compliant_count"] == 1
    assert arm_a_summary["uncertain_count"] == 1
    assert arm_a_summary["low_confidence_rate"] == 50.0
    assert arm_a_summary["selected_pack_size_by_bucket"]["terminal::primary"] == [5]
    assert any(not bool(item["same_status"]) for item in diff_rows)
    assert len(review_queue) == 1
    assert review_queue[0]["review_verdict"] == ""
    assert summary["status_drift_rate"] == 50.0
    assert "timeliness" in summary["family_drift_rate"]


@pytest.mark.asyncio
async def test_run_sc_rule_family_ab_experiment_should_write_outputs(tmp_path: Path):
    manifest = [
        {
            "institute_id": "H1",
            "patient_id": "P1",
            "visit_id": "V1",
            "scene": "final",
            "cohort_tag": "final_terminal",
        }
    ]

    class _DummyClient:
        model = "stub-model"

    class _DummyService:
        def __init__(self) -> None:
            self.client = _DummyClient()

        def assert_sc_rule_source_ready(self, *, context: str, block_batch: bool) -> dict[str, Any]:
            assert context == "rule_family_ab_runner"
            assert block_batch is True
            return {"sc_source": "pg_governance"}

        def get_sc_rules_for_rule_family_poc(self) -> list[dict[str, Any]]:
            return [
                {"rule_id": "SC-001"},
                {"rule_id": "SC-002"},
            ]

    async def _fake_evaluator(
        *,
        service,
        manifest_entry,
        rule_ids,
        bucket_strategy,
        quality_profile,
        enable_selective_refine,
        refine_confidence_threshold,
        schema,
    ) -> dict[str, Any]:
        results = []
        for rule_id in rule_ids:
            status = "non_compliant" if bucket_strategy == "domain_family" and rule_id == "SC-002" else "compliant"
            results.append(
                {
                    "rule_id": rule_id,
                    "rule_name": f"规则-{rule_id}",
                    "status": status,
                    "is_compliant": status == "compliant",
                    "findings": f"{rule_id}-{status}",
                    "evidence": "证据",
                    "suggestion": "建议",
                    "confidence": 0.9,
                    "metadata": {
                        "execution_domain": "terminal",
                        "doc_scope": "primary",
                        "rule_family": "presence_required" if rule_id == "SC-001" else "timeliness",
                        "bucket_strategy": bucket_strategy,
                        "bucket_key": (
                            "terminal::primary"
                            if bucket_strategy == "domain_only"
                            else f"terminal::primary::{ 'presence_required' if rule_id == 'SC-001' else 'timeliness'}"
                        ),
                        "pack_id": f"{bucket_strategy}-pack",
                        "pack_size": 2 if bucket_strategy == "domain_family" else 5,
                        "prompt_strategy": "batch_compact_v1",
                        "quality_profile": quality_profile,
                        "refined": bool(enable_selective_refine and rule_id == "SC-002"),
                        "refine_reason": "low_confidence" if enable_selective_refine and rule_id == "SC-002" else "",
                        "final_decision_source": "single_refine" if enable_selective_refine and rule_id == "SC-002" else "batch",
                    },
                }
            )
        return {
            "evaluation_results": results,
            "evidence_payload": {"primary_document_text": "病历片段"},
            "token_usage": {"total_tokens": 80 if bucket_strategy == "domain_only" else 60},
            "api_time": 1.1 if bucket_strategy == "domain_only" else 0.8,
            "_wall_clock_time": 2.1 if bucket_strategy == "domain_only" else 1.6,
            "quality_profile": quality_profile,
            "refine_summary": {
                "enabled": enable_selective_refine,
                "candidate_count": 1 if enable_selective_refine else 0,
                "refined_rule_count": 1 if enable_selective_refine else 0,
                "refine_failed_count": 0,
                "refine_reasons": {"low_confidence": 1} if enable_selective_refine else {},
            },
            "pack_metrics": {
                "total_packs": 1,
                "avg_pack_size": 5 if bucket_strategy == "domain_only" else 2,
                "fallback_packs": 0,
                "single_rule_retries": 0,
                "bucket_count": 1 if bucket_strategy == "domain_only" else 2,
                "pack_parse_error_count": 0,
                "missing_rule_items": 0,
            },
        }

    result = await run_sc_rule_family_ab_experiment(
        manifest=manifest,
        schema="public",
        rounds=2,
        output_dir=tmp_path,
        service=_DummyService(),
        evaluator=_fake_evaluator,
    )

    assert result["manifest_size"] == 1
    assert result["rule_count"] == 2
    assert (tmp_path / "ab_summary.json").exists()
    assert (tmp_path / "ab_rule_level_diff.csv").exists()
    assert (tmp_path / "ab_review_queue.csv").exists()
    assert (tmp_path / "refine_detail.csv").exists()
    assert result["summary"]["arms"]["A"]["medians"]["rule_coverage"] == 100.0
    assert result["summary"]["arms"]["B"]["medians"]["bucket_count"] == 2.0
    assert result["summary"]["arms"]["C"]["medians"]["refined_rule_count"] == 1.0
    assert result["refine_detail_rows"]
