"""可选的真实 PostgreSQL 场景：仅创建独立库，数据全部虚构，不读取业务表。

调用方提供内存连接参数；不在此文件存放或打印口令。数据库保留用于检查，不自动删除。
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from typing import Any
from unittest.mock import patch

from medqc_ingest import takeover
from medqc_ingest.config import PostgresSettings
from medqc_ingest.deployment_acceptance import (
    publish_twice,
    rollback_and_recovery,
    verify_published,
)
from medqc_ingest.domain import INTERFACE_REGISTRY, canonical_json, schema_signature, sha256_hex

ROOT = Path(__file__).resolve().parents[1]


def run_scenario(driver: Any, parameters: dict[str, Any], stamp: str) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9]{14}", stamp) or parameters.get("host") != "127.0.0.1":
        raise RuntimeError("isolated local test scope required")
    names = {kind: f"medqc_{kind}_takeover_{stamp}" for kind in ("source", "ingest", "cdm")}
    maintenance = driver.connect(**{**parameters, "dbname": "postgres"})
    maintenance.autocommit = True
    connections = []
    try:
        with maintenance.cursor() as cursor:
            cursor.execute("SELECT current_user")
            user = str(cursor.fetchone()[0])
            for database in names.values():
                cursor.execute(f'CREATE DATABASE "{database}"')
        for database in names.values():
            connections.append(driver.connect(**{**parameters, "dbname": database}))
        source, ingest, cdm = connections
        _seed_source(source)
        spec = importlib.util.spec_from_file_location(
            "scenario_initializer", ROOT / "tools/run_takeover.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.initialize(ingest, names["ingest"], user)
        _seed_cdm(cdm)
        with (
            patch.object(takeover, "ACCEPTANCE_DATABASE", names["source"]),
            patch.dict(takeover.EXPECTED_COUNTS, dict.fromkeys(INTERFACE_REGISTRY, 3), clear=True),
            patch.object(
                PostgresSettings,
                "connection_kwargs",
                lambda item: {**parameters, "dbname": item.database},
            ),
            patch.dict("os.environ", {"MEDQC_PG_DRIVER": "psycopg2"}),
        ):
            imported = takeover.import_legacy(source, ingest, names["ingest"], chunk_size=2)
            verified = takeover.verify_takeover(ingest, names["ingest"], chunk_size=2)
            ingest.rollback()
            ingest_settings = PostgresSettings(
                "127.0.0.1", parameters["port"], names["ingest"], user, Path("unused")
            )
            cdm_settings = PostgresSettings(
                "127.0.0.1", parameters["port"], names["cdm"], user, Path("unused")
            )
            probe = rollback_and_recovery(ingest_settings)
            published = publish_twice(ingest_settings, cdm_settings)
            equal = verify_published(ingest_settings, cdm_settings)
            reverified = takeover.verify_takeover(ingest, names["ingest"], chunk_size=2)
        return {
            "synthetic_data_only": True,
            "real_postgres_executed": True,
            "business_tables_accessed": False,
            "databases": names,
            "imported_rows": sum(imported["raw_counts"].values()),
            "verified": verified,
            "rollback_recovery": probe,
            "publish_rounds": published,
            "field_equality": equal,
            "reverified": reverified,
        }
    finally:
        for connection in connections:
            connection.close()
        maintenance.close()


def _seed_source(connection: Any) -> None:
    with connection.cursor() as cursor:
        cursor.execute("CREATE SCHEMA cache_raw; CREATE SCHEMA sync_ops")
        cursor.execute("CREATE TABLE sync_ops.source_interface(interface_name text PRIMARY KEY)")
        cursor.execute(
            "CREATE TABLE sync_ops.source_schema"
            "(interface_name text,schema_hash text,column_names_json jsonb)"
        )
        cursor.execute(
            "CREATE TABLE sync_ops.sync_batch(batch_id bigint PRIMARY KEY,interface_name text,"
            "window_start date,window_end date,status text,rows_fetched integer)"
        )
        cursor.execute(
            "CREATE TABLE cache_raw.source_record(interface_name text,source_key_hash text,"
            "source_key jsonb,payload jsonb,schema_hash text,row_hash text,first_batch_id bigint,"
            "last_batch_id bigint,source_window_start date,source_window_end date,"
            "first_seen_at timestamptz DEFAULT now(),PRIMARY KEY(interface_name,source_key_hash))"
        )
        cursor.execute(
            "CREATE TABLE cache_raw.source_record_version(interface_name text,source_key_hash text,"
            "batch_id bigint,row_hash text,payload jsonb)"
        )
        for ordinal, (name, spec) in enumerate(INTERFACE_REGISTRY.items()):
            digest = schema_signature(spec.source_columns)[0]
            cursor.execute("INSERT INTO sync_ops.source_interface VALUES (%s)", (name,))
            cursor.execute(
                "INSERT INTO sync_ops.source_schema VALUES (%s,%s,%s::jsonb)",
                (name, digest, json.dumps(spec.source_columns)),
            )
            for index in range(6):
                day = f"2026-10-{26 + index % 3}"
                cursor.execute(
                    "INSERT INTO sync_ops.sync_batch VALUES (%s,%s,%s,%s,'succeeded',1)",
                    (ordinal * 6 + index + 1, name, day, day),
                )
            for index in range(3):
                day = f"2026-10-{26 + index}"
                payload = dict.fromkeys(spec.source_columns)
                key = {field: f"synthetic-{field}-{index}" for field in spec.key_fields}
                payload.update(key)
                if "record_content" in payload:
                    payload["record_content"] = "synthetic content"
                if "recordcontent" in payload:
                    payload["recordcontent"] = "synthetic content"
                key_hash = sha256_hex(canonical_json(key))
                row_hash = sha256_hex(canonical_json(payload))
                first, last = ordinal * 6 + index + 1, ordinal * 6 + index + 4
                recorded_hash = " " * 32 if name in takeover.MORE_ARGUMENT_COUNTS else digest
                cursor.execute(
                    "INSERT INTO cache_raw.source_record(interface_name,source_key_hash,source_key,"
                    "payload,schema_hash,row_hash,first_batch_id,last_batch_id,source_window_start,"
                    "source_window_end) VALUES (%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s,%s,%s,%s)",
                    (
                        name,
                        key_hash,
                        json.dumps(key),
                        json.dumps(payload),
                        recorded_hash,
                        row_hash,
                        first,
                        last,
                        day,
                        day,
                    ),
                )
                cursor.execute(
                    "INSERT INTO cache_raw.source_record_version VALUES (%s,%s,%s,%s,%s::jsonb)",
                    (name, key_hash, first, row_hash, json.dumps(payload)),
                )
    connection.commit()


def _seed_cdm(connection: Any) -> None:
    sql_types = {
        "text": "text",
        "date": "date",
        "datetime": "timestamp without time zone",
        "timestamptz": "timestamp with time zone",
    }
    with connection.cursor() as cursor:
        cursor.execute("CREATE SCHEMA cdm")
        for spec in INTERFACE_REGISTRY.values():
            target = spec.publish
            fields = [
                f'"{mapping.target}" {sql_types[mapping.target_type]}'
                for mapping in target.mappings
            ]
            fields.append(
                "PRIMARY KEY (" + ",".join(f'"{key}"' for key in target.primary_key) + ")"
            )
            cursor.execute(f'CREATE TABLE "cdm"."{target.table}" (' + ",".join(fields) + ")")
    connection.commit()
