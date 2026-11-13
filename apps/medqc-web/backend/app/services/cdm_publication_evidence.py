"""同一 CDM 事务内读取发布回执；不推定上游覆盖或发布正文哈希。"""

import hashlib
import json
from pathlib import Path

from sqlalchemy import inspect, text

from .case_material_snapshot import MaterialSnapshotError

KEYS = json.loads(
    Path(__file__).with_name("cdm_publication_keys.json").read_text(encoding="utf-8")
)
COLUMNS = {
    "identity": ("epoch",),
    "contract": (
        "interface_name",
        "source_epoch",
        "mapping_hash",
        "activation",
        "bootstrap_required",
    ),
    "receipt": (
        "source_epoch",
        "interface_name",
        "source_key_hash",
        "generation",
        "mapping_hash",
        "activation",
        "target_key_hash",
    ),
    "operation": (
        "operation_id",
        "source_epoch",
        "interface_name",
        "mapping_hash",
        "queue_hash",
        "scope_hash",
        "commit_order",
    ),
    "operation_item": ("operation_id", "source_key_hash", "generation"),
}


def target_hash(value):
    # 与同步 domain.canonical_json 一致；不以 default=str 猜测特殊类型。
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def verified_receipt(interface, contract, receipt, operations):
    if not isinstance(receipt.get("generation"), int) or receipt["generation"] < 1:
        return False
    if any(
        str(receipt[key]) != str(contract[key])
        for key in ("source_epoch", "mapping_hash", "activation")
    ):
        return False
    return any(
        str(op["source_epoch"]) == str(contract["source_epoch"])
        and op["interface_name"] == interface
        and op["mapping_hash"] == contract["mapping_hash"]
        and op["queue_hash"]
        == target_hash([contract["mapping_hash"], contract["activation"]])
        for op in operations
    )


def read_publication(connection, tables):
    """元数据缺失/未授权如实记未知；不换账号，不额外建立连接。"""
    exists = connection.execute(
        text("SELECT EXISTS(SELECT 1 FROM pg_namespace WHERE nspname='sync_delivery')")
    ).scalar_one()
    if not exists:
        return {"status": "metadata_unavailable", "rows": {}}
    if not connection.execute(
        text("SELECT has_schema_privilege(current_user,'sync_delivery','USAGE')")
    ).scalar_one():
        return {"status": "metadata_permission_unconfirmed", "rows": {}}
    inspector = inspect(connection)
    for table, columns in COLUMNS.items():
        if not inspector.has_table(table, schema="sync_delivery"):
            return {"status": "metadata_unavailable", "rows": {}}
        if not set(columns).issubset(
            {c["name"] for c in inspector.get_columns(table, schema="sync_delivery")}
        ):
            return {"status": "metadata_contract_unconfirmed", "rows": {}}
        for column in columns:
            allowed = connection.execute(
                text(
                    "SELECT has_schema_privilege(current_user,'sync_delivery','USAGE') AND "
                    "has_column_privilege(current_user,:table,:column,'SELECT')"
                ),
                {"table": "sync_delivery." + table, "column": column},
            ).scalar_one()
            if not allowed:
                return {"status": "metadata_permission_unconfirmed", "rows": {}}
    epochs = (
        connection.execute(text("SELECT epoch FROM sync_delivery.identity LIMIT 2"))
        .scalars()
        .all()
    )
    if len(epochs) != 1:
        raise MaterialSnapshotError("material_publication_identity_conflict")
    result = {
        "status": "metadata_available",
        "target_epoch": str(epochs[0]),
        "rows": {},
    }
    for table, rows in tables.items():
        key_contract = KEYS.get(table)
        if not key_contract or not rows:
            continue
        interface = key_contract["interface"]
        contract = (
            connection.execute(
                text(
                    "SELECT source_epoch,mapping_hash,activation,bootstrap_required "
                    "FROM sync_delivery.contract WHERE interface_name=:interface"
                ),
                {"interface": interface},
            )
            .mappings()
            .one_or_none()
        )
        entries = []
        for row in rows:
            entry = {"status": "receipt_unverified"}
            entries.append(entry)
            if contract is None or any(
                key not in row or row[key] is None for key in key_contract["keys"]
            ):
                continue
            try:
                digest = target_hash({key: row[key] for key in key_contract["keys"]})
            except (TypeError, ValueError):
                continue
            matches = (
                connection.execute(
                    text(
                        "SELECT source_epoch,source_key_hash,generation,mapping_hash,activation,target_key_hash "
                        "FROM sync_delivery.receipt WHERE interface_name=:interface AND target_key_hash=:key LIMIT 2"
                    ),
                    {"interface": interface, "key": digest},
                )
                .mappings()
                .all()
            )
            if not matches:
                continue
            if len(matches) != 1:
                raise MaterialSnapshotError("material_publication_identity_conflict")
            receipt = matches[0]
            operations = (
                connection.execute(
                    text(
                        "SELECT o.operation_id,o.source_epoch,o.interface_name,o.mapping_hash,o.queue_hash,o.scope_hash,o.commit_order "
                        "FROM sync_delivery.operation o JOIN sync_delivery.operation_item i ON i.operation_id=o.operation_id "
                        "WHERE i.source_key_hash=:source_key AND i.generation=:generation "
                        "AND o.interface_name=:interface AND o.source_epoch=:epoch AND o.mapping_hash=:mapping "
                        "AND o.queue_hash=:queue ORDER BY o.commit_order DESC LIMIT 1"
                    ),
                    {
                        "source_key": receipt["source_key_hash"],
                        "generation": receipt["generation"],
                        "interface": interface,
                        "epoch": contract["source_epoch"],
                        "mapping": contract["mapping_hash"],
                        "queue": target_hash(
                            [contract["mapping_hash"], contract["activation"]]
                        ),
                    },
                )
                .mappings()
                .all()
            )
            if not verified_receipt(interface, contract, receipt, operations):
                raise MaterialSnapshotError("material_publication_version_conflict")
            entry.update(
                status="receipt_verified",
                target_key_hash=digest,
                receipt={**dict(receipt), "source_epoch": str(receipt["source_epoch"])},
                operation={
                    **dict(operations[0]),
                    "source_epoch": str(operations[0]["source_epoch"]),
                    "operation_id": str(operations[0]["operation_id"]),
                },
                bootstrap_required=contract["bootstrap_required"],
                coverage="unknown",
            )
        result["rows"][table] = entries
    return result
