"""
同步运行历史持久化服务

使用 JSON 文件存储最近 N 次运行记录，便于运维追溯。
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parent.parent / "data" / "sync_run_history.json"
MAX_ITEMS = 300
_LOCK = threading.Lock()


def _load_records() -> list[dict[str, Any]]:
    if not CONFIG_PATH.exists():
        return []
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
    except Exception as exc:
        logger.warning("读取同步历史失败，已忽略: %s", exc)
    return []


def _save_records(records: list[dict[str, Any]]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def append_sync_run_record(record: dict[str, Any], max_items: int = MAX_ITEMS) -> None:
    with _LOCK:
        records = _load_records()
        records.insert(0, record)
        records = records[:max_items]
        _save_records(records)


def list_sync_run_records(
    *,
    source: Optional[str] = None,
    tier: Optional[str] = None,
    limit: int = 50,
) -> dict[str, Any]:
    with _LOCK:
        records = _load_records()

    filtered = records
    if source:
        filtered = [item for item in filtered if str(item.get("source")) == source]
    if tier:
        filtered = [item for item in filtered if str(item.get("tier")) == tier]

    safe_limit = max(1, min(int(limit), 500))
    items = filtered[:safe_limit]

    return {
        "items": items,
        "total": len(filtered),
        "limit": safe_limit,
    }
