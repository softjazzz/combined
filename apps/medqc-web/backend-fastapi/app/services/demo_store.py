from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional


@dataclass
class DemoStore:
    cases: List[Dict[str, Any]]
    suggestions: List[Dict[str, Any]]
    alerts: List[Dict[str, Any]]
    groupings_by_admission: Dict[str, List[Dict[str, Any]]]

    _next_suggestion_id: int = 1000
    _next_alert_id: int = 2000
    _next_grouping_id: int = 3000

    @classmethod
    def create_default(cls) -> "DemoStore":
        now = datetime.utcnow()

        cases: List[Dict[str, Any]] = [
            {
                "front_page_id": 1,
                "admission_id": "ADM20250104001",
                "patient_id": "P001",
                "patient_name": "张三",
                "patient_age": 58,
                "patient_gender": "M",
                "primary_diagnosis_code": "I21.001",
                "primary_diagnosis_name": "急性前壁ST段抬高型心肌梗死",
                "main_procedure_code": "36.0700",
                "main_procedure_name": "经皮冠状动脉介入术",
                "main_procedure_date": (now - timedelta(days=5)).isoformat(),
                "admission_route": "急诊",
                "discharge_status": "好转",
                "total_hospital_days": 8,
                "total_cost": 128560.0,
                "coding_status": "draft",
                "review_status": "pending",
                "coder_id": "coder_001",
                "reviewer_id": None,
                "coding_started_at": (now - timedelta(days=4)).isoformat(),
                "coding_completed_at": None,
                "created_at": (now - timedelta(days=6)).isoformat(),
                "updated_at": (now - timedelta(hours=2)).isoformat(),
                "secondary_diagnoses": [
                    {"code": "I10.x01", "name": "高血压3级", "sequence": 1, "is_complication": False},
                    {"code": "E11.901", "name": "2型糖尿病", "sequence": 2, "is_complication": False},
                ],
                "procedures": [
                    {
                        "code": "36.0700",
                        "name": "经皮冠状动脉介入术",
                        "sequence": 1,
                        "procedure_date": (now - timedelta(days=5)).isoformat(),
                    }
                ],
            },
            {
                "front_page_id": 2,
                "admission_id": "ADM20250104002",
                "patient_id": "P002",
                "patient_name": "李四",
                "patient_age": 46,
                "patient_gender": "F",
                "primary_diagnosis_code": "K35.801",
                "primary_diagnosis_name": "急性阑尾炎",
                "main_procedure_code": "47.0100",
                "main_procedure_name": "阑尾切除术",
                "main_procedure_date": (now - timedelta(days=2)).isoformat(),
                "admission_route": "门诊",
                "discharge_status": "治愈",
                "total_hospital_days": 4,
                "total_cost": 23680.0,
                "coding_status": "completed",
                "review_status": "pending",
                "coder_id": "coder_002",
                "reviewer_id": None,
                "coding_started_at": (now - timedelta(days=2)).isoformat(),
                "coding_completed_at": (now - timedelta(days=1)).isoformat(),
                "created_at": (now - timedelta(days=3)).isoformat(),
                "updated_at": (now - timedelta(hours=5)).isoformat(),
                "secondary_diagnoses": [
                    {"code": "R50.901", "name": "发热", "sequence": 1, "is_complication": False}
                ],
                "procedures": [
                    {
                        "code": "47.0100",
                        "name": "阑尾切除术",
                        "sequence": 1,
                        "procedure_date": (now - timedelta(days=2)).isoformat(),
                    }
                ],
            },
            {
                "front_page_id": 3,
                "admission_id": "ADM20250104003",
                "patient_id": "P003",
                "patient_name": "王五",
                "patient_age": 72,
                "patient_gender": "M",
                "primary_diagnosis_code": "J18.901",
                "primary_diagnosis_name": "肺炎",
                "main_procedure_code": None,
                "main_procedure_name": None,
                "main_procedure_date": None,
                "admission_route": "急诊",
                "discharge_status": "好转",
                "total_hospital_days": 12,
                "total_cost": 65980.0,
                "coding_status": "draft",
                "review_status": "pending",
                "coder_id": "coder_001",
                "reviewer_id": None,
                "coding_started_at": (now - timedelta(days=1)).isoformat(),
                "coding_completed_at": None,
                "created_at": (now - timedelta(days=2)).isoformat(),
                "updated_at": (now - timedelta(minutes=30)).isoformat(),
                "secondary_diagnoses": [
                    {"code": "J44.901", "name": "慢性阻塞性肺疾病", "sequence": 1, "is_complication": True}
                ],
                "procedures": [],
            },
        ]

        suggestions: List[Dict[str, Any]] = [
            {
                "admission_id": "ADM20250104001",
                "suggestion_id": 101,
                "suggestion_type": "missing_diagnosis",
                "diagnosis_code": "I50.001",
                "diagnosis_name": "心力衰竭",
                "message": "病程记录提示心衰表现，建议补充次诊断：I50.001（心力衰竭）",
                "evidence": "病程记录第3天：出现呼吸困难、双肺底湿啰音，考虑心衰...",
                "severity": "warning",
                "status": "pending",
                "created_at": (now - timedelta(hours=10)).isoformat(),
            },
            {
                "admission_id": "ADM20250104002",
                "suggestion_id": 102,
                "suggestion_type": "procedure_missing",
                "diagnosis_code": None,
                "diagnosis_name": None,
                "message": "手术记录中存在麻醉方式，建议补充相应操作编码以提高一致性",
                "evidence": "手术记录：全身麻醉下行腹腔镜阑尾切除术...",
                "severity": "info",
                "status": "pending",
                "created_at": (now - timedelta(hours=6)).isoformat(),
            },
            {
                "admission_id": "ADM20250104003",
                "suggestion_id": 103,
                "suggestion_type": "complication_marking",
                "diagnosis_code": "J44.901",
                "diagnosis_name": "慢性阻塞性肺疾病",
                "message": "建议将 COPD 标记为并发症/合并症以更符合病情复杂度",
                "evidence": "入院记录：既往COPD多年，近期加重...",
                "severity": "warning",
                "status": "pending",
                "created_at": (now - timedelta(hours=3)).isoformat(),
            },
        ]

        alerts: List[Dict[str, Any]] = [
            {
                "admission_id": "ADM20250104001",
                "alert_id": 201,
                "alert_type": "cost_overrun",
                "alert_level": "critical",
                "message": "费用超标严重，建议复核耗材/药品结构",
                "metric_value": 135.0,
                "threshold_value": 100.0,
                "status": "pending",
                "triggered_at": (now - timedelta(hours=8)).isoformat(),
            },
            {
                "admission_id": "ADM20250104003",
                "alert_id": 202,
                "alert_type": "los_long",
                "alert_level": "warning",
                "message": "住院日偏长，建议评估是否可转康复/下转",
                "metric_value": 12.0,
                "threshold_value": 9.0,
                "status": "pending",
                "triggered_at": (now - timedelta(hours=4)).isoformat(),
            },
        ]

        groupings_by_admission: Dict[str, List[Dict[str, Any]]] = {
            "ADM20250104001": [
                {
                    "grouping_id": 301,
                    "drg_code": "FB19",
                    "drg_name": "急性心肌梗死伴PCI",
                    "weight": 1.95,
                    "baseline_payment": 58200.0,
                    "actual_cost": 128560.0,
                    "profit_margin": -0.55,
                    "version": 1,
                    "is_latest": True,
                    "grouped_at": (now - timedelta(hours=9)).isoformat(),
                },
                {
                    "grouping_id": 302,
                    "drg_code": "FB17",
                    "drg_name": "急性心肌梗死（不含复杂操作）",
                    "weight": 1.35,
                    "baseline_payment": 40500.0,
                    "actual_cost": 128560.0,
                    "profit_margin": -0.68,
                    "version": 0,
                    "is_latest": False,
                    "grouped_at": (now - timedelta(days=2)).isoformat(),
                },
            ],
            "ADM20250104002": [
                {
                    "grouping_id": 303,
                    "drg_code": "GB11",
                    "drg_name": "阑尾切除术",
                    "weight": 0.75,
                    "baseline_payment": 18500.0,
                    "actual_cost": 23680.0,
                    "profit_margin": -0.12,
                    "version": 1,
                    "is_latest": True,
                    "grouped_at": (now - timedelta(hours=7)).isoformat(),
                }
            ],
        }

        store = cls(
            cases=cases,
            suggestions=suggestions,
            alerts=alerts,
            groupings_by_admission=groupings_by_admission,
        )

        store._next_suggestion_id = max([s["suggestion_id"] for s in suggestions] + [1000]) + 1
        store._next_alert_id = max([a["alert_id"] for a in alerts] + [2000]) + 1
        store._next_grouping_id = max(
            [
                g["grouping_id"]
                for arr in groupings_by_admission.values()
                for g in arr
            ]
            + [3000]
        ) + 1

        return store

    def list_case_front_pages(self, limit: int = 100) -> List[Dict[str, Any]]:
        return sorted(self.cases, key=lambda x: x.get("updated_at") or "", reverse=True)[:limit]

    def get_case_front_page_detail(self, admission_id: str) -> Optional[Dict[str, Any]]:
        for c in self.cases:
            if c.get("admission_id") == admission_id:
                return c
        return None

    def list_coding_suggestions(
        self,
        admission_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        items = list(self.suggestions)
        if admission_id:
            items = [s for s in items if s.get("admission_id") == admission_id]
        if status:
            items = [s for s in items if s.get("status") == status]
        items = sorted(items, key=lambda x: x.get("created_at") or "", reverse=True)
        return items[:limit]

    def update_suggestion_status(self, suggestion_id: int, status: str, handled_by: str) -> bool:
        for s in self.suggestions:
            if s.get("suggestion_id") == suggestion_id:
                s["status"] = status
                s["handled_by"] = handled_by
                s["handled_at"] = datetime.utcnow().isoformat()
                return True
        return False

    def list_alerts(
        self,
        admission_id: Optional[str] = None,
        alert_level: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        items = list(self.alerts)
        if admission_id:
            items = [a for a in items if a.get("admission_id") == admission_id]
        if alert_level:
            items = [a for a in items if a.get("alert_level") == alert_level]
        if status:
            items = [a for a in items if a.get("status") == status]
        items = sorted(items, key=lambda x: x.get("triggered_at") or "", reverse=True)
        return items[:limit]

    def update_alert_status(self, alert_id: int, status: str, handled_by: str) -> bool:
        for a in self.alerts:
            if a.get("alert_id") == alert_id:
                a["status"] = status
                a["handled_by"] = handled_by
                a["handled_at"] = datetime.utcnow().isoformat()
                return True
        return False

    def save_drg_alert(
        self,
        admission_id: str,
        alert_type: str,
        alert_level: str,
        message: str,
        metric_value: Optional[float] = None,
        threshold_value: Optional[float] = None,
    ) -> int:
        alert_id = self._next_alert_id
        self._next_alert_id += 1
        self.alerts.append(
            {
                "admission_id": admission_id,
                "alert_id": alert_id,
                "alert_type": alert_type,
                "alert_level": alert_level,
                "message": message,
                "metric_value": metric_value,
                "threshold_value": threshold_value,
                "status": "pending",
                "triggered_at": datetime.utcnow().isoformat(),
            }
        )
        return alert_id

    def save_grouping_history(self, admission_id: str, item: Dict[str, Any]) -> int:
        grouping_id = self._next_grouping_id
        self._next_grouping_id += 1

        arr = self.groupings_by_admission.setdefault(admission_id, [])
        for g in arr:
            g["is_latest"] = False

        latest_version = max([g.get("version", 0) for g in arr] + [0])
        version = latest_version + 1

        payload = {
            **item,
            "grouping_id": grouping_id,
            "version": version,
            "is_latest": True,
            "grouped_at": datetime.utcnow().isoformat(),
        }
        arr.insert(0, payload)
        return grouping_id

    def get_grouping_history(self, admission_id: str) -> List[Dict[str, Any]]:
        return list(self.groupings_by_admission.get(admission_id, []))


demo_store = DemoStore.create_default()
