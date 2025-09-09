from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import traceback
import uuid


class UnifiedErrorMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        trace_id = str(uuid.uuid4())
        try:
            response = await call_next(request)
            return response
        except Exception as e:  # noqa: BLE001
            tb = traceback.format_exc(limit=2)
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "error": str(e),
                    "code": "INTERNAL_ERROR",
                    "traceId": trace_id,
                    "detail": tb,
                },
            )


