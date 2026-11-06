"""A0/A1实验隔离边界；只改变事实冻结目录，不改变模型或医学输入。"""

from contextlib import contextmanager
from contextvars import ContextVar
import os
from pathlib import Path
import re
from typing import Iterator


_ENV_NAMESPACE = "LLM_EXPERIMENT_NAMESPACE"
_NAMESPACE_PATTERN = re.compile(r"A[01](?:-[A-Za-z0-9][A-Za-z0-9_-]*)?")
_CURRENT: ContextVar[str | None] = ContextVar("llm_experiment_namespace", default=None)


class LLMExperimentConfigurationError(ValueError):
    """实验配置非法时失败关闭；不回显未受信任标识。"""


def _validated_namespace(namespace: object) -> str:
    if (
        not isinstance(namespace, str)
        or len(namespace) > 64
        or _NAMESPACE_PATTERN.fullmatch(namespace) is None
    ):
        raise LLMExperimentConfigurationError("invalid LLM experiment namespace")
    return namespace


def current_llm_experiment_namespace() -> str | None:
    """未配置时为原有基线；非法显式配置绝不静默退回基线。"""
    scoped = _CURRENT.get()
    if scoped is not None:
        return scoped
    configured = os.environ.get(_ENV_NAMESPACE)
    if configured in (None, ""):
        return None
    return _validated_namespace(configured)


@contextmanager
def llm_experiment_scope(namespace: str) -> Iterator[None]:
    """单次完整实验使用同一标签，支持嵌套及并发任务；不写进程环境。"""
    token = _CURRENT.set(_validated_namespace(namespace))
    try:
        yield
    finally:
        _CURRENT.reset(token)


def experiment_store_dir(base: Path) -> Path:
    """在真实存储owner最终IO路径处调用一次，不能对已隔离目录重复调用。"""
    from ..database.clinical_connection import current_selection
    source = current_selection()
    if source and source.get("binding"):
        import hashlib
        base = base / "clinical-sources" / hashlib.sha256(source["binding"].encode()).hexdigest()
    namespace = current_llm_experiment_namespace()
    from .llm_token_budget import freeze_namespace
    context_namespace = freeze_namespace()
    if context_namespace is not None:
        base = base / "context-budget" / context_namespace
    from .llm_task_roles import current_task_role_partition

    partition = current_task_role_partition()
    if namespace is None and partition is None:
        return base
    target = base / "experiments" / namespace if namespace else base
    if partition:
        target = target / "task-roles" / partition
    if base.resolve() not in target.resolve().parents:
        raise LLMExperimentConfigurationError(
            "LLM experiment store escapes owner directory"
        )
    # 分区之下仍有64位事实文件名；Windows部署目录较长时用长路径前缀。
    if partition and os.name == "nt":
        resolved = str(target.resolve())
        if not resolved.startswith("\\\\?\\"):
            resolved = "\\\\?\\UNC\\" + resolved[2:] if resolved.startswith("\\\\") else "\\\\?\\" + resolved
        return Path(resolved)
    return target
