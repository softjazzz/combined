"""已授权历史结果的准备/确认下载生命周期，只缓存脱敏制品。"""

from __future__ import annotations

import threading
import time
from uuid import uuid4

from .contracts import DiagnosticPackageError
from .history import build_history_documents, history_archive, replay_history


class HistoryDelivery:
    """五分钟内下载同一已预览制品；进程退出即失效，不读取文件或原始材料。"""

    def __init__(self) -> None:
        self._pending: dict[str, tuple[str, float, bytes]] = {}
        self._lock = threading.Lock()

    def __repr__(self) -> str:
        return "HistoryDelivery()"

    def prepare(self, *, workspace, owner: str, job_id: str, record_ref: str,
                institute_id: str, patient_id: str, visit_id: str) -> dict:
        if not owner or owner == "anonymous":
            raise DiagnosticPackageError("diagnostic_forbidden")
        # 先按任务创建人授权，再精确核对所选保存结果，拒绝替换成更新的任务。
        job = workspace.get_batch_job(job_id=job_id, created_by=owner)
        if not job or job.get("status") != "completed":
            raise DiagnosticPackageError("diagnostic_result_unavailable")
        result = workspace.get_latest_luxian_0609_record_result(
            institute_id=institute_id, patient_id=patient_id, visit_id=visit_id,
        )
        if result.get("state") != "ready" or result.get("job_id") != job_id or result.get("record_ref") != record_ref:
            raise DiagnosticPackageError("diagnostic_result_changed")
        documents = build_history_documents(result.get("items"))
        archive = history_archive(documents)
        preview = replay_history(documents)
        now, token = time.monotonic(), str(uuid4())
        with self._lock:
            self._prune(now)
            if len(self._pending) >= 128 or sum(len(value[2]) for value in self._pending.values()) + len(archive) > 4 * 1024 * 1024:
                raise DiagnosticPackageError("diagnostic_capacity_reached")
            self._pending[token] = (owner, now + 300, archive)
        return {"token": token, "expires_in_seconds": 300, "preview": preview,
                "included": ["规则编号与保存状态", "032/066 已支持的受控事实与文案投影"],
                "excluded": ["患者身份和病历正文", "模型请求与响应", "原始判定和执行版本", "其他规则的判定事实"],
                "notice": "历史受限包，不是完整质控复现。仅可核查受控字段；不能据此确认临床结论正确。"}

    def download(self, *, owner: str, token: str, confirmed: bool) -> bytes:
        if confirmed is not True:
            raise DiagnosticPackageError("diagnostic_confirmation_required")
        with self._lock:
            self._prune(time.monotonic())
            item = self._pending.get(token)
            if item is None or item[0] != owner:
                raise DiagnosticPackageError("diagnostic_download_unavailable")
            # 有效期内重试下载返回同一不可变制品，不重读数据库或重新生成。
            return item[2]

    def discard(self, *, owner: str, token: str) -> None:
        with self._lock:
            item = self._pending.get(token)
            if item is not None and item[0] == owner:
                del self._pending[token]

    def _prune(self, now: float) -> None:
        for token in list(self._pending):
            if self._pending[token][1] <= now:
                del self._pending[token]
