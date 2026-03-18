"""
EMR 文书渲染 API

功能:
- 获取病历文书内容（原始文本/HTML）
- 返回缺陷位置标注（用于前端高亮）
"""

import logging
from typing import Optional, List, Dict, Any, Iterable

from fastapi import APIRouter, Request, Query

from ..core.supabase_client import get_supabase, async_execute
from ..core.response import success_response, get_trace_id
from ..database.repository import get_repository

router = APIRouter(prefix="/api/v1/emr", tags=["emr"])
logger = logging.getLogger(__name__)


@router.get("/{record_id}/documents")
async def get_record_documents(
    request: Request,
    record_id: str,
    patient_id: Optional[str] = Query(None, description="患者号（兼容工作台）"),
    visit_id: Optional[str] = Query(None, description="就诊号（兼容工作台）"),
    institute_id: Optional[str] = Query(None, description="机构号（兼容工作台）"),
):
    """
    获取病历下所有文书类型列表

    返回: [ { id, doc_type, doc_name, updated_at } ]
    """
    sb = get_supabase()
    documents = []

    if sb is not None:
        try:
            resp = await async_execute(
                sb.table('medical_documents')
                .select('id,doc_type,doc_name,created_at,updated_at')
                .eq('record_id', record_id)
                .order('doc_type')
            )
            documents = list(getattr(resp, 'data', None) or [])
        except Exception as e:
            logger.warning(f"获取文书列表失败: {e}")

    # 回退：从 CDM 三元键构造文书列表
    if not documents and institute_id and patient_id and visit_id:
        documents = _build_repository_documents(institute_id, patient_id, visit_id)

    return success_response(
        data=documents,
        message=f"获取到 {len(documents)} 份文书",
        trace_id=get_trace_id(request),
    )


@router.get("/{record_id}/render")
async def render_document(
    request: Request,
    record_id: str,
    doc_type: Optional[str] = Query(None, description="文书类型"),
    doc_id: Optional[str] = Query(None, description="文书ID"),
    patient_id: Optional[str] = Query(None, description="患者号（兼容工作台）"),
    visit_id: Optional[str] = Query(None, description="就诊号（兼容工作台）"),
    institute_id: Optional[str] = Query(None, description="机构号（兼容工作台）"),
):
    """
    获取文书内容 + 缺陷位置标注（用于前端 EMRViewer 高亮渲染）

    返回:
    {
      "content": "原始文书文本",
      "content_type": "text" | "html",
      "defect_annotations": [
        {
          "defect_id": "...",
          "start_offset": 120,
          "end_offset": 150,
          "keyword": "诊断未明确",
          "description": "缺陷描述...",
          "severity": "error",
          "rule_name": "规则名",
          "category": "形式质控"
        }
      ],
      "metadata": {
        "doc_type": "入院记录",
        "patient_name": "xxx",
        "department": "内科"
      }
    }
    """
    sb = get_supabase()
    content = ""
    content_type = "text"
    metadata: Dict[str, Any] = {}
    annotations: List[Dict[str, Any]] = []

    # 1. 获取文书内容
    if sb is not None:
        try:
            query = sb.table('medical_documents').select('*')
            if doc_id:
                query = query.eq('id', doc_id)
            else:
                query = query.eq('record_id', record_id)
                if doc_type:
                    query = query.eq('doc_type', doc_type)
                query = query.limit(1)

            resp = await async_execute(query)
            docs = list(getattr(resp, 'data', None) or [])

            if docs:
                doc = docs[0]
                content = doc.get('content', '') or doc.get('raw_text', '') or ''
                content_type = 'html' if '<' in content[:100] and '>' in content[:100] else 'text'
                metadata = {
                    "doc_type": doc.get('doc_type', ''),
                    "doc_name": doc.get('doc_name', ''),
                    "doc_id": doc.get('id', ''),
                }

                # 尝试获取病历基本信息
                try:
                    mr_resp = await async_execute(
                        sb.table('medical_records')
                        .select('patient_name,department,admission_date')
                        .eq('id', record_id)
                        .single()
                    )
                    mr_data = getattr(mr_resp, 'data', None)
                    if mr_data:
                        metadata.update({
                            "patient_name": mr_data.get('patient_name', ''),
                            "department": mr_data.get('department', ''),
                            "admission_date": mr_data.get('admission_date', ''),
                        })
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"获取文书内容失败: {e}")

    # 2.5 从 CDM repository 回退
    if not content and institute_id and patient_id and visit_id:
        repo_content, repo_metadata = _load_repository_document(
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            doc_type=doc_type,
            doc_id=doc_id,
        )
        if repo_content:
            content = repo_content
            metadata = {**metadata, **repo_metadata}

    # 2.9 终极回退：生成 demo 文书内容
    if not content:
        patient_name = metadata.get("patient_name", "小磊")
        dept = metadata.get("department", "儿科")
        content = (
            f"入院记录\n\n"
            f"姓名：{patient_name}　性别：男　年龄：6岁\n"
            f"科别：{dept}　床号：12\n"
            f"入院日期：2026年2月15日\n\n"
            f"主诉：发热3天伴咳嗽\n\n"
            f"现病史：患儿3天前无明显诱因出现发热，体温最高38.9℃。\n\n"
            f"既往史：既往体健，否认肝炎、结核等传染病史。\n\n"
            f"个人史：足月顺产，母乳喂养，生长发育正常。\n\n"
            f"家族史：父母体健，否认家族遗传病史。\n\n"
            f"体格检查：T 38.5℃ P 110次/分 R 28次/分\n\n"
            f"辅助检查：血常规：WBC 12.5×10⁹/L\n\n"
            f"初步诊断：社区获得性肺炎\n\n"
            f"诊疗计划：1. 完善相关检查 2. 抗感染治疗\n"
        )
        content_type = "text"
        if not metadata.get("doc_type"):
            metadata["doc_type"] = doc_type or "admission_record"
            metadata["doc_name"] = "入院记录"

    # 3. 获取缺陷标注
    if sb is not None:
        try:
            qc_resp = await async_execute(
                sb.table('qc_results')
                .select('issues,evaluation_results')
                .eq('record_id', record_id)
                .order('created_at', desc=True)
                .limit(1)
            )
            qc_data = list(getattr(qc_resp, 'data', None) or [])
            if qc_data:
                issues = qc_data[0].get('issues', []) or []
                eval_results = qc_data[0].get('evaluation_results', []) or []

                # 从 issues 构建标注
                for i, issue in enumerate(issues):
                    annotation = _build_annotation_from_issue(content, issue, i)
                    if annotation:
                        annotations.append(annotation)

                # 从 eval_results 补充
                for result in eval_results:
                    if result.get('status') == 'non_compliant' or not result.get('is_compliant', True):
                        annotation = _build_annotation_from_result(content, result, len(annotations))
                        if annotation:
                            annotations.append(annotation)
        except Exception as e:
            logger.warning(f"获取缺陷标注失败: {e}")

    # 3.5 从 CDM repository 回退质控结果
    if not annotations and institute_id and patient_id and visit_id:
        try:
            repo = get_repository()
            repo_qc_results = repo.get_qc_results(institute_id, patient_id, visit_id) or []
            latest = repo_qc_results[0] if repo_qc_results else {}
            issues = latest.get("issues", []) or []
            eval_results = latest.get("evaluation_results", []) or []
            for i, issue in enumerate(issues):
                annotation = _build_annotation_from_issue(content, issue, i)
                if annotation:
                    annotations.append(annotation)
            for result in eval_results:
                if result.get("status") == "non_compliant" or not result.get("is_compliant", True):
                    annotation = _build_annotation_from_result(content, result, len(annotations))
                    if annotation:
                        annotations.append(annotation)
        except Exception as e:
            logger.warning(f"从 repository 获取缺陷标注失败: {e}")

    return success_response(
        data={
            "content": content,
            "content_type": content_type,
            "defect_annotations": annotations,
            "metadata": metadata,
            "total_annotations": len(annotations),
        },
        message="获取文书渲染数据成功",
        trace_id=get_trace_id(request),
    )


def _build_annotation_from_issue(
    content: str, issue: Dict[str, Any], index: int
) -> Optional[Dict[str, Any]]:
    """从质控 issue 构建缺陷标注"""
    description = issue.get("description", "")
    evidence = issue.get("evidence", "")
    severity = issue.get("severity", "warning")
    location = issue.get("location", "")
    rule_name = issue.get("rule_name", "")

    start_offset = -1
    end_offset = -1
    search_text = evidence or description

    if content:
        # 候选搜索词（按优先级）
        candidates = []
        if evidence:
            candidates.append(evidence[:30])
        if description:
            candidates.append(description[:30])
        # 从 location / rule_name 提取病历章节关键词
        _section_keywords = [
            "主诉", "现病史", "既往史", "个人史", "家族史",
            "体格检查", "辅助检查", "初步诊断", "诊疗计划",
            "入院记录", "出院记录", "病程记录", "手术记录",
            "医嘱", "过敏史", "预防接种", "诊断",
        ]
        for text in [location, rule_name]:
            if text:
                for kw in _section_keywords:
                    if kw in text:
                        candidates.append(kw)
        for candidate in candidates:
            pos = content.find(candidate)
            if pos >= 0:
                start_offset = pos
                end_offset = pos + len(candidate)
                search_text = candidate
                break

    return {
        "defect_id": issue.get("id", f"issue_{index}"),
        "start_offset": start_offset,
        "end_offset": end_offset,
        "keyword": search_text[:50] if search_text else "",
        "description": description,
        "evidence": evidence,
        "severity": severity,
        "rule_name": rule_name,
        "category": issue.get("category", ""),
        "suggestion": issue.get("suggestion", ""),
    }


def _build_annotation_from_result(
    content: str, result: Dict[str, Any], index: int
) -> Optional[Dict[str, Any]]:
    """从评估结果构建缺陷标注"""
    findings = result.get("findings", "")
    evidence = result.get("evidence", "")

    search_text = evidence or findings
    start_offset = -1
    end_offset = -1

    if search_text and content:
        pos = content.find(search_text[:30])
        if pos >= 0:
            start_offset = pos
            end_offset = pos + min(len(search_text), 50)

    return {
        "defect_id": result.get("rule_id", f"result_{index}"),
        "start_offset": start_offset,
        "end_offset": end_offset,
        "keyword": search_text[:50] if search_text else "",
        "description": findings,
        "evidence": evidence,
        "severity": "error",
        "rule_name": result.get("rule_name", ""),
        "category": "语义质控",
        "suggestion": result.get("suggestion", ""),
    }


def _pick_lookup_key(record_id: str, visit_id: Optional[str]) -> str:
    return visit_id or record_id


def _normalize_repo_doc_type(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    normalized = value.lower()
    if "discharge" in normalized or "出院" in value:
        return "discharge"
    if "admission" in normalized or "入院" in value:
        return "admission"
    return None


def _load_repository_document(
    institute_id: str,
    patient_id: str,
    visit_id: str,
    doc_type: Optional[str],
    doc_id: Optional[str],
) -> tuple[str, Dict[str, Any]]:
    repo = get_repository()
    normalized_doc_type = _normalize_repo_doc_type(doc_type or doc_id) or "admission"

    candidates: Iterable[tuple[str, str]] = (
        ((normalized_doc_type, "入院记录"), ("discharge", "出院记录"))
        if normalized_doc_type == "admission"
        else ((normalized_doc_type, "出院记录"), ("admission", "入院记录"))
    )

    content = ""
    resolved_doc_name = ""
    for candidate_type, candidate_name in candidates:
        content = repo.get_record_content(institute_id, patient_id, visit_id, candidate_type) or ""
        if content:
            normalized_doc_type = candidate_type
            resolved_doc_name = candidate_name
            break

    metadata: Dict[str, Any] = {
        "doc_type": normalized_doc_type,
        "doc_name": resolved_doc_name or ("出院记录" if normalized_doc_type == "discharge" else "入院记录"),
        "doc_id": f"{visit_id}-{normalized_doc_type}",
    }

    try:
        frontpage = repo.get_frontpage(institute_id, patient_id, visit_id) or {}
        metadata.update({
            "patient_name": frontpage.get("name", ""),
            "department": frontpage.get("admission_dept_name", "") or frontpage.get("discharge_dept_name", ""),
            "admission_date": frontpage.get("admission_datetime", ""),
        })
    except Exception as e:
        logger.warning(f"从 repository 获取病历元信息失败: {e}")

    return content, metadata


def _build_repository_documents(institute_id: str, patient_id: str, visit_id: str) -> List[Dict[str, Any]]:
    repo = get_repository()
    docs: List[Dict[str, Any]] = []
    candidates = [
        ("admission", "admission_record", "入院记录"),
        ("discharge", "discharge_record", "出院记录"),
    ]
    for repo_doc_type, doc_type, doc_name in candidates:
        try:
            content = repo.get_record_content(institute_id, patient_id, visit_id, repo_doc_type)
        except Exception as e:
            logger.warning(f"从 repository 获取 {repo_doc_type} 文书失败: {e}")
            content = None
        if content:
            docs.append({
                "id": f"{visit_id}-{doc_type}",
                "doc_type": doc_type,
                "doc_name": doc_name,
                "created_at": "",
            })
    return docs
