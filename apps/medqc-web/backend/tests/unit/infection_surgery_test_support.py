"""旧时长保护的固定客户端适配；仅按真实新Prompt返回感染事实。"""
import json


def infection_fact_response(prompt, states, *, quote=None):
    body = json.loads(prompt.split("INPUT_JSON=", 1)[1])
    documents = []
    for index, doc in enumerate(body["documents"]):
        state = states(index, doc) if callable(states) else states[index]
        events = []
        if state == "present":
            text = doc["text"]
            named = [item for item in body["surgeries"] if any(part["name"] and part["name"] in text for part in item["components"])]
            linked = named[0] if len(named) == 1 else None
            events = [{"action": "infection_finding", "infection_quote": quote or text.split("：", 1)[-1][:8],
                "site": None, "occurred_at": {"value": None, "precision": "unknown", "quote": None},
                "recorded_at": doc["recorded_at"], "relations": [{"target_surgery_ref": target,
                    "relation": "unattributed" if linked is None else "this_surgery" if linked["surgery_ref"] == target else "other_surgery",
                    "related_surgery_ref": linked["surgery_ref"] if linked else None, "identity_quote": text if linked else None}
                    for target in body["target_surgery_refs"]]}]
        documents.append({"document_ref": doc["document_ref"], "state": state, "events": events})
    return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps({
        "schema_version": body["schema_version"], "documents": documents}, ensure_ascii=False)}}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}
