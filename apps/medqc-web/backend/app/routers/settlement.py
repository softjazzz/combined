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
):
    """
    对 AI 生成的结算清单草稿运行形式质控（136 条规则）。
    不依赖 medical_insurance_settlement 表中有记录。
    返回的 summary 结构与旧 /qc 端点保持一致：{total, passed, failed, pass_rate}。
    """
    from ..services.settlement_formal_qc import SettlementFormalQCEngine

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

    return {
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


