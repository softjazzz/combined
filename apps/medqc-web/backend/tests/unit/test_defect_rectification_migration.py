import importlib.util
from pathlib import Path
from unittest.mock import Mock

import pytest


def migration():
    path = Path(__file__).parents[2] / "alembic/versions/20260930_000077_modern_defect_rectification.py"
    spec = importlib.util.spec_from_file_location("modern_rectification_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_has_single_qc_owner_and_unique_source_and_event(monkeypatch):
    module = migration()
    operations = Mock()
    monkeypatch.setattr(module, "op", operations)
    module.upgrade()
    assert module.down_revision == "20260930_000076"
    calls = operations.create_table.call_args_list
    assert [call.args[0] for call in calls] == ["qc_defect_rectifications", "qc_defect_rectification_events"]
    assert all(call.kwargs["schema"] == "qc" for call in calls)
    names = [{getattr(value, "name", None) for value in call.args[1:]} for call in calls]
    assert "uq_rectification_source" in names[0]
    assert "uq_rectification_event_version" in names[1]


def test_nonempty_downgrade_refused(monkeypatch):
    module = migration()
    operations = Mock()
    operations.get_bind.return_value.execute.return_value.scalar.return_value = 1
    monkeypatch.setattr(module, "op", operations)
    with pytest.raises(RuntimeError):
        module.downgrade()
    operations.drop_table.assert_not_called()


def test_withdrawal_migration_preserves_qc_event_owner(monkeypatch):
    path = Path(__file__).parents[2] / "alembic/versions/20261001_000078_rectification_urge_withdrawal.py"
    spec = importlib.util.spec_from_file_location("withdrawal_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    operations = Mock()
    monkeypatch.setattr(module, "op", operations)
    module.upgrade()
    assert module.down_revision == "20260930_000077"
    assert operations.add_column.call_args.kwargs["schema"] == "qc"
    assert operations.create_foreign_key.call_args.kwargs["referent_schema"] == "qc"
    assert operations.create_unique_constraint.call_args.args[0] == "uq_rectification_event_withdrawal"
    operations.get_bind.return_value.execute.return_value.scalar.return_value = 1
    with pytest.raises(RuntimeError):
        module.downgrade()
    operations.drop_column.assert_not_called()


def test_snapshot_migration_has_nullable_no_backfill_and_nonempty_downgrade_refused(monkeypatch):
    path = Path(__file__).parents[2] / "alembic/versions/20261001_000079_rectification_document_snapshots.py"
    spec = importlib.util.spec_from_file_location("snapshot_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    operations = Mock()
    monkeypatch.setattr(module, "op", operations)
    module.upgrade()
    assert module.down_revision == "20261001_000078"
    assert len(operations.add_column.call_args_list) == 2
    assert all(call.kwargs["schema"] == "qc" and call.args[1].nullable for call in operations.add_column.call_args_list)
    operations.execute.assert_not_called()
    operations.get_bind.return_value.execute.return_value.scalar.return_value = 1
    with pytest.raises(RuntimeError):
        module.downgrade()
    operations.drop_column.assert_not_called()
