"""首页专属持久账号权限；不放宽其他报表或人工审核权限。"""

from dataclasses import dataclass
from ...services.defect_rectification_service import RectificationError, _person


@dataclass(frozen=True)
class FrontpageAccess:
    actor_id: str
    institute_id: str | None
    roles: frozenset[str]


def resolve_frontpage_access(session, actor_id: str) -> FrontpageAccess:
    if not isinstance(actor_id, str) or not actor_id.strip():
        raise RectificationError("缺少可信账号身份", 403)
    person = _person(session, actor_id.strip())
    roles = frozenset(person["roles"])
    if not roles.intersection(
        {"admin", "sync_admin", "super_admin", "qc_manager", "coder"}
    ):
        raise RectificationError("没有首页质控权限", 403)
    if roles.intersection({"admin", "sync_admin", "super_admin"}):
        return FrontpageAccess(person["id"], None, roles)
    institute = person["institute_id"]
    if (
        not isinstance(institute, str)
        or not institute.strip()
        or institute != institute.strip()
    ):
        raise RectificationError("账号缺少可信机构范围", 403)
    return FrontpageAccess(person["id"], institute, roles)
