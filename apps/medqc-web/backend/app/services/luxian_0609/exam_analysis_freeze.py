"""检查检验族模型结论冻结：同一批输入只由模型判定一次。

覆盖三类调用（按命名空间分目录）：06-01-05 病程分析核验（analysis）、报告异常与本次
就诊相关性（relevance）、主事实抽取及其随附核验（main）。

问题证据（2026-10-22 复验）：开思考的分析核验在临界写法上逐次翻转（C15 第3次检查、
C26 同一轮两次运行结论相反）；主抽取挑选证据病程也有出入（C08 时限内病程漏引、C02/C04
报告与病程关联）。用户决定（2026-10-22）：照会诊意见冻结的做法，同一份病历版本的结论
首次确定后固定复用。

职责边界：只存 Python 对模型应答完成核验后的结论（事件事实、病程引用、受控不足类别），
不存原文与模型原始输出。键为该次调用提示词（报告片段、病程片段、协议版本）的内容指纹：
病历内容、提示词或判定口径变化时自然失效。
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
import threading
import time
from typing import Any, Mapping
import uuid
import weakref

from ..llm_experiment import experiment_store_dir

logger = logging.getLogger(__name__)

# v2：分析核验改为覆盖完整长文书，并修正截断父批聚合。版本同时参与 analysis、relevance、
# main 三个命名空间的 key，使可能含旧错误事实的主冻结自然失效；旧文件保留、不删除。
FREEZE_SCHEMA_VERSION = "exam-finding-analysis-freeze-v2"
_ENV_STORE_DIR = "LUXIAN_0609_EXAM_ANALYSIS_FREEZE_DIR"
_LOCK_STALE_SECONDS = 30.0
_LOCK_MAX_ATTEMPTS = 200


class _PathLock:
    __slots__ = ("_lock", "__weakref__")

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def __enter__(self) -> _PathLock:
        self._lock.acquire()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._lock.release()


_WRITE_LOCKS_GUARD = threading.Lock()
_WRITE_LOCKS: weakref.WeakValueDictionary[str, _PathLock] = weakref.WeakValueDictionary()


def _path_lock(path: Path) -> _PathLock:
    key = os.path.normcase(os.path.abspath(str(path)))
    with _WRITE_LOCKS_GUARD:
        holder = _WRITE_LOCKS.get(key)
        if holder is None:
            holder = _PathLock()
            _WRITE_LOCKS[key] = holder
        return holder


def _publish_once_fallback(temporary: Path, path: Path) -> None:
    """硬链接不可用时以进程内锁 + 跨进程排他锁文件保障首次写入者赢。"""
    lock_path = path.with_name(f"{path.name}.lock")
    with _path_lock(path):
        if path.is_file():
            return
        acquired = False
        for attempt in range(_LOCK_MAX_ATTEMPTS):
            if path.is_file():
                return
            try:
                fd = os.open(
                    lock_path,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                    0o600,
                )
            except FileExistsError:
                try:
                    if time.time() - lock_path.stat().st_mtime > _LOCK_STALE_SECONDS:
                        lock_path.unlink(missing_ok=True)
                        continue
                except OSError:
                    pass
                if attempt == _LOCK_MAX_ATTEMPTS - 1:
                    if path.is_file():
                        return
                    raise OSError(f"freeze publish lock busy: {lock_path}")
                time.sleep(0.01)
            else:
                os.close(fd)
                acquired = True
                break
        if not acquired:
            return
        try:
            if path.is_file():
                return
            try:
                os.replace(temporary, path)
            except PermissionError:
                if path.is_file():
                    return
                raise
        finally:
            try:
                lock_path.unlink(missing_ok=True)
            except OSError:
                pass


def default_store_dir() -> Path:
    override = os.environ.get(_ENV_STORE_DIR, "").strip()
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[3] / "data" / "luxian_0609_exam_analysis_freeze"


def freeze_key(prompt: str, expected: Mapping[int, tuple[str, ...]] | None = None) -> str:
    digest = hashlib.sha256()
    digest.update(FREEZE_SCHEMA_VERSION.encode("utf-8"))
    digest.update(b"\x1e")
    digest.update(prompt.encode("utf-8"))
    digest.update(b"\x1e")
    digest.update(json.dumps(sorted((position, list(refs)) for position, refs in (expected or {}).items()),
                             ensure_ascii=False).encode("utf-8"))
    return digest.hexdigest()


def _windows_storage_path(path: Path) -> Path:
    # P5-B/实验隔离增加目录深度；保留完整隔离键，使用Windows长路径而不截短摘要。
    if os.name != 'nt':
        return path
    absolute = str(path.resolve())
    if absolute.startswith('\\\\?\\'):
        return Path(absolute)
    if absolute.startswith('\\\\'):
        return Path('\\\\?\\UNC\\' + absolute[2:])
    return Path('\\\\?\\' + absolute)


def load_payload(namespace: str, key: str) -> Mapping[str, Any] | None:
    path = _windows_storage_path(experiment_store_dir(default_store_dir()) / namespace / f"{key}.json")
    if not path.is_file():
        return None
    try:
        artifact = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        logger.warning("exam_lab_freeze_unreadable namespace=%s key=%s", namespace, key[:12])
        return None
    if (not isinstance(artifact, dict) or artifact.get("schema_version") != FREEZE_SCHEMA_VERSION
            or artifact.get("key") != key or not isinstance(artifact.get("payload"), dict)):
        return None
    return artifact["payload"]


def save_payload(namespace: str, key: str, payload: Mapping[str, Any]) -> None:
    """首次写入者赢：已有同键冻结时不覆盖。"""
    from ..llm_token_budget import context_budget_failed
    if context_budget_failed():
        return
    directory = _windows_storage_path(experiment_store_dir(default_store_dir()) / namespace)
    path = directory / f"{key}.json"
    if path.is_file():
        return
    directory.mkdir(parents=True, exist_ok=True)
    artifact = {"schema_version": FREEZE_SCHEMA_VERSION, "key": key, "payload": payload}
    temporary = path.with_name(
        f"{path.name}.{os.getpid()}.{threading.get_ident()}.{uuid.uuid4().hex[:8]}.tmp"
    )
    try:
        temporary.write_text(
            json.dumps(artifact, ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        try:
            os.link(temporary, path)
        except FileExistsError:
            # 首次写入者赢：并发竞争中已有同键落盘时不覆盖。
            return
        except OSError:
            _publish_once_fallback(temporary, path)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def load_analysis(key: str) -> tuple[dict[int, tuple[str, ...]], dict[int, tuple[tuple[str, str], ...]]] | None:
    payload = load_payload("analysis", key)
    if payload is None:
        return None
    try:
        analysed = {int(position): tuple(str(ref) for ref in refs) for position, refs in payload["analysed"].items()}
        gaps = {
            int(position): tuple((str(ref), str(kind)) for ref, kind in items)
            for position, items in payload["gaps"].items()
        }
    except (ValueError, TypeError, KeyError, AttributeError):
        logger.warning("exam_analysis_freeze_unreadable key=%s", key[:12])
        return None
    return analysed, gaps


def save_analysis(
    key: str,
    analysed: Mapping[int, tuple[str, ...]],
    gaps: Mapping[int, tuple[tuple[str, str], ...]],
) -> None:
    save_payload("analysis", key, {
        "analysed": {str(position): list(refs) for position, refs in analysed.items()},
        "gaps": {str(position): [list(item) for item in items] for position, items in gaps.items()},
    })
