from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict, deque
from fastapi import HTTPException, Request, status


logger = logging.getLogger(__name__)
_rate_limit_lock = threading.Lock()
_rate_limit_store: dict[str, deque[float]] = defaultdict(deque)


def _build_client_key(request: Request, bucket: str) -> str:
    client_ip = request.client.host if request.client else "unknown"
    return f"{bucket}:{client_ip}"


def enforce_rate_limit(
    request: Request,
    *,
    bucket: str,
    max_requests: int,
    window_seconds: int,
):
    now = time.time()
    key = _build_client_key(request, bucket)
    with _rate_limit_lock:
        q = _rate_limit_store[key]
        threshold = now - max(1, int(window_seconds))
        while q and q[0] < threshold:
            q.popleft()
        if len(q) >= max(1, int(max_requests)):
            trace_id = getattr(request.state, "trace_id", "unknown")
            logger.warning(
                "audit.rate_limit.exceeded bucket=%s key=%s method=%s path=%s",
                bucket,
                key,
                request.method,
                request.url.path,
                extra={"trace_id": trace_id},
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests, please retry later.",
            )
        q.append(now)


def reset_rate_limit_store_for_testing() -> None:
    with _rate_limit_lock:
        _rate_limit_store.clear()
