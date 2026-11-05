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


@pytest.mark.parametrize("missing", [None, "validation_material_copies"])
def test_core_schema_validation_is_readonly_and_optional_tables_are_not_required(
    monkeypatch, missing
):
    from types import SimpleNamespace
    from app.core import server_startup
    from app.services import user_scope_owner, auth_store

    events = []

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, statement):
            events.append(str(statement))
            return SimpleNamespace(
                scalars=lambda: SimpleNamespace(all=lambda: ["20261105_000063"])
            )

        def rollback(self):
            events.append("rollback")

    class Inspector:
        def has_table(self, name, schema):
            return name not in {
                "rule_validation_runs",
                "rule_validation_events",
                missing,
            } and schema in {"qc", "sys"}

        def get_columns(self, *a, **kw):
            return [
                {"name": n}
                for n in auth_store._REQUIRED_AUTH_COLUMNS | {"institute_id"}
            ]

    from app.services.bundles import refresh_storage
    monkeypatch.setattr(refresh_storage, "bind_storage", lambda _: {})
    monkeypatch.setattr(server_startup.sa, "inspect", lambda _: Inspector())
    monkeypatch.setattr(
        user_scope_owner, "configured_search_path", lambda: ["sys", "qc", "public"]
    )
    engine = SimpleNamespace(
        dialect=SimpleNamespace(name="postgresql"), connect=lambda: Connection()
    )
    if missing:
        with pytest.raises(RuntimeError, match="server_required_table_missing"):
            server_startup.validate_server_schema(engine)
    else:
        server_startup.validate_server_schema(engine)
    assert events[0] == "SET TRANSACTION READ ONLY"
    assert events[-1] == "rollback"


def test_frontend_static_path_is_confined(tmp_path):
    import importlib.util

    path = Path(__file__).resolve().parents[3] / "scripts/serve_dist_spa.py"
    spec = importlib.util.spec_from_file_location("serve_dist_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    handler = object.__new__(module.SpaHandler)
    handler.directory = str(tmp_path / "dist")
    handler.path = "/index.html"
    assert handler._within_static_root()
    handler.path = "/%2e%2e/backend/.env"
    assert not handler._within_static_root()
