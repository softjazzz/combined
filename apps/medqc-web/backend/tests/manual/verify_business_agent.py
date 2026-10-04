"""真实模型＋合成业务 DTO 联调，必须显式传入 --run-real-model。"""
import argparse
import json
from pathlib import Path
from uuid import uuid4

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-real-model", action="store_true")
    args = parser.parse_args()
    if not args.run_real_model:
        parser.error("真实模型验证会产生模型调用，请显式指定 --run-real-model")
    results = []
    with httpx.Client(base_url="http://127.0.0.1:8003", headers={"Authorization": "Bearer synthetic-business-agent"}, timeout=75, trust_env=False) as client:
        scenarios = [
            ({"view": "doctor", "institute_id": "SYNTHETIC", "patient_id": "A", "visit_id": "A1", "patient_name": "合成病例A"}, ["这份病历有哪些已保存的质控问题？按返回顺序列出。", "第二条为什么不合规？请读取保存证据并给出来源。", "这条规则的要求来自哪里？有规范原文吗？"]),
            ({"view": "manager", "institute_id": "SYNTHETIC", "department": "合成科室", "care_phase": "discharged", "completed_from": "2026-09-01T00:00:00+08:00", "completed_to": "2026-09-30T23:59:59+08:00"}, ["当前范围哪些质控问题最多？给出原统计值并列出病例。", "读取刚才第一个病例的保存质控问题。"]),
        ]
        for context, questions in scenarios:
            response = client.post("/api/v1/qc-agent/business/sessions", json={"context": context})
            response.raise_for_status()
            session_id = response.json()["session_id"]
            for question in questions:
                response = client.post(f"/api/v1/qc-agent/business/sessions/{session_id}/chat", json={"run_id": str(uuid4()), "message": question})
                response.raise_for_status()
                turn = response.json()
                results.append({"context": context, "session_id": session_id, "turn": turn})
                print(json.dumps({"view": context["view"], "question": question, "status": turn["status"], "tool_calls": turn["tool_calls"], "model_calls": turn.get("model_calls"), "usage": turn.get("usage"), "elapsed_ms": turn["elapsed_ms"], "references": len(turn["references"])}, ensure_ascii=False), flush=True)
            restored = client.get(f"/api/v1/qc-agent/business/sessions/{session_id}")
            restored.raise_for_status()
            assert len(restored.json()["turns"]) == len(questions)
    target = Path(__file__).resolve().parents[3] / ".tmp/0910-full-audit/business-agent-validation-private/real-model-results.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assert all(row["turn"]["status"] == "completed" for row in results), "真实模型验证有未完成轮次，详见隔离目录中的结果"


if __name__ == "__main__":
    main()
