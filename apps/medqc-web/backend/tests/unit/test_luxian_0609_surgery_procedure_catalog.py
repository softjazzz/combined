from app.services.luxian_0609.surgery_procedure_catalog import (
    catalog_surgery_state,
    classify_surgery_procedure,
    effective_surgery_level,
    load_surgery_procedure_catalog,
)
from app.services.luxian_0609.source_evidence_reader import (
    has_qualified_traditional_surgery_row,
)


def test_hospital_performance_level_overrides_national_level() -> None:
    item = classify_surgery_procedure(code="01.2408")

    assert item is not None
    assert item.name == "颅内血肿清除术"
    assert item.category == "手术"
    assert item.effective_level == "四级"
    assert item.raw_level == "院内四级"
    assert item.source == "hospital_performance"
    assert item.match_mode == "code"


def test_conditional_level_is_treated_as_level_four() -> None:
    item = classify_surgery_procedure(code="01.2400x013")

    assert item is not None
    assert item.category == "手术"
    assert item.raw_level == "条件四级"
    assert item.effective_level == "四级"


def test_operation_category_does_not_become_surgery_from_raw_level() -> None:
    row = {
        "surgery_code": "00.5901",
        "surgery_name": "冠脉瞬时无波形比值检查[iFR检查]",
        "surgical_level": "四级",
    }

    assert catalog_surgery_state(row) is False
    assert effective_surgery_level(row) == ""
    assert has_qualified_traditional_surgery_row(row) is False


def test_composite_exact_names_choose_highest_surgery_level() -> None:
    item = classify_surgery_procedure(
        name="颅内血肿清除术+硬脑膜补片修补术+颅骨去骨瓣减压术"
    )

    assert item is not None
    assert item.name == "颅内血肿清除术"
    assert item.effective_level == "四级"
    assert item.match_mode == "composite_name"


def test_catalog_exposes_same_read_only_items_used_by_classifier() -> None:
    catalog = load_surgery_procedure_catalog()

    assert len(catalog) == 6509
    assert next(item for item in catalog if item.code == "01.2408").effective_level == "四级"
