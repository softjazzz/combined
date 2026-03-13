"""
医保结算清单 API 路由

挂载到 /api/medical-records 前缀下，与现有病案数据路由保持一致。
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..services.settlement_service import get_settlement_service

router = APIRouter(prefix="/api/medical-records", tags=["结算清单"])


@router.get("/settlement/list")
async def list_settlements(
    dept: Optional[str] = Query(None, description="科室筛选"),
    keyword: Optional[str] = Query(None, description="搜索病案号/住院号"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
):
    """获取医保结算清单列表（分页）"""
    svc = get_settlement_service()
    return svc.list_settlements(dept=dept, keyword=keyword, page=page, page_size=page_size)


@router.get("/settlement/{patient_id}/{visit_id}")
async def get_settlement_detail(
    patient_id: str,
    visit_id: str,
    institute_id: Optional[str] = Query(None, description="机构号（可选，默认自动匹配）"),
):
    """获取单条结算清单完整详情（含诊断、手术、费用明细）"""
    svc = get_settlement_service()
    result = svc.get_settlement_detail(patient_id, visit_id, institute_id)
    if not result:
        raise HTTPException(status_code=404, detail="结算清单未找到")
    return result


@router.post("/settlement/{patient_id}/{visit_id}/qc")
async def run_settlement_qc(
    patient_id: str,
    visit_id: str,
    institute_id: Optional[str] = Query(None, description="机构号（可选）"),
):
    """对单条结算清单执行形式质控（136条规则）"""
    svc = get_settlement_service()
    result = svc.run_qc(patient_id, visit_id, institute_id)
    if not result:
        raise HTTPException(status_code=404, detail="结算清单未找到，无法执行质控")
    return result


@router.get("/settlement/rules")
async def get_settlement_qc_rules():
    """获取结算清单质控规则摘要"""
    svc = get_settlement_service()
    return svc.get_rules_summary()


# ============================================================
# 草稿生成端点（不依赖 medical_insurance_settlement 表）
# ============================================================

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
    from ..services.settlement_assembly_service import SettlementAssemblyService
    from ..database.connection import engine
    from sqlalchemy.orm import Session

    assembly_svc = SettlementAssemblyService()

    # 尝试加载首页抽取缓存
    frontpage_draft = None
    try:
        from ..services.frontpage_extraction_service import FrontPageExtractionService
        fp_svc = FrontPageExtractionService()
        # 尝试从缓存获取（如果有的话）
        cached = getattr(fp_svc, '_last_draft_cache', {}).get(f"{patient_id}_{visit_id}")
        if cached:
            frontpage_draft = cached if isinstance(cached, dict) else cached.model_dump()
    except Exception:
        pass

    with Session(engine) as db:
        result = assembly_svc.generate(
            patient_id=patient_id,
            visit_id=visit_id,
            frontpage_draft=frontpage_draft,
            db=db,
        )

    return result


@router.post("/settlement/{patient_id}/{visit_id}/generate/qc")
async def run_generated_settlement_qc(
    patient_id: str,
    visit_id: str,
):
    """
    对 AI 生成的结算清单草稿运行形式质控（136 条规则）。
    不依赖 medical_insurance_settlement 表中有记录。
    """
    from ..services.settlement_assembly_service import SettlementAssemblyService
    from ..services.settlement_formal_qc import SettlementFormalQCEngine
    from ..database.connection import engine
    from sqlalchemy.orm import Session

    assembly_svc = SettlementAssemblyService()

    with Session(engine) as db:
        draft = assembly_svc.generate(
            patient_id=patient_id,
            visit_id=visit_id,
            db=db,
        )

    # 运行质控
    qc_engine = SettlementFormalQCEngine()
    report = qc_engine.validate(draft)

    return {
        "summary": {
            "total_rules": report.total_rules,
            "passed": report.passed,
            "failed": report.failed,
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

