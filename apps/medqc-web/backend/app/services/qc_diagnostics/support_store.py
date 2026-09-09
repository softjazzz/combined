"""显式单病例排障采集的本地制品存储；只落盘经过导出投影的 ZIP。"""
from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from .contracts import DiagnosticPackageError
from .job_capture import DiagnosticJobCapture

_ROOT = Path(__file__).resolve().parents[2] / "storage" / "qc_diagnostics"
MAX_ARCHIVE_BYTES = 20 * 1024 * 1024


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
    try:
        value = json.loads(_path(job_id, ".json").read_text(encoding="utf-8"))
        if value.get("state") == "running":
            _write_status(job_id, {"state": "failed", "error_code": "capture_incomplete_or_interrupted"})
    except (OSError, ValueError):
        pass


def status(job_id: str, job_status: str) -> dict:
    try:
        value = json.loads(_path(job_id, ".json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        value = {"state": "unavailable", "error_code": "capture_not_recorded"}
    if value.get("state") in {"running", "unavailable"}:
        if job_status in {"queued", "running"}:
            return {"state": "running"}
        # 正式结果提交和 ZIP 写入有短暂间隔；有采集标记时客户端继续轮询。
        if value.get("state") == "running":
            import time
            if time.time() - _path(job_id, ".json").stat().st_mtime < 3600:
                return value
        return {"state": "failed", "error_code": "capture_incomplete_or_interrupted"}
    return value


def download(job_id: str) -> bytes:
    try:
        with _path(job_id, ".zip").open("rb") as stream:
            result = stream.read(MAX_ARCHIVE_BYTES + 1)
        if len(result) > MAX_ARCHIVE_BYTES:
            raise OSError()
        return result
    except OSError:
        raise DiagnosticPackageError("diagnostic_download_unavailable") from None
