"""扫码与密码登录共用签发合同，不连接真实数据库。"""

from datetime import timedelta
from types import SimpleNamespace

import pytest

from app.core import security


def test_shared_login_pair_preserves_access_and_refresh_claims(monkeypatch):
    calls = []
    monkeypatch.setattr(
        security, "get_settings", lambda: SimpleNamespace(ACCESS_TOKEN_EXPIRE_MINUTES=45),
    )

    def sign(data, expires_delta):
        calls.append((data, expires_delta))
        return f"synthetic-token-{len(calls)}"

    monkeypatch.setattr(security, "create_access_token", sign)
    result = security.issue_login_token_pair({"id": "user-1", "email": "user@example.test"})
    assert calls == [
        ({"sub": "user@example.test", "uid": "user-1"}, timedelta(minutes=45)),
        ({"sub": "user@example.test", "uid": "user-1", "type": "refresh"}, timedelta(days=7)),
    ]
    assert result == {
        "access_token": "synthetic-token-1",
        "refresh_token": "synthetic-token-2",
        "token_type": "bearer",
        "expires_in": 2700,
    }


@pytest.mark.parametrize("user", [
    {"id": "user-1", "email": ""},
    {"id": "", "email": "user@example.test"},
    {"id": "user-1", "email": "   "},
])
def test_missing_persistent_identity_never_signs_token(monkeypatch, user):
    calls = []
    monkeypatch.setattr(security, "create_access_token", lambda **kwargs: calls.append(kwargs))
    with pytest.raises(ValueError):
        security.issue_login_token_pair(user)
    assert calls == []
