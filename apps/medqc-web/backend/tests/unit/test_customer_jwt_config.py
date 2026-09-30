"""客户配置优先级与占位值保护；全部使用合成密钥。"""
import pytest
from app.core.settings import get_settings


@pytest.mark.parametrize("dotenv_value,environment_value,valid", [
    ("synthetic-dotenv-unique-key-for-test", None, True),
    ("synthetic-dotenv-unique-key-for-test", "synthetic-environment-key-for-test", True),
    (None, None, False),
    ("dev-secret", None, False),
    ("replace-with-a-random-secret", None, False),
    ("synthetic-dotenv-unique-key-for-test", "dev-secret", False),
])
def test_customer_jwt_sources(tmp_path, monkeypatch, dotenv_value, environment_value, valid):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.setenv("PRODUCT_ACTIVATION_REQUIRED", "true")
    if dotenv_value is not None:
        (tmp_path / ".env").write_text("JWT_SECRET=" + dotenv_value, encoding="utf-8")
    if environment_value is not None:
        monkeypatch.setenv("JWT_SECRET", environment_value)
    if valid:
        assert get_settings().JWT_SECRET == (environment_value or dotenv_value)
    else:
        with pytest.raises((RuntimeError, ValueError)):
            get_settings()
