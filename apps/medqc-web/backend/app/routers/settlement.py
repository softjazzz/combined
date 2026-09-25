"""
医保结算清单 API 路由

挂载到 /api/medical-records 前缀下，与现有病案数据路由保持一致。
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Depends

from ..services.settlement_service import (
    SettlementIdentityAmbiguousError,
    get_settlement_service,
)
from ..core.security import get_current_user, require_roles
from ..core.pagination import page_param, page_size_param
from ..services.qc_persistence_service import (
    VerifiedQCIdentity,
    default_qc_persistence_service,
)
from ..services.workflow_queue_state_service import default_workflow_queue_state_service

def _current_user_id(current_user: Optional[Dict[str, Any]]) -> Optional[str]:
    if not current_user:
        return None
    value = current_user.get("id") or current_user.get("user_id")
    return str(value) if value else None


router = APIRouter(
    prefix="/api/medical-records",
    tags=["结算清单"],
    dependencies=[Depends(require_roles("admin", "qc_manager", "doctor", "reviewer"))],
)


def _grade_from_score(score: float) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    return "D"


def _build_settlement_persistence_result(
    *,
    patient_id: str,
    visit_id: str,
    settlement: Dict[str, Any],
    summary: Dict[str, Any],
    results: List[Dict[str, Any]],
    source: str,
    institute_id: Optional[str] = None,
) -> Dict[str, Any]:
    issues = [
        {
            "rule_code": str(item.get("rule_id") or "settlement_rule"),
            "rule_name": str(item.get("rule_name") or "控费监测规则"),
            "description": str(item.get("message") or ""),
            "severity": str(item.get("severity") or "warning"),
            "category": str(item.get("category") or "settlement"),
            "location": str(item.get("field_name") or "结算清单"),
            "suggestion": str(item.get("message") or "请复核结算清单相关字段"),
            "evidence": item.get("field_name"),
        }
        for item in results
        if not bool(item.get("passed"))
    ]
    pass_rate_raw = summary.get("pass_rate")
    try:
        overall_score = float(str(pass_rate_raw).replace("%", "")) if pass_rate_raw is not None else 0.0
    except ValueError:
        overall_score = 0.0
    department = str(
        settlement.get("discharge_dept")
        or settlement.get("admission_dept")
        or settlement.get("discharge_dept_name")
        or settlement.get("admission_dept_name")
        or ""
    )
    return {
        "record_id": f"settlement::{visit_id}",
        "workflow_type": "settlement",
        "patient_id": patient_id,
        "visit_id": visit_id,
        "overall_score": overall_score,
        "overall_grade": _grade_from_score(overall_score),
        "defect_count": len(issues),
        "issues": issues,
        "metadata": {
            "workflow_type": "settlement",
            **({"institute_id": institute_id} if institute_id is not None else {}),
            "patient_id": patient_id,
            "visit_id": visit_id,
            "department": department,
            "data_source": source,
            "trigger_source": "workstation_v4",
        },
        "analysis_engine": "settlement-formal-qc",
        "analysis_date": datetime.utcnow().isoformat() + "Z",
    }


@router.get("/settlement/list")
async def list_settlements(
    dept: Optional[str] = Query(None, description="科室筛选"),
    keyword: Optional[str] = Query(None, description="搜索病案号/住院号"),
    page: int = page_param(description="页码"),
    page_size: int = page_size_param(description="每页条数"),
):
    """获取医保结算清单列表（分页）"""
    svc = get_settlement_service()
    return svc.list_settlements(dept=dept, keyword=keyword, page=page, page_size=page_size)


@router.get("/settlement/rules")
async def get_settlement_qc_rules():
    """获取结算清单质控规则摘要"""
    svc = get_settlement_service()
    return svc.get_rules_summary()


@router.get("/settlement/rules/list")
async def list_settlement_qc_rules():
    """获取结算清单质控规则平铺列表（用于前端展示）"""
    svc = get_settlement_service()
    engine = svc._qc_engine
    rules_data = [
        {
            "rule_id": r.rule_id,
            "field_name": r.field_name,
            "rule_name": r.rule_name,
            "description": r.description,
            "severity": r.severity,
            "category": r.category,
            "affects_grouping": r.affects_grouping,
        }
        for r in engine.rules
    ]
    return {"success": True, "data": rules_data, "message": f"共 {len(rules_data)} 条结算清单质控规则"}


# --- 以下为参数化路由（必须在静态路由之后注册） ---

@router.get("/settlement/{patient_id}/{visit_id}")
async def get_settlement_detail(
    patient_id: str,
    visit_id: str,
    institute_id: Optional[str] = Query(None, description="机构号（可选，默认自动匹配）"),
):
    """获取单条结算清单完整详情（含诊断、手术、费用明细）"""
    svc = get_settlement_service()
    try:
        result = svc.get_settlement_detail(patient_id, visit_id, institute_id)
    except SettlementIdentityAmbiguousError as exc:
        raise HTTPException(status_code=409, detail="结算清单身份不唯一，请指定机构号") from exc
    if not result:
        raise HTTPException(status_code=404, detail="结算清单未找到")
    return result


@router.post("/settlement/{patient_id}/{visit_id}/qc")
async def run_settlement_qc(
    patient_id: str,
    visit_id: str,
    institute_id: Optional[str] = Query(None, description="机构号（可选）"),
    current_user: dict = Depends(get_current_user),
):
    """对单条结算清单执行形式质控（136条规则）"""
    user_id = _current_user_id(current_user)
    svc = get_settlement_service()
    try:
        resolved_institute_id = svc.resolve_settlement_institute_id(
            patient_id, visit_id, institute_id
        )
    except SettlementIdentityAmbiguousError as exc:
        raise HTTPException(status_code=409, detail="结算清单身份不唯一，请指定机构号") from exc
    if resolved_institute_id is None:
        raise HTTPException(status_code=404, detail="结算清单未找到，无法执行质控")

    try:
        run_id = default_workflow_queue_state_service.start_run(
            workflow_type="settlement_qc",
            visit_id=visit_id,
            patient_id=patient_id,
            institute_id=resolved_institute_id,
            source_key="settlement_qc",
            user_id=user_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail="结算清单质控任务启动失败，请稍后重试"
        ) from exc
    try:
        result = svc.run_qc(patient_id, visit_id, resolved_institute_id)
        if not result:
            raise HTTPException(status_code=404, detail="结算清单未找到，无法执行质控")
        settlement = result.get("settlement")
        if not isinstance(settlement, dict) or any(
            settlement.get(field) != expected
            for field, expected in (
                ("institute_id", resolved_institute_id),
                ("patient_id", patient_id),
                ("visit_id", visit_id),
            )
        ):
            raise HTTPException(status_code=409, detail="结算清单病例身份与请求不一致")
        persistence = await default_qc_persistence_service.persist_analysis(
            _build_settlement_persistence_result(
                patient_id=patient_id,
                visit_id=visit_id,
                settlement=settlement,
                summary=result.get("summary") or {},
                results=result.get("results") or [],
                source="settlement_qc",
                institute_id=resolved_institute_id,
            ),
            actor=current_user,
            verified_identity=VerifiedQCIdentity(
                resolved_institute_id, patient_id, visit_id, "settlement_qc"
            ),
        )
        default_workflow_queue_state_service.finish_success(
            workflow_type="settlement_qc",
            visit_id=visit_id,
            run_id=run_id,
            source_key="settlement_qc",
            patient_id=patient_id,
            institute_id=resolved_institute_id,
            user_id=user_id,
        )
        result["persistence"] = persistence
        return result
    except Exception as exc:
        public_error = exc if isinstance(exc, HTTPException) else HTTPException(
            status_code=503,
            detail="结算清单质控或结果保存失败，请稍后重试",
        )
        default_workflow_queue_state_service.finish_failed(
            workflow_type="settlement_qc",
            visit_id=visit_id,
            run_id=run_id,
            source_key="settlement_qc",
            patient_id=patient_id,
            institute_id=resolved_institute_id,
            error_message=str(public_error.detail),
            user_id=user_id,
        )
        if isinstance(exc, HTTPException):
            raise
        raise public_error from exc


# ============================================================
# 草稿生成端点（不依赖 medical_insurance_settlement 表）
# ============================================================

def _generate_draft(patient_id: str, visit_id: str) -> dict:
    """
    共享辅助函数：加载 frontpage draft + CDM SQL → 组装结算清单草稿。
    /generate 和 /generate/qc 统一调用此函数，保证数据一致性。
    """
    import json
    from ..services.settlement_assembly_service import SettlementAssemblyService
    from ..database.connection import engine
    from sqlalchemy.orm import Session
    from sqlalchemy import text

    assembly_svc = SettlementAssemblyService()

    # 尝试从 AI 结果表加载已有的首页抽取结果
    frontpage_draft = None
    try:
        with Session(engine) as db:
            row = db.execute(text(
                "SELECT result_data FROM ai_generation_results "
                "WHERE patient_id = :pid AND visit_id = :vid "
                "AND task_type = 'frontpage_extraction' "
                "ORDER BY created_at DESC LIMIT 1"
            ), {"pid": patient_id, "vid": visit_id}).first()
            if row and row[0]:
                frontpage_draft = json.loads(row[0]) if isinstance(row[0], str) else row[0]
    except Exception:
        pass  # 表不存在或无记录，回退到 mr 伪 draft

    with Session(engine) as db:
        return assembly_svc.generate(
            patient_id=patient_id,
            visit_id=visit_id,
            frontpage_draft=frontpage_draft,
            db=db,
        )


@router.post("/settlement/{patient_id}/{visit_id}/generate")
async def generate_settlement_from_frontpage(
    patient_id: str,
    visit_id: str,
):
    """
    从病案首页 AI 抽取结果 + CDM SQL 生成结算清单草稿。
    不写入数据库，仅返回瞬态数据。
    返回字段包含 is_draft=True, data_source='generated_from_frontpage'。
    """
    return _generate_draft(patient_id, visit_id)


@router.post("/settlement/{patient_id}/{visit_id}/generate/qc")
async def run_generated_settlement_qc(
    patient_id: str,
    visit_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    对 AI 生成的结算清单草稿运行形式质控（136 条规则）。
    不依赖 medical_insurance_settlement 表中有记录。
    返回的 summary 结构与旧 /qc 端点保持一致：{total, passed, failed, pass_rate}。
    """
    from ..services.settlement_formal_qc import SettlementFormalQCEngine

    user_id = _current_user_id(current_user)
    run_id = default_workflow_queue_state_service.start_run(
        workflow_type="settlement_qc",
        visit_id=visit_id,
        patient_id=patient_id,
        user_id=user_id,
    )

    try:
        # 使用与 /generate 完全相同的数据源
        draft = _generate_draft(patient_id, visit_id)

        # 运行质控
        qc_engine = SettlementFormalQCEngine()
        report = qc_engine.check(draft)

        # 计算通过率，与旧接口 settlement_service.run_qc 保持一致
        pass_rate = (
            f"{report.passed / report.total_rules * 100:.1f}%"
            if report.total_rules > 0
            else "0%"
        )

        result = {
            "summary": {
                "total": report.total_rules,
                "passed": report.passed,
                "failed": report.failed,
                "pass_rate": pass_rate,
            },
            "results": [
                {
                    "rule_id": r.rule_id,
                    "field_name": r.field_name,
                    "rule_name": r.rule_name,
                    "passed": r.passed,
                    "message": r.message,
                    "severity": r.severity,
                    "category": r.category,
                    "affects_grouping": r.affects_grouping,
                }
                for r in report.results
            ],
            "settlement": draft,
        }
        persistence = await default_qc_persistence_service.persist_analysis(
            _build_settlement_persistence_result(
                patient_id=patient_id,
                visit_id=visit_id,
                settlement=draft,
                summary=result["summary"],
                results=result["results"],
                source="settlement_generate_qc",
            ),
            actor=current_user,
        )
        default_workflow_queue_state_service.finish_success(
            workflow_type="settlement_qc",
            visit_id=visit_id,
            run_id=run_id,
            user_id=user_id,
        )
        result["persistence"] = persistence
        return result
    except Exception as exc:
        default_workflow_queue_state_service.finish_failed(
            workflow_type="settlement_qc",
            visit_id=visit_id,
            run_id=run_id,
            error_message=str(exc),
            user_id=user_id,
        )
        raise





