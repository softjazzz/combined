# 增强版审核任务管理服务
# 完全替代TypeScript实现，集成现有三层质控引擎的审核任务管理功能

import asyncio
import uuid
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, or_, func
from sqlalchemy.orm import selectinload

from ..models.audit_models import (
    QCAuditTask, QCAuditTaskItem, CreateAuditTaskRequest,
    AuditScope, SamplingConfig, RiskLevel, AuditTaskFilter,
    BatchAuditRequest, BatchAuditResult
)
from ..database.models import (
    QCAuditTaskDB, QCAuditTaskItemDB, MedicalRecordDB, PatientDB, DepartmentDB
)

logger = logging.getLogger(__name__)

# 负载均衡策略枚举
class LoadBalancingStrategy(Enum):
    ROUND_ROBIN = "round_robin"
    WEIGHTED = "weighted"
    LEAST_LOADED = "least_loaded"
    SKILL_BASED = "skill_based"

# 任务优先级枚举
class TaskPriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4

# 增强版配置
@dataclass
class EnhancedTaskConfig:
    max_concurrent_tasks: int = 10
    batch_size: int = 100
    load_balancing_strategy: LoadBalancingStrategy = LoadBalancingStrategy.SKILL_BASED
    enable_smart_assignment: bool = True
    enable_performance_tracking: bool = True
    cache_ttl: int = 1800  # 30分钟

# 审核员工作负载信息
@dataclass
class ReviewerWorkload:
    reviewer_id: str
    current_tasks: int
    completed_tasks: int
    average_completion_time: float
    expertise_areas: List[str]
    performance_score: float

# 假设现有的三层质控引擎接口
class ThreeLayerQCEngineInterface:
    async def batch_analyze_records(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量分析医疗记录"""
        pass
    
    async def assess_risk_level(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """评估单个记录的风险等级"""
        pass

class EnhancedIntelligentSamplingService:
    """增强版智能抽样服务"""
    
    def __init__(self, qc_engine: ThreeLayerQCEngineInterface, config: EnhancedTaskConfig):
        self.qc_engine = qc_engine
        self.config = config
        self.thread_pool = ThreadPoolExecutor(max_workers=4)
        
        # 性能统计
        self.sampling_stats = {
            "total_samples": 0,
            "average_sampling_time": 0.0,
            "cache_hits": 0,
            "qc_analysis_time": 0.0
        }
    
    async def execute_enhanced_sampling(
        self,
        scope: AuditScope,
        config: SamplingConfig,
        db: AsyncSession
    ) -> List[QCAuditTaskItem]:
        """执行增强版智能抽样算法"""
        
        start_time = datetime.utcnow()
        logger.info(f"开始执行增强版智能抽样: {config.sampling_method}")
        
        try:
            # 1. 获取候选病历数据（优化查询）
            candidate_records = await self._get_candidate_records_optimized(scope, db)
            logger.info(f"获取到 {len(candidate_records)} 条候选病历")
            
            if not candidate_records:
                return []
            
            # 2. 批量风险评估（使用现有质控引擎）
            risk_assessed_records = await self._batch_assess_risk_levels(candidate_records)
            
            # 3. 执行优化的抽样算法
            sampled_records = await self._apply_enhanced_sampling_algorithm(
                risk_assessed_records, config
            )
            
            # 4. 更新性能统计
            sampling_time = (datetime.utcnow() - start_time).total_seconds()
            self._update_sampling_stats(len(sampled_records), sampling_time)
            
            logger.info(f"增强版抽样完成，选中 {len(sampled_records)} 条病历，耗时 {sampling_time:.2f}s")
            return sampled_records
            
        except Exception as e:
            logger.error(f"增强版智能抽样失败: {e}", exc_info=True)
            raise e
    
    async def _get_candidate_records_optimized(
        self, 
        scope: AuditScope, 
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """优化的候选记录获取"""
        
        # 构建优化的查询
        query = select(MedicalRecordDB).join(PatientDB).join(DepartmentDB)
        
        # 应用范围过滤
        conditions = []
        
        if scope.departments:
            conditions.append(DepartmentDB.id.in_(scope.departments))
        
        if scope.document_types:
            conditions.append(MedicalRecordDB.document_type.in_(scope.document_types))
        
        if scope.date_range:
            conditions.append(
                and_(
                    MedicalRecordDB.created_at >= scope.date_range.start_date,
                    MedicalRecordDB.created_at <= scope.date_range.end_date
                )
            )
        
        if scope.patient_types:
            conditions.append(PatientDB.patient_type.in_(scope.patient_types))
        
        if conditions:
            query = query.where(and_(*conditions))
        
        # 执行查询
        result = await db.execute(query.limit(10000))  # 限制最大候选数量
        records = result.scalars().all()
        
        # 转换为字典格式
        return [
            {
                "id": record.id,
                "patient_id": record.patient_id,
                "department_id": record.department_id,
                "document_type": record.document_type,
                "content": record.content,
                "created_at": record.created_at,
                "complexity_indicators": self._extract_complexity_indicators(record)
            }
            for record in records
        ]
    
    async def _batch_assess_risk_levels(
        self, 
        records: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """批量风险等级评估"""
        
        logger.info(f"开始批量风险评估: {len(records)} 条记录")
        
        try:
            # 使用现有质控引擎进行批量分析
            qc_results = await self.qc_engine.batch_analyze_records(records)
            
            # 合并风险评估结果
            assessed_records = []
            for i, record in enumerate(records):
                qc_result = qc_results[i] if i < len(qc_results) else {}
                
                # 计算综合风险等级
                risk_level = self._calculate_comprehensive_risk_level(record, qc_result)
                complexity_score = self._calculate_complexity_score(record, qc_result)
                
                assessed_records.append({
                    **record,
                    "risk_level": risk_level,
                    "complexity_score": complexity_score,
                    "qc_analysis": qc_result,
                    "priority_score": self._calculate_priority_score(risk_level, complexity_score)
                })
            
            logger.info("批量风险评估完成")
            return assessed_records
            
        except Exception as e:
            logger.error(f"批量风险评估失败: {e}")
            # 返回默认风险等级
            return [
                {
                    **record,
                    "risk_level": RiskLevel.B,
                    "complexity_score": 50,
                    "priority_score": 50
                }
                for record in records
            ]
    
    async def _apply_enhanced_sampling_algorithm(
        self,
        records: List[Dict[str, Any]],
        config: SamplingConfig
    ) -> List[QCAuditTaskItem]:
        """应用增强版抽样算法"""
        
        if config.sampling_method == "stratified":
            return await self._enhanced_stratified_sampling(records, config)
        elif config.sampling_method == "risk_based":
            return await self._enhanced_risk_based_sampling(records, config)
        elif config.sampling_method == "systematic":
            return await self._enhanced_systematic_sampling(records, config)
        elif config.sampling_method == "adaptive":
            return await self._adaptive_sampling(records, config)
        else:
            return await self._enhanced_random_sampling(records, config)
    
    async def _enhanced_stratified_sampling(
        self,
        records: List[Dict[str, Any]],
        config: SamplingConfig
    ) -> List[QCAuditTaskItem]:
        """增强版分层抽样"""
        
        sampled_records = []
        
        # 按风险等级和复杂度分层
        strata = {
            "A_high": [r for r in records if r["risk_level"] == RiskLevel.A and r["complexity_score"] >= 70],
            "A_low": [r for r in records if r["risk_level"] == RiskLevel.A and r["complexity_score"] < 70],
            "B_high": [r for r in records if r["risk_level"] == RiskLevel.B and r["complexity_score"] >= 70],
            "B_low": [r for r in records if r["risk_level"] == RiskLevel.B and r["complexity_score"] < 70],
            "C": [r for r in records if r["risk_level"] == RiskLevel.C]
        }
        
        # 智能分层抽样规则
        enhanced_rules = {
            "A_high": {"ratio": 0.8, "min_size": 5, "max_size": 100},
            "A_low": {"ratio": 0.6, "min_size": 3, "max_size": 50},
            "B_high": {"ratio": 0.4, "min_size": 2, "max_size": 30},
            "B_low": {"ratio": 0.2, "min_size": 1, "max_size": 20},
            "C": {"ratio": 0.1, "min_size": 1, "max_size": 10}
        }
        
        for stratum_name, stratum_records in strata.items():
            if not stratum_records:
                continue
            
            rule = enhanced_rules[stratum_name]
            sample_size = max(
                min(
                    int(len(stratum_records) * rule["ratio"]),
                    rule["max_size"]
                ),
                rule["min_size"]
            )
            
            if sample_size > 0:
                # 按优先级排序后抽样
                sorted_records = sorted(
                    stratum_records, 
                    key=lambda x: x["priority_score"], 
                    reverse=True
                )
                
                selected = sorted_records[:sample_size]
                sampled_records.extend([self._convert_to_task_item(record) for record in selected])
        
        return sampled_records
    
    async def _adaptive_sampling(
        self,
        records: List[Dict[str, Any]],
        config: SamplingConfig
    ) -> List[QCAuditTaskItem]:
        """自适应抽样算法"""
        
        # 根据历史数据动态调整抽样策略
        total_sample_size = config.total_sample_size or int(len(records) * 0.1)
        
        # 按优先级分组
        high_priority = [r for r in records if r["priority_score"] >= 80]
        medium_priority = [r for r in records if 50 <= r["priority_score"] < 80]
        low_priority = [r for r in records if r["priority_score"] < 50]
        
        # 自适应分配
        high_sample = min(len(high_priority), int(total_sample_size * 0.6))
        medium_sample = min(len(medium_priority), int(total_sample_size * 0.3))
        low_sample = min(len(low_priority), total_sample_size - high_sample - medium_sample)
        
        sampled_records = []
        
        # 高优先级：全部或按复杂度排序选择
        if high_priority:
            selected = sorted(high_priority, key=lambda x: x["complexity_score"], reverse=True)[:high_sample]
            sampled_records.extend(selected)
        
        # 中优先级：随机抽样
        if medium_priority and medium_sample > 0:
            selected = np.random.choice(len(medium_priority), size=medium_sample, replace=False)
            sampled_records.extend([medium_priority[i] for i in selected])
        
        # 低优先级：系统抽样
        if low_priority and low_sample > 0:
            step = len(low_priority) // low_sample
            selected = [low_priority[i * step] for i in range(low_sample)]
            sampled_records.extend(selected)
        
        return [self._convert_to_task_item(record) for record in sampled_records]
    
    def _extract_complexity_indicators(self, record) -> Dict[str, Any]:
        """提取复杂度指标"""
        return {
            "content_length": len(record.content or ""),
            "has_complications": "并发症" in (record.content or ""),
            "multiple_diagnoses": record.content.count("诊断") if record.content else 0,
            "surgical_procedures": record.content.count("手术") if record.content else 0
        }
    
    def _calculate_comprehensive_risk_level(
        self, 
        record: Dict[str, Any], 
        qc_result: Dict[str, Any]
    ) -> RiskLevel:
        """计算综合风险等级"""
        
        # 基于QC分析结果和记录特征计算风险等级
        qc_score = qc_result.get("overall_score", 80)
        complexity_indicators = record.get("complexity_indicators", {})
        
        risk_score = 0
        
        # QC分数权重
        if qc_score < 60:
            risk_score += 40
        elif qc_score < 80:
            risk_score += 20
        else:
            risk_score += 5
        
        # 复杂度指标权重
        if complexity_indicators.get("has_complications"):
            risk_score += 15
        
        if complexity_indicators.get("multiple_diagnoses", 0) > 2:
            risk_score += 10
        
        if complexity_indicators.get("surgical_procedures", 0) > 0:
            risk_score += 10
        
        # 确定风险等级
        if risk_score >= 60:
            return RiskLevel.A
        elif risk_score >= 30:
            return RiskLevel.B
        else:
            return RiskLevel.C
    
    def _calculate_complexity_score(
        self, 
        record: Dict[str, Any], 
        qc_result: Dict[str, Any]
    ) -> int:
        """计算复杂度分数"""
        
        base_score = 50
        complexity_indicators = record.get("complexity_indicators", {})
        
        # 内容长度
        content_length = complexity_indicators.get("content_length", 0)
        if content_length > 5000:
            base_score += 20
        elif content_length > 2000:
            base_score += 10
        
        # 其他复杂度因素
        base_score += complexity_indicators.get("multiple_diagnoses", 0) * 5
        base_score += complexity_indicators.get("surgical_procedures", 0) * 10
        
        if complexity_indicators.get("has_complications"):
            base_score += 15
        
        return min(base_score, 100)
    
    def _calculate_priority_score(self, risk_level: RiskLevel, complexity_score: int) -> int:
        """计算优先级分数"""
        
        risk_weights = {
            RiskLevel.A: 40,
            RiskLevel.B: 25,
            RiskLevel.C: 10
        }
        
        return risk_weights.get(risk_level, 10) + int(complexity_score * 0.6)
    
    def _convert_to_task_item(self, record: Dict[str, Any]) -> QCAuditTaskItem:
        """转换为任务项"""
        
        return QCAuditTaskItem(
            id=str(uuid.uuid4()),
            task_id="",  # 将在创建任务时设置
            patient_id=record["patient_id"],
            medical_record_id=record["id"],
            patient_name=f"患者{record['patient_id'][-4:]}",
            admission_date=record.get("created_at", datetime.utcnow()),
            department_id=record["department_id"],
            department_name="",  # 将从数据库获取
            risk_level=record["risk_level"].value,
            complexity_score=record["complexity_score"],
            audit_status="pending",
            defect_count=0,
            has_critical_defects=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
    
    def _update_sampling_stats(self, sample_count: int, sampling_time: float):
        """更新抽样统计"""
        self.sampling_stats["total_samples"] += sample_count
        self.sampling_stats["average_sampling_time"] = (
            (self.sampling_stats["average_sampling_time"] + sampling_time) / 2
        )
    
    def get_sampling_stats(self) -> Dict[str, Any]:
        """获取抽样统计"""
        return self.sampling_stats.copy()

class EnhancedLoadBalancer:
    """增强版负载均衡器"""

    def __init__(self, config: EnhancedTaskConfig):
        self.config = config
        self.reviewer_workloads: Dict[str, ReviewerWorkload] = {}
        self.assignment_history: List[Dict[str, Any]] = []

    async def assign_tasks_intelligently(
        self,
        task_items: List[QCAuditTaskItem],
        available_reviewers: List[str],
        db: AsyncSession
    ) -> Dict[str, List[str]]:
        """智能任务分配"""

        logger.info(f"开始智能任务分配: {len(task_items)} 个任务项, {len(available_reviewers)} 个审核员")

        # 1. 获取审核员工作负载信息
        reviewer_workloads = await self._get_reviewer_workloads(available_reviewers, db)

        # 2. 根据策略分配任务
        if self.config.load_balancing_strategy == LoadBalancingStrategy.SKILL_BASED:
            assignments = await self._skill_based_assignment(task_items, reviewer_workloads, db)
        elif self.config.load_balancing_strategy == LoadBalancingStrategy.LEAST_LOADED:
            assignments = await self._least_loaded_assignment(task_items, reviewer_workloads)
        elif self.config.load_balancing_strategy == LoadBalancingStrategy.WEIGHTED:
            assignments = await self._weighted_assignment(task_items, reviewer_workloads)
        else:
            assignments = await self._round_robin_assignment(task_items, available_reviewers)

        # 3. 记录分配历史
        self._record_assignment_history(assignments, task_items)

        logger.info(f"智能任务分配完成: {len(assignments)} 个审核员获得任务")
        return assignments

    async def _get_reviewer_workloads(
        self,
        reviewer_ids: List[str],
        db: AsyncSession
    ) -> Dict[str, ReviewerWorkload]:
        """获取审核员工作负载信息"""

        workloads = {}

        for reviewer_id in reviewer_ids:
            # 查询当前任务数
            current_tasks_result = await db.execute(
                select(func.count(QCAuditTaskItemDB.id))
                .where(
                    and_(
                        QCAuditTaskItemDB.assigned_reviewer_id == reviewer_id,
                        QCAuditTaskItemDB.audit_status.in_(["pending", "in_progress"])
                    )
                )
            )
            current_tasks = current_tasks_result.scalar() or 0

            # 查询已完成任务数和平均完成时间
            completed_tasks_result = await db.execute(
                select(
                    func.count(QCAuditTaskItemDB.id),
                    func.avg(
                        func.extract('epoch', QCAuditTaskItemDB.completed_at - QCAuditTaskItemDB.assigned_at)
                    )
                )
                .where(
                    and_(
                        QCAuditTaskItemDB.assigned_reviewer_id == reviewer_id,
                        QCAuditTaskItemDB.audit_status == "completed",
                        QCAuditTaskItemDB.completed_at.isnot(None)
                    )
                )
            )
            completed_result = completed_tasks_result.first()
            completed_tasks = completed_result[0] or 0
            avg_completion_time = completed_result[1] or 3600  # 默认1小时

            # 计算性能分数
            performance_score = self._calculate_performance_score(
                completed_tasks, avg_completion_time, current_tasks
            )

            workloads[reviewer_id] = ReviewerWorkload(
                reviewer_id=reviewer_id,
                current_tasks=current_tasks,
                completed_tasks=completed_tasks,
                average_completion_time=avg_completion_time,
                expertise_areas=await self._get_reviewer_expertise(reviewer_id, db),
                performance_score=performance_score
            )

        return workloads

    async def _skill_based_assignment(
        self,
        task_items: List[QCAuditTaskItem],
        reviewer_workloads: Dict[str, ReviewerWorkload],
        db: AsyncSession
    ) -> Dict[str, List[str]]:
        """基于技能的任务分配"""

        assignments = {reviewer_id: [] for reviewer_id in reviewer_workloads.keys()}

        # 按任务复杂度和风险等级排序
        sorted_items = sorted(
            task_items,
            key=lambda x: (x.risk_level == "A", x.complexity_score),
            reverse=True
        )

        for item in sorted_items:
            # 找到最适合的审核员
            best_reviewer = self._find_best_reviewer_for_task(item, reviewer_workloads)

            if best_reviewer:
                assignments[best_reviewer].append(item.id)
                # 更新工作负载
                reviewer_workloads[best_reviewer].current_tasks += 1

        return assignments

    async def _least_loaded_assignment(
        self,
        task_items: List[QCAuditTaskItem],
        reviewer_workloads: Dict[str, ReviewerWorkload]
    ) -> Dict[str, List[str]]:
        """最少负载分配"""

        assignments = {reviewer_id: [] for reviewer_id in reviewer_workloads.keys()}

        for item in task_items:
            # 找到当前任务最少的审核员
            least_loaded_reviewer = min(
                reviewer_workloads.keys(),
                key=lambda r: reviewer_workloads[r].current_tasks
            )

            assignments[least_loaded_reviewer].append(item.id)
            reviewer_workloads[least_loaded_reviewer].current_tasks += 1

        return assignments

    async def _weighted_assignment(
        self,
        task_items: List[QCAuditTaskItem],
        reviewer_workloads: Dict[str, ReviewerWorkload]
    ) -> Dict[str, List[str]]:
        """加权分配"""

        assignments = {reviewer_id: [] for reviewer_id in reviewer_workloads.keys()}

        # 计算权重
        total_performance = sum(workload.performance_score for workload in reviewer_workloads.values())

        for item in task_items:
            # 根据性能分数和当前负载选择审核员
            best_reviewer = max(
                reviewer_workloads.keys(),
                key=lambda r: (
                    reviewer_workloads[r].performance_score / max(reviewer_workloads[r].current_tasks, 1)
                )
            )

            assignments[best_reviewer].append(item.id)
            reviewer_workloads[best_reviewer].current_tasks += 1

        return assignments

    async def _round_robin_assignment(
        self,
        task_items: List[QCAuditTaskItem],
        reviewer_ids: List[str]
    ) -> Dict[str, List[str]]:
        """轮询分配"""

        assignments = {reviewer_id: [] for reviewer_id in reviewer_ids}

        for i, item in enumerate(task_items):
            reviewer_id = reviewer_ids[i % len(reviewer_ids)]
            assignments[reviewer_id].append(item.id)

        return assignments

    def _find_best_reviewer_for_task(
        self,
        task_item: QCAuditTaskItem,
        reviewer_workloads: Dict[str, ReviewerWorkload]
    ) -> Optional[str]:
        """为任务找到最佳审核员"""

        # 计算每个审核员的适合度分数
        scores = {}

        for reviewer_id, workload in reviewer_workloads.items():
            score = 0

            # 性能分数权重
            score += workload.performance_score * 0.4

            # 负载权重（负载越低分数越高）
            load_factor = 1.0 / max(workload.current_tasks + 1, 1)
            score += load_factor * 100 * 0.3

            # 专业匹配权重
            expertise_match = self._calculate_expertise_match(task_item, workload.expertise_areas)
            score += expertise_match * 0.3

            scores[reviewer_id] = score

        # 返回分数最高的审核员
        return max(scores.keys(), key=lambda r: scores[r]) if scores else None

    def _calculate_expertise_match(
        self,
        task_item: QCAuditTaskItem,
        expertise_areas: List[str]
    ) -> float:
        """计算专业匹配度"""

        # 基于科室和风险等级计算匹配度
        match_score = 50.0  # 基础分数

        # 科室匹配
        if task_item.department_name in expertise_areas:
            match_score += 30.0

        # 风险等级匹配
        if task_item.risk_level == "A" and "高风险审核" in expertise_areas:
            match_score += 20.0
        elif task_item.risk_level == "B" and "常规审核" in expertise_areas:
            match_score += 10.0

        return min(match_score, 100.0)

    async def _get_reviewer_expertise(
        self,
        reviewer_id: str,
        db: AsyncSession
    ) -> List[str]:
        """获取审核员专业领域"""

        # 这里应该从用户表或专业配置表获取
        # 简化实现，返回默认专业领域
        return ["内科", "外科", "常规审核"]

    def _calculate_performance_score(
        self,
        completed_tasks: int,
        avg_completion_time: float,
        current_tasks: int
    ) -> float:
        """计算性能分数"""

        base_score = 50.0

        # 完成任务数量加分
        base_score += min(completed_tasks * 2, 30)

        # 平均完成时间加分（时间越短分数越高）
        if avg_completion_time < 1800:  # 30分钟
            base_score += 20
        elif avg_completion_time < 3600:  # 1小时
            base_score += 10

        # 当前负载扣分
        base_score -= min(current_tasks * 5, 20)

        return max(min(base_score, 100.0), 0.0)

    def _record_assignment_history(
        self,
        assignments: Dict[str, List[str]],
        task_items: List[QCAuditTaskItem]
    ):
        """记录分配历史"""

        assignment_record = {
            "timestamp": datetime.utcnow(),
            "strategy": self.config.load_balancing_strategy.value,
            "total_tasks": len(task_items),
            "assignments": {
                reviewer_id: len(item_ids)
                for reviewer_id, item_ids in assignments.items()
            }
        }

        self.assignment_history.append(assignment_record)

        # 保持历史记录在合理范围内
        if len(self.assignment_history) > 100:
            self.assignment_history = self.assignment_history[-50:]

    def get_assignment_stats(self) -> Dict[str, Any]:
        """获取分配统计"""

        if not self.assignment_history:
            return {"total_assignments": 0, "average_tasks_per_reviewer": 0}

        recent_assignments = self.assignment_history[-10:]  # 最近10次分配

        total_tasks = sum(record["total_tasks"] for record in recent_assignments)
        total_reviewers = sum(
            len(record["assignments"]) for record in recent_assignments
        )

        return {
            "total_assignments": len(self.assignment_history),
            "recent_total_tasks": total_tasks,
            "average_tasks_per_reviewer": total_tasks / max(total_reviewers, 1),
            "current_strategy": self.config.load_balancing_strategy.value
        }

class EnhancedAuditTaskService:
    """增强版审核任务管理服务 - 完全替代TypeScript实现"""

    def __init__(self, qc_engine: ThreeLayerQCEngineInterface, config: EnhancedTaskConfig = None):
        self.qc_engine = qc_engine
        self.config = config or EnhancedTaskConfig()
        self.sampling_service = EnhancedIntelligentSamplingService(qc_engine, self.config)
        self.load_balancer = EnhancedLoadBalancer(self.config)

        # 性能统计
        self.performance_stats = {
            "total_tasks_created": 0,
            "average_creation_time": 0.0,
            "total_items_processed": 0,
            "cache_hits": 0,
            "error_count": 0
        }

        logger.info("增强版审核任务服务初始化完成")

    async def create_enhanced_audit_task(
        self,
        request: CreateAuditTaskRequest,
        created_by: str,
        db: AsyncSession
    ) -> QCAuditTask:
        """创建增强版审核任务"""

        start_time = datetime.utcnow()
        logger.info(f"创建增强版审核任务: {request.task_name}")

        try:
            # 1. 验证请求参数
            self._validate_task_request(request)

            # 2. 生成任务代码
            task_code = self._generate_enhanced_task_code(request.task_type, request.audit_level)

            # 3. 创建任务记录
            task_data = QCAuditTaskDB(
                id=str(uuid.uuid4()),
                task_code=task_code,
                task_name=request.task_name,
                task_type=request.task_type,
                audit_level=request.audit_level,
                audit_scope=request.audit_scope.dict(),
                sampling_config=request.sampling_config.dict(),
                planned_start_date=request.planned_start_date,
                planned_end_date=request.planned_end_date,
                description=request.description,
                priority=request.priority,
                status="pending",
                created_by=created_by,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )

            db.add(task_data)
            await db.flush()  # 获取ID

            # 4. 执行增强版智能抽样
            task_items = await self.sampling_service.execute_enhanced_sampling(
                request.audit_scope,
                request.sampling_config,
                db
            )

            # 5. 创建任务明细
            await self._create_enhanced_task_items(task_data.id, task_items, db)

            # 6. 智能分配审核员
            if request.assigned_reviewers:
                await self._assign_reviewers_intelligently(
                    task_data.id, request.assigned_reviewers, db
                )

            # 7. 更新任务统计
            await self._update_enhanced_task_statistics(task_data.id, db)

            await db.commit()

            # 8. 更新性能统计
            creation_time = (datetime.utcnow() - start_time).total_seconds()
            self._update_performance_stats(len(task_items), creation_time)

            logger.info(f"增强版审核任务创建完成: {task_code}, 耗时: {creation_time:.2f}s")

            # 转换为响应模型
            return await self._convert_to_response_model(task_data, db)

        except Exception as e:
            await db.rollback()
            self.performance_stats["error_count"] += 1
            logger.error(f"创建增强版审核任务失败: {e}", exc_info=True)
            raise e

    async def get_enhanced_audit_tasks(
        self,
        filter_params: AuditTaskFilter,
        page: int = 1,
        page_size: int = 20,
        db: AsyncSession
    ) -> Tuple[List[QCAuditTask], int]:
        """获取增强版审核任务列表"""

        try:
            # 构建查询
            query = select(QCAuditTaskDB)

            # 应用过滤条件
            conditions = []

            if filter_params.task_type:
                conditions.append(QCAuditTaskDB.task_type == filter_params.task_type)

            if filter_params.audit_level:
                conditions.append(QCAuditTaskDB.audit_level == filter_params.audit_level)

            if filter_params.status:
                conditions.append(QCAuditTaskDB.status == filter_params.status)

            if filter_params.created_by:
                conditions.append(QCAuditTaskDB.created_by == filter_params.created_by)

            if filter_params.date_range:
                conditions.append(
                    and_(
                        QCAuditTaskDB.created_at >= filter_params.date_range.start_date,
                        QCAuditTaskDB.created_at <= filter_params.date_range.end_date
                    )
                )

            if filter_params.search:
                conditions.append(
                    or_(
                        QCAuditTaskDB.task_name.contains(filter_params.search),
                        QCAuditTaskDB.task_code.contains(filter_params.search),
                        QCAuditTaskDB.description.contains(filter_params.search)
                    )
                )

            if conditions:
                query = query.where(and_(*conditions))

            # 计算总数
            count_result = await db.execute(
                select(func.count(QCAuditTaskDB.id)).select_from(query.subquery())
            )
            total = count_result.scalar() or 0

            # 分页查询
            offset = (page - 1) * page_size
            result = await db.execute(
                query.order_by(QCAuditTaskDB.created_at.desc())
                .offset(offset)
                .limit(page_size)
            )

            tasks = []
            for task_data in result.scalars().all():
                task = await self._convert_to_response_model(task_data, db)
                tasks.append(task)

            return tasks, total

        except Exception as e:
            logger.error(f"获取增强版审核任务列表失败: {e}")
            raise e

    async def start_enhanced_audit_task(
        self,
        task_id: str,
        started_by: str,
        db: AsyncSession
    ) -> QCAuditTask:
        """启动增强版审核任务"""

        try:
            # 更新任务状态
            await db.execute(
                update(QCAuditTaskDB)
                .where(QCAuditTaskDB.id == task_id)
                .values(
                    status="in_progress",
                    actual_start_date=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    updated_by=started_by
                )
            )

            # 更新任务项状态
            await db.execute(
                update(QCAuditTaskItemDB)
                .where(QCAuditTaskItemDB.task_id == task_id)
                .values(
                    audit_status="ready",
                    updated_at=datetime.utcnow()
                )
            )

            await db.commit()

            # 获取更新后的任务
            result = await db.execute(
                select(QCAuditTaskDB).where(QCAuditTaskDB.id == task_id)
            )
            task_data = result.scalar_one()

            logger.info(f"增强版审核任务已启动: {task_data.task_code}")
            return await self._convert_to_response_model(task_data, db)

        except Exception as e:
            await db.rollback()
            logger.error(f"启动增强版审核任务失败: {e}")
            raise e

    def _validate_task_request(self, request: CreateAuditTaskRequest):
        """验证任务请求参数"""

        if not request.task_name or not request.task_name.strip():
            raise ValueError("任务名称不能为空")

        if not request.audit_scope.departments:
            raise ValueError("必须选择至少一个科室")

        if not request.audit_scope.document_types:
            raise ValueError("必须选择至少一种文书类型")

        if request.planned_end_date <= request.planned_start_date:
            raise ValueError("计划结束日期必须晚于开始日期")

        if not request.assigned_reviewers:
            raise ValueError("必须分配至少一个审核员")

    def _generate_enhanced_task_code(self, task_type: str, audit_level: str) -> str:
        """生成增强版任务代码"""

        prefix = f"ENH_{task_type.upper()}_{audit_level.upper()}"
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        random_suffix = str(uuid.uuid4())[:8].upper()

        return f"{prefix}_{timestamp}_{random_suffix}"

    async def _create_enhanced_task_items(
        self,
        task_id: str,
        items: List[QCAuditTaskItem],
        db: AsyncSession
    ) -> None:
        """创建增强版任务明细"""

        task_item_records = []
        for item in items:
            item.task_id = task_id
            task_item_records.append(QCAuditTaskItemDB(**item.dict()))

        db.add_all(task_item_records)
        logger.info(f"创建了 {len(task_item_records)} 个任务明细项")

    async def _assign_reviewers_intelligently(
        self,
        task_id: str,
        reviewer_ids: List[str],
        db: AsyncSession
    ) -> None:
        """智能分配审核员"""

        # 获取任务明细
        result = await db.execute(
            select(QCAuditTaskItemDB).where(QCAuditTaskItemDB.task_id == task_id)
        )
        task_items = result.scalars().all()

        # 转换为QCAuditTaskItem对象
        task_item_objects = [
            QCAuditTaskItem(**item.__dict__) for item in task_items
        ]

        # 使用负载均衡器进行智能分配
        assignments = await self.load_balancer.assign_tasks_intelligently(
            task_item_objects, reviewer_ids, db
        )

        # 批量更新分配
        for reviewer_id, item_ids in assignments.items():
            if item_ids:
                await db.execute(
                    update(QCAuditTaskItemDB)
                    .where(QCAuditTaskItemDB.id.in_(item_ids))
                    .values(
                        assigned_reviewer_id=reviewer_id,
                        assigned_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                )

        logger.info(f"智能分配完成: {len(assignments)} 个审核员获得任务")

    async def _update_enhanced_task_statistics(self, task_id: str, db: AsyncSession) -> None:
        """更新增强版任务统计信息"""

        # 统计任务项数量和分布
        stats_result = await db.execute(
            select(
                func.count(QCAuditTaskItemDB.id).label("total_records"),
                func.count(
                    func.case([(QCAuditTaskItemDB.risk_level == "A", 1)])
                ).label("high_risk_count"),
                func.count(
                    func.case([(QCAuditTaskItemDB.risk_level == "B", 1)])
                ).label("medium_risk_count"),
                func.count(
                    func.case([(QCAuditTaskItemDB.risk_level == "C", 1)])
                ).label("low_risk_count"),
                func.avg(QCAuditTaskItemDB.complexity_score).label("avg_complexity")
            )
            .where(QCAuditTaskItemDB.task_id == task_id)
        )

        stats = stats_result.first()

        # 更新任务记录
        await db.execute(
            update(QCAuditTaskDB)
            .where(QCAuditTaskDB.id == task_id)
            .values(
                total_records=stats.total_records or 0,
                high_risk_count=stats.high_risk_count or 0,
                medium_risk_count=stats.medium_risk_count or 0,
                low_risk_count=stats.low_risk_count or 0,
                average_complexity=float(stats.avg_complexity or 0),
                updated_at=datetime.utcnow()
            )
        )

    async def _convert_to_response_model(
        self,
        task_data: QCAuditTaskDB,
        db: AsyncSession
    ) -> QCAuditTask:
        """转换为响应模型"""

        # 查询分配的审核员信息
        assigned_reviewers = await self._get_assigned_reviewers(task_data.id, db)

        # 计算进度百分比
        progress_result = await db.execute(
            select(
                func.count(QCAuditTaskItemDB.id).label("total"),
                func.count(
                    func.case([(QCAuditTaskItemDB.audit_status == "completed", 1)])
                ).label("completed")
            )
            .where(QCAuditTaskItemDB.task_id == task_data.id)
        )

        progress = progress_result.first()
        total_records = progress.total or 0
        completed_records = progress.completed or 0
        progress_percentage = (completed_records / max(total_records, 1)) * 100

        return QCAuditTask(
            id=task_data.id,
            task_code=task_data.task_code,
            task_name=task_data.task_name,
            task_type=task_data.task_type,
            audit_level=task_data.audit_level,
            audit_scope=AuditScope(**task_data.audit_scope),
            sampling_config=SamplingConfig(**task_data.sampling_config),
            status=task_data.status,
            progress_percentage=progress_percentage,
            planned_start_date=task_data.planned_start_date,
            planned_end_date=task_data.planned_end_date,
            actual_start_date=task_data.actual_start_date,
            actual_end_date=task_data.actual_end_date,
            created_by=task_data.created_by,
            assigned_reviewers=assigned_reviewers,
            total_records=total_records,
            completed_records=completed_records,
            defect_rate=task_data.defect_rate,
            description=task_data.description,
            priority=task_data.priority,
            created_at=task_data.created_at,
            updated_at=task_data.updated_at
        )

    async def _get_assigned_reviewers(self, task_id: str, db: AsyncSession) -> List[Dict[str, Any]]:
        """获取分配的审核员信息"""

        result = await db.execute(
            select(
                QCAuditTaskItemDB.assigned_reviewer_id,
                func.count(QCAuditTaskItemDB.id).label("assigned_count"),
                func.count(
                    func.case([(QCAuditTaskItemDB.audit_status == "completed", 1)])
                ).label("completed_count")
            )
            .where(
                and_(
                    QCAuditTaskItemDB.task_id == task_id,
                    QCAuditTaskItemDB.assigned_reviewer_id.isnot(None)
                )
            )
            .group_by(QCAuditTaskItemDB.assigned_reviewer_id)
        )

        reviewers = []
        for row in result:
            reviewers.append({
                "user_id": row.assigned_reviewer_id,
                "user_name": f"审核员{row.assigned_reviewer_id[-4:]}",  # 简化实现
                "role": "qc_reviewer",
                "assigned_count": row.assigned_count,
                "completed_count": row.completed_count,
                "assigned_at": datetime.utcnow().isoformat()
            })

        return reviewers

    def _update_performance_stats(self, items_count: int, creation_time: float):
        """更新性能统计"""

        self.performance_stats["total_tasks_created"] += 1
        self.performance_stats["total_items_processed"] += items_count

        # 更新平均创建时间
        current_avg = self.performance_stats["average_creation_time"]
        total_tasks = self.performance_stats["total_tasks_created"]

        self.performance_stats["average_creation_time"] = (
            (current_avg * (total_tasks - 1) + creation_time) / total_tasks
        )

    def get_enhanced_service_stats(self) -> Dict[str, Any]:
        """获取增强版服务统计"""

        return {
            "performance_stats": self.performance_stats,
            "sampling_stats": self.sampling_service.get_sampling_stats(),
            "load_balancer_stats": self.load_balancer.get_assignment_stats(),
            "config": {
                "max_concurrent_tasks": self.config.max_concurrent_tasks,
                "batch_size": self.config.batch_size,
                "load_balancing_strategy": self.config.load_balancing_strategy.value,
                "enable_smart_assignment": self.config.enable_smart_assignment
            }
        }
