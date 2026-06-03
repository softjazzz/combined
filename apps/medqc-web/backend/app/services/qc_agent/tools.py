from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List

from fastapi import HTTPException, status
from pydantic import BaseModel

from app.services.custom_qc_workspace_service import CustomQCWorkspaceService
from app.services.frontpage_formal_qc import Category, FrontpageFormalQC, QCResult, Severity

from .schemas import (
    AgentToolObservation,
    GetRecordContextInput,
    RecordSummary,
    RunFrontpageQCInput,
    SearchRecordsInput,
    SearchRecordsPublicData,
)
from .tool_registry import AgentToolRegistry


SENSITIVE_OUTPUT_KEYS = {
    "medical_text",
    "record_content",
    "documents",
    "bundle",
    "structured_context",
    "text_preview",
    "frontpage_draft",
    "raw_draft",
    "draft_json",
}


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _record_summary(record: Dict[str, Any]) -> RecordSummary:
    return RecordSummary(
        visit_id=_text(record.get("visit_id") or record.get("record_id")),
        patient_id=_text(record.get("patient_id")),
        patient_name=_text(record.get("patient_name") or record.get("name")),
        department=_text(record.get("department")),
        doctor=_text(record.get("doctor") or record.get("attending_physician")),
        admission_date=_text(record.get("admission_date") or record.get("admission_datetime"))[:10],
        discharge_date=_text(record.get("discharge_date") or record.get("discharge_datetime"))[:10],
    )


def _record_summary_dict(record: Dict[str, Any]) -> Dict[str, Any]:
    summary = _record_summary(record).model_dump()
    summary["mr_no"] = _text(record.get("mr_no") or record.get("medical_record_no"))
    return summary


def _drop_sensitive_keys(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _drop_sensitive_keys(item)
            for key, item in value.items()
            if str(key) not in SENSITIVE_OUTPUT_KEYS
        }
    if isinstance(value, list):
        return [_drop_sensitive_keys(item) for item in value]
    return value


def assert_no_sensitive_output(value: Any) -> None:
    """测试和路由防御用：确保工具输出未携带病历全文或 bundle。"""
    if isinstance(value, dict):
        forbidden = SENSITIVE_OUTPUT_KEYS.intersection({str(key) for key in value.keys()})
        if forbidden:
            raise ValueError(f"工具输出包含敏感字段: {', '.join(sorted(forbidden))}")
        for item in value.values():
            assert_no_sensitive_output(item)
    elif isinstance(value, list):
        for item in value:
            assert_no_sensitive_output(item)


def _mask_sensitive_text(text: str) -> str:
    masked = re.sub(
        r"(?<!\d)(\d{6})\d{8}(\d{3}[\dXx])(?!\d)",
        r"\1********\2",
        text,
    )
    masked = re.sub(
        r"(?<!\d)(\d{6})\d{5}(\d{4})(?!\d)",
        r"\1*****\2",
        masked,
    )
    masked = re.sub(
        r"(?<!\d)(1[3-9])\d{7}(\d{2})(?!\d)",
        r"\1*******\2",
        masked,
    )
    masked = re.sub(
        r"((?:现住址|家庭住址|联系地址|地址|住址)[:：])\s*[^\n\r，,；;]{6,80}",
        r"\1[已脱敏]",
        masked,
    )
    return masked


def _extract_document_text(document: Dict[str, Any]) -> str:
    for key in ("content", "text", "medical_text", "record_content"):
        value = document.get(key)
        if value:
            return _text(value)
    return ""


def _document_type(document: Dict[str, Any]) -> str:
    return _text(
        document.get("document_type")
        or document.get("doc_type")
        or document.get("type")
        or document.get("name")
        or "未知文书"
    )


def _document_time(document: Dict[str, Any]) -> str:
    return _text(
        document.get("updated_at")
        or document.get("record_time")
        or document.get("document_time")
        or document.get("created_at")
    )


def _summarize_documents(documents: Any) -> List[Dict[str, Any]]:
    if not isinstance(documents, list):
        return []
    grouped: Dict[str, Dict[str, Any]] = {}
    for document in documents:
        if not isinstance(document, dict):
            continue
        doc_type = _document_type(document)
        summary = grouped.setdefault(
            doc_type,
            {
                "document_type": doc_type,
                "count": 0,
                "text_length": 0,
                "latest_time": "",
            },
        )
        summary["count"] += 1
        summary["text_length"] += len(_extract_document_text(document))
        doc_time = _document_time(document)
        if doc_time and doc_time > summary["latest_time"]:
            summary["latest_time"] = doc_time
    return list(grouped.values())


def _extract_medical_text(record: Dict[str, Any]) -> str:
    for key in ("medical_text", "record_content", "text"):
        value = record.get(key)
        if value:
            return _text(value)
    documents = record.get("documents")
    if isinstance(documents, list):
        parts = [_extract_document_text(document) for document in documents if isinstance(document, dict)]
        return "\n".join(part for part in parts if part)
    return ""


def _first_match(text: str, patterns: Iterable[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _text(match.group(1))
    return ""


def _parse_int(value: str) -> int | None:
    if not value:
        return None
    match = re.search(r"\d+", value)
    if not match:
        return None
    try:
        return int(match.group(0))
    except ValueError:
        return None


def _parse_float(value: str) -> float | None:
    if not value:
        return None
    match = re.search(r"\d+(?:\.\d+)?", value)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _normalize_datetime(value: str) -> str:
    if not value:
        return ""
    normalized = value.replace("年", "-").replace("月", "-").replace("日", "")
    normalized = re.sub(r"[/.]", "-", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", normalized):
        parts = normalized.split("-")
        return f"{parts[0]}-{int(parts[1]):02d}-{int(parts[2]):02d}"
    return normalized


def _sex_code(value: str) -> int | None:
    if value == "男":
        return 1
    if value == "女":
        return 2
    return None


def _extract_diagnoses(text: str) -> List[Dict[str, Any]]:
    main_name = _first_match(
        text,
        [
            r"出院主要诊断[:：]?\s*([^\n\r；;，,]+)",
            r"主要诊断[:：]?\s*([^\n\r；;，,]+)",
            r"出院诊断[:：]?\s*([^\n\r；;，,]+)",
        ],
    )
    main_code = _first_match(
        text,
        [
            r"主要诊断编码[:：]?\s*([A-Z]\d{2}(?:\.\d{1,4})?)",
            r"出院主要诊断.*?([A-Z]\d{2}(?:\.\d{1,4})?)",
            r"出院诊断编码[:：]?\s*([A-Z]\d{2}(?:\.\d{1,4})?)",
        ],
    )
    diagnoses: List[Dict[str, Any]] = []
    if main_name or main_code:
        diagnoses.append(
            {
                "diagnosis_name": main_name,
                "diagnosis_code": main_code,
                "diagnosis_type": "main",
                "admission_condition": _first_match(text, [r"入院病情[:：]?\s*([^\n\r；;，,]+)"]),
            }
        )

    other_line = _first_match(
        text,
        [
            r"出院其他诊断[:：]?\s*([^\n\r]+)",
            r"其他诊断[:：]?\s*([^\n\r]+)",
        ],
    )
    if other_line:
        names = [item.strip() for item in re.split(r"[；;、,，]", other_line) if item.strip()]
        codes = re.findall(r"[A-Z]\d{2}(?:\.\d{1,4})?", other_line, flags=re.IGNORECASE)
        for index, name in enumerate(names[:8]):
            clean_name = re.sub(r"[A-Z]\d{2}(?:\.\d{1,4})?", "", name, flags=re.IGNORECASE).strip(" ：:")
            diagnoses.append(
                {
                    "diagnosis_name": clean_name or name,
                    "diagnosis_code": codes[index] if index < len(codes) else "",
                    "diagnosis_type": "other",
                    "admission_condition": "",
                }
            )
    return diagnoses


def _extract_surgeries(text: str) -> List[Dict[str, Any]]:
    surgery_name = _first_match(
        text,
        [
            r"主要手术及操作[:：]?\s*([^\n\r；;，,]+)",
            r"手术名称[:：]?\s*([^\n\r；;，,]+)",
            r"手术及操作名称[:：]?\s*([^\n\r；;，,]+)",
        ],
    )
    surgery_code = _first_match(
        text,
        [
            r"主要手术及操作编码[:：]?\s*(\d{2}\.\d{2,4})",
            r"手术及操作代码[:：]?\s*(\d{2}\.\d{2,4})",
            r"手术编码[:：]?\s*(\d{2}\.\d{2,4})",
        ],
    )
    if not surgery_name and not surgery_code:
        return []
    return [
        {
            "surgery_name": surgery_name,
            "surgery_code": surgery_code,
            "surgery_date": _normalize_datetime(
                _first_match(text, [r"手术日期[:：]?\s*([0-9年月日\-/. :]+)"])
            ),
            "surgeon_name": _first_match(text, [r"术者[:：]?\s*([^\n\r；;，,]+)"]),
            "anesthesia_method": _first_match(text, [r"麻醉方式[:：]?\s*([^\n\r；;，,]+)"]),
        }
    ]


def _build_transient_frontpage_from_text(
    medical_text: str,
    record_summary: Dict[str, Any],
) -> tuple[Dict[str, Any], List[str]]:
    """构造仅供首页形式质控使用的内存首页字典，不持久化也不对外返回。"""
    warnings: List[str] = []
    patient_name = _first_match(medical_text, [r"姓名[:：]?\s*([\u4e00-\u9fa5A-Za-z·]{2,20})"])
    gender = _first_match(medical_text, [r"性别[:：]?\s*(男|女)"])
    age = _parse_int(_first_match(medical_text, [r"年龄[:：]?\s*(\d{1,3})\s*岁?"]))
    id_card = _first_match(
        medical_text,
        [
            r"身份证号(?:码)?[:：]?\s*([1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx])",
            r"患者证件号码[:：]?\s*([1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx])",
        ],
    )
    admission_datetime = _normalize_datetime(
        _first_match(medical_text, [r"入院时间[:：]?\s*([0-9年月日\-/. :]+)"])
    )
    discharge_datetime = _normalize_datetime(
        _first_match(medical_text, [r"出院时间[:：]?\s*([0-9年月日\-/. :]+)"])
    )
    diagnoses = _extract_diagnoses(medical_text)
    surgeries = _extract_surgeries(medical_text)
    if not diagnoses:
        warnings.append("未从病历文本识别到出院诊断，首页形式质控将按缺失处理")

    frontpage = {
        "visit_id": record_summary.get("visit_id", ""),
        "patient_id": record_summary.get("patient_id", ""),
        "patient_name": patient_name or record_summary.get("patient_name", ""),
        "sex": _sex_code(gender),
        "sex_text": gender,
        "age": age,
        "id_card": id_card,
        "admission_datetime": admission_datetime,
        "discharge_datetime": discharge_datetime,
        "admission_dept": _first_match(medical_text, [r"入院科(?:别|室)?[:：]?\s*([^\n\r；;，,]+)"]),
        "discharge_dept": _first_match(medical_text, [r"出院科(?:别|室)?[:：]?\s*([^\n\r；;，,]+)"]),
        "admission_route": _parse_int(_first_match(medical_text, [r"入院途径[:：]?\s*(\d)"])),
        "discharge_method": _parse_int(_first_match(medical_text, [r"离院方式[:：]?\s*(\d)"])),
        "los_days": _parse_int(_first_match(medical_text, [r"实际住院(?:天数)?[:：]?\s*(\d{1,4})\s*天"])),
        "attending_physician": _first_match(
            medical_text,
            [r"主诊医师[:：]?\s*([^\n\r；;，,]+)", r"主治医师[:：]?\s*([^\n\r；;，,]+)"],
        ) or record_summary.get("doctor", ""),
        "total_cost": _parse_float(_first_match(medical_text, [r"总费用[:：]?\s*([0-9]+(?:\.[0-9]+)?)"])),
        "coma_hours_before": _parse_int(_first_match(medical_text, [r"入院前昏迷(?:时间)?[:：]?\s*(\d+)\s*小时"])),
        "coma_hours_after": _parse_int(_first_match(medical_text, [r"入院后昏迷(?:时间)?[:：]?\s*(\d+)\s*小时"])),
        "diagnoses": diagnoses,
        "surgeries": surgeries,
    }
    return frontpage, warnings


def _normalize_rule_scope(params: RunFrontpageQCInput) -> tuple[List[Category] | None, List[Severity] | None]:
    if not params.rule_scope:
        return None, None
    categories = None
    severities = None
    if params.rule_scope.categories:
        categories = [Category(item) for item in params.rule_scope.categories]
    if params.rule_scope.severities:
        severities = [Severity(item) for item in params.rule_scope.severities]
    return categories, severities


def _qc_issue(result: QCResult) -> Dict[str, Any]:
    status_text = "通过" if result.passed else "未通过"
    suggestion = "" if result.passed else f"请核对或补充 {result.field_name}"
    return {
        "rule_id": result.rule_id,
        "rule_name": result.rule_name,
        "field_name": result.field_name,
        "severity": result.severity.value,
        "category": result.category.value,
        "message": result.message,
        "evidence_summary": f"规则 {result.rule_id} 对字段 {result.field_name} 的形式质控结果为{status_text}",
        "suggestion": suggestion,
    }


def _read_context_record(
    service: CustomQCWorkspaceService,
    record: Dict[str, Any],
) -> tuple[Dict[str, Any], str]:
    hydrate = getattr(service, "hydrate_records_with_medical_text", None)
    if not callable(hydrate):
        return record, "collect_records"
    hydrated = hydrate([record])
    if isinstance(hydrated, list) and hydrated:
        return hydrated[0], "hydrate_records_with_medical_text"
    return record, "hydrate_records_with_medical_text"


def search_records(payload: BaseModel, workspace: CustomQCWorkspaceService | None = None) -> AgentToolObservation:
    params = payload if isinstance(payload, SearchRecordsInput) else SearchRecordsInput(**payload.model_dump())
    service = workspace or CustomQCWorkspaceService()

    records = service.collect_records(
        scope=params.scope,
        department=params.department,
        doctor=params.doctor,
        date_field=params.date_field,
        start_date=params.start_date,
        end_date=params.end_date,
        keyword=params.keyword,
        record_ids=None,
    )
    total = len(records)
    start = (params.page - 1) * params.page_size
    end = start + params.page_size
    page_records = records[start:end]
    summaries = [_record_summary(record).model_dump() for record in page_records]
    public = SearchRecordsPublicData(
        records=summaries,
        total=total,
        page=params.page,
        page_size=params.page_size,
        capped=total > params.page_size,
    ).model_dump()
    internal = {
        "matched_record_count": total,
        "returned_record_count": len(summaries),
        "filters": params.model_dump(),
        "record_refs": [
            {
                "visit_id": item.get("visit_id", ""),
                "patient_id": item.get("patient_id", ""),
            }
            for item in summaries
        ],
    }
    public = _drop_sensitive_keys(public)
    internal = _drop_sensitive_keys(internal)
    assert_no_sensitive_output(public)
    assert_no_sensitive_output(internal)
    return AgentToolObservation(
        tool_name="search_records",
        status="success",
        public_data=public,
        internal_data=internal,
    )


def get_record_context(
    payload: BaseModel | Dict[str, Any],
    workspace: CustomQCWorkspaceService | None = None,
) -> AgentToolObservation:
    if isinstance(payload, GetRecordContextInput):
        params = payload
    elif isinstance(payload, dict):
        params = GetRecordContextInput(**payload)
    else:
        params = GetRecordContextInput(**payload.model_dump())
    service = workspace or CustomQCWorkspaceService()
    scope = params.scene if params.scene in {"running", "final"} else "all"
    records = service.collect_records(
        scope=scope,
        department=None,
        doctor=None,
        date_field="discharge",
        start_date=None,
        end_date=None,
        keyword=None,
        record_ids=[params.visit_id],
    )
    matched = [
        record
        for record in records
        if _text(record.get("visit_id") or record.get("record_id")) == params.visit_id
    ]
    if not matched:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到病历: visit_id={params.visit_id}",
        )
    if params.patient_id:
        patient_matched = [
            record for record in matched if _text(record.get("patient_id")) == params.patient_id
        ]
        if not patient_matched:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"patient_id 不匹配: visit_id={params.visit_id}",
            )
        matched = patient_matched
    if len(matched) != 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"visit_id 命中多条病历，需补充 patient_id: {params.visit_id}",
        )

    record = matched[0]
    context_record, source = _read_context_record(service, record)
    medical_text = _extract_medical_text(context_record)
    documents = context_record.get("documents")
    bundle = context_record.get("bundle")
    structured_context = context_record.get("structured_context")
    document_summary = _summarize_documents(documents)
    warnings: List[str] = []
    if not medical_text:
        warnings.append("未读取到病历文本")
    if not document_summary and medical_text:
        document_summary = [
            {
                "document_type": "合并病历文本",
                "count": 1,
                "text_length": len(medical_text),
                "latest_time": "",
            }
        ]
    preview = ""
    if params.include_preview and medical_text:
        preview = _mask_sensitive_text(medical_text)[:500]

    public = {
        "record_summary": _record_summary_dict(context_record),
        "context_status": {
            "text_available": bool(medical_text),
            "text_length": len(medical_text),
            "bundle_available": bool(bundle or structured_context),
            "source": source,
            "scene": params.scene,
        },
        "document_summary": document_summary,
        "preview": preview,
        "warnings": warnings,
    }
    public = _drop_sensitive_keys(public)
    assert_no_sensitive_output(public)
    return AgentToolObservation(
        tool_name="get_record_context",
        status="success",
        public_data=public,
        internal_data={
            "medical_text": medical_text,
            "documents": documents,
            "bundle": bundle,
            "structured_context": structured_context,
            "record_summary": public["record_summary"],
            "scene": params.scene,
            "source": source,
        },
    )


def run_frontpage_qc(
    payload: BaseModel | Dict[str, Any],
    workspace: CustomQCWorkspaceService | None = None,
    qc_engine: FrontpageFormalQC | None = None,
) -> AgentToolObservation:
    if isinstance(payload, RunFrontpageQCInput):
        params = payload
    elif isinstance(payload, dict):
        params = RunFrontpageQCInput(**payload)
    else:
        params = RunFrontpageQCInput(**payload.model_dump())
    if re.search(r"[,，;；|\s]+", params.visit_id.strip()):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="run_frontpage_qc 只支持单个 visit_id",
        )

    context = get_record_context(
        GetRecordContextInput(
            visit_id=params.visit_id,
            patient_id=params.patient_id,
            scene="frontpage",
            include_preview=False,
        ),
        workspace=workspace,
    )
    internal_context = context.internal_data or {}
    medical_text = _text(internal_context.get("medical_text"))
    record_summary = dict(internal_context.get("record_summary") or {})
    if not medical_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"病历上下文缺少 medical_text: visit_id={params.visit_id}",
        )

    frontpage_draft, generation_warnings = _build_transient_frontpage_from_text(
        medical_text,
        record_summary,
    )
    categories, severities = _normalize_rule_scope(params)
    engine = qc_engine or FrontpageFormalQC()
    report = engine.validate(frontpage_draft, categories=categories, severities=severities)
    selected_results = report.results if params.include_passed else [item for item in report.results if not item.passed]
    issues = [_qc_issue(item) for item in selected_results]
    pass_rate = round(report.passed / report.total_rules, 4) if report.total_rules else 1.0
    warnings = list(context.public_data.get("warnings") or []) + generation_warnings
    public = {
        "record_summary": record_summary,
        "qc_summary": {
            "total_rules": report.total_rules,
            "passed": report.passed,
            "failed": report.failed,
            "pass_rate": pass_rate,
            "issue_count": report.failed,
        },
        "issues": issues,
        "generation_status": {
            "draft_generated": True,
            "text_length": len(medical_text),
            "warnings": generation_warnings,
        },
        "warnings": warnings,
    }
    public = _drop_sensitive_keys(public)
    assert_no_sensitive_output(public)
    return AgentToolObservation(
        tool_name="run_frontpage_qc",
        status="success",
        public_data=public,
        internal_data={
            "frontpage_draft": frontpage_draft,
            "text_length": len(medical_text),
            "record_ref": {
                "visit_id": record_summary.get("visit_id", ""),
                "patient_id": record_summary.get("patient_id", ""),
            },
        },
    )


def register_default_tools(registry: AgentToolRegistry) -> AgentToolRegistry:
    registry.register(
        name="search_records",
        description="按安全筛选条件检索病历索引摘要；不返回病历全文。",
        input_model=SearchRecordsInput,
        handler=search_records,
        risk_level="low",
        writes_db=False,
        requires_confirmation=False,
        timeout_ms=5000,
        max_records=50,
    )
    registry.register(
        name="get_record_context",
        description="按 visit_id 只读获取单份病历上下文；API 仅返回摘要和脱敏预览。",
        input_model=GetRecordContextInput,
        handler=get_record_context,
        risk_level="medium",
        writes_db=False,
        requires_confirmation=False,
        timeout_ms=5000,
        max_records=1,
    )
    registry.register(
        name="run_frontpage_qc",
        description="对单份病历生成瞬态首页草稿并执行首页形式质控；不保存草稿或质控结果。",
        input_model=RunFrontpageQCInput,
        handler=run_frontpage_qc,
        risk_level="medium",
        writes_db=False,
        requires_confirmation=False,
        timeout_ms=30000,
        max_records=1,
    )
    return registry


def create_default_registry() -> AgentToolRegistry:
    return register_default_tools(AgentToolRegistry())


def contains_sensitive_keys(records: Iterable[Dict[str, Any]]) -> bool:
    for record in records:
        if SENSITIVE_OUTPUT_KEYS.intersection({str(key) for key in record.keys()}):
            return True
    return False
