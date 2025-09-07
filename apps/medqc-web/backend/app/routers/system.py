from fastapi import APIRouter
from datetime import datetime

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

