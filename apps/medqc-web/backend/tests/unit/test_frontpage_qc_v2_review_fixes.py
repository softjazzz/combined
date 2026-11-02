"""复审反例：真实持久账号SQL、内存结果保存与新旧任务轮次；不接业务库。"""

from datetime import datetime
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.routers import frontpage_qc_v2 as api
from app.database.models.v36_reports import SysUser
from app.services.frontpage_qc_v2 import FrontpageRef, evaluate_frontpage
from app.services.frontpage_qc_v2.access import resolve_frontpage_access
from app.services.frontpage_qc_v2.store import FrontpageQcStore, FrontpageQcNotFound
from app.services.frontpage_qc_v2.jobs import run_frontpage_qc_job
from tests.unit.frontpage_qc_v2_support import (
    make_doc,
    compliant_diagnoses,
    surgery_row,
)
from tests.unit.test_frontpage_qc_v2_router import FakeRepository


@pytest.fixture
def memory():
    engine = sa.create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    factory = sessionmaker(bind=engine)
    SysUser.__table__.create(engine)
    store = FrontpageQcStore(factory)
    store.create_all(engine)
    with factory() as session:
        for identity, role, institute, active, roles in [
            ("A", "qc_manager", "A", True, None),
            ("B", "coder", "B", True, None),
            ("admin", "admin", None, True, None),
            ("sync", "sync_admin", None, True, None),
            ("missing", "coder", None, True, None),
            ("disabled", "admin", None, False, None),
            ("broken", "admin", None, True, "{"),
            ("doctor", "doctor", "A", True, None),
        ]:
            session.add(
                SysUser(
                    id=identity,
                    username=identity,
                    display_name=identity,
                    role=role,
                    institute_id=institute,
                    is_active=active,
                    roles_json=roles,
                )
            )
        session.commit()
    yield factory, store
    engine.dispose()


def outcome(institute="A", **kwargs):
    doc = make_doc(**kwargs)
    doc.institute_id, doc.patient_id, doc.visit_id = (
        institute,
        "same-patient",
        "same-visit",
    )
    return evaluate_frontpage(doc)


def add_run(store, institute="A", actor="A"):
    return store.create_run(
        created_by=actor,
        refs=[FrontpageRef(institute, "same-patient", "same-visit")],
        filters={},
        ruleset_version="test",
    )


def test_persistent_owner_roles_and_institute_fail_closed(memory):
    from app.services.defect_rectification_service import RectificationError

    factory, _ = memory
    with factory() as session:
        assert resolve_frontpage_access(session, "A").institute_id == "A"
        assert resolve_frontpage_access(session, "B").institute_id == "B"
        assert resolve_frontpage_access(session, "admin").institute_id is None
        assert resolve_frontpage_access(session, "sync").institute_id is None
        for user in ["missing", "disabled", "broken", "absent", "", "doctor"]:
            with pytest.raises(RectificationError):
                resolve_frontpage_access(session, user)


def test_http_roles_and_requested_scope_cannot_expand_account(memory, monkeypatch):
    factory, global_store = memory
    monkeypatch.setattr(api, "_cdm_session_factory", lambda: factory)
    repo = FakeRepository(
        [
            FrontpageRef("A", "same-patient", "same-visit"),
            FrontpageRef("B", "same-patient", "same-visit"),
        ]
    )
    app = FastAPI()
    app.include_router(api.router)
    # HTTP声称全局管理员B院，真正持久账号仍是A院qc_manager。
    app.dependency_overrides[api.require_product_activation] = lambda: {
        "id": "A",
        "roles": ["admin"],
        "institute_id": "B",
    }
    app.dependency_overrides[api.get_record_repository] = lambda: repo
    app.dependency_overrides[api.get_home_institute] = lambda: "B"
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/frontpage-qc/records", params={"data_scope": "all"}
        )
        assert response.status_code == 200
        assert {r["institute_id"] for r in response.json()["data"]["items"]} == {"A"}
        assert (
            client.get(
                "/api/v1/frontpage-qc/record",
                params={
                    "institute_id": "B",
                    "patient_id": "same-patient",
                    "visit_id": "same-visit",
                },
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/api/v1/frontpage-qc/runs",
                json={
                    "record_refs": [
                        {
                            "institute_id": "B",
                            "patient_id": "same-patient",
                            "visit_id": "same-visit",
                        }
                    ]
                },
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/api/v1/frontpage-qc/records/export",
                json={
                    "record_refs": [
                        {
                            "institute_id": "B",
                            "patient_id": "same-patient",
                            "visit_id": "same-visit",
                        }
                    ]
                },
            ).status_code
            == 403
        )
        run = add_run(global_store, "B", "B")
        assert client.get("/api/v1/frontpage-qc/runs/" + run["id"]).status_code == 404


def test_scoped_sql_blocks_other_hospital_results_and_review(memory):
    factory, global_store = memory
    for institute in ["A", "B"]:
        run = add_run(global_store, institute, institute)
        global_store.save_outcome(
            run_id=run["id"], outcome=outcome(institute, mr_overrides={"sex": ""})
        )
    scoped = FrontpageQcStore(factory, institute_id="A", actor_id="A")
    assert (
        len(
            scoped.latest_by_keys(
                ["A|same-patient|same-visit", "B|same-patient|same-visit"]
            )
        )
        == 1
    )
    assert scoped.query_latest()[1] == 1
    assert len(scoped.latest_rows_for_analytics()) == 1
    assert scoped.latest_detail(FrontpageRef("B", "same-patient", "same-visit")) is None
    b = global_store.latest_detail(FrontpageRef("B", "same-patient", "same-visit"))
    assert scoped.latest_findings([b["id"]]) == []
    with pytest.raises(FrontpageQcNotFound):
        scoped.review_finding(
            b["findings"][0]["id"], status="confirmed", note="", reviewer="A"
        )


def test_injected_cross_hospital_rows_fail_closed(memory, monkeypatch):
    factory, _ = memory
    monkeypatch.setattr(api, "_cdm_session_factory", lambda: factory)

    class Injected(FakeRepository):
        def list_records(self, **kwargs):
            kwargs["institute_id"] = None
            return super().list_records(**kwargs)

    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[api.require_product_activation] = lambda: {"id": "A"}
    app.dependency_overrides[api.get_record_repository] = lambda: Injected(
        [FrontpageRef("B", "same-patient", "same-visit")]
    )
    app.dependency_overrides[api.get_home_institute] = lambda: "A"
    with TestClient(app) as client:
        assert client.get("/api/v1/frontpage-qc/records").status_code == 403


@pytest.mark.parametrize(
    "kind,expected,key",
    [("diagnosis", 99.0, "other_diag_code"), ("surgery", 99.5, "other_surgery_code")],
)
def test_secondary_sex_conflict_has_correct_deduction_and_saved_evidence(
    memory, kind, expected, key
):
    _, store = memory
    if kind == "diagnosis":
        rows = compliant_diagnoses()
        rows[1]["diagnosis_code"] = "C51.900"
        result = outcome(diagnoses=rows)
    else:
        result = outcome(
            surgeries=[surgery_row(1), surgery_row(2, code="65.0100", name="synthetic")]
        )
    assert result.score == expected
    assert result.findings[0].score_item == key
    run = add_run(store)
    store.save_outcome(run_id=run["id"], outcome=result)
    saved = store.latest_detail(FrontpageRef("A", "same-patient", "same-visit"))
    assert saved["score"] == expected
    assert saved["findings"][0]["score_item"] == key
    assert saved["findings"][0]["details"][0]["item_index"] == 1


def test_cancel_before_claim_never_loads_or_saves(memory):
    _, store = memory
    run = add_run(store)
    store.request_cancel(run["id"])

    def forbidden():
        raise AssertionError("cancelled task cannot read CDM")

    result = run_frontpage_qc_job(run["id"], store=store, cdm_session_factory=forbidden)
    assert result["status"] == "cancelled"
    assert store.query_latest()[1] == 0


def test_claim_is_cas_and_late_worker_cannot_revive_cancelled(memory):
    _, store = memory
    run = add_run(store)
    assert store.claim_run(run["id"]) is True
    assert store.claim_run(run["id"]) is False
    queued = add_run(store)
    store.request_cancel(queued["id"])
    store.update_run(queued["id"], status="running")
    assert store.get_run(queued["id"])["status"] == "cancelled"


def test_old_slow_run_cannot_replace_newer_success_and_only_one_latest(memory):
    factory, store = memory
    old = add_run(store)
    new = add_run(store)
    with factory() as session:
        session.execute(
            store.runs.update()
            .where(store.runs.c.id == old["id"])
            .values(created_at=datetime(2026, 1, 1))
        )
        session.execute(
            store.runs.update()
            .where(store.runs.c.id == new["id"])
            .values(created_at=datetime(2026, 1, 2))
        )
        session.commit()
    newer = store.save_outcome(run_id=new["id"], outcome=outcome())
    store.save_outcome(run_id=old["id"], outcome=outcome(mr_overrides={"sex": ""}))
    assert (
        store.latest_detail(FrontpageRef("A", "same-patient", "same-visit"))["id"]
        == newer
    )
    with factory() as session:
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(store.results)) == 2
        )
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(store.results)
                .where(store.results.c.is_latest.is_(True))
            )
            == 1
        )


def test_completion_cannot_overwrite_cancel_arriving_after_last_check(memory):
    _, store = memory
    run = add_run(store)
    assert store.claim_run(run["id"])
    assert not store.is_cancel_requested(run["id"])
    store.request_cancel(run["id"])
    store.update_run(
        run["id"], status="completed", processed_records=1, success_count=1
    )
    assert store.get_run(run["id"])["status"] == "cancelled"
    assert store.get_run(run["id"])["success_count"] == 1


def test_latest_partial_unique_index_rejects_second_true_row(memory):
    from sqlalchemy.exc import IntegrityError

    factory, store = memory
    run = add_run(store)
    store.save_outcome(run_id=run["id"], outcome=outcome())
    with factory() as session:
        row = dict(session.execute(sa.select(store.results)).mappings().one())
        row["id"] = "duplicate-latest"
        with pytest.raises(IntegrityError):
            session.execute(store.results.insert().values(**row))
        session.rollback()


def _business_migration():
    import importlib.util
    from pathlib import Path

    path = (
        Path(__file__).resolve().parents[2]
        / "alembic/versions/20261102_000061_frontpage_v2_business_heads.py"
    )
    spec = importlib.util.spec_from_file_location("frontpage_business_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_deduplicates_latest_by_run_not_save_order(memory, monkeypatch):
    from alembic.operations import Operations
    from alembic.migration import MigrationContext

    factory, store = memory
    old, new = add_run(store), add_run(store)
    for date, run in [(datetime(2026, 1, 1), old), (datetime(2026, 1, 2), new)]:
        with factory() as session:
            session.execute(
                store.runs.update()
                .where(store.runs.c.id == run["id"])
                .values(created_at=date)
            )
            session.commit()
    old_id = store.save_outcome(
        run_id=old["id"], outcome=outcome(mr_overrides={"sex": ""})
    )
    new_id = store.save_outcome(run_id=new["id"], outcome=outcome())
    engine = factory.kw["bind"]
    with engine.begin() as connection:
        index = next(
            i
            for i in store.results.indexes
            if i.name == "uq_frontpage_qc_results_latest"
        )
        index.drop(connection)
        connection.execute(store.results.update().values(is_latest=True))
        migration = _business_migration()
        monkeypatch.setattr(
            migration, "op", Operations(MigrationContext.configure(connection))
        )
        migration.upgrade()
        rows = dict(
            connection.execute(
                sa.select(store.results.c.id, store.results.c.is_latest)
            ).all()
        )
        assert rows == {old_id: False, new_id: True}
        assert any(
            i["name"] == "uq_frontpage_qc_results_latest" and i["unique"]
            for i in sa.inspect(connection).get_indexes("frontpage_qc_results")
        )
    assert (
        store.latest_detail(FrontpageRef("A", "same-patient", "same-visit"))["id"]
        == new_id
    )


def test_ambiguous_legacy_050_fails_signature_contract():
    migration = _business_migration()

    class Inspector:
        def has_table(self, table, schema):
            return True

        def get_columns(self, table, schema):
            return [{"name": "record_time"}]

    with pytest.raises(RuntimeError, match="ambiguous_050_history"):
        migration._assert_signature_history(Inspector(), "cdm")

    class Complete(Inspector):
        def get_columns(self, table, schema):
            return [{"name": name} for name in migration._SIGNATURE_COLUMNS[table]]

    migration._assert_signature_history(Complete(), "cdm")


@pytest.mark.parametrize(
    "kind,expected,key,cap",
    [
        ("diagnosis", 92.0, "other_diag_code", 4.0),
        ("surgery", 94.0, "other_surgery_code", 2.0),
    ],
)
def test_main_and_multiple_secondary_conflicts_keep_per_item_caps(
    memory, kind, expected, key, cap
):
    from tests.unit.frontpage_qc_v2_support import diagnosis_row

    _, store = memory
    if kind == "diagnosis":
        result = outcome(
            diagnoses=[
                diagnosis_row(n, "synthetic", "C51.900", main=n == 1)
                for n in range(1, 8)
            ]
            + [compliant_diagnoses()[-1]]
        )
    else:
        result = outcome(
            surgeries=[
                surgery_row(n, code="65.0100", name="synthetic") for n in range(1, 8)
            ]
        )
    assert result.score == expected
    score = next(item for item in result.item_scores if item.key == key)
    assert score.deduction == cap
    findings = [
        finding for finding in result.findings if finding.rule_id in ("L-06", "L-07")
    ]
    assert len(findings) == 2
    assert {d["item_index"] for finding in findings for d in finding.details} == set(
        range(7)
    )
    run = add_run(store)
    store.save_outcome(run_id=run["id"], outcome=result)
    saved = store.latest_detail(FrontpageRef("A", "same-patient", "same-visit"))
    assert saved["score"] == expected
    assert {
        f["score_item"] for f in saved["findings"] if f["rule_id"] in ("L-06", "L-07")
    } == {key, "main_diag_code" if kind == "diagnosis" else "main_surgery_code"}
