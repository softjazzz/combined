from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["tasks"], include_in_schema=False)


@router.get("/qc-tasks/{task_id}")
async def get_qc_task(task_id: str):
    return {"task_id": task_id, "status": "completed"}

