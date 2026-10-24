"""质量报表与人工审核共用持久账号机构范围，不接受客户端声明的全局权限。"""

from .defect_rectification_service import RectificationError, _person


def authorized_institute(session, actor_id):
    if not isinstance(actor_id, str) or not actor_id.strip():
        raise RectificationError("缺少可信账号身份", 403)
    person = _person(session, actor_id.strip())
    if not person["roles"] & {"admin", "qc_manager"}:
        raise RectificationError("没有质量报表或人工审核权限", 403)
    if "admin" in person["roles"]:
        return None
    institute = person["institute_id"]
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
        return authorized_institute(session, actor_id)


def authorized_requested_institute(actor_id, requested=None):
    institute = authorized_report_institute(actor_id)
    if institute is not None and requested not in (None, institute):
        raise RectificationError("无权访问其他机构报表", 403)
    return institute if institute is not None else requested
