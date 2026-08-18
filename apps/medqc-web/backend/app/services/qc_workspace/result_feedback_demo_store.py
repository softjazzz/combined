"""演示账号质控结果反馈的最小持久化闭环。

该 Store 只写反馈表，Canonical Envelope 仅作为结果存在性和当前摘要的读取源。
它不修改、不重算也不投影 Canonical 业务状态。
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re
import uuid
from functools import lru_cache
from typing import Any, Mapping

import sqlalchemy as sa
from sqlalchemy import MetaData, Table, and_, select
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from ...database.connection import DB_SCHEMA_MODE, SessionLocal, engine
from ...schemas.qc_sichuan import QcResultFeedbackRequest
from ..custom_qc_workspace_service import _record_result_envelopes_table


class ResultFeedbackDemoStoreUnavailable(RuntimeError):
    """反馈表或其数据库依赖尚未可用。"""


class ResultFeedbackDemoNotFound(LookupError):
    """根任务、病历引用或规则结果不存在。"""


class ResultFeedbackDemoConflict(RuntimeError):
    """Canonical 结果无法唯一解析。"""


_SAFE_RECORD_REF = re.compile(r"^rec_[0-9a-f]{24}$")
_SAFE_ROOT_JOB_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_SAFE_RULE_ID = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
_PHONE_PATTERN = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_ID_CARD_PATTERN = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")
_LONG_DIGIT_PATTERN = re.compile(r"(?<!\d)\d{8,}(?!\d)")


def _target_schema() -> str | None:
    return "qc" if DB_SCHEMA_MODE == "split" else None


@lru_cache(maxsize=1)
def _feedback_table() -> Table:
    if engine is None:
        raise ResultFeedbackDemoStoreUnavailable("反馈功能暂不可用")
    metadata = MetaData()
    return Table(
        "qc_result_feedback_demo",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("root_job_id", sa.String(64), nullable=False),
        sa.Column("record_ref", sa.String(96), nullable=False),
        sa.Column("rule_id", sa.String(32), nullable=False),
        sa.Column("original_status", sa.String(32), nullable=False),
        sa.Column("feedback_type", sa.String(16), nullable=False),
        sa.Column("expected_status", sa.String(32)),
        sa.Column("error_category", sa.String(32)),
        sa.Column("comment", sa.String(500)),
        sa.Column("result_digest", sa.String(64), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "feedback_type IN ('correct', 'incorrect', 'note')",
            name="ck_qc_result_feedback_demo_type",
        ),
        sa.CheckConstraint(
            "original_status IN ('non_compliant', 'compliant', 'data_gap', 'not_applicable', "
            "'evaluation_unknown', 'not_executed', 'technical_error', 'uncertain', "
            "'ai_suggested_non_compliant', 'ai_suggested_compliant')",
            name="ck_qc_result_feedback_demo_original_status",
        ),
        sa.CheckConstraint(
            "expected_status IS NULL OR expected_status IN "
            "('non_compliant', 'compliant', 'data_gap', 'not_applicable', "
            "'evaluation_unknown', 'not_executed')",
            name="ck_qc_result_feedback_demo_expected_status",
        ),
        sa.CheckConstraint(
            "error_category IS NULL OR error_category IN "
            "('wrong_status', 'wrong_reason', 'wrong_evidence', 'missing_data_read', "
            "'wrong_suggestion', 'rule_definition', 'other')",
            name="ck_qc_result_feedback_demo_error_category",
        ),
        sa.CheckConstraint(
            "created_by = 'admin-001'",
            name="ck_qc_result_feedback_demo_demo_account",
        ),
        sa.CheckConstraint(
            "(feedback_type = 'incorrect' AND expected_status IS NOT NULL "
            "AND error_category IS NOT NULL AND comment IS NOT NULL AND length(trim(comment)) > 0) "
            "OR (feedback_type = 'note' AND comment IS NOT NULL AND length(trim(comment)) > 0 "
            "AND expected_status IS NULL AND error_category IS NULL) "
            "OR (feedback_type = 'correct' AND expected_status IS NULL AND error_category IS NULL)",
            name="ck_qc_result_feedback_demo_required_fields",
        ),
        sa.UniqueConstraint(
            "root_job_id",
            "record_ref",
            "rule_id",
            "created_by",
            name="uq_qc_result_feedback_demo_current",
        ),
        schema=_target_schema(),
    )


def _session() -> Session:
    if SessionLocal is None:
        raise ResultFeedbackDemoStoreUnavailable("反馈功能暂不可用")
    try:
        return SessionLocal()
    except Exception as exc:  # pragma: no cover - engine-specific failure
        raise ResultFeedbackDemoStoreUnavailable("反馈功能暂不可用") from exc


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _iso_datetime(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    return _safe_text(value) or None


def _validate_identifiers(*, root_job_id: str, record_ref: str, rule_id: str) -> None:
    if not _SAFE_ROOT_JOB_ID.fullmatch(root_job_id):
        raise ResultFeedbackDemoNotFound("质控结果不存在")
    if not _SAFE_RECORD_REF.fullmatch(record_ref):
        raise ResultFeedbackDemoNotFound("质控结果不存在")
    if not _SAFE_RULE_ID.fullmatch(rule_id):
        raise ResultFeedbackDemoNotFound("质控结果不存在")


def contains_sensitive_feedback_text(comment: str | None) -> bool:
    """拒绝明显手机号、身份证号和住院号式连续长数字。"""

    value = _safe_text(comment)
    return bool(
        _PHONE_PATTERN.search(value)
        or _ID_CARD_PATTERN.search(value)
        or _LONG_DIGIT_PATTERN.search(value)
    )


def _rule_id(item: Mapping[str, Any]) -> str:
    return _safe_text(item.get("rule_id") or item.get("rule_code")).upper()


def _status(item: Mapping[str, Any]) -> str:
    return _safe_text(item.get("status") or item.get("result_status") or item.get("display_status"))


def _result_digest(item: Mapping[str, Any]) -> str:
    digest_payload = {
        "rule_id": _rule_id(item),
        "status": _status(item),
        "reason_code": _safe_text(item.get("reason_code")),
        "customer_display_facts": item.get("customer_display_facts")
        if isinstance(item.get("customer_display_facts"), (dict, list))
        else {},
        "customer_evidence": item.get("customer_evidence")
        if isinstance(item.get("customer_evidence"), (dict, list))
        else item.get("evidence")
        if isinstance(item.get("evidence"), (dict, list))
        else [],
    }
    encoded = json.dumps(
        digest_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _serialize_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": _safe_text(row.get("id")),
        "root_job_id": _safe_text(row.get("root_job_id")),
        "record_ref": _safe_text(row.get("record_ref")),
        "rule_id": _safe_text(row.get("rule_id")).upper(),
        "original_status": _safe_text(row.get("original_status")),
        "feedback_type": _safe_text(row.get("feedback_type")),
        "expected_status": _safe_text(row.get("expected_status")) or None,
        "error_category": _safe_text(row.get("error_category")) or None,
        "comment": _safe_text(row.get("comment")) or None,
        "result_digest": _safe_text(row.get("result_digest")),
        "created_by": _safe_text(row.get("created_by")),
        "created_at": _iso_datetime(row.get("created_at")),
        "updated_at": _iso_datetime(row.get("updated_at")),
    }


class ResultFeedbackDemoStore:
    """只保存演示账号的当前反馈，不保存病历正文或患者身份。"""

    def __init__(self) -> None:
        feedback_table = _feedback_table()
        canonical_table = _record_result_envelopes_table()
        if feedback_table is None or canonical_table is None:
            raise ResultFeedbackDemoStoreUnavailable("反馈功能暂不可用")
        self._feedback_table = feedback_table
        self._canonical_table = canonical_table

    @staticmethod
    def _canonical_item_from_row(
        row: Mapping[str, Any],
        *,
        root_job_id: str,
        record_ref: str,
        rule_id: str,
    ) -> dict[str, Any] | None:
        try:
            envelope = json.loads(_safe_text(row.get("envelope_json")))
        except (TypeError, ValueError, json.JSONDecodeError):
            raise ResultFeedbackDemoConflict("质控结果无法唯一确认")
        if not isinstance(envelope, dict):
            raise ResultFeedbackDemoConflict("质控结果无法唯一确认")
        if (
            _safe_text(envelope.get("root_job_id")) != root_job_id
            or _safe_text(envelope.get("record_ref")) != record_ref
            or not _safe_text(envelope.get("rule_set_key"))
            or not _safe_text(envelope.get("rule_set_version"))
        ):
            return None
        items = envelope.get("items")
        if not isinstance(items, list):
            raise ResultFeedbackDemoConflict("质控结果无法唯一确认")
        matches = [item for item in items if isinstance(item, dict) and _rule_id(item) == rule_id]
        if len(matches) > 1:
            raise ResultFeedbackDemoConflict("质控结果无法唯一确认")
        return dict(matches[0]) if matches else None

    def _resolve_canonical_item(
        self,
        session: Session,
        *,
        root_job_id: str,
        record_ref: str,
        rule_id: str,
        created_by: str,
    ) -> dict[str, Any]:
        try:
            rows = (
                session.execute(
                    select(self._canonical_table).where(
                        self._canonical_table.c.root_job_id == root_job_id,
                        self._canonical_table.c.created_by == created_by,
                    )
                )
                .mappings()
                .all()
            )
        except (OperationalError, ProgrammingError) as exc:
            raise ResultFeedbackDemoStoreUnavailable("反馈功能暂不可用") from exc

        matches: list[dict[str, Any]] = []
        for row in rows:
            if _safe_text(row.get("created_by")) != created_by:
                continue
            item = self._canonical_item_from_row(
                row,
                root_job_id=root_job_id,
                record_ref=record_ref,
                rule_id=rule_id,
            )
            if item is not None:
                matches.append(item)
        if not matches:
            raise ResultFeedbackDemoNotFound("质控结果不存在")
        if len(matches) != 1:
            raise ResultFeedbackDemoConflict("质控结果无法唯一确认")
        return matches[0]

    def _resolve_canonical_record(
        self,
        session: Session,
        *,
        root_job_id: str,
        record_ref: str,
        created_by: str,
    ) -> None:
        """确认根任务下该安全病历引用只有一个规则版本 Envelope。"""

        try:
            rows = (
                session.execute(
                    select(self._canonical_table).where(
                        self._canonical_table.c.root_job_id == root_job_id,
                        self._canonical_table.c.created_by == created_by,
                    )
                )
                .mappings()
                .all()
            )
        except (OperationalError, ProgrammingError) as exc:
            raise ResultFeedbackDemoStoreUnavailable("反馈功能暂不可用") from exc

        matched_versions: set[tuple[str, str]] = set()
        for row in rows:
            if _safe_text(row.get("created_by")) != created_by:
                continue
            try:
                envelope = json.loads(_safe_text(row.get("envelope_json")))
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ResultFeedbackDemoConflict("质控结果无法唯一确认") from exc
            if not isinstance(envelope, dict):
                raise ResultFeedbackDemoConflict("质控结果无法唯一确认")
            if (
                _safe_text(envelope.get("root_job_id")) == root_job_id
                and _safe_text(envelope.get("record_ref")) == record_ref
            ):
                rule_set_key = _safe_text(envelope.get("rule_set_key"))
                rule_set_version = _safe_text(envelope.get("rule_set_version"))
                if not rule_set_key or not rule_set_version:
                    raise ResultFeedbackDemoConflict("质控结果无法唯一确认")
                matched_versions.add((rule_set_key, rule_set_version))
        if not matched_versions:
            raise ResultFeedbackDemoNotFound("质控结果不存在")
        if len(matched_versions) != 1:
            raise ResultFeedbackDemoConflict("质控结果无法唯一确认")
        matching_rows = 0
        for row in rows:
            if _safe_text(row.get("created_by")) != created_by:
                continue
            try:
                envelope = json.loads(_safe_text(row.get("envelope_json")))
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            if (
                isinstance(envelope, dict)
                and _safe_text(envelope.get("root_job_id")) == root_job_id
                and _safe_text(envelope.get("record_ref")) == record_ref
            ):
                matching_rows += 1
        if matching_rows != 1:
            raise ResultFeedbackDemoConflict("质控结果无法唯一确认")

    def _ensure_feedback_table(self, session: Session) -> None:
        """在解析 Canonical 前确认反馈迁移已完成，避免缺表被误报为 404。"""

        try:
            session.execute(select(self._feedback_table).limit(0))
        except (OperationalError, ProgrammingError) as exc:
            raise ResultFeedbackDemoStoreUnavailable("反馈功能暂不可用") from exc

    def list_for_record(
        self,
        *,
        root_job_id: str,
        record_ref: str,
        created_by: str,
    ) -> dict[str, dict[str, Any]]:
        _validate_identifiers(root_job_id=root_job_id, record_ref=record_ref, rule_id="placeholder")
        session = _session()
        try:
            self._ensure_feedback_table(session)
            self._resolve_canonical_record(
                session,
                root_job_id=root_job_id,
                record_ref=record_ref,
                created_by=created_by,
            )
            try:
                rows = (
                    session.execute(
                        select(self._feedback_table).where(
                            and_(
                                self._feedback_table.c.root_job_id == root_job_id,
                                self._feedback_table.c.record_ref == record_ref,
                                self._feedback_table.c.created_by == created_by,
                            )
                        )
                    )
                    .mappings()
                    .all()
                )
            except (OperationalError, ProgrammingError) as exc:
                raise ResultFeedbackDemoStoreUnavailable("反馈功能暂不可用") from exc
            return {
                _safe_text(row.get("rule_id")).upper(): _serialize_row(row)
                for row in rows
            }
        finally:
            session.close()

    def list_all(self, *, created_by: str, limit: int) -> list[dict[str, Any]]:
        """读取演示账号已提交的全部反馈，不联表返回病历身份或正文。"""

        session = _session()
        try:
            self._ensure_feedback_table(session)
            try:
                rows = (
                    session.execute(
                        select(self._feedback_table)
                        .where(self._feedback_table.c.created_by == created_by)
                        .order_by(
                            self._feedback_table.c.updated_at.desc(),
                            self._feedback_table.c.id.desc(),
                        )
                        .limit(limit)
                    )
                    .mappings()
                    .all()
                )
            except (OperationalError, ProgrammingError) as exc:
                raise ResultFeedbackDemoStoreUnavailable("反馈功能暂不可用") from exc
            return [_serialize_row(row) for row in rows]
        finally:
            session.close()

    def save(
        self,
        *,
        root_job_id: str,
        record_ref: str,
        rule_id: str,
        created_by: str,
        payload: QcResultFeedbackRequest,
    ) -> dict[str, Any]:
        normalized_rule_id = _safe_text(rule_id).upper()
        _validate_identifiers(
            root_job_id=root_job_id,
            record_ref=record_ref,
            rule_id=normalized_rule_id,
        )
        session = _session()
        try:
            self._ensure_feedback_table(session)
            canonical_item = self._resolve_canonical_item(
                session,
                root_job_id=root_job_id,
                record_ref=record_ref,
                rule_id=normalized_rule_id,
                created_by=created_by,
            )
            current_status = _status(canonical_item)
            if not current_status:
                raise ResultFeedbackDemoConflict("质控结果无法唯一确认")
            now = datetime.now(timezone.utc)
            values = {
                "root_job_id": root_job_id,
                "record_ref": record_ref,
                "rule_id": normalized_rule_id,
                "original_status": current_status,
                "feedback_type": payload.feedback_type,
                "expected_status": payload.expected_status,
                "error_category": payload.error_category,
                "comment": payload.comment,
                "result_digest": _result_digest(canonical_item),
                "created_by": created_by,
                "updated_at": now,
            }
            try:
                existing = session.execute(
                    select(self._feedback_table).where(
                        and_(
                            self._feedback_table.c.root_job_id == root_job_id,
                            self._feedback_table.c.record_ref == record_ref,
                            self._feedback_table.c.rule_id == normalized_rule_id,
                            self._feedback_table.c.created_by == created_by,
                        )
                    )
                ).mappings().first()
                if existing:
                    session.execute(
                        self._feedback_table.update()
                        .where(self._feedback_table.c.id == existing["id"])
                        .values(**values)
                    )
                    feedback_id = _safe_text(existing["id"])
                    created_at = existing.get("created_at")
                else:
                    feedback_id = str(uuid.uuid4())
                    created_at = now
                    session.execute(
                        self._feedback_table.insert().values(
                            id=feedback_id,
                            created_at=created_at,
                            **values,
                        )
                    )
                session.commit()
            except (OperationalError, ProgrammingError) as exc:
                session.rollback()
                raise ResultFeedbackDemoStoreUnavailable("反馈功能暂不可用") from exc
            except IntegrityError as exc:
                session.rollback()
                raise ResultFeedbackDemoConflict("反馈保存冲突，请稍后重试") from exc
            return _serialize_row(
                {
                    **values,
                    "id": feedback_id,
                    "created_at": created_at,
                }
            )
        finally:
            session.close()
