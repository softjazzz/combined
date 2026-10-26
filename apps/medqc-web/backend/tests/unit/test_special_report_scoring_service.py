"""报表专用评分消费：合成结果及真实SQLite评分标准，不访问业务库。"""

import json
from copy import deepcopy
from datetime import datetime

import pytest
import sqlalchemy as sa
from app.database.models.v36_reports import (
    QCScoringDefaultBinding,
    QCScoringGroup,
    QCScoringItem,
    QCScoringStandard,
)
from app.services import scoring_service
from app.services import scoring_standard_service as standards
from app.services.special_report_scoring_service import score_special_report_cases
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

CASE = ("synthetic-hospital", "synthetic-patient", "synthetic-visit")
KEY = "luxian_0609_qc_v1"


def standard(**changes):
    result = {
        "id": "synthetic-standard",
        "name": "合成报表标准",
        "scene": "final",
        "status": "active",
        "version_seq": 3,
        "binding_version_seq": 2,
        "binding_purpose": "special_report",
        "rule_set_key": KEY,
        "updated_at": "2026-10-03T00:00:00",
        "base_score": 100,
        "grade_bands": [
            {"name": "甲", "min_score": 90, "max_score": 100},
            {"name": "乙", "min_score": 0, "max_score": 90},
        ],
        "veto_grade": "乙",
        "groups": [{"group_name": "合成项目组", "max_deduction": 3}],
        "items": [
            {
                "group_name": "合成项目组",
                "rule_id": "LX0609-001",
                "deduction": 2,
                "department_scope_mode": "all",
                "department_refs": [],
                "enabled": True,
            }
        ],
    }
    result.update(changes)
    return result


def result(**changes):
    data = {
        "status": "ready",
        "rule_set_key": KEY,
        "rule_set_version": "synthetic-v1",
        "envelope_id": "synthetic-envelope",
        "department_name": "合成科室",
        "items": [{"rule_id": "LX0609-001", "is_confirmed_issue": True}],
        "historical_score": 45,
        "historical_grade": "旧等级",
    }
    data.update(changes)
    return data


def test_one_standard_read_uses_real_scoring_owner_and_does_not_modify_history(
    monkeypatch,
):
    inputs = {CASE: result(), (CASE[0], CASE[1], "synthetic-visit-2"): result(items=[])}
    baseline = deepcopy(inputs)
    chosen = standard()
    before = deepcopy(chosen)
    calls = []
    owner = scoring_service.score_result

    def loader(scene):
        calls.append(scene)
        return chosen

    owner_calls = []

    def observed_owner(items, selected, **context):
        owner_calls.append(context)
        return owner(items, selected, **context)

    monkeypatch.setattr(scoring_service, "score_result", observed_owner)
    states, overview = score_special_report_cases(inputs, standard_loader=loader)
    assert calls == ["final"] and len(owner_calls) == 2
    assert (
        states[CASE]["report_score_status"] == "scored"
        and states[CASE]["report_score"] == 98.0
    )
    assert states[CASE]["report_grade"] == "甲" and states[CASE]["reason_code"] is None
    assert (
        states[CASE]["standard_id"] == chosen["id"]
        and states[CASE]["standard_version_seq"] == 3
    )
    assert (
        states[CASE]["binding_version_seq"] == 2
        and states[CASE]["report_veto_hit"] is False
    )
    assert states[(CASE[0], CASE[1], "synthetic-visit-2")]["report_score"] == 100.0
    assert overview["status"] == "configured" and overview["standard_version_seq"] == 3
    assert inputs == baseline and chosen == before


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"rule_set_key": "other"}, "rule_set_mismatch"),
        ({"rule_set_key": None}, "rule_set_mismatch"),
        ({"status": "unavailable"}, "result_unavailable"),
        ({"envelope_id": None}, "result_unavailable"),
        ({"rule_set_version": ""}, "result_unavailable"),
        ({"items": None}, "result_unavailable"),
        (
            {"items": [{"rule_id": "LX0609-001", "is_confirmed_issue": "true"}]},
            "result_unavailable",
        ),
    ],
)
def test_missing_or_incompatible_result_is_unknown(changes, reason):
    states, _ = score_special_report_cases(
        {CASE: result(**changes)}, standard_loader=lambda _: standard()
    )
    assert states[CASE]["report_score_status"] == "unknown"
    assert (
        states[CASE]["report_score"] is None and states[CASE]["reason_code"] == reason
    )


def test_scope_unknown_is_not_zero_or_full_score():
    selected = standard()
    selected["items"][0].update(
        department_scope_mode="selected",
        department_refs=[
            {
                "institute_id": CASE[0],
                "department_name": "合成科室",
            }
        ],
    )
    states, _ = score_special_report_cases(
        {CASE: result(department_name=None)}, standard_loader=lambda _: selected
    )
    assert (
        states[CASE]["reason_code"] == "scope_unavailable"
        and states[CASE]["report_score"] is None
    )


def test_nonconfirmed_flags_are_left_to_owner_and_scope_does_not_match_other_hospital():
    selected = standard()
    selected["items"][0].update(
        department_scope_mode="selected",
        department_refs=[
            {
                "institute_id": "different-hospital",
                "department_name": "合成科室",
            }
        ],
    )
    states, _ = score_special_report_cases(
        {CASE: result()}, standard_loader=lambda _: selected
    )
    assert states[CASE]["report_score"] == 100.0
    states, _ = score_special_report_cases(
        {
            CASE: result(
                items=[
                    {
                        "rule_id": "LX0609-001",
                        "status": "uncertain",
                        "is_confirmed_issue": False,
                    }
                ]
            )
        },
        standard_loader=lambda _: standard(),
    )
    assert states[CASE]["report_score"] == 100.0


def test_veto_rule_ids_are_moved_from_scoring_owner_only():
    chosen = standard()
    chosen["items"][0]["is_veto"] = True
    states, _ = score_special_report_cases(
        {
            CASE: result(
                items=[
                    {"rule_id": "LX0609-001", "is_confirmed_issue": True},
                    {"rule_id": "LX0609-002", "is_confirmed_issue": True},
                ]
            )
        },
        standard_loader=lambda _: chosen,
    )
    assert (
        states[CASE]["report_grade"] == "乙" and states[CASE]["report_veto_hit"] is True
    )
    assert states[CASE]["report_veto_rule_ids"] == ["LX0609-001"]
    assert states[CASE]["report_unscored_rule_ids"] == ["LX0609-002"]
    states, _ = score_special_report_cases(
        {CASE: result()}, standard_loader=lambda _: None
    )
    assert (
        states[CASE]["report_veto_hit"] is None
        and states[CASE]["report_veto_rule_ids"] is None
    )


@pytest.mark.parametrize("missing", [True, False])
def test_no_binding_or_unavailable_standard_never_falls_back(missing):
    def loader(_):
        if missing:
            return None
        raise standards.ScoringStandardUnavailable("合成来源不可用")

    states, overview = score_special_report_cases(
        {CASE: result()}, standard_loader=loader
    )
    assert states[CASE]["report_score"] is None
    assert states[CASE]["reason_code"] == (
        "no_standard" if missing else "standard_unavailable"
    )
    assert overview["status"] == ("no_standard" if missing else "unavailable")


def test_incomplete_standard_reference_or_case_identity_is_unknown():
    states, _ = score_special_report_cases(
        {CASE: result()}, standard_loader=lambda _: standard(binding_version_seq=None)
    )
    assert states[CASE]["reason_code"] == "standard_unavailable"
    bad_key = ("", CASE[1], CASE[2])
    states, _ = score_special_report_cases(
        {bad_key: result()}, standard_loader=lambda _: standard()
    )
    assert states[bad_key]["reason_code"] == "identity_unavailable"


def test_real_sqlite_binding_consumer_rebind_and_unbind_preserve_execute_default(
    monkeypatch,
):
    from app.services.custom_qc_workspace_service import (
        LUXIAN_0609_CUSTOMER_SCHEMA_VERSION,
        project_customer_safe_result_item,
    )

    engine = sa.create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    for model in (
        QCScoringStandard,
        QCScoringGroup,
        QCScoringItem,
        QCScoringDefaultBinding,
    ):
        model.__table__.create(engine)
    monkeypatch.setattr(
        standards, "SessionLocal", sessionmaker(bind=engine, expire_on_commit=False)
    )
    try:
        # 仅为只读消费者准备合成持久状态，不移植评分配置写接口。
        active = {"id": "synthetic-standard", "version_seq": 1}
        now = datetime(2026, 10, 3)
        with engine.begin() as conn:
            conn.execute(
                QCScoringStandard.__table__.insert().values(
                    **active,
                    name="合成消费标准",
                    scene="final",
                    rule_set_key=KEY,
                    status="active",
                    base_score=100,
                    grade_bands_json=json.dumps(standard()["grade_bands"]),
                    veto_grade="乙",
                    created_by="synthetic-user",
                    updated_by="synthetic-user",
                    activated_by="synthetic-user",
                    created_at=now,
                    updated_at=now,
                    activated_at=now,
                )
            )
            conn.execute(
                QCScoringGroup.__table__.insert().values(
                    id="group",
                    standard_id=active["id"],
                    **standard()["groups"][0],
                )
            )
            item = {
                key: value
                for key, value in standard()["items"][0].items()
                if key != "department_refs"
            }
            conn.execute(
                QCScoringItem.__table__.insert().values(
                    id="item",
                    standard_id=active["id"],
                    department_refs_json="[]",
                    **item,
                )
            )
        default_before = standards.get_default_standard("final")
        with engine.begin() as conn:
            conn.execute(
                QCScoringDefaultBinding.__table__.insert().values(
                    purpose="special_report",
                    execution_scene="final",
                    version_seq=1,
                    standard_id=active["id"],
                    standard_version_seq=active["version_seq"],
                    updated_by="synthetic-user",
                    updated_at=now,
                )
            )
        saved_item = {
            "schema_version": LUXIAN_0609_CUSTOMER_SCHEMA_VERSION,
            "rule_id": "LX0609-001",
            "status": "non_compliant",
            "result_status": "non_compliant",
            "is_compliant": False,
            "conclusion": "合成已保存缺陷",
            "suggestion": "合成建议",
            "criterion_results": [
                {
                    "criterion_id": "synthetic_completeness",
                    "kind": "completeness",
                    "status": "failed",
                    "reason_code": "synthetic_missing",
                }
            ],
        }
        projected = project_customer_safe_result_item(
            saved_item, hmac_key="synthetic-scoring-hmac"
        )
        ready = result(items=[projected])
        before = deepcopy(ready)
        states, overview = score_special_report_cases({CASE: ready})
        assert states[CASE]["report_score"] == 98.0
        assert (
            overview["standard_id"] == active["id"]
            and overview["binding_version_seq"] == 1
        )
        assert standards.get_default_standard("final") == default_before
        assert ready == before and projected["conclusion"] == "合成已保存缺陷"
        with engine.begin() as conn:
            conn.execute(
                QCScoringDefaultBinding.__table__.update().values(
                    standard_id=None,
                    standard_version_seq=None,
                    version_seq=2,
                )
            )
        states, _ = score_special_report_cases({CASE: result()})
        assert (
            states[CASE]["reason_code"] == "no_standard"
            and states[CASE]["report_score"] is None
        )
        assert standards.get_default_standard("final") == default_before
    finally:
        engine.dispose()
