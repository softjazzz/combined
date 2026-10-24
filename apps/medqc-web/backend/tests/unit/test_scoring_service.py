"""计分服务合同：纯函数 score_result、score_cases、单病历计分与列表批量计分（合成数据，不连库）。"""

from __future__ import annotations

import random
from decimal import Decimal

import pytest
from app.services import scoring_service
from app.services.scoring_service import grade_for, score_result

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
            {
                "group_name": "病程记录",
                "rule_id": "LX0609-001",
                "deduction": 3.0,
                "is_veto": False,
                "enabled": True,
            },
            {
                "group_name": "病程记录",
                "rule_id": "LX0609-002",
                "deduction": 4.0,
                "is_veto": False,
                "enabled": True,
            },
            {
                "group_name": "首页",
                "rule_id": "LX0609-003",
                "deduction": 2.5,
                "is_veto": False,
                "enabled": True,
            },
            {
                "group_name": "首页",
                "rule_id": "LX0609-004",
                "deduction": 1.0,
                "is_veto": True,
                "enabled": True,
            },
            {
                "group_name": "首页",
                "rule_id": "LX0609-005",
                "deduction": 9.0,
                "is_veto": True,
                "enabled": False,
            },
        ],
    }
    data.update(overrides)
    return data


def item(rule_id, status="non_compliant"):
    return {
        "rule_id": rule_id,
        "status": status,
        "is_confirmed_issue": status == "non_compliant",
    }


def test_only_confirmed_issues_are_deducted():
    items = [
        item("LX0609-001"),
        item("LX0609-002", "uncertain"),
        item("LX0609-003", "not_executed"),
        item("LX0609-004", "not_applicable"),
        {
            "rule_id": "LX0609-003",
            "is_confirmed_issue": "true",
        },  # 非布尔 True 不算确定问题
    ]
    result = score_result(items, standard())
    assert (
        result["score"] == 97.0
        and result["grade"] == "甲"
        and result["veto_hit"] is False
    )
    assert result["deductions"] == [
        {
            "rule_id": "LX0609-001",
            "group_name": "病程记录",
            "deduction": 3.0,
            "is_veto": False,
        },
    ]
    assert (
        result["standard_id"] == "std-1"
        and result["standard_updated_at"] == "2026-09-27T10:00:00"
    )


def test_department_scope_is_exact_within_institute_and_out_of_scope_is_not_unscored():
    scoped = standard(
        items=[
            {
                "group_name": "病程记录",
                "rule_id": "LX0609-001",
                "deduction": 3,
                "is_veto": False,
                "enabled": True,
                "department_scope_mode": "selected",
                "department_refs": [
                    {"institute_id": "H1", "department_name": "心内科"}
                ],
            }
        ]
    )
    matched = score_result(
        [item("LX0609-001")], scoped, institute_id="H1", department_name="心内科"
    )
    other_hospital = score_result(
        [item("LX0609-001")], scoped, institute_id="H2", department_name="心内科"
    )
    assert matched["score"] == 97.0
    assert (
        other_hospital["score"] == 100.0 and other_hospital["unscored_rule_ids"] == []
    )
    with pytest.raises(scoring_service.ScoringScopeContextUnavailable):
        score_result(
            [item("LX0609-001")], scoped, institute_id="H1", department_name=""
        )
    scoped["items"][0]["department_refs"] = []
    with pytest.raises(scoring_service.ScoringScopeContextUnavailable):
        score_result(
            [item("LX0609-001")], scoped, institute_id="H1", department_name="心内科"
        )
    malformed_all = standard(
        items=[
            {
                "group_name": "病程记录",
                "rule_id": "LX0609-001",
                "deduction": 3,
                "is_veto": False,
                "enabled": True,
                "department_scope_mode": "all",
                "department_refs": [
                    {"institute_id": "H1", "department_name": "心内科"}
                ],
            }
        ]
    )
    with pytest.raises(scoring_service.ScoringScopeContextUnavailable):
        score_result(
            [item("LX0609-001")],
            malformed_all,
            institute_id="H1",
            department_name="心内科",
        )


def test_group_cap_limits_deduction_and_uncapped_group_sums():
    result = score_result(
        [item("LX0609-001"), item("LX0609-002"), item("LX0609-003")], standard()
    )
    groups = {group["group_name"]: group for group in result["group_deductions"]}
    assert groups["病程记录"] == {
        "group_name": "病程记录",
        "raw_deduction": 7.0,
        "applied_deduction": 5.0,
        "max_deduction": 5.0,
    }
    assert (
        groups["首页"]["applied_deduction"] == 2.5
        and groups["首页"]["max_deduction"] is None
    )
    assert result["score"] == 92.5
    # 按项目组 sort_order、rule_id 排序
    assert [entry["rule_id"] for entry in result["deductions"]] == [
        "LX0609-001",
        "LX0609-002",
        "LX0609-003",
    ]


def test_score_floor_is_zero():
    heavy = standard(
        items=[
            {
                "group_name": "首页",
                "rule_id": "LX0609-003",
                "deduction": 80.0,
                "is_veto": False,
                "enabled": True,
            },
            {
                "group_name": "首页",
                "rule_id": "LX0609-006",
                "deduction": 50.0,
                "is_veto": False,
                "enabled": True,
            },
        ]
    )
    result = score_result([item("LX0609-003"), item("LX0609-006")], heavy)
    assert result["score"] == 0.0 and result["grade"] == "丙"


@pytest.mark.parametrize(
    "score,grade",
    [
        ("100", "甲"),
        ("90", "甲"),
        ("89.99", "乙"),
        ("75", "乙"),
        ("74.99", "丙"),
        ("0", "丙"),
    ],
)
def test_grade_boundaries_left_closed_right_open_top_closed(score, grade):
    assert grade_for(Decimal(score), BANDS) == grade


def test_veto_forces_grade_and_disabled_veto_is_ignored():
    result = score_result([item("LX0609-004")], standard(veto_grade="乙"))
    assert (
        result["score"] == 99.0
        and result["veto_hit"] is True
        and result["grade"] == "乙"
    )
    disabled = score_result([item("LX0609-005")], standard())
    assert (
        disabled["veto_hit"] is False
        and disabled["score"] == 100.0
        and disabled["deductions"] == []
    )
    assert disabled["unscored_rule_ids"] == []


def test_unscored_confirmed_issues_are_listed_not_ignored():
    result = score_result(
        [item("LX0609-001"), item("LX0609-070"), item("lx0609-071")], standard()
    )
    assert result["unscored_rule_ids"] == ["LX0609-070", "LX0609-071"]
    assert result["score"] == 97.0


def test_deterministic_regardless_of_order_and_duplicates():
    items = [
        item("LX0609-001"),
        item("LX0609-002"),
        item("LX0609-004"),
        item("LX0609-070"),
        item("LX0609-001"),
    ]
    expected = score_result(items, standard())
    for seed in range(5):
        shuffled = list(items)
        random.Random(seed).shuffle(shuffled)
        assert score_result(shuffled, standard()) == expected


def test_project_customer_items_uses_customer_projection(monkeypatch):
    from app.services import custom_qc_workspace_service
    from app.services.qc_workspace import canonical_result_store

    monkeypatch.setattr(
        canonical_result_store, "customer_safe_projection_key", lambda: "k"
    )
    monkeypatch.setattr(
        custom_qc_workspace_service,
        "project_customer_safe_result_item",
        lambda raw, hmac_key: {
            "rule_id": raw["rule_id"],
            "is_confirmed_issue": raw["status"] == "non_compliant",
            "key": hmac_key,
        },
    )
    projected = scoring_service.project_customer_items(
        [{"rule_id": "LX0609-001", "status": "non_compliant"}]
    )
    assert projected == [
        {"rule_id": "LX0609-001", "is_confirmed_issue": True, "key": "k"}
    ]
