"""固定测试病历的可回导导出与安全复制。"""

from __future__ import annotations

import io
from copy import deepcopy
from typing import Any, Callable

from openpyxl import load_workbook

from .custom_qc_sample_pool_service import CustomQCSamplePoolService
from .test_record_import_service import (
    MAX_CASES,
    TestRecordImportValidationError,
    build_test_record_import_template,
    parse_test_record_import,
)

EXPORT_FILENAME = "V3.6-test-records.xlsx"


class CustomerTestRecordCopyResultUnknown(RuntimeError):
    """创建链可能已提交，但调用方未能拿到最终回执。"""


def _service() -> CustomQCSamplePoolService:
    return CustomQCSamplePoolService()


def _literal_row(sheet: Any, values: list[Any]) -> None:
    if any(isinstance(value, str) and len(value) > 32_767 for value in values):
        raise ValueError("导出内容超过 Excel 单元格上限，无法完整导出")
    sheet.append(values)
    row_number = sheet.max_row
    for column, value in enumerate(values, start=1):
        if isinstance(value, str):
            cell = sheet.cell(row_number, column)
            cell.value = value
            cell.data_type = "s"


def export_customer_test_records(
    *,
    item_ids: list[str],
    allowed_rule_ids: set[str],
    sample_service_factory: Callable[[], CustomQCSamplePoolService] = _service,
) -> tuple[bytes, int]:
    if not isinstance(item_ids, list) or not item_ids:
        raise ValueError("至少选择一份测试病历")
    if len(item_ids) > MAX_CASES:
        raise ValueError(f"每次最多导出 {MAX_CASES} 份测试病历")
    normalized = [str(item_id or "").strip() for item_id in item_ids]
    if any(not item_id for item_id in normalized) or len(set(normalized)) != len(normalized):
        raise ValueError("测试病历 ID 不能为空或重复")
    payloads = sample_service_factory().load_customer_test_record_transfer_payloads(
        item_ids=normalized,
    )
    if len(payloads) != len(normalized):
        raise RuntimeError("测试病历导出读取不完整")
    allowed = {str(rule_id).strip().upper() for rule_id in allowed_rule_ids}
    for payload in payloads:
        unknown_rules = [
            rule_id for rule_id in payload.get("selected_rule_ids") or []
            if str(rule_id).strip().upper() not in allowed
        ]
        if unknown_rules:
            raise ValueError("所选测试病历包含当前规则集外的质控点")

    workbook = load_workbook(io.BytesIO(build_test_record_import_template()))
    cases = workbook["病历"]
    documents = workbook["文书"]
    cases.delete_rows(2, max(cases.max_row - 1, 0))
    documents.delete_rows(2, max(documents.max_row - 1, 0))
    for index, payload in enumerate(payloads, start=1):
        case_key = f"CASE-{index:03d}"
        basic = payload["basic_info"]
        _literal_row(cases, [
            case_key,
            "合成测试病历",
            payload["case_title"],
            basic["patient_name"],
            basic["sex"],
            basic["age"],
            basic["department"],
            basic["admission_time"],
            basic.get("discharge_time") or "",
            basic.get("mr_no") or "",
            basic.get("main_diagnosis") or "",
            "、".join(basic.get("other_diagnoses") or []),
            ",".join(payload.get("selected_rule_ids") or []),
            payload.get("manual_issue_text") or "",
        ])
        for document in payload["documents"]:
            _literal_row(documents, [
                case_key,
                document["document_type"],
                document["title"],
                document.get("record_time") or "",
                document.get("submit_time") or "",
                document["content"],
                document.get("doctor_name") or "",
                document.get("doctor_code") or "",
            ])
    output = io.BytesIO()
    workbook.save(output)
    workbook.close()
    content = output.getvalue()
    try:
        parse_test_record_import(
            content,
            allowed_rule_ids=allowed,
            file_sha256="export-validation",
        )
    except TestRecordImportValidationError as exc:
        first = exc.errors[0].message if exc.errors else "导出文件不符合导入合同"
        raise ValueError(f"导出文件无法完整回导：{first}") from exc
    return content, len(payloads)


def copy_customer_test_record(
    *,
    item_id: str,
    expected_updated_at: str,
    case_title: str | None,
    created_by: str,
    sample_service_factory: Callable[[], CustomQCSamplePoolService] = _service,
) -> dict[str, Any]:
    source_id = str(item_id or "").strip()
    actor = str(created_by or "").strip()
    if not source_id:
        raise ValueError("测试病历 ID 不能为空")
    if not actor or actor.lower() == "anonymous":
        raise ValueError("复制测试病历需要有效操作人")
    service = sample_service_factory()
    payloads = service.load_customer_test_record_transfer_payloads(
        item_ids=[source_id], expected_updated_at=expected_updated_at,
    )
    if len(payloads) != 1:
        raise RuntimeError("测试病历复制读取不完整")
    source = payloads[0]
    payload = deepcopy(source)
    payload.pop("source_item_id", None)
    payload.pop("source_updated_at", None)
    requested_title = str(case_title or "").strip()
    title = requested_title or f"{source['case_title']} - 副本"
    if not title or len(title) > 200:
        raise ValueError("测试病历名称不能为空且不能超过 200 个字符")
    payload["case_title"] = title
    payload["golden_answers"] = []
    payload["source"] = {
        "type": "customer_test_record_copy",
        "source_pool_id": "customer-created-test-records-v1",
        "source_record_id": source_id,
        "source_item_ids": [source_id],
        "created_from": "test_record_management_copy",
    }
    try:
        created = service.create_customer_test_record(payload=payload, created_by=actor)
    except Exception as exc:
        raise CustomerTestRecordCopyResultUnknown(
            "测试病历可能已复制，请勿重试；请刷新列表并按来源或名称核对"
        ) from exc
    return {
        **created,
        "source_item_id": source_id,
        "source_updated_at": expected_updated_at,
    }
