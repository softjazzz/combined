from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException
from datetime import datetime

router = APIRouter(prefix="/api/semantic-rules", tags=["semantic-rules"])


_rules = [
    {
        "rule_id": "SR-001",
        "rule_name": "病程记录完整性",
        "description": "检查病程记录结构是否完整",
        "category": "结构",
        "defect_level": "minor",
        "deduction_score": 2,
        "is_veto_defect": False,
        "complexity": "medium",
        "system_role": "医疗质控专家",
        "task_description": "按规则检查内容",
        "input_format": {"content": "文本"},
        "evaluation_criteria": ["包含必要字段"],
        "output_format": {"compliant": "bool"},
        "prompt_template": "请检查以下内容：\n{{content}}",
    }
]


@router.get("")
async def get_all():
    return {"success": True, "rules": _rules, "count": len(_rules)}


@router.get("/{rule_id}")
async def get_rule(rule_id: str):
    for r in _rules:
        if r["rule_id"] == rule_id:
            return {"success": True, "rule": r}
    raise HTTPException(status_code=404, detail=f"规则 {rule_id} 不存在")


@router.post("/{rule_id}/execute")
async def execute(rule_id: str, payload: Dict[str, Any]):
    content = (payload.get("input_data") or {}).get("content", "")
    compliant = len(content) > 0
    return {
        "success": True,
        "result": {
            "rule_id": rule_id,
            "rule_name": rule_id,
            "compliant": compliant,
            "confidence": 0.8,
            "evidence": content[:120],
            "reasoning": "基于内容非空的占位判断",
            "defect_details": {},
            "execution_time": 0.05,
            "token_usage": {"total": 0},
        },
    }


@router.post("/batch-execute")
async def batch_execute(payload: Dict[str, Any]):
    rule_ids: List[str] = payload.get("rule_ids", [])
    input_data = payload.get("input_data", {})
    results = []
    for rid in rule_ids:
        results.append({
            "rule_id": rid,
            "rule_name": rid,
            "compliant": True,
            "confidence": 0.8,
            "evidence": str(input_data)[:120],
            "reasoning": "占位批量执行",
            "defect_details": {},
            "execution_time": 0.05,
            "token_usage": {"total": 0},
        })
    return {"success": True, "results": results, "count": len(results)}


@router.post("/custom")
async def custom(payload: Dict[str, Any]):
    rid = f"SR-{len(_rules)+1:03d}"
    rule = {"rule_id": rid, **payload}
    _rules.append(rule)
    return {"success": True, "rule": rule, "message": f"自定义规则 {rid} 创建成功"}


@router.get("/stats")
async def stats():
    return {
        "success": True,
        "stats": {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "total_tokens": 0,
            "total_time": 0.0,
            "success_rate": 0.0,
            "avg_execution_time": 0.0,
        },
    }


@router.get("/validate-llm")
async def validate_llm():
    return {"success": True, "connection_info": {"real_llm_available": False, "mock_mode": True, "provider": "mock", "model": "mock-gpt-4"}}

