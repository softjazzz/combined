"""
医疗文书分类API
支持层级化的文书分类和质控
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import json

# 假设已有的数据库连接
# from .database import get_db_connection

router = APIRouter(prefix="/api/documents", tags=["文书分类"])

# ==================== 数据模型 ====================

class DocumentCategory(BaseModel):
    id: Optional[str] = None
    category_code: str
    category_name: str
    description: Optional[str] = None
    sort_order: int = 0
    is_active: bool = True

class DocumentType(BaseModel):
    id: Optional[str] = None
    category_id: str
    type_code: str
    type_name: str
    description: Optional[str] = None
    sort_order: int = 0
    is_active: bool = True
    required_sections: List[str] = []
    validation_rules: Dict[str, Any] = {}

class MedicalDocument(BaseModel):
    id: Optional[str] = None
    record_id: str
    category_id: str
    type_id: str
    title: str
    content: str
    summary: Optional[str] = None
    ai_classified: bool = False
    classification_confidence: float = 0.0
    manual_verified: bool = False
    position_info: Dict[str, Any] = {}
    sort_order: int = 0
    status: str = "active"
    qc_status: str = "pending"
    qc_score: Optional[float] = None
    qc_issues: List[Dict[str, Any]] = []
    metadata: Dict[str, Any] = {}

class DocumentClassificationRequest(BaseModel):
    record_id: str
    content: str
    auto_classify: bool = True
    confidence_threshold: float = 0.7

class QCTemplateRequest(BaseModel):
    document_id: str
    template_id: Optional[str] = None
    custom_rules: Dict[str, Any] = {}

# ==================== API端点 ====================

@router.get("/categories", response_model=List[DocumentCategory])
async def get_document_categories():
    """获取所有文书分类（一级目录）"""
    try:
        # 模拟数据库查询
        categories = [
            {
                "id": "cat_1",
                "category_code": "admission_record",
                "category_name": "入院记录",
                "description": "患者入院时的基本信息和病情记录",
                "sort_order": 1,
                "is_active": True
            },
            {
                "id": "cat_2", 
                "category_code": "progress_note",
                "category_name": "病程记录",
                "description": "患者住院期间的病情变化和治疗过程记录",
                "sort_order": 2,
                "is_active": True
            },
            {
                "id": "cat_3",
                "category_code": "operation_record", 
                "category_name": "手术记录",
                "description": "手术相关的各类记录文书",
                "sort_order": 3,
                "is_active": True
            },
            {
                "id": "cat_4",
                "category_code": "nursing_document",
                "category_name": "护理文书", 
                "description": "护理相关的记录和评估文书",
                "sort_order": 4,
                "is_active": True
            },
            {
                "id": "cat_5",
                "category_code": "discharge_record",
                "category_name": "出院记录",
                "description": "患者出院时的总结和后续指导", 
                "sort_order": 5,
                "is_active": True
            },
            {
                "id": "cat_6",
                "category_code": "examination_report",
                "category_name": "检查报告",
                "description": "各类检查和化验报告",
                "sort_order": 6,
                "is_active": True
            },
            {
                "id": "cat_7",
                "category_code": "medical_order",
                "category_name": "医嘱记录", 
                "description": "医生开具的各类医嘱记录",
                "sort_order": 7,
                "is_active": True
            }
        ]
        return categories
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取文书分类失败: {str(e)}")

@router.get("/types", response_model=List[DocumentType])
async def get_document_types(category_id: Optional[str] = None):
    """获取文书类型（二级目录）"""
    try:
        # 模拟数据库查询
        all_types = [
            # 入院记录类
            {"id": "type_1", "category_id": "cat_1", "type_code": "admission_record", "type_name": "入院记录", "sort_order": 1},
            {"id": "type_2", "category_id": "cat_1", "type_code": "admission_diagnosis", "type_name": "入院诊断", "sort_order": 2},
            
            # 病程记录类
            {"id": "type_3", "category_id": "cat_2", "type_code": "first_progress_note", "type_name": "首次病程记录", "sort_order": 1},
            {"id": "type_4", "category_id": "cat_2", "type_code": "daily_progress_note", "type_name": "日常病程记录", "sort_order": 2},
            {"id": "type_5", "category_id": "cat_2", "type_code": "attending_progress", "type_name": "上级医师查房记录", "sort_order": 3},
            
            # 手术记录类
            {"id": "type_6", "category_id": "cat_3", "type_code": "preoperative_summary", "type_name": "术前小结", "sort_order": 1},
            {"id": "type_7", "category_id": "cat_3", "type_code": "operation_record", "type_name": "手术记录", "sort_order": 2},
            
            # 护理文书类
            {"id": "type_8", "category_id": "cat_4", "type_code": "nursing_record", "type_name": "护理记录单", "sort_order": 1},
            {"id": "type_9", "category_id": "cat_4", "type_code": "temperature_chart", "type_name": "体温单", "sort_order": 2},
            
            # 出院记录类
            {"id": "type_10", "category_id": "cat_5", "type_code": "discharge_record", "type_name": "出院记录", "sort_order": 1},
            {"id": "type_11", "category_id": "cat_5", "type_code": "discharge_summary", "type_name": "出院小结", "sort_order": 2},
        ]
        
        if category_id:
            types = [t for t in all_types if t["category_id"] == category_id]
        else:
            types = all_types
            
        return types
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取文书类型失败: {str(e)}")

@router.post("/classify")
async def classify_document(request: DocumentClassificationRequest):
    """对医疗文书进行智能分类"""
    try:
        # 这里应该调用LLM进行文书分类
        # 模拟分类结果
        classification_result = {
            "record_id": request.record_id,
            "classified_documents": [
                {
                    "title": "入院记录",
                    "category_id": "cat_1",
                    "type_id": "type_1", 
                    "confidence": 0.95,
                    "content_summary": "患者因胸痛3天入院...",
                    "position_info": {
                        "start_marker": "入院记录",
                        "end_marker": "入院诊断",
                        "estimated_start": 0,
                        "estimated_end": 500
                    }
                },
                {
                    "title": "首次病程记录",
                    "category_id": "cat_2", 
                    "type_id": "type_3",
                    "confidence": 0.88,
                    "content_summary": "患者入院后病情稳定...",
                    "position_info": {
                        "start_marker": "首次病程记录",
                        "end_marker": "日常病程记录", 
                        "estimated_start": 800,
                        "estimated_end": 1200
                    }
                }
            ],
            "total_confidence": 0.91,
            "processing_time_ms": 1500
        }
        
        return classification_result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文书分类失败: {str(e)}")

@router.get("/records/{record_id}/documents")
async def get_record_documents(record_id: str):
    """获取指定病历的所有文书"""
    try:
        # 模拟数据库查询
        documents = [
            {
                "id": "doc_1",
                "record_id": record_id,
                "category_id": "cat_1",
                "type_id": "type_1",
                "title": "入院记录",
                "content": "患者张三，男，65岁...",
                "summary": "65岁男性患者因胸痛入院",
                "ai_classified": True,
                "classification_confidence": 0.95,
                "qc_status": "passed",
                "qc_score": 85.5
            }
        ]
        return {"documents": documents}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取文书列表失败: {str(e)}")

@router.post("/qc/analyze")
async def analyze_document_qc(request: QCTemplateRequest):
    """对指定文书进行质控分析"""
    try:
        # 这里应该根据文书类型选择对应的质控模板和规则
        qc_result = {
            "document_id": request.document_id,
            "template_used": "入院记录质控模板",
            "overall_score": 85.5,
            "detailed_scores": {
                "completeness": 90,
                "accuracy": 85,
                "timeliness": 80,
                "consistency": 87
            },
            "issues": [
                {
                    "category": "completeness",
                    "description": "缺少家族史记录",
                    "severity": "minor",
                    "suggestion": "建议补充患者家族史信息"
                }
            ],
            "passed": True,
            "analysis_time_ms": 2000
        }
        
        return qc_result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"质控分析失败: {str(e)}")

@router.get("/qc/templates")
async def get_qc_templates():
    """获取所有质控模板"""
    try:
        templates = [
            {
                "id": "template_1",
                "template_name": "入院记录质控模板",
                "template_code": "ADMISSION_QC",
                "applicable_categories": ["cat_1"],
                "description": "针对入院记录的专门质控模板"
            },
            {
                "id": "template_2", 
                "template_name": "病程记录质控模板",
                "template_code": "PROGRESS_QC",
                "applicable_categories": ["cat_2"],
                "description": "针对病程记录的专门质控模板"
            }
        ]
        return {"templates": templates}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取质控模板失败: {str(e)}")
