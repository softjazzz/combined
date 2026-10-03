"""四川终末受领任务的审核信封；不改变LX交付或SC执行事实。"""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, select

from ..database.models.qc import QCTask, QCTaskQCRun, QCTaskRecord
from .case_identity import CaseRef
from .qc_rule_sets import get_sichuan_rule_set

SC_FINAL_REVIEW_SCHEMA = "sc-final-task-review-envelope-v1"


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and value == value.strip()


def save_task_envelopes(session: Any, *, table: Any, job_row: Any, summary: dict,
                        items: list, failures: list, now: Any) -> None:
    """与job终态同事务；仅保存实际受领final任务的完整可读病例。"""
    from .task_qc_run_service import _sc_content_record_result
    from .scoring_service import project_customer_items
    from .qc_workspace.canonical_result_store import lock_case_result_mutations

    filters = json.loads(job_row.get("filters_json") or "{}")
    if not isinstance(filters, dict):
        return
    key = filters.get("rule_set_key")
    rule = get_sichuan_rule_set(key)
    if (not isinstance(key, str) or not key.startswith("sc_content_")
            or rule is None or rule.scope != "final" or not filters.get("task_id")):
        return
    root = job_row.get("parent_job_id") or job_row["id"]
    task = session.execute(select(QCTask.__table__).where(QCTask.id == filters["task_id"])).mappings().first()
    run = session.execute(select(QCTaskQCRun.__table__).where(
        QCTaskQCRun.task_id == filters["task_id"],
        QCTaskQCRun.run_number == filters.get("task_run_number"),
    )).mappings().first()
    if run is None or run["run_scope"] != "assigned":
        return  # 普通workspace与整范围运行不扩展审核合同。
    version = filters.get("rule_set_version")
    refs = filters.get("record_refs")
    if (task is None or task["scene"] != "final" or filters.get("query_scope") != "final"
            or task["rule_set_key"] != key or task["rule_set_version"] != version
            or not _text(version) or run["job_id"] != root
            or run["triggered_by"] != job_row["created_by"]
            or not isinstance(refs, list) or not refs
            or any(not isinstance(ref, dict) or any(not _text(ref.get(k)) for k in
                   ("institute_id", "patient_id", "visit_id")) for ref in refs)):
        raise ValueError("四川终末任务冻结来源不一致")
    frozen = [CaseRef.from_mapping(ref) for ref in refs]
    if len(set(frozen)) != len(frozen):
        raise ValueError("四川终末任务冻结病例重复")
    records = session.execute(select(QCTaskRecord.__table__).where(
        QCTaskRecord.task_id == task["id"], QCTaskRecord.assignee_id == run["triggered_by"],
    )).mappings().all()
    assigned = {CaseRef(row["institute_id"], row["patient_id"], row["visit_id"])
                for row in records if row["record_id"] == row["id"]}
    if not set(frozen).issubset(assigned):
        raise ValueError("四川终末任务冻结病例不属于受领范围")
    partial = summary.get("execution_status") == "partial_failed"
    if summary.get("execution_status") not in {"completed", "partial_failed"}:
        return
    job = {"items": items, "failed_records": failures, "summary": summary}
    prepared = []
    for ref in frozen:
        result = _sc_content_record_result(result={}, job=job, filters=filters,
                                          case_ref=ref, frozen_refs=frozen, partial=partial)
        if result.get("result_state") != "available":
            continue
        raw = [item for item in items if tuple(str(item.get(k) or "").strip() for k in
               ("institute_id", "patient_id", "visit_id")) == tuple(ref)]
        projected = project_customer_items(raw)
        flags = {item["rule_id"]: item.get("is_confirmed_issue") for item in projected}
        safe_items = []
        for item in result["items"]:
            flag = flags.get(item["rule_id"])
            if type(flag) is not bool:
                raise ValueError("四川终末确认缺陷投影不完整")
            safe_items.append({**item, "is_confirmed_issue": flag})
        source = {"job_id": root, "institute_id": ref.institute_id, "patient_id": ref.patient_id,
                  "visit_id": ref.visit_id, "rule_set_key": key, "rule_set_version": version, "scene": "final"}
        prepared.append((ref, {"schema_version": SC_FINAL_REVIEW_SCHEMA, "source": source,
                               "items": safe_items}))
    lock_case_result_mutations(session, [ref for ref, _ in prepared], rule_set_key=key)
    session.execute(delete(table).where(table.c.job_id == job_row["id"], table.c.rule_set_key == key))
    for ref, payload in prepared:
        session.execute(table.insert().values(
            id=str(uuid4()), job_id=job_row["id"], root_job_id=root, created_by=job_row["created_by"],
            record_id=ref.visit_id, institute_id=ref.institute_id, patient_id=ref.patient_id,
            visit_id=ref.visit_id, rule_set_key=key, rule_set_version=version,
            envelope_json=json.dumps(payload, ensure_ascii=False), result_count=len(payload["items"]),
            created_at=now, updated_at=now,
        ))


def load_items(row: Any, *, source: dict[str, Any], result: dict | None = None) -> list[dict]:
    """信封只搬运已验证SC投影；审核时还必须与当前真实reader一致。"""
    payload = json.loads(row.get("envelope_json") or "{}")
    expected = {k: source[k] for k in ("job_id", "institute_id", "patient_id", "visit_id",
                                      "rule_set_key", "rule_set_version", "scene")}
    if (not isinstance(payload, dict) or payload.get("schema_version") != SC_FINAL_REVIEW_SCHEMA
            or payload.get("source") != expected or row.get("root_job_id") != source["job_id"]
            or any(row.get(k) != source[k] for k in ("institute_id", "patient_id", "visit_id",
                                                    "rule_set_key", "rule_set_version"))):
        raise ValueError("四川终末审核信封来源不一致")
    items = payload.get("items")
    if (not isinstance(items, list) or not items or type(row.get("result_count")) is not int
            or row["result_count"] != len(items)
            or any(not isinstance(item, dict) or not _text(item.get("rule_id"))
                   or type(item.get("is_confirmed_issue")) is not bool for item in items)
            or len({item["rule_id"] for item in items}) != len(items)):
        raise ValueError("四川终末审核信封内容不完整")
    if result is not None and [
        {k: value for k, value in item.items() if k != "is_confirmed_issue"} for item in items
    ] != result.get("items"):
        raise ValueError("四川终末审核信封与当前保存结果不一致")
    from .scoring_service import project_customer_items

    projected = project_customer_items(items)
    if any(frozen["is_confirmed_issue"] != current.get("is_confirmed_issue")
           for frozen, current in zip(items, projected)):
        raise ValueError("四川终末审核信封确认缺陷事实不一致")
    return items
