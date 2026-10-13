from __future__ import annotations

from datetime import datetime

import pytest

from app.services.luxian_0609.surgery_event_association import (
    associate_preop_document_to_surgery_event,
    build_performed_surgery_events,
    count_associated_performed_surgery_events,
    procedure_matches_surgery,
)
from app.services.luxian_0609.evidence_material import EvidenceMaterialTruncated


class _Materials:
    def __init__(self, *, surgery_records=(), mr_surgeries=()):
        self._rows = {
            "surgery_record": tuple(surgery_records),
            "mr_surgery": tuple(mr_surgeries),
        }

    def rows(self, source_key: str):
        return self._rows[source_key]


@pytest.mark.parametrize(
    ("documented_name", "performed_name", "expected"),
    (
        ("腹腔镜胆囊切除术", "腹腔镜胆囊切除术", True),
        ("拟行腹腔镜胆囊切除术", "腹腔镜胆囊切除术", True),
        ("腹腔镜胆囊切除术", "腹腔镜胆囊切除术+腹腔引流术", True),
        ("胆囊切除术", "胆囊切除术+腹腔引流术", True),
        ("胆囊切除术", "胆囊切除术＋腹腔引流术", True),
        ("胆囊切除术", "胆囊切除术、腹腔引流术", True),
        ("胆囊切除术", "胆囊切除术，腹腔引流术", True),
        ("胆囊切除术", "胆囊切除术,腹腔引流术", True),
        ("胆囊切除术", "胆囊切除术；腹腔引流术", True),
        ("胆囊切除术", "胆囊切除术;腹腔引流术", True),
        (
            "全子宫切除术+双侧输卵管切除术+盆腔粘连松解术",
            "次全子宫切除术+双侧输卵管切除术+盆腔粘连松解术",
            False,
        ),
        ("腹腔镜胆囊切除术", "胆囊切除术", False),
        ("胆囊切除术", "腹腔镜胆囊切除术", False),
        ("经皮肾镜取石术", "肾镜取石术", False),
        ("人工晶体置入术", "人工晶体植入术", False),
        ("全子宫切除术", "次全子宫切除术", False),
        ("次全子宫切除术", "全子宫切除术", False),
        ("腹腔镜胆囊切除术", "腹腔镜阑尾切除术", False),
    ),
)
def test_procedure_match_uses_controlled_variants_without_arbitrary_substrings(
    documented_name: str,
    performed_name: str,
    expected: bool,
) -> None:
    assert procedure_matches_surgery(documented_name, performed_name) is expected


def _record(
    *,
    document_id: str,
    name: str,
    code: str | None = None,
    begin: str = "2026-01-01 08:00:00+08:00",
    end: str | None = None,
    record_time: str | None = None,
    process: str | None = "手术经过。",
    content: str | None = None,
) -> dict:
    return {
        "document_id": document_id,
        "surgery_name": name,
        "surgery_code": code,
        "surgery_begin_time": begin,
        "surgery_end_time": end,
        "record_time": record_time,
        "surgery_process": process,
        "record_content": content,
    }


def _mr(
    *,
    surgery_id: str,
    name: str,
    code: str | None = None,
    begin: datetime | None = datetime(2026, 1, 1, 0, 0),
) -> dict:
    return {
        "surgery_id": surgery_id,
        "surgery_name": name,
        "surgery_code": code,
        "surgical_level": "三级",
        "surgery_begin_datetime": begin,
    }


def test_composite_components_on_one_natural_day_are_one_event() -> None:
    materials = _Materials(
        surgery_records=(
            _record(
                document_id="record-composite",
                name="胸腔镜下右肺上叶切除术+纵隔淋巴结清扫术",
            ),
        ),
        mr_surgeries=(
            _mr(surgery_id="mr-lobectomy", name="右肺上叶切除术"),
            _mr(surgery_id="mr-nodes", name="纵隔淋巴结清扫术"),
        ),
    )

    assert count_associated_performed_surgery_events(materials) == (1, "")


def test_running_event_builder_does_not_use_mr_anchor_to_remove_different_time_shell() -> None:
    materials = _Materials(
        surgery_records=(
            _record(
                document_id="record-shell",
                name="腹腔镜胆囊切除术",
                code="51.2300",
                begin="2026-01-01 07:00:00+08:00",
                record_time="2026-01-01 11:00:00",
                process=None,
                content=None,
            ),
            _record(
                document_id="record-substantive",
                name="腹腔镜胆囊切除术",
                code="51.2300",
                begin="2026-01-01 08:00:00+08:00",
            ),
        ),
        mr_surgeries=(
            _mr(
                surgery_id="mr-cholecystectomy",
                name="腹腔镜胆囊切除术",
                code="51.2300",
                # mr_surgery 在真实数据中常只有手术自然日；与手术记录的
                # 具体时分不一致，但仍可作为同日实质记录的唯一锚点。
                begin=datetime(2026, 1, 1, 0, 0),
            ),
        ),
    )

    assert count_associated_performed_surgery_events(materials) == (1, "")
    events, reason = build_performed_surgery_events(materials)
    assert reason == "" and events is not None and len(events) == 2


def test_prefixed_continuous_procedure_clause_matches_one_surgery() -> None:
    materials = _Materials(
        surgery_records=(
            _record(document_id="record", name="腹腔镜胆囊切除术"),
            _record(
                document_id="other",
                name="腹腔镜阑尾切除术",
                begin="2026-01-02 08:00:00+08:00",
            ),
        )
    )
    events, reason = build_performed_surgery_events(materials)
    association = associate_preop_document_to_surgery_event(
        events=events or (),
        procedure_name="拟行腹腔镜胆囊切除术",
        record_time=None,
    )
    assert reason == ""
    assert (association.state, association.event_index) == ("matched", 1)


def test_single_event_with_conflicting_explicit_procedure_is_ambiguous() -> None:
    """单台已实施手术也不能覆盖术前文书中的明确术式冲突。"""

    materials = _Materials(
        surgery_records=(
            _record(document_id="record", name="腹腔镜胆囊切除术"),
        )
    )
    events, reason = build_performed_surgery_events(materials)

    association = associate_preop_document_to_surgery_event(
        events=events or (),
        procedure_name="拟行腹腔镜阑尾切除术",
        record_time=None,
    )

    assert reason == ""
    assert (association.state, association.event_index) == ("ambiguous", None)


@pytest.mark.parametrize(
    ("procedure_name", "expected"),
    [
        ("拟行腹腔镜胆囊切除术", ("matched", 1)),
        ("", ("matched", 1)),
    ],
)
def test_single_event_keeps_matching_and_missing_procedure_fallbacks(
    procedure_name: str, expected: tuple[str, int]
) -> None:
    materials = _Materials(
        surgery_records=(
            _record(document_id="record", name="腹腔镜胆囊切除术"),
        )
    )
    events, reason = build_performed_surgery_events(materials)

    association = associate_preop_document_to_surgery_event(
        events=events or (),
        procedure_name=procedure_name,
        record_time=datetime(2026, 1, 1, 7, 0),
    )

    assert reason == ""
    assert (association.state, association.event_index) == expected


def test_clause_that_contains_two_procedure_names_is_ambiguous() -> None:
    materials = _Materials(
        surgery_records=(
            _record(document_id="record", name="腹腔镜胆囊切除术"),
            _record(
                document_id="other",
                name="腹腔镜阑尾切除术",
                begin="2026-01-02 08:00:00+08:00",
            ),
        )
    )
    events, _reason = build_performed_surgery_events(materials)
    association = associate_preop_document_to_surgery_event(
        events=events or (),
        procedure_name="拟行腹腔镜胆囊切除术及腹腔镜阑尾切除术",
        record_time=None,
    )
    assert association.state == "ambiguous"


def test_same_name_document_between_completed_and_next_surgery_matches_next() -> None:
    name = "腹腔镜胆囊切除术"
    materials = _Materials(
        surgery_records=(
            _record(
                document_id="first",
                name=name,
                begin="2026-01-01 07:00:00+08:00",
                record_time="2026-01-01 11:00:00",
                end="2026-01-01 09:00:00+08:00",
            ),
            _record(
                document_id="second",
                name=name,
                begin="2026-01-01 11:00:00+08:00",
            ),
        )
    )
    events, _reason = build_performed_surgery_events(materials)
    association = associate_preop_document_to_surgery_event(
        events=events or (),
        procedure_name=name,
        record_time=datetime(2026, 1, 1, 10, 0),
    )
    assert (association.state, association.event_index) == ("matched", 2)


def test_truncated_surgery_records_do_not_fall_back_to_mr_surgery() -> None:
    class _TruncatedRecordsMaterials(_Materials):
        def rows(self, source_key: str):
            if source_key == "surgery_record":
                raise EvidenceMaterialTruncated("surgery_record")
            return super().rows(source_key)

    events, reason = build_performed_surgery_events(
        _TruncatedRecordsMaterials(
            mr_surgeries=(_mr(surgery_id="mr", name="腹腔镜胆囊切除术"),)
        )
    )
    assert (events, reason) == (None, "source_truncated")


def test_event_indexes_follow_reliable_start_time_not_input_order() -> None:
    materials = _Materials(
        surgery_records=(
            _record(
                document_id="later",
                name="腹腔镜阑尾切除术",
                begin="2026-01-02 08:00:00+08:00",
            ),
            _record(
                document_id="earlier",
                name="腹腔镜胆囊切除术",
                begin="2026-01-01 08:00:00+08:00",
            ),
        )
    )
    events, reason = build_performed_surgery_events(materials)
    assert reason == "" and events is not None
    assert [(event.event_index, event.surgery_name) for event in events] == [
        (1, "腹腔镜胆囊切除术"),
        (2, "腹腔镜阑尾切除术"),
    ]


def test_running_event_builder_uses_formal_records_without_mr_cross_check() -> None:
    materials = _Materials(
        surgery_records=(
            _record(
                document_id="record",
                name="腹腔镜胆囊切除术",
                begin="2026-01-01 08:00:00+08:00",
            ),
        ),
        mr_surgeries=(
            _mr(
                surgery_id="mr-same-event",
                name="腹腔镜胆囊切除术",
                begin=datetime(2026, 1, 1, 8, 0),
            ),
            _mr(
                surgery_id="mr-extra-event",
                name="腹腔镜阑尾切除术",
                begin=datetime(2026, 1, 2, 8, 0),
            ),
        ),
    )
    events, reason = build_performed_surgery_events(materials)
    assert reason == "" and events is not None and len(events) == 1
    assert events[0].surgery_name == "腹腔镜胆囊切除术"


def test_one_formal_record_and_same_day_components_build_one_event() -> None:
    materials = _Materials(
        surgery_records=(
            _record(
                document_id="record-composite",
                name="胸腔镜下右肺上叶切除术+纵隔淋巴结清扫术",
                begin="2026-01-01 08:00:00+08:00",
            ),
        ),
        mr_surgeries=(
            _mr(
                surgery_id="mr-lobectomy",
                name="右肺上叶切除术",
                begin=datetime(2026, 1, 1, 8, 0),
            ),
            _mr(
                surgery_id="mr-nodes",
                name="纵隔淋巴结清扫术",
                begin=datetime(2026, 1, 1, 8, 0),
            ),
        ),
    )
    events, reason = build_performed_surgery_events(materials)
    assert reason == "" and events is not None and len(events) == 1


def test_running_event_builder_does_not_wait_for_mr_components() -> None:
    materials = _Materials(
        surgery_records=(
            _record(
                document_id="record-cholecystectomy",
                name="腹腔镜胆囊切除术",
                begin="2026-01-01 08:00:00+08:00",
            ),
        ),
        mr_surgeries=(
            _mr(
                surgery_id="mr-cholecystectomy",
                name="腹腔镜胆囊切除术",
                begin=datetime(2026, 1, 1, 8, 0),
            ),
            _mr(
                surgery_id="mr-appendectomy",
                name="腹腔镜阑尾切除术",
                begin=datetime(2026, 1, 1, 12, 0),
            ),
        ),
    )
    events, reason = build_performed_surgery_events(materials)
    assert reason == "" and events is not None and len(events) == 1


def test_same_name_rows_at_different_times_are_not_time_shell_duplicates() -> None:
    materials = _Materials(
        surgery_records=(
            _record(
                document_id="substantive-first",
                name="腹腔镜胆囊切除术",
                begin="2026-01-01 08:00:00+08:00",
            ),
            _record(
                document_id="sparse-second",
                name="腹腔镜胆囊切除术",
                begin="2026-01-02 08:00:00+08:00",
                process=None,
                content=None,
            ),
        )
    )
    events, reason = build_performed_surgery_events(materials)
    assert reason == "" and events is not None and len(events) == 2


def test_later_sparse_same_name_event_is_retained_without_mr_dependency() -> None:
    materials = _Materials(
        surgery_records=(
            _record(
                document_id="substantive-first",
                name="腹腔镜胆囊切除术",
                code="51.2300",
                begin="2026-01-01 08:00:00+08:00",
            ),
            _record(
                document_id="sparse-second",
                name="腹腔镜胆囊切除术",
                code="51.2300",
                begin="2026-01-02 08:00:00+08:00",
                record_time="2026-01-02 12:00:00",
                process=None,
                content=None,
            ),
        ),
        mr_surgeries=(
            _mr(
                surgery_id="mr-first",
                name="腹腔镜胆囊切除术",
                code="51.2300",
                begin=datetime(2026, 1, 1, 8, 0),
            ),
        ),
    )
    events, reason = build_performed_surgery_events(materials)
    assert reason == "" and events is not None and len(events) == 2


def test_running_event_builder_never_reads_mr_surgery() -> None:
    class _RunningMaterials(_Materials):
        def rows(self, source_key: str):
            if source_key == "mr_surgery":
                raise AssertionError("running preop rules must not read mr_surgery")
            return super().rows(source_key)

    events, reason = build_performed_surgery_events(
        _RunningMaterials(
            surgery_records=(
                _record(
                    document_id="first",
                    name="腹腔镜胆囊切除术",
                    begin="2026-01-01 08:00:00+08:00",
                ),
                _record(
                    document_id="second",
                    name="腹腔镜阑尾切除术",
                    begin="2026-01-02 08:00:00+08:00",
                ),
            )
        )
    )
    assert reason == "" and events is not None and len(events) == 2


@pytest.mark.parametrize("placeholder", ("无", "无。", "-", "不详", "未记录"))
def test_record_content_placeholders_do_not_make_time_shell_substantive(
    placeholder: str,
) -> None:
    materials = _Materials(
        surgery_records=(
            _record(
                document_id="record-shell",
                name="腹腔镜胆囊切除术",
                code="51.2300",
                process=None,
                content=placeholder,
                begin="2026-01-01 08:00:00+08:00",
            ),
            _record(
                document_id="record-substantive",
                name="腹腔镜胆囊切除术",
                code="51.2300",
                begin="2026-01-01 08:00:00+08:00",
            ),
        ),
        mr_surgeries=(
            _mr(
                surgery_id="mr-cholecystectomy",
                name="腹腔镜胆囊切除术",
                code="51.2300",
            ),
        ),
    )

    assert count_associated_performed_surgery_events(materials) == (1, "")


def test_sparse_record_without_substantive_copy_is_retained() -> None:
    materials = _Materials(
        surgery_records=(
            _record(
                document_id="record-only-shell",
                name="腹腔镜胆囊切除术",
                code="51.2300",
                process=None,
                content=None,
                begin="2026-01-01 08:00:00+08:00",
            ),
        ),
        mr_surgeries=(
            _mr(
                surgery_id="mr-cholecystectomy",
                name="腹腔镜胆囊切除术",
                code="51.2300",
                begin=datetime(2026, 1, 1, 8, 0),
            ),
        ),
    )

    assert count_associated_performed_surgery_events(materials) == (1, "")


def test_two_substantive_surgery_records_still_fail_association() -> None:
    materials = _Materials(
        surgery_records=(
            _record(
                document_id="record-first",
                name="腹腔镜胆囊切除术",
                code="51.2300",
            ),
            _record(
                document_id="record-second",
                name="阑尾切除术",
                code="47.0900",
                begin="2026-01-02 08:00:00+08:00",
            ),
        ),
        mr_surgeries=(
            _mr(
                surgery_id="mr-cholecystectomy",
                name="腹腔镜胆囊切除术",
                code="51.2300",
            ),
        ),
    )

    assert count_associated_performed_surgery_events(materials) == (
        None,
        "association_failed",
    )


def test_component_on_different_natural_day_fails_association() -> None:
    materials = _Materials(
        surgery_records=(
            _record(
                document_id="record-composite",
                name="胸腔镜下右肺上叶切除术+纵隔淋巴结清扫术",
            ),
        ),
        mr_surgeries=(
            _mr(surgery_id="mr-lobectomy", name="右肺上叶切除术"),
            _mr(
                surgery_id="mr-nodes",
                name="纵隔淋巴结清扫术",
                begin=datetime(2026, 1, 2, 0, 0),
            ),
        ),
    )

    assert count_associated_performed_surgery_events(materials) == (
        None,
        "association_failed",
    )


def test_component_name_dictionary_difference_does_not_block_unique_record() -> None:
    materials = _Materials(
        surgery_records=(
            _record(
                document_id="record-composite",
                name="胸腔镜下右肺上叶切除术+纵隔淋巴结清扫术",
            ),
        ),
        mr_surgeries=(
            _mr(surgery_id="mr-lobectomy", name="肺叶切除术（右上叶）"),
            _mr(surgery_id="mr-nodes", name="纵隔淋巴结切除术"),
        ),
    )

    assert count_associated_performed_surgery_events(materials) == (1, "")


def test_same_code_allows_component_name_difference() -> None:
    materials = _Materials(
        surgery_records=(
            _record(
                document_id="record-composite",
                name="胸腔镜下右肺上叶切除术+纵隔淋巴结清扫术",
                code="32.4100",
            ),
        ),
        mr_surgeries=(
            _mr(
                surgery_id="mr-lobectomy",
                name="肺叶切除术",
                code="32.4100",
            ),
        ),
    )

    assert count_associated_performed_surgery_events(materials) == (1, "")


def test_missing_component_time_fails_association() -> None:
    materials = _Materials(
        surgery_records=(
            _record(
                document_id="record-composite",
                name="胸腔镜下右肺上叶切除术+纵隔淋巴结清扫术",
                code="32.4100",
            ),
        ),
        mr_surgeries=(
            _mr(
                surgery_id="mr-lobectomy",
                name="肺叶切除术",
                code="32.4100",
            ),
            _mr(
                surgery_id="mr-nodes",
                name="纵隔淋巴结清扫术",
                begin=None,
            ),
        ),
    )

    assert count_associated_performed_surgery_events(materials) == (
        None,
        "association_failed",
    )


def _timed_events(*specs):
    materials = _Materials(surgery_records=tuple(
        _record(document_id=f"record-{index}", name=name, begin=begin)
        for index, (name, begin) in enumerate(specs, start=1)
    ))
    events, reason = build_performed_surgery_events(materials)
    assert reason == ""
    return events or ()


@pytest.mark.parametrize(("procedure_name", "record_time", "planned", "expected"), [
    # 用户口径（2026-10-11）：时间优先，拟施术式写法不同不再阻断。
    ("拟行显微镜下左侧精索静脉低位结扎术", datetime(2026, 1, 1, 7, 0), None, ("matched", 1)),
    ("胸腔镜下右肺上叶结节楔形切除术", None, datetime(2026, 1, 1), ("matched", 1)),
    # 手术开始后才完成的属补写，不归属。
    ("拟行腹腔镜胆囊切除术", datetime(2026, 1, 1, 9, 0), None, ("ambiguous", None)),
    # 拟手术日期当天无手术。
    ("拟行腹腔镜胆囊切除术", None, datetime(2026, 1, 3), ("ambiguous", None)),
])
def test_single_surgery_association_is_time_first(procedure_name, record_time, planned, expected) -> None:
    events = _timed_events(("显微镜下精索静脉低位结扎术", "2026-01-01 08:00:00+08:00"))
    association = associate_preop_document_to_surgery_event(
        events=events, procedure_name=procedure_name, record_time=record_time, planned_surgery_time=planned,
    )
    assert (association.state, association.event_index) == expected


def test_preop_document_belongs_to_next_surgery_by_time_regardless_of_name() -> None:
    events = _timed_events(("甲手术", "2026-01-01 08:00:00+08:00"), ("乙手术", "2026-01-03 08:00:00+08:00"))
    association = associate_preop_document_to_surgery_event(
        events=events, procedure_name="拟行甲手术", record_time=datetime(2026, 1, 2, 10, 0),
    )
    assert (association.state, association.event_index) == ("matched", 2)


@pytest.mark.parametrize(("procedure_name", "expected"), [
    ("拟行乙手术", ("matched", 2)),
    ("拟行丙手术", ("ambiguous", None)),
])
def test_same_day_surgeries_are_split_by_name_only_when_time_cannot(procedure_name, expected) -> None:
    events = _timed_events(("甲手术", "2026-01-01 08:00:00+08:00"), ("乙手术", "2026-01-01 14:00:00+08:00"))
    association = associate_preop_document_to_surgery_event(
        events=events, procedure_name=procedure_name, record_time=None, planned_surgery_time=datetime(2026, 1, 1),
    )
    assert (association.state, association.event_index) == expected


@pytest.mark.parametrize(("text", "expected"), [
    ("麻醉方式：全麻拟诊手术日期：2025年08月15日手术要点：术中注意。", datetime(2025, 8, 15)),
    ("拟诊手术日期::2025-08-06手术要点：术中注意。", datetime(2025, 8, 6)),
    ("拟施手术日期：2025年8月10日", datetime(2025, 8, 10)),
    ("拟手术日期：2025年1月2日；拟手术日期：2025年1月3日", None),
    ("拟手术日期：2025年2月30日", None),
    ("入院日期：2025年1月2日", None),
])
def test_summary_planned_date_label_in_body(text, expected) -> None:
    from app.services.luxian_0609.surgery_event_association import summary_planned_surgery_time_from_row

    assert summary_planned_surgery_time_from_row({"record_content": text}) == expected
