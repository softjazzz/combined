"""服务器部署保护；合成内存与Mock，不访问模型或真实数据库。"""

import runpy
from pathlib import Path

import pytest


def test_production_memory_has_no_demo_accounts_or_sample_records(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    values = runpy.run_path(
        str(Path(__file__).resolve().parents[2] / "app/storage/memory.py")
    )
    assert values["users_db"] == {}
    assert values["medical_records_db"] == {}
    values["assert_no_default_demo_users_in_production"]("production")


def test_production_never_uses_cached_account_when_persistent_owner_unavailable(
    monkeypatch,
):
    from app.services import auth_store

    monkeypatch.setenv("ENV", "production")
    monkeypatch.setattr(auth_store, "_query_db_user_by_account", lambda _: None)
    monkeypatch.setattr(auth_store, "_query_db_user_by_subject", lambda _: None)
    monkeypatch.setattr(
        auth_store,
        "users_db",
        {"synthetic@test.invalid": {"id": "cached", "username": "cached"}},
    )
    assert auth_store.find_user_by_account("cached") is None
    assert auth_store.resolve_user_by_subject("cached") is None


def test_production_guard_still_rejects_injected_demo():
    from app.storage.memory import assert_no_default_demo_users_in_production

    with pytest.raises(RuntimeError, match="default in-memory demo"):
        assert_no_default_demo_users_in_production(
            "production", {"admin@medqc.com": {}}
        )
