"""048 术中输血原子事实协议的冻结替身；每份正文的事实由测试作者人工标注。"""
from __future__ import annotations

import json

SCHEMA_VERSION = "lx0609-intraoperative-transfusion-items-v1"


def item(quote, component, dose=None, event_time=None):
    return {"quote": quote, "component": component, "dose": dose, "event_time": event_time}


ABSENT = ("absent", ())
UNKNOWN = ("unknown", ())


def present(*items):
    return ("present", tuple(items))


class FrozenIntraoperativeClient:
    """按正文查人工标注返回协议 JSON；未标注正文直接报错，避免替身代替判断。"""

    def __init__(self, annotations, *, raw_documents=None):
        self.annotations = dict(annotations)
        # 可直接给出某份正文的原始 documents 项，用于构造非法模型输出。
        self.raw_documents = dict(raw_documents or {})
        self.calls = []

    async def generate(self, prompt, **kwargs):
        self.calls.append(kwargs)
        assert f"schema_version={SCHEMA_VERSION}" in prompt
        documents = json.loads(prompt.split("INPUT_JSON=", 1)[1])["documents"]
        output = []
        for doc in documents:
            body = doc["body"]
            if body in self.raw_documents:
                output.append({"document_ref": doc["document_ref"], **self.raw_documents[body]})
                continue
            assert body in self.annotations, "未人工标注的术中文书正文：" + body
            state, items = self.annotations[body]
            output.append({"document_ref": doc["document_ref"], "state": state, "items": list(items)})
        content = json.dumps({"schema_version": SCHEMA_VERSION, "documents": output}, ensure_ascii=False)
        return {"choices": [{"finish_reason": "stop", "message": {"content": content}}],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                "_api_time": 0.1}
