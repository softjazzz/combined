from app.services.bundles import assembly as bundle_assembly
from app.services.luxian_0609.source_evidence_reader import (
    luxian_0609_native_source_row_limit,
)


def test_audited_order_sources_use_limits_above_frozen_case_maxima():
    """258例审计（609/1377）与 1016 样本池（827/2156）的最大值必须能被 LX0609 读取上限完整覆盖。"""

    assert luxian_0609_native_source_row_limit("inpat_drug_order") == 3000
    assert luxian_0609_native_source_row_limit("inpat_nondrug_order") == 5000


def test_lx0609_order_limits_do_not_change_shared_bundle_limits():
    """LX0609 专用上限不改其他引擎共用的病历包读取上限。"""

    assert bundle_assembly._DOMAIN_FETCH_LIMITS["inpat_drug_order"] == 700
    assert bundle_assembly._DOMAIN_FETCH_LIMITS["inpat_nondrug_order"] == 1500
