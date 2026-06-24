#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import pathlib
import urllib.request
from typing import Dict, Any, List


def load_env(env_path: pathlib.Path) -> Dict[str, str]:
    env: Dict[str, str] = {}
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
    return env


def chat(endpoint: str, api_key: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url=endpoint.rstrip("/") + "/chat/completions",
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json; charset=utf-8",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    root = pathlib.Path(__file__).resolve().parents[1]
    env = load_env(root / ".env")
    endpoint = env.get("LLM_API_ENDPOINT", "")
    api_key = env.get("LLM_API_KEY", "")
    model = env.get("LLM_MODEL", "qwen3.5-35b-a3b")
    if not endpoint or not api_key:
        raise RuntimeError("Missing LLM_API_ENDPOINT or LLM_API_KEY in backend/.env")

    cases: List[Dict[str, str]] = [
        {
            "id": "C1",
            "case": "出院诊断：1. 冠状动脉粥样硬化性心脏病 2. 不稳定型心绞痛 3. 冠脉支架植入后状态。住院经过：因胸痛入院，行冠状动脉造影+支架植入术，术后抗血小板治疗。",
        },
        {
            "id": "C2",
            "case": "出院诊断：1. 社区获得性肺炎 2. 2型糖尿病。住院经过：入院即抗感染治疗，肺炎明显好转；糖尿病仅口服降糖药维持。",
        },
        {
            "id": "C3",
            "case": "出院诊断：1. 急性阑尾炎 2. 阑尾切除术后状态。住院经过：急诊手术阑尾切除，术后恢复出院。",
        },
        {
            "id": "C4",
            "case": "出院诊断：1. 脑梗死 2. 高血压3级。住院经过：以脑梗死治疗为主，控制血压为辅。",
        },
    ]

    out: List[Dict[str, Any]] = []
    for c in cases:
        user = f"""病例：
{c['case']}

任务：请基于《住院病案首页填写规范》判断“主要诊断”应选哪条，并给出规范性依据。
要求：
1) 必须给出“为什么这条是主要诊断、为什么其他条目不是主要诊断”；
2) 依据要体现首页规范口径（如：主要诊断与本次住院主要医疗资源消耗/主要治疗目标关系）；
3) 严格输出 JSON：
{{
  "main_diagnosis": "",
  "not_main_candidates": [""],
  "normative_basis": [""],
  "reasoning_steps": [""],
  "confidence": 0.0
}}
"""
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "你是病案编码与质控专家，回答必须贴合《住院病案首页填写规范》的判定口径。",
                },
                {"role": "user", "content": user},
            ],
            "temperature": 0,
            "max_tokens": 900,
            "stream": False,
            "enable_thinking": False,
        }

        try:
            resp = chat(endpoint, api_key, payload)
            content = (
                resp.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            out.append({"case_id": c["id"], "response": content})
        except Exception as e:  # noqa: BLE001
            out.append({"case_id": c["id"], "response": f"ERROR: {e}"})

    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

