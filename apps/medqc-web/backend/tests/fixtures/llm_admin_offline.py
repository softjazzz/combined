"""供禁网入口显式加载的HTTP夹具：不进入应用lifespan，不启动后台任务。"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def isolated_endpoint_storage(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_ENDPOINT_CONFIG_DIR", str(tmp_path / "endpoint-settings"))


@pytest.fixture
def client():
    from app.main import create_app
    app = create_app()
    client = TestClient(app)
    try:
        yield client
    finally:
        client.close()
        app.dependency_overrides.clear()
