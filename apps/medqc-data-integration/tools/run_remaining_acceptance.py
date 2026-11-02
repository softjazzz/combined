"""客户机剩余接口一次集中验收入口；固定现场、有限查询、按阶段续跑。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from remaining_environment import (  # noqa: E402
    Environment,
    load_combined_profile,
    require,
    write_json,
)

from medqc_ingest.domain import INTERFACE_REGISTRY  # noqa: E402


def _existing_file(path, location):
    name = path.name.lower()
    require(
        path.is_absolute()
        and path.is_file()
        and name != ".env"
        and not name.startswith(".env.")
        and path.suffix.lower() != ".env",
        location,
    )


def preflight(args):
    from prepare_sync_control_acceptance import check_acl, protect

    from medqc_ingest.periop_live import source_settings

    require(args.run_dir.is_absolute() and args.run_dir.parent.is_dir(), "remaining_run_directory")
    require(
        args.port == 5432 and args.pg_major == 16 and os.name == "nt", "remaining_customer_platform"
    )
    require(re.fullmatch(r"[a-z_][a-z0-9_]*", args.admin_user) is not None, "remaining_admin_user")
    require(not os.environ.get("PGPASSWORD"), "remaining_pgpassword_forbidden")
    for path in (args.source_config, args.admin_passfile, args.runtime_passfile):
        _existing_file(path, "remaining_existing_credential_file")
        check_acl(path)
    settings = source_settings(args.source_config)
    _existing_file(settings.password_file, "remaining_source_password_file")
    check_acl(settings.password_file)
    require(
        args.backend.is_absolute()
        and (args.backend / "scripts/bootstrap_cache_sync_database.py").is_file(),
        "remaining_backend_missing",
    )
    require(
        args.pg_bin.is_absolute()
        and all((args.pg_bin / (x + ".exe")).is_file() for x in ("pg_dump", "pg_restore")),
        "remaining_pg_tools",
    )
    check_acl(args.run_dir.parent)
    if args.run_dir.exists():
        require(
            args.resume and (args.run_dir / "run-manifest.json").is_file(),
            "remaining_resume_required",
        )
        check_acl(args.run_dir)
    else:
        require(not args.resume, "remaining_resume_directory_missing")
        args.run_dir.mkdir()
        protect(args.run_dir, synthetic=False)
    manifest_path = args.run_dir / "run-manifest.json"
    refs = {
        "source_config": str(args.source_config),
        "admin_passfile": str(args.admin_passfile),
        "runtime_passfile": str(args.runtime_passfile),
        "backend": str(args.backend),
        "source_config_sha256": hashlib.sha256(args.source_config.read_bytes()).hexdigest(),
        "port": args.port,
        "pg_major": args.pg_major,
        "admin_user": args.admin_user,
    }
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        require(manifest.get("references") == refs, "remaining_resume_configuration_changed")
    else:
        manifest = {
            "suffix": datetime.now().strftime("%Y%m%d%H%M%S"),
            "references": refs,
            "scope": "remaining25_periop17",
            "production_enabled": False,
        }
        write_json(manifest_path, manifest)
    args.output, args.suffix, args.synthetic = args.run_dir, manifest["suffix"], False
    args.contract = ROOT / "contracts/remaining-interface-contracts.json"
    return manifest


def cohort_review(args, environment):
    """仅核对新scope快照/标准raw的对照，不调用旧13接口，不输出任何病例键。"""
    from contextlib import closing

    candidate = args.cohort_file
    if candidate is None:
        candidate = Path(r"D:\medqc\secrets\cohort\inpatient-cohort.local.csv")
    if not candidate.is_file():
        return {"status": "blocked_missing_confirmed_inpatient_cohort", "source_called": False}
    from prepare_sync_control_acceptance import check_acl

    _existing_file(candidate, "remaining_cohort_path")
    check_acl(candidate)
    required = {
        "institute_id",
        "patient_id",
        "visit_id",
        "admission_date",
        "confirmed_inpatient_as_of",
        "confirmation_basis",
        "expected_documents",
        "document_date",
        "document_id",
    }
    try:
        from itertools import islice

        if candidate.stat().st_size > 1024 * 1024:
            return {
                "status": "invalid_local_cohort",
                "error_code": "cohort_size",
                "source_called": False,
            }
        with candidate.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream, strict=True)
            if set(reader.fieldnames or []) != required:
                return {
                    "status": "invalid_local_cohort",
                    "error_code": "cohort_header",
                    "source_called": False,
                }
            rows = list(islice(reader, 201))
    except (UnicodeError, csv.Error, OSError):
        return {
            "status": "invalid_local_cohort",
            "error_code": "cohort_parse",
            "source_called": False,
        }
    if not rows or len(rows) > 200:
        return {
            "status": "invalid_local_cohort",
            "error_code": "cohort_size",
            "source_called": False,
        }
    for row in rows:
        if any(not str(row.get(key, "")).strip() for key in required - {"document_id"}):
            return {
                "status": "invalid_local_cohort",
                "error_code": "cohort_required",
                "source_called": False,
            }
        try:
            for field in ("admission_date", "confirmed_inpatient_as_of", "document_date"):
                if datetime.strptime(row[field], "%Y-%m-%d").strftime("%Y-%m-%d") != row[field]:
                    raise ValueError
        except (ValueError, TypeError):
            return {
                "status": "invalid_local_cohort",
                "error_code": "cohort_date",
                "source_called": False,
            }
    found = 0
    with (
        closing(environment.connect("ingest", readonly=True)) as connection,
        connection.cursor() as cursor,
    ):
        for row in rows:
            cursor.execute(
                "SELECT EXISTS(SELECT 1 FROM cache_raw.source_record WHERE "
                "payload->>'institute_id'=%s AND payload->>'patient_id'=%s AND "
                "payload->>'visit_id'=%s)",
                tuple(row[k] for k in ("institute_id", "patient_id", "visit_id")),
            )
            found += int(cursor.fetchone()[0])
    return {
        "status": "cohort_presence_observed_only",
        "cohort_rows": len(rows),
        "rows_with_visit_in_new_scope": found,
        "source_called": False,
        "document_specific_availability_verified": False,
        "limitation": "new_scope_window_presence_is_not_full_inpatient_document_completeness",
    }


def critical_field_audit(environment, contract, outcomes):
    """只输出正文/时间/签署列的源目标计数，不解释医生是否签署。"""
    from contextlib import closing

    from psycopg2 import sql

    accepted = {o["interface"] for o in outcomes if o["status"] == "accepted"}
    result = []
    with (
        closing(environment.connect("ingest", readonly=True)) as source,
        closing(environment.connect("cdm", readonly=True)) as target,
        source.cursor() as source_cursor,
        target.cursor() as target_cursor,
    ):
        for item in contract["interfaces"]:
            name = item["interface"]
            mappings = item.get("mappings", item.get("field_mappings", []))
            by_source = {m["source"]: m for m in mappings if m.get("source")}
            fields = [
                column
                for column in (item.get("source_columns") or [])
                if (
                    column.lower() in {"record_content", "recordcontent"}
                    or "sign" in column.lower()
                    or column.lower().endswith(("_datetime", "datetime", "_date", "_time"))
                )
            ]
            for column in fields:
                mapping = by_source.get(column)
                row = {
                    "interface": name,
                    "source_field": column,
                    "target_field": mapping["target"] if mapping else None,
                    "classification": "not_projected_in_this_run",
                }
                if name in accepted:
                    source_cursor.execute(
                        "SELECT count(*),count(*) FILTER(WHERE payload->>%s IS NOT NULL "
                        "AND payload->>%s<>'') FROM cache_raw.source_record "
                        "WHERE interface_name=%s",
                        (column, column, name),
                    )
                    row["raw_rows"], row["raw_nonempty"] = source_cursor.fetchone()
                    if mapping:
                        target_cursor.execute(
                            sql.SQL(
                                "SELECT count(*),count(*) FILTER(WHERE {} IS NOT NULL "
                                "AND {}::text<>'') "
                                "FROM {}"
                            ).format(
                                sql.Identifier(mapping["target"]),
                                sql.Identifier(mapping["target"]),
                                sql.Identifier(*item["publish_target"].split(".")),
                            )
                        )
                        row["target_rows"], row["target_nonempty"] = target_cursor.fetchone()
                        row["classification"] = (
                            "source_empty" if row["raw_nonempty"] == 0 else "mapped_verified"
                        )
                    else:
                        row["classification"] = "raw_preserved_not_mapped"
                result.append(row)
    return {
        "fields": result,
        "values_exported": False,
        "interpretation": "source_empty_does_not_mean_clinically_missing",
    }


def contract_field_gaps(contract):
    def fields(value, name):
        return [
            dict(item)
            if isinstance(item, dict)
            else {
                name: item,
                "reason": "not_in_approved_projection",
            }
            for item in (value or [])
        ]

    rows = []
    for item in contract["interfaces"]:
        raw = item.get("raw_only_fields", item.get("raw_only_source_columns"))
        target = item.get("target_missing_fields", item.get("unmapped_target_columns"))
        rows.append(
            {
                "interface": item["interface"],
                "raw_only": fields(raw, "source"),
                "target_unmapped": fields(target, "target"),
                "interpretation": "unmapped_or_unprovided_is_not_a_clinical_absence",
            }
        )
    return {
        "report_version": "field-contract-gaps-v2",
        "population": "static_contract_all_42_interfaces_not_observed_clinical_missing",
        "interfaces": rows,
        "target_unmapped_does_not_mean_database_column_missing": True,
        "production_reader_registration_changed": False,
    }


def coverage(report, contract):
    by_name = {item["interface"]: item for item in report["interfaces"]}
    rows = []
    for name in sorted(INTERFACE_REGISTRY):
        rows.append(
            {
                "interface": name,
                "status": "prior_acceptance_reused_not_retested",
                "new_source_called": False,
                "production_changed": False,
            }
        )
    for item in contract["interfaces"]:
        result = by_name[item["interface"]]
        status = result["status"]
        if status == "accepted" and not result["source_complete"]:
            status = "accepted_successful_windows_with_source_limitations"
        rows.append(
            {
                "interface": item["interface"],
                "status": status,
                "snapshot_rows": result["snapshot_rows"],
                "source_complete": result["source_complete"],
                "production_changed": False,
            }
        )
    require(len(rows) == 55 and len({r["interface"] for r in rows}) == 55, "remaining_matrix_scope")
    return rows


def package_reports(args):
    import zipfile

    allowed = {
        "remaining-acceptance.json",
        "remaining-progress.json",
        "backup-restore.json",
        "coverage-55.json",
        "inpatient-availability.json",
        "critical-field-audit.json",
        "field-contract-gaps.json",
        "fatal-error.json",
        "execution-stages.json",
    }
    forbidden = {
        "payload",
        "source_key",
        "raw_values",
        "password",
        "token",
        "dsn",
        "connection_string",
    }

    def safe(value):
        if isinstance(value, dict):
            require(not (set(value) & forbidden), "remaining_report_secret_or_payload")
            for child in value.values():
                safe(child)
        elif isinstance(value, list):
            for child in value:
                safe(child)

    files = {}
    for name in sorted(allowed):
        path = args.output / "reports" / name
        if path.is_file():
            content = path.read_bytes()
            safe(json.loads(content))
            files[name] = content
    files["manifest.json"] = (
        json.dumps(
            {
                "package": "cache-remaining-consolidated-result-v1",
                "interfaces_in_matrix": 55,
                "contains_phi": False,
                "contains_raw_values": False,
                "contains_keys": False,
                "scheduled_task_created": False,
                "production_enabled": False,
            },
            indent=2,
        )
        + "\n"
    ).encode()
    files["CHECKSUMS.txt"] = "".join(
        hashlib.sha256(data).hexdigest() + "  " + name + "\n"
        for name, data in sorted(files.items())
    ).encode()
    output = args.output / "cache-remaining-consolidated-result.zip"
    pending = output.with_suffix(".pending")
    with zipfile.ZipFile(pending, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            archive.writestr(name, data)
    os.replace(pending, output)
    return output


def execution_stages(args):
    """物化追加式阶段审计供集中回传；不回传私有配置或源行。"""
    path = args.output / "reports" / "remaining-progress.json"
    if not path.is_file():
        return {"stages": {}}
    value = json.loads(path.read_text(encoding="utf-8"))
    events = path.with_suffix(".jsonl")
    if events.is_file():
        for line in events.read_text(encoding="utf-8").splitlines():
            event = json.loads(line)
            value["stages"][event["key"]] = event["value"]
    return value


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--source-config", type=Path, required=True)
    parser.add_argument("--admin-passfile", type=Path, required=True)
    parser.add_argument("--runtime-passfile", type=Path, required=True)
    parser.add_argument("--pg-bin", type=Path, required=True)
    parser.add_argument("--backend", type=Path, default=ROOT / "backend")
    parser.add_argument("--cohort-file", type=Path)
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--pg-major", type=int, default=16)
    parser.add_argument("--admin-user", default="postgres")
    parser.add_argument("--statement-timeout-seconds", type=int, default=120)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)
    try:
        preflight(args)
        contract, specs = load_combined_profile(args.contract)
        environment = Environment(args, contract, specs)
        from validate_remaining_interfaces import run

        report = run(args, environment=environment, profile=(contract, specs))
        write_json(args.output / "reports/execution-stages.json", execution_stages(args))
        write_json(
            args.output / "reports/coverage-55.json", {"interfaces": coverage(report, contract)}
        )
        write_json(
            args.output / "reports/inpatient-availability.json", cohort_review(args, environment)
        )
        write_json(
            args.output / "reports/critical-field-audit.json",
            critical_field_audit(environment, contract, report["interfaces"]),
        )
        write_json(
            args.output / "reports/field-contract-gaps.json",
            contract_field_gaps(contract),
        )
        output = package_reports(args)
        print(
            json.dumps(
                {
                    "status": "CONSOLIDATED_ACCEPTANCE_COMPLETE_WITH_COVERAGE",
                    "result_zip": str(output),
                    "bytes": output.stat().st_size,
                    "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                    "all_55_interfaces_accepted": False,
                    "production_enabled": False,
                }
            )
        )
        return 0
    except Exception as error:
        from validate_remaining_interfaces import error_metadata

        result = {"status": "STOPPED_PRESERVE_STATE", **error_metadata(error)}
        if hasattr(args, "output") and (args.output / "reports").is_dir():
            write_json(args.output / "reports/fatal-error.json", result)
            try:
                stages = execution_stages(args)
                write_json(args.output / "reports/execution-stages.json", stages)
                partial_contract, _ = load_combined_profile(args.contract)
                partial = []
                for item in partial_contract["interfaces"]:
                    name = item["interface"]
                    relevant = [v for k, v in stages["stages"].items() if f":{name}:" in k]
                    captured = [
                        v["result"]
                        for k, v in stages["stages"].items()
                        if k.startswith(f"snapshot:{name}:")
                        and v.get("status") == "done"
                        and v.get("result", {}).get("status") == "captured"
                    ]
                    partial.append(
                        {
                            "interface": name,
                            "status": "software_blocked_or_pending" if relevant else "not_executed",
                            "source_complete": False,
                            "snapshot_rows": sum(value["rows"] for value in captured),
                        }
                    )
                matrix = coverage({"interfaces": partial}, partial_contract)
                write_json(
                    args.output / "reports/coverage-55.json",
                    {"interfaces": matrix, "partial_counts_not_final": True},
                )
                result["result_zip"] = str(package_reports(args))
            except Exception:
                result["partial_report_packaging"] = "not_completed"
        print(json.dumps(result))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
