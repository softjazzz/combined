"""仅专属PG16合成库：材料读取/输入/副本，不执行医学规则或模型。"""
from copy import deepcopy
import json
import os
import re

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import make_url

from tests.fixtures.primary_material_fixtures import lifecycle_fixture, selection_fixture, synthetic_material


pytestmark = pytest.mark.skipif(
    not os.getenv("PRIMARY_MATERIAL_PG_TEST_URL"), reason="必须使用专属PG16 runner"
)


def _health():
    return {kind: {"state": "READY", "coverage": "OBSERVED_PUBLISHED",
                   "clinical_absence_confirmed": False} for kind in (
        "daily_course_record", "presurg_summary", "surgery_record", "postsurg_firstcourse_record")}


def _write_selection(connection, fixture, materials=None):
    from app.services import primary_material_readonly as m
    materials = deepcopy(materials if materials is not None else fixture["selection"]["materials"])
    policy, contracts = fixture["policy"], fixture["contracts"]
    selection = m.select_materials(policy, materials, _health())
    for value in materials:
        kind = value["document_type"]
        spec = contracts[kind].spec if value["source_namespace"] == "clinical" else m.cache_spec(kind)
        target = spec.publish
        columns = target.target_columns
        quoted = ",".join(m._ident(k) for k in columns)
        update = ",".join(f"{m._ident(k)}=EXCLUDED.{m._ident(k)}" for k in columns if k not in m.KEYS)
        connection.exec_driver_sql(
            f"INSERT INTO {m._ident(target.schema)}.{m._ident(target.table)} ({quoted}) "
            f"VALUES ({','.join(['%s']*len(columns))}) ON CONFLICT "
            f"({','.join(map(m._ident,m.KEYS))}) DO UPDATE SET {update}",
            tuple(value["target_payload"].get(k) for k in columns),
        )
        ref = value["publication"]
        connection.exec_driver_sql(
            "INSERT INTO sync_delivery.contract VALUES (%s,%s,%s,%s) "
            "ON CONFLICT (interface_name) DO UPDATE SET source_epoch=EXCLUDED.source_epoch,"
            "mapping_hash=EXCLUDED.mapping_hash,activation=EXCLUDED.activation",
            (spec.name, ref["source_epoch"], ref["mapping_hash"], ref["activation"]),
        )
        connection.exec_driver_sql(
            "INSERT INTO sync_delivery.receipt VALUES (%s,%s,%s,%s,%s,%s,%s) "
            "ON CONFLICT (interface_name,source_key_hash) DO UPDATE SET "
            "source_epoch=EXCLUDED.source_epoch,generation=EXCLUDED.generation,"
            "mapping_hash=EXCLUDED.mapping_hash,activation=EXCLUDED.activation,target_key_hash=EXCLUDED.target_key_hash",
            (spec.name, ref["source_key_hash"], ref["source_epoch"], ref["generation"],
             ref["mapping_hash"], ref["activation"], m.digest(value["native_key"])),
        )
    connection.exec_driver_sql(
        "INSERT INTO sync_material.primary_manifest VALUES (%s,%s::jsonb) ON CONFLICT DO NOTHING",
        (selection["selection_id"], json.dumps(selection, ensure_ascii=False)),
    )
    connection.exec_driver_sql(
        "INSERT INTO sync_material.primary_head VALUES (%s,%s) ON CONFLICT (case_id) "
        "DO UPDATE SET selection_id=EXCLUDED.selection_id", (policy.case_id, selection["selection_id"]),
    )
    return selection


def _schema(connection, fixture):
    from app.services import primary_material_readonly as m
    for schema in ("cdm", "sync_material", "sync_delivery"):
        connection.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
    for spec in [row["spec"] for row in fixture["target_rows"]]:
        target = spec.publish
        columns = ",".join(f"{m._ident(k)} text" for k in target.target_columns)
        connection.exec_driver_sql(f"CREATE TABLE {m._ident(target.schema)}.{m._ident(target.table)} "
                                   f"({columns},PRIMARY KEY({','.join(map(m._ident,m.KEYS))}))")
    statements = (
        "CREATE TABLE sync_material.primary_policy(case_id text PRIMARY KEY,policy_hash text)",
        "CREATE TABLE sync_material.primary_head(case_id text PRIMARY KEY,selection_id text)",
        "CREATE TABLE sync_material.primary_manifest(selection_id text PRIMARY KEY,result_json jsonb)",
        "CREATE TABLE sync_material.primary_coverage(case_id text,source_namespace text,coverage_json jsonb)",
        "CREATE TABLE sync_delivery.contract(interface_name text PRIMARY KEY,source_epoch uuid,mapping_hash text,activation bigint)",
        "CREATE TABLE sync_delivery.receipt(interface_name text,source_key_hash text,source_epoch uuid,"
        "generation bigint,mapping_hash text,activation bigint,target_key_hash text,PRIMARY KEY(interface_name,source_key_hash))",
    )
    for statement in statements:
        connection.exec_driver_sql(statement)
    p = fixture["policy"]
    connection.exec_driver_sql("INSERT INTO sync_material.primary_policy VALUES (%s,%s)", (p.case_id, p.policy_hash))
    for row in fixture["coverage_rows"]:
        connection.exec_driver_sql("INSERT INTO sync_material.primary_coverage VALUES (%s,%s,%s::jsonb)",
                                   (row["case_id"],row["source_namespace"],json.dumps(row["coverage_json"])))
    selected = _write_selection(connection, fixture)
    for schema in ("cdm", "sync_material", "sync_delivery"):
        connection.exec_driver_sql(f'GRANT USAGE ON SCHEMA "{schema}" TO primary_reader')
        # 仅本夹具创建的精确读取闭包对象；没有控制/原始/源库对象。
        connection.exec_driver_sql(f'GRANT SELECT ON ALL TABLES IN SCHEMA "{schema}" TO primary_reader')
    return selected


@pytest.fixture
def owned(monkeypatch, tmp_path, request):
    url = make_url(os.environ["PRIMARY_MATERIAL_PG_TEST_URL"])
    assert url.host == "127.0.0.1" and url.port == int(os.environ["PRIMARY_MATERIAL_PG_TEST_PORT"])
    assert re.fullmatch(r"delivery_cdm_[a-f0-9]{12}", url.database or "")
    admin = sa.create_engine(url)
    with admin.connect() as connection:
        assert connection.exec_driver_sql("SHOW server_version_num").scalar().startswith("16")
        assert connection.exec_driver_sql("SHOW cluster_name").scalar() == os.environ["PRIMARY_MATERIAL_PG_CLUSTER"]
    scenario = getattr(request, "param", "strict")
    fixture = (lifecycle_fixture(held=scenario == "lifecycle_held")
               if scenario.startswith("lifecycle_") else selection_fixture())
    with admin.begin() as connection:
        _schema(connection, fixture)
    reader = sa.create_engine(url.set(username="primary_reader"))
    from app.services import primary_material_projection as primary
    monkeypatch.setattr(primary, "load_read_plan", lambda identity: (fixture["policy"], fixture["contracts"]))
    monkeypatch.setenv("QC_PRIMARY_FOUR_MATERIAL_ENABLED", "true")
    monkeypatch.setenv("QC_CASE_MATERIAL_DIR", str(tmp_path / "materials"))
    try:
        from app.database import clinical_connection as clinical
        with clinical.selected({"id":"independent_cdm","binding":"synthetic-owned-primary"}):
            yield admin, reader, fixture
    finally:
        reader.dispose()
        admin.dispose()


def test_four_types_same_transaction_inputs_and_full_snapshot(owned):
    from app.database import clinical_connection as clinical
    from app.services import primary_material_projection as primary, case_material_snapshot as material
    from app.services.bundles import assembly
    from app.services.luxian_0609 import source_evidence_reader as reader
    admin, engine, fixture = owned
    with clinical.selected({"id":"independent_cdm","binding":"synthetic-owned-primary"}):
        with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
            with connection.begin():
                connection.exec_driver_sql("SET TRANSACTION READ ONLY")
                before_pid = connection.exec_driver_sql("SELECT pg_backend_pid()").scalar()
                state = {"protocol":material.PROTOCOL,"identity":["i","p","v"],"binding":clinical.source_binding(),
                         "schema":"cdm","engine":engine,"connection":connection,"columns":{},"tables":{},"queries":{}}
                primary.capture_into(state, connection, ("i","p","v"))
                value = state["primary_material_manifest"]
                assert len(value["materials"]) == 8 and all(x["selection_reason"]=="CLINICAL_PRIMARY" for x in value["items"])
                with material.recording(state):
                    for kind in primary.KINDS:
                        bundle = assembly._select_records(schema="cdm",table=kind,institute_id="i",patient_id="p",visit_id="v")
                        source = reader.read_luxian_0609_snapshot_source_rows(source_key=kind,institute_id="i",patient_id="p",visit_id="v",source_schema="cdm")
                        assert bundle[0]["version_id"] == source.rows[0]["version_id"]
                        assert bundle[0]["source_namespace"] == "clinical"
                        if kind == "surgery_record":
                            assert bundle[0]["surgery_process"] == "合成正文" and bundle[0]["record_content"] is None
                    docs = primary.project_documents(value)
                    assert len(docs)==8 and len({d["doc_key"] for d in docs})==8
                    assert sum(d["material_rule_usable"] for d in docs)==4
                assert before_pid == connection.exec_driver_sql("SELECT pg_backend_pid()").scalar()
                assert connection.in_transaction() and not connection.closed
                state.pop("engine");state.pop("connection")
        saved = material.persist("synthetic-primary-four",state)
        with material.activate(saved):
            for kind in primary.KINDS:
                assert primary.rows(("i","p","v"),kind)[0]["source_namespace"] == "clinical"
            assert primary.manifest()==value


def test_rr_concurrent_head_and_body_update_preserves_old_snapshot(owned):
    from app.database import clinical_connection as clinical
    from app.services import primary_material_projection as primary, primary_material_readonly as m, case_material_snapshot as material
    admin, engine, fixture = owned
    with clinical.selected({"id":"independent_cdm","binding":"synthetic-owned-primary"}):
        with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
            with connection.begin():
                connection.exec_driver_sql("SET TRANSACTION READ ONLY")
                first=primary.read_manifest(connection,("i","p","v"))
                changed=[]
                for old in fixture["selection"]["materials"]:
                    if old["source_namespace"]=="clinical":
                        value=synthetic_material(m,old["document_type"],"clinical",body=None)
                        value["publication"]["generation"]=2
                        value["version_id"]=m.digest([["clinical",value["publication"]["interface"],value["native_key"]],value["publication"]])
                        changed.append(value)
                    else:changed.append(deepcopy(old))
                with admin.begin() as writer:
                    _write_selection(writer,fixture,changed)
                second=primary.read_manifest(connection,("i","p","v"))
                assert first==second
        state={"protocol":material.PROTOCOL,"identity":["i","p","v"],"schema":"cdm","binding":clinical.source_binding(),
               "columns":{},"tables":{},"queries":{},"primary_material_manifest":first}
        frozen=material.persist("synthetic-original-selection",state)
        with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
            with connection.begin():
                connection.exec_driver_sql("SET TRANSACTION READ ONLY")
                latest=primary.read_manifest(connection,("i","p","v"))
                assert latest["selection_id"]!=first["selection_id"]
                assert all(item["selection_reason"]=="CACHE_FALLBACK" for item in latest["items"])
        with material.activate(material.load("synthetic-original-selection",("i","p","v"))):
            assert primary.manifest()==first and primary.manifest()!=latest
            assert primary.rows(("i","p","v"),"daily_course_record")[0]["source_namespace"]=="clinical"
        assert material.load("synthetic-original-selection",("i","p","v"))["fingerprint"]==frozen["fingerprint"]
        with admin.connect() as connection:
            old=fixture["selection"]["selection_id"]
            assert connection.exec_driver_sql("SELECT count(*) FROM sync_material.primary_manifest WHERE selection_id=%s",(old,)).scalar()==1


def test_latest_clinical_block_keeps_reliable_cache_and_full_alternatives(owned):
    from app.services import primary_material_projection as primary
    admin,engine,fixture=owned
    with admin.begin() as connection:
        connection.exec_driver_sql("UPDATE sync_material.primary_coverage SET coverage_json=%s::jsonb",
                                  (json.dumps({"publication_health":{"state":"BLOCKED"}}),))
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
        with connection.begin():
            connection.exec_driver_sql("SET TRANSACTION READ ONLY")
            value=primary.read_manifest(connection,("i","p","v"))
            assert all(item["selection_reason"]=="CACHE_FALLBACK" for item in value["items"])
            for kind in primary.KINDS:
                assert primary.project_rows(value,kind)[0]["source_namespace"]=="cache"
                assert not primary.scope_from_manifest(value,kind)["can_judge_clinical_absence"]
            assert len(primary.project_documents(value))==8
            assert len(value["materials"])==8


def test_missing_optional_metadata_keeps_base_transaction_and_denial_is_not_empty(owned):
    from app.services import primary_material_projection as primary
    admin,engine,fixture=owned
    with admin.begin() as connection:
        connection.exec_driver_sql("DROP TABLE sync_material.primary_head")
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
        with connection.begin():
            connection.exec_driver_sql("SET TRANSACTION READ ONLY")
            assert primary.read_manifest(connection,("i","p","v")) is None
            assert connection.exec_driver_sql("SELECT record_content FROM cdm.daily_course_record").scalar()=="合成正文"
    with admin.begin() as connection:
        _schema(connection,fixture)
        connection.exec_driver_sql("REVOKE SELECT ON sync_material.primary_head FROM primary_reader")
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
        with connection.begin():
            connection.exec_driver_sql("SET TRANSACTION READ ONLY")
            with pytest.raises(Exception) as error:
                primary.read_manifest(connection,("i","p","v"))
            assert getattr(error.value,"pgcode",None)=="42501"


def test_conflict_limits_only_related_body_and_keeps_display_versions(owned):
    from app.services import primary_material_projection as primary, primary_material_readonly as m
    admin,engine,fixture=owned
    changed=deepcopy(fixture["selection"]["materials"])
    for index,value in enumerate(changed):
        if value["document_type"]=="daily_course_record" and value["source_namespace"]=="clinical":
            replacement=synthetic_material(m,"daily_course_record","clinical",body="不同的合成正文")
            changed[index]=replacement
    with admin.begin() as connection:_write_selection(connection,fixture,changed)
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
        with connection.begin():
            connection.exec_driver_sql("SET TRANSACTION READ ONLY")
            value=primary.read_manifest(connection,("i","p","v"))
            daily=primary.project_rows(value,"daily_course_record")[0]
            assert daily["record_content"] is None
            assert primary.project_rows(value,"presurg_summary")[0]["record_content"]=="合成正文"
            docs=primary.project_documents(value)
            assert any(d["content"].find("不同的合成正文")>=0 for d in docs)
            assert any(d["material_selected"] and "差异" in d["material_notice"] for d in docs)


def _capture_lifecycle(engine):
    """真实只读RR连接取材，离开事务前去掉连接引用供全文快照保存。"""
    from app.database import clinical_connection as clinical
    from app.services import primary_material_projection as primary, case_material_snapshot as material
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
        with connection.begin():
            connection.exec_driver_sql("SET TRANSACTION READ ONLY")
            before = connection.exec_driver_sql("SELECT pg_backend_pid()").scalar()
            state = {"protocol": material.PROTOCOL, "identity": ["i", "p", "v"],
                     "binding": clinical.source_binding(), "schema": "cdm", "engine": engine,
                     "connection": connection, "columns": {}, "tables": {}, "queries": {}}
            primary.capture_into(state, connection, ("i", "p", "v"))
            assert before == connection.exec_driver_sql("SELECT pg_backend_pid()").scalar()
            assert connection.in_transaction() and not connection.closed
            _assert_lifecycle_inputs(state)
            state.pop("engine")
            state.pop("connection")
            return state


def _assert_lifecycle_inputs(state):
    from app.services import primary_material_projection as primary, case_material_snapshot as material
    from app.services.bundles import assembly
    from app.services.luxian_0609 import source_evidence_reader as reader
    value = state["primary_material_manifest"]
    with material.recording(state):
        for kind in primary.KINDS:
            expected = [row["version_id"] for row in primary.project_rows(value, kind)]
            bundle = assembly._select_records(schema="cdm", table=kind, institute_id="i", patient_id="p", visit_id="v", limit=100)
            source = reader.read_luxian_0609_snapshot_source_rows(
                source_key=kind, institute_id="i", patient_id="p", visit_id="v", source_schema="cdm")
            assert [row["version_id"] for row in bundle] == expected
            assert [row["version_id"] for row in source.rows] == expected
            assert not source.material_scope["can_judge_clinical_absence"]
        docs = primary.project_documents(value)
        assert {doc["version_id"] for doc in docs} == {entry["version_id"] for entry in value["materials"]}
        assert {doc["version_id"] for doc in docs if doc["material_rule_usable"]} == {
            item["selected_version"] for item in value["items"] if item["selected_version"] is not None}


def _set_lifecycle_coverage(admin, fixture, *, state="READY_FOR_INSPECTION", capture="COMPLETE", held=("daily-29",)):
    value = {"publication_health": {"state": state}, "record_lifecycle": {
        "mode": "record-hold-v1", "capture_state": capture, "held_document_ids": list(held)}}
    with admin.begin() as connection:
        connection.exec_driver_sql(
            "UPDATE sync_material.primary_coverage SET coverage_json=%s::jsonb WHERE case_id=%s",
            (json.dumps(value), fixture["policy"].health_case_id("daily_course_record")),
        )


@pytest.mark.parametrize("owned", ["lifecycle_held"], indirect=True)
def test_record_lifecycle_29_usable_and_held_full_business_chain(owned):
    from app.services import primary_material_projection as primary, case_material_snapshot as material
    _, engine, _ = owned
    state = _capture_lifecycle(engine)
    value = state["primary_material_manifest"]
    daily = primary.project_rows(value, "daily_course_record")
    assert sum(row["source_namespace"] == "clinical" for row in daily) == 29
    assert {row["document_id"] for row in daily} == {f"daily-{i:02d}" for i in range(29)} | {"cache-independent"}
    held = next(item for item in value["items"] if item["association_key"][-1] == "daily-29")
    assert held["selected_version"] is None and len(held["alternatives"]) == 2
    docs = primary.project_documents(value)
    assert len(docs) == 33 and sum(doc["material_rule_usable"] for doc in docs) == 31
    assert any(entry["lifecycle_admission"]["action"] == "HOLD" and entry["body"] == "合成正文"
               for entry in value["materials"] if entry["source_namespace"] == "clinical")
    saved = material.persist("synthetic-record-lifecycle-held", state)
    loaded = material.load("synthetic-record-lifecycle-held", ("i", "p", "v"))
    assert loaded["fingerprint"] == saved["fingerprint"]
    with material.activate(loaded):
        assert primary.manifest() == value
        assert primary.rows(("i", "p", "v"), "daily_course_record") == daily


@pytest.mark.parametrize("owned", ["lifecycle_usable"], indirect=True)
def test_latest_hold_pending_failure_and_restore_keep_frozen_business_copy(owned):
    from app.services import primary_material_projection as primary, primary_material_readonly as m, case_material_snapshot as material
    admin, engine, fixture = owned
    initial = _capture_lifecycle(engine)
    original = material.persist("synthetic-record-lifecycle-original", initial)
    original_version = next(entry["version_id"] for entry in initial["primary_material_manifest"]["materials"]
                            if entry["source_namespace"] == "clinical" and entry["native_key"][-1] == "daily-29")
    for state, capture in (("READY_FOR_INSPECTION", "COMPLETE"), ("BLOCKED", "PENDING"),
                           ("BLOCKED", "FAILED"), ("READY_FOR_INSPECTION", "COMPLETE")):
        # 失败或漏返的最新证据保留HOLD id；业务层不能从旧manifest复活它。
        _set_lifecycle_coverage(admin, fixture, state=state, capture=capture)
        current = _capture_lifecycle(engine)["primary_material_manifest"]
        rows = primary.project_rows(current, "daily_course_record")
        assert "daily-29" not in {row["document_id"] for row in rows}
        if capture == "PENDING":
            assert rows == []
        else:
            assert "cache-independent" in {row["document_id"] for row in rows}
        assert primary.project_rows(current, "presurg_summary")[0]["document_id"] == "other-kind-independent"
        assert any(entry["version_id"] == original_version for entry in current["materials"])
    restored = deepcopy(fixture["selection"]["materials"])
    restored = [synthetic_material(m, "daily_course_record", document_id="daily-29",
                                  contracts=fixture["contracts"], generation=2)
                if entry["source_namespace"] == "clinical" and entry["native_key"][-1] == "daily-29"
                else entry for entry in restored]
    with admin.begin() as writer:
        published = _write_selection(writer, fixture, restored)
    _set_lifecycle_coverage(admin, fixture, held=())
    latest = _capture_lifecycle(engine)["primary_material_manifest"]
    row = next(row for row in primary.project_rows(latest, "daily_course_record") if row["document_id"] == "daily-29")
    assert row["source_namespace"] == "clinical" and row["version_id"] != original_version
    assert latest["selection_id"] != initial["primary_material_manifest"]["selection_id"]
    with admin.connect() as connection:
        assert connection.exec_driver_sql("SELECT selection_id FROM sync_material.primary_head WHERE case_id=%s",
                                          (fixture["policy"].case_id,)).scalar() == published["selection_id"]
    loaded = material.load("synthetic-record-lifecycle-original", ("i", "p", "v"))
    assert loaded["fingerprint"] == original["fingerprint"]
    with material.activate(loaded):
        assert primary.manifest() == initial["primary_material_manifest"]
        assert next(row["version_id"] for row in primary.rows(("i", "p", "v"), "daily_course_record")
                    if row["document_id"] == "daily-29") == original_version


@pytest.mark.parametrize("owned", ["lifecycle_usable"], indirect=True)
def test_record_lifecycle_stale_version_and_denial_never_become_empty_success(owned):
    from app.services import primary_material_projection as primary, primary_material_readonly as m
    admin, engine, fixture = owned
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
        with connection.begin():
            connection.exec_driver_sql("SET TRANSACTION READ ONLY")
            before = m.read_primary_in_transaction(connection, fixture["policy"], fixture["contracts"])
            with admin.begin() as writer:
                writer.exec_driver_sql("UPDATE sync_delivery.receipt SET generation=generation+1 WHERE interface_name=%s",
                                      (fixture["contracts"]["daily_course_record"].spec.name,))
            assert m.read_primary_in_transaction(connection, fixture["policy"], fixture["contracts"]) == before
    stale = _capture_lifecycle(engine)["primary_material_manifest"]
    assert primary.project_rows(stale, "daily_course_record")[0]["document_id"] == "cache-independent"
    assert len(primary.project_rows(stale, "daily_course_record")) == 1
    assert sum(entry.get("publication_stale", False) for entry in stale["materials"]) == 30
    with admin.begin() as writer:
        writer.exec_driver_sql("REVOKE SELECT ON sync_material.primary_coverage FROM primary_reader")
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
        with connection.begin():
            connection.exec_driver_sql("SET TRANSACTION READ ONLY")
            with pytest.raises(Exception) as error:
                primary.read_manifest(connection, ("i", "p", "v"))
            assert getattr(error.value, "pgcode", None) == "42501"
