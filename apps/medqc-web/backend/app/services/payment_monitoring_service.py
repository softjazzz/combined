from __future__ import annotations

from typing import Any, Dict, Iterable, List

from .drg_config_store import get_runtime_grouping_config


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


class PaymentMonitoringService:
    """医保付费监测服务。

    基于 DRG/DIP 模拟或正式分组结果做支付、盈亏和费用区间判断。
    """

    def simulate(
        self,
        records: Iterable[Dict[str, Any]],
        *,
        payment_standard: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        runtime_config = get_runtime_grouping_config()
        if payment_standard:
            runtime_config = {**runtime_config, **payment_standard}

        normalized_records = [
            self._normalize_record(record, runtime_config)
            for record in records
        ]
        actual_cost = round(sum(item["actual_cost"] for item in normalized_records), 2)
        expected_payment = round(sum(item["expected_payment"] for item in normalized_records), 2)
        profit_loss = round(expected_payment - actual_cost, 2)
        payment_rate = round((expected_payment / actual_cost) * 100, 2) if actual_cost > 0 else 0.0
        loss_cases = [item for item in normalized_records if item["profit_loss"] < 0]

        group_counts = {
            "base_group": sum(1 for item in normalized_records if item["cost_group"] == "base"),
            "high_cost_group": sum(1 for item in normalized_records if item["cost_group"] == "high_cost"),
            "low_cost_group": sum(1 for item in normalized_records if item["cost_group"] == "low_cost"),
        }

        return {
            "result_type": "payment_monitoring",
            "config_version_id": runtime_config.get("config_version_id"),
            "payment_standard": {
                "base_rate": runtime_config.get("base_rate"),
                "hospital_coefficient": runtime_config.get("hospital_coefficient"),
                "region_coefficient": runtime_config.get("region_coefficient"),
                "high_rate_threshold": runtime_config.get("high_rate_threshold"),
                "low_rate_threshold": runtime_config.get("low_rate_threshold"),
            },
            "overview": {
                "case_count": len(normalized_records),
                "actual_cost": actual_cost,
                "expected_payment": expected_payment,
                "profit_loss": profit_loss,
                "payment_rate": payment_rate,
                "loss_case_count": len(loss_cases),
                **group_counts,
            },
            "records": normalized_records,
            "cost_control_hints": self._build_hints(normalized_records, profit_loss),
            "safety_warning": "付费监测为模拟测算，不写入正式医保结算清单或正式 DRG/DIP 结果。",
            "writes_formal_tables": False,
        }

    def _normalize_record(self, record: Dict[str, Any], runtime_config: Dict[str, Any]) -> Dict[str, Any]:
        actual_cost = _float(record.get("actual_cost"), _float(record.get("total_fee"), _float(record.get("total_cost"))))
        weight = _float(record.get("weight"), _float(record.get("rw"), 0.0))
        score = _float(record.get("score"), _float(record.get("dip_score"), 0.0))
        expected_payment = _float(
            record.get("expected_payment"),
            _float(record.get("insurance_payment"), _float(record.get("baseline_payment"), 0.0)),
        )
        if expected_payment <= 0 and weight > 0:
            expected_payment = self._payment_from_unit(weight, runtime_config)
        if expected_payment <= 0 and score > 0:
            expected_payment = self._payment_from_unit(score, runtime_config)

        profit_loss = round(expected_payment - actual_cost, 2)
        cost_ratio = round(actual_cost / expected_payment, 4) if expected_payment > 0 else 0.0
        cost_group = self._cost_group(cost_ratio, runtime_config)
        risk_level = "high" if profit_loss < 0 and cost_group == "high_cost" else "medium" if profit_loss < 0 else "low"

        return {
            "case_id": _text(record.get("case_id"), _text(record.get("visit_id"), _text(record.get("admission_id")))),
            "patient_name": _text(record.get("patient_name"), "未命名患者"),
            "department": _text(record.get("department"), _text(record.get("department_name"), "未知科室")),
            "group_type": _text(record.get("group_type"), "DRG" if record.get("drg_code") else "DIP"),
            "group_code": _text(record.get("group_code"), _text(record.get("drg_code"), _text(record.get("dip_code")))),
            "group_name": _text(record.get("group_name"), _text(record.get("drg_name"), _text(record.get("dip_name")))),
            "weight": weight,
            "score": score,
            "actual_cost": round(actual_cost, 2),
            "expected_payment": round(expected_payment, 2),
            "profit_loss": profit_loss,
            "payment_rate": round((expected_payment / actual_cost) * 100, 2) if actual_cost > 0 else 0.0,
            "cost_ratio": cost_ratio,
            "cost_group": cost_group,
            "risk_level": risk_level,
            "is_low_risk": bool(record.get("is_low_risk") or record.get("isLowRisk")),
        }

    def _payment_from_unit(self, unit: float, runtime_config: Dict[str, Any]) -> float:
        return round(
            unit
            * _float(runtime_config.get("base_rate"), 0)
            * _float(runtime_config.get("hospital_coefficient"), 1)
            * _float(runtime_config.get("region_coefficient"), 1),
            2,
        )

    def _cost_group(self, cost_ratio: float, runtime_config: Dict[str, Any]) -> str:
        if cost_ratio <= 0:
            return "base"
        if cost_ratio >= _float(runtime_config.get("high_rate_threshold"), 3):
            return "high_cost"
        if cost_ratio <= _float(runtime_config.get("low_rate_threshold"), 0.5):
            return "low_cost"
        return "base"

    def _build_hints(self, records: List[Dict[str, Any]], profit_loss: float) -> List[Dict[str, Any]]:
        hints: List[Dict[str, Any]] = []
        high_cost = [item for item in records if item["cost_group"] == "high_cost"]
        losses = sorted((item for item in records if item["profit_loss"] < 0), key=lambda x: x["profit_loss"])
        if profit_loss < 0:
            hints.append(
                {
                    "level": "high",
                    "title": "当前筛选范围预计亏损",
                    "message": "建议优先复核亏损病例的耗材、药品、检查和住院日结构。",
                }
            )
        if high_cost:
            hints.append(
                {
                    "level": "medium",
                    "title": "存在费用极高组风险",
                    "message": f"{len(high_cost)} 例费用超过支付标准阈值，需核对高值耗材和超路径检查。",
                }
            )
        if losses:
            hints.append(
                {
                    "level": "medium",
                    "title": "亏损病例优先级",
                    "message": f"优先处理 {losses[0]['patient_name']} / {losses[0]['case_id']}，预计差额 {losses[0]['profit_loss']} 元。",
                }
            )
        return hints
