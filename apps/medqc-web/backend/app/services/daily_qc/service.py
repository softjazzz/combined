"""计划授权、选项和正式批量接纳适配；不包含临床判断。"""

from datetime import datetime, timezone, date
import json

from fastapi import HTTPException
import sqlalchemy as sa
from starlette.requests import Request

from .contracts import PlanInput, date_window, utc_naive
from .store import ScheduleStore


def default_store():
    from ...database.connection import SessionLocal, DB_SCHEMA_MODE

    if SessionLocal is None:
        raise RuntimeError("schedule_storage_unavailable")
    return ScheduleStore(SessionLocal, "qc" if DB_SCHEMA_MODE == "split" else None)


def require_manager(store, actor_id):
    from ..defect_rectification_service import _person, RectificationError

    try:
        with store.sessions() as session:
            person = _person(session, actor_id)
        if "admin" not in person["roles"]:
            raise HTTPException(403, "仅持久管理员可管理定时质控")
        return person
    except RectificationError as exc:
        raise HTTPException(exc.status, "管理账号不可用或权限不足") from exc


def options(store, actor_id, *, institute_id=None, scope="final"):
    require_manager(store, actor_id)
    from ..clinical_source_policy import fixed_cdm
    from ..clinical_sources import ordinary_snapshot
    from ...database.clinical_connection import selected

    # 管理路由仍绑定业务库；只有临床筛选读取进入固定来源，退出后恢复。
    if fixed_cdm():
        with selected(ordinary_snapshot()):
            return _options(store, institute_id=institute_id, scope=scope)
    return _options(store, institute_id=institute_id, scope=scope)


def _options(store, *, institute_id, scope):
    from ...database.models.cdm import InpatRegistration, MedicalRecordFrontpage
    from ..clinical_read import clinical_query
    from ..qc_workspace.record_repository import RecordRepository
    from ..qc_rule_sets import list_sichuan_rule_sets

    from ...database.clinical_connection import configured

    if configured():
        from ..clinical_case_catalog import schedule_options

        clinical_options = schedule_options(scope=scope, institute_id=institute_id)
        institutes = clinical_options["institutes"]
        filters = clinical_options
    else:
        with store.sessions() as session:
            institutes = sorted(
                {
                    str(row[0]).strip()
                    for model in (InpatRegistration, MedicalRecordFrontpage)
                    for row in clinical_query(session, model.institute_id).distinct().all()
                    if row[0] and str(row[0]).strip()
                }
            )
        filters = (
            RecordRepository(session_factory=store.sessions).get_record_filters(
                scope=scope, department=None, institute_id=institute_id
            )
            if institute_id
            else {"departments": []}
        )
    if institute_id and institute_id not in institutes:
        raise HTTPException(422, "请选择已同步机构")
    return {
        "institutes": institutes,
        "departments": filters["departments"],
        "rule_sets": [
            {
                "key": item["rule_set_key"],
                "name": item["rule_set_name"],
                "scope": item["scope"],
                "description": item["description"],
            }
            for item in list_sichuan_rule_sets()
            if item["rule_set_key"] != "luxian_0916_qc_v1"
        ],
    }


def validate_definition(store, actor_id, data: PlanInput):
    selected = data.model_dump()
    choices = options(store, actor_id, institute_id=data.institute_id, scope=data.scope)
    if data.department and data.department not in choices["departments"]:
        raise HTTPException(422, "所选科室不在当前机构和场景中")
    from ..qc_rule_sets import get_sichuan_rule_set
    from ..luxian_0609.phase_scope import get_luxian_0609_acceptance_only_rule_ids

    rule_set = get_sichuan_rule_set(data.rule_set_key)
    if rule_set is None or data.rule_set_key == "luxian_0916_qc_v1":
        raise HTTPException(422, "未知质控规则集")
    if (
        rule_set.scope not in (None, "", "all", data.scope)
        and data.rule_set_key != "luxian_0609_qc_v1"
    ):
        raise HTTPException(422, "规则集与病历场景不一致")
    if data.rule_ids and data.rule_set_key != "luxian_0609_qc_v1":
        raise HTTPException(422, "该规则集仅支持整套定时运行")
    if (
        len(data.rule_ids) != len(set(data.rule_ids))
        or not set(data.rule_ids).issubset(rule_set.rule_ids)
        or set(data.rule_ids) & set(get_luxian_0609_acceptance_only_rule_ids())
    ):
        raise HTTPException(422, "规则选择不在正式可运行范围")
    return selected


def project_plan(row):
    def iso(value):
        return value.replace(tzinfo=timezone.utc).isoformat() if value else None

    return {
        "id": row["id"],
        **json.loads(row["definition_json"]),
        "enabled": row["enabled"],
        "revision": row["revision"],
        "next_run_at": iso(row["next_due"]),
        "last_status": row["last_status"],
        "last_job_id": row["last_job_id"],
    }


def project_run(row):
    return {
        "id": row["id"],
        "local_date": row["local_date"],
        "state": row["state"],
        "scheduled_for": row["scheduled_for"].replace(tzinfo=timezone.utc).isoformat(),
        "job_id": row["job_id"] if row["state"] == "submitted" else None,
        "reason": row["reason"],
        "attempts": row["attempts"],
    }


class BatchAdmission:
    """复用手工入口的规则/快照/Gateway/Outbox/旧Worker链。"""

    def __init__(self, store):
        self.store = store

    def job_status(self, job_id):
        from ..custom_qc_workspace_service import CustomQCWorkspaceService, _session

        workspace = CustomQCWorkspaceService(readonly=True)
        with _session() as session:
            status = session.execute(
                sa.select(workspace._batch_job_table.c.status).where(
                    workspace._batch_job_table.c.id == job_id
                )
            ).scalar_one_or_none()
        return status or "missing"

    async def submit(self, claimed, run):
        from ...routers.qc_sichuan import (
            admit_workspace_batch_job,
            SichuanWorkspaceBatchJobCreateRequest,
            get_qc_service,
            _run_sichuan_workspace_batch_job,
        )
        from ..custom_qc_workspace_service import CustomQCWorkspaceService
        from ..detached_task_runner import submit_detached_task
        from ..qc_dispatch.dispatcher import should_submit_detached_qc_task
        from ..product_activation import get_product_activation_service

        workspace = CustomQCWorkspaceService(readonly=True)
        existing = workspace.get_scheduled_batch_job(scheduled_run_id=run["id"])
        if existing:
            if existing["created_by"] != claimed["owner_id"]:
                raise HTTPException(403, "计划任务账号不匹配")
            try:
                require_manager(self.store, claimed["owner_id"])
            except HTTPException as exc:
                if exc.status_code != 403:
                    raise
                # 只补登记先前已接纳的任务，保留重叠保护；账号失效不重新投递。
                return existing["id"]
            get_product_activation_service().enforce()
            if existing["status"] == "queued" and should_submit_detached_qc_task(
                existing
            ):
                # 重复投递仍由原Worker领取CAS控制；不新建任务或重置结果。
                submit_detached_task(
                    "daily_qc_recover", _run_sichuan_workspace_batch_job, existing["id"]
                )
            return existing["id"]
        person = require_manager(self.store, claimed["owner_id"])
        get_product_activation_service().enforce()
        current = self.store.current(claimed["id"])
        if not current or not current["enabled"]:
            raise HTTPException(409, "schedule_disabled")
        definition = json.loads(run["definition_json"])
        start, end = date_window(date.fromisoformat(run["local_date"]), definition)
        payload = SichuanWorkspaceBatchJobCreateRequest(
            rule_set_key=definition["rule_set_key"],
            rule_ids=definition["rule_ids"] or None,
            scope=definition["scope"],
            department=definition["department"] or None,
            date_field=definition["date_field"],
            start_date=start,
            end_date=end,
            run_mode="parallel",
        )
        request = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/internal/daily-qc",
                "headers": [],
            }
        )
        result = await admit_workspace_batch_job(
            request,
            payload,
            {**person, "roles": list(person["roles"])},
            await get_qc_service(),
            scheduled_origin={
                "run_id": run["id"],
                "plan_id": claimed["id"],
                "scheduled_for": run["scheduled_for"]
                .replace(tzinfo=timezone.utc)
                .isoformat(),
                "institute_id": definition["institute_id"],
                "max_records": definition["max_records"],
            },
        )
        job_id = result["data"]["id"]
        if job_id != run["job_id"]:
            raise RuntimeError("scheduled_job_identity_mismatch")
        return job_id


async def tick(store, admission, now=None, *, limit=20):
    """每轮至多处理20个计划；不重试任何已经完成的临床任务。"""
    now = now or datetime.now(timezone.utc)
    states = []
    for _ in range(limit):
        claimed = store.claim(now)
        if not claimed:
            break
        run = None
        try:
            status = (
                admission.job_status(claimed["last_job_id"])
                if claimed["last_job_id"]
                else None
            )
            run = store.prepare(claimed, now, previous_job_status=status)
            if run is None:
                continue
            if run["state"] != "submitting":
                store.release(claimed)
                states.append(run["state"])
                continue
            if (utc_naive(now) - run["scheduled_for"]).total_seconds() > 3600:
                # 旧回执可以补登记；过期且尚未建任务的周期不能在恢复时补发。
                if admission.job_status(run["job_id"]) == "missing":
                    store.finish(claimed, run["id"], "missed", now, reason="missed")
                    states.append("missed")
                    continue
            if run["attempts"] > 3:
                # 只查固定ID：创建成功但回执丢失仍可收口；禁止借恢复重复开新轮。
                if admission.job_status(run["job_id"]) == "missing":
                    store.finish(
                        claimed,
                        run["id"],
                        "failed",
                        now,
                        reason="recovery_budget_exhausted",
                    )
                    states.append("failed")
                    continue
            job_id = await admission.submit(claimed, run)
            store.finish(claimed, run["id"], "submitted", now, job_id=job_id)
            states.append("submitted")
        except HTTPException as exc:
            if exc.status_code >= 500 and run is not None:
                store.defer(claimed, run["id"], now)
                states.append("pending_recovery")
                continue
            state = (
                "empty"
                if exc.status_code == 422
                and exc.detail == "当前筛选条件下没有可执行病历"
                else "failed"
            )
            reason = (
                "empty"
                if state == "empty"
                else "disabled"
                if exc.detail == "schedule_disabled"
                else "permission_denied"
                if exc.status_code == 403
                else "admission_rejected"
            )
            if run:
                store.finish(claimed, run["id"], state, now, reason=reason)
            states.append(state)
        except Exception:
            # 异常可能发生在任务已提交后：保留pending，租约到期再按固定ID恢复。
            if run is not None:
                store.defer(claimed, run["id"], now)
            states.append("pending_recovery")
        finally:
            if run is None or run["state"] != "submitting":
                store.release(claimed)
    return states
