"""缺陷快捷分区只读搬运整改与申诉 owner；没有任务不代表未整改。"""

from sqlalchemy import select, tuple_

from ..database.models.defect_rectification import DefectRectification
from ..database.models.qc import QCAppeal
from .defect_rectification_service import RectificationError, _manager, _person
from .appeal_manual_target_service import (
    AppealManualTargetConflict, AppealManualTargetNotFound, resolve_task_manual_defect_target,
)
from .record_review_service import (
    RecordReviewConflict, _batch_job_table, _workspace_scene_from_job,
)
from .custom_qc_workspace_service import CustomQCWorkspaceService

WORKFLOW_FILTERS = frozenset({"clinical_appeal", "pending_rectification"})
SOURCE_KEYS = (
    "institute_id", "patient_id", "visit_id", "scene", "target_kind", "target_id",
    "root_job_id", "envelope_id",
)


def source_key(source):
    values = tuple(str(source.get(key) or "").strip() for key in SOURCE_KEYS)
    return values if all(values) else None


def filter_defect_workflow(rows, *, workflow, actor_id, session_factory, scene):
    """按本轮冻结引用匹配，全部筛选不调用此服务；故障交由入口返回503。"""
    if workflow not in WORKFLOW_FILTERS:
        raise ValueError("缺陷流程筛选无效")
    with session_factory() as session:
        actor = _person(session, actor_id)
        if not _manager(actor):
            raise RectificationError("缺陷查询权限不足", 403)
        if "admin" not in actor["roles"] and not actor["institute_id"]:
            raise RectificationError("账号缺少可信医院归属", 403)
        scoped = [row for row in rows if "admin" in actor["roles"]
                  or row["institute_id"] == actor["institute_id"]]
        jobs = _load_jobs(session, scoped)
        scenes = {}
        targets = []
        for row in scoped:
            identity = tuple(row[key] for key in SOURCE_KEYS[:3])
            try:
                if row["source"] == "auto":
                    job = str(row.get("root_job_id") or "")
                    envelope = str(row.get("envelope_id") or "")
                    if not job or not envelope or not row.get("rule_id"):
                        continue
                    if job not in jobs or row.get("source_unique") is not True:
                        continue
                    scene_key = (*identity, job)
                    if scene_key not in scenes:
                        scenes[scene_key] = _workspace_scene_from_job(jobs[job], identity=identity)
                    source = {**row, "scene": scenes[scene_key],
                              "target_kind": "canonical_defect",
                              "target_id": row["rule_id"]}
                else:
                    if row["status"] != "approved":
                        continue
                    source = resolve_task_manual_defect_target(
                        defect_id=row["defect_id"], workspace_factory=CustomQCWorkspaceService,
                        session=session,
                    )
                    if tuple(source.get(key) for key in SOURCE_KEYS[:3]) != identity:
                        continue
                key = source_key(source)
                if key and (scene == "all" or source["scene"] == scene):
                    targets.append((row, key))
            except (RecordReviewConflict, AppealManualTargetConflict, AppealManualTargetNotFound):
                # 不完整或已换轮的引用是未知，不能串接历史状态。
                continue
        owner = QCAppeal if workflow == "clinical_appeal" else DefectRectification
        states = ("pending", "reviewing") if workflow == "clinical_appeal" else ("pending", "rejected")
        columns = [getattr(owner, key) for key in SOURCE_KEYS]
        matching = set()
        keys = sorted({key for _, key in targets})
        # 空集合仍核对所选 owner 可读，迁移未部署不得伪装空结果。
        for start in range(0, max(1, len(keys)), 100):
            statement = select(*columns).where(
                owner.status.in_(states), tuple_(*columns).in_(keys[start:start + 100]),
            )
            matching.update(tuple(row) for row in session.execute(statement).all())
        return [row for row, key in targets if key in matching]


def _load_jobs(session, rows):
    ids = sorted({row["root_job_id"] for row in rows
                  if row["source"] == "auto" and row.get("root_job_id")})
    if not ids:
        return {}
    table = _batch_job_table()
    jobs = {}
    for start in range(0, len(ids), 500):
        statement = select(table.c.id, table.c.scene, table.c.scope, table.c.filters_json).where(
            table.c.id.in_(ids[start:start + 500]),
        )
        jobs.update({row["id"]: row for row in session.execute(statement).mappings().all()})
    return jobs
