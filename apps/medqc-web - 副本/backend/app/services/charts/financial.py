"""Financial, insurance, and Sankey chart generators."""

import copy
from typing import Dict, Any
from .colors import COLORS


class FinancialChartsMixin:
    """财务/保险/Sankey 相关图表方法"""

    @staticmethod
    def cost_structure_pie(cost_data: Dict[str, Any]) -> Dict[str, Any]:
        """费用构成饼图"""
        breakdown = cost_data.get('breakdown', {})
        if not breakdown:
            return {'type': 'pie', 'title': {'text': '费用构成'}, 'series': []}
        label_map = {'drug_cost': '药品费', 'treatment_cost': '治疗费', 'exam_cost': '检查费',
                     'material_cost': '材料费', 'nursing_cost': '护理费', 'bed_cost': '床位费', 'other_cost': '其他'}
        pie_data = [{'name': label_map.get(key, key), 'value': value.get('amount', 0)} for key, value in breakdown.items()]
        return {
            'type': 'pie', 'title': {'text': '费用构成分析', 'left': 'center'},
            'tooltip': {'trigger': 'item', 'formatter': '{b}: {c}元 ({d}%)'},
            'legend': {'orient': 'vertical', 'left': 'left'},
            'series': [{'type': 'pie', 'radius': ['40%', '70%'], 'center': ['60%', '50%'], 'data': pie_data,
                        'label': {'formatter': '{b}: {d}%'}, 'itemStyle': {'borderRadius': 6, 'borderColor': '#fff', 'borderWidth': 2}}]
        }

    @staticmethod
    def drug_ratio_trend(cost_data: Dict[str, Any]) -> Dict[str, Any]:
        """药占比趋势面积图"""
        drug_trend = cost_data.get('drug_trend', [])
        if not drug_trend:
            return {'type': 'line', 'title': {'text': '药占比趋势'}, 'series': []}
        months = [item['month'] for item in drug_trend]
        ratios = [item['drug_ratio'] for item in drug_trend]
        return {
            'type': 'line', 'title': {'text': '药占比月度趋势', 'left': 'center'},
            'tooltip': {'trigger': 'axis', 'formatter': '{b}: {c}%'},
            'xAxis': {'type': 'category', 'data': months},
            'yAxis': {'type': 'value', 'name': '药占比(%)', 'max': 100},
            'series': [{'type': 'line', 'data': ratios, 'smooth': True, 'areaStyle': {'opacity': 0.3},
                        'lineStyle': {'width': 2}, 'itemStyle': {'color': COLORS['primary']}}],
            'grid': {'left': '10%', 'right': '5%', 'bottom': '10%'}
        }

    @staticmethod
    def insurance_type_pie(insurance_data: Dict[str, Any]) -> Dict[str, Any]:
        """险种分布饼图"""
        dist = insurance_data.get('insurance_distribution', [])
        if not dist:
            return {'type': 'pie', 'title': {'text': '险种分布'}, 'series': []}
        pie_data = [{'name': item['type'], 'value': item['count']} for item in dist]
        return {
            'type': 'pie', 'title': {'text': '医保险种分布', 'left': 'center'},
            'tooltip': {'trigger': 'item', 'formatter': '{b}: {c}例 ({d}%)'},
            'legend': {'orient': 'vertical', 'left': 'left'},
            'series': [{'type': 'pie', 'radius': '60%', 'center': ['60%', '50%'], 'data': pie_data,
                        'label': {'formatter': '{b}: {d}%'}}]
        }

    @staticmethod
    def location_distribution_bar(insurance_data: Dict[str, Any]) -> Dict[str, Any]:
        """异地/本地分布柱状图"""
        dist = insurance_data.get('location_distribution', [])
        if not dist:
            return {'type': 'bar', 'title': {'text': '异地分布'}, 'series': []}
        categories = [item['type'] for item in dist]
        values = [item['count'] for item in dist]
        colors = [COLORS['primary'] if c == '本地' else COLORS['steelblue'] for c in categories]
        return {
            'type': 'bar', 'title': {'text': '本地/异地病例分布', 'left': 'center'},
            'tooltip': {'trigger': 'axis'},
            'xAxis': {'type': 'category', 'data': categories},
            'yAxis': {'type': 'value', 'name': '病例数'},
            'series': [{'type': 'bar', 'data': [{'value': v, 'itemStyle': {'color': c}} for v, c in zip(values, colors)],
                        'label': {'show': True, 'position': 'top'}}],
            'grid': {'left': '10%', 'right': '10%', 'bottom': '15%'}
        }

    @staticmethod
    def fund_flow_sankey(fund_flow_data: Dict[str, Any]) -> Dict[str, Any]:
        """全院资金流向 Sankey 图"""
        nodes = copy.deepcopy(fund_flow_data.get('nodes', []))
        links = fund_flow_data.get('links', [])
        if not nodes or not links:
            return {'type': 'sankey', 'title': {'text': '资金流向'}, 'series': []}

        COLOR_L1, COLOR_L2 = '#0047AB', '#F0AD4E'
        COLOR_L3_TOP, COLOR_L3_BOTTOM = '#20B2AA', '#FF6F61'
        doc_nodes = [n for n in nodes if n.get('name', '').startswith('医生-')]
        total_docs = len(doc_nodes)
        current_doc_idx = 0

        for node in nodes:
            name = node.get('name', '')
            if 'itemStyle' not in node:
                node['itemStyle'] = {}
            if name == '全院投入':
                node['itemStyle']['color'] = COLOR_L1
                node['itemStyle']['borderColor'] = '#1F4E79'
            elif name.startswith('科室-') or name in ['药品费', '耗材费', '医疗服务费', '其他费用']:
                node['itemStyle']['color'] = COLOR_L2
                node['itemStyle']['borderColor'] = '#F0AD4E'
            elif name.startswith('医生-'):
                current_doc_idx += 1
                if current_doc_idx <= total_docs / 2:
                    node['itemStyle']['color'] = COLOR_L3_TOP
                    node['itemStyle']['borderColor'] = '#20B2AA'
                else:
                    node['itemStyle']['color'] = COLOR_L3_BOTTOM
                    node['itemStyle']['borderColor'] = '#FF6F61'
            else:
                if 'color' not in node['itemStyle']:
                    node['itemStyle']['color'] = '#999999'

        return {
            'type': 'sankey', 'title': {'text': '资金流向: 全院 → 科室 → 医生', 'left': 'center'},
            'tooltip': {'trigger': 'item', 'formatter': '{b}: {c}元'},
            'series': [{'type': 'sankey', 'layout': 'none', 'emphasis': {'focus': 'adjacency'},
                        'data': nodes, 'links': links,
                        'lineStyle': {'color': 'gradient', 'curveness': 0.5, 'opacity': 0.4},
                        'label': {'position': 'right', 'fontSize': 11, 'color': '#333'},
                        'itemStyle': {'borderWidth': 1, 'borderColor': '#fff'}}]
        }

    @staticmethod
    def cost_structure_sankey(fund_flow_data: Dict[str, Any]) -> Dict[str, Any]:
        """费用结构流向 Sankey 图"""
        nodes = copy.deepcopy(fund_flow_data.get('nodes', []))
        links = fund_flow_data.get('links', [])
        if not nodes or not links:
            return {'type': 'sankey', 'title': {'text': '费用结构流向'}, 'series': []}

        COLOR_L1 = '#0047AB'
        TYPE_COLORS = {'药品费': '#388E3C', '耗材费': '#F57C00', '医疗服务费': '#1976D2', '其他费用': '#9E9E9E'}
        COLOR_L3 = '#F0AD4E'

        for node in nodes:
            name = node.get('name', '')
            if 'itemStyle' not in node:
                node['itemStyle'] = {}
            if name == '全院投入':
                node['itemStyle']['color'] = COLOR_L1
            elif name in TYPE_COLORS:
                node['itemStyle']['color'] = TYPE_COLORS.get(name, '#999')
            elif name.startswith('科室-'):
                node['itemStyle']['color'] = COLOR_L3
            else:
                node['itemStyle']['color'] = '#999'

        return {
            'type': 'sankey', 'title': {'text': '费用流向: 全院 → 费用类型 → 科室', 'left': 'center'},
            'tooltip': {'trigger': 'item', 'formatter': '{b}: {c}元'},
            'series': [{'type': 'sankey', 'layout': 'none', 'emphasis': {'focus': 'adjacency'},
                        'data': nodes, 'links': links,
                        'lineStyle': {'color': 'gradient', 'curveness': 0.5, 'opacity': 0.4},
                        'label': {'position': 'right', 'fontSize': 11, 'color': '#333'},
                        'itemStyle': {'borderWidth': 1, 'borderColor': '#fff'}}]
        }

    @staticmethod
    def rate_type_pie(rate_data: list) -> Dict[str, Any]:
        """倍率类型分布饼图"""
        if not rate_data:
            return {'type': 'pie', 'title': {'text': '倍率类型分布'}, 'series': []}
        pie_data = [{'name': r['倍率类型'], 'value': r.get('病例数', 0)} for r in rate_data]
        return {
            'type': 'pie', 'title': {'text': '倍率类型病例分布', 'left': 'center'},
            'tooltip': {'trigger': 'item', 'formatter': '{b}: {c} ({d}%)'},
            'legend': {'orient': 'horizontal', 'bottom': '5%'},
            'series': [{'type': 'pie', 'radius': ['40%', '70%'], 'data': pie_data,
                        'label': {'formatter': '{b}: {d}%'}, 'emphasis': {'itemStyle': {'shadowBlur': 10}}}]
        }

    @staticmethod
    def rate_type_summary_table(rate_data: list) -> Dict[str, Any]:
        """倍率类型汇总表"""
        return {
            'type': 'table', 'title': {'text': '倍率类型核心指标汇总'},
            'headers': ['倍率类型', '病例数', '病组数', '次均费用', '总费用', '按DIP总费用', '结余'],
            'rows': [[r.get('倍率类型', ''), r.get('病例数', 0), r.get('病组数', 0), f"{r.get('次均费用', 0):,.2f}",
                       f"{r.get('总费用', 0) / 10000:,.2f}万", f"{r.get('按DIP总费用', 0) / 10000:,.2f}万",
                       f"{r.get('结余', 0) / 10000:,.2f}万"] for r in rate_data]
        }

    @staticmethod
    def insurance_type_table(insurance_data: Dict[str, Any]) -> Dict[str, Any]:
        """参保类型 KPI 汇总表"""
        dist = insurance_data.get('insurance_distribution', [])
        if not dist:
            return {'type': 'table', 'title': {'text': '参保类型分布'}, 'rows': []}
        return {
            'type': 'table', 'title': {'text': '参保类型 KPI 汇总'},
            'headers': ['参保类型', '病例数', '占比(%)'],
            'rows': [[item.get('type', ''), item.get('count', 0), f"{item.get('ratio', 0):.1f}%"] for item in dist]
        }
