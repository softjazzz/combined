"""Department and doctor analyzer methods."""

import pandas as pd
from typing import Dict, Any


def _safe_series_pct(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    safe_denom = denominator.where(denominator != 0)
    return (numerator / safe_denom * 100).fillna(0.0).round(2)


def _safe_scalar_pct(numerator: float, denominator: float) -> float:
    if pd.isna(numerator) or pd.isna(denominator) or denominator == 0:
        return 0.0
    return round(float(numerator) / float(denominator) * 100, 2)


def _safe_mean(series: pd.Series, digits: int = 2) -> float:
    val = series.mean()
    return round(float(val), digits) if pd.notna(val) else 0.0


class DepartmentAnalyzerMixin:
    """科室与医生分析方法"""

    def analyze_department(self) -> pd.DataFrame:
        """科室分析"""
        self.log("科室分析", "正在分析各科室绩效...")
        if (
            self.df.empty
            or "department" not in self.df.columns
            or "total_cost" not in self.df.columns
        ):
            self.results["department"] = []
            self.results["department_top10"] = []
            return pd.DataFrame()

        df = self.df
        agg_dict: Dict[str, Any] = {"total_cost": ["sum", "mean", "count"]}
        if "dip_payment" in df.columns:
            agg_dict["dip_payment"] = ["sum", "mean"]
        if "los" in df.columns:
            agg_dict["los"] = "mean"
        if "profit_loss" in df.columns:
            agg_dict["profit_loss"] = "sum"

        dept_df = df.groupby("department").agg(agg_dict).round(2)
        dept_df.columns = ["_".join(col).strip() for col in dept_df.columns]
        dept_df = dept_df.rename(columns={
            "total_cost_sum": "总费用", "total_cost_mean": "次均费用", "total_cost_count": "病例数",
            "dip_payment_sum": "总支付标准", "dip_payment_mean": "平均支付标准",
            "los_mean": "平均住院日", "profit_loss_sum": "盈亏"
        })
        if "盈亏" in dept_df.columns and "总费用" in dept_df.columns:
            dept_df["盈亏率%"] = _safe_series_pct(dept_df["盈亏"], dept_df["总费用"])
        dept_df = dept_df.sort_values("总费用", ascending=False)

        self.results["department"] = dept_df.reset_index().to_dict(orient="records")
        self.results["department_top10"] = dept_df.head(10).reset_index().to_dict(orient="records")
        return dept_df

    def analyze_department_deep_dive(self, dept_name: str) -> Dict:
        """科室深入分析"""
        self.log(f"科室深入分析", f"正在对 [{dept_name}] 进行深度扫描...")
        if self.df.empty or "department" not in self.df.columns:
            return {}

        all_depts = self.df["department"].unique().tolist()
        print(f"[DEBUG] 可用科室列表 (共{len(all_depts)}个): {all_depts[:10]}...")
        print(f"[DEBUG] 目标科室参数: '{dept_name}'")

        dept_df = self.df[self.df["department"] == dept_name].copy()
        if len(dept_df) == 0:
            print(f"[DEBUG] 警告: 未找到科室 '{dept_name}' 的数据!")
            return {}

        has_total_cost = "total_cost" in dept_df.columns
        has_dip_payment = "dip_payment" in dept_df.columns
        has_dip_weight = "dip_weight" in dept_df.columns
        result: Dict[str, Any] = {"department": dept_name}

        # 科内医生绩效
        if "doctor" in dept_df.columns and has_total_cost:
            doc_agg_dict: Dict[str, Any] = {"total_cost": ["sum", "mean", "count"]}
            if has_dip_payment:
                doc_agg_dict["dip_payment"] = "sum"
            doc_agg = dept_df.groupby("doctor").agg(doc_agg_dict).round(2)
            doc_agg.columns = ["_".join(col).strip() for col in doc_agg.columns]
            doc_agg = doc_agg.rename(columns={
                "total_cost_sum": "总费用",
                "total_cost_mean": "次均费用",
                "total_cost_count": "病例数",
                "dip_payment_sum": "支付标准",
            })
            if "支付标准" not in doc_agg.columns:
                doc_agg["支付标准"] = 0.0
            doc_agg["盈亏"] = (doc_agg["支付标准"] - doc_agg["总费用"]).round(2)
            result["doctor_performance"] = doc_agg.sort_values("病例数", ascending=False).head(20).reset_index().to_dict(orient="records")

        # 科内病种矩阵
        if "dip_name" in dept_df.columns and has_total_cost:
            disease_agg_dict: Dict[str, Any] = {"total_cost": ["sum", "count"]}
            if has_dip_payment:
                disease_agg_dict["dip_payment"] = "sum"
            if has_dip_weight:
                disease_agg_dict["dip_weight"] = "mean"
            disease_agg = dept_df.groupby("dip_name").agg(disease_agg_dict).round(2)
            disease_agg.columns = ["_".join(col).strip() for col in disease_agg.columns]
            disease_agg = disease_agg.rename(columns={
                "total_cost_sum": "总费用",
                "total_cost_count": "病例数",
                "dip_payment_sum": "支付标准",
                "dip_weight_mean": "平均分值",
            })
            if "支付标准" not in disease_agg.columns:
                disease_agg["支付标准"] = 0.0
            if "平均分值" not in disease_agg.columns:
                disease_agg["平均分值"] = 0.0
            else:
                disease_agg["平均分值"] = disease_agg["平均分值"].fillna(0.0)
            disease_agg["盈亏"] = (disease_agg["支付标准"] - disease_agg["总费用"]).round(2)
            result["disease_matrix"] = disease_agg.reset_index().to_dict(orient="records")

        # 科内成本结构
        total_cost = float(dept_df["total_cost"].sum()) if has_total_cost else 0.0
        if pd.isna(total_cost):
            total_cost = 0.0
        cost_structure = {}
        cost_fields = {"drug_cost": ["drug_cost", "西药费", "药品费", "药费"],
                       "material_cost": ["material_cost", "耗材费", "医用耗材费"],
                       "service_cost": ["treatment_cost", "nursing_cost", "exam_cost", "治疗费", "检查费"]}
        for type_name, cols in cost_fields.items():
            val = float(sum(dept_df[c].sum() for c in cols if c in dept_df.columns))
            if total_cost > 0:
                cost_structure[type_name] = {
                    "amount": round(val, 2),
                    "ratio": _safe_scalar_pct(val, total_cost),
                }
        result["cost_structure"] = cost_structure

        # 科室核心指标
        total_payment = float(dept_df["dip_payment"].sum()) if has_dip_payment else 0.0
        if pd.isna(total_payment):
            total_payment = 0.0
        disease_count = profit_disease_count = loss_disease_count = 0
        if "dip_name" in dept_df.columns and has_total_cost and has_dip_payment:
            disease_stats = dept_df.groupby("dip_name").agg({"total_cost": "sum", "dip_payment": "sum"})
            disease_stats["profit"] = disease_stats["dip_payment"] - disease_stats["total_cost"]
            disease_count = len(disease_stats)
            profit_disease_count = int((disease_stats["profit"] > 0).sum())
            loss_disease_count = int((disease_stats["profit"] < 0).sum())

        core_kpi = {
            "total_cost": round(total_cost, 2), "case_count": len(dept_df),
            "profit_loss": round(total_payment - total_cost, 2) if total_payment else 0,
            "total_payment": round(total_payment, 2),
            "payment_rate": _safe_scalar_pct(total_payment, total_cost) if total_cost > 0 else 0,
            "cmi": 0, "avg_los": 0,
            "disease_count": disease_count, "profit_disease_count": profit_disease_count,
            "loss_disease_count": loss_disease_count
        }
        if has_dip_weight:
            core_kpi["cmi"] = _safe_mean(dept_df["dip_weight"], 4)
        if "los" in dept_df.columns:
            core_kpi["avg_los"] = _safe_mean(dept_df["los"], 1)

        # 按医保类型计算盈亏
        if "insurance_type" in dept_df.columns and has_total_cost and has_dip_payment:
            insurance_series = dept_df["insurance_type"].astype(str)
            employee_df = dept_df[insurance_series.str.contains("职工", na=False)]
            core_kpi["employee_profit"] = round(float(employee_df["dip_payment"].sum() - employee_df["total_cost"].sum()), 2) if len(employee_df) > 0 else 0
            resident_df = dept_df[insurance_series.str.contains("居民|城乡", na=False)]
            core_kpi["resident_profit"] = round(float(resident_df["dip_payment"].sum() - resident_df["total_cost"].sum()), 2) if len(resident_df) > 0 else 0
        else:
            core_kpi["employee_profit"] = None
            core_kpi["resident_profit"] = None
        result["core_kpi"] = core_kpi

        # 盈亏病种排名
        if "dip_name" in dept_df.columns and has_total_cost and has_dip_payment:
            disease_pl = dept_df.groupby("dip_name").agg({"total_cost": "sum", "dip_payment": "sum"}).reset_index()
            disease_pl.columns = ["dip_name", "total_cost", "payment"]
            disease_pl["profit_loss"] = disease_pl["payment"] - disease_pl["total_cost"]
            disease_pl["case_count"] = dept_df.groupby("dip_name").size().values
            result["profit_loss_diseases"] = {
                "top_profit": disease_pl.nlargest(10, "profit_loss").to_dict(orient="records"),
                "top_loss": disease_pl.nsmallest(10, "profit_loss").to_dict(orient="records")
            }

        # 亏损病种趋势
        if "dip_name" in dept_df.columns and "discharge_date" in dept_df.columns and has_total_cost and has_dip_payment:
            if "profit_loss_diseases" in result:
                loss_diseases = [d["dip_name"] for d in result["profit_loss_diseases"]["top_loss"][:3]]
                dept_df["month"] = pd.to_datetime(dept_df["discharge_date"], errors="coerce").dt.to_period("M")
                loss_trend_data = []
                for disease in loss_diseases:
                    disease_df = dept_df[dept_df["dip_name"] == disease]
                    monthly = disease_df.groupby("month").agg({"total_cost": "sum", "dip_payment": "sum"}).reset_index()
                    monthly["profit_loss"] = monthly["dip_payment"] - monthly["total_cost"]
                    monthly["month"] = monthly["month"].astype(str)
                    loss_trend_data.append({"disease": disease, "trend": monthly[["month", "profit_loss"]].to_dict(orient="records")})
                result["loss_trend"] = loss_trend_data

        # 同病种不同医生对比
        if "doctor" in dept_df.columns and "dip_name" in dept_df.columns and has_total_cost:
            top_disease = dept_df["dip_name"].value_counts().head(1).index.tolist()
            if top_disease:
                target_disease = top_disease[0]
                agg_dict: Dict[str, Any] = {"total_cost": ["sum", "mean", "count"]}
                if has_dip_payment:
                    agg_dict["dip_payment"] = "sum"
                has_los = "los" in dept_df.columns
                if has_los:
                    agg_dict["los"] = "mean"
                disease_docs = dept_df[dept_df["dip_name"] == target_disease].groupby("doctor").agg(agg_dict).round(2)
                disease_docs.columns = ["_".join(col).strip() for col in disease_docs.columns]
                disease_docs = disease_docs.rename(columns={
                    "total_cost_sum": "总费用",
                    "total_cost_mean": "次均费用",
                    "total_cost_count": "病例数",
                    "dip_payment_sum": "支付标准",
                    "los_mean": "平均住院日",
                })
                if "支付标准" not in disease_docs.columns:
                    disease_docs["支付标准"] = 0.0
                disease_docs["盈亏"] = (disease_docs["支付标准"] - disease_docs["总费用"]).round(2)
                result["doctor_disease_comparison"] = {"disease_name": target_disease, "data": disease_docs.reset_index().to_dict(orient="records")}

        # 盈利性能矩阵
        if "dip_name" in dept_df.columns and has_total_cost and has_dip_payment:
            prof_agg: Dict[str, Any] = {"total_cost": "sum", "dip_payment": "sum"}
            if has_dip_weight:
                prof_agg["dip_weight"] = "mean"
            prof_matrix = dept_df.groupby("dip_name").agg(prof_agg).reset_index()
            prof_matrix = prof_matrix.rename(columns={
                "dip_payment": "payment",
                "dip_weight": "cmi",
            })
            if "cmi" not in prof_matrix.columns:
                prof_matrix["cmi"] = 0.0
            else:
                prof_matrix["cmi"] = prof_matrix["cmi"].fillna(0.0).round(4)
            prof_matrix["case_count"] = dept_df.groupby("dip_name").size().values
            prof_matrix["profit_loss"] = (prof_matrix["payment"] - prof_matrix["total_cost"]).round(2)
            prof_matrix["profitability"] = _safe_series_pct(
                prof_matrix["profit_loss"], prof_matrix["payment"]
            )
            result["profitability_matrix"] = prof_matrix.to_dict(orient="records")

        return result

    def analyze_doctor(self) -> pd.DataFrame:
        """医生分析"""
        self.log("医生分析", "正在分析医生工作量和绩效...")
        if (
            self.df.empty
            or "doctor" not in self.df.columns
            or "total_cost" not in self.df.columns
        ):
            self.results["doctor"] = []
            self.results["doctor_top10"] = []
            return pd.DataFrame()

        df = self.df[self.df["doctor"].notna()].copy()
        if len(df) == 0:
            self.results["doctor"] = []
            self.results["doctor_top10"] = []
            return pd.DataFrame()

        agg_dict: Dict[str, Any] = {"total_cost": ["sum", "mean", "count"]}
        if "dip_payment" in df.columns:
            agg_dict["dip_payment"] = ["sum", "mean"]
        if "dip_name" in df.columns:
            agg_dict["dip_name"] = "nunique"
        if "profit_loss" in df.columns:
            agg_dict["profit_loss"] = "sum"
        if "los" in df.columns:
            agg_dict["los"] = "mean"

        doctor_df = df.groupby("doctor").agg(agg_dict).round(2)
        doctor_df.columns = ["_".join(col).strip() for col in doctor_df.columns]
        doctor_df = doctor_df.rename(columns={
            "total_cost_sum": "总费用", "total_cost_mean": "次均费用", "total_cost_count": "病例数",
            "dip_payment_sum": "总支付标准", "dip_payment_mean": "平均支付标准",
            "dip_name_nunique": "病种数", "profit_loss_sum": "盈亏", "los_mean": "平均住院日"
        })
        doctor_df = doctor_df.sort_values("病例数", ascending=False)
        self.results["doctor"] = doctor_df.head(50).reset_index().to_dict(orient="records")
        self.results["doctor_top10"] = doctor_df.head(10).reset_index().to_dict(orient="records")
        return doctor_df
