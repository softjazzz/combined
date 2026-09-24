from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa

from scripts import import_visit_export as import_module


@pytest.fixture
def import_case(tmp_path: Path, monkeypatch):
    export_dir = tmp_path / "visit_export"
    export_dir.mkdir()
    csv_path = export_dir / "mr.csv"
    csv_path.write_text(
        "institute_id,patient_id,visit_id,name\nH1,P1,V1,Alice\n",
        encoding="utf-8",
    )
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE mr (institute_id TEXT, patient_id TEXT, visit_id TEXT, name TEXT)"))
    monkeypatch.setattr(import_module, "DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setattr(import_module.sa, "create_engine", lambda _url: engine)
    monkeypatch.setattr(import_module, "_ensure_schema", lambda _conn, _schema: None)
    monkeypatch.setattr(import_module, "_qualified_table", lambda _schema, table: f'"{table}"')
    stats = {"processed": 1, "updated": 1, "failed": 0, "skipped": 0}
    monkeypatch.setattr(import_module, "refresh_scene_bundles_for_rows", lambda **_kwargs: stats)
    monkeypatch.setattr(import_module, "refresh_domain_bundles_for_rows", lambda **_kwargs: stats)
    return export_dir, engine


def _row_count(engine: sa.Engine) -> int:
    with engine.connect() as conn:
        return conn.execute(sa.text("SELECT COUNT(*) FROM mr")).scalar_one()


def test_invalidation_precedes_first_cdm_write_and_publish_follows_refresh(import_case, monkeypatch) -> None:
    export_dir, engine = import_case
    events = []

    def invalidate(refs, *, session_factory):
        assert len(refs) == 1
        assert _row_count(engine) == 0
        events.append("invalidate")

    def refresh_scene(**kwargs):
        assert _row_count(engine) == 1
        assert kwargs["policy_version"].startswith("task-record-sync-invalidated-v1:")
        events.append(kwargs["scene"])
        return {"processed": 1, "updated": 1, "failed": 0}

    def publish(refs, *, staging_token, published_policy_version, session_factory):
        assert len(refs) == 1
        assert published_policy_version == ""
        assert staging_token.startswith("task-record-sync-invalidated-v1:")
        events.append("publish")

    monkeypatch.setattr(import_module, "invalidate_bundle_variants", invalidate)
    monkeypatch.setattr(import_module, "refresh_scene_bundles_for_rows", refresh_scene)
    monkeypatch.setattr(import_module, "publish_bundle_variants", publish)
    import_module.import_visit_export(export_dir=export_dir)
    assert events == ["invalidate", "running", "final", "publish"]


def test_no_rebuild_keeps_bundle_fenced(import_case, monkeypatch) -> None:
    export_dir, engine = import_case
    events = []
    monkeypatch.setattr(import_module, "invalidate_bundle_variants", lambda *args, **kwargs: events.append("invalidate"))
    monkeypatch.setattr(import_module, "publish_bundle_variants", lambda *args, **kwargs: events.append("publish"))
    result = import_module.import_visit_export(export_dir=export_dir, rebuild_bundles=False)
    assert _row_count(engine) == 1
    assert events == ["invalidate"]
    assert result["bundle_results"] == []


def test_partial_domain_refresh_fails_after_cdm_commit_without_publish(import_case, monkeypatch) -> None:
    export_dir, engine = import_case
    published = []

    def refresh_domain(**kwargs):
        return {"processed": 1, "updated": 0 if kwargs["domains"] == ("course",) else 1, "failed": 0}

    monkeypatch.setattr(import_module, "refresh_domain_bundles_for_rows", refresh_domain)
    monkeypatch.setattr(import_module, "publish_bundle_variants", lambda *args, **kwargs: published.append(True))
    with pytest.raises(RuntimeError, match="Bundle"):
        import_module.import_visit_export(export_dir=export_dir)
    assert _row_count(engine) == 1
    assert published == []


def test_invalidation_failure_prevents_cdm_write(import_case, monkeypatch) -> None:
    export_dir, engine = import_case

    def reject(*args, **kwargs):
        raise RuntimeError("fence failed")

    monkeypatch.setattr(import_module, "invalidate_bundle_variants", reject)
    with pytest.raises(RuntimeError, match="fence failed"):
        import_module.import_visit_export(export_dir=export_dir)
    assert _row_count(engine) == 0


def test_missing_case_coordinate_fails_before_cdm_write(import_case, monkeypatch) -> None:
    export_dir, engine = import_case
    (export_dir / "mr.csv").write_text(
        "institute_id,patient_id,visit_id,name\nH1,,V1,Alice\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="三坐标"):
        import_module.import_visit_export(export_dir=export_dir, rebuild_bundles=False)
    assert _row_count(engine) == 0


def test_postgres_lock_spans_the_entire_import_context() -> None:
    events = []

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            events.append("close")

        def execute(self, statement, params):
            events.append((str(statement), params["key"]))

        def rollback(self):
            events.append("rollback")

        def commit(self):
            events.append("commit")

    engine = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"), connect=lambda: FakeConnection())
    with import_module._bundle_write_lock(engine):
        events.append("import")
    assert events == [
        ("SELECT pg_advisory_lock(:key)", import_module._GLOBAL_LOCK_KEY),
        "import",
        "rollback",
        ("SELECT pg_advisory_unlock(:key)", import_module._GLOBAL_LOCK_KEY),
        "commit",
        "close",
    ]
