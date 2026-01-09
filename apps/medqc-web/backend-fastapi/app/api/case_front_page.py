"""\
病案首页 API
提供病案首页的查询与维护接口
"""

from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
try:
    from loguru import logger
except Exception:
    import logging

    logger = logging.getLogger(__name__)

from app.config import settings
from app.models.schemas import CaseFrontPageCreate, CaseFrontPageDetail
from app.services.database import db_service
from app.services.demo_data_store import get_demo_store
from app.services.llm_service import llm_service
from app.services.external_coding_service import external_coding_service

router = APIRouter(prefix="/case-front-page", tags=["病案首页"])


# 请求模型
class ExtractFrontpageRequest(BaseModel):
    """提取病案首页请求"""
    medical_text: str


class ExtractCodingRequest(BaseModel):
    """提取 ICD 编码请求"""
    medical_text: str
    patient_age: int = 50
    patient_gender: str = "M"  # M or F


@router.post(
    "/extract",
    summary="从病历原文中提取结构化数据",
    description="使用 LLM 从病历原文（入院记录、出院小结等）中提取病案首页结构化数据，并生成 ICD 编码"
)
async def extract_frontpage_from_text(request: ExtractFrontpageRequest) -> Dict[str, Any]:
    """
    从病历原文中提取病案首页结构化数据
    
    步骤：
    1. LLM 提取结构化字段（姓名、诊断、手术等）
    2. 为提取的诊断和手术生成 ICD 编码
    3. 合并返回完整结果
    """
    try:
        if not request.medical_text or len(request.medical_text.strip()) < 50:
            raise HTTPException(status_code=400, detail="病历原文内容过短，无法进行结构化提取")
        
        logger.info(f"开始 LLM 结构化提取，文本长度: {len(request.medical_text)}")
        
        # Step 1: LLM 结构化提取
        result = await llm_service.extract_frontpage_structured(request.medical_text)
        
        if not result:
            raise HTTPException(status_code=500, detail="LLM 结构化提取失败，请检查 LLM 服务配置")
        
        # Step 2: 从提取结果中获取诊断和手术名称（防止 None 值）
        diagnoses_section = result.get("diagnoses") or {}
        procedures_section = result.get("procedures") or {}
        
        # 收集入院诊断
        admission_main_diag = diagnoses_section.get("admission_main_diagnosis_text")
        admission_other_diags = diagnoses_section.get("admission_other_diagnoses_texts") or []
        
        # 收集出院诊断
        discharge_main_diag = diagnoses_section.get("discharge_main_diagnosis_text")
        discharge_other_diags = diagnoses_section.get("discharge_other_diagnoses_texts") or []
        
        # 合并所有诊断名称用于编码
        all_diagnoses = []
        if admission_main_diag:
            all_diagnoses.append(admission_main_diag)
        if admission_other_diags:
            all_diagnoses.extend(admission_other_diags)
        if discharge_main_diag:
            all_diagnoses.append(discharge_main_diag)
        if discharge_other_diags:
            all_diagnoses.extend(discharge_other_diags)
        
        # 收集手术名称
        all_procedures = []
        main_proc = procedures_section.get("main_procedure_text")
        if main_proc:
            all_procedures.append(main_proc)
        
        # Step 3: 为诊断和手术生成 ICD 编码
        if all_diagnoses or all_procedures:
            logger.info(f"开始生成 ICD 编码: {len(all_diagnoses)} 个诊断 (入院: {1 if admission_main_diag else 0}+{len(admission_other_diags)}, 出院: {1 if discharge_main_diag else 0}+{len(discharge_other_diags)}), {len(all_procedures)} 个手术")
            coding_result = await llm_service.generate_icd_codes(
                diagnoses=all_diagnoses,
                procedures=all_procedures
            )
            
            # Step 4: 将编码合并回结果
            diagnoses_with_codes = coding_result.get("diagnoses_with_codes", [])
            procedures_with_codes = coding_result.get("procedures_with_codes", [])
            
            logger.info(f"编码结果: {len(diagnoses_with_codes)} 个诊断编码, {len(procedures_with_codes)} 个手术编码")
            logger.debug(f"诊断编码详情: {diagnoses_with_codes}")
            
            # 辅助函数：根据诊断名称查找 ICD 编码
            def find_icd_code(diagnosis_name: str) -> str:
                for item in diagnoses_with_codes:
                    if item.get("name") == diagnosis_name:
                        return item.get("icd_code", "待编码")
                return "待编码"
            
            # 更新入院主诊断编码
            if admission_main_diag:
                icd_code = find_icd_code(admission_main_diag)
                result["diagnoses"]["admission_main_icd"] = icd_code
                logger.info(f"入院主诊断编码: {admission_main_diag} -> {icd_code}")
            
            # 更新入院其他诊断编码
            if admission_other_diags:
                admission_other_icds = [find_icd_code(diag) for diag in admission_other_diags]
                result["diagnoses"]["admission_other_icds"] = admission_other_icds
                logger.info(f"入院其他诊断编码: {len(admission_other_icds)} 个")
            
            # 更新出院主诊断编码
            if discharge_main_diag:
                icd_code = find_icd_code(discharge_main_diag)
                result["diagnoses"]["discharge_main_icd"] = icd_code
                logger.info(f"出院主诊断编码: {discharge_main_diag} -> {icd_code}")
            
            # 更新出院其他诊断编码
            if discharge_other_diags:
                discharge_other_icds = [find_icd_code(diag) for diag in discharge_other_diags]
                result["diagnoses"]["discharge_other_icds"] = discharge_other_icds
                logger.info(f"出院其他诊断编码: {len(discharge_other_icds)} 个")
            
            # 更新手术编码
            if procedures_with_codes and main_proc:
                for item in procedures_with_codes:
                    if item.get("name") == main_proc:
                        result["procedures"]["main_procedure_code"] = item.get("icd_code", "待编码")
                        break
            
            # 将完整编码结果附加到响应中
            result["coding_details"] = coding_result
        
        # ===== 保存到 demo store，供 DRG 分组使用 =====
        # 生成唯一的 admission_id
        import hashlib
        import time
        hash_input = f"{result.get('basic_info', {}).get('patient_name', '')}_{time.time()}"
        admission_id = f"EXT{hashlib.md5(hash_input.encode()).hexdigest()[:10].upper()}"
        
        # 映射为 DRG 分组所需的格式（防止 None 值）
        basic_info = result.get("basic_info") or {}
        diagnoses = result.get("diagnoses") or {}
        procedures = result.get("procedures") or {}
        costs = result.get("costs") or {}
        hospitalization = result.get("hospitalization") or {}
        
        # 构造次要诊断列表
        other_texts = diagnoses.get("discharge_other_diagnoses_texts") or []
        other_icds = diagnoses.get("discharge_other_icds") or []
        secondary_diagnoses = [
            {"code": other_icds[i] if i < len(other_icds) else "待编码", "name": name}
            for i, name in enumerate(other_texts)
        ]
        
        # 构造手术列表
        proc_list = []
        if procedures.get("main_procedure_code"):
            proc_list.append({
                "code": procedures.get("main_procedure_code"),
                "name": procedures.get("main_procedure_text", "")
            })
        
        case_for_drg = {
            "admission_id": admission_id,
            "patient_name": basic_info.get("patient_name", "未知"),
            "patient_age": basic_info.get("age_years") or 50,
            "patient_gender": "M" if basic_info.get("gender") == "1" else "F",
            "primary_diagnosis_code": diagnoses.get("discharge_main_icd"),
            "primary_diagnosis_name": diagnoses.get("discharge_main_diagnosis_text"),
            "main_procedure_code": procedures.get("main_procedure_code"),
            "main_procedure_name": procedures.get("main_procedure_text"),
            "secondary_diagnoses": secondary_diagnoses,
            "procedures": proc_list,
            "total_cost": costs.get("total_cost") or 0,
            "total_hospital_days": hospitalization.get("actual_hospital_days") or 0,
            "department": hospitalization.get("admission_dept") or "未知科室",
            "admission_date": hospitalization.get("admission_datetime", "")[:10] if hospitalization.get("admission_datetime") else None,
            "discharge_date": hospitalization.get("discharge_datetime", "")[:10] if hospitalization.get("discharge_datetime") else None,
        }
        
        # 保存到 demo store
        store = get_demo_store()
        store.upsert_case(case_for_drg)
        logger.info(f"已保存提取结果到 demo store, admission_id={admission_id}")
        
        # 在返回结果中附加 admission_id，供前端使用
        result["admission_id"] = admission_id
        
        return {
            "success": True,
            "data": result
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"结构化提取失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"结构化提取失败: {str(e)}")


@router.post(
    "/extract-coding",
    summary="从病历原文中提取 ICD 编码",
    description="调用外部编码服务，从病历原文中提取诊断和手术操作的 ICD 编码"
)
async def extract_coding_from_text(request: ExtractCodingRequest) -> Dict[str, Any]:
    """
    从病历原文中提取 ICD 编码
    
    使用外部专业编码服务（异步任务队列模式），
    返回主诊断、次诊断、主手术、次手术的 ICD 编码及置信度。
    
    Args:
        request: 包含 medical_text, patient_age, patient_gender 的请求体
        
    Returns:
        包含 coding_data 的结构化 ICD 编码结果
    """
    try:
        if not request.medical_text or len(request.medical_text.strip()) < 50:
            raise HTTPException(status_code=400, detail="病历原文内容过短，无法进行编码提取")
        
        logger.info(f"开始外部编码服务调用，文本长度: {len(request.medical_text)}")
        
        result = await external_coding_service.extract_coding(
            medical_text=request.medical_text,
            patient_context={
                "gender": request.patient_gender,
                "age": request.patient_age
            }
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=500, 
                detail=result.get("error", "编码提取失败")
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"编码提取失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"编码提取失败: {str(e)}")


class AnalyzeProfileRequest(BaseModel):
    """患者画像分析请求"""
    medical_text: str
    frontpage_diagnoses: List[str] = []
    frontpage_procedures: List[str] = []


@router.post(
    "/analyze-profile",
    summary="AI 患者画像分析",
    description="使用 LLM 对病历进行深度分析，生成诊断时间轴、生命体征趋势、风险评估等"
)
async def analyze_patient_profile(request: AnalyzeProfileRequest) -> Dict[str, Any]:
    """
    AI 患者画像分析
    
    从病历原文中提取：
    - 诊断发生发展时间轴
    - 生命体征趋势分析
    - 化验检查结果评估
    - 综合风险评估
    - 人体部位标记（用于可视化）
    
    Args:
        request: 包含病历原文和首页信息的请求体
        
    Returns:
        患者画像分析结果
    """
    try:
        if not request.medical_text or len(request.medical_text.strip()) < 50:
            raise HTTPException(status_code=400, detail="病历原文内容过短，无法进行画像分析")
        
        logger.info(f"开始患者画像分析，文本长度: {len(request.medical_text)}")
        
        result = await llm_service.analyze_patient_profile(
            medical_text=request.medical_text,
            frontpage_diagnoses=request.frontpage_diagnoses,
            frontpage_procedures=request.frontpage_procedures
        )
        
        if not result:
            raise HTTPException(status_code=500, detail="画像分析失败，请检查 LLM 服务配置")
        
        return {
            "success": True,
            "data": result
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"画像分析失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"画像分析失败: {str(e)}")


@router.get(
    "",
    response_model=List[CaseFrontPageDetail],
    summary="获取病案首页列表",
    description="获取病案首页列表（用于编码辅助列表页）"
)
async def list_case_front_pages(
    limit: int = Query(100, ge=1, le=500, description="返回数量"),
):
    try:
        if settings.DEMO_MODE or getattr(db_service, 'client', None) is None:
            store = get_demo_store()
            records = store.list_cases(limit=limit)
            return [CaseFrontPageDetail(**record) for record in records]

        records = await db_service.list_case_front_pages(limit=limit)
        if not records:
            store = get_demo_store()
            records = store.list_cases(limit=limit)
        return [CaseFrontPageDetail(**record) for record in records]
    except Exception as e:
        logger.error(f"获取病案首页列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取列表失败: {str(e)}")


@router.get(
    "/{admission_id}",
    response_model=CaseFrontPageDetail,
    summary="获取病案首页详情",
    description="根据住院号获取病案首页详情（包含次诊断、手术操作）"
)
async def get_case_front_page_detail(admission_id: str):
    try:
        if settings.DEMO_MODE or getattr(db_service, 'client', None) is None:
            store = get_demo_store()
            record = store.get_case_detail(admission_id)
            if not record:
                raise HTTPException(status_code=404, detail=f"未找到住院号 {admission_id} 的病案首页")
            return CaseFrontPageDetail(**record)

        record = await db_service.get_case_front_page_detail(admission_id)
        if not record:
            store = get_demo_store()
            record = store.get_case_detail(admission_id)
        if not record:
            raise HTTPException(status_code=404, detail=f"未找到住院号 {admission_id} 的病案首页")
        return CaseFrontPageDetail(**record)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取病案首页详情失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取详情失败: {str(e)}")


@router.post(
    "",
    response_model=CaseFrontPageDetail,
    summary="创建或更新病案首页",
    description="创建或更新病案首页（会同步保存次诊断、手术操作列表）"
)
async def upsert_case_front_page(payload: CaseFrontPageCreate):
    try:
        logger.info(f"保存病案首页: {payload.admission_id}")
        if settings.DEMO_MODE:
            store = get_demo_store()
            record = store.upsert_case(payload.model_dump())
            return CaseFrontPageDetail(**record)
        record = await db_service.upsert_case_front_page(payload)
        return CaseFrontPageDetail(**record)
    except Exception as e:
        logger.error(f"保存病案首页失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")

