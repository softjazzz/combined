"""客户样本同步水位仓储。

仓储只暴露成功写入后的显式推进方法，不接收或推断失败状态。调用方必须在
本地业务数据写入成功后，才调用 ``mark_success`` 或 ``mark_full_sync``。
"""

from __future__ import annotations

import hashlib
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Mapping, NamedTuple, Optional, Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session


TABLE_NAME = "custom_qc_sample_sync_cursors"
SUPPORTED_STRATEGIES = frozenset(
    {"updated_at", "append_only_record_time", "full_visit_reload"}
)


class VisitKey(NamedTuple):
    institute_id: str
    patient_id: str
    visit_id: str


class CursorKey(NamedTuple):
    source_identity: str
    institute_id: str
    patient_id: str
    visit_id: str
    table_name: str


@dataclass(frozen=True)
class SampleSyncCursor:
    id: str
    source_identity: str
    institute_id: str
    patient_id: str
    visit_id: str
    table_name: str
    strategy: str
    watermark_column: Optional[str]
    watermark_value: Optional[datetime]
    last_success_at: Optional[datetime]
    last_full_sync_at: Optional[datetime]
    source_row_count: int
    content_signature: Optional[str]
    last_job_id: Optional[str]
    schema_version: str
    created_at: datetime
    updated_at: datetime

    @property
    def key(self) -> CursorKey:
        return CursorKey(
            self.source_identity,
            self.institute_id,
            self.patient_id,
            self.visit_id,
            self.table_name,
        )


def build_source_identity(
    *,
    host: str,
    port: int | str,
    database: str,
    schema: str,
) -> str:
    """生成不含账号、密码和连接串的稳定数据源标识。"""

    normalized_host = str(host or "").strip().lower()
    normalized_port = str(port or "").strip()
    normalized_database = str(database or "").strip().lower()
    normalized_schema = str(schema or "").strip().lower()
    if not all(
        (normalized_host, normalized_port, normalized_database, normalized_schema)
    ):
        raise ValueError("host、port、database、schema 均不能为空")
    raw_identity = (
        f"{normalized_host}:{normalized_port}/"
        f"{normalized_database}:{normalized_schema}"
    )
    return hashlib.sha256(raw_identity.encode("utf-8")).hexdigest()[:32]


def build_cursor_table(*, schema: Optional[str] = None) -> sa.Table:
    metadata = sa.MetaData()
    return sa.Table(
        TABLE_NAME,
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_identity", sa.String(128), nullable=False),
        sa.Column("institute_id", sa.String(128), nullable=False),
        sa.Column("patient_id", sa.String(128), nullable=False),
        sa.Column("visit_id", sa.String(128), nullable=False),
        sa.Column("table_name", sa.String(128), nullable=False),
        sa.Column("strategy", sa.String(32), nullable=False),
        sa.Column("watermark_column", sa.String(128)),
        sa.Column("watermark_value", sa.DateTime(timezone=True)),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("last_full_sync_at", sa.DateTime(timezone=True)),
        sa.Column("source_row_count", sa.Integer, nullable=False, default=0),
        sa.Column("content_signature", sa.String(128)),
        sa.Column("last_job_id", sa.String(36)),
        sa.Column("schema_version", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "source_identity",
            "institute_id",
            "patient_id",
            "visit_id",
            "table_name",
            name="uq_sample_sync_cursor_source_visit_table",
        ),
        schema=schema,
    )


def _default_schema() -> Optional[str]:
    return "qc" if os.getenv("DB_SCHEMA_MODE", "single").strip().lower() == "split" else None


def _required_text(value: object, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} 不能为空")
    return text


def _validated_strategy(value: object) -> str:
    strategy = _required_text(value, "strategy")
    if strategy not in SUPPORTED_STRATEGIES:
        supported = "、".join(sorted(SUPPORTED_STRATEGIES))
        raise ValueError(f"strategy 必须是：{supported}")
    return strategy


def _normalize_visit_key(value: VisitKey | Sequence[str]) -> VisitKey:
    if isinstance(value, VisitKey):
        raw = value
    else:
        if len(value) != 3:
            raise ValueError("visit_key 必须包含 institute_id、patient_id、visit_id")
        raw = VisitKey(str(value[0]), str(value[1]), str(value[2]))
    return VisitKey(
        _required_text(raw.institute_id, "institute_id"),
        _required_text(raw.patient_id, "patient_id"),
        _required_text(raw.visit_id, "visit_id"),
    )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: object) -> Optional[datetime]:
    if value is None:
        return None
    if not isinstance(value, datetime):
        raise TypeError(f"期望 datetime，实际为 {type(value).__name__}")
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class SampleSyncCursorRepository:
    """在调用方事务中批量读取并显式推进同步水位。"""

    def __init__(
        self,
        session: Session,
        *,
        schema: Optional[str] = None,
        table: Optional[sa.Table] = None,
    ) -> None:
        self._session = session
        self._table = (
            table
            if table is not None
            else build_cursor_table(
                schema=_default_schema() if schema is None else schema
            )
        )

    @property
    def table(self) -> sa.Table:
        return self._table

    def get_many(
        self,
        *,
        source_identity: str,
        visit_keys: Iterable[VisitKey | Sequence[str]],
        table_names: Iterable[str],
    ) -> Mapping[CursorKey, SampleSyncCursor]:
        source = _required_text(source_identity, "source_identity")
        visits = tuple(dict.fromkeys(_normalize_visit_key(item) for item in visit_keys))
        tables = tuple(
            dict.fromkeys(_required_text(item, "table_name") for item in table_names)
        )
        if not visits or not tables:
            return {}

        visit_tuple = sa.tuple_(
            self._table.c.institute_id,
            self._table.c.patient_id,
            self._table.c.visit_id,
        )
        rows = (
            self._session.execute(
                sa.select(self._table).where(
                    self._table.c.source_identity == source,
                    visit_tuple.in_(visits),
                    self._table.c.table_name.in_(tables),
                )
            )
            .mappings()
            .all()
        )
        cursors = (self._from_row(row) for row in rows)
        return {cursor.key: cursor for cursor in cursors}

    def mark_success(
        self,
        *,
        source_identity: str,
        visit_key: VisitKey | Sequence[str],
        table_name: str,
        strategy: str,
        schema_version: str,
        watermark_column: Optional[str] = None,
        watermark_value: Optional[datetime] = None,
        source_row_count: int = 0,
        content_signature: Optional[str] = None,
        job_id: Optional[str] = None,
        succeeded_at: Optional[datetime] = None,
    ) -> SampleSyncCursor:
        """显式记录一次成功；较旧水位不会覆盖已推进的水位。"""

        return self._mark_success(
            source_identity=source_identity,
            visit_key=visit_key,
            table_name=table_name,
            strategy=strategy,
            schema_version=schema_version,
            watermark_column=watermark_column,
            watermark_value=watermark_value,
            source_row_count=source_row_count,
            content_signature=content_signature,
            job_id=job_id,
            succeeded_at=succeeded_at,
            full_sync=False,
        )

    def mark_full_sync(
        self,
        *,
        source_identity: str,
        visit_key: VisitKey | Sequence[str],
        table_name: str,
        strategy: str,
        schema_version: str,
        source_row_count: int,
        content_signature: Optional[str],
        job_id: Optional[str] = None,
        watermark_column: Optional[str] = None,
        watermark_value: Optional[datetime] = None,
        succeeded_at: Optional[datetime] = None,
    ) -> SampleSyncCursor:
        """显式记录一次成功的全量同步。"""

        return self._mark_success(
            source_identity=source_identity,
            visit_key=visit_key,
            table_name=table_name,
            strategy=strategy,
            schema_version=schema_version,
            watermark_column=watermark_column,
            watermark_value=watermark_value,
            source_row_count=source_row_count,
            content_signature=content_signature,
            job_id=job_id,
            succeeded_at=succeeded_at,
            full_sync=True,
        )

    def _mark_success(
        self,
        *,
        source_identity: str,
        visit_key: VisitKey | Sequence[str],
        table_name: str,
        strategy: str,
        schema_version: str,
        watermark_column: Optional[str],
        watermark_value: Optional[datetime],
        source_row_count: int,
        content_signature: Optional[str],
        job_id: Optional[str],
        succeeded_at: Optional[datetime],
        full_sync: bool,
    ) -> SampleSyncCursor:
        source = _required_text(source_identity, "source_identity")
        visit = _normalize_visit_key(visit_key)
        normalized_table = _required_text(table_name, "table_name")
        now = succeeded_at or _utc_now()
        key = CursorKey(source, *visit, normalized_table)
        existing = self.get_many(
            source_identity=source,
            visit_keys=[visit],
            table_names=[normalized_table],
        ).get(key)
        effective_watermark = watermark_value
        if (
            existing is not None
            and existing.watermark_value is not None
            and (
                effective_watermark is None
                or effective_watermark < existing.watermark_value
            )
        ):
            effective_watermark = existing.watermark_value

        values = {
            "id": existing.id if existing else str(uuid.uuid4()),
            "source_identity": source,
            "institute_id": visit.institute_id,
            "patient_id": visit.patient_id,
            "visit_id": visit.visit_id,
            "table_name": normalized_table,
            "strategy": _validated_strategy(strategy),
            "watermark_column": (
                str(watermark_column).strip() if watermark_column else None
            ),
            "watermark_value": effective_watermark,
            "last_success_at": now,
            "last_full_sync_at": (
                now
                if full_sync
                else (existing.last_full_sync_at if existing is not None else None)
            ),
            "source_row_count": max(0, int(source_row_count)),
            "content_signature": (
                str(content_signature).strip() if content_signature else None
            ),
            "last_job_id": str(job_id).strip()[:36] if job_id else None,
            "schema_version": _required_text(schema_version, "schema_version"),
            "created_at": existing.created_at if existing else now,
            "updated_at": now,
        }
        self._upsert(values)
        row = (
            self._session.execute(
                sa.select(self._table).where(
                    self._table.c.source_identity == source,
                    self._table.c.institute_id == visit.institute_id,
                    self._table.c.patient_id == visit.patient_id,
                    self._table.c.visit_id == visit.visit_id,
                    self._table.c.table_name == normalized_table,
                )
            )
            .mappings()
            .one()
        )
        return self._from_row(row)

    def _upsert(self, values: dict[str, object]) -> None:
        key_columns = (
            "source_identity",
            "institute_id",
            "patient_id",
            "visit_id",
            "table_name",
        )
        update_values: dict[str, object] = {
            key: value for key, value in values.items() if key not in {"id", "created_at"}
        }
        dialect = self._session.get_bind().dialect.name
        if dialect == "postgresql":
            statement = postgresql_insert(self._table).values(**values)
            update_values["watermark_value"] = self._monotonic_watermark_expression(
                statement.excluded.watermark_value
            )
            statement = statement.on_conflict_do_update(
                index_elements=[self._table.c[name] for name in key_columns],
                set_=update_values,
            )
        elif dialect == "sqlite":
            statement = sqlite_insert(self._table).values(**values)
            update_values["watermark_value"] = self._monotonic_watermark_expression(
                statement.excluded.watermark_value
            )
            statement = statement.on_conflict_do_update(
                index_elements=[self._table.c[name] for name in key_columns],
                set_=update_values,
            )
        else:
            result = self._session.execute(
                self._table.update()
                .where(
                    *[
                        self._table.c[name] == values[name] for name in key_columns
                    ]
                )
                .values(**update_values)
            )
            if result.rowcount:
                return
            statement = self._table.insert().values(**values)
        self._session.execute(statement)

    def _monotonic_watermark_expression(
        self, incoming_watermark: sa.ColumnElement[object]
    ) -> sa.ColumnElement[object]:
        current = self._table.c.watermark_value
        return sa.case(
            (incoming_watermark.is_(None), current),
            (current.is_(None), incoming_watermark),
            (incoming_watermark > current, incoming_watermark),
            else_=current,
        )

    @staticmethod
    def _from_row(row: Mapping[str, object]) -> SampleSyncCursor:
        return SampleSyncCursor(
            id=str(row["id"]),
            source_identity=str(row["source_identity"]),
            institute_id=str(row["institute_id"]),
            patient_id=str(row["patient_id"]),
            visit_id=str(row["visit_id"]),
            table_name=str(row["table_name"]),
            strategy=str(row["strategy"]),
            watermark_column=(
                str(row["watermark_column"]) if row["watermark_column"] else None
            ),
            watermark_value=_as_utc(row["watermark_value"]),
            last_success_at=_as_utc(row["last_success_at"]),
            last_full_sync_at=_as_utc(row["last_full_sync_at"]),
            source_row_count=int(row["source_row_count"] or 0),
            content_signature=(
                str(row["content_signature"]) if row["content_signature"] else None
            ),
            last_job_id=str(row["last_job_id"]) if row["last_job_id"] else None,
            schema_version=str(row["schema_version"]),
            created_at=_as_utc(row["created_at"]) or _utc_now(),
            updated_at=_as_utc(row["updated_at"]) or _utc_now(),
        )
