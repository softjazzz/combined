# -*- coding: utf-8 -*-
"""Patch main.py to add charset=utf-8 to all JSON responses."""
import pathlib

p = pathlib.Path(r"backend/app/main.py")
content = p.read_text(encoding="utf-8")

# Remove the broken middleware we added
middleware_block = """
    # \u5f3a\u5236\u6240\u6709 JSON \u54cd\u5e94\u58f0\u660e charset=utf-8\uff08\u4fee\u590d Windows \u4e2d\u6587\u7cfb\u7edf\u4e71\u7801\uff09
    @app.middleware('http')
    async def enforce_utf8_charset(request: Request, call_next):
        response = await call_next(request)
        ct = response.headers.get('content-type', '')
        if 'application/json' in ct and 'charset' not in ct:
            response.headers['content-type'] = ct + '; charset=utf-8'
        return response
"""
content = content.replace(middleware_block, "")

# Add custom response class before create_app
if "UTF8JSONResponse" not in content:
    # Find 'def create_app' and insert before it
    old = "def create_app() -> FastAPI:"
    new = """class UTF8JSONResponse(JSONResponse):
    \"\"\"JSON response with explicit charset=utf-8 for Windows CJK compatibility.\"\"\"
    media_type = "application/json; charset=utf-8"


def create_app() -> FastAPI:"""
    content = content.replace(old, new)

    # Also need to import JSONResponse at the top
    old_import = "from starlette.responses import JSONResponse"
    if old_import not in content:
        # Add import after existing imports
        content = content.replace(
            "from fastapi.middleware.cors import CORSMiddleware\n",
            "from fastapi.middleware.cors import CORSMiddleware\nfrom starlette.responses import JSONResponse as JSONResponse\n",
            1,
        )

    # Set default_response_class in FastAPI constructor
    content = content.replace(
        '        redoc_url="/redoc",\r\n    )',
        '        redoc_url="/redoc",\r\n        default_response_class=UTF8JSONResponse,\r\n    )',
    )

    p.write_text(content, encoding="utf-8")
    print("PATCHED OK")
else:
    print("ALREADY PATCHED")
