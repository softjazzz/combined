"""只读核验第二批快照与候选投影；不连接Caché，不创建CDM或任务。"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
from collections import Counter, defaultdict
from datetime import date
from itertools import combinations
from pathlib import Path

from major_document_transform import convert_value
from periop_transform import ALLOWED, ContractError, decode_snapshot, ordered_hash, project_row

DATABASE = "medqc_periop_acceptance_20261031104123"
ROOT = Path(__file__).resolve().parents[1]


def compare_rounds(first: Counter, second: Counter) -> bool:
    return first == second


def initial_metrics(contract):
    return {
        item["interface"]: {
            "rows": 0,
            "projected": 0,
            "source_duplicates": 0,
            "target_duplicates": 0,
            "errors": Counter(),
            "source_keys": set(),
            "target_keys": set(),
        }
        for item in contract["interfaces"]
    }


def evaluate(connection, contract):
    items = {item["interface"]: item for item in contract["interfaces"]}
    if set(items) != ALLOWED or contract.get("source_database") != DATABASE:
        raise ContractError("periop_contract_scope")
    with connection.cursor() as cursor:
        cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        cursor.execute(
            "SELECT current_database(),current_user,current_setting('transaction_read_only')"
        )
        if cursor.fetchone() != (DATABASE, "medqc_sync", "on"):
            raise ContractError("readonly_database_identity")
        cursor.execute(
            "SELECT batch_id,interface_name,source_date,round_no,status,coalesce(row_count,0),"
            "coalesce(result_set_count,0) FROM cache_raw.snapshot_batch ORDER BY batch_id"
        )
        batch_rows = cursor.fetchall()
        batches = {row[0]: row for row in batch_rows}
        expected = {
            (item["interface"], date.fromisoformat(window["date"]), number): window
            for item in items.values()
            for window in item["source_window_status"]
            for number in (1, 2)
            if number == 1 or window["status"] != "failed"
        }
        observed = {(row[1], row[2], row[3]) for row in batch_rows}
        if len(batches) != 95 or observed != set(expected):
            raise ContractError("snapshot_batch_inventory")
        for row in batch_rows:
            window = expected[(row[1], row[2], row[3])]
            if row[4] != window["status"] or row[5] != window["rows"]:
                raise ContractError("snapshot_batch_changed")
            if row[6] != int(row[4] != "failed"):
                raise ContractError("snapshot_batch_result_count")
        cursor.execute(
            "SELECT batch_id,result_set_index,columns_json,column_types_json,row_count "
            "FROM cache_raw.result_set ORDER BY 1,2"
        )
        sets = {(row[0], row[1]): row for row in cursor.fetchall()}
        if len(sets) != 88:
            raise ContractError("result_set_inventory")
        if any(
            sum(key[0] == batch_id for key in sets) != row[6] for batch_id, row in batches.items()
        ):
            raise ContractError("result_set_batch_coverage")
        for (batch_id, _index), result in sets.items():
            name = batches[batch_id][1]
            item = items[name]
            if (
                result[2] != item["ordered_source_columns"]
                or len(result[3]) != len(result[2])
                or result[4] != batches[batch_id][5]
            ):
                raise ContractError("result_set_schema_or_count")
        cursor.execute(
            "SELECT interface_name,schema_hash,column_names_json,schema_hash_version,column_count "
            "FROM sync_ops.source_schema"
        )
        schemas = cursor.fetchall()
        if len(schemas) != 16:
            raise ContractError("source_schema_inventory")
        for name, digest, columns, version, column_count in schemas:
            if (
                name not in items
                or columns != items[name]["ordered_source_columns"]
                or digest != items[name]["schema_hash"]
                or ordered_hash(columns) != digest
                or version != "ordered-column-names-v1"
                or column_count != len(columns)
            ):
                raise ContractError("source_schema_contract_mismatch")
        cursor.execute("SELECT event,status,count(*) FROM sync_ops.ingest_audit GROUP BY 1,2")
        audit = [{"event": row[0], "status": row[1], "count": row[2]} for row in cursor.fetchall()]
    metrics = initial_metrics(contract)
    counts = Counter()
    hashes = defaultdict(Counter)
    profiles = {}
    with connection.cursor(name="periop_readonly_preflight") as cursor:
        cursor.execute(
            "SELECT batch_id,result_set_index,row_number,values_json,row_hash,schema_hash "
            "FROM cache_raw.snapshot_row ORDER BY batch_id,result_set_index,row_number"
        )
        while chunk := cursor.fetchmany(1000):
            for batch_id, index, ordinal, values, row_hash, schema_hash in chunk:
                if (batch_id, index) not in sets:
                    raise ContractError("snapshot_without_result_set")
                batch = batches[batch_id]
                name, day, number = batch[1], batch[2], batch[3]
                counts[(batch_id, index)] += 1
                if ordinal != counts[(batch_id, index)]:
                    raise ContractError("snapshot_row_gap")
                item = items[name]
                payload = decode_snapshot(
                    contract, name, sets[(batch_id, index)][2], values, schema_hash, row_hash
                )
                hashes[(name, day, number)][row_hash] += 1
                if number != 1:
                    continue
                state = metrics[name]
                state["rows"] += 1
                key = tuple(payload[field] for field in item["raw_key_fields"])
                if any(not isinstance(value, str) or not value.strip() for value in key):
                    state["errors"]["source_key_not_nonempty_text"] += 1
                else:
                    state["source_duplicates"] += int(key in state["source_keys"])
                    state["source_keys"].add(key)
                try:
                    projected = project_row(contract, name, payload)
                    target_key = tuple(projected[field] for field in item["target_primary_key"])
                    state["projected"] += 1
                    state["target_duplicates"] += int(target_key in state["target_keys"])
                    state["target_keys"].add(target_key)
                except ContractError as error:
                    state["errors"][error.location] += 1
                for field, value in payload.items():
                    profile = profiles.setdefault(
                        (name, field),
                        {
                            "interface": name,
                            "field": field,
                            "raw_only": field in item["raw_only_source_columns"],
                            "rows": 0,
                            "nulls": 0,
                            "empty_strings": 0,
                            "nonempty": 0,
                            "temporal_parse_errors": 0,
                        },
                    )
                    profile["rows"] += 1
                    profile["nulls"] += int(value is None)
                    empty = isinstance(value, str) and not value.strip()
                    profile["empty_strings"] += int(empty)
                    profile["nonempty"] += int(value is not None and not empty)
                    if (
                        value is not None
                        and not empty
                        and field.lower().endswith(("datetime", "_date", "_time"))
                    ):
                        try:
                            convert_value(value, "datetime")
                        except ContractError:
                            profile["temporal_parse_errors"] += 1
    if sum(counts.values()) != 18730 or any(
        counts[key] != result[4] for key, result in sets.items()
    ):
        raise ContractError("snapshot_rows_incomplete")
    result = []
    date_observation = []
    for name, item in items.items():
        state = metrics[name]
        for window in item["source_window_status"]:
            if window["status"] != "failed":
                day = date.fromisoformat(window["date"])
                if not compare_rounds(hashes[(name, day, 1)], hashes[(name, day, 2)]):
                    state["errors"]["round_snapshot_multiset_changed"] += 1
        if state["rows"] != item["expected_first_round_rows"]:
            raise ContractError("first_round_rows_changed")
        status = item["source_state"]
        if state["rows"]:
            status = (
                "blocked_conversion"
                if state["errors"]
                else "blocked_source_key_collision"
                if state["source_duplicates"]
                else "blocked_target_key_collision"
                if state["target_duplicates"]
                else "candidate_ready_partial_source"
                if item["source_state"] == "partial_source"
                else "candidate_ready"
            )
        result.append(
            {
                "interface": name,
                "source_rows": state["rows"],
                "projected_in_memory": state["projected"],
                "source_unique_keys": len(state["source_keys"]),
                "target_unique_keys": len(state["target_keys"]),
                "source_duplicates": state["source_duplicates"],
                "target_duplicates": state["target_duplicates"],
                "status": status,
                "error_counts": json.dumps(state["errors"], sort_keys=True),
                "target_catalog_verified": False,
            }
        )
        days = [date.fromisoformat(window["date"]) for window in item["source_window_status"]]
        overlaps = []
        for first, second in combinations(days, 2):
            if (
                expected.get((name, first, 1), {}).get("status") == "failed"
                or expected.get((name, second, 1), {}).get("status") == "failed"
            ):
                continue
            overlaps.append(sum((hashes[(name, first, 1)] & hashes[(name, second, 1)]).values()))
        date_observation.append(
            {
                "interface": name,
                "date_semantics": "unverified",
                "compared_date_pairs": len(overlaps),
                "identical_full_rows_across_dates": sum(overlaps),
            }
        )
    audit_report = {
        "batches": len(batches),
        "audit_events": sum(row["count"] for row in audit),
        "events": audit,
        "cache_invocations_cannot_be_inferred_from_audit": True,
        "audit_is_event_history_not_running_batch_status": True,
    }
    return result, list(profiles.values()), date_observation, audit_report


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("x", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]) if rows else [])
        writer.writeheader()
        writer.writerows(rows)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True, choices=(DATABASE,))
    parser.add_argument("--passfile", type=Path, required=True)
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    connection = None
    try:
        if args.output.exists() or not args.passfile.is_absolute() or not args.passfile.is_file():
            raise ContractError("new_output_and_existing_passfile_required")
        if os.environ.get("PGPASSWORD"):
            raise ContractError("pgpassword_overrides_passfile")
        import psycopg2

        connection = psycopg2.connect(
            host="127.0.0.1",
            port=args.port,
            dbname=args.database,
            user="medqc_sync",
            passfile=str(args.passfile),
            connect_timeout=10,
            options="-c default_transaction_read_only=on",
            application_name="medqc_periop_mapping_preflight",
        )
        contract = json.loads(
            (ROOT / "contracts/periop-acceptance-contracts.json").read_text(encoding="utf-8")
        )
        rows, profiles, dates, audit = evaluate(connection, contract)
        args.output.mkdir(parents=True)
        write_csv(args.output / "projection-preflight.csv", rows)
        write_csv(args.output / "source-field-completeness.csv", profiles)
        write_csv(args.output / "date-observations.csv", dates)
        (args.output / "audit-review.json").write_text(
            json.dumps(audit, indent=2) + "\n", encoding="utf-8"
        )
        (args.output / "manifest.json").write_text(
            json.dumps(
                {
                    "database": DATABASE,
                    "readonly": True,
                    "interfaces": 17,
                    "source_rows": sum(row["source_rows"] for row in rows),
                    "cdm_written": False,
                    "cache_accessed": False,
                    "actual_target_catalog_verified": False,
                    "contains_phi": False,
                    "contains_raw_values": False,
                    "contains_keys": False,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print("PERIOP_READONLY_PREFLIGHT_COMPLETE: no CDM data written")
        return 0
    except Exception as error:
        code = getattr(error, "pgcode", None)
        code = code if isinstance(code, str) and re.fullmatch(r"[0-9A-Z]{5}", code) else None
        location = (
            error.location if isinstance(error, ContractError) else "periop_readonly_preflight"
        )
        print(f"failed type={type(error).__name__} sqlstate={code} location={location}")
        return 1
    finally:
        if connection is not None:
            connection.rollback()
            connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
