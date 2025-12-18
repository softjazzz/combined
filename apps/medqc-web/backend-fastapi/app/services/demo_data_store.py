"""Demo 数据存储与生成

用于 DRG/DIP 演示环境（DEMO_MODE=true）。
在进程内生成可复现的 Mock 数据，并支持状态流转（handle 后可回查）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import random
from typing import Any, Dict, List, Optional

try:
    from loguru import logger
except Exception:
    import logging

    logger = logging.getLogger(__name__)

from app.config import settings


DEPARTMENTS = [
    "心内科",
    "呼吸与危重症医学科",
    "内分泌科",
    "肾内科",
    "普外科",
    "骨科",
    "神经内科",
    "重症医学科",
]


PRIMARY_DIAG_POOL = [
    ("I21.001", "急性前壁ST段抬高型心肌梗死"),
    ("I20.001", "不稳定型心绞痛"),
    ("I10.x01", "高血压3级"),
    ("I50.001", "心力衰竭"),
    ("J18.901", "社区获得性肺炎"),
    ("J44.901", "慢性阻塞性肺疾病急性加重"),
    ("J96.001", "急性呼吸衰竭"),
    ("E11.901", "2型糖尿病伴并发症"),
    ("E10.901", "1型糖尿病"),
    ("N18.901", "慢性肾脏病"),
    ("K80.201", "胆囊结石伴急性胆囊炎"),
]


SECONDARY_DIAG_POOL = [
    ("I10.x01", "原发性高血压"),
    ("E11.901", "2型糖尿病伴并发症"),
    ("I50.001", "心力衰竭"),
    ("J96.001", "急性呼吸衰竭"),
    ("N18.901", "慢性肾脏病"),
    ("E78.501", "高脂血症"),
]


PROCEDURE_POOL = [
    ("36.0700", "经皮冠状动脉介入术"),
    ("88.5600", "冠状动脉造影"),
    ("37.2200", "心脏起搏器置入术"),
    ("45.1300", "结肠镜检查"),
    ("51.2300", "腹腔镜胆囊切除术"),
]


ALERT_TYPE_POOL = [
    "cost_overrun",
    "los_long",
    "coding_abnormal",
    "profit_loss",
]


SUGGESTION_TYPE_POOL = [
    "missing_diagnosis",
    "procedure_missing",
    "complication_marking",
    "logic_conflict",
]


FIRST_NAMES = ["张", "王", "李", "赵", "刘", "陈", "杨", "黄", "周", "吴"]
LAST_NAMES = ["伟", "芳", "娜", "敏", "静", "丽", "强", "磊", "军", "洋", "涛", "明", "超", "霞"]


def _now_cn() -> datetime:
    return datetime.now(timezone(timedelta(hours=8)))


def _dt_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(tzinfo=None).isoformat() + "Z"


def _rand_name(r: random.Random) -> str:
    return r.choice(FIRST_NAMES) + r.choice(LAST_NAMES) + r.choice(LAST_NAMES)


@dataclass
class DemoStoryCases:
    high_risk_loss: str
    coding_conflict: str
    high_cost_alert: str


class DemoDataStore:
    """进程内 Demo 数据存储（可复现 + 可变状态）。"""

    def __init__(self, seed: int, size: int):
        self.seed = int(seed)
        self.size = int(size)
        self._rand = random.Random(self.seed)

        self._cases: Dict[str, Dict[str, Any]] = {}
        self._icd10: List[Dict[str, Any]] = []
        self._icd9: List[Dict[str, Any]] = []

        self._coding_suggestions: Dict[int, Dict[str, Any]] = {}
        self._drg_alerts: Dict[int, Dict[str, Any]] = {}
        self._grouping_history: Dict[str, List[Dict[str, Any]]] = {}

        self._next_front_page_id = 1
        self._next_suggestion_id = 1001
        self._next_alert_id = 5001
        self._next_grouping_id = 9001

        self.story_cases: Optional[DemoStoryCases] = None

        self._init_data()

    def _init_data(self) -> None:
        self._build_icd_dicts()
        self._build_cases()
        self._build_suggestions()
        self._build_alerts()
        self._build_grouping_history()
        self._pick_story_cases()

        logger.info(
            f"[DEMO] DemoDataStore initialized: seed={self.seed}, size={self.size}, "
            f"cases={len(self._cases)}, icd10={len(self._icd10)}, icd9={len(self._icd9)}, "
            f"suggestions={len(self._coding_suggestions)}, alerts={len(self._drg_alerts)}"
        )

    def _build_icd_dicts(self) -> None:
        # ICD10: 基础 + 扩展
        base = []
        for code, name in PRIMARY_DIAG_POOL + SECONDARY_DIAG_POOL:
            base.append({"code": code, "name": name, "category": "diagnosis", "notes": None})

        # 扩展一些通用条目，保证搜索体验
        for i in range(1, 520):
            code = f"Z{i:02d}.9"
            name = f"其他影响健康状态的因素 {i}"
            base.append({"code": code, "name": name, "category": "diagnosis", "notes": None})

        self._icd10 = base

        # ICD9 手术
        procs = []
        for code, name in PROCEDURE_POOL:
            procs.append({"code": code, "name": name, "category": "procedure", "notes": None})

        for i in range(1, 220):
            code = f"99.{i:04d}"
            name = f"其他操作 {i}"
            procs.append({"code": code, "name": name, "category": "procedure", "notes": None})

        self._icd9 = procs

    def _build_cases(self) -> None:
        base_date = _now_cn() - timedelta(days=60)

        for idx in range(self.size):
            admission_id = f"ADM2025{idx + 1:05d}"
            patient_id = f"PID{idx + 1:06d}"
            patient_name = _rand_name(self._rand)
            department = self._rand.choice(DEPARTMENTS)
            age = self._rand.randint(18, 90)
            gender = self._rand.choice(["M", "F"])

            pd_code, pd_name = self._rand.choice(PRIMARY_DIAG_POOL)

            # 次诊断 0-3
            sec_count = self._rand.choices([0, 1, 2, 3], weights=[25, 40, 25, 10])[0]
            sec_diags = self._rand.sample(SECONDARY_DIAG_POOL, k=sec_count) if sec_count else []

            # 手术 0-2
            proc_count = self._rand.choices([0, 1, 2], weights=[45, 40, 15])[0]
            procs = self._rand.sample(PROCEDURE_POOL, k=proc_count) if proc_count else []

            admission_dt = base_date + timedelta(days=self._rand.randint(0, 55))

            # 住院日与费用：按主诊断粗略控制分布
            base_los = 6
            if pd_code.startswith("I21") or pd_code.startswith("J96"):
                base_los = 12
            elif pd_code.startswith("J18"):
                base_los = 9
            elif pd_code.startswith("K80"):
                base_los = 7

            total_hospital_days = max(2, int(self._rand.gauss(base_los + sec_count * 2, 2)))
            discharge_dt = admission_dt + timedelta(days=total_hospital_days)

            # 费用：基础 + 波动 + 并发症/手术加成
            base_cost = 12000
            if pd_code.startswith("I21"):
                base_cost = 45000
            elif pd_code.startswith("J96"):
                base_cost = 60000
            elif pd_code.startswith("J18"):
                base_cost = 18000
            elif pd_code.startswith("E11") or pd_code.startswith("N18"):
                base_cost = 16000

            cost = base_cost * (1.0 + 0.12 * sec_count + 0.18 * proc_count)
            cost = cost * self._rand.uniform(0.75, 1.35)
            total_cost = round(cost, 2)

            main_proc_code = procs[0][0] if procs else None
            main_proc_name = procs[0][1] if procs else None

            front_page_id = self._next_front_page_id
            self._next_front_page_id += 1

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
                "main_procedure_date": _dt_iso(admission_dt + timedelta(days=1)) if main_proc_code else None,
                "admission_route": self._rand.choice(["急诊", "门诊", "转入"]),
                "discharge_status": self._rand.choice(["治愈", "好转", "未愈", "死亡"]),
                "total_hospital_days": total_hospital_days,
                "total_cost": total_cost,
                "coding_status": self._rand.choice(["draft", "completed", "reviewed"]),
                "review_status": self._rand.choice(["pending", "approved", "rejected"]),
                "coder_id": self._rand.choice(["coder_001", "coder_002", "coder_003", None]),
                "reviewer_id": self._rand.choice(["reviewer_001", "reviewer_002", None]),
                "coding_started_at": _dt_iso(admission_dt + timedelta(hours=2)),
                "coding_completed_at": _dt_iso(admission_dt + timedelta(days=1, hours=3)),
                "created_at": _dt_iso(admission_dt),
                "updated_at": _dt_iso(discharge_dt),
                "secondary_diagnoses": [
                    {
                        "code": c,
                        "name": n,
                        "sequence": i + 1,
                        "is_complication": True if c in {"E11.901", "I50.001", "J96.001"} else False,
                    }
                    for i, (c, n) in enumerate(sec_diags)
                ],
                "procedures": [
                    {
                        "code": c,
                        "name": n,
                        "sequence": i + 1,
                        "procedure_date": _dt_iso(admission_dt + timedelta(days=1 + i)),
                    }
                    for i, (c, n) in enumerate(procs)
                ],
            }

            # 增加科室字段（前端常用）——不在 schema 内，但不会影响 Pydantic
            record["department"] = department
            record["admission_date"] = admission_dt.date().isoformat()
            record["discharge_date"] = discharge_dt.date().isoformat()

            self._cases[admission_id] = record

    def _build_suggestions(self) -> None:
        # 为部分病例生成编码建议，确保列表足够丰富
        admissions = list(self._cases.keys())
        self._rand.shuffle(admissions)

        for admission_id in admissions[: max(200, int(self.size * 1.5))]:
            case = self._cases[admission_id]
            n = self._rand.choices([0, 1, 2, 3], weights=[25, 45, 20, 10])[0]
            for _ in range(n):
                sid = self._next_suggestion_id
                self._next_suggestion_id += 1

                stype = self._rand.choice(SUGGESTION_TYPE_POOL)
                severity = self._rand.choices(["info", "warning", "error"], weights=[35, 45, 20])[0]

                message = {
                    "missing_diagnosis": "病程记录提示可能遗漏重要次诊断，建议补充完善。",
                    "procedure_missing": "检验/手术记录中出现操作信息，建议确认是否需要补充手术操作编码。",
                    "complication_marking": "合并症/并发症标记疑似不准确，建议核对是否符合标准。",
                    "logic_conflict": "主次诊断/手术之间可能存在逻辑冲突，请复核临床逻辑与编码规则。",
                }[stype]

                evidence = "（演示）病历摘要：..."

                item = {
                    "admission_id": admission_id,
                    "suggestion_id": sid,
                    "suggestion_type": stype,
                    "diagnosis_code": case.get("primary_diagnosis_code"),
                    "diagnosis_name": case.get("primary_diagnosis_name"),
                    "message": message,
                    "evidence": evidence,
                    "severity": severity,
                    "status": self._rand.choices(["pending", "accepted", "rejected"], weights=[70, 15, 15])[0],
                    "created_at": _now_cn() - timedelta(days=self._rand.randint(0, 30), hours=self._rand.randint(0, 23)),
                    "handled_by": None,
                    "handled_at": None,
                }

                self._coding_suggestions[sid] = item

    def _build_alerts(self) -> None:
        admissions = list(self._cases.keys())
        self._rand.shuffle(admissions)

        for admission_id in admissions[: max(200, int(self.size * 1.2))]:
            case = self._cases[admission_id]

            count = self._rand.choices([0, 1, 2], weights=[35, 45, 20])[0]
            for _ in range(count):
                aid = self._next_alert_id
                self._next_alert_id += 1

                atype = self._rand.choice(ALERT_TYPE_POOL)
                level = self._rand.choices(["info", "warning", "critical"], weights=[25, 50, 25])[0]
                status = self._rand.choices(["pending", "acknowledged", "resolved"], weights=[60, 20, 20])[0]

                message = {
                    "cost_overrun": "费用消耗率异常，建议关注费用结构与耗材使用。",
                    "los_long": "住院日偏长，建议关注诊疗路径与出院管理。",
                    "coding_abnormal": "编码异常风险，建议及时核对病案首页编码。",
                    "profit_loss": "预计亏损风险，建议强化费用控制与路径管理。",
                }[atype]

                metric_value = None
                threshold_value = None
                if atype == "cost_overrun":
                    metric_value = float(case.get("total_cost") or 0)
                    threshold_value = float((case.get("total_cost") or 0) * 0.85)

                item = {
                    "admission_id": admission_id,
                    "alert_id": aid,
                    "alert_type": atype,
                    "alert_level": level,
                    "message": message,
                    "metric_value": metric_value,
                    "threshold_value": threshold_value,
                    "status": status,
                    "triggered_at": _now_cn() - timedelta(days=self._rand.randint(0, 30), hours=self._rand.randint(0, 23)),
                }

                self._drg_alerts[aid] = item

    def _build_grouping_history(self) -> None:
        # 初始化每个病例至少 2 条历史，便于前端演示“版本迭代”
        for admission_id, case in self._cases.items():
            base_grouped_at = _now_cn() - timedelta(days=self._rand.randint(3, 30))

            # 粗略构造 weight 与 baseline_payment，不依赖数据库
            # weight: 0.6 ~ 2.8
            weight_v1 = round(self._rand.uniform(0.6, 2.8), 4)
            weight_v2 = round(max(0.4, weight_v1 * self._rand.uniform(0.92, 1.12)), 4)
            baseline_v1 = round(settings.OPENDRG_BASE_PAYMENT * weight_v1, 2)
            baseline_v2 = round(settings.OPENDRG_BASE_PAYMENT * weight_v2, 2)

            actual_cost = float(case.get("total_cost") or baseline_v2)

            h1 = {
                "grouping_id": self._next_grouping_id,
                "drg_code": "DEMO1",
                "drg_name": "演示分组V1",
                "weight": weight_v1,
                "baseline_payment": baseline_v1,
                "actual_cost": actual_cost,
                "profit_margin": round(baseline_v1 - actual_cost, 2),
                "version": 1,
                "is_latest": False,
                "grouped_at": base_grouped_at - timedelta(days=2),
            }
            self._next_grouping_id += 1

            h2 = {
                "grouping_id": self._next_grouping_id,
                "drg_code": "DEMO2",
                "drg_name": "演示分组V2",
                "weight": weight_v2,
                "baseline_payment": baseline_v2,
                "actual_cost": actual_cost,
                "profit_margin": round(baseline_v2 - actual_cost, 2),
                "version": 2,
                "is_latest": True,
                "grouped_at": base_grouped_at,
            }
            self._next_grouping_id += 1

            self._grouping_history[admission_id] = [h2, h1]

    def _pick_story_cases(self) -> None:
        # 固定挑选三个故事病例：高风险亏损、编码冲突、费用异常
        admissions = list(self._cases.keys())
        if len(admissions) < 3:
            return

        # high_risk_loss：挑一个费用较高的病例
        high_cost = sorted(admissions, key=lambda a: float(self._cases[a].get("total_cost") or 0), reverse=True)[0]

        # coding_conflict：挑一个次诊断较多的病例
        coding_conflict = sorted(admissions, key=lambda a: len(self._cases[a].get("secondary_diagnoses") or []), reverse=True)[0]

        # high_cost_alert：同 high_cost 但确保不同
        high_cost_alert = high_cost
        for a in admissions:
            if a != high_cost and a != coding_conflict:
                high_cost_alert = a
                break

        self.story_cases = DemoStoryCases(
            high_risk_loss=high_cost,
            coding_conflict=coding_conflict,
            high_cost_alert=high_cost_alert,
        )

    def get_story_cases(self) -> Dict[str, Any]:
        story = self.story_cases
        if not story:
            return {"cases": []}

        def _build(admission_id: str, label: str) -> Dict[str, Any]:
            c = self._cases.get(admission_id) or {}
            return {
                "label": label,
                "admission_id": admission_id,
                "patient_name": c.get("patient_name"),
                "department": c.get("department"),
                "primary_diagnosis_name": c.get("primary_diagnosis_name"),
                "total_cost": c.get("total_cost"),
                "total_hospital_days": c.get("total_hospital_days"),
            }

        return {
            "cases": [
                _build(story.high_risk_loss, "高风险亏损病例"),
                _build(story.coding_conflict, "编码冲突/复杂病例"),
                _build(story.high_cost_alert, "高费用预警病例"),
            ]
        }

    # =========================
    # Case Front Page
    # =========================

    def list_cases(self, limit: int) -> List[Dict[str, Any]]:
        items = list(self._cases.values())
        items.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
        return items[:limit]

    def get_case_detail(self, admission_id: str) -> Optional[Dict[str, Any]]:
        return self._cases.get(admission_id)

    def upsert_case(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        admission_id = payload.get("admission_id")
        if not admission_id:
            raise ValueError("admission_id is required")

        existing = self._cases.get(admission_id)
        if existing:
            merged = {**existing, **payload}
            merged["updated_at"] = _dt_iso(_now_cn())
            self._cases[admission_id] = merged
            return merged

        front_page_id = self._next_front_page_id
        self._next_front_page_id += 1

        now = _now_cn()
        record = {
            "front_page_id": front_page_id,
            "created_at": _dt_iso(now),
            "updated_at": _dt_iso(now),
            "coding_status": "draft",
            "review_status": "pending",
            **payload,
        }
        self._cases[admission_id] = record
        return record

    # =========================
    # ICD
    # =========================

    def search_icd(self, keyword: str, category: str, limit: int) -> List[Dict[str, Any]]:
        kw = (keyword or "").strip().lower()
        pool = self._icd10 if category == "diagnosis" else self._icd9

        if not kw:
            return pool[:limit]

        matched = [
            item
            for item in pool
            if kw in item["code"].lower() or kw in item["name"].lower()
        ]
        return matched[:limit]

    def get_icd_by_code(self, code: str, category: str) -> Optional[Dict[str, Any]]:
        pool = self._icd10 if category == "diagnosis" else self._icd9
        for item in pool:
            if item["code"] == code:
                return item
        return None

    def suggest_icd(self, name: str, category: str, top_k: int) -> List[Dict[str, Any]]:
        pool = self._icd10 if category == "diagnosis" else self._icd9
        q = (name or "").strip().lower()

        matched = [item for item in pool if q and q in item["name"].lower()]
        if not matched:
            matched = self._rand.sample(pool, k=min(top_k, len(pool)))

        candidates = []
        for i, item in enumerate(matched[:top_k]):
            conf = max(0.35, 0.92 - i * 0.12)
            candidates.append(
                {
                    "code": item["code"],
                    "name": item["name"],
                    "confidence": conf,
                    "note": "（演示）基于名称匹配与常见编码经验推荐",
                }
            )
        return candidates

    # =========================
    # Coding Suggestions
    # =========================

    def list_suggestions(
        self,
        admission_id: Optional[str],
        status: Optional[str],
        limit: int,
    ) -> List[Dict[str, Any]]:
        items = list(self._coding_suggestions.values())
        if admission_id:
            items = [s for s in items if s.get("admission_id") == admission_id]
        if status:
            items = [s for s in items if s.get("status") == status]

        items.sort(key=lambda x: x.get("created_at") or _now_cn(), reverse=True)
        return items[:limit]

    def update_suggestion_status(self, suggestion_id: int, status: str, handled_by: str) -> bool:
        item = self._coding_suggestions.get(int(suggestion_id))
        if not item:
            return False
        item["status"] = status
        item["handled_by"] = handled_by
        item["handled_at"] = _now_cn()
        return True

    # =========================
    # Alerts
    # =========================

    def list_alerts(
        self,
        admission_id: Optional[str],
        alert_level: Optional[str],
        status: Optional[str],
        limit: int,
    ) -> List[Dict[str, Any]]:
        items = list(self._drg_alerts.values())
        if admission_id:
            items = [a for a in items if a.get("admission_id") == admission_id]
        if alert_level:
            items = [a for a in items if a.get("alert_level") == alert_level]
        if status:
            items = [a for a in items if a.get("status") == status]

        items.sort(key=lambda x: x.get("triggered_at") or _now_cn(), reverse=True)
        return items[:limit]

    def create_alert(
        self,
        admission_id: str,
        alert_type: str,
        alert_level: str,
        message: str,
        metric_value: Optional[float],
        threshold_value: Optional[float],
    ) -> int:
        aid = self._next_alert_id
        self._next_alert_id += 1
        self._drg_alerts[aid] = {
            "admission_id": admission_id,
            "alert_id": aid,
            "alert_type": alert_type,
            "alert_level": alert_level,
            "message": message,
            "metric_value": metric_value,
            "threshold_value": threshold_value,
            "status": "pending",
            "triggered_at": _now_cn(),
        }
        return aid

    def update_alert_status(self, alert_id: int, status: str, handled_by: str) -> bool:
        item = self._drg_alerts.get(int(alert_id))
        if not item:
            return False
        item["status"] = status
        item["handled_by"] = handled_by
        item["handled_at"] = _now_cn()
        return True

    # =========================
    # Grouping History
    # =========================

    def get_grouping_history(self, admission_id: str) -> List[Dict[str, Any]]:
        return list(self._grouping_history.get(admission_id, []))

    def append_grouping_history(self, admission_id: str, drg_result: Dict[str, Any]) -> Dict[str, Any]:
        history = self._grouping_history.setdefault(admission_id, [])
        latest_version = max([h.get("version", 0) for h in history], default=0)
        version = latest_version + 1

        for h in history:
            h["is_latest"] = False

        actual_cost = float(self._cases.get(admission_id, {}).get("total_cost") or 0)
        baseline = float(drg_result.get("baseline_payment") or 0)

        item = {
            "grouping_id": self._next_grouping_id,
            "drg_code": drg_result.get("drg_code"),
            "drg_name": drg_result.get("drg_name"),
            "weight": float(drg_result.get("weight") or 0),
            "baseline_payment": baseline,
            "actual_cost": actual_cost,
            "profit_margin": round(baseline - actual_cost, 2) if baseline else None,
            "version": version,
            "is_latest": True,
            "grouped_at": _now_cn(),
        }
        self._next_grouping_id += 1

        history.insert(0, item)
        return item


_demo_store: Optional[DemoDataStore] = None


def get_demo_store() -> DemoDataStore:
    global _demo_store
    if _demo_store is None:
        _demo_store = DemoDataStore(seed=settings.DEMO_SEED, size=settings.DEMO_SIZE)
    return _demo_store
