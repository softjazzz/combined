"""
图表服务 - 为前端 ECharts 提供配置数据
由多个领域模块组合而成
"""

from .colors import COLORS
from .department import DepartmentChartsMixin
from .disease import DiseaseChartsMixin
from .monthly import MonthlyChartsMixin
from .financial import FinancialChartsMixin
from .orchestrator import OrchestratorMixin


class ChartService(
    DepartmentChartsMixin,
    DiseaseChartsMixin,
    MonthlyChartsMixin,
    FinancialChartsMixin,
    OrchestratorMixin,
):
    """图表配置生成服务 - 由领域模块组合"""
    COLORS = COLORS


__all__ = ["ChartService", "COLORS"]
