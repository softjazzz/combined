"""首页质控 V2：任务、结果、问题的持久化（qc schema 下三张表，迁移 20261013_000048）。

表结构与迁移保持一致，由 test_frontpage_qc_v2_store 的迁移往返测试保证。
表未迁移时抛 FrontpageQcStoreUnavailable，由接口层转成 503，不影响其他质控功能。
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
import uuid
from collections import defaultdict
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import SQLAlchemyError

from .catalog import RULES_BY_ID
from .config import grade_of
from .loader import FrontpageRef
from .model import FrontpageQcOutcome
from .scoring_items import GROUP_CAPS, SCORE_ITEMS, max_points

logger = logging.getLogger(__name__)

RUNS_TABLE = "frontpage_qc_runs"
RESULTS_TABLE = "frontpage_qc_results"
FINDINGS_TABLE = "frontpage_qc_findings"
_RESULT_REF_INLINE_LIMIT = 128
_CUSTOMER_TEST_INSTITUTE_ID = "CUSTOMER_TEST"

RUN_ACTIVE_STATUSES = ("queued", "running")
REVIEW_STATUSES = ("pending", "confirmed", "false_alarm")


class FrontpageQcStoreUnavailable(RuntimeError):
    """存储表不存在或数据库不可用。"""


class FrontpageQcNotFound(LookupError):
    pass


class FrontpageQcRunConflict(RuntimeError):
    """同一用户并发发起重复的活跃首页质控任务。"""

    def __init__(self, active_run: Dict[str, Any]) -> None:
        super().__init__("已有进行中的首页质控任务")
        self.active_run = active_run


_LOCAL_LOCKS_GUARD = threading.Lock()
_LOCAL_LOCKS: Dict[str, threading.Lock] = {}


def _get_local_lock(key: str) -> threading.Lock:
    with _LOCAL_LOCKS_GUARD:
        lock = _LOCAL_LOCKS.get(key)
        if lock is None:
            if len(_LOCAL_LOCKS) > 4096:
                idle = [k for k, v in _LOCAL_LOCKS.items() if not v.locked()]
                for k in idle[:2048]:
                    _LOCAL_LOCKS.pop(k, None)
            lock = threading.Lock()
            _LOCAL_LOCKS[key] = lock
        return lock


def _acquire_pg_advisory_xact_lock(session: Any, lock_key: str) -> None:
    if session.get_bind().dialect.name == "postgresql":
        lock_id = int.from_bytes(hashlib.sha256(lock_key.encode()).digest()[:8], "big", signed=True)
        session.execute(sa.text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_id})


def build_tables(schema: Optional[str] = None) -> Tuple[sa.Table, sa.Table, sa.Table]:
    metadata = sa.MetaData()
    runs = sa.Table(
        RUNS_TABLE,
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("ruleset_version", sa.String(32), nullable=False),
        sa.Column("filters_json", sa.Text, nullable=False),
        sa.Column("record_refs_json", sa.Text, nullable=False),
        sa.Column("total_records", sa.Integer, nullable=False),
        sa.Column("processed_records", sa.Integer, nullable=False),
        sa.Column("success_count", sa.Integer, nullable=False),
        sa.Column("failed_count", sa.Integer, nullable=False),
        sa.Column("issue_records", sa.Integer, nullable=False),
        sa.Column("data_gap_records", sa.Integer, nullable=False),
        sa.Column("failed_records_json", sa.Text, nullable=True),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("cancel_requested", sa.Boolean, nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Index("ix_frontpage_qc_runs_created_by_status", "created_by", "status"),
        sa.Index("ix_frontpage_qc_runs_created_at", "created_at"),
        schema=schema,
    )
    results = sa.Table(
        RESULTS_TABLE,
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("institute_id", sa.String(128), nullable=False),
        sa.Column("patient_id", sa.String(128), nullable=False),
        sa.Column("visit_id", sa.String(128), nullable=False),
        sa.Column("record_key", sa.String(400), nullable=False),
        sa.Column("department", sa.String(100), nullable=True),
        sa.Column("discharge_date", sa.String(10), nullable=True),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("grade", sa.String(16), nullable=False),
        sa.Column("fail_count", sa.Integer, nullable=False),
        sa.Column("hint_count", sa.Integer, nullable=False),
        sa.Column("required_missing_count", sa.Integer, nullable=False),
        sa.Column("data_gap_count", sa.Integer, nullable=False),
        sa.Column("scorable_ratio", sa.Float, nullable=False),
        sa.Column("completeness_rate", sa.Float, nullable=True),
        sa.Column("ruleset_version", sa.String(32), nullable=False),
        sa.Column("input_fingerprint", sa.String(64), nullable=False),
        sa.Column("item_scores_json", sa.Text, nullable=False),
        sa.Column("rule_verdicts_json", sa.Text, nullable=False),
        sa.Column("notes_json", sa.Text, nullable=True),
        sa.Column("is_latest", sa.Boolean, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Index("ix_frontpage_qc_results_record_latest", "record_key", "is_latest"),
        sa.Index("ix_frontpage_qc_results_run", "run_id"),
        sa.Index("ix_frontpage_qc_results_latest_discharge", "is_latest", "discharge_date"),
        schema=schema,
    )
    findings = sa.Table(
        FINDINGS_TABLE,
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("result_id", sa.String(36), nullable=False),
        sa.Column("record_key", sa.String(400), nullable=False),
        sa.Column("rule_id", sa.String(16), nullable=False),
        sa.Column("rule_name", sa.String(100), nullable=False),
        sa.Column("rule_group", sa.String(20), nullable=False),
        sa.Column("section", sa.String(20), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("score_item", sa.String(40), nullable=True),
        sa.Column("verdict", sa.String(16), nullable=False),
        sa.Column("problem", sa.String(200), nullable=False),
        sa.Column("reason", sa.String(200), nullable=True),
        sa.Column("details_json", sa.Text, nullable=False),
        sa.Column("deduction", sa.Float, nullable=False),
        sa.Column("review_status", sa.String(16), nullable=False),
        sa.Column("review_note", sa.String(500), nullable=True),
        sa.Column("reviewed_by", sa.String(128), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Index("ix_frontpage_qc_findings_result", "result_id"),
        sa.Index("ix_frontpage_qc_findings_rule", "rule_id"),
        schema=schema,
    )
    sa.Index('uq_frontpage_qc_results_latest', results.c.record_key, unique=True,
             postgresql_where=results.c.is_latest.is_(True), sqlite_where=results.c.is_latest.is_(True))
    return runs, results, findings


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        # SQLite 读回会丢失时区；写入统一为 UTC
        aware = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return aware.astimezone(timezone.utc).isoformat()
    return str(value)


def _loads(text: Optional[str], default: Any) -> Any:
    if not text:
        return default
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return default


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _finding_signature(rule_id: str, details: Any) -> str:
    return f"{rule_id}|{_dumps(details)}"


class FrontpageQcStore:
    def __init__(self, session_factory: Callable[[], Any], schema: Optional[str] = None, *, institute_id: str | None = None, actor_id: str | None = None) -> None:
        self.session_factory = session_factory
        self.institute_id, self.actor_id = institute_id, actor_id
        self.runs, self.results, self.findings = build_tables(schema)

    def _result_scope(self):
        return self.results.c.institute_id == self.institute_id if self.institute_id is not None else sa.true()

    def _result_ref_filter(self, refs: Sequence[FrontpageRef]):
        columns = self.results.c
        # record_key 用来命中现有索引，只有完整三坐标相符的结果才算同一病例。
        keys = {key for ref in refs for key in (ref.legacy_key(), ref.as_key())}
        return sa.and_(
            columns.record_key.in_(sorted(keys)),
            sa.tuple_(columns.institute_id, columns.patient_id, columns.visit_id).in_(
                [ref.as_case_ref() for ref in refs]
            ),
        )

    def _large_result_ref_filter(self, refs: Sequence[FrontpageRef], dialect: str):
        # 用一个绑定值传入关系，保留数据库统一计数、排序和分页。
        candidates = [
            (key, *ref.as_case_ref())
            for ref in refs
            for key in dict.fromkeys((ref.legacy_key(), ref.as_key()))
        ]
        payload = sa.bindparam(None, _dumps(candidates), type_=sa.Text())
        if dialect == "postgresql":
            source = sa.func.jsonb_array_elements(sa.cast(payload, JSONB)).table_valued(
                sa.column("value", JSONB)
            )
            fields = [source.c.value[index].astext for index in range(4)]
        else:  # SQLite 合成环境。
            source = sa.func.json_each(payload).table_valued("value")
            fields = [sa.func.json_extract(source.c.value, f"$[{index}]") for index in range(4)]
        columns = self.results.c
        return sa.tuple_(
            columns.record_key, columns.institute_id, columns.patient_id, columns.visit_id
        ).in_(sa.select(*fields).select_from(source))

    def _run_scope(self):
        return self.runs.c.created_by == self.actor_id if self.institute_id is not None else sa.true()

    def _check_refs(self, refs):
        if self.institute_id is not None and any(ref.institute_id != self.institute_id for ref in refs):
            raise FrontpageQcNotFound("无权访问其他机构病历")

    def claim_run(self, run_id: str) -> bool:
        def op(session):
            count = session.execute(self.runs.update().where(
                self.runs.c.id == run_id, self._run_scope(), self.runs.c.status == 'queued',
                self.runs.c.cancel_requested.is_(False),
            ).values(status='running', started_at=_now(), updated_at=_now())).rowcount
            session.commit()
            return count == 1
        return self._guard(op)

    # ---------- 通用 ----------

    def _guard(self, fn: Callable[[Any], Any]) -> Any:
        try:
            with self.session_factory() as session:
                return fn(session)
        except SQLAlchemyError as exc:
            logger.exception(
                "首页质控存储数据库操作失败 error_type=%s",
                type(exc).__name__,
            )
            raise FrontpageQcStoreUnavailable(
                "首页质控存储不可用：请确认已执行 20261013_000048 迁移并检查数据库连接"
            ) from exc

    def create_all(self, engine: Any) -> None:
        """仅供测试初始化使用；生产环境由 alembic 迁移建表。"""
        self.runs.metadata.create_all(engine)

    # ---------- 任务 ----------

    def create_run(self, *, created_by: str, refs: Sequence[FrontpageRef], filters: Dict[str, Any], ruleset_version: str) -> Dict[str, Any]:
        self._check_refs(refs)
        now = _now()
        row = {
            "id": str(uuid.uuid4()),
            "status": "queued",
            "ruleset_version": ruleset_version,
            "filters_json": _dumps(filters),
            "record_refs_json": _dumps([asdict(ref) for ref in refs]),
            "total_records": len(refs),
            "processed_records": 0,
            "success_count": 0,
            "failed_count": 0,
            "issue_records": 0,
            "data_gap_records": 0,
            "failed_records_json": None,
            "error_message": None,
            "cancel_requested": False,
            "created_by": created_by,
            "created_at": now,
            "started_at": None,
            "finished_at": None,
            "updated_at": now,
        }

        def op(session):
            session.execute(self.runs.insert().values(**row))
            session.commit()
            return self._public_run(row)

        return self._guard(op)

    def create_run_if_no_active(
        self,
        *,
        created_by: str,
        refs: Sequence[FrontpageRef],
        filters: Dict[str, Any],
        ruleset_version: str,
        stalled_after: Optional[timedelta] = None,
    ) -> Dict[str, Any]:
        """串行化检查并创建用户活跃任务，防止同用户并发 POST /runs 产生双活跃任务。"""
        self._check_refs(refs)
        now = _now()
        row = {
            "id": str(uuid.uuid4()),
            "status": "queued",
            "ruleset_version": ruleset_version,
            "filters_json": _dumps(filters),
            "record_refs_json": _dumps([asdict(ref) for ref in refs]),
            "total_records": len(refs),
            "processed_records": 0,
            "success_count": 0,
            "failed_count": 0,
            "issue_records": 0,
            "data_gap_records": 0,
            "failed_records_json": None,
            "error_message": None,
            "cancel_requested": False,
            "created_by": created_by,
            "created_at": now,
            "started_at": None,
            "finished_at": None,
            "updated_at": now,
        }
        lock_key = f"frontpage_qc_run:{created_by}"

        def op(session):
            _acquire_pg_advisory_xact_lock(session, lock_key)
            active_rows = (
                session.execute(
                    sa.select(self.runs)
                    .where(
                        self._run_scope(),
                        self.runs.c.created_by == created_by,
                        self.runs.c.status.in_(RUN_ACTIVE_STATUSES),
                    )
                    .order_by(self.runs.c.created_at.desc())
                    .limit(5)
                )
                .mappings()
                .all()
            )
            still_active: List[Dict[str, Any]] = []
            for active_row in active_rows:
                pub = self._public_run(active_row)
                if stalled_after is not None and pub.get("updated_at"):
                    updated = datetime.fromisoformat(pub["updated_at"])
                    if updated.tzinfo is None:
                        updated = updated.replace(tzinfo=timezone.utc)
                    if now - updated >= stalled_after:
                        cutoff = now - stalled_after
                        res = session.execute(
                            self.runs.update()
                            .where(
                                self.runs.c.id == pub["id"],
                                self._run_scope(),
                                self.runs.c.status.in_(RUN_ACTIVE_STATUSES),
                                self.runs.c.updated_at == active_row["updated_at"],
                                self.runs.c.updated_at <= cutoff,
                            )
                            .values(
                                status="failed",
                                error_message="任务中断（服务重启或执行异常），请重新发起",
                                finished_at=now,
                                updated_at=now,
                            )
                        )
                        if res.rowcount != 1:
                            refreshed = session.execute(
                                sa.select(self.runs).where(
                                    self.runs.c.id == pub["id"], self._run_scope()
                                )
                            ).mappings().first()
                            if refreshed is not None and refreshed["status"] in RUN_ACTIVE_STATUSES:
                                still_active.append(self._public_run(refreshed))
                        continue
                still_active.append(pub)
            if still_active:
                session.commit()
                raise FrontpageQcRunConflict(still_active[0])
            session.execute(self.runs.insert().values(**row))
            session.commit()
            return self._public_run(row)

        with _get_local_lock(lock_key):
            return self._guard(op)

    def _public_run(self, row: Any) -> Dict[str, Any]:
        data = dict(row)
        return {
            "id": data["id"],
            "status": data["status"],
            "ruleset_version": data["ruleset_version"],
            "filters": _loads(data.get("filters_json"), {}),
            "total_records": data["total_records"],
            "processed_records": data["processed_records"],
            "success_count": data["success_count"],
            "failed_count": data["failed_count"],
            "issue_records": data["issue_records"],
            "data_gap_records": data["data_gap_records"],
            "failed_records": _loads(data.get("failed_records_json"), []),
            "error_message": data.get("error_message"),
            "cancel_requested": bool(data.get("cancel_requested")),
            "created_by": data["created_by"],
            "created_at": _iso(data.get("created_at")),
            "started_at": _iso(data.get("started_at")),
            "finished_at": _iso(data.get("finished_at")),
            "updated_at": _iso(data.get("updated_at")),
        }

    def get_run(self, run_id: str) -> Dict[str, Any]:
        def op(session):
            row = session.execute(sa.select(self.runs).where(self.runs.c.id == run_id, self._run_scope())).mappings().first()
            if row is None:
                raise FrontpageQcNotFound("质控任务不存在")
            self._check_refs([FrontpageRef(**item) for item in _loads(row["record_refs_json"], [])])
            return self._public_run(row)

        return self._guard(op)

    def run_refs(self, run_id: str) -> List[FrontpageRef]:
        def op(session):
            text = session.execute(sa.select(self.runs.c.record_refs_json).where(self.runs.c.id == run_id, self._run_scope())).scalar()
            if text is None:
                raise FrontpageQcNotFound("质控任务不存在")
            refs = [FrontpageRef(**item) for item in _loads(text, [])]
            self._check_refs(refs)
            return refs

        return self._guard(op)

    def list_runs(self, *, created_by: Optional[str] = None, statuses: Iterable[str] = (), limit: int = 20) -> List[Dict[str, Any]]:
        def op(session):
            query = sa.select(self.runs).where(self._run_scope()).order_by(self.runs.c.created_at.desc()).limit(limit)
            if created_by:
                query = query.where(self.runs.c.created_by == created_by)
            status_list = list(statuses)
            if status_list:
                query = query.where(self.runs.c.status.in_(status_list))
            rows = session.execute(query).mappings().all()
            return [self._public_run(row) for row in rows if self.institute_id is None or all(
                item.get('institute_id') == self.institute_id for item in _loads(row['record_refs_json'], [])
            )]

        return self._guard(op)

    def update_run(self, run_id: str, **values: Any) -> None:
        if "failed_records" in values:
            values["failed_records_json"] = _dumps(values.pop("failed_records"))
        values["updated_at"] = _now()
        if values.get('status') in ('completed', 'completed_with_errors'):
            # 最后一次取消检查与终态提交之间仍可收到取消；以数据库提交时的值为准。
            values['status'] = sa.case((self.runs.c.cancel_requested.is_(True), 'cancelled'), else_=values['status'])

        def op(session):
            session.execute(self.runs.update().where(self.runs.c.id == run_id, self._run_scope(), self.runs.c.status.in_(RUN_ACTIVE_STATUSES)).values(**values))
            session.commit()

        self._guard(op)

    def settle_stalled_run(
        self,
        run_id: str,
        *,
        expected_updated_at: Optional[datetime] = None,
        stale_before: Optional[datetime] = None,
        error_message: str = "任务中断（服务重启或执行异常），请重新发起",
    ) -> bool:
        """按 updated_at CAS 将超时中断任务落为失败，避免误杀并发刷新心跳的运行中任务。"""
        now = _now()

        def _utc_aware(dt: datetime) -> datetime:
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)

        def op(session):
            conditions = [
                self.runs.c.id == run_id,
                self._run_scope(),
                self.runs.c.status.in_(RUN_ACTIVE_STATUSES),
            ]
            if expected_updated_at is not None:
                conditions.append(self.runs.c.updated_at == _utc_aware(expected_updated_at))
            if stale_before is not None:
                conditions.append(self.runs.c.updated_at <= _utc_aware(stale_before))
            res = session.execute(
                self.runs.update()
                .where(*conditions)
                .values(
                    status="failed",
                    error_message=error_message,
                    finished_at=now,
                    updated_at=now,
                )
            )
            session.commit()
            return res.rowcount == 1

        return self._guard(op)

    def request_cancel(self, run_id: str) -> Dict[str, Any]:
        self.get_run(run_id)
        def op(session):
            row = session.execute(sa.select(self.runs).where(self.runs.c.id == run_id, self._run_scope())).mappings().first()
            if row is None:
                raise FrontpageQcNotFound("质控任务不存在")
            if row["status"] in RUN_ACTIVE_STATUSES:
                values: Dict[str, Any] = {"cancel_requested": True, "updated_at": _now()}
                if row["status"] == "queued":
                    values.update(status=sa.case((self.runs.c.status == 'queued', 'cancelled'), else_=self.runs.c.status),
                                  finished_at=sa.case((self.runs.c.status == 'queued', _now()), else_=self.runs.c.finished_at))
                session.execute(self.runs.update().where(self.runs.c.id == run_id, self._run_scope(), self.runs.c.status.in_(RUN_ACTIVE_STATUSES)).values(**values))
                session.commit()
                row = session.execute(sa.select(self.runs).where(self.runs.c.id == run_id, self._run_scope())).mappings().first()
            return self._public_run(row)

        return self._guard(op)

    def is_cancel_requested(self, run_id: str) -> bool:
        def op(session):
            return bool(session.execute(sa.select(self.runs.c.cancel_requested).where(self.runs.c.id == run_id, self._run_scope())).scalar())

        return self._guard(op)

    # ---------- 结果 ----------

    def save_outcome(
        self,
        *,
        run_id: str,
        outcome: FrontpageQcOutcome,
        department: str = "",
        discharge_date: str = "",
    ) -> str:
        ref = FrontpageRef(outcome.institute_id, outcome.patient_id, outcome.visit_id)
        key = ref.as_key()
        now = _now()
        result_id = str(uuid.uuid4())

        def op(session):
            # 沿用上一次结果中相同问题的复核结论，避免重新质控后重复复核
            self._check_refs([ref])
            # PG事务级病例锁覆盖“首次还没有latest行”的并发窗口，并与 review_finding 共用同病例锁。
            _acquire_pg_advisory_xact_lock(session, ref.legacy_key())
            run = session.execute(sa.select(self.runs).where(self.runs.c.id == run_id)).mappings().first()
            if run is None:
                raise FrontpageQcNotFound('质控任务不存在')
            scope = (self._result_ref_filter([ref]), self.results.c.is_latest.is_(True), self._result_scope())
            existing = session.execute(sa.select(self.results.c.id, self.runs.c.created_at).join(
                self.runs, self.runs.c.id == self.results.c.run_id
            ).where(*scope)).mappings().first()
            is_latest = existing is None or (_iso(run['created_at']), run_id) >= (_iso(existing['created_at']),
                session.execute(sa.select(self.results.c.run_id).where(self.results.c.id == existing['id'])).scalar())
            previous_reviews: Dict[str, Dict[str, Any]] = {}
            previous = session.execute(
                sa.select(self.results.c.id).where(*scope)
            ).scalars().all()
            if previous and is_latest:
                rows = session.execute(
                    sa.select(self.findings).where(
                        self.findings.c.result_id.in_(previous), self.findings.c.review_status != "pending"
                    )
                ).mappings().all()
                for row in rows:
                    signature = _finding_signature(row["rule_id"], _loads(row["details_json"], []))
                    previous_reviews[signature] = {
                        "review_status": row["review_status"],
                        "review_note": row["review_note"],
                        "reviewed_by": row["reviewed_by"],
                        "reviewed_at": row["reviewed_at"],
                    }
                session.execute(
                    self.results.update().where(self.results.c.id.in_(previous)).values(is_latest=False)
                )
            session.execute(
                self.results.insert().values(
                    id=result_id,
                    run_id=run_id,
                    institute_id=ref.institute_id,
                    patient_id=ref.patient_id,
                    visit_id=ref.visit_id,
                    record_key=key,
                    department=(department or "")[:100] or None,
                    discharge_date=(discharge_date or "")[:10] or None,
                    score=outcome.score,
                    grade=outcome.grade,
                    fail_count=outcome.fail_count,
                    hint_count=outcome.hint_count,
                    required_missing_count=outcome.required_missing_count,
                    data_gap_count=outcome.data_gap_count,
                    scorable_ratio=outcome.scorable_ratio,
                    completeness_rate=outcome.completeness_rate,
                    ruleset_version=outcome.ruleset_version,
                    input_fingerprint=outcome.input_fingerprint,
                    item_scores_json=_dumps([asdict(item) for item in outcome.item_scores]),
                    rule_verdicts_json=_dumps(outcome.rule_verdicts),
                    notes_json=_dumps(outcome.notes),
                    is_latest=is_latest,
                    created_at=now,
                )
            )
            rows = []
            for finding in outcome.findings:
                review = previous_reviews.get(_finding_signature(finding.rule_id, finding.details), {})
                rows.append(
                    {
                        "id": str(uuid.uuid4()),
                        "result_id": result_id,
                        "record_key": key,
                        "rule_id": finding.rule_id,
                        "rule_name": finding.rule_name[:100],
                        "rule_group": finding.group,
                        "section": finding.section,
                        "severity": finding.severity,
                        "score_item": finding.score_item,
                        "verdict": finding.verdict,
                        "problem": finding.problem[:200],
                        "reason": (finding.reason or "")[:200] or None,
                        "details_json": _dumps(finding.details),
                        "deduction": finding.deduction,
                        "review_status": review.get("review_status", "pending"),
                        "review_note": review.get("review_note"),
                        "reviewed_by": review.get("reviewed_by"),
                        "reviewed_at": review.get("reviewed_at"),
                        "created_at": now,
                    }
                )
            if rows:
                session.execute(self.findings.insert(), rows)
                if any(item["review_status"] == "false_alarm" for item in rows):
                    self._recompute_result_aggregates(session, result_id)
            session.commit()
            return result_id

        with _get_local_lock(f"case:{ref.legacy_key()}"):
            return self._guard(op)

    def _public_result(self, row: Any) -> Dict[str, Any]:
        data = dict(row)
        return {
            "id": data["id"],
            "run_id": data["run_id"],
            "institute_id": data["institute_id"],
            "patient_id": data["patient_id"],
            "visit_id": data["visit_id"],
            "record_key": data["record_key"],
            "department": data.get("department") or "",
            "discharge_date": data.get("discharge_date") or "",
            "score": data["score"],
            "grade": data["grade"],
            "fail_count": data["fail_count"],
            "hint_count": data["hint_count"],
            "required_missing_count": data["required_missing_count"],
            "data_gap_count": data["data_gap_count"],
            "scorable_ratio": data["scorable_ratio"],
            "completeness_rate": data.get("completeness_rate"),
            "ruleset_version": data["ruleset_version"],
            "input_fingerprint": data["input_fingerprint"],
            "created_at": _iso(data.get("created_at")),
        }

    def _public_finding(self, row: Any) -> Dict[str, Any]:
        data = dict(row)
        return {
            "id": data["id"],
            "rule_id": data["rule_id"],
            "rule_name": data["rule_name"],
            "group": data["rule_group"],
            "section": data["section"],
            "severity": data["severity"],
            "score_item": data.get("score_item"),
            "verdict": data["verdict"],
            "problem": data["problem"],
            "reason": data.get("reason") or "",
            "details": _loads(data.get("details_json"), []),
            "deduction": data["deduction"],
            "review_status": data["review_status"],
            "review_note": data.get("review_note") or "",
            "reviewed_by": data.get("reviewed_by") or "",
            "reviewed_at": _iso(data.get("reviewed_at")),
        }

    def latest_by_refs(self, refs: Sequence[FrontpageRef]) -> Dict[FrontpageRef, Dict[str, Any]]:
        if not refs:
            return {}

        def op(session):
            found = {}
            unique_refs = list(dict.fromkeys(refs))
            for start in range(0, len(unique_refs), 500):
                rows = session.execute(sa.select(self.results).where(
                    self._result_ref_filter(unique_refs[start:start + 500]),
                    self.results.c.is_latest.is_(True),
                    self._result_scope(),
                )).mappings().all()
                found.update({FrontpageRef.from_record(row): self._public_result(row) for row in rows})
            return found

        return self._guard(op)

    def latest_detail(self, ref: FrontpageRef) -> Optional[Dict[str, Any]]:
        def op(session):
            row = session.execute(
                sa.select(self.results).where(self._result_ref_filter([ref]), self.results.c.is_latest.is_(True), self._result_scope())
            ).mappings().first()
            if row is None:
                return None
            findings = session.execute(
                sa.select(self.findings).where(self.findings.c.result_id == row["id"]).order_by(self.findings.c.rule_id)
            ).mappings().all()
            return {
                **self._public_result(row),
                "item_scores": _loads(row["item_scores_json"], []),
                "rule_verdicts": _loads(row["rule_verdicts_json"], {}),
                "notes": _loads(row["notes_json"], []),
                "findings": [self._public_finding(f) for f in findings],
            }

        return self._guard(op)

    def _recompute_result_aggregates(self, session: Any, result_id: str) -> None:
        """按当前非误报（review_status != 'false_alarm'）有效问题重算结果汇总与评分。"""
        result_row = session.execute(
            sa.select(
                self.results.c.item_scores_json,
                self.results.c.rule_verdicts_json,
            ).where(self.results.c.id == result_id)
        ).mappings().first()
        if result_row is None:
            return

        all_findings = session.execute(
            sa.select(self.findings).where(self.findings.c.result_id == result_id)
        ).mappings().all()

        effective = [f for f in all_findings if f["review_status"] != "false_alarm"]
        effective_fails = [f for f in effective if f["verdict"] == "fail"]

        fail_count = sum(1 for f in effective_fails if f["severity"] == "deduct")
        hint_count = sum(1 for f in effective_fails if f["severity"] == "hint")
        required_missing_count = sum(1 for f in effective_fails if f["severity"] == "required")
        data_gap_count = sum(1 for f in effective if f["verdict"] == "data_gap")

        rule_verdicts: Dict[str, str] = dict(_loads(result_row["rule_verdicts_json"], {}))
        by_rule: Dict[str, List[Any]] = defaultdict(list)
        for finding in all_findings:
            by_rule[finding["rule_id"]].append(finding)
        for rule_id, group in by_rule.items():
            active_group = [f for f in group if f["review_status"] != "false_alarm"]
            if any(f["verdict"] == "fail" for f in active_group):
                rule_verdicts[rule_id] = "fail"
            elif any(f["verdict"] == "data_gap" for f in active_group):
                rule_verdicts[rule_id] = "data_gap"
            else:
                rule_verdicts[rule_id] = (
                    "pass" if any(f["verdict"] == "fail" for f in group) else "not_applicable"
                )

        fails_by_score_item: Dict[str, List[Any]] = defaultdict(list)
        for finding in effective_fails:
            score_item_key = finding.get("score_item")
            if finding["severity"] == "deduct" and score_item_key in SCORE_ITEMS:
                fails_by_score_item[score_item_key].append(finding)

        item_deductions: Dict[str, float] = {}
        for key, item in SCORE_ITEMS.items():
            deduction = 0.0
            if key in fails_by_score_item:
                if item.per_item:
                    details = [
                        d
                        for f in fails_by_score_item[key]
                        for d in _loads(f.get("details_json"), [])
                        if isinstance(d, dict)
                    ]
                    indexed = {d.get("item_index") for d in details if d.get("item_index") is not None}
                    unindexed = sum(1 for d in details if d.get("item_index") is None)
                    count = max(1, len(indexed) + unindexed)
                    deduction = min(item.points * count, max_points(item))
                else:
                    deduction = item.points
            item_deductions[key] = deduction

        group_totals: Dict[Tuple[str, str], float] = defaultdict(float)
        for key, deduction in item_deductions.items():
            item = SCORE_ITEMS[key]
            group_totals[(item.section, item.klass)] += deduction
        total_deduction = 0.0
        for group_key, amount in group_totals.items():
            cap = GROUP_CAPS.get(group_key)
            total_deduction += min(amount, cap) if cap is not None else amount
        score = round(max(0.0, 100.0 - total_deduction) + 1e-9, 2)
        grade = grade_of(score)

        item_scores = _loads(result_row["item_scores_json"], [])
        if isinstance(item_scores, list):
            for entry in item_scores:
                if isinstance(entry, dict) and entry.get("key") in item_deductions:
                    entry["deduction"] = item_deductions[entry["key"]]

        completeness_judged = [
            verdict
            for rule_id, verdict in rule_verdicts.items()
            if verdict in ("pass", "fail")
            and RULES_BY_ID.get(rule_id) is not None
            and RULES_BY_ID[rule_id].group == "completeness"
            and RULES_BY_ID[rule_id].severity.value != "hint"
        ]
        completeness_rate = (
            round(
                sum(1 for v in completeness_judged if v == "pass") / len(completeness_judged)
                + 1e-9,
                2,
            )
            if completeness_judged
            else None
        )

        session.execute(
            self.results.update()
            .where(self.results.c.id == result_id)
            .values(
                score=score,
                grade=grade,
                fail_count=fail_count,
                hint_count=hint_count,
                required_missing_count=required_missing_count,
                data_gap_count=data_gap_count,
                completeness_rate=completeness_rate,
                item_scores_json=_dumps(item_scores),
                rule_verdicts_json=_dumps(rule_verdicts),
            )
        )

    def query_latest(
        self,
        *,
        department: str = "",
        start_date: str = "",
        end_date: str = "",
        grade: str = "",
        issue: str = "",
        rule_id: str = "",
        rule_verdict: str = "fail",
        institute_id: str = "",
        include_test_records: bool = True,
        record_refs: Optional[Sequence[FrontpageRef]] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """按已保存结果筛选（等级、问题类型、命中规则），用于只看已质控病历的列表。

        rule_id 用于从结果分析下钻：rule_verdict=fail 取该规则判为问题（含提示）的病历，
        data_gap 取该规则资料不足的病历。
        """
        refs = tuple(dict.fromkeys(record_refs)) if record_refs is not None else None
        if refs == ():
            return [], 0

        def op(session):
            t = self.results
            conditions = [t.c.is_latest.is_(True), self._result_scope()]
            if department:
                conditions.append(t.c.department == department)
            if start_date:
                conditions.append(t.c.discharge_date >= start_date)
            if end_date:
                conditions.append(t.c.discharge_date <= end_date)
            if grade:
                conditions.append(t.c.grade == grade)
            if issue == "fail":
                conditions.append(t.c.fail_count > 0)
            elif issue == "data_gap":
                conditions.append(t.c.data_gap_count > 0)
            elif issue == "hint":
                conditions.append(t.c.hint_count > 0)
            elif issue == "required_missing":
                conditions.append(t.c.required_missing_count > 0)
            elif issue == "clean":
                conditions.append(sa.and_(t.c.fail_count == 0, t.c.hint_count == 0, t.c.required_missing_count == 0))
            if institute_id:
                conditions.append(t.c.institute_id == institute_id)
            elif not include_test_records and not (
                refs and any(ref.institute_id == _CUSTOMER_TEST_INSTITUTE_ID for ref in refs)
            ):
                conditions.append(t.c.institute_id != _CUSTOMER_TEST_INSTITUTE_ID)
            if rule_id:
                f = self.findings
                conditions.append(
                    sa.exists().where(
                        sa.and_(
                            f.c.result_id == t.c.id,
                            f.c.rule_id == rule_id,
                            f.c.verdict == rule_verdict,
                            f.c.review_status != "false_alarm",
                        )
                    )
                )
            if refs is not None:
                if len(refs) > _RESULT_REF_INLINE_LIMIT:
                    conditions.append(self._large_result_ref_filter(refs, session.get_bind().dialect.name))
                else:
                    conditions.append(self._result_ref_filter(refs))
            where = sa.and_(*conditions)
            total = session.execute(sa.select(sa.func.count()).select_from(t).where(where)).scalar() or 0
            rows = session.execute(
                sa.select(t)
                .where(where)
                .order_by(
                    t.c.score.asc(),
                    sa.nullslast(t.c.discharge_date.desc()),
                    t.c.institute_id.asc(),
                    t.c.patient_id.asc(),
                    t.c.visit_id.asc(),
                )
                .offset(max(page - 1, 0) * page_size)
                .limit(page_size)
            ).mappings().all()
            return [self._public_result(row) for row in rows], int(total)

        return self._guard(op)

    def latest_rows_for_analytics(
        self,
        *,
        department: str = "",
        start_date: str = "",
        end_date: str = "",
        institute_id: str = "",
        include_test_records: bool = True,
    ) -> List[Dict[str, Any]]:
        def op(session):
            t = self.results
            conditions = [t.c.is_latest.is_(True), self._result_scope()]
            if institute_id:
                conditions.append(t.c.institute_id == institute_id)
            elif not include_test_records:
                conditions.append(t.c.institute_id != _CUSTOMER_TEST_INSTITUTE_ID)
            if department:
                conditions.append(t.c.department == department)
            if start_date:
                conditions.append(t.c.discharge_date >= start_date)
            if end_date:
                conditions.append(t.c.discharge_date <= end_date)
            rows = session.execute(
                sa.select(
                    t.c.id, t.c.record_key, t.c.department, t.c.score, t.c.grade, t.c.fail_count,
                    t.c.hint_count, t.c.required_missing_count, t.c.data_gap_count, t.c.rule_verdicts_json,
                ).where(sa.and_(*conditions))
            ).mappings().all()
            result_ids = [row["id"] for row in rows]
            l06_main_failed_ids: set[str] = set()
            if result_ids:
                f = self.findings
                for start in range(0, len(result_ids), 500):
                    matched_ids = session.execute(
                        sa.select(f.c.result_id).where(
                            f.c.result_id.in_(result_ids[start:start + 500]),
                            f.c.rule_id == "L-06",
                            f.c.score_item == "main_diag_code",
                            f.c.verdict == "fail",
                            f.c.review_status != "false_alarm",
                        )
                    ).scalars().all()
                    l06_main_failed_ids.update(matched_ids)
            return [
                {
                    **{k: row[k] for k in row.keys() if k != "rule_verdicts_json"},
                    "rule_verdicts": _loads(row["rule_verdicts_json"], {}),
                    "l06_main_failed": row["id"] in l06_main_failed_ids,
                }
                for row in rows
            ]

        return self._guard(op)

    def latest_findings(self, result_ids: Sequence[str]) -> List[Dict[str, Any]]:
        if not result_ids:
            return []

        def op(session):
            found: List[Dict[str, Any]] = []
            ids = list(result_ids)
            for start in range(0, len(ids), 500):
                rows = session.execute(
                    sa.select(self.findings)
                    .where(
                        self.findings.c.result_id.in_(ids[start:start + 500]),
                        sa.exists().where(self.results.c.id == self.findings.c.result_id, self._result_scope()),
                    )
                    .order_by(self.findings.c.result_id.asc(), self.findings.c.rule_id.asc(), self.findings.c.id.asc())
                ).mappings().all()
                found.extend({**self._public_finding(row), "result_id": row["result_id"], "record_key": row["record_key"]} for row in rows)
            found.sort(key=lambda item: (item["result_id"], item["rule_id"], item["id"]))
            return found

        return self._guard(op)

    # ---------- 复核 ----------

    def review_finding(self, finding_id: str, *, status: str, note: str, reviewer: str) -> Dict[str, Any]:
        if status not in REVIEW_STATUSES:
            raise ValueError("复核状态只能是 pending / confirmed / false_alarm")

        def locate_case(session):
            return session.execute(
                sa.select(
                    self.findings.c.result_id,
                    self.results.c.institute_id,
                    self.results.c.patient_id,
                    self.results.c.visit_id,
                )
                .join(self.results, self.results.c.id == self.findings.c.result_id)
                .where(self.findings.c.id == finding_id, self._result_scope())
            ).mappings().first()

        located = self._guard(locate_case)
        if located is None:
            raise FrontpageQcNotFound("问题不存在")
        case_ref = FrontpageRef(located["institute_id"], located["patient_id"], located["visit_id"])
        legacy_key = case_ref.legacy_key()

        def op(session):
            # 与 save_outcome 复用同一病例级锁，消除并发重跑时复核落到旧结果行导致丢失沿用的竞态
            _acquire_pg_advisory_xact_lock(session, legacy_key)
            row = session.execute(
                sa.select(self.findings)
                .join(self.results, self.results.c.id == self.findings.c.result_id)
                .where(self.findings.c.id == finding_id, self._result_scope())
            ).mappings().first()
            if row is None:
                raise FrontpageQcNotFound("问题不存在")
            latest = session.execute(
                sa.select(self.results.c.is_latest).where(self.results.c.id == row["result_id"])
            ).scalar()
            if not latest:
                raise FrontpageQcNotFound("该问题所在结果已被重新质控替换，请刷新后在最新结果上复核")
            values = {
                "review_status": status,
                "review_note": (note or "")[:500] or None,
                "reviewed_by": reviewer if status != "pending" else None,
                "reviewed_at": _now() if status != "pending" else None,
            }
            session.execute(self.findings.update().where(self.findings.c.id == finding_id).values(**values))
            self._recompute_result_aggregates(session, row["result_id"])
            session.commit()
            updated = session.execute(
                sa.select(self.findings)
                .join(self.results, self.results.c.id == self.findings.c.result_id)
                .where(self.findings.c.id == finding_id, self._result_scope())
            ).mappings().first()
            return self._public_finding(updated)

        with _get_local_lock(f"case:{legacy_key}"):
            return self._guard(op)


def date_text(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()[:10]
    return str(value or "")[:10]
