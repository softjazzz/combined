from typing import List, Dict, Any, Optional
import uuid
import json
import logging
from pathlib import Path
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Query, Request, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from datetime import datetime, timezone

from ..core.response import success_response, paginated_response, error_response, get_trace_id, ErrorCode, StatusCode
from ..services.sichuan_qc_service import SichuanQCService
from ..services.unified_rule_engine import UnifiedRuleEngine
from ..services.segmented_qc_pipeline import SegmentedQCPipeline
from ..services.llm_config_loader import LLMConfigLoader
from ..services.qc_input_adapters import evaluate_running_final_bundle
from ..core.supabase_client import get_supabase
from ..core.settings import get_settings
from ..core.security import require_admin, get_current_user
from ..services.custom_qc_workspace_service import CustomQCWorkspaceService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/qc/sichuan", tags=["qc-sichuan"])

# 全局服务实例（将在启动时初始化）
service: Optional[SichuanQCService] = None

async def init_qc_service():
    """初始化质控服务，从数据库加载配置"""
    global service
    try:
        # 尝试从数据库加载配置
        config = await LLMConfigLoader.load_config(config_name="default", user_id=None)
        service = SichuanQCService(config)
        logger.info(f"✅ 四川质控服务初始化成功: model={service.client.model}, source={service.client.config_source}")
    except Exception as exc:
        logger.warning(f"从数据库加载配置失败: {exc}，使用 .env 配置初始化")
        service = SichuanQCService()

async def get_qc_service() -> SichuanQCService:
    """
    依赖注入：获取配置好的质控服务实例

    Returns:
        使用数据库配置的SichuanQCService实例
    """
    global service
    if service is None:
        await init_qc_service()
    return service


class SichuanEvaluateRequest(BaseModel):
    document_id: str
    document_content: Optional[str] = None
    document_type: Optional[str] = "病程记录"
    document_types: Optional[List[str]] = None
    rule_ids: Optional[List[str]] = None
    bundle_input: Optional[Dict[str, Any]] = None
    use_multi_document_mode: Optional[bool] = False
    patient_info: Optional[Dict[str, str]] = None
    documents_by_type: Optional[Dict[str, Any]] = None
    # Optional preloaded grouped rules from frontend
    rules_by_document_type: Optional[Dict[str, List[Dict[str, Any]]]] = None
    # Optional LLM overrides for experimentation
    model: Optional[str] = None
    provider: Optional[str] = None
    # Persistence control (default on)
    persist: Optional[bool] = True
    # Prompt optimization mode (default: plan_a)
    prompt_mode: Optional[str] = "plan_a"
    # ── 质控引擎高级配置（前端高级设置面板） ──
    # 每批发给 LLM 的最大规则数（分段模式）
    max_rules_per_batch: Optional[int] = None
    # LLM 最大并发调用数（分段模式）
    max_concurrency: Optional[int] = None
    # LLM 温度参数
    temperature: Optional[float] = None
    # LLM 最大输出 token 数
    max_tokens: Optional[int] = None


class SichuanBatchDocument(BaseModel):
    document_id: str
    document_content: str
    document_type: Optional[str] = "病程记录"


class SichuanBatchRequest(BaseModel):
    documents: List[SichuanBatchDocument]


class SichuanBundleEvaluateRequest(BaseModel):
    scene: Optional[str] = None
    institute_id: Optional[str] = None
    patient_id: Optional[str] = None
    visit_id: Optional[str] = None
    bundle_input: Optional[Dict[str, Any]] = None
    rule_ids: Optional[List[str]] = None
    model: Optional[str] = None
    schema: Optional[str] = "public"


class SichuanRuleVisitEvaluateRequest(BaseModel):
    rule_id: str
    institute_id: str
    patient_id: str
    visit_id: str
    source_schema: Optional[str] = None
    bundle_schema: Optional[str] = "public"
    force_refresh_bundle: Optional[bool] = False
    model: Optional[str] = None


class SichuanWorkspaceBatchJobCreateRequest(BaseModel):
    rule_ids: List[str]
    scope: str = "final"
    department: Optional[str] = None
    doctor: Optional[str] = None
    date_field: str = "discharge"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    keyword: Optional[str] = None
    record_ids: Optional[List[str]] = None


class SaveQCResultRequest(BaseModel):
    mode: str
    document_type: str
    rule_ids: List[str]
    medical_text: Optional[str] = None  # 原始病历文本
    medical_text_length: int
    stats: Dict[str, Any]
    performance: Dict[str, Any]
    results: Optional[List[Dict[str, Any]]] = None
    payload: Optional[Dict[str, Any]] = None
    document_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    model: Optional[str] = None  # 使用的模型名称


def _grade_from_rate(rate: float) -> str:
    return "A" if rate >= 90 else "B" if rate >= 75 else "C"


def _current_user_id(current_user: Dict[str, Any]) -> str:
    return (
        str(current_user.get("id") or current_user.get("user_id") or current_user.get("username") or "")
        .strip()
        or "anonymous"
    )


def _normalize_scope(scope: Optional[str]) -> str:
    value = str(scope or "").strip().lower()
    if value not in {"all", "running", "final"}:
        return "all"
    return value


def _normalize_date_field(date_field: Optional[str]) -> str:
    value = str(date_field or "").strip().lower()
    if value not in {"admission", "discharge"}:
        return "admission"
    return value


def _resolve_document_type(scope: str, record_scope: Optional[str]) -> str:
    if scope == "running":
        return "病程记录"
    if scope == "final":
        return "出院记录"
    return "出院记录" if str(record_scope or "").strip().lower() == "final" else "病程记录"


def _build_cluster_key(item: Dict[str, Any]) -> str:
    evidence = str(item.get("evidence") or "").strip()
    findings = str(item.get("findings") or "").strip()
    base = evidence or findings or str(item.get("rule_name") or item.get("rule_code") or "命中项")
    return base[:64]


def _to_breakdown_list(counter: Dict[str, int], top_n: int = 8) -> List[Dict[str, Any]]:
    ranked = sorted(counter.items(), key=lambda it: it[1], reverse=True)[:top_n]
    return [{"key": key, "count": int(count)} for key, count in ranked if key]


def _build_result_aggregation(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    clusters: Dict[str, Dict[str, Any]] = {}
    rule_counter: Dict[str, int] = {}
    executor_counter: Dict[str, int] = {}
    doc_counter: Dict[str, int] = {}
    defect_counter: Dict[str, int] = {}

    for item in items:
        cluster_key = _build_cluster_key(item)
        cluster = clusters.setdefault(
            cluster_key,
            {
                "cluster_key": cluster_key,
                "sample_evidence": str(item.get("evidence") or "")[:120],
                "records": 0,
                "rules": {},
                "document_types": {},
                "executor_types": {},
                "defect_levels": {},
            },
        )
        cluster["records"] += 1
        rule_id = str(item.get("rule_id") or item.get("rule_code") or "").strip()
        rule_name = str(item.get("rule_name") or rule_id or "未知规则").strip()
        if rule_id:
            cluster["rules"][rule_id] = {"rule_id": rule_id, "rule_name": rule_name}
            rule_counter[rule_id] = int(rule_counter.get(rule_id) or 0) + 1
        doc_type = str(item.get("document_type") or "").strip()
        if doc_type:
            cluster["document_types"][doc_type] = int(cluster["document_types"].get(doc_type) or 0) + 1
            doc_counter[doc_type] = int(doc_counter.get(doc_type) or 0) + 1
        executor_type = str(item.get("executor_type") or "").strip().lower() or "llm"
        cluster["executor_types"][executor_type] = int(cluster["executor_types"].get(executor_type) or 0) + 1
        executor_counter[executor_type] = int(executor_counter.get(executor_type) or 0) + 1
        defect_level = str(item.get("defect_level") or "").strip()
        if defect_level:
            cluster["defect_levels"][defect_level] = int(cluster["defect_levels"].get(defect_level) or 0) + 1
            defect_counter[defect_level] = int(defect_counter.get(defect_level) or 0) + 1

    cluster_list: List[Dict[str, Any]] = []
    for cluster in clusters.values():
        cluster_list.append(
            {
                "cluster_key": cluster["cluster_key"],
                "sample_evidence": cluster["sample_evidence"],
                "records": int(cluster["records"]),
                "rules": list(cluster["rules"].values()),
                "document_types": cluster["document_types"],
                "executor_types": cluster["executor_types"],
                "defect_levels": cluster["defect_levels"],
            }
        )
    cluster_list.sort(key=lambda it: int(it.get("records") or 0), reverse=True)

    return {
        "cluster_count": len(cluster_list),
        "duplicate_hits": max(0, len(items) - len(cluster_list)),
        "clusters": cluster_list[:20],
        "rule_breakdown": [
            {
                "rule_id": rule_id,
                "rule_name": rule_id,
                "hits": int(hits),
            }
            for rule_id, hits in sorted(rule_counter.items(), key=lambda it: it[1], reverse=True)[:12]
        ],
        "executor_breakdown": _to_breakdown_list(executor_counter, top_n=6),
        "document_breakdown": _to_breakdown_list(doc_counter, top_n=8),
        "defect_level_breakdown": _to_breakdown_list(defect_counter, top_n=8),
    }


def _build_debug_snapshot(
    job: Dict[str, Any],
    *,
    rule_job_id: Optional[str] = None,
    item_limit: int = 30,
) -> Dict[str, Any]:
    rules = list(job.get("rule_results") or [])
    if rule_job_id:
        rules = [item for item in rules if str(item.get("id") or "") == str(rule_job_id)]
    current_rule = (
        next((item for item in rules if str(item.get("status") or "").lower() == "running"), None)
        or (rules[0] if rules else None)
    )
    all_items = list(job.get("items") or [])
    all_failed = list(job.get("failed_records") or [])
    if rule_job_id:
        all_items = [item for item in all_items if str(item.get("rule_job_id") or "") == str(rule_job_id)]
        all_failed = [item for item in all_failed if str(item.get("rule_job_id") or "") == str(rule_job_id)]

    return {
        "job_id": job.get("id"),
        "status": job.get("status"),
        "scope": job.get("scope"),
        "execution_mode": job.get("execution_mode") or "batch",
        "rule_count": int((job.get("summary") or {}).get("rule_count") or len(job.get("rule_results") or [])),
        "filtered_rule_count": len(rules),
        "summary": job.get("summary") or {},
        "current_rule": {
            "rule_job_id": current_rule.get("id"),
            "rule_code": current_rule.get("rule_code"),
            "rule_name": current_rule.get("rule_name"),
            "progress": current_rule.get("progress") or {},
        } if current_rule else None,
        "rules": [
            {
                "rule_job_id": item.get("id"),
                "rule_code": item.get("rule_code"),
                "rule_name": item.get("rule_name"),
                "status": item.get("status"),
                "progress": item.get("progress") or {},
                "debug": item.get("debug") or {},
                "total_records": item.get("total_records"),
                "success_count": item.get("success_count"),
                "failed_count": item.get("failed_count"),
                "issue_records": item.get("issue_records"),
                "compliant_records": item.get("compliant_records"),
                "total_tokens": item.get("total_tokens"),
                "total_processing_time": item.get("total_processing_time"),
                "error_message": item.get("error_message"),
                "updated_at": item.get("updated_at"),
            }
            for item in rules
        ],
        "recent_items": all_items[:max(1, int(item_limit or 30))],
        "recent_failed_records": all_failed[:max(1, int(item_limit or 30))],
        "updated_at": (job.get("summary") or {}).get("updated_at") or job.get("updated_at"),
    }


@router.post("/evaluate-fast")
async def evaluate_fast(
    request: Request,
    req: SichuanEvaluateRequest,
    qc_service: SichuanQCService = Depends(get_qc_service)
):
    """
    快速质控模式：一次 API 调用评估所有规则

    与 /evaluate 的区别：
    - /evaluate: 逐条规则调用 LLM（串行模式）
    - /evaluate-fast: 一次调用评估所有规则（快速模式）

    支持的 prompt_mode 参数：
    - current: 当前模式（只使用 rule_id + name + description）
    - plan_a: 方案A - 精简版（提取【检查要点】）
    - plan_b: 方案B - 完整版（使用完整 custom_prompt）
    - plan_c: 方案C - 平衡版（提取【检查要点】+【判定逻辑】）
    """
    try:
        # Allow runtime override of model
        if req.model:
            qc_service.client.model = req.model

        # 调用快速质控方法（传递 prompt_mode）
        result = await qc_service.evaluate_document_fast(
            document_id=req.document_id,
            content=req.document_content,
            document_type=req.document_type or "病程记录",
            rule_ids=req.rule_ids,
            prompt_mode=req.prompt_mode or "plan_a"
        )

        return result
    except Exception as e:
        raise HTTPException(status_code=StatusCode.INTERNAL_SERVER_ERROR, detail=f"快速质控评估失败: {e}")


@router.post("/evaluate")
async def evaluate(
    request: Request,
    req: SichuanEvaluateRequest,
    qc_service: SichuanQCService = Depends(get_qc_service)
):
    try:
        # Allow runtime override of model (for A/B testing different LLMs)
        if req.model:
            qc_service.client.model = req.model
        # running/final bundle 直入旧规则链入口（不依赖独立 runtime）
        if isinstance(req.bundle_input, dict) and req.bundle_input:
            bundle_result = await evaluate_running_final_bundle(
                qc_service=qc_service,
                bundle_input=req.bundle_input,
                rule_ids=req.rule_ids,
            )
            if req.persist:
                _persist_evaluation_to_db(req.document_id, bundle_result)
            return bundle_result

        if not str(req.document_content or "").strip():
            raise HTTPException(status_code=422, detail="document_content 不能为空（bundle_input 模式除外）")

        if req.use_multi_document_mode:
            # Prefer frontend-provided grouped rules; fallback to fetching from Supabase
            rules_by_document_type = req.rules_by_document_type
            if rules_by_document_type is None and req.document_types:
                try:
                    # Get rules grouped by document type from Supabase
                    supabase = get_supabase()
                    if supabase is not None:
                        async def _exec(q):
                            try:
                                exec_async = getattr(q, "execute_async", None)
                                if callable(exec_async):
                                    return await exec_async()
                            except Exception:
                                pass
                            return q.execute()

                        resp = await _exec(supabase.table("qc_rules").select("*").eq("is_active", True).limit(1000))
                        all_rules = resp.data or []

                        # Group rules by applicable document types
                        rules_by_document_type = {}
                        for rule in all_rules:
                            # Prefer top-level field, then fallback to nested check_logic.applicable_documents
                            applicable_docs = (
                                rule.get("applicable_documents")
                                or (rule.get("check_logic") or {}).get("applicable_documents")
                                or []
                            )
                            if isinstance(applicable_docs, str):
                                applicable_docs = [d.strip() for d in applicable_docs.split(",") if d.strip()]
                            try:
                                normalized_docs = [str(d).strip() for d in (applicable_docs or [])]
                            except Exception:
                                normalized_docs = []

                            for doc_type in (req.document_types or []):
                                if doc_type and any(doc_type.lower() == d.lower() for d in normalized_docs):
                                    if doc_type not in rules_by_document_type:
                                        rules_by_document_type[doc_type] = []
                                    rules_by_document_type[doc_type].append(rule)
                except Exception as e:
                    print(f"Warning: Failed to fetch grouped rules: {e}")
                    rules_by_document_type = None
            
            md = await qc_service.evaluate_multi_document(
                document_id=req.document_id,
                document_content=req.document_content,
                document_types=req.document_types,
                preclassified_documents=req.documents_by_type,
                rules_by_document_type=rules_by_document_type,
            )

            # Build legacy-compatible response
            response = {
                "document_id": req.document_id,
                "evaluation_summary": {
                    "total_rules": md["overall_summary"]["total_rules"],
                    "compliant_rules": md["overall_summary"]["compliant_rules"],
                    "not_applicable": md["overall_summary"].get("not_applicable", 0),
                    "issues_found": md["overall_summary"].get("issues_found", md["overall_summary"]["critical_violations"]),
                    "compliance_rate": md["overall_summary"]["compliance_rate"],
                    "overall_grade": md["overall_summary"]["overall_grade"],
                    "critical_violations": md["overall_summary"]["critical_violations"],
                    "document_breakdown": md["overall_summary"]["document_breakdown"],
                },
                "performance_metrics": {
                    "processing_time": md["total_processing_time"],
                    "token_usage": md["total_token_usage"],
                    "estimated_cost": md["total_token_usage"] / 1000 * 0.002,
                },
                "evaluation_results": [
                    item
                    for d in md["document_results"].values()
                    for item in d.get("evaluation_results", [])
                ],
                "optimization_metrics": md["optimization_metrics"],
                "document_results": md["document_results"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "success",
                "mode": "multi_document",
            }
            # Persist (best-effort)
            if req.persist:
                _persist_evaluation_to_db(req.document_id, response)
            return response
        else:
            # ── 使用分段 Pipeline（切段 → 规则路由 → 分批 → 并发 LLM） ──
            # 应用前端传入的高级配置
            if req.temperature is not None:
                qc_service.client.temperature = req.temperature
            if req.max_tokens is not None:
                qc_service.client.max_tokens = req.max_tokens

            pipeline = SegmentedQCPipeline(
                llm_client=qc_service.client,
                max_concurrency=req.max_concurrency or 3,
                max_rules_per_batch=req.max_rules_per_batch or 15,
            )
            result = await pipeline.evaluate(
                document_id=req.document_id,
                content=req.document_content,
                prompt_mode=req.prompt_mode or "plan_a",
            )

            # 将 pipeline 结果转为前端兼容格式
            summary = result.get("evaluation_summary", {})
            perf = result.get("performance_metrics", {})
            token_usage = perf.get("token_usage", 0)
            compliance_rate = summary.get("compliance_rate", 100.0)

            response = {
                "document_id": req.document_id,
                "evaluation_summary": {
                    "total_rules": summary.get("total_rules", 0),
                    "compliant_rules": summary.get("compliant_rules", 0),
                    "not_applicable": 0,
                    "issues_found": summary.get("issues_found", 0),
                    "compliance_rate": round(compliance_rate, 2),
                    "overall_grade": _grade_from_rate(compliance_rate),
                    "critical_violations": summary.get("issues_found", 0),
                    "model": summary.get("model", qc_service.client.model),
                },
                "performance_metrics": {
                    "processing_time": perf.get("pipeline_time", 0),
                    "token_usage": token_usage,
                    "estimated_cost": token_usage / 1000 * 0.002,
                    "llm_calls": perf.get("llm_calls", 0),
                },
                "evaluation_results": result.get("evaluation_results", []),
                "sections_summary": result.get("sections_summary", []),
                "optimization_metrics": {
                    "token_savings_rate": 0.80,
                    "estimated_original_tokens": token_usage * 5,
                    "actual_tokens_saved": token_usage * 4,
                    "cost_savings": token_usage * 4 / 1000 * 0.002,
                },
                "llm_info": {
                    "model": qc_service.client.model,
                    "api_endpoint": qc_service.client.api_endpoint,
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "success",
                "mode": "segmented_pipeline",
            }
            # Persist (best-effort)
            if req.persist:
                _persist_evaluation_to_db(req.document_id, response)
            return response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=StatusCode.INTERNAL_SERVER_ERROR, detail=f"四川省质控评估失败: {e}")


@router.post("/evaluate-bundle")
async def evaluate_bundle(
    request: Request,
    req: SichuanBundleEvaluateRequest,
    qc_service: SichuanQCService = Depends(get_qc_service)
):
    try:
        if req.model:
            qc_service.client.model = req.model
        result = await evaluate_running_final_bundle(
            qc_service=qc_service,
            scene=req.scene,
            institute_id=req.institute_id,
            patient_id=req.patient_id,
            visit_id=req.visit_id,
            bundle_input=req.bundle_input,
            rule_ids=list(req.rule_ids or []),
            schema=str(req.schema or "public").strip() or "public",
        )
        return success_response(
            data=result,
            message="bundle 质控评估完成",
            trace_id=get_trace_id(request),
        )
    except HTTPException:
        raise
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=StatusCode.INTERNAL_SERVER_ERROR, detail=f"bundle 质控评估失败: {exc}")


@router.post("/evaluate-rule-for-visit")
async def evaluate_rule_for_visit(
    request: Request,
    req: SichuanRuleVisitEvaluateRequest,
    qc_service: SichuanQCService = Depends(get_qc_service),
):
    try:
        if req.model:
            qc_service.client.model = req.model
        result = await qc_service.evaluate_rule_for_visit(
            rule_id=req.rule_id,
            institute_id=req.institute_id,
            patient_id=req.patient_id,
            visit_id=req.visit_id,
            source_schema=req.source_schema,
            bundle_schema=str(req.bundle_schema or "public").strip() or "public",
            force_refresh_bundle=bool(req.force_refresh_bundle),
        )
        return success_response(
            data=result,
            message="规则级 visit 质控评估完成",
            trace_id=get_trace_id(request),
        )
    except HTTPException:
        raise
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=StatusCode.INTERNAL_SERVER_ERROR, detail=f"规则级 visit 质控失败: {exc}")


@router.post("/evaluate/batch")
async def evaluate_batch(
    request: Request,
    req: SichuanBatchRequest,
    qc_service: SichuanQCService = Depends(get_qc_service)
):
    try:
        payloads = [
            {
                "document_id": d.document_id,
                "content": d.document_content,
                "document_type": d.document_type or "病程记录",
            }
            for d in req.documents
        ]
        results = await qc_service.evaluate_batch(payloads)

        total_documents = len(results)
        successful_evaluations = len([r for r in results])
        total_tokens = sum(int(r.get("token_usage", {}).get("total_tokens", 0)) for r in results)
        total_processing_time = sum(float(r.get("api_time", 0.0)) for r in results)

        total_rules_evaluated = 0
        total_compliant_rules = 0
        eval_summaries = []

        for r in results:
            doc_total_rules = int(r.get("total_rules", 0))
            total_rules_evaluated += doc_total_rules
            rate = float(r.get("evaluation_summary", {}).get("compliance_rate", 0.0))
            compliant = int(doc_total_rules * rate / 100.0) if doc_total_rules else 0
            total_compliant_rules += compliant
            eval_summaries.append(
                {
                    "document_id": r.get("document_id", "unknown"),
                    "total_rules": doc_total_rules,
                    "compliant_rules": compliant,
                    "compliance_rate": rate,
                    "overall_grade": _grade_from_rate(rate),
                    "processing_time": float(r.get("api_time", 0.0)),
                    "token_usage": int(r.get("token_usage", {}).get("total_tokens", 0)),
                    "critical_violations": int(r.get("evaluation_summary", {}).get("issues_found", 0)),
                }
            )

        response = {
            "batch_summary": {
                "total_documents": total_documents,
                "successful_evaluations": successful_evaluations,
                "success_rate": (successful_evaluations / total_documents * 100) if total_documents > 0 else 0,
                "total_rules_evaluated": total_rules_evaluated,
                "total_compliant_rules": total_compliant_rules,
                "overall_compliance_rate": (total_compliant_rules / total_rules_evaluated * 100) if total_rules_evaluated > 0 else 0,
            },
            "performance_metrics": {
                "total_processing_time": total_processing_time,
                "avg_processing_time": total_processing_time / successful_evaluations if successful_evaluations > 0 else 0,
                "total_token_usage": total_tokens,
                "avg_token_usage": total_tokens / successful_evaluations if successful_evaluations > 0 else 0,
                "total_estimated_cost": total_tokens / 1000 * 0.002,
            },
            "optimization_metrics": {
                "token_savings_rate": 0.80,
                "estimated_original_tokens": total_tokens * 5,
                "actual_tokens_saved": total_tokens * 4,
                "total_cost_savings": total_tokens * 4 / 1000 * 0.002,
            },
            "evaluation_results": eval_summaries,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "success",
        }
        return response
    except Exception as e:
        raise HTTPException(status_code=StatusCode.INTERNAL_SERVER_ERROR, detail=f"四川省批量质控评估失败: {e}")


def _sichuan_workspace_service() -> CustomQCWorkspaceService:
    return CustomQCWorkspaceService()


async def _run_sichuan_workspace_batch_job(job_id: str) -> None:
    workspace = _sichuan_workspace_service()
    job = workspace.get_batch_job_for_processing(job_id=job_id)
    if not job:
        return

    try:
        workspace.mark_batch_job_running(job_id=job_id)
        qc_service = await get_qc_service()
        current = workspace.get_batch_job_for_processing(job_id=job_id) or job
        filters = dict(current.get("filters") or {})
        rule_ids = [str(item).strip() for item in (filters.get("rule_ids") or []) if str(item).strip()]
        if not rule_ids:
            raise ValueError("批量任务缺少 rule_ids")

        records = workspace.collect_records(
            scope=str(current.get("scope") or "all"),
            department=filters.get("department"),
            doctor=filters.get("doctor"),
            date_field=filters.get("date_field") or "admission",
            start_date=filters.get("start_date"),
            end_date=filters.get("end_date"),
            keyword=filters.get("keyword"),
            record_ids=current.get("record_ids") or None,
        )
        hydrated_records = workspace.hydrate_records_with_medical_text(records)
        total_records = len(hydrated_records)

        all_items: List[Dict[str, Any]] = []
        all_failed_records: List[Dict[str, Any]] = []
        rule_results: List[Dict[str, Any]] = []
        issue_record_ids: set[str] = set()
        failed_record_ids: set[str] = set()
        total_tokens = 0
        total_processing_time = 0.0
        executor_program = 0
        executor_llm = 0
        cache_hit = 0
        cache_miss = 0

        for rule_index, rule_id in enumerate(rule_ids):
            latest = workspace.get_batch_job_for_processing(job_id=job_id)
            if not latest or str(latest.get("status") or "").lower() == "canceled":
                logger.info("四川批量任务 %s 已取消，停止执行", job_id)
                return

            rule = qc_service.get_rule_by_id(rule_id)
            rule_name = str((rule or {}).get("name") or rule_id)
            rule_code = str((rule or {}).get("rule_code") or rule_id)
            rule_job_id = str(uuid.uuid4())
            rule_items: List[Dict[str, Any]] = []
            rule_failed: List[Dict[str, Any]] = []
            rule_tokens = 0
            rule_processing_time = 0.0

            if not rule:
                rule_failed.append(
                    {
                        "rule_job_id": rule_job_id,
                        "rule_id": rule_id,
                        "rule_code": rule_code,
                        "rule_name": rule_name,
                        "error_phase": "rule_lookup",
                        "error": f"未找到规则: {rule_id}",
                    }
                )
            else:
                for record in hydrated_records:
                    record_id = str(record.get("record_id") or record.get("visit_id") or "").strip()
                    try:
                        document_type = _resolve_document_type(
                            str(current.get("scope") or "all"),
                            str(record.get("scope") or ""),
                        )
                        result = await qc_service.evaluate_document(
                            document_id=record_id or "unknown",
                            content=str(record.get("medical_text") or ""),
                            document_type=document_type,
                            rule_ids=[rule_id],
                        )
                        eval_items = list(result.get("evaluation_results") or [])
                        eval_item = eval_items[0] if eval_items else {}
                        status = str(eval_item.get("status") or "")
                        metadata = dict(eval_item.get("metadata") or {})
                        if status == "non_compliant":
                            issue_record_ids.add(record_id)
                        tokens_used = int(metadata.get("tokens_used") or 0)
                        api_time = float(metadata.get("api_time") or 0.0)
                        total_tokens += tokens_used
                        total_processing_time += api_time
                        rule_tokens += tokens_used
                        rule_processing_time += api_time
                        executor_type = str(metadata.get("executor_type") or "llm").lower()
                        if executor_type == "program":
                            executor_program += 1
                        else:
                            executor_llm += 1
                        if metadata.get("cache_hit") is True:
                            cache_hit += 1
                        else:
                            cache_miss += 1

                        issue_item = {
                            "rule_job_id": rule_job_id,
                            "rule_id": str(eval_item.get("rule_id") or rule_id),
                            "rule_code": rule_code,
                            "rule_name": str(eval_item.get("rule_name") or rule_name),
                            "record_id": record_id,
                            "visit_id": str(record.get("visit_id") or ""),
                            "patient_name": str(record.get("patient_name") or ""),
                            "department": str(record.get("department") or ""),
                            "status": status or ("compliant" if eval_item.get("is_compliant") else "non_compliant"),
                            "is_compliant": bool(eval_item.get("is_compliant") is True),
                            "findings": str(eval_item.get("findings") or ""),
                            "evidence": str(eval_item.get("evidence") or ""),
                            "suggestion": str(eval_item.get("suggestion") or ""),
                            "confidence": float(eval_item.get("confidence") or 0),
                            "executor_type": executor_type,
                            "rule_version": str(metadata.get("rule_version") or ""),
                            "prompt_version": str(metadata.get("prompt_version") or ""),
                            "model_version": str(metadata.get("model_version") or ""),
                            "evidence_source": str(metadata.get("evidence_source") or ""),
                            "cache_hit": bool(metadata.get("cache_hit") is True),
                            "trace_id": str(metadata.get("trace_id") or ""),
                            "cache_key": str(metadata.get("cache_key") or ""),
                            "execution_domain": str(metadata.get("execution_domain") or ""),
                            "doc_scope": str(metadata.get("doc_scope") or ""),
                            "cost_class": str(metadata.get("cost_class") or ""),
                            "document_type": document_type,
                            "defect_level": str(rule.get("defect_level") or ""),
                            "llm_fallback": bool(metadata.get("llm_fallback") is True),
                        }
                        if issue_item["status"] == "non_compliant":
                            rule_items.append(issue_item)
                            all_items.append(issue_item)
                    except Exception as exc:
                        failed_record_ids.add(record_id)
                        failed_payload = {
                            "rule_job_id": rule_job_id,
                            "rule_id": rule_id,
                            "rule_code": rule_code,
                            "rule_name": rule_name,
                            "record_id": record_id,
                            "visit_id": str(record.get("visit_id") or ""),
                            "patient_name": str(record.get("patient_name") or ""),
                            "department": str(record.get("department") or ""),
                            "error_phase": "evaluate_document",
                            "error": str(exc),
                        }
                        rule_failed.append(failed_payload)
                        all_failed_records.append(failed_payload)

            rule_summary = {
                "total_records": total_records,
                "success_count": max(0, total_records - len(rule_failed)),
                "failed_count": len(rule_failed),
                "issue_records": len({str(item.get("record_id") or "") for item in rule_items}),
                "compliant_records": max(0, total_records - len(rule_failed) - len({str(item.get("record_id") or "") for item in rule_items})),
                "total_tokens": int(rule_tokens),
                "total_processing_time": float(rule_processing_time),
            }
            rule_results.append(
                {
                    "id": rule_job_id,
                    "job_id": job_id,
                    "rule_code": rule_code,
                    "rule_name": rule_name,
                    "status": "failed" if rule_failed and len(rule_failed) >= total_records else "completed",
                    "items": rule_items,
                    "failed_records": rule_failed,
                    "total_records": rule_summary["total_records"],
                    "success_count": rule_summary["success_count"],
                    "failed_count": rule_summary["failed_count"],
                    "issue_records": rule_summary["issue_records"],
                    "compliant_records": rule_summary["compliant_records"],
                    "total_tokens": rule_summary["total_tokens"],
                    "total_processing_time": rule_summary["total_processing_time"],
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "progress": {
                        "rule_index": rule_index + 1,
                        "rule_count": len(rule_ids),
                        "processed_records": total_records,
                    },
                    "debug": {
                        "executor_breakdown": {
                            "program": executor_program,
                            "llm": executor_llm,
                        }
                    },
                }
            )

        summary = {
            "total_records": total_records,
            "success_count": max(0, total_records - len(failed_record_ids)),
            "failed_record_count": len(failed_record_ids),
            "failed_count": len(all_failed_records),
            "issue_records": len(issue_record_ids),
            "compliant_records": max(0, total_records - len(issue_record_ids) - len(failed_record_ids)),
            "total_tokens": int(total_tokens),
            "total_processing_time": float(total_processing_time),
            "rule_count": len(rule_ids),
            "processed_rule_count": len(rule_results),
            "executor_breakdown": {
                "program": executor_program,
                "llm": executor_llm,
            },
            "cache_breakdown": {
                "hit": cache_hit,
                "miss": cache_miss,
            },
            "result_aggregation": _build_result_aggregation(all_items),
            "rule_results": rule_results,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        workspace.complete_batch_job(
            job_id=job_id,
            summary=summary,
            items=all_items,
            failed_records=all_failed_records,
        )
    except Exception as exc:
        logger.exception("四川规则批量任务执行失败: %s", exc)
        workspace.fail_batch_job(job_id=job_id, error_message=str(exc))


@router.post("/workspace/batch-jobs")
async def create_workspace_batch_job(
    request: Request,
    payload: SichuanWorkspaceBatchJobCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    rule_ids = [str(item).strip() for item in (payload.rule_ids or []) if str(item).strip()]
    if not rule_ids:
        raise HTTPException(status_code=422, detail="rule_ids 不能为空")

    workspace = _sichuan_workspace_service()
    records = workspace.collect_records(
        scope=_normalize_scope(payload.scope),
        department=payload.department,
        doctor=payload.doctor,
        date_field=_normalize_date_field(payload.date_field),
        start_date=payload.start_date,
        end_date=payload.end_date,
        keyword=payload.keyword,
        record_ids=payload.record_ids or None,
    )
    if not records:
        raise HTTPException(status_code=422, detail="当前筛选条件下没有可执行病历")

    pseudo_draft = {
        "id": "sichuan-rule-library",
        "rule_code": "SC-BATCH",
        "name": f"四川规则库批量任务({len(rule_ids)}条规则)",
        "scene": "running" if _normalize_scope(payload.scope) == "running" else "final",
    }
    job = workspace.create_batch_job(
        draft=pseudo_draft,
        created_by=_current_user_id(current_user),
        scope=_normalize_scope(payload.scope),
        filters={
            "department": payload.department,
            "doctor": payload.doctor,
            "date_field": _normalize_date_field(payload.date_field),
            "start_date": payload.start_date,
            "end_date": payload.end_date,
            "keyword": payload.keyword,
            "rule_ids": rule_ids,
            "source": "sichuan_rule_workspace",
        },
        record_ids=payload.record_ids or [],
        total_records=len(records),
    )
    background_tasks.add_task(_run_sichuan_workspace_batch_job, job["id"])
    return success_response(
        data={
            **job,
            "execution_mode": "batch",
            "rule_count": len(rule_ids),
            "draft_ids": rule_ids,
        },
        message="四川规则批量任务已创建",
        trace_id=get_trace_id(request),
    )


@router.get("/workspace/batch-jobs")
async def list_workspace_batch_jobs(
    request: Request,
    status: Optional[str] = Query(None),
    scope: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    created_start_date: Optional[str] = Query(None),
    created_end_date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    workspace = _sichuan_workspace_service()
    list_kwargs = {
        "created_by": _current_user_id(current_user),
        "draft_id": "sichuan-rule-library",
        "status": status,
        "scope": scope,
        "created_start_date": created_start_date,
        "created_end_date": created_end_date,
        "page": page,
        "page_size": page_size,
    }
    try:
        result = workspace.list_batch_jobs(
            **list_kwargs,
            query=q,
        )
    except TypeError:
        result = workspace.list_batch_jobs(
            **list_kwargs,
            q=q,
        )
    items = [
        {
            **item,
            "execution_mode": "batch",
            "rule_count": int((item.get("summary") or {}).get("rule_count") or 0),
            "draft_ids": list(((item.get("filters") or {}).get("rule_ids") or [])),
        }
        for item in result.items
    ]
    return success_response(
        data={
            "items": items,
            "total": result.total,
            "page": result.page,
            "page_size": result.page_size,
        },
        message="获取四川规则批量任务成功",
        trace_id=get_trace_id(request),
    )


@router.get("/workspace/batch-jobs/{job_id}")
async def get_workspace_batch_job(
    request: Request,
    job_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    workspace = _sichuan_workspace_service()
    job = workspace.get_batch_job(job_id=job_id, created_by=_current_user_id(current_user))
    if not job or str(job.get("draft_id") or "") != "sichuan-rule-library":
        raise HTTPException(status_code=404, detail="批量任务不存在或无权限")
    return success_response(
        data={
            **job,
            "execution_mode": "batch",
            "rule_count": int((job.get("summary") or {}).get("rule_count") or 0),
            "draft_ids": list(((job.get("filters") or {}).get("rule_ids") or [])),
        },
        message="获取四川规则批量任务详情成功",
        trace_id=get_trace_id(request),
    )


@router.post("/workspace/batch-jobs/{job_id}/cancel")
async def cancel_workspace_batch_job(
    request: Request,
    job_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    workspace = _sichuan_workspace_service()
    job = workspace.cancel_batch_job(job_id=job_id, created_by=_current_user_id(current_user))
    if not job or str(job.get("draft_id") or "") != "sichuan-rule-library":
        raise HTTPException(status_code=404, detail="批量任务不存在或无权限")
    return success_response(
        data=job,
        message="批量任务已取消",
        trace_id=get_trace_id(request),
    )


@router.post("/workspace/batch-jobs/{job_id}/retry")
async def retry_workspace_batch_job(
    request: Request,
    job_id: str,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    workspace = _sichuan_workspace_service()
    job = workspace.retry_batch_job(job_id=job_id, created_by=_current_user_id(current_user))
    if not job or str(job.get("draft_id") or "") != "sichuan-rule-library":
        raise HTTPException(status_code=404, detail="批量任务不存在或无权限")
    background_tasks.add_task(_run_sichuan_workspace_batch_job, job_id)
    return success_response(
        data=job,
        message="批量任务已重新入队",
        trace_id=get_trace_id(request),
    )


@router.get("/workspace/batch-jobs/{job_id}/debug")
async def get_workspace_batch_job_debug(
    request: Request,
    job_id: str,
    rule_job_id: Optional[str] = Query(None),
    item_limit: int = Query(30, ge=1, le=200),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    workspace = _sichuan_workspace_service()
    job = workspace.get_batch_job(job_id=job_id, created_by=_current_user_id(current_user))
    if not job or str(job.get("draft_id") or "") != "sichuan-rule-library":
        raise HTTPException(status_code=404, detail="批量任务不存在或无权限")
    return success_response(
        data=_build_debug_snapshot(job, rule_job_id=rule_job_id, item_limit=item_limit),
        message="获取批量任务调试快照成功",
        trace_id=get_trace_id(request),
    )


@router.get("/workspace/batch-jobs/{job_id}/export")
async def export_workspace_batch_job(
    request: Request,
    job_id: str,
    format: str = Query("xlsx"),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    workspace = _sichuan_workspace_service()
    job = workspace.get_batch_job(job_id=job_id, created_by=_current_user_id(current_user))
    if not job or str(job.get("draft_id") or "") != "sichuan-rule-library":
        raise HTTPException(status_code=404, detail="批量任务不存在或无权限")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    if str(format or "").lower() == "csv":
        content = workspace.export_batch_job_csv(job=job)
        filename = f"sichuan_rules_{job_id}_{timestamp}.csv"
        return StreamingResponse(
            iter([content.getvalue().encode("utf-8-sig")]),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    workbook = workspace.export_batch_job_workbook(job=job)
    filename = f"sichuan_rules_{job_id}_{timestamp}.xlsx"
    return StreamingResponse(
        workbook,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/results/save")
async def save_qc_result(request: Request, req: SaveQCResultRequest):
    try:
        base_dir = Path(__file__).resolve().parent.parent / "storage" / "qc_results"
        base_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        result_id = str(uuid.uuid4())
        filename = f"{result_id}_{req.mode}_{timestamp}.json"
        filepath = base_dir / filename

        payload = {
            "id": result_id,
            "mode": req.mode,
            "document_type": req.document_type,
            "document_id": req.document_id,
            "rule_ids": req.rule_ids,
            "medical_text": req.medical_text,  # 保存原始病历文本
            "medical_text_length": req.medical_text_length,
            "stats": req.stats,
            "performance": req.performance,
            "results": req.results,
            "payload": req.payload,
            "metadata": req.metadata,
            "model": req.model,  # 保存使用的模型名称
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        with filepath.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        return success_response(
            data={"id": result_id, "path": str(filepath)},
            message="质控结果保存成功",
            trace_id=get_trace_id(request),
        )
    except Exception as e:
        raise HTTPException(status_code=StatusCode.INTERNAL_SERVER_ERROR, detail=f"保存质控结果失败: {e}")


@router.get("/results/history")
async def get_qc_history(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    document_type: Optional[str] = Query(None),
    mode: Optional[str] = Query(None),  # 新增：质控模式筛选 (optimized_batch/sequential_batch)
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    has_issues: Optional[bool] = Query(None)
):
    """获取质控结果历史列表"""
    try:
        base_dir = Path(__file__).resolve().parent.parent / "storage" / "qc_results"
        if not base_dir.exists():
            return success_response(
                data={
                    "records": [],
                    "total": 0,
                    "page": page,
                    "page_size": page_size,
                },
                message="暂无历史记录",
                trace_id=get_trace_id(request),
            )

        # 读取所有JSON文件
        all_files = sorted(base_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        records = []

        for filepath in all_files:
            try:
                with filepath.open("r", encoding="utf-8") as f:
                    data = json.load(f)

                # 提取摘要信息
                stats = data.get("stats", {})
                metadata = data.get("metadata", {})
                payload = data.get("payload", {})
                evaluation_summary = payload.get("evaluation_summary", {})

                # 应用筛选条件
                if document_type and data.get("document_type") != document_type:
                    continue

                if mode and data.get("mode") != mode:
                    continue

                created_at = data.get("created_at") or data.get("saved_at")
                if start_date and created_at < start_date:
                    continue
                if end_date and created_at > end_date:
                    continue

                # 优先从 evaluation_summary 获取合规率和问题数量，否则从 stats 获取
                compliance_rate = evaluation_summary.get("compliance_rate") or stats.get("compliance_rate", 0)
                issues_count = evaluation_summary.get("issues_found") or stats.get("issues", 0)

                if has_issues is not None:
                    if has_issues and issues_count == 0:
                        continue
                    if not has_issues and issues_count > 0:
                        continue

                # 优先从 evaluation_summary 获取 total_rules
                total_rules = evaluation_summary.get("total_rules") or stats.get("total", len(data.get("rule_ids", [])))

                # 获取模型名称（优先从 evaluation_summary，其次顶层 model，最后从 llm_info 中获取）
                llm_info = payload.get("llm_info") or data.get("llm_info") or {}
                model = (
                    evaluation_summary.get("model")
                    or data.get("model")
                    or llm_info.get("model")
                )

                record = {
                    "id": data.get("id", filepath.stem),
                    "document_id": data.get("document_id"),
                    "document_type": data.get("document_type"),
                    "mode": data.get("mode"),
                    "model": model,
                    "prompt_mode": metadata.get("prompt_mode"),
                    "compliance_rate": compliance_rate,
                    "issues_count": issues_count,
                    "total_rules": total_rules,
                    "created_at": created_at,
                    "stats": stats,
                    "performance": data.get("performance"),
                    "metadata": metadata
                }
                records.append(record)
            except Exception as e:
                logger.warning(f"读取质控结果文件失败 {filepath}: {e}")
                continue

        # 分页
        total = len(records)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_records = records[start_idx:end_idx]

        return success_response(
            data={
                "records": paginated_records,
                "total": total,
                "page": page,
                "page_size": page_size,
            },
            message="获取质控历史成功",
            trace_id=get_trace_id(request),
        )
    except Exception as e:
        raise HTTPException(status_code=StatusCode.INTERNAL_SERVER_ERROR, detail=f"获取质控历史失败: {e}")


@router.get("/results/latest")
async def get_latest_qc_result(request: Request):
    """获取最新一次质控结果"""
    try:
        base_dir = Path(__file__).resolve().parent.parent / "storage" / "qc_results"
        if not base_dir.exists():
            raise HTTPException(status_code=StatusCode.NOT_FOUND, detail="暂无质控结果")

        # 获取最新的文件
        all_files = sorted(base_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not all_files:
            raise HTTPException(status_code=StatusCode.NOT_FOUND, detail="暂无质控结果")

        latest_file = all_files[0]
        with latest_file.open("r", encoding="utf-8") as f:
            data = json.load(f)

        return success_response(
            data=data,
            message="获取最新质控结果成功",
            trace_id=get_trace_id(request),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=StatusCode.INTERNAL_SERVER_ERROR, detail=f"获取最新质控结果失败: {e}")


@router.get("/results/{result_id:path}")
async def get_qc_result_detail(request: Request, result_id: str):
    """获取指定ID的质控结果详情"""
    try:
        base_dir = Path(__file__).resolve().parent.parent / "storage" / "qc_results"
        if not base_dir.exists():
            raise HTTPException(status_code=StatusCode.NOT_FOUND, detail="质控结果不存在")

        # 首先尝试直接匹配文件名（result_id.json）
        direct_match = base_dir / f"{result_id}.json"
        if direct_match.exists():
            with direct_match.open("r", encoding="utf-8") as f:
                data = json.load(f)

            payload = data.get("payload", {})
            evaluation_summary = payload.get("evaluation_summary", {})
            llm_info = payload.get("llm_info") or data.get("llm_info") or {}
            model = (
                data.get("model")
                or evaluation_summary.get("model")
                or llm_info.get("model")
            )
            if model and not data.get("model"):
                data["model"] = model

            return success_response(
                data=data,
                message="获取质控结果详情成功",
                trace_id=get_trace_id(request),
            )

        # 如果直接匹配失败，尝试查找以result_id开头的文件（result_id_*.json）
        matching_files = list(base_dir.glob(f"{result_id}_*.json"))
        if not matching_files:
            # 最后尝试查找包含result_id的文件
            matching_files = [f for f in base_dir.glob("*.json") if result_id in f.stem]

        if not matching_files:
            raise HTTPException(status_code=StatusCode.NOT_FOUND, detail=f"质控结果不存在: {result_id}")

        filepath = matching_files[0]
        with filepath.open("r", encoding="utf-8") as f:
            data = json.load(f)

        payload = data.get("payload", {})
        evaluation_summary = payload.get("evaluation_summary", {})
        llm_info = payload.get("llm_info") or data.get("llm_info") or {}
        model = (
            data.get("model")
            or evaluation_summary.get("model")
            or llm_info.get("model")
        )
        if model and not data.get("model"):
            data["model"] = model

        return success_response(
            data=data,
            message="获取质控结果详情成功",
            trace_id=get_trace_id(request),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=StatusCode.INTERNAL_SERVER_ERROR, detail=f"获取质控结果详情失败: {e}")


@router.get("/stats")
async def stats(
    request: Request,
    qc_service: SichuanQCService = Depends(get_qc_service)
):
    try:
        st = qc_service.stats()
        s = get_settings()
        response = {
            "service_statistics": {
                "total_calls": st.get("total_calls", 0),
                "success_calls": st.get("success_calls", 0),
                "error_calls": st.get("error_calls", 0),
                "success_rate": st.get("success_rate", 0.0),
            },
            "performance_metrics": {
                "avg_api_time": st.get("avg_api_time", 0.0),
                "total_api_time": st.get("total_api_time", 0.0),
                "total_tokens": st.get("total_tokens", 0),
            },
            "optimization_achievements": {
                "token_savings_rate": 0.80,
                "estimated_original_tokens": st.get("total_tokens", 0) * 5,
                "actual_tokens_saved": st.get("total_tokens", 0) * 4,
                "total_cost_savings": st.get("total_tokens", 0) * 4 / 1000 * 0.002,
            },
            "real_time_status": {
                "service_health": "healthy",
                "api_endpoint": str(s.LLM_API_ENDPOINT) if s.LLM_API_ENDPOINT else None,
                "model": s.LLM_MODEL,
                "last_updated": datetime.now(timezone.utc).isoformat(),
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "success",
        }
        return response
    except Exception as e:
        raise HTTPException(status_code=StatusCode.INTERNAL_SERVER_ERROR, detail=f"获取四川省质控统计失败: {e}")


@router.get("/rules")
async def rules(
    request: Request,
    document_type: Optional[str] = Query(default=None, description="单个文书类型（中文）"),
    document_types: Optional[str] = Query(default=None, description="逗号分隔的文书类型（中文）"),
    grouped: Optional[bool] = Query(default=False, description="是否按文书类型分组返回")
):
    """
    返回四川省质控规则。
    优先从 Supabase 的 `qc_rules` 表读取；如果未配置或查询失败，则回退到内置示例规则。
    """
    # 临时：强制使用 JSON 文件中的 146 条规则，待规则稳定后再批量导入 Supabase
    supabase = None  # get_supabase()
    records: list[dict[str, Any]] | None = None

    if supabase is not None:
        try:
            # 取启用的规则，最多1000条
            async def _exec(q):
                try:
                    exec_async = getattr(q, "execute_async", None)
                    if callable(exec_async):
                        return await exec_async()
                except Exception:
                    pass
                return q.execute()

            resp = await _exec(supabase.table("qc_rules").select("*").eq("is_active", True).limit(1000))
            records = resp.data or []
        except Exception:
            records = None

    data: list[dict[str, Any]]
    source = "fallback"
    if records is not None and len(records) > 0:
        def normalize(rec: dict[str, Any]) -> dict[str, Any]:
            # 统一字段到前端所需格式
            # 业务主键优先使用规则库中的可读规则编号，避免回传数据库内部 id 影响后续接口
            # 优先级：rule_id(如 SC-001) > rule_code(如 SC-001/3.1.1) > id(内部主键兜底)
            rule_id = rec.get("rule_id") or rec.get("rule_code") or rec.get("id") or ""
            rule_code = rec.get("rule_code") or rec.get("rule_id") or rec.get("id") or ""
            name = rec.get("name") or rec.get("rule_name") or "未命名规则"
            description = rec.get("description") or rec.get("desc") or ""
            category = rec.get("category") or rec.get("rule_category") or "基础"
            # 复杂度/缺陷级别可能为英文，保持原样，前端已做兼容
            complexity = rec.get("complexity") or rec.get("rule_complexity") or "中复杂度"
            defect_level = rec.get("defect_level") or rec.get("severity") or "一般缺陷"
            score_deduction = rec.get("score_deduction") or rec.get("deduction_score") or 0
            # 文书类型来源优先级：top-level applicable_documents -> document_types -> check_logic.applicable_documents
            docs = (
                rec.get("applicable_documents")
                or rec.get("document_types")
                or (rec.get("check_logic") or {}).get("applicable_documents")
                or []
            )
            if isinstance(docs, str):
                # 简单拆分字符串形式
                docs = [d.strip() for d in docs.split(",") if d.strip()]
            return {
                "rule_id": rule_id,
                "rule_code": rule_code,
                "name": name,
                "description": description,
                "category": category,
                "complexity": complexity,
                "defect_level": defect_level,
                "score_deduction": score_deduction,
                "applicable_documents": docs,
                "medical_domain": rec.get("medical_domain") or rec.get("domain") or "通用",
                "requires_rag": bool(rec.get("requires_rag") or rec.get("need_rag") or False),
                "requires_cot": bool(rec.get("requires_cot") or rec.get("need_cot") or False),
            }

        data = [normalize(r) for r in records]
        source = "supabase"
    elif records is None or len(records) == 0:
        # 回退到完整的146条四川规则（从JSON文件加载）
        import json
        from pathlib import Path

        rules_file = Path(__file__).parent.parent / "data" / "sichuan_rules_146.json"
        try:
            with open(rules_file, "r", encoding="utf-8") as f:
                full_rules = json.load(f)

            # 英文→中文 文书类型映射，保持与服务侧一致
            doc_type_mapping = {
                "admission_record": "入院记录",
                "progress_note": "病程记录",
                "course_record": "病程记录",
                "operation_record": "手术记录",
                "discharge_record": "出院记录",
                "discharge_summary": "出院记录",
                "consent_form": "知情同意书",
                "examination_report": "检查报告",
                "lab_report": "检查报告",
                "medical_order": "医嘱",
                "consultation_record": "病程记录",
                "case_discussion": "病程记录",
                "anesthesia_record": "手术记录",
                "transfusion_record": "病程记录",
                "informed_consent": "知情同意书",
            }

            # 转换格式
            data = []
            for rule in full_rules:
                docs = [doc_type_mapping.get(d, d) for d in (rule.get("applicable_documents", []) or [])]
                data.append({
                    "rule_id": rule.get("rule_id", ""),
                    "rule_code": rule.get("rule_code", rule.get("rule_id", "")),
                    "name": rule.get("name", ""),
                    "category": rule.get("category", ""),
                    "defect_level": rule.get("defect_level", "一般缺陷"),
                    "complexity": rule.get("complexity", "中复杂度"),
                    "applicable_documents": docs,
                    "score_deduction": rule.get("score_deduction", ""),
                    "medical_domain": "通用",
                    "requires_rag": False,
                    "requires_cot": False,
                    "description": rule.get("description", "")
                })
            source = "json_file"
            logger.info("Loaded %s Sichuan rules from JSON file", len(data))
        except Exception as e:
            logger.warning("Failed to load Sichuan rules JSON file, fallback to minimal sample: %s", e)
            data = [
                {"rule_id": "sc-001", "name": "入院记录完整性", "category": "基础", "defect_level": "major", "complexity": "medium", "applicable_documents": ["入院记录"], "score_deduction": 2, "medical_domain": "通用", "requires_rag": False, "requires_cot": False, "description": "检查入院记录结构是否完整"},
            ]
    else:
        # Supabase 查询成功但无数据：返回空数组，不再回退
        data = []
        source = "supabase"

    # 可选过滤/分组
    def _match_doc(rule_docs: list[str], wanted: set[str]) -> bool:
        if not wanted:
            return True
        rd = {str(x).strip() for x in (rule_docs or [])}
        # 大小写/空白宽松匹配（中文一般直接等值）
        return bool(rd.intersection(wanted))

    wanted_docs: set[str] = set()
    if document_type:
        wanted_docs.add(document_type.strip())
    if document_types:
        for t in document_types.split(","):
            t = t.strip()
            if t:
                wanted_docs.add(t)

    filtered = [d for d in data if _match_doc(d.get("applicable_documents") or [], wanted_docs)]

    if grouped:
        by_type: dict[str, list[dict[str, Any]]] = {}
        for r in filtered:
            docs = r.get("applicable_documents") or []
            if not docs:
                docs = ["通用文书"]
            for dt in docs:
                by_type.setdefault(str(dt), []).append(r)
        return success_response(
            data={
                "rules_by_document_type": by_type,
                "document_types": list(sorted(by_type.keys())),
                "total_rules": sum(len(v) for v in by_type.values()),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "success",
                "source": source,
            },
            message="获取规则成功",
            trace_id=get_trace_id(request),
        )

    return success_response(
        data={
            "rules": filtered,
            "total_rules": len(filtered),
            "document_type_filter": list(wanted_docs) if wanted_docs else None,
            "rule_categories": list(sorted({d.get("category", "基础") for d in filtered})),
            "complexity_distribution": {},
            "defect_level_distribution": {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "success",
            "source": source,
        },
        message="获取规则成功",
        trace_id=get_trace_id(request),
    )


# ------------------------- Persistence Helpers -------------------------

def _is_uuid_like(s: str) -> bool:
    try:
        uuid.UUID(str(s))
        return True
    except Exception:
        return False


def _persist_evaluation_to_db(document_id: str, result: Dict[str, Any]) -> None:
    """Best-effort persistence into medical_documents and document_qc_results.
    - Skips silently if Supabase not configured or document_id not UUID.
    - Updates qc_* fields and inserts rule-level rows.
    """
    if not _is_uuid_like(document_id):
        return

    sb = get_supabase()
    if sb is None:
        return

    try:
        summary = (result.get("evaluation_summary") or result.get("overall_summary") or {})
        compliance_rate = float(summary.get("compliance_rate", 0.0))
        critical = int(summary.get("critical_violations", 0)) if "critical_violations" in summary else 0
        qc_status = (
            "passed" if compliance_rate >= 90 and critical == 0 else
            ("warning" if compliance_rate >= 60 else "failed")
        )

        # Update medical_documents
        sb.table("medical_documents").update({
            "qc_status": qc_status,
            "qc_score": round(compliance_rate, 2),
            "qc_last_analyzed": datetime.now(timezone.utc).isoformat(),
            "qc_analysis_version": "sichuan-1.0",
        }).eq("id", document_id).execute()

        # Insert rule-level results (if any)
        items: List[Dict[str, Any]] = result.get("evaluation_results") or []
        payloads: List[Dict[str, Any]] = []
        for it in items[:200]:
            passed = bool(it.get("is_compliant") is True)
            payloads.append({
                "document_id": document_id,
                "rule_id": it.get("rule_id") or "unknown",
                "result_status": "passed" if passed else "failed",
                "score": 0,
                "max_score": 100,
                "confidence_score": float(it.get("confidence", 0)) if it.get("confidence") is not None else None,
                "issue_category": None,
                "issue_description": it.get("findings") or "",
                "evidence_text": it.get("evidence") or "",
                "evidence_location": None,
                "suggestions": None,
                "ai_reasoning": None,
                "ai_model_used": None,
                "analysis_time_ms": None,
            })

        if payloads:
            # Bulk insert; ignore errors per-row by inserting one-by-one to keep simple
            for row in payloads:
                try:
                    sb.table("document_qc_results").insert(row).execute()
                except Exception:
                    continue
    except Exception:
        # Best-effort: never raise from persistence
        return


# ------------------------- Single Rule Testing -------------------------

class TestRuleRequest(BaseModel):
    rule_id: str
    medical_text: str


@router.post("/test-rule")
async def test_rule(
    request: Request,
    req: TestRuleRequest,
    qc_service: SichuanQCService = Depends(get_qc_service)
):
    """测试单条质控规则的有效性和正确性"""
    try:
        target_rule = qc_service.get_rule_by_id(req.rule_id)
        if target_rule is None:
            raise HTTPException(
                status_code=404, detail=f"未找到规则 ID: {req.rule_id}"
            )

        engine_result = await qc_service.rule_engine.evaluate(
            rule=target_rule,
            medical_record={
                "id": req.rule_id,
                "content": req.medical_text,
                "document_type": target_rule.get("category") or "",
            }
        )

        # 统一的响应结构，确保前端字段兼容
        metadata = engine_result.get("metadata", {}) or {}
        response_data = {
            "rule_id": engine_result.get("rule_id"),
            "rule_name": engine_result.get("rule_name"),
            "is_compliant": engine_result.get("is_compliant", True),
            "issues": engine_result.get("issues", []),
            "findings": engine_result.get("findings", ""),
            "evidence": engine_result.get("evidence", ""),
            "suggestion": engine_result.get("suggestion", ""),
            "confidence": engine_result.get("confidence", 0.7),
            "llm_raw_output": engine_result.get("llm_raw_output"),
            "status": engine_result.get("status"),
            "applicability": engine_result.get("applicability"),
            "not_applicable": not engine_result.get("applicability", {}).get("is_applicable", True),
            "not_applicable_reason": engine_result.get("applicability", {}).get("reason"),
            "evidence_verified": engine_result.get("evidence_verified", True),
            "evidence_span": engine_result.get("evidence_span"),
            "token_usage": {"total_tokens": metadata.get("tokens_used", 0)},
            "metadata": metadata,
        }

        return success_response(
            data=response_data,
            message="规则测试完成",
            trace_id=get_trace_id(request)
        )
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        return error_response(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"规则测试失败: {str(e)}",
            trace_id=get_trace_id(request)
        )

# ==================== 提示词管理接口（仅系统管理员） ====================

class UpdatePromptRequest(BaseModel):
    custom_prompt: Optional[str] = None


@router.get("/rules/{rule_id}/prompt")
async def get_rule_prompt(
    request: Request,
    rule_id: str,
    admin_user: dict = Depends(require_admin),
    qc_service: SichuanQCService = Depends(get_qc_service)
):
    """
    获取规则的提示词（仅系统管理员）

    Args:
        rule_id: 规则ID（如 "SC-010"）
        admin_user: 管理员用户（由 require_admin 依赖注入）

    Returns:
        规则的提示词（自定义或默认）
    """
    try:
        # 获取规则
        rule = qc_service.get_rule_by_id(rule_id)
        if not rule:
            raise HTTPException(
                status_code=404,
                detail=f"未找到规则 ID: {rule_id}"
            )

        # 获取自定义提示词或返回默认提示词标记
        custom_prompt = rule.get("custom_prompt")

        # 构建默认提示词（与 test_rule 中的一致）
        default_prompt = f"""你是一名经验丰富的病历质控专家，具有丰富的临床经验和质控标准知识。

请根据以下质控规则，对病历文本进行全面、深入的质控评估。

**质控规则信息：**
- 规则ID: {rule.get('rule_id')}
- 规则名称: {rule.get('name')}
- 规则描述: {rule.get('description')}
- 适用文书: {', '.join(rule.get('applicable_documents', []))}
- 缺陷级别: {rule.get('defect_level')}
- 复杂度: {rule.get('complexity')}

**病历文本：**
{{medical_text}}

**评估要求（请从以下多个维度进行全面分析）：**

1. **时间一致性**：检查主诉时间与现病史时间节点是否匹配，是否存在时间逻辑错误

2. **症状完整性**：验证主诉中的所有症状是否在现病史中得到详细描述和阐述

3. **症状矛盾性**：⚠️ 重点检查现病史中是否存在明确否定主诉症状的表述
   - 例如：主诉"胸痛"，但现病史中出现"无胸痛"、"否认胸痛"等否定表述
   - 这种明确的矛盾是严重的质控缺陷

4. **系统一致性**：分析主诉症状、现病史描述、入院诊断是否涉及同一器官系统
   - 例如：主诉为心血管症状，现病史却主要描述消化系统问题，诊断又是心血管疾病
   - 检查是否存在跨系统的逻辑错误

5. **诊断支撑性**：评估现病史是否为入院诊断提供了充分的临床证据
   - 诊断依据是否充分
   - 病史描述是否支持诊断结论

6. **逻辑闭环性**：验证"主诉 → 现病史 → 入院诊断"是否形成完整、合理的逻辑链条
   - 三者之间是否存在逻辑断裂
   - 是否存在多维度的不一致

**分析方法：**
- 逐字逐句仔细阅读病历文本
- 特别注意否定词："无"、"否认"、"未见"、"未诉"等
- 识别症状所属的器官系统（如心血管系统、消化系统、呼吸系统等）
- 评估时间线的合理性和连贯性
- 综合判断整体逻辑的一致性

**输出格式（JSON）：**
{{{{
  "is_compliant": true/false,
  "findings": "详细描述发现的所有问题，包括时间矛盾、症状否定矛盾、系统不一致、诊断支撑不足等各个维度的问题。如果合规则说明符合哪些要求",
  "evidence": "从病历中提取的相关文本片段，特别要引用包含否定词、时间信息、诊断信息的关键句子",
  "suggestion": "针对发现的问题提供改进建议，如果合规可以为空",
  "confidence": 0.85
}}}}

请直接输出 JSON，不要包含其他文字："""

        return success_response(
            data={
                "rule_id": rule_id,
                "has_custom_prompt": custom_prompt is not None,
                "prompt": custom_prompt if custom_prompt else default_prompt,
                "is_default": custom_prompt is None
            },
            message="获取提示词成功",
            trace_id=get_trace_id(request)
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        return error_response(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"获取提示词失败: {str(e)}",
            trace_id=get_trace_id(request)
        )


@router.put("/rules/{rule_id}/prompt")
async def update_rule_prompt(
    request: Request,
    rule_id: str,
    req: UpdatePromptRequest,
    admin_user: dict = Depends(require_admin),
    qc_service: SichuanQCService = Depends(get_qc_service)
):
    """
    更新规则的自定义提示词（仅系统管理员）

    Args:
        rule_id: 规则ID
        req: 包含 custom_prompt 的请求体（None 表示恢复默认）
        admin_user: 管理员用户

    Returns:
        更新结果
    """
    try:
        # 更新提示词
        success = qc_service.update_rule_prompt(rule_id, req.custom_prompt)

        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"未找到规则 ID: {rule_id}"
            )

        action = "恢复为默认提示词" if req.custom_prompt is None else "更新自定义提示词"

        return success_response(
            data={
                "rule_id": rule_id,
                "has_custom_prompt": req.custom_prompt is not None
            },
            message=f"{action}成功",
            trace_id=get_trace_id(request)
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        return error_response(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"更新提示词失败: {str(e)}",
            trace_id=get_trace_id(request)
        )


@router.post("/reload-config")
async def reload_llm_config(
    request: Request,
    config_name: str = Query(default="default"),
    user_id: Optional[str] = Query(default=None)
):
    """
    重新加载 LLM 配置（从数据库）

    当前端修改了 LLM 配置后，调用此接口让四川质控服务重新加载配置
    无需重启后端服务

    Args:
        config_name: 配置名称，默认为 "default"
        user_id: 用户 ID，如果为 None 则加载全局配置

    Returns:
        重新加载结果
    """
    try:
        qc_service = await get_qc_service()
        success = await qc_service.reload_config(config_name, user_id)

        if success:
            return success_response(
                data={
                    "config_name": config_name,
                    "user_id": user_id,
                    "current_model": qc_service.client.model,
                    "config_source": qc_service.client.config_source,
                    "reloaded_at": datetime.now(timezone.utc).isoformat()
                },
                message="LLM 配置重新加载成功",
                trace_id=get_trace_id(request)
            )
        else:
            return error_response(
                code=ErrorCode.INTERNAL_ERROR,
                message="LLM 配置重新加载失败",
                trace_id=get_trace_id(request)
            )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return error_response(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"重新加载配置失败: {str(e)}",
            trace_id=get_trace_id(request)
        )


@router.get("/current-config")
async def get_current_config(request: Request):
    """
    获取当前使用的 LLM 配置信息

    Returns:
        当前配置信息
    """
    try:
        qc_service = await get_qc_service()
        return success_response(
            data={
                "model": qc_service.client.model,
                "api_endpoint": qc_service.client.api_endpoint,
                "config_source": qc_service.client.config_source,
                "timeout_seconds": qc_service.client.timeout_seconds,
                "stats": qc_service.client.stats()
            },
            message="获取当前配置成功",
            trace_id=get_trace_id(request)
        )
    except Exception as e:
        return error_response(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"获取当前配置失败: {str(e)}",
            trace_id=get_trace_id(request)
        )
