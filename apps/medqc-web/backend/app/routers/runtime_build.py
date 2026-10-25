"""公开当前进程启动时冻结的发布声明，不读取请求时磁盘状态。"""

from datetime import datetime, timezone
import logging
import os

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse

from ..services.qc_diagnostics.runtime_build import load_runtime_build


router = APIRouter()
logger = logging.getLogger(__name__)


def initialize_runtime_build(app: FastAPI) -> None:
    """每个应用实例只读取一次；覆盖安装目录不会改变旧进程的启动版本。"""
    if hasattr(app.state, "runtime_build"):
        return
    build = load_runtime_build()
    available = build.get("available") is True
    snapshot = {
        "available": available,
        "build_id": build.get("build_id") if available else None,
        "git_commit": build.get("git_commit") if available else None,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "pid": os.getpid(),
    }
    if not available:
        snapshot["reason"] = "build_version_unavailable"
    from ..services.qc_workspace.p0_runtime import loaded_p0_proof
    p0_proof = loaded_p0_proof(release_identity=build)
    if p0_proof is not None:
        snapshot["p0_acceptance"] = p0_proof
    app.state.runtime_build = snapshot
    logger.info(
        "运行版本 available=%s build_id=%s git_commit=%s pid=%s started_at=%s",
        available, snapshot["build_id"], snapshot["git_commit"],
        snapshot["pid"], snapshot["started_at"],
    )


@router.get("/api/v1/runtime-build")
async def get_runtime_build(request: Request) -> JSONResponse:
    return JSONResponse(
        content=dict(request.app.state.runtime_build),
        headers={"Cache-Control": "no-store"},
    )
