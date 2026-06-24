"""
图表服务 - 向后兼容 re-export
实际实现已拆分至 charts/ 子包
"""

from .charts import ChartService

__all__ = ["ChartService"]
