"""病历池只读补充手术记录。准入与住院绑定由同步侧的当前版本证据提供。"""

from collections import Counter
from hashlib import sha256
import json

from sqlalchemy.exc import DBAPIError

from ...database import clinical_connection
from .. import case_material_snapshot
from ..primary_material_readonly import KEYS, digest
from ..validation_material_source import is_material_copy
from .emr_view import build_documents_tree

_INTERFACE = "clinical.public.surgery_record"
_LIMIT = 200
_QUERY = """
SELECT s.institute_id, s.patient_id, s.visit_id, s.document_id,
       s.document_title, s.record_time, s.submit_time, s.surgery_process,
       p.cache_document_id, p.surgery_process_sha256, r.source_epoch::text AS source_epoch,
       r.source_key_hash, r.target_key_hash, r.generation, r.mapping_hash, r.activation
FROM sync_material.clinical_surgery_browse_v1 p
JOIN sync_material.clinical_surgery_record_current s
  ON (s.institute_id, s.patient_id, s.visit_id, s.document_id) =
     (p.clinical_institute_id, p.clinical_patient_id, p.clinical_visit_id, p.document_id)
JOIN sync_delivery.receipt r
  ON r.interface_name = %s AND r.source_epoch = p.source_epoch
 AND r.source_key_hash = p.source_key_hash AND r.target_key_hash = p.target_key_hash
 AND r.generation = p.generation AND r.mapping_hash = p.mapping_hash AND r.activation = p.activation
JOIN sync_delivery.contract c
  ON c.interface_name = r.interface_name AND c.source_epoch = r.source_epoch
 AND c.mapping_hash = r.mapping_hash AND c.activation = r.activation
WHERE (p.institute_id, p.patient_id, p.visit_id) = (%s, %s, %s)
  AND p.lifecycle_state = 'USABLE' AND p.generation > 0 AND p.activation > 0
"""


def _read(identity, document_id=None):
    if (
        case_material_snapshot.current() is not None
        or not clinical_connection.configured()
        or is_material_copy(identity[1], identity[2])
    ):
        return [], "not_applicable"
    engine = clinical_connection.get_engine()
    query = _QUERY + (" AND s.document_id = %s" if document_id is not None else "")
    params = (_INTERFACE, *identity)
    if document_id is not None:
        params = (*params, document_id)
    try:
        with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
            with connection.begin():
                connection.exec_driver_sql("SET TRANSACTION READ ONLY")
                connection.exec_driver_sql("SET LOCAL statement_timeout = 5000")
                rows = connection.exec_driver_sql(
                    query + " ORDER BY s.document_id LIMIT %s", (*params, _LIMIT + 1),
                ).mappings().all()
    except DBAPIError as exc:
        # 补充能力尚未发布、授权缺失或暂不可用时，基础目录仍然可用。
        code = getattr(exc.orig, "pgcode", None) or getattr(exc.orig, "sqlstate", None)
        return [], {
            "42P01": "contract_unavailable",
            "42703": "contract_unavailable",
            "42501": "permission_unavailable",
        }.get(code, "read_unavailable")
    if len(rows) > _LIMIT:
        return [], "read_limit_exceeded"
    counts = Counter(row["document_id"] for row in rows)
    verified = []
    for row in rows:
        body = row["surgery_process"]
        if counts[row["document_id"]] != 1 or not isinstance(body, str) or not body.strip():
            continue
        # 手术同步合同原样投递四键，回执必须属于本行，而非另一条已发布记录。
        key_hash = digest({key: row[key] for key in KEYS})
        body_hash = sha256(body.encode("utf-8")).hexdigest()
        if (key_hash != row["source_key_hash"] or key_hash != row["target_key_hash"]
                or body_hash != row["surgery_process_sha256"]):
            continue
        verified.append(row)
    return verified, "available"


def _document(identity, row):
    version = sha256(json.dumps([
        clinical_connection.source_binding(), identity, row["document_id"],
        row["source_epoch"], row["source_key_hash"], row["target_key_hash"],
        row["generation"], row["mapping_hash"], row["activation"], row["surgery_process_sha256"],
    ], ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
    key = f"surgery_record::clinical::{version}"
    return {
        "id": key, "doc_key": key, "document_id": row["document_id"],
        "doc_type": "surgery_record", "doc_name": row["document_title"] or "手术记录",
        "execution_domain": "surgery", "group_key": "surgery",
        "record_time": row["record_time"], "submit_time": row["submit_time"],
        "source_namespace": "clinical", "version_id": version,
        "clinical_surgery_version": version, "generation": row["generation"],
        "has_content": True, "length": len(row["surgery_process"]),
    }


def supplement_directory(payload, identity):
    rows, status = _read(identity)
    payload["clinical_surgery_status"] = status
    if not rows:
        return payload
    base = payload["documents"]
    base_counts = Counter(doc.get("document_id") for doc in base if doc.get("doc_type") == "surgery_record")
    readable_base = {doc.get("document_id") for doc in base if doc.get("doc_type") == "surgery_record"
                     and (doc.get("has_content") is True or str(doc.get("content") or "").strip())}
    link_counts = Counter(row["cache_document_id"] for row in rows)
    supplements = [
        _document(identity, row)
        for row in rows
        if not (row["cache_document_id"] in readable_base and base_counts[row["cache_document_id"]] == 1
                and link_counts[row["cache_document_id"]] == 1)
    ]
    payload["documents"] = [*base, *supplements]
    payload["documents_tree"] = build_documents_tree(payload["documents"])
    return payload


def read_document(identity, document_id, version):
    rows, status = _read(identity, document_id)
    if len(rows) == 1:
        row = rows[0]
        document = _document(identity, row)
        if document["version_id"] == version:
            return {**document, "content": row["surgery_process"]}, status
    return None, status
