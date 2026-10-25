"""账号角色的运行时授权语义；不修改账号存储。"""
from typing import Any


def effective_roles(value: Any) -> list[str]:
    roles = [role for role in value if isinstance(role, str)] if isinstance(value, (list, tuple)) else []
    if "sync_admin" in roles:
        # 不附加doctor等业务身份，避免触发其个人病历范围等身份条件。
        return list(dict.fromkeys([*roles, "admin", "qc_manager", "developer", "super_admin"]))
    return roles


def effective_principal(user: dict) -> dict:
    return {**user, "roles": effective_roles(user.get("roles"))}
