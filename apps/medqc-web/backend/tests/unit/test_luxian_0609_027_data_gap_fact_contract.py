"""M17：027「诊断恶性性质未决」事实在 `data_gap` 终态下必须被接受。

背景：该事实此前只允许 `uncertain` 终态（`tumor_pathology_result_mapping.py:247`），
而 027 的客户契约**不允许交付 `uncertain`**（catalog 027 行 `allowed_result_statuses`
= hit; not_hit; data_quality_gap; not_applicable; needs_manual_review）。于是执行器
只能丢弃该事实（客户看不到「影像提示恶性可能、缺病理」这条未决线索）；一旦携带，
校验即判不自洽 → finalizer 升级为 `technical_error / model_invalid_output`。

M17 收口：执行器恢复携带该事实，校验同时接受 `data_gap`。该事实是**纯展示事实**，
不参与判定，故接受 `data_gap` 不放松任何判据；作用域仅限 `LX0609-027`。
"""

from __future__ import annotations

from app.services.luxian_0609.tumor_pathology_result_mapping import (
    tumor_pathology_customer_fact_status_is_valid,
)

_UNCERTAIN_FACTS = {
    "verification_kind": "malignant_diagnosis_applicability_uncertain",
    "malignancy_state": "unknown",
    "uncertain_diagnosis_count": 3,
}


def test_027_uncertain_fact_is_accepted_with_data_gap() -> None:
    """M17 的核心：`data_gap` 终态携带该事实必须通过（此前会被判不自洽）。"""

    assert (
        tumor_pathology_customer_fact_status_is_valid(
            rule_id="LX0609-027", status="data_gap", safe_facts=_UNCERTAIN_FACTS
        )
        is True
    )


def test_027_uncertain_fact_still_accepted_with_uncertain() -> None:
    """原有语义不变：`uncertain` 仍被接受。"""

    assert (
        tumor_pathology_customer_fact_status_is_valid(
            rule_id="LX0609-027", status="uncertain", safe_facts=_UNCERTAIN_FACTS
        )
        is True
    )


def test_027_uncertain_fact_rejects_compliant_and_non_compliant() -> None:
    """值校验未放宽：该事实与 compliant / non_compliant 仍不自洽。"""

    for status in ("compliant", "non_compliant"):
        assert (
            tumor_pathology_customer_fact_status_is_valid(
                rule_id="LX0609-027", status=status, safe_facts=_UNCERTAIN_FACTS
            )
            is False
        ), f"status={status} 应被拒绝"


def test_027_technical_error_still_bypasses_fact_validation() -> None:
    """技术异常分支不受影响（既有行为：technical_error 直接放行）。"""

    assert (
        tumor_pathology_customer_fact_status_is_valid(
            rule_id="LX0609-027", status="technical_error", safe_facts=None
        )
        is True
    )


def test_other_rules_are_not_affected_by_the_027_branch() -> None:
    """作用域纪律：同一事实形状用在 013 上不得因本次改动而被放行。"""

    for rule_id in ("LX0609-013", "LX0609-019", "LX0609-026"):
        for status in ("data_gap", "uncertain"):
            assert (
                tumor_pathology_customer_fact_status_is_valid(
                    rule_id=rule_id, status=status, safe_facts=_UNCERTAIN_FACTS
                )
                is False
            ), f"{rule_id}/{status} 不应被 027 的分支放行"
