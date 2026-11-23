"""会诊族第二阶段模型应答冻结：同一病历版本的执行核对只由模型判定一次。

问题证据（2026-10-22 例子验证）：第一阶段建议已冻结后，C04“动态复查血常规、血凝”在
逐建议执行核对中一次判未执行、一次匹配到医嘱，结论逐次不同。用户决定（2026-10-22）：
与检查检验族一样冻结复用。

做法：在执行器入口包装模型客户端，按“提示词 + 调用参数”的指纹记录本次运行的应答；只有
整次运行全部结论可交付（无 technical_error / evaluation_unknown）时才落盘。下次运行同一
提示词按记录顺序直接返回已存应答，Python 判定随之复现；病历或提示词变化即自然不命中。
同一提示词在一次运行中多次调用（如原样重试）时按调用顺序分别记录、分别返回。

存储含模型原始应答（与第一阶段意见冻结同一做法），落在 backend/data 下且不提交。
"""

from __future__ import annotations

from collections import defaultdict
import copy
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import threading
import time
from typing import Any, Mapping
import uuid
import weakref

from ..llm_experiment import (
    LLMExperimentConfigurationError, current_llm_experiment_namespace, experiment_store_dir,
)

logger = logging.getLogger(__name__)

FREEZE_SCHEMA_VERSION = "consultation-response-freeze-v1"
_ENV_STORE_DIR = "LUXIAN_0609_CONSULTATION_RESPONSE_FREEZE_DIR"
_SAFE_NAME = re.compile(r"[^0-9A-Za-z_.-]+")
_ZERO_USAGE = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


def default_store_dir() -> Path:
    override = os.environ.get(_ENV_STORE_DIR, "").strip()
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[3] / "data" / "luxian_0609_consultation_response_freeze"


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


def _atomic_replace(src: Path, dst: Path) -> None:
    for attempt in range(5):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if os.name != "nt" or attempt == 4:
                raise
            time.sleep(0.01 * (attempt + 1))


def _resolve_case_scope(
    visit_id: str,
    *,
    institute_id: str | None = None,
    patient_id: str | None = None,
) -> tuple[str, str] | None:
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


def _case_scope_hash(
    visit_id: str,
    *,
    institute_id: str | None = None,
    patient_id: str | None = None,
) -> str | None:
    scope = _resolve_case_scope(
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


def _freeze_stem(
    visit_id: str,
    *,
    institute_id: str | None = None,
    patient_id: str | None = None,
) -> str:
    raw_visit = str(visit_id)
    safe = _SAFE_NAME.sub("_", raw_visit).strip("_") or "unknown"
    safe_prefix = "visit" if safe in (".", "..") else safe[:80]
    scope_hash = _case_scope_hash(
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


def _path(
    visit_id: str,
    *,
    institute_id: str | None = None,
    patient_id: str | None = None,
) -> Path:
    stem = _freeze_stem(
        visit_id, institute_id=institute_id, patient_id=patient_id
    )
    return experiment_store_dir(default_store_dir()) / f"{stem}.json"


def _read_entries(
    path: Path,
    *,
    visit_id: str,
    case_scope_hash: str | None,
) -> dict[str, list[Any]]:
    if not path.is_file():
        return {}
    try:
        artifact = json.loads(path.read_text(encoding="utf-8"))
        if (
            isinstance(artifact, dict)
            and artifact.get("schema_version") == FREEZE_SCHEMA_VERSION
            and artifact.get("visit_id") == visit_id
            and artifact.get("case_scope_hash") == case_scope_hash
            and isinstance(artifact.get("entries"), dict)
        ):
            return {
                str(key): list(value)
                for key, value in artifact["entries"].items()
                if isinstance(value, list)
            }
    except (OSError, ValueError):
        logger.warning("consultation_response_freeze_unreadable")
    return {}


def _key(prompt: str, kwargs: Mapping[str, Any]) -> str:
    digest = hashlib.sha256()
    digest.update(FREEZE_SCHEMA_VERSION.encode("utf-8"))
    digest.update(b"\x1e")
    digest.update(str(prompt).encode("utf-8"))
    digest.update(b"\x1e")
    digest.update(json.dumps(kwargs, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8"))
    return digest.hexdigest()


def _without_usage(response: Any) -> Any:
    """复用的应答不再计入调用量与 Token（未实际调用模型）。"""
    if not isinstance(response, Mapping):
        return response
    reused = copy.deepcopy(dict(response))
    if "usage" in reused:
        reused["usage"] = dict(_ZERO_USAGE)
    for key in ("_api_time", "response_time"):
        if key in reused:
            reused[key] = 0.0
    return reused


class FrozenResponseClient:
    """包装模型客户端；其余属性（结构化输出能力等）透传给原客户端。"""

    def __init__(
        self,
        inner: Any,
        *,
        visit_id: str,
        institute_id: str | None = None,
        patient_id: str | None = None,
    ) -> None:
        self._inner = inner
        self._visit_id = visit_id
        self._stored: dict[str, list[Any]] = {}
        self._served: dict[str, int] = defaultdict(int)
        self._recorded: dict[str, list[Any]] = defaultdict(list)
        self.reused_calls = 0
        self._experiment_namespace = current_llm_experiment_namespace()
        from ..llm_task_roles import current_task_role_partition

        self._task_role_partition = current_task_role_partition()
        self._explicit_institute_id = institute_id
        self._explicit_patient_id = patient_id
        self._case_scope_hash = _case_scope_hash(
            visit_id, institute_id=institute_id, patient_id=patient_id
        )
        self._store_path = _path(
            visit_id, institute_id=institute_id, patient_id=patient_id
        )
        self._stored = _read_entries(
            self._store_path,
            visit_id=visit_id,
            case_scope_hash=self._case_scope_hash,
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def for_task_role(self, role: str) -> Any:
        from ..llm_task_roles import client_for_task

        selected = client_for_task(self._inner, role)
        if selected is self._inner:
            return self
        return _RoleResponseClient(self, selected)

    def _require_same_experiment(self) -> None:
        if current_llm_experiment_namespace() != self._experiment_namespace:
            raise LLMExperimentConfigurationError("frozen response client experiment changed")
        from ..llm_task_roles import current_task_role_partition

        if current_task_role_partition() != self._task_role_partition:
            raise LLMExperimentConfigurationError("frozen response client task roles changed")
        current_scope_hash = _case_scope_hash(
            self._visit_id,
            institute_id=self._explicit_institute_id,
            patient_id=self._explicit_patient_id,
        )
        if current_scope_hash != self._case_scope_hash:
            from .llm_prompt_privacy import PrivacyIdentityContextError

            raise PrivacyIdentityContextError("Patient identity context unavailable")

    async def generate(self, prompt: str, **kwargs: Any) -> Any:
        return await self._generate_with(self._inner, prompt, **kwargs)

    async def _generate_with(self, inner: Any, prompt: str, **kwargs: Any) -> Any:
        self._require_same_experiment()
        key = _key(prompt, kwargs)
        if getattr(inner, "task_role_identity", None):
            key += ":" + str(getattr(inner, "model_role", "default"))
        index = self._served[key]
        self._served[key] += 1
        stored = self._stored.get(key, ())
        if index < len(stored):
            self.reused_calls += 1
            response = stored[index]
            self._recorded[key].append(response)
            return _without_usage(response)
        response = await inner.generate(prompt, **kwargs)
        try:
            json.dumps(response, ensure_ascii=False)
            self._recorded[key].append(copy.deepcopy(response))
        except (TypeError, ValueError):
            pass
        return response

    def commit(self) -> None:
        """整次运行可交付时落盘：已有提示词的记录不覆盖（首次写入者赢），只补入新提示词。"""
        self._require_same_experiment()
        from ..llm_token_budget import context_budget_failed
        if context_budget_failed():
            return
        if not any(key not in self._stored for key in self._recorded):
            return
        path = self._store_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with _path_lock(path):
            disk_entries = _read_entries(
                path,
                visit_id=self._visit_id,
                case_scope_hash=self._case_scope_hash,
            )
            merged_base = {**self._stored, **disk_entries}
            new_keys = [key for key in self._recorded if key not in merged_base]
            if not new_keys:
                return
            entries = {
                **merged_base,
                **{key: self._recorded[key] for key in new_keys},
            }
            artifact: dict[str, Any] = {
                "schema_version": FREEZE_SCHEMA_VERSION,
                "visit_id": self._visit_id,
                "entries": entries,
            }
            if self._case_scope_hash is not None:
                artifact["case_scope_hash"] = self._case_scope_hash
            temporary = path.with_name(
                f"{path.name}.{os.getpid()}.{threading.get_ident()}.{uuid.uuid4().hex[:8]}.tmp"
            )
            try:
                temporary.write_text(
                    json.dumps(artifact, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                    newline="\n",
                )
                _atomic_replace(temporary, path)
            finally:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass


class _RoleResponseClient:
    """角色选择保留同一轮应答账本、使用量与完成后提交门槛。"""

    def __init__(self, owner, inner):
        self._owner, self._inner = owner, inner

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def for_task_role(self, role):
        return self._owner.for_task_role(role)

    async def generate(self, prompt, **kwargs):
        return await self._owner._generate_with(self._inner, prompt, **kwargs)
