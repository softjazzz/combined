"""0609 冻结存储底层共享原语：进程内路径锁、OS 内核文件锁、原子替换与病例范围键。

职责边界：
- 本模块只提供跨冻结域共享的底层同步与文件路径命名原语；
- 各类证据的 schema 版本、外置目录环境变量、载荷结构、有效性校验与旧键兼容策略仍由各自领域模块拥有。
"""

from __future__ import annotations

from contextlib import contextmanager
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import time
from typing import Iterator
import weakref

_SAFE_NAME = re.compile(r"[^0-9A-Za-z_.-]+")


class PathLock:
    __slots__ = ("_lock", "__weakref__")

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def __enter__(self) -> PathLock:
        self._lock.acquire()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._lock.release()


_WRITE_LOCKS_GUARD = threading.Lock()
_WRITE_LOCKS: weakref.WeakValueDictionary[str, PathLock] = weakref.WeakValueDictionary()


def path_lock(path: Path) -> PathLock:
    """返回同一规范路径的进程内排他锁（按路径弱引用回收）。"""
    key = os.path.normcase(os.path.abspath(str(path)))
    with _WRITE_LOCKS_GUARD:
        holder = _WRITE_LOCKS.get(key)
        if holder is None:
            holder = PathLock()
            _WRITE_LOCKS[key] = holder
        return holder


def is_valid_freeze_file(path: Path) -> bool:
    """检查目标冻结文件是否存在且可解析为 JSON 对象。"""
    if not path.is_file():
        return False
    try:
        artifact = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(artifact, dict)


@contextmanager
def kernel_file_lock(lock_path: Path) -> Iterator[None]:
    """使用 OS 内核文件锁跨进程排他同步，无超时窃锁；进程崩溃由内核立即释放。"""
    lock_fs = os.fspath(lock_path)
    open_flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_BINARY", 0)
    if os.name == "nt":
        import msvcrt

        fd: int | None = None
        for attempt in range(50):
            try:
                fd = os.open(lock_fs, open_flags, 0o600)
                break
            except PermissionError:
                if not lock_path.exists() or attempt == 49:
                    raise
                time.sleep(0.005)
        assert fd is not None
        locked = False
        try:
            while True:
                os.lseek(fd, 0, os.SEEK_SET)
                try:
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                    locked = True
                    break
                except OSError as exc:
                    if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                        raise
                    time.sleep(0.01)
            yield
        finally:
            if locked:
                try:
                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
            os.close(fd)
            try:
                lock_path.unlink(missing_ok=True)
            except OSError:
                pass
    else:
        import fcntl

        while True:
            fd = os.open(lock_fs, open_flags, 0o600)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX)
                try:
                    path_stat = os.stat(lock_fs)
                    fd_stat = os.fstat(fd)
                except FileNotFoundError:
                    os.close(fd)
                    continue
                if path_stat.st_ino != fd_stat.st_ino or path_stat.st_dev != fd_stat.st_dev:
                    os.close(fd)
                    continue
            except BaseException:
                os.close(fd)
                raise
            break
        try:
            yield
        finally:
            try:
                lock_path.unlink(missing_ok=True)
            except OSError:
                pass
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass
            os.close(fd)


def replace_with_retry(temporary: Path, path: Path) -> None:
    """在并发读取导致 Windows PermissionError 时重试替换；目标已有效则保留既有文件。"""
    for attempt in range(20):
        try:
            os.replace(temporary, path)
            return
        except PermissionError:
            if is_valid_freeze_file(path):
                return
            if attempt == 19:
                raise
            time.sleep(0.01)


def publish_once_with_kernel_lock(temporary: Path, path: Path) -> None:
    """无硬链接或目标残损时，以进程内锁 + OS 内核文件锁原子替换发布，首次有效写入者赢。"""
    lock_path = path.with_name(f"{path.name}.lock")
    with path_lock(path):
        if is_valid_freeze_file(path):
            return
        with kernel_file_lock(lock_path):
            if is_valid_freeze_file(path):
                return
            replace_with_retry(temporary, path)


def atomic_replace(src: Path, dst: Path) -> None:
    """跨平台原子替换（Windows 瞬时占用时指数短退避重试）。"""
    for attempt in range(5):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if os.name != "nt" or attempt == 4:
                raise
            time.sleep(0.01 * (attempt + 1))


def resolve_case_scope(
    visit_id: str,
    *,
    institute_id: str | None = None,
    patient_id: str | None = None,
) -> tuple[str, str] | None:
    """解析病例级冻结作用域（院区、患者），与当前请求隐私上下文交叉核对。"""
    from . import privacy_request_scope
    from .llm_prompt_privacy import PrivacyIdentityContextError

    scope = privacy_request_scope._SCOPE.get()
    if scope is not None and scope.case_coordinates is not None:
        if not scope.lease.active:
            raise PrivacyIdentityContextError("Patient identity context unavailable")
        scope_inst, scope_pat, scope_visit = scope.case_coordinates
        if scope_visit != str(visit_id).strip():
            raise PrivacyIdentityContextError("Patient identity context unavailable")
        if institute_id is not None and str(institute_id).strip() != scope_inst:
            raise PrivacyIdentityContextError("Patient identity context unavailable")
        if patient_id is not None and str(patient_id).strip() != scope_pat:
            raise PrivacyIdentityContextError("Patient identity context unavailable")
        return (scope_inst, scope_pat) if (scope_inst or scope_pat) else None
    if institute_id is not None or patient_id is not None:
        inst = "" if institute_id is None else str(institute_id).strip()
        pat = "" if patient_id is None else str(patient_id).strip()
        return (inst, pat) if (inst or pat) else None
    return None


def case_scope_hash(
    visit_id: str,
    *,
    institute_id: str | None = None,
    patient_id: str | None = None,
) -> str | None:
    """计算病例三键作用域哈希（与既有冻结文件旧键 100% 字节一致）。"""
    scope = resolve_case_scope(
        visit_id, institute_id=institute_id, patient_id=patient_id
    )
    if scope is None:
        return None
    inst, pat = scope
    digest = hashlib.sha256()
    digest.update(b"case\x1e")
    digest.update(inst.encode("utf-8"))
    digest.update(b"\x1e")
    digest.update(pat.encode("utf-8"))
    digest.update(b"\x1e")
    digest.update(str(visit_id).encode("utf-8"))
    return digest.hexdigest()[:16]


def freeze_stem(
    visit_id: str,
    *,
    institute_id: str | None = None,
    patient_id: str | None = None,
) -> str:
    """生成安全且稳定的病例冻结文件名主干（兼容历史旧键）。"""
    raw_visit = str(visit_id)
    safe = _SAFE_NAME.sub("_", raw_visit).strip("_") or "unknown"
    safe_prefix = "visit" if safe in (".", "..") else safe[:80]
    scope_hash = case_scope_hash(
        visit_id, institute_id=institute_id, patient_id=patient_id
    )
    if scope_hash is not None:
        return f"{safe_prefix}__{scope_hash}"
    if safe != raw_visit or safe in (".", "..") or len(raw_visit) > 80:
        visit_hash = hashlib.sha256(
            b"visit\x1e" + raw_visit.encode("utf-8")
        ).hexdigest()[:16]
        return f"{safe_prefix}__{visit_hash}"
    return safe


__all__ = [
    "PathLock",
    "atomic_replace",
    "case_scope_hash",
    "freeze_stem",
    "is_valid_freeze_file",
    "kernel_file_lock",
    "path_lock",
    "publish_once_with_kernel_lock",
    "replace_with_retry",
    "resolve_case_scope",
]
