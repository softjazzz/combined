"""计分服务合同：纯函数 score_result、score_cases、单病历计分与列表批量计分（合成数据，不连库）。"""

from __future__ import annotations

import random
from decimal import Decimal

import pytest

from app.services import scoring_service
from app.services.case_identity import CaseRef
from app.services.qc_workspace.canonical_result_store import keyed_ref
from app.services.scoring_service import grade_for, score_cases, score_result, score_workstation_page
from app.services.scoring_standard_service import ScoringStandardUnavailable, validate_grade_bands

BANDS = [
    {"name": "甲", "min_score": 90, "max_score": 100},
    {"name": "乙", "min_score": 75, "max_score": 90},
    {"name": "丙", "min_score": 0, "max_score": 75},
]


def standard(**overrides):
    data = {
        "id": "std-1",
        "name": "运行病历标准",
        "rule_set_key": "luxian_0609_qc_v1",
        "base_score": 100.0,
        "grade_bands": BANDS,
        "veto_grade": "丙",
        "updated_at": "2026-09-27T10:00:00",
        "groups": [
            {"group_name": "病程记录", "max_deduction": 5.0, "sort_order": 1},
            {"group_name": "首页", "max_deduction": None, "sort_order": 2},
        ],
        "items": [
            {"group_name": "病程记录", "rule_id": "LX0609-001", "deduction": 3.0, "is_veto": False, "enabled": True},
            {"group_name": "病程记录", "rule_id": "LX0609-002", "deduction": 4.0, "is_veto": False, "enabled": True},
            {"group_name": "首页", "rule_id": "LX0609-003", "deduction": 2.5, "is_veto": False, "enabled": True},
            {"group_name": "首页", "rule_id": "LX0609-004", "deduction": 1.0, "is_veto": True, "enabled": True},
            {"group_name": "首页", "rule_id": "LX0609-005", "deduction": 9.0, "is_veto": True, "enabled": False},
        ],
    }
    data.update(overrides)
    return data


def item(rule_id, status="non_compliant"):
    return {"rule_id": rule_id, "status": status, "is_confirmed_issue": status == "non_compliant"}


def test_only_confirmed_issues_are_deducted():
    items = [
        item("LX0609-001"),
        item("LX0609-002", "uncertain"),
        item("LX0609-003", "not_executed"),
        item("LX0609-004", "not_applicable"),
        {"rule_id": "LX0609-003", "is_confirmed_issue": "true"},  # 非布尔 True 不算确定问题
    ]
    result = score_result(items, standard())
    assert result["score"] == 97.0 and result["grade"] == "甲" and result["veto_hit"] is False
    assert result["deductions"] == [
        {"rule_id": "LX0609-001", "group_name": "病程记录", "deduction": 3.0, "is_veto": False},
    ]
    assert result["standard_id"] == "std-1" and result["standard_updated_at"] == "2026-09-27T10:00:00"


def test_group_cap_limits_deduction_and_uncapped_group_sums():
    result = score_result([item("LX0609-001"), item("LX0609-002"), item("LX0609-003")], standard())
    groups = {group["group_name"]: group for group in result["group_deductions"]}
    assert groups["病程记录"] == {
        "group_name": "病程记录", "raw_deduction": 7.0, "applied_deduction": 5.0, "max_deduction": 5.0,
    }
    assert groups["首页"]["applied_deduction"] == 2.5 and groups["首页"]["max_deduction"] is None
    assert result["score"] == 92.5
    # 按项目组 sort_order、rule_id 排序
    assert [entry["rule_id"] for entry in result["deductions"]] == ["LX0609-001", "LX0609-002", "LX0609-003"]


def test_score_floor_is_zero():
    heavy = standard(items=[
        {"group_name": "首页", "rule_id": "LX0609-003", "deduction": 80.0, "is_veto": False, "enabled": True},
        {"group_name": "首页", "rule_id": "LX0609-006", "deduction": 50.0, "is_veto": False, "enabled": True},
    ])
    result = score_result([item("LX0609-003"), item("LX0609-006")], heavy)
    assert result["score"] == 0.0 and result["grade"] == "丙"


@pytest.mark.parametrize("score,grade", [
    ("100", "甲"), ("90", "甲"), ("89.99", "乙"), ("75", "乙"), ("74.99", "丙"), ("0", "丙"),
])
def test_grade_boundaries_left_closed_right_open_top_closed(score, grade):
    assert grade_for(Decimal(score), BANDS) == grade


def test_veto_forces_grade_and_disabled_veto_is_ignored():
    result = score_result([item("LX0609-004")], standard(veto_grade="乙"))
    assert result["score"] == 99.0 and result["veto_hit"] is True and result["grade"] == "乙"
    disabled = score_result([item("LX0609-005")], standard())
    assert disabled["veto_hit"] is False and disabled["score"] == 100.0 and disabled["deductions"] == []
    assert disabled["unscored_rule_ids"] == []  # 已配置但停用，不属于未配置


def test_unscored_confirmed_issues_are_listed_not_ignored():
    result = score_result([item("LX0609-001"), item("LX0609-070"), item("lx0609-071")], standard())
    assert result["unscored_rule_ids"] == ["LX0609-070", "LX0609-071"]
    assert result["score"] == 97.0


def test_deterministic_regardless_of_order_and_duplicates():
    items = [item("LX0609-001"), item("LX0609-002"), item("LX0609-004"), item("LX0609-070"), item("LX0609-001")]
    expected = score_result(items, standard())
    for seed in range(5):
        shuffled = list(items)
        random.Random(seed).shuffle(shuffled)
        assert score_result(shuffled, standard()) == expected


# ---------------------------------------------------------------------------
# bands 校验
# ---------------------------------------------------------------------------


def _problems(bands, base=Decimal("100.00"), veto="丙"):
    return validate_grade_bands(bands, base, veto)[2]


def test_bands_valid_with_any_count():
    assert _problems(BANDS) == []
    assert _problems([{"name": "合格", "min_score": 0, "max_score": 100}], veto="合格") == []


def test_bands_gap_overlap_and_coverage_problems():
    gap = [BANDS[0], {"name": "乙", "min_score": 75, "max_score": 85}, BANDS[2]]
    assert any("空隙" in problem for problem in _problems(gap))
    overlap = [BANDS[0], {"name": "乙", "min_score": 75, "max_score": 95}, BANDS[2]]
    assert any("重叠" in problem for problem in _problems(overlap))
    top = [{"name": "甲", "min_score": 90, "max_score": 99}, BANDS[1], BANDS[2]]
    assert any("满分" in problem for problem in _problems(top))
    bottom = [BANDS[0], BANDS[1], {"name": "丙", "min_score": 10, "max_score": 75}]
    assert any("下限必须为 0" in problem for problem in _problems(bottom))
    ascending = list(reversed(BANDS))
    assert any("降序" in problem for problem in _problems(ascending))


def test_bands_veto_grade_must_be_a_band_and_problems_are_listed():
    problems = _problems(BANDS, veto="丁")
    assert any("veto_grade" in problem for problem in problems)
    many = _problems([
        {"name": "甲", "min_score": 95, "max_score": 90},
        {"name": "甲", "min_score": "x", "max_score": 10},
    ], veto="丁")
    assert len(many) >= 3  # 逐条列出


# ---------------------------------------------------------------------------
# score_cases / score_case
# ---------------------------------------------------------------------------


def test_score_cases_reads_standard_once():
    calls = []

    def loader(scene):
        calls.append(scene)
        return standard()

    results = {"a": {"items": [item("LX0609-001")]}, "b": {"items": [item("LX0609-004")]}}
    states = score_cases(results, "running", standard_loader=loader)
    assert calls == ["running"]
    assert states["a"] == {
        "status": "scored", "score": 97.0, "grade": "甲", "veto_hit": False, "standard_id": "std-1",
        "reason_code": None,
    }
    assert states["b"]["grade"] == "丙" and states["b"]["veto_hit"] is True


def test_score_cases_no_standard_and_failure():
    results = {"a": {"items": [item("LX0609-001")]}}
    assert score_cases(results, "final", standard_loader=lambda scene: None)["a"]["status"] == "no_standard"

    def broken(scene):
        raise RuntimeError("password=secret")

    assert score_cases(results, "final", standard_loader=broken)["a"]["status"] == "unavailable"
    mismatch = score_cases({"a": {"items": [], "rule_set_key": "sc_content_v1"}}, "final",
                           standard_loader=lambda scene: standard())
    assert mismatch["a"]["status"] == "unavailable" and mismatch["a"]["reason_code"] == "rule_set_mismatch"


class _Workspace:
    def __init__(self, dto):
        self.dto = dto
        self.calls = []

    def build_latest_single_record_result_dto(self, **kwargs):
        self.calls.append(kwargs)
        return self.dto


def test_score_case_no_standard_does_not_read_result():
    workspace = _Workspace({"state": "ready"})
    result = scoring_service.score_case(
        institute_id="H1", patient_id="P1", visit_id="V1", scene="running",
        standard_loader=lambda scene: None, workspace_factory=lambda: workspace,
    )
    assert result == {"status": "no_standard", "scene": "running"}
    assert workspace.calls == []


def test_score_case_no_result_and_scored(monkeypatch):
    empty = _Workspace({"state": "not_found", "items": []})
    result = scoring_service.score_case(
        institute_id="H1", patient_id="P1", visit_id="V1", scene="running",
        standard_loader=lambda scene: standard(), workspace_factory=lambda: empty,
    )
    assert result["status"] == "no_result" and result["result_state"] == "not_found"
    assert empty.calls[0]["rule_set_key"] == "luxian_0609_qc_v1"

    from app.services.qc_workspace import canonical_result_store

    monkeypatch.setattr(canonical_result_store, "customer_safe_projection_key", lambda: "k")
    ready = _Workspace({
        "state": "ready", "job_id": "job-1", "root_job_id": "job-1", "envelope_id": "env-1",
        "record_ref": keyed_ref("rec", CaseRef("H1", "P1", "V1").as_key(), hmac_key="k"),
        "rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09",
        "items": [{"raw": "LX0609-001"}],
    })
    result = scoring_service.score_case(
        institute_id="H1", patient_id="P1", visit_id="V1", scene="running",
        standard_loader=lambda scene: standard(version_seq=7), workspace_factory=lambda: ready,
        projector=lambda items: [item(entry["raw"]) for entry in items],
    )
    assert result["status"] == "scored" and result["score"] == 97.0 and result["standard_id"] == "std-1"
    assert result["job_id"] == "job-1"
    assert result["result_ref"] == {
        "envelope_id": "env-1", "root_job_id": "job-1",
        "institute_id": "H1", "patient_id": "P1", "visit_id": "V1",
        "rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09",
    }
    assert result["standard_ref"] == {
        "standard_id": "std-1", "version_seq": 7, "updated_at": "2026-09-27T10:00:00",
    }


def test_score_case_keeps_legacy_score_when_references_are_incomplete():
    ready = _Workspace({
        "state": "ready", "job_id": "job-1", "rule_set_key": "luxian_0609_qc_v1",
        "rule_set_version": "2026-06-09", "items": [],
    })
    result = scoring_service.score_case(
        institute_id="H1", patient_id="P1", visit_id="V1", scene="running",
        standard_loader=lambda scene: standard(updated_at=None), workspace_factory=lambda: ready,
        projector=lambda items: [],
    )
    assert result["status"] == "scored" and result["score"] == 100.0
    assert result["result_ref"] is None
    assert result["standard_ref"] is None


@pytest.mark.parametrize(
    "standard_override",
    [
        {"version_seq": True},
        {"version_seq": 7, "updated_at": 123},
        {"version_seq": 7, "updated_at": "not-an-iso-time"},
    ],
)
def test_score_case_does_not_trust_malformed_standard_references(standard_override):
    ready = _Workspace({
        "state": "ready", "rule_set_key": "luxian_0609_qc_v1", "items": [],
    })
    result = scoring_service.score_case(
        institute_id="H1", patient_id="P1", visit_id="V1", scene="running",
        standard_loader=lambda scene: standard(**standard_override),
        workspace_factory=lambda: ready, projector=lambda items: [],
    )
    assert result["status"] == "scored" and result["standard_ref"] is None


@pytest.mark.parametrize(
    "dto_override",
    [
        {"record_ref": "rec_tampered"},
        {"root_job_id": "job-other"},
        {"rule_set_key": "other-rule-set"},
    ],
)
def test_score_case_rejects_explicit_reference_conflicts(monkeypatch, dto_override):
    from app.services.qc_workspace import canonical_result_store

    monkeypatch.setattr(canonical_result_store, "customer_safe_projection_key", lambda: "k")
    dto = {
        "state": "ready", "job_id": "job-1", "root_job_id": "job-1", "envelope_id": "env-1",
        "record_ref": keyed_ref("rec", CaseRef("H1", "P1", "V1").as_key(), hmac_key="k"),
        "rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "canonical-v2", "items": [],
    }
    dto.update(dto_override)
    with pytest.raises(ScoringStandardUnavailable, match="引用不一致"):
        scoring_service.score_case(
            institute_id="H1", patient_id="P1", visit_id="V1", scene="running",
            standard_loader=lambda scene: standard(version_seq=9),
            workspace_factory=lambda: _Workspace(dto), projector=lambda items: [],
        )


def test_project_customer_items_uses_customer_projection(monkeypatch):
    from app.services import custom_qc_workspace_service
    from app.services.qc_workspace import canonical_result_store

    monkeypatch.setattr(canonical_result_store, "customer_safe_projection_key", lambda: "k")
    monkeypatch.setattr(
        custom_qc_workspace_service, "project_customer_safe_result_item",
        lambda raw, hmac_key: {"rule_id": raw["rule_id"], "is_confirmed_issue": raw["status"] == "non_compliant",
                               "key": hmac_key},
    )
    projected = scoring_service.project_customer_items([{"rule_id": "LX0609-001", "status": "non_compliant"}])
    assert projected == [{"rule_id": "LX0609-001", "is_confirmed_issue": True, "key": "k"}]


# ---------------------------------------------------------------------------
# 列表本页批量计分
# ---------------------------------------------------------------------------

A = ("H1", "P1", "V1")
B = ("H1", "P2", "V2")


def _loader_for(results):
    calls = []

    def loader(refs, session_factory):
        calls.append(refs)
        return results

    return loader, calls


def test_workstation_page_scores_ready_cases_and_checks_anchor():
    loader, calls = _loader_for({
        A: {"status": "ready", "envelope_id": "env-1", "items": [{"raw": "LX0609-001"}]},
        B: {"status": "ready", "envelope_id": "env-new", "items": []},
    })
    states, overview = score_workstation_page(
        {A: "running", B: "running"},
        {A: {"envelope_id": "env-1"}, B: {"envelope_id": "env-old"}},
        standard_loader=lambda scene: standard(),
        results_loader=loader,
        projector=lambda items: [item(entry["raw"]) for entry in items],
    )
    assert states[A]["status"] == "scored" and states[A]["score"] == 97.0
    assert states[B] == {
        "status": "unavailable", "score": None, "grade": None, "veto_hit": None, "standard_id": "std-1",
        "reason_code": "result_changed",
    }
    assert overview["running"]["status"] == "configured"
    assert len(calls) == 1 and len(calls[0]) == 2


def test_workstation_page_without_standard_reads_no_items():
    loader, calls = _loader_for({})
    states, overview = score_workstation_page(
        {A: "final"}, {A: {}}, standard_loader=lambda scene: None, results_loader=loader,
    )
    assert states[A]["status"] == "no_standard" and overview["final"]["status"] == "no_standard"
    assert calls == []


def test_workstation_page_degrades_on_failures():
    def broken_loader(refs, session_factory):
        raise RuntimeError("SELECT secret")

    states, _ = score_workstation_page(
        {A: "running"}, {A: {"envelope_id": "env-1"}},
        standard_loader=lambda scene: standard(), results_loader=broken_loader,
    )
    assert states[A]["status"] == "unavailable" and states[A]["reason_code"] == "result_unavailable"

    def broken_standard(scene):
        raise RuntimeError("password=secret")

    states, overview = score_workstation_page({A: "running"}, {A: {}}, standard_loader=broken_standard)
    assert states[A]["reason_code"] == "standard_unavailable" and overview["running"]["status"] == "unavailable"

    other = standard(rule_set_key="sc_content_v1")
    states, _ = score_workstation_page({A: "final"}, {A: {}}, standard_loader=lambda scene: other)
    assert states[A]["reason_code"] == "rule_set_mismatch"
