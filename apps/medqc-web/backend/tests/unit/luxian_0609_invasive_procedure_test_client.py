"""075 有创操作两步抽取的冻结测试客户端：按 schema_version 区分医嘱映射与记录核对。"""

from __future__ import annotations

import json
from typing import Any

from app.services.luxian_0609.extended_document.invasive_procedure_record import (
    MAPPING_SCHEMA_VERSION,
    RECORD_SCHEMA_VERSION,
)


class FrozenInvasiveProcedureClient:
    """mapping: 医嘱名称 -> 目录名称（None 表示不属于目录）。

    records: 目录名称 -> ("documented", 摘录) / "not_documented" / "uncertain"；
    documented 时取正文含该摘录的第一条记录。
    """

    def __init__(
        self,
        *,
        mapping: dict[str, str | None] | None = None,
        records: dict[str, Any] | None = None,
    ) -> None:
        self.mapping = mapping or {}
        self.records = records or {}
        self.prompts: list[str] = []

    async def generate(self, prompt: str, **_kwargs: Any) -> dict[str, Any]:
        self.prompts.append(prompt)
        payload = json.loads(prompt.split("INPUT_JSON=", 1)[1])
        if MAPPING_SCHEMA_VERSION in prompt:
            catalog_ids = {item["name"]: item["id"] for item in payload["catalog"]}
            matches = [
                {"id": order["id"], "catalog": catalog_ids[self.mapping[order["name"]]]}
                for order in payload["orders"]
                if self.mapping.get(order["name"])
            ]
            body = {"schema_version": MAPPING_SCHEMA_VERSION, "matches": matches}
        else:
            items = []
            for procedure in payload["procedures"]:
                decision = self.records.get(procedure["name"], "not_documented")
                if isinstance(decision, tuple):
                    quote = decision[1]
                    record = next(
                        (item["id"] for item in payload["records"] if quote in item["text"]),
                        "R99",
                    )
                    items.append({"id": procedure["id"], "state": "documented", "record": record, "quote": quote})
                else:
                    items.append({"id": procedure["id"], "state": decision, "record": None, "quote": None})
            body = {"schema_version": RECORD_SCHEMA_VERSION, "items": items}
        return {
            "choices": [{
                "finish_reason": "stop",
                "message": {"content": json.dumps(body, ensure_ascii=False)},
            }],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
        }
