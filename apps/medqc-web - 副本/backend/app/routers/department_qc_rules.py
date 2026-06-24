"""
科室级质控规则管理路由
实现科室级规则的 CRUD 操作、发布、变更历史查询等功能
"""

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


# ============================================================================
# Helper Functions
# ============================================================================

def set_current_user_context(supabase, user_id: str):
    """设置当前用户上下文（用于审计日志）"""
    try:
        # 使用 Supabase RPC 设置会话变量
        supabase.rpc('set_config', {
            'setting_name': 'app.current_user_id',
            'new_value': user_id,
            'is_local': True
        }).execute()
    except Exception as e:
        # 如果 RPC 不存在，使用原生 SQL
        try:
            supabase.postgrest.session.execute(
                f"SET LOCAL app.current_user_id = '{user_id}'"
            )
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
            sb.table('departments').select('id').eq('id', payload.department_id).single()
        )
        if not dept_check.data:
            raise HTTPException(
                status_code=StatusCode.NOT_FOUND,
                detail=f"科室不存在: {payload.department_id}"
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
            "status": payload.status.value,
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
    except Exception as e:
        raise HTTPException(
            status_code=StatusCode.INTERNAL_SERVER_ERROR,
            detail=f"创建科室规则失败: {str(e)}"
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
    except Exception as e:
        raise HTTPException(
            status_code=StatusCode.INTERNAL_SERVER_ERROR,
            detail=f"更新科室规则失败: {str(e)}"
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
            .select('id, scope')
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

        # 删除规则
        await async_execute(
            sb.table('qc_rules').delete().eq('id', rule_id)
        )

        return None  # 204 No Content

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=StatusCode.INTERNAL_SERVER_ERROR,
            detail=f"删除科室规则失败: {str(e)}"
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

        if rule_check.data.get('status') != RuleStatus.DRAFT.value:
            raise HTTPException(
                status_code=StatusCode.BAD_REQUEST,
                detail=f"只能发布草稿状态的规则，当前状态: {rule_check.data.get('status')}"
            )

        # 更新规则状态为已发布
        update_data = {
            "status": RuleStatus.PUBLISHED.value,
            "approved_by": payload.approved_by,
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
    except Exception as e:
        raise HTTPException(
            status_code=StatusCode.INTERNAL_SERVER_ERROR,
            detail=f"发布科室规则失败: {str(e)}"
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
            .select('id')
            .eq('id', rule_id)
            .single()
        )

        if not rule_check.data:
            raise HTTPException(
                status_code=StatusCode.NOT_FOUND,
                detail=f"规则不存在: {rule_id}"
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
    except Exception as e:
        raise HTTPException(
            status_code=StatusCode.INTERNAL_SERVER_ERROR,
            detail=f"获取变更历史失败: {str(e)}"
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
            .select('id')
            .eq('id', department_id)
            .single()
        )

        if not dept_check.data:
            raise HTTPException(
                status_code=StatusCode.NOT_FOUND,
                detail=f"科室不存在: {department_id}"
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
    except Exception as e:
        raise HTTPException(
            status_code=StatusCode.INTERNAL_SERVER_ERROR,
            detail=f"获取适用规则失败: {str(e)}"
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
        # 构建查询
        query = sb.table('qc_rules').select('*', count='exact')

        # 只查询科室规则
        query = query.eq('scope', RuleScope.DEPARTMENT.value)

        # 按科室筛选
        if department_id:
            query = query.eq('department_id', department_id)

        # 按状态筛选
        if status_filter:
            query = query.eq('status', status_filter)

        # 按覆盖行为筛选
        if override_action:
            query = query.eq('override_action', override_action)

        # 关键词搜索
        if keyword:
            if hasattr(query, 'or_'):
                query = query.or_(
                    f"name.ilike.%{keyword}%,"
                    f"description.ilike.%{keyword}%,"
                    f"rule_code.ilike.%{keyword}%"
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
    except Exception as e:
        raise HTTPException(
            status_code=StatusCode.INTERNAL_SERVER_ERROR,
            detail=f"获取科室规则列表失败: {str(e)}"
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

        return success_response(
            data=result.data,
            message="获取科室规则详情成功",
            trace_id=get_trace_id(request)
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=StatusCode.INTERNAL_SERVER_ERROR,
            detail=f"获取科室规则详情失败: {str(e)}"
        )

