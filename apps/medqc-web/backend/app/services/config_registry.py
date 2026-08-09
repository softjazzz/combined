"""
同步配置注册中心（PG 优先，非生产环境允许文件回退）。
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..database.connection import engine

logger = logging.getLogger(__name__)

_CONFIG_DIR = Path(__file__).parent.parent / "data"
_REGISTRY_FILE = _CONFIG_DIR / "sync_config_registry.json"
_TABLE_NAME = "sync_config_registry"


def _pg_required_in_current_env() -> bool:
    env = str(os.getenv("ENV") or "").strip().lower()
    return env in {"prod", "production"}


def _load_file_registry() -> dict[str, Any]:
    if not _REGISTRY_FILE.exists():
        return {}
    try:
        with open(_REGISTRY_FILE, "r", encoding="utf-8") as fp:
            raw = json.load(fp)
        return raw if isinstance(raw, dict) else {}
    except Exception as exc:
        logger.warning("读取配置注册中心文件失败: %s", exc)
        return {}


def _save_file_registry(payload: dict[str, Any]) -> bool:
    try:
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(_REGISTRY_FILE, "w", encoding="utf-8") as fp:
            json.dump(payload, fp, ensure_ascii=False, indent=2)
        return True
    except Exception as exc:
        logger.warning("写入配置注册中心文件失败: %s", exc)
        return False


def get_config(namespace: str, key: str) -> dict[str, Any] | list[Any] | str | int | float | bool | None:
    ns = str(namespace or "").strip()
    cfg_key = str(key or "").strip()
    if not ns or not cfg_key:
        return None

    if engine is not None:
        try:
            with Session(engine) as session:
                row = session.execute(
                    text(
                        f"""
                        SELECT payload_json
                        FROM {_TABLE_NAME}
                        WHERE namespace = :namespace
                          AND config_key = :config_key
                        LIMIT 1
                        """
                    ),
                    {"namespace": ns, "config_key": cfg_key},
                ).mappings().first()
            if row and str(row.get("payload_json") or "").strip():
                try:
                    return json.loads(str(row.get("payload_json")))
                except Exception as exc:
                    logger.warning("解析配置失败 namespace=%s key=%s error=%s", ns, cfg_key, exc)
                    return None
            return None
        except Exception as exc:
            if _pg_required_in_current_env():
                raise RuntimeError(f"读取配置失败: {ns}/{cfg_key}") from exc
            logger.warning("读取 PG 配置失败，回退文件: namespace=%s key=%s error=%s", ns, cfg_key, exc)

    if _pg_required_in_current_env():
        return None

    file_store = _load_file_registry()
    ns_bucket = file_store.get(ns)
    if not isinstance(ns_bucket, dict):
        return None
    item = ns_bucket.get(cfg_key)
    if not isinstance(item, dict):
        return None
    return item.get("payload")


def set_config(
    namespace: str,
    key: str,
    payload: dict[str, Any] | list[Any] | str | int | float | bool | None,
    *,
    updated_by: str = "system",
    source: str = "unknown",
    change_reason: str = "",
) -> bool:
    ns = str(namespace or "").strip()
    cfg_key = str(key or "").strip()
    if not ns or not cfg_key:
        return False

    payload_json = json.dumps(payload, ensure_ascii=False)

    if engine is not None:
        try:
            with Session(engine) as session:
                session.execute(
                    text(
                        f"""
                        INSERT INTO {_TABLE_NAME} (
                            namespace, config_key, payload_json, updated_by, source, change_reason, updated_at
                        )
                        VALUES (
                            :namespace, :config_key, :payload_json, :updated_by, :source, :change_reason, CURRENT_TIMESTAMP
                        )
                        ON CONFLICT (namespace, config_key) DO UPDATE SET
                            payload_json = EXCLUDED.payload_json,
                            updated_by = EXCLUDED.updated_by,
                            source = EXCLUDED.source,
                            change_reason = EXCLUDED.change_reason,
                            updated_at = CURRENT_TIMESTAMP
                        """
                    ),
                    {
                        "namespace": ns,
                        "config_key": cfg_key,
                        "payload_json": payload_json,
                        "updated_by": str(updated_by or "system")[:128],
                        "source": str(source or "unknown")[:128],
                        "change_reason": str(change_reason or "")[:255],
                    },
                )
                session.commit()
            return True
        except Exception as exc:
            if _pg_required_in_current_env():
                raise RuntimeError(f"写入配置失败: {ns}/{cfg_key}") from exc
            logger.warning("写入 PG 配置失败，回退文件: namespace=%s key=%s error=%s", ns, cfg_key, exc)

    if _pg_required_in_current_env():
        return False

    file_store = _load_file_registry()
    bucket = file_store.get(ns)
    if not isinstance(bucket, dict):
        bucket = {}
        file_store[ns] = bucket
    bucket[cfg_key] = {
        "payload": payload,
        "updated_by": str(updated_by or "system")[:128],
        "source": str(source or "unknown")[:128],
        "change_reason": str(change_reason or "")[:255],
    }
    return _save_file_registry(file_store)
