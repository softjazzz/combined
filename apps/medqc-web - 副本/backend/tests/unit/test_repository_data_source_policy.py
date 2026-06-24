"""
Repository 数据源策略行为测试

验证 ADR-2026-03-16 决策：
1. DATA_SOURCE 未设置 → 返回 PG repository
2. DATA_SOURCE=pg → 返回 PG repository
3. DATA_SOURCE=sqlite → 返回 PG repository（兼容别名）
4. DATA_SOURCE=mongo_api → 启动即失败 RuntimeError
5. DATA_SOURCE=typo → 启动即失败 ValueError
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


# 每个测试前重置单例
@pytest.fixture(autouse=True)
def reset_repo():
    from app.database.repository import reset_repository
    reset_repository()
    yield
    reset_repository()


# Mock SessionLocal 避免真实数据库连接
@pytest.fixture(autouse=True)
def mock_session_local():
    with patch("app.database.repository.SqliteRepository.__init__", return_value=None):
        yield


class TestDataSourcePolicy:
    """DATA_SOURCE 环境变量策略测试"""

    @pytest.mark.unit
    def test_default_returns_pg_repo(self):
        """未设置 DATA_SOURCE → 返回 PG repository（SqliteRepository）"""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DATA_SOURCE", None)
            from app.database.repository import get_repository, SqliteRepository
            repo = get_repository()
            assert isinstance(repo, SqliteRepository)

    @pytest.mark.unit
    def test_pg_returns_pg_repo(self):
        """DATA_SOURCE=pg → 返回 PG repository"""
        with patch.dict(os.environ, {"DATA_SOURCE": "pg"}):
            from app.database.repository import get_repository, SqliteRepository
            repo = get_repository()
            assert isinstance(repo, SqliteRepository)

    @pytest.mark.unit
    def test_sqlite_compat_returns_pg_repo(self):
        """DATA_SOURCE=sqlite → 兼容别名，返回 PG repository"""
        with patch.dict(os.environ, {"DATA_SOURCE": "sqlite"}):
            from app.database.repository import get_repository, SqliteRepository
            repo = get_repository()
            assert isinstance(repo, SqliteRepository)

    @pytest.mark.unit
    def test_mongo_api_raises_runtime_error(self):
        """DATA_SOURCE=mongo_api → 启动即失败 RuntimeError"""
        with patch.dict(os.environ, {"DATA_SOURCE": "mongo_api"}):
            from app.database.repository import get_repository
            with pytest.raises(RuntimeError, match="已弃用"):
                get_repository()

    @pytest.mark.unit
    def test_unknown_value_raises_value_error(self):
        """DATA_SOURCE=invalid_value → ValueError 配置错误前置暴露"""
        with patch.dict(os.environ, {"DATA_SOURCE": "mysql"}):
            from app.database.repository import get_repository
            with pytest.raises(ValueError, match="不是合法值"):
                get_repository()

    @pytest.mark.unit
    def test_case_insensitive(self):
        """DATA_SOURCE=PG（大写）→ 也应工作"""
        with patch.dict(os.environ, {"DATA_SOURCE": "PG"}):
            from app.database.repository import get_repository, SqliteRepository
            repo = get_repository()
            assert isinstance(repo, SqliteRepository)

    @pytest.mark.unit
    def test_whitespace_trimmed(self):
        """DATA_SOURCE=" pg " → 去空格后正常"""
        with patch.dict(os.environ, {"DATA_SOURCE": " pg "}):
            from app.database.repository import get_repository, SqliteRepository
            repo = get_repository()
            assert isinstance(repo, SqliteRepository)


class TestStartupIntegration:
    """验证 create_app() 启动阶段的 DATA_SOURCE 校验"""

    @pytest.mark.integration
    def test_startup_fails_with_mongo_api(self):
        """DATA_SOURCE=mongo_api → create_app() 启动即失败（RuntimeError）"""
        with patch.dict(os.environ, {"DATA_SOURCE": "mongo_api"}):
            from app.main import create_app
            app = create_app()
            with pytest.raises(RuntimeError, match="已弃用"):
                # startup 事件在 TestClient 进入上下文时触发
                with TestClient(app):
                    pass  # 不应到达此处

    @pytest.mark.integration
    def test_startup_fails_with_unknown_source(self):
        """DATA_SOURCE=redis → create_app() 启动即失败（ValueError）"""
        with patch.dict(os.environ, {"DATA_SOURCE": "redis"}):
            from app.main import create_app
            app = create_app()
            with pytest.raises(ValueError, match="不是合法值"):
                with TestClient(app):
                    pass
