"""RabbitMQ 整批任务到既有 LX0609 执行链的窄服务入口。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from app.services.luxian_0609 import LUXIAN_0609_RULE_SET_KEY
from app.services.qc_diagnostics.support_store import capture_for_job, finalize
from app.services.sichuan_qc_service import SichuanQCService
from app.services.sichuan_workspace_batch_worker import (
    run_sichuan_workspace_batch_job,
)

from .contracts import BatchDispatchEnvelope, qc_dispatch_mode_from_filters


_UNSUPPORTED_ERROR = "任务不属于 RabbitMQ LX0609 叶任务执行范围"


async def run_batch_dispatch_job(
    envelope: BatchDispatchEnvelope,
    *,
    workspace: Any,
    dispatch_repository: Any,
    qc_service_provider: Callable[[], Awaitable[SichuanQCService]],
    external_cancellation_check: Callable[[], bool] | None = None,
) -> None:
    """校验持久任务身份后调用既有批执行函数。

    0916、自定义任务和父任务在这里失败关闭，绝不误走 0609 医学判定。
    """

    job = workspace.get_batch_job_for_processing(job_id=envelope.job_id)
    if not job:
        return
    filters = job.get("filters") if isinstance(job.get("filters"), dict) else {}
    try:
        dispatch_mode = qc_dispatch_mode_from_filters(filters)
    except ValueError:
        dispatch_mode = "invalid"
    supported = (
        str(job.get("job_kind") or "").strip().lower() != "parent"
        and filters.get("rule_set_key") == LUXIAN_0609_RULE_SET_KEY
        and dispatch_mode == "rabbitmq"
    )
    if not supported:
        workspace.fail_batch_job(
            job_id=envelope.job_id,
            error_message=_UNSUPPORTED_ERROR,
            queued_only=True,
            expected_queued_filters_json=job.get("_claim_filters_json"),
        )
        if not dispatch_repository.record_terminal_failure(
            envelope.job_id,
            envelope.generation,
            error_code="worker_failed",
        ):
            raise RuntimeError("unsupported MQ task could not be made terminal")
        return

    capture = capture_for_job(workspace, envelope.job_id)
    try:
        await run_sichuan_workspace_batch_job(
            envelope.job_id,
            workspace=workspace,
            qc_service_provider=qc_service_provider,
            diagnostic_capture=capture,
            record_concurrency_limit=4,
            external_cancellation_check=external_cancellation_check,
            expected_dispatch_generation=envelope.generation,
        )
    finally:
        if capture is not None:
            finalize(envelope.job_id)
