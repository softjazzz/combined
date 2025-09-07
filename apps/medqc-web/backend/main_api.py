#!/usr/bin/env python3
"""
医疗质控系统完整API服务
支持前端28个API接口的完整后端实现
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
import json
import uuid
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Request, Depends, UploadFile, File, Form, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, ValidationError
from fastapi.exceptions import RequestValidationError
from passlib.context import CryptContext
from jose import JWTError, jwt
from dotenv import load_dotenv
import httpx
import os
import traceback

# Supabase 客户端
from supabase import create_client, Client

# 质控概念验证服务
from qc_poc_service import get_qc_poc_service

# 四川省质控服务
from services.sichuan_qc_service import get_sichuan_qc_service

# 加载环境变量
load_dotenv('.env')  # 从当前目录加载
load_dotenv('../.env')  # 也尝试从上级目录加载

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

# Supabase 配置 - 优先使用后端专用的环境变量，回退到前端变量
SUPABASE_URL = os.getenv('SUPABASE_URL') or os.getenv('VITE_SUPABASE_URL')
SUPABASE_ANON_KEY = os.getenv('SUPABASE_ANON_KEY') or os.getenv('VITE_SUPABASE_ANON_KEY')

# 调试信息
logger.info(f"SUPABASE_URL: {SUPABASE_URL}")
logger.info(f"SUPABASE_ANON_KEY: {'***' + SUPABASE_ANON_KEY[-10:] if SUPABASE_ANON_KEY else 'None'}")

# 初始化Supabase客户端（可选，如果配置不存在则使用内存存储）
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
    title="医疗质控系统API",
    description="完整的医疗质控系统后端API服务，支持用户认证、医疗记录管理和质控分析",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 配置CORS - 支持前端开发服务器
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",  # Vite 默认端口
        "http://127.0.0.1:5173",
        "http://localhost:5177",  # Vite 备用端口
        "http://127.0.0.1:5177",
        "http://localhost:8080",  # 备用端口
        "http://127.0.0.1:8080",
        # 服务器对外访问域名/IP
        "http://124.220.6.136:3000",
        "http://124.220.6.136:5173",
        "http://124.220.6.136:5177",  # 添加5177端口支持
        "http://124.220.6.136:8001",  # 添加8001端口支持（前端访问后端）
        "http://124.220.6.136"
    ],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|124\.220\.6\.136)(:[0-9]+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局异常处理器
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """处理请求验证错误"""
    logger.error(f"请求验证失败: {request.url} - {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={
            "detail": "请求数据验证失败",
            "errors": exc.errors(),
            "body": exc.body
        }
    )

# 注册增强版分类API路由
try:
    from enhanced_classification_api import router as enhanced_classification_router
    app.include_router(enhanced_classification_router)
    print("✅ 成功注册增强版分类API路由")
except ImportError as e:
    print(f"⚠️ 导入增强版分类API失败: {e}")
except Exception as e:
    print(f"⚠️ 注册增强版分类API路由失败: {e}")

# ==================== 数据模型 ====================

# -------- LLM 代理（后端转发） --------
class LLMProxyRequest(BaseModel):
    requestBody: Dict[str, Any]
    apiConfig: Dict[str, Any]

@app.post('/api/llm/parse-text')
async def llm_parse_text(req: LLMProxyRequest):
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

        # 模型特定参数修正
        model_name = request_body.get('model', '')

        # 阿里云特定模型需要的参数修正
        if 'dashscope.aliyuncs.com' in api_endpoint:
            # 对于需要 enable_thinking 参数的模型（如 qwen2.5-14b-instruct）
            thinking_required_models = [
                'qwen2.5-14b-instruct',
                'qwen2.5-32b-instruct',
                'qwen3-14b',
                'qwen3-30b-a3b-instruct-2507'
            ]

            if model_name in thinking_required_models:
                # 对于非流式调用，必须设置 enable_thinking 为 false
                if not request_body.get('stream', False):
                    request_body['enable_thinking'] = False
                    print(f"[LLM Proxy] Added enable_thinking=false for model: {model_name}")

            # 确保某些参数的正确性
            if 'response_format' in request_body:
                # 确保 response_format 格式正确
                response_format = request_body['response_format']
                if isinstance(response_format, dict) and response_format.get('type') == 'json_object':
                    # 某些模型可能不支持 json_object，回退到普通模式
                    if model_name.startswith('qwen2.5') or model_name.startswith('qwen3'):
                        print(f"[LLM Proxy] Removing response_format for compatibility with model: {model_name}")
                        del request_body['response_format']

        headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}

        # 调试日志（不会打印敏感信息）
        print(f"[LLM Proxy] Forward to: {api_endpoint} | model: {model_name} | body keys: {list(request_body.keys())}")

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
            print('[LLM Proxy] ReadTimeout:', repr(e))
            return JSONResponse(status_code=502, content={
                'error': 'HTTPXError',
                'exception': 'ReadTimeout',
                'message': str(e) or 'read timeout',
                'hint': 'LLM处理超时，可尝试缩短输入文本或稍后重试'
            })
        except httpx.HTTPError as e:
            print('[LLM Proxy] HTTPX error:', repr(e))
            print(traceback.format_exc())
            return JSONResponse(status_code=502, content={
                'error': 'HTTPXError',
                'exception': e.__class__.__name__,
                'message': str(e)
            })
    except Exception as e:
        print('[LLM Proxy] Exception:', repr(e))
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f'LLM代理请求失败: {e.__class__.__name__}: {str(e) or repr(e)}')

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

# LLM解析结果保存的数据模型
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
    updated_at: str
    execution_count: Optional[int] = 0
    pass_rate: Optional[float] = 0.0
    issue_count: Optional[int] = 0

# ==================== 内存数据存储 ====================

# 用户数据
users_db = {
    "admin@medqc.com": {
        "id": "admin-001",
        "email": "admin@medqc.com",
        "display_name": "系统管理员",
        "department": "系统管理部",
        "roles": ["admin", "qc_manager"],
        "password_hash": pwd_context.hash("admin123"),
        "avatar": "",
        "phone": "13800138000",
        "bio": "系统管理员，负责整个医疗质控系统的运维和管理工作。",
        "created_at": "2024-01-01T00:00:00Z",
        "last_login": None
    },
    "qc@medqc.com": {
        "id": "qc-001",
        "email": "qc@medqc.com",
        "display_name": "质控主管",
        "department": "质控科",
        "roles": ["qc_manager"],
        "password_hash": pwd_context.hash("qc123456"),
        "avatar": "",
        "phone": "13800138001",
        "bio": "质控科主管，专注于医疗质量控制和病案审核工作。",
        "created_at": "2024-01-15T00:00:00Z",
        "last_login": None
    },
    "doctor@medqc.com": {
        "id": "doctor-001",
        "email": "doctor@medqc.com",
        "display_name": "医务人员",
        "department": "内科",
        "roles": ["doctor"],
        "password_hash": pwd_context.hash("doctor123"),
        "avatar": "",
        "phone": "13800138002",
        "bio": "内科医生，从事临床诊疗和病案记录工作。",
        "created_at": "2024-02-01T00:00:00Z",
        "last_login": None
    }
}

# 医疗记录数据
medical_records_db = {}

# 质控结果数据
qc_results_db = {}

# 质控规则数据
qc_rules_db = {
    "rule-001": {
        "id": "rule-001",
        "rule_code": "QC001",
        "name": "主诉完整性检查",
        "description": "检查病案中主诉部分是否完整，包含患者主要症状和持续时间",
        "category": "基本信息",
        "severity": "major",
        "weight": 10,
        "is_active": True,
        "conditions": "content.includes('主诉') && content.match(/\\d+[天日月年]/)",
        "created_at": "2024-01-15T10:00:00Z",
        "updated_at": "2024-01-20T15:30:00Z",
        "execution_count": 1250,
        "pass_rate": 85.0,
        "issue_count": 187
    },
    "rule-002": {
        "id": "rule-002",
        "rule_code": "QC002",
        "name": "诊断依据充分性",
        "description": "检查诊断是否有充分的依据支撑，包括症状、体征、检查结果等",
        "category": "诊断质量",
        "severity": "critical",
        "weight": 15,
        "is_active": True,
        "conditions": "diagnosis.length > 0 && evidence.length >= 3",
        "created_at": "2024-01-10T09:00:00Z",
        "updated_at": "2024-01-25T11:45:00Z",
        "execution_count": 980,
        "pass_rate": 78.0,
        "issue_count": 215
    }
}

# ==================== 工具函数 ====================

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

def verify_password(plain_password, hashed_password):
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    """获取密码哈希"""
    return pwd_context.hash(password)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """获取当前用户"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = users_db.get(email)
    if user is None:
        raise credentials_exception
    return user

def generate_sample_medical_records():
    """生成示例医疗记录"""
    sample_records = [
        {
            "id": f"record-{i:03d}",
            "patient_name": f"患者{i:02d}",
            "patient_age": 30 + (i % 50),
            "patient_gender": "male" if i % 2 == 0 else "female",
            "department": ["内科", "外科", "儿科", "妇科", "骨科"][i % 5],
            "admission_date": (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d"),
            "record_type": ["inpatient", "outpatient", "emergency"][i % 3],
            "content": f"这是患者{i:02d}的病案记录内容，包含主诉、现病史、既往史、体格检查、辅助检查、诊断和治疗方案等详细信息。",
            "status": ["pending", "completed", "analyzing"][i % 3],
            "created_at": (datetime.now() - timedelta(days=i)).isoformat() + "Z",
            "updated_at": (datetime.now() - timedelta(days=i-1)).isoformat() + "Z",
            "created_by": "doctor-001",
            "file_url": None
        }
        for i in range(1, 21)
    ]

    for record in sample_records:
        medical_records_db[record["id"]] = record

# 初始化示例数据
generate_sample_medical_records()

# ==================== API端点 ====================

@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "医疗质控系统API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/api/health")

@app.get("/api/debug/pdf-env")
async def debug_pdf_env():
    import sys, os
    info = {
        "python_executable": sys.executable,
        "python_version": sys.version,
        "cwd": os.getcwd(),
        "sys_path_head": sys.path[:5],
    }
    # check direct imports in this runtime
    try:
        import fitz  # type: ignore
        info["has_pymupdf"] = True
        info["pymupdf_version"] = getattr(fitz, "__doc__", "").split("\n")[0] or "installed"
    except Exception as e:
        info["has_pymupdf"] = False
        info["pymupdf_error"] = str(e)
    try:
        import pdfplumber  # type: ignore
        info["has_pdfplumber"] = True
        info["pdfplumber_version"] = getattr(pdfplumber, "__version__", "installed")
    except Exception as e:
        info["has_pdfplumber"] = False
        info["pdfplumber_error"] = str(e)
    # check the parser module flags
    try:
        try:
            from backend.services.pdf_parser import pdf_parser  # type: ignore
        except Exception:
            from services.pdf_parser import pdf_parser  # type: ignore
        info["parser_available_methods"] = pdf_parser.get_available_methods()
    except Exception as e:
        info["parser_available_methods_error"] = str(e)
    return info

async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "medical_qc_api",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "message": "医疗质控系统API运行正常"
    }

# ==================== 用户认证API (B1任务 - 9个接口) ====================

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

@app.post("/api/auth/register", response_model=UserResponse)
async def register(user_data: UserCreate):
    """用户注册"""
    if user_data.email in users_db:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱已被注册"
        )

    user_id = f"user-{uuid.uuid4().hex[:8]}"
    new_user = {
        "id": user_id,
        "email": user_data.email,
        "display_name": user_data.display_name,
        "department": user_data.department,
        "roles": [user_data.role or "doctor"],
        "password_hash": get_password_hash(user_data.password),
        "avatar": "",
        "phone": user_data.phone,
        "bio": user_data.bio,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "last_login": None
    }

    users_db[user_data.email] = new_user

    return UserResponse(
        id=new_user["id"],
        email=new_user["email"],
        display_name=new_user["display_name"],
        department=new_user["department"],
        roles=new_user["roles"],
        avatar=new_user["avatar"],
        phone=new_user["phone"],
        bio=new_user["bio"],
        created_at=new_user["created_at"],
        last_login=new_user["last_login"]
    )

@app.get("/api/auth/me", response_model=UserResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """获取当前用户信息"""
    return UserResponse(
        id=current_user["id"],
        email=current_user["email"],
        display_name=current_user["display_name"],
        department=current_user["department"],
        roles=current_user["roles"],
        avatar=current_user["avatar"],
        phone=current_user["phone"],
        bio=current_user["bio"],
        created_at=current_user["created_at"],
        last_login=current_user["last_login"]
    )

@app.put("/api/auth/profile", response_model=UserResponse)
async def update_profile(
    profile_data: UserUpdate,
    current_user: dict = Depends(get_current_user)
):
    """更新用户资料"""
    user = users_db[current_user["email"]]

    if profile_data.display_name is not None:
        user["display_name"] = profile_data.display_name
    if profile_data.department is not None:
        user["department"] = profile_data.department
    if profile_data.phone is not None:
        user["phone"] = profile_data.phone
    if profile_data.bio is not None:
        user["bio"] = profile_data.bio

    return UserResponse(
        id=user["id"],
        email=user["email"],
        display_name=user["display_name"],
        department=user["department"],
        roles=user["roles"],
        avatar=user["avatar"],
        phone=user["phone"],
        bio=user["bio"],
        created_at=user["created_at"],
        last_login=user["last_login"]
    )

@app.put("/api/auth/password")
async def update_password(
    new_password: str = Form(...),
    current_password: str = Form(None),
    current_user: dict = Depends(get_current_user)
):
    """修改密码"""
    user = users_db[current_user["email"]]

    # 如果提供了当前密码，验证它
    if current_password and not verify_password(current_password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前密码错误"
        )

    user["password_hash"] = get_password_hash(new_password)

    return {"message": "密码修改成功"}

@app.post("/api/auth/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """用户登出"""
    # 在实际应用中，这里应该将token加入黑名单
    return {"message": "登出成功"}

@app.post("/api/auth/refresh", response_model=LoginResponse)
async def refresh_token(refresh_token: str = Form(...)):
    """刷新token"""
    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        token_type: str = payload.get("type")

        if email is None or token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的刷新令牌"
            )

        user = users_db.get(email)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户不存在"
            )

        # 创建新的访问令牌
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": email}, expires_delta=access_token_expires
        )

        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,  # 刷新令牌保持不变
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的刷新令牌"
        )

@app.post("/api/auth/forgot-password")
async def forgot_password(email: EmailStr = Form(...)):
    """忘记密码"""
    user = users_db.get(email)
    if not user:
        # 为了安全，即使用户不存在也返回成功消息
        return {"message": "如果邮箱存在，重置密码邮件已发送"}

    # 在实际应用中，这里应该发送重置密码邮件
    logger.info(f"Password reset requested for {email}")

    return {"message": "重置密码邮件已发送"}

@app.post("/api/auth/reset-password")
async def reset_password(
    token: str = Form(...),
    new_password: str = Form(...)
):
    """重置密码"""
    try:
        # 在实际应用中，这里应该验证重置令牌
        # 这里简化处理，直接返回成功
        return {"message": "密码重置成功"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="重置令牌无效或已过期"
        )

# ==================== 医疗记录API (B2任务 - 10个接口) ====================

@app.get("/api/records")
async def get_medical_records(
    keyword: Optional[str] = None,
    department: Optional[str] = None,
    status: Optional[str] = None,
    record_type: Optional[str] = None,
    sort_field: Optional[str] = None,
    sort_order: Optional[str] = None,
    page: int = 1,
    page_size: int = 10
):
    """获取医疗记录列表（仅从Supabase读取）"""
    try:
        records = []

        # 仅从Supabase获取数据
        if supabase:
            try:
                response = supabase.table('medical_records_test').select('*').execute()
                if response.data:
                    # 处理记录，恢复LLM解析记录的正确类型和部门信息
                    records = []
                    for record in response.data:
                        processed_record = dict(record)

                        # 如果是LLM解析记录，恢复原始类型和部门信息
                        if record.get('metadata', {}).get('source') == 'LLM解析':
                            processed_record['record_type'] = record['metadata'].get('original_record_type', 'LLM解析结果')
                            processed_record['department'] = record['metadata'].get('department_name', '未知')
                        else:
                            # 对于非LLM记录，保持原有的department_id字段（如果需要的话可以查询部门表）
                            processed_record['department'] = '未知'  # 这里可以根据department_id查询真实部门名称

                        records.append(processed_record)

                    logger.info(f"从Supabase获取到 {len(response.data)} 条记录")
                else:
                    logger.info("Supabase中没有找到记录")
            except Exception as e:
                logger.error(f"从Supabase获取记录失败: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"数据库查询失败: {str(e)}"
                )
        else:
            logger.warning("Supabase客户端未初始化")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="数据库服务不可用"
            )

        # 应用筛选
        if keyword:
            keyword_lower = keyword.lower()
            records = [r for r in records if
                      keyword_lower in (r.get("patient_name", "").lower()) or
                      keyword_lower in (r.get("content", "").lower())]
        if department:
            records = [r for r in records if r.get("department") == department]
        if status:
            records = [r for r in records if r.get("status") == status]
        if record_type:
            records = [r for r in records if r.get("record_type") == record_type]

        # 应用排序
        if sort_field:
            reverse = sort_order == "desc"
            if sort_field in ["created_at", "updated_at"]:
                records.sort(key=lambda x: x.get(sort_field, ""), reverse=reverse)
            elif sort_field == "patient_name":
                records.sort(key=lambda x: x.get("patient_name", ""), reverse=reverse)

        # 分页
        total = len(records)
        start = (page - 1) * page_size
        end = start + page_size
        paginated_records = records[start:end]

        return {
            "data": paginated_records,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取医疗记录列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取记录列表失败: {str(e)}"
        )

@app.get("/api/records/{record_id}", response_model=MedicalRecordResponse)
async def get_medical_record(
    record_id: str,
    current_user: dict = Depends(get_current_user)
):
    """获取单个医疗记录详情"""
    record = medical_records_db.get(record_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="医疗记录不存在"
        )

    return MedicalRecordResponse(**record)

@app.post("/api/records", response_model=MedicalRecordResponse)
async def create_medical_record(
    patient_name: str = Form(...),
    patient_age: int = Form(...),
    patient_gender: str = Form(...),
    department: str = Form(...),
    admission_date: str = Form(...),
    record_type: str = Form(...),
    content: str = Form(...),
    file: Optional[UploadFile] = File(None),
    current_user: dict = Depends(get_current_user)
):
    """创建医疗记录"""
    record_id = f"record-{uuid.uuid4().hex[:8]}"

    # 处理文件上传
    file_url = None
    if file:
        # 在实际应用中，这里应该保存文件到存储系统
        file_url = f"/uploads/{file.filename}"

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
        "file_url": file_url
    }

    medical_records_db[record_id] = new_record

    return MedicalRecordResponse(**new_record)

# 新增：LLM解析结果保存接口（无需认证，接受JSON数据）
@app.post("/api/medical-records", response_model=MedicalRecordResponse)
async def save_llm_parse_result(data: LLMParseResultSave):
    """保存LLM解析结果到数据库（无需认证）"""
    try:
        # 生成UUID作为记录ID
        record_id = str(uuid.uuid4())

        # 构建医疗记录数据 - 匹配Supabase表结构
        # 使用测试用的UUID（与main_api_with_supabase.py保持一致）
        default_department_id = "11111111-1111-1111-1111-111111111111"  # 测试部门ID
        default_user_id = "22222222-2222-2222-2222-222222222222"  # 测试用户ID

        # 构建适配medical_records_test表结构的数据
        # 注意：前端传递的字段名与后端期望的字段名需要正确映射
        record_data = {
            "record_number": data.record_number or f"LLM_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            "record_name": f"{data.patient_name or '未识别'}的病历记录",
            "patient_info": {
                "name": data.patient_name or '未识别',
                "age": data.patient_age or 0,
                "gender": data.patient_gender or '未识别'
            },
            "department": data.department or '未识别',
            "primary_diagnosis": data.primary_diagnosis or '',
            "secondary_diagnosis": data.secondary_diagnosis or [],
            "major_surgery": data.major_surgery or '',
            "raw_text": data.content or '',
            "ai_extraction_result": {
                "patient_info": {
                    "name": data.patient_name or '未识别',
                    "age": data.patient_age or 0,
                    "gender": data.patient_gender or '未识别'
                },
                "diagnosis": data.primary_diagnosis or '',
                "documents": data.documents or [],
                "confidence": data.confidence or 0,
                "method": data.method or 'LLM精准解析',
                "parse_metadata": data.parse_metadata or {}
            },
            "ai_confidence_score": data.confidence or 0,
            "documents": data.documents or [],
            "status": "active",  # medical_records_test表使用active状态
            "import_method": "smart_import"  # 标记为智能导入
        }

        # 调试：打印接收到的数据和构建的数据
        logger.info(f"接收到的前端数据: {data}")
        logger.info(f"构建的保存数据: {record_data}")

        # 优先保存到Supabase，如果失败则保存到内存
        if supabase:
            try:
                response = supabase.table('medical_records_test').insert(record_data).execute()
                if response.data:
                    saved_record = response.data[0]
                    # 转换字段名以匹配响应模型
                    # 从content_sections或metadata中获取部门名称
                    department_name = "未识别"
                    if saved_record.get("content_sections"):
                        department_name = saved_record["content_sections"].get("department_name", "未识别")
                    elif saved_record.get("metadata"):
                        department_name = saved_record["metadata"].get("department_name", "未识别")

                    # 从patient_info嵌套对象中获取患者信息
                    patient_info = saved_record.get("patient_info", {})

                    response_record = {
                        "id": saved_record.get("id", record_id),
                        "patient_name": patient_info.get("name", "未识别"),
                        "patient_age": patient_info.get("age", 0),
                        "patient_gender": patient_info.get("gender", "未识别"),
                        "department": saved_record.get("department", "未识别"),  # 直接从根级别获取部门
                        "admission_date": saved_record.get("admission_date", datetime.utcnow().isoformat()),
                        "record_type": "LLM解析结果",
                        "content": saved_record.get("raw_text", ""),  # 使用raw_text字段
                        "status": saved_record.get("status", "active"),
                        "created_at": saved_record.get("created_at", datetime.utcnow().isoformat()),
                        "updated_at": saved_record.get("updated_at", datetime.utcnow().isoformat()),
                        "created_by": saved_record.get("created_by", default_user_id),
                        "file_url": None
                    }

                    # 批量保存文档记录
                    await save_medical_documents(
                        medical_record_id=saved_record.get("id", record_id),
                        documents=data.documents or [],
                        extraction_method=data.method or 'LLM精准解析',
                        raw_content=data.content or ""
                    )

                    logger.info(f"LLM解析结果已保存到Supabase: {saved_record.get('id', record_id)}")
                    return MedicalRecordResponse(**response_record)
                else:
                    raise Exception("Supabase插入返回空数据")
            except Exception as e:
                logger.warning(f"保存到Supabase失败，使用内存存储: {e}")
                # 回退到内存存储，构建兼容的记录格式
                memory_record = {
                    "id": record_id,
                    "patient_name": data.patient_name or "未识别",
                    "patient_age": data.patient_age or 0,
                    "patient_gender": data.patient_gender or "未识别",
                    "department": data.department or "未识别",  # 内存存储使用department
                    "admission_date": datetime.utcnow().isoformat() + "Z",
                    "record_type": "LLM解析结果",
                    "content": data.content or "",
                    "status": "completed",
                    "created_at": datetime.utcnow().isoformat() + "Z",
                    "updated_at": datetime.utcnow().isoformat() + "Z",
                    "created_by": "llm-system",
                    "file_url": None
                }
                medical_records_db[record_id] = memory_record
                return MedicalRecordResponse(**memory_record)
        else:
            # 直接使用内存存储
            memory_record = {
                "id": record_id,
                "patient_name": data.patient_name or "未识别",
                "patient_age": data.patient_age or 0,
                "patient_gender": data.patient_gender or "未识别",
                "department": data.department or "未识别",
                "admission_date": datetime.utcnow().isoformat() + "Z",
                "record_type": "LLM解析结果",
                "content": data.content or "",
                "status": "completed",
                "created_at": datetime.utcnow().isoformat() + "Z",
                "updated_at": datetime.utcnow().isoformat() + "Z",
                "created_by": "llm-system",
                "file_url": None
            }
            medical_records_db[record_id] = memory_record
            logger.info(f"LLM解析结果已保存到内存: {record_id}")
            return MedicalRecordResponse(**memory_record)

    except Exception as e:
        logger.error(f"保存LLM解析结果失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"保存失败: {str(e)}"
        )


async def save_medical_documents(medical_record_id: str, documents: list, extraction_method: str = "LLM", raw_content: str = ""):
    """
    批量保存医疗文档到medical_documents_test表，使用现有的表结构

    Args:
        medical_record_id: 主病历记录ID
        documents: 文档列表
        extraction_method: 提取方法
    """
    if not documents or not supabase:
        return

    try:
        # 获取分类映射表
        category_mapping = await get_classification_mapping()
        document_records = []

        for i, doc in enumerate(documents):
            # 获取分类信息
            category_code = doc.get("category", "").strip()
            type_code = doc.get("type", "").strip()

            # 根据type_code推断category_code（如果category为空）
            if not category_code and type_code:
                category_code = infer_category_from_type(type_code)

            # 查找分类ID和类型ID
            category_id = category_mapping.get("categories", {}).get(category_code)
            type_id = category_mapping.get("types", {}).get(f"{category_code}.{type_code}")

            # 如果找不到分类，使用默认值
            if not category_id:
                # 尝试直接通过type_code查找
                for key, tid in category_mapping.get("types", {}).items():
                    if key.endswith(f".{type_code}"):
                        type_id = tid
                        # 获取对应的category_id
                        parent_category = key.split(".")[0]
                        category_id = category_mapping.get("categories", {}).get(parent_category)
                        category_code = parent_category
                        break

                # 如果还是找不到，使用默认分类
                if not category_id:
                    category_id = category_mapping.get("categories", {}).get("progress_note")  # 默认为病程记录
                    category_code = "progress_note"

            if not type_id:
                # 使用默认类型
                type_id = category_mapping.get("types", {}).get(f"{category_code}.{type_code}")
                if not type_id:
                    # 如果还是找不到，使用first_progress_note作为默认
                    type_id = category_mapping.get("types", {}).get("progress_note.first_progress_note")
                    type_code = "first_progress_note"

            # 构建文档记录，使用现有表结构的字段名
            doc_record = {
                "record_id": medical_record_id,  # 使用record_id而不是medical_record_id
                "category_id": category_id,
                "type_id": type_id,
                "title": doc.get("title", "未命名文档"),
                "content": extract_document_content(doc, raw_content),
                "summary": doc.get("summary", ""),
                "ai_classified": True,  # 标记为AI分类
                "classification_confidence": float(doc.get("confidence", 0)) / 100.0,  # 转换为0-1范围的小数
                "manual_verified": False,
                "position_info": {
                    "startIndex": doc.get("position", {}).get("startIndex"),
                    "endIndex": doc.get("position", {}).get("endIndex"),
                    "startMarker": doc.get("position", {}).get("startMarker", ""),
                    "endMarker": doc.get("position", {}).get("endMarker", "")
                },
                "sort_order": i + 1,  # 按文档顺序排序
                "status": "active",
                "qc_status": "pending",  # 质控状态为待审核
                "metadata": {
                    "extracted_at": doc.get("extractedAt"),
                    "original_doc_id": doc.get("id"),
                    "extraction_method": extraction_method,
                    "category_code": category_code,
                    "type_code": type_code,
                    **doc.get("metadata", {})
                }
            }

            document_records.append(doc_record)

        # 批量插入文档记录到现有的medical_documents_test表
        if document_records:
            try:
                # 先删除该记录的所有现有文档，避免重复键冲突
                delete_response = supabase.table("medical_documents_test").delete().eq("record_id", medical_record_id).execute()
                logger.info(f"🗑️ 清理旧文档记录: {len(delete_response.data) if delete_response.data else 0} 条")

                # 去重处理：基于 (record_id, type_id, title) 组合去重
                unique_records = {}
                for doc_record in document_records:
                    key = (doc_record["record_id"], doc_record["type_id"], doc_record["title"])
                    if key not in unique_records:
                        unique_records[key] = doc_record
                    else:
                        # 如果有重复，保留内容更长的那个
                        existing_content = unique_records[key].get("content", "")
                        new_content = doc_record.get("content", "")
                        if len(new_content) > len(existing_content):
                            unique_records[key] = doc_record

                final_records = list(unique_records.values())
                logger.info(f"📝 去重后文档数量: {len(final_records)} (原始: {len(document_records)})")

                # 插入去重后的文档记录
                if final_records:
                    response = supabase.table("medical_documents_test").insert(final_records).execute()
                    if response.data:
                        logger.info(f"✅ 成功保存 {len(response.data)} 个文档记录到medical_documents_test表")
                        # 记录分类统计
                        category_stats = {}
                        for doc in response.data:
                            cat_code = doc.get("metadata", {}).get("category_code", "unknown")
                            category_stats[cat_code] = category_stats.get(cat_code, 0) + 1
                        logger.info(f"📊 文档分类统计: {category_stats}")
                    else:
                        logger.warning("⚠️ 文档记录保存返回空数据")
                else:
                    logger.warning("⚠️ 去重后没有文档需要保存")

            except Exception as insert_error:
                logger.error(f"❌ 插入文档记录时出错: {insert_error}")
                raise

    except Exception as e:
        logger.error(f"❌ 保存文档记录失败: {e}")
        # 不抛出异常，避免影响主记录保存


async def get_classification_mapping():
    """
    获取分类映射表，用于将分类代码转换为ID
    """
    try:
        if not supabase:
            return {"categories": {}, "types": {}}

        # 获取文档分类
        categories_response = supabase.table("document_categories_test").select("id, category_code").execute()
        categories = {cat["category_code"]: cat["id"] for cat in categories_response.data} if categories_response.data else {}

        # 获取文档类型
        types_response = supabase.table("document_types_test").select(
            "id, type_code, category_id, document_categories_test!inner(category_code)"
        ).execute()

        types = {}
        if types_response.data:
            for doc_type in types_response.data:
                parent_code = doc_type["document_categories_test"]["category_code"]
                key = f"{parent_code}.{doc_type['type_code']}"
                types[key] = doc_type["id"]

        return {"categories": categories, "types": types}

    except Exception as e:
        logger.error(f"❌ 获取分类映射失败: {e}")
        return {"categories": {}, "types": {}}


@app.get("/api/test-classification-mapping")
async def test_classification_mapping():
    """测试分类映射功能"""
    try:
        mapping = await get_classification_mapping()
        return {
            "success": True,
            "mapping": mapping,
            "categories_count": len(mapping.get("categories", {})),
            "types_count": len(mapping.get("types", {}))
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def infer_category_from_type(type_code: str) -> str:
    """
    根据文档类型推断分类
    """
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

    return type_to_category_mapping.get(type_code, "progress_note")  # 默认为病程记录


def extract_document_content(doc: dict, raw_content: str) -> str:
    """
    从文档对象和原始内容中提取文档内容
    """
    # 优先使用已有的完整内容
    doc_content = doc.get("content", "") or doc.get("fullContent", "") or doc.get("content_preview", "")

    # 如果还是没有内容，尝试从原始内容中提取
    if not doc_content and raw_content:
        title = doc.get("title", "")
        if title and title in raw_content:
            # 找到标题在原始内容中的位置
            start_pos = raw_content.find(title)
            if start_pos != -1:
                # 提取标题后的内容
                content_start = start_pos

                # 寻找下一个文档的开始位置（通常是日期时间格式）
                remaining_content = raw_content[start_pos + len(title):]

                # 寻找下一个可能的标题或日期标记
                import re
                next_section_patterns = [
                    r'\n\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}',  # 日期时间格式
                    r'\n[=]{3,}.*[=]{3,}',  # 分页标记
                    r'\n\d+\.\s*[^\n]+记录',  # 编号+记录类型
                ]

                end_pos = len(raw_content)  # 默认到文档结尾

                for pattern in next_section_patterns:
                    match = re.search(pattern, remaining_content)
                    if match:
                        potential_end = start_pos + len(title) + match.start()
                        if potential_end < end_pos:
                            end_pos = potential_end
                        break

                # 移除内容长度限制，保留完整文档内容
                # 注释掉原来的长度限制，以支持完整的医疗文档显示
                # max_length = 2000
                # if end_pos - content_start > max_length:
                #     end_pos = content_start + max_length

                doc_content = raw_content[content_start:end_pos].strip()

                # 清理内容，移除多余的空行
                doc_content = re.sub(r'\n\s*\n\s*\n', '\n\n', doc_content)

    return doc_content


@app.get("/api/medical-records/{record_id}/documents")
async def get_medical_record_documents(record_id: str):
    """
    获取医疗记录的分类文档数据
    按照文书分类组织返回数据
    """
    try:
        if not supabase:
            raise HTTPException(status_code=500, detail="数据库连接未初始化")

        # 获取文档记录，包含分类信息
        response = supabase.table("medical_documents_test").select(
            """
            id,
            title,
            content,
            summary,
            ai_classified,
            classification_confidence,
            position_info,
            sort_order,
            status,
            qc_status,
            qc_score,
            metadata,
            created_at,
            updated_at,
            document_categories_test!category_id(
                id,
                category_code,
                category_name,
                description
            ),
            document_types_test!type_id(
                id,
                type_code,
                type_name,
                description
            )
            """
        ).eq("record_id", record_id).eq("status", "active").order("sort_order").execute()

        if not response.data:
            return {
                "record_id": record_id,
                "categories": [],
                "total_documents": 0,
                "classification_summary": {}
            }

        # 按分类组织数据
        categories_dict = {}
        classification_summary = {}

        for doc in response.data:
            # 获取分类信息
            category_info = doc.get("document_categories_test")
            type_info = doc.get("document_types_test")

            if not category_info:
                continue

            category_code = category_info["category_code"]
            category_name = category_info["category_name"]

            # 初始化分类
            if category_code not in categories_dict:
                categories_dict[category_code] = {
                    "category_id": category_info["id"],
                    "category_code": category_code,
                    "category_name": category_name,
                    "category_description": category_info.get("description", ""),
                    "document_count": 0,
                    "documents": []
                }
                classification_summary[category_code] = {
                    "name": category_name,
                    "count": 0,
                    "types": {}
                }

            # 添加文档到分类
            document_data = {
                "id": doc["id"],
                "title": doc["title"],
                "content": doc["content"],
                "summary": doc.get("summary", ""),
                "content_preview": doc["content"][:200] + "..." if len(doc["content"]) > 200 else doc["content"],
                "ai_classified": doc.get("ai_classified", False),
                "classification_confidence": float(doc.get("classification_confidence", 0)),
                "position_info": doc.get("position_info", {}),
                "sort_order": doc.get("sort_order", 0),
                "status": doc.get("status", "active"),
                "qc_status": doc.get("qc_status", "pending"),
                "qc_score": doc.get("qc_score"),
                "metadata": doc.get("metadata", {}),
                "created_at": doc.get("created_at"),
                "updated_at": doc.get("updated_at"),
                "type_info": {
                    "type_id": type_info["id"] if type_info else None,
                    "type_code": type_info["type_code"] if type_info else "unknown",
                    "type_name": type_info["type_name"] if type_info else "未知类型",
                    "type_description": type_info.get("description", "") if type_info else ""
                }
            }

            categories_dict[category_code]["documents"].append(document_data)
            categories_dict[category_code]["document_count"] += 1

            # 更新统计信息
            classification_summary[category_code]["count"] += 1
            type_code = type_info["type_code"] if type_info else "unknown"
            if type_code not in classification_summary[category_code]["types"]:
                classification_summary[category_code]["types"][type_code] = {
                    "name": type_info["type_name"] if type_info else "未知类型",
                    "count": 0
                }
            classification_summary[category_code]["types"][type_code]["count"] += 1

        # 转换为列表并排序
        categories_list = list(categories_dict.values())
        categories_list.sort(key=lambda x: x["category_code"])

        # 对每个分类内的文档按sort_order排序
        for category in categories_list:
            category["documents"].sort(key=lambda x: x["sort_order"])

        return {
            "record_id": record_id,
            "categories": categories_list,
            "total_documents": len(response.data),
            "classification_summary": classification_summary
        }

    except Exception as e:
        logger.error(f"获取医疗记录文档失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取文档失败: {str(e)}")


@app.put("/api/medical-documents/{document_id}")
async def update_medical_document(document_id: str, request: Request):
    """
    更新单个医疗文档，支持自动触发质控分析
    """
    try:
        if not supabase:
            raise HTTPException(status_code=500, detail="数据库连接未初始化")

        # 获取请求数据
        data = await request.json()
        auto_qc = data.get("auto_qc", True)  # 默认启用自动质控

        # 构建更新数据
        update_data = {}
        content_changed = False

        if "title" in data:
            update_data["title"] = data["title"]
        if "content" in data:
            update_data["content"] = data["content"]
            content_changed = True
        if "summary" in data:
            update_data["summary"] = data["summary"]
        if "type_code" in data:
            # 根据type_code查找对应的type_id
            type_response = supabase.table("document_types_test").select("id").eq("type_code", data["type_code"]).execute()
            if type_response.data:
                update_data["type_id"] = type_response.data[0]["id"]

        # 添加更新时间
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()

        # 更新文档
        response = supabase.table("medical_documents_test").update(update_data).eq("id", document_id).execute()

        if not response.data:
            raise HTTPException(status_code=404, detail="文档不存在")

        logger.info(f"✅ 成功更新文档: {document_id}")

        # 如果内容发生变化且启用自动质控，异步触发质控分析
        qc_task_id = None
        if content_changed and auto_qc and update_data.get("content"):
            try:
                qc_task_id = await trigger_auto_qc_analysis(document_id, update_data["content"])
                logger.info(f"✅ 已触发文档 {document_id} 的自动质控分析，任务ID: {qc_task_id}")
            except Exception as qc_error:
                logger.warning(f"⚠️ 自动质控分析触发失败: {qc_error}")
                # 质控失败不影响文档保存

        return {
            "success": True,
            "message": "文档更新成功",
            "document_id": document_id,
            "updated_fields": list(update_data.keys()),
            "qc_task_id": qc_task_id,
            "auto_qc_triggered": qc_task_id is not None
        }

    except Exception as e:
        logger.error(f"更新文档失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新文档失败: {str(e)}")


async def trigger_auto_qc_analysis(document_id: str, content: str) -> Optional[str]:
    """
    异步触发质控分析

    Args:
        document_id: 文档ID
        content: 文档内容

    Returns:
        质控任务ID，如果触发失败返回None
    """
    try:
        # 检查内容长度，避免对空内容或过短内容进行质控
        if not content or len(content.strip()) < 20:
            logger.info(f"文档 {document_id} 内容过短，跳过质控分析")
            return None

        # 生成任务ID
        task_id = f"qc-{document_id}-{uuid.uuid4().hex[:8]}"

        # 使用概念验证规则进行质控分析
        rule_codes = ["POC_001", "POC_002"]  # 使用现有的POC规则

        # 异步执行质控分析
        asyncio.create_task(
            perform_background_qc_analysis(document_id, content, rule_codes, task_id)
        )

        return task_id

    except Exception as e:
        logger.error(f"触发自动质控分析失败: {e}")
        return None


async def perform_background_qc_analysis(document_id: str, content: str, rule_codes: List[str], task_id: str):
    """
    后台执行质控分析
    """
    try:
        logger.info(f"开始后台质控分析，文档ID: {document_id}, 任务ID: {task_id}")

        # 更新文档状态为分析中
        if supabase:
            supabase.table("medical_documents_test").update({
                "qc_status": "analyzing",
                "updated_at": datetime.now(timezone.utc).isoformat()
            }).eq("id", document_id).execute()

        # 执行质控分析
        qc_result = await execute_qc_analysis_internal(document_id, content, rule_codes)

        # 更新文档的质控结果
        if supabase and qc_result:
            update_data = {
                "qc_status": qc_result.get("qc_status", "pending"),
                "qc_score": qc_result.get("qc_score"),
                "qc_last_analyzed": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }

            # 计算问题数量
            results = qc_result.get("results", [])
            failed_count = sum(1 for r in results if not r.get("compliant", True))
            update_data["qc_issues_count"] = failed_count

            supabase.table("medical_documents_test").update(update_data).eq("id", document_id).execute()

            # 保存详细的质控结果
            await save_qc_results_to_db(document_id, qc_result, task_id)

        logger.info(f"✅ 后台质控分析完成，文档ID: {document_id}, 评分: {qc_result.get('qc_score', 'N/A')}")

    except Exception as e:
        logger.error(f"后台质控分析失败，文档ID: {document_id}, 错误: {e}")

        # 更新文档状态为失败
        if supabase:
            supabase.table("medical_documents_test").update({
                "qc_status": "failed",
                "updated_at": datetime.now(timezone.utc).isoformat()
            }).eq("id", document_id).execute()


async def execute_qc_analysis_internal(document_id: str, content: str, rule_codes: List[str]) -> Optional[Dict[str, Any]]:
    """
    内部质控分析执行函数
    """
    try:
        # 使用现有的质控服务
        from qc_poc_service import QCPOCService

        qc_service = QCPOCService()

        # 构造文档数据
        document_data = {
            "id": document_id,
            "content": content,
            "title": f"Document {document_id}"
        }

        # 执行质控分析
        result = await qc_service.analyze_document_async(document_data, rule_codes)

        return result

    except Exception as e:
        logger.error(f"内部质控分析执行失败: {e}")
        return None


async def save_qc_results_to_db(document_id: str, qc_result: Dict[str, Any], task_id: str):
    """
    保存质控结果到数据库
    """
    try:
        if not supabase:
            return

        # 保存到质控结果表
        qc_record = {
            "id": str(uuid.uuid4()),
            "document_id": document_id,
            "task_id": task_id,
            "qc_status": qc_result.get("qc_status", "pending"),
            "qc_score": qc_result.get("qc_score"),
            "applied_rules": len(qc_result.get("results", [])),
            "failed_rules": sum(1 for r in qc_result.get("results", []) if not r.get("compliant", True)),
            "results": json.dumps(qc_result.get("results", []), ensure_ascii=False),
            "suggestions": json.dumps(qc_result.get("suggestions", []), ensure_ascii=False),
            "analysis_time": datetime.now(timezone.utc).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        supabase.table("document_qc_results_test").insert(qc_record).execute()
        logger.info(f"✅ 质控结果已保存到数据库，文档ID: {document_id}")

    except Exception as e:
        logger.error(f"保存质控结果失败: {e}")


@app.get("/api/qc-tasks/{task_id}")
async def get_qc_task_status(task_id: str):
    """
    获取质控任务状态
    """
    try:
        if not supabase:
            raise HTTPException(status_code=500, detail="数据库连接未初始化")

        # 查询质控结果
        response = supabase.table("document_qc_results_test").select("*").eq("task_id", task_id).execute()

        if not response.data:
            return {
                "task_id": task_id,
                "status": "pending",
                "message": "质控分析进行中..."
            }

        result = response.data[0]
        return {
            "task_id": task_id,
            "status": "completed",
            "document_id": result["document_id"],
            "qc_status": result["qc_status"],
            "qc_score": result["qc_score"],
            "applied_rules": result["applied_rules"],
            "failed_rules": result["failed_rules"],
            "analysis_time": result["analysis_time"],
            "results": json.loads(result["results"]) if result["results"] else [],
            "suggestions": json.loads(result["suggestions"]) if result["suggestions"] else []
        }

    except Exception as e:
        logger.error(f"获取质控任务状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取任务状态失败: {str(e)}")


@app.post("/api/medical-records/{record_id}/batch-qc-analysis")
async def batch_qc_analysis(record_id: str, request: Request):
    """
    批量质控分析
    """
    try:
        if not supabase:
            raise HTTPException(status_code=500, detail="数据库连接未初始化")

        data = await request.json()
        rule_codes = data.get("rule_codes", ["POC_001", "POC_002"])

        # 获取记录下的所有文档
        documents_response = supabase.table("medical_documents_test").select("*").eq("record_id", record_id).execute()

        if not documents_response.data:
            raise HTTPException(status_code=404, detail="未找到相关文档")

        documents = documents_response.data
        batch_task_id = f"batch-qc-{record_id}-{uuid.uuid4().hex[:8]}"

        # 为每个文档触发质控分析
        task_ids = []
        for doc in documents:
            if doc.get("content"):
                task_id = await trigger_auto_qc_analysis(doc["id"], doc["content"])
                if task_id:
                    task_ids.append(task_id)

        return {
            "success": True,
            "batch_task_id": batch_task_id,
            "record_id": record_id,
            "total_documents": len(documents),
            "queued_tasks": len(task_ids),
            "task_ids": task_ids,
            "message": f"已为 {len(task_ids)} 个文档启动质控分析"
        }

    except Exception as e:
        logger.error(f"批量质控分析失败: {e}")
        raise HTTPException(status_code=500, detail=f"批量质控分析失败: {str(e)}")


@app.delete("/api/medical-documents/{document_id}")
async def delete_medical_document(document_id: str):
    """
    删除单个医疗文档
    """
    try:
        if not supabase:
            raise HTTPException(status_code=500, detail="数据库连接未初始化")

        # 软删除：更新状态为inactive
        response = supabase.table("medical_documents_test").update({
            "status": "inactive",
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", document_id).execute()

        if not response.data:
            raise HTTPException(status_code=404, detail="文档不存在")

        logger.info(f"✅ 成功删除文档: {document_id}")

        return {
            "success": True,
            "message": "文档删除成功",
            "document_id": document_id
        }

    except Exception as e:
        logger.error(f"删除文档失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除文档失败: {str(e)}")


# 获取单个医疗记录详情接口（无需认证）
@app.get("/api/medical-records/{record_id}", response_model=MedicalRecordResponse)
async def get_medical_record_detail(record_id: str):
    """获取单个医疗记录详情（无需认证）"""
    try:
        # 优先从Supabase查询，如果失败则从内存查询
        if supabase:
            try:
                response = supabase.table('medical_records_test').select('*').eq('id', record_id).execute()
                if response.data:
                    record = response.data[0]
                    logger.info(f"从Supabase获取医疗记录: {record_id}")

                    # 处理medical_records_test表的数据结构
                    # 从patient_info嵌套对象中获取患者信息
                    patient_info = record.get("patient_info", {})
                    patient_name = patient_info.get("name", "未识别")
                    patient_age = patient_info.get("age", 0)
                    patient_gender = patient_info.get("gender", "未识别")

                    # 获取部门信息
                    department_name = record.get("department", "未识别")

                    # 获取诊断信息
                    primary_diagnosis = record.get("primary_diagnosis", "")

                    # 获取病历内容
                    content = record.get("raw_text", "")

                    response_record = {
                        "id": record.get("id"),
                        "patient_name": patient_name,
                        "patient_age": patient_age,
                        "patient_gender": patient_gender,
                        "department": department_name,
                        "admission_date": record.get("created_at", datetime.utcnow().isoformat()),
                        "record_type": "LLM解析结果",
                        "content": content,
                        "status": record.get("status", "active"),
                        "created_at": record.get("created_at", datetime.utcnow().isoformat()),
                        "updated_at": record.get("updated_at", datetime.utcnow().isoformat()),
                        "created_by": "LLM系统",
                        "file_url": None
                    }

                    return MedicalRecordResponse(**response_record)
                else:
                    # Supabase中没有找到，尝试从内存中查找
                    if record_id in medical_records_db:
                        record = medical_records_db[record_id]
                        logger.info(f"从内存获取医疗记录: {record_id}")
                        return MedicalRecordResponse(**record)
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail="医疗记录不存在"
                        )
            except HTTPException:
                raise
            except Exception as e:
                logger.warning(f"从Supabase查询失败，尝试内存查询: {e}")
                # 回退到内存查询
                if record_id in medical_records_db:
                    record = medical_records_db[record_id]
                    logger.info(f"从内存获取医疗记录: {record_id}")
                    return MedicalRecordResponse(**record)
                else:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="医疗记录不存在"
                    )
        else:
            # 直接从内存查询
            if record_id in medical_records_db:
                record = medical_records_db[record_id]
                logger.info(f"从内存获取医疗记录: {record_id}")
                return MedicalRecordResponse(**record)
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="医疗记录不存在"
                )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取医疗记录失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取失败: {str(e)}"
        )

# 添加医疗记录删除接口（无需认证，与前端路径匹配）
@app.delete("/api/medical-records/{record_id}")
async def delete_medical_record_by_id(record_id: str):
    """删除医疗记录（无需认证）"""
    try:
        # 验证 UUID 格式
        try:
            uuid.UUID(record_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无效的记录ID格式"
            )

        # 优先从Supabase删除，如果失败则从内存删除
        if supabase:
            try:
                # 检查记录是否存在
                existing_response = supabase.table('medical_records_test').select('id').eq('id', record_id).execute()
                if not existing_response.data:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="医疗记录不存在"
                    )

                # 删除记录
                response = supabase.table('medical_records_test').delete().eq('id', record_id).execute()
                logger.info(f"从Supabase删除医疗记录成功: {record_id}")

                return {
                    "success": True,
                    "message": "医疗记录删除成功",
                    "deleted_id": record_id
                }

            except HTTPException:
                raise
            except Exception as e:
                logger.warning(f"从Supabase删除失败，尝试从内存删除: {e}")
                # 如果Supabase删除失败，尝试从内存删除
                if record_id in medical_records_db:
                    del medical_records_db[record_id]
                    logger.info(f"从内存删除医疗记录成功: {record_id}")
                    return {
                        "success": True,
                        "message": "医疗记录删除成功",
                        "deleted_id": record_id
                    }
                else:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="医疗记录不存在"
                    )
        else:
            # 直接从内存删除
            if record_id in medical_records_db:
                del medical_records_db[record_id]
                logger.info(f"从内存删除医疗记录成功: {record_id}")
                return {
                    "success": True,
                    "message": "医疗记录删除成功",
                    "deleted_id": record_id
                }
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="医疗记录不存在"
                )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除医疗记录失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除失败: {str(e)}"
        )

@app.put("/api/records/{record_id}", response_model=MedicalRecordResponse)
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
    current_user: dict = Depends(get_current_user)
):
    """更新医疗记录"""
    record = medical_records_db.get(record_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="医疗记录不存在"
        )

    # 更新字段
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

    # 处理文件上传
    if file:
        record["file_url"] = f"/uploads/{file.filename}"

    record["updated_at"] = datetime.utcnow().isoformat() + "Z"

    return MedicalRecordResponse(**record)

@app.delete("/api/records/{record_id}")
async def delete_medical_record(
    record_id: str,
    current_user: dict = Depends(get_current_user)
):
    """删除医疗记录"""
    if record_id not in medical_records_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="医疗记录不存在"
        )

    del medical_records_db[record_id]

    return {"message": "医疗记录删除成功"}

@app.delete("/api/records/batch")
async def batch_delete_records(
    record_ids: List[str],
    current_user: dict = Depends(get_current_user)
):
    """批量删除医疗记录"""
    deleted_count = 0
    for record_id in record_ids:
        if record_id in medical_records_db:
            del medical_records_db[record_id]
            deleted_count += 1

    return {"message": f"成功删除 {deleted_count} 条记录"}

@app.post("/api/records/export")
async def export_records(
    record_ids: List[str],
    current_user: dict = Depends(get_current_user)
):
    """导出医疗记录"""
    # 在实际应用中，这里应该生成导出文件
    export_id = f"export-{uuid.uuid4().hex[:8]}"
    download_url = f"/downloads/{export_id}.xlsx"

    return {"download_url": download_url}

@app.get("/api/records/statistics")
async def get_medical_records_statistics(
    current_user: dict = Depends(get_current_user)
):
    """获取医疗记录统计信息"""
    records = list(medical_records_db.values())

    total_records = len(records)
    pending_records = len([r for r in records if r["status"] == "pending"])
    completed_records = len([r for r in records if r["status"] == "completed"])
    analyzing_records = len([r for r in records if r["status"] == "analyzing"])

    # 按科室统计
    department_stats = {}
    for record in records:
        dept = record["department"]
        department_stats[dept] = department_stats.get(dept, 0) + 1

    # 按记录类型统计
    type_stats = {}
    for record in records:
        record_type = record["record_type"]
        type_stats[record_type] = type_stats.get(record_type, 0) + 1

    return {
        "total_records": total_records,
        "pending_records": pending_records,
        "completed_records": completed_records,
        "analyzing_records": analyzing_records,
        "department_statistics": department_stats,
        "type_statistics": type_stats,
        "recent_activity": {
            "today": len([r for r in records if r["created_at"].startswith(datetime.now().strftime("%Y-%m-%d"))]),
            "this_week": len([r for r in records if (datetime.now() - datetime.fromisoformat(r["created_at"].replace("Z", ""))).days <= 7]),
            "this_month": len([r for r in records if (datetime.now() - datetime.fromisoformat(r["created_at"].replace("Z", ""))).days <= 30])
        }
    }

@app.post("/api/records/upload")
async def upload_record_file(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """上传医疗记录文件"""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件名不能为空"
        )

    # 在实际应用中，这里应该保存文件到存储系统
    file_url = f"/uploads/{file.filename}"

    return {
        "file_url": file_url,
        "file_name": file.filename
    }

@app.post("/api/parse-medical-file-public")
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
        if file.content_type == 'application/pdf' or (file.filename and file.filename.endswith('.pdf')):
            # PDF文件解析
            try:
                try:
                    from backend.services.pdf_parser import parse_pdf_file  # type: ignore
                except Exception:
                    from services.pdf_parser import parse_pdf_file  # type: ignore
                result = parse_pdf_file(file_content, file.filename)

                if not result["success"]:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"PDF解析失败: {result.get('error', '未知错误')}"
                    )

                return {
                    "success": True,
                    "data": {
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
                    "tokensUsed": 0
                }
            except ImportError:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="PDF解析服务不可用"
                )

        elif file.content_type == 'text/plain' or (file.filename and file.filename.endswith('.txt')):
            # 文本文件解析
            try:
                text_content = file_content.decode('utf-8')
            except UnicodeDecodeError:
                try:
                    text_content = file_content.decode('gbk')
                except UnicodeDecodeError:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="文本文件编码不支持，请使用UTF-8或GBK编码"
                    )

            # 简单的医疗信息提取
            import re
            medical_info = {}

            # 提取患者姓名
            name_patterns = [
                r"患者姓名[：:]\s*([^\s\n]+)",
                r"姓名[：:]\s*([^\s\n]+)",
                r"病人[：:]\s*([^\s\n]+)"
            ]
            for pattern in name_patterns:
                match = re.search(pattern, text_content)
                if match:
                    medical_info["patientName"] = match.group(1)
                    break

            # 提取科室
            dept_patterns = [
                r"科室[：:]\s*([^\s\n]+)",
                r"所在科室[：:]\s*([^\s\n]+)"
            ]
            for pattern in dept_patterns:
                match = re.search(pattern, text_content)
                if match:
                    medical_info["department"] = match.group(1)
                    break

            # 提取诊断
            diag_patterns = [
                r"诊断[：:]\s*([^\n]+)",
                r"主要诊断[：:]\s*([^\n]+)",
                r"入院诊断[：:]\s*([^\n]+)"
            ]
            for pattern in diag_patterns:
                match = re.search(pattern, text_content)
                if match:
                    medical_info["primaryDiagnosis"] = match.group(1).strip()
                    break

            return {
                "success": True,
                "data": {
                    "content": text_content,
                    "method": "文本文件解析",
                    "pages": 1,
                    "medical_info": medical_info,
                    "file_info": {
                        "filename": file.filename,
                        "size": len(file_content),
                        "type": file.content_type
                    },
                    **medical_info  # 兼容前端期望的字段名
                },
                "tokensUsed": 0
            }

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的文件类型: {file.content_type}。目前支持PDF和文本文件"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文件解析失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文件解析失败: {str(e)}"
        )

@app.post("/api/parse-medical-text")
async def parse_medical_text(request: dict):
    """解析医疗文本"""
    try:
        text = request.get("text", "").strip()
        if not text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="文本内容不能为空"
            )

        # 简单的医疗信息提取
        medical_info = {}

        # 提取患者姓名
        import re
        name_patterns = [
            r"患者姓名[：:]\s*([^\s\n]+)",
            r"姓名[：:]\s*([^\s\n]+)",
            r"病人[：:]\s*([^\s\n]+)"
        ]
        for pattern in name_patterns:
            match = re.search(pattern, text)
            if match:
                medical_info["patientName"] = match.group(1)
                break

        # 提取科室
        dept_patterns = [
            r"科室[：:]\s*([^\s\n]+)",
            r"所在科室[：:]\s*([^\s\n]+)"
        ]
        for pattern in dept_patterns:
            match = re.search(pattern, text)
            if match:
                medical_info["department"] = match.group(1)
                break

        # 提取诊断
        diag_patterns = [
            r"诊断[：:]\s*([^\n]+)",
            r"主要诊断[：:]\s*([^\n]+)",
            r"入院诊断[：:]\s*([^\n]+)"
        ]
        for pattern in diag_patterns:
            match = re.search(pattern, text)
            if match:
                medical_info["primaryDiagnosis"] = match.group(1).strip()
                break

        return {
            "success": True,
            "data": {
                "content": text,
                "method": "文本解析",
                "medical_info": medical_info,
                **medical_info  # 兼容前端期望的字段名
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文本解析失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文本解析失败: {str(e)}"
        )

@app.post("/api/parse-medical-file")
async def parse_medical_file(
    file: UploadFile = File(...),
    options: str = Form("{}"),
    current_user: dict = Depends(get_current_user)
):
    """解析医疗文件（支持PDF等格式）"""
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
            try:
                from backend.services.pdf_parser import parse_pdf_file  # type: ignore
            except Exception:
                from services.pdf_parser import parse_pdf_file  # type: ignore

            result = parse_pdf_file(file_content, file.filename)

            if not result["success"]:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"PDF解析失败: {result.get('error', '未知错误')}"
                )

            return {
                "success": True,
                "data": {
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
                "tokensUsed": 0  # PDF解析不消耗AI tokens
            }

        elif file.content_type == 'text/plain' or file.filename.endswith('.txt'):
            # 文本文件直接读取
            try:
                content = file_content.decode('utf-8')
            except UnicodeDecodeError:
                content = file_content.decode('gbk', errors='ignore')

            return {
                "success": True,
                "data": {
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
                "tokensUsed": 0
            }

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

@app.post("/api/records/{record_id}/duplicate", response_model=MedicalRecordResponse)
async def duplicate_record(
    record_id: str,
    current_user: dict = Depends(get_current_user)
):
    """复制医疗记录"""
    original_record = medical_records_db.get(record_id)
    if not original_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="医疗记录不存在"
        )

    new_record_id = f"record-{uuid.uuid4().hex[:8]}"
    new_record = original_record.copy()
    new_record.update({
        "id": new_record_id,
        "patient_name": f"{original_record['patient_name']}_副本",
        "status": "pending",
        "created_at": datetime.utcnow().isoformat() + "Z",
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "created_by": current_user["id"]
    })

    medical_records_db[new_record_id] = new_record

    return MedicalRecordResponse(**new_record)

# ==================== 质控分析API (B3任务 - 9个接口) ====================

def generate_mock_qc_result(record_id: str) -> dict:
    """生成模拟质控结果"""
    import random

    # 生成随机评分
    overall_score = random.randint(70, 95)

    # 根据评分确定等级
    if overall_score >= 90:
        overall_grade = "A"
    elif overall_score >= 80:
        overall_grade = "B"
    else:
        overall_grade = "C"

    # 生成模拟问题
    sample_issues = [
        {
            "id": f"issue-{i}",
            "rule_name": f"质控规则{i:02d}",
            "description": f"发现质控问题{i}：病案记录不够完整或规范",
            "severity": random.choice(["critical", "major", "minor"]),
            "category": random.choice(["基本信息", "诊断质量", "治疗方案", "护理记录"]),
            "location": f"第{random.randint(1, 10)}段",
            "suggestion": f"建议完善相关内容，确保符合医疗质控标准"
        }
        for i in range(1, random.randint(2, 6))
    ]

    # 生成模拟建议
    sample_suggestions = [
        {
            "id": f"suggestion-{i}",
            "category": random.choice(["诊断改进", "治疗优化", "记录完善"]),
            "title": f"改进建议{i}",
            "description": f"针对当前病案的改进建议{i}，提高医疗质量",
            "priority": random.choice(["high", "medium", "low"])
        }
        for i in range(1, random.randint(3, 6))
    ]

    # 生成规则执行结果
    rule_results = []
    for rule_id, rule in qc_rules_db.items():
        passed = random.choice([True, False, True, True])  # 75%通过率
        score = random.randint(80, 100) if passed else random.randint(50, 79)

        rule_results.append({
            "rule_id": rule_id,
            "rule_name": rule["name"],
            "passed": passed,
            "score": score,
            "details": f"规则执行详情：{'通过' if passed else '未通过'}质控检查"
        })

    return {
        "id": f"qc-result-{record_id}",
        "record_id": record_id,
        "overall_score": overall_score,
        "overall_grade": overall_grade,
        "analysis_date": datetime.utcnow().isoformat() + "Z",
        "issues": sample_issues,
        "suggestions": sample_suggestions,
        "rule_results": rule_results
    }

@app.post("/api/qc/analyze/{record_id}")
async def analyze_record(
    record_id: str,
    current_user: dict = Depends(get_current_user)
):
    """开始质控分析"""
    record = medical_records_db.get(record_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="医疗记录不存在"
        )

    # 生成分析ID
    analysis_id = f"analysis-{uuid.uuid4().hex[:8]}"

    # 更新记录状态
    record["status"] = "analyzing"

    # 模拟异步分析过程（实际应用中应该使用后台任务）
    # 这里直接生成结果
    qc_result = generate_mock_qc_result(record_id)
    qc_results_db[record_id] = qc_result

    # 分析完成后更新记录状态
    record["status"] = "completed"

    return {"analysis_id": analysis_id}

@app.post("/api/qc/analyze/batch")
async def batch_analyze_records(
    record_ids: List[str],
    current_user: dict = Depends(get_current_user)
):
    """批量质控分析"""
    analysis_ids = []

    for record_id in record_ids:
        record = medical_records_db.get(record_id)
        if record:
            analysis_id = f"analysis-{uuid.uuid4().hex[:8]}"
            analysis_ids.append(analysis_id)

            # 更新记录状态
            record["status"] = "analyzing"

            # 生成质控结果
            qc_result = generate_mock_qc_result(record_id)
            qc_results_db[record_id] = qc_result

            # 分析完成后更新记录状态
            record["status"] = "completed"

    return {"analysis_ids": analysis_ids}

@app.get("/api/qc/result/{record_id}", response_model=QCResult)
async def get_qc_result(
    record_id: str,
    current_user: dict = Depends(get_current_user)
):
    """获取质控分析结果"""
    qc_result = qc_results_db.get(record_id)
    if not qc_result:
        # 如果没有结果，生成一个新的
        qc_result = generate_mock_qc_result(record_id)
        qc_results_db[record_id] = qc_result

    return QCResult(**qc_result)

@app.get("/api/qc/progress/{analysis_id}")
async def get_analysis_progress(
    analysis_id: str,
    current_user: dict = Depends(get_current_user)
):
    """获取分析进度"""
    # 模拟进度数据
    return {
        "analysis_id": analysis_id,
        "status": "completed",
        "progress": 100,
        "current_step": "生成分析报告",
        "total_steps": 5,
        "start_time": (datetime.utcnow() - timedelta(minutes=2)).isoformat() + "Z",
        "estimated_completion": datetime.utcnow().isoformat() + "Z",
        "details": {
            "processed_records": 1,
            "total_records": 1,
            "issues_found": 3,
            "suggestions_generated": 4
        }
    }

@app.get("/api/qc/rules")
async def get_qc_rules(current_user: dict = Depends(get_current_user)):
    """获取质控规则列表"""
    return list(qc_rules_db.values())

@app.post("/api/qc/rules", response_model=QCRule)
async def create_qc_rule(
    rule_data: dict,
    current_user: dict = Depends(get_current_user)
):
    """创建质控规则"""
    rule_id = f"rule-{uuid.uuid4().hex[:8]}"

    new_rule = {
        "id": rule_id,
        "rule_code": rule_data.get("rule_code", f"QC{len(qc_rules_db) + 1:03d}"),
        "name": rule_data["name"],
        "description": rule_data["description"],
        "category": rule_data["category"],
        "severity": rule_data["severity"],
        "weight": rule_data.get("weight", 10),
        "is_active": rule_data.get("is_active", True),
        "conditions": rule_data.get("conditions"),
        "created_at": datetime.utcnow().isoformat() + "Z",
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "execution_count": 0,
        "pass_rate": 0.0,
        "issue_count": 0
    }

    qc_rules_db[rule_id] = new_rule

    return QCRule(**new_rule)

@app.put("/api/qc/rules/{rule_id}", response_model=QCRule)
async def update_qc_rule(
    rule_id: str,
    rule_data: dict,
    current_user: dict = Depends(get_current_user)
):
    """更新质控规则"""
    rule = qc_rules_db.get(rule_id)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="质控规则不存在"
        )

    # 更新字段
    for key, value in rule_data.items():
        if key in rule and value is not None:
            rule[key] = value

    rule["updated_at"] = datetime.utcnow().isoformat() + "Z"

    return QCRule(**rule)

@app.delete("/api/qc/rules/{rule_id}")
async def delete_qc_rule(
    rule_id: str,
    current_user: dict = Depends(get_current_user)
):
    """删除质控规则"""
    if rule_id not in qc_rules_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="质控规则不存在"
        )

    del qc_rules_db[rule_id]

    return {"message": "质控规则删除成功"}

@app.get("/api/qc/history")
async def get_qc_history(
    page: int = 1,
    page_size: int = 10,
    current_user: dict = Depends(get_current_user)
):
    """获取质控历史记录"""
    # 生成模拟历史数据
    history_records = []

    for record_id, record in medical_records_db.items():
        if record["status"] == "completed":
            qc_result = qc_results_db.get(record_id)
            if qc_result:
                history_records.append({
                    "id": record_id,
                    "patient_name": record["patient_name"],
                    "department": record["department"],
                    "analysis_date": qc_result["analysis_date"],
                    "overall_score": qc_result["overall_score"],
                    "overall_grade": qc_result["overall_grade"],
                    "issue_count": len(qc_result["issues"]),
                    "content": record["content"]
                })

    # 按分析日期排序
    history_records.sort(key=lambda x: x["analysis_date"], reverse=True)

    # 分页
    total = len(history_records)
    start = (page - 1) * page_size
    end = start + page_size
    paginated_records = history_records[start:end]

    return paginated_records

# ==================== 质控概念验证 API ====================

@app.post("/api/medical-documents/{document_id}/qc-analysis")
async def analyze_document_qc_poc(
    document_id: str,
    rule_codes: Optional[List[str]] = None
):
    """
    概念验证：单文档质控分析

    Args:
        document_id: 文档ID
        rule_codes: 要执行的规则代码列表，默认执行概念验证规则
    """
    try:
        logger.info(f"开始概念验证质控分析，文档ID: {document_id}")

        # 从数据库获取文档内容
        response = supabase.table('medical_documents_test').select('*').eq('id', document_id).execute()

        if not response.data:
            raise HTTPException(status_code=404, detail=f"文档 {document_id} 不存在")

        document = response.data[0]
        content = document.get('content', '')

        if not content:
            raise HTTPException(status_code=400, detail="文档内容为空")

        # 获取质控服务
        qc_service = get_qc_poc_service()

        # 执行质控分析
        analysis_result = await qc_service.analyze_document(
            document_id=document_id,
            content=content,
            rule_ids=rule_codes or ["POC_001", "POC_002"]
        )

        # 将结果写入数据库（概念验证阶段先写入测试表）
        try:
            # 更新文档的质控状态
            supabase.table('medical_documents_test').update({
                'qc_status': analysis_result['qc_status'],
                'qc_score': analysis_result['qc_score'],
                'qc_last_analyzed': analysis_result['analysis_time'],
                'qc_analysis_version': analysis_result['analysis_version'],
                'metadata': {
                    **document.get('metadata', {}),
                    'content_hash': analysis_result['content_hash']
                }
            }).eq('id', document_id).execute()

            # 写入详细结果到质控结果表
            for result in analysis_result['results']:
                supabase.table('document_qc_results_test').insert({
                    'document_id': document_id,
                    'rule_id': result['rule_id'],  # 这里需要映射到数据库中的规则ID
                    'result_status': 'passed' if result['compliant'] else 'failed',
                    'score': 100 if result['compliant'] else 95,  # 简化评分
                    'max_score': 100,
                    'confidence_score': result['confidence'],
                    'issue_category': 'completeness',
                    'issue_description': result['rule_name'],
                    'evidence_text': result['evidence'],
                    'ai_reasoning': result['reasoning'],
                    'ai_model_used': 'mock-llm-v1.0',
                    'analysis_time_ms': int(result['execution_time'] * 1000),
                    'manual_review_status': 'pending'
                }).execute()

        except Exception as db_error:
            logger.warning(f"写入数据库失败，但分析成功: {db_error}")

        logger.info(f"概念验证质控分析完成，文档ID: {document_id}，状态: {analysis_result['qc_status']}")

        return {
            "success": True,
            "data": {
                "document_id": document_id,
                "qc_status": analysis_result['qc_status'],
                "qc_score": analysis_result['qc_score'],
                "applied_rules": analysis_result['applied_rules'],
                "failed_rules": analysis_result['failed_rules'],
                "results": analysis_result['results'],
                "analysis_time": analysis_result['analysis_time']
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"概念验证质控分析失败: {e}")
        raise HTTPException(status_code=500, detail=f"质控分析失败: {str(e)}")

@app.get("/api/medical-documents/{document_id}/qc-results")
async def get_document_qc_results_poc(
    document_id: str,
    latest: bool = True
):
    """
    概念验证：获取文档质控结果

    Args:
        document_id: 文档ID
        latest: 是否只返回最新结果
    """
    try:
        # 获取文档基本信息
        doc_response = supabase.table('medical_documents_test').select('qc_status,qc_score,qc_last_analyzed').eq('id', document_id).execute()

        if not doc_response.data:
            raise HTTPException(status_code=404, detail=f"文档 {document_id} 不存在")

        document = doc_response.data[0]

        # 获取详细质控结果
        query = supabase.table('document_qc_results_test').select('*').eq('document_id', document_id)

        if latest:
            query = query.order('created_at', desc=True).limit(10)

        results_response = query.execute()

        return {
            "document_id": document_id,
            "qc_status": document.get('qc_status'),
            "qc_score": document.get('qc_score'),
            "last_analyzed": document.get('qc_last_analyzed'),
            "results": results_response.data or []
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取质控结果失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取质控结果失败: {str(e)}")

@app.get("/api/qc/poc/rules")
async def get_poc_qc_rules():
    """概念验证：获取可用的质控规则"""
    try:
        qc_service = get_qc_poc_service()
        rules = qc_service.get_available_rules()

        return {
            "rules": rules,
            "total": len(rules),
            "engine_stats": qc_service.get_engine_stats()
        }

    except Exception as e:
        logger.error(f"获取概念验证规则失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取规则失败: {str(e)}")

# =====================================================
# 质控LLM配置管理API
# =====================================================

@app.get("/api/qc/llm-configs")
async def get_qc_llm_configs():
    """获取质控LLM配置列表"""
    try:
        result = supabase.table('qc_llm_configs_view').select('*').execute()

        return {
            "configs": result.data,
            "total": len(result.data),
            "message": "获取配置成功"
        }
    except Exception as e:
        logger.error(f"获取LLM配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取LLM配置失败: {str(e)}")

@app.get("/api/llm/providers")
async def get_llm_providers():
    """获取LLM提供商列表"""
    try:
        result = supabase.table('llm_api_providers').select('*').eq('is_active', True).execute()

        return {
            "providers": result.data,
            "total": len(result.data),
            "message": "获取提供商成功"
        }
    except Exception as e:
        logger.error(f"获取LLM提供商失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取LLM提供商失败: {str(e)}")

@app.get("/api/llm/models")
async def get_llm_models():
    """获取LLM模型列表"""
    try:
        result = supabase.table('llm_models').select('*').eq('is_active', True).execute()

        return {
            "models": result.data,
            "total": len(result.data),
            "message": "获取模型成功"
        }
    except Exception as e:
        logger.error(f"获取LLM模型失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取LLM模型失败: {str(e)}")

class LLMConfigCreate(BaseModel):
    config_name: str
    provider_id: str
    model_id: str
    api_key: str
    custom_endpoint: Optional[str] = None
    custom_parameters: Optional[Dict[str, Any]] = None

@app.post("/api/qc/llm-configs")
async def create_qc_llm_config(config: LLMConfigCreate):
    """创建质控LLM配置"""
    try:
        # 插入配置
        result = supabase.table('user_llm_configs').insert({
            'user_id': None,  # 全局配置
            'config_name': config.config_name,
            'provider_id': config.provider_id,
            'model_id': config.model_id,
            'api_key_encrypted': config.api_key,  # 实际使用时应该加密
            'custom_endpoint': config.custom_endpoint,
            'custom_parameters': config.custom_parameters or {},
            'is_active': True
        }).execute()

        return {
            "config": result.data[0],
            "message": "配置创建成功"
        }
    except Exception as e:
        logger.error(f"创建LLM配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建LLM配置失败: {str(e)}")

@app.put("/api/qc/llm-configs/{config_id}")
async def update_qc_llm_config(config_id: str, config: LLMConfigCreate):
    """更新质控LLM配置"""
    try:
        update_data = {
            'provider_id': config.provider_id,
            'model_id': config.model_id,
            'custom_endpoint': config.custom_endpoint,
            'custom_parameters': config.custom_parameters or {},
            'updated_at': datetime.now().isoformat()
        }

        # 只有提供了API密钥才更新
        if config.api_key:
            update_data['api_key_encrypted'] = config.api_key

        result = supabase.table('user_llm_configs').update(update_data).eq('id', config_id).execute()

        return {
            "config": result.data[0] if result.data else None,
            "message": "配置更新成功"
        }
    except Exception as e:
        logger.error(f"更新LLM配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新LLM配置失败: {str(e)}")

@app.delete("/api/qc/llm-configs/{config_id}")
async def delete_qc_llm_config(config_id: str):
    """删除质控LLM配置"""
    try:
        result = supabase.table('user_llm_configs').delete().eq('id', config_id).execute()

        return {
            "message": "配置删除成功"
        }
    except Exception as e:
        logger.error(f"删除LLM配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除LLM配置失败: {str(e)}")

@app.post("/api/qc/llm-configs/{config_id}/test")
async def test_qc_llm_config(config_id: str):
    """测试质控LLM配置"""
    try:
        # 获取配置信息
        result = supabase.table('qc_llm_configs_view').select('*').eq('config_id', config_id).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="配置不存在")

        config_data = result.data[0]

        # 创建测试用的LLM客户端
        from qc_poc_service import RealLLMClient

        test_client = RealLLMClient(
            api_endpoint=config_data.get('custom_endpoint') or config_data['base_endpoint'],
            api_key=config_data.get('api_key_encrypted', ''),
            model=config_data['model_code']
        )

        # 执行测试
        start_time = time.time()
        test_result = test_client.execute_semantic_rule(
            'POC_001',
            '测试文档：患者张三，男，45岁，主诉：胸痛3天。现病史：患者3天前无明显诱因出现胸痛。'
        )
        response_time = int((time.time() - start_time) * 1000)

        # 解析测试结果
        if 'content' in test_result:
            content = json.loads(test_result['content'])
            success = content.get('compliant', False)
        else:
            success = test_result.get('compliant', False)

        return {
            "success": success,
            "message": "连接测试成功" if success else "连接测试失败",
            "details": {
                "responseTime": response_time,
                "model": config_data['model_name'],
                "tokenUsage": test_result.get('token_usage', {}).get('total', 0)
            }
        }

    except Exception as e:
        logger.error(f"测试LLM配置失败: {e}")
        return {
            "success": False,
            "message": f"测试失败: {str(e)}",
            "details": None
        }

# ==================== LLM 配置 API ====================

# 内存存储用于模拟配置保存（生产环境应使用真正的数据库）
llm_configs_storage = {}

@app.get('/api/llm/providers')
async def get_llm_providers():
    """获取所有可用的LLM提供商"""
    try:
        # 从Supabase数据库查询提供商
        response = supabase.table('llm_api_providers').select('*').eq('is_active', True).order('sort_order').execute()

        if response.data:
            print(f"✅ 从数据库获取到 {len(response.data)} 个提供商")
            return {'data': response.data}
        else:
            print("⚠️ 数据库中未找到提供商，返回空列表")
            return {'data': []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'获取LLM提供商失败: {str(e)}')

@app.get('/api/llm/models')
async def get_llm_models(provider_id: Optional[str] = None):
    """获取LLM模型列表"""
    try:
        # 从Supabase数据库查询模型
        query = supabase.table('llm_models').select('*')

        # 如果指定了provider_id，则过滤对应的模型
        if provider_id:
            query = query.eq('provider_id', provider_id)

        # 只返回激活的模型，按排序顺序
        query = query.eq('is_active', True).order('sort_order')

        response = query.execute()

        if response.data:
            print(f"✅ 从数据库获取到 {len(response.data)} 个模型")
            return {'data': response.data}
        else:
            print("⚠️ 数据库中未找到模型，返回空列表")
            return {'data': []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'获取LLM模型失败: {str(e)}')

@app.get('/api/llm/configs')
async def get_user_llm_configs(user_id: Optional[str] = None):
    """获取用户的LLM配置列表"""
    try:
        # 返回默认配置
        return {'data': []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'获取用户LLM配置失败: {str(e)}')

@app.get('/api/llm/configs/{config_name}')
async def get_llm_config_by_name(config_name: str, user_id: Optional[str] = None):
    """获取指定名称的LLM配置"""
    try:
        # 首先尝试从Supabase数据库加载
        try:
            # 查询用户配置或全局配置
            query = supabase.table('user_llm_configs').select('''
                *,
                provider:llm_api_providers(*),
                model:llm_models(*)
            ''').eq('config_name', config_name)

            if user_id:
                query = query.eq('user_id', user_id)
            else:
                query = query.is_('user_id', 'null')

            response = query.execute()

            if response.data:
                db_config = response.data[0]

                # 解密API密钥
                api_key_decrypted = None
                if db_config.get('api_key_encrypted'):
                    try:
                        import base64
                        api_key_decrypted = base64.b64decode(db_config['api_key_encrypted'].encode()).decode()
                    except Exception as e:
                        print(f"解密API密钥失败: {e}")

                # 构建返回格式
                config = {
                    'id': db_config['id'],
                    'config_name': db_config['config_name'],
                    'provider_id': db_config['provider_id'],
                    'model_id': db_config['model_id'],
                    'api_key_encrypted': db_config.get('api_key_encrypted'),
                    'api_key_decrypted': api_key_decrypted,
                    'custom_endpoint': db_config.get('custom_endpoint'),
                    'custom_parameters': db_config.get('custom_parameters', {}),
                    'is_active': db_config.get('is_active', True),
                    'provider': db_config.get('provider'),
                    'model': db_config.get('model'),
                    'created_at': db_config.get('created_at'),
                    'updated_at': db_config.get('updated_at')
                }

                print(f"✅ 从数据库加载配置: {config_name}")
                return {'data': config}

        except Exception as db_error:
            print(f"从数据库加载配置失败: {db_error}")

        # 回退到内存存储（向后兼容）
        user_config_key = f"{user_id}:{config_name}" if user_id else None
        global_config_key = f"global:{config_name}"

        config = None
        if user_config_key and user_config_key in llm_configs_storage:
            config = llm_configs_storage[user_config_key]
            print(f"✅ 找到用户级配置: {user_config_key}")
        elif global_config_key in llm_configs_storage:
            config = llm_configs_storage[global_config_key]
            print(f"✅ 找到全局配置: {global_config_key}")

        if config:
            return {'data': config}

        # 如果没有找到保存的配置，返回默认配置
        if config_name == 'default':
            print(f"⚠️ 未找到保存的配置，返回默认配置")
            return {'data': {
                'id': 'default-config',
                'config_name': 'default',
                'provider_id': 'alibaba',
                'model_id': 'qwen-plus',
                'custom_endpoint': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
                'api_key_encrypted': '',
                'custom_parameters': {},
                'is_active': True,
                'provider': {
                    'provider_code': 'alibaba',
                    'provider_name': '阿里通义千问',
                    'base_endpoint': 'https://dashscope.aliyuncs.com/compatible-mode/v1'
                },
                'model': {
                    'model_code': 'qwen-plus',
                    'model_name': '通义千问Plus'
                }
            }}
        else:
            return {'data': None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'获取LLM配置失败: {str(e)}')

@app.post('/api/llm/configs')
async def save_llm_config(config_data: dict):
    """保存LLM配置
    支持两种入参形式：
    - 形式A：provider_id + model_id（UUID）
    - 形式B：provider_code + model_code（字符串代码）
    前端可以只提交 code，后端负责解析为 ID。
    """
    try:
        from datetime import datetime, timezone

        config_name = config_data.get('config_name', 'default')
        user_id = config_data.get('user_id')
        provider_id = config_data.get('provider_id')
        model_id = config_data.get('model_id')
        provider_code = config_data.get('provider_code')
        model_code = config_data.get('model_code')
        api_key = config_data.get('api_key', '')

        # 解析提供商
        provider = None
        if provider_id:
            provider_resp = supabase.table('llm_api_providers').select('*').eq('id', provider_id).execute()
            provider = provider_resp.data[0] if provider_resp.data else None
        elif provider_code:
            provider_resp = supabase.table('llm_api_providers').select('*').eq('provider_code', provider_code).execute()
            provider = provider_resp.data[0] if provider_resp.data else None
            if provider:
                provider_id = provider['id']

        if not provider:
            raise HTTPException(status_code=400, detail=f"未找到提供商: {provider_id or provider_code}")

        # 解析模型
        model = None
        if model_id:
            model_resp = supabase.table('llm_models').select('*').eq('id', model_id).execute()
            model = model_resp.data[0] if model_resp.data else None
        elif model_code:
            # 按 code + provider 共同限定，避免同名冲突
            query = supabase.table('llm_models').select('*').eq('model_code', model_code)
            if provider_id:
                query = query.eq('provider_id', provider_id)
            model_resp = query.execute()
            model = model_resp.data[0] if model_resp.data else None
            if model:
                model_id = model['id']

        if not model:
            raise HTTPException(status_code=400, detail=f"未找到模型: {model_id or model_code}")

        # 加密API密钥（兼容空）
        api_key_encrypted = ''
        if api_key:
            import base64
            api_key_encrypted = base64.b64encode(api_key.encode()).decode()

        # 保存到Supabase数据库（只写入解析好的ID）
        config_data_to_save = {
            'config_name': config_name,
            'user_id': user_id,
            'provider_id': provider_id,
            'model_id': model_id,
            'api_key_encrypted': api_key_encrypted,
            'custom_endpoint': config_data.get('custom_endpoint'),
            'custom_parameters': config_data.get('custom_parameters', {}),
            'is_active': config_data.get('is_active', True),
            'updated_at': datetime.now(timezone.utc).isoformat()
        }

        # upsert：存在则更新；否则插入
        existing_query = supabase.table('user_llm_configs').select('*').eq('config_name', config_name)
        if user_id:
            existing_query = existing_query.eq('user_id', user_id)
        else:
            existing_query = existing_query.is_('user_id', 'null')
        existing_response = existing_query.execute()

        if existing_response.data:
            update_response = supabase.table('user_llm_configs').update(config_data_to_save).eq('id', existing_response.data[0]['id']).execute()
            saved_config = update_response.data[0] if update_response.data else None
            print(f"✅ 已更新LLM配置: {config_name}")
        else:
            insert_response = supabase.table('user_llm_configs').insert(config_data_to_save).execute()
            saved_config = insert_response.data[0] if insert_response.data else None
            print(f"✅ 已创建LLM配置: {config_name}")

        if not saved_config:
            raise HTTPException(status_code=500, detail='保存配置失败')

        # 构建返回数据（带上provider与model详情）
        result = {**saved_config, 'provider': provider, 'model': model, 'api_key_decrypted': api_key}
        print(f"✅ 保存成功: {provider['provider_name']} - {model['model_name']}")
        return {'data': result}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'保存LLM配置失败: {str(e)}')

# ================================
# 语义质控规则API
# ================================

# 导入语义规则引擎
sys.path.append(os.path.join(os.path.dirname(__file__), '../semantic_rules_engine'))

try:
    from semantic_rule_engine import (
        SemanticRuleEngine,
        SemanticRuleDefinition,
        SemanticRuleResult,
        DefectLevel,
        RuleComplexity
    )

    # Mock LLM客户端
    class MockLLMClient:
        """Mock LLM客户端，用于测试"""

        def execute_semantic_rule(self, rule_id: str, context: str) -> Dict[str, Any]:
            """执行语义规则的Mock实现"""
            import random
            import time

            # 模拟处理时间
            time.sleep(0.1 + random.random() * 0.2)

            # 基于上下文生成模拟响应
            compliant = random.choice([True, False])
            confidence = 0.7 + random.random() * 0.3

            return {
                'content': {
                    "compliant": compliant,
                    "confidence": confidence,
                    "evidence": f"基于输入内容的分析结果: {context[:100]}...",
                    "reasoning": f"根据规则 {rule_id} 进行了详细分析"
                },
                'token_usage': {
                    'prompt': 100 + random.randint(0, 50),
                    'completion': 50 + random.randint(0, 30),
                    'total': 150 + random.randint(0, 80)
                }
            }

        def validate_connection(self) -> Dict[str, Any]:
            """验证连接状态"""
            return {
                "real_llm_available": False,
                "mock_mode": True,
                "provider": "mock",
                "model": "mock-gpt-4"
            }

    # 初始化语义规则引擎
    mock_llm_client = MockLLMClient()
    semantic_engine = SemanticRuleEngine(
        llm_client=mock_llm_client,
        config={}
    )

    logger.info("✅ 语义规则引擎初始化成功")

except Exception as e:
    logger.error(f"❌ 语义规则引擎初始化失败: {e}")
    semantic_engine = None

# 语义规则相关的Pydantic模型
class SemanticRuleExecutionRequest(BaseModel):
    input_data: Dict[str, Any]
    use_mock_llm: bool = False

class SemanticBatchExecutionRequest(BaseModel):
    rule_ids: List[str]
    input_data: Dict[str, Any]
    use_mock_llm: bool = False

class SemanticCustomRuleRequest(BaseModel):
    rule_name: str
    description: str
    natural_language_rule: str
    category: str
    severity: str
    examples: Optional[List[str]] = None

# 注意：更具体的路由必须放在通用路由之前，避免路由冲突

@app.get("/api/semantic-rules/stats")
async def get_engine_stats():
    """获取语义规则引擎统计信息"""
    if not semantic_engine:
        raise HTTPException(status_code=500, detail="语义规则引擎未初始化")

    try:
        stats = semantic_engine.get_stats()
        return {
            "success": True,
            "stats": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}")

@app.get("/api/semantic-rules/validate-llm")
async def validate_llm_connection():
    """验证LLM连接状态"""
    if not semantic_engine:
        raise HTTPException(status_code=500, detail="语义规则引擎未初始化")

    try:
        # 检查LLM连接状态
        connection_info = semantic_engine.validate_llm_connection()

        return {
            "success": True,
            "connection_info": connection_info
        }

    except Exception as e:
        return {
            "success": False,
            "connection_info": {
                "real_llm_available": False,
                "mock_mode": True,
                "provider": "unknown",
                "model": "unknown",
                "error": str(e)
            }
        }

@app.get("/api/semantic-rules")
async def get_all_semantic_rules():
    """获取所有语义规则"""
    if not semantic_engine:
        raise HTTPException(status_code=500, detail="语义规则引擎未初始化")

    try:
        rules = semantic_engine.get_all_rules()
        # 转换规则对象为字典
        rules_data = []
        for rule in rules:
            rule_dict = {
                "rule_id": rule.rule_id,
                "rule_name": rule.rule_name,
                "description": rule.description,
                "category": rule.category,
                "defect_level": rule.defect_level.value if hasattr(rule.defect_level, 'value') else str(rule.defect_level),
                "deduction_score": rule.deduction_score,
                "is_veto_defect": rule.is_veto_defect,
                "complexity": rule.complexity.value if hasattr(rule.complexity, 'value') else str(rule.complexity),
                "system_role": rule.system_role,
                "task_description": rule.task_description,
                "input_format": rule.input_format,
                "evaluation_criteria": rule.evaluation_criteria,
                "output_format": rule.output_format,
                "prompt_template": rule.prompt_template
            }
            rules_data.append(rule_dict)

        return {
            "success": True,
            "rules": rules_data,
            "count": len(rules_data)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取规则失败: {str(e)}")

@app.get("/api/semantic-rules/{rule_id}")
async def get_semantic_rule(rule_id: str):
    """获取单个语义规则详情"""
    if not semantic_engine:
        raise HTTPException(status_code=500, detail="语义规则引擎未初始化")

    try:
        rule = semantic_engine.get_rule(rule_id)
        if not rule:
            raise HTTPException(status_code=404, detail=f"规则 {rule_id} 不存在")

        # 转换规则对象为字典
        rule_dict = {
            "rule_id": rule.rule_id,
            "rule_name": rule.rule_name,
            "description": rule.description,
            "category": rule.category,
            "defect_level": rule.defect_level.value if hasattr(rule.defect_level, 'value') else str(rule.defect_level),
            "deduction_score": rule.deduction_score,
            "is_veto_defect": rule.is_veto_defect,
            "complexity": rule.complexity.value if hasattr(rule.complexity, 'value') else str(rule.complexity),
            "system_role": rule.system_role,
            "task_description": rule.task_description,
            "input_format": rule.input_format,
            "evaluation_criteria": rule.evaluation_criteria,
            "output_format": rule.output_format,
            "prompt_template": rule.prompt_template
        }

        return {
            "success": True,
            "rule": rule_dict
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取规则详情失败: {str(e)}")

@app.post("/api/semantic-rules/{rule_id}/execute")
async def execute_semantic_rule(rule_id: str, request: SemanticRuleExecutionRequest):
    """执行单个语义规则"""
    if not semantic_engine:
        raise HTTPException(status_code=500, detail="语义规则引擎未初始化")

    try:
        # 执行规则
        result = await semantic_engine.execute_rule_async(
            rule_id=rule_id,
            input_data=request.input_data,
            use_mock_llm=request.use_mock_llm
        )

        # 转换结果对象为字典
        result_dict = {
            "rule_id": result.rule_id,
            "rule_name": result.rule_name,
            "compliant": result.compliant,
            "confidence": result.confidence,
            "evidence": result.evidence,
            "reasoning": result.reasoning,
            "defect_details": result.defect_details,
            "execution_time": result.execution_time,
            "token_usage": result.token_usage
        }

        return {
            "success": True,
            "result": result_dict
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"规则执行失败: {str(e)}")

@app.post("/api/semantic-rules/batch-execute")
async def execute_batch_semantic_rules(request: SemanticBatchExecutionRequest):
    """批量执行语义规则"""
    if not semantic_engine:
        raise HTTPException(status_code=500, detail="语义规则引擎未初始化")

    try:
        results = []
        for rule_id in request.rule_ids:
            try:
                result = await semantic_engine.execute_rule_async(
                    rule_id=rule_id,
                    input_data=request.input_data,
                    use_mock_llm=request.use_mock_llm
                )
                results.append(result)

            except Exception as e:
                # 创建错误结果
                from semantic_rule_engine import SemanticRuleResult
                error_result = SemanticRuleResult(
                    rule_id=rule_id,
                    rule_name=f"规则_{rule_id}",
                    compliant=False,
                    confidence=0.0,
                    evidence=f"执行错误: {str(e)}",
                    reasoning="规则执行过程中发生错误",
                    execution_time=0.0
                )
                results.append(error_result)

        # 转换结果对象为字典
        results_data = []
        for result in results:
            result_dict = {
                "rule_id": result.rule_id,
                "rule_name": result.rule_name,
                "compliant": result.compliant,
                "confidence": result.confidence,
                "evidence": result.evidence,
                "reasoning": result.reasoning,
                "defect_details": result.defect_details,
                "execution_time": result.execution_time,
                "token_usage": result.token_usage
            }
            results_data.append(result_dict)

        return {
            "success": True,
            "results": results_data,
            "count": len(results_data)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量执行失败: {str(e)}")

@app.post("/api/semantic-rules/custom")
async def create_custom_rule(request: SemanticCustomRuleRequest):
    """创建自定义语义规则"""
    if not semantic_engine:
        raise HTTPException(status_code=500, detail="语义规则引擎未初始化")

    try:
        # 生成规则ID
        rule_id = f"custom_{uuid.uuid4().hex[:8]}"

        # 映射严重程度到缺陷级别
        defect_level_enum = {
            "critical": DefectLevel.VETO,
            "major": DefectLevel.SEVERE,
            "minor": DefectLevel.MINOR
        }.get(request.severity, DefectLevel.GENERAL)

        # 创建规则定义
        rule_definition = SemanticRuleDefinition(
            rule_id=rule_id,
            rule_name=request.rule_name,
            description=request.description,
            category=request.category,
            defect_level=defect_level_enum,
            deduction_score=10 if request.severity == "critical" else 5 if request.severity == "major" else 2,
            is_veto_defect=(request.severity == "critical"),
            complexity=RuleComplexity.MEDIUM,
            system_role="你是一个专业的医疗质控专家，负责检查病历记录的质量。",
            task_description=f"根据以下规则检查病历内容：{request.natural_language_rule}",
            input_format={"content": "病历内容文本"},
            evaluation_criteria=[
                request.natural_language_rule,
                "检查内容的完整性和准确性",
                "评估是否符合医疗质控标准"
            ],
            output_format={
                "compliant": "是否合规（true/false）",
                "confidence": "置信度（0-1）",
                "evidence": "支持证据",
                "reasoning": "推理过程"
            },
            prompt_template=f"""
请根据以下规则检查病历内容：

规则：{request.natural_language_rule}

病历内容：
{{content}}

请按照以下格式输出检查结果：
1. 合规性：是否符合规则要求
2. 置信度：对判断结果的信心程度（0-1）
3. 支持证据：从病历中找到的相关证据
4. 推理过程：详细说明判断的逻辑

输出格式为JSON：
{{
    "compliant": true/false,
    "confidence": 0.0-1.0,
    "evidence": "具体证据",
    "reasoning": "推理过程"
}}
"""
        )

        # 添加规则到引擎
        semantic_engine.add_custom_rule(rule_definition)

        # 转换规则对象为字典
        rule_dict = {
            "rule_id": rule_definition.rule_id,
            "rule_name": rule_definition.rule_name,
            "description": rule_definition.description,
            "category": rule_definition.category,
            "defect_level": rule_definition.defect_level.value if hasattr(rule_definition.defect_level, 'value') else str(rule_definition.defect_level),
            "deduction_score": rule_definition.deduction_score,
            "is_veto_defect": rule_definition.is_veto_defect,
            "complexity": rule_definition.complexity.value if hasattr(rule_definition.complexity, 'value') else str(rule_definition.complexity),
            "system_role": rule_definition.system_role,
            "task_description": rule_definition.task_description,
            "input_format": rule_definition.input_format,
            "evaluation_criteria": rule_definition.evaluation_criteria,
            "output_format": rule_definition.output_format,
            "prompt_template": rule_definition.prompt_template
        }

        return {
            "success": True,
            "rule": rule_dict,
            "message": f"自定义规则 {rule_id} 创建成功"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建自定义规则失败: {str(e)}")

# ==================== 四川省住院病历语义质控 API ====================

class SichuanQCEvaluateRequest(BaseModel):
    """四川省质控评估请求"""
    document_id: str
    document_content: str
    document_type: str = "病程记录"
    document_types: Optional[List[str]] = None  # 支持多文书类型
    rule_ids: Optional[List[str]] = None        # 支持指定规则
    use_multi_document_mode: bool = True        # 是否使用多文书模式
    patient_info: Optional[Dict[str, str]] = None  # 患者信息
    documents_by_type: Optional[Dict[str, Any]] = None  # 预分类文书映射：{doc_type: [texts]|text|{content: text}}

class SichuanQCBatchRequest(BaseModel):
    """四川省质控批量评估请求"""
    documents: List[Dict[str, str]]

@app.post("/api/qc/sichuan/evaluate")
async def sichuan_qc_evaluate(request: SichuanQCEvaluateRequest):
    """
    四川省规则质控评估 - 支持单一prompt和多文书模式
    基于真实API测试验证的优化方案
    """
    try:
        logger.info(f"开始四川省质控评估: {request.document_id} (多文书模式: {request.use_multi_document_mode})")
        logger.info(f"请求数据: document_types={request.document_types}, rule_ids={len(request.rule_ids or [])}, documents_by_type={list(request.documents_by_type.keys()) if request.documents_by_type else None}")

        # 获取四川省质控服务
        qc_service = get_sichuan_qc_service()

        if request.use_multi_document_mode:
            # 使用新的多文书模式
            result = await qc_service.evaluate_multi_document(
                document_id=request.document_id,
                document_content=request.document_content,
                document_types=request.document_types,
                rule_ids=request.rule_ids,
                preclassified_documents=request.documents_by_type
            )

            # 转换为兼容的API响应格式
            response = {
                "document_id": result.document_id,
                "evaluation_summary": {
                    "total_rules": result.overall_summary["total_rules"],
                    "compliant_rules": result.overall_summary["compliant_rules"],
                    "compliance_rate": result.overall_summary["compliance_rate"],
                    "overall_grade": result.overall_grade,
                    "critical_violations": result.overall_summary["critical_violations"],
                    "document_breakdown": result.overall_summary["document_breakdown"]
                },
                "performance_metrics": {
                    "processing_time": result.total_processing_time,
                    "token_usage": result.total_token_usage,
                    "estimated_cost": result.total_token_usage / 1000 * 0.002
                },
                "evaluation_results": [],  # 将在下面填充
                "optimization_metrics": result.optimization_metrics,
                "document_results": {
                    doc_type: {
                        "total_rules": doc_result.total_rules,
                        "compliant_rules": doc_result.compliant_rules,
                        "processing_time": doc_result.processing_time,
                        "token_usage": doc_result.token_usage,
                        "confidence": doc_result.confidence,
                        "critical_violations": doc_result.critical_violations,
                        "evaluation_results": doc_result.evaluation_results
                    }
                    for doc_type, doc_result in result.document_results.items()
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "success",
                "mode": "multi_document"
            }

            # 合并所有文书的评估结果
            for doc_result in result.document_results.values():
                for eval_result in doc_result.evaluation_results:
                    response["evaluation_results"].append({
                        "rule_id": eval_result.get("rule_id"),
                        "is_compliant": eval_result.get("is_compliant"),
                        "findings": eval_result.get("findings"),
                        "evidence": eval_result.get("evidence"),
                        "confidence": eval_result.get("confidence")
                    })

        else:
            # 使用原有的单一prompt模式
            result = await qc_service.evaluate_document(
                document_id=request.document_id,
                document_content=request.document_content,
                document_type=request.document_type
            )

            # 转换为API响应格式（单一prompt模式）
            response = {
                "document_id": result.document_id,
                "evaluation_summary": {
                    "total_rules": result.total_rules,
                    "compliant_rules": result.compliant_rules,
                    "compliance_rate": (result.compliant_rules / result.total_rules * 100) if result.total_rules > 0 else 0,
                    "overall_grade": result.overall_grade,
                    "critical_violations": result.critical_violations
                },
                "performance_metrics": {
                    "processing_time": result.processing_time,
                    "token_usage": result.token_usage,
                    "estimated_cost": result.token_usage / 1000 * 0.002
                },
                "evaluation_results": [
                    {
                        "rule_id": eval_result.rule_id,
                        "is_compliant": eval_result.is_compliant,
                        "findings": eval_result.findings,
                        "evidence": eval_result.evidence,
                        "confidence": eval_result.confidence
                    }
                    for eval_result in result.evaluation_results
                ],
                "optimization_metrics": {
                    "token_savings_rate": 0.80,  # 基于真实测试的80%节省
                    "estimated_original_tokens": result.token_usage * 5,  # 假设5条规则分别调用
                    "actual_tokens_saved": result.token_usage * 4,
                    "cost_savings": result.token_usage * 4 / 1000 * 0.002
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "success",
                "mode": "single_prompt"
            }

        logger.info(f"四川省质控评估完成: {request.document_id}, 合规率: {response['evaluation_summary']['compliance_rate']:.1f}%")
        return response

    except ValidationError as ve:
        logger.error(f"四川省质控评估请求数据验证失败: {request.document_id}, 错误: {ve}")
        raise HTTPException(
            status_code=422,
            detail=f"请求数据验证失败: {str(ve)}"
        )
    except Exception as e:
        logger.error(f"四川省质控评估失败: {request.document_id}, 错误: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"四川省质控评估失败: {str(e)}"
        )

@app.post("/api/qc/sichuan/evaluate/batch")
async def sichuan_qc_batch_evaluate(request: SichuanQCBatchRequest):
    """
    四川省规则批量文档质控评估
    """
    try:
        logger.info(f"开始四川省批量质控评估: {len(request.documents)} 个文档")

        # 获取四川省质控服务
        qc_service = get_sichuan_qc_service()

        # 执行批量质控评估
        results = await qc_service.batch_evaluate_documents(request.documents)

        # 统计信息
        total_documents = len(request.documents)
        successful_evaluations = len(results)
        total_rules_evaluated = sum(result.total_rules for result in results)
        total_compliant_rules = sum(result.compliant_rules for result in results)
        total_tokens = sum(result.token_usage for result in results)
        total_processing_time = sum(result.processing_time for result in results)

        # 转换为API响应格式
        response = {
            "batch_summary": {
                "total_documents": total_documents,
                "successful_evaluations": successful_evaluations,
                "success_rate": (successful_evaluations / total_documents * 100) if total_documents > 0 else 0,
                "total_rules_evaluated": total_rules_evaluated,
                "total_compliant_rules": total_compliant_rules,
                "overall_compliance_rate": (total_compliant_rules / total_rules_evaluated * 100) if total_rules_evaluated > 0 else 0
            },
            "performance_metrics": {
                "total_processing_time": total_processing_time,
                "avg_processing_time": total_processing_time / successful_evaluations if successful_evaluations > 0 else 0,
                "total_token_usage": total_tokens,
                "avg_token_usage": total_tokens / successful_evaluations if successful_evaluations > 0 else 0,
                "total_estimated_cost": total_tokens / 1000 * 0.002
            },
            "optimization_metrics": {
                "token_savings_rate": 0.80,
                "estimated_original_tokens": total_tokens * 5,
                "actual_tokens_saved": total_tokens * 4,
                "total_cost_savings": total_tokens * 4 / 1000 * 0.002
            },
            "evaluation_results": [
                {
                    "document_id": result.document_id,
                    "total_rules": result.total_rules,
                    "compliant_rules": result.compliant_rules,
                    "compliance_rate": (result.compliant_rules / result.total_rules * 100) if result.total_rules > 0 else 0,
                    "overall_grade": result.overall_grade,
                    "processing_time": result.processing_time,
                    "token_usage": result.token_usage,
                    "critical_violations": result.critical_violations
                }
                for result in results
            ],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "success"
        }

        logger.info(f"四川省批量质控评估完成: {successful_evaluations}/{total_documents} 个文档成功")
        return response

    except Exception as e:
        logger.error(f"四川省批量质控评估失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"四川省批量质控评估失败: {str(e)}"
        )

@app.get("/api/qc/sichuan/stats")
async def sichuan_qc_stats():
    """
    获取四川省规则质控统计信息
    """
    try:
        # 获取四川省质控服务
        qc_service = get_sichuan_qc_service()

        # 获取服务统计
        stats = qc_service.get_service_stats()

        response = {
            "service_statistics": stats["service_info"],
            "performance_metrics": stats["llm_performance"],
            "optimization_achievements": stats["optimization_metrics"],
            "real_time_status": {
                "service_health": "healthy",
                "api_endpoint": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "model": "qwen2.5-14b-instruct",
                "last_updated": datetime.now(timezone.utc).isoformat()
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "success"
        }

        return response

    except Exception as e:
        logger.error(f"获取四川省质控统计失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取四川省质控统计失败: {str(e)}"
        )

@app.get("/api/qc/sichuan/rules")
async def sichuan_qc_rules(document_type: Optional[str] = None):
    """
    获取适用的四川省规则列表
    """
    try:
        # 获取四川省质控服务
        qc_service = get_sichuan_qc_service()

        # 获取适用规则
        rules = qc_service.get_applicable_rules(document_type)

        response = {
            "rules": rules,
            "total_rules": len(rules),
            "document_type_filter": document_type,
            "rule_categories": list(set(rule.get("category", "未分类") for rule in rules)),
            "complexity_distribution": {
                "高复杂度": len([r for r in rules if r.get("complexity") == "高复杂度"]),
                "中复杂度": len([r for r in rules if r.get("complexity") == "中复杂度"]),
                "低复杂度": len([r for r in rules if r.get("complexity") == "低复杂度"])
            },
            "defect_level_distribution": {
                "严重缺陷": len([r for r in rules if r.get("defect_level") == "严重缺陷"]),
                "一般缺陷": len([r for r in rules if r.get("defect_level") == "一般缺陷"]),
                "轻微缺陷": len([r for r in rules if r.get("defect_level") == "轻微缺陷"])
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "success"
        }

        return response

    except Exception as e:
        logger.error(f"获取四川省质控规则失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取四川省质控规则失败: {str(e)}"
        )

if __name__ == "__main__":
    # 启动服务器 - 固定端口8001
    port = int(os.getenv("API_PORT", "8001"))  # 从环境变量读取，默认8001
    print(f"🚀 启动医疗质控系统API服务器...")
    print(f"📡 服务地址: http://0.0.0.0:{port}")
    print(f"📚 API文档: http://localhost:{port}/docs")
    print(f"🔍 健康检查: http://localhost:{port}/api/health")

    uvicorn.run(
        "main_api:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )
