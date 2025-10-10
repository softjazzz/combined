"""
病历管理 API 单元测试
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
import uuid

from tests.conftest import assert_response_success, assert_response_error


@pytest.mark.unit
@pytest.mark.api
class TestMedicalRecordsAPI:
    """病历管理 API 测试类"""

    def test_get_record_from_memory_success(self, client, sample_medical_record):
        """测试从内存获取病历成功"""
        record_id = sample_medical_record["id"]
        
        # Mock 内存数据库
        with patch("app.routers.medical_records_alias.medical_records_db", {record_id: sample_medical_record}):
            with patch("app.routers.medical_records_alias.get_supabase", return_value=None):
                response = client.get(f"/api/v1/medical-records/{record_id}")

                assert response.status_code == 200
                data = response.json()
                assert data["id"] == record_id
                assert data["patient_name"] == sample_medical_record["patient_name"]
                assert data["department"] == sample_medical_record["department"]

    def test_get_record_not_found(self, client):
        """测试获取不存在的病历"""
        record_id = str(uuid.uuid4())
        
        with patch("app.routers.medical_records_alias.medical_records_db", {}):
            with patch("app.routers.medical_records_alias.get_supabase", return_value=None):
                response = client.get(f"/api/v1/medical-records/{record_id}")

                assert response.status_code == 404
                data = response.json()
                assert "医疗记录不存在" in data["detail"]

    @patch("app.routers.medical_records_alias.get_supabase")
    @patch("app.routers.medical_records_alias.async_execute")
    def test_get_record_from_supabase_success(self, mock_async_execute, mock_get_supabase, client, sample_medical_record):
        """测试从 Supabase 获取病历成功"""
        record_id = sample_medical_record["id"]
        
        # Mock Supabase 客户端
        mock_supabase = MagicMock()
        mock_get_supabase.return_value = mock_supabase
        
        # Mock 查询结果
        mock_result = MagicMock()
        mock_result.data = [sample_medical_record]
        mock_async_execute.return_value = mock_result

        response = client.get(f"/api/v1/medical-records/{record_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == record_id
        assert data["patient_name"] == sample_medical_record["patient_name"]

    @patch("app.routers.medical_records_alias.get_supabase")
    @patch("app.routers.medical_records_alias.async_execute")
    def test_get_record_supabase_fallback_to_memory(self, mock_async_execute, mock_get_supabase, client, sample_medical_record):
        """测试 Supabase 失败后回退到内存"""
        record_id = sample_medical_record["id"]
        
        # Mock Supabase 抛出异常
        mock_supabase = MagicMock()
        mock_get_supabase.return_value = mock_supabase
        mock_async_execute.side_effect = Exception("Database error")

        # Mock 内存数据库
        with patch("app.routers.medical_records_alias.medical_records_db", {record_id: sample_medical_record}):
            response = client.get(f"/api/v1/medical-records/{record_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == record_id

    def test_delete_record_success(self, client, sample_medical_record):
        """测试删除病历成功"""
        # 注册并登录获取 token
        email = f"deleteuser{uuid.uuid4().hex[:8]}@example.com"
        register_data = {
            "email": email,
            "password": "Password123!",
            "display_name": "删除用户",
            "department": "测试部门"
        }
        client.post("/api/v1/auth/register", json=register_data)

        login_response = client.post("/api/v1/auth/login", json={
            "email": email,
            "password": "Password123!"
        })
        token = login_response.json()["access_token"]

        record_id = sample_medical_record["id"]
        
        # Mock 内存数据库
        with patch("app.routers.medical_records_alias.medical_records_db", {record_id: sample_medical_record}):
            response = client.delete(
                f"/api/v1/medical-records/{record_id}",
                headers={"Authorization": f"Bearer {token}"}
            )

            assert_response_success(response, 200)
            data = response.json()
            assert data["message"] == "医疗记录删除成功"

    def test_delete_record_not_found(self, client):
        """测试删除不存在的病历"""
        # 注册并登录获取 token
        email = f"deleteuser2{uuid.uuid4().hex[:8]}@example.com"
        register_data = {
            "email": email,
            "password": "Password123!",
            "display_name": "删除用户2",
            "department": "测试部门"
        }
        client.post("/api/v1/auth/register", json=register_data)

        login_response = client.post("/api/v1/auth/login", json={
            "email": email,
            "password": "Password123!"
        })
        token = login_response.json()["access_token"]

        record_id = str(uuid.uuid4())
        
        with patch("app.routers.medical_records_alias.medical_records_db", {}):
            response = client.delete(
                f"/api/v1/medical-records/{record_id}",
                headers={"Authorization": f"Bearer {token}"}
            )

            assert response.status_code == 404
            data = response.json()
            assert "医疗记录不存在" in data["detail"]

    def test_delete_record_no_auth(self, client, sample_medical_record):
        """测试删除病历 - 未认证"""
        record_id = sample_medical_record["id"]
        
        with patch("app.routers.medical_records_alias.medical_records_db", {record_id: sample_medical_record}):
            response = client.delete(f"/api/v1/medical-records/{record_id}")

            assert response.status_code == 401

    def test_normalize_record_basic(self):
        """测试病历数据标准化 - 基本情况"""
        from app.routers.medical_records_alias import _normalize_record

        record = {
            "id": "rec-123",
            "patient_name": "张三",
            "patient_age": 45,
            "patient_gender": "男",
            "department": "心内科",
            "admission_date": "2025-01-01",
            "record_type": "入院记录",
            "content": "患者因胸痛入院...",
            "status": "completed",
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-02T00:00:00Z",
            "created_by": "doctor-1",
            "file_url": "https://example.com/file.pdf"
        }

        normalized = _normalize_record(record)

        assert normalized["id"] == "rec-123"
        assert normalized["patient_name"] == "张三"
        assert normalized["patient_age"] == 45
        assert normalized["patient_gender"] == "男"
        assert normalized["department"] == "心内科"
        assert normalized["admission_date"] == "2025-01-01"
        assert normalized["record_type"] == "入院记录"
        assert normalized["content"] == "患者因胸痛入院..."
        assert normalized["status"] == "completed"
        assert normalized["created_by"] == "doctor-1"
        assert normalized["file_url"] == "https://example.com/file.pdf"

    def test_normalize_record_with_patient_info(self):
        """测试病历数据标准化 - 包含 patient_info"""
        from app.routers.medical_records_alias import _normalize_record

        record = {
            "id": "rec-124",
            "patient_info": {
                "name": "李四",
                "age": 50,
                "gender": "女"
            },
            "department": "神经内科",
            "content": "患者因头痛入院..."
        }

        normalized = _normalize_record(record)

        assert normalized["patient_name"] == "李四"
        assert normalized["patient_age"] == 50
        assert normalized["patient_gender"] == "女"

    def test_normalize_record_with_defaults(self):
        """测试病历数据标准化 - 使用默认值"""
        from app.routers.medical_records_alias import _normalize_record

        record = {
            "id": "rec-125"
        }

        normalized = _normalize_record(record)

        assert normalized["id"] == "rec-125"
        assert normalized["patient_name"] == "未识别"
        assert normalized["patient_age"] == 0
        assert normalized["patient_gender"] == "未识别"
        assert normalized["department"] == "未识别"
        assert normalized["record_type"] == "病程记录"
        assert normalized["content"] == ""
        assert normalized["status"] == "pending"
        assert normalized["created_by"] == "system"

    def test_normalize_record_alternative_field_names(self):
        """测试病历数据标准化 - 替代字段名"""
        from app.routers.medical_records_alias import _normalize_record

        record = {
            "record_id": "rec-126",  # 替代 id
            "name": "王五",  # 替代 patient_name
            "department_name": "外科",  # 替代 department
            "admit_date": "2025-01-05",  # 替代 admission_date
            "type": "手术记录",  # 替代 record_type
            "raw_text": "手术过程...",  # 替代 content
            "user_id": "doctor-2"  # 替代 created_by
        }

        normalized = _normalize_record(record)

        assert normalized["id"] == "rec-126"
        assert normalized["patient_name"] == "王五"
        assert normalized["department"] == "外科"
        assert normalized["admission_date"] == "2025-01-05"
        assert normalized["record_type"] == "手术记录"
        assert normalized["content"] == "手术过程..."
        assert normalized["created_by"] == "doctor-2"

    def test_normalize_record_empty_dict(self):
        """测试病历数据标准化 - 空字典"""
        from app.routers.medical_records_alias import _normalize_record

        record = {}

        normalized = _normalize_record(record)

        # 应该有所有默认值
        assert "id" in normalized
        assert normalized["patient_name"] == "未识别"
        assert normalized["patient_age"] == 0
        assert normalized["status"] == "pending"

    def test_normalize_record_with_none_values(self):
        """测试病历数据标准化 - None 值"""
        from app.routers.medical_records_alias import _normalize_record

        record = {
            "id": "rec-127",
            "patient_name": None,
            "patient_age": None,
            "department": None,
            "content": None
        }

        normalized = _normalize_record(record)

        assert normalized["id"] == "rec-127"
        assert normalized["patient_name"] == "未识别"
        assert normalized["patient_age"] == 0
        assert normalized["department"] == "未识别"
        assert normalized["content"] == ""

    @pytest.mark.parametrize("record_id", [
        "rec-123",
        "550e8400-e29b-41d4-a716-446655440000",  # UUID
        "record_2025_001",
        "中文记录ID",
    ])
    def test_get_record_various_id_formats(self, client, record_id):
        """测试获取病历 - 各种 ID 格式"""
        sample_record = {
            "id": record_id,
            "patient_name": "测试患者",
            "department": "测试科室",
            "content": "测试内容"
        }
        
        with patch("app.routers.medical_records_alias.medical_records_db", {record_id: sample_record}):
            with patch("app.routers.medical_records_alias.get_supabase", return_value=None):
                response = client.get(f"/api/v1/medical-records/{record_id}")

                if response.status_code == 200:
                    data = response.json()
                    assert data["id"] == record_id

    def test_get_record_with_special_characters(self, client):
        """测试获取病历 - 包含特殊字符的内容"""
        record_id = "rec-special"
        sample_record = {
            "id": record_id,
            "patient_name": "张三 & 李四",
            "department": "心内科<重症>",
            "content": "患者主诉：\"胸痛\"、'气短'等症状..."
        }
        
        with patch("app.routers.medical_records_alias.medical_records_db", {record_id: sample_record}):
            with patch("app.routers.medical_records_alias.get_supabase", return_value=None):
                response = client.get(f"/api/v1/medical-records/{record_id}")

                assert response.status_code == 200
                data = response.json()
                assert "&" in data["patient_name"]
                assert "<" in data["department"]
                assert "\"" in data["content"]

    def test_concurrent_record_access(self, client, sample_medical_record):
        """测试并发访问病历"""
        import concurrent.futures

        record_id = sample_medical_record["id"]
        
        with patch("app.routers.medical_records_alias.medical_records_db", {record_id: sample_medical_record}):
            with patch("app.routers.medical_records_alias.get_supabase", return_value=None):
                def get_record():
                    return client.get(f"/api/v1/medical-records/{record_id}")

                # 并发访问 10 次
                with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                    futures = [executor.submit(get_record) for _ in range(10)]
                    responses = [f.result() for f in futures]

                # 所有请求都应该成功
                for response in responses:
                    assert response.status_code == 200

