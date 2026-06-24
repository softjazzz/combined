from __future__ import annotations

from collections import deque
import threading
import time
from typing import Deque, Dict


class RuntimeRequestMetrics:
    def __init__(self, *, max_latency_samples: int = 2048, qps_window_seconds: int = 60) -> None:
        self._lock = threading.Lock()
        self._started_at = time.time()
        self._qps_window_seconds = max(10, qps_window_seconds)
        self._total_requests = 0
        self._in_flight_requests = 0
        self._error_requests = 0
        self._total_latency_ms = 0.0
        self._latency_samples_ms: Deque[float] = deque(maxlen=max(32, max_latency_samples))
        self._request_timestamps: Deque[float] = deque()
        self._status_counts: Dict[str, int] = {
            "1xx": 0,
            "2xx": 0,
            "3xx": 0,
            "4xx": 0,
            "5xx": 0,
            "unknown": 0,
        }

    def mark_request_started(self) -> None:
        with self._lock:
            self._in_flight_requests += 1

    def mark_request_finished(self, status_code: int, duration_ms: float) -> None:
        status_bucket = self._to_status_bucket(status_code)
        now = time.time()
        normalized_duration_ms = max(0.0, duration_ms)
        with self._lock:
            self._in_flight_requests = max(0, self._in_flight_requests - 1)
            self._total_requests += 1
            self._total_latency_ms += normalized_duration_ms
            self._latency_samples_ms.append(normalized_duration_ms)
            self._request_timestamps.append(now)
            self._prune_request_timestamps_locked(now)
            self._status_counts[status_bucket] = self._status_counts.get(status_bucket, 0) + 1
            if status_code >= 400:
                self._error_requests += 1

    def snapshot(self) -> Dict[str, object]:
        with self._lock:
            now = time.time()
            self._prune_request_timestamps_locked(now)
            uptime_seconds = int(max(0.0, now - self._started_at))
            total = self._total_requests
            avg_latency = (self._total_latency_ms / total) if total else 0.0
            error_rate = (self._error_requests / total) if total else 0.0
            status_counts = dict(self._status_counts)
            qps_avg = (total / uptime_seconds) if uptime_seconds else 0.0
            qps_1m = (len(self._request_timestamps) / self._qps_window_seconds) if self._qps_window_seconds else 0.0
            p95_latency_ms = self._percentile_ms_locked(95.0)
            return {
                "uptime_seconds": uptime_seconds,
                "total_requests": total,
                "in_flight_requests": self._in_flight_requests,
                "error_requests": self._error_requests,
                "error_rate": round(error_rate, 6),
                "avg_latency_ms": round(avg_latency, 2),
                "p95_latency_ms": p95_latency_ms,
                "requests_per_second": round(qps_avg, 4),
                "requests_per_second_1m": round(qps_1m, 4),
                "status_counts": status_counts,
            }

    def _prune_request_timestamps_locked(self, now: float) -> None:
        threshold = now - self._qps_window_seconds
        while self._request_timestamps and self._request_timestamps[0] < threshold:
            self._request_timestamps.popleft()

    def _percentile_ms_locked(self, percentile: float) -> float:
        if not self._latency_samples_ms:
            return 0.0
        ordered = sorted(self._latency_samples_ms)
        position = int((percentile / 100.0) * (len(ordered) - 1))
        position = max(0, min(position, len(ordered) - 1))
        return round(float(ordered[position]), 2)

    @staticmethod
    def _to_status_bucket(status_code: int) -> str:
        if 100 <= status_code < 200:
            return "1xx"
        if 200 <= status_code < 300:
            return "2xx"
        if 300 <= status_code < 400:
            return "3xx"
        if 400 <= status_code < 500:
            return "4xx"
        if 500 <= status_code < 600:
            return "5xx"
        return "unknown"


runtime_request_metrics = RuntimeRequestMetrics()
