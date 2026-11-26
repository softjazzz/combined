"""LX0609 独立准生产评估 API。

该路由只按调用方提供的三坐标读取已持久化病例包，不创建任务，也不经过四川
质控服务。开关关闭时在病例包读取、模型客户端和准生产 runner 前直接返回 404。
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..core.roles import effective_roles
from ..core.security import optional_security, resolve_current_user_from_token
from ..core.response import get_trace_id
from ..core.settings import get_settings
from ..services.llm_observability import llm_observation_context
from ..services.luxian_0609.preproduction_runner import (
    run_luxian_0609_preproduction,
)
from ..services.luxian_0609.preproduction_bundle_reader import (
    read_luxian_0609_preproduction_bundle as load_running_final_bundle,
)


_SAFE_CONTRACT_ERROR = "准生产评估请求不符合安全契约"


class Luxian0609PreproductionRequest(BaseModel):
    """独立准生产入口的唯一请求契约。"""

    model_config = ConfigDict(extra="forbid")

    scene: Literal["running", "final"]
    institute_id: str = Field(min_length=1, max_length=256)
    patient_id: str = Field(min_length=1, max_length=256)
    visit_id: str = Field(min_length=1, max_length=256)
    selected_customer_rule_ids: list[str]
    evaluation_as_of_date: str


router = APIRouter(
    prefix="/api/v1/qc/luxian-0609/preproduction",
    tags=["luxian-0609-preproduction"],
)


def _build_llm_client() -> Any:
    """仅在开关开启并通过请求校验后构造裁决模型客户端。"""

    from ..services.llm_config_loader import build_adjudicator_runtime_config
    from ..services.qc_llm_client import SichuanQCLLMClient

    return SichuanQCLLMClient(build_adjudicator_runtime_config())


def _settings_dependency() -> Any:
    return get_settings()


_ALLOWED_PREPRODUCTION_ROLES = frozenset({"admin", "super_admin", "qc_manager"})
_GLOBAL_PREPRODUCTION_ROLES = frozenset({"admin", "super_admin", "sync_admin"})


def _user_effective_roles(user: dict[str, Any]) -> set[str]:
    roles = set(effective_roles(user.get("roles")))
    single = str(user.get("role") or "").strip()
    if single:
        roles.update(effective_roles([single]))
    return roles


async def _require_enabled_user(
    request: Request,
    settings: Any = Depends(_settings_dependency),
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_security),
) -> tuple[Any, dict[str, Any]]:
    """先短路关闭开关，开启后才解析用户并校验角色。"""

    if not settings.LUXIAN_0609_PREPRODUCTION_API_ENABLED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = resolve_current_user_from_token(credentials.credentials)
    if not (_user_effective_roles(user) & _ALLOWED_PREPRODUCTION_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足，仅管理员或质控管理员可执行准生产评估",
        )
    request.state.current_user = user
    return settings, user


def _safe_contract_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=_SAFE_CONTRACT_ERROR,
    )


@router.post("/evaluate")
async def evaluate_luxian_0609_preproduction(
    request: Request,
    enabled_context: tuple[Any, dict[str, Any]] = Depends(_require_enabled_user),
) -> dict[str, Any]:
    """运行一次无落库的 LX0609 准生产评估。"""

    settings, current_user = enabled_context

    # 在路由内解析并收敛错误，避免全局校验处理器记录含坐标/正文的 input。
    try:
        raw_payload = await request.json()
        payload = Luxian0609PreproductionRequest.model_validate(raw_payload)
    except (TypeError, ValueError, ValidationError):
        raise _safe_contract_error() from None

    if not (_user_effective_roles(current_user) & _GLOBAL_PREPRODUCTION_ROLES):
        user_institute_id = str(current_user.get("institute_id") or "").strip()
        if not user_institute_id or user_institute_id != payload.institute_id.strip():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权评估其他院区的准生产病例包",
            )

    try:
        bundle = load_running_final_bundle(
            scene=payload.scene,
            institute_id=payload.institute_id,
            patient_id=payload.patient_id,
            visit_id=payload.visit_id,
            schema="public",
        )
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="准生产病例包不存在",
        ) from None
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="准生产病例包暂不可用",
        ) from None

    try:
        client = _build_llm_client()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="准生产评估服务暂不可用",
        ) from None
    try:
        with llm_observation_context(
            business_scene="luxian_0609_preproduction",
            root_job_id=get_trace_id(request),
            record_identity=(
                payload.institute_id,
                payload.patient_id,
                payload.visit_id,
            ),
            rule_set_key="luxian_0609_qc_v1",
            executor_key="preproduction_adjudicator",
        ):
            return await run_luxian_0609_preproduction(
                bundle=bundle,
                selected_customer_rule_ids=payload.selected_customer_rule_ids,
                evaluation_as_of_date=payload.evaluation_as_of_date,
                llm_client=client,
                base_settings=settings,
                model_name=str(client.model or ""),
            )
    except (TypeError, ValueError):
        raise _safe_contract_error() from None
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="准生产评估服务暂不可用",
        ) from None
