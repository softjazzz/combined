"""06-01-05 病程分析核验结论冻结：同一批输入只由模型判定一次。

问题证据（2026-10-22 复验）：开思考的分析核验在临界写法上逐次翻转（C15 第3次检查、
C26 同一轮两次运行结论相反）。用户决定（2026-10-22）：照会诊意见冻结的做法，
同一份病历版本的分析结论首次确定后固定复用。

职责边界：只存 Python 对模型应答完成核验后的结论（各检查事件算分析的病程引用、
未分析时的受控不足类别），不存原文与模型原始输出。键为该批提示词（报告片段、病程片段、
协议版本）的内容指纹：病历内容、提示词或判定口径变化时自然失效。
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any, Mapping

logger = logging.getLogger(__name__)

# 判定口径（自有内容门槛、套话剔除、归属核对）变化时提升版本，使旧冻结失效。
FREEZE_SCHEMA_VERSION = "exam-finding-analysis-freeze-v1"
_ENV_STORE_DIR = "LUXIAN_0609_EXAM_ANALYSIS_FREEZE_DIR"


def default_store_dir() -> Path:
    override = os.environ.get(_ENV_STORE_DIR, "").strip()
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[3] / "data" / "luxian_0609_exam_analysis_freeze"


def freeze_key(prompt: str, expected: Mapping[int, tuple[str, ...]]) -> str:
    digest = hashlib.sha256()
    digest.update(FREEZE_SCHEMA_VERSION.encode("utf-8"))
    digest.update(b"\x1e")
    digest.update(prompt.encode("utf-8"))
    digest.update(b"\x1e")
    digest.update(json.dumps(sorted((position, list(refs)) for position, refs in expected.items()),
                             ensure_ascii=False).encode("utf-8"))
    return digest.hexdigest()


def load_analysis(key: str) -> tuple[dict[int, tuple[str, ...]], dict[int, tuple[tuple[str, str], ...]]] | None:
    path = default_store_dir() / f"{key}.json"
    if not path.is_file():
        return None
    try:
        artifact = json.loads(path.read_text(encoding="utf-8"))
        if artifact.get("schema_version") != FREEZE_SCHEMA_VERSION or artifact.get("key") != key:
            return None
        analysed = {int(position): tuple(str(ref) for ref in refs) for position, refs in artifact["analysed"].items()}
        gaps = {
            int(position): tuple((str(ref), str(kind)) for ref, kind in items)
            for position, items in artifact["gaps"].items()
        }
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        logger.warning("exam_analysis_freeze_unreadable key=%s", key[:12])
        return None
    return analysed, gaps


def save_analysis(
    key: str,
    analysed: Mapping[int, tuple[str, ...]],
    gaps: Mapping[int, tuple[tuple[str, str], ...]],
) -> None:
    """首次写入者赢：已有同键冻结时不覆盖。"""
    directory = default_store_dir()
    path = directory / f"{key}.json"
    if path.is_file():
        return
    directory.mkdir(parents=True, exist_ok=True)
    artifact: dict[str, Any] = {
        "schema_version": FREEZE_SCHEMA_VERSION,
        "key": key,
        "analysed": {str(position): list(refs) for position, refs in analysed.items()},
        "gaps": {str(position): [list(item) for item in items] for position, items in gaps.items()},
    }
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(artifact, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    os.replace(temporary, path)
