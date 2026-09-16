from app.services.luxian_0916.contracts import CUSTOMER_RESULT_STATUSES
from app.services.luxian_0916.rule_catalog import LUXIAN_0916_RULE_CATALOG


def test_catalog_contains_exactly_the_32_luxian0916_rules() -> None:
    assert tuple(item.rule_id for item in LUXIAN_0916_RULE_CATALOG) == tuple(
        f"LX0916-{number:03d}" for number in range(1, 33)
    )


def test_catalog_has_complete_runtime_metadata_without_external_rule_mapping() -> None:
    for item in LUXIAN_0916_RULE_CATALOG:
        assert item.name
        assert item.target_document
        assert item.execution_phase in {"direct", "event", "discharge"}
        assert item.trigger_type
        assert item.required_evidence
        assert item.allowed_statuses == CUSTOMER_RESULT_STATUSES
        assert "source_rule_id" not in item.to_dict()


def test_catalog_phase_counts_are_frozen() -> None:
    phases = [item.execution_phase for item in LUXIAN_0916_RULE_CATALOG]
    assert phases.count("direct") == 14
    assert phases.count("event") == 16
    assert phases.count("discharge") == 2
