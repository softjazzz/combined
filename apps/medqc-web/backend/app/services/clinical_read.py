"""临床只读入口使用 Bundle 的来源；不改变连接池、ORM元数据或写入会话。"""

import re
from typing import Any

from sqlalchemy import MetaData, Table
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Query, Session, aliased


def clinical_read_schema() -> str | None:
    from .bundles.assembly import _default_source_schema

    return "cdm" if _default_source_schema() == "cdm" else None


def clinical_query(session: Session, *entities: Any) -> Query:
    query = session.query(*entities)
    if clinical_read_schema():
        query = query.execution_options(schema_translate_map={None: "cdm"})
    return query


def clinical_read_table(table: Table) -> Table:
    if clinical_read_schema() and table.schema is None:
        return table.to_metadata(MetaData(), schema="cdm")
    return table


def clinical_read_model(model: type[Any]) -> Any:
    """混合临床/质控 JOIN 只限定临床模型，不迁移质控结果的读取来源。"""
    if clinical_read_schema():
        return aliased(model, clinical_read_table(model.__table__), adapt_on_names=True)
    return model


def clinical_table_sql(table_name: str) -> str:
    # 调用者只传代码维护的表名，仍检查标识符，不能插入任意SQL或指定其他schema。
    if not re.fullmatch(r"[a-z][a-z0-9_]*", table_name):
        raise ValueError("invalid_clinical_table_name")
    return f"cdm.{table_name}" if clinical_read_schema() else table_name


def optional_frontpage_unavailable(error: BaseException | None) -> bool:
    """仅首页展示读可隔离缺表与拒读，其他数据库故障继续抛出。"""
    return isinstance(error, ProgrammingError) and getattr(error.orig, "pgcode", None) in {"42P01", "42501"}


def is_synced_clinical_table(table_name: str) -> bool:
    from .etl_sync import _CDM_SYNC_TABLE_NAMES

    return table_name in _CDM_SYNC_TABLE_NAMES or table_name in {
        "medical_records", "medical_documents", "hospitalization_status_projection",
    }


def clinical_adapter_table(table_name: str) -> str:
    """通用适配器只对未限定的临床 SELECT 指定来源，保留其他 owner。"""
    if clinical_read_schema() and "." not in table_name and is_synced_clinical_table(table_name):
        return clinical_table_sql(table_name)
    return table_name
