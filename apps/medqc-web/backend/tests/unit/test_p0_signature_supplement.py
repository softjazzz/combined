from types import SimpleNamespace

import pytest

from app.services.document_assembly.signature_sync import safe_body_signature_supplement


def candidate(local, remote, *, other=None, local_fields=None):
    return SimpleNamespace(variants={"local": {"record_content": local, **(local_fields or {})},
        "homology": {"record_content": remote}, **({"clinical_data": {"record_content": other}} if other else {})})


def test_only_same_body_core_can_supply_all_names_without_role_order():
    row = candidate("合成病程。 医师签名：", "合成病程。 医师签名：甲医生 乙医生")
    assert safe_body_signature_supplement(row) == ("甲医生", "乙医生")
    reversed_row = candidate("合成病程。", "合成病程。 医师签名：乙医生 甲医生")
    assert safe_body_signature_supplement(reversed_row) == ("乙医生", "甲医生")


@pytest.mark.parametrize("local,remote", [
    ("旧版本正文。", "新版本正文。 医师签名：甲医生"),
    ("", "合成病程。 医师签名：甲医生"),
    ("合成病程。 医师签名：乙医生", "合成病程。 医师签名：甲医生"),
    ("合成病程。", "合成病程。 提交人：甲医生"),
    ("合成病程。", "合成病程。 医师签名：甲医生 2026-01-01"),
])
def test_changed_empty_or_ambiguous_body_does_not_supply_signature(local, remote):
    assert not safe_body_signature_supplement(candidate(local, remote))


def test_known_role_or_source_disagreement_requires_review():
    assert not safe_body_signature_supplement(candidate("合成病程。", "合成病程。 医师签名：甲医生", local_fields={"senior_physician_sign": "乙医生"}))
    assert not safe_body_signature_supplement(candidate("合成病程。", "合成病程。 医师签名：甲医生", other="合成病程。 医师签名：乙医生"))
