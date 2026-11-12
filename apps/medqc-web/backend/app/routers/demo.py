"""
演示页面 API 路由
用于 LX33 质控规则演示和反馈系统
演示反馈使用业务 PostgreSQL 独立表持久化
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any
import json
import os

from fastapi import APIRouter, Query, Request, Depends, HTTPException
from fastapi.responses import StreamingResponse
from starlette import status
from sqlalchemy.orm import Session
import uuid
import io
from collections import defaultdict
from pydantic import BaseModel

from ..core.response import success_response, error_response, get_trace_id
from ..schemas.demo import (
    FeedbackCreate,
    FeedbackResponse,
    FeedbackStats,
    FeedbackListResponse,
    RuleFeedbackStat,
    RuleGenerationRequest,
    DemoCustomRule,
    CustomRuleSaveRequest,
)
from ..database.demo_db import get_db
from ..models.demo import Feedback
from ..core.settings import get_settings
from ..core.http import safe_post_json
from ..services.llm_observability import (
    llm_observation_context,
    observe_llm_http_attempt,
)

router = APIRouter(prefix="/api/v1/demo", tags=["demo"])

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
LX_RULES_FILE = DATA_DIR / "custom_rules_33.json"
DEMO_RULES_FILE = DATA_DIR / "custom_rules_demo.json"
# 演示页面质控结果独立存储目录
DEMO_QC_RESULTS_DIR = BASE_DIR / "storage" / "demo_qc_results"

SYSTEM_ROLE_PROMPT = (
    "你是一名资深医疗病案质控专家，熟悉中国内地病案书写规范和临床诊疗流程。"
    "你的任务是根据用户描述生成结构化的质控规则，包括规则名称、规则描述、质控提示词，以及"
    "能体现规则内涵的合规/不合规病历示例。所有输出需使用简体中文。"
)


def _ensure_demo_rules_file() -> None:
    """确保 Demo 规则文件存在"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not DEMO_RULES_FILE.exists():
        DEMO_RULES_FILE.write_text("[]", encoding="utf-8")


def _load_rules_from_file(path: Path) -> List[Dict[str, Any]]:
    """从 JSON 文件加载规则列表"""
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []


def _save_rules_to_file(path: Path, rules: List[Dict[str, Any]]) -> None:
    """将规则写入 JSON 文件"""
    path.write_text(json.dumps(rules, ensure_ascii=False, indent=2), encoding="utf-8")


def _generate_custom_rule_id(existing_rules: List[Dict[str, Any]]) -> str:
    """生成唯一的自定义规则 ID"""
    existing_ids = {
        (rule.get("rule_id") or rule.get("rule_code") or "").strip()
        for rule in existing_rules
    }
    max_num = 0
    for rid in existing_ids:
        if rid.startswith("CUSTOM-"):
            try:
                num = int(rid.split("-")[1])
                max_num = max(max_num, num)
            except Exception:
                continue
    return f"CUSTOM-{max_num + 1:03d}"


def _build_rule_generation_prompt(payload: RuleGenerationRequest) -> str:
    """根据用户输入构建提示词"""
    docs = payload.applicable_documents or ([payload.category] if payload.category else [])
    docs_text = "、".join(docs) if docs else "通用文书"
    return (
        f"【质控需求】\n{payload.requirement.strip()}\n\n"
        f"【规则参数】\n"
        f"- 适用文书：{docs_text}\n"
        f"- 缺陷级别：{payload.defect_level}\n"
        f"- 复杂度：{payload.complexity}\n\n"
        "请严格按照以下 JSON 结构输出：\n"
        "{\n"
        '  "rule_name": "15字以内的规则名称",\n'
        '  "description": "规则描述，需包含质控要求",\n'
        '  "custom_prompt": "完整的质控提示词，包含【检查要点】【补充说明】【分析方法】【输出要求】等结构",\n'
        '  "positive_example": {\n'
        '    "title": "合规示例标题",\n'
        '    "content": "合规示例病历内容",\n'
        '    "explanation": "简要说明合规原因"\n'
        "  },\n"
        '  "negative_example": {\n'
        '    "title": "不合规示例标题",\n'
        '    "content": "不合规示例病历内容",\n'
        '    "explanation": "明确指出不合规点"\n'
        "  },\n"
        '  "category": "规则分类/文书类别",\n'
        '  "applicable_documents": ["适用文书列表（中文）"],\n'
        '  "defect_level": "缺陷级别",\n'
        '  "complexity": "复杂度",\n'
        '  "score_deduction": "扣分分值（字符串）"\n'
        "}\n"
        "务必输出合法的 JSON，对示例内容给出真实、具体、符合临床逻辑的病历片段。"
    )


async def _call_llm_for_rule(payload: RuleGenerationRequest) -> DemoCustomRule:
    """调用 LLM 生成规则并做结构化解析"""
    settings = get_settings()
    endpoint = os.getenv("DEMO_RULE_LLM_ENDPOINT") or settings.LLM_API_ENDPOINT
    api_key = os.getenv("DEMO_RULE_LLM_API_KEY") or settings.LLM_API_KEY
    model = os.getenv("DEMO_RULE_LLM_MODEL") or settings.LLM_MODEL
    provider_code = (
        os.getenv("DEMO_RULE_LLM_PROVIDER")
        or getattr(settings, "LLM_DEFAULT_PROVIDER", None)
        or "unknown"
    )

    if not endpoint or not api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="未配置 Demo 规则生成所需的 LLM 接口或密钥，请联系管理员。",
        )

    prompt = _build_rule_generation_prompt(payload)
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    request_body = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": SYSTEM_ROLE_PROMPT},
            {"role": "user", "content": prompt},
        ],
    }

    endpoint_str = str(endpoint)
    if not endpoint_str.rstrip("/").endswith("/chat/completions"):
        target_url = endpoint_str.rstrip("/") + "/chat/completions"
    else:
        target_url = endpoint_str

    async def _request() -> Dict[str, Any]:
        return await safe_post_json(
            target_url,
            headers,
            request_body,
            timeout_seconds=60,
        )

    llm_response = await observe_llm_http_attempt(
        _request,
        provider_code=str(provider_code),
        model=str(model),
        business_scene="demo_custom_rule_generation",
        executor_key="demo_custom_rule_generation",
    )

    if isinstance(llm_response, dict) and llm_response.get("__error__"):
        upstream_body = llm_response.get("body") or {}
        detail = upstream_body.get("error") or upstream_body or "调用 LLM 失败"
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM 调用失败: {detail}",
        )

    try:
        content = (
            llm_response.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"解析 LLM 响应失败: {exc}",
        ) from exc

    if not content:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LLM 未返回内容，请尝试调整需求描述后重试。",
        )

    try:
        raw_rule = json.loads(content)
    except json.JSONDecodeError:
        import re

        # 常见情形：包裹在 ```json ``` 代码块或前后带有说明文字
        cleaned = content.strip()
        if cleaned.startswith("```"):
            # 去掉三引号包裹
            cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
            cleaned = re.sub(r"```$", "", cleaned).strip()

        try:
            raw_rule = json.loads(cleaned)
        except json.JSONDecodeError:
            json_match = re.search(r"\{[\s\S]*\}", cleaned)
            if json_match:
                try:
                    raw_rule = json.loads(json_match.group(0))
                except json.JSONDecodeError as exc:
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="LLM 输出不是合法的 JSON，请调整需求描述后重试。",
                    ) from exc
            else:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="LLM 输出不是合法的 JSON，请调整需求描述后重试。",
                )

    # 填充默认字段
    if not raw_rule.get("applicable_documents"):
        docs = payload.applicable_documents or (
            [payload.category] if payload.category else []
        )
        raw_rule["applicable_documents"] = docs
    if not raw_rule.get("category"):
        raw_rule["category"] = payload.category or (
            payload.applicable_documents[0] if payload.applicable_documents else "通用规则"
        )
    # 字段名称容错处理
    raw_rule["name"] = (
        raw_rule.get("name")
        or raw_rule.get("rule_name")
        or raw_rule.get("title")
        or "未命名规则"
    )
    raw_rule["description"] = (
        raw_rule.get("description")
        or raw_rule.get("rule_description")
        or raw_rule.get("summary")
        or raw_rule.get("details")
        or payload.requirement.strip()
    )
    raw_rule["custom_prompt"] = (
        raw_rule.get("custom_prompt")
        or raw_rule.get("prompt")
        or raw_rule.get("instructions")
        or ""
    )

    def _normalize_example(data, fallback_title):
        if isinstance(data, dict):
            title = data.get("title") or data.get("name") or fallback_title
            content = data.get("content") or data.get("text") or data.get("body") or ""
            explanation = data.get("explanation") or data.get("reason") or ""
        elif isinstance(data, str):
            title = fallback_title
            content = data
            explanation = ""
        else:
            title = fallback_title
            content = ""
            explanation = ""
        if not content:
            content = "（示例待补充）"
        return {
            "title": title.strip() if isinstance(title, str) else fallback_title,
            "content": content.strip() if isinstance(content, str) else "",
            "explanation": explanation.strip() if isinstance(explanation, str) else "",
        }

    raw_rule["positive_example"] = _normalize_example(
        raw_rule.get("positive_example")
        or raw_rule.get("positive_case")
        or raw_rule.get("positive"),
        fallback_title="合规示例",
    )
    raw_rule["negative_example"] = _normalize_example(
        raw_rule.get("negative_example")
        or raw_rule.get("negative_case")
        or raw_rule.get("negative"),
        fallback_title="不合规示例",
    )

    raw_rule.setdefault("defect_level", payload.defect_level)
    raw_rule.setdefault("complexity", payload.complexity)
    raw_rule.setdefault("score_deduction", str(raw_rule.get("score_deduction", "2")))
    if not raw_rule["custom_prompt"]:
        docs_text = "、".join(raw_rule.get("applicable_documents", [])) or "通用文书"
        raw_rule["custom_prompt"] = (
            "你是一名经验丰富的病历质控专家。\n\n"
            f"【规则信息】\n- 规则名称：{raw_rule['name']}\n- 规则描述：{raw_rule['description']}\n"
            f"- 适用文书：{docs_text}\n\n"
            "请阅读病历文本，判断是否符合规则要求，并输出 JSON 结果：\n"
            "{\n  \"is_compliant\": true/false,\n  \"findings\": \"问题或符合依据\",\n"
            "  \"issues\": [{\"description\": \"问题\", \"evidence\": \"证据\"}],\n"
            "  \"evidence\": \"引用原文\",\n  \"suggestion\": \"改进建议\",\n  \"confidence\": 0.7\n}"
        )

    try:
        return DemoCustomRule.model_validate(raw_rule)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM 输出不符合规则结构: {exc}",
        ) from exc


def _merge_rules_for_listing() -> List[Dict[str, Any]]:
    """合并基础规则和 Demo 自定义规则用于前端展示"""
    base_rules = _load_rules_from_file(LX_RULES_FILE)
    demo_rules = _load_rules_from_file(DEMO_RULES_FILE)
    return base_rules + demo_rules


@router.get("/custom-rules", response_model=dict)
async def list_custom_rules(request: Request):
    """
    返回演示系统中的规则列表（基础规则 + AI 生成规则）
    """
    _ensure_demo_rules_file()
    rules = _merge_rules_for_listing()
    return success_response(
        data={"rules": rules},
        message="获取演示规则成功",
        trace_id=get_trace_id(request),
    )


@router.post("/custom-rules/generate", response_model=dict)
async def generate_custom_rule(
    request: Request,
    payload: RuleGenerationRequest,
):
    """
    调用 LLM 生成自定义质控规则草案
    """
    _ensure_demo_rules_file()
    normalized_payload = payload.model_copy()
    if not normalized_payload.category and normalized_payload.applicable_documents:
        normalized_payload.category = normalized_payload.applicable_documents[0]

    with llm_observation_context(
        business_scene="demo_custom_rule_generation",
        root_job_id=get_trace_id(request),
        executor_key="demo_custom_rule_generation",
    ):
        generated_rule = await _call_llm_for_rule(normalized_payload)
    all_rules = _merge_rules_for_listing()
    rule_id = _generate_custom_rule_id(all_rules)
    enriched_rule = generated_rule.model_copy(update={
        "rule_id": rule_id,
        "rule_code": rule_id,
        "source": "ai_generated",
        "generation_params": normalized_payload.model_dump(),
    })

    return success_response(
        data=enriched_rule.model_dump(),
        message="规则生成成功",
        trace_id=get_trace_id(request),
    )


@router.post("/custom-rules/save", response_model=dict)
async def save_custom_rule(
    request: Request,
    payload: CustomRuleSaveRequest,
):
    """
    保存 AI 生成的规则到 Demo 规则文件
    """
    _ensure_demo_rules_file()
    incoming_rule = payload.rule

    all_rules = _merge_rules_for_listing()
    rule_id = incoming_rule.rule_id or incoming_rule.rule_code
    if not rule_id or not rule_id.startswith("CUSTOM-"):
        # 分配新的自定义规则 ID
        rule_id = _generate_custom_rule_id(all_rules)
        incoming_rule = incoming_rule.model_copy(
            update={"rule_id": rule_id, "rule_code": rule_id}
        )

    # 更新来源标记
    incoming_rule = incoming_rule.model_copy(
        update={"source": incoming_rule.source or "ai_generated"}
    )

    # 写入 Demo 文件
    demo_rules = _load_rules_from_file(DEMO_RULES_FILE)
    demo_rules = [
        r for r in demo_rules if (r.get("rule_id") or r.get("rule_code")) != rule_id
    ]
    demo_rules.append(incoming_rule.model_dump())
    _save_rules_to_file(DEMO_RULES_FILE, demo_rules)

    return success_response(
        data={"rule_id": rule_id, "rule_code": rule_id},
        message="规则已保存",
        trace_id=get_trace_id(request),
    )

@router.post("/feedbacks", response_model=dict)
async def create_feedback(
    request: Request,
    feedback: FeedbackCreate,
    db: Session = Depends(get_db)
):
    """
    提交质控评估反馈

    Args:
        request: FastAPI 请求对象
        feedback: 反馈数据
        db: 数据库会话

    Returns:
        创建成功的反馈记录
    """
    # 生成反馈ID
    feedback_id = str(uuid.uuid4())

    # 创建反馈记录
    db_feedback = Feedback(
        feedback_id=feedback_id,
        evaluation_id=feedback.evaluation_id,
        rule_id=feedback.rule_id,
        rule_code=feedback.rule_code,
        rule_name=feedback.rule_name,
        document_name=feedback.document_name,
        evaluation_result=feedback.evaluation_result,
        feedback_type=feedback.feedback_type,
        error_category=feedback.error_category,
        error_detail=feedback.error_detail,
        evidence=feedback.evidence,
        feedback_by=feedback.feedback_by,
        medical_text=feedback.medical_text,
        created_at=datetime.utcnow()
    )

    # 保存到数据库
    db.add(db_feedback)
    db.commit()
    db.refresh(db_feedback)

    return success_response(
        data=FeedbackResponse(**db_feedback.to_dict()),
        message="反馈提交成功",
        trace_id=get_trace_id(request)
    )


@router.get("/feedbacks", response_model=FeedbackListResponse)
async def get_feedbacks(
    request: Request,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页记录数"),
    feedback_type: Optional[str] = Query(None, description="反馈类型筛选"),
    error_category: Optional[str] = Query(None, description="错误类别筛选"),
    rule_code: Optional[str] = Query(None, description="规则编号筛选"),
    db: Session = Depends(get_db)
):
    """
    获取反馈记录列表

    Args:
        request: FastAPI 请求对象
        page: 页码
        page_size: 每页记录数
        feedback_type: 反馈类型筛选
        error_category: 错误类别筛选
        rule_code: 规则编号筛选
        db: 数据库会话

    Returns:
        分页的反馈记录列表
    """
    # 构建查询
    query = db.query(Feedback)

    # 应用筛选条件
    if feedback_type:
        query = query.filter(Feedback.feedback_type == feedback_type)

    if error_category:
        query = query.filter(Feedback.error_category == error_category)

    if rule_code:
        query = query.filter(Feedback.rule_code.contains(rule_code.upper()))

    # 获取总数
    total = query.count()

    # 排序和分页
    feedbacks = query.order_by(Feedback.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return FeedbackListResponse(
        success=True,
        data=[FeedbackResponse(**f.to_dict()) for f in feedbacks],
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/feedbacks/stats", response_model=dict)
async def get_feedback_stats(
    request: Request,
    days: int = Query(30, ge=1, le=365, description="统计天数"),
    db: Session = Depends(get_db)
):
    """
    获取反馈统计数据

    Args:
        request: FastAPI 请求对象
        days: 统计天数（默认30天）
        db: 数据库会话

    Returns:
        反馈统计信息
    """
    # 计算时间范围
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    # 查询指定时间范围内的反馈
    feedbacks = db.query(Feedback).filter(Feedback.created_at >= cutoff_date).all()

    # 计算总体统计
    total_feedbacks = len(feedbacks)
    correct_feedbacks = len([f for f in feedbacks if f.feedback_type == "correct"])
    incorrect_feedbacks = len([f for f in feedbacks if f.feedback_type == "incorrect"])
    accuracy_rate = correct_feedbacks / total_feedbacks if total_feedbacks > 0 else 0

    # 按规则统计
    rule_stats = defaultdict(lambda: {"total": 0, "correct": 0, "incorrect": 0})
    for f in feedbacks:
        rule_key = f.rule_code
        rule_stats[rule_key]["rule_code"] = f.rule_code
        rule_stats[rule_key]["rule_name"] = f.rule_name
        rule_stats[rule_key]["total"] += 1
        if f.feedback_type == "correct":
            rule_stats[rule_key]["correct"] += 1
        else:
            rule_stats[rule_key]["incorrect"] += 1

    # 计算每个规则的准确率
    by_rule = []
    best_rule = None
    worst_rule = None
    best_accuracy = 0
    worst_accuracy = 1

    for rule_code, stats in rule_stats.items():
        accuracy = stats["correct"] / stats["total"] if stats["total"] > 0 else 0
        rule_stat = RuleFeedbackStat(
            rule_code=stats["rule_code"],
            rule_name=stats["rule_name"],
            total=stats["total"],
            correct=stats["correct"],
            incorrect=stats["incorrect"],
            accuracy=accuracy
        )
        by_rule.append(rule_stat)

        # 更新最佳和最差规则（至少需要3个反馈）
        if stats["total"] >= 3:
            if accuracy > best_accuracy:
                best_accuracy = accuracy
                best_rule = f"{stats['rule_code']} ({accuracy:.1%})"
            if accuracy < worst_accuracy:
                worst_accuracy = accuracy
                worst_rule = f"{stats['rule_code']} ({accuracy:.1%})"

    # 按准确率排序
    by_rule.sort(key=lambda x: x.accuracy, reverse=True)

    # 错误类别统计
    error_categories = defaultdict(int)
    for f in feedbacks:
        if f.feedback_type == "incorrect" and f.error_category:
            error_categories[f.error_category] += 1

    stats = FeedbackStats(
        total_feedbacks=total_feedbacks,
        correct_feedbacks=correct_feedbacks,
        incorrect_feedbacks=incorrect_feedbacks,
        accuracy_rate=accuracy_rate,
        best_rule=best_rule,
        worst_rule=worst_rule,
        by_rule=by_rule,
        error_categories=dict(error_categories)
    )

    return success_response(
        data=stats,
        message="统计数据获取成功",
        trace_id=get_trace_id(request)
    )


@router.get("/feedbacks/by-rule/{rule_code}")
async def get_feedbacks_by_rule(
    request: Request,
    rule_code: str,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页记录数"),
    db: Session = Depends(get_db)
):
    """
    获取指定规则的反馈记录

    Args:
        request: FastAPI 请求对象
        rule_code: 规则编号
        page: 页码
        page_size: 每页记录数
        db: 数据库会话

    Returns:
        该规则的反馈记录列表
    """
    # 查询该规则的反馈
    query = db.query(Feedback).filter(Feedback.rule_code == rule_code)

    # 获取总数
    total = query.count()

    # 排序和分页
    feedbacks = query.order_by(Feedback.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return success_response(
        data={
            "feedbacks": [FeedbackResponse(**f.to_dict()) for f in feedbacks],
            "total": total,
            "page": page,
            "page_size": page_size
        },
        message="反馈记录获取成功",
        trace_id=get_trace_id(request)
    )


@router.delete("/feedbacks/{feedback_id}", response_model=dict)
async def delete_feedback(
    request: Request,
    feedback_id: str,
    db: Session = Depends(get_db)
):
    """
    删除反馈记录

    Args:
        request: FastAPI 请求对象
        feedback_id: 反馈记录ID
        db: 数据库会话

    Returns:
        删除结果
    """
    # 查询反馈记录
    feedback = db.query(Feedback).filter(Feedback.feedback_id == feedback_id).first()

    if not feedback:
        return error_response(
            error="反馈记录不存在",
            code="FEEDBACK_NOT_FOUND",
            trace_id=get_trace_id(request)
        )

    # 删除记录
    db.delete(feedback)
    db.commit()

    return success_response(
        data={"feedback_id": feedback_id},
        message="反馈记录删除成功",
        trace_id=get_trace_id(request)
    )


@router.get("/feedbacks/export")
async def export_feedbacks(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    导出反馈数据为 Excel 文件

    Args:
        request: FastAPI 请求对象
        db: 数据库会话

    Returns:
        Excel 文件流
    """
    try:
        import openpyxl
        from openpyxl.styles import Font, Alignment, PatternFill
    except ImportError:
        return error_response(
            error="缺少 openpyxl 库，无法导出 Excel",
            code="MISSING_DEPENDENCY",
            trace_id=get_trace_id(request)
        )

    # 创建工作簿
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "反馈记录"

    # 设置表头
    headers = [
        "反馈ID", "规则编号", "规则名称", "文档名称",
        "评估结果", "反馈类型", "错误类别", "错误详情",
        "补充证据", "反馈人", "创建时间"
    ]

    # 写入表头
    for col, header in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        cell.alignment = Alignment(horizontal="center", vertical="center")

    # 查询所有反馈数据
    feedbacks = db.query(Feedback).order_by(Feedback.created_at.desc()).all()

    # 写入数据
    for row_idx, feedback in enumerate(feedbacks, start=2):
        ws.cell(row=row_idx, column=1, value=feedback.feedback_id)
        ws.cell(row=row_idx, column=2, value=feedback.rule_code)
        ws.cell(row=row_idx, column=3, value=feedback.rule_name)
        ws.cell(row=row_idx, column=4, value=feedback.document_name)
        ws.cell(row=row_idx, column=5, value="合规" if feedback.evaluation_result else "不合规")
        ws.cell(row=row_idx, column=6, value="正确" if feedback.feedback_type == "correct" else "错误")
        ws.cell(row=row_idx, column=7, value=feedback.error_category or "")
        ws.cell(row=row_idx, column=8, value=feedback.error_detail or "")
        ws.cell(row=row_idx, column=9, value=feedback.evidence or "")
        ws.cell(row=row_idx, column=10, value=feedback.feedback_by or "")
        ws.cell(row=row_idx, column=11, value=feedback.created_at.isoformat() + "Z" if feedback.created_at else "")

    # 调整列宽
    column_widths = [36, 12, 30, 25, 10, 10, 15, 40, 30, 15, 20]
    for col, width in enumerate(column_widths, start=1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = width

    # 保存到内存
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    # 生成文件名
    filename = f"lx33_feedbacks_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


# ==================== 演示页面质控结果保存和查询 ====================

class DemoSaveQCResultRequest(BaseModel):
    """演示页面质控结果保存请求"""
    mode: str
    document_type: str
    rule_ids: List[str]
    medical_text: Optional[str] = None
    medical_text_length: int
    stats: Dict[str, Any]
    performance: Dict[str, Any]
    results: Optional[List[Dict[str, Any]]] = None
    payload: Optional[Dict[str, Any]] = None
    document_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    model: Optional[str] = None


@router.post("/qc-results/save")
async def save_demo_qc_result(request: Request, req: DemoSaveQCResultRequest):
    """
    保存演示页面的质控结果（独立存储，不与主项目混合）
    """
    try:
        # 确保存储目录存在
        DEMO_QC_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

        # 生成唯一ID和文件名
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        result_id = str(uuid.uuid4())
        filename = f"demo_{result_id}_{req.mode}_{timestamp}.json"
        filepath = DEMO_QC_RESULTS_DIR / filename

        # 构建保存数据
        payload = {
            "id": result_id,
            "mode": req.mode,
            "document_type": req.document_type,
            "document_id": req.document_id,
            "rule_ids": req.rule_ids,
            "medical_text": req.medical_text,
            "medical_text_length": req.medical_text_length,
            "stats": req.stats,
            "performance": req.performance,
            "results": req.results,
            "payload": req.payload,
            "metadata": req.metadata,
            "model": req.model,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source": "demo"  # 标记为演示页面来源
        }

        # 保存到文件
        with filepath.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        return success_response(
            data={"id": result_id, "path": str(filepath)},
            message="演示质控结果保存成功",
            trace_id=get_trace_id(request)
        )
    except Exception as e:
        return error_response(
            message=f"保存演示质控结果失败: {str(e)}",
            trace_id=get_trace_id(request)
        )


@router.get("/qc-results/history")
async def get_demo_qc_history(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    document_type: Optional[str] = Query(None),
    mode: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    has_issues: Optional[bool] = Query(None)
):
    """
    获取演示页面的质控结果历史列表（仅返回演示页面的结果）
    """
    try:
        # 确保目录存在
        if not DEMO_QC_RESULTS_DIR.exists():
            return success_response(
                data={"records": [], "total": 0, "page": page, "page_size": page_size},
                message="暂无历史记录",
                trace_id=get_trace_id(request)
            )

        # 读取所有结果文件
        all_files = sorted(
            [f for f in DEMO_QC_RESULTS_DIR.glob("demo_*.json")],
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )

        records = []
        for filepath in all_files:
            try:
                with filepath.open("r", encoding="utf-8") as f:
                    data = json.load(f)

                # 应用筛选条件
                if document_type and data.get("document_type") != document_type:
                    continue
                if mode and data.get("mode") != mode:
                    continue

                # 日期筛选
                created_at = data.get("created_at", "")
                if start_date and created_at < start_date:
                    continue
                if end_date and created_at > end_date:
                    continue

                # 问题筛选
                if has_issues is not None:
                    issues_count = data.get("stats", {}).get("issues", 0)
                    if has_issues and issues_count == 0:
                        continue
                    if not has_issues and issues_count > 0:
                        continue

                # 构建记录摘要，展开stats字段以便前端直接使用
                stats = data.get("stats", {})
                records.append({
                    "id": data.get("id"),
                    "mode": data.get("mode"),
                    "document_type": data.get("document_type"),
                    "document_id": data.get("document_id"),
                    "rule_count": len(data.get("rule_ids", [])),
                    "stats": stats,
                    "performance": data.get("performance"),
                    "model": data.get("model"),
                    "created_at": data.get("created_at"),
                    "source": "demo",
                    # 展开stats字段，方便前端直接访问
                    "compliance_rate": stats.get("compliance_rate", 0),
                    "issues_count": stats.get("issues", 0),
                    "total_rules": stats.get("total", 0),
                    "prompt_mode": data.get("metadata", {}).get("prompt_mode")
                })
            except Exception as e:
                print(f"读取文件 {filepath} 失败: {e}")
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
                "page_size": page_size
            },
            message="获取演示质控历史成功",
            trace_id=get_trace_id(request)
        )
    except Exception as e:
        return error_response(
            message=f"获取演示质控历史失败: {str(e)}",
            trace_id=get_trace_id(request)
        )


@router.get("/qc-results/{result_id}")
async def get_demo_qc_result_detail(request: Request, result_id: str):
    """
    获取演示页面质控结果的详细信息
    """
    try:
        # 查找对应的结果文件
        matching_files = list(DEMO_QC_RESULTS_DIR.glob(f"demo_{result_id}_*.json"))

        if not matching_files:
            return error_response(
                message=f"未找到ID为 {result_id} 的质控结果",
                trace_id=get_trace_id(request)
            )

        filepath = matching_files[0]

        # 读取完整数据
        with filepath.open("r", encoding="utf-8") as f:
            data = json.load(f)

        return success_response(
            data=data,
            message="获取演示质控结果详情成功",
            trace_id=get_trace_id(request)
        )
    except Exception as e:
        return error_response(
            message=f"获取演示质控结果详情失败: {str(e)}",
            trace_id=get_trace_id(request)
        )


@router.get("/qc-results/latest")
async def get_demo_latest_qc_result(request: Request):
    """
    获取演示页面最新的质控结果
    """
    try:
        if not DEMO_QC_RESULTS_DIR.exists():
            return error_response(
                message="暂无质控结果",
                trace_id=get_trace_id(request)
            )

        # 获取最新的文件
        all_files = sorted(
            [f for f in DEMO_QC_RESULTS_DIR.glob("demo_*.json")],
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )

        if not all_files:
            return error_response(
                message="暂无质控结果",
                trace_id=get_trace_id(request)
            )

        # 读取最新文件
        with all_files[0].open("r", encoding="utf-8") as f:
            data = json.load(f)

        return success_response(
            data=data,
            message="获取最新演示质控结果成功",
            trace_id=get_trace_id(request)
        )
    except Exception as e:
        return error_response(
            message=f"获取最新演示质控结果失败: {str(e)}",
            trace_id=get_trace_id(request)
        )


# ==================== 病案首页与医保清单自动生成 Demo ====================


@router.get("/frontpage-demo")
async def get_frontpage_demo_case(request: Request):
    """
    获取一个模拟病例的病历文本 + 自动生成的病案首页 & 医保结算清单结果。

    说明：
    - 本接口仅用于前端 Demo 展示，不调用真实 LLM 或编码服务。
    - 数据来源于本地文件 app/data/frontpage_demo_case.json。
    """
    try:
        data_path = BASE_DIR / "data" / "frontpage_demo_case.json"
        if not data_path.exists():
            return error_response(
                message="frontpage_demo_case.json 不存在，请联系管理员配置示例数据。",
                trace_id=get_trace_id(request)
            )

        with data_path.open("r", encoding="utf-8") as f:
            payload = json.load(f)

        return success_response(
            data=payload,
            message="获取病案首页自动生成 Demo 数据成功",
            trace_id=get_trace_id(request)
        )
    except Exception as e:
        return error_response(
            message=f"加载病案首页 Demo 数据失败: {str(e)}",
            trace_id=get_trace_id(request)
        )
