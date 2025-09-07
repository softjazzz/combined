import uuid
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form

from ..core.supabase_client import get_supabase
from ..core.security import get_current_user
from ..schemas.records import MedicalRecordResponse
from ..storage.memory import medical_records_db
from ..core.settings import get_settings


router = APIRouter(prefix="/api/records", tags=["records"])


@router.get("")
async def get_medical_records(
    keyword: Optional[str] = None,
    department: Optional[str] = None,
    status: Optional[str] = None,
    record_type: Optional[str] = None,
    sort_field: Optional[str] = None,
    sort_order: Optional[str] = None,
    page: int = 1,
    page_size: int = 10,
):
    supabase = get_supabase()
    settings = get_settings()
    try:
        if supabase:
            # Use our custom REST client which returns _RestResponse with .data
            response = supabase.table(settings.RECORDS_TABLE).select('*').execute()  # type: ignore[attr-defined]
            records = list(response.data or [])
        else:
            # Fallback to in-memory records when Supabase is not configured
            records = list(medical_records_db.values())

        # basic filtering similar to legacy
        if keyword:
            kw = keyword.lower()
            records = [
                r for r in records
                if kw in (str((r.get('record_name') or r.get('patient_name') or '')).lower())
                or kw in (str((r.get('raw_text') or r.get('content') or '')).lower())
            ]
        if department:
            records = [r for r in records if r.get('department') == department]
        if status:
            records = [r for r in records if r.get('status') == status]
        if record_type:
            # in supabase, we mark LLM parse as a special type via metadata; keep simple
            records = [r for r in records if r.get('record_type') == record_type]

        # sorting
        if sort_field:
            reverse = sort_order == 'desc'
            records.sort(key=lambda x: x.get(sort_field, ''), reverse=reverse)

        total = len(records)
        start = (page - 1) * page_size
        end = start + page_size
        page_data = records[start:end]

        return {
            "data": page_data,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取记录列表失败: {e}")


@router.get("/{record_id}", response_model=MedicalRecordResponse)
async def get_medical_record(record_id: str, current_user: dict = Depends(get_current_user)):
    record = medical_records_db.get(record_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="医疗记录不存在")
    return MedicalRecordResponse(**record)


@router.post("")
async def create_medical_record(
    patient_name: str = Form(...),
    patient_age: int = Form(...),
    patient_gender: str = Form(...),
    department: str = Form(...),
    admission_date: str = Form(...),
    record_type: str = Form(...),
    content: str = Form(...),
    file: Optional[UploadFile] = File(None),
    current_user: dict = Depends(get_current_user),
):
    record_id = f"record-{uuid.uuid4().hex[:8]}"
    file_url = f"/uploads/{file.filename}" if file else None
    new_record = {
        "id": record_id,
        "patient_name": patient_name,
        "patient_age": patient_age,
        "patient_gender": patient_gender,
        "department": department,
        "admission_date": admission_date,
        "record_type": record_type,
        "content": content,
        "status": "pending",
        "created_at": datetime.utcnow().isoformat() + "Z",
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "created_by": current_user["id"],
        "file_url": file_url,
    }
    medical_records_db[record_id] = new_record
    return MedicalRecordResponse(**new_record)


@router.put("/{record_id}", response_model=MedicalRecordResponse)
async def update_medical_record(
    record_id: str,
    patient_name: Optional[str] = Form(None),
    patient_age: Optional[int] = Form(None),
    patient_gender: Optional[str] = Form(None),
    department: Optional[str] = Form(None),
    admission_date: Optional[str] = Form(None),
    record_type: Optional[str] = Form(None),
    content: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    current_user: dict = Depends(get_current_user),
):
    record = medical_records_db.get(record_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="医疗记录不存在")

    if patient_name is not None:
        record["patient_name"] = patient_name
    if patient_age is not None:
        record["patient_age"] = patient_age
    if patient_gender is not None:
        record["patient_gender"] = patient_gender
    if department is not None:
        record["department"] = department
    if admission_date is not None:
        record["admission_date"] = admission_date
    if record_type is not None:
        record["record_type"] = record_type
    if content is not None:
        record["content"] = content
    if file:
        record["file_url"] = f"/uploads/{file.filename}"

    record["updated_at"] = datetime.utcnow().isoformat() + "Z"
    return MedicalRecordResponse(**record)


@router.delete("/{record_id}")
async def delete_medical_record(record_id: str, current_user: dict = Depends(get_current_user)):
    if record_id not in medical_records_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="医疗记录不存在")
    del medical_records_db[record_id]
    return {"message": "医疗记录删除成功"}


@router.delete("/batch")
async def batch_delete_records(record_ids: List[str], current_user: dict = Depends(get_current_user)):
    deleted = 0
    for rid in record_ids:
        if rid in medical_records_db:
            del medical_records_db[rid]
            deleted += 1
    return {"message": f"成功删除 {deleted} 条记录"}


@router.post("/export")
async def export_records(record_ids: List[str], current_user: dict = Depends(get_current_user)):
    export_id = f"export-{uuid.uuid4().hex[:8]}"
    download_url = f"/downloads/{export_id}.xlsx"
    return {"download_url": download_url}


@router.get("/statistics")
async def get_medical_records_statistics(current_user: dict = Depends(get_current_user)):
    records = list(medical_records_db.values())
    total_records = len(records)
    pending_records = len([r for r in records if r.get("status") == "pending"])
    completed_records = len([r for r in records if r.get("status") == "completed"])
    analyzing_records = len([r for r in records if r.get("status") == "analyzing"])

    department_stats = {}
    for r in records:
        dept = r.get("department")
        department_stats[dept] = department_stats.get(dept, 0) + 1

    type_stats = {}
    for r in records:
        rt = r.get("record_type")
        type_stats[rt] = type_stats.get(rt, 0) + 1

    from datetime import datetime as dt
    today_prefix = dt.utcnow().strftime("%Y-%m-%d")
    recent = {
        "today": len([r for r in records if str(r.get("created_at", "")).startswith(today_prefix)]),
        "this_week": len(records),
        "this_month": len(records),
    }
    return {
        "total_records": total_records,
        "pending_records": pending_records,
        "completed_records": completed_records,
        "analyzing_records": analyzing_records,
        "department_statistics": department_stats,
        "type_statistics": type_stats,
        "recent_activity": recent,
    }


@router.post("/upload")
async def upload_record_file(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件名不能为空")
    file_url = f"/uploads/{file.filename}"
    return {"file_url": file_url, "file_name": file.filename}


@router.post("/{record_id}/duplicate", response_model=MedicalRecordResponse)
async def duplicate_record(record_id: str, current_user: dict = Depends(get_current_user)):
    original = medical_records_db.get(record_id)
    if not original:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="医疗记录不存在")
    new_id = f"record-{uuid.uuid4().hex[:8]}"
    new_record = {**original}
    new_record.update({
        "id": new_id,
        "patient_name": f"{original['patient_name']}_副本",
        "status": "pending",
        "created_at": datetime.utcnow().isoformat() + "Z",
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "created_by": current_user["id"],
    })
    medical_records_db[new_id] = new_record
    return MedicalRecordResponse(**new_record)
