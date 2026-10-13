"""063 出院诊断同义判定的测试替身：按给定配对回答，默认剩余名称均无同一诊断。"""

from __future__ import annotations

import json

from app.services.luxian_0609.extended_document.discharge_diagnosis_equivalence import (
    SCHEMA_VERSION,
)


class DiagnosisEquivalenceClient:
    def __init__(self, same: dict[str, str] | None = None, uncertain: set[str] | None = None):
        # same: 权威名称 -> 书写名称；uncertain: 无法判断的权威名称。
        self.same = dict(same or {})
        self.uncertain = set(uncertain or ())
        self.calls = 0
        self.prompts: list[str] = []

    async def generate(self, prompt, **_kwargs):
        self.calls += 1
        self.prompts.append(prompt)
        payload = json.loads(prompt.split("\nINPUT_JSON=", 1)[1])
        written_ids = {item["name"]: item["id"] for item in payload["written"]}
        items = []
        for item in payload["authoritative"]:
            name = item["name"]
            if name in self.same and self.same[name] in written_ids:
                items.append({"id": item["id"], "match": written_ids[self.same[name]], "relation": "same"})
            elif name in self.uncertain:
                items.append({"id": item["id"], "match": None, "relation": "uncertain"})
            else:
                items.append({"id": item["id"], "match": None, "relation": "absent"})
        return {
            "content": json.dumps({"schema_version": SCHEMA_VERSION, "items": items}, ensure_ascii=False),
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
