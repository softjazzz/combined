# 系统性能优化和监控
# 提供全面的系统性能监控、优化建议和资源管理

from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List, Optional
import asyncio
import psutil
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from .unified_api_standards import (
    UnifiedAPIResponse, create_success_response, 
    api_performance_monitor
)
from ..database.database import get_db
from ..auth.dependencies import get_current_user, require_permissions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/system", tags=["系统优化和监控"])

# 性能等级枚举
class PerformanceLevel(str, Enum):
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"

# 系统指标数据类
@dataclass
class SystemMetrics:
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    network_io: Dict[str, float]
    active_connections: int
    response_time_avg: float
    error_rate: float
    cache_hit_rate: float

# 性能监控服务
class SystemPerformanceMonitor:
    """系统性能监控服务"""
    
    def __init__(self):
        self.metrics_history: List[Dict[str, Any]] = []
        self.performance_thresholds = {
            "cpu_warning": 70.0,
            "cpu_critical": 85.0,
            "memory_warning": 75.0,
            "memory_critical": 90.0,
            "disk_warning": 80.0,
            "disk_critical": 95.0,
            "response_time_warning": 2000.0,  # ms
            "response_time_critical": 5000.0,  # ms
            "error_rate_warning": 5.0,  # %
            "error_rate_critical": 10.0  # %
        }
    
    async def collect_system_metrics(self) -> SystemMetrics:
        """收集系统指标"""
        
        # CPU使用率
        cpu_usage = psutil.cpu_percent(interval=1)
        
        # 内存使用率
        memory = psutil.virtual_memory()
        memory_usage = memory.percent
        
        # 磁盘使用率
        disk = psutil.disk_usage('/')
        disk_usage = (disk.used / disk.total) * 100
        
        # 网络IO
        network = psutil.net_io_counters()
        network_io = {
            "bytes_sent": network.bytes_sent,
            "bytes_recv": network.bytes_recv,
            "packets_sent": network.packets_sent,
            "packets_recv": network.packets_recv
        }
        
        # 活跃连接数（简化实现）
        active_connections = len(psutil.net_connections())
        
        # 应用级指标（从各服务获取）
        app_metrics = await self._collect_application_metrics()
        
        return SystemMetrics(
            cpu_usage=cpu_usage,
            memory_usage=memory_usage,
            disk_usage=disk_usage,
            network_io=network_io,
            active_connections=active_connections,
            response_time_avg=app_metrics.get("avg_response_time", 0.0),
            error_rate=app_metrics.get("error_rate", 0.0),
            cache_hit_rate=app_metrics.get("cache_hit_rate", 0.0)
        )
    
    async def _collect_application_metrics(self) -> Dict[str, float]:
        """收集应用级指标"""
        
        try:
            # 从各个增强版服务获取指标
            from ..services.enhanced_ai_defect_service import enhanced_ai_service
            from ..services.enhanced_audit_task_service import enhanced_audit_service
            
            ai_stats = enhanced_ai_service.get_cache_stats()
            audit_stats = enhanced_audit_service.get_enhanced_service_stats()
            
            # 计算综合指标
            total_requests = (
                ai_stats["performance_stats"]["total_requests"] +
                audit_stats["performance_stats"]["total_tasks_created"]
            )
            
            total_errors = (
                ai_stats["performance_stats"]["error_count"] +
                audit_stats["performance_stats"]["error_count"]
            )
            
            error_rate = (total_errors / max(total_requests, 1)) * 100
            
            avg_response_time = (
                ai_stats["performance_stats"]["average_response_time"] +
                audit_stats["performance_stats"]["average_creation_time"]
            ) / 2
            
            cache_hit_rate = ai_stats["cache_hit_rate"]
            
            return {
                "avg_response_time": avg_response_time,
                "error_rate": error_rate,
                "cache_hit_rate": cache_hit_rate
            }
            
        except Exception as e:
            logger.error(f"收集应用指标失败: {e}")
            return {
                "avg_response_time": 0.0,
                "error_rate": 0.0,
                "cache_hit_rate": 0.0
            }
    
    def analyze_performance_level(self, metrics: SystemMetrics) -> PerformanceLevel:
        """分析性能等级"""
        
        critical_count = 0
        warning_count = 0
        
        # 检查各项指标
        if metrics.cpu_usage >= self.performance_thresholds["cpu_critical"]:
            critical_count += 1
        elif metrics.cpu_usage >= self.performance_thresholds["cpu_warning"]:
            warning_count += 1
        
        if metrics.memory_usage >= self.performance_thresholds["memory_critical"]:
            critical_count += 1
        elif metrics.memory_usage >= self.performance_thresholds["memory_warning"]:
            warning_count += 1
        
        if metrics.disk_usage >= self.performance_thresholds["disk_critical"]:
            critical_count += 1
        elif metrics.disk_usage >= self.performance_thresholds["disk_warning"]:
            warning_count += 1
        
        if metrics.response_time_avg >= self.performance_thresholds["response_time_critical"]:
            critical_count += 1
        elif metrics.response_time_avg >= self.performance_thresholds["response_time_warning"]:
            warning_count += 1
        
        if metrics.error_rate >= self.performance_thresholds["error_rate_critical"]:
            critical_count += 1
        elif metrics.error_rate >= self.performance_thresholds["error_rate_warning"]:
            warning_count += 1
        
        # 确定性能等级
        if critical_count > 0:
            return PerformanceLevel.CRITICAL
        elif warning_count >= 3:
            return PerformanceLevel.POOR
        elif warning_count >= 2:
            return PerformanceLevel.FAIR
        elif warning_count >= 1:
            return PerformanceLevel.GOOD
        else:
            return PerformanceLevel.EXCELLENT
    
    def generate_optimization_recommendations(
        self, 
        metrics: SystemMetrics, 
        performance_level: PerformanceLevel
    ) -> List[Dict[str, Any]]:
        """生成优化建议"""
        
        recommendations = []
        
        # CPU优化建议
        if metrics.cpu_usage >= self.performance_thresholds["cpu_warning"]:
            recommendations.append({
                "category": "CPU优化",
                "priority": "high" if metrics.cpu_usage >= self.performance_thresholds["cpu_critical"] else "medium",
                "issue": f"CPU使用率过高: {metrics.cpu_usage:.1f}%",
                "recommendations": [
                    "考虑增加CPU核心数或升级CPU",
                    "优化高CPU消耗的算法和查询",
                    "启用更多的异步处理",
                    "考虑使用负载均衡分散CPU压力"
                ]
            })
        
        # 内存优化建议
        if metrics.memory_usage >= self.performance_thresholds["memory_warning"]:
            recommendations.append({
                "category": "内存优化",
                "priority": "high" if metrics.memory_usage >= self.performance_thresholds["memory_critical"] else "medium",
                "issue": f"内存使用率过高: {metrics.memory_usage:.1f}%",
                "recommendations": [
                    "增加系统内存",
                    "优化缓存策略，清理不必要的缓存",
                    "检查内存泄漏问题",
                    "调整数据库连接池大小"
                ]
            })
        
        # 磁盘优化建议
        if metrics.disk_usage >= self.performance_thresholds["disk_warning"]:
            recommendations.append({
                "category": "磁盘优化",
                "priority": "high" if metrics.disk_usage >= self.performance_thresholds["disk_critical"] else "medium",
                "issue": f"磁盘使用率过高: {metrics.disk_usage:.1f}%",
                "recommendations": [
                    "清理临时文件和日志文件",
                    "增加磁盘空间",
                    "实施数据归档策略",
                    "考虑使用SSD提升IO性能"
                ]
            })
        
        # 响应时间优化建议
        if metrics.response_time_avg >= self.performance_thresholds["response_time_warning"]:
            recommendations.append({
                "category": "响应时间优化",
                "priority": "high" if metrics.response_time_avg >= self.performance_thresholds["response_time_critical"] else "medium",
                "issue": f"平均响应时间过长: {metrics.response_time_avg:.1f}ms",
                "recommendations": [
                    "优化数据库查询和索引",
                    "增加缓存层",
                    "优化API端点性能",
                    "考虑使用CDN加速静态资源"
                ]
            })
        
        # 错误率优化建议
        if metrics.error_rate >= self.performance_thresholds["error_rate_warning"]:
            recommendations.append({
                "category": "错误率优化",
                "priority": "high" if metrics.error_rate >= self.performance_thresholds["error_rate_critical"] else "medium",
                "issue": f"错误率过高: {metrics.error_rate:.1f}%",
                "recommendations": [
                    "检查和修复应用程序错误",
                    "改进错误处理和重试机制",
                    "加强输入验证",
                    "监控和分析错误日志"
                ]
            })
        
        # 缓存优化建议
        if metrics.cache_hit_rate < 80.0:
            recommendations.append({
                "category": "缓存优化",
                "priority": "medium",
                "issue": f"缓存命中率较低: {metrics.cache_hit_rate:.1f}%",
                "recommendations": [
                    "优化缓存策略和TTL设置",
                    "增加缓存容量",
                    "实施更智能的缓存预热",
                    "考虑使用分布式缓存"
                ]
            })
        
        return recommendations

# 全局性能监控实例
performance_monitor = SystemPerformanceMonitor()

@router.get("/metrics", response_model=UnifiedAPIResponse[Dict[str, Any]])
@api_performance_monitor("系统指标收集")
async def get_system_metrics(
    current_user = Depends(get_current_user),
    _: None = Depends(require_permissions(["system_monitor"]))
):
    """获取系统性能指标"""
    try:
        metrics = await performance_monitor.collect_system_metrics()
        performance_level = performance_monitor.analyze_performance_level(metrics)
        
        return create_success_response(
            data={
                "system_metrics": {
                    "cpu_usage": metrics.cpu_usage,
                    "memory_usage": metrics.memory_usage,
                    "disk_usage": metrics.disk_usage,
                    "network_io": metrics.network_io,
                    "active_connections": metrics.active_connections
                },
                "application_metrics": {
                    "response_time_avg": metrics.response_time_avg,
                    "error_rate": metrics.error_rate,
                    "cache_hit_rate": metrics.cache_hit_rate
                },
                "performance_level": performance_level.value,
                "timestamp": datetime.utcnow().isoformat()
            },
            message="系统指标获取成功"
        )
        
    except Exception as e:
        logger.error(f"获取系统指标失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取系统指标失败: {str(e)}")

@router.get("/optimization-report", response_model=UnifiedAPIResponse[Dict[str, Any]])
@api_performance_monitor("系统优化报告")
async def get_optimization_report(
    current_user = Depends(get_current_user),
    _: None = Depends(require_permissions(["system_admin"]))
):
    """获取系统优化报告"""
    try:
        metrics = await performance_monitor.collect_system_metrics()
        performance_level = performance_monitor.analyze_performance_level(metrics)
        recommendations = performance_monitor.generate_optimization_recommendations(
            metrics, performance_level
        )
        
        return create_success_response(
            data={
                "performance_summary": {
                    "overall_level": performance_level.value,
                    "cpu_usage": metrics.cpu_usage,
                    "memory_usage": metrics.memory_usage,
                    "disk_usage": metrics.disk_usage,
                    "response_time_avg": metrics.response_time_avg,
                    "error_rate": metrics.error_rate,
                    "cache_hit_rate": metrics.cache_hit_rate
                },
                "optimization_recommendations": recommendations,
                "priority_actions": [
                    rec for rec in recommendations 
                    if rec["priority"] == "high"
                ],
                "report_generated_at": datetime.utcnow().isoformat()
            },
            message="系统优化报告生成成功"
        )
        
    except Exception as e:
        logger.error(f"生成优化报告失败: {e}")
        raise HTTPException(status_code=500, detail=f"生成优化报告失败: {str(e)}")

@router.get("/health-check", response_model=UnifiedAPIResponse[Dict[str, Any]])
async def comprehensive_health_check():
    """综合健康检查"""
    try:
        # 收集系统指标
        metrics = await performance_monitor.collect_system_metrics()
        performance_level = performance_monitor.analyze_performance_level(metrics)
        
        # 检查各个服务状态
        service_status = {}
        
        try:
            from ..services.enhanced_ai_defect_service import enhanced_ai_service
            ai_stats = enhanced_ai_service.get_cache_stats()
            service_status["ai_defect_service"] = "healthy"
        except Exception:
            service_status["ai_defect_service"] = "unhealthy"
        
        try:
            from ..services.enhanced_audit_task_service import enhanced_audit_service
            audit_stats = enhanced_audit_service.get_enhanced_service_stats()
            service_status["audit_task_service"] = "healthy"
        except Exception:
            service_status["audit_task_service"] = "unhealthy"
        
        # 确定整体健康状态
        overall_health = "healthy"
        if performance_level in [PerformanceLevel.CRITICAL, PerformanceLevel.POOR]:
            overall_health = "unhealthy"
        elif performance_level == PerformanceLevel.FAIR:
            overall_health = "degraded"
        
        unhealthy_services = [
            service for service, status in service_status.items() 
            if status != "healthy"
        ]
        
        if unhealthy_services:
            overall_health = "degraded" if overall_health == "healthy" else "unhealthy"
        
        return create_success_response(
            data={
                "overall_health": overall_health,
                "performance_level": performance_level.value,
                "system_metrics": {
                    "cpu_usage": metrics.cpu_usage,
                    "memory_usage": metrics.memory_usage,
                    "disk_usage": metrics.disk_usage,
                    "response_time_avg": metrics.response_time_avg,
                    "error_rate": metrics.error_rate
                },
                "service_status": service_status,
                "issues": [
                    f"性能等级: {performance_level.value}",
                    *[f"服务异常: {service}" for service in unhealthy_services]
                ],
                "timestamp": datetime.utcnow().isoformat()
            },
            message="综合健康检查完成"
        )
        
    except Exception as e:
        logger.error(f"综合健康检查失败: {e}")
        return create_success_response(
            data={
                "overall_health": "unknown",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            },
            message="健康检查部分失败"
        )
