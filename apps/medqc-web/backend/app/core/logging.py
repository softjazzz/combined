import logging
import time
from typing import Callable
from fastapi import Request


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


async def request_logger_middleware(request: Request, call_next: Callable):
    start = time.time()
    response = await call_next(request)
    duration = (time.time() - start) * 1000
    # 使用标准 logger 避免 uvicorn.access 自带格式冲突
    logging.getLogger("app.access").info(
        "%s %s -> %s in %.2fms", request.method, request.url.path, response.status_code, duration
    )
    return response

