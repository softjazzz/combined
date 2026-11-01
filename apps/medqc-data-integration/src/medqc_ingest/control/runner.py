"""持久任务的顺序执行器；数据事务由既有抽取/发布服务负责。"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, Protocol

from medqc_ingest.control.models import ControlError, SourceLimited


class UnitExecutor(Protocol):
    def execute(self, job: dict[str, Any], unit: dict[str, Any]) -> dict[str, Any]: ...


class RunnerRepository(Protocol):
    def get_job(self, job_id: str) -> dict[str, Any] | None: ...
    def units(self, job_id: str) -> list[dict[str, Any]]: ...
    def start_unit(self, job_id: str, token: str, unit_id: str) -> bool: ...
    def finish_unit(
        self, job_id: str, token: str, unit_id: str, status: str, result: dict[str, Any]
    ) -> bool: ...
    def finish_job(
        self, job_id: str, token: str, status: str, error: dict[str, Any] | None = None
    ) -> bool: ...
    def mark_recovery(self, job_id: str, token: str, reason: str) -> bool: ...


class UnitFailure(ControlError):
    """只携带可进入操作元数据表的结果；提交不明必须恢复核对。"""

    def __init__(
        self,
        code: str,
        location: str,
        *,
        result: dict[str, Any] | None = None,
        recovery_required: bool = False,
    ) -> None:
        super().__init__(code, location)
        self.result = result or {}
        self.recovery_required = recovery_required


_RESULT_KEYS = frozenset(
    {
        "counts",
        "batch_id",
        "publish_batch_id",
        "checkpoint_state",
        "source_limited",
        "selected",
        "written",
        "schema_hash",
        "error_kind",
        "error_location",
        "code",
        "location",
        "sqlstate",
        "native",
    }
)
_CODE = re.compile(r"[A-Za-z0-9_.:/-]{1,128}")


def safe_result(result: Mapping[str, Any]) -> dict[str, Any]:
    """拒绝正文/键或异常原文进入控制库，不依赖日志脱敏补救。"""
    if set(result) - _RESULT_KEYS:
        raise ControlError("unsafe_result", "runner_result")
    for key, value in result.items():
        if key == "counts":
            if (
                not isinstance(value, dict)
                or set(value) - {"fetched", "inserted", "updated", "unchanged"}
                or any(type(v) is not int or v < 0 for v in value.values())
            ):
                raise ControlError("unsafe_result", "runner_counts")
        elif key in {"batch_id", "publish_batch_id", "selected", "written"}:
            if value is not None and (type(value) is not int or value < 0):
                raise ControlError("unsafe_result", "runner_numeric_result")
        elif key == "native":
            if value is not None and (type(value) is not int or abs(value) > 999999):
                raise ControlError("unsafe_result", "runner_native_result")
        elif key == "source_limited":
            if type(value) is not bool:
                raise ControlError("unsafe_result", "runner_limited_result")
        elif key == "checkpoint_state":
            if value not in {"held", "advanced", "n/a"}:
                raise ControlError("unsafe_result", "runner_checkpoint_result")
        elif key == "schema_hash":
            if not isinstance(value, str) or re.fullmatch(r"[a-f0-9]{64}", value) is None:
                raise ControlError("unsafe_result", "runner_schema_result")
        elif key == "sqlstate":
            if value is not None and (
                not isinstance(value, str) or re.fullmatch(r"[0-9A-Z]{5}", value) is None
            ):
                raise ControlError("unsafe_result", "runner_sqlstate_result")
        elif not isinstance(value, str) or _CODE.fullmatch(value) is None:
            raise ControlError("unsafe_result", "runner_error_result")
    return dict(result)


class JobRunner:
    def __init__(self, repository: RunnerRepository, executor: UnitExecutor) -> None:
        self.repository = repository
        self.executor = executor

    def _recovery(self, job_id: str, token: str, reason: str) -> dict[str, Any]:
        self.repository.mark_recovery(job_id, token, reason)
        return {"job_id": job_id, "status": "recovery_required", "code": reason}

    def run(self, claimed_job: dict[str, Any]) -> dict[str, Any]:
        job_id, token = str(claimed_job["job_id"]), str(claimed_job["lease_token"])
        limited = False
        for unit in sorted(self.repository.units(job_id), key=lambda value: int(value["sequence"])):
            if unit["status"] in {"succeeded", "source_limited"}:
                limited |= unit["status"] == "source_limited"
                continue
            current = self.repository.get_job(job_id)
            if current is None or current["status"] != "running":
                return {"job_id": job_id, "status": "recovery_required", "code": "lease_lost"}
            if current["cancel_requested"]:
                self.repository.finish_job(job_id, token, "cancelled")
                return {"job_id": job_id, "status": "cancelled"}
            if unit["status"] != "queued":
                return self._recovery(job_id, token, "unit_state_unknown")
            unit_id = str(unit["unit_id"])
            if not self.repository.start_unit(job_id, token, unit_id):
                return self._recovery(job_id, token, "lease_lost")
            try:
                result = safe_result(self.executor.execute(claimed_job, unit))
                is_limited = bool(result.get("source_limited"))
            except SourceLimited as exc:
                result = safe_result(dict(exc.result, source_limited=True))
                is_limited = True
            except Exception as exc:
                failure = self._failure(exc)
                try:
                    stored = self.repository.finish_unit(job_id, token, unit_id, "failed", failure)
                except Exception:
                    return self._recovery(job_id, token, "unit_audit_unknown")
                if not stored:
                    return self._recovery(job_id, token, "lease_lost")
                if isinstance(exc, UnitFailure) and exc.recovery_required:
                    return self._recovery(job_id, token, "data_commit_unknown")
                if not self.repository.finish_job(job_id, token, "failed", failure):
                    return self._recovery(job_id, token, "job_audit_unknown")
                return {"job_id": job_id, "status": "failed", "error": failure}
            try:
                stored = self.repository.finish_unit(
                    job_id, token, unit_id, "source_limited" if is_limited else "succeeded", result
                )
            except Exception:
                return self._recovery(job_id, token, "unit_audit_unknown")
            if not stored:
                return self._recovery(job_id, token, "lease_lost")
            limited |= is_limited
        current = self.repository.get_job(job_id)
        if current is None or current["status"] != "running":
            return self._recovery(job_id, token, "job_audit_unknown")
        status = (
            "cancelled"
            if current["cancel_requested"]
            else "completed_with_source_limitations"
            if limited
            else "succeeded"
        )
        if not self.repository.finish_job(job_id, token, status):
            return self._recovery(job_id, token, "job_audit_unknown")
        return {"job_id": job_id, "status": status}

    @staticmethod
    def _failure(error: Exception) -> dict[str, Any]:
        if isinstance(error, UnitFailure):
            return safe_result(error.result)
        if isinstance(error, ControlError):
            # ControlError构造器仅允许受控code/location，不转发str(error)。
            return safe_result({"code": error.code, "location": error.location})
        return {"code": "execution_failed", "location": "runner_execute"}
