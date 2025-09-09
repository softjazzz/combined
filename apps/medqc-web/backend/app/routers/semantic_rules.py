from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query
from ..core.supabase_client import get_supabase
from datetime import datetime
from fastapi import status

router = APIRouter(prefix="/api/semantic-rules", tags=["semantic-rules"])


# 移除内置占位规则，保持为空。
_rules: list[dict[str, Any]] = []


@router.get("")
async def get_all(
    q: Optional[str] = Query(default=None, description="按名称/描述搜索"),
    category: Optional[str] = Query(default=None),
    defect_level: Optional[str] = Query(default=None),
    is_enabled: Optional[bool] = Query(default=None, description="启用状态，兼容 is_active"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    sort_by: str = Query(default="updated_at"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
):
    """返回语义规则定义（含筛选/排序/分页）。
    - 数据源：Supabase `qc_rules`（若不可用则返回空数组）。
    - 兼容字段：`is_enabled`/`is_active`、`defect_level`/`severity`、`category`/`rule_category`。
    """
    supabase = get_supabase()
    if supabase is None:
        return {"success": True, "rules": [], "count": 0, "page": page, "page_size": page_size}

    def normalize(r: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "rule_id": r.get("id") or r.get("rule_code") or r.get("rule_id") or "",
            "rule_name": r.get("name") or r.get("rule_name") or "未命名规则",
            "description": r.get("description") or r.get("desc") or "",
            "category": r.get("category") or r.get("rule_category") or "基础",
            "defect_level": r.get("defect_level") or r.get("severity") or "minor",
            "deduction_score": r.get("deduction_score") or r.get("score_deduction") or 0,
            "is_veto_defect": bool(r.get("is_veto_defect") or False),
            "complexity": r.get("complexity") or r.get("rule_complexity") or "medium",
            "is_enabled": bool((r.get("is_enabled") is True) or (r.get("is_active") is True)),
            "version": r.get("version") or r.get("rule_version") or 1,
            "prompt_template": r.get("prompt_template") or "请检查以下内容：\n{{content}}",
            "metadata": r.get("metadata") or {},
            "updated_at": r.get("updated_at") or r.get("modified_at") or r.get("created_at"),
        }

    try:
        # 简化实现：拉取较大窗口数据到内存，再在应用层做筛选/排序/分页（数据量小场景可接受）
        resp = supabase.table("qc_rules").select("*").limit(2000).execute()
        rows: List[Dict[str, Any]] = list(resp.data or [])

        # 兼容筛选
        def match(r: Dict[str, Any]) -> bool:
            if category:
                rc = (r.get("category") or r.get("rule_category") or "").lower()
                if rc != category.lower():
                    return False
            if defect_level:
                dl = (r.get("defect_level") or r.get("severity") or "").lower()
                if dl != defect_level.lower():
                    return False
            if is_enabled is not None:
                enabled = bool((r.get("is_enabled") is True) or (r.get("is_active") is True))
                if enabled != is_enabled:
                    return False
            if q:
                name = (r.get("name") or r.get("rule_name") or "").lower()
                desc = (r.get("description") or r.get("desc") or "").lower()
                if q.lower() not in name and q.lower() not in desc:
                    return False
            return True

        filtered = [normalize(r) for r in rows if match(r)]

        # 排序
        reverse = (sort_order.lower() == "desc")
        try:
            filtered.sort(key=lambda x: (x.get(sort_by) is None, x.get(sort_by)), reverse=reverse)
        except Exception:
            # 回退按更新时间/名称
            filtered.sort(key=lambda x: (x.get("updated_at") is None, x.get("updated_at")), reverse=True)

        # 分页
        total = len(filtered)
        start = (page - 1) * page_size
        end = start + page_size
        page_items = filtered[start:end]

        return {
            "success": True,
            "rules": page_items,
            "count": total,
            "page": page,
            "page_size": page_size,
        }
    except Exception:
        return {"success": True, "rules": [], "count": 0, "page": page, "page_size": page_size}


@router.get("/stats")
async def stats():
    print("DEBUG: stats endpoint called")  # Debug log
    try:
        result = {
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
        print(f"DEBUG: returning result: {result}")  # Debug log
        return result
    except Exception as e:
        print(f"DEBUG: exception in stats: {e}")  # Debug log
        raise


@router.get("/validate-llm")
async def validate_llm():
    """检测 LLM 连接状态。
    - 若 Supabase 中存在激活的 provider 或 model，则认为具备真实配置，显示为非 Mock。
    - 若查询失败或没有配置，则返回 Mock 模式。
    """
    supabase = get_supabase()
    provider_name = "mock"
    model_name = "mock-gpt-4"
    real = False

    if supabase is not None:
        try:
            p = supabase.table("llm_api_providers").select("*").eq("is_active", True).limit(1).execute()
            m = supabase.table("llm_models").select("*").eq("is_active", True).limit(1).execute()
            if p.data:
                provider = p.data[0]
                provider_name = provider.get("name") or provider.get("provider_code") or provider.get("id") or "unknown"
            if m.data:
                model = m.data[0]
                model_name = model.get("model_name") or model.get("model_code") or model.get("name") or model.get("id") or "unknown"
            real = bool(p.data or m.data)
        except Exception:
            real = False

    return {
        "success": True,
        "connection_info": {
            "real_llm_available": real,
            "mock_mode": not real,
            "provider": provider_name,
            "model": model_name,
        },
    }


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


# ------------------------- CRUD & Import/Export -------------------------

def _normalize_from_db(r: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "rule_id": r.get("id") or r.get("rule_code") or r.get("rule_id") or "",
        "rule_name": r.get("name") or r.get("rule_name") or "未命名规则",
        "description": r.get("description") or r.get("desc") or "",
        "category": r.get("category") or r.get("rule_category") or "基础",
        "defect_level": r.get("defect_level") or r.get("severity") or "minor",
        "deduction_score": r.get("deduction_score") or r.get("score_deduction") or 0,
        "is_veto_defect": bool(r.get("is_veto_defect") or False),
        "complexity": r.get("complexity") or r.get("rule_complexity") or "medium",
        "system_role": "医疗质控专家",
        "task_description": "按规则检查内容",
        "input_format": {"content": "文本"},
        "evaluation_criteria": ["包含必要字段"],
        "output_format": {"compliant": "bool"},
        "prompt_template": r.get("prompt_template") or "请检查以下内容：\n{{content}}",
    }


@router.post("")
async def create_rule(payload: Dict[str, Any]):
    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Supabase 未配置")
    try:
        body = {**payload}
        body.setdefault("is_active", True)
        resp = sb.table("qc_rules").insert(body).execute()
        data = (resp.data or [{}])[0]
        return {"success": True, "rule": _normalize_from_db(data)}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"创建规则失败: {e}")


@router.put("/{rule_id}")
async def update_rule(rule_id: str, payload: Dict[str, Any]):
    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Supabase 未配置")
    try:
        resp = sb.table("qc_rules").update(payload).eq("id", rule_id).execute()
        rows = resp.data or []
        if not rows:
            # 兼容按 rule_code 更新
            resp = sb.table("qc_rules").update(payload).eq("rule_code", rule_id).execute()
            rows = resp.data or []
        if not rows:
            raise HTTPException(status_code=404, detail="规则不存在")
        return {"success": True, "rule": _normalize_from_db(rows[0])}
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"更新规则失败: {e}")


@router.delete("/{rule_id}")
async def delete_rule(rule_id: str):
    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Supabase 未配置")
    try:
        resp = sb.table("qc_rules").delete().eq("id", rule_id).execute()
        rows = resp.data or []
        if not rows:
            resp = sb.table("qc_rules").delete().eq("rule_code", rule_id).execute()
            rows = resp.data or []
        if not rows:
            raise HTTPException(status_code=404, detail="规则不存在或已删除")
        return {"success": True, "deleted": len(rows)}
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"删除规则失败: {e}")


@router.post("/import")
async def import_rules(body: Dict[str, Any]):
    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Supabase 未配置")
    rules = body.get("rules") or []
    if not isinstance(rules, list):
        raise HTTPException(status_code=400, detail="rules 字段应为数组")
    try:
        # 映射函数：将中文/别名映射为数据库允许的枚举
        def map_category(raw: Any) -> str:
            if raw is None:
                return "consistency"
            s = str(raw).strip().lower()
            # DB 允许值：completeness / accuracy / timeliness / consistency / compliance
            mapping: dict[str, str] = {
                "completeness": "completeness",
                "accuracy": "accuracy",
                "timeliness": "timeliness",
                "consistency": "consistency",
                "compliance": "compliance",
            }
            if s in mapping:
                return mapping[s]
            # 中文/同义词归一
            if any(k in s for k in ["完整", "缺失", "齐全"]):
                return "completeness"
            if any(k in s for k in ["一致", "对应", "吻合", "语义"]):
                # 语义相关内容多归到一致性
                return "consistency"
            if any(k in s for k in ["合理", "不当", "适宜", "准确", "正确"]):
                return "accuracy"
            if any(k in s for k in ["时效", "及时", "延迟", "时间"]):
                return "timeliness"
            if any(k in s for k in ["合规", "规范", "遵循", "依从"]):
                return "compliance"
            # 默认
            return "consistency"

        def map_severity(raw: Any) -> str:
            if raw is None:
                return "minor"
            s = str(raw).strip().lower()
            # 英文直通
            if s in {"critical", "major", "minor"}:
                return s
            # 中文关键字
            if any(k in s for k in ["致命", "危急", "紧急"]):
                return "critical"
            if any(k in s for k in ["严重", "重大", "较大"]):
                return "major"
            if any(k in s for k in ["一般", "轻微", "次要"]):
                return "minor"
            # 包含括号扣分提示时的兜底
            if "3分" in s or "2分" in s or "1分" in s:
                return "minor"
            return "minor"

        def map_rule_type(raw: Any) -> str:
            if raw is None:
                return "semantic"
            s = str(raw).strip().lower()
            # DB 允许值：logical / semantic / hybrid
            if s in {"logical", "semantic", "hybrid"}:
                return s
            if s in {"subjective", "llm", "ai", "nlp", "gpt", "chatgpt"}:
                return "semantic"
            if s in {"objective", "rule", "regex", "pattern"}:
                return "logical"
            return "semantic"

        # 动态探测 qc_rules 可用列，避免 Unknown column 报错
        allowed_keys: set[str] = set()
        try:
            probe = sb.table("qc_rules").select("*").limit(1).execute()
            rows0 = list(getattr(probe, "data", None) or [])
            if rows0:
                allowed_keys = set(rows0[0].keys())
        except Exception:
            allowed_keys = set()

        # 安全兜底列集合（最小集合）
        minimal_keys = {
            "id",
            "rule_code",
            "name",
            "description",
            "category",
            "severity",
            "rule_type",
            "is_active",
            "version",
            "created_by",
        }

        inserted = 0
        updated = 0
        errors = 0
        sample_error: str | None = None
        created_by_fallback = None
        # 若表包含 created_by 列，则尝试准备一个可用的 user_profiles.id 作为兜底
        if (allowed_keys or minimal_keys) and ("created_by" in (allowed_keys or minimal_keys)):
            try:
                up = sb.table("user_profiles").select("id").limit(1).execute()
                rows = list(getattr(up, "data", None) or [])
                if rows:
                    created_by_fallback = rows[0].get("id")
            except Exception:
                created_by_fallback = None
        for r in rules:
            try:
                src = dict(r)
                rule_code = src.get("rule_code") or src.get("rule_id")
                if not rule_code:
                    # 无唯一键，跳过
                    continue

                # 规范化到 qc_rules 字段
                rec: Dict[str, Any] = {
                    "rule_code": rule_code,
                    "name": src.get("name") or src.get("rule_name") or "未命名规则",
                    "description": src.get("description") or src.get("desc") or "",
                    # 分类、严重级别、类型映射到数据库枚举
                    "category": map_category(src.get("category") or src.get("rule_category") or ""),
                    "severity": map_severity(src.get("defect_level") or src.get("severity") or ""),
                    "rule_type": map_rule_type(src.get("rule_type")),
                    # check_logic 为 NOT NULL，提供最小占位
                    "check_logic": src.get("check_logic") or {},
                    "complexity": src.get("complexity") or src.get("rule_complexity") or "medium",
                    "deduction_score": src.get("deduction_score") or src.get("score_deduction") or 0,
                    "applicable_documents": src.get("applicable_documents") or src.get("document_types") or [],
                    "medical_domain": src.get("medical_domain") or src.get("domain") or "通用",
                    "is_active": True if src.get("is_active") is None else bool(src.get("is_active")),
                    "version": str(src.get("version") or src.get("rule_version") or "1.0"),
                    "metadata": src.get("metadata") or {},
                }

                # 过滤字段到目标表允许列（并集，避免缺列导致 NOT NULL 约束失败）
                keys_to_use = (allowed_keys | minimal_keys) if allowed_keys else minimal_keys
                rec_filtered = {k: v for k, v in rec.items() if k in keys_to_use}
                # 若需要 created_by 且未提供，使用兜底值
                if "created_by" in keys_to_use and not rec_filtered.get("created_by") and created_by_fallback:
                    rec_filtered["created_by"] = created_by_fallback

                # 优先尝试更新；若无匹配则采用 delete+insert 防止重复
                updated_rows: list[dict[str, Any]] = []
                try:
                    if "rule_code" in keys_to_use:
                        upd = sb.table("qc_rules").update(rec_filtered).eq("rule_code", rule_code).execute()
                        updated_rows = list(upd.data or [])
                except Exception:
                    updated_rows = []
                if not updated_rows and "name" in keys_to_use:
                    try:
                        upd2 = sb.table("qc_rules").update(rec_filtered).eq("name", rec_filtered.get("name")).execute()
                        updated_rows = list(upd2.data or [])
                    except Exception:
                        updated_rows = []
                if updated_rows:
                    updated += 1
                    continue

                # delete + insert
                try:
                    if "rule_code" in keys_to_use:
                        try:
                            sb.table("qc_rules").delete().eq("rule_code", rule_code).execute()
                        except Exception:
                            pass
                    elif "name" in keys_to_use and rec_filtered.get("name"):
                        try:
                            sb.table("qc_rules").delete().eq("name", rec_filtered.get("name")).execute()
                        except Exception:
                            pass
                except Exception:
                    pass

                ins = sb.table("qc_rules").insert(rec_filtered).execute()
                if ins.data:
                    inserted += 1
            except Exception as e:
                # 记录首个错误，尽量包含后端响应体帮助诊断
                if sample_error is None:
                    detail = None
                    try:
                        resp = getattr(e, "response", None)
                        if resp is not None:
                            try:
                                detail = resp.text
                            except Exception:
                                detail = None
                    except Exception:
                        detail = None
                    try:
                        sample_error = detail or str(e)
                    except Exception:
                        sample_error = "unknown error"
                errors += 1
                continue
        return {"success": True, "inserted": inserted, "updated": updated, "errors": errors, "sample_error": sample_error}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"导入规则失败: {e}")


@router.get("/export")
async def export_rules():
    sb = get_supabase()
    if sb is None:
        # 与列表接口保持一致，返回空
        return {"success": True, "rules": [], "count": 0}
    try:
        resp = sb.table("qc_rules").select("*").limit(2000).execute()
        records = resp.data or []
        rules = [_normalize_from_db(r) for r in records]
        return {"success": True, "rules": rules, "count": len(rules)}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"导出规则失败: {e}")

