"""显式单病例排障采集的本地制品存储；只落盘经过导出投影的 ZIP。"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from uuid import UUID

from .contracts import DiagnosticPackageError
from .job_capture import DiagnosticJobCapture

_ROOT = Path(__file__).resolve().parents[2] / "storage" / "qc_diagnostics"
MAX_ARCHIVE_BYTES = 20 * 1024 * 1024
DEFAULT_ARCHIVE_TTL_SECONDS = 24 * 60 * 60
ARCHIVE_TTL_ENV_VAR = "QC_DIAGNOSTIC_ARCHIVE_TTL_SECONDS"
ARCHIVE_TTL_HOURS_ENV_VAR = "QC_DIAGNOSTIC_ARCHIVE_TTL_HOURS"
_MANAGED_SUFFIXES = (".zip", ".json", ".zip.tmp", ".json.tmp")


def archive_ttl_seconds() -> float:
    """读取排障包落盘保留时长（默认 24 小时，支持环境变量配置）。"""
    raw_seconds = os.getenv(ARCHIVE_TTL_ENV_VAR)
    if raw_seconds is not None and raw_seconds.strip():
        try:
            value = float(raw_seconds.strip())
            if value > 0:
                return value
        except ValueError:
            pass
    raw_hours = os.getenv(ARCHIVE_TTL_HOURS_ENV_VAR)
    if raw_hours is not None and raw_hours.strip():
        try:
            value = float(raw_hours.strip())
            if value > 0:
                return value * 3600.0
        except ValueError:
            pass
    return float(DEFAULT_ARCHIVE_TTL_SECONDS)


def _artifact_key(path: Path) -> str | None:
    name = path.name
    for suffix in _MANAGED_SUFFIXES:
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return None


def cleanup_expired_archives(
    *,
    now: float | None = None,
    ttl_seconds: float | None = None,
) -> int:
    """清理超过 TTL 的排障 ZIP/状态/临时文件，避免含医疗正文的排障包在磁盘无限堆积。"""
    if not _ROOT.exists():
        return 0
    ttl = archive_ttl_seconds() if ttl_seconds is None else float(ttl_seconds)
    if ttl <= 0:
        ttl = float(DEFAULT_ARCHIVE_TTL_SECONDS)
    cutoff = (time.time() if now is None else float(now)) - ttl

    expired_paths: set[Path] = set()
    expired_keys: set[str] = set()
    try:
        entries = list(_ROOT.iterdir())
    except OSError:
        return 0

    for entry in entries:
        key = _artifact_key(entry)
        if key is None:
            continue
        try:
            if not entry.is_file():
                continue
            if entry.stat().st_mtime <= cutoff:
                expired_paths.add(entry)
                if entry.name.endswith((".zip", ".json")):
                    expired_keys.add(key)
        except OSError:
            continue

    # 任一主文件过期时同步清理配对的 .zip / .json，防止状态残留或孤立 ZIP 滞留。
    for key in expired_keys:
        for suffix in (".zip", ".json"):
            candidate = _ROOT / (key + suffix)
            if candidate.exists():
                expired_paths.add(candidate)

    removed = 0
    for target in expired_paths:
        try:
            target.unlink()
            removed += 1
        except OSError:
            continue
    return removed


def _path(job_id: str, suffix: str) -> Path:
    try:
        key = str(UUID(job_id))
    except (ValueError, TypeError, AttributeError):
        raise DiagnosticPackageError("invalid_capture_job") from None
    return _ROOT / (key + suffix)


def _write_status(job_id: str, value: dict) -> None:
    _ROOT.mkdir(parents=True, exist_ok=True)
    target = _path(job_id, ".json")
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    temporary.replace(target)


def capture_for_job(workspace, job_id: str):
    """在 detached worker 所在进程构造，不跨进程传递原始材料。"""
    cleanup_expired_archives()
    job = workspace.get_batch_job_for_processing(job_id=job_id)
    filters = (job or {}).get("filters") or {}
    if filters.get("diagnostic_capture") is not True:
        return None
    refs = filters.get("record_refs") or []
    if len(refs) != 1:
        return None
    identity = tuple(str(refs[0].get(key) or "") for key in ("institute_id", "patient_id", "visit_id"))
    try:
        _write_status(job_id, {"state": "running"})
    except OSError:
        return None  # 诊断磁盘故障不得改变正式质控状态。

    def consume(data: dict, summary: dict):
        from .support_archive import build_support_archive
        cleanup_expired_archives()
        try:
            archive, metadata = build_support_archive(data, summary)
            if len(archive) > MAX_ARCHIVE_BYTES:
                raise DiagnosticPackageError("support_archive_size_limit")
            target = _path(job_id, ".zip")
            temporary = target.with_suffix(".zip.tmp")
            temporary.write_bytes(archive)
            temporary.replace(target)
            _write_status(job_id, {**metadata, "state": "ready", "size_bytes": len(archive),
                "missing_components": metadata.get("missing_reasons", []),
                "included": ["当次执行输入与源表读取状态", "模型请求响应", "保存结果与分规则索引", "执行版本与采集缺口"],
                "notice": "含必要医疗正文，身份仅尽力替换，临床日期保留；请人工复核后在授权范围使用。"})
        except Exception:
            _write_status(job_id, {"state": "failed", "error_code": "diagnostic_archive_failed"})

    try:
        return DiagnosticJobCapture(job_id=job_id, record_identity=identity,
                                    consume=consume, capture_partial=True)
    except DiagnosticPackageError:
        _write_status(job_id, {"state": "failed", "error_code": "invalid_capture_identity"})
        return None


def finalize(job_id: str) -> None:
    cleanup_expired_archives()
    try:
        value = json.loads(_path(job_id, ".json").read_text(encoding="utf-8"))
        if value.get("state") == "running":
            _write_status(job_id, {"state": "failed", "error_code": "capture_incomplete_or_interrupted"})
    except (OSError, ValueError):
        pass


def status(job_id: str, job_status: str) -> dict:
    cleanup_expired_archives()
    try:
        value = json.loads(_path(job_id, ".json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        value = {"state": "unavailable", "error_code": "capture_not_recorded"}
    if value.get("state") in {"running", "unavailable"}:
        if job_status in {"queued", "running"}:
            return {"state": "running"}
        # 正式结果提交和 ZIP 写入有短暂间隔；有采集标记时客户端继续轮询。
        if value.get("state") == "running":
            if time.time() - _path(job_id, ".json").stat().st_mtime < 3600:
                return value
        return {"state": "failed", "error_code": "capture_incomplete_or_interrupted"}
    return value


def download(job_id: str) -> bytes:
    cleanup_expired_archives()
    try:
        with _path(job_id, ".zip").open("rb") as stream:
            result = stream.read(MAX_ARCHIVE_BYTES + 1)
        if len(result) > MAX_ARCHIVE_BYTES:
            raise OSError()
        return result
    except OSError:
        raise DiagnosticPackageError("diagnostic_download_unavailable") from None
