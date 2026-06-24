"""
Table Data Injector - 为每个图表注入对应的明细数据表格 (tableData)

在 orchestrator.generate_all_charts() 返回前调用，
自动根据 analysis_results 为每个 chart 字典附加 tableData 字段。
"""

from typing import Dict, Any, List, Optional


def inject_table_data(charts: Dict[str, Any], analysis_results: Dict[str, Any]) -> Dict[str, Any]:
    """
    为图表字典批量注入 tableData。

    Args:
        charts: orchestrator 生成的图表配置字典
        analysis_results: enhanced_analysis 的原始分析结果

    Returns:
        注入 tableData 后的 charts 字典（原地修改）
    """

    # ── 科室分析 ──
    if 'department' in analysis_results and analysis_results['department']:
        dept_table = _build_department_table(analysis_results['department'])
        for key in ('dept_cost_ranking', 'dept_profit_ranking', 'efficiency_bubble'):
            if key in charts:
                charts[key]['tableData'] = dept_table

    # ── 病种分析 ──
    if 'disease' in analysis_results and analysis_results['disease']:
        disease_table = _build_disease_table(analysis_results['disease'])
        for key in ('disease_count_ranking', 'disease_cost_ranking', 'disease_matrix',
                     'drg_scatter', 'disease_sunburst'):
            if key in charts:
                charts[key]['tableData'] = disease_table

    # ── 月度趋势 ──
    if 'monthly_trend' in analysis_results and analysis_results['monthly_trend']:
        monthly_table = _build_monthly_table(analysis_results['monthly_trend'])
        for key in ('monthly_trend', 'monthly_case_count', 'monthly_profit_loss',
                     'monthly_cmi', 'monthly_avg_cost', 'monthly_balance_trend'):
            if key in charts:
                charts[key]['tableData'] = monthly_table

    # ── 医生分析 ──
    if 'doctor' in analysis_results and analysis_results['doctor']:
        doctor_table = _build_doctor_table(analysis_results['doctor'])
        for key in ('doctor_workload_ranking', 'doctor_performance',
                     'doctor_profit_ranking', 'doctor_quadrant'):
            if key in charts:
                charts[key]['tableData'] = doctor_table

    # ── 资金流向 Sankey ──
    if 'fund_flow' in analysis_results and analysis_results['fund_flow']:
        fund_table = _build_fund_flow_table(analysis_results['fund_flow'])
        if 'fund_flow_sankey' in charts:
            charts['fund_flow_sankey']['tableData'] = fund_table

    # ── 费用结构流向 Sankey ──
    if 'fund_flow_structure' in analysis_results and analysis_results['fund_flow_structure']:
        cost_flow_table = _build_cost_flow_table(analysis_results['fund_flow_structure'])
        if 'cost_structure_sankey' in charts:
            charts['cost_structure_sankey']['tableData'] = cost_flow_table

    # ── 盈亏瀑布图 ──
    if 'overview' in analysis_results and 'profit_waterfall' in charts:
        charts['profit_waterfall']['tableData'] = _build_waterfall_table(analysis_results['overview'])

    # ── 倍率类型 ──
    if 'rate_type' in analysis_results and analysis_results['rate_type']:
        rate_table = _build_rate_type_table(analysis_results['rate_type'])
        for key in ('rate_type_pie', 'rate_type_summary_table'):
            if key in charts:
                charts[key]['tableData'] = rate_table

    # ── 参保类型 ──
    if 'insurance_analysis' in analysis_results and analysis_results['insurance_analysis']:
        ins_table = _build_insurance_table(analysis_results['insurance_analysis'])
        for key in ('insurance_type_pie', 'insurance_type_table', 'location_distribution'):
            if key in charts:
                charts[key]['tableData'] = ins_table

    # ── 结余排行 ──
    if 'balance_top10' in analysis_results and 'balance_bottom10' in analysis_results:
        balance_table = _build_balance_table(
            analysis_results['balance_top10'], analysis_results['balance_bottom10']
        )
        if 'balance_ranking_table' in charts:
            charts['balance_ranking_table']['tableData'] = balance_table

    return charts


# ═══════════════════════════════════════════════════════════════
# 各维度的表格构建函数
# ═══════════════════════════════════════════════════════════════

def _safe_round(val, n=2):
    """安全的四舍五入"""
    try:
        return round(float(val), n) if val is not None else None
    except (TypeError, ValueError):
        return val


def _build_department_table(dept_data: List[Dict]) -> Dict:
    columns = [
        {'key': 'department', 'label': '科室', 'sortable': True, 'width': 140},
        {'key': 'case_count', 'label': '病例数', 'sortable': True, 'width': 100},
        {'key': 'total_cost', 'label': '总费用(万元)', 'sortable': True, 'width': 130},
        {'key': 'avg_cost', 'label': '次均费用(元)', 'sortable': True, 'width': 130},
        {'key': 'profit_loss', 'label': '盈亏(万元)', 'sortable': True, 'width': 120},
        {'key': 'avg_los', 'label': '平均住院日', 'sortable': True, 'width': 110},
        {'key': 'cmi', 'label': 'CMI', 'sortable': True, 'width': 80},
    ]
    rows = []
    for d in dept_data:
        case_count = d.get('case_count') or d.get('病例数', 0)
        total_cost = d.get('total_cost') or d.get('总费用', 0)
        rows.append({
            'department': d.get('department') or d.get('科室', ''),
            'case_count': int(case_count) if case_count else 0,
            'total_cost': _safe_round((total_cost or 0) / 10000),
            'avg_cost': _safe_round(total_cost / case_count if case_count else 0),
            'profit_loss': _safe_round((d.get('profit_loss') or d.get('盈亏', 0) or 0) / 10000),
            'avg_los': _safe_round(d.get('avg_los') or d.get('平均住院日', 0), 1),
            'cmi': _safe_round(d.get('cmi') or d.get('CMI', 0), 3),
        })
    rows.sort(key=lambda x: x.get('total_cost', 0), reverse=True)
    return {'columns': columns, 'rows': rows}


def _build_disease_table(disease_data: List[Dict]) -> Dict:
    columns = [
        {'key': 'disease', 'label': '病种', 'sortable': True, 'width': 200},
        {'key': 'case_count', 'label': '病例数', 'sortable': True, 'width': 100},
        {'key': 'total_cost', 'label': '总费用(万元)', 'sortable': True, 'width': 130},
        {'key': 'avg_cost', 'label': '次均费用(元)', 'sortable': True, 'width': 130},
        {'key': 'profit_loss', 'label': '盈亏(万元)', 'sortable': True, 'width': 120},
        {'key': 'cmi', 'label': 'CMI', 'sortable': True, 'width': 80},
    ]
    rows = []
    for d in disease_data:
        case_count = d.get('case_count') or d.get('病例数', 0)
        total_cost = d.get('total_cost') or d.get('总费用', 0)
        rows.append({
            'disease': d.get('dip_name') or d.get('病种', ''),
            'case_count': int(case_count) if case_count else 0,
            'total_cost': _safe_round((total_cost or 0) / 10000),
            'avg_cost': _safe_round(total_cost / case_count if case_count else 0),
            'profit_loss': _safe_round((d.get('profit_loss') or d.get('盈亏', 0) or 0) / 10000),
            'cmi': _safe_round(d.get('cmi') or d.get('CMI', 0), 3),
        })
    rows.sort(key=lambda x: x.get('case_count', 0), reverse=True)
    return {'columns': columns, 'rows': rows}


def _build_monthly_table(monthly_data: List[Dict]) -> Dict:
    columns = [
        {'key': 'month', 'label': '月份', 'sortable': True, 'width': 110},
        {'key': 'case_count', 'label': '病例数', 'sortable': True, 'width': 100},
        {'key': 'total_cost', 'label': '总费用(万元)', 'sortable': True, 'width': 130},
        {'key': 'avg_cost', 'label': '次均费用(元)', 'sortable': True, 'width': 130},
        {'key': 'profit_loss', 'label': '盈亏(万元)', 'sortable': True, 'width': 120},
        {'key': 'cmi', 'label': 'CMI', 'sortable': True, 'width': 80},
    ]
    rows = []
    for d in monthly_data:
        case_count = d.get('case_count') or d.get('病例数', 0)
        total_cost = d.get('total_cost') or d.get('总费用', 0)
        rows.append({
            'month': d.get('数据月份') or d.get('month', ''),
            'case_count': int(case_count) if case_count else 0,
            'total_cost': _safe_round((total_cost or 0) / 10000),
            'avg_cost': _safe_round(total_cost / case_count if case_count else 0),
            'profit_loss': _safe_round((d.get('profit_loss') or d.get('盈亏', 0) or 0) / 10000),
            'cmi': _safe_round(d.get('cmi') or d.get('CMI', 0), 3),
        })
    return {'columns': columns, 'rows': rows}


def _build_doctor_table(doctor_data: List[Dict]) -> Dict:
    columns = [
        {'key': 'doctor', 'label': '医生', 'sortable': True, 'width': 120},
        {'key': 'case_count', 'label': '病例数', 'sortable': True, 'width': 100},
        {'key': 'total_cost', 'label': '总费用(万元)', 'sortable': True, 'width': 130},
        {'key': 'avg_cost', 'label': '次均费用(元)', 'sortable': True, 'width': 130},
        {'key': 'profit_loss', 'label': '盈亏(万元)', 'sortable': True, 'width': 120},
        {'key': 'avg_los', 'label': '平均住院日', 'sortable': True, 'width': 110},
    ]
    rows = []
    for d in doctor_data:
        case_count = d.get('case_count') or d.get('病例数', 0)
        total_cost = d.get('total_cost') or d.get('总费用', 0)
        rows.append({
            'doctor': d.get('doctor') or d.get('医生', ''),
            'case_count': int(case_count) if case_count else 0,
            'total_cost': _safe_round((total_cost or 0) / 10000),
            'avg_cost': _safe_round(total_cost / case_count if case_count else 0),
            'profit_loss': _safe_round((d.get('profit_loss') or d.get('盈亏', 0) or 0) / 10000),
            'avg_los': _safe_round(d.get('avg_los') or d.get('平均住院日', 0), 1),
        })
    rows.sort(key=lambda x: x.get('case_count', 0), reverse=True)
    return {'columns': columns, 'rows': rows}


def _build_fund_flow_table(fund_flow_data: Dict) -> Dict:
    """从资金流向数据中构建表格 - 展示科室→医生的资金分配"""
    columns = [
        {'key': 'source', 'label': '来源', 'sortable': True, 'width': 140},
        {'key': 'target', 'label': '流向', 'sortable': True, 'width': 140},
        {'key': 'value', 'label': '金额(万元)', 'sortable': True, 'width': 120},
    ]
    rows = []
    links = fund_flow_data.get('links', [])
    for link in links:
        rows.append({
            'source': link.get('source', ''),
            'target': link.get('target', ''),
            'value': _safe_round(link.get('value', 0) / 10000),
        })
    rows.sort(key=lambda x: x.get('value', 0), reverse=True)
    return {'columns': columns, 'rows': rows}


def _build_cost_flow_table(cost_flow_data: Dict) -> Dict:
    """从费用结构流向数据中构建表格"""
    columns = [
        {'key': 'source', 'label': '来源', 'sortable': True, 'width': 140},
        {'key': 'target', 'label': '流向', 'sortable': True, 'width': 140},
        {'key': 'value', 'label': '金额(万元)', 'sortable': True, 'width': 120},
    ]
    rows = []
    links = cost_flow_data.get('links', [])
    for link in links:
        rows.append({
            'source': link.get('source', ''),
            'target': link.get('target', ''),
            'value': _safe_round(link.get('value', 0) / 10000),
        })
    rows.sort(key=lambda x: x.get('value', 0), reverse=True)
    return {'columns': columns, 'rows': rows}


def _build_waterfall_table(overview: Dict) -> Dict:
    columns = [
        {'key': 'item', 'label': '项目', 'sortable': False, 'width': 160},
        {'key': 'amount', 'label': '金额(万元)', 'sortable': True, 'width': 130},
    ]
    total_cost = overview.get('total_cost', 0)
    total_payment = overview.get('total_payment', total_cost + overview.get('total_profit_loss', 0))
    total_profit = overview.get('total_profit_loss', 0)
    rows = [
        {'item': 'DIP支付/收入', 'amount': _safe_round(total_payment / 10000)},
        {'item': '总成本', 'amount': _safe_round(total_cost / 10000)},
        {'item': '盈亏', 'amount': _safe_round(total_profit / 10000)},
    ]
    return {'columns': columns, 'rows': rows}


def _build_rate_type_table(rate_type_data: List[Dict]) -> Dict:
    columns = [
        {'key': 'rate_type', 'label': '倍率类型', 'sortable': True, 'width': 140},
        {'key': 'case_count', 'label': '病例数', 'sortable': True, 'width': 100},
        {'key': 'total_cost', 'label': '总费用(万元)', 'sortable': True, 'width': 130},
        {'key': 'proportion', 'label': '占比(%)', 'sortable': True, 'width': 100},
    ]
    total = sum(d.get('case_count', d.get('病例数', 0)) or 0 for d in rate_type_data)
    rows = []
    for d in rate_type_data:
        case_count = d.get('case_count') or d.get('病例数', 0)
        rows.append({
            'rate_type': d.get('rate_type') or d.get('倍率类型', ''),
            'case_count': int(case_count) if case_count else 0,
            'total_cost': _safe_round((d.get('total_cost') or d.get('总费用', 0) or 0) / 10000),
            'proportion': _safe_round(case_count / total * 100 if total else 0, 1),
        })
    return {'columns': columns, 'rows': rows}


def _build_insurance_table(insurance_data: Any) -> Dict:
    columns = [
        {'key': 'type', 'label': '参保类型', 'sortable': True, 'width': 140},
        {'key': 'case_count', 'label': '病例数', 'sortable': True, 'width': 100},
        {'key': 'total_cost', 'label': '总费用(万元)', 'sortable': True, 'width': 130},
        {'key': 'proportion', 'label': '占比(%)', 'sortable': True, 'width': 100},
    ]
    rows = []
    data_list = insurance_data if isinstance(insurance_data, list) else insurance_data.get('data', [])
    total = sum(d.get('case_count', d.get('病例数', 0)) or 0 for d in data_list)
    for d in data_list:
        case_count = d.get('case_count') or d.get('病例数', 0)
        rows.append({
            'type': d.get('insurance_type') or d.get('参保类型', ''),
            'case_count': int(case_count) if case_count else 0,
            'total_cost': _safe_round((d.get('total_cost') or d.get('总费用', 0) or 0) / 10000),
            'proportion': _safe_round(case_count / total * 100 if total else 0, 1),
        })
    return {'columns': columns, 'rows': rows}


def _build_balance_table(top10: List[Dict], bottom10: List[Dict]) -> Dict:
    columns = [
        {'key': 'disease', 'label': '病种', 'sortable': True, 'width': 200},
        {'key': 'balance', 'label': '结余(万元)', 'sortable': True, 'width': 120},
        {'key': 'case_count', 'label': '病例数', 'sortable': True, 'width': 100},
        {'key': 'category', 'label': '分类', 'sortable': True, 'width': 100},
    ]
    rows = []
    for d in (top10 or []):
        rows.append({
            'disease': d.get('dip_name') or d.get('病种', ''),
            'balance': _safe_round((d.get('balance') or d.get('结余', 0) or 0) / 10000),
            'case_count': int(d.get('case_count') or d.get('病例数', 0)),
            'category': '盈利TOP',
        })
    for d in (bottom10 or []):
        rows.append({
            'disease': d.get('dip_name') or d.get('病种', ''),
            'balance': _safe_round((d.get('balance') or d.get('结余', 0) or 0) / 10000),
            'case_count': int(d.get('case_count') or d.get('病例数', 0)),
            'category': '亏损TOP',
        })
    return {'columns': columns, 'rows': rows}
