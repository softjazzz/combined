"""PR8报表只读消费子集，来源88e8f864b；不移植写入口与执行链。"""

import json

from sqlalchemy import select

from ..database.models.v36_reports import SysUser
from .user_scope_owner import user_owner_options

MANAGERS = {"admin", "qc_manager", "qc_staff"}


class RectificationError(ValueError):
    def __init__(self, message, status=422):
        super().__init__(message)
        self.status = status


def _persistent_roles(role, roles_json):
    """整改授权只读取明确持久角色；损坏的多角色配置不得回退放行。"""
    if roles_json is not None and roles_json != "":
        try:
            roles = json.loads(roles_json)
        except (TypeError, ValueError):
            return set()
        if not isinstance(roles, list) or any(
            not isinstance(item, str) or not item.strip() for item in roles
        ):
            return set()
        return {item.strip() for item in roles}
    return {role.strip()} if isinstance(role, str) and role.strip() else set()


def _person(session, user_id):
    row = session.execute(
        select(SysUser).where(SysUser.id == user_id),
        execution_options=user_owner_options(session),
    ).scalar_one_or_none()
    if row is None or not row.is_active:
        raise RectificationError("账号不可用", 403)
    roles = _persistent_roles(row.role, row.roles_json)
    if not roles:
        raise RectificationError("账号缺少可信持久角色", 403)
    return {
        "id": row.id,
        "name": row.display_name,
        "institute_id": row.institute_id,
        "department": row.department,
        "roles": roles,
    }


def _manager(person):
    return bool(person["roles"] & MANAGERS)


def _active_urge_ids(events):
    # 医生提交已回应此前提醒；被明确撤回的提醒不再有效，历史行保留。
    submitted_version = max(
        (event.version for event in events if event.action == "submit"), default=0
    )
    withdrawn = {
        event.related_event_id for event in events if event.action == "withdraw_urge"
    }
    return {
        event.id
        for event in events
        if event.action == "urge"
        and event.version > submitted_version
        and event.id not in withdrawn
    }
