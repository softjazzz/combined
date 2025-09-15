"""
性能指标采集模块
收集和统计引擎执行的性能数据
"""

import time
from typing import Dict, List, Optional
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import statistics


@dataclass
class ExecutionMetric:
    """单次执行指标"""
    timestamp: datetime
    event_type: Optional[str]
    execution_time_ms: float
    rules_evaluated: int
    rules_hit: int
    decision: str
    cache_hits: int = 0
    cache_misses: int = 0


class MetricsCollector:
    """指标收集器"""
    
    def __init__(self, max_history: int = 1000):
        """
        初始化指标收集器
        
        Args:
            max_history: 保留的历史记录数量
        """
        self.max_history = max_history
        self.execution_history: deque = deque(maxlen=max_history)
        
        # 累计统计
        self.total_requests = 0
        self.total_execution_time = 0.0
        self.total_rules_evaluated = 0
        self.total_rules_hit = 0
        self.total_cache_hits = 0
        self.total_cache_misses = 0
        
        # 决策统计
        self.decision_counts = {
            'pass': 0,
            'warn': 0,
            'block': 0
        }
        
        # 错误统计
        self.error_count = 0
        self.last_error_time: Optional[datetime] = None
        
        # 启动时间
        self.start_time = datetime.now()
    
    def record_execution(
        self,
        event_type: Optional[str],
        execution_time_ms: float,
        rules_evaluated: int,
        rules_hit: int,
        decision: str,
        cache_hits: int = 0,
        cache_misses: int = 0
    ) -> None:
        """
        记录一次执行
        
        Args:
            event_type: 事件类型
            execution_time_ms: 执行时间（毫秒）
            rules_evaluated: 评估的规则数
            rules_hit: 命中的规则数
            decision: 决策结果
            cache_hits: 缓存命中数
            cache_misses: 缓存未命中数
        """
        metric = ExecutionMetric(
            timestamp=datetime.now(),
            event_type=event_type,
            execution_time_ms=execution_time_ms,
            rules_evaluated=rules_evaluated,
            rules_hit=rules_hit,
            decision=decision,
            cache_hits=cache_hits,
            cache_misses=cache_misses
        )
        
        # 添加到历史记录
        self.execution_history.append(metric)
        
        # 更新累计统计
        self.total_requests += 1
        self.total_execution_time += execution_time_ms
        self.total_rules_evaluated += rules_evaluated
        self.total_rules_hit += rules_hit
        self.total_cache_hits += cache_hits
        self.total_cache_misses += cache_misses
        
        # 更新决策统计
        if decision in self.decision_counts:
            self.decision_counts[decision] += 1
    
    def record_error(self) -> None:
        """记录错误"""
        self.error_count += 1
        self.last_error_time = datetime.now()
    
    def get_stats(self) -> Dict:
        """
        获取统计信息
        
        Returns:
            统计信息字典
        """
        uptime = datetime.now() - self.start_time
        
        # 计算平均值
        avg_execution_time = (
            self.total_execution_time / self.total_requests
            if self.total_requests > 0 else 0
        )
        
        avg_rules_evaluated = (
            self.total_rules_evaluated / self.total_requests
            if self.total_requests > 0 else 0
        )
        
        # 计算缓存命中率
        total_cache_access = self.total_cache_hits + self.total_cache_misses
        cache_hit_rate = (
            self.total_cache_hits / total_cache_access
            if total_cache_access > 0 else 0
        )
        
        # 计算规则命中率
        rule_hit_rate = (
            self.total_rules_hit / self.total_rules_evaluated
            if self.total_rules_evaluated > 0 else 0
        )
        
        # 计算错误率
        error_rate = (
            self.error_count / self.total_requests
            if self.total_requests > 0 else 0
        )
        
        return {
            'uptime_seconds': uptime.total_seconds(),
            'total_requests': self.total_requests,
            'avg_execution_time_ms': round(avg_execution_time, 2),
            'avg_rules_evaluated': round(avg_rules_evaluated, 1),
            'total_rules_evaluated': self.total_rules_evaluated,
            'total_rules_hit': self.total_rules_hit,
            'rule_hit_rate': round(rule_hit_rate, 3),
            'cache_hit_rate': round(cache_hit_rate, 3),
            'decision_counts': self.decision_counts.copy(),
            'error_count': self.error_count,
            'error_rate': round(error_rate, 3),
            'last_error_time': (
                self.last_error_time.isoformat()
                if self.last_error_time else None
            )
        }
    
    def get_percentiles(self) -> Dict:
        """
        获取执行时间的百分位数
        
        Returns:
            百分位数统计
        """
        if not self.execution_history:
            return {
                'p50': 0,
                'p75': 0,
                'p90': 0,
                'p95': 0,
                'p99': 0,
                'max': 0,
                'min': 0
            }
        
        execution_times = [m.execution_time_ms for m in self.execution_history]
        
        return {
            'p50': round(statistics.median(execution_times), 2),
            'p75': round(self._percentile(execution_times, 75), 2),
            'p90': round(self._percentile(execution_times, 90), 2),
            'p95': round(self._percentile(execution_times, 95), 2),
            'p99': round(self._percentile(execution_times, 99), 2),
            'max': round(max(execution_times), 2),
            'min': round(min(execution_times), 2)
        }
    
    def get_recent_stats(self, minutes: int = 5) -> Dict:
        """
        获取最近N分钟的统计
        
        Args:
            minutes: 时间窗口（分钟）
        
        Returns:
            最近的统计信息
        """
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        recent_metrics = [
            m for m in self.execution_history
            if m.timestamp >= cutoff_time
        ]
        
        if not recent_metrics:
            return {
                'count': 0,
                'avg_execution_time_ms': 0,
                'decision_counts': {'pass': 0, 'warn': 0, 'block': 0}
            }
        
        # 计算最近的统计
        recent_execution_times = [m.execution_time_ms for m in recent_metrics]
        recent_decisions = [m.decision for m in recent_metrics]
        
        decision_counts = {
            'pass': recent_decisions.count('pass'),
            'warn': recent_decisions.count('warn'),
            'block': recent_decisions.count('block')
        }
        
        return {
            'count': len(recent_metrics),
            'avg_execution_time_ms': round(
                statistics.mean(recent_execution_times), 2
            ),
            'decision_counts': decision_counts
        }
    
    def get_by_event_type(self) -> Dict:
        """
        按事件类型分组统计
        
        Returns:
            按事件类型的统计信息
        """
        event_stats = {}
        
        for metric in self.execution_history:
            event_type = metric.event_type or 'unknown'
            
            if event_type not in event_stats:
                event_stats[event_type] = {
                    'count': 0,
                    'total_time': 0,
                    'rules_evaluated': 0,
                    'rules_hit': 0
                }
            
            stats = event_stats[event_type]
            stats['count'] += 1
            stats['total_time'] += metric.execution_time_ms
            stats['rules_evaluated'] += metric.rules_evaluated
            stats['rules_hit'] += metric.rules_hit
        
        # 计算平均值
        for event_type, stats in event_stats.items():
            if stats['count'] > 0:
                stats['avg_time_ms'] = round(
                    stats['total_time'] / stats['count'], 2
                )
                stats['avg_rules_evaluated'] = round(
                    stats['rules_evaluated'] / stats['count'], 1
                )
                stats['hit_rate'] = round(
                    stats['rules_hit'] / stats['rules_evaluated']
                    if stats['rules_evaluated'] > 0 else 0,
                    3
                )
        
        return event_stats
    
    def reset(self) -> None:
        """重置所有统计"""
        self.execution_history.clear()
        self.total_requests = 0
        self.total_execution_time = 0.0
        self.total_rules_evaluated = 0
        self.total_rules_hit = 0
        self.total_cache_hits = 0
        self.total_cache_misses = 0
        self.decision_counts = {'pass': 0, 'warn': 0, 'block': 0}
        self.error_count = 0
        self.last_error_time = None
        self.start_time = datetime.now()
    
    @staticmethod
    def _percentile(data: List[float], percentile: float) -> float:
        """
        计算百分位数
        
        Args:
            data: 数据列表
            percentile: 百分位数 (0-100)
        
        Returns:
            百分位数值
        """
        if not data:
            return 0
        
        sorted_data = sorted(data)
        index = (len(sorted_data) - 1) * percentile / 100
        lower = int(index)
        upper = lower + 1
        
        if upper >= len(sorted_data):
            return sorted_data[lower]
        
        weight = index - lower
        return sorted_data[lower] * (1 - weight) + sorted_data[upper] * weight


# 创建全局指标收集器实例
metrics_collector = MetricsCollector()


# 导出
__all__ = [
    'ExecutionMetric',
    'MetricsCollector',
    'metrics_collector'
]
