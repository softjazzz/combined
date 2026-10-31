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
from typing import Any, Mapping

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


def _path(visit_id: str) -> Path:
    safe = _SAFE_NAME.sub("_", str(visit_id)).strip("_") or "unknown"
    return experiment_store_dir(default_store_dir()) / f"{safe}.json"


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

    def __init__(self, inner: Any, *, visit_id: str) -> None:
        self._inner = inner
        self._visit_id = visit_id
        self._stored: dict[str, list[Any]] = {}
        self._served: dict[str, int] = defaultdict(int)
        self._recorded: dict[str, list[Any]] = defaultdict(list)
        self.reused_calls = 0
        self._experiment_namespace = current_llm_experiment_namespace()
        self._store_path = _path(visit_id)
        path = self._store_path
        if path.is_file():
            try:
                artifact = json.loads(path.read_text(encoding="utf-8"))
                if (isinstance(artifact, dict) and artifact.get("schema_version") == FREEZE_SCHEMA_VERSION
                        and artifact.get("visit_id") == visit_id and isinstance(artifact.get("entries"), dict)):
                    self._stored = {
                        str(key): list(value) for key, value in artifact["entries"].items() if isinstance(value, list)
                    }
            except (OSError, ValueError):
                logger.warning("consultation_response_freeze_unreadable")

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def _require_same_experiment(self) -> None:
        if current_llm_experiment_namespace() != self._experiment_namespace:
            raise LLMExperimentConfigurationError("frozen response client experiment changed")

    async def generate(self, prompt: str, **kwargs: Any) -> Any:
        self._require_same_experiment()
        key = _key(prompt, kwargs)
        index = self._served[key]
        self._served[key] += 1
        stored = self._stored.get(key, ())
        if index < len(stored):
            self.reused_calls += 1
            response = stored[index]
            self._recorded[key].append(response)
            return _without_usage(response)
        response = await self._inner.generate(prompt, **kwargs)
        try:
            json.dumps(response, ensure_ascii=False)
            self._recorded[key].append(copy.deepcopy(response))
        except (TypeError, ValueError):
            pass
        return response

    def commit(self) -> None:
        """整次运行可交付时落盘：已有提示词的记录不覆盖（首次写入者赢），只补入新提示词。"""
        self._require_same_experiment()
        new_keys = [key for key in self._recorded if key not in self._stored]
        if not new_keys:
            return
        path = self._store_path
        path.parent.mkdir(parents=True, exist_ok=True)
        artifact = {
            "schema_version": FREEZE_SCHEMA_VERSION,
            "visit_id": self._visit_id,
            "entries": {**self._stored, **{key: self._recorded[key] for key in new_keys}},
        }
        temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
        temporary.write_text(json.dumps(artifact, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        os.replace(temporary, path)
