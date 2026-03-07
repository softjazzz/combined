"""Monthly trend chart generators."""

import pandas as pd
from typing import Dict, Any


class MonthlyChartsMixin:
    """月度趋势相关图表方法"""

    @staticmethod
    def monthly_trend(monthly_df: pd.DataFrame) -> Dict[str, Any]:
        """月度趋势双轴图"""
        months = monthly_df.index.tolist()
        rotate_angle = 45 if len(months) > 6 else 0
        return {
            'type': 'mixed',
            'title': {'text': '月度病例数与总费用趋势', 'textStyle': {'fontSize': 16, 'fontWeight': 'bold', 'color': '#333'}, 'left': 'center', 'top': 10},
            'tooltip': {'trigger': 'axis', 'axisPointer': {'type': 'cross', 'crossStyle': {'color': '#999'}},
                        'backgroundColor': 'rgba(255, 255, 255, 0.95)', 'borderColor': '#ccc', 'borderWidth': 1,
                        'textStyle': {'color': '#333'}, 'formatter': '{b}<br/>{a0}: {c0} 例<br/>{a1}: {c1} 万元'},
            'legend': {'data': ['病例数', '总费用'], 'top': 40, 'itemWidth': 25, 'itemHeight': 14},
            'grid': {'left': '8%', 'right': '8%', 'bottom': '15%', 'top': '20%', 'containLabel': True},
            'xAxis': {'type': 'category', 'data': months, 'axisLine': {'lineStyle': {'color': '#ccc'}},
                      'axisLabel': {'color': '#666', 'fontSize': 12, 'rotate': rotate_angle}, 'axisTick': {'show': False}},
            'yAxis': [
                {'type': 'value', 'name': '病例数', 'position': 'left',
                 'nameTextStyle': {'color': '#4A90E2', 'fontSize': 12}, 'axisLine': {'show': True, 'lineStyle': {'color': '#4A90E2'}},
                 'axisLabel': {'color': '#4A90E2'}, 'splitLine': {'lineStyle': {'type': 'dashed', 'color': '#eee'}}},
                {'type': 'value', 'name': '总费用（万元）', 'position': 'right',
                 'nameTextStyle': {'color': '#FF7F50', 'fontSize': 12}, 'axisLine': {'show': True, 'lineStyle': {'color': '#FF7F50'}},
                 'axisLabel': {'color': '#FF7F50'}, 'splitLine': {'show': False}}
            ],
            'series': [
                {'name': '病例数', 'type': 'bar', 'data': monthly_df['病例数'].astype(int).tolist(), 'yAxisIndex': 0, 'barWidth': '40%',
                 'itemStyle': {'color': {'type': 'linear', 'x': 0, 'y': 0, 'x2': 0, 'y2': 1,
                                         'colorStops': [{'offset': 0, 'color': '#83bff6'}, {'offset': 1, 'color': '#188df0'}]},
                               'borderRadius': [4, 4, 0, 0]},
                 'emphasis': {'itemStyle': {'shadowBlur': 10, 'shadowColor': 'rgba(0,0,0,0.3)'}},
                 'label': {'show': True, 'position': 'top', 'color': '#4A90E2', 'fontSize': 11, 'formatter': '{c}'}},
                {'name': '总费用', 'type': 'line', 'data': (monthly_df['总费用'] / 10000).round(2).tolist(), 'yAxisIndex': 1, 'smooth': True,
                 'symbol': 'circle', 'symbolSize': 10,
                 'lineStyle': {'width': 3, 'color': '#FF7F50', 'shadowBlur': 4, 'shadowColor': 'rgba(255,127,80,0.4)'},
                 'itemStyle': {'color': '#FF7F50', 'borderColor': '#fff', 'borderWidth': 2},
                 'areaStyle': {'color': {'type': 'linear', 'x': 0, 'y': 0, 'x2': 0, 'y2': 1,
                                         'colorStops': [{'offset': 0, 'color': 'rgba(255,127,80,0.3)'}, {'offset': 1, 'color': 'rgba(255,127,80,0.05)'}]}},
                 'label': {'show': True, 'position': 'top', 'color': '#FF7F50', 'fontSize': 11, 'formatter': '{c}万'}}
            ],
            'animationDuration': 1000, 'animationEasing': 'elasticOut'
        }

    @staticmethod
    def monthly_balance_trend(monthly_data: list) -> Dict[str, Any]:
        """月度结余趋势折线图"""
        if not monthly_data:
            return {'type': 'line', 'title': {'text': '月度结余趋势'}, 'series': []}
        months = [m.get('数据月份', m.get('月份', '')) for m in monthly_data]
        balances = [round(m.get('结余', 0) / 10000, 2) for m in monthly_data]
        return {
            'type': 'line', 'title': {'text': '月度结余趋势', 'left': 'center'},
            'tooltip': {'trigger': 'axis', 'formatter': '{b}: {c}万元'},
            'xAxis': {'type': 'category', 'data': months, 'name': '月份'},
            'yAxis': {'type': 'value', 'name': '结余(万元)'},
            'series': [{'type': 'line', 'data': balances, 'smooth': True, 'areaStyle': {'opacity': 0.3},
                        'lineStyle': {'width': 3}, 'itemStyle': {'color': '#6366f1'},
                        'label': {'show': True, 'formatter': '{c}万'}}],
            'grid': {'left': '10%', 'right': '10%', 'bottom': '15%'}
        }

    @staticmethod
    def monthly_case_count(monthly_data: list) -> Dict[str, Any]:
        """月度病例数柱状图"""
        if not monthly_data:
            return {'type': 'bar', 'title': {'text': '月度病例数'}, 'series': []}
        months = [str(d.get('month', '')) for d in monthly_data]
        case_counts = [int(d.get('病例数', 0)) for d in monthly_data]
        return {
            'type': 'bar', 'title': {'text': '月度病例数', 'left': 'center'},
            'tooltip': {'trigger': 'axis'},
            'xAxis': {'type': 'category', 'data': months, 'name': '月份'},
            'yAxis': {'type': 'value', 'name': '病例数'},
            'series': [{'type': 'bar', 'data': case_counts, 'itemStyle': {'color': '#5B8FF9'},
                        'label': {'show': True, 'position': 'top'}}],
            'grid': {'left': '10%', 'right': '10%', 'bottom': '15%'}
        }

    @staticmethod
    def monthly_profit_loss(monthly_data: list) -> Dict[str, Any]:
        """月度盈亏柱状图"""
        if not monthly_data:
            return {'type': 'bar', 'title': {'text': '月度盈亏'}, 'series': []}
        months = [str(d.get('month', '')) for d in monthly_data]
        profit_loss = [round(d.get('结余', 0), 2) for d in monthly_data]
        colors = ['#52C41A' if v >= 0 else '#FF4D4F' for v in profit_loss]
        bar_data = [{'value': v, 'itemStyle': {'color': c}} for v, c in zip(profit_loss, colors)]
        return {
            'type': 'bar', 'title': {'text': '月度盈亏 (元)', 'left': 'center'},
            'tooltip': {'trigger': 'axis', 'formatter': '{b}: {c}元'},
            'xAxis': {'type': 'category', 'data': months, 'name': '月份'},
            'yAxis': {'type': 'value', 'name': '盈亏(元)'},
            'series': [{'type': 'bar', 'data': bar_data, 'label': {'show': True, 'position': 'top', 'formatter': '{c}'}}],
            'grid': {'left': '10%', 'right': '10%', 'bottom': '15%'}
        }

    @staticmethod
    def monthly_cmi(monthly_data: list) -> Dict[str, Any]:
        """月度CMI折线图"""
        if not monthly_data:
            return {'type': 'line', 'title': {'text': '月度CMI'}, 'series': []}
        months = [str(d.get('month', '')) for d in monthly_data]
        cmi_values = [round(d.get('CMI指数', d.get('cmi', 1.0)), 4) for d in monthly_data]
        return {
            'type': 'line', 'title': {'text': '月度CMI (难度)', 'left': 'center'},
            'tooltip': {'trigger': 'axis'},
            'xAxis': {'type': 'category', 'data': months, 'name': '月份'},
            'yAxis': {'type': 'value', 'name': 'CMI指数', 'min': 'dataMin', 'max': 'dataMax'},
            'series': [{'type': 'line', 'data': cmi_values, 'smooth': True,
                        'lineStyle': {'color': '#9254DE', 'width': 2}, 'itemStyle': {'color': '#9254DE'},
                        'areaStyle': {'color': 'rgba(146, 84, 222, 0.1)'}}],
            'grid': {'left': '10%', 'right': '10%', 'bottom': '15%'}
        }

    @staticmethod
    def monthly_avg_cost(monthly_data: list) -> Dict[str, Any]:
        """次均费用趋势折线图"""
        if not monthly_data:
            return {'type': 'line', 'title': {'text': '次均费用趋势'}, 'series': []}
        months = [str(d.get('month', '')) for d in monthly_data]
        avg_costs = [round(d.get('次均费用', 0), 2) for d in monthly_data]
        return {
            'type': 'line', 'title': {'text': '次均费用趋势', 'left': 'center'},
            'tooltip': {'trigger': 'axis', 'formatter': '{b}: {c}元'},
            'xAxis': {'type': 'category', 'data': months, 'name': '月份'},
            'yAxis': {'type': 'value', 'name': '次均费用(元)'},
            'series': [{'type': 'line', 'data': avg_costs, 'smooth': True,
                        'lineStyle': {'color': '#FAAD14', 'width': 2}, 'itemStyle': {'color': '#FAAD14'}}],
            'grid': {'left': '10%', 'right': '10%', 'bottom': '15%'}
        }

    @staticmethod
    def monthly_case_type_trend(monthly_data: list) -> Dict[str, Any]:
        """不同病例类型病例数趋势"""
        if not monthly_data:
            return {'type': 'line', 'title': {'text': '不同病例类型病例数趋势'}, 'series': []}
        palette = ['#5B8FF9', '#5AD8A6', '#FF6B6B', '#FAAD14', '#9254DE', '#13C2C2']

        # New structure: {"months": [...], "series": {...}}
        if isinstance(monthly_data, dict) and monthly_data.get("months") and monthly_data.get("series"):
            months = [str(m) for m in monthly_data.get("months", [])]
            series_map = monthly_data.get("series", {})
            series_data, legend_names = [], []
            for idx, (name, values) in enumerate(series_map.items()):
                series_data.append({'name': name, 'type': 'line', 'data': values, 'smooth': True,
                                    'lineStyle': {'color': palette[idx % len(palette)]}, 'itemStyle': {'color': palette[idx % len(palette)]}})
                legend_names.append(name)
            return {'type': 'line', 'title': {'text': '不同病例类型病例数趋势', 'left': 'center'}, 'tooltip': {'trigger': 'axis'},
                    'legend': {'data': legend_names, 'bottom': '5%'}, 'xAxis': {'type': 'category', 'data': months, 'name': '月份'},
                    'yAxis': {'type': 'value', 'name': '病例数'}, 'series': series_data,
                    'grid': {'left': '10%', 'right': '10%', 'bottom': '20%'}}

        # Legacy structure: list of dict
        months = [str(d.get('month', '')) for d in monthly_data]
        series_config = [{'key': '正常病例', 'color': '#5B8FF9'}, {'key': '低倍率病例', 'color': '#5AD8A6'},
                         {'key': '高倍率病例', 'color': '#FF6B6B'}, {'key': '极高异常病例', 'color': '#FAAD14'}]
        series_data, legend_names = [], []
        for cfg in series_config:
            values = [d.get(cfg['key'], 0) for d in monthly_data]
            if any(v > 0 for v in values):
                series_data.append({'name': cfg['key'], 'type': 'line', 'data': values, 'smooth': True,
                                    'lineStyle': {'color': cfg['color']}, 'itemStyle': {'color': cfg['color']}})
                legend_names.append(cfg['key'])
        return {'type': 'line', 'title': {'text': '不同病例类型病例数趋势', 'left': 'center'}, 'tooltip': {'trigger': 'axis'},
                'legend': {'data': legend_names, 'bottom': '5%'}, 'xAxis': {'type': 'category', 'data': months, 'name': '月份'},
                'yAxis': {'type': 'value', 'name': '病例数'}, 'series': series_data,
                'grid': {'left': '10%', 'right': '10%', 'bottom': '20%'}}

    @staticmethod
    def monthly_disease_type_trend(monthly_data: list) -> Dict[str, Any]:
        """不同病种类型病例数趋势"""
        if not monthly_data:
            return {'type': 'line', 'title': {'text': '不同病种类型病例数趋势'}, 'series': []}
        palette = ['#5B8FF9', '#5AD8A6', '#FF6B6B', '#FAAD14', '#9254DE', '#13C2C2']

        if isinstance(monthly_data, dict) and monthly_data.get("months") and monthly_data.get("series"):
            months = [str(m) for m in monthly_data.get("months", [])]
            series_map = monthly_data.get("series", {})
            series_data, legend_names = [], []
            for idx, (name, values) in enumerate(series_map.items()):
                series_data.append({'name': name, 'type': 'line', 'data': values, 'smooth': True,
                                    'lineStyle': {'color': palette[idx % len(palette)]}, 'itemStyle': {'color': palette[idx % len(palette)]}})
                legend_names.append(name)
            return {'type': 'line', 'title': {'text': '不同病种类型病例数趋势', 'left': 'center'}, 'tooltip': {'trigger': 'axis'},
                    'legend': {'data': legend_names, 'bottom': '5%'}, 'xAxis': {'type': 'category', 'data': months, 'name': '月份'},
                    'yAxis': {'type': 'value', 'name': '病例数'}, 'series': series_data,
                    'grid': {'left': '10%', 'right': '10%', 'bottom': '20%'}}

        months = [str(d.get('month', '')) for d in monthly_data]
        series_config = [{'key': '核心组', 'color': '#5B8FF9'}, {'key': '综合组', 'color': '#5AD8A6'},
                         {'key': '未入组', 'color': '#FF6B6B'}, {'key': '基层病种', 'color': '#FAAD14'}]
        series_data, legend_names = [], []
        for cfg in series_config:
            values = [d.get(cfg['key'], 0) for d in monthly_data]
            if any(v > 0 for v in values):
                series_data.append({'name': cfg['key'], 'type': 'line', 'data': values, 'smooth': True,
                                    'lineStyle': {'color': cfg['color']}, 'itemStyle': {'color': cfg['color']}})
                legend_names.append(cfg['key'])
        return {'type': 'line', 'title': {'text': '不同病种类型病例数趋势', 'left': 'center'}, 'tooltip': {'trigger': 'axis'},
                'legend': {'data': legend_names, 'bottom': '5%'}, 'xAxis': {'type': 'category', 'data': months, 'name': '月份'},
                'yAxis': {'type': 'value', 'name': '病例数'}, 'series': series_data,
                'grid': {'left': '10%', 'right': '10%', 'bottom': '20%'}}

    @staticmethod
    def point_value_trend(point_data: list) -> Dict[str, Any]:
        """月度点值趋势双线图"""
        if not point_data:
            return {'type': 'line', 'title': {'text': '月度点值趋势'}, 'series': []}
        months = [p.get('月份', '') for p in point_data]
        series_data, legend_names = [], []
        for col in ['预结算点值', '职工点值', '居民点值', 'point_value']:
            values = [p.get(col) for p in point_data]
            if any(v is not None for v in values):
                clean_values = [v if v is not None else 0 for v in values]
                series_data.append({'name': col, 'type': 'line', 'data': clean_values, 'smooth': True})
                legend_names.append(col)
        return {
            'type': 'line', 'title': {'text': '月度点值趋势', 'left': 'center'},
            'tooltip': {'trigger': 'axis'}, 'legend': {'data': legend_names, 'bottom': '5%'},
            'xAxis': {'type': 'category', 'data': months, 'name': '月份'},
            'yAxis': {'type': 'value', 'name': '点值(元)'},
            'series': series_data, 'grid': {'left': '10%', 'right': '10%', 'bottom': '20%'}
        }
