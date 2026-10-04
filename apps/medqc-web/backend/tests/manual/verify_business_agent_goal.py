"""M1目标级真实验证；旧账本保留，本目标包括失败/取消最多10回合。"""
import argparse
import json
from uuid import uuid4

import httpx

from verify_business_agent_compact import PRIVATE, check_cards, write


LEDGER = PRIVATE / "m1-goal-real-budget-private.json"
RESULTS = PRIVATE / "m1-goal-model-private.json"


def reserve(purpose, session_id=None, run_id=None):
    ledger = json.loads(LEDGER.read_text(encoding="utf-8")) if LEDGER.exists() else {
        "goal": "2026-10-01-business-agent-m1", "baseline": "07ff44c73", "limit": 10, "spent": 0, "attempts": [],
    }
    if ledger["spent"] >= 10 or ledger["limit"] != 10:
        raise RuntimeError("本目标真实回合预算已用尽或账本不符")
    ledger["spent"] += 1
    entry = {"number": ledger["spent"], "purpose": purpose, "session_id": session_id, "run_id": run_id}
    ledger["attempts"].append(entry)
    write(LEDGER, ledger)
    return entry


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-same-five", action="store_true")
    parser.add_argument("--reserve-browser-turn")
    args = parser.parse_args()
    if args.reserve_browser_turn:
        print(json.dumps(reserve(args.reserve_browser_turn)))
        return
    if not args.run_same_five:
        parser.error("显式选择原五问真实重放，或在浏览器发送前登记回合")
    previous = json.loads((PRIVATE / "clinical-model-private.json").read_text(encoding="utf-8"))
    login = json.loads((PRIVATE / "admin-read-private.json").read_text(encoding="utf-8"))
    rows = json.loads(RESULTS.read_text(encoding="utf-8")) if RESULTS.exists() else []
    if rows:
        raise RuntimeError("原五问已执行或部分执行，禁止整组自动重复；后续仅定向复验")
    sessions = {}
    with httpx.Client(base_url="http://127.0.0.1:8003", headers={"Authorization": "Bearer " + login["token"]}, timeout=75, trust_env=False) as client:
        health = client.get("/readonly-health")
        health.raise_for_status()
        assert health.json()["database_readonly"] is True
        for index, old in enumerate(previous):
            if old["session_id"] not in sessions:
                response = client.post("/api/v1/qc-agent/business/sessions", json={"context": old["context"]})
                response.raise_for_status()
                sessions[old["session_id"]] = response.json()["session_id"]
            sid, run_id = sessions[old["session_id"]], str(uuid4())
            entry = reserve(f"same-five-{index}", sid, run_id)
            row = {"attempt": entry["number"], "baseline_index": index, "context": old["context"], "session_id": sid, "run_id": run_id}
            rows.append(row)
            write(RESULTS, rows)
            try:
                response = client.post(f"/api/v1/qc-agent/business/sessions/{sid}/chat", json={"run_id": run_id, "message": old["turn"]["question"]})
                response.raise_for_status()
                row["turn"] = response.json()
                write(RESULTS, rows)
                row["card_checks"] = check_cards(client, row)
                restored = client.get(f"/api/v1/qc-agent/business/sessions/{sid}")
                restored.raise_for_status()
                row["restore_matches"] = restored.json()["turns"][-1] == row["turn"]
                turn = row["turn"]
                print(json.dumps({"attempt": entry["number"], "baseline_index": index, "status": turn["status"], "model_calls": turn.get("model_calls"), "tool_calls": turn["tool_calls"], "usage": turn.get("usage"), "elapsed_ms": turn["elapsed_ms"], "formal_cards_match": all(c["version_matches"] and all(c["formal_fields_match"].values()) for c in row["card_checks"]), "restore_matches": row["restore_matches"]}), flush=True)
            except httpx.HTTPError as exc:
                row["transport_error"] = type(exc).__name__
                print(json.dumps({"attempt": entry["number"], "transport_error": row["transport_error"]}), flush=True)
                raise
            finally:
                write(RESULTS, rows)


if __name__ == "__main__":
    main()
