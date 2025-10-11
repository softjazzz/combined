"""
四川质控服务单元测试

测试 P0 优先级任务的实现：
1. 从数据库加载规则
2. 使用 Prompt 模板构建 Prompt
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.sichuan_qc_service import SichuanQCService


class TestSichuanQCService:
    """四川质控服务单元测试类"""

    @pytest.fixture
    def service(self):
        """创建服务实例"""
        return SichuanQCService()

    @pytest.fixture
    def mock_rules(self):
        """模拟规则数据"""
        return [
            {
                "id": "rule-001",
                "rule_code": "SC-001",
                "name": "病情分析完整性",
                "description": "首次病程记录必须包含详细的病情分析",
                "category": "completeness",
                "severity": "critical",
                "is_active": True,
                "check_logic": {
                    "applicable_documents": ["首次病程记录", "病程记录"]
                }
            },
            {
                "id": "rule-002",
                "rule_code": "SC-002",
                "name": "鉴别诊断完整性",
                "description": "首次病程记录必须包含鉴别诊断",
                "category": "completeness",
                "severity": "critical",
                "is_active": True,
                "check_logic": {
                    "applicable_documents": ["首次病程记录"]
                }
            },
            {
                "id": "rule-003",
                "rule_code": "SC-003",
                "name": "诊疗计划完整性",
                "description": "首次病程记录必须包含详细的诊疗计划",
                "category": "completeness",
                "severity": "major",
                "is_active": True,
                "check_logic": {
                    "applicable_documents": ["首次病程记录", "病程记录"]
                }
            },
            {
                "id": "rule-004",
                "rule_code": "SC-004",
                "name": "手术记录完整性",
                "description": "手术记录必须包含手术过程描述",
                "category": "completeness",
                "severity": "critical",
                "is_active": True,
                "check_logic": {
                    "applicable_documents": ["手术记录"]
                }
            },
        ]

    @pytest.mark.asyncio
    async def test_load_rules_from_db_success_with_db_filtering(self, service, mock_rules):
        """测试从数据库成功加载规则（使用数据库层面筛选）"""
        # Mock Supabase 客户端
        mock_supabase = MagicMock()
        mock_query = MagicMock()
        mock_response = MagicMock()

        # 模拟数据库层面筛选后的结果（只返回适用的规则）
        filtered_rules = [r for r in mock_rules if r["rule_code"] in ["SC-001", "SC-002", "SC-003"]]
        mock_response.data = filtered_rules

        # 设置 Mock 链
        mock_supabase.table.return_value = mock_query
        mock_query.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.or_.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.execute.return_value = mock_response

        with patch('app.services.sichuan_qc_service.get_supabase', return_value=mock_supabase):
            # 测试加载首次病程记录的规则
            rules = await service._load_rules_from_db("首次病程记录")

            # 验证结果
            assert len(rules) == 3  # SC-001, SC-002, SC-003
            assert all(r["rule_code"] in ["SC-001", "SC-002", "SC-003"] for r in rules)

            # 验证 Supabase 调用（使用数据库层面筛选）
            mock_supabase.table.assert_called_once_with("qc_rules")
            mock_query.select.assert_called_once_with("*")
            mock_query.eq.assert_called_once_with("is_active", True)
            mock_query.or_.assert_called_once()  # 验证使用了 or_ 筛选
            mock_query.limit.assert_called_once_with(1000)

    @pytest.mark.asyncio
    async def test_load_rules_from_db_success_with_app_filtering(self, service, mock_rules):
        """测试从数据库成功加载规则（回退到应用层筛选）"""
        # Mock Supabase 客户端
        mock_supabase = MagicMock()
        mock_query = MagicMock()
        mock_response = MagicMock()
        mock_response.data = mock_rules

        # 设置 Mock 链
        mock_supabase.table.return_value = mock_query
        mock_query.select.return_value = mock_query
        mock_query.eq.return_value = mock_query

        # 模拟数据库层面筛选失败（or_ 方法抛出异常）
        mock_query.or_.side_effect = Exception("Database filtering not supported")

        mock_query.limit.return_value = mock_query
        mock_query.execute.return_value = mock_response

        with patch('app.services.sichuan_qc_service.get_supabase', return_value=mock_supabase):
            # 测试加载首次病程记录的规则
            rules = await service._load_rules_from_db("首次病程记录")

            # 验证结果（应该回退到应用层筛选）
            assert len(rules) == 3  # SC-001, SC-002, SC-003
            assert all(r["rule_code"] in ["SC-001", "SC-002", "SC-003"] for r in rules)

            # 验证 Supabase 调用
            mock_supabase.table.assert_called_with("qc_rules")
            mock_query.select.assert_called_with("*")
            mock_query.eq.assert_called_with("is_active", True)

    @pytest.mark.asyncio
    async def test_load_rules_from_db_filter_by_document_type(self, service, mock_rules):
        """测试按文书类型筛选规则"""
        # Mock Supabase 客户端
        mock_supabase = MagicMock()
        mock_query = MagicMock()
        mock_response = MagicMock()

        # 模拟数据库层面筛选后的结果（只返回适用于手术记录的规则）
        filtered_rules = [r for r in mock_rules if r["rule_code"] == "SC-004"]
        mock_response.data = filtered_rules

        mock_supabase.table.return_value = mock_query
        mock_query.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.or_.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.execute.return_value = mock_response

        with patch('app.services.sichuan_qc_service.get_supabase', return_value=mock_supabase):
            # 测试加载手术记录的规则
            rules = await service._load_rules_from_db("手术记录")

            # 验证结果：只有 SC-004 适用于手术记录
            assert len(rules) == 1
            assert rules[0]["rule_code"] == "SC-004"

    @pytest.mark.asyncio
    async def test_load_rules_from_db_no_supabase(self, service):
        """测试 Supabase 不可用时的降级处理"""
        with patch('app.services.sichuan_qc_service.get_supabase', return_value=None):
            rules = await service._load_rules_from_db("首次病程记录")
            
            # 验证返回空列表
            assert rules == []

    @pytest.mark.asyncio
    async def test_load_rules_from_db_exception(self, service):
        """测试数据库异常时的降级处理"""
        mock_supabase = MagicMock()
        mock_supabase.table.side_effect = Exception("Database connection error")
        
        with patch('app.services.sichuan_qc_service.get_supabase', return_value=mock_supabase):
            rules = await service._load_rules_from_db("首次病程记录")
            
            # 验证返回空列表
            assert rules == []

    @pytest.mark.asyncio
    async def test_build_prompt_with_rules(self, service, mock_rules):
        """测试使用规则构建 Prompt"""
        content = "这是一份首次病程记录的内容..."
        document_type = "首次病程记录"
        
        # 使用前 3 条规则
        rules = mock_rules[:3]
        
        prompt = await service._build_prompt(rules, content, document_type)
        
        # 验证 Prompt 包含关键信息
        assert "资深病案质控专家" in prompt
        assert "首次病程记录" in prompt
        assert "适用规则数: 3" in prompt
        assert "病情分析完整性" in prompt
        assert "鉴别诊断完整性" in prompt
        assert "诊疗计划完整性" in prompt
        assert content in prompt

    @pytest.mark.asyncio
    async def test_build_prompt_without_rules(self, service):
        """测试无规则时构建 Prompt"""
        content = "这是一份病程记录的内容..."
        document_type = "病程记录"
        
        prompt = await service._build_prompt([], content, document_type)
        
        # 验证 Prompt 包含关键信息
        assert "资深病案质控专家" in prompt
        assert "病程记录" in prompt
        assert "适用规则数: 0" in prompt
        assert "未加载到具体规则" in prompt
        assert content in prompt

    @pytest.mark.asyncio
    async def test_evaluate_document_with_db_rules(self, service, mock_rules):
        """测试使用数据库规则进行质控评估"""
        # Mock Supabase 客户端
        mock_supabase = MagicMock()
        mock_query = MagicMock()
        mock_response = MagicMock()

        # 模拟数据库层面筛选后的结果（只返回适用于首次病程记录的规则）
        filtered_rules = [r for r in mock_rules if r["rule_code"] in ["SC-001", "SC-002", "SC-003"]]
        mock_response.data = filtered_rules

        mock_supabase.table.return_value = mock_query
        mock_query.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.or_.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.execute.return_value = mock_response

        # Mock LLM 客户端
        mock_llm_response = {
            "choices": [{"message": {"content": "质控分析结果..."}}],
            "usage": {"total_tokens": 1000},
            "_api_time": 2.5,
            "_mock": True
        }

        with patch('app.services.sichuan_qc_service.get_supabase', return_value=mock_supabase):
            with patch.object(service.client, 'generate', return_value=mock_llm_response):
                result = await service.evaluate_document(
                    document_id="test-001",
                    content="首次病程记录内容...",
                    document_type="首次病程记录"
                )

                # 验证结果
                assert result["document_id"] == "test-001"
                assert result["document_type"] == "首次病程记录"
                assert result["total_rules"] == 3  # SC-001, SC-002, SC-003
                assert len(result["applicable_rules"]) == 3
                assert "SC-001" in result["applicable_rules"]
                assert "SC-002" in result["applicable_rules"]
                assert "SC-003" in result["applicable_rules"]
                assert result["llm_output"] == "质控分析结果..."
                assert result["token_usage"]["total_tokens"] == 1000
                assert result["api_time"] == 2.5

    @pytest.mark.asyncio
    async def test_evaluate_document_fallback_to_empty_rules(self, service):
        """测试数据库不可用时的降级处理"""
        # Mock LLM 客户端
        mock_llm_response = {
            "choices": [{"message": {"content": "质控分析结果..."}}],
            "usage": {"total_tokens": 500},
            "_api_time": 1.5,
            "_mock": True
        }
        
        with patch('app.services.sichuan_qc_service.get_supabase', return_value=None):
            with patch.object(service.client, 'generate', return_value=mock_llm_response):
                result = await service.evaluate_document(
                    document_id="test-002",
                    content="病程记录内容...",
                    document_type="病程记录"
                )
                
                # 验证结果：规则数为 0，但仍然可以进行质控
                assert result["document_id"] == "test-002"
                assert result["document_type"] == "病程记录"
                assert result["total_rules"] == 0
                assert result["applicable_rules"] == []
                assert result["llm_output"] == "质控分析结果..."

    @pytest.mark.asyncio
    async def test_evaluate_multi_document_with_db_rules(self, service, mock_rules):
        """测试多文档质控使用数据库规则"""
        # Mock Supabase 客户端
        mock_supabase = MagicMock()

        # 使用计数器跟踪调用次数
        call_counter = {'count': 0}

        # 为不同的文书类型返回不同的规则
        def mock_table_call(table_name):
            mock_query = MagicMock()
            mock_response = MagicMock()

            # 根据调用次数返回不同的规则
            if call_counter['count'] == 0:  # 第一次调用：首次病程记录
                filtered_rules = [r for r in mock_rules if r["rule_code"] in ["SC-001", "SC-002", "SC-003"]]
                call_counter['count'] += 1
            else:  # 第二次调用：手术记录
                filtered_rules = [r for r in mock_rules if r["rule_code"] == "SC-004"]

            mock_response.data = filtered_rules

            mock_query.select.return_value = mock_query
            mock_query.eq.return_value = mock_query
            mock_query.or_.return_value = mock_query
            mock_query.limit.return_value = mock_query
            mock_query.execute.return_value = mock_response

            return mock_query

        mock_supabase.table.side_effect = mock_table_call

        # Mock LLM 客户端
        mock_llm_response = {
            "choices": [{"message": {"content": "质控分析结果..."}}],
            "usage": {"total_tokens": 1000},
            "_api_time": 2.5,
            "_mock": True
        }

        with patch('app.services.sichuan_qc_service.get_supabase', return_value=mock_supabase):
            with patch.object(service.client, 'generate', return_value=mock_llm_response):
                result = await service.evaluate_multi_document(
                    document_id="test-multi-001",
                    document_content="病历内容...",
                    document_types=["首次病程记录", "手术记录"]
                )

                # 验证结果
                assert result["document_id"] == "test-multi-001"
                assert "document_results" in result
                assert "首次病程记录" in result["document_results"]
                assert "手术记录" in result["document_results"]

                # 验证首次病程记录的规则数（SC-001, SC-002, SC-003）
                first_course_result = result["document_results"]["首次病程记录"]
                assert first_course_result["total_rules"] == 3

                # 验证手术记录的规则数（SC-004）
                surgery_result = result["document_results"]["手术记录"]
                assert surgery_result["total_rules"] == 1

