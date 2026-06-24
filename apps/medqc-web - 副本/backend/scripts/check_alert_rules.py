from __future__ import annotations

import re
import sys
from pathlib import Path


def _repo_root() -> Path:
    # backend/scripts/check_alert_rules.py -> backend -> medqc-web -> apps -> repo_root
    return Path(__file__).resolve().parents[4]


def main() -> int:
    rules_path = _repo_root() / "scripts" / "medqc_prometheus_alert_rules.yml"
    if not rules_path.exists():
        print(f"[alert-rules] missing file: {rules_path}")
        return 1

    text = rules_path.read_text(encoding="utf-8")
    alert_names = set(re.findall(r"^\s*-\s*alert:\s*([A-Za-z0-9_]+)\s*$", text, flags=re.MULTILINE))
    required_alerts = {
        "MedQCBackendDown",
        "MedQCHigh5xxRate",
        "MedQCHighP95Latency",
        "MedQCSyncFailureRateHigh",
        "MedQCSyncLagHigh",
    }
    missing = sorted(required_alerts - alert_names)
    if missing:
        print(f"[alert-rules] missing required alerts: {', '.join(missing)}")
        return 1

    required_tokens = [
        "medqc_runtime_status_bucket_total",
        "medqc_runtime_requests_total",
        "medqc_runtime_request_latency_p95_ms",
        "medqc_sync_failure_rate",
        "medqc_sync_last_success_lag_seconds",
    ]
    missing_tokens = [token for token in required_tokens if token not in text]
    if missing_tokens:
        print(f"[alert-rules] missing metric tokens in expressions: {', '.join(missing_tokens)}")
        return 1

    has_for_duration = bool(re.search(r"^\s*for:\s+\d+[smhd]\s*$", text, flags=re.MULTILINE))
    if not has_for_duration:
        print("[alert-rules] no alert 'for:' duration found")
        return 1

    print(f"[alert-rules] PASS file={rules_path} alerts={len(alert_names)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
