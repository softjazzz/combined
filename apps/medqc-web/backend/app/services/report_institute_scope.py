"""质量报表与人工审核共用持久账号机构范围，不接受客户端声明的全局权限。"""

from .defect_rectification_service import RectificationError, _person

EXCLUDED_SYNTHETIC_TEST_INSTITUTES = frozenset(
    {"CUSTOMER_TEST", "LX0609_SYN", "LX0609_0426_SYN", "MOCKV2"}
)


def is_excluded_synthetic_institute(institute_id: object) -> bool:
    return str(institute_id or "").strip() in EXCLUDED_SYNTHETIC_TEST_INSTITUTES


def _trusted_bound_institute(person: dict) -> str | None:
    institute = person.get("institute_id")
    if (
        isinstance(institute, str)
        and institute.strip()
        and institute == institute.strip()
    ):
        return institute
    return None


def authorized_institute(session, actor_id):
    if not isinstance(actor_id, str) or not actor_id.strip():
        raise RectificationError("缺少可信账号身份", 403)
    person = _person(session, actor_id.strip())
    roles = person["roles"]
    if not roles & {"admin", "super_admin", "qc_manager"}:
        raise RectificationError("没有质量报表或人工审核权限", 403)
    institute = person["institute_id"]
    is_global = ("sync_admin" in roles) or (
        bool(roles & {"admin", "super_admin"}) and not institute
    )
    if is_global:
        return None
    if (
        not isinstance(institute, str)
        or not institute.strip()
        or institute != institute.strip()
    ):
        raise RectificationError("账号缺少可信机构范围", 403)
    return institute


def authorized_report_institute(actor_id):
    from ..database.connection import SessionLocal

    if SessionLocal is None:
        raise RuntimeError("账号范围来源暂不可用")
    with SessionLocal() as session:
        allowed = authorized_institute(session, actor_id)
        if allowed is not None:
            return allowed
        person = _person(session, actor_id.strip())
        if "sync_admin" in person["roles"]:
            return _trusted_bound_institute(person)
        return None


def authorized_requested_institute(actor_id, requested=None):
    from ..database.connection import SessionLocal

    if SessionLocal is None:
        raise RuntimeError("账号范围来源暂不可用")
    with SessionLocal() as session:
        allowed = authorized_institute(session, actor_id)
        if allowed is not None:
            if requested not in (None, allowed):
                raise RectificationError("无权访问其他机构报表", 403)
            return allowed
        if requested is not None:
            return requested
        person = _person(session, actor_id.strip())
        if "sync_admin" in person["roles"]:
            return _trusted_bound_institute(person)
        return None
