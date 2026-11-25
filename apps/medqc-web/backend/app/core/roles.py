"""账号角色的运行时授权语义；不修改账号存储。"""
from typing import Any

from ..storage.memory import DEFAULT_DEMO_USER_EMAILS


_SUPER_ADMIN_ROLES = ("sync_admin", "super_admin")


def is_demo_account_email(email: Any) -> bool:
    return str(email or "").strip().lower() in DEFAULT_DEMO_USER_EMAILS


def effective_roles(value: Any) -> list[str]:
    roles = [role for role in value if isinstance(role, str)] if isinstance(value, (list, tuple)) else []
    if any(role in _SUPER_ADMIN_ROLES for role in roles):
        # 不附加doctor等业务身份，避免触发其个人病历范围等身份条件。
        # 纯 super_admin 不附加 sync_admin，保留基于 sync_admin/institute_id 判定的全局范围语义。
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
