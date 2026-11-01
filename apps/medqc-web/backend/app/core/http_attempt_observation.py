"""可选的单次调用传输观测；不改变准入、请求或重试。"""

from contextlib import contextmanager
from contextvars import ContextVar
from threading import Lock


_ACTIVE = ContextVar("llm_http_attempt_observation", default=None)


class HTTPAttemptObservation:
    def __init__(self):
        self._lock = Lock()
        self.observed = False
        self.complete = False
        self.queue_ms = None
        self.transport_ms = None
        self.requests_started = 0
        self.responses_received = 0

    def submitted(self):
        with self._lock:
            self.observed = True

    def started(self, queue_seconds):
        with self._lock:
            self.queue_ms = max(0.0, queue_seconds * 1000)

    def finished(self, seconds):
        with self._lock:
            self.transport_ms = max(0.0, seconds * 1000)
            self.complete = True

    def sending(self):
        with self._lock:
            self.requests_started += 1

    def received(self):
        with self._lock:
            self.responses_received += 1

    def snapshot(self):
        with self._lock:
            return {"observed": self.observed, "complete": self.complete,
                    "queue_ms": self.queue_ms, "transport_ms": self.transport_ms,
                    "requests_started": self.requests_started,
                    "responses_received": self.responses_received}


def current_http_attempt_observation():
    return _ACTIVE.get()


@contextmanager
def http_attempt_observation_scope(*, enabled):
    # 子线程沿现有 copy_context 使用同一带锁收集器；不读取病例或响应正文。
    observation = HTTPAttemptObservation() if enabled else None
    token = _ACTIVE.set(observation)
    try:
        yield observation
    finally:
        _ACTIVE.reset(token)
