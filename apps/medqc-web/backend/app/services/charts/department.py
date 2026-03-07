"""Department chart generators."""

import pandas as pd
from typing import Dict, Any
from .colors import COLORS


class DepartmentChartsMixin:
    """科室相关图表方法"""

    @staticmethod
    def dept_cost_ranking(dept_df: pd.DataFrame, top_n: int = 15) -> Dict[str, Any]:
        """科室费用排名 - 水平条形图"""
        top_depts = dept_df.head(top_n).sort_values('总费用')
        return {
            'type': 'bar',
            'title': {'text': f'科室住院费用排名（Top {top_n}）'},
            'xAxis': {'type': 'value', 'name': '总费用（万元）', 'axisLabel': {'formatter': '{value}万'}},
            'yAxis': {'type': 'category', 'data': top_depts.index.tolist()},
            'series': [{'name': '总费用', 'type': 'bar',
                        'data': (top_depts['总费用'] / 10000).round(2).tolist(),
                        'itemStyle': {'color': {'type': 'linear', 'x': 0, 'y': 0, 'x2': 1, 'y2': 0,
                                                'colorStops': [{'offset': 0, 'color': '#83bff6'}, {'offset': 1, 'color': '#188df0'}]}},
                        'label': {'show': True, 'position': 'right', 'formatter': '{c}万'}}],
            'grid': {'left': '20%', 'right': '10%'},
            'table_data': {
                'headers': ['科室', '总费用(万元)', '病例数'],
                'rows': [[idx, f"{row['总费用']/10000:.2f}", int(row.get('病例数', 0))] for idx, row in top_depts.iterrows()]
            }
        }

    @staticmethod
    def dept_profit_ranking(dept_df: pd.DataFrame, top_n: int = 15) -> Dict[str, Any]:
        """科室盈亏排名 - 水平条形图"""
        profit_col = '盈亏' if '盈亏' in dept_df.columns else 'profit_loss'
        top_depts = dept_df.sort_values(profit_col, ascending=False).head(top_n)
        
        profit_data = []
        for val in top_depts[profit_col]:
            val_wan = round(val / 10000, 2)
            color = '#22c55e' if val_wan >= 0 else '#ef4444'
            profit_data.append({'value': val_wan, 'itemStyle': {'color': color}})
            
        return {
            'type': 'bar',
            'title': {'text': f'科室盈亏排名（Top {top_n}盈利）'},
            'xAxis': {'type': 'value', 'name': '盈亏（万元）'},
            'yAxis': {'type': 'category', 'data': top_depts.index.tolist()[::-1]},
            'series': [{'name': '盈亏', 'type': 'bar',
                        'data': profit_data[::-1],
                        'label': {'show': True, 'position': 'right', 'formatter': '{c}万'}}],
            'grid': {'left': '20%', 'right': '10%'},
            'tooltip': {'formatter': '{b}: {c}万元'}
        }

    @staticmethod
    def efficiency_bubble(dept_df: pd.DataFrame, top_n: int = 20) -> Dict[str, Any]:
        """效率-费用气泡图"""
        top_depts = dept_df.head(top_n)
        
        # 为了让气泡大小有视觉区分度，找出这批数据中的最大总费用
        max_cost_wan = top_depts['总费用'].max() / 10000 if not top_depts.empty and top_depts['总费用'].max() > 0 else 1
        
        scatter_data = []
        for idx, row in top_depts.iterrows():
            cost_wan = round(row['总费用'] / 10000, 2)
            # 基础大小 15，最大增加 40。使用面积(即平方根)映射更符合视觉直觉
            size = 15 + ((cost_wan / max_cost_wan) ** 0.5) * 40
            
            scatter_data.append({
                'value': [int(row['病例数']), round(row['次均费用'], 2), cost_wan],
                'name': idx,
                'symbolSize': round(size, 1)
            })
            
        return {
            'type': 'scatter',
            'title': {'text': '科室病例数与次均费用关系（气泡大小=总费用）'},
            'xAxis': {'type': 'value', 'name': '病例数', 'splitLine': {'show': True}},
            'yAxis': {'type': 'value', 'name': '次均费用（元）', 'splitLine': {'show': True}},
            'series': [{'type': 'scatter', 'data': scatter_data, 
                        'label': {'show': True, 'formatter': '{b}', 'position': 'top'},
                        'itemStyle': {'color': COLORS['primary'], 'opacity': 0.7}}],
            'tooltip': {'formatter': '{b}<br/>病例数: {c0}<br/>次均费用: {c1}元<br/>总费用: {c2}万'}
        }

    @staticmethod
    def doctor_workload_ranking(doctor_df: pd.DataFrame, top_n: int = 15) -> Dict[str, Any]:
        """医生工作量排名"""
        top_doctors = doctor_df.head(top_n).sort_values('病例数')
        return {
            'type': 'bar',
            'title': {'text': f'医生病例数排名（Top {top_n}）'},
            'xAxis': {'type': 'value', 'name': '病例数'},
            'yAxis': {'type': 'category', 'data': top_doctors.index.tolist()},
            'series': [{'type': 'bar', 'data': top_doctors['病例数'].astype(int).tolist(),
                        'itemStyle': {'color': {'type': 'linear', 'x': 0, 'y': 0, 'x2': 1, 'y2': 0,
                                                'colorStops': [{'offset': 0, 'color': '#83bff6'}, {'offset': 1, 'color': '#188df0'}]}},
                        'label': {'show': True, 'position': 'right'}}],
            'grid': {'left': '15%', 'right': '10%'},
            'table_data': {
                'headers': ['医生姓名', '病例数'],
                'rows': [[idx, int(row['病例数'])] for idx, row in top_doctors.iterrows()]
            }
        }
