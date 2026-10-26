"""两种已部署父链在专属合成PG汇合；不读取dotenv或现有业务库。"""

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from pathlib import Path

from scripts import bootstrap_pr8_empty_database as bootstrap
from test_report_alembic_upgrade import HELPER, seed_legacy, snapshot

pytest_plugins = ("test_report_migration_compatibility",)
BACKEND = Path(__file__).resolve().parents[2]
HEAD = "20261025_000054"


def test_product_report_graph_has_one_head_and_keeps_old_parents():
    config = Config()
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    script = ScriptDirectory.from_config(config)
    assert script.get_heads() == [HEAD]
    assert set(script.get_revision(HEAD).down_revision) == {"20261023_000053", "20261025_000052"}
    assert script.get_revision("20261023_000051").down_revision == "20261020_000050"
    assert script.get_revision("20261022_000051").down_revision == "20261020_000050"


@pytest.mark.parametrize("start", ["20261023_000053", "20261025_000052"])
@pytest.mark.parametrize("owner", ["sys", "public"])
def test_both_existing_heads_upgrade_without_overwriting_rows(raw_pg, monkeypatch, start, owner):
    bootstrap.initialize(raw_pg.url.database, target="20261020_000050")
    path = f"qc,{owner}," + ("sys," if owner == "public" else "") + "cdm,public,legacy"
    with raw_pg.begin() as conn:
        seed_legacy(conn)
        if owner == "public":
            # 原用户owner保留为哨兵，实际授权owner明确为public，不混用两表。
            conn.exec_driver_sql("CREATE TABLE public.sys_users (LIKE sys.sys_users INCLUDING ALL)")
        # 记录两线都不应修改的既有列和数据；后续只允许新增表、列、索引等增量。
        before = snapshot(conn)
    with bootstrap.migration_environment(raw_pg.url) as config:
        monkeypatch.setenv("DB_SEARCH_PATH", path)
        command.upgrade(config, start)
        command.upgrade(config, "head")
    with raw_pg.connect() as conn:
        assert conn.exec_driver_sql("SELECT version_num FROM public.alembic_version").scalars().all() == [HEAD]
        after = snapshot(conn, before)
        for key in before:
            assert after[key]["rows"] == before[key]["rows"], key
            assert all(after[key]["columns"][name] == value for name, value in before[key]["columns"].items()), key
        assert HELPER["plan"](sa.inspect(conn), search_path=path) == []
        for table in ("sys_user_registrations", "sys_user_registration_events"):
            assert sa.inspect(conn).has_table(table, schema=owner)
        for table, columns in {
            "discharge_record": {"chief_physician_sign_datetime", "v2_schema"},
            "death_record": {"death_datetime", "death_reason", "treatment_course", "admission_condition"},
            "inpat_drug_order": {"planned_end_datetime", "reviewed_datetime", "carried_datetime", "canceled_datetime"},
        }.items():
            assert columns <= {column["name"] for column in sa.inspect(conn).get_columns(table, schema="cdm")}
    # 汇合后再次升级无操作，结果仍只有一个版本号。
    with bootstrap.migration_environment(raw_pg.url) as config:
        monkeypatch.setenv("DB_SEARCH_PATH", path)
        command.upgrade(config, "head")


@pytest.mark.parametrize("drift", ["missing", "wrong_type", "wrong_default"])
def test_merge_refuses_drift_instead_of_only_merging_version_numbers(raw_pg, drift):
    bootstrap.initialize(raw_pg.url.database, target="20261020_000050")
    with bootstrap.migration_environment(raw_pg.url) as config:
        command.upgrade(config, "20261023_000053")
        command.upgrade(config, "20261025_000052")
        with raw_pg.begin() as conn:
            conn.exec_driver_sql({
                "missing": "ALTER TABLE cdm.death_record DROP COLUMN death_reason",
                "wrong_type": "ALTER TABLE cdm.inpat_drug_order ALTER COLUMN carried_datetime TYPE TEXT",
                "wrong_default": "ALTER TABLE qc.visit_index ALTER COLUMN sync_interval_minutes SET DEFAULT 99",
            }[drift])
        with pytest.raises(RuntimeError, match="父链字段"):
            command.upgrade(config, "head")
    with raw_pg.connect() as conn:
        assert set(conn.exec_driver_sql("SELECT version_num FROM public.alembic_version").scalars()) == {
            "20261023_000053", "20261025_000052"
        }
