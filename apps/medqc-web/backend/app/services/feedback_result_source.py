"""反馈只消费目标线当前Canonical读取器；不改选轮，不从旧payload补造来源。"""

from sqlalchemy import select

from ..database.models.v36_reports import QCDefect, SysUser
from .defect_rectification_service import (
    RectificationError,
    _manager,
    _persistent_roles,
    _scope,
)
from .user_scope_owner import user_owner_options


class _BorrowedReadSession:
    # 原只读owner在finally关闭会话；借用派发事务时不能关闭外层写会话。
    def __init__(self, session):
        self.session = session

    def execute(self, *args, **kwargs):
        return self.session.execute(*args, **kwargs)

    def close(self):
        pass


def verify_historical_envelope(session, identity, root_job_id, envelope_id):
    """校验历史保存结果 envelope 存在且归属三坐标与 root_job_id，不要求其仍为最新轮次。"""
    from .custom_qc_workspace_service import _record_result_envelopes_table

    mapping = dict(zip(("institute_id", "patient_id", "visit_id"), identity))
    envelopes = _record_result_envelopes_table()
    locked = session.execute(
        select(envelopes.c.id)
        .where(
            envelopes.c.id == envelope_id,
            envelopes.c.root_job_id == root_job_id,
            *(getattr(envelopes.c, key) == value for key, value in mapping.items()),
        )
        .with_for_update(read=True)
    ).scalar_one_or_none()
    if locked is None:
        raise RectificationError("原保存结果对象不存在或归属不一致", 409)
    return locked


def current_result(session, identity, expected_job_id, expected_envelope_id=None):
    from .case_identity import CaseRef
    from .custom_qc_workspace_service import (
        CustomQCWorkspaceService,
        _batch_jobs_table,
        _record_result_envelopes_table,
    )
    from .qc_workspace.canonical_result_store import (
        customer_safe_projection_key,
        keyed_ref,
    )
    from .record_review_service import _workspace_scene_from_job
    from .scoring_service import project_customer_items

    mapping = dict(zip(("institute_id", "patient_id", "visit_id"), identity))
    if expected_envelope_id is not None:
        # 派发事务保护被引用的保存对象免遭并发替换；不阻止新轮产生，也不改选轮规则。
        envelopes = _record_result_envelopes_table()
        locked = session.execute(
            select(envelopes.c.id)
            .where(
                envelopes.c.id == expected_envelope_id,
                envelopes.c.root_job_id == expected_job_id,
                *(getattr(envelopes.c, key) == value for key, value in mapping.items()),
            )
            .with_for_update(read=True)
        ).scalar_one_or_none()
        if locked is None:
            raise RectificationError("保存结果对象已变化或不存在", 409)
    result = (
        CustomQCWorkspaceService(readonly=True)
        .build_luxian_0609_completed_record_result_summaries(
            record_refs=[mapping],
            include_items=True,
            include_rule_set_context=True,
            session_factory=lambda: _BorrowedReadSession(session),
        )
        .get(identity, {})
    )
    if (
        result.get("status") != "ready"
        or result.get("root_job_id") != expected_job_id
        or (
            expected_envelope_id is not None
            and result.get("envelope_id") != expected_envelope_id
        )
    ):
        raise RectificationError("当前保存结果已变化或不可用，请刷新", 409)
    expected_ref = keyed_ref(
        "rec", CaseRef(*identity).as_key(), hmac_key=customer_safe_projection_key()
    )
    if result.get("record_ref") != expected_ref:
        raise RectificationError("保存结果病例引用不一致", 409)
    jobs = _batch_jobs_table(readonly=True)
    job = (
        session.execute(
            select(jobs.c.id, jobs.c.scene, jobs.c.scope, jobs.c.filters_json).where(
                jobs.c.id == expected_job_id,
            )
        )
        .mappings()
        .one()
    )
    scene = _workspace_scene_from_job(job, identity=identity)
    if scene not in {"running", "final"}:
        raise RectificationError("当前仅接通运行和终末反馈", 409)
    return {
        **mapping,
        "scene": scene,
        "root_job_id": result["root_job_id"],
        "envelope_id": result["envelope_id"],
        "rule_set_key": result["rule_set_key"],
        "rule_set_version": result["rule_set_version"],
        "items": project_customer_items(result["items"]),
    }


def manual_target(session, defect, current):
    from .defect_workflow_filter_service import SOURCE_KEYS
    from .manual_quality_report_service import ManualQualityReportService, _source

    data = ManualQualityReportService()._batch(session, [defect])
    task, _, source = _source(
        defect,
        data["histories"].get(defect.id, []),
        data["records"],
        data["runs"],
        data["jobs"],
        data["envelopes"],
    )
    if not source or task["task_id"] not in data["tasks"]:
        raise RectificationError("人工缺陷缺少可信冻结来源", 409)
    target = dict(zip(SOURCE_KEYS, source))
    if any(
        target[key] != current[key]
        for key in (
            "institute_id",
            "patient_id",
            "visit_id",
            "scene",
            "root_job_id",
            "envelope_id",
        )
    ):
        raise RectificationError("人工缺陷不属于当前保存结果", 409)
    return {
        **target,
        "rule_set_key": current["rule_set_key"],
        "rule_set_version": current["rule_set_version"],
        "_dispatchable": True,
    }


def resolve_target(session, request):
    identity = tuple(request[key] for key in ("institute_id", "patient_id", "visit_id"))
    current = current_result(
        session, identity, request["root_job_id"], request["envelope_id"]
    )
    if request["scene"] != current["scene"]:
        raise RectificationError("保存结果场景不一致", 409)
    if request["target_kind"] == "canonical_defect":
        matches = [
            item
            for item in current["items"]
            if item.get("rule_id") == request["target_id"]
        ]
        if len(matches) != 1 or matches[0].get("is_confirmed_issue") is not True:
            raise RectificationError("目标不是当前唯一已确认缺陷", 409)
        return {key: value for key, value in current.items() if key != "items"} | {
            "target_kind": "canonical_defect",
            "target_id": request["target_id"],
            "_dispatchable": True,
        }
    if request["target_kind"] != "task_manual_defect":
        raise RectificationError("不支持的缺陷目标")
    defect = session.execute(
        select(QCDefect).where(QCDefect.id == request["target_id"]).with_for_update()
    ).scalar_one_or_none()
    if (
        defect is None
        or defect.source_key != "task_assigned_qc"
        or defect.origin != "manual"
        or (
            defect.manual_review_status != "approved"
            or defect.status not in {"pending", "urged", "rejected"}
        )
    ):
        raise RectificationError("仅已审核且有效的人工缺陷可派发", 409)
    return manual_target(session, defect, current)


def candidates(
    service, actor_id, *, institute_id, patient_id, visit_id, expected_job_id
):
    identity = (institute_id, patient_id, visit_id)
    with service.sessions() as session:
        actor = service.person(session, actor_id)
        if not _manager(actor):
            raise RectificationError("仅质控人员可以派发", 403)
        _scope(actor, institute_id, None)
        department = service.department(session, identity)
        _scope(actor, institute_id, department)
        current = current_result(session, identity, expected_job_id)
        items = current["items"]
        targets = [
            {
                "target_kind": "canonical_defect",
                "target_id": item["rule_id"],
                "label": item.get("rule_name") or item["rule_id"],
                **{
                    key: current[key] for key in ("scene", "root_job_id", "envelope_id")
                },
            }
            for item in items
            if item.get("is_confirmed_issue") is True
        ]
        manual = session.scalars(
            select(QCDefect)
            .where(
                QCDefect.institute_id == institute_id,
                QCDefect.patient_id == patient_id,
                QCDefect.visit_id == visit_id,
                QCDefect.scene == current["scene"],
                QCDefect.source_key == "task_assigned_qc",
                QCDefect.origin == "manual",
                QCDefect.manual_review_status == "approved",
                QCDefect.status.in_(["pending", "urged", "rejected"]),
            )
            .order_by(QCDefect.id)
            .limit(201)
        ).all()
        if len(manual) > 200:
            raise RectificationError("人工缺陷超过单病例候选上限", 422)
        for defect in manual:
            try:
                target = manual_target(session, defect, current)
            except RectificationError:
                continue
            targets.append(
                {
                    key: target[key]
                    for key in (
                        "target_kind",
                        "target_id",
                        "scene",
                        "root_job_id",
                        "envelope_id",
                    )
                }
                | {"label": defect.rule_name or defect.rule_code or "人工缺陷"}
            )
        people = session.scalars(
            select(SysUser).where(
                SysUser.institute_id == institute_id,
                SysUser.department == department,
                SysUser.is_active.is_(True),
            ),
            execution_options=user_owner_options(session),
        ).all()
        return {
            "targets": targets,
            "department": department,
            "doctors": [
                {"id": person.id, "name": person.display_name}
                for person in people
                if "doctor" in _persistent_roles(person.role, person.roles_json)
            ],
        }
