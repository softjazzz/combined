"""真实 FQ 执行器与 SQLite 评分标准的合成首页消费，不访问业务库。"""

from copy import deepcopy

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from app.database.models.qc import QCScoringGroup, QCScoringItem, QCScoringStandard
from app.services import scoring_service
from app.services import scoring_standard_service as standards
from app.services.frontpage_formal_qc import FrontpageFormalQC
from app.services.frontpage_rule_catalog import FRONTPAGE_RULE_SET_KEY, FRONTPAGE_RULE_SET_VERSION
from app.services.frontpage_scoring_service import score_frontpage_report


def standard(**changes):
    value = {
        "id": "synthetic-frontpage", "scene": "frontpage", "status": "active", "is_default": True,
        "version_seq": 2, "rule_set_key": FRONTPAGE_RULE_SET_KEY, "updated_at": "2026-10-03",
        "base_score": 100, "veto_grade": "乙",
        "grade_bands": [{"name": "甲", "min_score": 90, "max_score": 100},
                        {"name": "乙", "min_score": 0, "max_score": 90}],
        "groups": [{"group_name": "首页", "max_deduction": 3}],
        "items": [{"rule_id": "FQ-001", "group_name": "首页", "deduction": 2,
                   "is_veto": True, "enabled": True, "department_scope_mode": "all", "department_refs": []}],
    }
    value.update(changes)
    return value


def consume(report=None, chosen=None, **kwargs):
    return score_frontpage_report(
        FrontpageFormalQC().validate({}) if report is None else report,
        institute_id="synthetic-hospital", department_name="合成科室",
        rule_set_key=FRONTPAGE_RULE_SET_KEY, rule_set_version=FRONTPAGE_RULE_SET_VERSION,
        standard_loader=lambda _: chosen if chosen is not None else standard(), **kwargs,
    )


def test_real_report_one_read_unique_owner_and_unchanged_inputs(monkeypatch):
    report = FrontpageFormalQC().validate({})
    before = deepcopy(report)
    chosen = standard()
    original = deepcopy(chosen)
    reads, calls = [], []
    owner = scoring_service.score_result

    def loader(scene):
        reads.append(scene)
        return chosen

    def observed(items, config, **context):
        calls.append(items)
        return owner(items, config, **context)

    monkeypatch.setattr(scoring_service, "score_result", observed)
    state = score_frontpage_report(
        report, institute_id="synthetic-hospital", department_name="合成科室",
        rule_set_key=FRONTPAGE_RULE_SET_KEY, rule_set_version=FRONTPAGE_RULE_SET_VERSION,
        standard_loader=loader,
    )
    assert reads == ["frontpage"] and len(calls) == 1
    assert state["status"] == "scored" and state["score"] == 98
    assert state["grade"] == "乙" and state["veto_hit"] is True
    assert state["standard_version_seq"] == 2 and state["rule_set_version"] == FRONTPAGE_RULE_SET_VERSION
    assert report == before and chosen == original


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "extra", "nonbool", "count"])
def test_incomplete_or_malformed_report_is_unknown(mutation):
    report = FrontpageFormalQC().validate({})
    if mutation == "missing":
        report.results.pop()
    elif mutation == "duplicate":
        report.results[-1] = report.results[0]
    elif mutation == "extra":
        report.results[-1].rule_id = "FQ-UNKNOWN"
    elif mutation == "nonbool":
        report.results[0].passed = 0
    else:
        report.failed += 1
    state = consume(report)
    assert state["status"] == "unavailable" and state["reason_code"] == "result_unavailable"
    assert state["score"] is None


@pytest.mark.parametrize("changes,reason", [
    ({"scene": "final"}, "standard_unavailable"),
    ({"rule_set_key": "luxian_0609_qc_v1"}, "rule_set_mismatch"),
    ({"status": "archived"}, "standard_unavailable"),
    ({"version_seq": None}, "standard_unavailable"),
])
def test_bad_standard_never_borrows_final(changes, reason):
    state = consume(chosen=standard(**changes))
    assert state["reason_code"] == reason and state["score"] is None


def test_missing_standard_failure_version_and_selected_scope():
    report = FrontpageFormalQC().validate({})
    args = dict(institute_id="synthetic-hospital", department_name=None,
                rule_set_key=FRONTPAGE_RULE_SET_KEY, rule_set_version=FRONTPAGE_RULE_SET_VERSION)
    assert score_frontpage_report(report, **args, standard_loader=lambda _: None)["status"] == "no_standard"

    def failed(_):
        raise RuntimeError("合成配置故障")

    assert score_frontpage_report(report, **args, standard_loader=failed)["reason_code"] == "standard_unavailable"
    chosen = standard()
    chosen["items"][0].update(department_scope_mode="selected", department_refs=[{
        "institute_id": "synthetic-hospital", "department_name": "合成科室",
    }])
    assert score_frontpage_report(report, **args, standard_loader=lambda _: chosen)["reason_code"] == "scope_unavailable"
    args["rule_set_version"] = "old-version"
    assert score_frontpage_report(report, **args, standard_loader=lambda _: chosen)["reason_code"] == "rule_set_mismatch"


def test_complete_all_passed_report_and_department_scope_are_left_to_owner():
    report = FrontpageFormalQC().validate({})
    for item in report.results:
        item.passed = True
    report.passed, report.failed = report.total_rules, 0
    assert consume(report)["score"] == 100
    chosen = standard()
    chosen["items"][0].update(department_scope_mode="selected", department_refs=[{
        "institute_id": "other-hospital", "department_name": "合成科室",
    }])
    state = consume(chosen=chosen)
    assert state["score"] == 100 and state["veto_hit"] is False


def test_real_sqlite_default_and_real_fq_execution(monkeypatch):
    engine = sa.create_engine("sqlite://")
    for model in (QCScoringStandard, QCScoringGroup, QCScoringItem):
        model.__table__.create(engine)
    monkeypatch.setattr(standards, "SessionLocal", sessionmaker(bind=engine, expire_on_commit=False))
    try:
        chosen = standard()
        draft = standards.create_standard(
            actor="synthetic-user", name="合成首页标准", scene="frontpage", rule_set_key=FRONTPAGE_RULE_SET_KEY,
            base_score=100, grade_bands=chosen["grade_bands"], veto_grade="乙",
        )
        saved = standards.save_items(
            draft["id"], actor="synthetic-user", version_seq=draft["version_seq"],
            groups=chosen["groups"], items=chosen["items"],
        )
        active = standards.activate_standard(saved["id"], actor="synthetic-user", version_seq=saved["version_seq"])
        report = FrontpageFormalQC().validate({})
        before = deepcopy(report)
        state = score_frontpage_report(
            report, institute_id="synthetic-hospital", department_name="合成科室",
            rule_set_key=FRONTPAGE_RULE_SET_KEY, rule_set_version=FRONTPAGE_RULE_SET_VERSION,
        )
        assert state["status"] == "scored" and state["score"] == 98
        assert state["standard_id"] == active["id"] and state["standard_version_seq"] == active["version_seq"]
        assert standards.get_default_standard("final") is None and report == before
        standards.archive_standard(active["id"], actor="synthetic-user", version_seq=active["version_seq"])
        state = score_frontpage_report(
            report, institute_id="synthetic-hospital", department_name="合成科室",
            rule_set_key=FRONTPAGE_RULE_SET_KEY, rule_set_version=FRONTPAGE_RULE_SET_VERSION,
        )
        assert state["status"] == "no_standard" and state["score"] is None
    finally:
        engine.dispose()
