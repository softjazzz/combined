# 审核任务管理服务
# 集成现有三层质控引擎的审核任务管理功能

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, or_
from sqlalchemy.orm import selectinload

from ..models.audit_models import (
    QCAuditTask, QCAuditTaskItem, CreateAuditTaskRequest,
    AuditScope, SamplingConfig, RiskLevel, AuditTaskFilter,
    BatchAuditRequest, BatchAuditResult
)
from ..database.models import (
    QCAuditTaskDB, QCAuditTaskItemDB, MedicalRecordDB, PatientDB, DepartmentDB
)

# 假设现有的三层质控引擎接口
class ThreeLayerQCEngineInterface:
    """现有三层质控引擎的接口抽象"""
    
    async def analyze_medical_record(
        self, 
        patient_id: str, 
        record_data: Dict[str, Any],
        analysis_level: str = "comprehensive"
    ) -> Dict[str, Any]:
        """分析医疗记录，返回质控结果"""
        pass
    
    async def batch_analyze_records(
        self,
        records: List[Dict[str, Any]],
        analysis_config: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """批量分析医疗记录"""
        pass
    
    async def calculate_risk_score(
        self,
        qc_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """基于质控结果计算风险评分"""
        pass

class IntelligentSamplingService:
    """智能抽样服务，集成现有质控引擎"""
    
    def __init__(self, qc_engine: ThreeLayerQCEngineInterface):
        self.qc_engine = qc_engine
    
    async def execute_sampling(
        self,
        scope: AuditScope,
        config: SamplingConfig,
        db: AsyncSession
    ) -> List[QCAuditTaskItem]:
        """执行智能抽样算法"""
        
        print(f"开始执行智能抽样: {config.sampling_method}")
        
        # 1. 获取候选病历数据
        candidate_records = await self._get_candidate_records(scope, db)
        print(f"获取到 {len(candidate_records)} 条候选病历")
        
        # 2. 使用现有质控引擎进行风险评估
        risk_assessed_records = await self._assess_risk_levels(candidate_records)
        
        # 3. 执行抽样算法
        sampled_records = await self._apply_sampling_algorithm(
            risk_assessed_records, config
        )
        
        print(f"抽样完成，选中 {len(sampled_records)} 条病历")
        return sampled_records
    
    async def _get_candidate_records(
        self, 
        scope: AuditScope, 
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """获取候选病历记录"""
        
        # 构建查询条件
        query = select(MedicalRecordDB).join(PatientDB).join(DepartmentDB)
        
        # 应用科室范围过滤
        if scope.departments:
            query = query.where(MedicalRecordDB.department_id.in_(scope.departments))
        
        # 应用文书类型过滤
        if scope.document_types:
            query = query.where(MedicalRecordDB.document_type.in_(scope.document_types))
        
        # 应用时间范围过滤
        if scope.date_range:
            start_date = datetime.fromisoformat(scope.date_range['start'])
            end_date = datetime.fromisoformat(scope.date_range['end'])
            query = query.where(
                and_(
                    MedicalRecordDB.created_at >= start_date,
                    MedicalRecordDB.created_at <= end_date
                )
            )
        
        # 是否包含已出院患者
        if not scope.include_discharged:
            query = query.where(PatientDB.discharge_date.is_(None))
        
        result = await db.execute(query.limit(10000))  # 限制最大候选数量
        records = result.scalars().all()
        
        # 转换为字典格式
        candidate_records = []
        for record in records:
            candidate_records.append({
                'id': record.id,
                'patient_id': record.patient_id,
                'medical_record_id': record.id,
                'patient_name': record.patient.name if record.patient else '',
                'admission_date': record.patient.admission_date if record.patient else None,
                'discharge_date': record.patient.discharge_date if record.patient else None,
                'department_id': record.department_id,
                'department_name': record.department.name if record.department else '',
                'document_type': record.document_type,
                'created_at': record.created_at,
                'record_data': record.content  # 病历内容
            })
        
        return candidate_records
    
    async def _assess_risk_levels(
        self, 
        records: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """使用现有质控引擎进行风险评估"""
        
        assessed_records = []
        
        # 批量处理以提高效率
        batch_size = 50
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            
            try:
                # 使用现有质控引擎批量分析
                batch_records_data = [
                    {
                        'patient_id': record['patient_id'],
                        'record_data': record['record_data'],
                        'department_id': record['department_id']
                    }
                    for record in batch
                ]
                
                qc_results = await self.qc_engine.batch_analyze_records(
                    batch_records_data,
                    {'analysis_level': 'risk_assessment'}
                )
                
                # 处理批量结果
                for record, qc_result in zip(batch, qc_results):
                    risk_level = self._calculate_risk_level(qc_result)
                    complexity_score = self._calculate_complexity_score(record, qc_result)
                    
                    assessed_records.append({
                        **record,
                        'risk_level': risk_level,
                        'complexity_score': complexity_score,
                        'qc_analysis_result': qc_result
                    })
                
            except Exception as e:
                print(f"风险评估批次失败: {e}")
                # 使用默认风险等级
                for record in batch:
                    assessed_records.append({
                        **record,
                        'risk_level': RiskLevel.B,
                        'complexity_score': 50,
                        'qc_analysis_result': None
                    })
        
        return assessed_records
    
    def _calculate_risk_level(self, qc_result: Dict[str, Any]) -> RiskLevel:
        """基于质控结果计算风险等级"""
        if not qc_result:
            return RiskLevel.B
        
        overall_score = qc_result.get('overall_score', 80)
        risk_indicators = qc_result.get('risk_indicators', [])
        
        # 基于评分和风险指标确定风险等级
        if overall_score < 60 or any(indicator.get('severity') == 'critical' for indicator in risk_indicators):
            return RiskLevel.A  # 高风险
        elif overall_score < 80 or any(indicator.get('severity') == 'major' for indicator in risk_indicators):
            return RiskLevel.B  # 中风险
        else:
            return RiskLevel.C  # 低风险
    
    def _calculate_complexity_score(
        self, 
        record: Dict[str, Any], 
        qc_result: Dict[str, Any]
    ) -> int:
        """计算复杂度评分"""
        score = 0
        
        # 基于住院天数
        if record.get('admission_date') and record.get('discharge_date'):
            admission_date = record['admission_date']
            discharge_date = record['discharge_date']
            if isinstance(admission_date, str):
                admission_date = datetime.fromisoformat(admission_date)
            if isinstance(discharge_date, str):
                discharge_date = datetime.fromisoformat(discharge_date)
            
            stay_days = (discharge_date - admission_date).days
            score += min(stay_days * 2, 30)
        
        # 基于质控发现的问题数量
        if qc_result:
            issue_count = len(qc_result.get('findings', []))
            score += min(issue_count * 5, 30)
        
        # 基于科室复杂度
        department_complexity = self._get_department_complexity(
            record.get('department_name', '')
        )
        score += department_complexity
        
        return min(score, 100)
    
    def _get_department_complexity(self, department_name: str) -> int:
        """获取科室复杂度评分"""
        complexity_map = {
            'ICU': 20, '重症医学科': 20,
            '急诊科': 18, '急诊': 18,
            '心外科': 16, '神经外科': 16,
            '肿瘤科': 14, '肿瘤': 14,
            '内科': 10, '外科': 12,
            '妇产科': 10, '儿科': 12
        }
        
        for dept_key, complexity in complexity_map.items():
            if dept_key in department_name:
                return complexity
        
        return 8  # 默认复杂度
    
    async def _apply_sampling_algorithm(
        self,
        records: List[Dict[str, Any]],
        config: SamplingConfig
    ) -> List[QCAuditTaskItem]:
        """应用抽样算法"""
        
        if config.sampling_method == SamplingMethod.STRATIFIED:
            return await self._stratified_sampling(records, config)
        elif config.sampling_method == SamplingMethod.RISK_BASED:
            return await self._risk_based_sampling(records, config)
        elif config.sampling_method == SamplingMethod.SYSTEMATIC:
            return await self._systematic_sampling(records, config)
        else:
            return await self._random_sampling(records, config)
    
    async def _stratified_sampling(
        self,
        records: List[Dict[str, Any]],
        config: SamplingConfig
    ) -> List[QCAuditTaskItem]:
        """分层抽样"""
        
        sampled_records = []
        
        # 按风险等级分层
        strata = {
            RiskLevel.A: [r for r in records if r['risk_level'] == RiskLevel.A],
            RiskLevel.B: [r for r in records if r['risk_level'] == RiskLevel.B],
            RiskLevel.C: [r for r in records if r['risk_level'] == RiskLevel.C]
        }
        
        # 应用分层抽样规则
        if config.stratification_rules:
            for rule in config.stratification_rules:
                stratum_name = rule.stratum_name
                if stratum_name in ['A', 'B', 'C']:
                    stratum_records = strata.get(RiskLevel(stratum_name), [])
                    
                    sample_size = max(
                        min(
                            int(len(stratum_records) * rule.sample_ratio),
                            rule.max_sample_size or len(stratum_records)
                        ),
                        rule.min_sample_size or 1
                    )
                    
                    if sample_size > 0 and stratum_records:
                        stratum_sample = np.random.choice(
                            len(stratum_records),
                            size=min(sample_size, len(stratum_records)),
                            replace=False
                        )
                        
                        for idx in stratum_sample:
                            sampled_records.append(stratum_records[idx])
        
        return [self._convert_to_task_item(record) for record in sampled_records]
    
    async def _risk_based_sampling(
        self,
        records: List[Dict[str, Any]],
        config: SamplingConfig
    ) -> List[QCAuditTaskItem]:
        """基于风险的抽样"""
        
        weights = config.risk_based_weights or {
            'risk_A_weight': 0.6,
            'risk_B_weight': 0.3,
            'risk_C_weight': 0.1
        }
        
        total_sample_size = config.total_sample_size or int(
            len(records) * (config.sampling_ratio or 0.1)
        )
        
        # 计算各风险等级的抽样数量
        sample_sizes = {
            RiskLevel.A: int(total_sample_size * weights.risk_A_weight),
            RiskLevel.B: int(total_sample_size * weights.risk_B_weight),
            RiskLevel.C: int(total_sample_size * weights.risk_C_weight)
        }
        
        sampled_records = []
        
        # 按风险等级抽样
        for risk_level, sample_size in sample_sizes.items():
            risk_records = [r for r in records if r['risk_level'] == risk_level]
            
            if risk_records and sample_size > 0:
                actual_sample_size = min(sample_size, len(risk_records))
                selected_indices = np.random.choice(
                    len(risk_records),
                    size=actual_sample_size,
                    replace=False
                )
                
                for idx in selected_indices:
                    sampled_records.append(risk_records[idx])
        
        return [self._convert_to_task_item(record) for record in sampled_records]
    
    async def _random_sampling(
        self,
        records: List[Dict[str, Any]],
        config: SamplingConfig
    ) -> List[QCAuditTaskItem]:
        """随机抽样"""
        
        sample_size = config.total_sample_size or int(
            len(records) * (config.sampling_ratio or 0.1)
        )
        
        actual_sample_size = min(sample_size, len(records))
        
        if actual_sample_size > 0:
            selected_indices = np.random.choice(
                len(records),
                size=actual_sample_size,
                replace=False
            )
            
            sampled_records = [records[idx] for idx in selected_indices]
        else:
            sampled_records = []
        
        return [self._convert_to_task_item(record) for record in sampled_records]
    
    async def _systematic_sampling(
        self,
        records: List[Dict[str, Any]],
        config: SamplingConfig
    ) -> List[QCAuditTaskItem]:
        """系统抽样"""
        
        sample_size = config.total_sample_size or int(
            len(records) * (config.sampling_ratio or 0.1)
        )
        
        if sample_size >= len(records):
            return [self._convert_to_task_item(record) for record in records]
        
        interval = len(records) // sample_size
        start_index = np.random.randint(0, interval)
        
        sampled_records = []
        for i in range(sample_size):
            index = (start_index + i * interval) % len(records)
            sampled_records.append(records[index])
        
        return [self._convert_to_task_item(record) for record in sampled_records]
    
    def _convert_to_task_item(self, record: Dict[str, Any]) -> QCAuditTaskItem:
        """转换为审核任务项"""
        return QCAuditTaskItem(
            id=str(uuid.uuid4()),
            task_id='',  # 将在创建时设置
            patient_id=record['patient_id'],
            medical_record_id=record['medical_record_id'],
            patient_name=record['patient_name'],
            admission_date=record['admission_date'],
            discharge_date=record.get('discharge_date'),
            department_id=record['department_id'],
            department_name=record['department_name'],
            risk_level=record['risk_level'],
            complexity_score=record['complexity_score'],
            audit_status=TaskItemStatus.PENDING,
            defect_count=0,
            has_critical_defects=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

class AuditTaskService:
    """审核任务管理服务"""
    
    def __init__(self, qc_engine: ThreeLayerQCEngineInterface):
        self.qc_engine = qc_engine
        self.sampling_service = IntelligentSamplingService(qc_engine)
    
    async def create_audit_task(
        self,
        request: CreateAuditTaskRequest,
        created_by: str,
        db: AsyncSession
    ) -> QCAuditTask:
        """创建审核任务"""
        
        print(f"创建审核任务: {request.task_name}")
        
        try:
            # 1. 生成任务代码
            task_code = self._generate_task_code(request.task_type, request.audit_level)
            
            # 2. 创建任务记录
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
                status=AuditStatus.PENDING,
                created_by=created_by,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            db.add(task_data)
            await db.flush()  # 获取ID
            
            # 3. 执行智能抽样
            task_items = await self.sampling_service.execute_sampling(
                request.audit_scope,
                request.sampling_config,
                db
            )
            
            # 4. 创建任务明细
            await self._create_task_items(task_data.id, task_items, db)
            
            # 5. 分配审核员
            await self._assign_reviewers(task_data.id, request.assigned_reviewers, db)
            
            # 6. 更新任务统计
            await self._update_task_statistics(task_data.id, db)
            
            await db.commit()
            
            print(f"审核任务创建完成: {task_code}")
            
            # 转换为响应模型
            return await self._convert_to_response_model(task_data, db)
            
        except Exception as e:
            await db.rollback()
            print(f"创建审核任务失败: {e}")
            raise e
    
    def _generate_task_code(self, task_type: str, audit_level: str) -> str:
        """生成任务代码"""
        prefix = f"{task_type.upper()}_{audit_level.upper()}"
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        random_suffix = str(uuid.uuid4())[:8].upper()
        
        return f"{prefix}_{timestamp}_{random_suffix}"
    
    async def _create_task_items(
        self,
        task_id: str,
        items: List[QCAuditTaskItem],
        db: AsyncSession
    ) -> None:
        """创建任务明细"""
        
        task_item_records = []
        for item in items:
            item.task_id = task_id
            task_item_records.append(QCAuditTaskItemDB(**item.dict()))
        
        db.add_all(task_item_records)
    
    async def _assign_reviewers(
        self,
        task_id: str,
        reviewer_ids: List[str],
        db: AsyncSession
    ) -> None:
        """分配审核员"""
        
        # 获取任务明细
        result = await db.execute(
            select(QCAuditTaskItemDB).where(QCAuditTaskItemDB.task_id == task_id)
        )
        task_items = result.scalars().all()
        
        # 负载均衡分配
        assignments = self._distribute_task_items(task_items, reviewer_ids)
        
        # 批量更新分配
        for reviewer_id, item_ids in assignments.items():
            await db.execute(
                update(QCAuditTaskItemDB)
                .where(QCAuditTaskItemDB.id.in_(item_ids))
                .values(
                    assigned_reviewer_id=reviewer_id,
                    assigned_at=datetime.utcnow()
                )
            )
    
    def _distribute_task_items(
        self,
        items: List[QCAuditTaskItemDB],
        reviewer_ids: List[str]
    ) -> Dict[str, List[str]]:
        """负载均衡分配任务项"""
        
        assignments = {reviewer_id: [] for reviewer_id in reviewer_ids}
        
        # 轮询分配
        for i, item in enumerate(items):
            reviewer_id = reviewer_ids[i % len(reviewer_ids)]
            assignments[reviewer_id].append(item.id)
        
        return assignments
    
    async def _update_task_statistics(self, task_id: str, db: AsyncSession) -> None:
        """更新任务统计信息"""
        
        # 统计任务项数量
        result = await db.execute(
            select(func.count(QCAuditTaskItemDB.id))
            .where(QCAuditTaskItemDB.task_id == task_id)
        )
        total_records = result.scalar() or 0
        
        # 更新任务记录
        await db.execute(
            update(QCAuditTaskDB)
            .where(QCAuditTaskDB.id == task_id)
            .values(
                total_records=total_records,
                updated_at=datetime.utcnow()
            )
        )
    
    async def _convert_to_response_model(
        self,
        task_data: QCAuditTaskDB,
        db: AsyncSession
    ) -> QCAuditTask:
        """转换为响应模型"""
        
        # 这里需要根据实际的数据库模型进行转换
        # 简化实现，实际需要查询关联的审核员信息
        
        return QCAuditTask(
            id=task_data.id,
            task_code=task_data.task_code,
            task_name=task_data.task_name,
            task_type=task_data.task_type,
            audit_level=task_data.audit_level,
            audit_scope=AuditScope(**task_data.audit_scope),
            sampling_config=SamplingConfig(**task_data.sampling_config),
            status=task_data.status,
            progress_percentage=0,
            planned_start_date=task_data.planned_start_date,
            planned_end_date=task_data.planned_end_date,
            actual_start_date=task_data.actual_start_date,
            actual_end_date=task_data.actual_end_date,
            created_by=task_data.created_by,
            assigned_reviewers=[],  # 需要查询关联数据
            total_records=task_data.total_records or 0,
            completed_records=0,
            defect_rate=task_data.defect_rate,
            description=task_data.description,
            priority=task_data.priority,
            created_at=task_data.created_at,
            updated_at=task_data.updated_at
        )
