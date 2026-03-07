"""
增强版分析服务 - 由多个领域模块组合而成
"""

from .base import BaseAnalyzerMixin
from .department import DepartmentAnalyzerMixin
from .disease import DiseaseAnalyzerMixin
from .financial import FinancialAnalyzerMixin


class EnhancedAnalyzer(
    BaseAnalyzerMixin,
    DepartmentAnalyzerMixin,
    DiseaseAnalyzerMixin,
    FinancialAnalyzerMixin,
):
    """增强版数据分析器 - 由领域模块组合"""
    pass


__all__ = ["EnhancedAnalyzer"]
