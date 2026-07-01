import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.storage.memory import assert_no_default_demo_users_in_production


def test_production_guard_rejects_default_demo_users():
    with pytest.raises(RuntimeError, match="default in-memory demo users"):
        assert_no_default_demo_users_in_production(
            "production",
            {
                "admin@medqc.com": {"id": "admin-001"},
                "doctor@medqc.com": {"id": "doctor-001"},
                "sync_admin@medqc.com": {"id": "sync-admin-001"},
            },
        )


def test_production_guard_ignores_non_production_env():
    assert_no_default_demo_users_in_production(
        "development",
        {
            "admin@medqc.com": {"id": "admin-001"},
        },
    )


def test_production_guard_rejects_default_sync_admin_user():
    with pytest.raises(RuntimeError, match="sync_admin@medqc.com"):
        assert_no_default_demo_users_in_production(
            "production",
            {
                "sync_admin@medqc.com": {"id": "sync-admin-001"},
            },
        )


def test_startup_fails_fast_in_production_with_default_demo_users(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "test-secret-for-guard")

    app = create_app()
    with pytest.raises(RuntimeError, match="default in-memory demo users"):
        with TestClient(app):
            pass
