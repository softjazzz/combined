"""抗菌药族模型事实冻结：同一批输入只由模型判定一次。

覆盖三类抽取（按命名空间分目录）：054/057 用药理由（order_reason）、058 特殊级专家同意
（special_approval）、055 疗效与安全性评价（effect）。

问题证据（2026-10-23 客户包复跑）：C11 05-01-05 同一份病历一次把“继续头孢曲松抗感染，
必要时据药敏调整”摘为选药理由判合规，一次留空判不合规；27 例验收中 05-01-03、05-01-05、
05-01-06 均有逐次翻转。用户决定（2026-10-22/23）：照检查检验族的做法冻结复用。

职责边界：只存 Python 完成引文核验后的事实（事件、引文及所在文书编号），不存模型原始输出。
键为该次调用提示词的内容指纹：病历内容、提示词或判定口径变化时自然失效。只有抽取完整就绪
（state=ready）才落盘，技术错误、资料不足的下次重新调用模型。
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
import threading
from typing import Any, Mapping
import uuid

from ..llm_experiment import experiment_store_dir

logger = logging.getLogger(__name__)

# 冻结内容的结构或核验口径变化时提升版本，使旧冻结失效。
FREEZE_SCHEMA_VERSION = "antimicrobial-fact-freeze-v1"
_ENV_STORE_DIR = "LUXIAN_0609_ANTIMICROBIAL_FREEZE_DIR"


def default_store_dir() -> Path:
    override = os.environ.get(_ENV_STORE_DIR, "").strip()
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[3] / "data" / "luxian_0609_antimicrobial_freeze"


def freeze_key(prompt: str) -> str:
    digest = hashlib.sha256()
    digest.update(FREEZE_SCHEMA_VERSION.encode("utf-8"))
    digest.update(b"\x1e")
    digest.update(prompt.encode("utf-8"))
    return digest.hexdigest()


def load_payload(namespace: str, key: str) -> Mapping[str, Any] | None:
    path = experiment_store_dir(default_store_dir()) / namespace / f"{key}.json"
    if not path.is_file():
        return None
    try:
        artifact = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        logger.warning("antimicrobial_freeze_unreadable namespace=%s key=%s", namespace, key[:12])
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
    try:
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
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
    except OSError:
        # 冻结只为复现，写不进去不影响本次结论。
        logger.warning("antimicrobial_freeze_unwritable namespace=%s key=%s", namespace, key[:12])
