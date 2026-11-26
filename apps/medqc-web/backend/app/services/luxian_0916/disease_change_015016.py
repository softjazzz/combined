"""LX0916-015/016 的结构化病情变化触发事实。

病危/病重医嘱和检验危急值是客户口径指定的触发来源。本模块只读取本次
住院三坐标下的原始结构化行，不复用 0609 的结论，也不让模型判断触发。
在没有已批准的事件--病程关联或评价时窗合同前，触发事件保留为可复核事实，
由规则层交付 ``data_quality_gap``，不能据此推断已到检查时点。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import text

from ...database import clinical_connection
from ...database.connection import engine
from ..clinical_read import clinical_table_sql


_RULE_IDS = ("LX0916-015", "LX0916-016")
_MAX_ROWS_PER_SOURCE = 200
_EFFECTIVE_ORDER_STATUSES = frozenset({"新开", "执行中", "停止"})
_EXCLUDED_ORDER_STATUSES = frozenset({"取消", "撤销", "作废"})
_VOID_MARKERS = ("取消", "撤销", "作废", "解除")
_CRITICAL_FLAGS = frozenset({"PL", "PH"})


def _order_query():
    nondrug_table = clinical_table_sql("inpat_nondrug_order")
    return text(
        f"""
        SELECT order_id, order_name, order_status, prescribed_datetime
        FROM {nondrug_table}
        WHERE institute_id = :institute_id
          AND patient_id = :patient_id
          AND visit_id = :visit_id
          AND (order_name LIKE :critical_name OR order_name LIKE :serious_name)
        ORDER BY prescribed_datetime ASC NULLS LAST,
                 order_id ASC
        LIMIT :limit_rows
        """
    )


def _lab_query():
    item_table = clinical_table_sql("labtest_item_report")
    master_table = clinical_table_sql("labtest_master")
    return text(
        f"""
        SELECT item.document_id AS item_document_id,
               item.test_id AS item_test_id,
               item.test_no AS item_test_no,
               item.item_id AS item_id,
               item.item_name AS item_name,
               item.result AS result,
               item.unit AS unit,
               item.abnormal_indicator AS abnormal_indicator,
               item.report_time AS item_report_time,
               master.test_id AS master_test_id,
               master.report_datetime AS master_report_datetime
        FROM {item_table} AS item
        LEFT JOIN {master_table} AS master
          ON master.institute_id = item.institute_id
         AND master.patient_id = item.patient_id
         AND master.visit_id = item.visit_id
         AND master.test_id = item.test_id
        WHERE item.institute_id = :institute_id
          AND item.patient_id = :patient_id
          AND item.visit_id = :visit_id
          AND UPPER(TRIM(COALESCE(item.abnormal_indicator, ''))) IN ('PL', 'PH')
        ORDER BY item.report_time ASC NULLS LAST,
                 master.report_datetime ASC NULLS LAST,
                 item.test_id ASC,
                 item.item_id ASC
        LIMIT :limit_rows
        """
    )


def load_disease_change_015016_facts(
    *, institute_id: str, patient_id: str, visit_id: str
) -> dict[str, Any]:
    """读取两类触发源；任何查询异常或截断均不把“无事件”当作事实。"""

    db_engine = clinical_connection.get_engine() if clinical_connection.configured() else engine
    if db_engine is None:
        return _source_gap("structured_trigger_source_unavailable")
    params = {
        "institute_id": institute_id,
        "patient_id": patient_id,
        "visit_id": visit_id,
        "critical_name": "%病危%",
        "serious_name": "%病重%",
        "limit_rows": _MAX_ROWS_PER_SOURCE + 1,
    }
    try:
        order_query = _order_query()
        lab_query = _lab_query()
        with db_engine.connect() as connection:
            order_rows = [
                dict(row)
                for row in connection.execute(order_query, params).mappings().all()
            ]
            lab_rows = [
                dict(row)
                for row in connection.execute(lab_query, params).mappings().all()
            ]
    except Exception:  # noqa: BLE001 - 只将来源故障映射为客户资料缺口。
        return _source_gap("structured_trigger_source_unavailable")
    return build_disease_change_015016_facts(order_rows=order_rows, lab_rows=lab_rows)


def build_disease_change_015016_facts(
    *, order_rows: Sequence[Mapping[str, Any]], lab_rows: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """把固定输入归一为 015/016 唯一的事件事实，可用于可重放单元测试。"""

    if len(order_rows) > _MAX_ROWS_PER_SOURCE or len(lab_rows) > _MAX_ROWS_PER_SOURCE:
        return _source_gap("structured_trigger_source_partial")

    issues: list[str] = []
    events: list[dict[str, Any]] = []
    for row in order_rows:
        event, issue = _severity_order_event(row)
        if issue:
            issues.append(issue)
        elif event:
            events.append(event)
    lab_events, lab_issues = _critical_lab_events(lab_rows)
    events.extend(lab_events)
    issues.extend(lab_issues)
    if issues:
        return _source_gap("structured_trigger_source_invalid", events=events)
    events.sort(
        key=lambda item: (str(item.get("event_time") or ""), str(item["event_id"]))
    )
    return {
        "event_facts": {"disease_changes": events},
        "event_source_state_by_rule": {
            rule_id: "structured_complete" for rule_id in _RULE_IDS
        },
        "diagnostic": {
            "code": "structured_disease_change_trigger_ready",
            "event_count": len(events),
            "llm_call_count": 0,
        },
    }


def merge_disease_change_015016_facts(
    *, context: Mapping[str, Any], structured_facts: Mapping[str, Any]
) -> dict[str, Any]:
    """在共享语义提取之后覆盖 015/016；旧模型 ``disease_changes`` 不可回流。"""

    merged = dict(context)
    event_facts = dict(_mapping(context.get("event_facts")))
    structured_events = _mapping(structured_facts.get("event_facts"))
    if "disease_changes" in structured_events:
        event_facts["disease_changes"] = list(
            _sequence_of_mappings(structured_events["disease_changes"])
        )
    merged["event_facts"] = event_facts
    states = dict(_mapping(context.get("event_source_state_by_rule")))
    states.update(_mapping(structured_facts.get("event_source_state_by_rule")))
    merged["event_source_state_by_rule"] = states
    return merged


def _source_gap(
    code: str, *, events: Sequence[Mapping[str, Any]] = ()
) -> dict[str, Any]:
    return {
        "event_facts": {"disease_changes": [dict(item) for item in events]},
        "event_source_state_by_rule": {rule_id: code for rule_id in _RULE_IDS},
        "diagnostic": {"code": code, "event_count": len(events), "llm_call_count": 0},
    }


def _severity_order_event(
    row: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    name = _clean(row.get("order_name"))
    status = _clean(row.get("order_status"))
    if (
        any(marker in name for marker in _VOID_MARKERS)
        or status in _EXCLUDED_ORDER_STATUSES
    ):
        return None, None
    if status not in _EFFECTIVE_ORDER_STATUSES:
        return None, "order_status_unresolved"
    severity = _severity(name)
    order_id = _clean(row.get("order_id"))
    if severity is None or not order_id:
        return None, "order_coordinate_unavailable"
    # ``planned_start_datetime`` 不是已核实的下达时间，不能替代原始下达字段。
    event_time = _trusted_time(row.get("prescribed_datetime"))
    return _event(
        event_id=f"severity-order:{order_id}",
        event_source_type="inpat_nondrug_order",
        event_source_id=order_id,
        event_time=event_time,
        event_kind=f"severity_{severity}",
        lifecycle_state="stopped" if status == "停止" else "active",
    ), None


def _critical_lab_events(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """同一检验报告的多个 PL/PH 项目归并为一个病情变化事件。"""

    grouped: dict[str, list[Mapping[str, Any]]] = {}
    issues: list[str] = []
    for row in rows:
        indicator = _clean(row.get("abnormal_indicator")).upper()
        if indicator not in _CRITICAL_FLAGS:
            # 固定输入重放显式证明 HI/LI 不是本院危急值触发标志。
            continue
        test_id = _clean(row.get("item_test_id"))
        master_test_id = _clean(row.get("master_test_id"))
        if not test_id or master_test_id != test_id:
            issues.append("critical_lab_coordinate_unavailable")
            continue
        grouped.setdefault(test_id, []).append(row)

    events: list[dict[str, Any]] = []
    for test_id, report_rows in grouped.items():
        item_ids = tuple(
            dict.fromkeys(
                _clean(row.get("item_id")) or _clean(row.get("item_document_id"))
                for row in report_rows
            )
        )
        if not item_ids or any(not item_id for item_id in item_ids):
            issues.append("critical_lab_coordinate_unavailable")
            continue
        item_times = {
            value
            for row in report_rows
            for value in (_trusted_time(row.get("item_report_time")),)
            if value
        }
        master_times = {
            value
            for row in report_rows
            for value in (_trusted_time(row.get("master_report_datetime")),)
            if value
        }
        all_times = item_times | master_times
        if len(item_times) > 1 or len(master_times) > 1 or len(all_times) > 1:
            issues.append("critical_lab_time_conflict")
            continue
        event_time = next(iter(all_times), None)
        flags = tuple(
            sorted(
                {_clean(row.get("abnormal_indicator")).upper() for row in report_rows}
            )
        )
        critical_items: list[dict[str, str]] = []
        critical_context_complete = True
        for row in report_rows:
            item_id = _clean(row.get("item_id")) or _clean(row.get("item_document_id"))
            item_name = _bounded_context_text(row.get("item_name"))
            result = _bounded_context_text(row.get("result"))
            unit = _bounded_context_text(row.get("unit"))
            critical_flag = _clean(row.get("abnormal_indicator")).upper()
            if not item_id or not item_name or not result:
                critical_context_complete = False
                critical_items = []
                break
            critical_items.append(
                {
                    "item_id": item_id,
                    "item_name": item_name,
                    "result": result,
                    "unit": unit,
                    "critical_flag": critical_flag,
                }
            )
        events.append(
            _event(
                event_id=f"critical-lab:{test_id}",
                event_source_type="labtest_master",
                event_source_id=test_id,
                event_time=event_time,
                event_kind="critical_lab_report",
                related_source_type="labtest_item_report",
                related_source_ids=item_ids,
                critical_flags=flags,
                critical_items=(critical_items if critical_context_complete else ()),
            )
        )
    return events, issues


def _event(
    *,
    event_id: str,
    event_source_type: str,
    event_source_id: str,
    event_time: str | None,
    event_kind: str,
    lifecycle_state: str | None = None,
    related_source_type: str | None = None,
    related_source_id: str | None = None,
    related_source_ids: Sequence[str] = (),
    critical_flags: Sequence[str] = (),
    critical_items: Sequence[Mapping[str, str]] = (),
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "event_type": "disease_changes",
        "event_id": event_id,
        "trigger_confirmed": True,
        # 当前客户口径未定义时窗；保留未知，绝不以状态或更新时间冒充成熟。
        "evaluation_window_mature": None,
        "event_source_type": event_source_type,
        "event_source_id": event_source_id,
        "event_kind": event_kind,
    }
    if event_time:
        event["event_time"] = event_time
    if lifecycle_state:
        event["lifecycle_state"] = lifecycle_state
    if related_source_type and related_source_id:
        event["related_source_type"] = related_source_type
        event["related_source_id"] = related_source_id
    if related_source_type and related_source_ids:
        event["related_source_type"] = related_source_type
        event["related_source_ids"] = list(related_source_ids)
    if critical_flags:
        event["critical_flags"] = list(critical_flags)
    if critical_items:
        event["critical_items"] = [dict(item) for item in critical_items]
    return event


def _severity(name: str) -> str | None:
    has_critical = "病危" in name
    has_serious = "病重" in name
    if has_critical == has_serious:
        return None
    return "critical" if has_critical else "serious"


def _trusted_time(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="seconds")
    if isinstance(value, str):
        normalized = value.strip()
        if (
            not normalized
            or "\n" in normalized
            or "\r" in normalized
            or len(normalized) > 40
        ):
            return None
        try:
            return datetime.fromisoformat(normalized.replace("Z", "+00:00")).isoformat(
                sep=" ", timespec="seconds"
            )
        except ValueError:
            return None
    return None


def _clean(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _bounded_context_text(value: Any) -> str:
    text_value = _clean(value)
    if not text_value:
        return ""
    if "\n" in text_value or "\r" in text_value or len(text_value) > 160:
        return ""
    return text_value


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence_of_mappings(value: Any) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


__all__ = [
    "build_disease_change_015016_facts",
    "load_disease_change_015016_facts",
    "merge_disease_change_015016_facts",
]
