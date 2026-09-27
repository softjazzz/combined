"""编号切换后的保存/读取边界：新身份合法，旧身份不可静默交付。"""
import pytest

from app.services.qc_workspace.canonical_result_store import (
    canonical_envelope_items_are_consistent,
)


def _item():
    return {
        "rule_id": "LX0609-06-01-02",
        "status": "compliant",
        "result_status": "compliant",
        "is_compliant": True,
    }


def test_canonical_accepts_one_published_identity_with_equal_aliases():
    item = _item()
    for key in ("rule_code", "qc_point_id", "customer_rule_id"):
        item[key] = item["rule_id"]
    assert canonical_envelope_items_are_consistent([item])


@pytest.mark.parametrize("rule_id", ["LX0609-010", "LX0609-99-99-99"])
def test_canonical_rejects_legacy_and_unpublished_rule_identity(rule_id):
    assert not canonical_envelope_items_are_consistent([{**_item(), "rule_id": rule_id}])


@pytest.mark.parametrize("field", ["rule_code", "qc_point_id", "customer_rule_id"])
def test_canonical_rejects_mixed_rule_identity(field):
    assert not canonical_envelope_items_are_consistent([{**_item(), field: "LX0609-010"}])


def test_canonical_still_rejects_two_results_with_the_same_new_identity():
    assert not canonical_envelope_items_are_consistent([_item(), _item()])
