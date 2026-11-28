"""账号角色的运行时授权语义；不修改账号存储。"""
from collections.abc import Iterable, Mapping
import json
from typing import Any

from ..storage.memory import DEFAULT_DEMO_USER_EMAILS


_SUPER_ADMIN_ROLES = ("sync_admin", "super_admin")


def is_demo_account_email(email: Any) -> bool:
    return str(email or "").strip().lower() in DEFAULT_DEMO_USER_EMAILS


def persistent_roles(role: Any, roles_json: Any) -> set[str]:
    """解析持久化账号角色；损坏的多角色 JSON 配置不得回退放行。"""
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


def effective_persistent_roles(role: Any, roles_json: Any) -> set[str]:
    """先验证持久原值，再沿用系统统一权限展开；损坏 JSON 返回空集。"""
    return set(effective_roles(list(persistent_roles(role, roles_json))))


def effective_roles(value: Any) -> list[str]:
    if isinstance(value, (str, bytes, bytearray, Mapping)) or not isinstance(value, Iterable):
        roles: list[str] = []
    else:
        roles = [role for role in value if isinstance(role, str)]
    if any(role in _SUPER_ADMIN_ROLES for role in roles):
        # 不附加doctor等业务身份，避免触发其个人病历范围等身份条件。
        # 纯 super_admin 不附加 sync_admin，两者均具备全局管理角色展开能力。
        return list(dict.fromkeys([*roles, "admin", "qc_manager", "developer", "super_admin"]))
    return roles


def effective_principal(user: dict) -> dict:
    explicit = user.get("is_demo_account")
    is_demo = (
        explicit
        if isinstance(explicit, bool)
        else is_demo_account_email(user.get("email"))
    )
    return {
        **user,
        "roles": effective_roles(user.get("roles")),
        "is_demo_account": is_demo,
    }
