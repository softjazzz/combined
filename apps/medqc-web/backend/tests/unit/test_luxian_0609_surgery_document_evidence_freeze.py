"""冻结 034/036/039 typed fact_refs 到公共客户证据的精确投影。"""

from __future__ import annotations

from typing import Any, Mapping

import pytest

from tests.unit.test_luxian_0609_surgery_document_freeze import (
    _anesthesia_record,
    _consent,
    _discussion,
    _evidence_coordinates,
    _fact_ref_coordinates,
    _rows,
    _run_chain,
    _surgery,
    _visit,
)


def _reference_source(coordinate: tuple[Any, ...]) -> str:
    kind = coordinate[0]
    if kind == "material":
        return str(coordinate[1])
    if kind == "fact":
        return str(coordinate[2])
    if kind == "observation":
        return str(coordinate[1])
    raise AssertionError(f"unexpected fact_ref coordinate: {coordinate!r}")


def _material_coordinates(
    coordinates: tuple[tuple[Any, ...], ...],
) -> set[tuple[str, str]]:
    return {
        (str(coordinate[1]), str(coordinate[2]))
        for coordinate in coordinates
        if coordinate[0] == "material"
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "rule_id",
        "rows_by_source",
        "error_sources",
        "expected_status",
        "expected_evidence",
        "expected_ref_sources",
    ),
    (
        # 034：麻醉记录触发，知情同意书为目标。
        (
            "LX0609-11-02-01",
            {
                "anesthesia_record": _rows(_anesthesia_record()),
                "consent_form": _rows(_consent(complete=True)),
            },
            frozenset(),
            "compliant",
            {("anesthesia_record", "anesthesia-1"), ("consent_form", "consent-1")},
            {"anesthesia_record", "consent_form"},
        ),
        (
            "LX0609-11-02-01",
            {"anesthesia_record": _rows(_anesthesia_record())},
            frozenset(),
            "non_compliant",
            {("anesthesia_record", "anesthesia-1")},
            {"anesthesia_record"},
        ),
        (
            "LX0609-11-02-01",
            {},
            frozenset(),
            "not_applicable",
            set(),
            {"anesthesia_record", "consent_form", "mr_surgery"},
        ),
        (
            "LX0609-11-02-01",
            {
                "anesthesia_record": _rows(
                    _anesthesia_record("anesthesia-1"),
                    _anesthesia_record("anesthesia-2"),
                )
            },
            frozenset(),
            "data_gap",
            {("anesthesia_record", "anesthesia-1"), ("anesthesia_record", "anesthesia-2")},
            {"anesthesia_record"},
        ),
        (
            "LX0609-11-02-01",
            {},
            frozenset({"anesthesia_record"}),
            "technical_error",
            set(),
            {"anesthesia_record", "consent_form", "mr_surgery"},
        ),
        # 036：麻醉主表触发，术前/术后访视为目标。
        (
            "LX0609-04-04-01",
            {
                "anesthesia_record": _rows(_anesthesia_record()),
                "mr_surgery": _rows(_surgery("mr-1")),
                "preane_surveil_record": _rows(_visit("pre-1", post=False)),
                "postane_surveil_record": _rows(_visit("post-1", post=True)),
            },
            frozenset(),
            "compliant",
            {
                ("mr_surgery", "mr-1"),
                ("preane_surveil_record", "pre-1"),
                ("postane_surveil_record", "post-1"),
            },
            {"mr_surgery", "preane_surveil_record", "postane_surveil_record"},
        ),
        (
            "LX0609-04-04-01",
            {
                "anesthesia_record": _rows(_anesthesia_record()),
                "mr_surgery": _rows(_surgery("mr-1")),
                "preane_surveil_record": _rows(_visit("pre-1", post=False)),
            },
            frozenset(),
            "non_compliant",
            {("mr_surgery", "mr-1"), ("preane_surveil_record", "pre-1")},
            {"mr_surgery", "preane_surveil_record"},
        ),
        (
            "LX0609-04-04-01",
            {
                "anesthesia_record": _rows(
                    {**_anesthesia_record(), "anesthesia_method": "局部麻醉"}
                ),
                "mr_surgery": _rows(_surgery("mr-1", anesthesia_method="局部麻醉")),
            },
            frozenset(),
            "not_applicable",
            {("mr_surgery", "mr-1")},
            {"mr_surgery"},
        ),
        (
            "LX0609-04-04-01",
            {
                "anesthesia_record": _rows(
                    {"document_id": "anesthesia-no-method", "record_content": "麻醉记录"}
                ),
                "mr_surgery": _rows(_surgery("mr-no-method", anesthesia_method="")),
            },
            frozenset(),
            "data_gap",
            {("anesthesia_record", "anesthesia-no-method")},
            {"anesthesia_record"},
        ),
        (
            "LX0609-04-04-01",
            {"anesthesia_record": _rows(_anesthesia_record())},
            frozenset({"mr_surgery"}),
            "technical_error",
            {("anesthesia_record", "anesthesia-1")},
            {"anesthesia_record"},
        ),
        # 039：已实施手术触发；讨论和抢救例外资料只在实际参与结论时进入 refs。
        (
            "LX0609-04-01-02",
            {
                "surgery_record": _rows(
                    {
                        **_surgery("surgery-1"),
                        "record_content": "本次手术不属于紧急抢救手术。",
                    }
                ),
                "presurg_discussion": _rows(_discussion(participants="王医生")),
            },
            frozenset(),
            "compliant",
            {("surgery_record", "surgery-1"), ("presurg_discussion", "discussion-1")},
            {"surgery_record", "presurg_discussion"},
        ),
        (
            "LX0609-04-01-02",
            {
                "surgery_record": _rows(
                    {
                        **_surgery("surgery-1"),
                        "record_content": "本次手术不属于紧急抢救手术。",
                    }
                )
            },
            frozenset(),
            "non_compliant",
            {("surgery_record", "surgery-1")},
            {"surgery_record"},
        ),
        (
            "LX0609-04-01-02",
            {},
            frozenset(),
            "not_applicable",
            set(),
            {"surgery_record", "mr_surgery", "rescue_record", "presurg_discussion"},
        ),
        (
            "LX0609-04-01-02",
            {"surgery_record": _rows(_surgery("surgery-1"))},
            frozenset(),
            "data_gap",
            {("surgery_record", "surgery-1")},
            {"surgery_record"},
        ),
        (
            "LX0609-04-01-02",
            {
                "surgery_record": _rows(
                    {
                        **_surgery("surgery-1"),
                        "record_content": "本次手术不属于紧急抢救手术。",
                    }
                )
            },
            frozenset({"rescue_record"}),
            "technical_error",
            {("surgery_record", "surgery-1")},
            {"surgery_record"},
        ),
    ),
)
async def test_034_036_039_typed_fact_refs_match_public_projector_coordinates(
    rule_id: str,
    rows_by_source: Mapping[str, tuple[Mapping[str, Any], ...]],
    error_sources: frozenset[str],
    expected_status: str,
    expected_evidence: set[tuple[str, str]],
    expected_ref_sources: set[str],
) -> None:
    """所有可达状态只投影本次判定实际引用的同会话材料坐标。"""

    session, execution, _reduced, result = await _run_chain(
        rule_id,
        rows_by_source,
        error_sources=error_sources,
    )

    coordinates = _fact_ref_coordinates(session, execution.decisions[0].fact_refs)
    assert execution.decisions[0].rule_id == rule_id
    assert result["status"] == expected_status
    assert coordinates
    assert {_reference_source(coordinate) for coordinate in coordinates} == expected_ref_sources
    assert _material_coordinates(coordinates) == expected_evidence
    assert _evidence_coordinates(result) == expected_evidence
