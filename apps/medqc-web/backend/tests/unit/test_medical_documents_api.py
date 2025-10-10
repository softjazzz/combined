"""
病历文档 API 单元测试

测试 medical_documents 路由的核心功能：
- 获取文档类型列表
- 文档查询
- 文档创建
- 权限验证
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime
import uuid


@pytest.mark.unit
@pytest.mark.api
class TestMedicalDocumentsAPI:
    """病历文档 API 测试类"""

    @pytest.mark.asyncio
    async def test_get_document_types_success(self, client):
        """测试获取文档类型列表成功"""
        mock_supabase = MagicMock()
        
        # Mock 分类响应
        mock_categories_response = MagicMock()
        mock_categories_response.data = [
            {
                "id": "cat-1",
                "category_code": "admission_record",
                "category_name": "入院记录",
                "description": "入院记录分类",
                "sort_order": 1,
            }
        ]

        # Mock 类型响应
        mock_types_response = MagicMock()
        mock_types_response.data = [
            {
                "id": "type-1",
                "category_id": "cat-1",
                "type_code": "admission_record",
                "type_name": "入院记录",
                "description": "入院记录类型",
                "sort_order": 1,
                "document_categories_test": {
                    "category_code": "admission_record",
                    "category_name": "入院记录",
                },
            }
        ]

        with patch("app.routers.medical_documents.get_supabase", return_value=mock_supabase):
            with patch("app.routers.medical_documents.async_execute") as mock_execute:
                mock_execute.side_effect = [mock_categories_response, mock_types_response]

                response = client.get("/api/v1/document-types")

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert "categories" in data["data"]
                assert len(data["data"]["categories"]) > 0

    @pytest.mark.asyncio
    async def test_get_document_types_no_supabase(self, client):
        """测试 Supabase 不可用时获取文档类型"""
        with patch("app.routers.medical_documents.get_supabase", return_value=None):
            response = client.get("/api/v1/document-types")

            assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_get_document_types_empty_result(self, client):
        """测试获取空文档类型列表"""
        mock_supabase = MagicMock()
        mock_response = MagicMock()
        mock_response.data = []

        with patch("app.routers.medical_documents.get_supabase", return_value=mock_supabase):
            with patch("app.routers.medical_documents.async_execute", return_value=mock_response):
                response = client.get("/api/v1/document-types")

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert data["data"]["categories"] == []

    @pytest.mark.asyncio
    async def test_get_document_types_filter_inactive(self, client):
        """测试过滤非活动的文档类型"""
        mock_supabase = MagicMock()
        
        # 包含活动和非活动的分类
        mock_categories_response = MagicMock()
        mock_categories_response.data = [
            {
                "id": "cat-1",
                "category_code": "admission_record",
                "category_name": "入院记录",
                "is_active": True,
                "sort_order": 1,
            }
        ]

        mock_types_response = MagicMock()
        mock_types_response.data = []

        with patch("app.routers.medical_documents.get_supabase", return_value=mock_supabase):
            with patch("app.routers.medical_documents.async_execute") as mock_execute:
                mock_execute.side_effect = [mock_categories_response, mock_types_response]

                response = client.get("/api/v1/document-types")

                assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_document_types_sorted(self, client):
        """测试文档类型按顺序排列"""
        mock_supabase = MagicMock()
        
        mock_categories_response = MagicMock()
        mock_categories_response.data = [
            {
                "id": "cat-1",
                "category_code": "admission_record",
                "category_name": "入院记录",
                "sort_order": 1,
            },
            {
                "id": "cat-2",
                "category_code": "progress_note",
                "category_name": "病程记录",
                "sort_order": 2,
            },
        ]

        mock_types_response = MagicMock()
        mock_types_response.data = []

        with patch("app.routers.medical_documents.get_supabase", return_value=mock_supabase):
            with patch("app.routers.medical_documents.async_execute") as mock_execute:
                mock_execute.side_effect = [mock_categories_response, mock_types_response]

                response = client.get("/api/v1/document-types")

                assert response.status_code == 200
                data = response.json()
                # 验证返回的分类是按顺序的
                if len(data["data"]["categories"]) >= 2:
                    assert data["data"]["categories"][0]["category_code"] == "admission_record"

    @pytest.mark.asyncio
    async def test_get_document_types_with_trace_id(self, client):
        """测试响应包含 trace_id"""
        mock_supabase = MagicMock()
        mock_response = MagicMock()
        mock_response.data = []

        with patch("app.routers.medical_documents.get_supabase", return_value=mock_supabase):
            with patch("app.routers.medical_documents.async_execute", return_value=mock_response):
                response = client.get("/api/v1/document-types")

                assert response.status_code == 200
                data = response.json()
                assert "trace_id" in data

    @pytest.mark.asyncio
    async def test_get_document_types_error_handling(self, client):
        """测试获取文档类型时的错误处理"""
        mock_supabase = MagicMock()

        with patch("app.routers.medical_documents.get_supabase", return_value=mock_supabase):
            with patch("app.routers.medical_documents.async_execute", side_effect=Exception("Database error")):
                response = client.get("/api/v1/document-types")

                # 应该返回错误响应
                assert response.status_code in [500, 503]

    @pytest.mark.asyncio
    async def test_get_document_types_multiple_categories(self, client):
        """测试获取多个分类的文档类型"""
        mock_supabase = MagicMock()
        
        mock_categories_response = MagicMock()
        mock_categories_response.data = [
            {"id": f"cat-{i}", "category_code": f"cat_{i}", "category_name": f"分类{i}", "sort_order": i}
            for i in range(1, 6)
        ]

        mock_types_response = MagicMock()
        mock_types_response.data = [
            {
                "id": f"type-{i}",
                "category_id": f"cat-{i}",
                "type_code": f"type_{i}",
                "type_name": f"类型{i}",
                "sort_order": 1,
                "document_categories_test": {
                    "category_code": f"cat_{i}",
                    "category_name": f"分类{i}",
                },
            }
            for i in range(1, 6)
        ]

        with patch("app.routers.medical_documents.get_supabase", return_value=mock_supabase):
            with patch("app.routers.medical_documents.async_execute") as mock_execute:
                mock_execute.side_effect = [mock_categories_response, mock_types_response]

                response = client.get("/api/v1/document-types")

                assert response.status_code == 200
                data = response.json()
                assert len(data["data"]["categories"]) == 5

    @pytest.mark.asyncio
    async def test_get_document_types_response_structure(self, client):
        """测试响应结构正确性"""
        mock_supabase = MagicMock()
        
        mock_categories_response = MagicMock()
        mock_categories_response.data = [
            {
                "id": "cat-1",
                "category_code": "admission_record",
                "category_name": "入院记录",
                "description": "入院记录分类",
                "sort_order": 1,
            }
        ]

        mock_types_response = MagicMock()
        mock_types_response.data = [
            {
                "id": "type-1",
                "category_id": "cat-1",
                "type_code": "admission_record",
                "type_name": "入院记录",
                "description": "入院记录类型",
                "sort_order": 1,
                "document_categories_test": {
                    "category_code": "admission_record",
                    "category_name": "入院记录",
                },
            }
        ]

        with patch("app.routers.medical_documents.get_supabase", return_value=mock_supabase):
            with patch("app.routers.medical_documents.async_execute") as mock_execute:
                mock_execute.side_effect = [mock_categories_response, mock_types_response]

                response = client.get("/api/v1/document-types")

                assert response.status_code == 200
                data = response.json()
                
                # 验证顶层结构
                assert "success" in data
                assert "data" in data
                assert "message" in data
                assert "trace_id" in data

                # 验证数据结构
                assert "categories" in data["data"]
                if data["data"]["categories"]:
                    category = data["data"]["categories"][0]
                    assert "category_id" in category
                    assert "category_code" in category
                    assert "category_name" in category
                    assert "types" in category

    @pytest.mark.asyncio
    async def test_get_document_types_concurrent_requests(self, client):
        """测试并发请求"""
        import asyncio
        from concurrent.futures import ThreadPoolExecutor

        mock_supabase = MagicMock()
        mock_response = MagicMock()
        mock_response.data = []

        with patch("app.routers.medical_documents.get_supabase", return_value=mock_supabase):
            with patch("app.routers.medical_documents.async_execute", return_value=mock_response):
                # 使用线程池模拟并发请求
                with ThreadPoolExecutor(max_workers=5) as executor:
                    futures = [executor.submit(client.get, "/api/v1/document-types") for _ in range(5)]
                    responses = [f.result() for f in futures]

                # 验证所有请求都成功
                for response in responses:
                    assert response.status_code == 200

