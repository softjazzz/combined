"""Base analyzer mixin - core methods, initialization, column mapping, exports."""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
from datetime import datetime
import json


class BaseAnalyzerMixin:
    """核心方法: __init__, column mapping, log, run_full_analysis, overview, exports"""

    def __init__(self, df: pd.DataFrame, user_mappings: Dict[str, str] = None, target_department: str = None):
        """初始化分析器"""
        print(f"[EnhancedAnalyzer] 初始化，收到 user_mappings: {type(user_mappings)}, 长度: {len(user_mappings) if user_mappings else 0}")
        print(f"[EnhancedAnalyzer] 目标科室: {target_department}")
        print(f"[EnhancedAnalyzer] DataFrame 列: {list(df.columns)[:10]}...")
        self.df = self._apply_column_mapping(df.copy(), user_mappings)
        print(f"[EnhancedAnalyzer] 映射后列: {list(self.df.columns)[:10]}...")
        self.results: Dict[str, Any] = {}
        self.analysis_log: List[Dict] = []
        self.target_department = target_department

    def _apply_column_mapping(self, df: pd.DataFrame, user_mappings: Dict[str, str] = None) -> pd.DataFrame:
        """只使用 LLM 智能映射的列名转换"""
        if not user_mappings:
            print("[EnhancedAnalyzer] 警告: 没有提供 LLM 映射，将尝试使用内置别名")
            user_mappings = {}

        rename_map = {}
        used_standard_names = set()
        for original_col, standard_name in user_mappings.items():
            if original_col in df.columns and standard_name not in used_standard_names:
                rename_map[original_col] = standard_name
                used_standard_names.add(standard_name)

        if rename_map:
            df = df.rename(columns=rename_map)
            print(f"[EnhancedAnalyzer] LLM 映射已应用: {rename_map}")
        else:
            print("[EnhancedAnalyzer] 警告: 没有有效的列名映射可应用")

        internal_aliases = {
            "department_name": "department", "attending_doctor": "doctor",
            "actual_cost": "total_cost", "main_diagnosis": "diagnosis_name",
            "main_diagnosis_code": "diagnosis_code", "dip_payment_amount": "dip_payment",
            "profit_loss_amount": "profit_loss",
        }

        direct_aliases = {
            "住院医疗总费用": "total_cost", "住院总费用": "total_cost", "总费用": "total_cost",
            "住院费用": "total_cost", "医疗总费用": "total_cost",
            "统筹支出": "dip_payment", "DIP支付标准": "dip_payment", "支付标准": "dip_payment",
            "DIP统筹支付总金额": "dip_payment", "盈亏额": "profit_loss",
            "科室": "department", "出院科室名称": "department", "住院科室": "department",
            "主管医生": "doctor", "主诊医师姓名": "doctor", "主治医师": "doctor", "医师姓名": "doctor",
            "分组名称": "dip_name", "病种名称": "dip_name", "分组编码": "dip_code", "病种编码": "dip_code",
            "分组病种分值": "dip_weight", "实际结算分值": "dip_weight",
            "住院天数": "los", "实际住院天数": "los",
            "入院日期": "admission_date", "出院日期": "discharge_date", "结算日期": "discharge_date",
            "险种类型": "insurance_type", "医保类型": "insurance_type", "医疗类别": "insurance_type",
        }

        alias_rename = {}
        for llm_name, internal_name in internal_aliases.items():
            if llm_name in df.columns and internal_name not in df.columns:
                alias_rename[llm_name] = internal_name
        if alias_rename:
            df = df.rename(columns=alias_rename)
            print(f"[EnhancedAnalyzer] 内部别名转换: {alias_rename}")

        direct_rename = {}
        for chinese_name, internal_name in direct_aliases.items():
            if chinese_name in df.columns and internal_name not in df.columns:
                direct_rename[chinese_name] = internal_name
        if direct_rename:
            df = df.rename(columns=direct_rename)
            print(f"[EnhancedAnalyzer] 直接别名转换: {direct_rename}")

        if df.columns.duplicated().any():
            dup_cols = df.columns[df.columns.duplicated()].unique().tolist()
            print(f"[EnhancedAnalyzer] 警告: 检测到重复列名，将只保留第一个: {dup_cols}")
            df = df.loc[:, ~df.columns.duplicated()]

        if "profit_loss" not in df.columns and "total_cost" in df.columns and "dip_payment" in df.columns:
            df["profit_loss"] = df["dip_payment"] - df["total_cost"]
            print("[EnhancedAnalyzer] 已计算派生字段: profit_loss")

        if "department" in df.columns:
            df["department"] = df["department"].fillna("未知科室")

        print(f"[EnhancedAnalyzer] 最终可用列: {[c for c in df.columns if c in ['department', 'total_cost', 'dip_payment', 'profit_loss', 'doctor', 'los']]}")
        return df

    def log(self, step: str, message: str):
        """记录分析日志"""
        self.analysis_log.append({"step": step, "message": message, "time": datetime.now().isoformat()})

    def run_full_analysis(self) -> Dict[str, Any]:
        """运行全部分析"""
        self.log("开始分析", "正在执行多维度数据分析...")

        self.analyze_overview()
        self.analyze_department()
        self.analyze_disease()
        self.analyze_doctor()
        self.analyze_monthly_trend()
        self.analyze_payment_distribution()
        self.analyze_profit_loss()
        self.analyze_cost_structure()
        self.analyze_insurance_type()
        self.analyze_fund_flow()
        self.analyze_cost_structure_flow()
        self.analyze_rate_type()
        self.analyze_disease_type()
        self.analyze_balance_ranking()

        # 科室深度分析
        print(f"[DEBUG run_full_analysis] 检查科室深度分析条件...")
        if "department" in self.df.columns and "total_cost" in self.df.columns:
            if self.target_department and self.target_department != '__ALL__':
                self.log("科室深度分析", f"分析指定科室: {self.target_department}")
                deep_dive_data = self.analyze_department_deep_dive(self.target_department)
                deep_dive_data["rank"] = 1
                self.results["dept_deep_dive_list"] = [deep_dive_data]
                self.results["top_dept_deep_dive"] = deep_dive_data
            elif self.target_department == '__ALL__':
                all_depts = self.df.groupby("department")["total_cost"].sum().sort_values(ascending=False).index.tolist()
                self.log("科室深度分析", f"全部科室分析模式，共 {len(all_depts)} 个科室")
                self.results["dept_deep_dive_list"] = []
                for rank, dept_name in enumerate(all_depts):
                    deep_dive_data = self.analyze_department_deep_dive(dept_name)
                    deep_dive_data["rank"] = rank + 1
                    self.results["dept_deep_dive_list"].append(deep_dive_data)
                if self.results["dept_deep_dive_list"]:
                    self.results["top_dept_deep_dive"] = self.results["dept_deep_dive_list"][0]
            else:
                top_depts = self.df.groupby("department")["total_cost"].sum().nlargest(5).index.tolist()
                self.results["dept_deep_dive_list"] = []
                for rank, dept_name in enumerate(top_depts):
                    deep_dive_data = self.analyze_department_deep_dive(dept_name)
                    deep_dive_data["rank"] = rank + 1
                    self.results["dept_deep_dive_list"].append(deep_dive_data)
                if self.results["dept_deep_dive_list"]:
                    self.results["top_dept_deep_dive"] = self.results["dept_deep_dive_list"][0]

        self.log("分析完成", f"共完成 {len(self.results)} 个分析维度")
        return self._convert_types(self.results)

    def _convert_types(self, obj):
        """递归转换 numpy 类型为 Python 原生类型"""
        if isinstance(obj, dict):
            return {k: self._convert_types(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_types(i) for i in obj]
        elif isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float64, np.float32)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif pd.isna(obj):
            return None
        return obj

    def analyze_overview(self) -> Dict:
        """总体概况分析（丰富版）"""
        self.log("总体概况", "正在计算全院汇总指标...")
        df = self.df
        total_cases = len(df)
        total_cost = df["total_cost"].sum() if "total_cost" in df.columns else 0
        total_payment = df["dip_payment"].sum() if "dip_payment" in df.columns else 0
        avg_cost = df["total_cost"].mean() if "total_cost" in df.columns else 0
        avg_los = df["los"].mean() if "los" in df.columns else 0
        total_profit = 0
        if "profit_loss" in df.columns:
            total_profit = df["profit_loss"].sum()
        elif "total_cost" in df.columns and "dip_payment" in df.columns:
            total_profit = total_payment - total_cost

        overview = {
            "total_cases": int(total_cases), "total_cost": round(float(total_cost), 2),
            "total_payment": round(float(total_payment), 2), "total_profit_loss": round(float(total_profit), 2),
            "avg_cost_per_case": round(float(avg_cost), 2),
            "avg_payment_per_case": round(float(df["dip_payment"].mean() if "dip_payment" in df.columns else 0), 2),
            "avg_los": round(float(avg_los), 2),
            "profit_rate": round((total_profit / total_cost * 100) if total_cost > 0 else 0, 2),
            "department_count": df["department"].nunique() if "department" in df.columns else 0,
            "disease_count": df["dip_name"].nunique() if "dip_name" in df.columns else 0,
            "doctor_count": df["doctor"].nunique() if "doctor" in df.columns else 0,
        }

        # ---- 扩展指标 ----

        # CMI (Case Mix Index)
        if "dip_weight" in df.columns:
            weights = df["dip_weight"].dropna()
            if len(weights) > 0:
                overview["cmi"] = round(float(weights.mean()), 4)
                overview["median_weight"] = round(float(weights.median()), 4)

        # 药占比
        drug_col = next((c for c in ["drug_cost", "西药费", "药品费", "药费"] if c in df.columns), None)
        if drug_col and total_cost > 0:
            drug_total = df[drug_col].sum()
            overview["drug_cost_ratio"] = round(float(drug_total / total_cost * 100), 2)

        # 费用回收率
        if total_cost > 0 and total_payment > 0:
            overview["cost_recovery_rate"] = round(float(total_payment / total_cost * 100), 2)

        # 盈亏分布
        if "profit_loss" in df.columns:
            profit_cases = df[df["profit_loss"] > 0]
            loss_cases = df[df["profit_loss"] <= 0]
            overview["profit_case_count"] = int(len(profit_cases))
            overview["loss_case_count"] = int(len(loss_cases))
            overview["profit_case_rate"] = round(len(profit_cases) / total_cases * 100, 2) if total_cases > 0 else 0
            overview["avg_profit_per_case"] = round(float(profit_cases["profit_loss"].mean()), 2) if len(profit_cases) > 0 else 0
            overview["avg_loss_per_case"] = round(float(loss_cases["profit_loss"].mean()), 2) if len(loss_cases) > 0 else 0

        # Top3 亏损科室
        if "profit_loss" in df.columns and "department" in df.columns:
            dept_profit = df.groupby("department")["profit_loss"].sum().sort_values()
            top_loss_depts = dept_profit.head(3)
            overview["top_loss_departments"] = [
                {"name": str(dept), "loss": round(float(val), 2)}
                for dept, val in top_loss_depts.items() if val < 0
            ]

        # Top3 亏损病种
        if "profit_loss" in df.columns and "dip_name" in df.columns:
            disease_profit = df.groupby("dip_name")["profit_loss"].sum().sort_values()
            top_loss_diseases = disease_profit.head(3)
            overview["top_loss_diseases"] = [
                {"name": str(d), "loss": round(float(v), 2)}
                for d, v in top_loss_diseases.items() if v < 0
            ]

        # 高低倍率占比
        rate_col = next((c for c in ["分值状态", "rate_status", "倍率类型"] if c in df.columns), None)
        if rate_col:
            rate_dist = df[rate_col].value_counts(normalize=True) * 100
            overview["rate_distribution"] = {str(k): round(v, 2) for k, v in rate_dist.items()}
        elif "total_cost" in df.columns and "dip_payment" in df.columns:
            ratios = df["total_cost"] / df["dip_payment"].replace(0, float('nan'))
            high_rate = (ratios > 2).sum()
            low_rate = (ratios < 0.5).sum()
            overview["high_rate_count"] = int(high_rate)
            overview["low_rate_count"] = int(low_rate)
            overview["high_rate_pct"] = round(high_rate / total_cases * 100, 2) if total_cases > 0 else 0
            overview["low_rate_pct"] = round(low_rate / total_cases * 100, 2) if total_cases > 0 else 0

        # 住院天数分布
        if "los" in df.columns:
            los_series = df["los"].dropna()
            if len(los_series) > 0:
                overview["median_los"] = round(float(los_series.median()), 1)
                overview["los_over_14"] = int((los_series > 14).sum())
                overview["los_over_14_pct"] = round((los_series > 14).sum() / total_cases * 100, 2) if total_cases > 0 else 0

        # 月度趋势方向
        if "数据月份" in df.columns:
            monthly_counts = df.groupby("数据月份").size()
            if len(monthly_counts) >= 2:
                overview["month_count"] = int(len(monthly_counts))
                first_half = monthly_counts.iloc[:len(monthly_counts)//2].mean()
                second_half = monthly_counts.iloc[len(monthly_counts)//2:].mean()
                if second_half > first_half * 1.1:
                    overview["volume_trend"] = "上升"
                elif second_half < first_half * 0.9:
                    overview["volume_trend"] = "下降"
                else:
                    overview["volume_trend"] = "平稳"

        self.results["overview"] = overview
        return overview

    def export_to_json(self, output_path: str) -> str:
        """导出为 JSON"""
        def convert_types(obj):
            if isinstance(obj, dict):
                return {k: convert_types(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_types(i) for i in obj]
            elif isinstance(obj, (np.integer, np.int64)):
                return int(obj)
            elif isinstance(obj, (np.floating, np.float64)):
                return float(obj)
            elif pd.isna(obj):
                return None
            return obj
        results = convert_types(self.results)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        return output_path

    def export_to_csv(self, output_dir: str) -> List[str]:
        """导出为多个 CSV 文件"""
        import os
        os.makedirs(output_dir, exist_ok=True)
        files = []
        for key, filename in [("department", "dept_analysis.csv"), ("disease", "disease_analysis.csv"),
                               ("doctor", "doctor_analysis.csv"), ("monthly_trend", "monthly_trend.csv")]:
            if key in self.results and self.results[key]:
                path = os.path.join(output_dir, filename)
                pd.DataFrame(self.results[key]).to_csv(path, index=False, encoding='utf-8-sig')
                files.append(path)
        return files

    def get_analysis_log(self) -> List[Dict]:
        """获取分析日志"""
        return self.analysis_log
