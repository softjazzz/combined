from __future__ import annotations

from datetime import datetime

import pytest

from app.services.luxian_0609.surgery_event_association import (
    count_associated_performed_surgery_events,
)


class _Materials:
    def __init__(self, *, surgery_records=(), mr_surgeries=()):
        self._rows = {
            "surgery_record": tuple(surgery_records),
            "mr_surgery": tuple(mr_surgeries),
        }

    def rows(self, source_key: str):
        return self._rows[source_key]


def _record(
    *,
    document_id: str,
    name: str,
    code: str | None = None,
    begin: str = "2026-01-01 08:00:00+08:00",
    process: str | None = "手术经过。",
    content: str | None = None,
) -> dict:
    return {
        "document_id": document_id,
        "surgery_name": name,
        "surgery_code": code,
        "surgery_begin_time": begin,
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


def test_duplicate_time_shell_is_removed_only_when_substantive_copy_exists() -> None:
    materials = _Materials(
        surgery_records=(
            _record(
                document_id="record-shell",
                name="腹腔镜胆囊切除术",
                code="51.2300",
                begin="2026-01-01 07:00:00+08:00",
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
            ),
        ),
    )

    assert count_associated_performed_surgery_events(materials) == (1, "")


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
                begin="2026-01-01 07:00:00+08:00",
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
