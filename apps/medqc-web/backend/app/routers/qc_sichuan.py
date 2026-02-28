from typing import List, Dict, Any, Optional
import uuid
import json
import logging
from pathlib import Path
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Query, Request, Depends
from datetime import datetime, timezone

from ..core.response import success_response, paginated_response, error_response, get_trace_id, ErrorCode, StatusCode
from ..services.sichuan_qc_service import SichuanQCService
from ..services.unified_rule_engine import UnifiedRuleEngine
from ..services.segmented_qc_pipeline import SegmentedQCPipeline
from ..services.llm_config_loader import LLMConfigLoader
from ..core.supabase_client import get_supabase
from ..core.settings import get_settings
from ..core.security import require_admin

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
    document_content: str
    document_type: Optional[str] = "病程记录"
    document_types: Optional[List[str]] = None
    rule_ids: Optional[List[str]] = None
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


class SichuanBatchDocument(BaseModel):
    document_id: str
    document_content: str
    document_type: Optional[str] = "病程记录"


class SichuanBatchRequest(BaseModel):
    documents: List[SichuanBatchDocument]


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
            pipeline = SegmentedQCPipeline(
                llm_client=qc_service.client,
                max_concurrency=3,
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
    except Exception as e:
        raise HTTPException(status_code=StatusCode.INTERNAL_SERVER_ERROR, detail=f"四川省质控评估失败: {e}")


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


@router.post("/results/save")
async def save_qc_result(req: SaveQCResultRequest):
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

        return {"success": True, "id": result_id, "path": str(filepath)}
    except Exception as e:
        raise HTTPException(status_code=StatusCode.INTERNAL_SERVER_ERROR, detail=f"保存质控结果失败: {e}")


@router.get("/results/history")
async def get_qc_history(
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
            return {
                "records": [],
                "total": 0,
                "page": page,
                "page_size": page_size
            }

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

        return {
            "records": paginated_records,
            "total": total,
            "page": page,
            "page_size": page_size
        }
    except Exception as e:
        raise HTTPException(status_code=StatusCode.INTERNAL_SERVER_ERROR, detail=f"获取质控历史失败: {e}")


@router.get("/results/latest")
async def get_latest_qc_result():
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

        return data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=StatusCode.INTERNAL_SERVER_ERROR, detail=f"获取最新质控结果失败: {e}")


@router.get("/results/{result_id:path}")
async def get_qc_result_detail(result_id: str):
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

            return data

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

        return data
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
                "api_endpoint": str(s.SICHUAN_API_ENDPOINT) if s.SICHUAN_API_ENDPOINT else None,
                "model": s.SICHUAN_MODEL,
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
            rule_id = rec.get("id") or rec.get("rule_code") or rec.get("rule_id") or ""
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
            print(f"✅ 已从JSON文件加载 {len(data)} 条四川规则")
        except Exception as e:
            print(f"⚠️ 加载JSON文件失败: {e}，使用最小示例")
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
        return {
            "rules_by_document_type": by_type,
            "document_types": list(sorted(by_type.keys())),
            "total_rules": sum(len(v) for v in by_type.values()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "success",
            "source": source,
        }

    return {
        "rules": filtered,
        "total_rules": len(filtered),
        "document_type_filter": list(wanted_docs) if wanted_docs else None,
        "rule_categories": list(sorted({d.get("category", "基础") for d in filtered})),
        "complexity_distribution": {},
        "defect_level_distribution": {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "success",
        "source": source,
    }


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
