"""
医疗质控系统简化后端API
移除内存存储，仅保留必要的认证和工具API
前端直连Supabase处理数据操作
"""

from fastapi import FastAPI, HTTPException, Depends, status, Form, File, UploadFile
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from passlib.context import CryptContext
from jose import JWTError, jwt
import uuid
import random
import os

# ==================== 应用配置 ====================

app = FastAPI(
    title="医疗质控系统API",
    description="基于Supabase的医疗质控系统后端API",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# JWT配置
SECRET_KEY = os.getenv("JWT_SECRET", "your-secret-key-here")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# 密码加密
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

# ==================== 数据模型 ====================

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: Dict[str, Any]

class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str
    department: str
    roles: List[str]

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str
    message: str

# ==================== 演示数据 ====================

# 演示用户（仅用于JWT认证）
DEMO_USERS = {
    "admin@medqc.com": {
        "id": "admin-001",
        "email": "admin@medqc.com",
        "display_name": "系统管理员",
        "department": "系统管理部",
        "roles": ["admin", "qc_manager"],
        "password_hash": pwd_context.hash("admin123"),
    },
    "qc@medqc.com": {
        "id": "qc-001", 
        "email": "qc@medqc.com",
        "display_name": "质控主管",
        "department": "质控科",
        "roles": ["qc_manager"],
        "password_hash": pwd_context.hash("qc123456"),
    },
    "doctor@medqc.com": {
        "id": "doctor-001",
        "email": "doctor@medqc.com", 
        "display_name": "医务人员",
        "department": "内科",
        "roles": ["doctor"],
        "password_hash": pwd_context.hash("doctor123"),
    }
}

# ==================== 工具函数 ====================

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """创建访问令牌"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """获取当前用户"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的认证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = DEMO_USERS.get(email)
    if user is None:
        raise credentials_exception
    return user

# ==================== API端点 ====================

@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """健康检查"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat() + "Z",
        version="2.0.0",
        message="医疗质控系统API运行正常 - 数据存储在Supabase"
    )

@app.post("/api/auth/login", response_model=LoginResponse)
async def login(login_data: LoginRequest):
    """用户登录"""
    user = DEMO_USERS.get(login_data.email)
    if not user or not verify_password(login_data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["email"]}, expires_delta=access_token_expires
    )
    
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
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

# ==================== 工具API ====================

@app.post("/api/qc/analyze-demo")
async def analyze_demo(
    content: str = Form(...),
    current_user: dict = Depends(get_current_user)
):
    """演示质控分析（生成模拟结果）"""
    
    # 生成模拟分析结果
    analysis_result = {
        "id": f"analysis-{uuid.uuid4().hex[:8]}",
        "overall_score": random.randint(75, 95),
        "overall_grade": random.choice(["A", "B", "C"]),
        "analysis_date": datetime.utcnow().isoformat() + "Z",
        "issues": [
            {
                "id": f"issue-{i}",
                "rule_name": f"质控规则{i:02d}",
                "description": f"发现质控问题{i}：病案记录需要完善",
                "severity": random.choice(["critical", "major", "minor"]),
                "category": random.choice(["基本信息", "诊断质量", "治疗方案", "护理记录"]),
                "location": f"第{random.randint(1, 10)}段",
                "suggestion": f"建议完善相关内容，确保符合医疗质控标准"
            }
            for i in range(1, random.randint(2, 5))
        ],
        "suggestions": [
            {
                "id": f"suggestion-{i}",
                "category": random.choice(["诊断改进", "治疗优化", "记录完善"]),
                "title": f"改进建议{i}",
                "description": f"针对当前病案的改进建议{i}，提高医疗质量",
                "priority": random.choice(["high", "medium", "low"])
            }
            for i in range(1, random.randint(2, 4))
        ]
    }
    
    return {
        "success": True,
        "data": analysis_result,
        "message": "质控分析完成"
    }

@app.post("/api/files/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """文件上传（演示）"""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件名不能为空"
        )
    
    # 在实际应用中，这里应该保存文件到存储系统
    file_url = f"/uploads/{file.filename}"
    
    return {
        "success": True,
        "data": {
            "file_url": file_url,
            "file_name": file.filename,
            "file_size": file.size if hasattr(file, 'size') else 0
        },
        "message": "文件上传成功"
    }

@app.get("/api/demo/qc-rules")
async def get_demo_qc_rules(current_user: dict = Depends(get_current_user)):
    """获取演示质控规则"""
    demo_rules = [
        {
            "id": "rule-001",
            "rule_code": "QC001",
            "name": "主诉完整性检查",
            "description": "检查病案中主诉部分是否完整，包含患者主要症状和持续时间",
            "category": "基本信息",
            "severity": "major",
            "weight": 10,
            "is_active": True
        },
        {
            "id": "rule-002", 
            "rule_code": "QC002",
            "name": "诊断依据充分性",
            "description": "检查诊断是否有充分的依据支撑，包括症状、体征、检查结果等",
            "category": "诊断质量",
            "severity": "critical",
            "weight": 15,
            "is_active": True
        },
        {
            "id": "rule-003",
            "rule_code": "QC003", 
            "name": "用药合理性检查",
            "description": "检查用药是否符合诊断，剂量是否合理",
            "category": "治疗方案",
            "severity": "major",
            "weight": 12,
            "is_active": True
        }
    ]
    
    return {
        "success": True,
        "data": demo_rules,
        "message": "获取演示规则成功"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main_api_simplified:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
