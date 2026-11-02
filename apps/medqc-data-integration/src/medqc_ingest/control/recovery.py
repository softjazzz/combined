"""恢复前核对旧执行和提交状态；不凭租约自动重发源查询。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from medqc_ingest.control.models import ControlError


class RecoveryRepository(Protocol):
    def list_recovery(self) -> list[dict[str, Any]]: ...
    def reconcile(
        self, job_id: str, actor_id: str, decision: str, proof: dict[str, Any]
    ) -> dict[str, Any]: ...


def validate_recovery_proof(proof: dict[str, Any]) -> None:
    if set(proof) != {"executor_stopped", "target_locks_clear", "batches_checked", "commit_state"}:
        raise ControlError("invalid_recovery_proof", "recovery_proof_fields")
    if any(
        proof[key] is not True
        for key in ("executor_stopped", "target_locks_clear", "batches_checked")
    ):
        raise ControlError("recovery_not_verified", "recovery_execution_unknown", 409)
    if proof["commit_state"] not in {"not_committed", "committed_verified", "idempotent_retry"}:
        raise ControlError("recovery_not_verified", "recovery_commit_unknown", 409)


class RecoveryService:
    def __init__(
        self, repository: RecoveryRepository, checker: Callable[[str], dict[str, Any]] | None = None
    ) -> None:
        self.repository = repository
        self.checker = checker

    def pending(self) -> list[dict[str, Any]]:
        return self.repository.list_recovery()

    def reconcile(self, job_id: str, actor_id: str, decision: str) -> dict[str, Any]:
        if decision not in {"retry", "cancel", "fail"}:
            raise ControlError("invalid_recovery_decision", "recovery_decision")
        if self.checker is None:
            raise ControlError("recovery_not_verified", "recovery_checker_required", 409)
        proof = self.checker(job_id)
        validate_recovery_proof(proof)
        return self.repository.reconcile(job_id, actor_id, decision, proof)
