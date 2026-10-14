"""首页质控 V2：任务、结果、问题的持久化（qc schema 下三张表，迁移 20261013_000048）。

表结构与迁移保持一致，由 test_frontpage_qc_v2_store 的迁移往返测试保证。
表未迁移时抛 FrontpageQcStoreUnavailable，由接口层转成 503，不影响其他质控功能。
"""
from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from datetime import date, datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import sqlalchemy as sa
from sqlalchemy.exc import SQLAlchemyError

from .loader import FrontpageRef
from .model import FrontpageQcOutcome

RUNS_TABLE = "frontpage_qc_runs"
RESULTS_TABLE = "frontpage_qc_results"
FINDINGS_TABLE = "frontpage_qc_findings"

RUN_ACTIVE_STATUSES = ("queued", "running")
REVIEW_STATUSES = ("pending", "confirmed", "false_alarm")


class FrontpageQcStoreUnavailable(RuntimeError):
    """存储表不存在或数据库不可用。"""


class FrontpageQcNotFound(LookupError):
    pass


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


def ref_key(ref: FrontpageRef) -> str:
    return ref.as_key()


def _finding_signature(rule_id: str, details: Any) -> str:
    return f"{rule_id}|{_dumps(details)}"


class FrontpageQcStore:
    def __init__(self, session_factory: Callable[[], Any], schema: Optional[str] = None) -> None:
        self.session_factory = session_factory
        self.runs, self.results, self.findings = build_tables(schema)

    # ---------- 通用 ----------

    def _guard(self, fn: Callable[[Any], Any]) -> Any:
        try:
            with self.session_factory() as session:
                return fn(session)
        except SQLAlchemyError as exc:
            raise FrontpageQcStoreUnavailable(
                "首页质控存储不可用：请确认已执行 20261013_000048 迁移并检查数据库连接"
            ) from exc

    def create_all(self, engine: Any) -> None:
        """仅供测试初始化使用；生产环境由 alembic 迁移建表。"""
        self.runs.metadata.create_all(engine)

    # ---------- 任务 ----------

    def create_run(self, *, created_by: str, refs: Sequence[FrontpageRef], filters: Dict[str, Any], ruleset_version: str) -> Dict[str, Any]:
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
            row = session.execute(sa.select(self.runs).where(self.runs.c.id == run_id)).mappings().first()
            if row is None:
                raise FrontpageQcNotFound("质控任务不存在")
            return self._public_run(row)

        return self._guard(op)

    def run_refs(self, run_id: str) -> List[FrontpageRef]:
        def op(session):
            text = session.execute(sa.select(self.runs.c.record_refs_json).where(self.runs.c.id == run_id)).scalar()
            if text is None:
                raise FrontpageQcNotFound("质控任务不存在")
            return [FrontpageRef(**item) for item in _loads(text, [])]

        return self._guard(op)

    def list_runs(self, *, created_by: Optional[str] = None, statuses: Iterable[str] = (), limit: int = 20) -> List[Dict[str, Any]]:
        def op(session):
            query = sa.select(self.runs).order_by(self.runs.c.created_at.desc()).limit(limit)
            if created_by:
                query = query.where(self.runs.c.created_by == created_by)
            status_list = list(statuses)
            if status_list:
                query = query.where(self.runs.c.status.in_(status_list))
            return [self._public_run(row) for row in session.execute(query).mappings().all()]

        return self._guard(op)

    def update_run(self, run_id: str, **values: Any) -> None:
        if "failed_records" in values:
            values["failed_records_json"] = _dumps(values.pop("failed_records"))
        values["updated_at"] = _now()

        def op(session):
            session.execute(self.runs.update().where(self.runs.c.id == run_id).values(**values))
            session.commit()

        self._guard(op)

    def request_cancel(self, run_id: str) -> Dict[str, Any]:
        def op(session):
            row = session.execute(sa.select(self.runs).where(self.runs.c.id == run_id)).mappings().first()
            if row is None:
                raise FrontpageQcNotFound("质控任务不存在")
            if row["status"] in RUN_ACTIVE_STATUSES:
                values: Dict[str, Any] = {"cancel_requested": True, "updated_at": _now()}
                if row["status"] == "queued":
                    values.update(status="cancelled", finished_at=_now())
                session.execute(self.runs.update().where(self.runs.c.id == run_id).values(**values))
                session.commit()
                row = session.execute(sa.select(self.runs).where(self.runs.c.id == run_id)).mappings().first()
            return self._public_run(row)

        return self._guard(op)

    def is_cancel_requested(self, run_id: str) -> bool:
        def op(session):
            return bool(session.execute(sa.select(self.runs.c.cancel_requested).where(self.runs.c.id == run_id)).scalar())

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
        key = ref_key(ref)
        now = _now()
        result_id = str(uuid.uuid4())

        def op(session):
            # 沿用上一次结果中相同问题的复核结论，避免重新质控后重复复核
            previous_reviews: Dict[str, Dict[str, Any]] = {}
            previous = session.execute(
                sa.select(self.results.c.id).where(self.results.c.record_key == key, self.results.c.is_latest.is_(True))
            ).scalars().all()
            if previous:
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
                    is_latest=True,
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
            session.commit()
            return result_id

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

    def latest_by_keys(self, keys: Sequence[str]) -> Dict[str, Dict[str, Any]]:
        if not keys:
            return {}

        def op(session):
            rows = session.execute(
                sa.select(self.results).where(self.results.c.record_key.in_(list(keys)), self.results.c.is_latest.is_(True))
            ).mappings().all()
            return {row["record_key"]: self._public_result(row) for row in rows}

        return self._guard(op)

    def latest_detail(self, ref: FrontpageRef) -> Optional[Dict[str, Any]]:
        key = ref_key(ref)

        def op(session):
            row = session.execute(
                sa.select(self.results).where(self.results.c.record_key == key, self.results.c.is_latest.is_(True))
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
        record_keys: Optional[Sequence[str]] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """按已保存结果筛选（等级、问题类型、命中规则），用于只看已质控病历的列表。

        rule_id 用于从结果分析下钻：rule_verdict=fail 取该规则判为问题（含提示）的病历，
        data_gap 取该规则资料不足的病历。
        """

        def op(session):
            t = self.results
            conditions = [t.c.is_latest.is_(True)]
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
            elif issue == "clean":
                conditions.append(sa.and_(t.c.fail_count == 0, t.c.hint_count == 0, t.c.required_missing_count == 0))
            if institute_id:
                conditions.append(t.c.institute_id == institute_id)
            if rule_id:
                f = self.findings
                conditions.append(
                    sa.exists().where(
                        sa.and_(f.c.result_id == t.c.id, f.c.rule_id == rule_id, f.c.verdict == rule_verdict)
                    )
                )
            if record_keys is not None:
                conditions.append(t.c.record_key.in_(list(record_keys)))
            where = sa.and_(*conditions)
            total = session.execute(sa.select(sa.func.count()).select_from(t).where(where)).scalar() or 0
            rows = session.execute(
                sa.select(t)
                .where(where)
                .order_by(t.c.score.asc(), t.c.discharge_date.desc(), t.c.record_key)
                .offset(max(page - 1, 0) * page_size)
                .limit(page_size)
            ).mappings().all()
            return [self._public_result(row) for row in rows], int(total)

        return self._guard(op)

    def latest_rows_for_analytics(
        self, *, department: str = "", start_date: str = "", end_date: str = "", institute_id: str = ""
    ) -> List[Dict[str, Any]]:
        def op(session):
            t = self.results
            conditions = [t.c.is_latest.is_(True)]
            if institute_id:
                conditions.append(t.c.institute_id == institute_id)
            if department:
                conditions.append(t.c.department == department)
            if start_date:
                conditions.append(t.c.discharge_date >= start_date)
            if end_date:
                conditions.append(t.c.discharge_date <= end_date)
            rows = session.execute(
                sa.select(
                    t.c.id, t.c.record_key, t.c.department, t.c.score, t.c.grade, t.c.fail_count,
                    t.c.hint_count, t.c.data_gap_count, t.c.rule_verdicts_json,
                ).where(sa.and_(*conditions))
            ).mappings().all()
            return [
                {**{k: row[k] for k in row.keys() if k != "rule_verdicts_json"}, "rule_verdicts": _loads(row["rule_verdicts_json"], {})}
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
                    sa.select(self.findings).where(self.findings.c.result_id.in_(ids[start:start + 500]))
                ).mappings().all()
                found.extend({**self._public_finding(row), "result_id": row["result_id"], "record_key": row["record_key"]} for row in rows)
            return found

        return self._guard(op)

    # ---------- 复核 ----------

    def review_finding(self, finding_id: str, *, status: str, note: str, reviewer: str) -> Dict[str, Any]:
        if status not in REVIEW_STATUSES:
            raise ValueError("复核状态只能是 pending / confirmed / false_alarm")

        def op(session):
            row = session.execute(sa.select(self.findings).where(self.findings.c.id == finding_id)).mappings().first()
            if row is None:
                raise FrontpageQcNotFound("问题不存在")
            latest = session.execute(sa.select(self.results.c.is_latest).where(self.results.c.id == row["result_id"])).scalar()
            if not latest:
                raise FrontpageQcNotFound("该问题所在结果已被重新质控替换，请刷新后在最新结果上复核")
            values = {
                "review_status": status,
                "review_note": (note or "")[:500] or None,
                "reviewed_by": reviewer if status != "pending" else None,
                "reviewed_at": _now() if status != "pending" else None,
            }
            session.execute(self.findings.update().where(self.findings.c.id == finding_id).values(**values))
            session.commit()
            updated = session.execute(sa.select(self.findings).where(self.findings.c.id == finding_id)).mappings().first()
            return self._public_finding(updated)

        return self._guard(op)


def date_text(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()[:10]
    return str(value or "")[:10]
