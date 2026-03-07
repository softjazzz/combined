"""Department and doctor analyzer methods."""

import pandas as pd
from typing import Dict, Any


class DepartmentAnalyzerMixin:
    """科室与医生分析方法"""

    def analyze_department(self) -> pd.DataFrame:
        """科室分析"""
        self.log("科室分析", "正在分析各科室绩效...")
        if "department" not in self.df.columns or "total_cost" not in self.df.columns:
            self.results["department"] = []
            self.results["department_top10"] = []
            return pd.DataFrame()

        df = self.df
        agg_dict = {"total_cost": ["sum", "mean", "count"], "dip_payment": ["sum", "mean"]}
        if "los" in df.columns: agg_dict["los"] = "mean"
        if "profit_loss" in df.columns: agg_dict["profit_loss"] = "sum"

        dept_df = df.groupby("department").agg(agg_dict).round(2)
        dept_df.columns = ["_".join(col).strip() for col in dept_df.columns]
        dept_df = dept_df.rename(columns={
            "total_cost_sum": "总费用", "total_cost_mean": "次均费用", "total_cost_count": "病例数",
            "dip_payment_sum": "总支付标准", "dip_payment_mean": "平均支付标准",
            "los_mean": "平均住院日", "profit_loss_sum": "盈亏"
        })
        if "盈亏" in dept_df.columns and "总费用" in dept_df.columns:
            dept_df["盈亏率%"] = (dept_df["盈亏"] / dept_df["总费用"] * 100).round(2)
        dept_df = dept_df.sort_values("总费用", ascending=False)

        self.results["department"] = dept_df.reset_index().to_dict(orient="records")
        self.results["department_top10"] = dept_df.head(10).reset_index().to_dict(orient="records")
        return dept_df

    def analyze_department_deep_dive(self, dept_name: str) -> Dict:
        """科室深入分析"""
        self.log(f"科室深入分析", f"正在对 [{dept_name}] 进行深度扫描...")
        if "department" not in self.df.columns:
            return {}

        all_depts = self.df["department"].unique().tolist()
        print(f"[DEBUG] 可用科室列表 (共{len(all_depts)}个): {all_depts[:10]}...")
        print(f"[DEBUG] 目标科室参数: '{dept_name}'")

        dept_df = self.df[self.df["department"] == dept_name].copy()
        if len(dept_df) == 0:
            print(f"[DEBUG] 警告: 未找到科室 '{dept_name}' 的数据!")
            return {}

        result = {"department": dept_name}

        # 科内医生绩效
        if "doctor" in dept_df.columns:
            doc_agg = dept_df.groupby("doctor").agg({"total_cost": ["sum", "mean", "count"], "dip_payment": "sum"}).round(2)
            doc_agg.columns = ["总费用", "次均费用", "病例数", "支付标准"]
            doc_agg["盈亏"] = doc_agg["支付标准"] - doc_agg["总费用"]
            result["doctor_performance"] = doc_agg.sort_values("病例数", ascending=False).head(20).reset_index().to_dict(orient="records")

        # 科内病种矩阵
        if "dip_name" in dept_df.columns:
            disease_agg = dept_df.groupby("dip_name").agg({"total_cost": ["sum", "count"], "dip_payment": "sum", "dip_weight": "mean"}).round(2)
            disease_agg.columns = ["总费用", "病例数", "支付标准", "平均分值"]
            disease_agg["盈亏"] = disease_agg["支付标准"] - disease_agg["总费用"]
            result["disease_matrix"] = disease_agg.reset_index().to_dict(orient="records")

        # 科内成本结构
        total_cost = dept_df["total_cost"].sum()
        cost_structure = {}
        cost_fields = {"drug_cost": ["drug_cost", "西药费", "药品费", "药费"],
                       "material_cost": ["material_cost", "耗材费", "医用耗材费"],
                       "service_cost": ["treatment_cost", "nursing_cost", "exam_cost", "治疗费", "检查费"]}
        for type_name, cols in cost_fields.items():
            val = sum(dept_df[c].sum() for c in cols if c in dept_df.columns)
            if total_cost > 0:
                cost_structure[type_name] = {"amount": round(val, 2), "ratio": round(val / total_cost * 100, 2)}
        result["cost_structure"] = cost_structure

        # 科室核心指标
        total_payment = dept_df["dip_payment"].sum() if "dip_payment" in dept_df.columns else 0
        disease_count = profit_disease_count = loss_disease_count = 0
        if "dip_name" in dept_df.columns and "dip_payment" in dept_df.columns:
            disease_stats = dept_df.groupby("dip_name").agg({"total_cost": "sum", "dip_payment": "sum"})
            disease_stats["profit"] = disease_stats["dip_payment"] - disease_stats["total_cost"]
            disease_count = len(disease_stats)
            profit_disease_count = int((disease_stats["profit"] > 0).sum())
            loss_disease_count = int((disease_stats["profit"] < 0).sum())

        core_kpi = {
            "total_cost": round(total_cost, 2), "case_count": len(dept_df),
            "profit_loss": round(total_payment - total_cost, 2) if total_payment else 0,
            "total_payment": round(total_payment, 2),
            "payment_rate": round(total_payment / total_cost * 100, 2) if total_cost > 0 else 0,
            "cmi": 0, "avg_los": 0,
            "disease_count": disease_count, "profit_disease_count": profit_disease_count,
            "loss_disease_count": loss_disease_count
        }
        if "dip_weight" in dept_df.columns: core_kpi["cmi"] = round(dept_df["dip_weight"].mean(), 4)
        if "los" in dept_df.columns: core_kpi["avg_los"] = round(dept_df["los"].mean(), 1)

        # 按医保类型计算盈亏
        if "insurance_type" in dept_df.columns and "dip_payment" in dept_df.columns:
            employee_df = dept_df[dept_df["insurance_type"].str.contains("职工", na=False)]
            core_kpi["employee_profit"] = round(employee_df["dip_payment"].sum() - employee_df["total_cost"].sum(), 2) if len(employee_df) > 0 else 0
            resident_df = dept_df[dept_df["insurance_type"].str.contains("居民|城乡", na=False)]
            core_kpi["resident_profit"] = round(resident_df["dip_payment"].sum() - resident_df["total_cost"].sum(), 2) if len(resident_df) > 0 else 0
        else:
            core_kpi["employee_profit"] = None
            core_kpi["resident_profit"] = None
        result["core_kpi"] = core_kpi

        # 盈亏病种排名
        if "dip_name" in dept_df.columns and "dip_payment" in dept_df.columns:
            disease_pl = dept_df.groupby("dip_name").agg({"total_cost": "sum", "dip_payment": "sum"}).reset_index()
            disease_pl.columns = ["dip_name", "total_cost", "payment"]
            disease_pl["profit_loss"] = disease_pl["payment"] - disease_pl["total_cost"]
            disease_pl["case_count"] = dept_df.groupby("dip_name").size().values
            result["profit_loss_diseases"] = {
                "top_profit": disease_pl.nlargest(10, "profit_loss").to_dict(orient="records"),
                "top_loss": disease_pl.nsmallest(10, "profit_loss").to_dict(orient="records")
            }

        # 亏损病种趋势
        if "dip_name" in dept_df.columns and "discharge_date" in dept_df.columns:
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
        if "doctor" in dept_df.columns and "dip_name" in dept_df.columns:
            top_disease = dept_df["dip_name"].value_counts().head(1).index.tolist()
            if top_disease:
                target_disease = top_disease[0]
                agg_dict = {"total_cost": ["sum", "mean", "count"], "dip_payment": "sum"}
                has_los = "los" in dept_df.columns
                if has_los: agg_dict["los"] = "mean"
                disease_docs = dept_df[dept_df["dip_name"] == target_disease].groupby("doctor").agg(agg_dict).round(2)
                disease_docs.columns = ["总费用", "次均费用", "病例数", "支付标准", "平均住院日"] if has_los else ["总费用", "次均费用", "病例数", "支付标准"]
                disease_docs["盈亏"] = disease_docs["支付标准"] - disease_docs["总费用"]
                result["doctor_disease_comparison"] = {"disease_name": target_disease, "data": disease_docs.reset_index().to_dict(orient="records")}

        # 盈利性能矩阵
        if "dip_name" in dept_df.columns and "dip_payment" in dept_df.columns:
            prof_matrix = dept_df.groupby("dip_name").agg({
                "total_cost": "sum", "dip_payment": "sum",
                "dip_weight": "mean" if "dip_weight" in dept_df.columns else "count"
            }).reset_index()
            prof_matrix.columns = ["dip_name", "total_cost", "payment", "cmi"]
            prof_matrix["case_count"] = dept_df.groupby("dip_name").size().values
            prof_matrix["profit_loss"] = prof_matrix["payment"] - prof_matrix["total_cost"]
            prof_matrix["profitability"] = ((prof_matrix["payment"] - prof_matrix["total_cost"]) / prof_matrix["payment"].replace(0, 1) * 100).round(2)
            result["profitability_matrix"] = prof_matrix.to_dict(orient="records")

        return result

    def analyze_doctor(self) -> pd.DataFrame:
        """医生分析"""
        self.log("医生分析", "正在分析医生工作量和绩效...")
        if "doctor" not in self.df.columns or "total_cost" not in self.df.columns:
            self.results["doctor"] = []
            return pd.DataFrame()

        df = self.df[self.df["doctor"].notna()].copy()
        if len(df) == 0:
            return pd.DataFrame()

        agg_dict = {"total_cost": ["sum", "mean", "count"], "dip_payment": ["sum", "mean"]}
        if "dip_name" in df.columns: agg_dict["dip_name"] = "nunique"
        if "profit_loss" in df.columns: agg_dict["profit_loss"] = "sum"
        if "los" in df.columns: agg_dict["los"] = "mean"

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
