"""Disease analyzer methods."""

import pandas as pd
from typing import Dict, Any


class DiseaseAnalyzerMixin:
    """病种分析方法"""

    def analyze_disease(self) -> pd.DataFrame:
        """病种分析"""
        self.log("病种分析", "正在分析病种结构...")
        if "dip_name" not in self.df.columns or "total_cost" not in self.df.columns:
            self.results["disease"] = []
            self.results["disease_top10"] = []
            return pd.DataFrame()

        df = self.df
        agg_dict = {"total_cost": ["sum", "mean", "count"], "dip_payment": ["sum", "mean"]}
        if "profit_loss" in df.columns: agg_dict["profit_loss"] = "sum"

        disease_df = df.groupby("dip_name").agg(agg_dict).round(2)
        disease_df.columns = ["_".join(col).strip() for col in disease_df.columns]
        disease_df = disease_df.rename(columns={
            "total_cost_sum": "总费用", "total_cost_mean": "次均费用", "total_cost_count": "病例数",
            "dip_payment_sum": "总支付标准", "dip_payment_mean": "平均支付标准", "profit_loss_sum": "盈亏"
        })
        disease_df = disease_df.sort_values("病例数", ascending=False)

        self.results["disease"] = disease_df.head(50).reset_index().to_dict(orient="records")
        self.results["disease_top10"] = disease_df.head(10).reset_index().to_dict(orient="records")
        if "盈亏" in disease_df.columns:
            self.results["disease_profit_top10"] = disease_df.nlargest(10, "盈亏").reset_index().to_dict(orient="records")
            self.results["disease_loss_top10"] = disease_df.nsmallest(10, "盈亏").reset_index().to_dict(orient="records")
        return disease_df

    def analyze_disease_type(self) -> Dict:
        """病种类型分析 - 按核心/综合病种分组"""
        self.log("病种类型分析", "正在按核心/综合病种分组分析...")
        df = self.df

        surgery_col = None
        for col in ["手术分组代码", "surgery_code", "dip_code", "手术分组编码", "操作分组代码", "DIP手术分组代码"]:
            if col in df.columns:
                surgery_col = col
                break
        if not surgery_col:
            print(f"[DIP分析] 未找到手术分组代码列，当前列名: {list(df.columns)[:20]}")
            self.results["disease_type"] = []
            return {}

        df["病种类型"] = df[surgery_col].apply(lambda x: "综合" if x and "ZH" in str(x).upper() else "核心")

        agg_dict = {"total_cost": ["sum", "mean", "count"]}
        if "dip_payment" in df.columns: agg_dict["dip_payment"] = ["sum"]
        if "profit_loss" in df.columns: agg_dict["profit_loss"] = ["sum"]
        if "dip_name" in df.columns: agg_dict["dip_name"] = ["nunique"]

        type_df = df.groupby("病种类型").agg(agg_dict).round(2)
        type_df.columns = ["_".join(col).strip() for col in type_df.columns]
        type_df = type_df.rename(columns={
            "total_cost_sum": "总费用", "total_cost_mean": "次均费用", "total_cost_count": "病例数",
            "dip_payment_sum": "按DIP总费用", "profit_loss_sum": "结余", "dip_name_nunique": "病组数"
        })
        self.results["disease_type"] = type_df.reset_index().to_dict(orient="records")

        # 月度趋势
        if "数据月份" in df.columns:
            trend_df = df.groupby(["数据月份", "病种类型"]).size().reset_index(name="病例数")
            all_months = sorted(df["数据月份"].unique())
            all_types = df["病种类型"].unique()
            disease_type_trend = {"months": [str(m) for m in all_months], "series": {}}
            for t in all_types:
                disease_type_trend["series"][t] = [0] * len(all_months)
            for _, row in trend_df.iterrows():
                m = str(row["数据月份"])
                t = row["病种类型"]
                idx = disease_type_trend["months"].index(m)
                disease_type_trend["series"][t][idx] = int(row["病例数"])
            self.results["disease_type_trend"] = disease_type_trend

        return self.results["disease_type"]

    def analyze_balance_ranking(self) -> Dict:
        """结余排行分析"""
        self.log("结余排行分析", "正在计算病种结余排行...")
        df = self.df
        if "dip_name" not in df.columns or "profit_loss" not in df.columns:
            self.results["balance_top10"] = []
            self.results["balance_bottom10"] = []
            return {}

        balance_df = df.groupby("dip_name").agg({"profit_loss": "sum", "total_cost": ["sum", "count"]}).round(2)
        balance_df.columns = ["结余", "总费用", "病例数"]
        balance_df = balance_df.reset_index().rename(columns={"dip_name": "病种"})

        self.results["balance_top10"] = balance_df.nlargest(10, "结余").to_dict(orient="records")
        self.results["balance_bottom10"] = balance_df.nsmallest(10, "结余").to_dict(orient="records")
        return {"top10": self.results["balance_top10"], "bottom10": self.results["balance_bottom10"]}
