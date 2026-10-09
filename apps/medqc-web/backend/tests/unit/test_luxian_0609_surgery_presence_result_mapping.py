from __future__ import annotations

from typing import Any

import pytest

from app.services.luxian_0609.canonical_result_finalizer import (
    validate_luxian_0609_executor_customer_display_facts,
)
from app.services.luxian_0609.surgery_presence_result_mapping import (
    SURGERY_PRESENCE_DOCUMENT_TARGETS,
    is_surgery_presence_customer_rule,
    safe_surgery_presence_customer_display_facts,
)


@pytest.mark.parametrize(
    ("rule_id", "raw", "expected"),
    (
        (
            "LX0609-04-02-02",
            {
                "verification_kind": "surgery_document_present",
                "target_document": "surgery_record",
                "surgery_trigger_kind": "performed_surgery",
                "performed_surgery_confirmed": True,
            },
            {
                "verification_kind": "surgery_document_present",
                "target_document": "surgery_record",
                "surgery_trigger_kind": "performed_surgery",
                "performed_surgery_confirmed": True,
            },
        ),
        (
            "LX0609-04-03-01",
            {
                "verification_kind": "surgery_document_present",
                "target_document": "surgery_safecheck_record",
                "performed_surgery_confirmed": True,
            },
            {
                "verification_kind": "surgery_document_present",
                "target_document": "surgery_safecheck_record",
                "performed_surgery_confirmed": True,
            },
        ),
        (
            "LX0609-04-02-02",
            {
                "failure_kind": "surgery_document_missing",
                "target_document": "surgery_record",
                "surgery_trigger_kind": "surgery_order",
                "surgery_order_confirmed": True,
            },
            {
                "failure_kind": "surgery_document_missing",
                "target_document": "surgery_record",
                "surgery_trigger_kind": "surgery_order",
                "surgery_order_confirmed": True,
            },
        ),
        (
            "LX0609-04-02-02",
            {
                "failure_kind": "surgery_document_blank",
                "target_document": "surgery_record",
                "surgery_trigger_kind": "performed_surgery",
                "performed_surgery_confirmed": True,
            },
            {
                "failure_kind": "surgery_document_blank",
                "target_document": "surgery_record",
                "surgery_trigger_kind": "performed_surgery",
                "performed_surgery_confirmed": True,
            },
        ),
        (
            "LX0609-04-03-01",
            {
                "failure_kind": "surgery_document_missing",
                "target_document": "surgery_safecheck_record",
                "performed_surgery_confirmed": True,
            },
            {
                "failure_kind": "surgery_document_missing",
                "target_document": "surgery_safecheck_record",
                "performed_surgery_confirmed": True,
            },
        ),
        (
            "LX0609-04-03-01",
            {
                "failure_kind": "surgery_document_blank",
                "target_document": "surgery_safecheck_record",
                "performed_surgery_confirmed": True,
            },
            {
                "failure_kind": "surgery_document_blank",
                "target_document": "surgery_safecheck_record",
                "performed_surgery_confirmed": True,
            },
        ),
        (
            "LX0609-04-02-02",
            {
                "verification_kind": "surgery_document_present",
                "target_document": "surgery_safecheck_record",
                "performed_surgery_confirmed": True,
            },
            None,
        ),
        (
            "LX0609-04-02-02",
            {
                "verification_kind": "surgery_document_present",
                "target_document": "surgery_record",
                "performed_surgery_confirmed": True,
            },
            {
                "verification_kind": "surgery_document_present",
                "target_document": "surgery_record",
                "performed_surgery_confirmed": True,
            },
        ),
        (
            "LX0609-04-03-01",
            {
                "failure_kind": "unexpected_failure",
                "target_document": "surgery_safecheck_record",
                "performed_surgery_confirmed": True,
            },
            None,
        ),
        (
            "LX0609-04-02-02",
            {
                "failure_kind": "surgery_document_missing",
                "target_document": "surgery_record",
                "performed_surgery_confirmed": False,
            },
            None,
        ),
        ("LX0609-04-02-02", {"source_document_id": "PRIVATE-030"}, None),
    ),
)
def test_surgery_presence_mapping_matches_current_finalizer_contract(
    rule_id: str, raw: dict[str, Any], expected: dict[str, Any] | None
) -> None:
    """阶段 1 先冻结新模块与现有 Finalizer 的逐形状等价性。"""

    assert safe_surgery_presence_customer_display_facts(
        rule_id=rule_id, raw=raw
    ) == expected
    assert validate_luxian_0609_executor_customer_display_facts(
        rule_id=rule_id, raw=raw
    ) == expected


def test_surgery_presence_mapping_whitelists_private_fields_without_leaking_them() -> None:
    raw = {
        "verification_kind": "surgery_document_present",
        "target_document": "surgery_record",
        "surgery_trigger_kind": "performed_surgery",
        "performed_surgery_confirmed": True,
        "source_document_id": "PRIVATE-SURGERY-030",
        "source_document_refs": ["PRIVATE-REF"],
        "raw_private_text": "PRIVATE-TEXT",
    }

    safe = safe_surgery_presence_customer_display_facts(
        rule_id="LX0609-04-02-02", raw=raw
    )

    assert safe == {
        "verification_kind": "surgery_document_present",
        "target_document": "surgery_record",
        "surgery_trigger_kind": "performed_surgery",
        "performed_surgery_confirmed": True,
    }
    assert "PRIVATE" not in repr(safe)
    assert validate_luxian_0609_executor_customer_display_facts(
        rule_id="LX0609-04-02-02", raw=raw
    ) == safe


def test_surgery_presence_rule_membership_and_targets_are_frozen() -> None:
    assert SURGERY_PRESENCE_DOCUMENT_TARGETS == {
        "LX0609-04-02-02": "surgery_record",
        "LX0609-04-03-01": "surgery_safecheck_record",
    }
    # 四段式统一身份大小写不敏感（原 030）。
    assert is_surgery_presence_customer_rule("lx0609-04-02-02") is True
    assert is_surgery_presence_customer_rule("LX0609-04-03-01") is True
    assert is_surgery_presence_customer_rule("LX0609-04-01-01") is False
