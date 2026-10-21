import pytest

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


@pytest.mark.parametrize(
    ("code", "name"),
    (
        ("33.2200X003", "纤维支气管镜检查"),
        ("33.2403", "纤维支气管镜检查伴肺泡灌洗术"),
    ),
)
def test_bronchoscopy_operation_codes_override_structured_surgery_level(
    code: str, name: str
) -> None:
    row = {
        "surgery_code": code,
        "surgery_name": name,
        "surgical_level": "二级",
    }

    item = classify_surgery_procedure(code=code)

    assert item is not None
    assert item.name == name
    assert item.category == "诊断性操作"
    assert item.effective_level == "二级"
    assert item.raw_level == "二级"
    assert catalog_surgery_state(row) is False
    assert effective_surgery_level(row) == ""
    assert has_qualified_traditional_surgery_row(row) is False


@pytest.mark.parametrize(
    ("code", "name", "category"),
    (
        ("34.0401", "胸腔闭式引流术", "治疗性操作"),
        ("45.1300X004", "胃-十二指肠镜检查", "诊断性操作"),
    ),
)
def test_catalog_contains_authoritative_non_surgical_operation_codes(
    code: str, name: str, category: str
) -> None:
    item = classify_surgery_procedure(code=code)

    assert item is not None
    assert item.name == name
    assert item.category == category
    assert item.effective_level == ""
    assert item.raw_level == ""
    assert item.source == "national_catalog"
    assert item.is_surgery is False


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

    assert len(catalog) == 6513
    assert next(item for item in catalog if item.code == "01.2408").effective_level == "四级"


@pytest.mark.parametrize(
    ("code", "name", "category", "match_mode"),
    [
        # 1019 C21：目录未收录 45.2302，同亚目 45.23 全为诊断性操作。
        ("45.2302", "电子结肠镜检查", "诊断性操作", "subcategory"),
        # 目录连亚目都未收录时只认用户确认的补充清单（2026-10-20）。
        ("44.1300x001", "胃镜检查", "诊断性操作", "supplement_code"),
        ("33.2302", "电子支气管镜检查", "诊断性操作", "supplement_code"),
        ("31.1x00x005", "暂时性气管切开术", "治疗性操作", "supplement_code"),
        ("96.0400", "气管内插管", "治疗性操作", "supplement_code"),
        (None, "气管插管术", "治疗性操作", "supplement_name"),
    ],
)
def test_uncatalogued_procedures_fall_back_to_subcategory_or_confirmed_supplement(
    code, name, category, match_mode
) -> None:
    item = classify_surgery_procedure(code=code, name=name)

    assert item is not None
    assert (item.category, item.match_mode, item.is_surgery) == (category, match_mode, False)
    row = {"surgery_code": code, "surgery_name": name, "surgical_level": "二级"}
    assert has_qualified_traditional_surgery_row(row) is False


def test_mixed_subcategory_and_unknown_names_keep_structured_fallback() -> None:
    # 44.1 下同时有诊断性操作和手术，不能按亚目推断；名称也不做关键词猜测。
    assert classify_surgery_procedure(code="44.1999", name="未收录胃部检查") is None
    assert has_qualified_traditional_surgery_row(
        {"surgery_code": "44.1999", "surgery_name": "未收录胃部检查", "surgical_level": "二级"}
    ) is True


def test_surgery_type_order_for_bedside_procedure_is_not_surgery_order() -> None:
    from app.services.luxian_0609.surgery_procedure_catalog import is_non_surgical_procedure_order

    assert is_non_surgical_procedure_order({"order_name": "气管插管术"}) is True
    assert is_non_surgical_procedure_order({"order_name": "心肺复苏术"}) is True
    assert is_non_surgical_procedure_order({"order_name": "腹腔镜下阑尾切除术"}) is False
    assert is_non_surgical_procedure_order({"order_name": "气管插管护理"}) is False


def test_vessel_count_adjunct_code_is_not_surgery() -> None:
    # 1019 C15：冠脉介入首页的“两根血管操作”附加编码带三级等级，不能单独触发手术。
    item = classify_surgery_procedure(code="00.4100", name="两根血管操作")

    assert item is not None
    assert (item.category, item.match_mode, item.is_surgery) == ("附加编码", "adjunct_code", False)
    assert has_qualified_traditional_surgery_row(
        {"surgery_code": "00.4100", "surgery_name": "两根血管操作", "surgical_level": "三级"}
    ) is False
    # 00.49 是目录内的独立治疗性操作，不属于附加编码。
    assert classify_surgery_procedure(code="00.4900").category == "治疗性操作"
