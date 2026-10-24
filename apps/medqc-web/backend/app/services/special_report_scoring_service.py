"""特殊病历报表的只读评分消费；计分唯一owner仍为scoring_service.score_result。

调用方由权威读取器核验三坐标、source/run信封，提供最新ready结果、完整客户投影条目及可信科室。
本模块只核对来源合同、一次读取专用标准并搬运计分结果，不读写历史评分。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Mapping

from . import scoring_service
from .scoring_standard_service import get_special_report_default_standard

Identity = tuple[str, str, str]


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _reference(standard: Mapping[str, Any] | None) -> dict[str, Any]:
    return {
        "standard_id": standard.get("id") if standard else None,
        "standard_version_seq": standard.get("version_seq") if standard else None,
        "binding_version_seq": standard.get("binding_version_seq")
        if standard
        else None,
    }


def _unknown(reason: str, reference: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "report_score_status": "unknown",
        "report_score": None,
        "report_grade": None,
        "report_veto_hit": None,
        "report_veto_rule_ids": None,
        "report_deductions": None,
        "report_unscored_rule_ids": None,
        "reason_code": reason,
        **reference,
    }


def score_special_report_cases(
    results: Mapping[Identity, Mapping[str, Any]],
    *,
    standard_loader: Callable[[str], Mapping[str, Any] | None] | None = None,
) -> tuple[dict[Identity, dict[str, Any]], dict[str, Any]]:
    """同批结果固定一个专用标准版本，不套用终末执行默认。

    results值为{status,rule_set_key,rule_set_version,envelope_id,items,department_name}；
    items必须是已完成客户投影的完整列表（权威明确[]可计分，字段缺失不可当成空）。
    返回(每病例报表评分,专用标准概况)，历史score/grade字段完全不参与消费。
    """
    try:
        standard = (standard_loader or get_special_report_default_standard)("final")
        if standard is not None and (
            standard.get("scene") != "final"
            or standard.get("status") != "active"
            or standard.get("binding_purpose") != "special_report"
            or not _text(standard.get("id"))
            or not _text(standard.get("rule_set_key"))
            or type(standard.get("version_seq")) is not int
            or standard["version_seq"] < 1
            or type(standard.get("binding_version_seq")) is not int
            or standard["binding_version_seq"] < 1
        ):
            raise ValueError("专用标准引用不完整")
    except Exception:  # noqa: BLE001 - 标准来源故障只影响报表评分，不伪造通过
        reference = _reference(None)
        overview = {
            "purpose": "special_report",
            "execution_scene": "final",
            "status": "unavailable",
            "standard_name": None,
            "rule_set_key": None,
            "standard_updated_at": None,
            **reference,
        }
        return {
            key: _unknown("standard_unavailable", reference) for key in results
        }, overview

    reference = _reference(standard)
    updated_at = standard.get("updated_at") if standard else None
    overview = {
        "purpose": "special_report",
        "execution_scene": "final",
        "status": "configured" if standard else "no_standard",
        "standard_name": standard.get("name") if standard else None,
        "rule_set_key": standard.get("rule_set_key") if standard else None,
        "standard_updated_at": updated_at.isoformat()
        if isinstance(updated_at, datetime)
        else updated_at,
        **reference,
    }
    if standard is None:
        return {key: _unknown("no_standard", reference) for key in results}, overview

    states: dict[Identity, dict[str, Any]] = {}
    for identity, result in results.items():
        if (
            not isinstance(identity, tuple)
            or len(identity) != 3
            or any(not _text(value) for value in identity)
        ):
            states[identity] = _unknown("identity_unavailable", reference)
            continue
        if (
            not isinstance(result, Mapping)
            or result.get("status") != "ready"
            or not _text(result.get("envelope_id"))
            or not _text(result.get("rule_set_version"))
        ):
            states[identity] = _unknown("result_unavailable", reference)
            continue
        if _text(result.get("rule_set_key")) != standard["rule_set_key"]:
            states[identity] = _unknown("rule_set_mismatch", reference)
            continue
        items = result.get("items")
        if not isinstance(items, list) or any(
            not isinstance(item, Mapping)
            or not _text(item.get("rule_id"))
            or type(item.get("is_confirmed_issue")) is not bool
            for item in items
        ):
            states[identity] = _unknown("result_unavailable", reference)
            continue
        try:
            scored = scoring_service.score_result(
                items,
                standard,
                institute_id=identity[0].strip(),
                department_name=_text(result.get("department_name")),
            )
        except scoring_service.ScoringScopeContextUnavailable:
            states[identity] = _unknown("scope_unavailable", reference)
        except Exception:  # noqa: BLE001 - 单病例消费失败关闭，医学事实仍由原结果owner保留
            states[identity] = _unknown("score_unavailable", reference)
        else:
            states[identity] = {
                "report_score_status": "scored",
                "report_score": scored["score"],
                "report_grade": scored["grade"],
                "reason_code": None,
                **reference,
                "report_veto_hit": scored["veto_hit"],
                "report_deductions": scored["deductions"],
                "report_unscored_rule_ids": scored["unscored_rule_ids"],
                "report_veto_rule_ids": [
                    item["rule_id"] for item in scored["deductions"] if item["is_veto"]
                ],
            }
    return states, overview
