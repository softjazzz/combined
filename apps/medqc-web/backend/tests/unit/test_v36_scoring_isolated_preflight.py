"""只读预检的目标库和连接前失败关闭合同。"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

spec = spec_from_file_location("scoring_preflight_test", Path(__file__).resolve().parents[2]
                              / "scripts" / "v36_scoring_isolated_preflight.py")
preflight = module_from_spec(spec)
spec.loader.exec_module(preflight)


def test_credentials_never_choose_the_target_database():
    url = preflight.isolated_url({"DATABASE_URL": "postgresql://synthetic:fake@localhost/medqc"})
    assert url.database == preflight.DATABASE
    assert url.username == "synthetic" and url.password == "fake"
    with pytest.raises(RuntimeError):
        preflight.isolated_url({"DATABASE_URL": "sqlite://"})


@pytest.mark.parametrize("values", [("off",), ("on", "medqc")])
def test_read_only_and_database_are_checked_before_table_inspection(monkeypatch, values):
    values = iter(values)

    class Connection:
        def execute(self, statement):
            assert str(statement) in ("SHOW transaction_read_only", "SELECT current_database()")
            value = next(values)

            class Result:
                def scalar_one(self):
                    return value

            return Result()

    monkeypatch.setattr(preflight.sa, "inspect", lambda _connection: pytest.fail("不应反射表"))
    with pytest.raises(RuntimeError):
        preflight.inspect_preflight(Connection())


def test_migration_modules_loaded_without_running_upgrade(monkeypatch):
    for number in ("082", "083", "084"):
        module = preflight.load_migration(number)
        assert callable(module.schema_state)
        assert module.SCHEMAS == ("qc", "public")
    assert preflight.load_migration("083").down_revision == "20261002_000082"
    assert preflight.load_migration("084").down_revision == "20261003_000083"


def test_after_phase_only_adapts_the_authorized_parent_scene_check():
    before = preflight.binding_migration("before")._baseline()
    after = preflight.binding_migration("after")._baseline()
    frontpage = preflight.load_migration("084")
    assert before.SPECS[frontpage.TABLE]["checks"][frontpage.CONSTRAINT] == frontpage.OLD_CHECK
    assert after.SPECS[frontpage.TABLE]["checks"][frontpage.CONSTRAINT] == frontpage.NEW_CHECK
    after.SPECS[frontpage.TABLE]["checks"][frontpage.CONSTRAINT] = frontpage.OLD_CHECK
    assert before.SPECS == after.SPECS
