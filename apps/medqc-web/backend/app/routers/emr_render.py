"""
EMR 文书渲染 API

功能:
- 获取病历文书内容（原始文本/HTML）
- 返回缺陷位置标注（用于前端高亮）
"""

import logging
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Request, HTTPException, Depends, Query

from ..core.supabase_client import get_supabase, async_execute
from ..core.response import success_response, get_trace_id
from ..core.security import get_current_user

router = APIRouter(prefix="/api/v1/emr", tags=["emr"])
logger = logging.getLogger(__name__)


@router.get("/{record_id}/documents")
async def get_record_documents(
    request: Request,
    record_id: str,
    current_user: dict = Depends(get_current_user),
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

    # 回退：从内存中的质控结果获取文书类型
    if not documents:
        from ..storage.memory import qc_results_db

        if record_id in qc_results_db:
            result = qc_results_db[record_id]
            doc_type = result.get("document_type", "入院记录")
            documents = [
                {
                    "id": f"doc_{record_id}",
                    "doc_type": doc_type,
                    "doc_name": doc_type,
                    "created_at": result.get("analyzed_at", ""),
                }
            ]

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
    current_user: dict = Depends(get_current_user),
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

    # 2. 从内存回退
    if not content:
        from ..storage.memory import qc_results_db

        if record_id in qc_results_db:
            result = qc_results_db[record_id]
            content = result.get("medical_text", "")
            metadata = {
                "doc_type": result.get("document_type", "入院记录"),
                "patient_name": result.get("patient_name", ""),
            }
        else:
            raise HTTPException(status_code=404, detail=f"未找到病历 {record_id} 的文书内容")

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

    # 从内存 QC 结果构建标注
    if not annotations:
        from ..storage.memory import qc_results_db

        if record_id in qc_results_db:
            result = qc_results_db[record_id]
            issues = result.get("issues", [])
            for i, issue in enumerate(issues):
                annotation = _build_annotation_from_issue(content, issue, i)
                if annotation:
                    annotations.append(annotation)

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

    # 尝试在文书中找到证据文本的位置
    search_text = evidence or description
    start_offset = -1
    end_offset = -1

    if search_text and content:
        # 在文书中搜索关键词
        pos = content.find(search_text[:30])  # 用前30个字符搜索
        if pos >= 0:
            start_offset = pos
            end_offset = pos + min(len(search_text), 50)

    return {
        "defect_id": issue.get("id", f"issue_{index}"),
        "start_offset": start_offset,
        "end_offset": end_offset,
        "keyword": search_text[:50] if search_text else "",
        "description": description,
        "evidence": evidence,
        "severity": severity,
        "rule_name": issue.get("rule_name", ""),
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
