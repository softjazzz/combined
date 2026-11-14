"""保存结果入口的机构授权；账号角色与机构只取持久 owner。"""

from fastapi import HTTPException

from .defect_rectification_service import RectificationError, _person


def saved_result_institute_scope(actor_id: str) -> str | None:
    """None 仅表示持久账号具有全局角色，不以请求中的角色或机构兜底。"""
    from ..database.connection import SessionLocal

    if not isinstance(actor_id, str) or not actor_id.strip():
        raise HTTPException(403, "缺少可信账号身份")
    try:
        if SessionLocal is None:
            raise RuntimeError("account_store_unavailable")
        with SessionLocal() as session:
            actor = _person(session, actor_id.strip())
        # 与既有报表的 admin/sync_admin 全局范围一致，保留本入口原有 super_admin。
        if actor["roles"] & {"admin", "sync_admin", "super_admin"}:
            return None
        if "qc_manager" not in actor["roles"]:
            raise HTTPException(403, "无权读取质控结果")
        scope = actor["institute_id"]
        if not isinstance(scope, str) or not scope.strip() or scope != scope.strip():
            raise HTTPException(403, "账号缺少可信机构范围")
        return scope
    except RectificationError:
        raise HTTPException(403, "账号或机构权限无效") from None
    except HTTPException:
        raise
    except Exception:
        # 数据库异常不回显连接串、SQL或账号内部信息，也不按请求角色兜底。
        raise HTTPException(503, "账号机构权限来源暂不可用") from None


def check_saved_result_institute(scope: str | None, institute_id: str) -> None:
    if not isinstance(institute_id, str) or not institute_id.strip() or institute_id != institute_id.strip():
        raise HTTPException(403, "缺少可信病历机构范围")
    if scope is not None and scope != institute_id:
        raise HTTPException(403, "无权读取其他机构质控结果")


def require_saved_result_institute(actor_id: str, institute_id: str) -> None:
    check_saved_result_institute(saved_result_institute_scope(actor_id), institute_id)


def require_retry_record_institutes(actor_id: str, record_refs: object) -> None:
    """每次重试重新读取账号权限；旧任务创建者身份不等于当前机构授权。"""
    scope = saved_result_institute_scope(actor_id)
    if not isinstance(record_refs, list) or not record_refs:
        raise HTTPException(403, "重试任务缺少可信病历范围")
    for ref in record_refs:
        if not isinstance(ref, dict) or not all(isinstance(ref.get(key), str) and ref[key].strip()
                for key in ("institute_id", "patient_id", "visit_id")):
            raise HTTPException(403, "重试任务缺少可信病历范围")
        check_saved_result_institute(scope, ref["institute_id"])
