"""病历执行耗时观测；不参与质控判定或结果投影。"""
from datetime import datetime


def summarize_record_timings(attempts: list[dict]) -> dict:
    """首次执行到最终成功包含重试等待；单次耗时不含病历并发排队。"""
    grouped: dict[str, list[dict]] = {}
    for row in attempts:
        grouped.setdefault(row["record_key"], []).append(row)
    records = []
    for key, rows in grouped.items():
        first, last = rows[0], rows[-1]
        complete = first["attempt_kind"] == "initial" and last["completed"]
        elapsed = (
            datetime.fromisoformat(last["finished_at"]) - datetime.fromisoformat(first["started_at"])
        ).total_seconds() if complete else None
        records.append({
            "record_key": key,
            "attempt_count": len(rows),
            "initial_execution_seconds": first["execution_seconds"] if first["attempt_kind"] == "initial" else None,
            "active_execution_seconds": round(sum(r["execution_seconds"] for r in rows), 4),
            "complete_elapsed_seconds": round(max(0.0, elapsed), 4) if elapsed is not None else None,
        })
    durations = [r["complete_elapsed_seconds"] for r in records if r["complete_elapsed_seconds"] is not None]
    return {
        "schema_version": "record_execution_timing_v1",
        "basis": "evaluation_start_to_final_success_including_retry_wait",
        "attempts": attempts,
        "records": records,
        "measured_record_count": len(records),
        "completed_timed_record_count": len(durations),
        "average_complete_seconds": round(sum(durations) / len(durations), 4) if durations else None,
    }
