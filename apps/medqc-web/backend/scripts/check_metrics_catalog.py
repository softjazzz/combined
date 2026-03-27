from __future__ import annotations

import re
import sys
from pathlib import Path


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _extract_metric_names(text: str) -> set[str]:
    return set(re.findall(r"\b(medqc_[a-zA-Z0-9_]+)\b", text))


def _extract_metric_template_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if "medqc_" in line and "{" in line and "}" in line]


def _extract_label_names_from_metric_templates(text: str) -> set[str]:
    # Extract label keys from Prometheus template lines only, e.g.
    # f'medqc_xxx{{env="{env}",code_class="{bucket}"}} {value}'
    label_names: set[str] = set()
    for line in _extract_metric_template_lines(text):
        for key in re.findall(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*"\{', line):
            label_names.add(key)
    return label_names


def main() -> int:
    system_router = _backend_root() / "app" / "routers" / "system.py"
    if not system_router.exists():
        print(f"[metrics-catalog] missing file: {system_router}")
        return 1

    text = system_router.read_text(encoding="utf-8")
    metric_names = _extract_metric_names(text)

    required_metrics = {
        # QPS
        "medqc_runtime_requests_per_second_1m",
        # Latency
        "medqc_runtime_request_latency_p95_ms",
        # Error rate and 5xx
        "medqc_runtime_request_error_rate",
        "medqc_runtime_status_bucket_total",
        # Sync success/failure and lag/backlog proxy
        "medqc_sync_window_success_runs_total",
        "medqc_sync_window_failed_runs_total",
        "medqc_sync_failure_rate",
        "medqc_sync_last_success_lag_seconds",
        "medqc_sync_backlog_estimate",
    }
    missing_metrics = sorted(required_metrics - metric_names)
    if missing_metrics:
        print(f"[metrics-catalog] missing required metrics: {', '.join(missing_metrics)}")
        return 1

    # Guard against high-cardinality labels.
    label_names = _extract_label_names_from_metric_templates(text)
    allowed_labels = {"env", "code_class"}
    disallowed = sorted(label_names - allowed_labels)
    if disallowed:
        print(f"[metrics-catalog] disallowed metric labels detected: {', '.join(disallowed)}")
        return 1

    high_cardinality_hints = (
        "user_id=",
        "patient_id=",
        "trace_id=",
        "request_id=",
        "session_id=",
        "token=",
    )
    metric_template_blob = "\n".join(_extract_metric_template_lines(text))
    found_hints = [token for token in high_cardinality_hints if token in metric_template_blob]
    if found_hints:
        print(f"[metrics-catalog] high-cardinality label hint detected: {', '.join(found_hints)}")
        return 1

    print(
        "[metrics-catalog] PASS "
        f"file={system_router} required={len(required_metrics)} labels={','.join(sorted(label_names)) or '<none>'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
