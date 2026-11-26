"""质控运行设置：仅系统管理账号，配置只影响新任务，不操作已有任务。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from ..core.audit import audit_event
from ..core.security import require_global_system_admin
from ..core.settings import get_settings
from ..services.qc_dispatch.control import (
    DispatchControlConflict, DispatchControlError, load_control, save_control,
)
from ..services.qc_dispatch.readiness import check_readiness, readiness_snapshot
from ..storage.memory import DEFAULT_DEMO_USER_EMAILS

router = APIRouter(prefix='/api/v1/system/qc-runtime', tags=['QC Runtime Settings'])


async def require_runtime_manager(user: dict = Depends(require_global_system_admin)) -> dict:
    # 演示账号不能修改全局调度，即使历史角色数组包含admin。
    is_demo = user.get('is_demo_account') is True or str(user.get('email') or '').strip().lower() in DEFAULT_DEMO_USER_EMAILS
    if is_demo and not set(user.get('roles') or []).intersection({'sync_admin', 'super_admin'}):
        raise HTTPException(403, '演示账号不能管理质控运行配置')
    return user


class RuntimeUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    rabbitmq_enabled: StrictBool
    expected_revision: int = Field(ge=0, strict=True)


def _view(settings, readiness: dict | None = None) -> dict:
    current, source = load_control(settings)
    return {
        'rabbitmq_enabled': current.rabbitmq_enabled,
        'effective_mode': 'rabbitmq' if current.rabbitmq_enabled else 'legacy',
        'source': source, 'revision': current.revision, 'updated_at': current.updated_at,
        'readiness': readiness if readiness is not None else readiness_snapshot(settings),
    }


@router.get('')
def get_runtime_settings(user: dict = Depends(require_runtime_manager)):
    try:
        return _view(get_settings())
    except DispatchControlError as exc:
        raise HTTPException(503, str(exc)) from None


@router.post('/check')
async def check_runtime_settings(user: dict = Depends(require_runtime_manager)):
    try:
        cfg = get_settings()
        return _view(cfg, await check_readiness(cfg))
    except DispatchControlError as exc:
        raise HTTPException(503, str(exc)) from None


@router.put('')
async def update_runtime_settings(payload: RuntimeUpdate, request: Request,
                                  user: dict = Depends(require_runtime_manager)):
    cfg = get_settings()
    try:
        readiness = await check_readiness(cfg) if payload.rabbitmq_enabled else None
        if readiness is not None and not readiness['ready']:
            raise HTTPException(409, detail={'message': '配套服务未就绪，未启用RabbitMQ', 'readiness': readiness})
        save_control(enabled=payload.rabbitmq_enabled, expected_revision=payload.expected_revision,
                     actor=str(user.get('id') or user.get('user_id') or 'system-admin'), settings=cfg)
        audit_event(request, action='qc_runtime.update', resource='qc-dispatch', outcome='success',
                    details={'rabbitmq_enabled': payload.rabbitmq_enabled}, current_user=user)
        return _view(cfg, readiness)
    except DispatchControlConflict as exc:
        raise HTTPException(409, str(exc)) from None
    except DispatchControlError as exc:
        raise HTTPException(503, str(exc)) from None
