import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List

from ..core.supabase_client import get_supabase, async_execute
from ..core.settings import get_settings
from ..storage.memory import medical_records_db

logger = logging.getLogger(__name__)


async def get_classification_mapping() -> Dict[str, Dict[str, str]]:
    try:
        supabase = get_supabase()
        if not supabase:
            return {"categories": {}, "types": {}}

        categories_response = await async_execute(supabase.table("document_categories_test").select("id, category_code"))
        categories = {cat["category_code"]: cat["id"] for cat in (categories_response.data or [])}

        types_response = await async_execute(
            supabase.table("document_types_test").select(
                "id, type_code, category_id, document_categories_test!inner(category_code)"
            )
        )

        types: Dict[str, str] = {}
        if types_response.data:
            for doc_type in types_response.data:
                parent_code = doc_type["document_categories_test"]["category_code"]
                key = f"{parent_code}.{doc_type['type_code']}"
                types[key] = doc_type["id"]

        return {"categories": categories, "types": types}
    except Exception as e:
        logger.error(f"获取分类映射失败: {e}")
        return {"categories": {}, "types": {}}


def infer_category_from_type(type_code: str) -> str:
    type_to_category_mapping = {
        # 病程记录
        "first_progress_note": "progress_note",
        "daily_progress_note": "progress_note",
        "attending_progress": "progress_note",
        "consultation_record": "progress_note",
        "handover_record": "progress_note",
        "transfer_record": "progress_note",
        "stage_summary": "progress_note",
        # 手术记录
        "preoperative_summary": "operation_record",
        "preoperative_discussion": "operation_record",
        "operation_record": "operation_record",
        "postoperative_first_note": "operation_record",
        "anesthesia_record": "operation_record",
        # 检查报告
        "imaging_report": "examination_report",
        "imaging_examination": "examination_report",
        "laboratory_test": "examination_report",
        "pathology_examination": "examination_report",
        "special_examination": "examination_report",
        # 入院记录
        "admission_record": "admission_record",
        "admission_diagnosis": "admission_record",
        # 出院记录
        "discharge_record": "discharge_record",
        "discharge_summary": "discharge_record",
        "death_record": "discharge_record",
        # 护理文书
        "nursing_record": "nursing_document",
        "temperature_chart": "nursing_document",
        "nursing_plan": "nursing_document",
        "nursing_assessment": "nursing_document",
        # 医嘱记录
        "long_term_order": "medical_order",
        "temporary_order": "medical_order",
        "order_execution": "medical_order",
    }
    return type_to_category_mapping.get(type_code, "progress_note")


def extract_document_content(doc: dict, raw_content: str) -> str:
    doc_content = doc.get("content", "") or doc.get("fullContent", "") or doc.get("content_preview", "")
    if not doc_content and raw_content:
        title = doc.get("title", "")
        if title and title in raw_content:
            start_pos = raw_content.find(title)
            if start_pos != -1:
                content_start = start_pos
                remaining_content = raw_content[start_pos + len(title):]
                import re
                next_section_patterns = [
                    r'\n\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}',
                    r'\n[=]{3,}.*[=]{3,}',
                    r'\n\d+\.\s*[^\n]+记录',
                ]
                end_pos = len(raw_content)
                for pattern in next_section_patterns:
                    match = re.search(pattern, remaining_content)
                    if match:
                        potential_end = start_pos + len(title) + match.start()
                        if potential_end < end_pos:
                            end_pos = potential_end
                        break
                doc_content = raw_content[content_start:end_pos].strip()
                doc_content = re.sub(r'\n\s*\n\s*\n', '\n\n', doc_content)
    return doc_content


async def save_medical_documents(medical_record_id: str, documents: list, extraction_method: str = "LLM", raw_content: str = ""):
    supabase = get_supabase()
    if not documents or not supabase:
        return
    try:
        category_mapping = await get_classification_mapping()
        document_records = []
        for i, doc in enumerate(documents):
            category_code = (doc.get("category", "") or "").strip()
            type_code = (doc.get("type", "") or "").strip()
            if not category_code and type_code:
                category_code = infer_category_from_type(type_code)
            category_id = category_mapping.get("categories", {}).get(category_code)
            type_id = category_mapping.get("types", {}).get(f"{category_code}.{type_code}")
            if not category_id:
                for key, tid in category_mapping.get("types", {}).items():
                    if key.endswith(f".{type_code}"):
                        type_id = tid
                        parent_category = key.split(".")[0]
                        category_id = category_mapping.get("categories", {}).get(parent_category)
                        category_code = parent_category
                        break
                if not category_id:
                    category_id = category_mapping.get("categories", {}).get("progress_note")
                    category_code = "progress_note"
            if not type_id:
                type_id = category_mapping.get("types", {}).get(f"{category_code}.{type_code}")
                if not type_id:
                    type_id = category_mapping.get("types", {}).get("progress_note.first_progress_note")
                    type_code = "first_progress_note"
            doc_record = {
                "record_id": medical_record_id,
                "category_id": category_id,
                "type_id": type_id,
                "title": doc.get("title", "未命名文档"),
                "content": extract_document_content(doc, raw_content),
                "summary": doc.get("summary", ""),
                "ai_classified": True,
                "classification_confidence": float(doc.get("confidence", 0)) / 100.0,
                "manual_verified": False,
                "position_info": {
                    "startIndex": doc.get("position", {}).get("startIndex"),
                    "endIndex": doc.get("position", {}).get("endIndex"),
                    "startMarker": doc.get("position", {}).get("startMarker", ""),
                    "endMarker": doc.get("position", {}).get("endMarker", ""),
                },
                "sort_order": i + 1,
                "status": "active",
                "qc_status": "pending",
                "metadata": {
                    "extracted_at": doc.get("extractedAt"),
                    "original_doc_id": doc.get("id"),
                    "extraction_method": extraction_method,
                    "category_code": category_code,
                    "type_code": type_code,
                    **(doc.get("metadata", {}) or {}),
                },
            }
            document_records.append(doc_record)

        if document_records:
            settings = get_settings()
            delete_response = await async_execute(supabase.table(settings.DOCUMENTS_TABLE).delete().eq("record_id", medical_record_id))
            logger.info(f"清理旧文档记录: {len(delete_response.data) if delete_response.data else 0} 条")
            unique_records: Dict[Any, Dict[str, Any]] = {}
            for dr in document_records:
                key = (dr["record_id"], dr["type_id"], dr["title"])
                if key not in unique_records:
                    unique_records[key] = dr
                else:
                    if len(dr.get("content", "")) > len(unique_records[key].get("content", "")):
                        unique_records[key] = dr
            final_records = list(unique_records.values())
            if final_records:
                settings = get_settings()
                response = await async_execute(supabase.table(settings.DOCUMENTS_TABLE).insert(final_records))
                logger.info(f"保存 {len(response.data or [])} 个文档记录到medical_documents_test")
    except Exception as e:
        logger.warning(f"保存文档记录失败: {e}")


async def ingest_llm_parse_result(data: Dict[str, Any]) -> Dict[str, Any]:
    record_id = str(uuid.uuid4())
    supabase = get_supabase()
    try:
        record_data = {
            "record_number": data.get("record_number") or f"LLM_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            "record_name": f"{data.get('patient_name') or '未识别'}的病历记录",
            "patient_info": {
                "name": data.get("patient_name") or '未识别',
                "age": data.get("patient_age") or 0,
                "gender": data.get("patient_gender") or '未识别',
            },
            "department": data.get("department") or '未识别',
            "primary_diagnosis": data.get("primary_diagnosis") or '',
            "secondary_diagnosis": data.get("secondary_diagnosis") or [],
            "major_surgery": data.get("major_surgery") or '',
            "raw_text": data.get("content") or '',
            "ai_extraction_result": {
                "patient_info": {
                    "name": data.get("patient_name") or '未识别',
                    "age": data.get("patient_age") or 0,
                    "gender": data.get("patient_gender") or '未识别',
                },
                "diagnosis": data.get("primary_diagnosis") or '',
                "documents": data.get("documents") or [],
                "confidence": data.get("confidence") or 0,
                "method": data.get("method") or 'LLM精准解析',
                "parse_metadata": data.get("parse_metadata") or {},
            },
            "ai_confidence_score": data.get("confidence") or 0,
            "documents": data.get("documents") or [],
            "status": "active",
            "import_method": "smart_import",
        }

        if supabase:
            settings = get_settings()
            response = await async_execute(supabase.table(settings.RECORDS_TABLE).insert(record_data))
            if response.data:
                saved_record = response.data[0]
                department_name = "未识别"
                if saved_record.get("content_sections"):
                    department_name = saved_record["content_sections"].get("department_name", "未识别")
                elif saved_record.get("metadata"):
                    department_name = saved_record["metadata"].get("department_name", "未识别")
                patient_info = saved_record.get("patient_info", {})
                response_record = {
                    "id": saved_record.get("id", record_id),
                    "patient_name": patient_info.get("name", "未识别"),
                    "patient_age": patient_info.get("age", 0),
                    "patient_gender": patient_info.get("gender", "未识别"),
                    "department": saved_record.get("department", "未识别"),
                    "admission_date": saved_record.get("admission_date", datetime.utcnow().isoformat()),
                    "record_type": "LLM解析结果",
                    "content": saved_record.get("raw_text", ""),
                    "status": saved_record.get("status", "active"),
                    "created_at": saved_record.get("created_at", datetime.utcnow().isoformat()),
                    "updated_at": saved_record.get("updated_at", datetime.utcnow().isoformat()),
                    "created_by": saved_record.get("created_by", "llm-system"),
                    "file_url": None,
                }
                await save_medical_documents(
                    medical_record_id=saved_record.get("id", record_id),
                    documents=data.get("documents") or [],
                    extraction_method=data.get("method") or 'LLM精准解析',
                    raw_content=data.get("content") or "",
                )
                return response_record
            else:
                raise RuntimeError("Supabase插入返回空数据")
        # fallback to memory
        memory_record = {
            "id": record_id,
            "patient_name": data.get("patient_name") or "未识别",
            "patient_age": data.get("patient_age") or 0,
            "patient_gender": data.get("patient_gender") or "未识别",
            "department": data.get("department") or "未识别",
            "admission_date": datetime.utcnow().isoformat() + "Z",
            "record_type": "LLM解析结果",
            "content": data.get("content") or "",
            "status": "completed",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "updated_at": datetime.utcnow().isoformat() + "Z",
            "created_by": "llm-system",
            "file_url": None,
        }
        medical_records_db[record_id] = memory_record
        return memory_record
    except Exception as e:
        logger.error(f"保存LLM解析结果失败: {e}")
        raise
