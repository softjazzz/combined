"""Bundle刷新审计v1合同；只读绑定真实owner，不按search_path猜测。"""

import sqlalchemy as sa

TABLES = ("bundle_refresh_jobs", "bundle_refresh_failures")
SCHEMAS = ("public", "qc")
# 类型类别、最小字符容量、可空、必要缺省语义；这是新v1合同，不是历史DDL声明。
JOBS = {
    "job_id": ("str", 64, False, None),
    "scene": ("str", 32, False, None),
    "job_type": ("str", 32, False, None),
    "status": ("str", 32, False, None),
    "requested_by": ("str", 128, False, "empty"),
    "policy_version": ("str", 128, False, "empty"),
    "source_schema": ("str", 64, False, None),
    "bundle_schema": ("str", 64, False, None),
    "filters_json": ("jsonb", 0, False, "object"),
    **{
        k: ("int", 0, False, "zero")
        for k in ("input_total", "processed", "succeeded", "failed")
    },
    "error": ("str", 1000, False, "empty"),
    "created_at": ("time", 0, False, "now"),
    "started_at": ("time", 0, True, None),
    "finished_at": ("time", 0, True, None),
}
FAILURES = {
    "id": ("int", 0, False, "generated"),
    "scene": ("str", 32, False, None),
    **{
        k: ("str", 128, False, None) for k in ("institute_id", "patient_id", "visit_id")
    },
    "policy_version": ("str", 128, False, None),
    "source_schema": ("str", 64, False, None),
    "bundle_schema": ("str", 64, False, None),
    "trigger_source": ("str", 64, False, None),
    "error_stage": ("str", 64, False, None),
    "error_message": ("str", 2000, False, None),
    "error_detail": ("jsonb", 0, False, None),
    "attempt_count": ("int", 0, False, "one"),
    "first_failed_at": ("time", 0, False, None),
    "last_failed_at": ("time", 0, False, None),
    "last_retry_at": ("time", 0, True, None),
    "last_job_id": ("str", 64, True, None),
    "resolved": ("bool", 0, False, "false"),
    "resolved_at": ("time", 0, True, None),
    "resolved_by": ("str", 128, True, None),
}


class RefreshStorageError(RuntimeError):
    pass


def qualified(schema, table):
    if schema not in SCHEMAS or table not in TABLES:
        raise RefreshStorageError("refresh_storage_identifier_rejected")
    return f'"{schema}"."{table}"'


def owner_plan(connection, *, allow_missing=False, split=True):
    result = {}
    for table in TABLES:
        rows = (
            connection.execute(
                sa.text("""
            SELECT n.nspname AS schema_name,c.relkind FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname IN ('public','qc') AND c.relname=:name
        """),
                {"name": table},
            )
            .mappings()
            .all()
        )
        if len(rows) > 1:
            raise RefreshStorageError("refresh_storage_owner_ambiguous:" + table)
        if rows and rows[0]["relkind"] not in ("r", "p"):
            raise RefreshStorageError("refresh_storage_not_physical_table:" + table)
        result[table] = rows[0]["schema_name"] if rows else None
    existing = set(value for value in result.values() if value)
    preferred = (
        next(iter(existing)) if len(existing) == 1 else "qc" if split else "public"
    )
    if not allow_missing and any(value is None for value in result.values()):
        raise RefreshStorageError(
            "refresh_storage_missing:" + ",".join(k for k, v in result.items() if not v)
        )
    return result, preferred


def validate_table(connection, schema, table, *, permissions=True):
    name = qualified(schema, table)
    if (
        permissions
        and not connection.execute(
            sa.text("SELECT has_schema_privilege(current_user,:schema,'USAGE')"),
            {"schema": schema},
        ).scalar()
    ):
        raise RefreshStorageError("refresh_storage_schema_permissions:" + schema)
    inspector = sa.inspect(connection)
    columns = {c["name"]: c for c in inspector.get_columns(table, schema=schema)}
    expected = JOBS if table == TABLES[0] else FAILURES
    for key, (kind, capacity, nullable, default) in expected.items():
        c = columns.get(key)
        if c is None:
            raise RefreshStorageError(
                f"refresh_storage_missing_column:{schema}.{table}.{key}"
            )
        t = c["type"]
        valid = {
            "str": isinstance(t, sa.String)
            and (getattr(t, "length", None) is None or t.length >= capacity),
            "int": isinstance(t, sa.Integer),
            "time": isinstance(t, sa.DateTime) and not t.timezone,
            "bool": isinstance(t, sa.Boolean),
            "jsonb": str(t).upper() == "JSONB",
        }[kind]
        if not valid or bool(c["nullable"]) != nullable:
            raise RefreshStorageError(
                f"refresh_storage_column_contract:{schema}.{table}.{key}"
            )
        value = str(c.get("default") or "").lower().replace(" ", "")
        good = (
            default is None
            or default == "empty"
            and value.startswith("''")
            or default == "object"
            and value.startswith("'{}'")
            or default == "zero"
            and value.strip("()") in ("0", "0::integer", "0::bigint")
            or default == "one"
            and value.strip("()") in ("1", "1::integer", "1::bigint")
            or default == "false"
            and value.strip("()") in ("false", "false::boolean")
            or default == "now"
            and value in ("now()", "current_timestamp", "transaction_timestamp()")
            or default == "generated"
            and (c.get("identity") or "nextval(" in value)
        )
        if not good:
            raise RefreshStorageError(
                f"refresh_storage_default_contract:{schema}.{table}.{key}"
            )
    for key, c in columns.items():
        if (
            key not in expected
            and not c["nullable"]
            and not c.get("default")
            and not c.get("identity")
            and not c.get("computed")
        ):
            raise RefreshStorageError(
                f"refresh_storage_extra_required_column:{schema}.{table}.{key}"
            )
    primary = inspector.get_pk_constraint(table, schema=schema).get(
        "constrained_columns"
    )
    if primary != (["job_id"] if table == TABLES[0] else ["id"]):
        raise RefreshStorageError("refresh_storage_primary_contract:" + name)
    indexes = (
        connection.execute(
            sa.text("""
        SELECT i.indisunique,i.indisvalid,i.indisready,i.indpred IS NULL AS whole,
            i.indexprs IS NULL AS plain, i.indoption::smallint[] AS options,
            ARRAY(SELECT a.attname::text FROM unnest(i.indkey::smallint[]) WITH ORDINALITY k(num,pos)
                  JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=k.num
                  WHERE k.pos<=i.indnkeyatts ORDER BY k.pos) AS keys
        FROM pg_index i WHERE i.indrelid=to_regclass(:name)
    """),
            {"name": name},
        )
        .mappings()
        .all()
    )
    valid_indexes = [
        i
        for i in indexes
        if i["indisvalid"] and i["indisready"] and i["whole"] and i["plain"]
    ]
    if table == TABLES[1] and not any(
        i["indisunique"]
        and set(i["keys"]) == {"scene", "institute_id", "patient_id", "visit_id"}
        and len(i["keys"]) == 4
        for i in valid_indexes
    ):
        raise RefreshStorageError("refresh_storage_unique_contract:" + name)
    sort_keys = (
        ["created_at"] if table == TABLES[0] else ["resolved", "last_failed_at", "id"]
    )
    directions = [1] if table == TABLES[0] else [0, 1, 1]
    if not any(
        list(i["keys"])[: len(sort_keys)] == sort_keys
        and [int(v) & 1 for v in i["options"][: len(sort_keys)]] == directions
        for i in valid_indexes
    ):
        raise RefreshStorageError("refresh_storage_index_contract:" + name)
    if permissions:
        allowed = connection.execute(
            sa.text(
                "SELECT has_schema_privilege(current_user,:schema,'USAGE') AND has_table_privilege(current_user,:name,'SELECT') AND has_table_privilege(current_user,:name,'INSERT') AND has_table_privilege(current_user,:name,'UPDATE')"
            ),
            {"schema": schema, "name": name},
        ).scalar()
        if not allowed:
            raise RefreshStorageError("refresh_storage_permissions:" + name)
        if table == TABLES[1]:
            sequences = (
                connection.execute(
                    sa.text("""
                SELECT seq.oid::regclass::text FROM pg_attrdef ad
                JOIN pg_attribute a ON a.attrelid=ad.adrelid AND a.attnum=ad.adnum
                JOIN pg_depend d ON d.classid='pg_attrdef'::regclass AND d.objid=ad.oid AND d.refclassid='pg_class'::regclass
                JOIN pg_class seq ON seq.oid=d.refobjid AND seq.relkind='S'
                WHERE ad.adrelid=to_regclass(:name) AND a.attname='id'
            """),
                    {"name": name},
                )
                .scalars()
                .all()
            )
            owned = connection.execute(
                sa.text("SELECT pg_get_serial_sequence(:name,'id')"), {"name": name}
            ).scalar()
            if owned:
                sequences.append(owned)
            if not sequences:
                raise RefreshStorageError("refresh_storage_sequence_unverified:" + name)
            for sequence in set(sequences):
                if not connection.execute(
                    sa.text("SELECT has_sequence_privilege(current_user,:seq,'USAGE')"),
                    {"seq": sequence},
                ).scalar():
                    raise RefreshStorageError(
                        "refresh_storage_sequence_permissions:" + name
                    )


def bind_storage(connection):
    owners, _ = owner_plan(connection)
    for table, schema in owners.items():
        validate_table(connection, schema, table)
    return {table: qualified(schema, table) for table, schema in owners.items()}
