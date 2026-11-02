"""对客户既有验收 raw/CDM 作只读对照；不属于发布放行路径。"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any

from medqc_ingest.domain import (
    ErrorKind,
    IngestError,
    KeyTracker,
    canonical_json,
    project_record,
    resolve_interface,
    schema_signature,
    sha256_hex,
)
from medqc_ingest.orders_lab_exam_contracts import MORE_ARGUMENT_COUNTS
from medqc_ingest.repositories.postgres import (
    _TARGET_TYPE_COMPATIBILITY,
    _ident,
    _read_cdm_contract,
)

ACCEPTANCE_DATABASE = "medqc_bundle_time_clone_20261029180906"
VERIFICATION_INTERFACES = tuple(MORE_ARGUMENT_COUNTS)


def verify_existing_cdm(
    connection: Any,
    interfaces: Sequence[str] = VERIFICATION_INTERFACES,
    chunk_size: int = 1000,
) -> list[dict[str, Any]]:
    """只输出计数与合同字段名；空哈希只标注，不修改、不授权发布。"""
    if chunk_size <= 0 or not interfaces or set(interfaces) - set(VERIFICATION_INTERFACES):
        raise IngestError(ErrorKind.CONFIGURATION, "verification_scope")
    with connection.cursor() as cursor:
        cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        cursor.execute("SET LOCAL statement_timeout='60s'")
        cursor.execute("SET LOCAL timezone='Asia/Shanghai'")
        cursor.execute(
            "SELECT current_database(),current_setting('transaction_read_only'),rolsuper "
            "FROM pg_roles WHERE rolname=current_user"
        )
        identity = cursor.fetchone()
        if not identity or identity[0] != ACCEPTANCE_DATABASE:
            raise IngestError(ErrorKind.CONFIGURATION, "verification_database")
        if identity[1] != "on" or identity[2]:
            raise IngestError(ErrorKind.CONFIGURATION, "verification_readonly_identity")

    results: list[dict[str, Any]] = []
    for name in interfaces:
        spec = resolve_interface(name)
        target = spec.publish
        assert target is not None
        columns, primary_key = _read_cdm_contract(connection, target)
        if tuple(primary_key) != target.primary_key or any(
            columns.get(m.target) not in _TARGET_TYPE_COMPATIBILITY[m.target_type]
            for m in target.mappings
        ):
            raise IngestError(ErrorKind.PUBLISH_CONTRACT, "verification_target_contract")
        expected_hash = schema_signature(spec.source_columns)[0]
        table = f"{_ident(target.schema)}.{_ident(target.table)}"
        selected_columns = ",".join(_ident(c) for c in target.target_columns)
        key_columns = ",".join(_ident(c) for c in target.primary_key)
        matched = missing = mismatched = raw_count = blank_hashes = 0
        field_mismatches = dict.fromkeys(target.target_columns, 0)
        target_keys = KeyTracker()
        source_keys = KeyTracker()
        with connection.cursor() as query, connection.cursor(name="medqc_readonly_raw") as raw:
            query.execute(f"SELECT count(*) FROM {table}")
            target_count = int(query.fetchone()[0])
            raw.execute(
                "SELECT payload,schema_hash,source_key_hash,row_hash "
                "FROM cache_raw.source_record WHERE interface_name=%s ORDER BY source_key_hash",
                (name,),
            )
            while True:
                rows = raw.fetchmany(chunk_size)
                if not rows:
                    break
                projected: list[dict[str, Any]] = []
                for payload, schema_hash, source_key_hash, row_hash in rows:
                    if not isinstance(payload, dict) or set(payload) != set(spec.source_columns):
                        raise IngestError(ErrorKind.SCHEMA, "verification_payload_columns")
                    source_keys.extend((str(source_key_hash),))
                    if sha256_hex(canonical_json(payload)) != row_hash:
                        raise IngestError(ErrorKind.SCHEMA, "verification_content_hash")
                    if schema_hash is None or not str(schema_hash).strip():
                        blank_hashes += 1
                    elif schema_hash != expected_hash:
                        raise IngestError(ErrorKind.SCHEMA, "verification_schema_hash")
                    # 六接口没有本地生成时间映射；此参数不会代替任何源时间。
                    projected.append(
                        project_record(spec, payload, datetime(1970, 1, 1, tzinfo=timezone.utc))
                    )
                keys = [tuple(row[c] for c in target.primary_key) for row in projected]
                target_keys.extend(sha256_hex(canonical_json(key)) for key in keys)
                row_placeholder = "(" + ",".join("%s" for _ in target.primary_key) + ")"
                query.execute(
                    f"SELECT {selected_columns} FROM {table} WHERE ({key_columns}) IN ("
                    + ",".join(row_placeholder for _ in keys)
                    + ")",
                    tuple(value for key in keys for value in key),
                )
                actual = {}
                for values in query.fetchall():
                    row = dict(zip(target.target_columns, values, strict=True))
                    key = tuple(row[c] for c in target.primary_key)
                    if key in actual:
                        raise IngestError(ErrorKind.KEY, "verification_target_duplicate")
                    actual[key] = row
                for key, row in zip(keys, projected, strict=True):
                    if key not in actual:
                        missing += 1
                    elif actual[key] != row:
                        mismatched += 1
                        for field in target.target_columns:
                            if actual[key][field] != row[field]:
                                field_mismatches[field] += 1
                    else:
                        matched += 1
                raw_count += len(rows)
        extra = target_count - (raw_count - missing)
        results.append(
            {
                "interface": name,
                "rows_compared": raw_count,
                "rows_all_fields_equal": matched,
                "missing_target_rows": missing,
                "mismatched_rows": mismatched,
                "extra_target_rows": extra,
                "raw_schema_hash_blank_rows": blank_hashes,
                "mapped_fields": len(target.mappings),
                "field_mismatch_counts": field_mismatches,
                "status": "verified"
                if raw_count > 0 and not (missing or mismatched or extra)
                else "failed",
                "legacy_blank_hash_publish_authorized": False,
            }
        )
    return results
