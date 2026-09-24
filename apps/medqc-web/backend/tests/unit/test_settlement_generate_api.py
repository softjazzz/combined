"""
settlement /generate 和 /generate/qc 端点测试

测试要点：
- /generate 返回 is_draft=True, data_source='generated_from_frontpage'
- /generate/qc 返回 summary.{total,passed,failed,pass_rate}
- /generate/qc 的 draft 数据与 /generate 一致（共享 _generate_draft）
- 无 frontpage draft 时回退到 mr 伪 draft 不报错
"""

import pytest
from unittest.mock import AsyncMock, patch


class TestGenerateDraft:
    """测试共享辅助函数 _generate_draft（通过组装服务间接验证）。"""

    def test_assembly_service_returns_draft_markers(self):
        """生成结果必须包含 is_draft 和 data_source 标记。"""
        from app.services.settlement_assembly_service import SettlementAssemblyService
        svc = SettlementAssemblyService()
        result = svc.generate(patient_id="p001", visit_id="v001")
        assert result["is_draft"] is True
        assert result["data_source"] == "generated_from_frontpage"
        assert result["patient_id"] == "p001"
        assert result["visit_id"] == "v001"

    def test_assembly_service_generates_declaration_time(self):
        """自动生成申报时间。"""
        from app.services.settlement_assembly_service import SettlementAssemblyService
        svc = SettlementAssemblyService()
        result = svc.generate(patient_id="p001", visit_id="v001")
        assert result.get("declaration_time")  # 非空


class TestGenerateEndpoint:
    """测试 /generate 端点行为。"""

    @patch("app.routers.settlement._generate_draft")
    @pytest.mark.asyncio
    async def test_generate_calls_shared_helper(self, mock_gen):
        """/generate 端点应调用共享 _generate_draft。"""
        from app.routers.settlement import generate_settlement_from_frontpage

        mock_gen.return_value = {"is_draft": True, "data_source": "generated_from_frontpage"}
        result = await generate_settlement_from_frontpage("p001", "v001")
        mock_gen.assert_called_once_with("p001", "v001")
        assert result["is_draft"] is True


class TestGenerateQcEndpoint:
    """测试 /generate/qc 端点行为。"""

    @patch("app.routers.settlement._generate_draft")
    @pytest.mark.asyncio
    async def test_qc_uses_same_draft_as_generate(self, mock_gen):
        """/generate/qc 应使用与 /generate 完全相同的 _generate_draft。"""
        from app.routers.settlement import run_generated_settlement_qc

        mock_gen.return_value = {
            "is_draft": True,
            "data_source": "generated_from_frontpage",
            "patient_name": "张三",
        }
        with (
            patch("app.routers.settlement.default_workflow_queue_state_service.start_run", return_value="run-1"),
            patch("app.routers.settlement.default_workflow_queue_state_service.finish_success"),
            patch("app.routers.settlement.default_qc_persistence_service.persist_analysis", new_callable=AsyncMock),
        ):
            result = await run_generated_settlement_qc(
                "p001", "v001", current_user={"id": "test-user"}
            )
        mock_gen.assert_called_once_with("p001", "v001")

        # 验证 summary 结构与旧接口一致
        assert "summary" in result
        summary = result["summary"]
        assert "total" in summary
        assert "passed" in summary
        assert "failed" in summary
        assert "pass_rate" in summary
        assert "%" in summary["pass_rate"]

        # 验证 settlement 为 draft 本体
        assert result["settlement"]["is_draft"] is True
        assert result["settlement"]["data_source"] == "generated_from_frontpage"

    @patch("app.routers.settlement._generate_draft")
    @pytest.mark.asyncio
    async def test_qc_returns_results_list(self, mock_gen):
        """/generate/qc 返回具体规则校验结果列表。"""
        from app.routers.settlement import run_generated_settlement_qc

        mock_gen.return_value = {"is_draft": True, "data_source": "generated_from_frontpage"}
        with (
            patch("app.routers.settlement.default_workflow_queue_state_service.start_run", return_value="run-1"),
            patch("app.routers.settlement.default_workflow_queue_state_service.finish_success"),
            patch("app.routers.settlement.default_qc_persistence_service.persist_analysis", new_callable=AsyncMock),
        ):
            result = await run_generated_settlement_qc(
                "p001", "v001", current_user={"id": "test-user"}
            )
        assert "results" in result
        assert isinstance(result["results"], list)
        assert len(result["results"]) > 0
        # 每条结果都有必要字段
        for r in result["results"]:
            assert "rule_id" in r
            assert "passed" in r
            assert "severity" in r
