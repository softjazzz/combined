import json
import logging
from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException, status, Depends

from ..core.response import success_response, error_response, get_trace_id, ErrorCode, StatusCode
from ..core.rate_limit import enforce_rate_limit
from ..core.security import get_current_user
from ..core.upload_security import validate_uploaded_file

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/v1", tags=["tools"])


def _import_pdf_parser():
    try:
        from backend.services.pdf_parser import parse_pdf_file  # type: ignore
        return parse_pdf_file
    except Exception:
        try:
            from services.pdf_parser import parse_pdf_file  # type: ignore
            return parse_pdf_file
        except Exception as e:
            raise HTTPException(status_code=StatusCode.INTERNAL_SERVER_ERROR, detail=f"PDF解析服务不可用: {e}")


ALLOWED_TYPES = [
    'application/pdf',
    'text/plain',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
]
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".doc", ".docx"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


async def _parse_text_file(file: UploadFile, file_content: bytes):
    try:
        text = file_content.decode('utf-8')
    except UnicodeDecodeError:
        try:
            text = file_content.decode('gbk')
        except UnicodeDecodeError:
            raise HTTPException(status_code=StatusCode.BAD_REQUEST, detail="文本文件编码不支持，请使用UTF-8或GBK编码")

    # 简单的医疗信息提取
    import re
    medical_info = {}
    name_patterns = [r"患者姓名[：:]\s*([^\s\n]+)", r"姓名[：:]\s*([^\s\n]+)", r"病人[：:]\s*([^\s\n]+)"]
    for p in name_patterns:
        m = re.search(p, text)
        if m:
            medical_info["patientName"] = m.group(1)
            break
    dept_patterns = [r"科室[：:]\s*([^\s\n]+)", r"所在科室[：:]\s*([^\s\n]+)"]
    for p in dept_patterns:
        m = re.search(p, text)
        if m:
            medical_info["department"] = m.group(1)
            break
    diag_patterns = [r"诊断[：:]\s*([^\n]+)", r"主要诊断[：:]\s*([^\n]+)", r"入院诊断[：:]\s*([^\n]+)"]
    for p in diag_patterns:
        m = re.search(p, text)
        if m:
            medical_info["primaryDiagnosis"] = m.group(1).strip()
            break

    return {
        "success": True,
        "data": {
            "content": text,
            "method": "文本解析",
            "medical_info": medical_info,
            **medical_info,
        },
    }


async def _parse_file_common(request: Request, file: UploadFile, options: str):
    content = await file.read()
    validate_uploaded_file(
        request=request,
        file=file,
        content=content,
        allowed_extensions=ALLOWED_EXTENSIONS,
        allowed_content_types=ALLOWED_TYPES,
        max_bytes=MAX_UPLOAD_BYTES,
    )
    try:
        parse_options = json.loads(options)
    except json.JSONDecodeError:
        parse_options = {}

    if file.content_type == 'application/pdf' or (file.filename and file.filename.endswith('.pdf')):
        parse_pdf_file = _import_pdf_parser()
        result = parse_pdf_file(content, file.filename)
        if not result.get("success"):
            raise HTTPException(status_code=StatusCode.INTERNAL_SERVER_ERROR, detail=f"PDF解析失败: {result.get('error', '未知错误')}")
        return {
            "success": True,
            "data": {
                "content": result.get("content"),
                "method": result.get("method"),
                "pages": result.get("pages"),
                "medical_info": result.get("medical_info"),
                "file_info": {
                    "filename": file.filename,
                    "size": len(content),
                    "type": file.content_type,
                },
            },
            "tokensUsed": 0,
        }
    elif file.content_type == 'text/plain' or (file.filename and file.filename.endswith('.txt')):
        return await _parse_text_file(file, content)
    else:
        raise HTTPException(status_code=StatusCode.BAD_REQUEST, detail=f"暂不支持解析 {file.content_type} 格式的文件")


@router.post("/parse-medical-file-public")
async def parse_medical_file_public(    request: Request,file: UploadFile = File(...), options: str = Form("{}")):
    enforce_rate_limit(request, bucket="tools_parse_medical_file_public", max_requests=20, window_seconds=60)
    return await _parse_file_common(request, file, options)


@router.post("/parse-medical-file")
async def parse_medical_file(    request: Request,file: UploadFile = File(...), options: str = Form("{}"), current_user: dict = Depends(get_current_user)):
    enforce_rate_limit(request, bucket="tools_parse_medical_file", max_requests=30, window_seconds=60)
    return await _parse_file_common(request, file, options)


@router.post("/parse-medical-text")
async def parse_medical_text(    request: Request,text: str = Form(...)):
    enforce_rate_limit(request, bucket="tools_parse_medical_text", max_requests=60, window_seconds=60)
    # Reuse text parsing logic
    from starlette.datastructures import UploadFile as _UF  # type: ignore
    fake_file = type("F", (), {"filename": "input.txt", "content_type": "text/plain"})()
    return await _parse_text_file(fake_file, text.encode("utf-8", errors="ignore"))
