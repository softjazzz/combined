"""058 专家同意抽取的受控模型桩：只在原文分句明确同意/建议使用该药时给出逐字引文。"""

from __future__ import annotations

import json
import re

_APPROVAL = re.compile(r"同意|建议|予以|给予|加用|改用|使用")
_REFUSAL = re.compile(r"不同意|不建议|暂不|拒绝|未行|尚未|停用")
_GENERIC = re.compile(r"特殊级|特殊使用级|抗菌|抗感染|方案")
_OTHER_DRUG = re.compile(r"美罗培南|亚胺培南|万古霉素|利奈唑胺|替加环素|伏立康唑|卡泊芬净|头孢|西林|沙星")


class FrozenSpecialApprovalClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def generate(self, prompt, **kwargs):
        self.calls.append(prompt)
        payload = json.loads(prompt.rsplit("INPUT_JSON=", 1)[1])
        texts = {doc["doc_ref"]: doc["text"] for doc in payload["documents"]}
        single = len(payload["events"]) == 1
        events = []
        for event in payload["events"]:
            item = {"event_id": event["event_id"], "documented_use": "no", "quote_doc_refs": {}}
            for ref in event["doc_refs"]:
                # 模拟模型：点名该药的明确同意；仅一种特殊级药物时，未点任何药名的“同意特殊级方案”也归该药。
                clause = next((
                    part for part in re.split(r"[。；;\n]", texts[ref])
                    if (event["drug"] in part or (single and _GENERIC.search(part) and not _OTHER_DRUG.search(part)))
                    and _APPROVAL.search(part) and not _REFUSAL.search(part)
                ), None)
                if clause and clause.strip():
                    item.update(documented_use="yes", approval_quote=clause.strip())
                    item["quote_doc_refs"]["approval"] = ref
                    break
            if "approval_quote" not in item and not single and any(
                _GENERIC.search(part) and _APPROVAL.search(part) and not _OTHER_DRUG.search(part)
                and not _REFUSAL.search(part)
                for ref in event["doc_refs"] for part in re.split(r"[。；;\n]", texts[ref])
            ):
                # 模拟模型：多个特殊级药物时笼统同意无法归属。
                item["documented_use"] = "unknown"
            events.append(item)
        content = json.dumps({"schema_version": "lx0609_special_antimicrobial_approval_v1", "events": events},
                             ensure_ascii=False)
        return {"choices": [{"finish_reason": "stop", "message": {"content": content}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}
