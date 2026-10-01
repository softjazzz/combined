"""迁移80离线合同：不连接数据库，不复制通知已读状态。"""

import importlib.util
from pathlib import Path
from unittest.mock import Mock

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.database.models.case_communication import CaseCommunication


def migration():
    path = Path(__file__).parents[2] / "alembic/versions/20261001_000080_case_communications.py"
    spec = importlib.util.spec_from_file_location("case_communication_migration_80", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upgrade_matches_single_owner_model_and_constraints(monkeypatch):
    module = migration()
    operations = Mock()
    monkeypatch.setattr(module, "op", operations)
    module.upgrade()
    assert module.revision == "20261001_000080"
    assert module.down_revision == "20261001_000079"
    operations.create_table.assert_called_once()
    call = operations.create_table.call_args
    assert call.args[0] == "qc_case_communications" and call.kwargs["schema"] == "qc"
    table = sa.Table(call.args[0], sa.MetaData(), *call.args[1:], schema="qc")
    model = CaseCommunication.__table__
    assert set(table.c.keys()) == set(model.c.keys())
    for column in table.c:
        expected = model.c[column.name]
        assert column.nullable == expected.nullable
        assert str(column.type) == str(expected.type)
    assert not {"is_read", "read_at"} & set(table.c.keys())
    unique_columns = {tuple(column.name for column in constraint.columns)
                      for constraint in table.constraints if isinstance(constraint, sa.UniqueConstraint)}
    assert {("actor_id", "request_id"), ("related_event_id",), ("notification_id",)} <= unique_columns
    assert {key.target_fullname for key in table.foreign_keys} == {"qc.qc_case_communications.id"}
    sql = str(sa.schema.CreateTable(table).compile(dialect=postgresql.dialect()))
    assert "ck_case_communication_action" in sql and "ck_case_communication_content" in sql
    operations.create_index.assert_called_once_with(
        "ix_case_communication_identity", "qc_case_communications",
        ["institute_id", "patient_id", "visit_id", "created_at"], schema="qc",
    )
    operations.execute.assert_not_called()


@pytest.mark.parametrize("count", [1, 20])
def test_nonempty_history_refuses_downgrade(monkeypatch, count):
    module = migration()
    operations = Mock()
    operations.get_bind.return_value.execute.return_value.scalar.return_value = count
    monkeypatch.setattr(module, "op", operations)
    with pytest.raises(RuntimeError, match="拒绝破坏性降级"):
        module.downgrade()
    operations.drop_table.assert_not_called()


def test_empty_downgrade_only_removes_communication_owner(monkeypatch):
    module = migration()
    operations = Mock()
    operations.get_bind.return_value.execute.return_value.scalar.return_value = 0
    monkeypatch.setattr(module, "op", operations)
    module.downgrade()
    operations.drop_table.assert_called_once_with("qc_case_communications", schema="qc")
    operations.execute.assert_not_called()
