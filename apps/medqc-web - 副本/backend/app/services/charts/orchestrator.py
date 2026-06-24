"""Chart generation orchestrator - generates all charts from analysis results."""

import pandas as pd
from typing import Dict, Any
from .colors import COLORS


class OrchestratorMixin:
    """generate_all_charts 编排方法"""

    @classmethod
    def generate_all_charts(cls, analysis_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        根据分析结果生成所有图表配置

        Args:
            analysis_results: enhanced_analysis.py 的输出结果

        Returns:
            图表配置字典
        """
        charts = {}

        # 科室分析
        if 'department' in analysis_results and analysis_results['department']:
            dept_df = pd.DataFrame(analysis_results['department']).set_index('department')
            charts['dept_cost_ranking'] = cls.dept_cost_ranking(dept_df)
            charts['dept_profit_ranking'] = cls.dept_profit_ranking(dept_df)
            charts['efficiency_bubble'] = cls.efficiency_bubble(dept_df)

        # 病种分析
        if 'disease' in analysis_results and analysis_results['disease']:
            disease_df = pd.DataFrame(analysis_results['disease']).set_index('dip_name')
            charts['disease_count_ranking'] = cls.disease_count_ranking(disease_df)
            charts['disease_cost_ranking'] = cls.disease_cost_ranking(disease_df)
            charts['disease_matrix'] = cls.disease_matrix_bubble(disease_df)
            charts['disease_sunburst'] = cls.disease_sunburst(disease_df)

        # 月度趋势
        if 'monthly_trend' in analysis_results and analysis_results['monthly_trend']:
            monthly_df = pd.DataFrame(analysis_results['monthly_trend']).set_index('数据月份')
            charts['monthly_trend'] = cls.monthly_trend(monthly_df)

        # 医生排名
        if 'doctor' in analysis_results and analysis_results['doctor']:
            doctor_df = pd.DataFrame(analysis_results['doctor']).set_index('doctor')
            charts['doctor_workload_ranking'] = cls.doctor_workload_ranking(doctor_df)
            import copy as _copy
            charts['doctor_performance'] = _copy.deepcopy(charts['doctor_workload_ranking'])

        # DIP散点图
        if 'department' in analysis_results and analysis_results['department']:
            if 'disease' in analysis_results and analysis_results['disease']:
                disease_df = pd.DataFrame(analysis_results['disease']).set_index('dip_name')
                charts['drg_scatter'] = cls.payment_vs_cost_scatter(disease_df)

        # 盈亏瀑布图
        if 'overview' in analysis_results:
            ov = analysis_results['overview']
            total_cost = ov.get('total_cost', 0)
            total_payment = ov.get('total_payment', total_cost + ov.get('total_profit_loss', 0))
            total_profit_loss = ov.get('total_profit_loss', 0)

            charts['profit_waterfall'] = {
                'type': 'bar',
                'title': {'text': '收支盈亏分析（瀑布图）'},
                'xAxis': {'type': 'category', 'data': ['DIP支付', '总成本', '盈亏']},
                'yAxis': {'type': 'value', 'name': '金额（万元）'},
                'series': [{'type': 'bar', 'data': [
                    {'value': round(total_payment / 10000, 2), 'itemStyle': {'color': COLORS['success']}},
                    {'value': round(-total_cost / 10000, 2), 'itemStyle': {'color': COLORS['danger']}},
                    {'value': round(total_profit_loss / 10000, 2),
                     'itemStyle': {'color': COLORS['primary'] if total_profit_loss > 0 else COLORS['danger']}}
                ], 'stack': 'total', 'label': {'show': True, 'position': 'top', 'formatter': '{c}万'}}],
                'tooltip': {'formatter': '{b}: {c}万元'}
            }

        # 总体概览 KPI
        if 'overview' in analysis_results:
            ov = analysis_results['overview']
            charts['summary_kpi'] = {
                'type': 'text',
                'data': {
                    'case_count': ov.get('total_cases', 0),
                    'total_cost': ov.get('total_cost', 0),
                    'profit_loss': ov.get('total_profit_loss', 0),
                    'cmi': ov.get('cmi', 0),
                    'avg_los': ov.get('avg_los', 0),
                    'drug_cost_ratio': ov.get('drug_cost_ratio', 0),
                    'cost_recovery_rate': ov.get('cost_recovery_rate', 0),
                    'profit_case_rate': ov.get('profit_case_rate', 0),
                }
            }

        # 费用构成
        if 'cost_structure' in analysis_results and analysis_results['cost_structure']:
            cost_data = analysis_results['cost_structure']
            charts['cost_structure_pie'] = cls.cost_structure_pie(cost_data)
            charts['drug_ratio_trend'] = cls.drug_ratio_trend(cost_data)

        # 医保类型
        if 'insurance_analysis' in analysis_results and analysis_results['insurance_analysis']:
            insurance_data = analysis_results['insurance_analysis']
            charts['insurance_type_pie'] = cls.insurance_type_pie(insurance_data)
            charts['location_distribution'] = cls.location_distribution_bar(insurance_data)

        # DIP 倍率类型
        if 'rate_type' in analysis_results and analysis_results['rate_type']:
            charts['rate_type_pie'] = cls.rate_type_pie(analysis_results['rate_type'])
            charts['rate_type_summary_table'] = cls.rate_type_summary_table(analysis_results['rate_type'])

        # DIP 病种类型对比
        if 'disease_type' in analysis_results and analysis_results['disease_type']:
            charts['disease_type_comparison'] = cls.disease_type_comparison(analysis_results['disease_type'])

        # 结余排行
        if 'balance_top10' in analysis_results and 'balance_bottom10' in analysis_results:
            charts['balance_ranking_table'] = cls.balance_ranking_table(
                analysis_results['balance_top10'], analysis_results['balance_bottom10'])

        # 月度结余趋势
        if 'monthly_trend' in analysis_results and analysis_results['monthly_trend']:
            charts['monthly_balance_trend'] = cls.monthly_balance_trend(analysis_results['monthly_trend'])

        # 月度点值趋势
        if 'point_value_trend' in analysis_results and analysis_results['point_value_trend']:
            charts['point_value_trend'] = cls.point_value_trend(analysis_results['point_value_trend'])

        # 参保类型汇总表
        if 'insurance_analysis' in analysis_results and analysis_results['insurance_analysis']:
            charts['insurance_type_table'] = cls.insurance_type_table(analysis_results['insurance_analysis'])

        # 全院资金流向 Sankey
        if 'fund_flow' in analysis_results and analysis_results['fund_flow']:
            charts['fund_flow_sankey'] = cls.fund_flow_sankey(analysis_results['fund_flow'])

        # 费用结构流向 Sankey
        if 'fund_flow_structure' in analysis_results and analysis_results['fund_flow_structure']:
            charts['cost_structure_sankey'] = cls.cost_structure_sankey(analysis_results['fund_flow_structure'])

        # 月度详细趋势图表
        if 'monthly_trend' in analysis_results and analysis_results['monthly_trend']:
            monthly_data = analysis_results['monthly_trend']
            charts['monthly_case_count'] = cls.monthly_case_count(monthly_data)
            charts['monthly_profit_loss'] = cls.monthly_profit_loss(monthly_data)
            charts['monthly_cmi'] = cls.monthly_cmi(monthly_data)
            charts['monthly_avg_cost'] = cls.monthly_avg_cost(monthly_data)

        if 'rate_type_trend' in analysis_results and analysis_results['rate_type_trend']:
            charts['monthly_case_type_trend'] = cls.monthly_case_type_trend(analysis_results['rate_type_trend'])

        if 'disease_type_trend' in analysis_results and analysis_results['disease_type_trend']:
            charts['monthly_disease_type_trend'] = cls.monthly_disease_type_trend(analysis_results['disease_type_trend'])

        # ========== 科室运营深度分析 (Top N 科室) ==========
        deep_dives = []
        if 'dept_deep_dive_list' in analysis_results and analysis_results['dept_deep_dive_list']:
            deep_dives = analysis_results['dept_deep_dive_list']
        elif 'top_dept_deep_dive' in analysis_results and analysis_results['top_dept_deep_dive']:
            deep_dives = [analysis_results['top_dept_deep_dive']]

        for idx, dd in enumerate(deep_dives):
            rank = idx + 1
            dept_name = dd.get('department', '未知科室')

            def _tag(chart, _name=dept_name, _rank=rank):
                chart['department'] = _name
                chart['rank'] = _rank
                return chart

            # Pre-build disease DataFrame once if available
            _dm_df = None
            if 'disease_matrix' in dd and dd['disease_matrix']:
                _dm_df = pd.DataFrame(dd['disease_matrix']).set_index('dip_name')

            # 1. 科内医生绩效
            if 'doctor_performance' in dd and dd['doctor_performance']:
                doc_perf_df = pd.DataFrame(dd['doctor_performance']).set_index('doctor')
                chart = cls.doctor_workload_ranking(doc_perf_df)
                chart['title']['text'] = f'{dept_name} - 医生绩效TOP榜'
                _tag(chart)
                if rank == 1: charts['dept_doctor_performance'] = chart
                charts[f'dept_doctor_performance_{rank}'] = chart

            # 2. 科内病种矩阵
            if _dm_df is not None:
                chart = cls.disease_matrix_bubble(_dm_df)
                chart['title']['text'] = f'{dept_name} - 病种绩效矩阵'
                _tag(chart)
                if rank == 1: charts['dept_disease_matrix'] = chart
                charts[f'dept_disease_matrix_{rank}'] = chart

            # 3. 科内成本结构
            if 'cost_structure' in dd and dd['cost_structure']:
                chart = cls.cost_structure_pie({'breakdown': dd['cost_structure']})
                chart['title']['text'] = f'{dept_name} - 成本结构分布'
                _tag(chart)
                if rank == 1: charts['dept_cost_structure'] = chart
                charts[f'dept_cost_structure_{rank}'] = chart

            # 4. 科内DRG分值散点图
            if _dm_df is not None:
                chart = cls.payment_vs_cost_scatter(_dm_df, top_n=50)
                chart['title']['text'] = f'{dept_name} - 支付标准 vs 费用'
                _tag(chart)
                if rank == 1: charts['dept_drg_scatter'] = chart
                charts[f'dept_drg_scatter_{rank}'] = chart

            # 5. 科室核心指标卡片
            if 'core_kpi' in dd and dd['core_kpi']:
                kpi = dd['core_kpi']
                chart = {
                    'type': 'kpi_card',
                    'title': {'text': f'{dept_name} - 核心指标概览'},
                    'priority': 0,
                    'department': dept_name,
                    'rank': rank,
                    'data': {
                        'case_count': kpi.get('case_count', 0), 'total_cost': kpi.get('total_cost', 0),
                        'total_payment': kpi.get('total_payment', 0), 'profit_loss': kpi.get('profit_loss', 0),
                        'payment_rate': kpi.get('payment_rate', 0), 'cmi': kpi.get('cmi', 0),
                        'avg_los': kpi.get('avg_los', 0), 'disease_count': kpi.get('disease_count', 0),
                        'profit_disease_count': kpi.get('profit_disease_count', 0),
                        'loss_disease_count': kpi.get('loss_disease_count', 0),
                        'employee_profit': kpi.get('employee_profit'), 'resident_profit': kpi.get('resident_profit')
                    }
                }
                if rank == 1: charts['dept_core_kpi'] = chart
                charts[f'dept_core_kpi_{rank}'] = chart

            # 6. 主要病种分析
            if _dm_df is not None:
                dm = dd['disease_matrix']
                sorted_diseases = sorted(dm, key=lambda x: x.get('病例数', 0), reverse=True)[:15]
                disease_names = [d.get('dip_name', '')[:20] for d in sorted_diseases]
                case_counts = [int(d.get('病例数', 0)) for d in sorted_diseases]
                chart = {
                    'type': 'bar',
                    'title': {'text': f'{dept_name} - 主要病种分析', 'left': 'center'},
                    'department': dept_name, 'rank': rank,
                    'tooltip': {'trigger': 'axis', 'axisPointer': {'type': 'shadow'}, 'formatter': '{b}: {c} 例'},
                    'grid': {'left': 180, 'right': 40, 'top': 50, 'bottom': 30},
                    'xAxis': {'type': 'value', 'name': '病例数量', 'nameLocation': 'center', 'nameGap': 25},
                    'yAxis': {'type': 'category', 'data': disease_names[::-1],
                              'axisLabel': {'width': 160, 'overflow': 'truncate', 'ellipsis': '...'}},
                    'series': [{'name': '病例数', 'type': 'bar', 'data': case_counts[::-1],
                                'itemStyle': {'color': {'type': 'linear', 'x': 0, 'y': 0, 'x2': 1, 'y2': 0,
                                                        'colorStops': [{'offset': 0, 'color': '#3b82f6'}, {'offset': 1, 'color': '#60a5fa'}]},
                                              'borderRadius': [0, 4, 4, 0]},
                                'label': {'show': True, 'position': 'right', 'formatter': '{c}'}}]
                }
                if rank == 1: charts['dept_main_diseases'] = chart
                charts[f'dept_main_diseases_{rank}'] = chart

            # 7. 盈亏病种排名
            if 'profit_loss_diseases' in dd and dd['profit_loss_diseases']:
                pld = dd['profit_loss_diseases']
                profit_data = pld.get('top_profit', [])[:10]
                loss_data = pld.get('top_loss', [])[:10]
                all_diseases = [d['dip_name'][:15] for d in profit_data] + [d['dip_name'][:15] for d in loss_data]
                profit_values = [d.get('profit_loss', 0) for d in profit_data] + [0] * len(loss_data)
                loss_values = [0] * len(profit_data) + [d.get('profit_loss', 0) for d in loss_data]
                chart = {
                    'type': 'bar', 'title': {'text': f'{dept_name} - 盈亏病种排名', 'left': 'center'},
                    'department': dept_name, 'rank': rank,
                    'tooltip': {'trigger': 'axis'}, 'legend': {'data': ['盈利', '亏损'], 'top': 30},
                    'grid': {'left': 150, 'right': 50, 'containLabel': True},
                    'xAxis': {'type': 'value'}, 'yAxis': {'type': 'category', 'data': all_diseases, 'inverse': True},
                    'series': [
                        {'name': '盈利', 'type': 'bar', 'data': profit_values, 'itemStyle': {'color': '#22c55e'}},
                        {'name': '亏损', 'type': 'bar', 'data': loss_values, 'itemStyle': {'color': '#ef4444'}}
                    ]
                }
                if rank == 1: charts['dept_profit_loss_diseases'] = chart
                charts[f'dept_profit_loss_diseases_{rank}'] = chart

            # 8. 亏损病种趋势
            if 'loss_trend' in dd and dd['loss_trend']:
                lt = dd['loss_trend']
                all_months = set()
                for item in lt:
                    for t in item.get('trend', []):
                        all_months.add(t['month'])
                months = sorted(list(all_months))
                series = []
                for item in lt:
                    disease_name = item.get('disease', '未知')[:10]
                    trend = {t['month']: t['profit_loss'] for t in item.get('trend', [])}
                    data = [trend.get(m, 0) for m in months]
                    series.append({'name': disease_name, 'type': 'line', 'data': data, 'smooth': True})
                chart = {
                    'type': 'line', 'title': {'text': f'{dept_name} - 主要亏损病种趋势', 'left': 'center'},
                    'department': dept_name, 'rank': rank,
                    'tooltip': {'trigger': 'axis'}, 'legend': {'data': [s['name'] for s in series], 'top': 30},
                    'xAxis': {'type': 'category', 'data': months}, 'yAxis': {'type': 'value', 'name': '盈亏金额'},
                    'series': series
                }
                if rank == 1: charts['dept_loss_trend'] = chart
                charts[f'dept_loss_trend_{rank}'] = chart

            # 9. 同病种医生对比
            if 'doctor_disease_comparison' in dd and dd['doctor_disease_comparison']:
                ddc = dd['doctor_disease_comparison']
                disease_name = ddc.get('disease_name', '未知病种')
                data = ddc.get('data', [])
                doctors = [d.get('doctor', '')[:6] for d in data]
                costs = [d.get('次均费用', 0) for d in data]
                profits = [d.get('盈亏', 0) for d in data]
                profit_points = [{'value': v, 'itemStyle': {'color': '#22c55e' if v >= 0 else '#ef4444'}} for v in profits]
                chart = {
                    'type': 'bar', 'title': {'text': f'{dept_name} - {disease_name[:10]} 医生对比', 'left': 'center'},
                    'department': dept_name, 'rank': rank,
                    'tooltip': {'trigger': 'axis'}, 'legend': {'data': ['次均费用', '盈亏'], 'top': 30},
                    'xAxis': {'type': 'category', 'data': doctors},
                    'yAxis': [{'type': 'value', 'name': '费用'}, {'type': 'value', 'name': '盈亏'}],
                    'series': [
                        {'name': '次均费用', 'type': 'bar', 'data': costs, 'itemStyle': {'color': '#3b82f6'}},
                        {'name': '盈亏', 'type': 'bar', 'yAxisIndex': 1, 'data': profit_points}
                    ]
                }
                if rank == 1: charts['dept_doctor_disease_comparison'] = chart
                charts[f'dept_doctor_disease_comparison_{rank}'] = chart

            # 10. 盈利性能气泡矩阵
            if 'profitability_matrix' in dd and dd['profitability_matrix']:
                pm = dd['profitability_matrix']
                bubble_data = []
                max_cases = 1
                for item in pm[:30]:
                    profitability = round(item.get('profitability', 0), 2)
                    cases = item.get('case_count', 1)
                    if cases > max_cases:
                        max_cases = cases
                    bubble_data.append({
                        'value': [
                            round(item.get('cmi', 0), 2), profitability,
                            cases
                        ],
                        'name': item.get('dip_name', '')[:15],
                        'itemStyle': {'color': '#22c55e' if profitability >= 0 else '#ef4444'}
                    })
                chart = {
                    'type': 'scatter', 'title': {'text': f'{dept_name} - 病种盈利性能矩阵', 'left': 'center'},
                    'department': dept_name, 'rank': rank,
                    'tooltip': {'trigger': 'item',
                                'formatter': '{b}<br>CMI: {c0}<br>盈利性能: {c1}%<br>病例数: {c2}'},
                    'xAxis': {'type': 'value', 'name': 'CMI', 'scale': True},
                    'yAxis': {'type': 'value', 'name': '盈利性能(%)', 'scale': True},
                    'visualMap': {'show': False, 'min': 0, 'max': max_cases, 'dimension': 2, 'inRange': {'symbolSize': [10, 50]}},
                    'series': [{'type': 'scatter', 'data': bubble_data}]
                }
                if rank == 1: charts['dept_profitability_bubble'] = chart
                charts[f'dept_profitability_bubble_{rank}'] = chart

        # 注入表格明细数据
        from .table_data_injector import inject_table_data
        inject_table_data(charts, analysis_results)

        return charts
