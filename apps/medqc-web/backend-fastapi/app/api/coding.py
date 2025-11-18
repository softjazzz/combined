"""
编码辅助 API
PRD 3.2.1 - 编码智能辅助
"""

from fastapi import APIRouter, HTTPException
from loguru import logger

from app.models.schemas import (
    CodingSuggestRequest,
    CodingSuggestResponse,
    CodingValidateRequest,
    ValidationResult,
    ICDSearchRequest,
    ICDSearchResponse,
    ICDCode
)
from app.services.llm_service import llm_service
from app.services.database import db_service

router = APIRouter(prefix="/coding", tags=["编码辅助"])


@router.post(
    "/suggest",
    response_model=CodingSuggestResponse,
    summary="ICD 编码推荐",
    description="PRD 3.2.1 API接口1：根据诊断名称推荐 ICD 编码"
)
async def suggest_coding(request: CodingSuggestRequest):
    """
    ICD 编码推荐

    使用 LLM 根据诊断或手术操作名称推荐最合适的 ICD 编码。

    **示例请求**：
    ```json
    {
      "diagnosis_name": "急性心肌梗死",
      "context": "患者突发胸痛，心电图示前壁ST段抬高",
      "category": "diagnosis"
    }
    ```

    **返回**：
    - candidates: ICD 编码推荐列表（按置信度降序）
    - total: 推荐结果总数
    """
    try:
        logger.info(f"接收编码推荐请求: {request.diagnosis_name}")

        # 调用 LLM 服务
        suggestions = await llm_service.suggest_icd_codes(
            diagnosis_name=request.diagnosis_name,
            context=request.context,
            category=request.category,
            top_k=3
        )

        return CodingSuggestResponse(
            candidates=suggestions,
            total=len(suggestions)
        )

    except Exception as e:
        logger.error(f"编码推荐失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"编码推荐失败: {str(e)}")


@router.post(
    "/validate",
    response_model=ValidationResult,
    summary="编码校验",
    description="PRD 3.2.1 API接口2：校验编码完整性和准确性"
)
async def validate_coding(request: CodingValidateRequest):
    """
    编码校验

    检查病案编码的完整性、准确性和逻辑一致性。

    **检查项**：
    - 诊断编码完整性（是否遗漏重要诊断）
    - 手术操作编码完整性
    - 并发症标记是否准确
    - 主次诊断的逻辑关系
    - 诊断与手术的匹配性

    **示例请求**：
    ```json
    {
      "admission_id": "ADM20250104001",
      "primary_diagnosis": {
        "code": "I21.001",
        "name": "急性前壁ST段抬高型心肌梗死"
      },
      "secondary_diagnoses": [
        {"code": "I10.x01", "name": "高血压3级"}
      ],
      "procedures": [
        {"code": "36.0700", "name": "经皮冠状动脉介入术"}
      ]
    }
    ```

    **返回**：
    - is_valid: 编码是否有效
    - warnings: 警告列表
    - conflicts: 逻辑冲突列表
    """
    try:
        logger.info(f"接收编码校验请求: {request.admission_id}")

        # 准备数据
        primary_diag_dict = {
            'code': request.primary_diagnosis.code,
            'name': request.primary_diagnosis.name
        }

        secondary_diags_list = [
            {'code': d.code, 'name': d.name}
            for d in request.secondary_diagnoses
        ]

        procedures_list = [
            {'code': p.code, 'name': p.name}
            for p in request.procedures
        ]

        # TODO: 获取病历摘要（可选）
        # medical_record = await get_medical_record_summary(request.admission_id)
        medical_record = None

        # 调用 LLM 服务进行校验
        warnings = await llm_service.validate_coding(
            primary_diagnosis=primary_diag_dict,
            secondary_diagnoses=secondary_diags_list,
            procedures=procedures_list,
            medical_record=medical_record
        )

        # 检查逻辑冲突
        conflicts = []
        # TODO: 实现规则引擎检查逻辑冲突
        # 例如：主诊断和次诊断的互斥关系、手术与诊断的不匹配等

        # 判定是否有效
        has_errors = any(w.severity == 'error' for w in warnings)
        is_valid = not has_errors and len(conflicts) == 0

        # 保存编码建议到数据库（如果有警告）
        if warnings:
            for warning in warnings:
                await db_service.save_coding_suggestion(
                    admission_id=request.admission_id,
                    suggestion_type=warning.type,
                    message=warning.message,
                    evidence=warning.evidence,
                    severity=warning.severity
                )

        return ValidationResult(
            is_valid=is_valid,
            warnings=warnings,
            conflicts=conflicts
        )

    except Exception as e:
        logger.error(f"编码校验失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"编码校验失败: {str(e)}")


@router.get(
    "/search",
    response_model=ICDSearchResponse,
    summary="ICD 编码搜索",
    description="搜索 ICD-10 或 ICD-9-CM-3 编码库"
)
async def search_icd_codes(
    keyword: str,
    category: str = "diagnosis",
    limit: int = 20
):
    """
    ICD 编码搜索

    在 ICD 编码库中搜索关键词，支持编码和名称搜索。

    **参数**：
    - keyword: 搜索关键词（支持编码或名称）
    - category: 编码类型（diagnosis=诊断, procedure=手术操作）
    - limit: 返回结果数量（默认20）

    **示例**：
    - GET /api/v1/coding/search?keyword=心肌梗死&category=diagnosis
    - GET /api/v1/coding/search?keyword=I21&category=diagnosis
    """
    try:
        logger.info(f"ICD 编码搜索: {keyword}, 类型: {category}")

        # 调用数据库服务
        if category == 'diagnosis':
            results = await db_service.search_icd10_codes(keyword, limit)
        else:
            results = await db_service.search_icd9_procedures(keyword, limit)

        # 转换为 Pydantic 模型
        icd_codes = [
            ICDCode(
                code=item['code'],
                name=item['name'],
                category=item.get('category'),
                notes=item.get('notes')
            )
            for item in results
        ]

        return ICDSearchResponse(
            results=icd_codes,
            total=len(icd_codes)
        )

    except Exception as e:
        logger.error(f"ICD 编码搜索失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")


@router.get(
    "/icd/{code}",
    response_model=ICDCode,
    summary="获取 ICD 编码详情",
    description="根据编码获取 ICD 详细信息"
)
async def get_icd_code_detail(code: str, category: str = "diagnosis"):
    """
    获取 ICD 编码详情

    **参数**：
    - code: ICD 编码
    - category: 编码类型（diagnosis/procedure）

    **示例**：
    - GET /api/v1/coding/icd/I21.001?category=diagnosis
    """
    try:
        logger.info(f"获取 ICD 编码详情: {code}")

        result = await db_service.get_icd_code_by_code(code, category)

        if not result:
            raise HTTPException(status_code=404, detail=f"编码 {code} 未找到")

        return ICDCode(
            code=result['code'],
            name=result['name'],
            category=result.get('category'),
            notes=result.get('notes')
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取 ICD 编码详情失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")
