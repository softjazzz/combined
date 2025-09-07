#!/usr/bin/env python3
"""
医疗质控系统完整API服务 - 集成版
包含原有的28个API接口 + 新的层级化医疗文书分类功能
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
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from jose import JWTError, jwt
from dotenv import load_dotenv
import httpx
import traceback

# Supabase 客户端
from supabase import create_client, Client

# 导入增强版分类API
from enhanced_classification_api import router as classification_router

# 加载环境变量
load_dotenv('.env')
load_dotenv('../.env')

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# JWT配置
SECRET_KEY = os.getenv("JWT_SECRET", "your-secret-key-here")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# 密码加密
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

# Supabase 配置
SUPABASE_URL = os.getenv('SUPABASE_URL') or os.getenv('VITE_SUPABASE_URL')
SUPABASE_ANON_KEY = os.getenv('SUPABASE_ANON_KEY') or os.getenv('VITE_SUPABASE_ANON_KEY')

logger.info(f"SUPABASE_URL: {SUPABASE_URL}")
logger.info(f"SUPABASE_ANON_KEY: {'***' + SUPABASE_ANON_KEY[-10:] if SUPABASE_ANON_KEY else 'None'}")

# 初始化Supabase客户端
supabase: Optional[Client] = None
if SUPABASE_URL and SUPABASE_ANON_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        logger.info(f"Supabase 客户端初始化成功: {SUPABASE_URL}")
    except Exception as e:
        logger.warning(f"Supabase 客户端初始化失败，将使用内存存储: {e}")
        supabase = None
else:
    logger.warning("Supabase 配置缺失，将使用内存存储")

# 创建FastAPI应用
app = FastAPI(
    title="医疗质控系统API - 完整集成版",
    description="包含用户认证、医疗记录管理、质控分析和层级化文书分类的完整API服务",
    version="2.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://124.220.6.136:3000",
        "http://124.220.6.136:5173",
        "http://124.220.6.136"
    ],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|124\.220\.6\.136)(:\\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册增强版分类路由
app.include_router(classification_router)

# ==================== 数据模型 ====================

# LLM 代理请求模型
class LLMProxyRequest(BaseModel):
    requestBody: Dict[str, Any]
    apiConfig: Dict[str, Any]

# 用户相关模型
class UserBase(BaseModel):
    email: EmailStr
    display_name: str
    department: str
    phone: Optional[str] = None
    bio: Optional[str] = None

class UserCreate(UserBase):
    password: str
    role: Optional[str] = "doctor"

class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    department: Optional[str] = None
    phone: Optional[str] = None
    bio: Optional[str] = None

class UserResponse(UserBase):
    id: str
    roles: List[str]
    avatar: Optional[str] = None
    created_at: str
    last_login: Optional[str] = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    role: Optional[str] = None

class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = ACCESS_TOKEN_EXPIRE_MINUTES * 60

# 医疗记录相关模型
class MedicalRecordBase(BaseModel):
    patient_name: str
    patient_age: int
    patient_gender: str
    department: str
    admission_date: str
    record_type: str
    content: str

class MedicalRecordCreate(MedicalRecordBase):
    pass

class MedicalRecordUpdate(BaseModel):
    patient_name: Optional[str] = None
    patient_age: Optional[int] = None
    patient_gender: Optional[str] = None
    department: Optional[str] = None
    admission_date: Optional[str] = None
    record_type: Optional[str] = None
    content: Optional[str] = None

class MedicalRecordResponse(MedicalRecordBase):
    id: str
    status: str
    created_at: str
    updated_at: str
    created_by: str
    file_url: Optional[str] = None

# LLM解析结果保存模型
class LLMParseResultSave(BaseModel):
    record_number: Optional[str] = None
    patient_name: Optional[str] = None
    patient_age: Optional[int] = None
    patient_gender: Optional[str] = None
    department: Optional[str] = None
    primary_diagnosis: Optional[str] = None
    secondary_diagnosis: Optional[List[str]] = None
    major_surgery: Optional[str] = None
    documents: Optional[List[dict]] = None
    confidence: Optional[int] = None
    content: Optional[str] = None
    method: Optional[str] = None
    parse_metadata: Optional[dict] = None

# 质控相关模型
class QCIssue(BaseModel):
    id: str
    rule_name: str
    description: str
    severity: str
    category: str
    location: str
    suggestion: str

class QCSuggestion(BaseModel):
    id: str
    category: str
    title: str
    description: str
    priority: str

class QCRuleResult(BaseModel):
    rule_id: str
    rule_name: str
    passed: bool
    score: int
    details: str

class QCResult(BaseModel):
    id: str
    record_id: str
    overall_score: int
    overall_grade: str
    analysis_date: str
    issues: List[QCIssue]
    suggestions: List[QCSuggestion]
    rule_results: List[QCRuleResult]

class QCRule(BaseModel):
    id: str
    rule_code: str
    name: str
    description: str
    category: str
    severity: str
    weight: int
    is_active: bool
    conditions: Optional[str] = None
    created_at: str

# ==================== 辅助函数 ====================

def verify_password(plain_password, hashed_password):
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    """获取密码哈希"""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """创建访问令牌"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """获取当前用户"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    # 这里应该从数据库获取用户信息
    # 简化处理，返回模拟用户
    user = {
        "id": "user-123",
        "email": email,
        "display_name": "测试用户",
        "department": "内科",
        "roles": ["doctor"]
    }
    return user

# ==================== 内存存储 (用于演示) ====================

# 用户数据存储
users_db = {}

# 医疗记录数据存储
medical_records_db = {}

# 质控结果存储
qc_results_db = {}

# 质控规则存储
qc_rules_db = {}

def generate_sample_users():
    """生成示例用户数据"""
    sample_users = [
        {
            "id": "user-001",
            "email": "doctor@example.com",
            "display_name": "张医生",
            "department": "内科",
            "roles": ["doctor"],
            "password_hash": get_password_hash("123456"),
            "avatar": "",
            "phone": "13800138000",
            "bio": "内科主治医师",
            "created_at": "2024-01-01T00:00:00Z",
            "last_login": None
        },
        {
            "id": "user-002", 
            "email": "admin@example.com",
            "display_name": "管理员",
            "department": "质控科",
            "roles": ["admin"],
            "password_hash": get_password_hash("admin123"),
            "avatar": "",
            "phone": "13900139000",
            "bio": "系统管理员",
            "created_at": "2024-01-01T00:00:00Z",
            "last_login": None
        }
    ]
    
    for user in sample_users:
        users_db[user["email"]] = user

def generate_sample_medical_records():
    """生成示例医疗记录数据"""
    sample_records = [
        {
            "id": "record-001",
            "patient_name": "张三",
            "patient_age": 45,
            "patient_gender": "男",
            "department": "内科",
            "admission_date": "2024-01-15",
            "record_type": "inpatient",
            "content": "患者张三，男，45岁，因胸痛3天入院...",
            "status": "completed",
            "created_at": "2024-01-15T08:00:00Z",
            "updated_at": "2024-01-15T08:00:00Z",
            "created_by": "user-001",
            "file_url": None
        }
    ]
    
    for record in sample_records:
        medical_records_db[record["id"]] = record

# 初始化示例数据
generate_sample_users()
generate_sample_medical_records()

# ==================== API端点 ====================

@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "医疗质控系统API - 完整集成版",
        "version": "2.1.0",
        "features": [
            "用户认证系统 (9个接口)",
            "医疗记录管理 (10个接口)", 
            "质控分析系统 (9个接口)",
            "层级化文书分类 (6个接口)",
            "LLM集成功能"
        ],
        "docs": "/docs",
        "health": "/api/health",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/api/health")
async def health_check():
    """健康检查"""
    try:
        # 测试 Supabase 连接
        if supabase:
            response = supabase.table('document_categories_test').select('count').limit(1).execute()
            supabase_status = "connected"
        else:
            supabase_status = "not_configured"
    except Exception as e:
        supabase_status = f"error: {str(e)}"

    return {
        "status": "healthy",
        "service": "medical_qc_api_complete",
        "version": "2.1.0",
        "timestamp": datetime.utcnow().isoformat(),
        "supabase_status": supabase_status,
        "features": {
            "authentication": True,
            "medical_records": True,
            "quality_control": True,
            "hierarchical_classification": True,
            "llm_integration": True
        },
        "message": "医疗质控系统完整API运行正常"
    }

# ==================== LLM代理API ====================

@app.post('/api/llm/parse-text')
async def llm_parse_text(req: LLMProxyRequest):
    """LLM文本解析代理"""
    try:
        api_endpoint = (req.apiConfig.get('apiEndpoint') or '').strip()
        api_key = req.apiConfig.get('apiKey') or ''
        request_body = req.requestBody or {}

        if not api_endpoint or not api_key:
            return JSONResponse(status_code=400, content={
                'error': 'Missing apiEndpoint or apiKey',
                'apiEndpoint': bool(api_endpoint),
                'apiKeyProvided': bool(api_key)
            })
        if not (api_endpoint.startswith('http://') or api_endpoint.startswith('https://')):
            return JSONResponse(status_code=400, content={
                'error': 'Invalid apiEndpoint, must start with http:// or https://',
                'apiEndpoint': api_endpoint
            })

        # 兼容性修正：DashScope/OpenAI 兼容端点若仅到 /v1，自动补全 /chat/completions
        endpoint_l = api_endpoint.rstrip('/').lower()
        if ('dashscope.aliyuncs.com' in endpoint_l or 'openai.com' in endpoint_l) and endpoint_l.endswith('/v1'):
            api_endpoint = api_endpoint.rstrip('/') + '/chat/completions'

        headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}

        logger.info(f"[LLM Proxy] Forward to: {api_endpoint} | body keys: {list(request_body.keys())}")

        try:
            timeout = httpx.Timeout(connect=10.0, read=110.0, write=30.0, pool=30.0)
            async with httpx.AsyncClient(timeout=timeout, http2=True) as client:
                r = await client.post(api_endpoint, headers=headers, json=request_body)
                try:
                    content = r.json() if r.text else {}
                except Exception:
                    content = {'text': r.text}

                if r.status_code >= 400:
                    return JSONResponse(status_code=r.status_code, content={
                        'error': 'Upstream error',
                        'upstream_status': r.status_code,
                        'upstream_body': content
                    })

                return JSONResponse(status_code=r.status_code, content=content)
        except httpx.ReadTimeout as e:
            logger.error('[LLM Proxy] ReadTimeout:', repr(e))
            return JSONResponse(status_code=502, content={
                'error': 'HTTPXError',
                'exception': 'ReadTimeout',
                'message': str(e) or 'read timeout',
                'hint': 'LLM处理超时，可尝试缩短输入文本或稍后重试'
            })
        except httpx.HTTPError as e:
            logger.error('[LLM Proxy] HTTPX error:', repr(e))
            return JSONResponse(status_code=502, content={
                'error': 'HTTPXError',
                'exception': e.__class__.__name__,
                'message': str(e)
            })
    except Exception as e:
        logger.error('[LLM Proxy] Exception:', repr(e))
        raise HTTPException(status_code=500, detail=f'LLM代理请求失败: {e.__class__.__name__}: {str(e) or repr(e)}')

@app.post('/api/llm/save-result')
async def save_llm_result(data: LLMParseResultSave):
    """保存LLM解析结果"""
    try:
        if supabase:
            # 保存到Supabase
            record_data = {
                "record_number": data.record_number or f"REC-{uuid.uuid4().hex[:8]}",
                "record_name": f"{data.patient_name or '未识别'}的医疗记录",
                "patient_info": {
                    "name": data.patient_name or "未识别",
                    "age": data.patient_age or 0,
                    "gender": data.patient_gender or "未识别"
                },
                "department": data.department or "未识别",
                "primary_diagnosis": data.primary_diagnosis or "未识别",
                "secondary_diagnosis": data.secondary_diagnosis or [],
                "major_surgery": data.major_surgery or "无",
                "raw_text": data.content or "",
                "ai_extraction_result": {
                    "extraction_time": datetime.utcnow().isoformat(),
                    "model_used": data.method or "unknown",
                    "confidence_scores": {"overall": data.confidence or 0},
                    "metadata": data.parse_metadata or {}
                },
                "ai_confidence_score": data.confidence or 0,
                "documents": data.documents or [],
                "import_method": "llm_parse",
                "status": "draft"
            }

            response = supabase.table('medical_records_test').insert(record_data).execute()

            if response.data:
                return {
                    "success": True,
                    "record_id": response.data[0]["id"],
                    "message": "LLM解析结果保存成功"
                }
            else:
                raise Exception("数据库插入失败")
        else:
            # 保存到内存
            record_id = f"record-{uuid.uuid4().hex[:8]}"
            record = {
                "id": record_id,
                "patient_name": data.patient_name or "未识别",
                "patient_age": data.patient_age or 0,
                "patient_gender": data.patient_gender or "未识别",
                "department": data.department or "未识别",
                "admission_date": datetime.utcnow().strftime("%Y-%m-%d"),
                "record_type": "llm_parsed",
                "content": data.content or "",
                "status": "draft",
                "created_at": datetime.utcnow().isoformat() + "Z",
                "updated_at": datetime.utcnow().isoformat() + "Z",
                "created_by": "llm_system",
                "file_url": None,
                "llm_data": {
                    "primary_diagnosis": data.primary_diagnosis,
                    "secondary_diagnosis": data.secondary_diagnosis,
                    "major_surgery": data.major_surgery,
                    "documents": data.documents,
                    "confidence": data.confidence,
                    "method": data.method,
                    "parse_metadata": data.parse_metadata
                }
            }
            medical_records_db[record_id] = record

            return {
                "success": True,
                "record_id": record_id,
                "message": "LLM解析结果保存成功"
            }

    except Exception as e:
        logger.error(f"保存LLM解析结果失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")

# ==================== 用户认证API (9个接口) ====================

@app.options("/api/auth/login")
async def login_options():
    """处理登录接口的CORS预检请求"""
    return {"message": "OK"}

@app.post("/api/auth/login", response_model=LoginResponse)
async def login(login_data: LoginRequest):
    """用户登录"""
    user = users_db.get(login_data.email)
    if not user or not verify_password(login_data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )

    # 更新最后登录时间
    user["last_login"] = datetime.utcnow().isoformat() + "Z"

    # 创建访问令牌
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["email"]}, expires_delta=access_token_expires
    )

    # 创建刷新令牌（有效期更长）
    refresh_token_expires = timedelta(days=7)
    refresh_token = create_access_token(
        data={"sub": user["email"], "type": "refresh"}, expires_delta=refresh_token_expires
    )

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
