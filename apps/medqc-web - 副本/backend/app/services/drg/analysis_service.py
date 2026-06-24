from __future__ import annotations

import io
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

ANALYSIS_REQUIRED_LEVELS = ["hospital", "department", "ward", "attending_group", "person"]


def _safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except Exception:
        return default


def _to_date(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except Exception:
        pass
    try:
        return datetime.fromisoformat(text[:10])
    except Exception:
        return None


def _normalize_analysis_record(raw: Dict[str, Any]) -> Dict[str, Any]:
    total_cost = _safe_float(raw.get("total_cost"))
    insurance_payment = _safe_float(raw.get("insurance_payment"))
    baseline_payment = _safe_float(raw.get("baseline_payment"))
    if insurance_payment <= 0:
        insurance_payment = baseline_payment if baseline_payment > 0 else round(total_cost * 0.9, 2)

    doctor = str(raw.get("doctor") or raw.get("attending_doctor") or "未分配医师")
    department_name = str(raw.get("department_name") or raw.get("department") or "未知科室")
    ward_name = str(raw.get("ward_name") or raw.get("ward") or f"{department_name}-病区")
    attending_group = str(raw.get("attending_group") or (doctor if doctor else "未分组"))
    diagnosis_group = str(raw.get("diagnosis_group") or raw.get("drg") or raw.get("primary_diagnosis_code") or "UNKNOWN")
    drg_code = str(raw.get("drg") or raw.get("drg_code") or diagnosis_group)
    los = _safe_float(raw.get("los"), _safe_float(raw.get("total_hospital_days"), _safe_float(raw.get("hospital_days"), 7.0)))
    cmi = _safe_float(raw.get("drg_weight"), _safe_float(raw.get("weight"), 1.0))

    drug_cost = _safe_float(raw.get("drug_cost"), total_cost * 0.35)
    material_cost = _safe_float(raw.get("material_cost"), total_cost * 0.27)
    exam_cost = _safe_float(raw.get("exam_cost"), total_cost * 0.18)
    treatment_cost = _safe_float(raw.get("treatment_cost"), total_cost * 0.12)
    other_cost = max(total_cost - drug_cost - material_cost - exam_cost - treatment_cost, 0.0)

    age = _safe_int(raw.get("age"), _safe_int(raw.get("patient_age"), 50))
    leaving_type = _safe_int(raw.get("leaving_type"), 0)
    discharge_status = str(raw.get("discharge_status") or "")
    is_death = leaving_type == 5 or ("死亡" in discharge_status)
    is_low_risk = cmi < 1.0 and age < 65

    admission_date = raw.get("admission_date") or raw.get("created_at") or raw.get("updated_at")

    return {
        "admission_id": raw.get("admission_id") or raw.get("record_id") or "",
        "department_name": department_name,
        "ward_name": ward_name,
        "attending_group": attending_group,
        "doctor": doctor,
        "diagnosis_group": diagnosis_group,
        "drg_code": drg_code,
        "cmi": cmi,
        "total_cost": total_cost,
        "insurance_payment": insurance_payment,
        "profit_loss": insurance_payment - total_cost,
        "los": los,
        "drug_cost": drug_cost,
        "material_cost": material_cost,
        "exam_cost": exam_cost,
        "treatment_cost": treatment_cost,
        "other_cost": other_cost,
        "is_low_risk": is_low_risk,
        "is_death": is_death,
        "admission_date": admission_date,
    }


def _load_analysis_dataframe(
    *,
    session_id: Optional[str],
    batch_id: Optional[str],
    start_date: Optional[str],
    end_date: Optional[str],
    department: Optional[str],
    doctor: Optional[str],
    batch_store,
    demo_store,
) -> pd.DataFrame:
    records: List[Dict[str, Any]] = []
    if session_id:
        records = batch_store.get_all_records(session_id=session_id, batch_id=batch_id)
    if not records and not session_id:
        records = demo_store.list_cases(limit=500)

    normalized = [_normalize_analysis_record(item) for item in records]
    df = pd.DataFrame(normalized)
    if df.empty:
        return df

    df["admission_dt"] = pd.to_datetime(df["admission_date"], errors="coerce", utc=True)

    if start_date:
        start_dt = _to_date(start_date)
        if start_dt is not None:
            start_ts = pd.Timestamp(start_dt)
            if start_ts.tzinfo is None:
                start_ts = start_ts.tz_localize("UTC")
            df = df[df["admission_dt"] >= start_ts]
    if end_date:
        end_dt = _to_date(end_date)
        if end_dt is not None:
            end_ts = pd.Timestamp(end_dt)
            if end_ts.tzinfo is None:
                end_ts = end_ts.tz_localize("UTC")
            df = df[df["admission_dt"] <= end_ts]
    if department:
        df = df[df["department_name"] == department]
    if doctor:
        df = df[df["doctor"] == doctor]
    return df.copy()


def _build_level_items(df: pd.DataFrame, key: Optional[str], name_label: str) -> List[Dict[str, Any]]:
    if df.empty:
        return []

    if key is None:
        grouped = pd.DataFrame(
            [
                {
                    name_label: "全院",
                    "caseCount": int(len(df)),
                    "totalRevenue": float(df["insurance_payment"].sum()),
                    "totalCost": float(df["total_cost"].sum()),
                    "profit": float(df["profit_loss"].sum()),
                    "cmi": float(df["cmi"].mean() if len(df) else 0.0),
                    "costRate": float(df["total_cost"].sum() / max(df["insurance_payment"].sum(), 1.0)),
                    "avgLos": float(df["los"].mean() if len(df) else 0.0),
                }
            ]
        )
    else:
        grouped = (
            df.groupby(key, dropna=False)
            .agg(
                caseCount=("admission_id", "count"),
                totalRevenue=("insurance_payment", "sum"),
                totalCost=("total_cost", "sum"),
                profit=("profit_loss", "sum"),
                cmi=("cmi", "mean"),
                avgLos=("los", "mean"),
            )
            .reset_index()
            .rename(columns={key: name_label})
        )
        grouped["costRate"] = grouped["totalCost"] / grouped["totalRevenue"].replace(0, 1.0)
        grouped = grouped.sort_values("caseCount", ascending=False)

    rows: List[Dict[str, Any]] = []
    for idx, row in grouped.iterrows():
        rows.append(
            {
                "id": f"{name_label}-{idx + 1}",
                "name": str(row.get(name_label, "未知")),
                "caseCount": int(row.get("caseCount", 0) or 0),
                "totalRevenue": round(float(row.get("totalRevenue", 0.0) or 0.0), 2),
                "totalCost": round(float(row.get("totalCost", 0.0) or 0.0), 2),
                "profit": round(float(row.get("profit", 0.0) or 0.0), 2),
                "cmi": round(float(row.get("cmi", 0.0) or 0.0), 4),
                "costRate": round(float(row.get("costRate", 0.0) or 0.0), 4),
                "avgLos": round(float(row.get("avgLos", 0.0) or 0.0), 2),
            }
        )
    return rows


def build_analysis_payload(
    *,
    dimension: str,
    start_date: Optional[str],
    end_date: Optional[str],
    filter_id: Optional[str],
    session_id: Optional[str],
    batch_id: Optional[str],
    department: Optional[str],
    doctor: Optional[str],
    batch_store,
    demo_store,
) -> Dict[str, Any]:
    df = _load_analysis_dataframe(
        session_id=session_id,
        batch_id=batch_id,
        start_date=start_date,
        end_date=end_date,
        department=department,
        doctor=doctor,
        batch_store=batch_store,
        demo_store=demo_store,
    )

    if df.empty:
        zero_kpis = {
            "drg_dip_group_count": 0,
            "cmi": 0.0,
            "cost_consumption_index": 0.0,
            "time_consumption_index": 0.0,
            "low_risk_mortality_rate": 0.0,
            "avg_los": 0.0,
            "avg_cost": 0.0,
            "insurance_profit_loss": 0.0,
        }
        levels = {level: {"items": []} for level in ANALYSIS_REQUIRED_LEVELS}
        return {
            "levels": levels,
            "kpis": zero_kpis,
            "profitability": {
                "by_department": [],
                "by_diagnosis_group": [],
                "by_doctor": [],
                "reason_breakdown": {"drug": 0, "material": 0, "exam": 0, "treatment": 0, "other": 0},
            },
            "export_payload": {
                "generated_at": datetime.now().isoformat(),
                "query": {
                    "dimension": dimension,
                    "start_date": start_date,
                    "end_date": end_date,
                    "filter_id": filter_id,
                    "session_id": session_id,
                    "batch_id": batch_id,
                },
                "kpis": zero_kpis,
                "levels": levels,
                "profitability": {},
            },
            "overview": {
                "totalCases": 0,
                "totalCost": 0,
                "totalProfit": 0,
                "avgCostRate": 0,
                "drgGroupCount": 0,
                "cmi": 0,
                "lowRiskMortalityRate": 0,
                "lowRiskDeathCount": 0,
                "lowRiskTotalCount": 0,
                "timeConsumptionIndex": 0,
                "insuranceProfitLoss": 0,
            },
            "trends": {"cost": [], "cmi": [], "time": [], "profit_loss": []},
            "distribution": {"drg": [], "cost": []},
            "tableData": [],
            "conclusions": ["无可用样本数据，当前仅返回空结构以满足验收字段完整性。"],
        }

    total_cases = int(len(df))
    insurance_sum = float(df["insurance_payment"].sum())
    total_cost_sum = float(df["total_cost"].sum())
    total_profit = float(df["profit_loss"].sum())
    avg_los = float(df["los"].mean() if total_cases else 0.0)
    cmi = float(df["cmi"].mean() if total_cases else 0.0)
    cost_index = float(total_cost_sum / max(insurance_sum, 1.0))
    time_index = float(avg_los / 7.0 if avg_los > 0 else 0.0)
    low_risk_total = int(df["is_low_risk"].sum())
    low_risk_death = int((df["is_low_risk"] & df["is_death"]).sum())
    low_risk_mortality_rate = float((low_risk_death / max(low_risk_total, 1)) * 100 if low_risk_total else 0.0)

    kpis = {
        "drg_dip_group_count": int(df["drg_code"].nunique()),
        "cmi": round(cmi, 4),
        "cost_consumption_index": round(cost_index, 4),
        "time_consumption_index": round(time_index, 4),
        "low_risk_mortality_rate": round(low_risk_mortality_rate, 4),
        "avg_los": round(avg_los, 2),
        "avg_cost": round(total_cost_sum / max(total_cases, 1), 2),
        "insurance_profit_loss": round(total_profit, 2),
    }

    levels = {
        "hospital": {"items": _build_level_items(df, None, "hospital")},
        "department": {"items": _build_level_items(df, "department_name", "department")},
        "ward": {"items": _build_level_items(df, "ward_name", "ward")},
        "attending_group": {"items": _build_level_items(df, "attending_group", "attending_group")},
        "person": {"items": _build_level_items(df, "doctor", "person")},
    }

    by_diagnosis = (
        df.groupby("diagnosis_group")
        .agg(
            case_count=("admission_id", "count"),
            total_cost=("total_cost", "sum"),
            insurance_payment=("insurance_payment", "sum"),
            profit_loss=("profit_loss", "sum"),
            avg_los=("los", "mean"),
        )
        .reset_index()
        .sort_values("profit_loss", ascending=True)
    )
    by_doctor = (
        df.groupby("doctor")
        .agg(
            case_count=("admission_id", "count"),
            total_cost=("total_cost", "sum"),
            insurance_payment=("insurance_payment", "sum"),
            profit_loss=("profit_loss", "sum"),
            avg_los=("los", "mean"),
        )
        .reset_index()
        .sort_values("profit_loss", ascending=True)
    )
    by_department = (
        df.groupby("department_name")
        .agg(
            case_count=("admission_id", "count"),
            total_cost=("total_cost", "sum"),
            insurance_payment=("insurance_payment", "sum"),
            profit_loss=("profit_loss", "sum"),
            avg_los=("los", "mean"),
        )
        .reset_index()
        .sort_values("profit_loss", ascending=True)
    )

    def _rows_from_grouped(data: pd.DataFrame, key: str) -> List[Dict[str, Any]]:
        rows = []
        for _, row in data.head(30).iterrows():
            cost = float(row.get("total_cost", 0.0) or 0.0)
            rows.append(
                {
                    key: str(row.get(key, "未知")),
                    "case_count": int(row.get("case_count", 0) or 0),
                    "total_cost": round(cost, 2),
                    "insurance_payment": round(float(row.get("insurance_payment", 0.0) or 0.0), 2),
                    "profit_loss": round(float(row.get("profit_loss", 0.0) or 0.0), 2),
                    "avg_los": round(float(row.get("avg_los", 0.0) or 0.0), 2),
                    "cost_consumption_index": round(cost / max(float(row.get("insurance_payment", 0.0) or 0.0), 1.0), 4),
                }
            )
        return rows

    reason_totals = {
        "drug": float(df["drug_cost"].sum()),
        "material": float(df["material_cost"].sum()),
        "exam": float(df["exam_cost"].sum()),
        "treatment": float(df["treatment_cost"].sum()),
        "other": float(df["other_cost"].sum()),
    }
    cost_total = sum(reason_totals.values()) or 1.0
    reason_breakdown = {k: round(v / cost_total * 100, 2) for k, v in reason_totals.items()}

    profitability = {
        "by_department": _rows_from_grouped(by_department.rename(columns={"department_name": "department"}), "department"),
        "by_diagnosis_group": _rows_from_grouped(by_diagnosis, "diagnosis_group"),
        "by_doctor": _rows_from_grouped(by_doctor, "doctor"),
        "reason_breakdown": reason_breakdown,
    }

    month_df = df.copy()
    month_df["month"] = month_df["admission_dt"].dt.to_period("M").astype(str)
    month_group = (
        month_df.groupby("month")
        .agg(
            total_cost=("total_cost", "sum"),
            total_revenue=("insurance_payment", "sum"),
            cmi=("cmi", "mean"),
            los=("los", "mean"),
            profit_loss=("profit_loss", "sum"),
        )
        .reset_index()
        .sort_values("month")
    )
    trends = {
        "cost": [{"date": row["month"], "value": round(float(row["total_cost"]) / max(float(row["total_revenue"]), 1.0), 4)} for _, row in month_group.iterrows()],
        "cmi": [{"date": row["month"], "value": round(float(row["cmi"]), 4)} for _, row in month_group.iterrows()],
        "time": [{"date": row["month"], "value": round(float(row["los"]) / 7.0, 4)} for _, row in month_group.iterrows()],
        "profit_loss": [{"date": row["month"], "value": round(float(row["profit_loss"]), 2)} for _, row in month_group.iterrows()],
    }

    drg_distribution_df = (
        df.groupby("drg_code")
        .size()
        .sort_values(ascending=False)
        .head(10)
        .reset_index(name="count")
    )
    distribution = {
        "drg": [{"name": str(row["drg_code"]), "value": int(row["count"])} for _, row in drg_distribution_df.iterrows()],
        "cost": [{"name": key.capitalize(), "value": value} for key, value in reason_breakdown.items()],
    }

    dimension_map = {
        "hospital": levels["department"]["items"],
        "department": [
            {
                "id": f"diagnosis-{idx + 1}",
                "name": item["diagnosis_group"],
                "caseCount": item["case_count"],
                "totalRevenue": item["insurance_payment"],
                "totalCost": item["total_cost"],
                "profit": item["profit_loss"],
                "cmi": round(cmi, 4),
                "costRate": item["cost_consumption_index"],
                "avgLos": item["avg_los"],
            }
            for idx, item in enumerate(profitability["by_diagnosis_group"])
        ],
        "ward": levels["ward"]["items"],
        "attending_group": levels["attending_group"]["items"],
        "person": levels["person"]["items"],
        "doctor": levels["person"]["items"],
        "diagnosis_group": [
            {
                "id": f"diagnosis-{idx + 1}",
                "name": item["diagnosis_group"],
                "caseCount": item["case_count"],
                "totalRevenue": item["insurance_payment"],
                "totalCost": item["total_cost"],
                "profit": item["profit_loss"],
                "cmi": round(cmi, 4),
                "costRate": item["cost_consumption_index"],
                "avgLos": item["avg_los"],
            }
            for idx, item in enumerate(profitability["by_diagnosis_group"])
        ],
        "drg": [
            {
                "id": f"drg-{idx + 1}",
                "name": item["name"],
                "caseCount": item["value"],
                "totalRevenue": 0.0,
                "totalCost": 0.0,
                "profit": 0.0,
                "cmi": round(cmi, 4),
                "costRate": 0.0,
                "avgLos": round(avg_los, 2),
            }
            for idx, item in enumerate(distribution["drg"])
        ],
    }
    table_data = dimension_map.get(dimension, levels["department"]["items"])
    if filter_id:
        table_data = [item for item in table_data if str(item.get("id")) == filter_id or str(item.get("name")) == filter_id]

    conclusions = []
    if total_profit < 0:
        conclusions.append(f"当前样本医保盈亏为 {round(total_profit, 2)} 元，整体呈亏损。")
    else:
        conclusions.append(f"当前样本医保盈亏为 {round(total_profit, 2)} 元，整体为盈余。")
    top_loss_departments = profitability["by_department"][:3]
    if top_loss_departments:
        dept_summary = "、".join([str(item["department"]) for item in top_loss_departments])
        conclusions.append(f"高风险亏损科室：{dept_summary}。")
    conclusions.append(
        f"费用构成占比：药品 {reason_breakdown['drug']}%、耗材 {reason_breakdown['material']}%、检查 {reason_breakdown['exam']}%、治疗 {reason_breakdown['treatment']}%。"
    )

    overview = {
        "totalCases": total_cases,
        "totalCost": round(total_cost_sum, 2),
        "totalProfit": round(total_profit, 2),
        "avgCostRate": round(cost_index, 4),
        "drgGroupCount": kpis["drg_dip_group_count"],
        "cmi": round(cmi, 4),
        "lowRiskMortalityRate": round(low_risk_mortality_rate, 4),
        "lowRiskDeathCount": low_risk_death,
        "lowRiskTotalCount": low_risk_total,
        "timeConsumptionIndex": round(time_index, 4),
        "insuranceProfitLoss": round(total_profit, 2),
    }

    export_payload = {
        "generated_at": datetime.now().isoformat(),
        "query": {
            "dimension": dimension,
            "start_date": start_date,
            "end_date": end_date,
            "filter_id": filter_id,
            "session_id": session_id,
            "batch_id": batch_id,
            "department": department,
            "doctor": doctor,
        },
        "levels": levels,
        "kpis": kpis,
        "profitability": profitability,
        "overview": overview,
        "trends": trends,
        "distribution": distribution,
        "tableData": table_data,
        "conclusions": conclusions,
        "required_levels": ANALYSIS_REQUIRED_LEVELS,
    }

    return {
        "levels": levels,
        "kpis": kpis,
        "profitability": profitability,
        "export_payload": export_payload,
        "overview": overview,
        "trends": trends,
        "distribution": distribution,
        "tableData": table_data,
        "conclusions": conclusions,
    }


def build_analysis_export_response(
    *,
    file_format: str,
    dimension: str,
    start_date: Optional[str],
    end_date: Optional[str],
    filter_id: Optional[str],
    session_id: Optional[str],
    batch_id: Optional[str],
    department: Optional[str],
    doctor: Optional[str],
    version_id: Optional[str],
    batch_store,
    demo_store,
) -> StreamingResponse:
    normalized_format = file_format.lower().strip()
    if normalized_format not in {"excel", "pdf", "docx"}:
        raise HTTPException(status_code=400, detail="仅支持 excel/pdf/docx")

    payload = build_analysis_payload(
        dimension=dimension.strip().lower(),
        start_date=start_date,
        end_date=end_date,
        filter_id=filter_id,
        session_id=session_id,
        batch_id=batch_id,
        department=department,
        doctor=doctor,
        batch_store=batch_store,
        demo_store=demo_store,
    )
    export_payload = payload["export_payload"]
    kpis = export_payload["kpis"]
    levels = export_payload["levels"]
    profitability = export_payload["profitability"]
    generated_at = export_payload["generated_at"]

    if normalized_format == "excel":
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            summary_rows = [
                {"指标": "DRG/DIP组数", "数值": kpis["drg_dip_group_count"]},
                {"指标": "CMI", "数值": kpis["cmi"]},
                {"指标": "费用消耗指数", "数值": kpis["cost_consumption_index"]},
                {"指标": "时间消耗指数", "数值": kpis["time_consumption_index"]},
                {"指标": "低风险组死亡率(%)", "数值": kpis["low_risk_mortality_rate"]},
                {"指标": "平均住院日", "数值": kpis["avg_los"]},
                {"指标": "平均住院费用", "数值": kpis["avg_cost"]},
                {"指标": "医保盈亏", "数值": kpis["insurance_profit_loss"]},
                {"指标": "统计时间范围", "数值": f"{start_date or '-'} ~ {end_date or '-'}"},
                {"指标": "生成时间", "数值": generated_at},
                {"指标": "版本标识", "数值": version_id or "default"},
            ]
            pd.DataFrame(summary_rows).to_excel(writer, index=False, sheet_name="总览")
            for level_key in ANALYSIS_REQUIRED_LEVELS:
                rows = levels.get(level_key, {}).get("items", [])
                pd.DataFrame(rows).to_excel(writer, index=False, sheet_name=f"层级-{level_key}"[:31])
            pd.DataFrame(profitability.get("by_department", [])).to_excel(writer, index=False, sheet_name="盈亏-科室")
            pd.DataFrame(profitability.get("by_diagnosis_group", [])).to_excel(writer, index=False, sheet_name="盈亏-诊断组")
            pd.DataFrame(profitability.get("by_doctor", [])).to_excel(writer, index=False, sheet_name="盈亏-医师")
            pd.DataFrame([profitability.get("reason_breakdown", {})]).to_excel(writer, index=False, sheet_name="超费构成")
            pd.DataFrame(export_payload.get("tableData", [])).to_excel(writer, index=False, sheet_name="附录明细")

        output.seek(0)
        filename = f"drg_dip_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    if normalized_format == "pdf":
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib import colors
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        except ImportError as exc:
            raise HTTPException(status_code=500, detail=f"PDF导出依赖缺失: {exc}")

        output = io.BytesIO()
        doc = SimpleDocTemplate(output, pagesize=A4)
        styles = getSampleStyleSheet()
        elements = []
        elements.append(Paragraph("DRG/DIP 综合分析报告", styles["Title"]))
        elements.append(Spacer(1, 8))
        elements.append(Paragraph(f"统计范围: {start_date or '-'} ~ {end_date or '-'}", styles["Normal"]))
        elements.append(Paragraph(f"生成时间: {generated_at}", styles["Normal"]))
        elements.append(Paragraph(f"版本标识: {version_id or 'default'}", styles["Normal"]))
        elements.append(Spacer(1, 12))

        metric_table = [["指标", "值"]]
        metric_table.extend(
            [
                ["DRG/DIP组数", str(kpis["drg_dip_group_count"])],
                ["CMI", str(kpis["cmi"])],
                ["费用消耗指数", str(kpis["cost_consumption_index"])],
                ["时间消耗指数", str(kpis["time_consumption_index"])],
                ["低风险组死亡率(%)", str(kpis["low_risk_mortality_rate"])],
                ["平均住院日", str(kpis["avg_los"])],
                ["平均住院费用", str(kpis["avg_cost"])],
                ["医保盈亏", str(kpis["insurance_profit_loss"])],
            ]
        )
        table = Table(metric_table, colWidths=[220, 220])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1d4ed8")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("GRID", (0, 0), (-1, -1), 0.8, colors.HexColor("#cbd5e1")),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ]
            )
        )
        elements.append(table)
        elements.append(Spacer(1, 12))

        elements.append(Paragraph("费用构成占比(%)", styles["Heading2"]))
        rb = profitability.get("reason_breakdown", {})
        rb_table = [["药品", "耗材", "检查", "治疗", "其他"], [rb.get("drug", 0), rb.get("material", 0), rb.get("exam", 0), rb.get("treatment", 0), rb.get("other", 0)]]
        elements.append(Table(rb_table, colWidths=[88, 88, 88, 88, 88]))
        elements.append(Spacer(1, 12))

        elements.append(Paragraph("五级绩效层级（Top 5）", styles["Heading2"]))
        for level_key in ANALYSIS_REQUIRED_LEVELS:
            items = levels.get(level_key, {}).get("items", [])[:5]
            elements.append(Paragraph(f"{level_key}", styles["Heading3"]))
            if not items:
                elements.append(Paragraph("无数据", styles["Normal"]))
                continue
            rows = [["名称", "病例数", "CMI", "费用", "盈亏"]]
            for row in items:
                rows.append(
                    [
                        str(row.get("name", "")),
                        str(row.get("caseCount", 0)),
                        str(row.get("cmi", 0)),
                        str(row.get("totalCost", 0)),
                        str(row.get("profit", 0)),
                    ]
                )
            elements.append(Table(rows, colWidths=[180, 60, 60, 80, 80]))
            elements.append(Spacer(1, 8))

        elements.append(Paragraph("附录：口径说明", styles["Heading2"]))
        elements.append(Paragraph("一致口径：页面指标与导出指标均来源于同一 /analysis 数据模型。", styles["Normal"]))
        doc.build(elements)
        output.seek(0)
        filename = f"drg_dip_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        return StreamingResponse(
            output,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    try:
        from docx import Document
    except ImportError as exc:
        raise HTTPException(status_code=500, detail=f"DOCX导出依赖缺失: {exc}")

    doc = Document()
    doc.add_heading("DRG/DIP 综合分析报告", level=0)
    doc.add_paragraph(f"统计范围: {start_date or '-'} ~ {end_date or '-'}")
    doc.add_paragraph(f"生成时间: {generated_at}")
    doc.add_paragraph(f"版本标识: {version_id or 'default'}")

    doc.add_heading("总览指标", level=1)
    metric_rows = [
        ("DRG/DIP组数", kpis["drg_dip_group_count"]),
        ("CMI", kpis["cmi"]),
        ("费用消耗指数", kpis["cost_consumption_index"]),
        ("时间消耗指数", kpis["time_consumption_index"]),
        ("低风险组死亡率(%)", kpis["low_risk_mortality_rate"]),
        ("平均住院日", kpis["avg_los"]),
        ("平均住院费用", kpis["avg_cost"]),
        ("医保盈亏", kpis["insurance_profit_loss"]),
    ]
    table = doc.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "指标"
    table.rows[0].cells[1].text = "值"
    for label, value in metric_rows:
        row = table.add_row().cells
        row[0].text = str(label)
        row[1].text = str(value)

    doc.add_heading("五级绩效层级（Top 5）", level=1)
    for level_key in ANALYSIS_REQUIRED_LEVELS:
        doc.add_heading(level_key, level=2)
        rows = levels.get(level_key, {}).get("items", [])[:5]
        if not rows:
            doc.add_paragraph("无数据")
            continue
        t = doc.add_table(rows=1, cols=5)
        hdr = t.rows[0].cells
        hdr[0].text = "名称"
        hdr[1].text = "病例数"
        hdr[2].text = "CMI"
        hdr[3].text = "总费用"
        hdr[4].text = "盈亏"
        for item in rows:
            r = t.add_row().cells
            r[0].text = str(item.get("name", ""))
            r[1].text = str(item.get("caseCount", 0))
            r[2].text = str(item.get("cmi", 0))
            r[3].text = str(item.get("totalCost", 0))
            r[4].text = str(item.get("profit", 0))

    doc.add_heading("盈亏原因分解", level=1)
    rb = profitability.get("reason_breakdown", {})
    doc.add_paragraph(
        f"药品 {rb.get('drug', 0)}%，耗材 {rb.get('material', 0)}%，检查 {rb.get('exam', 0)}%，治疗 {rb.get('treatment', 0)}%，其他 {rb.get('other', 0)}%。"
    )
    doc.add_heading("附录", level=1)
    doc.add_paragraph("口径说明：一致率按统一分析模型计算；样本数据优先，真实库联调请以生产数据复核。")
    output = io.BytesIO()
    doc.save(output)
    output.seek(0)
    filename = f"drg_dip_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
