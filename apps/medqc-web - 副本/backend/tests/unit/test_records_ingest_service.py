"""
病历导入服务单元测试

测试 records_ingest_service 的核心功能：
- 分类映射获取
- 文档内容提取
- 病历文档保存
- LLM 解析结果导入
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime
import uuid

from app.services.records_ingest_service import (
    get_classification_mapping,
    infer_category_from_type,
    extract_document_content,
    save_medical_documents,
    ingest_llm_parse_result,
)


@pytest.mark.unit
@pytest.mark.service
class TestRecordsIngestService:
    """病历导入服务测试类"""

    @pytest.mark.asyncio
    async def test_get_classification_mapping_success(self):
        """测试获取分类映射成功"""
        mock_supabase = MagicMock()
        mock_categories_response = MagicMock()
        mock_categories_response.data = [
            {
                "id": "cat-1",
                "category_code": "admission_record",
                "category_name": "入院记录",
                "description": "入院记录分类",
            }
        ]

        mock_types_response = MagicMock()
        mock_types_response.data = [
            {
                "id": "type-1",
                "type_code": "admission_record",
                "type_name": "入院记录",
                "description": "入院记录类型",
                "category_id": "cat-1",
                "document_categories_test": {"category_code": "admission_record"},
            }
        ]

        with patch("app.services.records_ingest_service.get_supabase", return_value=mock_supabase):
            with patch("app.services.records_ingest_service.async_execute") as mock_execute:
                mock_execute.side_effect = [mock_categories_response, mock_types_response]

                result = await get_classification_mapping()

                assert "categories" in result
                assert "types" in result
                assert "admission_record" in result["categories"]
                assert result["categories"]["admission_record"]["category_name"] == "入院记录"

    @pytest.mark.asyncio
    async def test_get_classification_mapping_no_supabase(self):
        """测试 Supabase 不可用时的分类映射"""
        with patch("app.services.records_ingest_service.get_supabase", return_value=None):
            result = await get_classification_mapping()

            assert result == {"categories": {}, "types": {}}

    @pytest.mark.asyncio
    async def test_get_classification_mapping_error(self):
        """测试获取分类映射时发生错误"""
        mock_supabase = MagicMock()

        with patch("app.services.records_ingest_service.get_supabase", return_value=mock_supabase):
            with patch("app.services.records_ingest_service.async_execute", side_effect=Exception("Database error")):
                result = await get_classification_mapping()

                # 应该返回空映射而不是抛出异常
                assert result == {"categories": {}, "types": {}}

    def test_infer_category_from_type_admission(self):
        """测试推断入院记录类别"""
        result = infer_category_from_type("admission_record")
        assert result == "admission_record"

        result = infer_category_from_type("admission_diagnosis")
        assert result == "admission_record"

    def test_infer_category_from_type_progress(self):
        """测试推断病程记录类别"""
        result = infer_category_from_type("first_progress_note")
        assert result == "progress_note"

        result = infer_category_from_type("daily_progress_note")
        assert result == "progress_note"

    def test_infer_category_from_type_operation(self):
        """测试推断手术记录类别"""
        result = infer_category_from_type("operation_record")
        assert result == "operation_record"

        result = infer_category_from_type("preoperative_summary")
        assert result == "operation_record"

    def test_infer_category_from_type_examination(self):
        """测试推断检查报告类别"""
        result = infer_category_from_type("imaging_report")
        assert result == "examination_report"

        result = infer_category_from_type("laboratory_test")
        assert result == "examination_report"

    def test_infer_category_from_type_unknown(self):
        """测试推断未知类型"""
        result = infer_category_from_type("unknown_type")
        assert result == "progress_note"  # 默认值

    def test_extract_document_content_from_doc(self):
        """测试从文档对象提取内容"""
        doc = {"content": "这是文档内容"}
        result = extract_document_content(doc, "")

        assert result == "这是文档内容"

    def test_extract_document_content_from_full_content(self):
        """测试从 fullContent 字段提取内容"""
        doc = {"fullContent": "这是完整内容"}
        result = extract_document_content(doc, "")

        assert result == "这是完整内容"

    def test_extract_document_content_from_raw(self):
        """测试从原始内容中提取"""
        doc = {"title": "入院记录"}
        raw_content = "入院记录\n患者信息...\n\n病程记录\n..."

        result = extract_document_content(doc, raw_content)

        assert "入院记录" in result
        assert "患者信息" in result

    def test_extract_document_content_empty(self):
        """测试提取空内容"""
        doc = {}
        result = extract_document_content(doc, "")

        assert result == ""

    @pytest.mark.asyncio
    async def test_save_medical_documents_success(self):
        """测试保存病历文档成功"""
        mock_supabase = MagicMock()
        mock_delete_response = MagicMock()
        mock_delete_response.data = []
        mock_insert_response = MagicMock()
        mock_insert_response.data = [{"id": "doc-1"}]

        documents = [
            {
                "title": "入院记录",
                "type": "admission_record",
                "category": "admission_record",
                "content": "患者信息...",
                "confidence": 95,
            }
        ]

        with patch("app.services.records_ingest_service.get_supabase", return_value=mock_supabase):
            with patch("app.services.records_ingest_service.get_classification_mapping") as mock_mapping:
                mock_mapping.return_value = {
                    "categories": {"admission_record": "cat-1"},  # 简化结构
                    "types": {"admission_record.admission_record": "type-1"},  # 简化结构
                }
                with patch("app.services.records_ingest_service.async_execute") as mock_execute:
                    mock_execute.side_effect = [mock_delete_response, mock_insert_response]

                    # 应该不抛出异常
                    await save_medical_documents("record-123", documents)

    @pytest.mark.asyncio
    async def test_save_medical_documents_no_supabase(self):
        """测试 Supabase 不可用时保存文档"""
        with patch("app.services.records_ingest_service.get_supabase", return_value=None):
            # 应该直接返回，不抛出异常
            await save_medical_documents("record-123", [])

    @pytest.mark.asyncio
    async def test_save_medical_documents_empty_list(self):
        """测试保存空文档列表"""
        mock_supabase = MagicMock()

        with patch("app.services.records_ingest_service.get_supabase", return_value=mock_supabase):
            # 应该直接返回，不抛出异常
            await save_medical_documents("record-123", [])

    @pytest.mark.asyncio
    async def test_ingest_llm_parse_result_success(self):
        """测试导入 LLM 解析结果成功"""
        mock_supabase = MagicMock()
        mock_insert_response = MagicMock()
        mock_insert_response.data = [
            {
                "id": "record-123",
                "patient_info": {"name": "张三", "age": 65, "gender": "男"},
                "department": "心内科",
                "raw_text": "病历内容...",
                "status": "active",
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
                "created_by": "llm-system",
            }
        ]

        data = {
            "patient_name": "张三",
            "patient_age": 65,
            "patient_gender": "男",
            "department": "心内科",
            "content": "病历内容...",
            "documents": [],
        }

        with patch("app.services.records_ingest_service.get_supabase", return_value=mock_supabase):
            with patch("app.services.records_ingest_service.async_execute", return_value=mock_insert_response):
                with patch("app.services.records_ingest_service.save_medical_documents", new_callable=AsyncMock):
                    result = await ingest_llm_parse_result(data)

                    assert result is not None
                    assert result["id"] == "record-123"
                    assert result["patient_name"] == "张三"
                    assert result["patient_age"] == 65

    @pytest.mark.asyncio
    async def test_ingest_llm_parse_result_fallback_to_memory(self):
        """测试导入失败时回退到内存"""
        data = {
            "patient_name": "张三",
            "patient_age": 65,
            "patient_gender": "男",
            "department": "心内科",
            "content": "病历内容...",
        }

        with patch("app.services.records_ingest_service.get_supabase", return_value=None):
            with patch("app.services.records_ingest_service.medical_records_db", {}) as mock_db:
                result = await ingest_llm_parse_result(data)

                assert result is not None
                assert result["patient_name"] == "张三"
                assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_ingest_llm_parse_result_with_documents(self):
        """测试导入包含文档的 LLM 解析结果"""
        mock_supabase = MagicMock()
        mock_insert_response = MagicMock()
        mock_insert_response.data = [
            {
                "id": "record-123",
                "patient_info": {"name": "张三"},
                "department": "心内科",
                "raw_text": "病历内容...",
                "status": "active",
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
                "created_by": "llm-system",
            }
        ]

        data = {
            "patient_name": "张三",
            "content": "病历内容...",
            "documents": [
                {"title": "入院记录", "type": "admission_record", "content": "..."}
            ],
        }

        with patch("app.services.records_ingest_service.get_supabase", return_value=mock_supabase):
            with patch("app.services.records_ingest_service.async_execute", return_value=mock_insert_response):
                with patch("app.services.records_ingest_service.save_medical_documents", new_callable=AsyncMock) as mock_save:
                    result = await ingest_llm_parse_result(data)

                    # 验证调用了保存文档
                    mock_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_ingest_llm_parse_result_error_handling(self):
        """测试导入时的错误处理"""
        mock_supabase = MagicMock()

        data = {"patient_name": "张三"}

        with patch("app.services.records_ingest_service.get_supabase", return_value=mock_supabase):
            with patch("app.services.records_ingest_service.async_execute", side_effect=Exception("Database error")):
                with pytest.raises(Exception):
                    await ingest_llm_parse_result(data)

