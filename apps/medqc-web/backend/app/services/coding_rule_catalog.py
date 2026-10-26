"""编码质控点目录：稳定 ID、展示元数据与可执行范围的唯一 owner。"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .qc_rule_sets import QCRuleSet

CODING_RULE_SET_KEY = "coding_qc_v1"
CODING_RULE_SET_VERSION = "1.0"
CODING_RULE_IDS = tuple(f"CR-{index:03d}" for index in range(1, 19))
CODING_PENDING_RULE_IDS = frozenset({"CR-011", "CR-018"})
CODING_EXECUTABLE_RULE_IDS = frozenset(CODING_RULE_IDS) - CODING_PENDING_RULE_IDS

CODING_RULE_SET = QCRuleSet(
    key=CODING_RULE_SET_KEY,
    name="编码质控点 v1",
    version=CODING_RULE_SET_VERSION,
    scope="coding",
    rule_ids=CODING_RULE_IDS,
    description="编码质控18项稳定目录；未具备真实判据的规则保持暂停。",
)


@lru_cache(maxsize=1)
def load_coding_rule_catalog() -> tuple[dict[str, Any], ...]:
    path = Path(__file__).resolve().parents[1] / "data" / "coding_rules.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise RuntimeError("编码质控点目录格式无效")
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            raise RuntimeError("编码质控点目录条目格式无效")
        rule_id = str(item.get("rule_id") or "").strip().upper()
        if rule_id not in CODING_RULE_IDS or rule_id in seen:
            raise RuntimeError("编码质控点目录ID无效或重复")
        name = str(item.get("name") or "").strip()
        category = str(item.get("category") or "").strip()
        category_name = str(item.get("category_name") or "").strip()
        if not name or not category or not category_name:
            raise RuntimeError(f"编码质控点目录元数据不完整：{rule_id}")
        seen.add(rule_id)
        executable = rule_id in CODING_EXECUTABLE_RULE_IDS
        rows.append(
            {
                **item,
                "rule_id": rule_id,
                "name": name,
                "category": category,
                "category_name": category_name,
                "executable": executable,
                "is_active": executable,
            }
        )
    if seen != set(CODING_RULE_IDS):
        raise RuntimeError("编码质控点目录必须完整覆盖CR-001至CR-018")
    return tuple(sorted(rows, key=lambda item: item["rule_id"]))


def coding_rule_metadata() -> dict[str, dict[str, str]]:
    return {
        item["rule_id"]: {
            "qc_point": item["name"],
            "category": item["category"],
            "category_name": item["category_name"],
        }
        for item in load_coding_rule_catalog()
    }


def get_coding_rule_set(rule_set_key: Any) -> QCRuleSet | None:
    return (
        CODING_RULE_SET
        if str(rule_set_key or "").strip().lower() == CODING_RULE_SET_KEY
        else None
    )
