from types import SimpleNamespace

from app.routers import sqlbot


def test_sqlbot_config_requires_auth(client):
    response = client.get("/api/v1/sqlbot/config")

    assert response.status_code == 401
    assert response.json()["error"] == "Authentication required"


def _settings(**overrides):
    values = {
        "SQLBOT_ENABLED": False,
        "SQLBOT_BASE_URL": "",
        "SQLBOT_EMBED_URL": "",
        "SQLBOT_APP_ID": "",
        "SQLBOT_TIMEOUT_SECONDS": 30,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_sqlbot_config_disabled(monkeypatch):
    monkeypatch.setattr(sqlbot, "get_settings", lambda: _settings())

    response = sqlbot.get_sqlbot_config()

    assert response.enabled is False
    assert response.display_mode == "disabled"
    assert "未启用" in response.message
    assert response.embed_url is None


def test_sqlbot_config_enabled_without_embed_url(monkeypatch):
    monkeypatch.setattr(
        sqlbot,
        "get_settings",
        lambda: _settings(SQLBOT_ENABLED=True, SQLBOT_BASE_URL="http://127.0.0.1:8080/"),
    )

    response = sqlbot.get_sqlbot_config()

    assert response.enabled is False
    assert response.display_mode == "disabled"
    assert response.base_url == "http://127.0.0.1:8080"
    assert "未配置嵌入地址" in response.message


def test_sqlbot_config_enabled_with_embed_url(monkeypatch):
    monkeypatch.setattr(
        sqlbot,
        "get_settings",
        lambda: _settings(
            SQLBOT_ENABLED=True,
            SQLBOT_BASE_URL="https://sqlbot.example.com/",
            SQLBOT_EMBED_URL="https://sqlbot.example.com/embed/app-1",
            SQLBOT_APP_ID="app-1",
        ),
    )

    response = sqlbot.get_sqlbot_config()

    assert response.enabled is True
    assert response.display_mode == "iframe"
    assert response.base_url == "https://sqlbot.example.com"
    assert response.embed_url == "https://sqlbot.example.com/embed/app-1"
    assert response.app_id == "app-1"
    assert "密钥" not in response.model_dump_json()
