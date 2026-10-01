"""本机真实只读联调：复用实际身份，禁止数据库写入且不加载主应用/Worker。"""
import os
import httpx
from pathlib import Path

from dotenv import dotenv_values, load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import event, text

backend = Path(__file__).resolve().parents[2]
load_dotenv(backend / ".env")
# 用户授权按需读取既有 backend/.env，绝不整份复制或加载队列配置。
source = os.environ.get("MEDQC_AGENT_SOURCE_ENV", "")
if not source:
    raise RuntimeError("需要显式指定既有 backend/.env 路径")
values = dotenv_values(source)
for key in ("DATABASE_URL", "DB_SCHEMA_MODE", "DB_SEARCH_PATH", "JWT_SECRET", "JWT_ALGORITHM"):
    if values.get(key):
        os.environ[key] = values[key]
if not os.environ.get("DATABASE_URL") or not values.get("JWT_SECRET"):
    raise RuntimeError("只读联调需要实际数据库与身份签名配置")

from app.database.connection import engine  # noqa: E402

if engine is None or engine.dialect.name != "postgresql":
    raise RuntimeError("只读保护仅对实际 PostgreSQL 生效")


@event.listens_for(engine, "connect")
def enforce_readonly(connection, _):
    # 在任何业务查询之前设定默认事务只读；不执行 init_db 或 DDL。
    connection.set_session(readonly=True)


from app.core.security import get_current_user  # noqa: E402
from app.routers.business_agent import router  # noqa: E402
from app.services.qc_agent.business_store import BusinessSessionStore, get_business_store  # noqa: E402

app = FastAPI(title="业务助手真实只读验证")
app.include_router(router, prefix="/api/v1/qc-agent")
store = BusinessSessionStore(backend.parent / ".tmp/0910-full-audit/business-agent-validation-private/real-metadata")
app.dependency_overrides[get_business_store] = lambda: store


@app.get("/api/auth/me")
async def me(user=Depends(get_current_user)):
    return user


@app.get("/readonly-health")
async def health(user=Depends(get_current_user)):
    with engine.connect() as connection:
        readonly = connection.execute(text("SHOW transaction_read_only")).scalar_one()
    return {"database_readonly": readonly == "on", "authenticated": bool(user.get("id"))}


class ValidationLogin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str
    password: str


@app.post("/api/auth/login")
async def login(body: ValidationLogin):
    # 登录由用户已授权的现有主服务处理；验证服务不注册账号或修改角色。
    async with httpx.AsyncClient(timeout=15, trust_env=False) as client:
        response = await client.post("http://127.0.0.1:8001/api/v1/auth/login", json={"account": body.username, "password": body.password})
    if response.status_code != 200:
        raise HTTPException(response.status_code, "现有主服务登录失败")
    return response.json()
