"""
DRG 批量数据模型

用于存储 Excel 上传的 DRG 病例数据和分组结果
"""

from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import date, datetime
from decimal import Decimal


class DRGBatchRecord(BaseModel):
    """DRG 批量记录"""
    id: Optional[int] = None
    batch_id: str = Field(..., description="批次ID")
    admission_id: str = Field(..., description="住院号/病案号")
    
    # 患者信息
    gender: int = Field(..., description="性别: 1=男, 2=女")
    age: int = Field(..., description="年龄(岁)")
    age_day: Optional[int] = Field(None, description="年龄(天), 新生儿必填")
    weight: Optional[int] = Field(None, description="出生体重(g), 新生儿必填")
    
    # 住院信息
    department: str = Field(..., description="科室代码")
    department_name: Optional[str] = Field(None, description="科室名称")
    los: int = Field(..., description="住院天数")
    leaving_type: int = Field(..., description="离院方式: 1-5,9")
    admission_date: Optional[date] = Field(None, description="入院日期")
    discharge_date: Optional[date] = Field(None, description="出院日期")
    
    # 诊断和手术
    diagnosis_codes: str = Field(..., description="诊断ICD列表, |分隔")
    procedure_codes: Optional[str] = Field(None, description="手术ICD列表, |分隔")
    
    # 费用信息
    total_cost: Decimal = Field(..., description="总费用")
    insurance_payment: Optional[Decimal] = Field(None, description="医保支付")
    drug_cost: Optional[Decimal] = Field(None, description="药品费")
    material_cost: Optional[Decimal] = Field(None, description="耗材费")
    exam_cost: Optional[Decimal] = Field(None, description="检查费")
    treatment_cost: Optional[Decimal] = Field(None, description="治疗费")
    
    # 医生信息
    doctor: Optional[str] = Field(None, description="主管医生")
    
    # DRG 分组结果
    mdc: Optional[str] = Field(None, description="MDC 大类")
    adrg: Optional[str] = Field(None, description="ADRG 组")
    drg: Optional[str] = Field(None, description="DRG 组")
    drg_weight: Optional[float] = Field(None, description="DRG 权重")
    baseline_payment: Optional[Decimal] = Field(None, description="基准支付")
    profit_margin: Optional[Decimal] = Field(None, description="盈亏金额")
    status: Optional[str] = Field(None, description="分组状态")
    messages: Optional[str] = Field(None, description="分组消息")
    
    created_at: Optional[datetime] = None


class DRGBatchUploadRequest(BaseModel):
    """批量上传请求"""
    batch_name: Optional[str] = Field(None, description="批次名称")


class DRGBatchUploadResponse(BaseModel):
    """批量上传响应"""
    batch_id: str
    total_records: int
    success_count: int
    failed_count: int
    results: List[dict]


class DRGStatisticsRequest(BaseModel):
    """统计查询请求"""
    batch_id: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    department: Optional[str] = None
    doctor: Optional[str] = None


class DRGDrillDownRequest(BaseModel):
    """钻取请求"""
    dimension: str = Field(..., description="维度: department/doctor/drg/mdc")
    value: str = Field(..., description="维度值")
    page: int = 1
    per_page: int = 20
