"""
Pytest 配置和共享 fixtures

该文件定义了所有测试共享的 fixtures 和配置
"""

import os
import uuid
from datetime import datetime
from typing import Generator
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url

# 单元测试默认拒连；不得从 backend/.env 隐式继承业务库连接。
_TEST_REFUSE_DSN = "postgresql://invalid:invalid@127.0.0.1:1/nonexistent"
_explicit_database_url = os.environ.get("DATABASE_URL", "").strip()
if not _explicit_database_url:
    os.environ["DATABASE_URL"] = _TEST_REFUSE_DSN
elif make_url(_explicit_database_url).database == "medqc":
    raise RuntimeError("拒绝在业务库 medqc 上运行后端测试")

# 导入应用
from app.main import create_app  # noqa: E402 - 先隔离数据库再导入应用
from app.core.rate_limit import reset_rate_limit_store_for_testing  # noqa: E402
from app.core.upload_security import clear_virus_scan_hook_for_testing  # noqa: E402
from app.services.sync_idempotency import reset_sync_idempotency_memory_for_testing  # noqa: E402

# 导入语义规则 fixtures
pytest_plugins = ["tests.fixtures.semantic_rules_fixtures"]


@pytest.fixture(autouse=True)
def _isolate_consultation_opinion_freeze(tmp_path, monkeypatch):
    """会诊意见事实冻结按用例隔离：避免用例之间复用第一阶段事实。"""

    monkeypatch.setenv(
        "LUXIAN_0609_OPINION_FREEZE_DIR", str(tmp_path / "opinion-freeze")
    )


@pytest.fixture(autouse=True)
def _empty_rule_set_version_store(monkeypatch):
    """默认拒连时，规则集版本表视为空表（只有内置版本）。

    任务创建与 prepare 会读取 current_version；单元测试不连库，用内存 SQLite 空表
    模拟“未发布任何版本”，与生产表为空时的行为一致。显式配置隔离库时不替换。
    需要其他版本数据或故障语义的用例自行覆盖 SessionLocal。
    """

    if _explicit_database_url:
        yield
        return
    import sqlalchemy as sa
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.database.models.qc import QCRuleSetVersion
    from app.services import rule_set_version_service

    engine = sa.create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    QCRuleSetVersion.__table__.create(engine)
    monkeypatch.setattr(
        rule_set_version_service,
        "SessionLocal",
        sessionmaker(bind=engine, expire_on_commit=False),
    )
    yield
    engine.dispose()


@pytest.fixture(scope="session")
def app():
    """
    创建 FastAPI 应用实例（会话级别）

    Returns:
        FastAPI: 应用实例
    """
    return create_app()


@pytest.fixture(scope="function")
def client(app) -> Generator:
    """
    创建测试客户端（函数级别）

    Args:
        app: FastAPI 应用实例

    Yields:
        TestClient: 测试客户端
    """
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="function")
def mock_supabase():
    """
    Mock Supabase 客户端

    Returns:
        Mock: Supabase 客户端 mock
    """
    mock_client = MagicMock()

    # Mock table 方法
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table

    # Mock 查询链
    mock_query = MagicMock()
    mock_table.select.return_value = mock_query
    mock_table.insert.return_value = mock_query
    mock_table.update.return_value = mock_query
    mock_table.delete.return_value = mock_query

    # Mock 查询方法
    mock_query.eq.return_value = mock_query
    mock_query.neq.return_value = mock_query
    mock_query.gt.return_value = mock_query
    mock_query.gte.return_value = mock_query
    mock_query.lt.return_value = mock_query
    mock_query.lte.return_value = mock_query
    mock_query.like.return_value = mock_query
    mock_query.ilike.return_value = mock_query
    mock_query.in_.return_value = mock_query
    mock_query.order.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.range.return_value = mock_query

    # Mock execute 返回
    mock_result = MagicMock()
    mock_result.data = []
    mock_result.count = 0
    mock_query.execute.return_value = mock_result

    return mock_client


@pytest.fixture(scope="function")
def mock_current_user():
    """
    Mock 当前用户

    Returns:
        Dict: 用户信息
    """
    return {
        "id": str(uuid.uuid4()),
        "email": "test@example.com",
        "name": "Test User",
        "role": "admin"
    }


@pytest.fixture(scope="function")
def sample_medical_record():
    """
    示例病历记录

    Returns:
        Dict: 病历数据
    """
    record_id = str(uuid.uuid4())
    return {
        "id": record_id,
        "patient_name": "张三",
        "patient_id": "P123456",
        "admission_number": "A2025001",
        "department": "心内科",
        "attending_doctor": "李医生",
        "admission_date": "2025-01-01T00:00:00Z",
        "discharge_date": "2025-01-10T00:00:00Z",
        "diagnosis": "冠心病",
        "content": "患者男性，65岁，因胸痛3天入院...",
        "created_at": datetime.utcnow().isoformat() + "Z",
        "updated_at": datetime.utcnow().isoformat() + "Z"
    }


@pytest.fixture(scope="function")
def sample_qc_result():
    """
    示例质控结果

    Returns:
        Dict: 质控结果数据
    """
    return {
        "id": str(uuid.uuid4()),
        "record_id": str(uuid.uuid4()),
        "overall_score": 85,
        "overall_grade": "B",
        "analysis_date": datetime.utcnow().isoformat() + "Z",
        "issues": [
            {
                "id": "issue-1",
                "rule_name": "入院记录完整性",
                "description": "缺少过敏史记录",
                "severity": "medium",
                "category": "completeness",
                "location": "入院记录",
                "suggestion": "请补充过敏史信息"
            }
        ],
        "suggestions": [],
        "rule_results": [],
        "metadata": {}
    }


@pytest.fixture(scope="function")
def sample_appeal():
    """
    示例申诉记录

    Returns:
        Dict: 申诉数据
    """
    return {
        "id": str(uuid.uuid4()),
        "appeal_number": "AP-20250109-0001",
        "qc_result_id": str(uuid.uuid4()),
        "record_id": str(uuid.uuid4()),
        "appeal_type": "defect",
        "defect_item": "过敏史缺失",
        "reason": "患者无过敏史，无需记录",
        "evidence": [],
        "status": "pending",
        "priority": "medium",
        "appellant_id": str(uuid.uuid4()),
        "appellant_name": "张医生",
        "appellant_department": "心内科",
        "created_at": datetime.utcnow().isoformat() + "Z",
        "updated_at": datetime.utcnow().isoformat() + "Z"
    }


@pytest.fixture(scope="function")
def sample_remediation_task():
    """
    示例整改任务

    Returns:
        Dict: 整改任务数据
    """
    return {
        "id": str(uuid.uuid4()),
        "task_number": "RM-20250109-0001",
        "qc_result_id": str(uuid.uuid4()),
        "record_id": str(uuid.uuid4()),
        "defect_type": "完整性缺陷",
        "defect_description": "入院记录缺少过敏史",
        "defect_location": "入院记录第3页",
        "severity": "medium",
        "remediation_requirement": "请在入院记录中补充患者过敏史信息",
        "deadline": "2025-01-15T00:00:00Z",
        "assignee_id": str(uuid.uuid4()),
        "assignee_name": "张医生",
        "assignee_department": "心内科",
        "status": "pending",
        "created_at": datetime.utcnow().isoformat() + "Z",
        "updated_at": datetime.utcnow().isoformat() + "Z"
    }


@pytest.fixture(autouse=True)
def reset_mocks(monkeypatch):
    """
    自动重置所有 mocks（每个测试函数执行前）

    Args:
        monkeypatch: pytest monkeypatch fixture
    """
    # 可以在这里添加需要自动重置的 mocks
    pass


@pytest.fixture(autouse=True)
def reset_rate_limit_store():
    """避免测试间共享限流桶导致相互污染。"""
    reset_rate_limit_store_for_testing()
    clear_virus_scan_hook_for_testing()
    reset_sync_idempotency_memory_for_testing()


# 测试辅助函数

def assert_response_success(response, expected_status: int = 200):
    """
    断言响应成功

    Args:
        response: HTTP 响应
        expected_status: 期望的状态码
    """
    assert response.status_code == expected_status
    data = response.json()
    assert data.get("success") is True
    assert "data" in data
    assert "trace_id" in data


def assert_response_error(response, expected_status: int, expected_code: str = None):
    """
    断言响应错误

    Args:
        response: HTTP 响应
        expected_status: 期望的状态码
        expected_code: 期望的错误代码
    """
    assert response.status_code == expected_status
    data = response.json()
    assert data.get("success") is False
    assert "error" in data
    if expected_code:
        assert data.get("code") == expected_code


# 导出辅助函数
__all__ = [
    "app",
    "client",
    "mock_supabase",
    "mock_current_user",
    "sample_medical_record",
    "sample_qc_result",
    "sample_appeal",
    "sample_remediation_task",
    "assert_response_success",
    "assert_response_error",
]
