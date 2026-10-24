"""人工审核 PG 合成验收的只读结构门禁，不以 revision 大小推断分叉兼容。"""

from __future__ import annotations

import re

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.database.models.qc import QCDefect, QCDefectHistory, SysUser
from app.services.user_scope_owner import UserOwnerUnavailable, resolve_user_owner_schema

TARGET_DB = "medqc_v36_validation_20260924"


class PreflightRejected(RuntimeError):
    """结构不足或 owner 不确定；必须在创建任何合成行前中止。"""


def _check_sql(value):
    value = str(value if value is not None else "").lower().replace('"', "")
    value = re.sub(r"::(?:character varying(?:\(\d+\))?|varchar(?:\(\d+\))?|text)(?:\[\])?", "", value)
    return re.sub(r"[\s()\[\]]", "", value).replace("=anyarray", "in")


def validate_schema(inspector, owner: str | None) -> None:
    if owner not in {"sys", "public"}:
        raise PreflightRejected("账号持久表 owner 不明确或不受信任")
    for schema, model in ((owner, SysUser), ("qc", QCDefect), ("qc", QCDefectHistory)):
        table = model.__table__
        label = f"{schema}.{table.name}"
        if not inspector.has_table(table.name, schema=schema):
            raise PreflightRejected(f"{label} 不存在")
        columns = {row["name"]: row for row in inspector.get_columns(table.name, schema=schema)}
        missing = sorted(set(table.columns.keys()) - columns.keys())
        if missing:
            raise PreflightRejected(f"{label} 缺少模型读取/夹具写入列: {', '.join(missing)}")
        # 新的必填列若无法由 ORM 默认值填充，夹具同样不能安全写入。
        unsupported = sorted(name for name, col in columns.items() if name not in table.columns
                             and not col.get("nullable") and col.get("default") is None
                             and not col.get("identity") and not col.get("computed"))
        if unsupported:
            raise PreflightRejected(f"{label} 存在夹具不能填充的必填列: {', '.join(unsupported)}")
        if inspector.get_pk_constraint(table.name, schema=schema).get("constrained_columns") != ["id"]:
            raise PreflightRejected(f"{label} 缺少 id 单列主键")
    users = {row["name"]: row for row in inspector.get_columns("sys_users", schema=owner)}
    institute = users["institute_id"]
    if (not isinstance(institute["type"], sa.String) or isinstance(institute["type"], sa.Text)
            or institute["type"].length != 128 or institute.get("nullable") is not True
            or institute.get("default") is not None):
        raise PreflightRejected(f"{owner}.sys_users.institute_id 不符合迁移 76 的机构列合同")
    indexes = inspector.get_indexes("sys_users", schema=owner)
    if not any(row.get("name") == "ix_sys_users_institute_department"
               and row.get("column_names") == ["institute_id", "department"]
               and not row.get("unique") for row in indexes):
        raise PreflightRejected(f"{owner}.sys_users 缺少机构/科室联合索引")
    uniques = inspector.get_unique_constraints("sys_users", schema=owner)
    if not any(row.get("column_names") == ["username"] for row in uniques + [r for r in indexes if r.get("unique")]):
        raise PreflightRejected(f"{owner}.sys_users 缺少 username 单列唯一约束")
    checks = {row["name"]: _check_sql(row.get("sqltext"))
              for row in inspector.get_check_constraints("qc_defects", schema="qc")}
    for constraint in QCDefect.__table__.constraints:
        if isinstance(constraint, sa.CheckConstraint) and checks.get(constraint.name) != _check_sql(constraint.sqltext):
            raise PreflightRejected(f"qc.qc_defects.{constraint.name} 缺失或合同漂移")


def preflight(engine) -> str:
    """仅连接指定隔离库，整个预检事务只读；返回经应用 resolver 核实的 owner。"""
    with engine.connect() as conn, conn.begin():
        conn.execute(sa.text("SET TRANSACTION READ ONLY"))
        if conn.execute(sa.text("SELECT current_database()")).scalar_one() != TARGET_DB:
            raise PreflightRejected("连接库不是明确授权的合成隔离库")
        if conn.execute(sa.text("SELECT current_schema()")).scalar_one() != "qc":
            raise PreflightRejected("缺陷模型的当前 schema 不是 qc")
        with Session(bind=conn) as session:
            try:
                owner = resolve_user_owner_schema(session)
            except UserOwnerUnavailable as exc:
                raise PreflightRejected(f"账号 owner 无法确定: {exc}") from exc
        validate_schema(sa.inspect(conn), owner)
    return owner
