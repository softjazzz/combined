"""只在smoke.sh创建的回环55498合成PG16内验证，不接受任意业务库地址。"""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit

import psycopg2
from psycopg2 import sql
from dotenv import dotenv_values


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--kit", type=Path, required=True)
    args = parser.parse_args()
    cfg = dotenv_values(args.root / "config/business.env")
    url = cfg["DATABASE_URL"]
    parts = urlsplit(url)
    if (
        parts.hostname != "127.0.0.1"
        or parts.port != 55498
        or parts.path != "/medqc_business"
        or not str(args.root).startswith("/tmp/medqc-linux-offline-")
    ):
        raise RuntimeError("disposable_cluster_required")
    transfer = load("transfer_pg_tool", args.kit / "deploy/sample_set_transfer.py")
    jobs = load("job_bootstrap_test", args.kit / "deploy/job_schema.py")
    contract = json.loads(
        (Path(__file__).parent / "shared-schema-contract.json").read_text()
    )
    conn = psycopg2.connect(url)
    checks = []
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database(),inet_server_port()")
            assert cur.fetchone() == ("medqc_business", 55498)
            # 独立冻结的真实导出结构20项，不是用目标库自身反射后自证兼容。
            for table in contract["tables"]:
                actual = transfer.descriptor(cur, table["schema"], table["name"])
                transfer.compatible_columns(table["columns"], actual["columns"])
                assert actual["primary"] == table["primary"]
            checks.append("20_exported_shared_schemas_compatible")
            assert jobs.ensure_job_owner(cur, transfer) is False
            cur.execute("SELECT id FROM sys.sys_users WHERE username='fixture_admin'")
            owner = cur.fetchone()[0]
            # 模拟上一版062留下的31列空表，并让新增三列追加在末尾。
            for column in jobs.EXTRAS:
                cur.execute(
                    sql.SQL(
                        "ALTER TABLE qc.custom_qc_batch_jobs DROP COLUMN {}"
                    ).format(sql.Identifier(column))
                )
            cur.execute(
                "ALTER TABLE qc.custom_qc_batch_jobs ALTER COLUMN job_kind SET NOT NULL"
            )
            assert jobs.ensure_job_owner(cur, transfer) is True
            assert jobs.ensure_job_owner(cur, transfer) is False
            descriptor = transfer.descriptor(cur, "qc", "custom_qc_batch_jobs")
            assert len(descriptor["columns"]) == 34
            source_job = next(
                t for t in contract["tables"] if t["name"] == "custom_qc_batch_jobs"
            )
            assert [c["name"] for c in descriptor["columns"]] != [
                c["name"] for c in source_job["columns"]
            ]
        conn.commit()
        checks.append("empty_31_column_repair_defaults_and_idempotency")

        with tempfile.TemporaryDirectory(
            prefix="synthetic-transfer-", dir=args.root.parent
        ) as folder:
            folder = Path(folder)
            schema = "pdfmat_012345abcdef"
            tables = []
            event = {
                "event_id": "synthetic-event",
                "evidence_id": "synthetic-document",
                "status": "non_compliant",
                "reason": "synthetic-only",
            }

            def row_for(table):
                row = {}
                for c in table["columns"]:
                    kind = c["type"]
                    if not c["notnull"]:
                        row[c["name"]] = None
                    elif kind == "boolean":
                        row[c["name"]] = False
                    elif "timestamp" in kind:
                        row[c["name"]] = (
                            "2026-01-01T00:00:00+08:00"
                            if "with time zone" in kind
                            else "2026-01-01T00:00:00"
                        )
                    elif kind in {
                        "integer",
                        "bigint",
                        "double precision",
                        "real",
                        "smallint",
                    }:
                        row[c["name"]] = 0
                    elif kind in {"json", "jsonb"}:
                        row[c["name"]] = {}
                    else:
                        row[c["name"]] = "fixture"
                return row

            for original in contract["tables"]:
                table = {**original, "constraints": [], "indexes": []}
                rows = []
                if table["name"] == "custom_qc_batch_jobs":
                    row = row_for(table)
                    row.update(
                        id="synthetic-job",
                        draft_id="synthetic-draft",
                        status="failed",
                        created_by="source-owner",
                        execution_mode="multi",
                        draft_ids_json='["synthetic-draft"]',
                        rule_count=1,
                        filters_json="{}",
                        record_ids_json='["synthetic-visit"]',
                        summary_json="{}",
                        items_json=json.dumps([event]),
                        failed_records_json="[]",
                        child_job_ids_json="[]",
                        child_summary_json="{}",
                    )
                    rows = [row]
                    table["columns"] = list(reversed(table["columns"]))
                elif table["name"] == "luxian_0609_record_result_envelopes":
                    row = row_for(table)
                    row.update(
                        id="synthetic-envelope",
                        job_id="synthetic-job",
                        root_job_id="synthetic-job",
                        created_by="source-owner",
                        institute_id="synthetic-institute",
                        patient_id="synthetic-patient",
                        visit_id="synthetic-visit",
                        record_id="synthetic-visit",
                        result_count=1,
                        envelope_json=json.dumps({"items": [event]}),
                    )
                    rows = [row]
                elif table["name"] == "course_domain_bundle":
                    row = row_for(table)
                    row.update(
                        institute_id="synthetic-institute",
                        patient_id="synthetic-patient",
                        visit_id="synthetic-visit",
                        source_documents=[
                            {"document_id": "synthetic-document", "text": "纯合成正文"}
                        ],
                        timeline_facts=[event],
                    )
                    rows = [row]
                table["file"] = f"{table['schema']}.{table['name']}.jsonl"
                table["count"] = len(rows)
                (folder / table["file"]).write_text(
                    "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                    encoding="utf-8",
                )
                table["sha256"] = transfer.sha256(folder / table["file"])
                tables.append(table)
            material = dict(
                schema=schema,
                name="synthetic_documents",
                primary=["id"],
                constraints=[{"name": "synthetic_pk", "kind": "p", "columns": ["id"]}],
                indexes=[],
                columns=[
                    {"name": n, "type": t, "notnull": True}
                    for n, t in [
                        ("id", "text"),
                        ("content", "text"),
                        ("payload", "jsonb"),
                        ("precision_value", "numeric(30,20)"),
                        ("binary_value", "bytea"),
                        ("record_time", "timestamp without time zone"),
                    ]
                ],
                file="synthetic-material.jsonl",
                count=1,
            )
            (folder / material["file"]).write_text(
                json.dumps(
                    dict(
                        id="synthetic-document",
                        content="纯合成正文",
                        payload=event,
                        precision_value="0.12345678901234567890",
                        binary_value="\\x00ff1234",
                        record_time="2026-01-01 08:40:00",
                    ),
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            material["sha256"] = transfer.sha256(folder / material["file"])
            tables.append(material)
            manifest = dict(
                protocol=transfer.PROTOCOL,
                migration=transfer.REVISION,
                material_schema=schema,
                institutes=["synthetic-institute"],
                tables=tables,
                summary=dict(
                    cases=1, material_rows=1, jobs=1, envelopes=1, result_items=1
                ),
            )

            def save_manifest():
                transfer.write_json(folder / "manifest.json", manifest)

            def command(action, *, failure=None):
                command = [
                    sys.executable,
                    str(args.kit / "deploy/sample_set_transfer.py"),
                    action,
                    "--env-file",
                    str(args.root / "config/business.env"),
                    "--package",
                    str(folder),
                    "--owner-username",
                    "fixture_admin",
                ]
                if action == "import":
                    command += [
                        "--pg-bin",
                        str(args.kit / "tools/pg16"),
                        "--backup-dir",
                        str(args.root / "backups"),
                        "--maintenance-confirmed",
                    ]
                result = subprocess.run(command, capture_output=True, text=True)
                if failure:
                    assert result.returncode != 0 and failure in result.stderr, (
                        result.stderr[-500:]
                    )
                else:
                    assert result.returncode == 0, result.stderr[-500:]
                    return json.loads(result.stdout.splitlines()[-1])

            save_manifest()
            assert command("check")["preflight"]
            job = next(t for t in tables if t["name"] == "custom_qc_batch_jobs")
            original = (folder / job["file"]).read_text()
            bad = json.loads(original)
            bad["rule_count"] = None
            (folder / job["file"]).write_text(json.dumps(bad) + "\n")
            job["sha256"] = transfer.sha256(folder / job["file"])
            save_manifest()
            command("check", failure="source_required_column_missing_or_null")
            (folder / job["file"]).write_text(original)
            job["sha256"] = transfer.sha256(folder / job["file"])
            save_manifest()
            checks.append("null_source_required_column_rejected")
            assert command("import")["verified"]
            assert command("verify")["verified"]
            assert command("import")["already_imported"]
            checks.append(
                "check_backup_import_verify_idempotency_with_reordered_columns"
            )
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT created_by,status,execution_mode,draft_ids_json,rule_count,items_json FROM qc.custom_qc_batch_jobs WHERE id='synthetic-job'"
                )
                values = cur.fetchone()
                assert values[:5] == (
                    owner,
                    "failed",
                    "multi",
                    '["synthetic-draft"]',
                    1,
                )
                assert json.loads(values[5]) == [event]
                cur.execute(
                    "SELECT envelope_json FROM qc.luxian_0609_record_result_envelopes WHERE id='synthetic-envelope'"
                )
                assert json.loads(cur.fetchone()[0]) == {"items": [event]}
                cur.execute(
                    "SELECT precision_value::text,encode(binary_value,'hex'),record_time::text,payload FROM pdfmat_012345abcdef.synthetic_documents"
                )
                assert cur.fetchone() == (
                    "0.12345678901234567890",
                    "00ff1234",
                    "2026-01-01 08:40:00",
                    event,
                )
                cur.execute(
                    "SELECT source_documents,timeline_facts FROM public.course_domain_bundle WHERE visit_id='synthetic-visit'"
                )
                assert cur.fetchone() == (
                    [{"document_id": "synthetic-document", "text": "纯合成正文"}],
                    [event],
                )
            checks.append("owner_status_event_evidence_time_numeric_binary_preserved")
            conn.rollback()
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE qc.custom_qc_batch_jobs SET items_json='[]' WHERE id='synthetic-job'"
                )
            conn.commit()
            command("check", failure="target_row_conflict")
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE qc.custom_qc_batch_jobs SET items_json=%s WHERE id='synthetic-job'",
                    (values[5],),
                )
            conn.commit()
            checks.append("existing_result_conflict_rejected")
            for ddl in [
                "ALTER COLUMN rule_count TYPE bigint",
                "ALTER COLUMN rule_count DROP NOT NULL",
                "ADD COLUMN unexpected text",
            ]:
                with conn.cursor() as cur:
                    cur.execute("ALTER TABLE qc.custom_qc_batch_jobs " + ddl)
                try:
                    transfer.preflight(conn, folder, manifest, "fixture_admin", "sys")
                except ValueError as exc:
                    assert str(exc) == "target_columns_differ_from_export"
                else:
                    raise AssertionError("structural_drift_accepted")
                finally:
                    conn.rollback()
            checks.append("real_pg_type_nullability_extra_column_drift_rejected")
            with conn.cursor() as cur:
                cur.execute(
                    "ALTER TABLE qc.custom_qc_batch_jobs DROP COLUMN execution_mode"
                )
                try:
                    jobs.ensure_job_owner(cur, transfer)
                except ValueError as exc:
                    assert str(exc) == "nonempty_job_schema_repair_refused"
                else:
                    raise AssertionError("nonempty_repair_accepted")
            conn.rollback()
            checks.append("nonempty_job_repair_rejected")

        # 正式任务创建仍保留NULL表示尚无结果；只建合成元数据，不执行质控。
        os.environ.update({k: v for k, v in cfg.items() if v is not None})
        sys.path.insert(0, str(args.root / "current/backend"))
        from app.services.custom_qc_workspace_service import CustomQCWorkspaceService

        created = CustomQCWorkspaceService().create_batch_job(
            draft={
                "id": "synthetic-draft",
                "rule_code": "SYNTHETIC",
                "name": "synthetic",
            },
            created_by=owner,
            scope="final",
            filters={},
            record_ids=[],
            total_records=0,
        )
        assert created["status"] == "queued" and created["items"] == []
        with conn.cursor() as cur:
            cur.execute(
                "SELECT execution_mode,draft_ids_json,rule_count,items_json,failed_records_json FROM qc.custom_qc_batch_jobs WHERE id=%s",
                (created["id"],),
            )
            assert cur.fetchone() == ("batch", "[]", 1, None, None)
        checks.append(
            "formal_job_creation_without_execution_preserves_null_empty_results"
        )
        print(
            json.dumps(
                {
                    "passed": len(checks),
                    "checks": checks,
                    "model_calls": 0,
                    "shared_schema_contracts": 20,
                },
                ensure_ascii=False,
            )
        )
    finally:
        conn.rollback()
        conn.close()


if __name__ == "__main__":
    main()
