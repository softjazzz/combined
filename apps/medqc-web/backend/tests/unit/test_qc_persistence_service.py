"""Offline unit tests for QCPersistenceService (Batch 2 / B2-2 / P1-8)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any, Dict

from unittest.mock import AsyncMock

import pytest
import sqlalchemy as sa
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, MetaData, String, Table, Text, create_engine
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.services.qc_persistence_service as qps
from app.routers.qc import (
    _build_coding_qc_persistence_result,
    _build_formal_qc_persistence_result,
)
from app.services.coding_qc_service import CodingQCEngine
from app.services.frontpage_formal_qc import Category as FQCategory, FrontpageFormalQC
from app.services.qc_service import QCService


def _build_sqlite_persistence_env(
    monkeypatch: pytest.MonkeyPatch,
    *,
    include_origin: bool = False,
    shared_pool: bool = False,
):
    """Create an isolated in-memory SQLite schema and wire QCPersistenceService to it."""
    engine_kwargs: Dict[str, Any] = {"connect_args": {"check_same_thread": False}}
    if shared_pool:
        engine_kwargs["poolclass"] = StaticPool
    eng = create_engine("sqlite:///:memory:", **engine_kwargs)
    meta = MetaData()

    qc_results = Table(
        "qc_results",
        meta,
        Column("id", String(64), primary_key=True),
        Column("record_id", String(128), nullable=False),
        Column("rule_set", String(64)),
        Column("overall_score", Float),
        Column("grade", String(16)),
        Column("defect_count", Integer),
        Column("analysis_engine", String(64)),
        Column("analysis_date", DateTime),
        Column("raw_output", Text),
        Column("created_by", String(64)),
        Column("issues", Text),
        Column("metadata", Text),
        Column("created_at", DateTime),
        Column("updated_at", DateTime),
    )

    defect_columns = [
        Column("id", String(64), primary_key=True),
        Column("result_id", String(64)),
        Column("record_id", String(128), nullable=False),
        Column("department", String(128)),
        Column("rule_code", String(128)),
        Column("rule_name", String(256)),
        Column("description", Text),
        Column("severity", String(32)),
        Column("category", String(64)),
        Column("deduct_score", Float),
        Column("location", String(256)),
        Column("evidence", Text),
        Column("suggestion", Text),
        Column("status", String(32)),
        Column("created_at", DateTime),
        Column("updated_at", DateTime),
    ]
    if include_origin:
        defect_columns.append(Column("origin", String(32), default="auto"))

    qc_defects = Table("qc_defects", meta, *defect_columns)

    qc_defect_history = Table(
        "qc_defect_history",
        meta,
        Column("id", String(64), primary_key=True),
        Column("defect_id", String(64)),
        Column("action", String(64)),
        Column("actor_id", String(64)),
        Column("actor_name", String(128)),
        Column("details", Text),
        Column("created_at", DateTime),
    )

    notifications = Table(
        "notifications",
        meta,
        Column("id", String(64), primary_key=True),
        Column("type", String(64)),
        Column("title", String(256)),
        Column("content", Text),
        Column("record_id", String(128)),
        Column("severity", String(32)),
        Column("sender_id", String(64)),
        Column("recipient_id", String(64)),
        Column("related_type", String(64)),
        Column("related_id", String(64)),
        Column("is_read", Boolean),
        Column("read_at", DateTime),
        Column("created_at", DateTime),
    )

    meta.create_all(eng)
    tables = {
        ("qc", "qc_results"): qc_results,
        ("qc", "qc_defects"): qc_defects,
        ("qc", "qc_defect_history"): qc_defect_history,
        ("qc", "notifications"): notifications,
    }
    monkeypatch.setattr(qps, "_table", lambda schema, name: tables[(schema, name)])
    monkeypatch.setattr(qps, "pg_insert", sqlite_insert)

    session_factory = sessionmaker(bind=eng, autoflush=False, autocommit=False)
    service = qps.QCPersistenceService(session_factory=session_factory)
    return SimpleNamespace(
        engine=eng,
        session_factory=session_factory,
        service=service,
        qc_results=qc_results,
        qc_defects=qc_defects,
        qc_defect_history=qc_defect_history,
        notifications=notifications,
    )


def _issue(rule_code: str, category: str = "required", severity: str = "error", location: str = "field_a", description: str = "desc") -> Dict[str, Any]:
    return {
        "rule_code": rule_code,
        "rule_name": f"规则 {rule_code}",
        "category": category,
        "severity": severity,
        "location": location,
        "description": description,
    }


def test_subset_rerun_by_evaluated_rule_codes_preserves_unevaluated_defects_and_notification(monkeypatch):
    env = _build_sqlite_persistence_env(monkeypatch)
    actor = {"id": "u1", "username": "reviewer"}

    r1 = env.service._persist_analysis_sync(
        {
            "record_id": "frontpage::V001",
            "workflow_type": "frontpage",
            "visit_id": "V001",
            "overall_score": 60.0,
            "issues": [
                _issue("FP_REQ_01", category="required", severity="error", location="name"),
                _issue("FP_FMT_01", category="format", severity="warning", location="id_card"),
            ],
            "metadata": {"workflow_type": "frontpage", "visit_id": "V001"},
        },
        actor=actor,
    )
    assert r1["defects_created"] == 2

    # Subset rerun evaluates ONLY FP_REQ_01 and finds 0 issues in that subset.
    r2 = env.service._persist_analysis_sync(
        {
            "record_id": "frontpage::V001",
            "workflow_type": "frontpage",
            "visit_id": "V001",
            "overall_score": 100.0,
            "issues": [],
            "metadata": {
                "workflow_type": "frontpage",
                "visit_id": "V001",
                "categories": ["required"],
                "evaluated_rule_codes": ["FP_REQ_01"],
                "is_partial_run": True,
            },
        },
        actor=actor,
    )
    assert r2["defects_resolved"] == 1

    with env.session_factory() as s:
        defects = {
            row["rule_code"]: row["status"]
            for row in s.execute(sa.select(env.qc_defects.c.rule_code, env.qc_defects.c.status)).mappings().all()
        }
        assert defects == {"FP_REQ_01": "completed", "FP_FMT_01": "pending"}

        notif = s.execute(
            sa.select(
                env.notifications.c.title,
                env.notifications.c.content,
                env.notifications.c.severity,
                env.notifications.c.is_read,
            )
        ).mappings().one()
        assert notif["title"] == "首页质控发现问题"
        assert "1 条待处理问题" in notif["content"]
        assert notif["severity"] == "warning"
        assert notif["is_read"] is False


def test_subset_rerun_by_categories_and_severities_without_rule_codes(monkeypatch):
    env = _build_sqlite_persistence_env(monkeypatch)
    actor = {"id": "u1", "username": "reviewer"}

    env.service._persist_analysis_sync(
        {
            "record_id": "frontpage::V002",
            "workflow_type": "frontpage",
            "visit_id": "V002",
            "overall_score": 50.0,
            "issues": [
                _issue("FP_REQ_ERR", category="required", severity="error", location="name"),
                _issue("FP_REQ_WARN", category="required", severity="warning", location="phone"),
                _issue("FP_FMT_ERR", category="format", severity="error", location="id_card"),
            ],
            "metadata": {"workflow_type": "frontpage", "visit_id": "V002"},
        },
        actor=actor,
    )

    # Filter by categories=['required'] AND severities=['error'] without evaluated_rule_codes.
    r2 = env.service._persist_analysis_sync(
        {
            "record_id": "frontpage::V002",
            "workflow_type": "frontpage",
            "visit_id": "V002",
            "overall_score": 100.0,
            "issues": [],
            "metadata": {
                "workflow_type": "frontpage",
                "visit_id": "V002",
                "categories": ["required"],
                "severities": ["error"],
            },
        },
        actor=actor,
    )
    assert r2["defects_resolved"] == 1

    with env.session_factory() as s:
        defects = {
            row["rule_code"]: row["status"]
            for row in s.execute(sa.select(env.qc_defects.c.rule_code, env.qc_defects.c.status)).mappings().all()
        }
        assert defects == {
            "FP_REQ_ERR": "completed",
            "FP_REQ_WARN": "pending",
            "FP_FMT_ERR": "pending",
        }
        notif = s.execute(sa.select(env.notifications.c.title, env.notifications.c.content, env.notifications.c.is_read)).mappings().one()
        assert notif["title"] == "首页质控发现问题"
        assert "2 条待处理问题" in notif["content"]
        assert notif["is_read"] is False


def test_coding_qc_skip_llm_partial_run_does_not_auto_close_llm_defects(monkeypatch):
    env = _build_sqlite_persistence_env(monkeypatch)
    actor = {"id": "u1", "username": "coder"}

    full_payload = {"patient_id": "P01", "visit_id": "V_CODE_1", "skip_llm": False}
    full_report = {
        "total_issues": 2,
        "rule_issues": [{"rule_id": "CODE_RULE_01", "rule_name": "编码格式错误", "severity": "error", "dimension": "coding_rule"}],
        "llm_issues": [{"rule_id": "CODE_LLM_01", "rule_name": "主诊断选择不合理", "severity": "warning", "dimension": "coding_llm"}],
    }
    res_full = _build_coding_qc_persistence_result(full_payload, full_report, llm_executed=True)
    assert res_full["metadata"]["is_partial_run"] is False
    env.service._persist_analysis_sync(res_full, actor=actor)

    # Partial rerun with skip_llm=True and 0 rule issues should NOT close CODE_LLM_01.
    partial_payload = {"patient_id": "P01", "visit_id": "V_CODE_1", "skip_llm": True}
    partial_report = {"total_issues": 0, "rule_issues": [], "llm_issues": []}
    res_partial = _build_coding_qc_persistence_result(partial_payload, partial_report, llm_executed=False)
    assert res_partial["metadata"]["is_partial_run"] is True
    assert res_partial["metadata"]["skip_llm"] is True

    summary = env.service._persist_analysis_sync(res_partial, actor=actor)
    assert summary["defects_resolved"] == 0

    with env.session_factory() as s:
        defects = {
            row["rule_code"]: row["status"]
            for row in s.execute(sa.select(env.qc_defects.c.rule_code, env.qc_defects.c.status)).mappings().all()
        }
        assert defects == {"CODE_RULE_01": "pending", "CODE_LLM_01": "pending"}
        notif = s.execute(sa.select(env.notifications.c.title, env.notifications.c.is_read)).mappings().one()
        assert notif["title"] == "编码质控发现问题"
        assert notif["is_read"] is False


def test_full_rerun_auto_closes_fixed_defects_and_marks_notification_passed(monkeypatch):
    env = _build_sqlite_persistence_env(monkeypatch)
    actor = {"id": "u1", "username": "reviewer"}

    r1 = env.service._persist_analysis_sync(
        {
            "record_id": "settlement::V003",
            "workflow_type": "settlement",
            "visit_id": "V003",
            "overall_score": 70.0,
            "issues": [
                _issue("SET_01", category="settlement", severity="error", location="fee_total"),
                _issue("SET_02", category="settlement", severity="warning", location="icd_main"),
            ],
        },
        actor=actor,
    )
    assert r1["defects_created"] == 2

    # Full rerun (no subset metadata) with all issues resolved.
    r2 = env.service._persist_analysis_sync(
        {
            "record_id": "settlement::V003",
            "workflow_type": "settlement",
            "visit_id": "V003",
            "overall_score": 100.0,
            "issues": [],
        },
        actor=actor,
    )
    assert r2["defects_resolved"] == 2

    with env.session_factory() as s:
        statuses = [
            row["status"]
            for row in s.execute(sa.select(env.qc_defects.c.status)).mappings().all()
        ]
        assert statuses == ["completed", "completed"]

        actions = [
            row["action"]
            for row in s.execute(sa.select(env.qc_defect_history.c.action)).mappings().all()
        ]
        assert actions.count("auto_resolved") == 2

        notif = s.execute(sa.select(env.notifications.c.title, env.notifications.c.severity, env.notifications.c.is_read)).mappings().one()
        assert notif["title"] == "控费监测最近一次复核已通过"
        assert notif["severity"] == "info"
        assert notif["is_read"] is True


def test_manual_origin_defect_is_not_auto_closed_on_full_rerun(monkeypatch):
    env = _build_sqlite_persistence_env(monkeypatch, include_origin=True)
    actor = {"id": "u1", "username": "reviewer"}

    env.service._persist_analysis_sync(
        {
            "record_id": "frontpage::V_MANUAL",
            "workflow_type": "frontpage",
            "visit_id": "V_MANUAL",
            "overall_score": 80.0,
            "issues": [_issue("AUTO_01", category="required", severity="error", location="name")],
        },
        actor=actor,
    )
    with env.session_factory() as s:
        s.execute(
            sqlite_insert(env.qc_defects).values(
                id="manual-defect-1",
                result_id="manual-res",
                record_id="frontpage::V_MANUAL",
                rule_code="MANUAL_01",
                rule_name="人工缺陷",
                description="人工复核补充",
                severity="error",
                category="required",
                deduct_score=0.0,
                location="首页",
                status="pending",
                origin="manual",
            )
        )
        s.commit()

    r2 = env.service._persist_analysis_sync(
        {
            "record_id": "frontpage::V_MANUAL",
            "workflow_type": "frontpage",
            "visit_id": "V_MANUAL",
            "overall_score": 100.0,
            "issues": [],
        },
        actor=actor,
    )
    assert r2["defects_resolved"] == 1

    with env.session_factory() as s:
        defects = {
            row["rule_code"]: row["status"]
            for row in s.execute(sa.select(env.qc_defects.c.rule_code, env.qc_defects.c.status)).mappings().all()
        }
        assert defects == {"AUTO_01": "completed", "MANUAL_01": "pending"}


def test_zero_overall_score_preserved_and_none_falls_back_to_score(monkeypatch):
    env = _build_sqlite_persistence_env(monkeypatch)

    assert env.service._normalize_result({"record_id": "S1", "overall_score": 0, "score": 85})["overall_score"] == 0.0
    assert env.service._normalize_result({"record_id": "S2", "overall_score": 0.0, "score": 92.5})["overall_score"] == 0.0
    assert env.service._normalize_result({"record_id": "S3", "overall_score": None, "score": 77})["overall_score"] == 77.0
    assert env.service._normalize_result({"record_id": "S4", "overall_score": "", "score": 64.5})["overall_score"] == 64.5
    assert env.service._normalize_result({"record_id": "S5"})["overall_score"] == 0.0

    persisted = env.service._persist_analysis_sync(
        {"record_id": "S1", "overall_score": 0, "score": 85, "issues": []}
    )
    with env.session_factory() as s:
        row = s.execute(
            sa.select(env.qc_results.c.overall_score).where(env.qc_results.c.id == persisted["qc_result_id"])
        ).mappings().one()
        assert row["overall_score"] == 0.0


def test_department_fallback_precedence_with_record_dict(monkeypatch):
    env = _build_sqlite_persistence_env(monkeypatch)

    cases = [
        (
            {
                "record_id": "D1",
                "department": "外科",
                "metadata": {"department": "儿科", "record": {"department": "内科"}},
            },
            "儿科",
        ),
        (
            {
                "record_id": "D2",
                "department": "外科",
                "metadata": {"department": "", "record": {"department": "内科"}},
            },
            "内科",
        ),
        (
            {
                "record_id": "D3",
                "department": "心内科",
                "metadata": {"record": {"id": "D3", "department": None}},
            },
            "心内科",
        ),
        (
            {
                "record_id": "D4",
                "department": "外科",
                "metadata": {"record": {}},
            },
            "外科",
        ),
        (
            {
                "record_id": "D5",
                "department": "骨科",
                "metadata": {},
            },
            "骨科",
        ),
    ]
    for payload, expected in cases:
        norm = env.service._normalize_result(payload)
        assert norm["metadata"]["department"] == expected


def test_duplicate_issues_in_same_batch_deduplicated(monkeypatch):
    env = _build_sqlite_persistence_env(monkeypatch)
    actor = {"id": "u1", "username": "tester"}

    summary = env.service._persist_analysis_sync(
        {
            "record_id": "REC_DUP",
            "overall_score": 60.0,
            "issues": [
                _issue("R_DUP", category="general", location="病历正文", description="first"),
                _issue("R_DUP", category="general", location="病历正文", description="second"),
            ],
        },
        actor=actor,
    )
    assert summary["defects_created"] == 1
    assert summary["defects_updated"] == 0
    assert len(summary["defect_ids"]) == 1

    with env.session_factory() as s:
        rows = s.execute(
            sa.select(env.qc_defects.c.id, env.qc_defects.c.description).where(env.qc_defects.c.record_id == "REC_DUP")
        ).mappings().all()
        assert len(rows) == 1
        assert rows[0]["description"] == "second"

        hist = s.execute(
            sa.select(env.qc_defect_history.c.action).where(env.qc_defect_history.c.defect_id == rows[0]["id"])
        ).mappings().all()
        assert [h["action"] for h in hist] == ["auto_created"]


def test_concurrent_insert_conflict_does_not_inflate_created_or_write_phantom_history(monkeypatch):
    env = _build_sqlite_persistence_env(monkeypatch)
    race_issue = _issue("R_RACE", category="general", location="病历正文", description="from_worker_B")
    race_defect_id, _ = env.service._defect_identity("REC_RACE", race_issue)

    orig_execute = sa.orm.Session.execute
    injected = {"done": False}

    def _racing_execute(self, stmt, *args, **kwargs):
        res = orig_execute(self, stmt, *args, **kwargs)
        if not injected["done"] and "FROM qc_defects" in str(stmt):
            params = stmt.compile().params.values()
            if "REC_RACE" in params:
                injected["done"] = True
                with env.session_factory() as other:
                    other.execute(
                        sqlite_insert(env.qc_defects).values(
                            id=race_defect_id,
                            result_id="other-res",
                            record_id="REC_RACE",
                            rule_code="R_RACE",
                            rule_name="并发规则",
                            description="from_worker_A",
                            severity="warning",
                            category="general",
                            deduct_score=0.0,
                            location="病历正文",
                            status="pending",
                        )
                    )
                    other.commit()
        return res

    monkeypatch.setattr(sa.orm.Session, "execute", _racing_execute)
    summary = env.service._persist_analysis_sync(
        {"record_id": "REC_RACE", "overall_score": 70.0, "issues": [race_issue]},
        actor={"id": "u2", "username": "worker_B"},
    )
    assert summary["defects_created"] == 0
    assert summary["defects_updated"] == 1

    with env.session_factory() as s:
        row = s.execute(
            sa.select(env.qc_defects.c.description).where(env.qc_defects.c.id == race_defect_id)
        ).mappings().one()
        assert row["description"] == "from_worker_B"

        actions = [
            h["action"]
            for h in s.execute(
                sa.select(env.qc_defect_history.c.action).where(env.qc_defect_history.c.defect_id == race_defect_id)
            ).mappings().all()
        ]
        assert "auto_created" not in actions
        assert actions == ["auto_updated"]


def test_concurrent_auto_resolve_rowcount_zero_does_not_inflate_resolved_or_history(monkeypatch):
    env = _build_sqlite_persistence_env(monkeypatch)
    env.service._persist_analysis_sync(
        {
            "record_id": "REC_RES_RACE",
            "overall_score": 50.0,
            "issues": [_issue("R_CLOSE", category="general", location="病历正文")],
        },
        actor={"id": "u1", "username": "worker_A"},
    )

    orig_execute = sa.orm.Session.execute
    injected = {"done": False}

    def _racing_resolve_execute(self, stmt, *args, **kwargs):
        res = orig_execute(self, stmt, *args, **kwargs)
        if not injected["done"] and "FROM qc_defects" in str(stmt):
            params = stmt.compile().params.values()
            if "REC_RES_RACE" in params:
                injected["done"] = True
                with env.session_factory() as other:
                    other.execute(
                        env.qc_defects.update()
                        .where(env.qc_defects.c.record_id == "REC_RES_RACE")
                        .values(status="completed")
                    )
                    other.commit()
        return res

    monkeypatch.setattr(sa.orm.Session, "execute", _racing_resolve_execute)
    summary = env.service._persist_analysis_sync(
        {"record_id": "REC_RES_RACE", "overall_score": 100.0, "issues": []},
        actor={"id": "u2", "username": "worker_B"},
    )
    assert summary["defects_resolved"] == 0

    with env.session_factory() as s:
        actions = [
            h["action"]
            for h in s.execute(sa.select(env.qc_defect_history.c.action)).mappings().all()
        ]
        assert "auto_resolved" not in actions


def test_caller_metadata_propagation_for_formal_qc_and_qc_service():
    eng = FrontpageFormalQC()
    fp = {"basic_info": {"patient_id": "P1"}, "hospitalization": {"visit_id": "V_PROP"}}
    full_report = eng.validate(fp)
    sub_report = eng.validate(fp, categories=[FQCategory.REQUIRED])

    full_pers = _build_formal_qc_persistence_result(fp, full_report, {"visit_id": "V_PROP"})
    sub_pers = _build_formal_qc_persistence_result(fp, sub_report, {"visit_id": "V_PROP", "categories": ["required"]})

    assert full_pers["metadata"]["is_partial_run"] is False
    assert len(full_pers["metadata"]["evaluated_rule_codes"]) == full_report.total_rules
    assert sub_pers["metadata"]["is_partial_run"] is True
    assert len(sub_pers["metadata"]["evaluated_rule_codes"]) == sub_report.total_rules
    assert sub_report.total_rules < full_report.total_rules

    qc_service = QCService()
    subset_eval = asyncio.run(
        qc_service.evaluate(
            {
                "record_id": "REC_EVAL",
                "rules": [{"id": "RULE_A", "rule_code": "CODE_A", "name": "规则A", "category": "completeness"}],
            }
        )
    )
    assert subset_eval["metadata"]["is_partial_run"] is True
    assert subset_eval["metadata"]["evaluated_rule_codes"] == ["CODE_A"]

    full_eval = asyncio.run(qc_service.evaluate({"record_id": "REC_EVAL_FULL"}))
    assert full_eval["metadata"]["is_partial_run"] is False
    assert isinstance(full_eval["metadata"]["evaluated_rule_codes"], list)


def _seed_coding_d4_defect(env, *, visit_id: str, actor: Dict[str, Any]):
    """Seed an active D4 (exclusion) semantic defect via a completed full coding QC run."""
    payload = {"patient_id": "P_D4", "visit_id": visit_id, "skip_llm": False}
    initial_report = {
        "total_issues": 1,
        "rule_issues": [],
        "llm_issues": [
            {
                "dimension": "exclusion",
                "severity": "error",
                "code": "E10/E11",
                "rule_id": "D4_EXCLUSION_01",
                "rule_name": "1型与2型糖尿病编码互斥",
                "description": "E10 与 E11 互斥，不应同时编码",
                "suggestion": "请核实糖尿病分型并删除互斥编码",
            }
        ],
        "llm_review_completed": True,
        "llm_review_status": "completed",
    }
    res_seed = _build_coding_qc_persistence_result(payload, initial_report)
    assert res_seed["metadata"]["is_partial_run"] is False
    assert res_seed["metadata"]["llm_review_completed"] is True
    assert res_seed["metadata"]["llm_review_status"] == "completed"
    seed_summary = asyncio.run(env.service.persist_analysis(res_seed, actor=actor))
    assert seed_summary["defects_created"] == 1
    return payload


def test_coding_qc_llm_timeout_preserves_existing_d4_defect(monkeypatch):
    """Regression: stub LLM raising TimeoutError must NOT auto-close active D4 defect."""
    env = _build_sqlite_persistence_env(monkeypatch, shared_pool=True)
    actor = {"id": "u1", "username": "coder"}
    payload = _seed_coding_d4_defect(env, visit_id="V_CODE_TIMEOUT", actor=actor)

    stub_llm = AsyncMock()
    stub_llm.generate.side_effect = TimeoutError("LLM semantic review timed out")
    engine = CodingQCEngine(llm_client=stub_llm)
    frontpage = {"diagnoses": [{"code": "I21.001", "name": "急性心梗"}]}
    report_dict = asyncio.run(engine.run_all(frontpage)).to_dict()

    assert report_dict["llm_review_completed"] is False
    assert report_dict["llm_review_status"] == "timeout"

    pers_input = _build_coding_qc_persistence_result(payload, report_dict)
    assert pers_input["metadata"]["is_partial_run"] is True
    assert pers_input["metadata"]["llm_review_completed"] is False
    assert pers_input["metadata"]["llm_review_status"] == "timeout"

    summary = asyncio.run(env.service.persist_analysis(pers_input, actor=actor))
    assert summary["defects_resolved"] == 0

    with env.session_factory() as s:
        row = s.execute(
            sa.select(env.qc_defects.c.rule_code, env.qc_defects.c.status)
            .where(env.qc_defects.c.rule_code == "D4_EXCLUSION_01")
        ).mappings().one()
        assert row["status"] == "pending"


@pytest.mark.parametrize(
    "bad_output",
    [
        "not valid json garbage",
        "",
        "{}",
        '{"issues": [{}]}',
        '[{"issues": []}]',
        '```json\n[{"issues": []}]\n```',
        '{"issues": [{"severity": "high"}]}',
    ],
)
def test_coding_qc_llm_parse_failure_preserves_existing_d4_defect(monkeypatch, bad_output):
    """Regression: unparseable/empty/malformed-schema LLM output must NOT auto-close active D4 defect."""
    env = _build_sqlite_persistence_env(monkeypatch, shared_pool=True)
    actor = {"id": "u1", "username": "coder"}
    payload = _seed_coding_d4_defect(env, visit_id="V_CODE_PARSE_FAIL", actor=actor)

    stub_llm = AsyncMock()
    stub_llm.generate.return_value = {"choices": [{"message": {"content": bad_output}}]}
    engine = CodingQCEngine(llm_client=stub_llm)
    frontpage = {"diagnoses": [{"code": "I21.001", "name": "急性心梗"}]}
    report_dict = asyncio.run(engine.run_all(frontpage)).to_dict()

    assert report_dict["llm_review_completed"] is False
    assert report_dict["llm_review_status"] == "parse_failed"

    pers_input = _build_coding_qc_persistence_result(payload, report_dict)
    assert pers_input["metadata"]["is_partial_run"] is True
    assert pers_input["metadata"]["llm_review_completed"] is False
    assert pers_input["metadata"]["llm_review_status"] == "parse_failed"

    summary = asyncio.run(env.service.persist_analysis(pers_input, actor=actor))
    assert summary["defects_resolved"] == 0

    with env.session_factory() as s:
        row = s.execute(
            sa.select(env.qc_defects.c.rule_code, env.qc_defects.c.status)
            .where(env.qc_defects.c.rule_code == "D4_EXCLUSION_01")
        ).mappings().one()
        assert row["status"] == "pending"


def test_coding_qc_llm_valid_issue_payload_marks_completed_and_not_partial(monkeypatch):
    """Valid semantic JSON with a well-formed issue marks completed and is_partial_run=False."""
    env = _build_sqlite_persistence_env(monkeypatch, shared_pool=True)
    actor = {"id": "u1", "username": "coder"}
    payload = _seed_coding_d4_defect(env, visit_id="V_CODE_VALID_ISSUE", actor=actor)

    stub_llm = AsyncMock()
    stub_llm.generate.return_value = {
        "choices": [
            {
                "message": {
                    "content": (
                        '{"issues": [{"dimension": "merge", "severity": "warning", '
                        '"code": "K35/K65", "description": "阑尾炎与腹膜炎应使用合并编码", '
                        '"suggestion": "改用 K35.2"}]}'
                    )
                }
            }
        ]
    }
    engine = CodingQCEngine(llm_client=stub_llm)
    frontpage = {"diagnoses": [{"code": "I21.001", "name": "急性心梗"}]}
    report_dict = asyncio.run(engine.run_all(frontpage)).to_dict()

    assert report_dict["llm_review_completed"] is True
    assert report_dict["llm_review_status"] == "completed"
    assert len(report_dict["llm_issues"]) == 1

    pers_input = _build_coding_qc_persistence_result(payload, report_dict)
    assert pers_input["metadata"]["is_partial_run"] is False
    assert pers_input["metadata"]["llm_review_completed"] is True
    assert pers_input["metadata"]["llm_review_status"] == "completed"

    summary = asyncio.run(env.service.persist_analysis(pers_input, actor=actor))
    assert summary["defects_created"] == 1
    assert summary["defects_resolved"] == 1


def test_coding_qc_llm_valid_empty_issues_auto_closes_fixed_d4_defect(monkeypatch):
    """Valid empty-issues semantic JSON marks review completed and auto-closes fixed D4 defect."""
    env = _build_sqlite_persistence_env(monkeypatch, shared_pool=True)
    actor = {"id": "u1", "username": "coder"}
    payload = _seed_coding_d4_defect(env, visit_id="V_CODE_FIXED", actor=actor)

    stub_llm = AsyncMock()
    stub_llm.generate.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"issues": [], "summary": {"total_issues": 0, "overall_assessment": "通过"}}'
                }
            }
        ]
    }
    engine = CodingQCEngine(llm_client=stub_llm)
    frontpage = {"diagnoses": [{"code": "I21.001", "name": "急性心梗"}]}
    report_dict = asyncio.run(engine.run_all(frontpage)).to_dict()

    assert report_dict["llm_review_completed"] is True
    assert report_dict["llm_review_status"] == "completed"

    pers_input = _build_coding_qc_persistence_result(payload, report_dict)
    assert pers_input["metadata"]["is_partial_run"] is False
    assert pers_input["metadata"]["llm_review_completed"] is True
    assert pers_input["metadata"]["llm_review_status"] == "completed"

    summary = asyncio.run(env.service.persist_analysis(pers_input, actor=actor))
    assert summary["defects_resolved"] == 1

    with env.session_factory() as s:
        row = s.execute(
            sa.select(env.qc_defects.c.rule_code, env.qc_defects.c.status)
            .where(env.qc_defects.c.rule_code == "D4_EXCLUSION_01")
        ).mappings().one()
        assert row["status"] == "completed"


def test_coding_qc_skip_llm_engine_run_preserves_existing_d4_defect(monkeypatch):
    """skip_llm=True through CodingQCEngine.run_all produces skipped status and preserves D4 defect."""
    env = _build_sqlite_persistence_env(monkeypatch, shared_pool=True)
    actor = {"id": "u1", "username": "coder"}
    _seed_coding_d4_defect(env, visit_id="V_CODE_SKIP", actor=actor)

    stub_llm = AsyncMock()
    engine = CodingQCEngine(llm_client=stub_llm)
    frontpage = {"diagnoses": [{"code": "I21.001", "name": "急性心梗"}]}
    report_dict = asyncio.run(engine.run_all(frontpage, skip_llm=True)).to_dict()

    assert report_dict["llm_review_completed"] is False
    assert report_dict["llm_review_status"] == "skipped"
    stub_llm.generate.assert_not_awaited()

    skip_payload = {"patient_id": "P_D4", "visit_id": "V_CODE_SKIP", "skip_llm": True}
    pers_input = _build_coding_qc_persistence_result(skip_payload, report_dict)
    assert pers_input["metadata"]["is_partial_run"] is True
    assert pers_input["metadata"]["llm_review_completed"] is False
    assert pers_input["metadata"]["llm_review_status"] == "skipped"

    summary = asyncio.run(env.service.persist_analysis(pers_input, actor=actor))
    assert summary["defects_resolved"] == 0

    with env.session_factory() as s:
        row = s.execute(
            sa.select(env.qc_defects.c.rule_code, env.qc_defects.c.status)
            .where(env.qc_defects.c.rule_code == "D4_EXCLUSION_01")
        ).mappings().one()
        assert row["status"] == "pending"
