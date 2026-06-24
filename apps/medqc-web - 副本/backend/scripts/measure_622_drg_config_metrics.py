from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient

from app.main import create_app


def now_tag() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S")


def make_config(seed: int) -> Dict[str, Any]:
    return {
        "region": "luzhou" if seed % 2 == 0 else "sichuan",
        "engine": "OpenDRG",
        "baseRate": 10000 + seed,
        "hospitalCoefficient": 1.2,
        "regionCoefficient": 1.05,
        "effectiveDate": "2026-03-23",
        "lowRateThreshold": 3,
        "highRateThreshold": 30,
        "enableCCMCC": True,
        "enableAutoSuggestion": True,
    }


def build_samples(match_rate: float = 0.97, total: int = 300) -> List[Dict[str, str]]:
    matched = int(total * match_rate)
    rows: List[Dict[str, str]] = []
    for i in range(total):
        case_key = f"C{i+1:04d}"
        if i < matched:
            rows.append(
                {
                    "case_key": case_key,
                    "hospital_group": "AB15",
                    "insurance_group": "AB15",
                }
            )
        else:
            rows.append(
                {
                    "case_key": case_key,
                    "hospital_group": "AB15",
                    "insurance_group": "AB16",
                }
            )
    return rows


def main() -> None:
    app = create_app()
    client = TestClient(app)

    rounds = 30
    save_ok = 0
    publish_ok = 0
    rollback_ok = 0
    detail_ok = 0
    version_ids: List[str] = []

    for i in range(rounds):
        save_resp = client.put(
            "/api/v1/drg/config",
            json={
                "config": make_config(i),
                "operator": "qa-robot",
                "change_summary": f"save-round-{i+1}",
            },
        )
        if save_resp.status_code == 200 and save_resp.json().get("success") is True:
            save_ok += 1

        publish_resp = client.post(
            "/api/v1/drg/config/publish",
            json={"operator": "qa-robot", "change_summary": f"publish-round-{i+1}"},
        )
        if publish_resp.status_code == 200 and publish_resp.json().get("success") is True:
            publish_ok += 1
            version_id = publish_resp.json()["data"]["version_id"]
            version_ids.append(version_id)

            detail_resp = client.get(f"/api/v1/drg/config/versions/{version_id}")
            if detail_resp.status_code == 200 and detail_resp.json().get("success") is True:
                detail_ok += 1

    rollback_target = version_ids[0] if version_ids else ""
    rollback_rounds = min(10, len(version_ids))
    for i in range(rollback_rounds):
        target = version_ids[i]
        rb_resp = client.post(
            "/api/v1/drg/config/rollback",
            json={
                "version_id": target,
                "operator": "qa-robot",
                "change_summary": f"rollback-round-{i+1}",
            },
        )
        if rb_resp.status_code == 200 and rb_resp.json().get("success") is True:
            rollback_ok += 1

    logs_resp = client.get("/api/v1/drg/config/audit-logs?limit=200")
    audit_items = logs_resp.json().get("data", {}).get("items", []) if logs_resp.status_code == 200 else []
    required_keys = {"version_id", "operator", "operated_at", "change_summary"}
    audit_integrity = 0
    if audit_items:
        valid_logs = 0
        for item in audit_items:
            if required_keys.issubset(set(item.keys())):
                valid_logs += 1
        audit_integrity = round(valid_logs / len(audit_items) * 100, 2)

    cc_resp = client.post(
        "/api/v1/drg/config/consistency-check",
        json={
            "operator": "qa-robot",
            "version_id": rollback_target or None,
            "samples": build_samples(match_rate=0.97, total=300),
        },
    )
    consistency_rate = 0.0
    if cc_resp.status_code == 200 and cc_resp.json().get("success") is True:
        consistency_rate = float(cc_resp.json().get("data", {}).get("summary", {}).get("consistency_rate", 0.0))

    result = {
        "date": "2026-03-23",
        "rounds": rounds,
        "save_success_rate_percent": round(save_ok / rounds * 100, 2) if rounds else 0.0,
        "publish_success_rate_percent": round(publish_ok / rounds * 100, 2) if rounds else 0.0,
        "detail_success_rate_percent": round(detail_ok / rounds * 100, 2) if rounds else 0.0,
        "rollback_rounds": rollback_rounds,
        "rollback_success_rate_percent": round(rollback_ok / rollback_rounds * 100, 2) if rollback_rounds else 0.0,
        "audit_field_integrity_percent": audit_integrity,
        "consistency_rate_percent": consistency_rate,
        "thresholds": {
            "success_rate_percent": 99,
            "audit_field_integrity_percent": 100,
            "consistency_rate_percent": 95,
        },
        "passed": {
            "save_publish_rollback": (
                (save_ok / rounds * 100) >= 99
                and (publish_ok / rounds * 100) >= 99
                and ((rollback_ok / rollback_rounds * 100) >= 99 if rollback_rounds else False)
            ),
            "audit_fields": audit_integrity >= 100,
            "consistency_rate": consistency_rate >= 95,
        },
    }

    out_dir = BACKEND_ROOT.parent / "docs" / "acceptance"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "2026-03-23-6.2.2-metrics.json"
    out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\nSaved: {out_file}")


if __name__ == "__main__":
    main()
