# 🔧 Agent B 后端开发任务指导文档

**角色**: 后端专家 (Backend Developer)  
**技术栈**: FastAPI + Python + Supabase + PostgreSQL  
**开发周期**: 3 周  
**协作对象**: Agent A (前端专家)  

---

## 📋 **任务背景**

### 🎯 **项目概述**
医疗质控系统是一个基于 AI 的智能医疗质控平台，采用 Vue 3 + FastAPI + Supabase 架构。系统已完成基础架构搭建和集成验证，现在进入并行开发阶段。

### 🏗️ **当前状态**
- ✅ **数据库设计**: 完整的医疗质控数据模型已定义
- ✅ **API 框架**: FastAPI 基础框架已搭建
- ✅ **Supabase 集成**: 数据库连接和认证配置完成
- ✅ **基础服务**: 部分核心业务逻辑已实现
- ⚠️ **待完善**: API 接口需要增强和优化

### 🎯 **后端开发目标**
1. **API 服务完善**: 实现完整的 RESTful API 接口
2. **业务逻辑优化**: 核心业务功能的深度实现
3. **性能优化**: 高并发处理和响应速度优化
4. **安全加固**: 认证授权和数据安全保护
5. **AI 服务集成**: 智能质控分析引擎集成

---

## 🗓️ **Week 1 核心任务 (高优先级)**

### 🔐 **Task B1: 用户认证API增强**
**优先级**: 🔥 高  
**预估工作量**: 3 天  
**依赖**: 无 (可立即开始)  

#### **任务描述**
完善用户认证系统，实现多角色权限管理，增强安全性和用户体验。

#### **具体工作内容**
1. **认证接口完善**
   - 用户登录/注册 API 优化
   - JWT 令牌管理和刷新机制
   - 多角色权限验证中间件
   - 密码安全策略实现

2. **用户管理功能**
   - 用户资料 CRUD 操作
   - 头像上传和文件管理
   - 密码重置和邮箱验证
   - 用户会话管理

3. **权限控制系统**
   - 基于角色的访问控制 (RBAC)
   - API 权限装饰器
   - 资源级权限验证
   - 审计日志记录

#### **文件结构**
```
production_system/
├── api/
│   ├── auth.py               # 认证相关API路由
│   ├── users.py              # 用户管理API路由
│   └── __init__.py
├── core/
│   ├── auth.py               # 认证核心逻辑
│   ├── security.py           # 安全相关工具
│   ├── permissions.py        # 权限管理
│   └── exceptions.py         # 自定义异常
├── middleware/
│   ├── auth.py               # 认证中间件
│   ├── permissions.py        # 权限中间件
│   └── logging.py            # 日志中间件
├── models/
│   ├── user.py               # 用户数据模型
│   └── auth.py               # 认证相关模型
├── services/
│   ├── auth_service.py       # 认证服务
│   ├── user_service.py       # 用户服务
│   └── email_service.py      # 邮件服务
└── utils/
    ├── jwt_handler.py        # JWT 处理工具
    ├── password_utils.py     # 密码工具
    └── validators.py         # 数据验证器
```

#### **API 接口实现**

**1. 用户登录接口**
```python
# production_system/api/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from pydantic import BaseModel, EmailStr
from typing import Optional
import bcrypt
from datetime import datetime, timedelta

from ..core.auth import create_access_token, verify_password
from ..services.auth_service import AuthService
from ..models.auth import LoginRequest, LoginResponse
from ..core.database import get_db

router = APIRouter(prefix="/api/auth", tags=["认证"])
security = HTTPBearer()

class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    role: Optional[str] = None
    remember_me: bool = False

class LoginResponse(BaseModel):
    user: dict
    tokens: dict

@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    db = Depends(get_db),
    auth_service: AuthService = Depends()
):
    """用户登录"""
    try:
        # 验证用户凭据
        user = await auth_service.authenticate_user(
            email=request.email,
            password=request.password,
            role=request.role
        )
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="邮箱、密码或角色不正确"
            )
        
        # 生成访问令牌
        access_token = create_access_token(
            data={"sub": user.id, "role": user.role},
            expires_delta=timedelta(hours=24 if request.remember_me else 1)
        )
        
        refresh_token = create_access_token(
            data={"sub": user.id, "type": "refresh"},
            expires_delta=timedelta(days=30)
        )
        
        # 更新最后登录时间
        await auth_service.update_last_login(user.id)
        
        return LoginResponse(
            user={
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
                "department_id": user.department_id,
                "avatar_url": user.avatar_url
            },
            tokens={
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_in": 86400 if request.remember_me else 3600
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"登录失败: {str(e)}"
        )

@router.post("/register")
async def register(
    request: RegisterRequest,
    db = Depends(get_db),
    auth_service: AuthService = Depends()
):
    """用户注册"""
    try:
        # 检查邮箱是否已存在
        existing_user = await auth_service.get_user_by_email(request.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该邮箱已被注册"
            )
        
        # 创建新用户
        user = await auth_service.create_user(
            email=request.email,
            password=request.password,
            full_name=request.full_name,
            role=request.role,
            department_id=request.department_id,
            phone=request.phone
        )
        
        return {"message": "注册成功", "user_id": user.id}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"注册失败: {str(e)}"
        )

@router.post("/refresh")
async def refresh_token(
    request: RefreshRequest,
    auth_service: AuthService = Depends()
):
    """刷新访问令牌"""
    try:
        # 验证刷新令牌
        payload = verify_token(request.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的刷新令牌"
            )
        
        user_id = payload.get("sub")
        user = await auth_service.get_user_by_id(user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户不存在"
            )
        
        # 生成新的访问令牌
        new_access_token = create_access_token(
            data={"sub": user.id, "role": user.role}
        )
        
        return {
            "access_token": new_access_token,
            "expires_in": 3600
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"令牌刷新失败: {str(e)}"
        )
```

**2. 权限验证中间件**
```python
# production_system/middleware/auth.py
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List, Optional
import jwt
from functools import wraps

from ..core.config import settings
from ..services.auth_service import AuthService

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    auth_service: AuthService = Depends()
):
    """获取当前用户"""
    try:
        token = credentials.credentials
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的认证令牌"
            )
        
        user = await auth_service.get_user_by_id(user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户不存在"
            )
        
        return user
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="认证令牌已过期"
        )
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证令牌"
        )

def require_roles(allowed_roles: List[str]):
    """角色权限装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 从kwargs中获取current_user
            current_user = kwargs.get('current_user')
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="需要认证"
                )
            
            if current_user.role not in allowed_roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="权限不足"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# 权限依赖函数
def require_admin(current_user = Depends(get_current_user)):
    """需要管理员权限"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    return current_user

def require_doctor_or_admin(current_user = Depends(get_current_user)):
    """需要医生或管理员权限"""
    if current_user.role not in ["doctor", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要医生或管理员权限"
        )
    return current_user

def require_qc_manager_or_admin(current_user = Depends(get_current_user)):
    """需要质控管理员或管理员权限"""
    if current_user.role not in ["qc_manager", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要质控管理员或管理员权限"
        )
    return current_user
```

#### **验收标准**
- [ ] 支持 4 种用户角色认证 (admin, doctor, qc_manager, viewer)
- [ ] JWT 令牌管理完善，支持刷新机制
- [ ] 密码安全策略实现 (加密、强度验证)
- [ ] 权限中间件正常工作，API 权限控制有效
- [ ] 用户注册流程完整，邮箱验证功能
- [ ] 用户资料管理 API 完整
- [ ] API 响应时间 < 200ms
- [ ] 安全性验证通过 (SQL注入、XSS防护)

---

### 📄 **Task B2: 医疗记录处理API**
**优先级**: 🔥 高  
**预估工作量**: 4 天  
**依赖**: Task B1 (认证系统)  

#### **任务描述**
实现完整的医疗记录管理 API，包括 CRUD 操作、文件处理、搜索筛选、批量操作等功能。

#### **具体工作内容**
1. **记录管理 API**
   - 医疗记录 CRUD 操作
   - 记录搜索和筛选功能
   - 分页和排序支持
   - 记录状态管理

2. **文件处理服务**
   - 多格式文件上传
   - 文件存储和管理
   - 文件预览和下载
   - 文件安全验证

3. **批量操作功能**
   - 批量导入医疗记录
   - 批量导出数据
   - 批量删除和更新
   - 操作进度跟踪

4. **数据验证和处理**
   - 医疗记录数据验证
   - 数据格式标准化
   - 重复记录检测
   - 数据完整性检查

#### **文件结构**
```
production_system/
├── api/
│   ├── records.py            # 医疗记录API路由
│   ├── files.py              # 文件管理API路由
│   └── batch.py              # 批量操作API路由
├── core/
│   ├── records.py            # 记录核心逻辑
│   ├── file_handler.py       # 文件处理核心
│   └── validators.py         # 数据验证器
├── services/
│   ├── records_service.py    # 记录服务
│   ├── file_service.py       # 文件服务
│   ├── search_service.py     # 搜索服务
│   └── batch_service.py      # 批量操作服务
├── models/
│   ├── records.py            # 记录数据模型
│   └── files.py              # 文件数据模型
└── utils/
    ├── file_utils.py         # 文件工具
    ├── data_parser.py        # 数据解析器
    └── export_utils.py       # 导出工具
```

#### **API 接口实现**

**1. 医疗记录列表接口**
```python
# production_system/api/records.py
from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Optional, List
from datetime import datetime

from ..middleware.auth import get_current_user, require_doctor_or_admin
from ..services.records_service import RecordsService
from ..models.records import RecordsQuery, RecordResponse, CreateRecordRequest

router = APIRouter(prefix="/api/records", tags=["医疗记录"])

@router.get("/", response_model=dict)
async def get_records(
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(10, ge=1, le=100, description="每页数量"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    department_id: Optional[str] = Query(None, description="科室ID"),
    doctor_id: Optional[str] = Query(None, description="医生ID"),
    status: Optional[str] = Query(None, description="记录状态"),
    date_from: Optional[str] = Query(None, description="开始日期"),
    date_to: Optional[str] = Query(None, description="结束日期"),
    sort_by: str = Query("created_at", description="排序字段"),
    sort_order: str = Query("desc", description="排序方向"),
    current_user = Depends(get_current_user),
    records_service: RecordsService = Depends()
):
    """获取医疗记录列表"""
    try:
        # 构建查询参数
        query_params = RecordsQuery(
            page=page,
            limit=limit,
            search=search,
            department_id=department_id,
            doctor_id=doctor_id,
            status=status,
            date_from=date_from,
            date_to=date_to,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        # 根据用户角色过滤数据
        if current_user.role == "doctor":
            query_params.doctor_id = current_user.id
        elif current_user.role == "qc_manager":
            query_params.department_id = current_user.department_id
        
        # 获取记录列表
        result = await records_service.get_records(query_params)
        
        return {
            "success": True,
            "data": {
                "records": result.records,
                "pagination": {
                    "total": result.total,
                    "page": page,
                    "limit": limit,
                    "pages": (result.total + limit - 1) // limit
                }
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取记录列表失败: {str(e)}"
        )

@router.post("/", response_model=dict)
async def create_record(
    request: CreateRecordRequest,
    current_user = Depends(require_doctor_or_admin),
    records_service: RecordsService = Depends()
):
    """创建医疗记录"""
    try:
        # 验证数据
        if not request.patient_name or not request.diagnosis_primary:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="患者姓名和主要诊断不能为空"
            )
        
        # 创建记录
        record = await records_service.create_record(
            data=request.dict(),
            creator_id=current_user.id
        )
        
        return {
            "success": True,
            "data": record,
            "message": "医疗记录创建成功"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建记录失败: {str(e)}"
        )

@router.get("/{record_id}", response_model=dict)
async def get_record_detail(
    record_id: str,
    current_user = Depends(get_current_user),
    records_service: RecordsService = Depends()
):
    """获取医疗记录详情"""
    try:
        record = await records_service.get_record_by_id(record_id)
        
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="医疗记录不存在"
            )
        
        # 权限检查
        if (current_user.role == "doctor" and 
            record.doctor_id != current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此记录"
            )
        
        # 获取详细信息
        detail = await records_service.get_record_detail(record_id)
        
        return {
            "success": True,
            "data": detail
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取记录详情失败: {str(e)}"
        )
```

**2. 文件上传接口**
```python
# production_system/api/files.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from typing import Optional
import os
import uuid
from pathlib import Path

from ..middleware.auth import get_current_user
from ..services.file_service import FileService
from ..utils.file_utils import validate_file, get_file_info

router = APIRouter(prefix="/api/files", tags=["文件管理"])

@router.post("/upload", response_model=dict)
async def upload_file(
    file: UploadFile = File(...),
    record_id: Optional[str] = Form(None),
    patient_name: Optional[str] = Form(None),
    patient_id: Optional[str] = Form(None),
    department_id: Optional[str] = Form(None),
    current_user = Depends(get_current_user),
    file_service: FileService = Depends()
):
    """上传医疗记录文件"""
    try:
        # 验证文件
        validation_result = validate_file(file)
        if not validation_result.is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=validation_result.error_message
            )
        
        # 生成文件ID和路径
        file_id = str(uuid.uuid4())
        file_extension = Path(file.filename).suffix
        file_path = f"medical_records/{current_user.id}/{file_id}{file_extension}"
        
        # 上传文件到 Supabase Storage
        upload_result = await file_service.upload_to_storage(
            file=file,
            path=file_path
        )
        
        # 提取文件内容（如果是文本文件）
        extracted_data = None
        if file.content_type in ['text/plain', 'application/pdf']:
            extracted_data = await file_service.extract_content(file)
        
        # 保存文件记录
        file_record = await file_service.save_file_record(
            file_id=file_id,
            filename=file.filename,
            file_path=file_path,
            file_size=file.size,
            content_type=file.content_type,
            uploader_id=current_user.id,
            record_id=record_id,
            extracted_data=extracted_data
        )
        
        return {
            "success": True,
            "data": {
                "file_id": file_id,
                "filename": file.filename,
                "file_size": file.size,
                "file_type": file.content_type,
                "url": upload_result.url,
                "extracted_data": extracted_data
            },
            "message": "文件上传成功"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文件上传失败: {str(e)}"
        )
```

#### **验收标准**
- [ ] 支持医疗记录完整 CRUD 操作
- [ ] 支持多格式文件上传 (PDF, DOC, TXT, 图片)
- [ ] 文件大小限制 50MB，安全验证完整
- [ ] 搜索功能响应时间 < 1 秒
- [ ] 分页查询性能优化，支持大数据量
- [ ] 批量操作支持进度跟踪
- [ ] 数据验证完整，错误处理友好
- [ ] 权限控制正确，数据安全保护

---

### 🔍 **Task B3: AI质控分析引擎**
**优先级**: 🔥 高  
**预估工作量**: 5 天  
**依赖**: Task B2 (医疗记录API)  

#### **任务描述**
实现 AI 驱动的质控分析引擎，包括规则引擎、AI 服务集成、批量分析、结果缓存等功能。

#### **具体工作内容**
1. **质控规则引擎**
   - 可配置的质控规则系统
   - 规则优先级和权重管理
   - 规则执行引擎
   - 规则结果聚合

2. **AI 服务集成**
   - OpenAI API 集成
   - 智能分析提示工程
   - 结果解析和标准化
   - 错误处理和重试机制

3. **批量分析功能**
   - 异步任务队列
   - 批量分析调度
   - 进度跟踪和状态管理
   - 结果通知机制

4. **缓存和优化**
   - 分析结果缓存
   - 重复分析检测
   - 性能监控
   - 资源使用优化

#### **验收标准**
- [ ] AI 分析准确率 > 85%
- [ ] 支持并发分析处理 (10+ 并发)
- [ ] 分析结果缓存有效，命中率 > 70%
- [ ] 任务状态跟踪完整，实时更新
- [ ] 批量分析支持 100+ 记录
- [ ] 错误处理和重试机制完善
- [ ] API 响应时间 < 3 秒 (单个分析)
- [ ] 资源使用监控和告警

---

## 🗓️ **Week 2-3 高级功能和优化**

### 🔍 **Task B4: 向量搜索服务** (Week 2)
### 📊 **Task B5: 统计分析API** (Week 2)  
### 🚀 **Task B6: 系统性能优化** (Week 3)

---

## 🛠️ **技术要求和规范**

### 📦 **技术栈**
- **框架**: FastAPI 0.116+
- **语言**: Python 3.13+
- **数据库**: PostgreSQL + Supabase
- **认证**: JWT + Supabase Auth
- **异步**: asyncio + asyncpg
- **AI服务**: OpenAI API
- **文件存储**: Supabase Storage
- **缓存**: Redis (可选)

### 🏗️ **架构规范**
- **分层架构**: API → Service → Core → Database
- **依赖注入**: FastAPI Depends
- **异常处理**: 统一异常处理机制
- **日志记录**: 结构化日志
- **配置管理**: 环境变量配置

### 📝 **代码规范**
```python
# 示例：API 路由结构
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional, List
from pydantic import BaseModel

from ..middleware.auth import get_current_user
from ..services.example_service import ExampleService
from ..models.example import ExampleRequest, ExampleResponse

router = APIRouter(prefix="/api/example", tags=["示例"])

class ExampleRequest(BaseModel):
    name: str
    description: Optional[str] = None
    
    class Config:
        schema_extra = {
            "example": {
                "name": "示例名称",
                "description": "示例描述"
            }
        }

@router.post("/", response_model=dict)
async def create_example(
    request: ExampleRequest,
    current_user = Depends(get_current_user),
    service: ExampleService = Depends()
):
    """创建示例"""
    try:
        result = await service.create_example(
            data=request.dict(),
            user_id=current_user.id
        )
        
        return {
            "success": True,
            "data": result,
            "message": "创建成功"
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建失败: {str(e)}"
        )
```

---

## 🤝 **协作机制**

### 📋 **任务跟踪**
```bash
# 查看当前可开始的任务
python3 tools/coordination/task_tracker.py ready agent_b

# 开始任务
python3 tools/coordination/task_tracker.py status B1 in_progress "开始用户认证API增强"

# 完成任务
python3 tools/coordination/task_tracker.py status B1 completed "认证API增强完成"

# 生成每日报告
python3 tools/coordination/task_tracker.py report
```

### 🔄 **与 Agent A 协作**
1. **API 接口协调**
   - 维护 `docs/api/API_INTERFACE_SPECIFICATION.md`
   - 接口变更及时通知前端
   - 提供接口测试环境

2. **依赖管理**
   - Task A2 依赖 Task B2 (医疗记录API)
   - Task A3 依赖 Task B3 (质控分析API)
   - 优先完成前端依赖的接口

3. **文件协调**
   - 只修改 `production_system/` 后端文件
   - 不要修改 `src/` 前端文件
   - 共享文件需要协调

### 🌿 **Git 工作流**
```bash
# 切换到后端开发分支
git checkout feature/agent-b-backend-api

# 每日提交代码
git add .
git commit -m "feat(auth): 完成用户认证API增强"
git push origin feature/agent-b-backend-api

# 每日合并到 develop 分支
git checkout develop
git pull origin develop
git merge feature/agent-b-backend-api
git push origin develop
```

---

## 📚 **重要参考文档**

1. **[并行开发计划](PARALLEL_DEVELOPMENT_PLAN.md)** - 整体开发计划
2. **[API 接口规范](docs/api/API_INTERFACE_SPECIFICATION.md)** - 需要维护的接口文档
3. **[数据库设计](database/setup/database_init_complete.sql)** - 数据库结构
4. **[FastAPI 官方文档](https://fastapi.tiangolo.com/)** - FastAPI 开发指南
5. **[Supabase 文档](https://supabase.com/docs)** - Supabase 集成指南

---

## 🎯 **成功标准**

### 📊 **质量指标**
- **API 响应时间**: 平均 < 200ms
- **并发处理能力**: 支持 100+ 并发请求
- **错误率**: < 1%
- **测试覆盖率**: > 80%
- **代码质量**: 通过 pylint 检查

### ✅ **验收清单**
- [ ] 所有 Week 1 任务按时完成
- [ ] API 接口文档完整准确
- [ ] 前后端接口对接成功
- [ ] 安全性验证通过
- [ ] 性能指标达标
- [ ] 错误处理完善
- [ ] 日志记录完整

---

---

## 🚀 **快速启动指南**

### **第一步：环境准备**
```bash
# 1. 切换到项目目录
cd examples/002medqc/MedQC0817

# 2. 切换到后端开发分支
git checkout feature/agent-b-backend-api

# 3. 进入后端工作区
cd workspace/agent-b

# 4. 查看当前可开始的任务
python3 ../../tools/coordination/task_tracker.py ready agent_b
```

### **第二步：开始第一个任务**
```bash
# 1. 更新任务状态为进行中
python3 ../../tools/coordination/task_tracker.py status B1 in_progress "开始用户认证API增强"

# 2. 进入后端系统目录
cd ../../production_system

# 3. 检查依赖
pip install -r requirements.txt

# 4. 启动开发服务器
python main.py
```

### **第三步：创建认证服务**

创建文件：`services/auth_service.py`

```python
# production_system/services/auth_service.py
from typing import Optional, Dict, Any
import bcrypt
from datetime import datetime
import uuid

from ..core.database import get_supabase_client
from ..models.user import User
from ..utils.password_utils import hash_password, verify_password

class AuthService:
    """认证服务"""

    def __init__(self):
        self.supabase = get_supabase_client()

    async def authenticate_user(
        self,
        email: str,
        password: str,
        role: Optional[str] = None
    ) -> Optional[User]:
        """验证用户凭据"""
        try:
            # 查询用户
            query = self.supabase.table('user_profiles').select('*').eq('email', email)

            if role:
                query = query.eq('role', role)

            result = query.execute()

            if not result.data:
                return None

            user_data = result.data[0]

            # 验证密码
            if not verify_password(password, user_data['password_hash']):
                return None

            return User(**user_data)

        except Exception as e:
            print(f"认证失败: {e}")
            return None

    async def create_user(
        self,
        email: str,
        password: str,
        full_name: str,
        role: str,
        department_id: Optional[str] = None,
        phone: Optional[str] = None
    ) -> User:
        """创建新用户"""
        try:
            # 生成用户ID
            user_id = str(uuid.uuid4())

            # 加密密码
            password_hash = hash_password(password)

            # 插入用户数据
            user_data = {
                'id': user_id,
                'email': email,
                'password_hash': password_hash,
                'full_name': full_name,
                'role': role,
                'department_id': department_id,
                'phone': phone,
                'created_at': datetime.utcnow().isoformat(),
                'is_active': True
            }

            result = self.supabase.table('user_profiles').insert(user_data).execute()

            if result.data:
                return User(**result.data[0])
            else:
                raise Exception("用户创建失败")

        except Exception as e:
            raise Exception(f"创建用户失败: {e}")

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """根据邮箱获取用户"""
        try:
            result = self.supabase.table('user_profiles').select('*').eq('email', email).execute()

            if result.data:
                return User(**result.data[0])
            return None

        except Exception as e:
            print(f"获取用户失败: {e}")
            return None

    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """根据ID获取用户"""
        try:
            result = self.supabase.table('user_profiles').select('*').eq('id', user_id).execute()

            if result.data:
                return User(**result.data[0])
            return None

        except Exception as e:
            print(f"获取用户失败: {e}")
            return None

    async def update_last_login(self, user_id: str):
        """更新最后登录时间"""
        try:
            self.supabase.table('user_profiles').update({
                'last_login': datetime.utcnow().isoformat()
            }).eq('id', user_id).execute()

        except Exception as e:
            print(f"更新登录时间失败: {e}")
```

### **第四步：创建JWT工具**

创建文件：`utils/jwt_handler.py`

```python
# production_system/utils/jwt_handler.py
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import os

# JWT 配置
SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-secret-key-here')
ALGORITHM = 'HS256'
ACCESS_TOKEN_EXPIRE_MINUTES = 60

def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """创建访问令牌"""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire, "iat": datetime.utcnow()})

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Dict[str, Any]:
    """验证令牌"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise Exception("令牌已过期")
    except jwt.JWTError:
        raise Exception("无效的令牌")
```

### **第五步：每日工作流程**
```bash
# 早上：查看进度和任务
python3 ../../tools/coordination/task_tracker.py report

# 开发过程中：提交代码
git add .
git commit -m "feat(auth): 实现用户认证服务"

# 晚上：更新任务状态
python3 ../../tools/coordination/task_tracker.py status B1 completed "用户认证API增强完成"

# 推送代码
git push origin feature/agent-b-backend-api
```

### **第六步：API 测试**
```bash
# 启动服务器
python main.py

# 测试登录接口
curl -X POST "http://localhost:8001/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@medqc.com",
    "password": "admin123",
    "role": "admin"
  }'

# 测试受保护的接口
curl -X GET "http://localhost:8001/api/auth/profile" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

---

## 📝 **开发提示**

### **1. 数据库操作**
```python
# 使用 Supabase 客户端
from ..core.database import get_supabase_client

supabase = get_supabase_client()

# 查询数据
result = supabase.table('user_profiles').select('*').eq('id', user_id).execute()

# 插入数据
result = supabase.table('user_profiles').insert(data).execute()

# 更新数据
result = supabase.table('user_profiles').update(data).eq('id', user_id).execute()

# 删除数据
result = supabase.table('user_profiles').delete().eq('id', user_id).execute()
```

### **2. 错误处理规范**
```python
from fastapi import HTTPException, status

try:
    # 业务逻辑
    result = await service.do_something()
    return {"success": True, "data": result}

except ValueError as e:
    # 客户端错误
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(e)
    )
except Exception as e:
    # 服务器错误
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"操作失败: {str(e)}"
    )
```

### **3. 异步编程规范**
```python
import asyncio
from typing import List

async def process_batch(items: List[Any]) -> List[Any]:
    """批量处理示例"""
    tasks = []
    for item in items:
        task = asyncio.create_task(process_single_item(item))
        tasks.append(task)

    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results

async def process_single_item(item: Any) -> Any:
    """单个项目处理"""
    # 异步处理逻辑
    await asyncio.sleep(0.1)  # 模拟异步操作
    return item
```

### **4. 配置管理**
```python
# production_system/core/config.py
import os
from pydantic import BaseSettings

class Settings(BaseSettings):
    # 数据库配置
    SUPABASE_URL: str = os.getenv('VITE_SUPABASE_URL')
    SUPABASE_KEY: str = os.getenv('VITE_SUPABASE_ANON_KEY')

    # JWT 配置
    SECRET_KEY: str = os.getenv('JWT_SECRET_KEY', 'your-secret-key')
    ALGORITHM: str = 'HS256'
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # OpenAI 配置
    OPENAI_API_KEY: str = os.getenv('OPENAI_API_KEY', '')

    # 文件上传配置
    MAX_FILE_SIZE: int = 50 * 1024 * 1024  # 50MB
    ALLOWED_FILE_TYPES: list = [
        'application/pdf',
        'application/msword',
        'text/plain',
        'image/jpeg',
        'image/png'
    ]

    class Config:
        env_file = '.env'

settings = Settings()
```

---

## 🧪 **测试和验证**

### **单元测试示例**
```python
# tests/test_auth_service.py
import pytest
from unittest.mock import Mock, patch
from services.auth_service import AuthService

@pytest.fixture
def auth_service():
    return AuthService()

@pytest.mark.asyncio
async def test_authenticate_user_success(auth_service):
    """测试用户认证成功"""
    with patch.object(auth_service, 'supabase') as mock_supabase:
        # 模拟数据库返回
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [{
            'id': '123',
            'email': 'test@example.com',
            'password_hash': 'hashed_password',
            'role': 'doctor'
        }]

        with patch('utils.password_utils.verify_password', return_value=True):
            user = await auth_service.authenticate_user('test@example.com', 'password')

            assert user is not None
            assert user.email == 'test@example.com'

@pytest.mark.asyncio
async def test_authenticate_user_invalid_password(auth_service):
    """测试密码错误"""
    with patch.object(auth_service, 'supabase') as mock_supabase:
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [{
            'id': '123',
            'email': 'test@example.com',
            'password_hash': 'hashed_password',
            'role': 'doctor'
        }]

        with patch('utils.password_utils.verify_password', return_value=False):
            user = await auth_service.authenticate_user('test@example.com', 'wrong_password')

            assert user is None
```

### **API 测试脚本**
```python
# tools/testing/test_backend_apis.py
import requests
import json

BASE_URL = "http://localhost:8001"

def test_login_api():
    """测试登录API"""
    url = f"{BASE_URL}/api/auth/login"
    data = {
        "email": "admin@medqc.com",
        "password": "admin123",
        "role": "admin"
    }

    response = requests.post(url, json=data)

    print(f"登录测试: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"登录成功: {result['user']['full_name']}")
        return result['tokens']['access_token']
    else:
        print(f"登录失败: {response.text}")
        return None

def test_protected_api(token):
    """测试受保护的API"""
    url = f"{BASE_URL}/api/auth/profile"
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(url, headers=headers)

    print(f"资料获取测试: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"用户资料: {result}")
    else:
        print(f"获取失败: {response.text}")

if __name__ == "__main__":
    token = test_login_api()
    if token:
        test_protected_api(token)
```

---

## 🎯 **验收清单模板**

### **Task B1: 用户认证API增强**
- [ ] 登录API支持4种角色认证
- [ ] JWT令牌生成和验证正常
- [ ] 密码加密和验证安全
- [ ] 权限中间件工作正常
- [ ] 用户注册流程完整
- [ ] 用户资料管理API完整
- [ ] API响应时间 < 200ms
- [ ] 错误处理完善
- [ ] 单元测试覆盖率 > 80%
- [ ] API文档更新完整

**现在可以开始后端开发工作了！记住每天更新任务状态，及时与 Agent A 沟通接口变更。** 🚀

---

**开始时间**: 立即开始
**负责人**: Agent B (后端专家)
**协作对象**: Agent A (前端专家)
**预期完成**: 3 周内完成所有任务
