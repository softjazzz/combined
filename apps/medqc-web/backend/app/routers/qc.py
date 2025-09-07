import uuid
from datetime import datetime
from typing import List, Dict, Any

from fastapi import APIRouter, HTTPException, status

from ..schemas.qc import QCResult, QCRule
from ..services.qc_service import QCService
from ..storage.memory import qc_results_db, qc_rules_db


router = APIRouter(prefix="/api/qc", tags=["qc"])
service = QCService()


@router.post("/analyze/{record_id}")
async def analyze_record(record_id: str):
    result = await service.evaluate({"record_id": record_id})
    # store result
    qc_results_db[record_id] = result
    analysis_id = f"analysis-{uuid.uuid4().hex[:8]}"
    return {"analysis_id": analysis_id, "status": "started", "record_id": record_id}


@router.post("/analyze/batch")
async def analyze_batch(payload: Dict[str, Any]):
    record_ids: List[str] = payload.get("record_ids", [])
    started = []
    for rid in record_ids:
        res = await service.evaluate({"record_id": rid})
        qc_results_db[rid] = res
        started.append({"record_id": rid, "status": "started"})
    return {"started": started, "message": f"已为 {len(started)} 个文档启动质控分析"}


@router.get("/result/{record_id}", response_model=QCResult)
async def get_result(record_id: str):
    res = qc_results_db.get(record_id)
    if not res:
        raise HTTPException(status_code=404, detail="质控结果不存在")
    return res


@router.get("/progress/{analysis_id}")
async def get_progress(analysis_id: str):
    # Simplified: assume completed if any result exists
    return {"analysis_id": analysis_id, "status": "completed"}


 


@router.get("/rules")
async def list_rules():
    return {"data": list(qc_rules_db.values()), "total": len(qc_rules_db)}


@router.post("/rules", response_model=QCRule)
async def create_rule(rule: QCRule):
    if rule.id in qc_rules_db:
        raise HTTPException(status_code=400, detail="质控规则已存在")
    qc_rules_db[rule.id] = rule.model_dump()
    return rule


@router.put("/rules/{rule_id}", response_model=QCRule)
async def update_rule(rule_id: str, rule: QCRule):
    if rule_id not in qc_rules_db:
        raise HTTPException(status_code=404, detail="质控规则不存在")
    qc_rules_db[rule_id] = rule.model_dump()
    return rule


@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: str):
    if rule_id not in qc_rules_db:
        raise HTTPException(status_code=404, detail="质控规则不存在")
    del qc_rules_db[rule_id]
    return {"message": "质控规则删除成功"}


@router.get("/history")
async def get_history():
    # Simplified history: return all results summary
    return {"items": list(qc_results_db.values()), "total": len(qc_results_db)}


@router.get("/poc/rules")
async def poc_rules():
    return {
        "rules": [
            {"id": "POC-001", "name": "主诉完整性（PoC）", "category": "基础", "severity": "minor"},
            {"id": "POC-002", "name": "诊断一致性（PoC）", "category": "诊断", "severity": "major"},
        ]
    }
