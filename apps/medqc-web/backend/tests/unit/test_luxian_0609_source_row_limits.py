from app.services.luxian_0609.source_evidence_reader import (
    luxian_0609_native_source_row_limit,
)


def test_audited_order_sources_use_limits_above_frozen_case_maxima():
    """258例审计最大值必须能被生产读取上限完整覆盖。"""

    assert luxian_0609_native_source_row_limit("inpat_drug_order") == 700
    assert luxian_0609_native_source_row_limit("inpat_nondrug_order") == 1500
