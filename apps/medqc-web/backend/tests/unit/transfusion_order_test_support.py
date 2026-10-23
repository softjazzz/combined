"""医嘱/专用记录协议的冻结替身；标签来自测试作者，不调用产品分类器。"""
from __future__ import annotations

import json

OPEN_TRANSFUSION_ORDER = {
    "order_id": "fixture-open-transfusion-order",
    "order_name": "输注去白悬浮红细胞2U",
    "order_status": "新开",
}


class FrozenTransfusionProtocolClient:
    def __init__(self, delegate=None, *, course_labels=None, default_course_label=None,
                 intraoperative=None, performance_state=None, effect_labels=None):
        self.delegate = delegate
        self.course_labels = dict(course_labels or {})
        # 仅供正文全部由测试作者写成同一类记录的用例使用，避免逐句重复标注。
        self.default_course_label = default_course_label
        # 048 术中原子事实协议的人工标注替身（FrozenIntraoperativeClient）。
        self.intraoperative = intraoperative
        # 实施事实抽取协议的人工标注：整份正文作为引用、不给开始时刻；未提供时视为替身不可用。
        self.performance_state = performance_state
        # 047 输血效果评价抽取的人工标注：{正文片段: (state, quote)}，未命中的病程为 not_evaluated。
        self.effect_labels = dict(effect_labels or {})
        self.protocol_calls = 0
        self.protocol_prompts = []

    async def generate(self, prompt, **kwargs):
        if "INPUT_JSON=" not in prompt:
            if self.delegate is None:
                raise RuntimeError("fixture semantic model unavailable")
            return await self.delegate.generate(prompt)
        if "lx0609-intraoperative-transfusion-items-v1" in prompt:
            if self.intraoperative is None:
                raise RuntimeError("未提供 048 术中事实人工标注")
            self.protocol_calls += 1
            self.protocol_prompts.append(prompt)
            return await self.intraoperative.generate(prompt, **kwargs)
        payload = json.loads(prompt.split("INPUT_JSON=", 1)[1])
        self.protocol_calls += 1
        self.protocol_prompts.append(prompt)
        if set(payload) == {"items"}:
            from app.services.luxian_0609.posttransfusion_effect_extraction import SCHEMA_VERSION

            items = []
            for item in payload["items"]:
                state, quote = next(
                    (label for marker, label in self.effect_labels.items() if marker in item["content"]),
                    ("not_evaluated", ""),
                )
                items.append({"index": item["index"], "state": state, "quote": quote})
            output = {"schema_version": SCHEMA_VERSION, "items": items}
            return {"choices": [{"message": {"content": json.dumps(output, ensure_ascii=False)},
                                 "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}
        if set(payload) == {"documents"}:
            if self.performance_state is None:
                raise RuntimeError("未提供实施事实人工标注")
            from app.services.luxian_0609.extended_document.transfusion_performance_extraction import SCHEMA_VERSION

            output = {
                "schema_version": SCHEMA_VERSION,
                "documents": [{"document_ref": doc["document_ref"], "state": self.performance_state,
                               "quote": doc["body"], "start_time_quote": None}
                              for doc in payload["documents"]],
            }
            # 实施抽取按 choices 结构解析。
            return {"choices": [{"message": {"content": json.dumps(output, ensure_ascii=False)},
                                 "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}
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
                assert row["content"] in self.course_labels or self.default_course_label, (
                    "未人工标注的病例正文"
                )
            output = {
                "schema_version": "lx0609-transfusion-course-presence-v1",
                "records": [{"index": row["index"],
                             "kind": self.course_labels.get(row["content"], self.default_course_label),
                             "quote": row["content"]} for row in rows],
            }
        return {"content": json.dumps(output, ensure_ascii=False), "_api_time": 0.2,
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}
