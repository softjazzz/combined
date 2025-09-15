"""
智慧医保质控系统 - 独立后端服务
基于 FastAPI 的医保规则管理和质控分析 API 服务
端口: 8002 (独立于 medqc 后端的 8001 端口)
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import uuid

from fastapi import FastAPI, HTTPException, Depends, status, Form, File, UploadFile
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from jose import jwt, JWTError
import uvicorn

# Supabase 集成
from supabase import create_client, Client

# 认证工具
from auth_utils import (
    get_current_user, authenticate_user, create_access_token,
    verify_password, get_password_hash, DEMO_USERS, pwd_context,
    ACCESS_TOKEN_EXPIRE_MINUTES, SECRET_KEY, ALGORITHM
)

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== 配置和环境变量 ====================

# Supabase 配置
SUPABASE_URL = os.getenv("VITE_SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("VITE_SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

# ==================== Supabase 客户端初始化 ====================

supabase: Optional[Client] = None
if SUPABASE_URL and SUPABASE_ANON_KEY:
    try:
        # 优先使用 Service Role Key，回退到 Anon Key
        api_key = SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY
        supabase = create_client(SUPABASE_URL, api_key)
        logger.info(f"Supabase 客户端初始化成功: {SUPABASE_URL}")
    except Exception as e:
        logger.warning(f"Supabase 客户端初始化失败，将使用 Mock 数据: {e}")
        supabase = None
else:
    logger.warning("Supabase 配置缺失，将使用 Mock 数据")

# ==================== FastAPI 应用初始化 ====================

app = FastAPI(
    title="智慧医保质控系统 API",
    description="医保规则管理和质控分析的独立后端服务",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS 配置
ALLOWED_ORIGINS = [
    "http://localhost:3008",
    "http://localhost:3009",
    "http://localhost:3010",
    "http://127.0.0.1:3008",
    "http://127.0.0.1:3009",
    "http://127.0.0.1:3010",
    "http://43.163.116.243:3008",
    "http://43.163.116.243:3009",
    "http://43.163.116.243:3010",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== 数据模型 ====================

class LoginRequest(BaseModel):
    email: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: int
    user: Optional[Dict[str, Any]] = None

class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str
    department: Optional[str] = None
    roles: List[str] = []

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    display_name: str
    department: Optional[str] = None
    role: Optional[str] = "user"

# ==================== Mock 用户数据 ====================
# 用户数据已移至 auth_utils.py

# ==================== 工具函数 ====================
# 认证相关函数已移至 auth_utils.py

# ==================== 测试数据文件路径解析 ====================

def _resolve_test_data_file(filename: str = 'test_medical_records.json') -> str | None:
    """查找测试数据文件，优先使用 backend/test_data，
    若不存在则回退到 tests/backend/test_data。
    返回可用路径或 None。
    """
    try:
        base_dir = os.path.dirname(__file__)
        primary = os.path.join(base_dir, 'test_data', filename)
        if os.path.exists(primary):
            return primary
        fallback = os.path.abspath(os.path.join(base_dir, '..', 'tests', 'backend', 'test_data', filename))
        if os.path.exists(fallback):
            return fallback
    except Exception:
        pass
    return None

# ==================== 基础路由 ====================

@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "智慧医保质控系统 API",
        "version": "1.0.0",
        "service": "yibao-backend",
        "port": 8002,
        "docs": "/docs",
        "health": "/api/health",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/api/health")
async def health_check():
    """健康检查"""
    supabase_status = "connected" if supabase else "not_configured"

    return {
        "status": "healthy",
        "service": "yibao-backend",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "supabase_status": supabase_status,
        "features": {
            "authentication": True,
            "rule_management": True,
            "sandbox_testing": True,
            "statistics": True
        },
        "message": "智慧医保质控系统后端服务运行正常"
    }

# ==================== 认证 API ====================

@app.options("/api/auth/login")
async def login_options():
    """处理登录接口的CORS预检请求"""
    return {"message": "OK"}

@app.post("/api/auth/login", response_model=LoginResponse)
async def login(login_data: LoginRequest):
    """用户登录"""
    user = authenticate_user(login_data.email, login_data.password)
    if not user:
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
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user={
            "id": user["id"],
            "email": user["email"],
            "display_name": user["display_name"],
            "department": user["department"],
            "roles": user["roles"]
        }
    )

@app.get("/api/auth/me", response_model=UserResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """获取当前用户信息"""
    return UserResponse(
        id=current_user["id"],
        email=current_user["email"],
        display_name=current_user["display_name"],
        department=current_user["department"],
        roles=current_user["roles"]
    )

@app.post("/api/auth/logout")
async def logout():
    """用户登出"""
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

        user = DEMO_USERS.get(email)
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
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的刷新令牌"
        )

# ==================== 注册路由 ====================

# 导入并注册规则管理路由
def register_rules_router():
    try:
        # 延迟导入并注入 Supabase 客户端，避免循环依赖
        import rules_api
        try:
            rules_api.set_supabase(supabase)
        except Exception:
            # 注入失败不影响 Mock 模式
            pass
        app.include_router(rules_api.router)
        logger.info("规则管理路由注册成功")
    except ImportError as e:
        logger.warning(f"无法导入规则管理路由: {e}")

# 延迟注册路由
register_rules_router()

# 注册质控引擎路由
def register_engine_router():
    try:
        # 延迟导入并初始化引擎
        from engine.api import router as engine_router, initialize_engine

        # 初始化引擎（使用 Supabase 客户端）
        initialize_engine(supabase)

        # 注册路由
        app.include_router(engine_router)
        logger.info("质控引擎路由注册成功")
    except ImportError as e:
        logger.warning(f"无法导入质控引擎路由: {e}")
    except Exception as e:
        logger.error(f"质控引擎初始化失败: {e}")

register_engine_router()

# ==================== 病历管理 API ====================

@app.get("/api/medical-records")
async def get_medical_records(
    page: int = 1,
    page_size: int = 20,
    current_user: dict = Depends(get_current_user)
):
    """获取病历列表"""
    try:
        # 加载测试病历数据
        import json
        import os

        test_data_file = _resolve_test_data_file()

        if os.path.exists(test_data_file):
            with open(test_data_file, 'r', encoding='utf-8') as f:
                test_records = json.load(f)

            # 转换数据格式以匹配前端期望
            formatted_records = []
            for i, record in enumerate(test_records):
                patient = record.get('patient', {})
                visit = record.get('visit', {})
                drug_orders = record.get('drug_orders', [])
                test_scenario = record.get('test_scenario', {})

                formatted_record = {
                    'id': record.get('record_id', f'MR_{i+1}'),
                    'name': f"{patient.get('name', '测试患者')}病历",
                    'patient_name': patient.get('name', '测试患者'),
                    'patient_id': patient.get('patient_id', f'P{i+1:03d}'),
                    'department': visit.get('department', '内科'),
                    'record_type': visit.get('visit_type', '门诊'),
                    'disease_type': '测试疾病',
                    'complexity_level': '中等',
                    'status': 'completed',
                    'qc_score': 85 + (i % 15),  # 85-99分
                    'expected_grade': 'A' if (85 + (i % 15)) >= 90 else 'B',
                    'expected_score': 90,
                    'content': f"患者{patient.get('name', '测试患者')}，{patient.get('gender', '男')}，{patient.get('age', 30)}岁...",
                    'created_at': record.get('created_at', '2025-09-11 15:30'),
                    'updated_at': record.get('created_at', '2025-09-11 15:30'),
                    'created_by': '测试医生',
                    'tags': [test_scenario.get('rule_type', '测试'), visit.get('visit_type', '门诊')],
                    'medical_insurance_type': patient.get('insurance_type', '城镇职工'),
                    'cost_amount': sum(order.get('total_amount', 0) for order in drug_orders),
                    'violation_risk': test_scenario.get('expected_result', 'pass'),
                    'test_scenario': test_scenario.get('name', ''),
                    'age': patient.get('age', 30),
                    'gender': patient.get('gender', '男'),
                    'drug_count': len(drug_orders)
                }
                formatted_records.append(formatted_record)

            # 分页处理
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            paginated_records = formatted_records[start_idx:end_idx]

            return {
                "data": paginated_records,
                "total": len(formatted_records),
                "page": page,
                "page_size": page_size,
                "total_pages": (len(formatted_records) + page_size - 1) // page_size
            }
        else:
            # 如果测试数据文件不存在，返回空数据
            return {
                "data": [],
                "total": 0,
                "page": page,
                "page_size": page_size,
                "total_pages": 0
            }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取病历数据失败: {str(e)}"
        )

@app.get("/api/medical-records/{record_id}")
async def get_medical_record(
    record_id: str,
    current_user: dict = Depends(get_current_user)
):
    """获取单个病历详情"""
    try:
        # 加载测试病历数据
        import json
        import os

        test_data_file = _resolve_test_data_file()

        if os.path.exists(test_data_file):
            with open(test_data_file, 'r', encoding='utf-8') as f:
                test_records = json.load(f)

            # 查找对应的病历
            for record in test_records:
                if record.get('record_id') == record_id:
                    return record

            raise HTTPException(
                status_code=404,
                detail="病历不存在"
            )
        else:
            raise HTTPException(
                status_code=404,
                detail="测试数据文件不存在"
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取病历详情失败: {str(e)}"
        )

@app.get("/api/medical-records/statistics/overview")
async def get_medical_records_statistics(
    current_user: dict = Depends(get_current_user)
):
    """获取病历统计概览"""
    try:
        # 加载测试病历数据
        import json
        import os

        test_data_file = _resolve_test_data_file()

        if os.path.exists(test_data_file):
            with open(test_data_file, 'r', encoding='utf-8') as f:
                test_records = json.load(f)

            # 统计分析
            total_records = len(test_records)

            # 按测试场景分类统计
            scenario_stats = {}
            risk_stats = {'pass': 0, 'info': 0, 'warn': 0, 'block': 0}
            age_stats = {'儿童': 0, '成年': 0, '老年': 0}
            gender_stats = {'男': 0, '女': 0}

            for record in test_records:
                # 测试场景统计
                scenario = record.get('test_scenario', {})
                scenario_name = scenario.get('name', '未知场景')
                scenario_stats[scenario_name] = scenario_stats.get(scenario_name, 0) + 1

                # 风险等级统计
                expected_result = scenario.get('expected_result', 'pass')
                if expected_result in risk_stats:
                    risk_stats[expected_result] += 1

                # 年龄统计
                patient = record.get('patient', {})
                age = patient.get('age', 30)
                if age < 18:
                    age_stats['儿童'] += 1
                elif age < 60:
                    age_stats['成年'] += 1
                else:
                    age_stats['老年'] += 1

                # 性别统计
                gender = patient.get('gender', '男')
                if gender in gender_stats:
                    gender_stats[gender] += 1

            return {
                "total_records": total_records,
                "scenario_distribution": scenario_stats,
                "risk_distribution": risk_stats,
                "age_distribution": age_stats,
                "gender_distribution": gender_stats,
                "generated_at": "2025-09-11T15:30:00Z"
            }
        else:
            return {
                "total_records": 0,
                "scenario_distribution": {},
                "risk_distribution": {},
                "age_distribution": {},
                "gender_distribution": {},
                "generated_at": "2025-09-11T15:30:00Z"
            }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取统计数据失败: {str(e)}"
        )

if __name__ == "__main__":
    # 启动服务器 - 使用端口 8002
    port = int(os.getenv("YIBAO_API_PORT", "8002"))
    print(f"🚀 启动智慧医保质控系统后端服务...")
    print(f"📡 服务地址: http://0.0.0.0:{port}")
    print(f"📚 API文档: http://localhost:{port}/docs")
    print(f"🔍 健康检查: http://localhost:{port}/api/health")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )
