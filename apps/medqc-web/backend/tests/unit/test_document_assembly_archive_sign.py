"""状态标志字段不得被装配为签名人。

`cdm.mr.archive_sign` 的模型语义是“归档标志”，本地真实取值为“是”一类的状态值；
`print_sign` 在字段清单中同样标注为“打印标志”。两者都不是人名。装配层的签名
映射必须只产出真实的签名身份，不得把状态字段投影成签名人；原始字段仍须按
元数据列保留。
"""

from app.services.bundles.assembly import _inventory_entry
from app.services.bundles.emr_view import _normalize_source_document
from app.services.document_assembly.assembler import (
    build_document_select_columns,
    extract_document_identity_metadata,
)


def test_archive_sign_state_value_is_not_a_signature_person() -> None:
    metadata = extract_document_identity_metadata(
        {
            "submitter": "张医生",
            "submitter_id": "D001",
            "physician_sign": "王医生",
            "archive_sign": "是",
            "print_sign": "是",
        }
    )

    assert metadata["signatures"] == [
        {
            "role": "physician",
            "name": "王医生",
            "source_field": "physician_sign",
        }
    ]
    assert all(
        item.get("source_field") != "archive_sign" for item in metadata["signatures"]
    )
    assert all(item["name"] != "是" for item in metadata["signatures"])
    assert all(
        item.get("source_field") not in {"archive_sign", "print_sign"}
        for item in metadata["signatures"]
    )


def test_mr_inventory_entry_keeps_archive_flag_out_of_signatures() -> None:
    entry = _inventory_entry(
        table_name="mr",
        row={
            "document_id": "mr-1",
            "document_title": "病案首页",
            "record_content": "病案首页正文。",
            "archive_sign": "是",
            "print_sign": "是",
            "physician_sign": "王医生",
        },
    )

    assert entry["signatures"] == [
        {
            "role": "physician",
            "name": "王医生",
            "source_field": "physician_sign",
        }
    ]
    assert all(
        item.get("source_field") not in {"archive_sign", "print_sign"}
        for item in entry["signatures"]
    )

    normalized = _normalize_source_document(
        raw_doc=entry,
        index=0,
        execution_domain="index_coding_settlement",
    )
    assert all(
        item.get("source_field") not in {"archive_sign", "print_sign"}
        for item in normalized["signatures"]
    )


def test_archive_sign_raw_field_is_still_selectable_metadata() -> None:
    # 错误签名映射被移除后，原始归档字段仍须能被选中并原样承载。
    columns = build_document_select_columns(
        "mr",
        {"document_id", "archive_sign", "physician_sign"},
    )

    assert "archive_sign" in columns
    assert "physician_sign" in columns


def test_print_sign_flag_is_not_a_signature_person() -> None:
    metadata = extract_document_identity_metadata(
        {
            "physician_sign": "王医生",
            "print_sign": "是",
        }
    )

    assert metadata["signatures"] == [
        {
            "role": "physician",
            "name": "王医生",
            "source_field": "physician_sign",
        }
    ]
    # 打印标志不得被投影为 printer 签名角色。
    assert all(item["role"] != "printer" for item in metadata["signatures"])

    entry = _inventory_entry(
        table_name="labtest_master",
        row={
            "document_id": "lab-1",
            "document_title": "检验申请单",
            "record_content": "检验申请正文。",
            "print_sign": "是",
        },
    )
    assert entry["signatures"] == []


def test_print_sign_raw_field_is_still_selectable_metadata() -> None:
    columns = build_document_select_columns(
        "labtest_master",
        {"document_id", "print_sign"},
    )

    assert "print_sign" in columns
