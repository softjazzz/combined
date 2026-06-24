from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional


class DRGConfigVersionNotFoundError(KeyError):
    """Raised when a requested DRG config version does not exist."""


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def get_current_config(store) -> Dict[str, Any]:
    return store.get_current()


def save_draft_config(store, *, config: Dict[str, Any], operator: str, change_summary: str) -> Dict[str, Any]:
    return store.save_draft(
        config=deepcopy(config),
        operator=_clean_text(operator),
        change_summary=_clean_text(change_summary),
    )


def publish_config(store, *, operator: str, change_summary: str) -> Dict[str, Any]:
    return store.publish(
        operator=_clean_text(operator),
        change_summary=_clean_text(change_summary),
    )


def list_versions(store, *, limit: int) -> Dict[str, Any]:
    versions = store.list_versions()[:limit]
    return {"items": versions, "total": len(versions)}


def get_version_detail(store, *, version_id: str) -> Dict[str, Any]:
    detail = store.get_version(version_id)
    if detail is None:
        raise DRGConfigVersionNotFoundError(version_id)
    return detail


def rollback_config(store, *, version_id: str, operator: str, change_summary: str) -> Dict[str, Any]:
    try:
        return store.rollback(
            version_id=version_id,
            operator=_clean_text(operator),
            change_summary=_clean_text(change_summary),
        )
    except KeyError as exc:
        raise DRGConfigVersionNotFoundError(version_id) from exc


def list_audit_logs(store, *, limit: int) -> Dict[str, Any]:
    logs = store.get_audit_logs(limit=limit)
    return {"items": logs, "total": len(logs)}


def run_consistency_check(
    store,
    *,
    operator: str,
    version_id: Optional[str],
    samples: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return store.run_consistency_check(
        samples=samples,
        operator=_clean_text(operator),
        version_id=version_id,
    )

