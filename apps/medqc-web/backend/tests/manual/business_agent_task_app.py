"""手工联调专用：仅在用户授权的真实复检验证中运行。

挂载业务助手与正式质控路由，主连接可写以便正式任务链保存结果；不加载主应用启动钩子、
不恢复排队任务、不启动同步或其他后台监控。默认端口 8023，不替代主 3000/8001。
"""
import os
from datetime import timedelta
from pathlib import Path

from dotenv import dotenv_values, load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict

backend = Path(__file__).resolve().parents[2]
load_dotenv(backend / ".env")
source = os.environ.get("MEDQC_AGENT_SOURCE_ENV", "")
if not source:
    raise RuntimeError("需要显式指定既有 backend/.env 路径")
if os.environ.get("MEDQC_AGENT_TASK_WRITE_ENABLED") != "1":
    raise RuntimeError("真实任务联调需显式设置 MEDQC_AGENT_TASK_WRITE_ENABLED=1")
values = dotenv_values(source)
# 只按需读取数据库、身份与正式质控执行所需键；不读取同步锁、Mongo同步、遥测或DRG队列配置。
NEEDED = ("DATABASE_URL", "DB_SCHEMA_MODE", "DB_SEARCH_PATH", "DB_CONNECT_TIMEOUT_SECONDS", "JWT_SECRET", "JWT_ALGORITHM",
          "DATA_SOURCE", "RECORDS_TABLE", "DOCUMENTS_TABLE", "LLM_TIMEOUT_SECONDS", "LLM_ENABLE_TRUNCATE", "LLM_MAX_CONTENT_LENGTH",
          "LLM_ALLOW_MOCK_WHEN_UNCONFIGURED", "LLM_ADJUDICATOR_MODEL", "LLM_THINKING_BUDGET", "LLM_ENABLE_THINKING",
          "FIELD_MAPPER_MODEL", "SILICONFLOW_API_KEY", "SILICONFLOW_API_ENDPOINT", "OUTBOUND_ALLOWLIST")
for key in NEEDED:
    if values.get(key):
        os.environ[key] = values[key]
os.environ["MEDQC_AGENT_BACKEND_URL"] = "http://127.0.0.1:8023"
os.environ.setdefault("MEDQC_DETACHED_TASK_WORKERS", "1")
if not os.environ.get("DATABASE_URL") or not values.get("JWT_SECRET"):
    raise RuntimeError("任务联调需要实际数据库与身份签名配置")

from app.core.security import create_access_token, get_current_user, verify_password  # noqa: E402
from app.routers.business_agent import router as business_router  # noqa: E402
from app.routers.qc_sichuan import router as qc_router  # noqa: E402
from app.services.qc_agent.business_store import BusinessSessionStore, get_business_store  # noqa: E402

app = FastAPI(title="业务助手真实任务联调")
app.include_router(business_router, prefix="/api/v1/qc-agent")
app.include_router(qc_router)
from app.routers.icd_search import router as icd_router  # noqa: E402
app.include_router(icd_router)
store = BusinessSessionStore(backend.parent / ".tmp/0910-full-audit/business-agent-validation-private/real-metadata")
app.dependency_overrides[get_business_store] = lambda: store


def public_user(user):
    return {key: user.get(key) for key in ("id", "email", "username", "display_name", "department", "roles")}


@app.get("/api/v1/auth/me")
async def me(user=Depends(get_current_user)):
    return public_user(user)


class ValidationLogin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    account: str | None = None
    username: str | None = None
    password: str


@app.post("/api/v1/auth/login")
async def login(body: ValidationLogin):
    from app.services.auth_store import find_user_by_account
    user = find_user_by_account(body.account or body.username or "")
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "现有账号或密码不正确")
    token = create_access_token({"sub": user["email"], "uid": user["id"]}, expires_delta=timedelta(hours=2))
    return {"access_token": token, "token_type": "bearer", "user": public_user(user)}
