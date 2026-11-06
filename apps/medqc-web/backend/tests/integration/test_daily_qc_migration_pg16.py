"""只验证新增064在owned PG16的DDL、权限及租约，不运行质控。"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from joint_pg_support import ISOLATION_ACTIVE
from test_bundle_refresh_storage_pg16 import db, grant, migrate

pytestmark = pytest.mark.skipif(not ISOLATION_ACTIVE, reason="owned PG16 guard required")


@pytest.mark.parametrize("mode", ["single", "split"])
def test_063_to_064_preserves_refresh_and_claims_once(db, monkeypatch, mode):
    from app.services.daily_qc.contracts import PlanInput
    from app.services.daily_qc.store import ScheduleStore

    owner, api = db
    migrate(owner)
    with owner.begin() as connection:
        connection.execute(sa.text("CREATE TABLE qc.preserved_result(id integer PRIMARY KEY, value text)"))
        connection.execute(sa.text("INSERT INTO qc.preserved_result VALUES (1, 'existing-evidence')"))
        old_oid = connection.execute(sa.text("SELECT 'qc.bundle_refresh_jobs'::regclass::oid")).scalar_one()
        path = Path(__file__).resolve().parents[2] / "alembic/versions/20261106_000064_daily_qc_schedules.py"
        spec = importlib.util.spec_from_file_location("schedule_revision_064", path)
        revision = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(revision)
        assert revision.down_revision == "20261105_000063"
        monkeypatch.setenv("DB_SCHEMA_MODE", mode)
        with Operations.context(MigrationContext.configure(connection)):
            revision.upgrade()
        assert connection.execute(sa.text("SELECT 'qc.bundle_refresh_jobs'::regclass::oid")).scalar_one() == old_oid
        assert connection.execute(sa.text("SELECT value FROM qc.preserved_result")).scalar_one() == 'existing-evidence'
        schema = "qc" if mode == "split" else "public"
        default = next(c for c in sa.inspect(connection).get_columns("daily_qc_plans", schema=schema) if c["name"] == "enabled")
        assert default["default"] == "false"
    grant(owner)
    store = ScheduleStore(sessionmaker(bind=api), schema if mode == "split" else None)
    now = datetime(2026, 11, 6, 0, 0, tzinfo=timezone.utc)
    definition = PlanInput(name="synthetic", time_of_day="08:05", timezone="Asia/Shanghai",
                           institute_id="synthetic", rule_set_key="luxian_0609_qc_v1").model_dump()
    plan = store.save("manager", definition, now)
    assert not store.current(plan)["enabled"]
    assert store.list("other") == []
    with owner.begin() as connection:
        connection.execute(store.plans.update().where(store.plans.c.id == plan).values(enabled=True, next_due=now.replace(tzinfo=None)))
    with ThreadPoolExecutor(max_workers=2) as executor:
        claims = list(executor.map(lambda _: store.claim(now), range(2)))
    assert sum(claim is not None for claim in claims) == 1
    claimed = next(claim for claim in claims if claim)
    run = store.prepare(claimed, now)
    assert run["state"] == "submitting"
    assert store.claim(now) is None
    recovered = store.claim(now + timedelta(minutes=10))
    recovered_run = store.prepare(recovered, now + timedelta(minutes=10))
    assert recovered_run["id"] == run["id"]
    assert recovered_run["job_id"] == run["job_id"]
    with owner.connect() as connection:
        assert connection.execute(sa.select(sa.func.count()).select_from(store.runs)).scalar_one() == 1
