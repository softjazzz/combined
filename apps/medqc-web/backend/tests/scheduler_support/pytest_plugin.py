"""QC 调度器离线 suite 的最小 pytest fixtures。"""

from fastapi.testclient import TestClient
import pytest


@pytest.fixture
def client():
    """构造真实路由客户端，但不进入 context manager、不运行主 app lifespan。"""

    from app.main import create_app

    test_client = TestClient(create_app())
    try:
        yield test_client
    finally:
        test_client.close()
