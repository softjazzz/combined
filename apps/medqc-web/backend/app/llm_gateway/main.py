"""`uvicorn app.llm_gateway.main:create_app --factory` 独立入口。"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import secrets
import time
from typing import Any, AsyncIterator, Callable

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import httpx

from app.services.llm_dispatch.contracts import (
    GATEWAY_COMPLETIONS_PATH,
    GATEWAY_RESOURCES_PATH,
    GatewayCompletionRequest,
    GatewayErrorCode,
    GatewayTiming,
)

from .admission import (
    AdmissionDeadlineError,
    AdmissionError,
    AdmissionLease,
    AdmissionManager,
    GatewayShuttingDownError,
)
from .config import GatewaySettings, ProfileConfig
from .case_cache import CasePrefixCache
from .lifecycle import (
    LifecycleClosedError,
    RESTART_INFLIGHT_POLICY,
    RequestLifecycle,
    SingleInstanceSentinel,
)
from .providers import (
    HttpxProviderSender,
    ProviderError,
    ProviderSender,
    ProviderTimeoutError,
    ProviderTransportError,
    prepare_provider_payload,
)
from app.services.llm_token_budget import BudgetError, guard_payload, strict_enabled


class GatewayAPIError(RuntimeError):
    def __init__(self, code: str, *, status_code: int, retryable: bool) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code
        self.retryable = retryable


class ProviderDispatchState:
    """区分“已创建 task”与“sender 已开始执行”。"""

    def __init__(self) -> None:
        self.started = False


class GatewayRuntime:
    def __init__(
        self,
        settings: GatewaySettings,
        sender: ProviderSender,
        *,
        provider_start_gate: asyncio.Event | None = None,
        deadline_clock: Callable[[], float] | None = None,
    ) -> None:
        self.settings = settings
        self.sender = sender
        self.admission = AdmissionManager(settings.resources.values(),
            continuation_resources={profile.resource_id for profile in settings.profiles.values()
                if profile.provider_code == "strata" and settings.strata_case_sequential},
            continuation=settings.continuation)
        self.lifecycle = RequestLifecycle()
        self.ready = True
        self.case_cache = CasePrefixCache(settings)
        # 仅用于确定性验证 task-created/sender-started 窗口；生产为 None。
        self._provider_start_gate = provider_start_gate
        self._deadline_clock = deadline_clock

    async def complete(self, completion: GatewayCompletionRequest) -> dict[str, Any]:
        if completion.case_prefix is None:
            return await self._complete_uncached(completion)
        profile = self.settings.profiles.get(completion.profile)
        if profile is None:
            raise GatewayAPIError(GatewayErrorCode.INVALID_PROFILE.value, status_code=400, retryable=False)
        # 先校验完整原始 payload，缓存元数据不能放宽 Provider 白名单。
        prepare_provider_payload(profile, completion.payload)
        loop = asyncio.get_running_loop()
        deadline = loop.time() + min(float(completion.timeout_seconds), _seconds_until(completion.deadline_at))

        async def invoke(payload):
            remaining = min(deadline - loop.time(), _seconds_until(completion.deadline_at))
            if remaining <= 0:
                raise AdmissionDeadlineError()
            request = completion.model_copy(update={"payload": payload, "case_prefix": None,
                                                     "timeout_seconds": remaining})
            return await self._complete_uncached(request, internal_prefix=True)

        return await self.case_cache.run(completion, profile, invoke, deadline=deadline)

    async def _complete_uncached(self, completion: GatewayCompletionRequest, *, internal_prefix=False) -> dict[str, Any]:
        profile = self.settings.profiles.get(completion.profile)
        if profile is None:
            raise GatewayAPIError(GatewayErrorCode.INVALID_PROFILE.value, status_code=400, retryable=False)
        payload = prepare_provider_payload(profile, completion.payload, allow_strata_prefix=internal_prefix)
        try:
            guard_payload(profile.provider_code, profile.name, payload, profile.context_budget,
                          enabled=strict_enabled() or completion.context_budget_required, phase="gateway_before_queue", attribution={"request_id": str(completion.request_id)})
        except BudgetError as error:
            raise GatewayAPIError(error.code, status_code=400, retryable=False) from None
        try:
            return await self._complete_prepared(completion, profile, payload)
        except (AdmissionError, ProviderError, GatewayAPIError) as error:
            if completion.observe_request:
                error.request_observation = self._request_receipt(completion, payload)
            raise

    @staticmethod
    def _request_receipt(completion, payload):
        try:
            from app.services.llm_request_observation import GatewayRequestObservation, request_parameters
            return GatewayRequestObservation(
                request_id=completion.request_id, parameters=request_parameters(payload),
            ).model_dump(mode="json")
        except Exception:
            # 观测失败不能改变原有响应、错误码或重试。
            return None

    async def _complete_prepared(self, completion, profile, payload):
        loop = asyncio.get_running_loop()
        absolute_remaining = _seconds_until(completion.deadline_at)
        initial_remaining = min(float(completion.timeout_seconds), absolute_remaining)
        if initial_remaining <= 0:
            raise AdmissionDeadlineError()
        monotonic_deadline = loop.time() + initial_remaining
        lease = await self.admission.acquire(
            profile.resource_id,
            monotonic_deadline=monotonic_deadline,
            # 旧客户端无匿名病例键时共享保守通道，不能靠省略身份突破串行。
            case_key=(completion.case_key or "0" * 64)
            if profile.provider_code == "strata" and self.settings.strata_case_sequential else None,
            package_key=completion.package_key if profile.provider_code == "strata" else None,
        )

        task: asyncio.Task[tuple[dict[str, Any], float]] | None = None
        dispatch_state = ProviderDispatchState()
        try:
            remaining = min(
                monotonic_deadline - loop.time(),
                _seconds_until(completion.deadline_at),
            )
            if remaining <= 0:
                raise AdmissionDeadlineError()
            task = self.lifecycle.create_provider_task(
                self._send_with_owned_lease(
                    lease=lease,
                    profile=profile,
                    payload=payload,
                    monotonic_deadline=monotonic_deadline,
                    dispatch_state=dispatch_state,
                    context_budget_required=completion.context_budget_required,
                )
            )
        except (AdmissionDeadlineError, LifecycleClosedError):
            await lease.release()
            if task is None and not self.lifecycle.accepting:
                raise GatewayShuttingDownError() from None
            raise
        except BaseException:
            await lease.release()
            raise

        # 调用方断开只取消等待；Provider task 继续持有 slot 至实际结束/超时。
        try:
            response, http_seconds = await asyncio.shield(task)
        except asyncio.CancelledError:
            if not dispatch_state.started:
                # task 只是被创建/排程，sender 尚未运行，取消后永不发送。
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                await lease.release()
            raise
        result = dict(response)
        # 模型返回的同名字段不具有网关控制面权限。
        result.pop("_gateway_request_observation", None)
        result.pop("_gateway_request_observation_invalid", None)
        if completion.observe_request:
            receipt = self._request_receipt(completion, payload)
            if receipt is not None:
                result["_gateway_request_observation"] = receipt
        # Provider 无权伪造 Gateway 成本边车。
        result.pop("_strata_cache", None)
        result.pop("_strata_cache_expected", None)
        result.pop("_strata_cache_invalid", None)
        result["_gateway_timing"] = GatewayTiming(
            queue_seconds=lease.queue_seconds,
            http_seconds=http_seconds,
        ).model_dump()
        return result

    async def _send_with_owned_lease(
        self,
        *,
        lease: AdmissionLease,
        profile: ProfileConfig,
        payload: dict[str, Any],
        monotonic_deadline: float,
        dispatch_state: ProviderDispatchState,
        context_budget_required: bool = False,
    ) -> tuple[dict[str, Any], float]:
        started = time.monotonic()
        try:
            if self._provider_start_gate is not None:
                await self._provider_start_gate.wait()
            timeout_seconds = monotonic_deadline - self._deadline_now()
            if timeout_seconds <= 0:
                # 准入后等待调度也属于端到端预算；此时尚未进入 sender。
                raise AdmissionDeadlineError()

            async def invoke_sender() -> dict[str, Any]:
                latest_remaining = monotonic_deadline - self._deadline_now()
                if latest_remaining <= 0:
                    raise AdmissionDeadlineError()
                # 排队期间若payload发生变化，最终发送前重新计量；不能复用旧计数。
                try:
                    guard_payload(profile.provider_code, profile.name, payload, profile.context_budget,
                                  enabled=strict_enabled() or context_budget_required, phase="gateway_final_send")
                except BudgetError as error:
                    raise GatewayAPIError(error.code, status_code=400, retryable=False) from None
                # 这段在 wait_for 创建的 task 真正被调度后才执行。
                # 置位后直接 await coroutine，中间无任务切换点，sender 函数体立即进入。
                dispatch_state.started = True
                return await self.sender.send(
                    profile,
                    payload,
                    timeout_seconds=latest_remaining,
                )

            try:
                result = await asyncio.wait_for(
                    invoke_sender(),
                    timeout=timeout_seconds,
                )
            except AdmissionDeadlineError:
                # sender 尚未进入，不得标记远程未知在途。
                raise
            except asyncio.TimeoutError:
                await self._quarantine_unknown_remote(profile.resource_id)
                raise ProviderTimeoutError() from None
            except (ProviderTimeoutError, ProviderTransportError):
                await self._quarantine_unknown_remote(profile.resource_id)
                raise
            except (ProviderError, GatewayAPIError):
                raise
            except Exception:
                # 注入 sender 的未知异常也不可回显文本。
                await self._quarantine_unknown_remote(profile.resource_id)
                raise ProviderTransportError() from None
            return result, max(0.0, time.monotonic() - started)
        finally:
            await lease.release()

    def _deadline_now(self) -> float:
        if self._deadline_clock is not None:
            return self._deadline_clock()
        return asyncio.get_running_loop().time()

    async def _quarantine_unknown_remote(self, resource_id: str) -> None:
        # HTTP 已发出后的超时/断线只证明本地观测结束，不证明 GPU 停止。
        self.lifecycle.mark_remote_inflight_unknown()
        await self.admission.quarantine(resource_id)

    async def resource_counts(self) -> list[dict[str, int | bool | str]]:
        return await self.admission.snapshots()

    async def set_resource_capacity(self, resource_id: str, capacity: int) -> None:
        """内部容量控制入口；本轮仅Mock调用，不探测或猜测Replica接口。"""
        await self.admission.set_capacity(resource_id, capacity)

    async def shutdown(self) -> bool:
        self.ready = False
        self.lifecycle.stop_accepting()
        await self.case_cache.close()
        await self.admission.close()
        drained = await self.lifecycle.drain(self.settings.shutdown_grace_seconds)
        snapshots = await self.admission.snapshots()
        no_slots = all(int(item["inflight"]) == 0 and int(item["queued"]) == 0 for item in snapshots)
        return drained and no_slots and not self.lifecycle.remote_inflight_unknown


def create_app(
    settings: GatewaySettings | None = None,
    *,
    sender: ProviderSender | None = None,
    http_transport: httpx.AsyncBaseTransport | None = None,
    enforce_single_instance: bool = True,
) -> FastAPI:
    """创建不依赖主 app/DB 的独立 Gateway。"""

    resolved = settings or GatewaySettings.from_env()
    provider_sender = sender or HttpxProviderSender(transport=http_transport)
    runtime = GatewayRuntime(resolved, provider_sender)
    sentinel = SingleInstanceSentinel(resolved.state_dir) if enforce_single_instance else None

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        if sentinel is not None:
            sentinel.acquire()
        clean = False
        try:
            runtime.ready = False
            # 新启动默认保守隔离；异常退出则 sentinel 直接阻止自动重启。
            if resolved.startup_isolation_seconds:
                await asyncio.sleep(resolved.startup_isolation_seconds)
            runtime.ready = True
            yield
            clean = await runtime.shutdown()
        finally:
            runtime.ready = False
            if runtime.lifecycle.accepting:
                clean = await runtime.shutdown()
            if sentinel is not None and clean:
                sentinel.release_after_clean_drain()

    app = FastAPI(
        title="MedQC LLM Gateway",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.gateway_runtime = runtime
    app.state.gateway_sentinel = sentinel

    @app.middleware("http")
    async def authenticate_before_body_validation(request: Request, call_next: Any) -> Any:
        if request.url.path in {GATEWAY_COMPLETIONS_PATH, GATEWAY_RESOURCES_PATH}:
            try:
                _authenticate(request, resolved.token)
            except GatewayAPIError as error:
                return _error_response(
                    error.code,
                    status_code=error.status_code,
                    retryable=error.retryable,
                )
        return await call_next(request)

    @app.exception_handler(RequestValidationError)
    async def safe_validation_error(_request: Request, _error: RequestValidationError) -> JSONResponse:
        # Pydantic 默认 detail 可包含 input/ctx，这里绝不回显患者原文。
        return _error_response(GatewayErrorCode.INVALID_REQUEST.value, status_code=422, retryable=False)

    @app.exception_handler(GatewayAPIError)
    async def gateway_api_error(_request: Request, error: GatewayAPIError) -> JSONResponse:
        return _error_response(error.code, status_code=error.status_code, retryable=error.retryable, cache_trace=getattr(error, "cache_trace", None), request_observation=getattr(error, "request_observation", None))

    @app.exception_handler(AdmissionError)
    async def admission_error(_request: Request, error: AdmissionError) -> JSONResponse:
        return _error_response(error.code, status_code=error.status_code, retryable=error.retryable, cache_trace=getattr(error, "cache_trace", None), request_observation=getattr(error, "request_observation", None))

    @app.exception_handler(ProviderError)
    async def provider_error(_request: Request, error: ProviderError) -> JSONResponse:
        return _error_response(error.code, status_code=error.status_code, retryable=error.retryable, cache_trace=getattr(error, "cache_trace", None), request_observation=getattr(error, "request_observation", None))

    @app.exception_handler(Exception)
    async def safe_unexpected_error(_request: Request, _error: Exception) -> JSONResponse:
        return _error_response(GatewayErrorCode.INTERNAL_ERROR.value, status_code=500, retryable=False)

    @app.get("/health")
    async def health() -> JSONResponse:
        if not runtime.ready:
            return JSONResponse(status_code=503, content={"status": "unavailable"})
        if runtime.lifecycle.remote_inflight_unknown:
            return JSONResponse(status_code=503, content={"status": "degraded"})
        if any(item["effective_max_inflight"] < item["max_inflight"] for item in await runtime.resource_counts()):
            return JSONResponse(status_code=503, content={"status": "degraded"})
        return JSONResponse(content={"status": "ok"})

    @app.get(GATEWAY_RESOURCES_PATH)
    async def resources() -> JSONResponse:
        return JSONResponse(content={"resources": await runtime.resource_counts()})

    @app.post(GATEWAY_COMPLETIONS_PATH)
    async def completions(completion: GatewayCompletionRequest, request: Request) -> dict[str, Any]:
        return await _complete_until_disconnect(runtime, completion, request)

    return app


def _authenticate(request: Request, expected_token: str) -> None:
    authorization = request.headers.get("Authorization", "")
    prefix = "Bearer "
    if not authorization.startswith(prefix) or not secrets.compare_digest(
        authorization[len(prefix) :], expected_token
    ):
        raise GatewayAPIError(GatewayErrorCode.INVALID_AUTH.value, status_code=401, retryable=False)


def _seconds_until(deadline_at: datetime) -> float:
    return (deadline_at.astimezone(timezone.utc) - datetime.now(timezone.utc)).total_seconds()


async def _complete_until_disconnect(
    runtime: GatewayRuntime,
    completion: GatewayCompletionRequest,
    request: Request,
) -> dict[str, Any]:
    completion_task = asyncio.create_task(runtime.complete(completion))
    disconnect_task = asyncio.create_task(_wait_for_disconnect(request))
    try:
        done, _pending = await asyncio.wait(
            {completion_task, disconnect_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if completion_task in done:
            return await completion_task

        # 排队期取消会撤销 waiter；已发出时 runtime 的 shield 保留底层 task/slot。
        completion_task.cancel()
        await asyncio.gather(completion_task, return_exceptions=True)
        raise asyncio.CancelledError()
    finally:
        # 服务停机/上层直接 cancel 也必须回收两个子 task，不依赖 http.disconnect。
        disconnect_task.cancel()
        if not completion_task.done():
            completion_task.cancel()
        await asyncio.gather(disconnect_task, completion_task, return_exceptions=True)


async def _wait_for_disconnect(request: Request) -> None:
    while True:
        message = await request.receive()
        if message.get("type") == "http.disconnect":
            return


def _error_response(code: str, *, status_code: int, retryable: bool, cache_trace=None, request_observation=None) -> JSONResponse:
    detail = {"code": code, "retryable": retryable}
    if request_observation is not None:
        detail["request_observation"] = request_observation
    if cache_trace is not None:
        detail["cache_trace"] = cache_trace.model_dump(mode="json")
    return JSONResponse(
        status_code=status_code,
        content={"detail": detail},
    )


__all__ = [
    "GatewayAPIError",
    "GatewayRuntime",
    "RESTART_INFLIGHT_POLICY",
    "create_app",
]
