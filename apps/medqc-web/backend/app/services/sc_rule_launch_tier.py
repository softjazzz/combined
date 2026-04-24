from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ALLOWED_LAUNCH_TIERS: tuple[str, ...] = ("A", "B", "C")
DEFAULT_LAUNCH_TIER = "UNKNOWN"

_SERVICE_DIR = Path(__file__).resolve().parent
SC_RULES_JSON_PATH = _SERVICE_DIR.parent / "data" / "sichuan_rules_146.json"
SC_RULE_LAUNCH_TIER_PATH = _SERVICE_DIR.parent / "data" / "sc146_intrinsic_launch_tiers.json"


def _normalize_rule_id(rule_id: Any) -> str:
    return str(rule_id or "").strip().upper()


def list_sc_rule_ids_from_json_baseline(path: Path | None = None) -> list[str]:
    source_path = path or SC_RULES_JSON_PATH
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        return []
    rule_ids: list[str] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        rule_id = _normalize_rule_id(item.get("rule_id"))
        if rule_id.startswith("SC-"):
            rule_ids.append(rule_id)
    return sorted(rule_ids)


def load_sc_intrinsic_launch_tier_payload(path: Path | None = None) -> dict[str, Any]:
    source_path = path or SC_RULE_LAUNCH_TIER_PATH
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("sc146_intrinsic_launch_tiers.json 必须是对象结构")
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise ValueError("sc146_intrinsic_launch_tiers.json.entries 必须是数组")
    return payload


def list_sc_intrinsic_rule_ids_from_launch_tier_payload(path: Path | None = None) -> list[str]:
    payload = load_sc_intrinsic_launch_tier_payload(path)
    rule_ids: list[str] = []
    for item in payload.get("entries") or []:
        if not isinstance(item, dict):
            continue
        rule_id = _normalize_rule_id(item.get("rule_id"))
        if rule_id.startswith("SC-"):
            rule_ids.append(rule_id)
    return sorted(rule_ids)


def list_sc_intrinsic_rule_ids_by_launch_tier(
    launch_tier: Any,
    *,
    path: Path | None = None,
) -> tuple[str, ...]:
    normalized_tier = str(launch_tier or "").strip().upper()
    if normalized_tier not in ALLOWED_LAUNCH_TIERS:
        return ()
    payload = load_sc_intrinsic_launch_tier_payload(path)
    rule_ids: list[str] = []
    for item in payload.get("entries") or []:
        if not isinstance(item, dict):
            continue
        rule_id = _normalize_rule_id(item.get("rule_id"))
        item_tier = str(item.get("launch_tier") or "").strip().upper()
        if rule_id.startswith("SC-") and item_tier == normalized_tier:
            rule_ids.append(rule_id)
    return tuple(sorted(rule_ids))


def load_sc_intrinsic_launch_tier_map(path: Path | None = None) -> dict[str, str]:
    payload = load_sc_intrinsic_launch_tier_payload(path)
    mapping: dict[str, str] = {}
    for item in payload.get("entries") or []:
        if not isinstance(item, dict):
            continue
        rule_id = _normalize_rule_id(item.get("rule_id"))
        tier = str(item.get("launch_tier") or "").strip().upper()
        if not rule_id.startswith("SC-"):
            continue
        mapping[rule_id] = tier

    report = validate_sc_intrinsic_launch_tier_map(mapping)
    if not report["ok"]:
        raise ValueError(
            "SC intrinsic launch_tier 映射校验失败: "
            f"missing={len(report['missing_rule_ids'])} "
            f"invalid={len(report['invalid_tiers'])} "
            f"extra={len(report['extra_rule_ids'])}"
        )
    return mapping


def validate_sc_intrinsic_launch_tier_map(
    mapping: dict[str, str],
    *,
    expected_rule_ids: list[str] | None = None,
) -> dict[str, Any]:
    normalized_mapping = {
        _normalize_rule_id(rule_id): str(tier or "").strip().upper()
        for rule_id, tier in dict(mapping or {}).items()
        if _normalize_rule_id(rule_id).startswith("SC-")
    }
    expected_ids = sorted(expected_rule_ids or list_sc_intrinsic_rule_ids_from_launch_tier_payload())
    intrinsic_rule_ids = sorted(
        rule_id
        for rule_id, tier in normalized_mapping.items()
        if tier in ALLOWED_LAUNCH_TIERS
    )
    invalid_tiers = sorted(
        rule_id
        for rule_id, tier in normalized_mapping.items()
        if tier not in ALLOWED_LAUNCH_TIERS
    )
    missing_rule_ids = sorted(set(expected_ids) - set(normalized_mapping.keys()))
    extra_rule_ids = sorted(set(normalized_mapping.keys()) - set(expected_ids))
    return {
        "ok": not invalid_tiers and not missing_rule_ids and not extra_rule_ids,
        "expected_rule_count": len(expected_ids),
        "mapped_rule_count": len(normalized_mapping),
        "intrinsic_rule_count": len(intrinsic_rule_ids),
        "invalid_tiers": invalid_tiers,
        "missing_rule_ids": missing_rule_ids,
        "extra_rule_ids": extra_rule_ids,
    }


def resolve_sc_intrinsic_launch_tier(
    rule_id: Any,
    *,
    launch_tier_map: dict[str, str] | None = None,
) -> str:
    normalized = _normalize_rule_id(rule_id)
    if not normalized.startswith("SC-"):
        return DEFAULT_LAUNCH_TIER
    mapping = launch_tier_map or {}
    tier = str(mapping.get(normalized) or "").strip().upper()
    if tier in ALLOWED_LAUNCH_TIERS:
        return tier
    return DEFAULT_LAUNCH_TIER
