from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import random
from typing import Any, Dict, List, Optional, Tuple


def _utc_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(tzinfo=None).isoformat() + "Z"


def _now() -> datetime:
    return datetime.now(timezone.utc)


PRIMARY_DIAG_POOL: List[Tuple[str, str]] = [
    ("I21.001", "急性前壁ST段抬高型心肌梗死"),
    ("J18.901", "社区获得性肺炎"),
    ("J44.901", "慢性阻塞性肺疾病急性加重"),
    ("E11.901", "2型糖尿病伴并发症"),
    ("N18.901", "慢性肾脏病"),
    ("K80.201", "胆囊结石伴急性胆囊炎"),
]

SECONDARY_DIAG_POOL: List[Tuple[str, str]] = [
    ("I10.x01", "原发性高血压"),
    ("E11.901", "2型糖尿病伴并发症"),
    ("I50.001", "心力衰竭"),
    ("J96.001", "急性呼吸衰竭"),
]

PROCEDURE_POOL: List[Tuple[str, str]] = [
    ("36.0700", "经皮冠状动脉介入术"),
    ("88.5600", "冠状动脉造影"),
    ("51.2300", "腹腔镜胆囊切除术"),
]

DEPARTMENTS = [
    "心内科",
    "呼吸与危重症医学科",
    "内分泌科",
    "肾内科",
    "普外科",
    "骨科",
    "神经内科",
]

FIRST_NAMES = ["张", "王", "李", "赵", "刘", "陈", "杨", "黄", "周", "吴"]
LAST_NAMES = ["伟", "芳", "娜", "敏", "静", "丽", "强", "磊", "军", "洋", "涛", "明", "超", "霞"]


@dataclass
class StoryCases:
    high_risk_loss: str
    coding_conflict: str
    high_cost_alert: str


class DemoDRGStore:
    """A small in-memory store to support DRG/DIP demo endpoints.

    This store is intentionally self-contained (no Supabase/OpenDRG dependency)
    so that demo pages can work out-of-the-box.
    """

    def __init__(self, seed: int = 20251218, size: int = 50):
        self.seed = int(seed)
        self.size = int(size)
        self._rand = random.Random(self.seed)

        self._cases: Dict[str, Dict[str, Any]] = {}
        self._suggestions: Dict[int, Dict[str, Any]] = {}
        self._alerts: Dict[int, Dict[str, Any]] = {}
        self._grouping_history: Dict[str, List[Dict[str, Any]]] = {}

        self._next_front_page_id = 1
        self._next_suggestion_id = 1001
        self._next_alert_id = 5001
        self._next_grouping_id = 9001

        self.story_cases: Optional[StoryCases] = None

        self._init_data()

    def _name(self) -> str:
        r = self._rand
        return r.choice(FIRST_NAMES) + r.choice(LAST_NAMES) + r.choice(LAST_NAMES)

    def _init_data(self) -> None:
        base_dt = _now() - timedelta(days=60)

        for idx in range(self.size):
            admission_id = f"ADM2025{idx + 1:05d}"
            patient_id = f"PID{idx + 1:06d}"
            patient_name = self._name()
            age = self._rand.randint(18, 90)
            gender = self._rand.choice(["M", "F"])

            pd_code, pd_name = self._rand.choice(PRIMARY_DIAG_POOL)

            sec_count = self._rand.choices([0, 1, 2], weights=[40, 45, 15])[0]
            secondary = self._rand.sample(SECONDARY_DIAG_POOL, k=sec_count) if sec_count else []

            proc_count = self._rand.choices([0, 1], weights=[55, 45])[0]
            procs = self._rand.sample(PROCEDURE_POOL, k=proc_count) if proc_count else []

            admit_dt = base_dt + timedelta(days=self._rand.randint(0, 55))
            hospital_days = max(2, int(self._rand.gauss(8 + sec_count * 2, 2)))
            discharge_dt = admit_dt + timedelta(days=hospital_days)

            base_cost = 18000
            if pd_code.startswith("I21"):
                base_cost = 45000
            elif pd_code.startswith("J44"):
                base_cost = 26000
            elif pd_code.startswith("N18"):
                base_cost = 22000
            elif pd_code.startswith("K80"):
                base_cost = 20000

            total_cost = round(base_cost * (1.0 + 0.12 * sec_count + 0.2 * proc_count) * self._rand.uniform(0.75, 1.35), 2)

            main_proc_code = procs[0][0] if procs else None
            main_proc_name = procs[0][1] if procs else None

            front_page_id = self._next_front_page_id
            self._next_front_page_id += 1

            coding_status = self._rand.choices(["draft", "completed", "reviewed"], weights=[35, 50, 15])[0]
            record = {
                "front_page_id": front_page_id,
                "admission_id": admission_id,
                "patient_id": patient_id,
                "patient_name": patient_name,
                "patient_age": age,
                "patient_gender": gender,
                "primary_diagnosis_code": pd_code,
                "primary_diagnosis_name": pd_name,
                "main_procedure_code": main_proc_code,
                "main_procedure_name": main_proc_name,
                "main_procedure_date": _utc_iso(admit_dt + timedelta(days=1)) if main_proc_code else None,
                "admission_route": self._rand.choice(["急诊", "门诊", "转入"]),
                "discharge_status": self._rand.choice(["治愈", "好转", "未愈"]),
                "total_hospital_days": hospital_days,
                "total_cost": total_cost,
                "coder_id": self._rand.choice(["coder_001", "coder_002", None]),
                "coding_started_at": _utc_iso(admit_dt + timedelta(hours=2)),
                "coding_completed_at": _utc_iso(admit_dt + timedelta(days=1, hours=3)),
                "coding_status": coding_status,
                "reviewer_id": self._rand.choice(["reviewer_001", None]),
                "reviewed_at": _utc_iso(admit_dt + timedelta(days=2)) if coding_status == "reviewed" else None,
                "review_status": self._rand.choice(["pending", "approved", "rejected"]),
                "created_at": _utc_iso(admit_dt),
                "updated_at": _utc_iso(discharge_dt),
                "secondary_diagnoses": [
                    {
                        "code": code,
                        "name": name,
                        "sequence": i + 1,
                        "is_complication": True if code in {"E11.901", "I50.001", "J96.001"} else False,
                    }
                    for i, (code, name) in enumerate(secondary)
                ],
                "procedures": [
                    {
                        "code": code,
                        "name": name,
                        "sequence": i + 1,
                        "procedure_date": _utc_iso(admit_dt + timedelta(days=1 + i)),
                    }
                    for i, (code, name) in enumerate(procs)
                ],
                "department": self._rand.choice(DEPARTMENTS),
            }

            self._cases[admission_id] = record

        # Seed suggestions and alerts
        admission_ids = list(self._cases.keys())
        for _ in range(max(10, self.size // 3)):
            admission_id = self._rand.choice(admission_ids)
            self._create_suggestion(admission_id)

        for _ in range(max(10, self.size // 3)):
            admission_id = self._rand.choice(admission_ids)
            self._create_alert(admission_id)

        self.story_cases = StoryCases(
            high_risk_loss=admission_ids[0],
            coding_conflict=admission_ids[1],
            high_cost_alert=admission_ids[2],
        )

    def _create_suggestion(self, admission_id: str) -> None:
        now = _now()
        sid = self._next_suggestion_id
        self._next_suggestion_id += 1

        suggestion_type = self._rand.choice(
            ["missing_diagnosis", "procedure_missing", "complication_marking", "logic_conflict"]
        )

        msg_map = {
            "missing_diagnosis": "病程记录提示存在并发症，建议补充次诊断（演示）",
            "procedure_missing": "可能遗漏关键手术操作编码，建议核对手术记录（演示）",
            "complication_marking": "并发症标记可能影响入组，建议核对是否标记为并发症（演示）",
            "logic_conflict": "主诊断与主手术逻辑冲突，建议调整顺序或更换主诊断（演示）",
        }

        self._suggestions[sid] = {
            "suggestion_id": sid,
            "admission_id": admission_id,
            "suggestion_type": suggestion_type,
            "diagnosis_code": None,
            "diagnosis_name": None,
            "message": msg_map.get(suggestion_type, "编码建议（演示）"),
            "evidence": "[DEMO] 证据片段：...",
            "severity": self._rand.choice(["info", "warning", "error"]),
            "status": self._rand.choices(["pending", "accepted", "rejected"], weights=[70, 15, 15])[0],
            "created_at": _utc_iso(now - timedelta(hours=self._rand.randint(1, 240))),
        }

    def _create_alert(self, admission_id: str) -> None:
        now = _now()
        aid = self._next_alert_id
        self._next_alert_id += 1

        alert_type = self._rand.choice(["cost_overrun", "los_long", "coding_abnormal", "profit_loss"])
        msg_map = {
            "cost_overrun": "费用消耗率偏高，建议关注费用结构（演示）",
            "los_long": "住院日可能超标，请关注治疗路径（演示）",
            "coding_abnormal": "编码存在异常风险，请复核（演示）",
            "profit_loss": "预计亏损病例，请尽快核对入组与费用（演示）",
        }

        level = self._rand.choice(["info", "warning", "critical"])

        self._alerts[aid] = {
            "alert_id": aid,
            "admission_id": admission_id,
            "alert_type": alert_type,
            "alert_level": level,
            "message": msg_map.get(alert_type, "预警（演示）"),
            "metric_value": None,
            "threshold_value": None,
            "status": self._rand.choices(["pending", "acknowledged", "resolved"], weights=[65, 20, 15])[0],
            "triggered_at": _utc_iso(now - timedelta(hours=self._rand.randint(1, 240))),
        }

    # ==================== case front page ====================

    def list_cases(self, limit: int = 100) -> List[Dict[str, Any]]:
        items = list(self._cases.values())
        items.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
        return items[: max(1, min(limit, 500))]

    def get_case_detail(self, admission_id: str) -> Optional[Dict[str, Any]]:
        return self._cases.get(admission_id)

    def upsert_case(self, admission_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
        existing = self._cases.get(admission_id)
        if existing is None:
            # Create minimal case
            now = _now()
            front_page_id = self._next_front_page_id
            self._next_front_page_id += 1
            existing = {
                "front_page_id": front_page_id,
                "admission_id": admission_id,
                "patient_id": patch.get("patient_id") or f"PID{front_page_id:06d}",
                "patient_name": patch.get("patient_name") or self._name(),
                "patient_age": int(patch.get("patient_age") or 50),
                "patient_gender": patch.get("patient_gender") or "M",
                "primary_diagnosis_code": patch.get("primary_diagnosis_code") or "J18.901",
                "primary_diagnosis_name": patch.get("primary_diagnosis_name") or "社区获得性肺炎",
                "coding_status": patch.get("coding_status") or "draft",
                "review_status": patch.get("review_status") or "pending",
                "created_at": _utc_iso(now),
                "updated_at": _utc_iso(now),
            }
            self._cases[admission_id] = existing

        existing.update({k: v for k, v in patch.items() if v is not None})
        existing["updated_at"] = _utc_iso(_now())
        return existing

    # ==================== suggestions ====================

    def list_suggestions(self, admission_id: Optional[str], status: Optional[str], limit: int) -> List[Dict[str, Any]]:
        items = list(self._suggestions.values())
        if admission_id:
            items = [s for s in items if s.get("admission_id") == admission_id]
        if status:
            items = [s for s in items if s.get("status") == status]
        items.sort(key=lambda x: x.get("created_at") or "", reverse=True)
        return items[: max(1, min(limit, 200))]

    def update_suggestion_status(self, suggestion_id: int, status: str) -> bool:
        item = self._suggestions.get(int(suggestion_id))
        if not item:
            return False
        item["status"] = status
        return True

    # ==================== alerts ====================

    def list_alerts(self, admission_id: Optional[str], alert_level: Optional[str], status: Optional[str], limit: int) -> List[Dict[str, Any]]:
        items = list(self._alerts.values())
        if admission_id:
            items = [a for a in items if a.get("admission_id") == admission_id]
        if alert_level:
            items = [a for a in items if a.get("alert_level") == alert_level]
        if status:
            items = [a for a in items if a.get("status") == status]
        items.sort(key=lambda x: x.get("triggered_at") or "", reverse=True)
        return items[: max(1, min(limit, 200))]

    def update_alert_status(self, alert_id: int, status: str) -> bool:
        item = self._alerts.get(int(alert_id))
        if not item:
            return False
        item["status"] = status
        return True

    # ==================== grouping ====================

    def append_grouping_history(self, admission_id: str, grouping: Dict[str, Any]) -> Dict[str, Any]:
        gid = self._next_grouping_id
        self._next_grouping_id += 1

        hist_item = {
            "grouping_id": gid,
            "drg_code": grouping.get("drg_code"),
            "drg_name": grouping.get("drg_name"),
            "weight": grouping.get("weight"),
            "baseline_payment": grouping.get("baseline_payment"),
            "actual_cost": grouping.get("actual_cost"),
            "profit_margin": grouping.get("profit_margin"),
            "version": len(self._grouping_history.get(admission_id, [])) + 1,
            "is_latest": True,
            "grouped_at": _utc_iso(_now()),
        }

        existing = self._grouping_history.get(admission_id, [])
        for x in existing:
            x["is_latest"] = False
        existing.insert(0, hist_item)
        self._grouping_history[admission_id] = existing
        return hist_item

    def get_grouping_history(self, admission_id: str) -> List[Dict[str, Any]]:
        return list(self._grouping_history.get(admission_id, []))


_store: Optional[DemoDRGStore] = None


def get_demo_drg_store() -> DemoDRGStore:
    global _store
    if _store is None:
        _store = DemoDRGStore()
    return _store
