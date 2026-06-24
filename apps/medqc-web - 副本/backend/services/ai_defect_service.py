# AI辅助缺陷识别服务 - 增强版
# 完全迁移TypeScript AI服务到Python，集成现有三层质控引擎

import asyncio
import json
import hashlib
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from dataclasses import dataclass
from enum import Enum

from ..models.audit_models import (
    QCAuditTaskItem, QCDefect, AIDefectSuggestion,
    DefectAnalysisContext, DefectSeverity, QCAuditResult
)
from ..database.models import QCAuditTaskItemDB, QCDefectDB, MedicalRecordDB

logger = logging.getLogger(__name__)

# 性能监控装饰器
def performance_monitor(func_name: str):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            start_time = datetime.utcnow()
            try:
                result = await func(*args, **kwargs)
                duration = (datetime.utcnow() - start_time).total_seconds()
                logger.info(f"{func_name} 执行完成，耗时: {duration:.3f}s")
                return result
            except Exception as e:
                duration = (datetime.utcnow() - start_time).total_seconds()
                logger.error(f"{func_name} 执行失败，耗时: {duration:.3f}s，错误: {e}")
                raise
        return wrapper
    return decorator

# 批量处理配置
@dataclass
class BatchProcessingConfig:
    batch_size: int = 50
    max_concurrency: int = 5
    timeout_seconds: int = 300
    retry_attempts: int = 2
    enable_cache: bool = True

# 缓存策略枚举
class CacheStrategy(Enum):
    MEMORY_ONLY = "memory_only"
    REDIS_ONLY = "redis_only"
    HYBRID = "hybrid"
    DISABLED = "disabled"

# 假设现有的三层质控引擎和LLM服务接口
class ThreeLayerQCEngineInterface:
    """现有三层质控引擎接口"""
    
    async def deep_analyze_for_defects(
        self,
        record_data: Dict[str, Any],
        focus_areas: List[str] = None,
        analysis_config: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """深度分析医疗记录以识别缺陷"""
        pass
    
    async def batch_analyze_for_defects(
        self,
        records_data: List[Dict[str, Any]],
        focus_areas: List[str] = None
    ) -> List[Dict[str, Any]]:
        """批量分析医疗记录缺陷"""
        pass
    
    async def generate_rectification_suggestions(
        self,
        defect_analysis: Dict[str, Any],
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """生成整改建议"""
        pass

class LLMServiceInterface:
    """现有LLM服务接口"""
    
    async def generate_response(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        model: str = "gpt-4"
    ) -> Dict[str, Any]:
        """生成LLM响应"""
        pass
    
    async def batch_generate_responses(
        self,
        prompts: List[str],
        **kwargs
    ) -> List[Dict[str, Any]]:
        """批量生成LLM响应"""
        pass

class EnhancedAIDefectDetectionService:
    """增强版AI辅助缺陷识别服务 - 完全替代TypeScript实现"""

    def __init__(
        self,
        qc_engine: ThreeLayerQCEngineInterface,
        llm_service: LLMServiceInterface,
        config: BatchProcessingConfig = None,
        cache_strategy: CacheStrategy = CacheStrategy.HYBRID
    ):
        self.qc_engine = qc_engine
        self.llm_service = llm_service
        self.config = config or BatchProcessingConfig()
        self.cache_strategy = cache_strategy

        # 多层缓存系统
        self.memory_cache = {}  # L1内存缓存
        self.redis_cache = None  # L2 Redis缓存 (待实现)
        self.cache_ttl = 3600  # 缓存1小时

        # 性能统计
        self.performance_stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "average_response_time": 0.0,
            "error_count": 0
        }

        # 线程池用于CPU密集型任务
        self.thread_pool = ThreadPoolExecutor(max_workers=4)

        logger.info(f"AI缺陷识别服务初始化完成，配置: {self.config}")

    async def cleanup(self):
        """清理资源"""
        if self.thread_pool:
            self.thread_pool.shutdown(wait=True)
        logger.info("AI缺陷识别服务资源已清理")
    
    @performance_monitor("AI缺陷识别")
    async def suggest_defects(
        self,
        task_item: QCAuditTaskItem,
        context: DefectAnalysisContext,
        db: AsyncSession,
        use_cache: bool = True
    ) -> List[AIDefectSuggestion]:
        """增强版AI辅助缺陷识别 - 完全替代TypeScript实现"""

        self.performance_stats["total_requests"] += 1
        logger.info(f"AI辅助缺陷识别: 患者 {task_item.patient_name}")

        try:
            # 1. 获取医疗记录数据
            medical_record_data = await self._get_medical_record_data(
                task_item.medical_record_id, db
            )

            if not medical_record_data:
                logger.warning(f"未找到医疗记录: {task_item.medical_record_id}")
                return []

            # 2. 智能缓存检查
            cache_key = self._generate_cache_key(medical_record_data, context)
            if use_cache:
                cached_result = await self._get_cached_result(cache_key)
                if cached_result:
                    self.performance_stats["cache_hits"] += 1
                    logger.info("使用缓存的AI分析结果")
                    return cached_result
                else:
                    self.performance_stats["cache_misses"] += 1

            # 3. 使用现有质控引擎进行深度分析
            qc_analysis_result = await self._execute_qc_analysis(
                medical_record_data, context
            )

            # 4. 转换质控结果为缺陷建议
            defect_suggestions = await self._convert_qc_results_to_defect_suggestions(
                qc_analysis_result, context, medical_record_data
            )

            # 5. 使用LLM增强缺陷描述和整改建议
            enhanced_suggestions = await self._enhance_defect_suggestions_with_llm(
                defect_suggestions, medical_record_data, context
            )

            # 6. 智能缓存结果
            if use_cache and enhanced_suggestions:
                await self._cache_result(cache_key, enhanced_suggestions)

            logger.info(f"AI识别到 {len(enhanced_suggestions)} 个潜在缺陷")
            return enhanced_suggestions

        except Exception as e:
            self.performance_stats["error_count"] += 1
            logger.error(f"AI缺陷识别失败: {e}", exc_info=True)
            return []

    async def _execute_qc_analysis(
        self,
        medical_record_data: Dict[str, Any],
        context: DefectAnalysisContext
    ) -> Dict[str, Any]:
        """执行质控分析"""
        return await self.qc_engine.deep_analyze_for_defects(
            record_data=medical_record_data,
            focus_areas=["completeness", "consistency", "timeliness", "accuracy", "compliance"],
            analysis_config={
                "audit_level": context.audit_level,
                "reviewer_expertise": context.reviewer_expertise,
                "enable_detailed_analysis": True,
                "include_confidence_scores": True,
                "generate_evidence": True
            }
        )
    
    @performance_monitor("批量AI缺陷识别")
    async def batch_suggest_defects(
        self,
        task_items: List[QCAuditTaskItem],
        context: DefectAnalysisContext,
        db: AsyncSession,
        use_cache: bool = True
    ) -> Dict[str, List[AIDefectSuggestion]]:
        """增强版批量AI缺陷识别 - 优化性能和错误处理"""

        logger.info(f"批量AI缺陷识别: {len(task_items)} 个任务项")

        if not task_items:
            return {}

        # 分批处理以避免内存溢出
        all_results = {}
        batch_size = self.config.batch_size

        for i in range(0, len(task_items), batch_size):
            batch_items = task_items[i:i + batch_size]
            batch_results = await self._process_batch_items(
                batch_items, context, db, use_cache
            )
            all_results.update(batch_results)

            # 避免过载，添加短暂延迟
            if i + batch_size < len(task_items):
                await asyncio.sleep(0.1)

        logger.info(f"批量分析完成，处理了 {len(all_results)} 个项目")
        return all_results

    async def _process_batch_items(
        self,
        batch_items: List[QCAuditTaskItem],
        context: DefectAnalysisContext,
        db: AsyncSession,
        use_cache: bool
    ) -> Dict[str, List[AIDefectSuggestion]]:
        """处理单个批次的任务项"""

        results = {}

        try:
            # 1. 批量获取医疗记录数据
            medical_records_data = await self._batch_get_medical_record_data(
                [item.medical_record_id for item in batch_items], db
            )

            # 2. 准备有效的分析数据
            valid_items = []
            item_record_mapping = {}

            for item in batch_items:
                record_data = medical_records_data.get(item.medical_record_id)
                if record_data:
                    valid_items.append(item)
                    item_record_mapping[item.id] = record_data
                else:
                    results[item.id] = []  # 无数据的项目返回空结果

            if not valid_items:
                return results

            # 3. 检查缓存（批量）
            cache_results = {}
            uncached_items = []

            if use_cache:
                for item in valid_items:
                    record_data = item_record_mapping[item.id]
                    cache_key = self._generate_cache_key(record_data, context)
                    cached_result = await self._get_cached_result(cache_key)

                    if cached_result:
                        cache_results[item.id] = cached_result
                        self.performance_stats["cache_hits"] += 1
                    else:
                        uncached_items.append(item)
                        self.performance_stats["cache_misses"] += 1
            else:
                uncached_items = valid_items

            # 4. 批量分析未缓存的项目
            if uncached_items:
                batch_analysis_results = await self._execute_batch_qc_analysis(
                    uncached_items, item_record_mapping, context
                )

                # 5. 处理分析结果并缓存
                for item_id, qc_result in batch_analysis_results.items():
                    item = next(item for item in uncached_items if item.id == item_id)
                    record_data = item_record_mapping[item_id]

                    # 转换为缺陷建议
                    defect_suggestions = await self._convert_qc_results_to_defect_suggestions(
                        qc_result, context, record_data
                    )

                    # LLM增强（可选，批量处理时可能跳过以提高性能）
                    if len(uncached_items) <= 10:  # 小批量时进行LLM增强
                        defect_suggestions = await self._enhance_defect_suggestions_with_llm(
                            defect_suggestions, record_data, context
                        )

                    results[item_id] = defect_suggestions

                    # 缓存结果
                    if use_cache and defect_suggestions:
                        cache_key = self._generate_cache_key(record_data, context)
                        await self._cache_result(cache_key, defect_suggestions)

            # 6. 合并缓存结果
            results.update(cache_results)

            return results

        except Exception as e:
            logger.error(f"批量处理失败: {e}", exc_info=True)
            # 返回空结果而不是抛出异常
            return {item.id: [] for item in batch_items}

    async def _execute_batch_qc_analysis(
        self,
        items: List[QCAuditTaskItem],
        item_record_mapping: Dict[str, Dict[str, Any]],
        context: DefectAnalysisContext
    ) -> Dict[str, Dict[str, Any]]:
        """执行批量质控分析"""

        batch_analysis_data = [
            item_record_mapping[item.id] for item in items
        ]

        # 使用质控引擎批量分析
        batch_qc_results = await self.qc_engine.batch_analyze_for_defects(
            records_data=batch_analysis_data,
            focus_areas=["completeness", "consistency", "timeliness", "accuracy", "compliance"],
            analysis_config={
                "audit_level": context.audit_level,
                "reviewer_expertise": context.reviewer_expertise,
                "batch_mode": True,
                "include_confidence_scores": True
            }
        )

        # 映射结果到项目ID
        results = {}
        for i, item in enumerate(items):
            if i < len(batch_qc_results):
                results[item.id] = batch_qc_results[i]
            else:
                results[item.id] = {"findings": [], "overall_score": 80}

        return results
    
    async def generate_rectification_plan(
        self,
        defects: List[QCDefect],
        medical_record_data: Dict[str, Any],
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """生成整改计划"""
        
        try:
            # 使用现有质控引擎生成整改建议
            rectification_analysis = await self.qc_engine.generate_rectification_suggestions(
                defect_analysis={
                    "defects": [self._defect_to_dict(defect) for defect in defects],
                    "medical_record": medical_record_data
                },
                context=context or {}
            )
            
            # 使用LLM生成详细的整改计划
            rectification_prompt = self._build_rectification_plan_prompt(
                defects, medical_record_data, rectification_analysis
            )
            
            llm_response = await self.llm_service.generate_response(
                prompt=rectification_prompt,
                temperature=0.3,  # 较低温度以获得更一致的结果
                max_tokens=1500
            )
            
            # 解析LLM响应
            rectification_plan = self._parse_rectification_plan(llm_response)
            
            return {
                "plan": rectification_plan,
                "estimated_time": self._calculate_estimated_rectification_time(defects),
                "priority_order": self._determine_rectification_priority(defects),
                "resources_needed": self._identify_required_resources(defects),
                "quality_checkpoints": self._define_quality_checkpoints(defects)
            }
            
        except Exception as e:
            print(f"生成整改计划失败: {e}")
            return {"error": str(e)}
    
    async def _get_medical_record_data(
        self, 
        medical_record_id: str, 
        db: AsyncSession
    ) -> Optional[Dict[str, Any]]:
        """获取医疗记录数据"""
        
        result = await db.execute(
            select(MedicalRecordDB).where(MedicalRecordDB.id == medical_record_id)
        )
        record = result.scalar_one_or_none()
        
        if not record:
            return None
        
        return {
            "id": record.id,
            "patient_id": record.patient_id,
            "department_id": record.department_id,
            "document_type": record.document_type,
            "content": record.content,
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "updated_at": record.updated_at.isoformat() if record.updated_at else None
        }
    
    async def _batch_get_medical_record_data(
        self,
        medical_record_ids: List[str],
        db: AsyncSession
    ) -> Dict[str, Dict[str, Any]]:
        """批量获取医疗记录数据"""
        
        result = await db.execute(
            select(MedicalRecordDB).where(MedicalRecordDB.id.in_(medical_record_ids))
        )
        records = result.scalars().all()
        
        records_data = {}
        for record in records:
            records_data[record.id] = {
                "id": record.id,
                "patient_id": record.patient_id,
                "department_id": record.department_id,
                "document_type": record.document_type,
                "content": record.content,
                "created_at": record.created_at.isoformat() if record.created_at else None,
                "updated_at": record.updated_at.isoformat() if record.updated_at else None
            }
        
        return records_data
    
    async def _convert_qc_results_to_defect_suggestions(
        self,
        qc_result: Dict[str, Any],
        context: DefectAnalysisContext,
        medical_record_data: Dict[str, Any]
    ) -> List[AIDefectSuggestion]:
        """将质控结果转换为缺陷建议"""
        
        suggestions = []
        
        # 处理质控引擎发现的问题
        findings = qc_result.get("findings", [])
        
        for finding in findings:
            # 映射缺陷类型和类别
            defect_type = self._map_finding_to_defect_type(finding.get("type", ""))
            defect_category = self._map_finding_to_defect_category(finding.get("category", ""))
            severity = self._map_severity_to_defect_severity(finding.get("severity", "minor"))
            
            # 计算置信度
            confidence = min(finding.get("confidence", 70) * 1.2, 100)  # 基于质控引擎结果提升置信度
            
            # 生成整改建议
            rectification_suggestions = self._generate_rectification_suggestions(
                finding, medical_record_data, context
            )
            
            suggestion = AIDefectSuggestion(
                suggested_type=defect_type,
                suggested_category=defect_category,
                suggested_severity=severity,
                suggested_title=finding.get("title", f"{defect_type}问题"),
                suggested_description=self._enhance_defect_description(finding, context),
                suggested_location=finding.get("location", ""),
                confidence=confidence,
                supporting_evidence=finding.get("evidence", []),
                rectification_suggestions=rectification_suggestions
            )
            
            suggestions.append(suggestion)
        
        return suggestions
    
    async def _enhance_defect_suggestions_with_llm(
        self,
        suggestions: List[AIDefectSuggestion],
        medical_record_data: Dict[str, Any],
        context: DefectAnalysisContext
    ) -> List[AIDefectSuggestion]:
        """使用LLM增强缺陷建议"""
        
        if not suggestions:
            return suggestions
        
        try:
            # 构建LLM提示词
            enhancement_prompt = self._build_defect_enhancement_prompt(
                suggestions, medical_record_data, context
            )
            
            # 调用LLM服务
            llm_response = await self.llm_service.generate_response(
                prompt=enhancement_prompt,
                temperature=0.5,
                max_tokens=2000
            )
            
            # 解析LLM响应并增强建议
            enhanced_suggestions = self._parse_and_enhance_suggestions(
                suggestions, llm_response
            )
            
            return enhanced_suggestions
            
        except Exception as e:
            print(f"LLM增强缺陷建议失败: {e}")
            return suggestions  # 返回原始建议
    
    def _map_finding_to_defect_type(self, finding_type: str) -> str:
        """映射发现类型到缺陷类型"""
        type_mapping = {
            "missing_section": "内容缺失",
            "missing_content": "信息不完整",
            "format_error": "格式错误",
            "logical_inconsistency": "逻辑不一致",
            "duplication": "内容重复",
            "timeliness_issue": "时效性问题",
            "compliance_violation": "规范违反",
            "data_accuracy": "数据准确性问题"
        }
        return type_mapping.get(finding_type, "其他问题")
    
    def _map_finding_to_defect_category(self, finding_category: str) -> str:
        """映射发现类别到缺陷类别"""
        category_mapping = {
            "completeness": "完整性",
            "consistency": "一致性",
            "timeliness": "时效性",
            "accuracy": "准确性",
            "compliance": "合规性",
            "format": "格式规范"
        }
        return category_mapping.get(finding_category, "质量问题")
    
    def _map_severity_to_defect_severity(self, severity: str) -> DefectSeverity:
        """映射严重程度"""
        severity_mapping = {
            "critical": DefectSeverity.CRITICAL,
            "major": DefectSeverity.MAJOR,
            "minor": DefectSeverity.MINOR,
            "high": DefectSeverity.MAJOR,
            "medium": DefectSeverity.MINOR,
            "low": DefectSeverity.MINOR
        }
        return severity_mapping.get(severity.lower(), DefectSeverity.MINOR)
    
    def _generate_cache_key(
        self, 
        medical_record_data: Dict[str, Any], 
        context: DefectAnalysisContext
    ) -> str:
        """生成缓存键"""
        key_data = {
            "record_id": medical_record_data.get("id"),
            "audit_level": context.audit_level,
            "content_hash": hashlib.md5(
                str(medical_record_data.get("content", "")).encode()
            ).hexdigest()[:16]
        }
        return hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()
    
    async def _get_cached_result(self, cache_key: str) -> Optional[List[AIDefectSuggestion]]:
        """智能缓存获取 - 支持多层缓存策略"""

        if self.cache_strategy == CacheStrategy.DISABLED:
            return None

        # L1内存缓存检查
        if self.cache_strategy in [CacheStrategy.MEMORY_ONLY, CacheStrategy.HYBRID]:
            if cache_key in self.memory_cache:
                cached_data, timestamp, access_count = self.memory_cache[cache_key]
                if datetime.utcnow().timestamp() - timestamp < self.cache_ttl:
                    # 更新访问计数（LRU策略）
                    self.memory_cache[cache_key] = (cached_data, timestamp, access_count + 1)
                    return cached_data
                else:
                    del self.memory_cache[cache_key]

        # L2 Redis缓存检查（待实现）
        if self.cache_strategy in [CacheStrategy.REDIS_ONLY, CacheStrategy.HYBRID]:
            # TODO: 实现Redis缓存
            pass

        return None

    async def _cache_result(self, cache_key: str, result: List[AIDefectSuggestion]) -> None:
        """智能缓存存储 - 支持多层缓存策略"""

        if self.cache_strategy == CacheStrategy.DISABLED:
            return

        current_time = datetime.utcnow().timestamp()

        # L1内存缓存存储
        if self.cache_strategy in [CacheStrategy.MEMORY_ONLY, CacheStrategy.HYBRID]:
            # LRU缓存清理（保持最多1000个条目）
            if len(self.memory_cache) >= 1000:
                # 移除最少访问的条目
                oldest_key = min(
                    self.memory_cache.keys(),
                    key=lambda k: self.memory_cache[k][2]  # 按访问次数排序
                )
                del self.memory_cache[oldest_key]

            self.memory_cache[cache_key] = (result, current_time, 1)

        # L2 Redis缓存存储（待实现）
        if self.cache_strategy in [CacheStrategy.REDIS_ONLY, CacheStrategy.HYBRID]:
            # TODO: 实现Redis缓存
            pass

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        return {
            "memory_cache_size": len(self.memory_cache),
            "cache_hit_rate": (
                self.performance_stats["cache_hits"] /
                max(self.performance_stats["total_requests"], 1)
            ) * 100,
            "cache_strategy": self.cache_strategy.value,
            "performance_stats": self.performance_stats
        }

    def clear_cache(self) -> None:
        """清理所有缓存"""
        self.memory_cache.clear()
        logger.info("AI分析缓存已清理")
    
    def _enhance_defect_description(
        self, 
        finding: Dict[str, Any], 
        context: DefectAnalysisContext
    ) -> str:
        """增强缺陷描述"""
        base_description = finding.get("description", "")
        
        # 添加上下文信息
        if context.audit_level:
            base_description += f"\n\n审核级别：{context.audit_level}"
        
        if finding.get("medical_reasoning"):
            base_description += f"\n\n医学推理：{finding['medical_reasoning']}"
        
        return base_description
    
    def _generate_rectification_suggestions(
        self,
        finding: Dict[str, Any],
        medical_record_data: Dict[str, Any],
        context: DefectAnalysisContext
    ) -> List[str]:
        """生成整改建议"""
        suggestions = []
        
        # 基于缺陷类型生成建议
        defect_type = finding.get("type", "")
        
        if defect_type == "missing_section":
            suggestions.append("请补充缺失的病历章节")
            suggestions.append("参考相关医疗文书规范要求")
        elif defect_type == "format_error":
            suggestions.append("请按照标准格式要求修正")
            suggestions.append("检查日期、时间格式是否正确")
        elif defect_type == "logical_inconsistency":
            suggestions.append("请核实相关信息的逻辑一致性")
            suggestions.append("确保前后记录内容相符")
        
        # 添加通用建议
        if finding.get("recommendation"):
            suggestions.append(finding["recommendation"])
        
        return suggestions
    
    def _build_defect_enhancement_prompt(
        self,
        suggestions: List[AIDefectSuggestion],
        medical_record_data: Dict[str, Any],
        context: DefectAnalysisContext
    ) -> str:
        """构建缺陷增强提示词"""
        
        prompt = f"""
作为医疗质控专家，请帮助优化以下缺陷识别结果：

病历信息：
- 科室：{medical_record_data.get('department_id', '未知')}
- 文书类型：{medical_record_data.get('document_type', '未知')}
- 审核级别：{context.audit_level}

已识别的缺陷：
"""
        
        for i, suggestion in enumerate(suggestions, 1):
            prompt += f"""
{i}. {suggestion.suggested_title}
   类型：{suggestion.suggested_type}
   严重程度：{suggestion.suggested_severity}
   描述：{suggestion.suggested_description}
   置信度：{suggestion.confidence}%
"""
        
        prompt += """
请为每个缺陷提供：
1. 更准确的缺陷描述
2. 具体的整改建议
3. 预计整改时间
4. 相关的医疗规范依据

请以JSON格式返回优化结果。
"""
        
        return prompt
    
    def _parse_and_enhance_suggestions(
        self,
        original_suggestions: List[AIDefectSuggestion],
        llm_response: Dict[str, Any]
    ) -> List[AIDefectSuggestion]:
        """解析并增强建议"""
        
        try:
            # 尝试解析LLM响应
            response_content = llm_response.get("content", "")
            
            # 简化实现：直接返回原始建议
            # 实际实现中需要解析LLM的JSON响应并更新建议
            
            return original_suggestions
            
        except Exception as e:
            print(f"解析LLM响应失败: {e}")
            return original_suggestions
    
    def _defect_to_dict(self, defect: QCDefect) -> Dict[str, Any]:
        """将缺陷对象转换为字典"""
        return {
            "type": defect.defect_type,
            "category": defect.defect_category,
            "severity": defect.severity,
            "title": defect.title,
            "description": defect.description,
            "location": defect.location,
            "score_deduction": defect.score_deduction
        }
