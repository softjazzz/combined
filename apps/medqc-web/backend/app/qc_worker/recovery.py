"""独立 Worker 的持久恢复 owner。"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from enum import Enum
import logging
from typing import Any
from fastapi import HTTPException

from app.services.luxian_0609 import LUXIAN_0609_RULE_SET_KEY
from app.services.qc_dispatch.contracts import qc_dispatch_mode_from_filters
from app.services.qc_execution_errors import task_error_blocks_automatic_retry


logger = logging.getLogger(__name__)


class RecoveryOutcome(str, Enum):
    DELIVERY_ENSURED = "delivery_ensured"
    RETRY_SCHEDULED = "retry_scheduled"
    MANUAL_SCOPE_REQUIRED = "manual_scope_required"
    TERMINAL_FAILURE = "terminal_failure"
    SKIPPED = "skipped"


class WorkerRecovery:
    """恢复 queued 漏投与租约过期 attempt，不清空已有成功结果。"""

    def __init__(
        self,
        *,
        repository: Any,
        workspace: Any,
        retry_delay_seconds: float = 5.0,
        stale_after_seconds: float = 180.0,
        scan_interval_seconds: float = 30.0,
    ) -> None:
        if min(retry_delay_seconds, stale_after_seconds, scan_interval_seconds) < 0:
            raise ValueError("recovery timing must not be negative")
        self._repository = repository
        self._workspace = workspace
        self._retry_delay_seconds = float(retry_delay_seconds)
        self._stale_after_seconds = float(stale_after_seconds)
        self._scan_interval_seconds = float(scan_interval_seconds)

    def recover_startup_queued(self) -> dict[str, RecoveryOutcome]:
        outcomes: dict[str, RecoveryOutcome] = {}
        for raw_job_id in self._workspace.list_queued_luxian_0609_batch_job_ids(
            dispatch_mode="rabbitmq"
        ):
            job_id = str(raw_job_id or "").strip()
            if not job_id:
                continue
            outcomes[job_id] = self.ensure_queued_delivery(job_id)
        return outcomes

    def recover_failed_candidates(self) -> dict[str, RecoveryOutcome]:
        """继续 stale fencing 已提交、但恢复安排尚未提交的崩溃窗口。"""

        outcomes: dict[str, RecoveryOutcome] = {}
        for dispatch in self._repository.list_recovery_candidates(limit=100):
            job_id = str(getattr(dispatch, "job_id", "") or "").strip()
            if not job_id:
                continue
            outcomes[job_id] = self.recover_failed_job(job_id)
        return outcomes

    def ensure_queued_delivery(self, job_id: str) -> RecoveryOutcome:
        dispatch = self._repository.get_dispatch(job_id)
        if (
            dispatch is None
            or str(getattr(dispatch, "mode", "")) != "rabbitmq"
            or self._repository.get_job_status(job_id) != "queued"
        ):
            return RecoveryOutcome.SKIPPED
        generation = int(getattr(dispatch, "generation", 0) or 0)
        if generation <= 0:
            return RecoveryOutcome.SKIPPED
        # 只有持久恢复 owner 可重新开放已 confirmed 但任务仍 queued 的同一
        # message_id。先登记当前 generation，再由 ensure_due_delivery 把
        # confirmed Outbox 置回 pending；普通 consumer 不得现场登记后 ACK。
        if not self._repository.register_recovery(
            job_id,
            generation,
            recovery_kind="delivery",
            reason_code="startup_queued_reconcile",
            scope=None,
        ):
            raise RuntimeError("queued delivery recovery lost its generation CAS")
        self._repository.ensure_due_delivery(job_id, generation, target="main")
        return RecoveryOutcome.DELIVERY_ENSURED

    def recover_stale_once(self, *, now: datetime | None = None) -> dict[str, RecoveryOutcome]:
        current = now or datetime.utcnow()
        stale_before = current - timedelta(seconds=self._stale_after_seconds)
        # workspace owner 以 status+filters+updated_at CAS fencing；dispatch_mode 参数
        # 保证独立 Worker 不会失败 legacy Web 任务。
        failed_job_ids = self._workspace.fail_stale_luxian_0609_running_jobs(
            stale_before=stale_before,
            dispatch_mode="rabbitmq",
        )
        return {
            job_id: self.recover_failed_job(job_id)
            for job_id in failed_job_ids
        }

    def recover_failed_job(self, job_id: str) -> RecoveryOutcome:
        dispatch = self._repository.get_dispatch(job_id)
        if (
            dispatch is None
            or str(getattr(dispatch, "mode", "")) != "rabbitmq"
            or self._repository.get_job_status(job_id) != "failed"
        ):
            return RecoveryOutcome.SKIPPED
        generation = int(getattr(dispatch, "generation", 0) or 0)
        if generation <= 0:
            return RecoveryOutcome.SKIPPED
        if self._has_retry_successor(job_id, generation):
            # 独立新身份与其Outbox已提交；旧attempt只保留追溯，不重复扫描/分类。
            return RecoveryOutcome.RETRY_SCHEDULED
        if str(getattr(dispatch, "recovery_kind", "") or "") == (
            "manual_scope_required"
        ):
            return RecoveryOutcome.MANUAL_SCOPE_REQUIRED

        job = self._workspace.get_batch_job_for_processing(job_id=job_id)
        if not isinstance(job, dict):
            return RecoveryOutcome.SKIPPED
        filters = job.get("filters") if isinstance(job.get("filters"), dict) else {}
        try:
            supported_mq_job = (
                str(job.get("job_kind") or "").strip().lower() != "parent"
                and filters.get("rule_set_key") == LUXIAN_0609_RULE_SET_KEY
                and qc_dispatch_mode_from_filters(filters) == "rabbitmq"
            )
        except ValueError:
            supported_mq_job = False
        if not supported_mq_job:
            if not self._repository.record_terminal_failure(
                job_id,
                generation,
                error_code="worker_failed",
            ):
                if self._has_retry_successor(job_id, generation):
                    return RecoveryOutcome.RETRY_SCHEDULED
                raise RuntimeError("unsupported recovery task was not made terminal")
            return RecoveryOutcome.TERMINAL_FAILURE
        if task_error_blocks_automatic_retry(job.get("summary")):
            # 正常终止的合同/配置/程序错误不是失联，不能登记为空产出恢复。
            if not self._repository.record_terminal_failure(job_id, generation, error_code="worker_failed"):
                if self._has_retry_successor(job_id, generation):
                    return RecoveryOutcome.RETRY_SCHEDULED
                raise RuntimeError("nonretryable task failure was not made terminal")
            return RecoveryOutcome.TERMINAL_FAILURE
        has_success = self._has_saved_success(job_id, job)
        has_failed_scope = self._has_explicit_failed_scope(job)

        if has_success and not has_failed_scope:
            if not self._repository.register_recovery(
                job_id,
                generation,
                recovery_kind="manual_scope_required",
                reason_code="saved_results_without_provable_scope",
                scope={"saved_result_count": self._saved_result_count(job_id, job)},
            ):
                if self._has_retry_successor(job_id, generation):
                    return RecoveryOutcome.RETRY_SCHEDULED
                raise RuntimeError("manual recovery state was not persisted")
            return RecoveryOutcome.MANUAL_SCOPE_REQUIRED

        failure_count = int(getattr(dispatch, "failure_count", 0) or 0)
        failure_budget = int(getattr(dispatch, "failure_budget", 0) or 0)
        if failure_budget <= 0 or failure_count >= failure_budget:
            if not self._repository.record_terminal_failure(
                job_id,
                generation,
                error_code="retry_budget_exhausted",
            ):
                if self._has_retry_successor(job_id, generation):
                    return RecoveryOutcome.RETRY_SCHEDULED
                raise RuntimeError("terminal recovery state was not persisted")
            return RecoveryOutcome.TERMINAL_FAILURE

        recovery_kind = "failed_scope" if has_failed_scope else "unstarted"
        reason_code = (
            "explicit_failed_scope"
            if has_failed_scope
            else "no_saved_results_after_stale_attempt"
        )
        if not self._repository.register_recovery(
            job_id,
            generation,
            recovery_kind=recovery_kind,
            reason_code=reason_code,
            scope={
                "saved_result_count": self._saved_result_count(job_id, job),
                "failed_item_count": len(job.get("failed_records") or []),
            },
        ):
            if self._has_retry_successor(job_id, generation):
                return RecoveryOutcome.RETRY_SCHEDULED
            raise RuntimeError("recovery registration lost its generation CAS")

        try:
            retried = self._workspace.retry_batch_job(
                job_id=job_id,
                created_by=str(job.get("created_by") or ""),
                automatic=True,
                expected_attempt_filters_json=job.get("_claim_filters_json"),
                retry_delay_seconds=self._retry_delay_seconds,
            )
        except HTTPException as exc:
            if self._has_retry_successor(job_id, generation):
                return RecoveryOutcome.RETRY_SCHEDULED
            if exc.status_code == 503:
                # 权限owner暂不可用，保留失败候选；后续扫描可重试，不能停整个消费者。
                return RecoveryOutcome.SKIPPED
            if exc.status_code == 403:
                if not self._repository.register_recovery(
                    job_id, generation, recovery_kind="manual_scope_required",
                    reason_code="retry_permission_revoked",
                ):
                    if self._has_retry_successor(job_id, generation):
                        return RecoveryOutcome.RETRY_SCHEDULED
                    raise RuntimeError("permission recovery state was not persisted") from None
                return RecoveryOutcome.MANUAL_SCOPE_REQUIRED
            raise
        except ValueError:
            # 暂停范围、失效lineage等受控合同拒绝只阻止本任务恢复，不终止owner。
            if self._has_retry_successor(job_id, generation):
                return RecoveryOutcome.RETRY_SCHEDULED
            if not self._repository.register_recovery(
                job_id, generation, recovery_kind="manual_scope_required",
                reason_code="retry_contract_rejected",
            ):
                if self._has_retry_successor(job_id, generation):
                    return RecoveryOutcome.RETRY_SCHEDULED
                raise RuntimeError("rejected retry recovery state was not persisted") from None
            return RecoveryOutcome.MANUAL_SCOPE_REQUIRED
        if retried and str(retried.get("status") or "") == "queued":
            return RecoveryOutcome.RETRY_SCHEDULED

        # 已保存成功项时绝不能把 retry 返回 None 解释为允许整批清空重排。
        if has_success:
            self._repository.register_recovery(
                job_id,
                generation,
                recovery_kind="manual_scope_required",
                reason_code="failed_scope_not_recoverable",
                scope={"saved_result_count": self._saved_result_count(job_id, job)},
            )
            return RecoveryOutcome.MANUAL_SCOPE_REQUIRED
        if not self._repository.record_terminal_failure(
            job_id,
            generation,
            error_code="worker_failed",
        ):
            if self._has_retry_successor(job_id, generation):
                return RecoveryOutcome.RETRY_SCHEDULED
            raise RuntimeError("failed recovery could not be made terminal")
        return RecoveryOutcome.TERMINAL_FAILURE

    def _has_retry_successor(self, job_id: str, generation: int) -> bool:
        """CAS竞争后仅认可已持久化的新调度身份，不吞掉真实存储失败。"""
        source = self._repository.get_dispatch(job_id)
        if (source is None or source.generation != generation
                or getattr(source, "recovery_reason_code", None) != "retry_successor_created"):
            return False
        try:
            scope = json.loads(source.recovery_scope_json or "{}")
            successor_id = scope.get("retry_job_id")
        except (ValueError, TypeError, AttributeError):
            return False
        if not isinstance(successor_id, str) or not successor_id or successor_id == job_id:
            return False
        successor = self._repository.get_dispatch(successor_id)
        return (successor is not None and getattr(successor, "job_id", None) == successor_id
                and successor.mode == "rabbitmq")

    async def run(self) -> None:
        await asyncio.to_thread(self.recover_startup_queued)
        await asyncio.to_thread(self.recover_failed_candidates)
        while True:
            await asyncio.sleep(self._scan_interval_seconds)
            outcomes = await asyncio.to_thread(self.recover_stale_once)
            outcomes.update(await asyncio.to_thread(self.recover_failed_candidates))
            if outcomes:
                logger.warning("QC Worker 已处理 %d 个租约过期任务", len(outcomes))

    def _has_saved_success(self, job_id: str, job: dict[str, Any]) -> bool:
        return self._saved_result_count(job_id, job) > 0

    def _saved_result_count(self, job_id: str, job: dict[str, Any]) -> int:
        item_count = len(job.get("items") or [])
        list_refs = getattr(self._workspace, "list_record_result_case_refs", None)
        if not callable(list_refs):
            return item_count
        refs = list_refs(job_id=job_id)
        return max(item_count, len(refs or ()))

    @staticmethod
    def _has_explicit_failed_scope(job: dict[str, Any]) -> bool:
        failures = list(job.get("failed_records") or [])
        if not failures:
            return False
        for failure in failures:
            if not isinstance(failure, dict):
                return False
            rule_id = str(failure.get("rule_id") or "").strip()
            raw_ref = failure.get("record_ref")
            if isinstance(raw_ref, dict):
                record_identity = all(
                    str(raw_ref.get(key) or "").strip()
                    for key in ("institute_id", "patient_id", "visit_id")
                )
            else:
                record_identity = any(
                    str(failure.get(key) or "").strip()
                    for key in ("record_ref", "record_key", "record_id", "visit_id")
                )
            if not rule_id or not record_identity:
                return False
        return True
