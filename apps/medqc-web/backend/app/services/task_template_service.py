"""当前用户私有的任务创建参数模板。

模板只保存可复用配置，不保存任务、病例或人员身份；所有读写都带 owner_id，
更新和删除使用 version CAS。写入与回读在同一事务中完成，无法确认回读结果时回滚。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import delete, func, insert, select, text, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from ..database.connection import SessionLocal
from ..database.models.qc import QCTaskTemplate
from ..schemas.tasks import TaskTemplateConfig
from .qc_rule_sets import get_sichuan_rule_set
from .task_sampling_service import (
    validate_active_running_date_range,
    validate_scoped_sampling_config,
)

MAX_TEMPLATES_PER_USER = 20
MAX_OWNER_ID_LENGTH = 64
MAX_TEMPLATE_ID_LENGTH = 36

_TABLE = QCTaskTemplate.__table__
_COLUMNS = (
    _TABLE.c.id,
    _TABLE.c.name,
    _TABLE.c.config_json,
    _TABLE.c.version,
    _TABLE.c.created_at,
    _TABLE.c.updated_at,
)


class TaskTemplateNotFound(LookupError):
    """模板不存在或不属于当前用户。"""


class TaskTemplateInvalid(ValueError):
    """模板输入不符合创建合同。"""

    code = "invalid_template"


class TaskTemplateConflict(ValueError):
    """同名、上限或 CAS 冲突。"""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


class TaskTemplateUnavailable(RuntimeError):
    """模板存储暂不可用；对外不得暴露底层错误。"""


def _require_session_factory() -> Any:
    if SessionLocal is None:
        raise TaskTemplateUnavailable("任务模板存储不可用")
    return SessionLocal


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _owner(owner_id: Any) -> str:
    if not isinstance(owner_id, str):
        raise TaskTemplateInvalid("当前用户缺少有效身份")
    normalized = owner_id.strip()
    if not normalized or len(normalized) > MAX_OWNER_ID_LENGTH:
        raise TaskTemplateInvalid("当前用户缺少有效身份")
    return normalized


def _name(name: Any) -> str:
    if not isinstance(name, str):
        raise TaskTemplateInvalid("模板名称无效")
    normalized = name.strip()
    if not normalized or len(normalized) > 50:
        raise TaskTemplateInvalid("模板名称须为 1 到 50 个字符")
    return normalized


def _template_id(template_id: Any) -> str:
    if not isinstance(template_id, str):
        raise TaskTemplateNotFound("任务模板不存在")
    normalized = template_id.strip()
    if not normalized or len(normalized) > MAX_TEMPLATE_ID_LENGTH:
        raise TaskTemplateNotFound("任务模板不存在")
    return normalized


def _version(version: Any) -> int:
    if type(version) is not int or version < 1:
        raise TaskTemplateInvalid("version 无效")
    return version


def validate_task_template_config(config: Any) -> dict[str, Any]:
    """严格规范化允许保存的八个字段；额外字段由 Pydantic 失败关闭。"""
    try:
        parsed = config if isinstance(config, TaskTemplateConfig) else TaskTemplateConfig.model_validate(config)
    except ValidationError as exc:
        first = exc.errors(include_url=False)[0] if exc.errors() else {}
        message = str(first.get("msg") or "模板配置无效").removeprefix("Value error, ")
        raise TaskTemplateInvalid(message) from exc

    normalized = parsed.model_dump(mode="json")
    rule_set = get_sichuan_rule_set(normalized["rule_set_key"])
    if rule_set is None:
        raise TaskTemplateInvalid("规则集不存在或不可用")
    if rule_set.scope != normalized["scene"]:
        raise TaskTemplateInvalid("规则集与任务场景不匹配")
    try:
        validate_scoped_sampling_config(
            normalized["scene"], normalized["sampling_method"], normalized["sampling_config"],
        )
        if normalized["scene"] == "running":
            validate_active_running_date_range(normalized.get("date_range"))
    except ValueError as exc:
        raise TaskTemplateInvalid(str(exc)) from exc
    return normalized


def _dump_config(config: Any) -> str:
    return json.dumps(
        validate_task_template_config(config),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _load_config(raw: Any) -> tuple[dict[str, Any] | None, str | None]:
    """存量损坏或已不可用模板仍可列出，但不得伪装为空配置或继续套用。"""
    try:
        decoded = json.loads(raw)
        return validate_task_template_config(decoded), None
    except (TypeError, ValueError, json.JSONDecodeError):
        return None, "模板配置已损坏或当前不可用，请编辑后再套用"


def _item(row: Any) -> dict[str, Any]:
    config, unavailable_reason = _load_config(row.config_json)
    return {
        "id": row.id,
        "name": row.name,
        "config": config,
        "usable": config is not None,
        "unavailable_reason": unavailable_reason,
        "version": int(row.version),
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _lock_owner(session: Any, owner_id: str) -> None:
    if session.get_bind().dialect.name == "postgresql":
        session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
            {"key": f"qc_task_templates:{owner_id}"},
        )


def _read_one(session: Any, owner_id: str, template_id: str) -> Any:
    return session.execute(
        select(*_COLUMNS).where(
            _TABLE.c.id == template_id,
            _TABLE.c.owner_id == owner_id,
        )
    ).first()


def _name_taken(
    session: Any,
    owner_id: str,
    name: str,
    *,
    exclude_id: str | None = None,
) -> bool:
    predicates = [_TABLE.c.owner_id == owner_id, _TABLE.c.name == name]
    if exclude_id is not None:
        predicates.append(_TABLE.c.id != exclude_id)
    return session.execute(select(_TABLE.c.id).where(*predicates).limit(1)).first() is not None


def list_task_templates(*, owner_id: str) -> dict[str, Any]:
    owner_id = _owner(owner_id)
    factory = _require_session_factory()
    try:
        with factory() as session:
            rows = session.execute(
                select(*_COLUMNS)
                .where(_TABLE.c.owner_id == owner_id)
                .order_by(_TABLE.c.updated_at.desc(), _TABLE.c.name.asc(), _TABLE.c.id.asc())
            ).all()
    except SQLAlchemyError as exc:
        raise TaskTemplateUnavailable("任务模板读取失败") from exc
    return {"items": [_item(row) for row in rows], "max_templates": MAX_TEMPLATES_PER_USER}


def create_task_template(*, owner_id: str, name: str, config: Any) -> dict[str, Any]:
    owner_id = _owner(owner_id)
    name = _name(name)
    config_json = _dump_config(config)
    template_id = str(uuid4())
    factory = _require_session_factory()
    try:
        with factory() as session:
            with session.begin():
                _lock_owner(session, owner_id)
                count = session.execute(
                    select(func.count(_TABLE.c.id)).where(_TABLE.c.owner_id == owner_id)
                ).scalar_one()
                if int(count) >= MAX_TEMPLATES_PER_USER:
                    raise TaskTemplateConflict(
                        f"每个用户最多保存 {MAX_TEMPLATES_PER_USER} 个任务模板",
                        code="template_limit",
                    )
                if _name_taken(session, owner_id, name):
                    raise TaskTemplateConflict("已存在同名任务模板", code="name_conflict")
                now = _now()
                session.execute(insert(_TABLE).values(
                    id=template_id,
                    owner_id=owner_id,
                    name=name,
                    config_json=config_json,
                    version=1,
                    created_at=now,
                    updated_at=now,
                ))
                row = _read_one(session, owner_id, template_id)
                if row is None:
                    raise TaskTemplateUnavailable("任务模板保存结果无法确认")
                result = _item(row)
    except IntegrityError as exc:
        raise TaskTemplateConflict("已存在同名任务模板", code="name_conflict") from exc
    except SQLAlchemyError as exc:
        raise TaskTemplateUnavailable("任务模板保存失败") from exc
    return result


def update_task_template(
    *,
    owner_id: str,
    template_id: str,
    version: int,
    name: Any = None,
    config: Any = None,
) -> dict[str, Any]:
    owner_id = _owner(owner_id)
    template_id = _template_id(template_id)
    version = _version(version)
    changes: dict[str, Any] = {}
    if name is not None:
        changes["name"] = _name(name)
    if config is not None:
        changes["config_json"] = _dump_config(config)
    if not changes:
        raise TaskTemplateInvalid("没有需要更新的字段")
    factory = _require_session_factory()
    try:
        with factory() as session:
            with session.begin():
                _lock_owner(session, owner_id)
                current = session.execute(
                    select(_TABLE.c.id, _TABLE.c.version)
                    .where(_TABLE.c.id == template_id, _TABLE.c.owner_id == owner_id)
                    .with_for_update()
                ).first()
                if current is None:
                    raise TaskTemplateNotFound("任务模板不存在")
                if int(current.version) != version:
                    raise TaskTemplateConflict("任务模板已被修改，请刷新后重试", code="version_conflict")
                if "name" in changes and _name_taken(
                    session, owner_id, changes["name"], exclude_id=template_id,
                ):
                    raise TaskTemplateConflict("已存在同名任务模板", code="name_conflict")
                updated = session.execute(
                    update(_TABLE)
                    .where(
                        _TABLE.c.id == template_id,
                        _TABLE.c.owner_id == owner_id,
                        _TABLE.c.version == version,
                    )
                    .values(**changes, version=version + 1, updated_at=_now())
                )
                if updated.rowcount != 1:
                    raise TaskTemplateConflict(
                        "任务模板已被修改，请刷新后重试", code="version_conflict",
                    )
                row = _read_one(session, owner_id, template_id)
                if row is None:
                    raise TaskTemplateUnavailable("任务模板保存结果无法确认")
                result = _item(row)
    except IntegrityError as exc:
        raise TaskTemplateConflict("已存在同名任务模板", code="name_conflict") from exc
    except SQLAlchemyError as exc:
        raise TaskTemplateUnavailable("任务模板保存失败") from exc
    return result


def delete_task_template(*, owner_id: str, template_id: str, version: int) -> dict[str, Any]:
    owner_id = _owner(owner_id)
    template_id = _template_id(template_id)
    version = _version(version)
    factory = _require_session_factory()
    try:
        with factory() as session:
            with session.begin():
                current = session.execute(
                    select(_TABLE.c.id, _TABLE.c.version)
                    .where(_TABLE.c.id == template_id, _TABLE.c.owner_id == owner_id)
                    .with_for_update()
                ).first()
                if current is None:
                    raise TaskTemplateNotFound("任务模板不存在")
                if int(current.version) != version:
                    raise TaskTemplateConflict("任务模板已被修改，请刷新后重试", code="version_conflict")
                deleted = session.execute(
                    delete(_TABLE).where(
                        _TABLE.c.id == template_id,
                        _TABLE.c.owner_id == owner_id,
                        _TABLE.c.version == version,
                    )
                )
                if deleted.rowcount != 1:
                    raise TaskTemplateConflict(
                        "任务模板已被修改，请刷新后重试", code="version_conflict",
                    )
    except SQLAlchemyError as exc:
        raise TaskTemplateUnavailable("任务模板删除失败") from exc
    return {"id": template_id, "deleted": True}


__all__ = [
    "MAX_TEMPLATES_PER_USER",
    "TaskTemplateConflict",
    "TaskTemplateInvalid",
    "TaskTemplateNotFound",
    "TaskTemplateUnavailable",
    "create_task_template",
    "delete_task_template",
    "list_task_templates",
    "update_task_template",
    "validate_task_template_config",
]
