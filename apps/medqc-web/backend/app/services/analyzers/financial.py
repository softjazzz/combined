"""Financial, insurance, and monthly trend analyzer methods."""

import pandas as pd
from typing import Dict, Any


def _safe_pct(numerator: float, denominator: float) -> float:
    if pd.isna(numerator) or pd.isna(denominator) or denominator == 0:
        return 0.0
    return round(float(numerator) / float(denominator) * 100, 2)


class FinancialAnalyzerMixin:
    """财务/保险/月度趋势/资金流向分析方法"""

    def analyze_monthly_trend(self) -> pd.DataFrame:
        """月度趋势分析"""
        self.log("月度趋势", "正在分析月度变化趋势...")
        if (
            self.df.empty
            or "数据月份" not in self.df.columns
            or "total_cost" not in self.df.columns
        ):
            self.results["monthly_trend"] = []
            self.results["point_value_trend"] = []
            return pd.DataFrame()

        df = self.df
        agg_dict: Dict[str, Any] = {"total_cost": ["sum", "mean", "count"]}
        if "dip_payment" in df.columns:
            agg_dict["dip_payment"] = ["sum", "mean"]
        if "profit_loss" in df.columns:
            agg_dict["profit_loss"] = "sum"
        if "dip_name" in df.columns:
            agg_dict["dip_name"] = "nunique"

        monthly_df = df.groupby("数据月份").agg(agg_dict).round(2)
        monthly_df.columns = ["_".join(col).strip() for col in monthly_df.columns]
        monthly_df = monthly_df.rename(columns={
            "total_cost_sum": "总费用", "total_cost_mean": "次均费用", "total_cost_count": "病例数",
            "dip_payment_sum": "按DIP总费用", "dip_payment_mean": "按DIP平均费用",
            "profit_loss_sum": "结余", "dip_name_nunique": "病组数"
        })
        try:
            monthly_df = monthly_df.sort_index()
        except Exception:
            pass

        self.results["monthly_trend"] = monthly_df.reset_index().to_dict(orient="records")
        self._analyze_point_value_trend(df)
        return monthly_df

    def _analyze_point_value_trend(self, df: pd.DataFrame):
        """月度点值趋势分析"""
        point_value_cols = [col for col in ["预结算点值", "职工点值", "居民点值", "point_value"] if col in df.columns]
        if df.empty or not point_value_cols or "数据月份" not in df.columns:
            self.results["point_value_trend"] = []
            return

        trend_data = []
        for month in df["数据月份"].unique():
            month_df = df[df["数据月份"] == month]
            row: Dict[str, Any] = {"月份": month}
            for col in point_value_cols:
                if col in month_df.columns:
                    mean_val = month_df[col].mean()
                    row[col] = round(float(mean_val), 4) if pd.notna(mean_val) else 0.0
            trend_data.append(row)
        try:
            trend_data = sorted(trend_data, key=lambda x: x["月份"])
        except Exception:
            pass
        self.results["point_value_trend"] = trend_data

    def analyze_payment_distribution(self) -> pd.DataFrame:
        """支付标准区间分布"""
        self.log("支付分布", "正在分析支付标准区间分布...")
        if (
            self.df.empty
            or "dip_payment" not in self.df.columns
            or "total_cost" not in self.df.columns
        ):
            self.results["payment_distribution"] = []
            return pd.DataFrame()

        df = self.df.copy()
        bins = [0, 2000, 3000, 4000, 5000, 8000, 10000, 20000, float('inf')]
        labels = ['0-2000', '2000-3000', '3000-4000', '4000-5000', '5000-8000', '8000-10000', '10000-20000', '20000+']
        df['支付区间'] = pd.cut(df['dip_payment'], bins=bins, labels=labels)

        dist_df = df.groupby('支付区间', observed=False).agg({'total_cost': ['count', 'sum', 'mean']}).round(2)
        dist_df.columns = ['病例数', '总费用', '平均费用']
        dist_df['平均费用'] = dist_df['平均费用'].fillna(0.0)
        total_cases = dist_df['病例数'].sum()
        dist_df['占比%'] = (
            (dist_df['病例数'] / total_cases * 100).round(2)
            if pd.notna(total_cases) and total_cases > 0
            else 0.0
        )
        self.results["payment_distribution"] = dist_df.reset_index().to_dict(orient="records")
        return dist_df

    def analyze_profit_loss(self) -> Dict:
        """盈亏分析"""
        self.log("盈亏分析", "正在分析盈亏结构...")
        df = self.df.copy()
        if "profit_loss" not in df.columns:
            if "total_cost" in df.columns and "dip_payment" in df.columns:
                df["profit_loss"] = df["dip_payment"] - df["total_cost"]
            else:
                self.results["profit_analysis"] = {}
                return {}

        total_cases = len(df)
        profit_cases = df[df["profit_loss"] > 0]
        loss_cases = df[df["profit_loss"] <= 0]
        profit_analysis = {
            "profit_case_count": len(profit_cases),
            "profit_case_rate": _safe_pct(len(profit_cases), total_cases),
            "total_profit": round(float(profit_cases["profit_loss"].sum()), 2) if len(profit_cases) > 0 else 0.0,
            "loss_case_count": len(loss_cases),
            "loss_case_rate": _safe_pct(len(loss_cases), total_cases),
            "total_loss": round(float(loss_cases["profit_loss"].sum()), 2) if len(loss_cases) > 0 else 0.0,
            "net_profit_loss": round(float(df["profit_loss"].sum()), 2) if total_cases > 0 else 0.0,
        }
        self.results["profit_analysis"] = profit_analysis
        return profit_analysis

    def analyze_cost_structure(self) -> Dict:
        """费用构成分析"""
        self.log("费用构成", "正在分析费用构成...")
        df = self.df
        if df.empty or "total_cost" not in df.columns:
            self.results["cost_structure"] = {}
            return {}

        total_cost = float(df["total_cost"].sum())
        if pd.isna(total_cost):
            total_cost = 0.0
        cost_fields = {
            "drug_cost": ["drug_cost", "西药费", "药品费", "药费"],
            "treatment_cost": ["treatment_cost", "治疗费"],
            "exam_cost": ["exam_cost", "检查费", "检验费"],
            "material_cost": ["material_cost", "材料费", "耗材费"],
            "nursing_cost": ["nursing_cost", "护理费"],
            "bed_cost": ["bed_cost", "床位费"],
        }

        cost_breakdown = {}
        mapped_total = 0.0
        for cost_type, possible_cols in cost_fields.items():
            for col in possible_cols:
                if col in df.columns:
                    amount = float(df[col].sum())
                    if pd.notna(amount) and amount > 0:
                        cost_breakdown[cost_type] = {
                            "amount": round(amount, 2),
                            "ratio": _safe_pct(amount, total_cost) if total_cost > 0 else 0.0,
                        }
                        mapped_total += amount
                    break

        other_amount = total_cost - mapped_total
        if other_amount > 0:
            cost_breakdown["other_cost"] = {
                "amount": round(float(other_amount), 2),
                "ratio": _safe_pct(other_amount, total_cost) if total_cost > 0 else 0.0,
            }

        # 药占比趋势
        drug_trend = []
        if "admission_date" in df.columns or "入院日期" in df.columns:
            date_col = "admission_date" if "admission_date" in df.columns else "入院日期"
            df_copy = df.copy()
            df_copy["月份"] = pd.to_datetime(df_copy[date_col], errors='coerce').dt.to_period('M')
            drug_col = next((c for c in ["drug_cost", "西药费", "药品费"] if c in df_copy.columns), None)
            if drug_col:
                monthly = df_copy.groupby("月份").agg({"total_cost": "sum", drug_col: "sum"}).round(2)
                for period, row in monthly.iterrows():
                    if pd.notna(row["total_cost"]) and row["total_cost"] > 0:
                        drug_trend.append({
                            "month": str(period),
                            "drug_ratio": _safe_pct(row[drug_col], row["total_cost"]),
                        })

        result = {"breakdown": cost_breakdown, "drug_trend": drug_trend, "total_cost": round(float(total_cost), 2)}
        self.results["cost_structure"] = result
        return result

    def analyze_insurance_type(self) -> Dict:
        """医保类型分析"""
        self.log("医保类型", "正在分析医保类型分布...")
        df = self.df
        total = len(df)

        insurance_dist = []
        insurance_col = next((c for c in ["insurance_type", "险种类型", "医疗类别"] if c in df.columns), None)
        if insurance_col and total > 0:
            dist = df[insurance_col].value_counts()
            insurance_dist = [{"type": str(name) if name else "未知", "count": int(count), "ratio": _safe_pct(count, total)}
                              for name, count in dist.items()]

        location_dist = []
        location_col = next((c for c in ["异地标志", "is_remote", "异地"] if c in df.columns), None)
        if location_col and total > 0:
            dist = df[location_col].value_counts()
            location_dist = [{"type": "异地" if str(name) in ["1", "是", "Y", "异地"] else "本地",
                              "count": int(count), "ratio": _safe_pct(count, total)} for name, count in dist.items()]

        region_dist = []
        region_col = next((c for c in ["参保所属医保区划", "统筹区", "所属区划"] if c in df.columns), None)
        if region_col and total > 0:
            dist = df[region_col].value_counts().head(10)
            region_dist = [{"region": str(name)[:20] if name else "未知", "count": int(count), "ratio": _safe_pct(count, total)}
                           for name, count in dist.items()]

        result = {"insurance_distribution": insurance_dist, "location_distribution": location_dist, "region_distribution": region_dist}
        self.results["insurance_analysis"] = result
        return result

    def analyze_fund_flow(self) -> Dict:
        """资金流向分析 (全院 -> 科室 -> 医生)"""
        self.log("资金流向", "正在分析资金流向 (全院 -> 科室 -> 医生)...")
        df = self.df
        if "total_cost" not in df.columns or "department" not in df.columns or "doctor" not in df.columns:
            self.results["fund_flow"] = None
            return {}

        dept_flow = df.groupby("department")["total_cost"].sum().sort_values(ascending=False)
        top_depts = dept_flow.head(8)
        nodes = [{"name": "全院投入"}]
        links = []

        for dept_name, cost in top_depts.items():
            dept_node = f"科室-{dept_name}"
            nodes.append({"name": dept_node})
            links.append({"source": "全院投入", "target": dept_node, "value": round(float(cost), 2)})
            dept_doctors = df[df["department"] == dept_name].groupby("doctor")["total_cost"].sum().nlargest(3)
            for doc_name, doc_cost in dept_doctors.items():
                doc_node = f"医生-{doc_name}"
                if not any(n["name"] == doc_node for n in nodes):
                    nodes.append({"name": doc_node})
                links.append({"source": dept_node, "target": doc_node, "value": round(float(doc_cost), 2)})

        self.results["fund_flow"] = {"nodes": nodes, "links": links}
        return self.results["fund_flow"]

    def analyze_cost_structure_flow(self) -> Dict:
        """资金流向分析 (全院 -> 费用类型 -> 科室)"""
        self.log("资金流向(结构)", "正在分析资金流向 (全院 -> 费用类型 -> 科室)...")
        df = self.df
        if "total_cost" not in df.columns or "department" not in df.columns:
            self.results["fund_flow_structure"] = None
            return {}

        cost_fields = {
            "药品费": ["西药费", "中成药费", "中草药费", "药品费"],
            "耗材费": ["耗材费", "医用耗材费", "一次性耗材费", "材料费"],
            "医疗服务费": ["诊察费", "手术费", "治疗费", "护理费", "床位费", "检查费", "化验费"],
            "其他费用": ["一般诊疗费", "挂号费", "其他费", "其他费用"]
        }

        type_totals, valid_cost_cols = {}, {}
        mapped_total = 0
        total_cost = df["total_cost"].sum()

        for type_name, cols in cost_fields.items():
            current_type_cols, type_sum = [], 0
            for col in cols:
                if col in df.columns:
                    current_type_cols.append(col)
                    type_sum += df[col].sum()
            if type_sum > 0:
                type_totals[type_name] = type_sum
                mapped_total += type_sum
                valid_cost_cols[type_name] = current_type_cols

        other_sum = total_cost - mapped_total
        if other_sum > 0:
            type_totals["其他费用"] = other_sum

        nodes = [{"name": "全院投入"}]
        links = []
        for type_name, value in type_totals.items():
            nodes.append({"name": type_name})
            links.append({"source": "全院投入", "target": type_name, "value": round(float(value), 2)})

        top_depts = df.groupby("department")["total_cost"].sum().nlargest(5).index.tolist()
        for dept in top_depts:
            dept_node = f"科室-{dept}"
            nodes.append({"name": dept_node})
            dept_df = df[df["department"] == dept]
            for type_name, cols in valid_cost_cols.items():
                dept_type_sum = sum(dept_df[col].sum() for col in cols)
                if dept_type_sum > 0:
                    links.append({"source": type_name, "target": dept_node, "value": round(float(dept_type_sum), 2)})
            dept_total = dept_df["total_cost"].sum()
            dept_mapped = sum(dept_df[col].sum() for cols in valid_cost_cols.values() for col in cols)
            dept_other = dept_total - dept_mapped
            if dept_other > 0 and "其他费用" in type_totals:
                links.append({"source": "其他费用", "target": dept_node, "value": round(float(dept_other), 2)})

        self.results["fund_flow_structure"] = {"nodes": nodes, "links": links}
        return self.results["fund_flow_structure"]

    def analyze_rate_type(self) -> Dict:
        """倍率类型分析"""
        self.log("倍率类型分析", "正在按倍率类型分组分析...")
        if self.df.empty or "total_cost" not in self.df.columns:
            self.results["rate_type"] = []
            return {}
        df = self.df.copy()

        rate_col = next((c for c in ["分值状态", "rate_status", "rate_type", "倍率类型", "分值类型"] if c in df.columns), None)

        if rate_col:
            rate_labels = {1: "低倍率", 2: "正常", 3: "高倍率"}
            df["倍率类型"] = df[rate_col].map(rate_labels).fillna("其他")
        elif "dip_payment" in df.columns:
            print("[DIP分析] 未找到分值状态列，将根据费用/支付标准动态计算倍率类型")
            def calc_rate_type(row):
                cost = row.get("total_cost", 0)
                payment = row.get("dip_payment", 0)
                cost = 0.0 if pd.isna(cost) else float(cost)
                payment = 0.0 if pd.isna(payment) else float(payment)
                if payment <= 0:
                    return "其他"
                if cost > payment * 2:
                    return "高倍率"
                elif cost < payment * 0.5:
                    return "低倍率"
                else:
                    return "正常"
            df["倍率类型"] = df.apply(calc_rate_type, axis=1)
        else:
            self.results["rate_type"] = []
            return {}

        agg_dict: Dict[str, Any] = {"total_cost": ["sum", "mean", "count"]}
        if "dip_payment" in df.columns:
            agg_dict["dip_payment"] = ["sum"]
        if "profit_loss" in df.columns:
            agg_dict["profit_loss"] = ["sum"]
        if "dip_name" in df.columns:
            agg_dict["dip_name"] = ["nunique"]

        rate_df = df.groupby("倍率类型").agg(agg_dict).round(2)
        rate_df.columns = ["_".join(col).strip() for col in rate_df.columns]
        rate_df = rate_df.rename(columns={
            "total_cost_sum": "总费用", "total_cost_mean": "次均费用", "total_cost_count": "病例数",
            "dip_payment_sum": "按DIP总费用", "profit_loss_sum": "结余", "dip_name_nunique": "病组数"
        })
        self.results["rate_type"] = rate_df.reset_index().to_dict(orient="records")

        # 月度趋势
        if "数据月份" in df.columns:
            trend_df = df.groupby(["数据月份", "倍率类型"]).size().reset_index(name="病例数")
            all_months = sorted(df["数据月份"].unique())
            all_types = df["倍率类型"].unique()
            rate_type_trend = {"months": [str(m) for m in all_months], "series": {}}
            for t in all_types:
                rate_type_trend["series"][t] = [0] * len(all_months)
            for _, row in trend_df.iterrows():
                m = str(row["数据月份"])
                t = row["倍率类型"]
                idx = rate_type_trend["months"].index(m)
                rate_type_trend["series"][t][idx] = int(row["病例数"])
            self.results["rate_type_trend"] = rate_type_trend

        return self.results["rate_type"]
