"""注册科室只读目录：复用临床读取 owner，仅返回科室选项，不返回患者数据。"""

import hashlib
import os

import sqlalchemy as sa

from .clinical_read import clinical_read_schema
from .defect_rectification_service import RectificationError


def registration_departments(session):
    schema = clinical_read_schema()
    # 部署级范围，不采用公开请求参数；兼容已有双源同步目标机构配置。
    target_institute = (
        os.getenv("REGISTRATION_INSTITUTE_ID")
        or os.getenv("HOMOLOGY_TARGET_INSTITUTE_ID")
        or ""
    ).strip()
    inspector = sa.inspect(session.connection())
    pairs = set()
    for name, fields in (
        ("mr", ("discharge_dept_name", "admission_dept_name")),
        ("inpat_registration", ("discharge_dept_name", "admission_dept_name")),
        ("discharge_record", ("dept_name",)),
        ("admission_record", ("dept_name",)),
    ):
        if not inspector.has_table(name, schema=schema):
            continue
        columns = {
            column["name"] for column in inspector.get_columns(name, schema=schema)
        }
        if "institute_id" not in columns:
            continue
        table = sa.table(name, *(sa.column(col) for col in columns), schema=schema)
        for field in fields:
            if field not in columns:
                continue
            institute, department = (
                sa.func.trim(table.c.institute_id),
                sa.func.trim(table.c[field]),
            )
            query = sa.select(institute, department).where(
                institute.is_not(None),
                institute != "",
                department.is_not(None),
                department.not_in(("", "-", "未知", "未返回")),
            )
            if target_institute:
                query = query.where(institute == target_institute)
            if "is_deleted" in columns:
                query = query.where(
                    sa.func.coalesce(sa.cast(table.c.is_deleted, sa.String), "0").in_(
                        ("0", "false", "False")
                    )
                )
            rows = session.execute(query.distinct().limit(1001)).all()
            if len(rows) > 1000:
                raise RectificationError("科室目录超出可选范围，请联系管理员配置", 503)
            pairs.update(rows)
    if not pairs:
        raise RectificationError("本机尚无可用科室，请联系管理员同步科室数据", 503)
    return [
        {
            "key": hashlib.sha256(f"{institute}\0{department}".encode()).hexdigest(),
            "name": department,
            "label": department
            if sum(other == department for _, other in pairs) == 1
            else f"{department}（{institute}）",
            "institute_id": institute,
        }
        for institute, department in sorted(pairs)
    ]
