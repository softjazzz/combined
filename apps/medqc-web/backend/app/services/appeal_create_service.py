"""现代申诉创建：医生对本科室病例的已反馈问题发起申诉。

唯一职责：在同一事务内重验申诉目标、授权与科室，冻结来源后写入 ``qc.qc_appeals``。
目标事实由 ``appeal_workspace_target_service``（Canonical 缺陷）与
``appeal_manual_target_service``（任务人工缺陷）解析；审核仍由
``appeal_review_service`` 负责，本模块不判定缺陷状态、不计分、不审核。

授权口径（业务已确认）：
- 创建方仅 ``doctor`` 角色；账号机构与科室都必须来自服务端登录身份，任一缺失即失败关闭；
- 病例科室取工作台同一口径的权威科室（三坐标精确关联），机构和科室都必须与账号范围精确相等；
- 人工缺陷仅 ``manual_review_status == 'approved'`` 才算已反馈、可申诉。
任何失败都在写入前抛出，事务回滚，零写入。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Mapping
from uuid import uuid4

from sqlalchemy import and_, cast, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from ..database import connection as _connection
from ..database.models.qc import QCAppeal, QCDefect
from . import appeal_manual_target_service as manual_targets
from . import appeal_workspace_target_service as workspace_targets
from .case_identity import CaseRef
from .luxian_0609_rule_catalog import LUXIAN_0609_RULE_SET_KEY
from .qc_workspace.canonical_result_store import lock_case_result_mutations

TARGET_CANONICAL_DEFECT = workspace_targets.TARGET_CANONICAL_DEFECT
TARGET_TASK_MANUAL_DEFECT = "task_manual_defect"
TARGET_KINDS = frozenset({TARGET_CANONICAL_DEFECT, TARGET_TASK_MANUAL_DEFECT})
SCENES = frozenset({"running", "final", "outpatient_emergency"})
CANONICAL_NO_RESULT_STATES = frozenset({"not_found"})
OPEN_STATUSES = ("pending", "reviewing")
CREATOR_ROLE = "doctor"
EFFECTIVE_MANUAL_DEFECT_STATUSES = frozenset(
    {"pending", "urged", "rejected"}
)
_IDENTITY_KEYS = ("institute_id", "patient_id", "visit_id")
_MAX_REASON = 2000
_MIN_REASON = 10
_MAX_EVIDENCE_ITEMS = 20
_MAX_EVIDENCE_BYTES = 20_000


class ModernAppealInvalid(ValueError):
    """请求字段无效。"""


class ModernAppealForbidden(PermissionError):
    """当前账号无权对该病例发起申诉。"""


class ModernAppealNotFound(LookupError):
    """申诉目标不存在。"""


class ModernAppealConflict(ValueError):
    """目标与请求不一致、已变化、不可申诉或已存在未完结申诉。"""


class ModernAppealUnavailable(RuntimeError):
    """来源或数据库暂不可用。"""


@dataclass(frozen=True)
class ModernAppealRequest:
    target_kind: str
    institute_id: str
    patient_id: str
    visit_id: str
    scene: str
    reason: str
    expected_job_id: str | None = None
    expected_envelope_id: str | None = None
    rule_id: str | None = None
    defect_id: str | None = None
    evidence: list[dict[str, Any]] = field(default_factory=list)
    priority: str = "medium"


@dataclass(frozen=True)
class Appellant:
    user_id: str
    name: str
    institute_id: str
    department: str


def _text(value: Any, *, maximum: int = 128) -> str | None:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        return None
    return value if len(value) <= maximum else None


def _roles(user: Mapping[str, Any]) -> set[str]:
    raw = user.get("roles") or []
    if isinstance(raw, str):
        raw = [raw]
    return {str(role).strip().lower() for role in raw if str(role).strip()}


def resolve_appellant(user: Mapping[str, Any] | None) -> Appellant:
    """只接受有服务端机构/科室范围的医生账号；缺失时失败关闭。"""
    current = user or {}
    user_id = str(current.get("id") or current.get("user_id") or "").strip()
    if not user_id or len(user_id) > 36:
        raise ModernAppealForbidden("缺少申诉人身份")
    if CREATOR_ROLE not in _roles(current):
        raise ModernAppealForbidden("仅医生账号可以发起申诉")
    institute_id = _text(current.get("institute_id"))
    if institute_id is None:
        raise ModernAppealForbidden("账号未配置机构范围，无法发起申诉")
    department = str(current.get("department") or "").strip()
    if not department:
        raise ModernAppealForbidden("账号未配置科室，无法发起申诉")
    name = str(
        current.get("display_name") or current.get("name")
        or current.get("full_name") or current.get("email") or user_id
    ).strip()[:100]
    return Appellant(
        user_id=user_id, name=name or user_id,
        institute_id=institute_id, department=department,
    )


def _validated_request(request: ModernAppealRequest) -> tuple[tuple[str, str, str], str]:
    if request.target_kind not in TARGET_KINDS:
        raise ModernAppealInvalid("申诉目标类型无效")
    identity = tuple(_text(getattr(request, key)) for key in _IDENTITY_KEYS)
    if any(part is None for part in identity):
        raise ModernAppealInvalid("病历三坐标无效")
    if request.scene not in SCENES:
        raise ModernAppealInvalid("质控场景无效")
    reason = request.reason.strip() if isinstance(request.reason, str) else ""
    if not _MIN_REASON <= len(reason) <= _MAX_REASON:
        raise ModernAppealInvalid(f"申诉理由需为 {_MIN_REASON}–{_MAX_REASON} 个字符")
    if request.priority not in {"low", "medium", "high", "urgent"}:
        raise ModernAppealInvalid("优先级无效")
    if (
        not isinstance(request.evidence, list)
        or len(request.evidence) > _MAX_EVIDENCE_ITEMS
        or any(not isinstance(item, dict) for item in request.evidence)
        or len(json.dumps(request.evidence, ensure_ascii=False)) > _MAX_EVIDENCE_BYTES
    ):
        raise ModernAppealInvalid("证据材料格式无效")
    if request.target_kind == TARGET_CANONICAL_DEFECT:
        if request.defect_id is not None:
            raise ModernAppealInvalid("自动缺陷申诉不得指定人工缺陷 ID")
        if (
            _text(request.expected_job_id, maximum=36) is None
            or _text(request.expected_envelope_id, maximum=36) is None
        ):
            raise ModernAppealInvalid("结果引用无效")
        if _text(request.rule_id, maximum=100) is None:
            raise ModernAppealInvalid("缺陷规则 ID 无效")
    else:
        if request.rule_id is not None:
            raise ModernAppealInvalid("人工缺陷申诉不得指定规则 ID")
        if _text(request.defect_id, maximum=36) is None:
            raise ModernAppealInvalid("人工缺陷 ID 无效")
    return identity, reason  # type: ignore[return-value]


def _appeal_options(session: Session) -> dict[str, Any]:
    """PostgreSQL 下申诉表固定解析到权威 ``qc`` schema，避免命中 public 同名旧表。"""
    if session.get_bind().dialect.name == "postgresql":
        return {"schema_translate_map": {None: "qc"}}
    return {}


def _is_postgres(session: Session) -> bool:
    return session.get_bind().dialect.name == "postgresql"


def _default_workspace_factory() -> Any:
    from .custom_qc_workspace_service import CustomQCWorkspaceService

    return CustomQCWorkspaceService()


def _default_department_loader() -> Callable[..., dict[tuple[str, str, str], str]]:
    from .medical_records.query_service import load_scoring_departments

    return load_scoring_departments


def _case_department(
    session: Session, identity: tuple[str, str, str],
    department_loader: Callable[..., dict[tuple[str, str, str], str]],
) -> str:
    try:
        departments = department_loader([identity], session=session)
    except Exception as exc:  # noqa: BLE001 - 科室来源不可用时失败关闭
        raise ModernAppealUnavailable("病例科室暂不可用") from exc
    department = str((departments or {}).get(identity) or "").strip()
    if not department:
        raise ModernAppealForbidden("病例科室无法确定，不能发起申诉")
    return department


def _require_own_department(case_department: str, appellant: Appellant) -> None:
    if case_department != appellant.department:
        raise ModernAppealForbidden("只能对本科室病例发起申诉")


def _require_own_institute(identity: tuple[str, str, str], appellant: Appellant) -> None:
    """机构范围只信服务端账号，不信请求声称的机构。"""
    if identity[0] != appellant.institute_id:
        raise ModernAppealForbidden("只能对本机构病例发起申诉")


def _resolve_canonical(
    session: Session, request: ModernAppealRequest, identity: tuple[str, str, str],
    workspace_factory: Callable[[], Any],
) -> dict[str, Any]:
    try:
        return workspace_targets.resolve_workspace_appeal_target(
            target_kind=TARGET_CANONICAL_DEFECT,
            institute_id=identity[0], patient_id=identity[1], visit_id=identity[2],
            expected_job_id=str(request.expected_job_id),
            expected_envelope_id=str(request.expected_envelope_id),
            rule_id=request.rule_id, workspace_factory=workspace_factory, session=session,
        )
    except workspace_targets.AppealWorkspaceTargetInvalid as exc:
        raise ModernAppealInvalid(str(exc)) from exc
    except workspace_targets.AppealWorkspaceTargetNotFound as exc:
        raise ModernAppealNotFound(str(exc)) from exc
    except workspace_targets.AppealWorkspaceTargetConflict as exc:
        raise ModernAppealConflict(str(exc)) from exc
    except workspace_targets.AppealWorkspaceTargetUnavailable as exc:
        raise ModernAppealUnavailable(str(exc)) from exc


def _require_doctor_visible_target(
    target: Mapping[str, Any], appellant: Appellant,
) -> None:
    from .doctor_rule_visibility_service import (
        DoctorRuleVisibilityUnavailable,
        visible_rule_ids,
    )

    try:
        allowed = visible_rule_ids(
            rule_set_key=str(target.get("rule_set_key") or ""),
            rule_set_version=str(target.get("rule_set_version") or ""),
            institute_id=appellant.institute_id,
            department_name=appellant.department,
        )
    except DoctorRuleVisibilityUnavailable as exc:
        raise ModernAppealUnavailable("医生端规则配置暂不可用") from exc
    if (
        target.get("_can_show_to_doctor") is not True
        or str(target.get("target_id") or "").strip().upper() not in allowed
    ):
        raise ModernAppealForbidden("该质控问题未对本科室医生开放")


def _resolve_manual(
    session: Session, request: ModernAppealRequest, workspace_factory: Callable[[], Any],
) -> tuple[dict[str, Any], str | None]:
    defect_id = str(request.defect_id)
    try:
        target = manual_targets.resolve_task_manual_defect_target(
            defect_id=defect_id, workspace_factory=workspace_factory,
            session=session, lock=True,
        )
    except manual_targets.AppealManualTargetNotFound as exc:
        raise ModernAppealNotFound(str(exc)) from exc
    except manual_targets.AppealManualTargetConflict as exc:
        raise ModernAppealConflict(str(exc)) from exc
    except manual_targets.AppealManualTargetUnavailable as exc:
        raise ModernAppealUnavailable(str(exc)) from exc
    # 解析器已在本事务内对缺陷行加共享锁；此处只读取审核状态，不改缺陷。
    row = session.execute(
        select(QCDefect.manual_review_status, QCDefect.rule_code, QCDefect.status)
        .where(QCDefect.id == defect_id)
        .with_for_update(read=True)
    ).first()
    if row is None:
        raise ModernAppealNotFound("人工缺陷不存在")
    if row.manual_review_status != "approved":
        raise ModernAppealConflict("人工缺陷尚未审核通过，不能申诉")
    if row.status not in EFFECTIVE_MANUAL_DEFECT_STATUSES:
        raise ModernAppealConflict("人工缺陷已失效，不能申诉")
    return target, (str(row.rule_code).strip() or None) if row.rule_code else None


def _require_same_source(
    target: Mapping[str, Any], request: ModernAppealRequest, identity: tuple[str, str, str],
) -> None:
    if tuple(target.get(key) for key in _IDENTITY_KEYS) != identity:
        raise ModernAppealConflict("申诉目标与病历三坐标不一致")
    if target.get("scene") != request.scene:
        raise ModernAppealConflict("申诉目标的质控场景与请求不一致")
    for key in ("target_id", "root_job_id", "envelope_id", "rule_set_key", "rule_set_version"):
        if _text(target.get(key), maximum=100) is None:
            raise ModernAppealConflict("申诉目标来源不完整")
    if request.target_kind == TARGET_TASK_MANUAL_DEFECT and (
        (request.expected_job_id is not None and request.expected_job_id != target["root_job_id"])
        or (
            request.expected_envelope_id is not None
            and request.expected_envelope_id != target["envelope_id"]
        )
    ):
        raise ModernAppealConflict("人工缺陷来源结果与请求不一致")


def _open_duplicate_exists(
    session: Session, appellant: Appellant, target: Mapping[str, Any],
) -> bool:
    table = QCAppeal.__table__
    statement = select(table.c.id).where(and_(
        table.c.appellant_id == appellant.user_id,
        table.c.target_kind == target["target_kind"],
        table.c.target_id == target["target_id"],
        table.c.institute_id == target["institute_id"],
        table.c.patient_id == target["patient_id"],
        table.c.visit_id == target["visit_id"],
        table.c.scene == target["scene"],
        table.c.root_job_id == target["root_job_id"],
        table.c.envelope_id == target["envelope_id"],
        table.c.status.in_(OPEN_STATUSES),
    )).limit(1)
    return session.execute(
        statement, execution_options=_appeal_options(session),
    ).first() is not None


def _row_to_dict(row: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(row)
    evidence = result.get("evidence")
    if isinstance(evidence, str):
        try:
            result["evidence"] = json.loads(evidence)
        except ValueError:
            result["evidence"] = []
    return result


def _is_open_target_unique_conflict(exc: IntegrityError) -> bool:
    original = getattr(exc, "orig", None)
    constraint = getattr(getattr(original, "diag", None), "constraint_name", None)
    if constraint == "uq_qc_appeals_open_target":
        return True
    message = str(original or "").lower()
    return "unique constraint failed" in message and all(
        f"qc_appeals.{name}" in message
        for name in (
            "appellant_id", "target_kind", "target_id", "institute_id", "patient_id",
            "visit_id", "scene", "root_job_id", "envelope_id",
        )
    )


def create_modern_appeal(
    request: ModernAppealRequest,
    *,
    current_user: Mapping[str, Any] | None,
    workspace_factory: Callable[[], Any] | None = None,
    department_loader: Callable[..., dict[tuple[str, str, str], str]] | None = None,
    session_factory: Callable[[], Session] | None = None,
) -> dict[str, Any]:
    """在单一事务内重验、授权、冻结并写入现代申诉；任何失败零写入。

    Canonical 自动缺陷与 Envelope 写 owner 共用病例事务锁，并在写申诉前二次重验
    latest；取源后若结果切换则冲突并回滚。
    """
    appellant = resolve_appellant(current_user)
    identity, reason = _validated_request(request)
    factory = session_factory or _connection.SessionLocal
    if factory is None:
        raise ModernAppealUnavailable("数据库会话不可用")
    workspace = workspace_factory or _default_workspace_factory
    loader = department_loader or _default_department_loader()

    session = factory()
    try:
        with session.begin():
            # 先按服务端账号做机构/科室授权，避免向范围外账号暴露目标是否存在。
            _require_own_institute(identity, appellant)
            case_department = _case_department(session, identity, loader)
            _require_own_department(case_department, appellant)

            if request.target_kind == TARGET_CANONICAL_DEFECT:
                lock_case_result_mutations(
                    session, [CaseRef(*identity)], rule_set_key=LUXIAN_0609_RULE_SET_KEY,
                )
                target = _resolve_canonical(session, request, identity, workspace)
                _require_doctor_visible_target(target, appellant)
                defect_item = str(target["target_id"])
            else:
                target, rule_code = _resolve_manual(session, request, workspace)
                defect_item = rule_code or str(target["target_id"])
            _require_same_source(target, request, identity)

            if _open_duplicate_exists(session, appellant, target):
                raise ModernAppealConflict("该问题已有未完结的申诉")

            if request.target_kind == TARGET_CANONICAL_DEFECT:
                refreshed = _resolve_canonical(session, request, identity, workspace)
                _require_doctor_visible_target(refreshed, appellant)
                if refreshed != target:
                    raise ModernAppealConflict("质控结果已更新，请刷新后重试")

            appeal_id = str(uuid4())
            now = datetime.now(timezone.utc)
            evidence_json = json.dumps(request.evidence, ensure_ascii=False)
            values = {
                "id": appeal_id,
                "qc_result_id": None,
                "record_id": None,
                "appeal_type": "defect",
                "defect_item": defect_item[:200],
                "reason": reason,
                "evidence": (
                    cast(evidence_json, JSONB) if _is_postgres(session) else evidence_json
                ),
                "priority": request.priority,
                "appellant_id": appellant.user_id,
                "appellant_name": appellant.name,
                "appellant_department": appellant.department,
                "status": "pending",
                "created_at": now.replace(tzinfo=None),
                "updated_at": now,
                "target_kind": target["target_kind"],
                "target_id": target["target_id"],
                "institute_id": target["institute_id"],
                "patient_id": target["patient_id"],
                "visit_id": target["visit_id"],
                "scene": target["scene"],
                "root_job_id": target["root_job_id"],
                "envelope_id": target["envelope_id"],
                "rule_set_key": target["rule_set_key"],
                "rule_set_version": target["rule_set_version"],
                "case_department": case_department,
            }
            options = _appeal_options(session)
            table = QCAppeal.__table__
            session.execute(table.insert().values(**values), execution_options=options)
            row = session.execute(
                select(table).where(table.c.id == appeal_id), execution_options=options,
            ).mappings().one()
            result = _row_to_dict(row)
        return result
    except IntegrityError as exc:
        session.rollback()
        if _is_open_target_unique_conflict(exc):
            raise ModernAppealConflict("该问题已有未完结的申诉") from exc
        raise ModernAppealUnavailable("申诉创建暂不可用") from exc
    except (
        ModernAppealInvalid, ModernAppealForbidden, ModernAppealNotFound,
        ModernAppealConflict, ModernAppealUnavailable,
    ):
        session.rollback()
        raise
    except SQLAlchemyError as exc:
        session.rollback()
        raise ModernAppealUnavailable("申诉创建暂不可用") from exc
    finally:
        session.close()


def list_modern_appeal_candidates(
    *,
    institute_id: str, patient_id: str, visit_id: str,
    current_user: Mapping[str, Any] | None,
    workspace_factory: Callable[[], Any] | None = None,
    department_loader: Callable[..., dict[tuple[str, str, str], str]] | None = None,
    session_factory: Callable[[], Session] | None = None,
) -> dict[str, Any]:
    """医生端申诉入口的只读候选：本科室病例当前结果中的已确认缺陷与已审核通过的人工缺陷。

    候选只用于展示和回填请求；真正创建时仍会在事务内全部重验。
    """
    appellant = resolve_appellant(current_user)
    identity = tuple(_text(value) for value in (institute_id, patient_id, visit_id))
    if any(part is None for part in identity):
        raise ModernAppealInvalid("病历三坐标无效")
    factory = session_factory or _connection.SessionLocal
    if factory is None:
        raise ModernAppealUnavailable("数据库会话不可用")
    workspace = workspace_factory or _default_workspace_factory
    loader = department_loader or _default_department_loader()

    try:
        with factory() as session:
            _require_own_institute(identity, appellant)  # type: ignore[arg-type]
            case_department = _case_department(session, identity, loader)  # type: ignore[arg-type]
            _require_own_department(case_department, appellant)
            canonical = _canonical_candidates(
                session, identity, workspace, appellant,
            )  # type: ignore[arg-type]
            manual = _manual_candidates(session, identity)  # type: ignore[arg-type]
    except (ModernAppealForbidden, ModernAppealInvalid, ModernAppealUnavailable):
        raise
    except SQLAlchemyError as exc:
        raise ModernAppealUnavailable("申诉候选暂不可用") from exc
    return {
        "institute_id": identity[0], "patient_id": identity[1], "visit_id": identity[2],
        "case_department": case_department,
        "canonical": canonical,
        "manual_defects": manual,
    }


def _canonical_candidates(
    session: Session, identity: tuple[str, str, str], workspace_factory: Callable[[], Any],
    appellant: Appellant,
) -> dict[str, Any]:
    """读取当前最新 Canonical 结果；不可用时返回 unavailable，不伪造空缺陷。"""
    from .record_review_service import resolve_workspace_result_reference

    try:
        dto = workspace_factory().build_latest_single_record_result_dto(
            institute_id=identity[0], patient_id=identity[1], visit_id=identity[2],
        )
    except Exception:  # noqa: BLE001 - 对外固定脱敏
        return {"state": "unavailable", "items": []}
    if not isinstance(dto, dict):
        return {"state": "unavailable", "items": []}
    state = dto.get("state")
    if state in CANONICAL_NO_RESULT_STATES:
        return {"state": "no_result", "items": []}
    if state != "ready":
        return {"state": "unavailable", "items": []}
    try:
        source = resolve_workspace_result_reference(
            institute_id=identity[0], patient_id=identity[1], visit_id=identity[2],
            expected_job_id=str(dto.get("job_id") or ""),
            expected_envelope_id=str(dto.get("envelope_id") or ""),
            workspace_factory=workspace_factory, session=session,
        )
        from .doctor_rule_visibility_service import project_doctor_visible_items

        items = project_doctor_visible_items(
            workspace_targets._project_items(source.get("items")),
            rule_set_key=str(source.get("rule_set_key") or ""),
            rule_set_version=str(source.get("rule_set_version") or ""),
            institute_id=appellant.institute_id,
            department_name=appellant.department,
        )
    except Exception:  # noqa: BLE001 - 对外固定脱敏
        return {"state": "unavailable", "items": []}
    counts: dict[str, int] = {}
    for item in items:
        rule_id = str(item.get("rule_id") or "").strip().upper()
        counts[rule_id] = counts.get(rule_id, 0) + 1
    confirmed = [
        {
            "rule_id": str(item.get("rule_id") or "").strip().upper(),
            "rule_name": item.get("rule_name"),
            "conclusion": item.get("conclusion"),
        }
        for item in items
        if item.get("is_confirmed_issue") is True
        and counts.get(str(item.get("rule_id") or "").strip().upper()) == 1
    ]
    return {
        "state": "ready",
        "scene": source["scene"],
        "job_id": source["root_job_id"],
        "envelope_id": source["envelope_id"],
        "items": confirmed,
    }


def _manual_candidates(
    session: Session, identity: tuple[str, str, str],
) -> list[dict[str, Any]]:
    rows = session.execute(
        select(
            QCDefect.id, QCDefect.rule_code, QCDefect.rule_name, QCDefect.description,
            QCDefect.scene, QCDefect.created_at,
        ).where(
            QCDefect.institute_id == identity[0],
            QCDefect.patient_id == identity[1],
            QCDefect.visit_id == identity[2],
            QCDefect.origin == "manual",
            QCDefect.source_key == "task_assigned_qc",
            QCDefect.identity_version == 1,
            QCDefect.manual_review_status == "approved",
            QCDefect.status.in_(sorted(EFFECTIVE_MANUAL_DEFECT_STATUSES)),
            QCDefect.scene.in_(sorted(SCENES)),
        ).order_by(QCDefect.created_at.desc(), QCDefect.id.desc()).limit(200)
    ).all()
    return [
        {
            "defect_id": row.id, "rule_code": row.rule_code, "rule_name": row.rule_name,
            "description": row.description, "scene": row.scene,
        }
        for row in rows
    ]


__all__ = [
    "ModernAppealConflict",
    "ModernAppealForbidden",
    "ModernAppealInvalid",
    "ModernAppealNotFound",
    "ModernAppealRequest",
    "ModernAppealUnavailable",
    "SCENES",
    "TARGET_KINDS",
    "create_modern_appeal",
    "list_modern_appeal_candidates",
    "resolve_appellant",
]
