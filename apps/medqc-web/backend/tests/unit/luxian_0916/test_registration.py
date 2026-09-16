import inspect

from app.services import qc_rule_sets
from app.services.qc_rule_sets import get_sichuan_rule_set
from app.services.luxian_0916.rule_catalog import LUXIAN_0916_RULE_CATALOG
from app.services.sample_validation_rule_sets import (
    get_luxian_0916_sample_validation_rule_set,
    list_sample_validation_rule_sets,
    resolve_sample_validation_rule_set_by_key,
)


def test_luxian_0916_registers_exact_independent_catalog():
    rule_set = get_sichuan_rule_set("luxian_0916_qc_v1")

    assert rule_set is not None
    assert rule_set.scope == "running"
    assert rule_set.rule_ids == tuple(f"LX0916-{index:03d}" for index in range(1, 33))
    assert rule_set.rule_ids == tuple(item.rule_id for item in LUXIAN_0916_RULE_CATALOG)
    assert all("LX0609" not in rule_id and not rule_id.startswith("SC-") for rule_id in rule_set.rule_ids)


def test_public_rule_set_catalog_does_not_import_luxian_0916_executor_package():
    source = inspect.getsource(qc_rule_sets)

    assert "from .luxian_0916" not in source


def test_luxian_0916_is_explicit_customer_selection_and_does_not_replace_default():
    items = list_sample_validation_rule_sets()

    assert items[0]["rule_set_key"] == "luxian_0609_qc_v1"
    item = next(entry for entry in items if entry["rule_set_key"] == "luxian_0916_qc_v1")
    assert item["validation_mode"] == "customer"
    assert item["rule_count"] == 32
    assert item["scope"] == "running"

    resolved = resolve_sample_validation_rule_set_by_key("luxian_0916_qc_v1")
    assert resolved == {
        "validation_mode": "customer",
        "rule_set": get_luxian_0916_sample_validation_rule_set(),
    }
