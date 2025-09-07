from fastapi import APIRouter
import sys
import os

router = APIRouter(prefix="/api/debug", tags=["debug"], include_in_schema=False)


@router.get("/pdf-env")
async def pdf_env():
    info = {
        "python_executable": sys.executable,
        "python_version": sys.version,
        "cwd": os.getcwd(),
        "sys_path_head": sys.path[:5],
    }
    try:
        import fitz  # type: ignore
        info["has_pymupdf"] = True
        info["pymupdf_version"] = getattr(fitz, "__doc__", "").split("\n")[0] or "installed"
    except Exception as e:
        info["has_pymupdf"] = False
        info["pymupdf_error"] = str(e)
    try:
        import pdfplumber  # type: ignore
        info["has_pdfplumber"] = True
        info["pdfplumber_version"] = getattr(pdfplumber, "__version__", "installed")
    except Exception as e:
        info["has_pdfplumber"] = False
        info["pdfplumber_error"] = str(e)
    return info

