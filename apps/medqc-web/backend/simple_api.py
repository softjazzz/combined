#!/usr/bin/env python3
"""
医疗质控系统简化后端API
仅提供认证功能，数据操作由前端直连Supabase处理
"""

from fastapi import FastAPI, HTTPException, Depends, status, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from passlib.context import CryptContext
from jose import JWTError, jwt
import uuid
import random

# ==================== 应用配置 ====================

"""
DEPRECATED: Legacy toy API. Use `app/main.py`.
"""
app = FastAPI(
    title="医疗质控系统API",
    description="简化版API，数据操作直连Supabase",
    version="2.0.0"
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
SECRET_KEY = "your-secret-key-here"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

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

# ==================== 演示用户 ====================

DEMO_USERS = {
    "admin@medqc.com": {
        "id": "admin-001",
        "email": "admin@medqc.com",
        "display_name": "系统管理员",
        "department": "系统管理部",
        "roles": ["admin"],
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
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
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

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "version": "2.0.0",
        "message": "简化API运行正常，数据操作请使用Supabase"
    }

@app.post("/api/auth/login", response_model=LoginResponse)
async def login(login_data: LoginRequest):
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

@app.get("/api/auth/me")
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    return {
        "id": current_user["id"],
        "email": current_user["email"],
        "display_name": current_user["display_name"],
        "department": current_user["department"],
        "roles": current_user["roles"]
    }

@app.post("/api/auth/logout")
async def logout():
    return {"message": "登出成功"}

# ==================== 工具API ====================

@app.post("/api/qc/analyze-demo")
async def analyze_demo(
    content: str = Form(...),
    current_user: dict = Depends(get_current_user)
):
    """演示质控分析"""
    return {
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
                "category": random.choice(["基本信息", "诊断质量", "治疗方案"]),
                "suggestion": f"建议完善相关内容，确保符合医疗质控标准"
            }
            for i in range(1, random.randint(2, 4))
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "simple_api:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )
