"""日常材料唯一业务投影：搬运固定同步判定，不执行去重或重新裁决。"""
from __future__ import annotations

from copy import deepcopy
from contextlib import contextmanager
import os
from types import SimpleNamespace

from . import case_material_snapshot as material
from . import daily_material_readonly as readonly


class MissingDailyBinding(material.MaterialSnapshotError):
    """仅目录可保留未批准关联的基础观察，正式捕获必须拒绝。"""


def enabled():
    return os.getenv("QC_DAILY_MATERIAL_ENABLED", "").strip().lower() == "true"


def read_manifest(connection, identity):
    """仅借用当前 SQLAlchemy connection 的底层连接，所有权仍归捕获者。"""
    url = connection.engine.url
    settings = SimpleNamespace(host=url.host, port=url.port or 5432, database=url.database)
    readonly.independent_database(settings, "cdm")
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
    if not bindings:
        raise MissingDailyBinding("daily_material_binding_missing")
    readonly.require(len(bindings) == 1, "material_business_binding_not_unique")
    case_id, policy_json = bindings[0]
    policy = readonly.CasePolicy.from_dict(policy_json)
    readonly.require(case_id == policy.case_id and ("cache", *identity) in policy.native_cases,
                     "material_business_identity_mismatch")
    result = readonly.read_manifest_in_transaction(settings, driver, case_id, readonly.clinical_contract())
    result["business_base_inventory"] = read_base_inventory(connection, result, identity)
    result["business_binding"] = {"policy": deepcopy(policy_json), "native_case": list(identity),
                                  "reader_source_commit": readonly.SOURCE_COMMIT}
    return result


def read_base_inventory(connection, value, identity):
    with connection.connection.driver_connection.cursor() as cursor:
        cursor.execute(
            "SELECT " + ",".join(map(readonly._ident, readonly.CACHE_COLUMNS)) +
            " FROM cdm.daily_course_record WHERE institute_id=%s AND patient_id=%s AND visit_id=%s",
            tuple(identity),
        )
        return observed_base_inventory(cursor.fetchall(), value, identity)


def observed_base_inventory(rows, value, identity):
    """同RR观察仅用于目录；未被判定绑定的当前行不冒充已发布版本。"""
    known = {readonly.digest(item.get("target_payload", {})) for item in value.get("items", ()) if item.get("source_namespace") == "cache"}
    observed = {}
    for values in rows:
        raw = dict(zip(readonly.CACHE_COLUMNS, values, strict=True))
        payload = {key: readonly.normalize(item) for key, item in raw.items()}
        fingerprint = readonly.digest(payload)
        if fingerprint in known:
            continue
        observed[fingerprint] = {
            "version_id":"observed-" + fingerprint,
            "record_identity":readonly.digest(["cache-observation", *identity, raw["document_id"]]),
            "native_key":[*identity, raw["document_id"]], "source_namespace":"cache", "source_object":"web.daily_course_record",
            "body":raw.get("record_content"), "title":raw.get("document_title"),
            "record_time":raw.get("record_datetime").isoformat() if hasattr(raw.get("record_datetime"),"isoformat") else raw.get("record_datetime"),
            "source_status":raw.get("document_status"), "target_payload":payload, "native_fields":payload,
            "state":"PENDING_RECONCILIATION", "selected":False, "rule_usable":False,
            "source_revision":"UNCONFIRMED", "observation_hash":fingerprint,
        }
    return [observed[key] for key in sorted(observed)]


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


def status_meaning(item, value):
    policy = value.get("business_binding", {}).get("policy", {})
    for source, status, meaning in policy.get("status_rules", ()):
        if source == item.get("source_namespace") and status == item.get("source_status"):
            return meaning
    return None


def display_scope(value):
    if value is None:
        return None
    parts = []
    if value.get("business_binding", {}).get("state") == "UNAPPROVED":
        parts.append("补充来源尚未批准关联")
    if not value.get("items") and not value.get("business_base_inventory"):
        parts.append("暂无已判定日常病程材料")
    if not value.get("fresh"):
        parts.append("材料选择待更新")
    if not scope_from_manifest(value)["can_judge_clinical_absence"]:
        parts.append("来源覆盖待核，不能据此认定未书写")
    return {"fresh": value.get("fresh") is True,
            "can_judge_clinical_absence": scope_from_manifest(value)["can_judge_clinical_absence"],
            "notice": "；".join(parts)}


def display_item(item, value):
    labels = {"CONTENT_CONFLICT":"内容冲突", "PENDING_RECONCILIATION":"待判定", "SUPPLEMENT_CONFIRMED":"补充已确认",
              "EQUIVALENT_SUPPRESSED":"等价版本保留", "BASE_CONFIRMED":"基础材料已确认", "EQUIVALENT_CONFIRMED":"等价关系已确认",
              "ASSOCIATION_AMBIGUOUS":"关联关系待核", "IDENTITY_TYPE_UNRESOLVED":"身份或文书类型待核"}
    state = item.get("state")
    meaning = status_meaning(item, value)
    parts = [labels.get(state, str(state or "待核"))]
    if meaning is None or meaning not in ("valid", "cancelled"):
        parts.append("源状态语义待核")
    elif meaning == "cancelled":
        parts.append("源状态已撤销")
    usable = item.get("selected") is True and item.get("rule_usable") is True and meaning == "valid"
    if item.get("source_revision") == "UNCONFIRMED":
        parts.append("发布版本未确认")
    parts.append("已纳入正式材料" if usable else "未纳入正式材料")
    return {"material_state":state, "material_selected":item.get("selected") is True,
            "material_rule_usable":usable, "material_source_label":{"cache":"基础病程", "clinical":"临床补充"}.get(item.get("source_namespace"),"来源待核"),
            "material_notice":"；".join(parts), "material_scope_notice":display_scope(value)["notice"]}


def scope_from_manifest(value):
    return deepcopy({
        "contract": readonly.CONTRACT,
        "fresh": value.get("fresh", False),
        "decision_id": value.get("decision_id"),
        "policy_hash": value.get("policy_hash"),
        "input_hash": value.get("input_hash"),
        "coverage": value.get("coverage", {}),
        "can_judge_clinical_absence": value.get("can_judge_clinical_absence") is True and all(status_meaning(item, value) in ("valid", "cancelled") for item in value["items"] if item.get("selected")),
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
    return [_row(item, value) for item in value["items"] if item.get("selected") is True and item.get("rule_usable") is True and status_meaning(item, value) == "valid"]


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
    for index, item in enumerate([*value["items"], *value.get("business_base_inventory", ())]):
        raw = _row(item, value)
        raw.update(document_type="daily_course_record", content=item.get("body"),
                   document_title=item.get("title"), display_time=item.get("record_time"))
        doc = _normalize_source_document(raw_doc=raw, index=index, execution_domain="course")
        doc.update(version_id=item["version_id"], source_record_identity=item["record_identity"],
                   source_namespace=item["source_namespace"], source_object=item["source_object"],
                   daily_material=deepcopy(item), daily_material_scope=scope_from_manifest(value),
                   doc_key="daily_course_record::" + item["record_identity"] + "::" + item["version_id"])
        doc.update(display_item(item, value))
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
            try:
                captured = read_manifest(connection, identity)
            except MissingDailyBinding:
                # 仅目录的零关联边界；多关联、错绑、缺权等异常继续失败。
                captured = {"contract":readonly.CONTRACT, "items":[], "fresh":False,
                            "can_judge_clinical_absence":False, "coverage":{}, "business_binding":{"state":"UNAPPROVED"}}
                captured["business_base_inventory"] = read_base_inventory(connection, captured, identity)
            state = {"identity":list(identity), "binding":clinical.source_binding(), "schema":"cdm",
                     "engine":engine, "connection":connection, "columns":{}, "tables":{}, "queries":{},
                     "daily_material_manifest":captured}
            with material.recording(state):
                yield
