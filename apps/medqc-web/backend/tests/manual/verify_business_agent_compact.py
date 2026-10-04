"""同五轮真实重放；持久化10轮上限，患者产物仅写private目录。"""
import argparse
import json
from pathlib import Path
from uuid import uuid4

import httpx


PRIVATE = Path(__file__).resolve().parents[3] / ".tmp/0910-full-audit/business-agent-validation-private"


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def check_cards(client, row):
    context, turn = row["context"], row["turn"]
    metadata = json.loads((PRIVATE / "real-metadata" / f"{row['session_id']}.json").read_text(encoding="utf-8"))
    checked = []
    sources = {}
    for ref in turn["references"]:
        if ref["kind"] != "saved_result":
            continue
        binding = metadata["references"][ref["id"]]
        identity = binding["identity"]
        key = json.dumps(identity, sort_keys=True)
        if key not in sources:
            response = client.get(f"/api/v1/qc-agent/business/records/{identity['visit_id']}/latest-result", params={**identity, "view": context["view"], "department": context.get("department", "")})
            response.raise_for_status()
            sources[key] = response.json()["data"]
        source = sources[key]
        item = next(item for item in source["items"] if item["rule_id"] == ref["rule_id"])
        fields = {field: ref.get(field, "") == item.get(field, "") for field in ("status", "conclusion", "suggestion")}
        version = source["job_id"] == binding["job_id"] and source["record_ref"] == binding["record_ref"]
        checked.append({"reference_id": ref["id"], "rule_id": ref["rule_id"], "version_matches": version, "formal_fields_match": fields,
                        "answer_has_conclusion": item.get("conclusion", "") in turn["answer"], "answer_has_suggestion": item.get("suggestion", "") in turn["answer"]})
    return checked


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-real-model", action="store_true")
    args = parser.parse_args()
    if not args.run_real_model:
        parser.error("必须显式选择真实模型；本轮最多10轮")
    baseline = json.loads((PRIVATE / "clinical-model-private.json").read_text(encoding="utf-8"))
    login = json.loads((PRIVATE / "admin-read-private.json").read_text(encoding="utf-8"))
    budget_path = PRIVATE / "compact-real-budget-private.json"
    budget = json.loads(budget_path.read_text(encoding="utf-8")) if budget_path.exists() else {"spent": 0, "limit": 10}
    output_path = PRIVATE / "compact-model-private.json"
    results = json.loads(output_path.read_text(encoding="utf-8")) if output_path.exists() else []
    sessions = {}
    with httpx.Client(base_url="http://127.0.0.1:8003", headers={"Authorization": "Bearer " + login["token"]}, timeout=75, trust_env=False) as client:
        health = client.get("/readonly-health")
        health.raise_for_status()
        assert health.json()["database_readonly"] is True
        for index, previous in enumerate(baseline):
            if budget["spent"] >= budget["limit"]:
                raise RuntimeError("本轮真实模型10轮上限已用尽")
            original_id = previous["session_id"]
            if original_id not in sessions:
                response = client.post("/api/v1/qc-agent/business/sessions", json={"context": previous["context"]})
                response.raise_for_status()
                sessions[original_id] = response.json()["session_id"]
            sid = sessions[original_id]
            budget["spent"] += 1
            write(budget_path, budget)
            response = client.post(f"/api/v1/qc-agent/business/sessions/{sid}/chat", json={"run_id": str(uuid4()), "message": previous["turn"]["question"]})
            response.raise_for_status()
            row = {"baseline_index": index, "context": previous["context"], "session_id": sid, "turn": response.json()}
            results.append(row)
            write(output_path, results)
            row["card_checks"] = check_cards(client, row)
            restored = client.get(f"/api/v1/qc-agent/business/sessions/{sid}")
            restored.raise_for_status()
            row["restore_matches"] = restored.json()["turns"][-1] == row["turn"]
            write(output_path, results)
            turn = row["turn"]
            print(json.dumps({"baseline_index": index, "status": turn["status"], "model_calls": turn.get("model_calls"), "tool_calls": turn["tool_calls"], "usage": turn.get("usage"), "elapsed_ms": turn["elapsed_ms"], "references": len(turn["references"]), "formal_cards_match": all(check["version_matches"] and all(check["formal_fields_match"].values()) for check in row["card_checks"]), "restore_matches": row["restore_matches"]}), flush=True)


if __name__ == "__main__":
    main()
