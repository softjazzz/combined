from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/v1", tags=["tasks"], include_in_schema=False)


@router.get("/qc-tasks/{task_id}")
async def get_qc_task(    request: Request,task_id: str):
    return {"task_id": task_id, "status": "completed"}

