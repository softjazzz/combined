"""客户证据可追溯合同：按正式生成方式逆向核验，不以原样子串误判伪造。

1026 验收对不合规证据做了“文书ID直接匹配 + 原样子串”检查，部分未命中。
正式合同中文书级依据是空白归一、可截断的文书开头导航摘录，ID 可能被替换为
source_version_key；本文件用合成材料证明：合同产物可逆向核验，而原样子串检查
对同一合法证据必然失败；篡改的摘录或无法定位的引用仍被拒绝。
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.luxian_0609.customer_evidence_enrichment import (
    enrich_customer_evidence,
    trace_customer_evidence,
)

BODY = "主诉：合成症状三天。\n\n现病史：  合成描述" + "合成" * 200
ROWS = (
    {"document_id": "D-1", "source_version_key": "D-1@v2", "record_time": "2026-01-02 08:00:00",
     "record_content": BODY},
    {"document_id": "D-2", "record_time": "2026-01-03 08:00:00", "record_content": "另一份合成文书"},
)


def _materials(rows=ROWS) -> SimpleNamespace:
    return SimpleNamespace(rows=lambda source_type: rows if source_type == "admission_record" else ())


def _enriched(**extra) -> dict:
    [evidence] = enrich_customer_evidence(
        [{"source_type": "admission_record", "source_document_id": "D-1", **extra}],
        evidence_materials=_materials(),
    )
    return evidence


def test_document_level_excerpt_is_traceable_by_contract_but_not_by_raw_substring() -> None:
    evidence = _enriched()
    # 生成时 ID 已替换为版本键，摘录空白已折叠并截断。
    assert evidence["source_document_id"] == "D-1@v2"
    assert evidence["excerpt_kind"] == "文书级依据" and evidence["evidence_excerpt"].endswith("…")
    assert trace_customer_evidence(evidence, ROWS) == "verified_document_excerpt"
    # 1026 验收脚本的两项朴素检查对同一合法证据均失败：不能据此认定伪造。
    assert not any(row["document_id"] == evidence["source_document_id"] for row in ROWS)
    assert evidence["evidence_excerpt"] not in BODY


def test_field_level_excerpt_is_traced_to_the_named_field() -> None:
    rows = ({"document_id": "S-1", "record_time": "2026-01-02 08:00:00",
             "surgery_name": "合成手术名称", "record_content": "合成正文"},)
    [evidence] = enrich_customer_evidence(
        [{"source_type": "surgery_record", "source_document_id": "S-1"}],
        evidence_materials=SimpleNamespace(rows=lambda _source: rows),
        preferred_source_fields={"surgery_record": "surgery_name"},
    )
    assert (evidence["excerpt_kind"], evidence["field_path"]) == ("字段级依据", "surgery_name")
    assert trace_customer_evidence(evidence, rows) == "verified_field_excerpt"


@pytest.mark.parametrize(
    ("tamper", "expected"),
    [
        ({"evidence_excerpt": "合成症状三天，经治疗好转"}, "excerpt_mismatch"),
        ({"excerpt_kind": "原文引用"}, "excerpt_mismatch"),
        ({"source_document_id": "D-404"}, "unresolved_identity"),
        ({"evidence_excerpt": ""}, "reference_only"),
    ],
)
def test_tampered_or_unlocatable_evidence_is_not_verified(tamper: dict, expected: str) -> None:
    assert trace_customer_evidence({**_enriched(), **tamper}, ROWS) == expected


def test_duplicate_identity_is_ambiguous_not_guessed() -> None:
    rows = (*ROWS, {"document_id": "D-1", "record_content": "同号另一份"})
    assert trace_customer_evidence({**_enriched(), "source_document_id": "D-1"}, rows) == "ambiguous_identity"
