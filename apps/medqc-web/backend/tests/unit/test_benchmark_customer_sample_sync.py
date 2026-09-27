from scripts.benchmark_customer_sample_sync import (
    build_sync_payload,
    build_acceptance_template,
    evaluate_acceptance,
    extract_metrics,
    get_job_progress,
    validate_payload,
)


def test_acceptance_template_is_pending_and_complete():
    payload = build_acceptance_template()

    assert validate_payload(payload) == []
    assert payload["measurement_status"] == "待客户机实测"
    assert payload["acceptance"]["overall"] == "pending"
    assert set(payload["measurements"]) == {"8", "30", "100"}


def test_evaluate_acceptance_applies_planned_thresholds():
    payload = build_acceptance_template()
    for size in ("8", "30", "100"):
        payload["measurements"][size]["baseline_first"]["primary_visible_ms"] = 1000
        payload["measurements"][size]["optimized_first"]["primary_visible_ms"] = 300
        payload["measurements"][size]["baseline_first"]["total_duration_ms"] = 1000
        payload["measurements"][size]["optimized_first"]["total_duration_ms"] = 600
    payload["measurements"]["30"]["baseline_second_unchanged"]["total_duration_ms"] = 1000
    payload["measurements"]["30"]["optimized_second_unchanged"]["total_duration_ms"] = 300
    payload["measurements"]["30"]["optimized_second_unchanged"]["visits_refreshed"] = 0

    acceptance = evaluate_acceptance(payload)

    assert acceptance["overall"] == "pass"
    assert all(item["status"] == "pass" for item in acceptance["checks"])


def test_extract_metrics_reads_summary_without_sensitive_fields():
    metrics = extract_metrics(
        {
            "started_at": "2026-07-31T08:00:00+00:00",
            "retry_count": 1,
            "summary": {
                "primary_completed_at": "2026-07-31T08:00:01+00:00",
                "total_rows_pulled": 10,
                "total_rows_upserted": 3,
                "bundle_refresh": {"processed": 2},
                "sync_performance": {
                    "detail_sync_ms": 500,
                    "bundle_refresh_duration_ms": 100,
                    "total_duration_ms": 1600,
                    "tables_skipped_unchanged": 4,
                    "visits_refreshed": 1,
                    "retry_count": 2,
                },
                "synced_tables": [
                    {"sync_status": "skipped_unchanged"},
                    {"sync_status": "synced"},
                ],
                "patient_name": "不应进入指标",
            },
        }
    )

    assert metrics == {
        "source_resolve_ms": None,
        "primary_visible_ms": 1000.0,
        "detail_sync_ms": 500,
        "bundle_refresh_ms": 100,
        "total_duration_ms": 1600,
        "rows_pulled": 10,
        "rows_upserted": 3,
        "tables_skipped_unchanged": 4,
        "visits_refreshed": 1,
        "retry_count": 2,
    }


def test_sync_request_covers_entire_pool_and_progress_comes_from_summary():
    assert build_sync_payload(["sample_full_domain"]) == {
        "only_intrinsic": False,
        "include_in_batch_1": False,
        "table_groups": ["sample_full_domain"],
    }
    assert get_job_progress(
        {
            "progress": {"step_key": "wrong-location"},
            "summary": {
                "progress": {
                    "step_key": "primary_visible",
                    "primary_visible": True,
                }
            },
        }
    ) == {
        "step_key": "primary_visible",
        "primary_visible": True,
    }
