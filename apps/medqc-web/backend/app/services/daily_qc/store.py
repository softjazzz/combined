"""轻量计划/触发账本；不读取质控结果大JSON、不在运行时建表。"""

from datetime import timedelta, timezone
import json
from uuid import uuid4
from zoneinfo import ZoneInfo

import sqlalchemy as sa

from .contracts import (
    next_occurrence,
    occurrence,
    run_identity,
    job_identity,
    utc_naive,
)


def tables(schema=None):
    metadata = sa.MetaData()
    plans = sa.Table(
        "daily_qc_plans",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(64), nullable=False, index=True),
        sa.Column("definition_json", sa.Text, nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False, default=False),
        sa.Column("revision", sa.Integer, nullable=False, default=1),
        sa.Column("next_due", sa.DateTime, nullable=False, index=True),
        sa.Column("pending_run_id", sa.String(36)),
        sa.Column("last_job_id", sa.String(36)),
        sa.Column("last_status", sa.String(32)),
        sa.Column("lease_token", sa.String(36)),
        sa.Column("lease_until", sa.DateTime),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        schema=schema,
    )
    runs = sa.Table(
        "daily_qc_runs",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("plan_id", sa.String(36), sa.ForeignKey(plans.c.id), nullable=False),
        sa.Column("local_date", sa.String(10), nullable=False),
        sa.Column("scheduled_for", sa.DateTime, nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("definition_json", sa.Text, nullable=False),
        sa.Column("job_id", sa.String(36)),
        sa.Column("attempts", sa.Integer, nullable=False, default=0),
        sa.Column("reason", sa.String(64)),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("plan_id", "local_date", name="uq_daily_qc_plan_day"),
        schema=schema,
    )
    return metadata, plans, runs


class PlanConflict(ValueError):
    pass


class ScheduleStore:
    def __init__(self, session_factory, schema=None):
        self.sessions = session_factory
        _, self.plans, self.runs = tables(schema)

    def list(self, owner_id, *, all_owners: bool = False):
        with self.sessions() as session:
            stmt = sa.select(self.plans)
            if not all_owners:
                stmt = stmt.where(self.plans.c.owner_id == owner_id)
            return [
                dict(row)
                for row in session.execute(
                    stmt.order_by(self.plans.c.created_at.desc()).limit(100)
                ).mappings()
            ]

    def history(self, plan_id, owner_id, *, all_owners: bool = False):
        with self.sessions() as session:
            conds = [self.plans.c.id == plan_id]
            if not all_owners:
                conds.append(self.plans.c.owner_id == owner_id)
            if (
                session.execute(
                    sa.select(self.plans.c.id).where(*conds)
                ).first()
                is None
            ):
                raise KeyError("plan_not_found")
            return [
                dict(row)
                for row in session.execute(
                    sa.select(self.runs)
                    .where(self.runs.c.plan_id == plan_id)
                    .order_by(self.runs.c.scheduled_for.desc())
                    .limit(30)
                ).mappings()
            ]

    def save(
        self,
        owner_id,
        definition,
        now,
        plan_id=None,
        revision=None,
        *,
        all_owners: bool = False,
    ):
        current = utc_naive(now)
        with self.sessions() as session, session.begin():
            values = dict(
                definition_json=json.dumps(definition, ensure_ascii=False),
                enabled=definition["enabled"],
                next_due=next_occurrence(now, definition),
                updated_at=current,
            )
            if plan_id is None:
                if (
                    session.execute(
                        sa.select(sa.func.count())
                        .select_from(self.plans)
                        .where(self.plans.c.owner_id == owner_id)
                    ).scalar_one()
                    >= 100
                ):
                    raise PlanConflict("schedule_limit")
                plan_id = str(uuid4())
                session.execute(
                    self.plans.insert().values(
                        id=plan_id,
                        owner_id=owner_id,
                        revision=1,
                        created_at=current,
                        **values,
                    )
                )
            else:
                conds = [
                    self.plans.c.id == plan_id,
                    self.plans.c.revision == revision,
                ]
                if not all_owners:
                    conds.append(self.plans.c.owner_id == owner_id)
                updated = session.execute(
                    self.plans.update()
                    .where(*conds)
                    .values(revision=self.plans.c.revision + 1, **values)
                )
                if updated.rowcount != 1:
                    raise PlanConflict("plan_changed_or_unavailable")
            return plan_id

    def delete(self, plan_id, owner_id, *, all_owners: bool = False):
        with self.sessions() as session, session.begin():
            conds = [self.plans.c.id == plan_id]
            if not all_owners:
                conds.append(self.plans.c.owner_id == owner_id)
            existing = session.execute(
                sa.select(self.plans.c.id).where(*conds).with_for_update()
            ).first()
            if existing is None:
                raise KeyError("plan_not_found")
            session.execute(
                self.runs.delete().where(self.runs.c.plan_id == plan_id)
            )
            deleted = session.execute(self.plans.delete().where(*conds))
            if deleted.rowcount != 1:
                raise KeyError("plan_not_found")
            return True

    def claim(self, now):
        current = utc_naive(now)
        available = sa.or_(
            self.plans.c.lease_until.is_(None), self.plans.c.lease_until <= current
        )
        eligible = sa.or_(
            self.plans.c.pending_run_id.is_not(None),
            sa.and_(self.plans.c.enabled.is_(True), self.plans.c.next_due <= current),
        )
        with self.sessions() as session, session.begin():
            row = (
                session.execute(
                    sa.select(self.plans)
                    .where(available, eligible)
                    .order_by(self.plans.c.next_due)
                    .limit(1)
                    .with_for_update(skip_locked=True)
                )
                .mappings()
                .first()
            )
            if not row:
                return None
            token = str(uuid4())
            changed = session.execute(
                self.plans.update()
                .where(self.plans.c.id == row["id"], available)
                .values(lease_token=token, lease_until=current + timedelta(minutes=5))
            )
            if changed.rowcount != 1:
                return None
            return {**dict(row), "lease_token": token}

    def prepare(self, claimed, now, *, previous_job_status=None):
        """在同一计划租约下分配逐日身份；旧周期最多记录一条汇总missed。"""
        current = utc_naive(now)
        with self.sessions() as session, session.begin():
            row = (
                session.execute(
                    sa.select(self.plans)
                    .where(
                        self.plans.c.id == claimed["id"],
                        self.plans.c.lease_token == claimed["lease_token"],
                    )
                    .with_for_update()
                )
                .mappings()
                .one()
            )
            if row["pending_run_id"]:
                run = (
                    session.execute(
                        sa.select(self.runs).where(
                            self.runs.c.id == row["pending_run_id"]
                        )
                    )
                    .mappings()
                    .one()
                )
                session.execute(
                    self.runs.update()
                    .where(self.runs.c.id == run["id"])
                    .values(attempts=self.runs.c.attempts + 1, updated_at=current)
                )
                return {**dict(run), "attempts": run["attempts"] + 1}
            if not row["enabled"] or row["next_due"] > current:
                # 领取后管理员可能修改时间或停用；不能用旧领取结果提前触发新计划。
                return None
            definition = json.loads(row["definition_json"])
            due = row["next_due"]
            local_day = (
                due.replace(tzinfo=timezone.utc)
                .astimezone(ZoneInfo(definition["timezone"]))
                .date()
            )
            run_id = run_identity(row["id"], local_day.isoformat())
            old = (
                session.execute(sa.select(self.runs).where(self.runs.c.id == run_id))
                .mappings()
                .first()
            )
            next_due = occurrence(
                local_day + timedelta(days=1),
                definition["time_of_day"],
                definition["timezone"],
            )
            state = (
                "skipped_disabled"
                if not row["enabled"]
                else "missed"
                if current - due > timedelta(hours=1)
                else "skipped_overlap"
                if previous_job_status not in {None, "completed", "failed", "canceled", "missing"}
                else "submitting"
            )
            if state == "missed":
                # 跳过历史积压，保留当前日仍在宽限内的那一次；不追补全部旧日期。
                today = now.astimezone(ZoneInfo(definition["timezone"])).date()
                today_due = occurrence(
                    today, definition["time_of_day"], definition["timezone"]
                )
                next_due = (
                    today_due
                    if today_due > due and current - today_due <= timedelta(hours=1)
                    else next_occurrence(now, definition)
                )
            run = dict(
                id=run_id,
                plan_id=row["id"],
                local_date=local_day.isoformat(),
                scheduled_for=due,
                state=state,
                definition_json=row["definition_json"],
                job_id=job_identity(run_id),
                attempts=1,
                reason=state if state != "submitting" else None,
                created_at=current,
                updated_at=current,
            )
            if old is None:
                session.execute(self.runs.insert().values(**run))
            else:
                run = dict(old)
            pending = run_id if run["state"] == "submitting" else None
            session.execute(
                self.plans.update()
                .where(self.plans.c.id == row["id"])
                .values(
                    next_due=next_due,
                    pending_run_id=pending,
                    last_status=run["state"],
                    updated_at=current,
                )
            )
            return run

    def finish(self, claimed, run_id, state, now, *, reason=None, job_id=None):
        current = utc_naive(now)
        with self.sessions() as session, session.begin():
            changes = dict(
                pending_run_id=None,
                last_status=state,
                lease_token=None,
                lease_until=None,
                updated_at=current,
            )
            if job_id:
                changes["last_job_id"] = job_id
            changed = session.execute(
                self.plans.update()
                .where(
                    self.plans.c.id == claimed["id"],
                    self.plans.c.lease_token == claimed["lease_token"],
                )
                .values(**changes)
            )
            if changed.rowcount != 1:
                return False
            session.execute(
                self.runs.update()
                .where(self.runs.c.id == run_id)
                .values(state=state, reason=reason, updated_at=current)
            )
            return True

    def current(self, plan_id):
        with self.sessions() as session:
            row = (
                session.execute(sa.select(self.plans).where(self.plans.c.id == plan_id))
                .mappings()
                .first()
            )
            return dict(row) if row else None

    def defer(self, claimed, run_id, now):
        """保留租约与固定任务身份，只记录安全原因，不保存异常中的患者材料。"""
        with self.sessions() as session, session.begin():
            owns_lease = session.execute(
                sa.select(self.plans.c.id)
                .where(
                    self.plans.c.id == claimed["id"],
                    self.plans.c.lease_token == claimed["lease_token"],
                )
                .with_for_update()
            ).first()
            if owns_lease:
                session.execute(
                    self.runs.update()
                    .where(self.runs.c.id == run_id)
                    .values(reason="submission_interrupted", updated_at=utc_naive(now))
                )

    def release(self, claimed):
        with self.sessions() as session, session.begin():
            session.execute(
                self.plans.update()
                .where(
                    self.plans.c.id == claimed["id"],
                    self.plans.c.lease_token == claimed["lease_token"],
                )
                .values(lease_token=None, lease_until=None)
            )
