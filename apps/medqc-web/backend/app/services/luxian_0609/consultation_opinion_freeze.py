"""会诊意见事实冻结：同一病例版本的「会诊意见 → 原子建议」只抽取一次。

问题证据（0910 样本实测）：同一病例、同一模型、3 轮重复执行，第一阶段输出的
建议条数与原文会变（C17 1/3/1、C25 8/8/9、C30 3/18/18），而
`recommendation_ref` 只是按响应数组顺序编号，因此 020/023 的**判定对象**每轮
都不同，下游任何判据都只能继承这份抖动。

工程结论（见《LX0609-03-01-04 会诊执行记录 口径标准与分歧处置清单》第十节）：
用确定性 Python 切分替代模型抽取无法同时保住一致性与质量（集合稳定 16/17 但
命中 4/17），唯一可行的是把**模型产出的第一阶段事实按病例版本冻结**。

职责边界：本模块是「会诊意见事实」的唯一所有者。首次运行由模型产生 payload，
校验通过后冻结；后续运行直接复用，不再调用模型；意见文书内容变化（指纹变化）
时失效并重新生成。除本模块外，任何层不得再生成或改写该建议集合。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import logging
import os
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from ..llm_experiment import experiment_store_dir


logger = logging.getLogger(__name__)

# v3：区分治疗动作与施治部位、会诊建议与原科室执行反馈。
# 抽取口径变化时旧冻结自动失效，避免重新运行仍复用旧的错误建议清单。
# v4（2026-10-22）：建议另抽执行范围、是否延续当前治疗、会诊文书内拒绝/暂缓，替代正则。
# v5（2026-10-22）：条件式须给出建议开头的条件原话（scope_quote）供结构核对。
# v6（2026-10-22）：第一阶段提示词加入用户确认的成对判定例子，旧冻结须重新抽取。
FREEZE_SCHEMA_VERSION = "consultation-opinion-freeze-v6"
_ENV_STORE_DIR = "LUXIAN_0609_OPINION_FREEZE_DIR"
_PAYLOAD_KEYS = ("episodes", "consultation_event_facts")
_SAFE_NAME = re.compile(r"[^0-9A-Za-z_.-]+")


@dataclass(frozen=True)
class FrozenOpinionPayload:
    """冻结命中或新建的结果。payload 即第一阶段模型原始输出。"""

    payload: Mapping[str, Any]
    fingerprint: str
    created_at: str
    state: str  # reused | created | rebuilt
    path: Path


def default_store_dir() -> Path:
    """默认落点：backend/data/luxian_0609_opinion_freeze（可用环境变量覆盖）。"""

    override = os.environ.get(_ENV_STORE_DIR, "").strip()
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[3] / "data" / "luxian_0609_opinion_freeze"


def documents_fingerprint(documents: Sequence[Mapping[str, Any]]) -> str:
    """按文书顺序计算内容指纹：任一文书的引用、时间或正文变化都会失效。

    顺序参与指纹，因为 episode_ref 与 recommendation_ref 的编号依赖输入顺序。
    """

    digest = hashlib.sha256()
    for document in documents:
        digest.update(
            "\x1f".join(
                str(document.get(key) or "")
                for key in ("ref", "time", "text", "event_group_ref")
            ).encode("utf-8")
        )
        digest.update(b"\x1e")
    return digest.hexdigest()


def _freeze_path(*, visit_id: str, store_dir: Path | None) -> Path:
    safe = _SAFE_NAME.sub("_", str(visit_id)).strip("_") or "unknown"
    return experiment_store_dir(store_dir or default_store_dir()) / f"{safe}.json"


def _coerce_store_dir(store_dir: Path | str | None) -> Path | None:
    if store_dir is None:
        return None
    return Path(store_dir)


def load_opinion_payload(
    *,
    visit_id: str,
    documents: Sequence[Mapping[str, Any]],
    store_dir: Path | str | None = None,
) -> FrozenOpinionPayload | None:
    """命中同一病例版本的冻结事实；缺失、指纹不符或内容损坏时返回 None。"""

    path = _freeze_path(visit_id=visit_id, store_dir=_coerce_store_dir(store_dir))
    if not path.is_file():
        return None
    fingerprint = documents_fingerprint(documents)
    try:
        artifact = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        logger.warning("consultation_opinion_freeze_unreadable visit=%s", visit_id)
        return None
    if not isinstance(artifact, Mapping):
        return None
    if artifact.get("schema_version") != FREEZE_SCHEMA_VERSION:
        return None
    if artifact.get("visit_id") != visit_id:
        return None
    if artifact.get("fingerprint") != fingerprint:
        return None
    payload = artifact.get("payload")
    if not isinstance(payload, Mapping) or not any(key in payload for key in _PAYLOAD_KEYS):
        return None
    return FrozenOpinionPayload(
        payload=payload,
        fingerprint=fingerprint,
        created_at=str(artifact.get("created_at") or ""),
        state="reused",
        path=path,
    )


def save_opinion_payload(
    *,
    visit_id: str,
    documents: Sequence[Mapping[str, Any]],
    payload: Mapping[str, Any],
    store_dir: Path | str | None = None,
    created_at: str | None = None,
) -> FrozenOpinionPayload:
    """写入冻结事实（原子替换）。已存在旧版本时状态记为 rebuilt。"""
    from ..llm_token_budget import context_budget_failed
    if context_budget_failed():
        return

    directory = _coerce_store_dir(store_dir) or default_store_dir()
    existing = load_opinion_payload(
        visit_id=visit_id, documents=documents, store_dir=directory
    )
    if existing is not None:
        # 首次写入者赢：同一文书版本的并发执行不得互相覆盖（否则冻结等于没冻结）。
        return existing
    path = _freeze_path(visit_id=visit_id, store_dir=directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    replaced = path.is_file()
    fingerprint = documents_fingerprint(documents)
    stamp = created_at or datetime.now().astimezone().isoformat(timespec="seconds")
    artifact = {
        "schema_version": FREEZE_SCHEMA_VERSION,
        "visit_id": visit_id,
        "fingerprint": fingerprint,
        "created_at": stamp,
        "payload": payload,
    }
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)
    return FrozenOpinionPayload(
        payload=payload,
        fingerprint=fingerprint,
        created_at=stamp,
        state="rebuilt" if replaced else "created",
        path=path,
    )


def reset_opinion_freeze(
    *, visit_id: str, store_dir: Path | str | None = None
) -> bool:
    """显式清除某病例的冻结事实（下次运行将由模型重新生成）。"""

    path = _freeze_path(visit_id=visit_id, store_dir=_coerce_store_dir(store_dir))
    if not path.is_file():
        return False
    path.unlink()
    return True
