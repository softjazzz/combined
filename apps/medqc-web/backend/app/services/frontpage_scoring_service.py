"""本次完整首页形式质控的只读评分消费，不改变判定、通过率或历史保存。"""

from __future__ import annotations

from typing import Any, Callable, Mapping

from . import scoring_service, scoring_standard_service
from .frontpage_rule_catalog import (
    FRONTPAGE_RULE_IDS,
    FRONTPAGE_RULE_SET_KEY,
    FRONTPAGE_RULE_SET_VERSION,
)
from .frontpage_formal_qc import QCReport


def score_frontpage_report(
    report: QCReport, *, institute_id: str, department_name: str | None,
    rule_set_key: str, rule_set_version: str,
    standard_loader: Callable[[str], Mapping[str, Any] | None] | None = None,
) -> dict[str, Any]:
    """只消费当前执行器的完整布尔报告；调用方负责服务端身份与科室核实。"""
    state: dict[str, Any] = {
        "status": "unavailable", "score": None, "grade": None, "veto_hit": None,
        "standard_id": None, "standard_version_seq": None, "standard_updated_at": None,
        "rule_set_key": rule_set_key, "rule_set_version": rule_set_version,
        "reason_code": "standard_unavailable", "deductions": None,
        "group_deductions": None, "unscored_rule_ids": None,
    }
    try:
        standard = (standard_loader or scoring_standard_service.get_default_standard)("frontpage")
        if standard is None:
            return {**state, "status": "no_standard", "reason_code": "no_standard"}
        if (
            not isinstance(standard, Mapping) or standard.get("scene") != "frontpage"
            or standard.get("status") != "active" or standard.get("is_default") is not True
            or not isinstance(standard.get("id"), str) or not standard["id"].strip()
            or type(standard.get("version_seq")) is not int or standard["version_seq"] < 1
        ):
            return state
        state.update(
            standard_id=standard["id"], standard_version_seq=standard["version_seq"],
            standard_updated_at=standard.get("updated_at"),
        )
        if (
            rule_set_key != FRONTPAGE_RULE_SET_KEY
            or standard.get("rule_set_key") != FRONTPAGE_RULE_SET_KEY
            or rule_set_version != FRONTPAGE_RULE_SET_VERSION
        ):
            return {**state, "reason_code": "rule_set_mismatch"}
        state["reason_code"] = "result_unavailable"
        if not isinstance(report.results, list):
            return state
        ids = [item.rule_id for item in report.results]
        if (
            len(ids) != len(FRONTPAGE_RULE_IDS) or len(set(ids)) != len(ids)
            or set(ids) != set(FRONTPAGE_RULE_IDS)
            or any(type(item.passed) is not bool for item in report.results)
            or any(type(value) is not int for value in (report.total_rules, report.passed, report.failed))
            or report.total_rules != len(ids)
            or report.passed != sum(item.passed for item in report.results)
            or report.failed != sum(not item.passed for item in report.results)
        ):
            return state
        if not isinstance(institute_id, str) or not institute_id.strip():
            return {**state, "reason_code": "identity_unavailable"}
        if scoring_service.standard_needs_department(standard) and (
            not isinstance(department_name, str) or not department_name.strip()
        ):
            return {**state, "reason_code": "scope_unavailable"}
        # passed 是执行器唯一事实；此处仅适配既有计分 owner 的输入字段。
        items = [{"rule_id": item.rule_id, "is_confirmed_issue": not item.passed}
                 for item in report.results]
        state["reason_code"] = "score_unavailable"
        scored = scoring_service.score_result(
            items, standard, institute_id=institute_id.strip(),
            department_name=department_name.strip() if isinstance(department_name, str) else "",
        )
        return {
            **state, "status": "scored", "reason_code": None,
            **{key: scored[key] for key in (
                "score", "grade", "veto_hit", "deductions", "group_deductions", "unscored_rule_ids",
            )},
        }
    except Exception:  # noqa: BLE001 - 专用评分失效不得阻断既有形式判定和保存
        return state
