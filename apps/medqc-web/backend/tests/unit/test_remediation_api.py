"""
整改跟踪 API 单元测试
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import uuid

from tests.conftest import assert_response_success, assert_response_error


@pytest.mark.unit
@pytest.mark.api
@pytest.mark.remediation
class TestRemediationAPI:
    """整改跟踪 API 测试类"""

    def test_create_remediation_task_success(self, client, mock_supabase, mock_current_user, sample_remediation_task):
        """测试创建整改任务成功"""
        # Mock 数据库查询
        mock_result = MagicMock()
        mock_result.data = [sample_remediation_task]

        # Mock Supabase 客户端
        with patch("app.routers.remediation.get_supabase", return_value=mock_supabase):
            with patch("app.routers.remediation.get_current_user", return_value=mock_current_user):
                # Mock QC 结果存在
                mock_supabase.table("qc_results").select("id").eq.return_value.execute.return_value.data = [{"id": sample_remediation_task["qc_result_id"]}]
                # Mock 病历存在
                mock_supabase.table("medical_records").select("id").eq.return_value.execute.return_value.data = [{"id": sample_remediation_task["record_id"]}]
                # Mock 插入成功
                mock_supabase.table("qc_remediation_tasks").insert.return_value.execute.return_value = mock_result

                # 发送请求
                response = client.post(
                    "/api/v1/remediation",
                    json={
                        "qc_result_id": sample_remediation_task["qc_result_id"],
                        "record_id": sample_remediation_task["record_id"],
                        "defect_type": "incomplete_record",
                        "defect_description": "入院记录不完整",
                        "remediation_requirement": "补充完整入院记录",
                        "deadline": (datetime.utcnow() + timedelta(days=7)).isoformat(),
                        "assignee_id": str(uuid.uuid4()),
                        "assignee_name": "张医生",
                        "priority": "medium"
                    }
                )

                # 验证响应
                assert_response_success(response, 200)
                data = response.json()
                assert data["data"]["defect_type"] == "incomplete_record"

    def test_create_remediation_task_qc_result_not_found(self, client, mock_supabase, mock_current_user):
        """测试创建整改任务 - 质控结果不存在"""
        with patch("app.routers.remediation.get_supabase", return_value=mock_supabase):
            with patch("app.routers.remediation.get_current_user", return_value=mock_current_user):
                # Mock QC 结果不存在
                mock_supabase.table("qc_results").select("id").eq.return_value.execute.return_value.data = []

                response = client.post(
                    "/api/v1/remediation",
                    json={
                        "qc_result_id": str(uuid.uuid4()),
                        "record_id": str(uuid.uuid4()),
                        "defect_type": "incomplete_record",
                        "defect_description": "入院记录不完整",
                        "remediation_requirement": "补充完整入院记录",
                        "assignee_id": str(uuid.uuid4()),
                        "assignee_name": "张医生",
                        "priority": "medium"
                    }
                )

                # 验证响应
                assert_response_error(response, 404)

    def test_list_remediation_tasks(self, client, mock_supabase, mock_current_user, sample_remediation_task):
        """测试获取整改任务列表"""
        # Mock 查询结果
        mock_result = MagicMock()
        mock_result.data = [sample_remediation_task]
        mock_result.count = 1

        with patch("app.routers.remediation.get_supabase", return_value=mock_supabase):
            with patch("app.routers.remediation.get_current_user", return_value=mock_current_user):
                mock_supabase.table("qc_remediation_tasks").select.return_value.order.return_value.range.return_value.execute.return_value = mock_result

                response = client.get("/api/v1/remediation?page=1&page_size=20")

                # 验证响应
                assert_response_success(response, 200)
                data = response.json()
                assert data["data"]["total"] == 1
                assert len(data["data"]["items"]) == 1

    def test_list_remediation_tasks_filter_by_status(self, client, mock_supabase, mock_current_user, sample_remediation_task):
        """测试按状态过滤整改任务"""
        # Mock 查询结果
        mock_result = MagicMock()
        mock_result.data = [sample_remediation_task]
        mock_result.count = 1

        with patch("app.routers.remediation.get_supabase", return_value=mock_supabase):
            with patch("app.routers.remediation.get_current_user", return_value=mock_current_user):
                mock_supabase.table("qc_remediation_tasks").select.return_value.eq.return_value.order.return_value.range.return_value.execute.return_value = mock_result

                response = client.get("/api/v1/remediation?status=pending&page=1&page_size=20")

                # 验证响应
                assert_response_success(response, 200)
                data = response.json()
                assert data["data"]["total"] == 1

    def test_get_remediation_task_detail(self, client, mock_supabase, mock_current_user, sample_remediation_task):
        """测试获取整改任务详情"""
        task_id = sample_remediation_task["id"]

        # Mock 查询结果
        mock_task_result = MagicMock()
        mock_task_result.data = [sample_remediation_task]

        mock_history_result = MagicMock()
        mock_history_result.data = []

        with patch("app.routers.remediation.get_supabase", return_value=mock_supabase):
            with patch("app.routers.remediation.get_current_user", return_value=mock_current_user):
                mock_supabase.table("qc_remediation_tasks").select.return_value.eq.return_value.execute.return_value = mock_task_result
                mock_supabase.table("qc_remediation_history").select.return_value.eq.return_value.order.return_value.execute.return_value = mock_history_result

                response = client.get(f"/api/v1/remediation/{task_id}")

                # 验证响应
                assert_response_success(response, 200)
                data = response.json()
                assert data["data"]["id"] == task_id
                assert "history" in data["data"]

    def test_get_remediation_task_not_found(self, client, mock_supabase, mock_current_user):
        """测试获取不存在的整改任务"""
        task_id = str(uuid.uuid4())

        # Mock 查询结果为空
        mock_result = MagicMock()
        mock_result.data = []

        with patch("app.routers.remediation.get_supabase", return_value=mock_supabase):
            with patch("app.routers.remediation.get_current_user", return_value=mock_current_user):
                mock_supabase.table("qc_remediation_tasks").select.return_value.eq.return_value.execute.return_value = mock_result

                response = client.get(f"/api/v1/remediation/{task_id}")

                # 验证响应
                assert_response_error(response, 404)

    def test_update_remediation_task_success(self, client, mock_supabase, mock_current_user, sample_remediation_task):
        """测试更新整改任务成功"""
        task_id = sample_remediation_task["id"]
        sample_remediation_task["creator_id"] = mock_current_user["id"]  # 确保是创建人

        # Mock 查询和更新
        mock_existing_result = MagicMock()
        mock_existing_result.data = [sample_remediation_task]

        updated_task = sample_remediation_task.copy()
        updated_task["remediation_requirement"] = "更新后的整改要求"
        mock_update_result = MagicMock()
        mock_update_result.data = [updated_task]

        with patch("app.routers.remediation.get_supabase", return_value=mock_supabase):
            with patch("app.routers.remediation.get_current_user", return_value=mock_current_user):
                mock_supabase.table("qc_remediation_tasks").select.return_value.eq.return_value.execute.return_value = mock_existing_result
                mock_supabase.table("qc_remediation_tasks").update.return_value.eq.return_value.execute.return_value = mock_update_result

                response = client.put(
                    f"/api/v1/remediation/{task_id}",
                    json={"remediation_requirement": "更新后的整改要求"}
                )

                # 验证响应
                assert_response_success(response, 200)
                data = response.json()
                assert data["data"]["remediation_requirement"] == "更新后的整改要求"

    def test_update_remediation_task_forbidden(self, client, mock_supabase, mock_current_user, sample_remediation_task):
        """测试更新整改任务 - 非创建人"""
        task_id = sample_remediation_task["id"]
        sample_remediation_task["creator_id"] = str(uuid.uuid4())  # 不是当前用户

        # Mock 查询
        mock_existing_result = MagicMock()
        mock_existing_result.data = [sample_remediation_task]

        with patch("app.routers.remediation.get_supabase", return_value=mock_supabase):
            with patch("app.routers.remediation.get_current_user", return_value=mock_current_user):
                mock_supabase.table("qc_remediation_tasks").select.return_value.eq.return_value.execute.return_value = mock_existing_result

                response = client.put(
                    f"/api/v1/remediation/{task_id}",
                    json={"remediation_requirement": "更新后的整改要求"}
                )

                # 验证响应
                assert_response_error(response, 403)

    def test_submit_remediation_success(self, client, mock_supabase, mock_current_user, sample_remediation_task):
        """测试提交整改成功"""
        task_id = sample_remediation_task["id"]
        sample_remediation_task["assignee_id"] = mock_current_user["id"]
        sample_remediation_task["status"] = "in_progress"

        # Mock 查询和更新
        mock_existing_result = MagicMock()
        mock_existing_result.data = [sample_remediation_task]

        submitted_task = sample_remediation_task.copy()
        submitted_task["status"] = "submitted"
        mock_update_result = MagicMock()
        mock_update_result.data = [submitted_task]

        with patch("app.routers.remediation.get_supabase", return_value=mock_supabase):
            with patch("app.routers.remediation.get_current_user", return_value=mock_current_user):
                mock_supabase.table("qc_remediation_tasks").select.return_value.eq.return_value.execute.return_value = mock_existing_result
                mock_supabase.table("qc_remediation_tasks").update.return_value.eq.return_value.execute.return_value = mock_update_result

                response = client.post(
                    f"/api/v1/remediation/{task_id}/submit",
                    json={
                        "remediation_result": "已完成整改",
                        "remediation_evidence": "见附件截图"
                    }
                )

                # 验证响应
                assert_response_success(response, 200)
                data = response.json()
                assert data["data"]["status"] == "submitted"

    def test_submit_remediation_forbidden(self, client, mock_supabase, mock_current_user, sample_remediation_task):
        """测试提交整改 - 非任务负责人"""
        task_id = sample_remediation_task["id"]
        sample_remediation_task["assignee_id"] = str(uuid.uuid4())  # 不是当前用户

        # Mock 查询
        mock_existing_result = MagicMock()
        mock_existing_result.data = [sample_remediation_task]

        with patch("app.routers.remediation.get_supabase", return_value=mock_supabase):
            with patch("app.routers.remediation.get_current_user", return_value=mock_current_user):
                mock_supabase.table("qc_remediation_tasks").select.return_value.eq.return_value.execute.return_value = mock_existing_result

                response = client.post(
                    f"/api/v1/remediation/{task_id}/submit",
                    json={
                        "remediation_result": "已完成整改",
                        "remediation_evidence": "见附件截图"
                    }
                )

                # 验证响应
                assert_response_error(response, 403)

    def test_review_remediation_approve(self, client, mock_supabase, mock_current_user, sample_remediation_task):
        """测试审核整改 - 批准"""
        task_id = sample_remediation_task["id"]
        sample_remediation_task["status"] = "submitted"

        # Mock 查询和更新
        mock_existing_result = MagicMock()
        mock_existing_result.data = [sample_remediation_task]

        approved_task = sample_remediation_task.copy()
        approved_task["status"] = "approved"
        mock_update_result = MagicMock()
        mock_update_result.data = [approved_task]

        with patch("app.routers.remediation.get_supabase", return_value=mock_supabase):
            with patch("app.routers.remediation.get_current_user", return_value=mock_current_user):
                mock_supabase.table("qc_remediation_tasks").select.return_value.eq.return_value.execute.return_value = mock_existing_result
                mock_supabase.table("qc_remediation_tasks").update.return_value.eq.return_value.execute.return_value = mock_update_result

                response = client.post(
                    f"/api/v1/remediation/{task_id}/review",
                    json={
                        "approved": True,
                        "review_comment": "整改完成良好，予以批准"
                    }
                )

                # 验证响应
                assert_response_success(response, 200)
                data = response.json()
                assert data["data"]["status"] == "approved"

    def test_review_remediation_reject(self, client, mock_supabase, mock_current_user, sample_remediation_task):
        """测试审核整改 - 拒绝"""
        task_id = sample_remediation_task["id"]
        sample_remediation_task["status"] = "submitted"

        # Mock 查询和更新
        mock_existing_result = MagicMock()
        mock_existing_result.data = [sample_remediation_task]

        rejected_task = sample_remediation_task.copy()
        rejected_task["status"] = "rejected"
        mock_update_result = MagicMock()
        mock_update_result.data = [rejected_task]

        with patch("app.routers.remediation.get_supabase", return_value=mock_supabase):
            with patch("app.routers.remediation.get_current_user", return_value=mock_current_user):
                mock_supabase.table("qc_remediation_tasks").select.return_value.eq.return_value.execute.return_value = mock_existing_result
                mock_supabase.table("qc_remediation_tasks").update.return_value.eq.return_value.execute.return_value = mock_update_result

                response = client.post(
                    f"/api/v1/remediation/{task_id}/review",
                    json={
                        "approved": False,
                        "review_comment": "整改不完整，需要重新整改"
                    }
                )

                # 验证响应
                assert_response_success(response, 200)
                data = response.json()
                assert data["data"]["status"] == "rejected"

    def test_close_remediation_task_success(self, client, mock_supabase, mock_current_user, sample_remediation_task):
        """测试关闭整改任务成功"""
        task_id = sample_remediation_task["id"]
        sample_remediation_task["creator_id"] = mock_current_user["id"]
        sample_remediation_task["status"] = "approved"

        # Mock 查询和更新
        mock_existing_result = MagicMock()
        mock_existing_result.data = [sample_remediation_task]

        closed_task = sample_remediation_task.copy()
        closed_task["status"] = "closed"
        mock_update_result = MagicMock()
        mock_update_result.data = [closed_task]

        with patch("app.routers.remediation.get_supabase", return_value=mock_supabase):
            with patch("app.routers.remediation.get_current_user", return_value=mock_current_user):
                mock_supabase.table("qc_remediation_tasks").select.return_value.eq.return_value.execute.return_value = mock_existing_result
                mock_supabase.table("qc_remediation_tasks").update.return_value.eq.return_value.execute.return_value = mock_update_result

                response = client.post(
                    f"/api/v1/remediation/{task_id}/close",
                    json={"closure_reason": "整改任务已完成"}
                )

                # 验证响应
                assert_response_success(response, 200)
                data = response.json()
                assert data["data"]["status"] == "closed"

    def test_get_remediation_statistics(self, client, mock_supabase, mock_current_user):
        """测试获取整改统计"""
        # Mock 统计数据
        mock_result = MagicMock()
        mock_result.data = [
            {
                "status": "pending",
                "defect_type": "incomplete_record",
                "priority": "medium",
                "count": 10,
                "avg_resolution_time_seconds": 172800
            },
            {
                "status": "approved",
                "defect_type": "inconsistent_data",
                "priority": "high",
                "count": 5,
                "avg_resolution_time_seconds": 86400
            }
        ]

        with patch("app.routers.remediation.get_supabase", return_value=mock_supabase):
            with patch("app.routers.remediation.get_current_user", return_value=mock_current_user):
                mock_supabase.table("qc_remediation_statistics").select.return_value.execute.return_value = mock_result

                response = client.get("/api/v1/remediation/statistics/summary")

                # 验证响应
                assert_response_success(response, 200)
                data = response.json()
                assert "total" in data["data"]
                assert "pending" in data["data"]
                assert "approved" in data["data"]
                assert "avg_resolution_time_hours" in data["data"]

    def test_get_workload_analysis(self, client, mock_supabase, mock_current_user):
        """测试获取工作量分析"""
        # Mock 工作量数据
        mock_result = MagicMock()
        mock_result.data = [
            {
                "assignee_id": str(uuid.uuid4()),
                "assignee_name": "张医生",
                "total_tasks": 15,
                "pending_tasks": 3,
                "in_progress_tasks": 5,
                "completed_tasks": 7,
                "overdue_tasks": 2,
                "avg_completion_time_seconds": 86400
            }
        ]

        with patch("app.routers.remediation.get_supabase", return_value=mock_supabase):
            with patch("app.routers.remediation.get_current_user", return_value=mock_current_user):
                mock_supabase.table("qc_assignee_workload").select.return_value.execute.return_value = mock_result

                response = client.get("/api/v1/remediation/statistics/workload")

                # 验证响应
                assert_response_success(response, 200)
                data = response.json()
                assert "assignees" in data["data"]
                assert len(data["data"]["assignees"]) == 1
                assert data["data"]["assignees"][0]["assignee_name"] == "张医生"

    def test_get_overdue_alerts(self, client, mock_supabase, mock_current_user):
        """测试获取逾期提醒"""
        # Mock 逾期任务
        overdue_task = {
            "id": str(uuid.uuid4()),
            "task_number": "RM-20250109-0001",
            "status": "overdue",
            "defect_type": "incomplete_record",
            "priority": "high",
            "assignee_name": "张医生",
            "deadline": (datetime.utcnow() - timedelta(days=1)).isoformat(),
            "overdue_days": 1
        }

        mock_result = MagicMock()
        mock_result.data = [overdue_task]

        with patch("app.routers.remediation.get_supabase", return_value=mock_supabase):
            with patch("app.routers.remediation.get_current_user", return_value=mock_current_user):
                mock_supabase.table("qc_remediation_tasks").select.return_value.eq.return_value.order.return_value.execute.return_value = mock_result

                response = client.get("/api/v1/remediation/statistics/overdue")

                # 验证响应
                assert_response_success(response, 200)
                data = response.json()
                assert "overdue_tasks" in data["data"]
                assert len(data["data"]["overdue_tasks"]) == 1


@pytest.mark.unit
@pytest.mark.remediation
class TestRemediationValidation:
    """整改任务数据验证测试"""

    def test_create_remediation_task_invalid_defect_description_too_short(self, client, mock_current_user):
        """测试创建整改任务 - 缺陷描述太短"""
        with patch("app.routers.remediation.get_current_user", return_value=mock_current_user):
            response = client.post(
                "/api/v1/remediation",
                json={
                    "qc_result_id": str(uuid.uuid4()),
                    "record_id": str(uuid.uuid4()),
                    "defect_type": "incomplete_record",
                    "defect_description": "短",  # 太短
                    "remediation_requirement": "补充完整入院记录",
                    "assignee_id": str(uuid.uuid4()),
                    "assignee_name": "张医生",
                    "priority": "medium"
                }
            )

            # 验证响应 - 应该返回验证错误
            assert response.status_code == 422

    def test_create_remediation_task_invalid_priority(self, client, mock_current_user):
        """测试创建整改任务 - 无效的优先级"""
        with patch("app.routers.remediation.get_current_user", return_value=mock_current_user):
            response = client.post(
                "/api/v1/remediation",
                json={
                    "qc_result_id": str(uuid.uuid4()),
                    "record_id": str(uuid.uuid4()),
                    "defect_type": "incomplete_record",
                    "defect_description": "入院记录不完整",
                    "remediation_requirement": "补充完整入院记录",
                    "assignee_id": str(uuid.uuid4()),
                    "assignee_name": "张医生",
                    "priority": "invalid_priority"  # 无效优先级
                }
            )

            # 验证响应 - 应该返回验证错误
            assert response.status_code == 422

    def test_create_remediation_task_missing_assignee(self, client, mock_current_user):
        """测试创建整改任务 - 缺少负责人"""
        with patch("app.routers.remediation.get_current_user", return_value=mock_current_user):
            response = client.post(
                "/api/v1/remediation",
                json={
                    "qc_result_id": str(uuid.uuid4()),
                    "record_id": str(uuid.uuid4()),
                    "defect_type": "incomplete_record",
                    "defect_description": "入院记录不完整",
                    "remediation_requirement": "补充完整入院记录",
                    "priority": "medium"
                    # 缺少 assignee_id 和 assignee_name
                }
            )

            # 验证响应 - 应该返回验证错误
            assert response.status_code == 422
