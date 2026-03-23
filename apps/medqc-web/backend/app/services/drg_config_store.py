from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from threading import RLock
from typing import Any, Dict, List, Optional
from uuid import uuid4


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat() + "Z"


def _default_config() -> Dict[str, Any]:
    return {
        "region": "sichuan",
        "engine": "OpenDRG",
        "baseRate": 10000,
        "hospitalCoefficient": 1.2,
        "regionCoefficient": 1.05,
        "effectiveDate": "2024-01-01",
        "lowRateThreshold": 3,
        "highRateThreshold": 30,
        "enableCCMCC": True,
        "enableAutoSuggestion": True,
    }


def _new_version_id() -> str:
    return f"drgcfg-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}"


@dataclass
class ConsistencySummary:
    matched_count: int
    valid_count: int
    consistency_rate: float
    difference_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "matched_count": self.matched_count,
            "valid_count": self.valid_count,
            "consistency_rate": self.consistency_rate,
            "difference_count": self.difference_count,
        }


class DRGConfigStore:
    """File-backed DRG grouper configuration store for config/version/rollback."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._path = (
            Path(__file__).resolve().parents[2]
            / "data"
            / "drg_grouper_config_store.json"
        )
        self._state: Dict[str, Any] = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        if self._path.exists():
            try:
                raw = json.loads(self._path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    return raw
            except Exception:
                pass
        initial = {
            "draft": _default_config(),
            "published_version_id": None,
            "versions": [],
            "audit_logs": [],
            "latest_consistency_report": None,
        }
        self._persist(initial)
        return initial

    def _persist(self, state: Optional[Dict[str, Any]] = None) -> None:
        current = state if state is not None else self._state
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(current, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_current(self) -> Dict[str, Any]:
        with self._lock:
            published = self._find_version(self._state.get("published_version_id"))
            latest = self._latest_version()
            return {
                "draft": deepcopy(self._state.get("draft", _default_config())),
                "published_version_id": self._state.get("published_version_id"),
                "published_config": deepcopy(published["config"]) if published else None,
                "latest_version_id": latest["version_id"] if latest else None,
                "latest_consistency_report": deepcopy(self._state.get("latest_consistency_report")),
            }

    def save_draft(self, config: Dict[str, Any], operator: str, change_summary: str) -> Dict[str, Any]:
        with self._lock:
            self._state["draft"] = deepcopy(config)
            audit_entry = {
                "action": "save",
                "version_id": self._state.get("published_version_id"),
                "operator": operator,
                "operated_at": _now_iso(),
                "change_summary": change_summary,
            }
            self._state.setdefault("audit_logs", []).append(audit_entry)
            self._persist()
            return {
                "draft": deepcopy(self._state["draft"]),
                "audit": audit_entry,
            }

    def publish(self, operator: str, change_summary: str) -> Dict[str, Any]:
        with self._lock:
            version_id = _new_version_id()
            now = _now_iso()
            version = {
                "version_id": version_id,
                "config": deepcopy(self._state.get("draft", _default_config())),
                "operator": operator,
                "operated_at": now,
                "change_summary": change_summary,
                "published_at": now,
            }
            self._state.setdefault("versions", []).append(version)
            self._state["published_version_id"] = version_id
            self._state.setdefault("audit_logs", []).append(
                {
                    "action": "publish",
                    "version_id": version_id,
                    "operator": operator,
                    "operated_at": now,
                    "change_summary": change_summary,
                }
            )
            self._persist()
            return deepcopy(version)

    def list_versions(self) -> List[Dict[str, Any]]:
        with self._lock:
            published_id = self._state.get("published_version_id")
            versions = []
            for item in self._state.get("versions", []):
                versions.append(
                    {
                        "version_id": item.get("version_id"),
                        "operator": item.get("operator"),
                        "operated_at": item.get("operated_at"),
                        "change_summary": item.get("change_summary"),
                        "published_at": item.get("published_at"),
                        "is_published": item.get("version_id") == published_id,
                    }
                )
            versions.sort(key=lambda v: v.get("published_at") or "", reverse=True)
            return versions

    def get_version(self, version_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            item = self._find_version(version_id)
            if not item:
                return None
            return deepcopy(item)

    def rollback(self, version_id: str, operator: str, change_summary: str) -> Dict[str, Any]:
        with self._lock:
            target = self._find_version(version_id)
            if not target:
                raise KeyError(version_id)
            now = _now_iso()
            self._state["published_version_id"] = version_id
            self._state["draft"] = deepcopy(target["config"])
            self._state.setdefault("audit_logs", []).append(
                {
                    "action": "rollback",
                    "version_id": version_id,
                    "operator": operator,
                    "operated_at": now,
                    "change_summary": change_summary,
                }
            )
            self._persist()
            return {
                "version_id": version_id,
                "operator": operator,
                "operated_at": now,
                "change_summary": change_summary,
                "config": deepcopy(target["config"]),
            }

    def get_audit_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            logs = list(self._state.get("audit_logs", []))
            logs.sort(key=lambda item: item.get("operated_at") or "", reverse=True)
            return logs[: max(1, limit)]

    def run_consistency_check(
        self,
        samples: List[Dict[str, Any]],
        operator: str,
        version_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        with self._lock:
            check_version_id = version_id or self._state.get("published_version_id")
            valid_count = 0
            matched_count = 0
            diff_items: List[Dict[str, Any]] = []

            for idx, item in enumerate(samples):
                hospital_group = str(item.get("hospital_group") or "").strip()
                insurance_group = str(item.get("insurance_group") or "").strip()
                case_key = str(item.get("case_key") or item.get("admission_id") or f"sample-{idx + 1}")
                if not hospital_group or not insurance_group:
                    continue
                valid_count += 1
                if hospital_group == insurance_group:
                    matched_count += 1
                else:
                    diff_items.append(
                        {
                            "case_key": case_key,
                            "hospital_group": hospital_group,
                            "insurance_group": insurance_group,
                        }
                    )

            rate = round((matched_count / valid_count) * 100, 2) if valid_count > 0 else 0.0
            summary = ConsistencySummary(
                matched_count=matched_count,
                valid_count=valid_count,
                consistency_rate=rate,
                difference_count=len(diff_items),
            )
            report = {
                "version_id": check_version_id,
                "operator": operator,
                "operated_at": _now_iso(),
                "formula": "一致率 = 匹配成功样本数 / 有效对照样本数",
                "summary": summary.to_dict(),
                "differences": diff_items,
                "samples_preview": samples[:50],
            }
            self._state["latest_consistency_report"] = deepcopy(report)
            self._state.setdefault("audit_logs", []).append(
                {
                    "action": "consistency_check",
                    "version_id": check_version_id,
                    "operator": operator,
                    "operated_at": report["operated_at"],
                    "change_summary": f"一致率校验: {rate}%",
                }
            )
            self._persist()
            return report

    def _find_version(self, version_id: Optional[str]) -> Optional[Dict[str, Any]]:
        if not version_id:
            return None
        for item in self._state.get("versions", []):
            if item.get("version_id") == version_id:
                return item
        return None

    def _latest_version(self) -> Optional[Dict[str, Any]]:
        versions = self._state.get("versions", [])
        if not versions:
            return None
        return sorted(versions, key=lambda item: item.get("published_at") or "", reverse=True)[0]


_STORE: Optional[DRGConfigStore] = None


def get_drg_config_store() -> DRGConfigStore:
    global _STORE
    if _STORE is None:
        _STORE = DRGConfigStore()
    return _STORE

