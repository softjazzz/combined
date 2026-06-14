from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


LUXIAN_0609_RULE_SET_KEY = "luxian_0609_qc_v1"
LUXIAN_0609_RULE_SET_NAME = "泸县0609质控点验证 v1"

_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "luxian_0609_rules_v1.json"


@lru_cache(maxsize=1)
def load_luxian_0609_rules() -> list[dict[str, Any]]:
    """Load the customer-facing Luxian 0609 rule wrappers.

    These are management-page view models. Actual execution still uses the
    mapped SC/LX/CL rule ids recorded on each wrapper.
    """
    with _DATA_PATH.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, list):
        raise ValueError("luxian_0609_rules_v1.json must contain a list")
    return [dict(item) for item in payload if isinstance(item, dict)]


def get_luxian_0609_rule(rule_id: str) -> dict[str, Any] | None:
    """Return a single Luxian 0609 wrapper rule by its customer-facing ID."""
    normalized_rule_id = str(rule_id or "").strip().upper()
    if not normalized_rule_id:
        return None
    for rule in load_luxian_0609_rules():
        candidate_id = str(rule.get("rule_id") or rule.get("rule_code") or "").strip().upper()
        if candidate_id == normalized_rule_id:
            return dict(rule)
    return None


def filter_luxian_0609_rules_by_documents(
    rules: list[dict[str, Any]],
    *,
    wanted_docs: set[str],
) -> list[dict[str, Any]]:
    if not wanted_docs:
        return list(rules)

    normalized_wanted = {str(item).strip() for item in wanted_docs if str(item).strip()}
    filtered: list[dict[str, Any]] = []
    for rule in rules:
        docs = {str(item).strip() for item in (rule.get("applicable_documents") or [])}
        doc_labels = {str(item).strip() for item in (rule.get("applicable_document_labels") or [])}
        if docs.intersection(normalized_wanted) or doc_labels.intersection(normalized_wanted):
            filtered.append(rule)
    return filtered
