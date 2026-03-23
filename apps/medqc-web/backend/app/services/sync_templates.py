"""
数据同步模板服务

用于将“复杂参数配置”收敛为少量可直接应用的模板。
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Optional

from ..services.etl_config import MongoSyncConfig

TemplateId = str

SYNC_TEMPLATE_CATALOG: list[dict[str, Any]] = [
    {
        "id": "hospital_standard",
        "name": "全院标准",
        "description": "全院稳定抽取，采用默认推荐参数。",
        "risk_tip": "适用于大多数上线场景，风险最低。",
        "requires_departments": False,
        "allow_multi_departments": False,
        "defaults": {
            "target_departments": ["*"],
            "discharge_stable_days": 3,
            "lookback_minutes": 10,
            "rescan_recent_days": 7,
            "tier1_interval_minutes": 30,
            "tier2_interval_minutes": 120,
            "tier3_cron": "0 2 * * *",
            "max_batch_size": 100,
            "inter_request_delay_ms": 200,
            "night_window_start": "22:00",
            "night_window_end": "06:00",
        },
    },
    {
        "id": "single_department_focus",
        "name": "单科精准",
        "description": "仅对单个科室进行抽取，快速灰度。",
        "risk_tip": "需选择 1 个科室；不支持 *。",
        "requires_departments": True,
        "allow_multi_departments": False,
        "defaults": {
            "discharge_stable_days": 3,
            "lookback_minutes": 10,
            "rescan_recent_days": 7,
            "tier1_interval_minutes": 30,
            "tier2_interval_minutes": 120,
            "tier3_cron": "0 2 * * *",
            "max_batch_size": 100,
            "inter_request_delay_ms": 200,
            "night_window_start": "22:00",
            "night_window_end": "06:00",
        },
    },
    {
        "id": "multi_department_joint",
        "name": "多科联合",
        "description": "按多个科室联合抽取，适合分批推进。",
        "risk_tip": "需选择多个科室；不支持 *。",
        "requires_departments": True,
        "allow_multi_departments": True,
        "defaults": {
            "discharge_stable_days": 3,
            "lookback_minutes": 10,
            "rescan_recent_days": 7,
            "tier1_interval_minutes": 30,
            "tier2_interval_minutes": 120,
            "tier3_cron": "0 2 * * *",
            "max_batch_size": 100,
            "inter_request_delay_ms": 200,
            "night_window_start": "22:00",
            "night_window_end": "06:00",
        },
    },
    {
        "id": "night_low_impact",
        "name": "夜间低干扰",
        "description": "降低白天负载，夜间窗口保守运行。",
        "risk_tip": "吞吐降低但更稳，适合生产高峰时段保护源端。",
        "requires_departments": False,
        "allow_multi_departments": True,
        "defaults": {
            "target_departments": ["*"],
            "tier1_interval_minutes": 60,
            "tier2_interval_minutes": 180,
            "max_batch_size": 50,
            "inter_request_delay_ms": 500,
            "tier3_cron": "0 2 * * *",
        },
    },
]


def _normalize_departments(departments: Optional[list[str]]) -> list[str]:
    if not departments:
        return []
    out: list[str] = []
    seen = set()
    for dep in departments:
        name = str(dep or "").strip()
        if not name or name in seen:
            continue
        out.append(name)
        seen.add(name)
    return out


def _find_template(template_id: TemplateId) -> dict[str, Any]:
    for item in SYNC_TEMPLATE_CATALOG:
        if item["id"] == template_id:
            return item
    raise ValueError(f"未知模板: {template_id}")


def list_sync_templates() -> list[dict[str, Any]]:
    return SYNC_TEMPLATE_CATALOG


def build_template_overrides(
    *,
    template_id: TemplateId,
    departments: Optional[list[str]],
    current_config: MongoSyncConfig,
) -> dict[str, Any]:
    template = _find_template(template_id)
    normalized = _normalize_departments(departments)

    if template["requires_departments"] and not normalized:
        raise ValueError("该模板必须选择科室")

    if "*" in normalized and len(normalized) > 1:
        raise ValueError("科室列表不允许同时包含 * 和具体科室")

    if template_id == "single_department_focus":
        if len(normalized) != 1:
            raise ValueError("单科模板必须且仅能选择 1 个科室")
        if normalized[0] == "*":
            raise ValueError("单科模板不允许使用 *")

    if template_id == "multi_department_joint":
        if not normalized:
            raise ValueError("多科模板至少选择 1 个科室")
        if "*" in normalized:
            raise ValueError("多科模板不允许使用 *")

    payload = asdict(current_config)
    for key, value in template["defaults"].items():
        payload[key] = value

    if template_id in {"single_department_focus", "multi_department_joint"}:
        payload["target_departments"] = normalized
    elif template_id == "night_low_impact":
        payload["target_departments"] = normalized if normalized else ["*"]

    return payload
