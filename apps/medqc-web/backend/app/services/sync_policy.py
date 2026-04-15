"""
PG 同步策略服务。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .config_registry import get_config, set_config

_POLICY_NAMESPACE = "sync"
_POLICY_KEY = "policy"
_VALID_SCOPES = {"running", "final", "frontpage", "coding", "settlement", "both"}
_VALID_SCHEDULE_MODES = {"interval", "cron"}


def _default_policy() -> dict[str, Any]:
    return {
        "scope": "both",
        "target_departments": ["*"],
        "start_date": "",
        "end_date": "",
        "schedule": {
            "mode": "interval",
            "minutes": 30,
        },
        "night_window": {
            "start": "22:00",
            "end": "06:00",
        },
        "mirror_delay_base_minutes": 30,
        "policy_version": "policy-legacy-v1",
    }


def _now_policy_version() -> str:
    return f"policy-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"


def _is_hhmm(value: str) -> bool:
    if len(value) != 5 or value[2] != ":":
        return False
    hh, mm = value.split(":", 1)
    if not hh.isdigit() or not mm.isdigit():
        return False
    h = int(hh)
    m = int(mm)
    return 0 <= h <= 23 and 0 <= m <= 59


def _normalize_target_departments(values: Any) -> list[str]:
    if not isinstance(values, list):
        return ["*"]
    cleaned: list[str] = []
    seen: set[str] = set()
    wildcard_seen = False
    for item in values:
        dep = str(item or "").strip()
        if not dep:
            continue
        if dep == "*":
            wildcard_seen = True
            continue
        if dep in seen:
            continue
        cleaned.append(dep)
        seen.add(dep)
    if wildcard_seen and cleaned:
        return cleaned
    if wildcard_seen:
        return ["*"]
    return cleaned or ["*"]


def _normalize_policy(raw: dict[str, Any]) -> dict[str, Any]:
    merged = _default_policy()
    merged.update(raw or {})

    scope = str(merged.get("scope") or "both").strip().lower()
    if scope not in _VALID_SCOPES:
        raise ValueError(f"无效 scope: {scope}")
    merged["scope"] = scope

    start_date = str(merged.get("start_date") or "").strip()
    end_date = str(merged.get("end_date") or "").strip()
    if start_date and len(start_date) != 10:
        raise ValueError("start_date 格式必须为 YYYY-MM-DD")
    if end_date and len(end_date) != 10:
        raise ValueError("end_date 格式必须为 YYYY-MM-DD")
    if start_date and end_date and start_date > end_date:
        raise ValueError("start_date 不能晚于 end_date")
    merged["start_date"] = start_date
    merged["end_date"] = end_date

    schedule = merged.get("schedule")
    if not isinstance(schedule, dict):
        schedule = {}
    schedule_mode = str(schedule.get("mode") or "interval").strip().lower()
    if schedule_mode not in _VALID_SCHEDULE_MODES:
        raise ValueError(f"无效 schedule.mode: {schedule_mode}")
    schedule_minutes = int(schedule.get("minutes") or 30)
    if schedule_mode == "interval" and not (1 <= schedule_minutes <= 1440):
        raise ValueError("schedule.minutes 必须在 1~1440 之间")
    schedule["mode"] = schedule_mode
    schedule["minutes"] = schedule_minutes
    merged["schedule"] = schedule

    night_window = merged.get("night_window")
    if not isinstance(night_window, dict):
        night_window = {}
    night_start = str(night_window.get("start") or "22:00").strip()
    night_end = str(night_window.get("end") or "06:00").strip()
    if not _is_hhmm(night_start):
        raise ValueError("night_window.start 格式错误，应为 HH:MM")
    if not _is_hhmm(night_end):
        raise ValueError("night_window.end 格式错误，应为 HH:MM")
    night_window["start"] = night_start
    night_window["end"] = night_end
    merged["night_window"] = night_window

    mirror_delay_base_minutes = int(merged.get("mirror_delay_base_minutes") or 30)
    if not (0 <= mirror_delay_base_minutes <= 720):
        raise ValueError("mirror_delay_base_minutes 必须在 0~720 之间")
    merged["mirror_delay_base_minutes"] = mirror_delay_base_minutes

    merged["target_departments"] = _normalize_target_departments(merged.get("target_departments"))
    merged["policy_version"] = str(merged.get("policy_version") or "policy-legacy-v1").strip()
    return merged


def load_sync_policy() -> dict[str, Any]:
    raw = get_config(_POLICY_NAMESPACE, _POLICY_KEY)
    if not isinstance(raw, dict):
        return _default_policy()
    return _normalize_policy(raw)


def save_sync_policy(payload: dict[str, Any], keep_policy_version: bool = False) -> dict[str, Any]:
    current = load_sync_policy()
    merged = dict(current)
    merged.update(payload or {})
    normalized = _normalize_policy(merged)

    if keep_policy_version and str(current.get("policy_version") or "").strip():
        normalized["policy_version"] = str(current.get("policy_version") or "").strip()
    else:
        normalized["policy_version"] = _now_policy_version()

    ok = set_config(
        _POLICY_NAMESPACE,
        _POLICY_KEY,
        normalized,
        updated_by="system",
        source="sync_policy",
        change_reason="update sync policy",
    )
    if not ok:
        raise RuntimeError("写入 sync policy 失败")
    return normalized
