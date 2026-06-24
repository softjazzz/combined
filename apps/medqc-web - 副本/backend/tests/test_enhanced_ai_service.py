# 增强版AI服务单元测试
# 确保迁移后的Python服务功能正确性和性能

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from typing import List, Dict, Any

_ai_defect_service = pytest.importorskip(
    "app.services.ai_defect_service",
    reason="ai_defect_service module not available in current backend",
)
_audit_models = pytest.importorskip(
    "app.models.audit_models",
    reason="audit_models module not available in current backend",
)

EnhancedAIDefectDetectionService = _ai_defect_service.EnhancedAIDefectDetectionService
BatchProcessingConfig = _ai_defect_service.BatchProcessingConfig
CacheStrategy = _ai_defect_service.CacheStrategy
QCAuditTaskItem = _audit_models.QCAuditTaskItem
AIDefectSuggestion = _audit_models.AIDefectSuggestion
DefectAnalysisContext = _audit_models.DefectAnalysisContext
DefectSeverity = _audit_models.DefectSeverity
AuditLevel = _audit_models.AuditLevel

class TestEnhancedAIDefectDetectionService:
    """增强版AI缺陷识别服务测试"""
    
    @pytest.fixture
    def mock_qc_engine(self):
        """模拟质控引擎"""
        engine = Mock()
        engine.deep_analyze_for_defects = AsyncMock(return_value={
            "findings": [
                {
                    "type": "missing_section",
                    "category": "completeness",
                    "severity": "major",
                    "title": "缺少主诉信息",
                    "description": "病历中未记录患者主诉",
                    "confidence": 85,
                    "evidence": ["未找到主诉章节"],
                    "location": "病史部分"
                }
            ],
            "overall_score": 75
        })
        engine.batch_analyze_for_defects = AsyncMock(return_value=[
            {"findings": [{"type": "format_error", "severity": "minor", "confidence": 70}]},
            {"findings": [{"type": "logical_inconsistency", "severity": "major", "confidence": 90}]}
        ])
        return engine
    
    @pytest.fixture
    def mock_llm_service(self):
        """模拟LLM服务"""
        service = Mock()
        service.generate_response = AsyncMock(return_value={
            "content": '{"title": "增强的缺陷标题", "content": "详细的缺陷描述"}'
        })
        return service
    
    @pytest.fixture
    def ai_service(self, mock_qc_engine, mock_llm_service):
        """创建AI服务实例"""
        config = BatchProcessingConfig(
            batch_size=10,
            max_concurrency=2,
            timeout_seconds=60,
            enable_cache=True
        )
        return EnhancedAIDefectDetectionService(
            qc_engine=mock_qc_engine,
            llm_service=mock_llm_service,
            config=config,
            cache_strategy=CacheStrategy.MEMORY_ONLY
        )
    
    @pytest.fixture
    def sample_task_item(self):
        """示例任务项"""
        return QCAuditTaskItem(
            id="task_item_1",
            task_id="task_1",
            patient_id="patient_1",
            medical_record_id="record_1",
            patient_name="张三",
            admission_date=datetime.utcnow(),
            department_id="dept_1",
            department_name="内科",
            risk_level="B",
            complexity_score=60,
            audit_status="pending",
            defect_count=0,
            has_critical_defects=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
    
    @pytest.fixture
    def sample_context(self):
        """示例分析上下文"""
        return DefectAnalysisContext(
            medical_record={"content": "病历内容示例"},
            audit_level=AuditLevel.LEVEL_2,
            reviewer_expertise=["内科", "质控"]
        )
    
    @pytest.fixture
    def mock_db_session(self):
        """模拟数据库会话"""
        db = Mock()
        # 模拟医疗记录查询
        db.execute = AsyncMock()
        db.execute.return_value.scalar_one_or_none.return_value = Mock(
            id="record_1",
            patient_id="patient_1",
            content="病历内容示例",
            created_at=datetime.utcnow()
        )
        return db

class TestSingleDefectDetection:
    """单个缺陷识别测试"""
    
    @pytest.mark.asyncio
    async def test_suggest_defects_success(
        self, 
        ai_service, 
        sample_task_item, 
        sample_context, 
        mock_db_session
    ):
        """测试成功的缺陷识别"""
        
        # 模拟医疗记录数据获取
        with patch.object(ai_service, '_get_medical_record_data') as mock_get_data:
            mock_get_data.return_value = {
                "id": "record_1",
                "content": "病历内容示例",
                "patient_id": "patient_1"
            }
            
            # 执行缺陷识别
            suggestions = await ai_service.suggest_defects(
                task_item=sample_task_item,
                context=sample_context,
                db=mock_db_session,
                use_cache=False
            )
            
            # 验证结果
            assert isinstance(suggestions, list)
            assert len(suggestions) > 0
            
            suggestion = suggestions[0]
            assert isinstance(suggestion, AIDefectSuggestion)
            assert suggestion.suggested_type == "内容缺失"
            assert suggestion.confidence > 0
            assert len(suggestion.supporting_evidence) > 0
    
    @pytest.mark.asyncio
    async def test_suggest_defects_with_cache(
        self, 
        ai_service, 
        sample_task_item, 
        sample_context, 
        mock_db_session
    ):
        """测试缓存功能"""
        
        with patch.object(ai_service, '_get_medical_record_data') as mock_get_data:
            mock_get_data.return_value = {
                "id": "record_1",
                "content": "病历内容示例"
            }
            
            # 第一次调用
            suggestions1 = await ai_service.suggest_defects(
                task_item=sample_task_item,
                context=sample_context,
                db=mock_db_session,
                use_cache=True
            )
            
            # 第二次调用应该使用缓存
            suggestions2 = await ai_service.suggest_defects(
                task_item=sample_task_item,
                context=sample_context,
                db=mock_db_session,
                use_cache=True
            )
            
            # 验证缓存统计
            stats = ai_service.get_cache_stats()
            assert stats["cache_hit_rate"] > 0
            assert len(suggestions1) == len(suggestions2)
    
    @pytest.mark.asyncio
    async def test_suggest_defects_no_medical_record(
        self, 
        ai_service, 
        sample_task_item, 
        sample_context, 
        mock_db_session
    ):
        """测试医疗记录不存在的情况"""
        
        with patch.object(ai_service, '_get_medical_record_data') as mock_get_data:
            mock_get_data.return_value = None
            
            suggestions = await ai_service.suggest_defects(
                task_item=sample_task_item,
                context=sample_context,
                db=mock_db_session
            )
            
            # 应该返回空列表
            assert suggestions == []

class TestBatchDefectDetection:
    """批量缺陷识别测试"""
    
    @pytest.mark.asyncio
    async def test_batch_suggest_defects_success(
        self, 
        ai_service, 
        sample_context, 
        mock_db_session
    ):
        """测试成功的批量缺陷识别"""
        
        # 创建多个任务项
        task_items = [
            QCAuditTaskItem(
                id=f"item_{i}",
                task_id="task_1",
                patient_id=f"patient_{i}",
                medical_record_id=f"record_{i}",
                patient_name=f"患者{i}",
                admission_date=datetime.utcnow(),
                department_id="dept_1",
                department_name="内科",
                risk_level="B",
                complexity_score=60,
                audit_status="pending",
                defect_count=0,
                has_critical_defects=False,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            for i in range(5)
        ]
        
        with patch.object(ai_service, '_batch_get_medical_record_data') as mock_batch_get:
            mock_batch_get.return_value = {
                f"record_{i}": {
                    "id": f"record_{i}",
                    "content": f"病历内容{i}",
                    "patient_id": f"patient_{i}"
                }
                for i in range(5)
            }
            
            # 执行批量识别
            results = await ai_service.batch_suggest_defects(
                task_items=task_items,
                context=sample_context,
                db=mock_db_session,
                use_cache=False
            )
            
            # 验证结果
            assert isinstance(results, dict)
            assert len(results) == 5
            
            for item_id, suggestions in results.items():
                assert isinstance(suggestions, list)
                # 每个项目都应该有结果（即使是空列表）
                assert item_id.startswith("item_")
    
    @pytest.mark.asyncio
    async def test_batch_suggest_defects_empty_input(
        self, 
        ai_service, 
        sample_context, 
        mock_db_session
    ):
        """测试空输入的批量识别"""
        
        results = await ai_service.batch_suggest_defects(
            task_items=[],
            context=sample_context,
            db=mock_db_session
        )
        
        assert results == {}
    
    @pytest.mark.asyncio
    async def test_batch_processing_with_large_dataset(
        self, 
        ai_service, 
        sample_context, 
        mock_db_session
    ):
        """测试大数据集的批量处理"""
        
        # 创建大量任务项（超过批次大小）
        task_items = [
            QCAuditTaskItem(
                id=f"item_{i}",
                task_id="task_1",
                patient_id=f"patient_{i}",
                medical_record_id=f"record_{i}",
                patient_name=f"患者{i}",
                admission_date=datetime.utcnow(),
                department_id="dept_1",
                department_name="内科",
                risk_level="B",
                complexity_score=60,
                audit_status="pending",
                defect_count=0,
                has_critical_defects=False,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            for i in range(25)  # 超过默认批次大小10
        ]
        
        with patch.object(ai_service, '_batch_get_medical_record_data') as mock_batch_get:
            mock_batch_get.return_value = {
                f"record_{i}": {"id": f"record_{i}", "content": f"内容{i}"}
                for i in range(25)
            }
            
            results = await ai_service.batch_suggest_defects(
                task_items=task_items,
                context=sample_context,
                db=mock_db_session
            )
            
            # 验证所有项目都被处理
            assert len(results) == 25

class TestCacheSystem:
    """缓存系统测试"""
    
    def test_cache_key_generation(self, ai_service, sample_context):
        """测试缓存键生成"""
        
        medical_record_data = {
            "id": "record_1",
            "content": "病历内容"
        }
        
        key1 = ai_service._generate_cache_key(medical_record_data, sample_context)
        key2 = ai_service._generate_cache_key(medical_record_data, sample_context)
        
        # 相同输入应该生成相同的键
        assert key1 == key2
        assert isinstance(key1, str)
        assert len(key1) > 0
    
    def test_cache_stats(self, ai_service):
        """测试缓存统计"""
        
        stats = ai_service.get_cache_stats()
        
        assert isinstance(stats, dict)
        assert "memory_cache_size" in stats
        assert "cache_hit_rate" in stats
        assert "cache_strategy" in stats
        assert "performance_stats" in stats
    
    def test_clear_cache(self, ai_service):
        """测试缓存清理"""
        
        # 添加一些缓存数据
        ai_service.memory_cache["test_key"] = ([], datetime.utcnow().timestamp(), 1)
        
        assert len(ai_service.memory_cache) > 0
        
        # 清理缓存
        ai_service.clear_cache()
        
        assert len(ai_service.memory_cache) == 0

class TestPerformanceMonitoring:
    """性能监控测试"""
    
    @pytest.mark.asyncio
    async def test_performance_stats_tracking(
        self, 
        ai_service, 
        sample_task_item, 
        sample_context, 
        mock_db_session
    ):
        """测试性能统计跟踪"""
        
        initial_stats = ai_service.performance_stats.copy()
        
        with patch.object(ai_service, '_get_medical_record_data') as mock_get_data:
            mock_get_data.return_value = {"id": "record_1", "content": "内容"}
            
            await ai_service.suggest_defects(
                task_item=sample_task_item,
                context=sample_context,
                db=mock_db_session
            )
            
            # 验证统计数据更新
            assert ai_service.performance_stats["total_requests"] > initial_stats["total_requests"]

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
