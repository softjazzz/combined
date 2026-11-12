"""日常材料唯一业务投影：搬运固定同步判定，不执行去重或重新裁决。"""
from __future__ import annotations

from copy import deepcopy
from contextlib import contextmanager
import os
from types import SimpleNamespace

from . import case_material_snapshot as material
from . import daily_material_readonly as readonly


def enabled():
    return os.getenv("QC_DAILY_MATERIAL_ENABLED", "").strip().lower() == "true"


def read_manifest(connection, identity):
    """仅借用当前 SQLAlchemy connection 的底层连接，所有权仍归捕获者。"""
    url = connection.engine.url
    settings = SimpleNamespace(host=url.host, port=url.port or 5432, database=url.database)
    driver = connection.connection.driver_connection
    with driver.cursor() as cursor:
        cursor.execute(
            "SELECT b.case_id,p.policy_json FROM sync_material.case_binding b "
            "JOIN sync_material.case_policy c ON c.case_id=b.case_id "
            "JOIN sync_material.policy_version p ON p.policy_hash=c.policy_hash "
            "WHERE b.source_namespace=%s AND b.native_case_hash=%s",
            ("cache", readonly.digest(tuple(identity))),
        )
        bindings = cursor.fetchall()
    readonly.require(len(bindings) == 1, "material_business_binding_not_unique")
    case_id, policy_json = bindings[0]
    policy = readonly.CasePolicy.from_dict(policy_json)
    readonly.require(case_id == policy.case_id and ("cache", *identity) in policy.native_cases,
                     "material_business_identity_mismatch")
    result = readonly.read_manifest_in_transaction(settings, driver, case_id, readonly.clinical_contract())
    result["business_binding"] = {"policy": deepcopy(policy_json), "native_case": list(identity),
                                  "reader_source_commit": readonly.SOURCE_COMMIT}
    return result


def manifest(identity=None):
    from .validation_material_source import is_material_copy
    if identity is not None and is_material_copy(identity[1], identity[2]):
        return None
    state = material.context()
    if state is None and enabled():
        raise material.MaterialSnapshotError("daily_material_capture_required")
    if state is None or "daily_material_manifest" not in state:
        return None
    if identity is not None:
        material.identity_check(state, identity)
    return deepcopy(state["daily_material_manifest"])


def scope_from_manifest(value):
    return deepcopy({
        "contract": readonly.CONTRACT,
        "fresh": value.get("fresh", False),
        "decision_id": value.get("decision_id"),
        "policy_hash": value.get("policy_hash"),
        "input_hash": value.get("input_hash"),
        "coverage": value.get("coverage", {}),
        "can_judge_clinical_absence": value.get("can_judge_clinical_absence") is True,
        "field_availability": {i["version_id"]: i.get("field_availability", {}) for i in value["items"]},
        "states": {i["version_id"]: i.get("state") for i in value["items"]},
        "confirmation_basis": value.get("confirmation_basis", {}),
    })


def scope(source_key):
    value = manifest() if source_key == "daily_course_record" else None
    return scope_from_manifest(value) if value is not None else None


def permits_absence(source_key):
    value = scope(source_key)
    # 无扩展字段的旧任务沿用原协议，不能受当前开关影响。
    return value is None or value["can_judge_clinical_absence"]


def _row(item, value):
    row = {key: _decode_scalar(v) for key, v in item.get("target_payload", {}).items()}
    row.update({
        "document_id": item["native_key"][-1],
        "document_title": item.get("title"),
        "record_content": item.get("body"),
        "record_datetime": item.get("record_time"),
        "record_time": item.get("record_time"),
        "submit_datetime": item.get("submit_time"),
        "last_modified_datetime": item.get("modified_time"),
        "document_status": item.get("source_status"),
        "__document_type": "daily_course_record",
        "source_version_key": "daily_course_record::" + item["record_identity"] + "::" + item["version_id"],
        "version_id": item["version_id"],
        "source_record_identity": item["record_identity"],
        "source_namespace": item["source_namespace"],
        "source_object": item["source_object"],
        "daily_material": deepcopy(item),
        "daily_material_scope": scope_from_manifest(value),
    })
    # 原身份完整保存在 daily_material；业务三键由批准 canonical case 绑定。
    return row


def project_rows(value):
    return [_row(item, value) for item in value["items"] if item.get("selected") is True and item.get("rule_usable") is True]


def rows(identity, *, limit=None):
    value = manifest(identity)
    if value is None:
        return None
    result = project_rows(value)
    return result if limit is None else result[:limit]


def rule_rows(identity, approved_fields):
    projected = rows(identity)
    if projected is None:
        return None
    metadata = ("source_version_key", "version_id", "source_record_identity", "source_namespace", "source_object")
    return [{key: row[key] for key in (*approved_fields, *metadata) if key in row} for row in projected]


def project_documents(value):
    from .bundles.emr_view import _normalize_source_document
    result = []
    for index, item in enumerate(value["items"]):
        raw = _row(item, value)
        raw.update(document_type="daily_course_record", content=item.get("body"),
                   document_title=item.get("title"), display_time=item.get("record_time"))
        doc = _normalize_source_document(raw_doc=raw, index=index, execution_domain="course")
        doc.update(version_id=item["version_id"], source_record_identity=item["record_identity"],
                   source_namespace=item["source_namespace"], source_object=item["source_object"],
                   daily_material=deepcopy(item), daily_material_scope=scope_from_manifest(value),
                   doc_key="daily_course_record::" + item["record_identity"] + "::" + item["version_id"])
        result.append(doc)
    return result


def _decode_scalar(value):
    if not isinstance(value, dict) or "$type" not in value:
        return deepcopy(value)
    from datetime import date, datetime
    from decimal import Decimal
    converters = {"datetime": lambda v: datetime.fromisoformat(v["iso"]),
                  "date": lambda v: date.fromisoformat(v["iso"]),
                  "decimal": lambda v: Decimal(v["text"]), "str": lambda v: v["text"]}
    if value["$type"] not in converters:
        raise material.MaterialSnapshotError("daily_target_scalar_unsupported")
    return converters[value["$type"]](value)


@contextmanager
def live_context(identity):
    """普通查看与任务捕获共用投影；整次当前目录在同一RR中组装。"""
    from .validation_material_source import is_material_copy
    if not enabled() or material.context() is not None or is_material_copy(identity[1], identity[2]):
        yield
        return
    from ..database import clinical_connection as clinical
    from .bundles import assembly
    if not clinical.configured():
        raise material.MaterialSnapshotError("daily_material_independent_cdm_required")
    engine = assembly._source_engine("cdm")
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
        with connection.begin():
            connection.exec_driver_sql("SET TRANSACTION READ ONLY")
            connection.exec_driver_sql("SET LOCAL statement_timeout=10000")
            state = {"identity":list(identity), "binding":clinical.source_binding(), "schema":"cdm",
                     "engine":engine, "connection":connection, "columns":{}, "tables":{}, "queries":{},
                     "daily_material_manifest":read_manifest(connection, identity)}
            with material.recording(state):
                yield
