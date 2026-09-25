"""
医保结算清单 API 路由

挂载到 /api/medical-records 前缀下，与现有病案数据路由保持一致。
"""

import logging
from dataclasses import dataclass
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

logger = logging.getLogger(__name__)


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
    except Exception as exc:
        public_error = exc if isinstance(exc, HTTPException) else HTTPException(
            status_code=503,
            detail="结算清单质控或结果保存失败，请稍后重试",
        )
        try:
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
        except Exception:
            # 队列收尾失败不得覆盖原始脱敏错误。
            logger.warning("结算清单质控队列收尾失败: 状态写入异常")
        if isinstance(exc, HTTPException):
            raise
        raise public_error from exc

    # 结果已落库：队列收尾异常只记脱敏日志，既不降级为失败，也不写 finish_failed。
    try:
        default_workflow_queue_state_service.finish_success(
            workflow_type="settlement_qc",
            visit_id=visit_id,
            run_id=run_id,
            source_key="settlement_qc",
            patient_id=patient_id,
            institute_id=resolved_institute_id,
            user_id=user_id,
        )
    except Exception:
        logger.warning("结算清单质控队列收尾失败: 状态写入异常")
    result["persistence"] = persistence
    return result


# ============================================================
# 草稿生成端点（不依赖 medical_insurance_settlement 表）
# ============================================================

def _generate_draft(
    patient_id: str,
    visit_id: str,
    institute_id: Optional[str] = None,
) -> dict:
    """
    共享辅助函数：加载 frontpage draft + CDM SQL → 组装结算清单草稿。

    /generate（旧入口）与 /generate/qc（现代入口）共用同一组装链，但取数口径不同：
    - institute_id 为 None：旧入口语义，允许读取无法核实机构归属的 ai_generation_results。
    - institute_id 非空：现代入口语义，只使用机构过滤后的 CDM 组装，不读旧 A 源。
    """
    import json
    from ..services.settlement_assembly_service import SettlementAssemblyService
    from ..database.connection import engine
    from sqlalchemy.orm import Session
    from sqlalchemy import text

    assembly_svc = SettlementAssemblyService()

    frontpage_draft = None
    if institute_id is None:
        # 旧入口：尝试从 AI 结果表加载已有的首页抽取结果。
        # 该表没有机构归属字段，无法与已核验三坐标对齐，因此现代入口不得读取。
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
            institute_id=institute_id,
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


@dataclass(frozen=True)
class SettlementGenerateIdentity:
    """结算清单草稿质控被分析数据的唯一三坐标。"""

    institute_id: str
    patient_id: str
    visit_id: str


class SettlementGenerateIdentityAmbiguousError(RuntimeError):
    """同一就诊在三坐标上存在多个候选，或三坐标不完整，无法确定唯一病例身份。"""


class SettlementGenerateIdentityRejectedError(ValueError):
    """请求提供的病例坐标残缺（空患者/空就诊/空机构号），不允许自动补全身份。"""


class SettlementGenerateSourceUnavailableError(RuntimeError):
    """结算清单草稿质控取数依赖的数据库不可用或读取失败。"""


def _resolve_settlement_generate_identity(
    patient_id: Optional[str],
    visit_id: str,
    institute_id: Optional[str] = None,
) -> Optional[SettlementGenerateIdentity]:
    """
    在唯一权威表 ``cdm.mr`` 上确立结算清单草稿质控的三坐标。

    - 权威来源只有 cdm.mr，与落库侧的“唯一 cdm.mr 行”合同一致；结算清单表缺失时也能定身份。
    - 显式限定 ``cdm.mr`` 并参数化，不经 search_path 解析，避免把 public.mr 当成权威表。
    - 显式机构：按机构精确匹配，只在候选为空时判定缺失。
    - 未给机构：只允许唯一候选推断；多个机构同时命中时报歧义，不猜机构。
    - 同一三坐标出现重复行、或候选缺机构/缺患者时一律拒绝，不降级猜测。
    - 患者/就诊残缺、或显式传入空白机构号时直接拒绝，不用 visit 单键推断或当作未提供。
    """
    from sqlalchemy import text
    from sqlalchemy.orm import Session
    from ..database.connection import engine as db_engine

    patient_key = str(patient_id or "").strip()
    visit_key = str(visit_id or "").strip()
    if not patient_key or not visit_key:
        # 缺患者或就诊时不做单键推断，避免把其他患者/其他就诊认成请求病例。
        raise SettlementGenerateIdentityRejectedError("结算清单草稿质控病例坐标不完整")
    if institute_id is not None and not str(institute_id).strip():
        # 显式传空白机构号不等于“未提供”，不得退化为自动推断。
        raise SettlementGenerateIdentityRejectedError("结算清单草稿质控机构号为空")
    institute_key = str(institute_id).strip() if institute_id is not None else ""

    sql = (
        "SELECT institute_id, patient_id FROM cdm.mr "
        "WHERE patient_id = :patient_id AND visit_id = :visit_id"
    )
    params: Dict[str, Any] = {"patient_id": patient_key, "visit_id": visit_key}
    if institute_key:
        sql += " AND institute_id = :institute_id"
        params["institute_id"] = institute_key
    # LIMIT 2 保留“同三坐标重复行也算歧义”的判定，不需要 DISTINCT。
    sql += " LIMIT 2"

    try:
        with Session(db_engine) as session:
            rows = session.execute(text(sql), params).all()
    except Exception as exc:
        # 不把底层 DSN/驱动细节暴露给调用方与队列状态。
        logger.warning("结算清单草稿质控三坐标解析失败: 病例来源读取异常")
        raise SettlementGenerateSourceUnavailableError("结算清单草稿质控数据读取失败") from exc

    candidates = [
        (str(row[0] or "").strip(), str(row[1] or "").strip())
        for row in rows
    ]
    if not candidates:
        return None
    if len(candidates) > 1:
        raise SettlementGenerateIdentityAmbiguousError("结算清单草稿质控病例身份不唯一")
    resolved_institute_id, resolved_patient_id = candidates[0]
    if not resolved_institute_id or not resolved_patient_id:
        # 三坐标缺一不可，空机构/空患者不构成可核验身份。
        raise SettlementGenerateIdentityAmbiguousError("结算清单草稿质控病例身份不完整")
    return SettlementGenerateIdentity(resolved_institute_id, resolved_patient_id, visit_key)


@router.post("/settlement/{patient_id}/{visit_id}/generate/qc")
async def run_generated_settlement_qc(
    patient_id: str,
    visit_id: str,
    institute_id: Optional[str] = Query(
        None, description="机构号（可选，跨机构时必须显式指定）"
    ),
    current_user: dict = Depends(get_current_user),
):
    """
    对生成的结算清单草稿运行形式质控（136 条规则）。

    不依赖 medical_insurance_settlement 表中有记录。
    现代身份：先在 cdm.mr 上确立唯一三坐标，取数、队列、结果落库与落库核验共用同一身份；
    客户端传入的 institute_id 只用于消歧，不作为身份依据。
    返回的 summary 结构与旧 /qc 端点保持一致：{total, passed, failed, pass_rate}。
    """
    from ..services.settlement_formal_qc import SettlementFormalQCEngine

    user_id = _current_user_id(current_user)

    # === 1) 服务端以 cdm.mr 为唯一权威确立三坐标 ===
    try:
        identity = _resolve_settlement_generate_identity(patient_id, visit_id, institute_id)
    except SettlementGenerateIdentityRejectedError as exc:
        raise HTTPException(
            status_code=422,
            detail="结算清单草稿质控病例坐标不完整，请提供机构号、患者号与就诊号",
        ) from exc
    except SettlementGenerateIdentityAmbiguousError as exc:
        raise HTTPException(
            status_code=409,
            detail="结算清单草稿病例身份无法唯一确定，请核对机构号后重试",
        ) from exc
    except SettlementGenerateSourceUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail="结算清单草稿数据读取失败，请稍后重试",
        ) from exc
    if identity is None:
        raise HTTPException(
            status_code=404,
            detail="未找到该就诊的病案数据，无法生成结算清单草稿并质控",
        )

    # === 2) 队列以现代身份启动：source_key + 三坐标，不再用请求坐标 ===
    try:
        run_id = default_workflow_queue_state_service.start_run(
            workflow_type="settlement_qc",
            visit_id=identity.visit_id,
            patient_id=identity.patient_id,
            institute_id=identity.institute_id,
            source_key="settlement_generate_qc",
            user_id=user_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail="结算清单草稿质控任务启动失败，请稍后重试"
        ) from exc

    try:
        # === 3) 取数：机构过滤后的 CDM 组装，与解析身份同一三坐标 ===
        draft = _generate_draft(
            identity.patient_id, identity.visit_id, institute_id=identity.institute_id
        )

        # 草稿身份必须与已核验三坐标完全一致，缺失同样失败关闭，不允许产出伪结果。
        if any(
            draft.get(field) != expected
            for field, expected in (
                ("institute_id", identity.institute_id),
                ("patient_id", identity.patient_id),
                ("visit_id", identity.visit_id),
            )
        ):
            raise HTTPException(
                status_code=503,
                detail="结算清单草稿病例身份未通过核验，请稍后重试",
            )

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
                patient_id=identity.patient_id,
                visit_id=identity.visit_id,
                settlement=draft,
                summary=result["summary"],
                results=result["results"],
                source="settlement_generate_qc",
                institute_id=identity.institute_id,
            ),
            actor=current_user,
            verified_identity=VerifiedQCIdentity(
                identity.institute_id,
                identity.patient_id,
                identity.visit_id,
                "settlement_generate_qc",
            ),
        )
    except Exception as exc:
        # 解析身份之后、结果落库之前的所有失败（取数消失、组装异常、落库失败）一律脱敏 503；
        # 队列只记录对外文案，不泄露底层异常或 SQL/DSN。
        public_error = exc if isinstance(exc, HTTPException) else HTTPException(
            status_code=503,
            detail="结算清单草稿质控或结果保存失败，请稍后重试",
        )
        if not isinstance(exc, HTTPException):
            logger.warning("结算清单草稿质控执行失败: %s", type(exc).__name__)
        try:
            default_workflow_queue_state_service.finish_failed(
                workflow_type="settlement_qc",
                visit_id=identity.visit_id,
                run_id=run_id,
                source_key="settlement_generate_qc",
                patient_id=identity.patient_id,
                institute_id=identity.institute_id,
                error_message=str(public_error.detail),
                user_id=user_id,
            )
        except Exception:
            # 队列收尾失败不得覆盖原始脱敏错误。
            logger.warning("结算清单草稿质控队列收尾失败: 状态写入异常")
        if isinstance(exc, HTTPException):
            raise
        raise public_error from exc

    # 结果已落库：队列收尾异常只记脱敏日志，既不降级为失败，也不写 finish_failed。
    try:
        default_workflow_queue_state_service.finish_success(
            workflow_type="settlement_qc",
            visit_id=identity.visit_id,
            run_id=run_id,
            source_key="settlement_generate_qc",
            patient_id=identity.patient_id,
            institute_id=identity.institute_id,
            user_id=user_id,
        )
    except Exception:
        logger.warning("结算清单草稿质控队列收尾失败: 状态写入异常")
    result["persistence"] = persistence
    return result





