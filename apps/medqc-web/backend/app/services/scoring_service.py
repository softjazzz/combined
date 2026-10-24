"""PR8报表只读消费子集，来源88e8f864b；不移植写入口与执行链。"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Iterable, Mapping, Sequence

_CENT = Decimal("0.01")


class ScoringScopeContextUnavailable(RuntimeError):
    """评分条目选择了范围，但病例缺少可信适用上下文。"""


def standard_needs_department(standard: Mapping[str, Any]) -> bool:
    return any(
        isinstance(item, Mapping)
        and item.get("enabled", True)
        and item.get("department_scope_mode", "all") == "selected"
        for item in standard.get("items") or []
    )


def item_applies_to_department(
    config: Mapping[str, Any],
    *,
    institute_id: str,
    department_name: str,
) -> bool:
    department_mode = config.get("department_scope_mode", "all")
    refs = config.get("department_refs", [])
    if not isinstance(refs, list):
        raise ScoringScopeContextUnavailable("评分科室范围不可用")
    if department_mode == "selected":
        if not institute_id or not department_name:
            raise ScoringScopeContextUnavailable("病例缺少可信科室上下文")
        normalized_refs = []
        for ref in refs:
            if (
                not isinstance(ref, Mapping)
                or not isinstance(ref.get("institute_id"), str)
                or not isinstance(ref.get("department_name"), str)
                or not ref["institute_id"].strip()
                or not ref["department_name"].strip()
            ):
                raise ScoringScopeContextUnavailable("评分科室范围不可用")
            normalized_refs.append(
                (ref["institute_id"].strip(), ref["department_name"].strip())
            )
        if not normalized_refs:
            raise ScoringScopeContextUnavailable("评分科室范围不可用")
        if (institute_id, department_name) not in set(normalized_refs):
            return False
    elif department_mode != "all":
        raise ScoringScopeContextUnavailable("评分科室范围不可用")
    elif refs:
        raise ScoringScopeContextUnavailable("全科室模式包含非法科室引用")
    return True


_in_scope = item_applies_to_department


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value)).quantize(_CENT)


def _float(value: Decimal) -> float:
    return float(value.quantize(_CENT))


def grade_for(score: Decimal, bands: Sequence[Mapping[str, Any]]) -> str | None:
    """按档位定级：区间左闭右开 [min, max)，最高档（第一档）右闭 [min, max]。"""
    for index, band in enumerate(bands):
        low = _decimal(band["min_score"])
        high = _decimal(band["max_score"])
        if low <= score < high or (index == 0 and score == high):
            return str(band["name"])
    return None


def score_result(
    items: Iterable[Mapping[str, Any]],
    standard: Mapping[str, Any],
    *,
    institute_id: str = "",
    department_name: str = "",
) -> dict[str, Any]:
    """纯函数计分。同一条目集合配同一标准，结果恒定（与条目顺序无关）。

    返回 {score, grade, veto_hit, deductions, group_deductions, unscored_rule_ids, base_score,
    standard_id, standard_updated_at}。扣分与未配置规则按 rule_id 去重。
    """
    item_list = list(items)
    configured = {
        str(item["rule_id"]).strip().upper(): item
        for item in standard.get("items") or []
    }
    groups = {str(group["group_name"]): group for group in standard.get("groups") or []}
    confirmed = sorted(
        {
            str(item.get("rule_id") or "").strip().upper()
            for item in item_list
            if isinstance(item, Mapping)
            and item.get("is_confirmed_issue") is True
            and str(item.get("rule_id") or "").strip()
        }
    )

    deductions: list[dict[str, Any]] = []
    unscored: list[str] = []
    raw_by_group: dict[str, Decimal] = {}
    veto_hit = False
    for rule_id in confirmed:
        config = configured.get(rule_id)
        if config is None:
            unscored.append(rule_id)
            continue
        if not config.get("enabled", True):
            continue
        if not _in_scope(
            config,
            institute_id=str(institute_id or "").strip(),
            department_name=str(department_name or "").strip(),
        ):
            continue
        amount = _decimal(config["deduction"])
        group_name = str(config["group_name"])
        is_veto = bool(config.get("is_veto"))
        veto_hit = veto_hit or is_veto
        raw_by_group[group_name] = raw_by_group.get(group_name, Decimal("0")) + amount
        deductions.append(
            {
                "rule_id": rule_id,
                "group_name": group_name,
                "deduction": _float(amount),
                "is_veto": is_veto,
            }
        )

    def group_order(name: str) -> tuple[int, str]:
        group = groups.get(name) or {}
        return (int(group.get("sort_order") or 0), name)

    group_deductions = []
    total = Decimal("0")
    for name in sorted(raw_by_group, key=group_order):
        raw = raw_by_group[name]
        cap = (groups.get(name) or {}).get("max_deduction")
        applied = raw if cap is None else min(raw, _decimal(cap))
        total += applied
        group_deductions.append(
            {
                "group_name": name,
                "raw_deduction": _float(raw),
                "applied_deduction": _float(applied),
                "max_deduction": None if cap is None else _float(_decimal(cap)),
            }
        )
    deductions.sort(key=lambda item: (group_order(item["group_name"]), item["rule_id"]))

    base = _decimal(standard["base_score"])
    score = max(Decimal("0"), base - total)
    grade = (
        standard["veto_grade"]
        if veto_hit
        else grade_for(score, standard.get("grade_bands") or [])
    )
    return {
        "score": _float(score),
        "grade": grade,
        "veto_hit": veto_hit,
        "base_score": _float(base),
        "deductions": deductions,
        "group_deductions": group_deductions,
        "unscored_rule_ids": unscored,
        "standard_id": standard.get("id"),
        "standard_updated_at": standard.get("updated_at"),
    }


def project_customer_items(
    raw_items: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """把 Canonical 原始条目投影为客户可见条目；is_confirmed_issue 的唯一 owner 为投影函数。"""
    from .custom_qc_workspace_service import project_customer_safe_result_item
    from .qc_workspace.canonical_result_store import customer_safe_projection_key

    hmac_key = customer_safe_projection_key()
    return [
        project_customer_safe_result_item(dict(item), hmac_key=hmac_key)
        for item in raw_items
    ]
