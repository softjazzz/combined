#!/usr/bin/env python3
"""
医疗质控系统 - 集成 Supabase 的后端 API 服务
支持前后端联动，直接操作 Supabase 数据库
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import json
import uuid
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Request, Depends, UploadFile, File, Form, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from dotenv import load_dotenv
import httpx

# Supabase 客户端
from supabase import create_client, Client

# 加载环境变量
load_dotenv('.env')  # 从当前目录加载
load_dotenv('../.env')  # 也尝试从上级目录加载

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Supabase 配置 - 优先使用后端专用的环境变量，回退到前端变量
SUPABASE_URL = os.getenv('SUPABASE_URL') or os.getenv('VITE_SUPABASE_URL')
SUPABASE_ANON_KEY = os.getenv('SUPABASE_ANON_KEY') or os.getenv('VITE_SUPABASE_ANON_KEY')

# 调试信息
logger.info(f"SUPABASE_URL: {SUPABASE_URL}")
logger.info(f"SUPABASE_ANON_KEY: {'***' + SUPABASE_ANON_KEY[-10:] if SUPABASE_ANON_KEY else 'None'}")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    logger.error("Supabase 配置缺失，请检查环境变量")
    logger.error(f"当前工作目录: {os.getcwd()}")
    logger.error(f"环境变量 SUPABASE_URL: {os.getenv('SUPABASE_URL')}")
    logger.error(f"环境变量 VITE_SUPABASE_URL: {os.getenv('VITE_SUPABASE_URL')}")
    sys.exit(1)

# 创建 Supabase 客户端
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
logger.info(f"Supabase 客户端初始化成功: {SUPABASE_URL}")

# 创建FastAPI应用
"""
DEPRECATED: Legacy API with direct Supabase integration. Use `app/main.py`.
"""
app = FastAPI(
    title="医疗质控系统API - Supabase版",
    description="集成Supabase的医疗质控系统后端API服务，支持前后端联动",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 配置CORS - 允许前端访问（必须与前端来源严格匹配，避免通配与凭据冲突）
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://124.220.6.136:3000",
    "http://124.220.6.136:5173",
    "http://124.220.6.136"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|124\.220\.6\.136)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# 如需自定义响应头，可启用以下中间件；默认由 CORSMiddleware 处理更可靠
# @app.middleware("http")
# async def add_cors_headers(request: Request, call_next):
#     response = await call_next(request)
#     origin = request.headers.get("origin")
#     if origin and origin in ALLOWED_ORIGINS:
#         response.headers["Access-Control-Allow-Origin"] = origin
#         response.headers["Vary"] = "Origin"
#     return response

# ==================== 数据模型 ====================

class MedicalRecordCreate(BaseModel):
    record_number: str
    patient_name: str
    patient_id: Optional[str] = None
    patient_age: Optional[int] = None
    patient_gender: Optional[str] = None
    department_id: str  # 需要传入部门UUID
    doctor_id: Optional[str] = None
    admission_date: Optional[str] = None
    discharge_date: Optional[str] = None
    record_type: str = "inpatient"
    diagnosis_primary: Optional[str] = None
    diagnosis_secondary: Optional[List[str]] = None
    content: str
    content_sections: Optional[Dict[str, Any]] = None
    file_attachments: Optional[List[Dict[str, Any]]] = None
    total_pages: Optional[int] = 1
    word_count: Optional[int] = 0
    priority_level: Optional[int] = 1
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    created_by: str  # 需要传入用户UUID

class MedicalRecordRequest(BaseModel):
    """用于更新医疗记录的请求模型"""
    patient_name: Optional[str] = None
    patient_id: Optional[str] = None
    patient_age: Optional[int] = None
    patient_gender: Optional[str] = None
    department_id: Optional[str] = None
    doctor_id: Optional[str] = None
    admission_date: Optional[str] = None
    discharge_date: Optional[str] = None
    record_type: Optional[str] = None
    diagnosis_primary: Optional[str] = None
    diagnosis_secondary: Optional[List[str]] = None
    content: Optional[str] = None
    content_sections: Optional[Dict[str, Any]] = None
    file_attachments: Optional[List[Dict[str, Any]]] = None
    total_pages: Optional[int] = None
    word_count: Optional[int] = None
    status: Optional[str] = None
    qc_score: Optional[float] = None
    qc_grade: Optional[str] = None
    priority_level: Optional[int] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None

class MedicalRecordResponse(BaseModel):
    id: str
    record_number: str
    patient_name: str
    patient_id: Optional[str] = None
    patient_age: Optional[int] = None
    patient_gender: Optional[str] = None
    department_id: str
    doctor_id: Optional[str] = None
    admission_date: Optional[str] = None
    discharge_date: Optional[str] = None
    record_type: str
    diagnosis_primary: Optional[str] = None
    diagnosis_secondary: Optional[List[str]] = None
    content: str
    content_sections: Optional[Dict[str, Any]] = None
    file_attachments: Optional[List[Dict[str, Any]]] = None
    total_pages: Optional[int] = None
    word_count: Optional[int] = None
    status: Optional[str] = None
    qc_score: Optional[float] = None
    qc_grade: Optional[str] = None
    priority_level: Optional[int] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    created_by: str
    created_at: str
    updated_at: str

class ParseResult(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    tokensUsed: int = 0

class SmartImportRequest(BaseModel):
    """智能导入专用的简化请求模型"""
    patient_name: str
    content: str
    file_info: Optional[Dict[str, Any]] = None
    parse_result: Optional[Dict[str, Any]] = None

# ==================== API端点 ====================

# -------- 医疗文书 CRUD（简化版） --------
class MedicalDocument(BaseModel):
    id: Optional[str] = None
    record_id: str
    document_type: str
    title: str
    content: str
    summary: Optional[str] = None
    ai_classified: Optional[bool] = True
    ai_confidence_score: Optional[float] = 0.0
    ai_extraction_metadata: Optional[Dict[str, Any]] = None
    document_metadata: Optional[Dict[str, Any]] = None
    position: Optional[Dict[str, Any]] = None
    sort_order: Optional[int] = 0
    status: Optional[str] = 'active'

# -------- LLM 代理（后端转发） --------
class LLMProxyRequest(BaseModel):
    requestBody: Dict[str, Any]
    apiConfig: Dict[str, Any]

@app.post('/api/llm/parse-text')
async def llm_parse_text(req: LLMProxyRequest):
    try:
        api_endpoint = req.apiConfig.get('apiEndpoint')
        api_key = req.apiConfig.get('apiKey')
        headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(api_endpoint, headers=headers, json=req.requestBody)
            # 直接透传第三方响应内容
            return JSONResponse(status_code=r.status_code, content=r.json() if r.text else {})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'LLM代理请求失败: {str(e)}')

@app.post('/api/medical-documents/batch')
async def create_medical_documents_batch(items: List[MedicalDocument]):
    try:
        payload = [item.dict(exclude_none=True) for item in items]
        resp = supabase.table('medical_documents').insert(payload).execute()
        return { 'data': resp.data, 'count': len(resp.data or []) }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'创建医疗文书失败: {str(e)}')

@app.post('/api/medical-documents')
async def create_medical_document(item: MedicalDocument):
    return await create_medical_documents_batch([item])

@app.get('/api/medical-documents')
async def list_medical_documents(record_id: Optional[str] = None):
    try:
        q = supabase.table('medical_documents').select('*')
        if record_id:
            q = q.eq('record_id', record_id)
        resp = q.order('sort_order').execute()
        return { 'data': resp.data }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'查询医疗文书失败: {str(e)}')

@app.put('/api/medical-documents/{doc_id}')
async def update_medical_document(doc_id: str, item: MedicalDocument):
    try:
        payload = item.dict(exclude_none=True)
        resp = supabase.table('medical_documents').update(payload).eq('id', doc_id).execute()
        return { 'data': resp.data }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'更新医疗文书失败: {str(e)}')

@app.delete('/api/medical-documents/{doc_id}')
async def delete_medical_document(doc_id: str):
    try:
        supabase.table('medical_documents').delete().eq('id', doc_id).execute()
        return { 'success': True }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'删除医疗文书失败: {str(e)}')

@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "医疗质控系统API - Supabase版",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/api/health",
        "supabase_url": SUPABASE_URL,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/api/health")
async def health_check():
    """健康检查"""
    try:
        # 测试 Supabase 连接
        response = supabase.table('medical_records').select('count').limit(1).execute()
        supabase_status = "connected"
    except Exception as e:
        supabase_status = f"error: {str(e)}"

    return {
        "status": "healthy",
        "service": "medical_qc_api_supabase",
        "version": "2.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "supabase_status": supabase_status,
        "message": "医疗质控系统API运行正常"
    }

@app.post("/api/parse-medical-file-public", response_model=ParseResult)
async def parse_medical_file_public(
    file: UploadFile = File(...),
    options: str = Form("{}")
):
    """解析医疗文件（支持PDF等格式）- 公开接口，无需认证"""
    try:
        # 验证文件类型
        allowed_types = [
            'application/pdf',
            'text/plain',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        ]

        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的文件类型: {file.content_type}"
            )

        # 验证文件大小 (10MB限制)
        file_content = await file.read()
        if len(file_content) > 10 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="文件大小不能超过10MB"
            )

        # 解析选项
        try:
            parse_options = json.loads(options)
        except json.JSONDecodeError:
            parse_options = {}

        # 根据文件类型进行解析
        if file.content_type == 'application/pdf' or file.filename.endswith('.pdf'):
            # PDF文件解析
            from services.pdf_parser import parse_pdf_file

            result = parse_pdf_file(file_content, file.filename)

            if not result["success"]:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"PDF解析失败: {result.get('error', '未知错误')}"
                )

            return ParseResult(
                success=True,
                data={
                    "content": result["content"],
                    "method": result["method"],
                    "pages": result["pages"],
                    "medical_info": result["medical_info"],
                    "file_info": {
                        "filename": file.filename,
                        "size": len(file_content),
                        "type": file.content_type
                    }
                },
                tokensUsed=0  # PDF解析不消耗AI tokens
            )

        elif file.content_type == 'text/plain' or file.filename.endswith('.txt'):
            # 文本文件直接读取
            try:
                content = file_content.decode('utf-8')
            except UnicodeDecodeError:
                content = file_content.decode('gbk', errors='ignore')

            return ParseResult(
                success=True,
                data={
                    "content": content,
                    "method": "文本文件直接读取",
                    "pages": 1,
                    "medical_info": {},
                    "file_info": {
                        "filename": file.filename,
                        "size": len(file_content),
                        "type": file.content_type
                    }
                },
                tokensUsed=0
            )

        else:
            # 其他文件类型暂不支持
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"暂不支持解析 {file.content_type} 格式的文件"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文件解析失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文件解析失败: {str(e)}"
        )

@app.post("/api/medical-records", response_model=MedicalRecordResponse)
async def create_medical_record(record: MedicalRecordCreate):
    """创建医疗记录并保存到 Supabase"""
    try:
        # 准备数据 - 匹配实际表结构
        record_data = {
            "record_number": record.record_number,
            "patient_name": record.patient_name,
            "patient_id": record.patient_id,
            "patient_age": record.patient_age,
            "patient_gender": record.patient_gender,
            "department_id": record.department_id,
            "doctor_id": record.doctor_id,
            "admission_date": record.admission_date,
            "discharge_date": record.discharge_date,
            "record_type": record.record_type,
            "diagnosis_primary": record.diagnosis_primary,
            "diagnosis_secondary": record.diagnosis_secondary,
            "content": record.content,
            "content_sections": record.content_sections or {},
            "file_attachments": record.file_attachments or [],
            "total_pages": record.total_pages,
            "word_count": record.word_count,
            "status": "pending",
            "priority_level": record.priority_level,
            "tags": record.tags,
            "metadata": record.metadata or {},
            "created_by": record.created_by
        }

        # 插入到 Supabase
        response = supabase.table('medical_records').insert(record_data).execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="创建医疗记录失败"
            )

        created_record = response.data[0]
        logger.info(f"医疗记录创建成功: {created_record['id']}")

        return MedicalRecordResponse(**created_record)

    except Exception as e:
        logger.error(f"创建医疗记录失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建医疗记录失败: {str(e)}"
        )

@app.get("/api/medical-records")
async def get_medical_records(
    page: int = 1,
    page_size: int = 10,
    status: Optional[str] = None,
    department_id: Optional[str] = None
):
    """获取医疗记录列表"""
    try:
        # 构建查询
        query = supabase.table('medical_records').select('*')

        # 应用筛选
        if status:
            query = query.eq('status', status)
        if department_id:
            query = query.eq('department_id', department_id)

        # 应用分页和排序
        start = (page - 1) * page_size
        end = start + page_size - 1

        response = query.order('created_at', desc=True).range(start, end).execute()

        return {
            "data": response.data,
            "page": page,
            "page_size": page_size,
            "total": len(response.data)  # 简化版本，实际应该查询总数
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取医疗记录失败: {str(e)}")


@app.get("/api/records-test")
async def get_records_test(
    page: int = 1,
    page_size: int = 10,
    search: Optional[str] = None,
    department: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc"
):
    """获取测试表 medical_records_test 的病历列表（供前端低延时使用）"""
    try:
        table = 'medical_records_test'
        # 基础选择
        query = supabase.table(table).select('*')

        # 过滤
        if search:
            # PostgREST or() 语法: 字段.ilike.*%keyword%*
            # Python客户端缺少 or() 组合的便捷API，退化为 record_name 匹配
            # 若需要多字段匹配，可在数据库创建全文索引或视图
            query = query.ilike('record_name', f"%{search}%")
        if department:
            query = query.eq('department', department)
        if date_from:
            query = query.gte('created_at', date_from)
        if date_to:
            query = query.lte('created_at', date_to)

        # 排序
        query = query.order(sort_by, desc=(sort_order != 'asc'))

        # 分页
        start = (page - 1) * page_size
        end = start + page_size - 1
        response = query.range(start, end).execute()

        data = response.data or []
        return {
            "data": data,
            "page": page,
            "page_size": page_size,
            "total": len(data)  # 简化：如需准确总数，可改为单独 count 查询
        }
    except Exception as e:
        logger.error(f"获取测试表记录失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取测试表记录失败: {str(e)}"
        )

@app.get("/api/medical-records/{record_id}", response_model=MedicalRecordResponse)
async def get_medical_record_by_id(record_id: str):
    """根据ID获取单个医疗记录详情"""
    try:
        # 验证 UUID 格式
        try:
            uuid.UUID(record_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无效的记录ID格式"
            )

        # 从 Supabase 查询记录
        response = supabase.table('medical_records').select('*').eq('id', record_id).execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="医疗记录不存在"
            )

        record = response.data[0]
        logger.info(f"获取医疗记录成功: {record_id}")

        return MedicalRecordResponse(**record)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取医疗记录失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取医疗记录失败: {str(e)}"
        )
async def get_medical_record(record_id: str):
    """获取单个医疗记录"""
    try:
        response = supabase.table('medical_records').select('*').eq('id', record_id).single().execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="医疗记录不存在"
            )

        return MedicalRecordResponse(**response.data)

    except Exception as e:
        logger.error(f"获取医疗记录失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取医疗记录失败: {str(e)}"
        )

@app.put("/api/medical-records/{record_id}", response_model=MedicalRecordResponse)
async def update_medical_record(record_id: str, request: MedicalRecordRequest):
    """更新医疗记录"""
    try:
        # 验证 UUID 格式
        try:
            uuid.UUID(record_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无效的记录ID格式"
            )

        # 检查记录是否存在
        existing_response = supabase.table('medical_records').select('id').eq('id', record_id).execute()
        if not existing_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="医疗记录不存在"
            )

        # 准备更新数据
        update_data = request.dict(exclude_unset=True)
        update_data['updated_at'] = datetime.utcnow().isoformat()

        # 更新记录
        response = supabase.table('medical_records').update(update_data).eq('id', record_id).execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="更新医疗记录失败"
            )

        updated_record = response.data[0]
        logger.info(f"更新医疗记录成功: {record_id}")

        return MedicalRecordResponse(**updated_record)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新医疗记录失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新医疗记录失败: {str(e)}"
        )

@app.delete("/api/medical-records/{record_id}")
async def delete_medical_record(record_id: str):
    """删除医疗记录"""
    try:
        # 验证 UUID 格式
        try:
            uuid.UUID(record_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无效的记录ID格式"
            )

        # 检查记录是否存在
        existing_response = supabase.table('medical_records').select('id').eq('id', record_id).execute()
        if not existing_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="医疗记录不存在"
            )

        # 删除记录
        response = supabase.table('medical_records').delete().eq('id', record_id).execute()

        logger.info(f"删除医疗记录成功: {record_id}")

        return {
            "success": True,
            "message": "医疗记录删除成功",
            "deleted_id": record_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除医疗记录失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除医疗记录失败: {str(e)}"
        )

@app.post("/api/smart-import", response_model=MedicalRecordResponse)
async def smart_import_medical_record(request: SmartImportRequest):
    """智能导入医疗记录 - 简化版本，用于前端智能导入功能"""
    try:
        # 生成记录编号
        record_number = f"SMART_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

        # 使用测试部门ID和用户ID
        # 实际应用中应该从认证信息和部门表获取真实ID
        default_department_id = "11111111-1111-1111-1111-111111111111"  # 测试部门ID
        default_user_id = "22222222-2222-2222-2222-222222222222"  # 测试用户ID

        # 从解析结果中提取医疗信息
        medical_info = request.parse_result.get('medical_info', {}) if request.parse_result else {}

        # 准备数据
        record_data = {
            "record_number": record_number,
            "patient_name": request.patient_name,
            "patient_id": medical_info.get('patient_id'),
            "patient_age": medical_info.get('patient_age'),
            "patient_gender": medical_info.get('patient_gender'),
            "department_id": default_department_id,
            "doctor_id": None,
            "admission_date": None,
            "discharge_date": None,
            "record_type": "inpatient",
            "diagnosis_primary": medical_info.get('diagnosis', [None])[0] if medical_info.get('diagnosis') else None,
            "diagnosis_secondary": medical_info.get('diagnosis', [])[1:] if medical_info.get('diagnosis') and len(medical_info.get('diagnosis', [])) > 1 else None,
            "content": request.content,
            "content_sections": {},
            "file_attachments": [request.file_info] if request.file_info else [],
            "total_pages": request.file_info.get('pages', 1) if request.file_info else 1,
            "word_count": len(request.content),
            "status": "pending",
            "priority_level": 1,
            "tags": ["智能导入"],
            "metadata": {
                "import_method": "smart_import",
                "parse_result": request.parse_result,
                "import_time": datetime.utcnow().isoformat()
            },
            "created_by": default_user_id
        }

        # 插入到 Supabase
        response = supabase.table('medical_records').insert(record_data).execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="智能导入医疗记录失败"
            )

        created_record = response.data[0]
        logger.info(f"智能导入医疗记录成功: {created_record['id']}")

        return MedicalRecordResponse(**created_record)

    except Exception as e:
        logger.error(f"智能导入医疗记录失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"智能导入医疗记录失败: {str(e)}"
        )

@app.get("/api/debug/tables")
async def debug_tables():
    """调试：查看数据库中的表"""
    try:
        # 查询所有表
        tables_query = """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        ORDER BY table_name;
        """

        # 这里需要使用原始SQL查询，但supabase-py客户端不直接支持
        # 作为替代，我们返回一些有用的调试信息

        return {
            "message": "请在Supabase SQL Editor中运行以下查询来获取表信息",
            "queries": [
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';",
                "SELECT id, name FROM departments LIMIT 5;",
                "SELECT id FROM auth.users LIMIT 5;",
                "SELECT * FROM medical_records LIMIT 1;"
            ]
        }
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/debug/create-test-data")
async def create_test_data():
    """创建测试数据：部门和用户"""
    try:
        results = []

        # 1. 创建测试部门
        try:
            dept_data = {
                "id": "11111111-1111-1111-1111-111111111111",
                "name": "测试部门",
                "code": "TEST_DEPT",
                "description": "用于API测试的部门",
                "category": "clinical"
            }

            # 先检查是否已存在
            existing_dept = supabase.table('departments').select('id').eq('id', dept_data['id']).execute()

            if not existing_dept.data:
                dept_response = supabase.table('departments').insert(dept_data).execute()
                results.append({"type": "department", "status": "created", "data": dept_response.data})
            else:
                results.append({"type": "department", "status": "already_exists", "id": dept_data['id']})

        except Exception as e:
            results.append({"type": "department", "status": "error", "error": str(e)})

        # 2. 检查是否有 user_profiles 表，如果有则创建测试用户
        try:
            # 尝试查询 user_profiles 表
            users_check = supabase.table('user_profiles').select('id').limit(1).execute()

            # 如果 user_profiles 表存在，创建测试用户
            user_data = {
                "id": "22222222-2222-2222-2222-222222222222",
                "username": "testuser",
                "full_name": "测试用户",
                "email": "test@example.com",
                "role_type": "doctor",
                "department_id": "11111111-1111-1111-1111-111111111111"  # 关联到测试部门
            }

            existing_user = supabase.table('user_profiles').select('id').eq('id', user_data['id']).execute()

            if not existing_user.data:
                user_response = supabase.table('user_profiles').insert(user_data).execute()
                results.append({"type": "user", "status": "created", "data": user_response.data})
            else:
                results.append({"type": "user", "status": "already_exists", "id": user_data['id']})

        except Exception as e:
            # user_profiles 表可能不存在或字段不匹配
            results.append({"type": "user", "status": "table_not_found_or_error", "error": str(e)})

        return {
            "message": "测试数据创建完成",
            "results": results,
            "next_step": "现在可以测试智能导入API了"
        }

    except Exception as e:
        return {"error": f"创建测试数据失败: {str(e)}"}

@app.get("/api/debug/llm-tables")
async def debug_llm_tables():
    """检查 LLM 配置表的状态"""
    try:
        results = {}

        # 检查 llm_api_providers 表
        try:
            providers = supabase.table('llm_api_providers').select('*').execute()
            results['llm_api_providers'] = {
                'exists': True,
                'count': len(providers.data),
                'data': providers.data[:3] if providers.data else []  # 只显示前3条
            }
        except Exception as e:
            results['llm_api_providers'] = {
                'exists': False,
                'error': str(e)
            }

        # 检查 llm_models 表
        try:
            models = supabase.table('llm_models').select('*').execute()
            results['llm_models'] = {
                'exists': True,
                'count': len(models.data),
                'data': models.data[:3] if models.data else []  # 只显示前3条
            }
        except Exception as e:
            results['llm_models'] = {
                'exists': False,
                'error': str(e)
            }

        # 检查 user_llm_configs 表
        try:
            configs = supabase.table('user_llm_configs').select('*').execute()
            results['user_llm_configs'] = {
                'exists': True,
                'count': len(configs.data),
                'data': configs.data[:3] if configs.data else []  # 只显示前3条
            }
        except Exception as e:
            results['user_llm_configs'] = {
                'exists': False,
                'error': str(e)
            }

        return {
            'message': 'LLM 配置表状态检查完成',
            'results': results
        }

    except Exception as e:
        return {"error": f"检查 LLM 表失败: {str(e)}"}

# ==================== LLM 配置 API ====================

@app.get('/api/llm/providers')
async def get_llm_providers():
    """获取所有可用的LLM提供商"""
    try:
        response = supabase.table('llm_api_providers').select('*').eq('is_active', True).order('sort_order').execute()
        return {'data': response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'获取LLM提供商失败: {str(e)}')

@app.get('/api/llm/models')
async def get_llm_models(provider_id: Optional[str] = None):
    """获取LLM模型列表"""
    try:
        query = supabase.table('llm_models').select('*').eq('is_active', True)
        if provider_id:
            query = query.eq('provider_id', provider_id)
        response = query.order('sort_order').execute()
        return {'data': response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'获取LLM模型失败: {str(e)}')

@app.get('/api/llm/configs')
async def get_user_llm_configs(user_id: Optional[str] = None):
    """获取用户的LLM配置列表"""
    try:
        query = supabase.table('user_llm_configs').select('''
            *,
            provider:llm_api_providers(*),
            model:llm_models(*)
        ''').eq('is_active', True)

        if user_id:
            query = query.eq('user_id', user_id)
        else:
            query = query.is_('user_id', None)

        response = query.order('created_at', {'ascending': False}).execute()
        return {'data': response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'获取用户LLM配置失败: {str(e)}')

@app.get('/api/llm/configs/{config_name}')
async def get_llm_config_by_name(config_name: str, user_id: Optional[str] = None):
    """获取指定名称的LLM配置"""
    try:
        query = supabase.table('user_llm_configs').select('''
            *,
            provider:llm_api_providers(*),
            model:llm_models(*)
        ''').eq('config_name', config_name).eq('is_active', True)

        if user_id:
            query = query.eq('user_id', user_id)
        else:
            query = query.is_('user_id', None)

        response = query.order('updated_at', {'ascending': False}).order('created_at', {'ascending': False}).limit(1).execute()

        if response.data:
            return {'data': response.data[0]}
        else:
            return {'data': None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'获取LLM配置失败: {str(e)}')

if __name__ == "__main__":
    # 启动服务器
    uvicorn.run(
        "main_api_with_supabase:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )
