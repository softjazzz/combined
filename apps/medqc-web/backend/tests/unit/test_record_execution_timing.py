from app.services.qc_workspace.record_timing import summarize_record_timings


def row(key, start, end, kind="initial", completed=True):
    return {"record_key": key, "started_at": f"2026-09-29T00:00:{start:02d}+00:00",
            "finished_at": f"2026-09-29T00:00:{end:02d}+00:00",
            "execution_seconds": end-start, "attempt_kind": kind, "completed": completed}


def test_parallel_records_use_individual_duration_not_batch_throughput():
    result = summarize_record_timings([row("a", 0, 10), row("b", 0, 20)])
    assert result["average_complete_seconds"] == 15
    assert result["completed_timed_record_count"] == 2


def test_retry_preserves_initial_start_and_includes_wait():
    result = summarize_record_timings([row("a", 0, 10, completed=False), row("a", 20, 25, "retry")])
    assert result["average_complete_seconds"] == 25
    assert result["records"][0]["active_execution_seconds"] == 15
    assert result["records"][0]["initial_execution_seconds"] == 10


def test_failure_and_legacy_retry_do_not_claim_full_duration():
    result = summarize_record_timings([row("a", 0, 10, completed=False), row("b", 20, 25, "retry")])
    assert result["average_complete_seconds"] is None
    assert result["completed_timed_record_count"] == 0


def test_empty_timing_is_unknown_not_zero():
    assert summarize_record_timings([])["average_complete_seconds"] is None
