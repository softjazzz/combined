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
from typing import Any, Mapping

from ..llm_experiment import experiment_store_dir

logger = logging.getLogger(__name__)

# v2：分析核验改为覆盖完整长文书，并修正截断父批聚合。版本同时参与 analysis、relevance、
# main 三个命名空间的 key，使可能含旧错误事实的主冻结自然失效；旧文件保留、不删除。
FREEZE_SCHEMA_VERSION = "exam-finding-analysis-freeze-v2"
_ENV_STORE_DIR = "LUXIAN_0609_EXAM_ANALYSIS_FREEZE_DIR"


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


def load_payload(namespace: str, key: str) -> Mapping[str, Any] | None:
    path = experiment_store_dir(default_store_dir()) / namespace / f"{key}.json"
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
    directory = experiment_store_dir(default_store_dir()) / namespace
    path = directory / f"{key}.json"
    if path.is_file():
        return
    directory.mkdir(parents=True, exist_ok=True)
    artifact = {"schema_version": FREEZE_SCHEMA_VERSION, "key": key, "payload": payload}
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(artifact, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    os.replace(temporary, path)


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
