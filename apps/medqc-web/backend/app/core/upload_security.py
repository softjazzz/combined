from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Iterable, Optional

from fastapi import HTTPException, Request, UploadFile
from starlette import status

logger = logging.getLogger(__name__)

VirusScanHook = Callable[[bytes, str], tuple[bool, str]]
_virus_scan_hook: Optional[VirusScanHook] = None

_EICAR_SIGNATURE = b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE"


def register_virus_scan_hook_for_testing(hook: Optional[VirusScanHook]) -> None:
    global _virus_scan_hook
    _virus_scan_hook = hook


def clear_virus_scan_hook_for_testing() -> None:
    register_virus_scan_hook_for_testing(None)


def _audit_upload_rejected(
    *,
    request: Optional[Request],
    reason: str,
    filename: str,
    content_type: str,
    size_bytes: int,
) -> None:
    trace_id = getattr(request.state, "trace_id", "unknown") if request is not None else "unknown"
    logger.warning(
        "audit.upload.rejected reason=%s filename=%s content_type=%s size_bytes=%s",
        reason,
        filename or "<empty>",
        content_type or "<empty>",
        size_bytes,
        extra={"trace_id": trace_id},
    )


def _raise_upload_rejection(
    *,
    request: Optional[Request],
    reason: str,
    detail: str,
    filename: str,
    content_type: str,
    size_bytes: int,
) -> None:
    _audit_upload_rejected(
        request=request,
        reason=reason,
        filename=filename,
        content_type=content_type,
        size_bytes=size_bytes,
    )
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _human_readable_size(size_bytes: int) -> str:
    if size_bytes >= 1024 * 1024:
        mb = size_bytes / 1024 / 1024
        return f"{mb:.1f}MB"
    if size_bytes >= 1024:
        kb = size_bytes / 1024
        return f"{kb:.1f}KB"
    return f"{size_bytes}B"


def _scan_virus(content: bytes, filename: str) -> tuple[bool, str]:
    if _virus_scan_hook is not None:
        try:
            return _virus_scan_hook(content, filename)
        except Exception as exc:
            logger.exception("virus_scan_hook_failed filename=%s", filename)
            return False, f"病毒扫描钩子执行失败: {exc}"

    # Minimal built-in protection for CI/dev: block EICAR test signature.
    if _EICAR_SIGNATURE in content:
        return False, "检测到潜在恶意文件签名"
    return True, ""


def validate_uploaded_file(
    *,
    request: Optional[Request],
    file: UploadFile,
    content: bytes,
    allowed_extensions: Iterable[str],
    allowed_content_types: Iterable[str],
    max_bytes: int,
) -> None:
    filename = str(file.filename or "")
    if not filename:
        _raise_upload_rejection(
            request=request,
            reason="empty_filename",
            detail="文件名不能为空",
            filename=filename,
            content_type=str(file.content_type or ""),
            size_bytes=len(content),
        )

    ext = Path(filename).suffix.lower()
    content_type = str(file.content_type or "").lower().strip()
    size_bytes = len(content)

    normalized_exts = {item.lower().strip() for item in allowed_extensions if str(item).strip()}
    normalized_mimes = {item.lower().strip() for item in allowed_content_types if str(item).strip()}

    if ext not in normalized_exts:
        _raise_upload_rejection(
            request=request,
            reason="extension_not_allowed",
            detail=f"不支持的文件扩展名: {ext or '<none>'}",
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
        )

    if size_bytes > int(max(1, max_bytes)):
        _raise_upload_rejection(
            request=request,
            reason="file_too_large",
            detail=f"文件大小不能超过 {_human_readable_size(int(max_bytes))}",
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
        )

    # 浏览器/客户端常见回退 MIME: application/octet-stream
    if content_type and content_type not in normalized_mimes and content_type != "application/octet-stream":
        _raise_upload_rejection(
            request=request,
            reason="mime_not_allowed",
            detail=f"不支持的文件类型: {content_type}",
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
        )

    is_clean, scan_message = _scan_virus(content, filename)
    if not is_clean:
        _raise_upload_rejection(
            request=request,
            reason="virus_scan_blocked",
            detail=scan_message or "文件安全扫描未通过",
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
        )
