"""只为部署初始化空任务owner；不改动已有任务或放宽导入结构合同。"""

import json
from pathlib import Path

from psycopg2 import sql


EXTRAS = {
    "execution_mode": ("character varying(20)", "batch"),
    "draft_ids_json": ("text", "[]"),
    "rule_count": ("integer", 1),
}


def expected_job_schema():
    return json.loads(
        (Path(__file__).parent / "runtime-job-schema.json").read_text(encoding="utf-8")
    )


def ensure_job_owner(cur, transfer):
    expected = expected_job_schema()
    if expected["schema"] != "qc" or expected["name"] != "custom_qc_batch_jobs":
        raise ValueError("invalid_job_owner_template")
    target = transfer.table_sql("qc", "custom_qc_batch_jobs")
    cur.execute("SELECT to_regclass('qc.custom_qc_batch_jobs')")
    exists = cur.fetchone()[0] is not None
    if not exists:
        transfer.create_material(cur, expected)
        # 这三列未由正式运行时写入，必须有源库已核实的服务器默认值。
        for name, value in {
            **{k: v[1] for k, v in EXTRAS.items()},
            "job_kind": "leaf",
        }.items():
            cur.execute(
                sql.SQL("ALTER TABLE {} ALTER COLUMN {} SET DEFAULT {}").format(
                    target, transfer.ident(name), sql.Literal(value)
                )
            )
        return True

    actual = transfer.descriptor(cur, "qc", "custom_qc_batch_jobs")
    expected_map = {c["name"]: c for c in expected["columns"]}
    actual_map = {c["name"]: c for c in actual["columns"]}
    if (
        actual["primary"] != expected["primary"]
        or actual_map.keys() - expected_map.keys()
    ):
        raise ValueError("job_owner_schema_mismatch")
    missing = expected_map.keys() - actual_map.keys()
    if missing - EXTRAS.keys():
        raise ValueError("job_owner_schema_mismatch")
    nullable_job_kind = False
    for name in actual_map.keys() & expected_map.keys():
        if actual_map[name] == expected_map[name]:
            continue
        if name == "job_kind" and actual_map[name] == {
            **expected_map[name],
            "notnull": True,
        }:
            nullable_job_kind = True
        else:
            raise ValueError("job_owner_schema_mismatch")
    if not missing and not nullable_job_kind:
        transfer.compatible_columns(expected["columns"], actual["columns"])
        return False

    cur.execute(sql.SQL("LOCK TABLE {} IN ACCESS EXCLUSIVE MODE NOWAIT").format(target))
    cur.execute(sql.SQL("SELECT 1 FROM {} LIMIT 1").format(target))
    if cur.fetchone() is not None:
        raise ValueError("nonempty_job_schema_repair_refused")
    for name, (kind, default) in EXTRAS.items():
        if name in missing:
            cur.execute(
                sql.SQL("ALTER TABLE {} ADD COLUMN {} {} DEFAULT {} NOT NULL").format(
                    target,
                    transfer.ident(name),
                    sql.SQL(transfer.safe_type(kind)),
                    sql.Literal(default),
                )
            )
    if nullable_job_kind:
        cur.execute(
            sql.SQL("ALTER TABLE {} ALTER COLUMN job_kind DROP NOT NULL").format(target)
        )
    repaired = transfer.descriptor(cur, "qc", "custom_qc_batch_jobs")
    transfer.compatible_columns(expected["columns"], repaired["columns"])
    return True
