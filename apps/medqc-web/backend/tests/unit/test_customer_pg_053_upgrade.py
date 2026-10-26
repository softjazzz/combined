"""客户升级工具的备份门禁、文件校验与既有值保护；不连接数据库。"""

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


@pytest.fixture
def tool():
    path = Path(__file__).resolve().parents[3] / "tools/deployment/upgrade_customer_pg_053.py"
    spec = importlib.util.spec_from_file_location("customer_pg_053_upgrade", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_backup_must_finish_before_install_and_upgrade(tool, monkeypatch, tmp_path):
    events = []
    for method in ("backup_database", "install_migrations", "migrate"):
        monkeypatch.setattr(tool, method, lambda *args, name=method: events.append(name))
    tool.backup_then_upgrade({}, tmp_path, tmp_path, tmp_path, tmp_path, {})
    assert events == ["backup_database", "install_migrations", "migrate"]


def test_backup_failure_blocks_install_and_database_upgrade(tool, monkeypatch, tmp_path):
    events = []

    def fail(*args):
        raise RuntimeError("archive_verification_failed")

    monkeypatch.setattr(tool, "backup_database", fail)
    monkeypatch.setattr(tool, "install_migrations", lambda *args: events.append("install"))
    monkeypatch.setattr(tool, "migrate", lambda *args: events.append("migrate"))
    with pytest.raises(RuntimeError, match="archive_verification_failed"):
        tool.backup_then_upgrade({}, tmp_path, tmp_path, tmp_path, tmp_path, {})
    assert events == []


def test_installed_conflict_is_not_overwritten(tool, tmp_path):
    versions = tmp_path / "alembic/versions"
    versions.mkdir(parents=True)
    existing = versions / tool.MIGRATIONS[0]
    existing.write_text("existing migration", encoding="utf8")
    with pytest.raises(RuntimeError, match="installed_migration_conflict"):
        tool.install_migrations(tmp_path, tmp_path, {tool.MIGRATIONS[0]: "different"})
    assert existing.read_text(encoding="utf8") == "existing migration"


def test_package_checksum_catches_tampered_migration(tool, tmp_path):
    (tmp_path / "migrations").mkdir()
    expected = {}
    for name in tool.MIGRATIONS:
        content = name.encode()
        (tmp_path / "migrations" / name).write_bytes(content)
        expected[name] = hashlib.sha256(content).hexdigest()
    (tmp_path / "migration-sha256.json").write_text(json.dumps(expected), encoding="utf8")
    assert tool.check_package(tmp_path) == expected
    (tmp_path / "migrations" / tool.MIGRATIONS[0]).write_bytes(b"changed")
    with pytest.raises(RuntimeError, match="checksum_mismatch"):
        tool.check_package(tmp_path)


def state(tool):
    return {"schema": "public", "revisions": [tool.TARGET],
            "visits": [{"visit_id": "synthetic", "scene_current": "final"}],
            "deaths": [{"document_id": "synthetic", "record_content": "unchanged"}]}


def test_nullable_new_columns_do_not_change_old_values(tool):
    before = state(tool)
    after = state(tool)
    after["visits"][0].update(dict(zip(tool.FIELDS, [None, 30, 30])))
    after["deaths"][0]["death_datetime"] = None
    tool.verify_preserved(before, after)


@pytest.mark.parametrize("scope,field", [("visits", "scene_current"), ("deaths", "record_content")])
def test_existing_values_must_be_preserved(tool, scope, field):
    before, after = state(tool), state(tool)
    after[scope][0][field] = "changed"
    with pytest.raises(RuntimeError, match="existing_field_changed"):
        tool.verify_preserved(before, after)


def test_row_loss_is_not_reported_success(tool):
    before, after = state(tool), state(tool)
    after["deaths"] = []
    with pytest.raises(RuntimeError, match="existing_row_count_changed"):
        tool.verify_preserved(before, after)
