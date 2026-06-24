"""Disease chart generators."""

import pandas as pd
from typing import Dict, Any, List
from .colors import COLORS


class DiseaseChartsMixin:
    """病种相关图表方法"""

    @staticmethod
    def disease_count_ranking(disease_df: pd.DataFrame, top_n: int = 20) -> Dict[str, Any]:
        """病种病例数排名"""
        top_diseases = disease_df.head(top_n).sort_values('病例数')
        return {
            'type': 'bar',
            'title': {'text': f'病种病例数排名（Top {top_n}）'},
            'xAxis': {'type': 'value', 'name': '病例数'},
            'yAxis': {'type': 'category', 'data': top_diseases.index.tolist(),
                      'axisLabel': {'interval': 0, 'fontSize': 10}},
            'series': [{'type': 'bar', 'data': top_diseases['病例数'].astype(int).tolist(),
                        'itemStyle': {'color': COLORS['coral']},
                        'label': {'show': True, 'position': 'right'}}],
            'grid': {'left': '30%', 'right': '10%'},
            'table_data': {
                'headers': ['病种名称', '病例数', '次均费用(元)'],
                'rows': [[idx, int(row['病例数']), f"{row.get('次均费用', 0):.0f}"] for idx, row in top_diseases.iterrows()]
            }
        }

    @staticmethod
    def disease_cost_ranking(disease_df: pd.DataFrame, top_n: int = 20) -> Dict[str, Any]:
        """病种费用排名"""
        top_diseases = disease_df.sort_values('总费用', ascending=False).head(top_n).sort_values('总费用')
        return {
            'type': 'bar',
            'title': {'text': f'病种总费用排名（Top {top_n}）'},
            'xAxis': {'type': 'value', 'name': '总费用（万元）'},
            'yAxis': {'type': 'category', 'data': top_diseases.index.tolist(),
                      'axisLabel': {'interval': 0, 'fontSize': 10}},
            'series': [{'type': 'bar', 'data': (top_diseases['总费用'] / 10000).round(2).tolist(),
                        'itemStyle': {'color': COLORS['mediumseagreen']},
                        'label': {'show': True, 'position': 'right', 'formatter': '{c}万'}}],
            'grid': {'left': '30%', 'right': '10%'},
            'table_data': {
                'headers': ['病种名称', '总费用(万元)', '次均费用(元)'],
                'rows': [[idx, f"{row['总费用']/10000:.2f}", f"{row.get('次均费用', 0):.0f}"] for idx, row in top_diseases.iterrows()]
            }
        }

    @staticmethod
    def disease_matrix_bubble(disease_df: pd.DataFrame, top_n: int = 50) -> Dict[str, Any]:
        """病种四象限分析 (气泡图)"""
        if '次均费用' not in disease_df.columns:
            if '总费用' in disease_df.columns and '病例数' in disease_df.columns:
                disease_df = disease_df.copy()
                disease_df['次均费用'] = disease_df['总费用'] / disease_df['病例数'].replace(0, 1)
            else:
                return {'type': 'scatter', 'title': {'text': '病种绩效四象限分析'}, 'series': [], 'error': '缺少费用数据'}

        top_df = disease_df.sort_values('病例数', ascending=False).head(top_n)
        
        max_cases = top_df['病例数'].max() if not top_df.empty and top_df['病例数'].max() > 0 else 1
        
        data = []
        for idx, row in top_df.iterrows():
            weight = row.get('dip_weight', 1.0)
            profit = row.get('profit_loss', 0)
            cases = int(row['病例数'])
            
            # 基础大小 15，最大增加 40，按病例数比例计算
            size = 15 + ((cases / max_cases) ** 0.5) * 40
            
            data.append({
                'value': [round(float(weight), 2), round(float(row['次均费用']), 2),
                          cases, round(float(profit), 2), idx],
                'name': idx,
                'symbolSize': round(size, 1),
                'itemStyle': {'color': COLORS['success'] if profit > 0 else COLORS['danger'], 'opacity': 0.7}
            })

        return {
            'type': 'scatter',
            'title': {'text': '病种绩效四象限分析', 'left': 'center'},
            'grid': {'left': '10%', 'right': '15%', 'top': '15%', 'bottom': '10%'},
            'xAxis': {'type': 'value', 'name': 'DRG/DIP权重(RW)', 'splitLine': {'show': False}},
            'yAxis': {'type': 'value', 'name': '次均费用(元)', 'splitLine': {'show': True, 'lineStyle': {'type': 'dashed'}}},
            'series': [{'type': 'scatter',
                        'data': data,
                        'label': {'show': True, 'formatter': '{b}', 'position': 'top', 'fontSize': 10},
                        'markLine': {'lineStyle': {'type': 'dashed', 'color': '#999'},
                                     'data': [{'type': 'average', 'name': '平均费用', 'valueIndex': 1},
                                              {'type': 'average', 'name': '平均权重', 'valueIndex': 0}]}}],
            'tooltip': {'formatter': '<b>{b}</b><br/>权重: {c0}<br/>次均费用: {c1}元<br/>病例数: {c2}<br/>盈亏: {c3}元'},
            'table_data': {
                'headers': ['病种名称', '权重(RW)', '次均费用', '病例数', '盈亏金额'],
                'rows': [[idx, f"{float(row.get('dip_weight', 1.0)):.2f}", f"{float(row['次均费用']):.0f}",
                           int(row['病例数']), f"{float(row.get('profit_loss', 0)):.2f}"]
                          for idx, row in top_df.iterrows()]
            }
        }

    @staticmethod
    def disease_sunburst(disease_df: pd.DataFrame) -> Dict[str, Any]:
        """病种成本结构旭日图"""
        if '次均费用' not in disease_df.columns:
            if '总费用' in disease_df.columns and '病例数' in disease_df.columns:
                disease_df = disease_df.copy()
                disease_df['次均费用'] = disease_df['总费用'] / disease_df['病例数'].replace(0, 1)
            else:
                return {'type': 'sunburst', 'title': {'text': '病种成本分布旭日图'}, 'series': {'type': 'sunburst', 'data': []}}

        try:
            cost_labels = ['低成本组', '中成本组', '高成本组', '超高成本组']
            disease_df['cost_level'] = pd.qcut(disease_df['次均费用'], q=4, labels=cost_labels, duplicates='drop')
        except Exception:
            disease_df['cost_level'] = '全部病种'

        sunburst_data = []
        if 'cost_level' in disease_df.columns:
            grouped = disease_df.groupby('cost_level')
            for level, group in grouped:
                children = []
                top_in_group = group.sort_values('总费用', ascending=False).head(5)
                for idx, row in top_in_group.iterrows():
                    children.append({'name': str(idx), 'value': round(row['总费用'] / 10000, 2), 'label': {'rotate': 'tangential'}})
                if children:
                    sunburst_data.append({'name': str(level), 'children': children, 'label': {'rotate': 'radial'}})

        return {
            'type': 'sunburst',
            'title': {'text': '病种成本分布旭日图', 'left': 'center'},
            'tooltip': {'formatter': '{b}: {c}万元'},
            'series': {'type': 'sunburst', 'data': sunburst_data, 'radius': [0, '90%'],
                       'label': {'rotate': 'radial'}, 'itemStyle': {'borderRadius': 4, 'borderWidth': 2}}
        }

    @staticmethod
    def payment_vs_cost_scatter(disease_df: pd.DataFrame, top_n: int = 100) -> Dict[str, Any]:
        """DIP分值与实际费用散点图"""
        top_df = disease_df.sort_values('病例数', ascending=False).head(top_n)
        max_cases = top_df['病例数'].max() if not top_df.empty and top_df['病例数'].max() > 0 else 1
        
        data = []
        max_val = 0
        for idx, row in top_df.iterrows():
            payment = float(row.get('次均支付', row.get('dip_payment', 0) / row.get('病例数', 1)))
            cost = float(row.get('次均费用', 0))
            cases = int(row.get('病例数', 0))
            profit = payment - cost
            if payment > max_val: max_val = payment
            if cost > max_val: max_val = cost
            
            # 这个图散点多（100个），基础大小设小点（8-25）
            size = 8 + ((cases / max_cases) ** 0.5) * 17
            
            data.append({
                'value': [round(payment, 2), round(cost, 2), cases, round(profit, 2), idx],
                'name': idx,
                'symbolSize': round(size, 1),
                'itemStyle': {'color': COLORS['success'] if profit > 0 else COLORS['danger'], 'opacity': 0.6}
            })

        return {
            'type': 'scatter',
            'title': {'text': 'DIP分值(支付标准) vs 实际费用分析', 'left': 'center'},
            'grid': {'left': '10%', 'right': '15%', 'top': '15%', 'bottom': '10%'},
            'xAxis': {'type': 'value', 'name': '次均支付标准(元)', 'splitLine': {'show': False}, 'max': int(max_val * 1.1)},
            'yAxis': {'type': 'value', 'name': '次均住院费用(元)', 'splitLine': {'show': True}, 'max': int(max_val * 1.1)},
            'series': [{'type': 'scatter', 'data': data,
                        'label': {'show': True, 'formatter': '{b}', 'position': 'right', 'fontSize': 9, 'minMargin': 5},
                        'markLine': {'silent': True, 'animation': False,
                                     'lineStyle': {'type': 'dashed', 'color': '#999', 'width': 1},
                                     'data': [[{'coord': [0, 0], 'symbol': 'none'},
                                               {'coord': [max_val * 1.1, max_val * 1.1], 'symbol': 'none',
                                                'label': {'formatter': '盈亏平衡线', 'position': 'end'}}]]}}],
            'tooltip': {'formatter': '<b>{b}</b><br/>次均支付: {c0}元<br/>次均费用: {c1}元<br/>单例盈亏: {c3}元<br/>病例数: {c2}'}
        }

    @staticmethod
    def disease_type_comparison(disease_type_data: list) -> Dict[str, Any]:
        """核心/综合病种对比柱状图"""
        if not disease_type_data:
            return {'type': 'bar', 'title': {'text': '病种类型对比'}, 'series': []}
        categories = [d['病种类型'] for d in disease_type_data]
        case_counts = [d.get('病例数', 0) for d in disease_type_data]
        total_costs = [round(d.get('总费用', 0) / 10000, 2) for d in disease_type_data]
        balances = [round(d.get('结余', 0) / 10000, 2) for d in disease_type_data]
        return {
            'type': 'bar',
            'title': {'text': '核心病种 vs 综合病种对比', 'left': 'center'},
            'tooltip': {'trigger': 'axis'},
            'legend': {'data': ['病例数', '总费用(万)', '结余(万)'], 'bottom': '5%'},
            'xAxis': {'type': 'category', 'data': categories},
            'yAxis': [{'type': 'value', 'name': '病例数', 'position': 'left'},
                      {'type': 'value', 'name': '金额(万)', 'position': 'right'}],
            'series': [
                {'name': '病例数', 'type': 'bar', 'data': case_counts, 'yAxisIndex': 0},
                {'name': '总费用(万)', 'type': 'bar', 'data': total_costs, 'yAxisIndex': 1},
                {'name': '结余(万)', 'type': 'bar', 'data': balances, 'yAxisIndex': 1}
            ]
        }

    @staticmethod
    def balance_ranking_table(top10: list, bottom10: list) -> Dict[str, Any]:
        """结余排行表（Top 10 盈利 + Bottom 10 亏损）"""
        return {
            'type': 'dual_table',
            'title': {'text': '病种结余排行榜'},
            'tables': [
                {'subtitle': '盈利 Top 10', 'headers': ['病种', '病例数', '总费用(万)', '结余(万)'],
                 'rows': [[r.get('病种', ''), r.get('病例数', 0), f"{r.get('总费用', 0) / 10000:,.2f}",
                            f"{r.get('结余', 0) / 10000:,.2f}"] for r in top10]},
                {'subtitle': '亏损 Top 10', 'headers': ['病种', '病例数', '总费用(万)', '结余(万)'],
                 'rows': [[r.get('病种', ''), r.get('病例数', 0), f"{r.get('总费用', 0) / 10000:,.2f}",
                            f"{r.get('结余', 0) / 10000:,.2f}"] for r in bottom10]}
            ]
        }
