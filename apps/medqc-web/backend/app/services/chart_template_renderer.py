"""
图表模板渲染器
- 根据 LLM 输出的参数生成完整的 ECharts 配置
- 预定义多种图表模板
- 统一视觉规范（配色、字号、动画）
"""
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


# 统一配色方案
CHART_COLORS = {
    'primary': ['#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de', 
                '#3ba272', '#fc8452', '#9a60b4', '#ea7ccc'],
    'medical': ['#2563eb', '#16a34a', '#dc2626', '#f59e0b', '#8b5cf6',
                '#06b6d4', '#ec4899', '#84cc16', '#f97316'],
    'gradient_blue': ['#667eea', '#764ba2'],
    'gradient_green': ['#56ab2f', '#a8e063']
}

# 通用样式配置
COMMON_STYLE = {
    'animation': True,
    'animationDuration': 800,
    'animationEasing': 'cubicOut',
    'textStyle': {
        'fontFamily': 'PingFang SC, Microsoft YaHei, sans-serif'
    }
}


class ChartTemplateRenderer:
    """图表模板渲染器"""
    
    def __init__(self, color_palette: str = 'medical'):
        self.colors = CHART_COLORS.get(color_palette, CHART_COLORS['medical'])
    
    def render(self, template_params: Dict[str, Any], data: List[Dict] = None) -> Dict:
        """
        根据 LLM 输出的参数渲染图表配置
        
        Args:
            template_params: LLM 输出的图表参数
            data: 可选的数据（若未提供则使用 params 中的数据）
            
        Returns:
            完整的 ECharts 配置
        """
        chart_type = template_params.get('chart_type', 'bar')
        
        # 根据图表类型选择渲染方法
        render_methods = {
            'bar': self._render_bar,
            'line': self._render_line,
            'pie': self._render_pie,
            'scatter': self._render_scatter,
            'mixed': self._render_mixed,
            'horizontal_bar': self._render_horizontal_bar,
            'sankey': self._render_sankey,
            'diverging_bar': self._render_diverging_bar,
            'quadrant': self._render_quadrant
        }
        
        render_fn = render_methods.get(chart_type, self._render_bar)
        
        try:
            option = render_fn(template_params, data)
            logger.info(f"[ChartTemplateRenderer] 渲染成功: {chart_type}")
            return option
        except Exception as e:
            logger.error(f"[ChartTemplateRenderer] 渲染失败: {e}", exc_info=True)
            return self._render_fallback(template_params)
    
    def _render_bar(self, params: Dict, data: List[Dict] = None) -> Dict:
        """渲染柱状图"""
        title = params.get('title', '数据分析')
        x_field = params.get('x_field', 'name')
        y_field = params.get('y_field', 'value')
        sort = params.get('sort', 'none')
        top_n = params.get('top_n', 15)
        
        # 处理数据
        x_data = params.get('x_data', [])
        # y_field 可能是数组（多指标），保持渲染健壮性
        if isinstance(y_field, list):
            y_fields = [str(f) for f in y_field if f is not None]
        else:
            y_fields = [str(y_field)]

        y_data_list = params.get('y_data_list')
        if y_data_list is None:
            y_data_list = [params.get('y_data', [])]
        # 过滤 None，确保长度与 y_fields 对齐（不足则截断/补空）
        y_data_list = [(d or []) for d in (y_data_list or [])]
        if len(y_data_list) < len(y_fields):
            y_data_list = y_data_list + ([[]] * (len(y_fields) - len(y_data_list)))
        elif len(y_data_list) > len(y_fields):
            y_data_list = y_data_list[:len(y_fields)]
        
        # 排序处理
        primary_y = y_data_list[0] if y_data_list else []
        if sort in ('desc', 'asc') and x_data and primary_y:
            zipped = list(zip(primary_y, x_data, *y_data_list[1:]))
            zipped_sorted = sorted(zipped, key=lambda t: t[0], reverse=(sort == 'desc'))[:top_n]
            if zipped_sorted:
                x_data = [t[1] for t in zipped_sorted]
                y_data_list = [[t[0] for t in zipped_sorted]] + [
                    [t[i] for t in zipped_sorted] for i in range(2, 2 + len(y_data_list[1:]))
                ]
            else:
                x_data = []
                y_data_list = [[] for _ in y_fields]
        
        series = []
        for idx, field_name in enumerate(y_fields):
            series.append({
                'name': field_name,
                'type': 'bar',
                'data': y_data_list[idx] if idx < len(y_data_list) else [],
                'itemStyle': {
                    'borderRadius': [4, 4, 0, 0]
                },
                'emphasis': {
                    'itemStyle': {
                        'shadowBlur': 10,
                        'shadowOffsetX': 0,
                        'shadowColor': 'rgba(0, 0, 0, 0.5)'
                    }
                }
            })

        return {
            **COMMON_STYLE,
            'color': self.colors,
            'title': {
                'text': title,
                'left': 'center',
                'textStyle': {'fontSize': 16, 'fontWeight': 'bold'}
            },
            'tooltip': {
                'trigger': 'axis',
                'axisPointer': {'type': 'shadow'}
            },
            'grid': {
                'left': '3%',
                'right': '4%',
                'bottom': '3%',
                'containLabel': True
            },
            'xAxis': {
                'type': 'category',
                'data': x_data,
                'axisLabel': {
                    'rotate': 45 if len(x_data) > 6 else 0,
                    'interval': 0
                }
            },
            'yAxis': {
                'type': 'value',
                'name': y_fields[0] if y_fields else '值'
            },
            'series': series
        }
    
    def _render_horizontal_bar(self, params: Dict, data: List[Dict] = None) -> Dict:
        """渲染水平柱状图（适合排名展示）"""
        title = params.get('title', '数据排名')
        x_field = params.get('x_field', 'name')
        y_field = params.get('y_field', 'value')
        top_n = params.get('top_n', 10)
        
        if isinstance(y_field, list):
            y_fields = [str(f) for f in y_field if f is not None]
        else:
            y_fields = [str(y_field)]

        x_data = (params.get('x_data', []) or [])[:top_n]
        y_data_list = params.get('y_data_list')
        if y_data_list is None:
            y_data_list = [params.get('y_data', [])]
        y_data_list = [(d or [])[:top_n] for d in (y_data_list or [])]
        if len(y_data_list) < len(y_fields):
            y_data_list = y_data_list + ([[]] * (len(y_fields) - len(y_data_list)))
        elif len(y_data_list) > len(y_fields):
            y_data_list = y_data_list[:len(y_fields)]
        
        # 反转顺序（最大在上）
        x_data = list(reversed(x_data))
        y_data_list = [list(reversed(d)) for d in y_data_list]

        series = []
        for idx, field_name in enumerate(y_fields):
            series.append({
                'name': field_name,
                'type': 'bar',
                'data': y_data_list[idx] if idx < len(y_data_list) else [],
                'itemStyle': {
                    'borderRadius': [0, 4, 4, 0]
                },
                'label': {
                    'show': True,
                    'position': 'right',
                    'formatter': '{c}'
                }
            })
        
        return {
            **COMMON_STYLE,
            'color': self.colors,
            'title': {
                'text': title,
                'left': 'center',
                'textStyle': {'fontSize': 16, 'fontWeight': 'bold'}
            },
            'tooltip': {
                'trigger': 'axis',
                'axisPointer': {'type': 'shadow'}
            },
            'grid': {
                'left': '25%',
                'right': '10%',
                'bottom': '5%',
                'top': '15%'
            },
            'xAxis': {
                'type': 'value',
                'name': y_fields[0] if y_fields else '值'
            },
            'yAxis': {
                'type': 'category',
                'data': x_data,
                'axisLabel': {'fontSize': 12}
            },
            'series': series
        }
    
    def _render_sankey(self, params: Dict, data: List[Dict] = None) -> Dict:
        """渲染桑基图"""
        title = params.get('title', '流向分析')
        nodes = params.get('nodes', [])
        links = params.get('links', [])
        
        # 适配: 如果传入了 data 但没传 nodes/links，尝试从 data 构建 (简化版，通常由外部构建好)
        if not nodes and not links and data:
            # TODO: 实现自动构建 Sankey 数据逻辑 (Src -> Target -> Value)
            pass

        return {
            **COMMON_STYLE,
            'title': {
                'text': title,
                'left': 'center',
                'textStyle': {'fontSize': 16, 'fontWeight': 'bold'}
            },
            'tooltip': {
                'trigger': 'item',
                'triggerOn': 'mousemove'
            },
            'series': [
                {
                    'type': 'sankey',
                    'data': nodes,
                    'links': links,
                    'emphasis': {
                        'focus': 'adjacency'
                    },
                    'lineStyle': {
                        'color': 'gradient',
                        'curveness': 0.5
                    },
                    'label': {
                        'position': 'right'
                    }
                }
            ]
        }

    def _render_diverging_bar(self, params: Dict, data: List[Dict] = None) -> Dict:
        """渲染双向（盈亏）条形图"""
        title = params.get('title', '盈亏分析')
        x_data = params.get('x_data', [])
        y_data = params.get('y_data', [])  # 这里 y_data 是数值
        
        series_data = []
        for val in y_data:
            val_num = float(val) if val is not None else 0
            series_data.append({
                'value': val_num,
                'itemStyle': {
                    'color': '#10b981' if val_num >= 0 else '#ef4444', # 绿盈红亏
                    'borderRadius': [0, 4, 4, 0] if val_num >= 0 else [4, 0, 0, 4]
                }
            })
            
        return {
            **COMMON_STYLE,
            'title': {
                'text': title,
                'left': 'center',
                'textStyle': {'fontSize': 16, 'fontWeight': 'bold'}
            },
            'tooltip': {
                'trigger': 'axis',
                'axisPointer': {'type': 'shadow'},
                'formatter': '{b}: {c}'
            },
            'grid': {
                'left': '3%',
                'right': '4%',
                'bottom': '3%',
                'containLabel': True
            },
            'xAxis': {
                'type': 'value',
                'position': 'top',
                'splitLine': {'lineStyle': {'type': 'dashed'}}
            },
            'yAxis': {
                'type': 'category',
                'axisTick': {'show': False},
                'data': x_data
            },
            'series': [
                {
                    'name': '盈亏额',
                    'type': 'bar',
                    'stack': 'Total',
                    'label': {'show': True, 'position': 'outside'},
                    'data': series_data
                }
            ]
        }

    def _render_quadrant(self, params: Dict, data: List[Dict] = None) -> Dict:
        """渲染四象限散点图 (带平均线)"""
        title = params.get('title', '四象限分析')
        x_field = params.get('x_field', 'X轴')
        y_field = params.get('y_field', 'Y轴')
        name_field = params.get('name_field', 'Label')
        
        # scatter_data 结构: [[x, y, name, size, ...], ...]
        raw_data = params.get('scatter_data', [])
        
        # 计算平均值作为象限分割线
        x_vals = [d[0] for d in raw_data if d[0] is not None]
        y_vals = [d[1] for d in raw_data if d[1] is not None]
        
        x_avg = sum(x_vals) / len(x_vals) if x_vals else 0
        y_avg = sum(y_vals) / len(y_vals) if y_vals else 0

        # 预处理数据：计算颜色和大小，构建 ECharts 数据项
        processed_data = []
        for item in raw_data:
            x_val, y_val = item[0], item[1]
            name = item[2] if len(item) > 2 else ''
            size_val = item[3] if len(item) > 3 else 10
            
            # 颜色逻辑: 只有同时小于均值才红，同时大于均值才绿，否则黄
            color = '#f59e0b'
            if x_val < x_avg and y_val < y_avg:
                color = '#ef4444'
            elif x_val > x_avg and y_val > y_avg:
                color = '#10b981'
            
            # 大小归一化 (简单处理)
            symbol_size = min(max(size_val / 2, 8), 40)

            processed_data.append({
                'value': [x_val, y_val, name, size_val],
                'symbolSize': symbol_size,
                'itemStyle': {
                    'color': color,
                    'shadowBlur': 10,
                    'shadowColor': 'rgba(120, 36, 50, 0.5)',
                    'shadowOffsetY': 5
                }
            })

        return {
            **COMMON_STYLE,
            'color': self.colors,
            'title': {
                'text': title,
                'left': 'center',
                'textStyle': {'fontSize': 16, 'fontWeight': 'bold'}
            },
            'tooltip': {
                'trigger': 'item',
                # 使用 ECharts 字符串模板: {c} 是 value 数组
                # value: [x, y, name, size]
                # 索引: 0->x, 1->y, 2->name
                'formatter':  f"{{b}}<br/>{name_field}: {{@2}}<br/>{x_field}: {{@0}}<br/>{y_field}: {{@1}}"
            },
            'xAxis': {
                'type': 'value',
                'name': x_field,
                'nameLocation': 'middle',
                'nameGap': 30,
                'splitLine': {'lineStyle': {'type': 'dashed'}}
            },
            'yAxis': {
                'type': 'value',
                'name': y_field,
                'nameLocation': 'middle',
                'nameGap': 40,
                'splitLine': {'lineStyle': {'type': 'dashed'}}
            },
            'series': [{
                'name': title,
                'type': 'scatter',
                'data': processed_data,
                'label': {
                    'show': True,
                    'formatter': '{@2}', # 显示 name
                    'position': 'top'
                },
                'markLine': {
                    'silent': True,
                    'lineStyle': {'color': '#333', 'type': 'solid'},
                    'data': [
                        {'xAxis': x_avg, 'label': {'formatter': '平均值'}},
                        {'yAxis': y_avg, 'label': {'formatter': '平均值'}}
                    ]
                }
            }]
        }

    def _render_line(self, params: Dict, data: List[Dict] = None) -> Dict:
        """渲染折线图"""
        title = params.get('title', '趋势分析')
        x_field = params.get('x_field', 'date')
        y_fields = params.get('y_field', ['value'])
        
        if isinstance(y_fields, str):
            y_fields = [y_fields]
        
        x_data = params.get('x_data', [])
        y_data_list = params.get('y_data_list', [params.get('y_data', [])])
        
        series = []
        for i, (y_field, y_data) in enumerate(zip(y_fields, y_data_list)):
            series.append({
                'name': y_field,
                'type': 'line',
                'data': y_data,
                'smooth': True,
                'symbol': 'circle',
                'symbolSize': 6,
                'lineStyle': {'width': 2},
                'areaStyle': {
                    'opacity': 0.1
                }
            })
        
        return {
            **COMMON_STYLE,
            'color': self.colors,
            'title': {
                'text': title,
                'left': 'center',
                'textStyle': {'fontSize': 16, 'fontWeight': 'bold'}
            },
            'tooltip': {
                'trigger': 'axis'
            },
            'legend': {
                'top': 30,
                'data': y_fields
            },
            'grid': {
                'left': '3%',
                'right': '4%',
                'bottom': '3%',
                'top': '20%',
                'containLabel': True
            },
            'xAxis': {
                'type': 'category',
                'data': x_data,
                'boundaryGap': False
            },
            'yAxis': {
                'type': 'value'
            },
            'series': series
        }
    
    def _render_pie(self, params: Dict, data: List[Dict] = None) -> Dict:
        """渲染饼图"""
        title = params.get('title', '占比分析')
        
        pie_data = params.get('pie_data', [])
        if not pie_data and params.get('x_data') and params.get('y_data'):
            pie_data = [
                {'name': x, 'value': y} 
                for x, y in zip(params['x_data'], params['y_data'])
            ]
        
        return {
            **COMMON_STYLE,
            'color': self.colors,
            'title': {
                'text': title,
                'left': 'center',
                'textStyle': {'fontSize': 16, 'fontWeight': 'bold'}
            },
            'tooltip': {
                'trigger': 'item',
                'formatter': '{b}: {c} ({d}%)'
            },
            'legend': {
                'orient': 'vertical',
                'left': 'left',
                'top': 'middle'
            },
            'series': [{
                'name': title,
                'type': 'pie',
                'radius': ['40%', '70%'],
                'center': ['60%', '55%'],
                'avoidLabelOverlap': True,
                'itemStyle': {
                    'borderRadius': 6,
                    'borderColor': '#fff',
                    'borderWidth': 2
                },
                'label': {
                    'show': True,
                    'formatter': '{b}: {d}%'
                },
                'emphasis': {
                    'label': {
                        'fontSize': 14,
                        'fontWeight': 'bold'
                    }
                },
                'data': pie_data
            }]
        }
    
    def _render_scatter(self, params: Dict, data: List[Dict] = None) -> Dict:
        """渲染散点图"""
        title = params.get('title', '分布分析')
        x_field = params.get('x_field', 'x')
        y_field = params.get('y_field', 'y')
        
        scatter_data = params.get('scatter_data', [])
        
        return {
            **COMMON_STYLE,
            'color': self.colors,
            'title': {
                'text': title,
                'left': 'center',
                'textStyle': {'fontSize': 16, 'fontWeight': 'bold'}
            },
            'tooltip': {
                'trigger': 'item',
                'formatter': '{b}: {c}'  # 改为字符串模板，避免 lambda 序列化问题
            },
            'xAxis': {
                'type': 'value',
                'name': x_field,
                'nameLocation': 'center',
                'nameGap': 30
            },
            'yAxis': {
                'type': 'value',
                'name': y_field,
                'nameLocation': 'center',
                'nameGap': 40
            },
            'series': [{
                'name': title,
                'type': 'scatter',
                'data': scatter_data,
                'symbolSize': 10,
                'itemStyle': {
                    'opacity': 0.7
                },
                'emphasis': {
                    'itemStyle': {
                        'opacity': 1,
                        'shadowBlur': 10
                    }
                }
            }]
        }
    
    def _render_mixed(self, params: Dict, data: List[Dict] = None) -> Dict:
        """渲染混合图表（柱状+折线）"""
        title = params.get('title', '综合分析')
        x_data = params.get('x_data', [])
        bar_data = params.get('bar_data', [])
        line_data = params.get('line_data', [])
        bar_name = params.get('bar_name', '数量')
        line_name = params.get('line_name', '金额')
        
        return {
            **COMMON_STYLE,
            'color': self.colors,
            'title': {
                'text': title,
                'left': 'center',
                'textStyle': {'fontSize': 16, 'fontWeight': 'bold'}
            },
            'tooltip': {
                'trigger': 'axis',
                'axisPointer': {'type': 'cross'}
            },
            'legend': {
                'top': 30,
                'data': [bar_name, line_name]
            },
            'grid': {
                'left': '3%',
                'right': '4%',
                'bottom': '3%',
                'top': '20%',
                'containLabel': True
            },
            'xAxis': {
                'type': 'category',
                'data': x_data,
                'axisLabel': {'rotate': 45 if len(x_data) > 6 else 0}
            },
            'yAxis': [
                {
                    'type': 'value',
                    'name': bar_name,
                    'position': 'left'
                },
                {
                    'type': 'value',
                    'name': line_name,
                    'position': 'right'
                }
            ],
            'series': [
                {
                    'name': bar_name,
                    'type': 'bar',
                    'data': bar_data,
                    'itemStyle': {'borderRadius': [4, 4, 0, 0]}
                },
                {
                    'name': line_name,
                    'type': 'line',
                    'yAxisIndex': 1,
                    'data': line_data,
                    'smooth': True,
                    'symbol': 'circle',
                    'symbolSize': 8
                }
            ]
        }
    
    def _render_fallback(self, params: Dict) -> Dict:
        """降级渲染"""
        title = params.get('title', '数据分析')
        
        return {
            **COMMON_STYLE,
            'title': {
                'text': title,
                'subtext': '图表渲染失败，请检查数据',
                'left': 'center',
                'top': 'center',
                'textStyle': {'fontSize': 16}
            },
            'xAxis': {'show': False},
            'yAxis': {'show': False},
            'series': []
        }
    
    
    # 全局实例
chart_renderer = ChartTemplateRenderer()


def render_chart_from_params(params: Dict, data: List[Dict] = None) -> Dict:
    """便捷函数：根据参数渲染图表"""
    return chart_renderer.render(params, data)
