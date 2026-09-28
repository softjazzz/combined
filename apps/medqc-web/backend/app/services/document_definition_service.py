"""正式文书定义列表与原子批量导入 owner。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable
from uuid import uuid4

from sqlalchemy import func, insert, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from ..database.connection import SessionLocal
from ..database.models.qc import QCDocumentDefinition
from .document_definition_excel_service import ParsedDocumentDefinition

MAX_PAGE_SIZE = 100
MAX_QUERY_LENGTH = 200

_TABLE = QCDocumentDefinition.__table__
_COLUMNS = (
    _TABLE.c.id,
    _TABLE.c.code,
    _TABLE.c.name,
    _TABLE.c.category,
    _TABLE.c.template_content,
    _TABLE.c.import_batch_id,
    _TABLE.c.created_by,
    _TABLE.c.created_at,
)


class DocumentDefinitionInvalid(ValueError):
    """调用参数无效。"""


class DocumentDefinitionConflict(ValueError):
    """编码已存在；整批不得覆盖。"""

    code = "document_definition_code_conflict"

    def __init__(self, codes: Iterable[str]):
        self.codes = sorted(set(codes))
        super().__init__("文书编码已存在，拒绝覆盖")


class DocumentDefinitionUnavailable(RuntimeError):
    """存储不可用，对外统一脱敏。"""


def _require_factory() -> Any:
    if SessionLocal is None:
        raise DocumentDefinitionUnavailable("文书定义存储不可用")
    return SessionLocal


def _positive_int(value: Any, *, field: str, maximum: int | None = None) -> int:
    if type(value) is not int or value < 1 or (maximum is not None and value > maximum):
        raise DocumentDefinitionInvalid(f"{field} 无效")
    return value


def _actor(value: Any) -> str:
    if not isinstance(value, str):
        raise DocumentDefinitionInvalid("当前用户缺少有效身份")
    actor = value.strip()
    if not actor or len(actor) > 64:
        raise DocumentDefinitionInvalid("当前用户缺少有效身份")
    return actor


def _query(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise DocumentDefinitionInvalid("q 无效")
    normalized = value.strip()
    if len(normalized) > MAX_QUERY_LENGTH:
        raise DocumentDefinitionInvalid("q 不能超过 200 个字符")
    return normalized or None


def _literal_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _item(row: Any) -> dict[str, Any]:
    return {column.name: getattr(row, column.name) for column in _COLUMNS}


def list_document_definitions(
    *, page: int, page_size: int, q: str | None = None,
) -> dict[str, Any]:
    page = _positive_int(page, field="page")
    page_size = _positive_int(page_size, field="page_size", maximum=MAX_PAGE_SIZE)
    q = _query(q)
    predicate = None
    if q is not None:
        predicate = func.lower(_TABLE.c.name).like(
            f"%{_literal_like(q.lower())}%", escape="\\",
        )
    factory = _require_factory()
    try:
        with factory() as session:
            with session.begin():
                if session.get_bind().dialect.name == "postgresql":
                    session.execute(text(
                        "SELECT pg_advisory_xact_lock_shared("
                        "hashtext('qc_document_definitions:import'))"
                    ))
                count_query = select(func.count(_TABLE.c.id))
                rows_query = select(*_COLUMNS)
                if predicate is not None:
                    count_query = count_query.where(predicate)
                    rows_query = rows_query.where(predicate)
                total = int(session.execute(count_query).scalar_one())
                rows = session.execute(
                    rows_query
                    .order_by(_TABLE.c.created_at.desc(), _TABLE.c.code.asc(), _TABLE.c.id.asc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                ).all()
    except SQLAlchemyError as exc:
        raise DocumentDefinitionUnavailable("文书定义读取失败") from exc
    return {
        "items": [_item(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def _lock_import(session: Any) -> None:
    if session.get_bind().dialect.name == "postgresql":
        session.execute(text("SELECT pg_advisory_xact_lock(hashtext('qc_document_definitions:import'))"))


def import_document_definitions(
    *, actor: str, definitions: Iterable[ParsedDocumentDefinition],
) -> dict[str, Any]:
    actor = _actor(actor)
    definitions = tuple(definitions)
    if not definitions:
        raise DocumentDefinitionInvalid("至少导入一条文书定义")
    codes = [entry.code for entry in definitions]
    if len(codes) != len(set(codes)):
        raise DocumentDefinitionInvalid("导入文件包含重复文书编码")
    batch_id = str(uuid4())
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    values = [
        {
            "id": str(uuid4()),
            "code": entry.code,
            "name": entry.name,
            "category": entry.category,
            "template_content": entry.template_content,
            "import_batch_id": batch_id,
            "created_by": actor,
            "created_at": now,
        }
        for entry in definitions
    ]
    factory = _require_factory()
    try:
        with factory() as session:
            with session.begin():
                _lock_import(session)
                existing = session.execute(
                    select(_TABLE.c.code).where(_TABLE.c.code.in_(codes)).order_by(_TABLE.c.code.asc())
                ).scalars().all()
                if existing:
                    raise DocumentDefinitionConflict(existing)
                session.execute(insert(_TABLE), values)
    except DocumentDefinitionConflict:
        raise
    except IntegrityError as exc:
        constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        message = str(exc.orig).lower()
        if (
            constraint == "uq_qc_document_definitions_code"
            or "unique constraint failed: qc_document_definitions.code" in message
        ):
            raise DocumentDefinitionConflict(codes) from exc
        raise DocumentDefinitionUnavailable("文书定义导入失败") from exc
    except SQLAlchemyError as exc:
        raise DocumentDefinitionUnavailable("文书定义导入失败") from exc
    return {
        "import_batch_id": batch_id,
        "imported_count": len(values),
        "items": values,
    }
