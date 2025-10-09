"""
申诉流程 API 单元测试
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
import uuid

from tests.conftest import assert_response_success, assert_response_error


@pytest.mark.unit
@pytest.mark.api
@pytest.mark.appeals
class TestAppealsAPI:
    """申诉 API 测试类"""

    def test_create_appeal_success(self, client, mock_supabase, mock_current_user, sample_appeal):
        """测试创建申诉成功"""
        # Mock 数据库查询
        mock_result = MagicMock()
        mock_result.data = [sample_appeal]

        # Mock Supabase 客户端
        with patch("app.routers.appeals.get_supabase", return_value=mock_supabase):
            with patch("app.routers.appeals.get_current_user", return_value=mock_current_user):
                # Mock QC 结果存在
                mock_supabase.table("qc_results").select("id").eq.return_value.execute.return_value.data = [{"id": sample_appeal["qc_result_id"]}]
                # Mock 病历存在
                mock_supabase.table("medical_records").select("id").eq.return_value.execute.return_value.data = [{"id": sample_appeal["record_id"]}]
                # Mock 插入成功
                mock_supabase.table("qc_appeals").insert.return_value.execute.return_value = mock_result

                # 发送请求
                response = client.post(
                    "/api/v1/appeals",
                    json={
                        "qc_result_id": sample_appeal["qc_result_id"],
                        "record_id": sample_appeal["record_id"],
                        "appeal_type": "defect",
                        "reason": "测试申诉理由",
                        "priority": "medium"
                    }
                )

                # 验证响应
                assert_response_success(response, 200)
                data = response.json()
                assert data["data"]["appeal_type"] == "defect"

    def test_create_appeal_qc_result_not_found(self, client, mock_supabase, mock_current_user):
        """测试创建申诉 - 质控结果不存在"""
        with patch("app.routers.appeals.get_supabase", return_value=mock_supabase):
            with patch("app.routers.appeals.get_current_user", return_value=mock_current_user):
                # Mock QC 结果不存在
                mock_supabase.table("qc_results").select("id").eq.return_value.execute.return_value.data = []

                response = client.post(
                    "/api/v1/appeals",
                    json={
                        "qc_result_id": str(uuid.uuid4()),
                        "record_id": str(uuid.uuid4()),
                        "appeal_type": "defect",
                        "reason": "测试申诉理由",
                        "priority": "medium"
                    }
                )

                # 验证响应
                assert_response_error(response, 404)

    def test_list_appeals(self, client, mock_supabase, mock_current_user, sample_appeal):
        """测试获取申诉列表"""
        # Mock 查询结果
        mock_result = MagicMock()
        mock_result.data = [sample_appeal]
        mock_result.count = 1

        with patch("app.routers.appeals.get_supabase", return_value=mock_supabase):
            with patch("app.routers.appeals.get_current_user", return_value=mock_current_user):
                mock_supabase.table("qc_appeals").select.return_value.order.return_value.range.return_value.execute.return_value = mock_result

                response = client.get("/api/v1/appeals?page=1&page_size=20")

                # 验证响应
                assert_response_success(response, 200)
                data = response.json()
                assert data["data"]["total"] == 1
                assert len(data["data"]["items"]) == 1

    def test_get_appeal_detail(self, client, mock_supabase, mock_current_user, sample_appeal):
        """测试获取申诉详情"""
        appeal_id = sample_appeal["id"]

        # Mock 查询结果
        mock_appeal_result = MagicMock()
        mock_appeal_result.data = [sample_appeal]

        mock_reviews_result = MagicMock()
        mock_reviews_result.data = []

        with patch("app.routers.appeals.get_supabase", return_value=mock_supabase):
            with patch("app.routers.appeals.get_current_user", return_value=mock_current_user):
                mock_supabase.table("qc_appeals").select.return_value.eq.return_value.execute.return_value = mock_appeal_result
                mock_supabase.table("qc_appeal_reviews").select.return_value.eq.return_value.order.return_value.execute.return_value = mock_reviews_result

                response = client.get(f"/api/v1/appeals/{appeal_id}")

                # 验证响应
                assert_response_success(response, 200)
                data = response.json()
                assert data["data"]["id"] == appeal_id
                assert "reviews" in data["data"]

    def test_get_appeal_not_found(self, client, mock_supabase, mock_current_user):
        """测试获取不存在的申诉"""
        appeal_id = str(uuid.uuid4())

        # Mock 查询结果为空
        mock_result = MagicMock()
        mock_result.data = []

        with patch("app.routers.appeals.get_supabase", return_value=mock_supabase):
            with patch("app.routers.appeals.get_current_user", return_value=mock_current_user):
                mock_supabase.table("qc_appeals").select.return_value.eq.return_value.execute.return_value = mock_result

                response = client.get(f"/api/v1/appeals/{appeal_id}")

                # 验证响应
                assert_response_error(response, 404)

    def test_update_appeal_success(self, client, mock_supabase, mock_current_user, sample_appeal):
        """测试更新申诉成功"""
        appeal_id = sample_appeal["id"]
        sample_appeal["appellant_id"] = mock_current_user["id"]  # 确保是申诉人

        # Mock 查询和更新
        mock_existing_result = MagicMock()
        mock_existing_result.data = [sample_appeal]

        updated_appeal = sample_appeal.copy()
        updated_appeal["reason"] = "更新后的申诉理由"
        mock_update_result = MagicMock()
        mock_update_result.data = [updated_appeal]

        with patch("app.routers.appeals.get_supabase", return_value=mock_supabase):
            with patch("app.routers.appeals.get_current_user", return_value=mock_current_user):
                mock_supabase.table("qc_appeals").select.return_value.eq.return_value.execute.return_value = mock_existing_result
                mock_supabase.table("qc_appeals").update.return_value.eq.return_value.execute.return_value = mock_update_result

                response = client.put(
                    f"/api/v1/appeals/{appeal_id}",
                    json={"reason": "更新后的申诉理由"}
                )

                # 验证响应
                assert_response_success(response, 200)
                data = response.json()
                assert data["data"]["reason"] == "更新后的申诉理由"

    def test_update_appeal_forbidden(self, client, mock_supabase, mock_current_user, sample_appeal):
        """测试更新申诉 - 非申诉人"""
        appeal_id = sample_appeal["id"]
        sample_appeal["appellant_id"] = str(uuid.uuid4())  # 不是当前用户

        # Mock 查询
        mock_existing_result = MagicMock()
        mock_existing_result.data = [sample_appeal]

        with patch("app.routers.appeals.get_supabase", return_value=mock_supabase):
            with patch("app.routers.appeals.get_current_user", return_value=mock_current_user):
                mock_supabase.table("qc_appeals").select.return_value.eq.return_value.execute.return_value = mock_existing_result

                response = client.put(
                    f"/api/v1/appeals/{appeal_id}",
                    json={"reason": "更新后的申诉理由"}
                )

                # 验证响应
                assert_response_error(response, 403)

    def test_withdraw_appeal_success(self, client, mock_supabase, mock_current_user, sample_appeal):
        """测试撤回申诉成功"""
        appeal_id = sample_appeal["id"]
        sample_appeal["appellant_id"] = mock_current_user["id"]

        # Mock 查询和更新
        mock_existing_result = MagicMock()
        mock_existing_result.data = [sample_appeal]

        withdrawn_appeal = sample_appeal.copy()
        withdrawn_appeal["status"] = "withdrawn"
        mock_update_result = MagicMock()
        mock_update_result.data = [withdrawn_appeal]

        with patch("app.routers.appeals.get_supabase", return_value=mock_supabase):
            with patch("app.routers.appeals.get_current_user", return_value=mock_current_user):
                mock_supabase.table("qc_appeals").select.return_value.eq.return_value.execute.return_value = mock_existing_result
                mock_supabase.table("qc_appeals").update.return_value.eq.return_value.execute.return_value = mock_update_result

                response = client.post(
                    f"/api/v1/appeals/{appeal_id}/withdraw",
                    json={"reason": "撤回原因"}
                )

                # 验证响应
                assert_response_success(response, 200)
                data = response.json()
                assert data["data"]["status"] == "withdrawn"

    def test_review_appeal_approve(self, client, mock_supabase, mock_current_user, sample_appeal):
        """测试审核申诉 - 批准"""
        appeal_id = sample_appeal["id"]
        sample_appeal["status"] = "pending"

        # Mock 查询和更新
        mock_existing_result = MagicMock()
        mock_existing_result.data = [sample_appeal]

        approved_appeal = sample_appeal.copy()
        approved_appeal["status"] = "approved"
        mock_update_result = MagicMock()
        mock_update_result.data = [approved_appeal]

        mock_review_result = MagicMock()
        mock_review_result.data = [{"id": str(uuid.uuid4())}]

        with patch("app.routers.appeals.get_supabase", return_value=mock_supabase):
            with patch("app.routers.appeals.get_current_user", return_value=mock_current_user):
                mock_supabase.table("qc_appeals").select.return_value.eq.return_value.execute.return_value = mock_existing_result
                mock_supabase.table("qc_appeal_reviews").insert.return_value.execute.return_value = mock_review_result
                mock_supabase.table("qc_appeals").update.return_value.eq.return_value.execute.return_value = mock_update_result

                response = client.post(
                    f"/api/v1/appeals/{appeal_id}/review",
                    json={
                        "action": "approve",
                        "comment": "申诉合理，予以批准",
                        "resolution": "已批准"
                    }
                )

                # 验证响应
                assert_response_success(response, 200)
                data = response.json()
                assert data["data"]["status"] == "approved"

    def test_get_appeal_statistics(self, client, mock_supabase, mock_current_user):
        """测试获取申诉统计"""
        # Mock 统计数据
        mock_result = MagicMock()
        mock_result.data = [
            {
                "status": "pending",
                "appeal_type": "defect",
                "priority": "medium",
                "count": 10,
                "avg_resolution_time_seconds": 86400
            },
            {
                "status": "approved",
                "appeal_type": "score",
                "priority": "high",
                "count": 5,
                "avg_resolution_time_seconds": 43200
            }
        ]

        with patch("app.routers.appeals.get_supabase", return_value=mock_supabase):
            with patch("app.routers.appeals.get_current_user", return_value=mock_current_user):
                mock_supabase.table("qc_appeals_statistics").select.return_value.execute.return_value = mock_result

                response = client.get("/api/v1/appeals/statistics/summary")

                # 验证响应
                assert_response_success(response, 200)
                data = response.json()
                assert "total" in data["data"]
                assert "pending" in data["data"]
                assert "approved" in data["data"]
                assert "avg_resolution_time_hours" in data["data"]


@pytest.mark.unit
@pytest.mark.appeals
class TestAppealsValidation:
    """申诉数据验证测试"""

    def test_create_appeal_invalid_reason_too_short(self, client, mock_current_user):
        """测试创建申诉 - 申诉理由太短"""
        with patch("app.routers.appeals.get_current_user", return_value=mock_current_user):
            response = client.post(
                "/api/v1/appeals",
                json={
                    "qc_result_id": str(uuid.uuid4()),
                    "record_id": str(uuid.uuid4()),
                    "appeal_type": "defect",
                    "reason": "短",  # 太短
                    "priority": "medium"
                }
            )

            # 验证响应 - 应该返回验证错误
            assert response.status_code == 422

    def test_create_appeal_invalid_type(self, client, mock_current_user):
        """测试创建申诉 - 无效的申诉类型"""
        with patch("app.routers.appeals.get_current_user", return_value=mock_current_user):
            response = client.post(
                "/api/v1/appeals",
                json={
                    "qc_result_id": str(uuid.uuid4()),
                    "record_id": str(uuid.uuid4()),
                    "appeal_type": "invalid_type",  # 无效类型
                    "reason": "测试申诉理由",
                    "priority": "medium"
                }
            )

            # 验证响应 - 应该返回验证错误
            assert response.status_code == 422
