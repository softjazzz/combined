"""本机只读联调：复用既有账号身份，禁止数据库写入且不加载主应用/Worker。"""
import os
from datetime import timedelta
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


from app.core.security import get_current_user, create_access_token, verify_password  # noqa: E402
from app.routers.business_agent import router  # noqa: E402
from app.services.qc_agent.business_store import BusinessSessionStore, get_business_store  # noqa: E402

app = FastAPI(title="业务助手真实只读验证")
app.include_router(router, prefix="/api/v1/qc-agent")
store = BusinessSessionStore(backend.parent / ".tmp/0910-full-audit/business-agent-validation-private/real-metadata")
app.dependency_overrides[get_business_store] = lambda: store

# 默认关闭。仅取得共享库反馈写入授权后，在独立联调进程显式开启。
# 主 engine 的 enforce_readonly 监听始终保留，不加载主应用或 worker。
from tests.manual.business_feedback_session import install_feedback_override  # noqa: E402

feedback_engine = install_feedback_override(
    app, values, enabled=os.environ.get("MEDQC_AGENT_FEEDBACK_WRITE_ENABLED", "0"),
)


def public_user(user):
    return {key: user.get(key) for key in ("id", "email", "username", "display_name", "department", "roles", "avatar", "phone", "bio", "created_at", "last_login")}


@app.get("/api/v1/auth/me")
@app.get("/api/auth/me")
async def me(user=Depends(get_current_user)):
    return public_user(user)


@app.get("/readonly-health")
async def health(user=Depends(get_current_user)):
    with engine.connect() as connection:
        readonly = connection.execute(text("SHOW transaction_read_only")).scalar_one()
    return {"database_readonly": readonly == "on", "authenticated": bool(user.get("id"))}


class ValidationLogin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    account: str | None = None
    username: str | None = None
    password: str


@app.post("/api/v1/auth/login")
@app.post("/api/auth/login")
async def login(body: ValidationLogin):
    # 手工只读联调专用：复用正式账号查询及密码校验（含既有内存身份）。
    # 身份来源必须单独记录；不调用正式登录的 last_login 写入，不新增身份。
    from app.services.auth_store import find_user_by_account
    user = find_user_by_account(body.account or body.username or "")
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "现有账号或密码不正确")
    token = create_access_token({"sub": user["email"], "uid": user["id"]}, expires_delta=timedelta(hours=2))
    return {"access_token": token, "token_type": "bearer", "user": public_user(user)}
