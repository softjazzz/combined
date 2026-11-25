"""
科室级质控规则管理路由
实现科室级规则的 CRUD 操作、发布、变更历史查询等功能
"""

import logging
import re
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, HTTPException, status, Query, Request, Depends

from ..schemas.qc import (
    QCRuleExtended,
    DepartmentRuleCreate,
    DepartmentRuleUpdate,
    DepartmentRulePublish,
    RuleChangeLog,
    RuleScope,
    RuleStatus,
    OverrideAction,
)
from ..core.supabase_client import get_supabase, async_execute
from ..core.response import success_response, paginated_response, get_trace_id, ErrorCode, StatusCode
from ..core.roles import effective_roles
from ..core.security import get_current_user
from ..core.permissions import (
    require_permission,
    require_role,
    require_admin,
    ResourceType,
    PermissionAction,
    UserRole,
)

router = APIRouter(prefix="/api/v1/qc/rules/department", tags=["department-qc-rules"])
logger = logging.getLogger(__name__)

_GLOBAL_RULE_ROLES = frozenset({"admin", "super_admin", "sync_admin"})
_DEMO_FULL_ROLES = frozenset({"sync_admin", "super_admin", "developer"})
_OR_FILTER_UNSAFE_RE = re.compile(r"[,().*%_\\\"\']+")


# ============================================================================
# Helper Functions
# ============================================================================

def _sanitize_or_keyword(keyword: str) -> str:
    """移除 PostgREST .or_() 语法敏感字符，防止通过逗号/括号/点号注入额外过滤条件。"""
    return _OR_FILTER_UNSAFE_RE.sub("", str(keyword or "").strip())


def _user_roles(current_user: dict) -> set[str]:
    roles = set(effective_roles((current_user or {}).get("roles")))
    single = str((current_user or {}).get("role") or "").strip()
    if single:
        roles.update(effective_roles([single]))
    return {r.strip().lower() for r in roles if isinstance(r, str) and r.strip()}


def _is_restricted_demo_account(current_user: Optional[Dict[str, Any]]) -> bool:
    if not isinstance(current_user, dict):
        return False
    if current_user.get("is_demo_account") is not True:
        return False
    return not bool(_user_roles(current_user).intersection(_DEMO_FULL_ROLES))


def _reject_restricted_demo_account(
    current_user: Optional[Dict[str, Any]],
    detail: str = "演示账号禁止执行该操作",
) -> None:
    if _is_restricted_demo_account(current_user):
        raise HTTPException(status_code=StatusCode.FORBIDDEN, detail=detail)


def _resolve_qc_manager_scope(current_user: dict) -> tuple[bool, str, str, str]:
    """解析用户的院区/科室作用域。

    返回 `(is_global, institute_id, department_id, department_name)`。
    仅 `sync_admin` 或无绑定 `institute_id` 的 `admin`/`super_admin` 放行全局；
    绑定了 `institute_id` 的 `admin`/`super_admin` 强制按本院隔离。
    """
    roles = _user_roles(current_user)
    user_id = str((current_user or {}).get("id") or (current_user or {}).get("user_id") or "").strip()
    user_inst = str((current_user or {}).get("institute_id") or "").strip()
    user_dept_id = str((current_user or {}).get("department_id") or "").strip()
    user_dept_name = str((current_user or {}).get("department") or "").strip()

    # 若持久账号库可用且存在该账号，以持久账号记录为准，不信任请求覆盖
    if user_id:
        try:
            from sqlalchemy import inspect as sa_inspect, text as sa_text
            from ..database import connection as db_connection
            from ..services.defect_rectification_service import _effective_persistent_roles
            from ..services.user_scope_owner import resolve_user_owner_schema

            session_factory = db_connection.SessionLocal
            if session_factory is not None:
                with session_factory() as session:
                    owner_schema = resolve_user_owner_schema(session)
                    inspector = sa_inspect(session.connection())
                    if inspector.has_table("sys_users", schema=owner_schema):
                        cols = {
                            col["name"]
                            for col in inspector.get_columns("sys_users", schema=owner_schema)
                        }
                        has_inst = "institute_id" in cols
                        has_dept = "department" in cols
                        table_ref = (
                            f'"{owner_schema}"."sys_users"'
                            if owner_schema
                            else '"sys_users"'
                        )
                        select_cols = (
                            "id, role, roles_json, is_active"
                            + (", institute_id" if has_inst else "")
                            + (", department" if has_dept else "")
                        )
                        row = (
                            session.execute(
                                sa_text(f"SELECT {select_cols} FROM {table_ref} WHERE id = :uid"),
                                {"uid": user_id},
                            )
                            .mappings()
                            .one_or_none()
                        )
                        if row is not None:
                            if not bool(row.get("is_active")):
                                return False, "", "", ""
                            p_roles = _effective_persistent_roles(
                                row.get("role"), row.get("roles_json")
                            )
                            if not p_roles:
                                return False, "", "", ""
                            roles = {r.strip().lower() for r in p_roles if isinstance(r, str) and r.strip()}
                            user_inst = str((row.get("institute_id") if has_inst else "") or "").strip()
                            user_dept_name = str((row.get("department") if has_dept else "") or "").strip()
        except Exception:
            pass

    is_global = ("sync_admin" in roles) or (
        bool(roles & {"admin", "super_admin"}) and not user_inst
    )
    if is_global:
        return True, "", "", ""

    # 绑定院区的 admin/super_admin 按院区强制隔离，可管理本院内各科室规则
    if roles & {"admin", "super_admin"}:
        return False, user_inst, "", ""

    return False, user_inst, user_dept_id, user_dept_name


async def _enforce_qc_manager_department_scope(
    sb,
    current_user: dict,
    department_id: Optional[str],
    *,
    dept_row: Optional[Dict[str, Any]] = None,
    rule_row: Optional[Dict[str, Any]] = None,
) -> None:
    """为非全局 qc_manager 强制校验目标科室的院区/科室归属。"""
    is_global, user_inst, user_dept_id, user_dept_name = _resolve_qc_manager_scope(current_user)
    if is_global:
        return

    if not any((user_inst, user_dept_id, user_dept_name)):
        raise HTTPException(
            status_code=StatusCode.FORBIDDEN,
            detail="质控管理员账号缺少院区或科室归属配置，无权操作科室规则",
        )

    target_dept_id = str(department_id or (rule_row or {}).get("department_id") or "").strip()
    if not target_dept_id:
        raise HTTPException(
            status_code=StatusCode.FORBIDDEN,
            detail="目标规则缺少科室归属，无权操作",
        )

    resolved_dept = dept_row
    if resolved_dept is None and sb is not None:
        try:
            resp = await async_execute(
                sb.table('departments').select('*').eq('id', target_dept_id).single()
            )
            resolved_dept = getattr(resp, 'data', None)
        except Exception:
            resolved_dept = None

    # 院区归属校验
    if user_inst:
        target_inst = str(
            (resolved_dept or {}).get("institute_id")
            or (rule_row or {}).get("institute_id")
            or ""
        ).strip()
        if target_inst:
            if target_inst != user_inst:
                raise HTTPException(
                    status_code=StatusCode.FORBIDDEN,
                    detail="无权操作其他院区的科室规则",
                )
        elif not (user_dept_id or user_dept_name):
            raise HTTPException(
                status_code=StatusCode.FORBIDDEN,
                detail="目标科室缺少可信院区归属，无权操作",
            )

    # 科室归属校验（当账号配置了明确科室时）
    if user_dept_id or user_dept_name:
        matched = False
        if user_dept_id and target_dept_id == user_dept_id:
            matched = True
        if not matched and isinstance(resolved_dept, dict):
            dept_candidates = {
                str(resolved_dept.get("id") or "").strip(),
                str(resolved_dept.get("name") or "").strip(),
                str(resolved_dept.get("code") or "").strip(),
            }
            dept_candidates.discard("")
            if (user_dept_id and user_dept_id in dept_candidates) or (
                user_dept_name and user_dept_name in dept_candidates
            ):
                matched = True
        if not matched and isinstance(rule_row, dict):
            rule_dept_name = str(rule_row.get("department_name") or "").strip()
            if user_dept_name and rule_dept_name == user_dept_name:
                matched = True
        if not matched:
            raise HTTPException(
                status_code=StatusCode.FORBIDDEN,
                detail="无权操作其他科室的质控规则",
            )


def set_current_user_context(supabase, user_id: str):
    """设置当前用户上下文（用于审计日志）"""
    safe_uid = str(user_id or "").strip()
    if not safe_uid:
        return
    try:
        # 使用 Supabase RPC 设置会话变量
        supabase.rpc('set_config', {
            'setting_name': 'app.current_user_id',
            'new_value': safe_uid,
            'is_local': True
        }).execute()
    except Exception:
        # 忽略错误，审计日志会使用默认值
        pass


# ============================================================================
# API Endpoints
# ============================================================================

@router.post("", status_code=status.HTTP_201_CREATED)
@require_role([UserRole.ADMIN, UserRole.QC_MANAGER])
async def create_department_rule(
    request: Request,
    payload: DepartmentRuleCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    创建科室规则
    
    支持两种模式：
    1. 覆盖全局规则：提供 base_rule_id，创建科室覆盖规则
    2. 创建新规则：不提供 base_rule_id，创建科室特有规则
    """
    _reject_restricted_demo_account(current_user, "演示账号禁止创建科室规则")
    sb = get_supabase()
    if sb is None:
        raise HTTPException(
            status_code=StatusCode.SERVICE_UNAVAILABLE,
            detail="数据库服务不可用"
        )
    
    try:
        # 设置当前用户上下文（用于审计日志）
        user_id = current_user.get("id") or current_user.get("user_id")
        set_current_user_context(sb, user_id)
        
        # 验证科室是否存在
        dept_check = await async_execute(
            sb.table('departments').select('*').eq('id', payload.department_id).single()
        )
        if not dept_check.data:
            raise HTTPException(
                status_code=StatusCode.NOT_FOUND,
                detail=f"科室不存在: {payload.department_id}"
            )

        # 非全局 qc_manager 必须校验院区/科室归属
        await _enforce_qc_manager_department_scope(
            sb,
            current_user,
            payload.department_id,
            dept_row=dept_check.data,
        )
        
        # 如果是覆盖规则，验证基础规则是否存在
        parent_rule_id = None
        if payload.base_rule_id:
            base_rule_check = await async_execute(
                sb.table('qc_rules')
                .select('id, rule_code, scope')
                .eq('id', payload.base_rule_id)
                .single()
            )
            if not base_rule_check.data:
                raise HTTPException(
                    status_code=StatusCode.NOT_FOUND,
                    detail=f"基础规则不存在: {payload.base_rule_id}"
                )
            if base_rule_check.data.get('scope') != RuleScope.GLOBAL.value:
                raise HTTPException(
                    status_code=StatusCode.BAD_REQUEST,
                    detail="只能覆盖全局规则"
                )
            parent_rule_id = payload.base_rule_id
        
        # 检查是否已存在相同的科室规则
        existing_check = await async_execute(
            sb.table('qc_rules')
            .select('id')
            .eq('department_id', payload.department_id)
            .eq('rule_code', payload.rule_code)
            .eq('status', RuleStatus.PUBLISHED.value)
        )
        if existing_check.data and len(existing_check.data) > 0:
            raise HTTPException(
                status_code=StatusCode.CONFLICT,
                detail=f"科室已存在相同规则编号的已发布规则: {payload.rule_code}"
            )
        
        # 构建规则数据
        rule_data = {
            "id": str(uuid.uuid4()),
            "rule_code": payload.rule_code,
            "name": payload.name,
            "description": payload.description,
            "category": payload.category,
            "severity": payload.severity,
            "scope": RuleScope.DEPARTMENT.value,
            "department_id": payload.department_id,
            "parent_rule_id": parent_rule_id,
            "override_action": payload.override_action.value,
            "override_config": payload.override_config or {},
            "priority": payload.priority,
            # 强制创建为草稿状态，禁止跳过发布审批流
            "status": RuleStatus.DRAFT.value,
            "effective_from": payload.effective_from.isoformat() if payload.effective_from else None,
            "effective_to": payload.effective_to.isoformat() if payload.effective_to else None,
            "check_logic": payload.check_logic or {},
            "scoring_config": payload.scoring_config or {},
            "applicable_documents": payload.applicable_documents or [],
            "is_active": True,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        
        # 插入规则
        result = await async_execute(
            sb.table('qc_rules').insert(rule_data).select().single()
        )
        
        if not result.data:
            raise HTTPException(
                status_code=StatusCode.INTERNAL_SERVER_ERROR,
                detail="创建规则失败"
            )
        
        return success_response(
            data=result.data,
            message="科室规则创建成功",
            trace_id=get_trace_id(request)
        )
    
    except HTTPException:
        raise
    except Exception:
        logger.exception("创建科室规则失败")
        raise HTTPException(
            status_code=StatusCode.INTERNAL_SERVER_ERROR,
            detail="创建科室规则失败，请稍后重试"
        )


@router.put("/{rule_id}")
@require_role([UserRole.ADMIN, UserRole.QC_MANAGER])
async def update_department_rule(
    request: Request,
    rule_id: str,
    payload: DepartmentRuleUpdate,
    current_user: dict = Depends(get_current_user)
):
    """
    更新科室规则
    
    只能更新科室规则（scope='department'），不能更新全局规则
    """
    _reject_restricted_demo_account(current_user, "演示账号禁止更新科室规则")
    sb = get_supabase()
    if sb is None:
        raise HTTPException(
            status_code=StatusCode.SERVICE_UNAVAILABLE,
            detail="数据库服务不可用"
        )
    
    try:
        # 设置当前用户上下文
        user_id = current_user.get("id") or current_user.get("user_id")
        set_current_user_context(sb, user_id)
        
        # 验证规则是否存在且为科室规则
        rule_check = await async_execute(
            sb.table('qc_rules')
            .select('*')
            .eq('id', rule_id)
            .single()
        )
        
        if not rule_check.data:
            raise HTTPException(
                status_code=StatusCode.NOT_FOUND,
                detail=f"规则不存在: {rule_id}"
            )
        
        if rule_check.data.get('scope') != RuleScope.DEPARTMENT.value:
            raise HTTPException(
                status_code=StatusCode.BAD_REQUEST,
                detail="只能更新科室规则"
            )

        # 非全局 qc_manager 必须校验院区/科室归属
        await _enforce_qc_manager_department_scope(
            sb,
            current_user,
            rule_check.data.get('department_id'),
            rule_row=rule_check.data,
        )

        # 禁止原地篡改已发布规则，避免绕过发布审批与版本留痕
        if str(rule_check.data.get('status') or '').strip().lower() == RuleStatus.PUBLISHED.value:
            raise HTTPException(
                status_code=StatusCode.CONFLICT,
                detail="已发布规则禁止原地修改，请创建新草稿后再发布",
            )
        
        # 构建更新数据（只更新提供的字段）
        update_data = {"updated_at": datetime.utcnow().isoformat()}
        
        if payload.name is not None:
            update_data["name"] = payload.name
        if payload.description is not None:
            update_data["description"] = payload.description
        if payload.severity is not None:
            update_data["severity"] = payload.severity
        if payload.override_action is not None:
            update_data["override_action"] = payload.override_action.value
        if payload.override_config is not None:
            update_data["override_config"] = payload.override_config
        if payload.priority is not None:
            update_data["priority"] = payload.priority
        if payload.effective_from is not None:
            update_data["effective_from"] = payload.effective_from.isoformat()
        if payload.effective_to is not None:
            update_data["effective_to"] = payload.effective_to.isoformat()
        if payload.check_logic is not None:
            update_data["check_logic"] = payload.check_logic
        if payload.scoring_config is not None:
            update_data["scoring_config"] = payload.scoring_config
        if payload.applicable_documents is not None:
            update_data["applicable_documents"] = payload.applicable_documents
        if payload.is_active is not None:
            update_data["is_active"] = payload.is_active
        
        # 更新规则
        result = await async_execute(
            sb.table('qc_rules')
            .update(update_data)
            .eq('id', rule_id)
            .select()
            .single()
        )
        
        if not result.data:
            raise HTTPException(
                status_code=StatusCode.INTERNAL_SERVER_ERROR,
                detail="更新规则失败"
            )
        
        return success_response(
            data=result.data,
            message="科室规则更新成功",
            trace_id=get_trace_id(request)
        )

    except HTTPException:
        raise
    except Exception:
        logger.exception("更新科室规则失败 rule_id=%s", rule_id)
        raise HTTPException(
            status_code=StatusCode.INTERNAL_SERVER_ERROR,
            detail="更新科室规则失败，请稍后重试"
        )


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
@require_admin()
async def delete_department_rule(
    request: Request,
    rule_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    删除科室规则

    只有管理员可以删除规则
    只能删除科室规则（scope='department'），不能删除全局规则
    """
    _reject_restricted_demo_account(current_user, "演示账号禁止删除科室规则")
    sb = get_supabase()
    if sb is None:
        raise HTTPException(
            status_code=StatusCode.SERVICE_UNAVAILABLE,
            detail="数据库服务不可用"
        )

    try:
        # 设置当前用户上下文
        user_id = current_user.get("id") or current_user.get("user_id")
        set_current_user_context(sb, user_id)

        # 验证规则是否存在且为科室规则
        rule_check = await async_execute(
            sb.table('qc_rules')
            .select('*')
            .eq('id', rule_id)
            .single()
        )

        if not rule_check.data:
            raise HTTPException(
                status_code=StatusCode.NOT_FOUND,
                detail=f"规则不存在: {rule_id}"
            )

        if rule_check.data.get('scope') != RuleScope.DEPARTMENT.value:
            raise HTTPException(
                status_code=StatusCode.BAD_REQUEST,
                detail="只能删除科室规则"
            )

        # 非全局管理员/质控管理员必须校验院区/科室归属
        await _enforce_qc_manager_department_scope(
            sb,
            current_user,
            rule_check.data.get('department_id'),
            rule_row=rule_check.data,
        )

        # 删除规则
        await async_execute(
            sb.table('qc_rules').delete().eq('id', rule_id)
        )

        return None  # 204 No Content

    except HTTPException:
        raise
    except Exception:
        logger.exception("删除科室规则失败 rule_id=%s", rule_id)
        raise HTTPException(
            status_code=StatusCode.INTERNAL_SERVER_ERROR,
            detail="删除科室规则失败，请稍后重试"
        )


@router.patch("/{rule_id}/publish")
@require_role([UserRole.ADMIN, UserRole.QC_MANAGER])
async def publish_department_rule(
    request: Request,
    rule_id: str,
    payload: DepartmentRulePublish,
    current_user: dict = Depends(get_current_user)
):
    """
    发布科室规则

    将草稿状态的规则发布为正式规则
    """
    _reject_restricted_demo_account(current_user, "演示账号禁止发布科室规则")
    sb = get_supabase()
    if sb is None:
        raise HTTPException(
            status_code=StatusCode.SERVICE_UNAVAILABLE,
            detail="数据库服务不可用"
        )

    try:
        # 设置当前用户上下文
        user_id = current_user.get("id") or current_user.get("user_id")
        set_current_user_context(sb, user_id)

        # 验证规则是否存在且为草稿状态
        rule_check = await async_execute(
            sb.table('qc_rules')
            .select('*')
            .eq('id', rule_id)
            .single()
        )

        if not rule_check.data:
            raise HTTPException(
                status_code=StatusCode.NOT_FOUND,
                detail=f"规则不存在: {rule_id}"
            )

        if rule_check.data.get('scope') != RuleScope.DEPARTMENT.value:
            raise HTTPException(
                status_code=StatusCode.BAD_REQUEST,
                detail="只能发布科室规则"
            )

        # 非全局 qc_manager 必须校验院区/科室归属
        await _enforce_qc_manager_department_scope(
            sb,
            current_user,
            rule_check.data.get('department_id'),
            rule_row=rule_check.data,
        )

        if rule_check.data.get('status') != RuleStatus.DRAFT.value:
            raise HTTPException(
                status_code=StatusCode.BAD_REQUEST,
                detail=f"只能发布草稿状态的规则，当前状态: {rule_check.data.get('status')}"
            )

        approver_id = str(current_user.get("id") or current_user.get("user_id") or "").strip()
        if not approver_id:
            raise HTTPException(
                status_code=StatusCode.FORBIDDEN,
                detail="缺少可信审批人身份",
            )

        # 更新规则状态为已发布（approved_by 强制取当前认证用户，不信任请求体）
        update_data = {
            "status": RuleStatus.PUBLISHED.value,
            "approved_by": approver_id,
            "approved_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }

        result = await async_execute(
            sb.table('qc_rules')
            .update(update_data)
            .eq('id', rule_id)
            .select()
            .single()
        )

        if not result.data:
            raise HTTPException(
                status_code=StatusCode.INTERNAL_SERVER_ERROR,
                detail="发布规则失败"
            )

        return success_response(
            data=result.data,
            message="科室规则发布成功",
            trace_id=get_trace_id(request)
        )

    except HTTPException:
        raise
    except Exception:
        logger.exception("发布科室规则失败 rule_id=%s", rule_id)
        raise HTTPException(
            status_code=StatusCode.INTERNAL_SERVER_ERROR,
            detail="发布科室规则失败，请稍后重试"
        )


@router.get("/{rule_id}/history")
@require_permission(ResourceType.QC_RULES, PermissionAction.READ)
async def get_rule_change_history(
    request: Request,
    rule_id: str,
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user: dict = Depends(get_current_user)
):
    """
    查看规则变更历史

    返回规则的所有变更审计日志
    """
    sb = get_supabase()
    if sb is None:
        raise HTTPException(
            status_code=StatusCode.SERVICE_UNAVAILABLE,
            detail="数据库服务不可用"
        )

    try:
        # 验证规则是否存在
        rule_check = await async_execute(
            sb.table('qc_rules')
            .select('id, scope, department_id')
            .eq('id', rule_id)
            .single()
        )

        if not rule_check.data:
            raise HTTPException(
                status_code=StatusCode.NOT_FOUND,
                detail=f"规则不存在: {rule_id}"
            )

        if rule_check.data.get('scope') == RuleScope.DEPARTMENT.value:
            await _enforce_qc_manager_department_scope(
                sb,
                current_user,
                rule_check.data.get('department_id'),
                rule_row=rule_check.data,
            )

        # 查询变更历史
        offset = (page - 1) * limit
        query = (
            sb.table('qc_rule_change_logs')
            .select('*', count='exact')
            .eq('rule_id', rule_id)
            .order('created_at', desc=True)
            .range(offset, offset + limit - 1)
        )

        result = await async_execute(query)

        data = list(getattr(result, 'data', None) or [])
        total = getattr(result, 'count', None) or len(data)

        return paginated_response(
            items=data,
            total=total,
            page=page,
            page_size=limit,
            message="获取变更历史成功",
            trace_id=get_trace_id(request)
        )

    except HTTPException:
        raise
    except Exception:
        logger.exception("获取变更历史失败 rule_id=%s", rule_id)
        raise HTTPException(
            status_code=StatusCode.INTERNAL_SERVER_ERROR,
            detail="获取变更历史失败，请稍后重试"
        )


@router.get("/applicable")
@require_permission(ResourceType.QC_RULES, PermissionAction.READ)
async def get_applicable_rules(
    request: Request,
    department_id: str = Query(..., description="科室ID"),
    document_type: Optional[str] = Query(None, description="文书类型"),
    at: Optional[str] = Query(None, description="时间点（ISO 8601格式，用于生效期判断）"),
    current_user: dict = Depends(get_current_user)
):
    """
    获取适用的质控规则

    调用数据库 RPC 函数 get_applicable_qc_rules，返回适用于指定科室和文书类型的规则列表

    规则匹配逻辑：
    1. 获取有效的全局规则
    2. 获取有效的科室规则
    3. 处理覆盖和禁用逻辑：
       - 科室覆盖规则会替换同 rule_code 的全局规则
       - 科室禁用规则会排除同 rule_code 的全局规则
    4. 按优先级排序返回
    """
    sb = get_supabase()
    if sb is None:
        raise HTTPException(
            status_code=StatusCode.SERVICE_UNAVAILABLE,
            detail="数据库服务不可用"
        )

    try:
        # 验证科室是否存在
        dept_check = await async_execute(
            sb.table('departments')
            .select('*')
            .eq('id', department_id)
            .single()
        )

        if not dept_check.data:
            raise HTTPException(
                status_code=StatusCode.NOT_FOUND,
                detail=f"科室不存在: {department_id}"
            )

        await _enforce_qc_manager_department_scope(
            sb,
            current_user,
            department_id,
            dept_row=dept_check.data,
        )

        # 解析时间点参数
        at_timestamp = None
        if at:
            try:
                at_timestamp = datetime.fromisoformat(at.replace('Z', '+00:00')).isoformat()
            except ValueError:
                raise HTTPException(
                    status_code=StatusCode.BAD_REQUEST,
                    detail=f"无效的时间格式: {at}，请使用 ISO 8601 格式"
                )
        else:
            at_timestamp = datetime.utcnow().isoformat()

        # 调用 RPC 函数获取适用规则
        rpc_params = {
            'p_department_id': department_id
        }
        # 仅当提供文书类型 / 时间点时再传参，避免 PostgREST 参数解析问题
        if document_type is not None:
            rpc_params['p_document_type'] = document_type
        if at_timestamp is not None:
            rpc_params['p_at'] = at_timestamp

        result = await async_execute(
            sb.rpc('get_applicable_qc_rules', rpc_params)
        )

        rules = list(getattr(result, 'data', None) or [])

        return success_response(
            data={
                "rules": rules,
                "count": len(rules),
                "department_id": department_id,
                "document_type": document_type,
                "at": at_timestamp,
            },
            message=f"获取适用规则成功，共 {len(rules)} 条",
            trace_id=get_trace_id(request)
        )

    except HTTPException:
        raise
    except Exception:
        logger.exception("获取适用规则失败 department_id=%s", department_id)
        raise HTTPException(
            status_code=StatusCode.INTERNAL_SERVER_ERROR,
            detail="获取适用规则失败，请稍后重试"
        )


@router.get("")
@require_permission(ResourceType.QC_RULES, PermissionAction.READ)
async def list_department_rules(
    request: Request,
    department_id: Optional[str] = Query(None, description="科室ID"),
    status_filter: Optional[str] = Query(None, description="规则状态"),
    override_action: Optional[str] = Query(None, description="覆盖行为"),
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user: dict = Depends(get_current_user)
):
    """
    获取科室规则列表

    支持按科室、状态、覆盖行为、关键词筛选
    """
    sb = get_supabase()
    if sb is None:
        raise HTTPException(
            status_code=StatusCode.SERVICE_UNAVAILABLE,
            detail="数据库服务不可用"
        )

    try:
        is_global, user_inst, user_dept_id, user_dept_name = _resolve_qc_manager_scope(current_user)
        if not is_global:
            if not any((user_inst, user_dept_id, user_dept_name)):
                raise HTTPException(
                    status_code=StatusCode.FORBIDDEN,
                    detail="账号缺少院区或科室归属配置，无权查看科室规则列表",
                )
            if department_id:
                await _enforce_qc_manager_department_scope(sb, current_user, department_id)

        # 构建查询
        query = sb.table('qc_rules').select('*', count='exact')

        # 只查询科室规则
        query = query.eq('scope', RuleScope.DEPARTMENT.value)

        # 按科室筛选
        if department_id:
            query = query.eq('department_id', department_id)
        elif not is_global:
            if user_dept_id:
                query = query.eq('department_id', user_dept_id)
            else:
                # 查询账号可访问的科室列表并限定过滤
                dept_query = sb.table('departments').select('id, name, code, institute_id')
                if user_inst:
                    dept_query = dept_query.eq('institute_id', user_inst)
                dept_resp = await async_execute(dept_query)
                dept_rows = list(getattr(dept_resp, 'data', None) or [])
                allowed_dept_ids = [
                    str(row.get('id'))
                    for row in dept_rows
                    if row.get('id')
                    and (
                        not user_dept_name
                        or str(row.get('name') or '').strip() == user_dept_name
                        or str(row.get('code') or '').strip() == user_dept_name
                    )
                ]
                if not allowed_dept_ids:
                    return paginated_response(
                        items=[],
                        total=0,
                        page=page,
                        page_size=limit,
                        message="获取科室规则列表成功",
                        trace_id=get_trace_id(request),
                    )
                if hasattr(query, 'in_'):
                    query = query.in_('department_id', allowed_dept_ids)

        # 按状态筛选
        if status_filter:
            query = query.eq('status', status_filter)

        # 按覆盖行为筛选
        if override_action:
            query = query.eq('override_action', override_action)

        # 关键词搜索（转义 PostgREST .or_() 语法敏感字符防过滤注入）
        if keyword is not None and str(keyword).strip():
            safe_keyword = _sanitize_or_keyword(keyword)
            if not safe_keyword:
                return paginated_response(
                    items=[],
                    total=0,
                    page=page,
                    page_size=limit,
                    message="获取科室规则列表成功",
                    trace_id=get_trace_id(request),
                )
            if hasattr(query, 'or_'):
                query = query.or_(
                    f"name.ilike.%{safe_keyword}%,"
                    f"description.ilike.%{safe_keyword}%,"
                    f"rule_code.ilike.%{safe_keyword}%"
                )

        # 分页
        offset = (page - 1) * limit
        query = query.range(offset, offset + limit - 1)

        # 排序：按优先级降序，再按规则代码升序
        query = query.order('priority', desc=True).order('rule_code')

        # 执行查询
        result = await async_execute(query)

        data = list(getattr(result, 'data', None) or [])
        total = getattr(result, 'count', None) or len(data)

        return paginated_response(
            items=data,
            total=total,
            page=page,
            page_size=limit,
            message="获取科室规则列表成功",
            trace_id=get_trace_id(request)
        )

    except HTTPException:
        raise
    except Exception:
        logger.exception("获取科室规则列表失败")
        raise HTTPException(
            status_code=StatusCode.INTERNAL_SERVER_ERROR,
            detail="获取科室规则列表失败，请稍后重试"
        )


@router.get("/{rule_id}")
@require_permission(ResourceType.QC_RULES, PermissionAction.READ)
async def get_department_rule(
    request: Request,
    rule_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    获取单个科室规则详情
    """
    sb = get_supabase()
    if sb is None:
        raise HTTPException(
            status_code=StatusCode.SERVICE_UNAVAILABLE,
            detail="数据库服务不可用"
        )

    try:
        result = await async_execute(
            sb.table('qc_rules')
            .select('*')
            .eq('id', rule_id)
            .single()
        )

        if not result.data:
            raise HTTPException(
                status_code=StatusCode.NOT_FOUND,
                detail=f"规则不存在: {rule_id}"
            )

        if result.data.get('scope') != RuleScope.DEPARTMENT.value:
            raise HTTPException(
                status_code=StatusCode.BAD_REQUEST,
                detail="该规则不是科室规则"
            )

        await _enforce_qc_manager_department_scope(
            sb,
            current_user,
            result.data.get('department_id'),
            rule_row=result.data,
        )

        return success_response(
            data=result.data,
            message="获取科室规则详情成功",
            trace_id=get_trace_id(request)
        )

    except HTTPException:
        raise
    except Exception:
        logger.exception("获取科室规则详情失败 rule_id=%s", rule_id)
        raise HTTPException(
            status_code=StatusCode.INTERNAL_SERVER_ERROR,
            detail="获取科室规则详情失败，请稍后重试"
        )

