"""规则验收摘要白名单与无初始化写入证明；仅合成内存SQLite。"""
from datetime import datetime
import json
from uuid import uuid4

from fastapi import HTTPException
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from app.services.qc_agent import business_rule_validation as reader


RULE = "LX0609-01-01-01"
MANAGER = {"context": {"view": "manager"}}
USER = {"roles": ["qc_manager"]}
PHI = "患者隐私与原文绝不进入摘要"


def detail():
    run_id = str(uuid4())
    return {"rule": {"rule_id": RULE, "name": "合成规则", "source_document": "入院记录", "release_scope": "acceptance_only", "unknown": PHI},
            "stage": "pending_approval",
            "coverage": {"counts": {"compliant": {"synthetic": 2, "real_copy": 1, "unknown": PHI}}, "gaps": ["data_gap"], "acceptance_cases": 3, "unknown": PHI},
            "runs": [{"id": run_id, "rule_id": RULE, "state": "bound", "created_at": "2026-10-02T00:00:00+00:00",
                      "build_kind": "development", "execution_version": {"lx0609_task_runtime": {"implementation": {"kind": "development", "git_commit": "abc123", "unknown": PHI}, "unknown": PHI}, "unknown": PHI},
                      "cases": [PHI], "regression_cases": [PHI], "created_by": PHI, "job_id": PHI, "unknown": PHI}],
            "events": [{"rule_id": RULE, "run_id": run_id, "kind": "conclusion", "decision": "accepted", "created_at": "2026-10-02T01:00:00+00:00", "note": PHI, "payload": {"unknown": PHI}, "actor": PHI, "item_id": PHI},
                       {"rule_id": RULE, "run_id": run_id, "kind": "case_review", "decision": "confirmed", "note": PHI},
                       {"rule_id": RULE, "run_id": "other-run", "kind": "approval", "decision": "approved", "note": PHI}],
            "cases": [PHI], "latest_run_rows": [{"result": {"evidence": PHI}}], "acceptance_blockers": [PHI], "regression_gaps": [{"reason": PHI}], "unknown": PHI}


def test_projection_preserves_owner_stage_counts_decisions_and_omits_phi():
    payload = detail()
    result = reader.project_rule_validation(payload, RULE)
    assert result["stage"] == payload["stage"]
    assert result["coverage"] == {"counts": {"compliant": {"synthetic": 2, "real_copy": 1}}, "gaps": ["data_gap"], "acceptance_cases": 3}
    assert result["runs"][0]["saved_decisions"] == [{"kind": "conclusion", "decision": "accepted", "created_at": "2026-10-02T01:00:00+00:00"}]
    assert result["runs"][0]["execution_version"] == {"lx0609_task_runtime": {"implementation": {"kind": "development", "git_commit": "abc123"}}}
    assert PHI not in json.dumps(result, ensure_ascii=False)
    assert "events" not in result and "cases" not in result and "acceptance_blockers" not in result
    assert result["entry_path"] == f"/workstation-v4/rules/validation/{RULE}"
    assert "不是当前病例或科室" in result["scope_note"]
    assert "不能证明当前规则已通过" in result["runs"][0]["version_note"]


def test_chinese_card_uses_safe_counts_and_decisions_without_raw_notes_or_entry_path():
    projected = reader.project_rule_validation(detail(), RULE)
    projected.update(cases=[PHI], notes=PHI, events=[{"note": PHI}], entry_path="/fake-user-input-path")
    projected["runs"][0].update(cases=[PHI], note=PHI, created_by=PHI)
    projected["runs"][0]["saved_decisions"].append({"kind": "approval", "decision": "approved", "created_at": "2026-10-02T02:00:00+00:00", "note": PHI})
    text = reader.rule_validation_card_text(projected)
    assert "记录阶段：待审批" in text
    assert "合规：合成样本 2；真实病历副本样本 1" in text
    assert "不合规：合成样本 未提供" in text
    assert "保存结论：已接受" in text and "保存审批：已批准" in text
    assert "2026年10月02日 09:00:00（UTC+08:00）" in text
    assert "代码版本：abc123" in text
    assert PHI not in text and "/fake-user-input-path" not in text
    assert "pending_approval" not in text and "accepted" not in text


def test_card_missing_coverage_versions_and_runs_do_not_become_zero_or_pass():
    text = reader.rule_validation_card_text({"rule": {"rule_id": RULE}, "stage": "released", "runs": []})
    assert "记录阶段：已发布" in text
    assert "未提供覆盖字段" in text
    assert "本摘要未展示保存运行" in text
    assert "不是当前病例或科室质控结果" in text
    assert "0" not in text.split("测试样本覆盖", 1)[1]


def test_missing_version_and_metadata_are_explicit_not_current_catalog_fallback():
    payload = detail()
    payload["coverage"] = None
    payload["runs"][0]["execution_version"] = None
    payload["events"] = None
    result = reader.project_rule_validation(payload, RULE)
    assert "coverage" not in result
    assert result["runs"][0]["execution_version"] is None
    assert "未提供可用执行版本" in result["runs"][0]["version_note"]
    assert "saved_decisions" not in result["runs"][0]
    assert len(result["data_notes"]) == 2


def test_unknown_gap_or_kind_only_version_cannot_become_complete_coverage_or_identified_version():
    payload = detail()
    payload["coverage"]["gaps"] = [{"patient": PHI}]
    payload["runs"][0]["execution_version"] = {"lx0609_task_runtime": {"implementation": {"kind": "development"}}}
    result = reader.project_rule_validation(payload, RULE)
    assert "gaps" not in result["coverage"]
    assert "覆盖字段不完整" in result["data_notes"][0]
    assert "未提供可用执行版本" in result["runs"][0]["version_note"]
    assert PHI not in json.dumps(result, ensure_ascii=False)


@pytest.mark.parametrize("rule_id", ["other", "../secret", "LX0609-01-01-01/../../secret", "LX0609-01-01-01?target=secret"])
def test_entry_rule_id_rejects_arbitrary_paths(rule_id):
    with pytest.raises(HTTPException) as exc:
        reader.project_rule_validation(detail(), rule_id)
    assert exc.value.status_code == 422


@pytest.mark.parametrize("metadata,user", [({"context": {"view": "doctor"}}, {"roles": ["admin"]}),
                                          (MANAGER, {"roles": ["doctor"]}), (MANAGER, {"roles": ["super_admin"]})])
def test_role_and_view_match_existing_endpoint_without_doctor_expansion(monkeypatch, metadata, user):
    monkeypatch.setattr(reader, "_readonly_service", lambda: pytest.fail("拒绝身份不得读取数据库"))
    with pytest.raises(HTTPException) as exc:
        reader.read_rule_validation(RULE, metadata, user)
    assert exc.value.status_code == 403


@pytest.mark.parametrize("changes", [{"stage": None}, {"stage": []}, {"stage": "future_stage"}, {"rule": {"rule_id": "LX0609-01-01-02"}}])
def test_invalid_owner_identity_or_stage_never_claims_pass(changes):
    with pytest.raises(HTTPException) as exc:
        reader.project_rule_validation({**detail(), **changes}, RULE)
    assert exc.value.status_code == 502


def setup_database(monkeypatch, *, create=True):
    from app.database import connection
    from app.services import rule_validation as owner
    from app.services import custom_qc_sample_pool_service as pools
    engine = sa.create_engine("sqlite://")
    monkeypatch.setattr(connection, "SessionLocal", sessionmaker(bind=engine))
    monkeypatch.setattr(connection, "DB_SCHEMA_MODE", "single")
    monkeypatch.setattr(owner, "rule_catalog", lambda: {RULE: detail()["rule"]})
    monkeypatch.setattr(pools, "_sample_pool_items_table", lambda: pytest.fail("不得初始化样本池表"))
    monkeypatch.setattr(owner, "_tables", lambda: pytest.fail("不得初始化验收表"))
    service = reader._readonly_service()
    if create:
        for table in (service.items, service.runs, service.events):
            table.create(engine)
    monkeypatch.setattr(sa.MetaData, "create_all", lambda *_args, **_kwargs: pytest.fail("读取路径不得create_all"))
    return engine, service


@pytest.mark.asyncio
@pytest.mark.parametrize("answer_revision,expected_stage", [(0, "pending_approval"), (None, "ready_to_run")])
async def test_existing_owner_reads_only_select_and_keeps_saved_conclusion(monkeypatch, answer_revision, expected_stage):
    engine, service = setup_database(monkeypatch)
    run_id, item_id = str(uuid4()), str(uuid4())
    case = {"item_id": item_id, "record_ref": {"institute_id": "H", "patient_id": "P", "visit_id": "V"}, "case_title": PHI,
            "expected_status": "compliant", "source_kind": "synthetic", "purpose": "acceptance",
            "answer_revision": answer_revision}
    from app.services.custom_qc_sample_pool_service import CUSTOMER_TEST_POOL_ID
    with engine.begin() as conn:
        conn.execute(service.items.insert().values(id=item_id, pool_id=CUSTOMER_TEST_POOL_ID, patient_name=PHI,
                     raw_payload_json=json.dumps({"golden_answers": [{"qc_point_id": RULE, "expected_status": "compliant", "human_reason": PHI, "purpose": "acceptance"}]})))
        conn.execute(service.runs.insert().values(id=run_id, rule_id=RULE, cases_json=json.dumps({"cases": [case]}), state="bound", job_id="saved-job",
                     created_by=PHI, created_at=datetime(2026, 10, 2), execution_version_json=None))
        conn.execute(service.events.insert().values(id=str(uuid4()), rule_id=RULE, run_id=run_id, kind="conclusion", decision="accepted", note=PHI,
                     actor=PHI, created_at=datetime(2026, 10, 2)))
    from app.services import custom_qc_workspace_service as workspace_module
    class ReadonlyWorkspace:
        def __init__(self, *, readonly):
            assert readonly is True
        def get_batch_job_for_processing(self, *, job_id):
            assert job_id == "saved-job"
            return {"status": "completed"}
        def _load_batch_job_canonical_items(self, *, job, allow_partial):
            return [{"rule_id": RULE, "institute_id": "H", "patient_id": "P", "visit_id": "V", "status": "compliant", "conclusion": PHI}]
    monkeypatch.setattr(workspace_module, "CustomQCWorkspaceService", ReadonlyWorkspace)
    statements = []
    @sa.event.listens_for(engine, "before_cursor_execute")
    def only_select(_conn, _cursor, statement, _params, _context, _executemany):
        statements.append(statement)
        assert statement.lstrip().upper().startswith("SELECT")
    result = reader.read_rule_validation(RULE, MANAGER, USER)
    assert result["stage"] == expected_stage
    assert result["coverage"]["counts"]["compliant"]["synthetic"] == 1
    assert result["coverage"]["acceptance_cases"] == 1
    assert result["runs"][0]["saved_decisions"][0]["decision"] == "accepted"
    assert statements and PHI not in json.dumps(result, ensure_ascii=False)
    # 原详情的 _read_job/Canonical hydrate/compare_cases/summarize/derive_stage 全链
    # 同源同输入，仅替换其旧默认构造为同一只读workspace；不重判任何stage。
    from app.routers import rule_validation as source_router, qc_sichuan
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: ReadonlyWorkspace(readonly=True))
    monkeypatch.setattr(source_router, "_project_result", lambda item: item)
    source_detail = await source_router._detail(None, service, RULE, USER)
    expected = reader.project_rule_validation(source_detail, RULE)
    assert result == expected
    engine.dispose()


def test_missing_tables_returns_503_without_building_tables(monkeypatch):
    engine, _service = setup_database(monkeypatch, create=False)
    with pytest.raises(HTTPException) as exc:
        reader.read_rule_validation(RULE, MANAGER, USER)
    assert exc.value.status_code == 503
    assert sa.inspect(engine).get_table_names() == []
    engine.dispose()


@pytest.mark.parametrize("status", [404, 409, 503])
def test_source_failure_never_becomes_zero_or_pass(monkeypatch, status):
    def fail():
        raise HTTPException(status, "读取失败")
    monkeypatch.setattr(reader, "_readonly_service", fail)
    with pytest.raises(HTTPException) as exc:
        reader.read_rule_validation(RULE, MANAGER, USER)
    assert exc.value.status_code == status
