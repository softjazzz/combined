"""显式运行的PG18只读验收；不输出患者数据、实际内容哈希或凭据。"""

import argparse
import hashlib
import json
import logging
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests/integration")]


def run(handoff):
    from local_pg18_readonly_support import ReadonlyGuard
    import psycopg2

    contract = json.loads(
        (handoff / "readonly-access-contract.json").read_text(encoding="utf-8-sig")
    )
    for line in (
        (handoff / "CHECKSUMS.txt").read_text(encoding="utf-8-sig").splitlines()
    ):
        digest, name = line.split(maxsplit=1)
        path = (handoff / name.lstrip("* ")).resolve()
        if (
            not path.is_relative_to(handoff.resolve())
            or hashlib.sha256(path.read_bytes()).hexdigest() != digest.lower()
        ):
            raise RuntimeError("handoff_checksum_mismatch")
    guard = ReadonlyGuard(contract)
    report = {
        "stage": "PG18_READONLY",
        "status": "BLOCKED/FAIL",
        "tables": [],
        "paths": [],
        "server_connections": 0,
        "medqc_connections": 0,
        "cache_connections": 0,
    }
    logging.disable(logging.CRITICAL)
    with guard.activate():

        def connect(role):
            return psycopg2.connect(
                host="127.0.0.1",
                port=5432,
                dbname=role["database"],
                user=role["role"],
                passfile=role["passfile"],
                sslmode="prefer",
                connect_timeout=5,
            )

        def baseline():
            state = {}
            for role in guard.roles.values():
                conn = connect(role)
                try:
                    for table in role["tables"]:
                        name = table["table"]
                        assert name in role["table_select_whitelist"]
                        schema, tab = name.split(".")
                        with conn.cursor() as cur:
                            cur.execute(
                                "SELECT attname FROM pg_catalog.pg_attribute WHERE attrelid=%s::regclass AND attnum>0 AND NOT attisdropped ORDER BY attnum",
                                (name,),
                            )
                            columns = [row[0] for row in cur.fetchall()]
                            if set(columns) != {
                                column["name"] for column in table["columns"]
                            }:
                                raise RuntimeError(
                                    "local_readonly_columns_contract_mismatch"
                                )
                            cur.execute(
                                "SELECT a.attname FROM pg_catalog.pg_index i JOIN pg_catalog.pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=ANY(i.indkey) WHERE i.indrelid=%s::regclass AND i.indisprimary ORDER BY array_position(i.indkey,a.attnum)",
                                (name,),
                            )
                            if [row[0] for row in cur.fetchall()] != table[
                                "primary_key"
                            ]:
                                raise RuntimeError(
                                    "local_readonly_primary_key_contract_mismatch"
                                )
                            cur.execute(
                                f'SELECT to_jsonb(t)::text FROM "{schema}"."{tab}" t'
                            )
                            rows = sorted(value[0] for value in cur.fetchall())
                            state[(role["database"], name)] = (
                                len(rows),
                                hashlib.sha256("\n".join(rows).encode()).digest(),
                            )
                finally:
                    conn.close()
            return state

        before = baseline()
        for (db, table), (count, _) in before.items():
            report["tables"].append(
                {
                    "source": "ingest" if "ingest" in db else "cdm",
                    "table": table,
                    "rows": count,
                }
            )
        ingest = next(r for r in guard.roles.values() if "ingest" in r["database"])
        conn = connect(ingest)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT count(*) FROM sync_ops.publish_lineage l WHERE NOT EXISTS (SELECT 1 FROM sync_ops.publish_batch b WHERE b.publish_batch_id=l.publish_batch_id)"
                )
                report["lineage_orphan_batches"] = cur.fetchone()[0]
                cur.execute(
                    "SELECT count(*) FROM cache_raw.source_record r WHERE NOT EXISTS (SELECT 1 FROM sync_ops.source_interface i WHERE i.interface_name=r.interface_name)"
                )
                report["raw_unregistered_sources"] = cur.fetchone()[0]
        finally:
            conn.close()

        role = next(r for r in guard.roles.values() if "cdm" in r["database"])
        os.environ["CDM_PGPASSFILE"] = role["passfile"]
        from app.services import clinical_sources
        from app.database import clinical_connection
        from app.services.luxian_0609 import source_evidence_reader as reader
        from app.services.bundles import assembly

        settings = clinical_sources.SourceSettings(
            default_source="independent_cdm",
            cdm=clinical_sources.CDMProfile(
                enabled=True,
                host="127.0.0.1",
                port=5432,
                database=role["database"],
                username=role["role"],
            ),
        )
        source = clinical_sources.snapshot(settings, "independent_cdm")
        independent_engine = None
        conn = connect(role)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT institute_id,patient_id,visit_id FROM cdm.mr")
                identities = cur.fetchall()
            report["sample_count"] = len(identities)
            with clinical_connection.selected(source):
                independent_engine = clinical_connection.get_engine()
                for entry in role["tables"]:
                    key = entry["table"].split(".")[1]
                    result = {
                        "source": key,
                        "calls": 0,
                        "rows": 0,
                        "matched": 0,
                        "truncated": 0,
                    }
                    if key not in reader._SNAPSHOT_SOURCE_FIELDS:
                        result.update(
                            status="not_in_selected_reader_contract",
                            reason="public_reader_source_not_supported",
                        )
                        report["paths"].append(result)
                        continue
                    for identity in identities:
                        with conn.cursor() as cur:
                            cur.execute(
                                f'SELECT to_jsonb(t) FROM cdm."{key}" t WHERE institute_id=%s AND patient_id=%s AND visit_id=%s',
                                identity,
                            )
                            raw = [row[0] for row in cur.fetchall()]
                        read = reader.read_luxian_0609_snapshot_source_rows(
                            source_key=key,
                            institute_id=identity[0],
                            patient_id=identity[1],
                            visit_id=identity[2],
                            source_schema="cdm",
                        )
                        result["calls"] += 1
                        result["rows"] += len(read.rows)
                        result["truncated"] += int(read.truncated)
                        for row in read.rows:
                            # 原文及时间只在进程内比较，不导出值或内容指纹。
                            comparable = {
                                k: v
                                for k, v in row.items()
                                if k
                                in {
                                    "record_content",
                                    "record_datetime",
                                    "report_time",
                                    "submit_datetime",
                                    "last_modified_datetime",
                                    "update_time",
                                }
                                and v is not None
                            }

                            def same(candidate):
                                return all(
                                    str(candidate.get(k)).replace("T", " ")
                                    == str(v).replace("T", " ")
                                    for k, v in comparable.items()
                                )

                            if not comparable or not any(
                                same(candidate) for candidate in raw
                            ):
                                raise RuntimeError("formal_source_material_mismatch")
                            result["matched"] += 1
                        if len(read.rows) != len(raw):
                            raise RuntimeError("formal_source_count_mismatch")
                    result["status"] = "PASS"
                    report["paths"].append(result)
                assert clinical_connection.current_selection() == source
            assert clinical_connection.current_selection() is None
        finally:
            conn.close()
            assembly._get_table_columns.cache_clear()
            if independent_engine is not None:
                independent_engine.dispose()
            clinical_connection._engine.cache_clear()
        after = baseline()
        report["existing_data_unchanged"] = before == after
        report["sequence_state_verified"] = False
        report["limitations"] = [
            "sequence_select_not_authorized",
            "bundle_persistence_no_authorized_local_business_connection",
            "cdm.inpat_registration_missing",
            "cdm.patient_information_missing",
            "cdm.diagnosis_missing",
            "cdm.discharge_record.discharge_time_missing",
        ]
        report["counts"] = guard.counts
        if (
            before == after
            and not report["lineage_orphan_batches"]
            and not report["raw_unregistered_sources"]
            and all(
                not guard.counts[k]
                for k in (
                    "forbidden_connections",
                    "write_attempts",
                    "model_attempts",
                    "external_transport_attempts",
                )
            )
        ):
            report["status"] = "PASS_WITH_DOCUMENTED_FIXTURE_LIMITATIONS"
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--handoff", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = run(args.handoff)
    except BaseException as error:
        # 绝不输出异常正文、SQL参数或患者材料。
        result = {
            "stage": "PG18_READONLY",
            "status": "BLOCKED/FAIL",
            "error_type": type(error).__name__,
        }
        if type(error).__name__ == "OfflineIsolationError" and str(error).startswith(
            "local_readonly_"
        ):
            result["error_code"] = str(error)
        if hasattr(error, "identity"):
            result["identity"] = error.identity
        import traceback

        result["frames"] = [
            {
                "file": Path(frame.filename).name,
                "function": frame.name,
                "line": frame.lineno,
            }
            for frame in traceback.extract_tb(error.__traceback__)
        ]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {k: v for k, v in result.items() if k not in {"tables", "paths"}},
            ensure_ascii=False,
        )
    )
    raise SystemExit(0 if result["status"].startswith("PASS") else 1)
