"""医嘱/专用记录协议的冻结替身；标签来自测试作者，不调用产品分类器。"""
from __future__ import annotations

import json

OPEN_TRANSFUSION_ORDER = {
    "order_id": "fixture-open-transfusion-order",
    "order_name": "输注去白悬浮红细胞2U",
    "order_status": "新开",
}


class FrozenTransfusionProtocolClient:
    def __init__(self, delegate=None, *, course_labels=None):
        self.delegate = delegate
        self.course_labels = dict(course_labels or {})
        self.protocol_calls = 0
        self.protocol_prompts = []

    async def generate(self, prompt):
        if "INPUT_JSON=" not in prompt:
            if self.delegate is None:
                raise RuntimeError("fixture semantic model unavailable")
            return await self.delegate.generate(prompt)
        payload = json.loads(prompt.split("INPUT_JSON=", 1)[1])
        self.protocol_calls += 1
        self.protocol_prompts.append(prompt)
        if set(payload) == {"orders"}:
            rows = payload["orders"]
            assert len({row["index"] for row in rows}) == len(rows)
            for row in rows:
                assert row["name"] == OPEN_TRANSFUSION_ORDER["order_name"]
                assert row["order_name"] == OPEN_TRANSFUSION_ORDER["order_name"]
                assert row["order_status"] == OPEN_TRANSFUSION_ORDER["order_status"]
            output = {
                "schema_version": "lx0609-transfusion-order-trigger-v1",
                "orders": [{"index": row["index"], "classification": "transfusion",
                            "cancelled": False, "quote": row["name"]} for row in rows],
            }
        else:
            assert set(payload) == {"records"}
            rows = payload["records"]
            assert len({row["index"] for row in rows}) == len(rows)
            for row in rows:
                assert row["content"] in self.course_labels, "未人工标注的病例正文"
            output = {
                "schema_version": "lx0609-transfusion-course-presence-v1",
                "records": [{"index": row["index"], "kind": self.course_labels[row["content"]],
                             "quote": row["content"]} for row in rows],
            }
        return {"content": json.dumps(output, ensure_ascii=False), "_api_time": 0.2,
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}
