"""
任务管理相关 Schema

用于质控抽查任务的创建、分配、执行等操作
"""

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from typing import Annotated, Optional, List, Dict, Any, Literal
from enum import Enum


# ============================================================================
# Enums
# ============================================================================

class TaskType(str, Enum):
    """任务类型"""
    ONE_TIME = "one_time"       # 单次
    SCHEDULED = "scheduled"     # 定时/定期


class TaskStatus(str, Enum):
    """任务状态"""
    DRAFT = "draft"             # 草稿
    SAMPLING = "sampling"       # 抽样中
    ASSIGNED = "assigned"       # 已分配
    IN_PROGRESS = "in_progress" # 进行中
    COMPLETED = "completed"     # 已完成
    CANCELLED = "cancelled"     # 已取消


class TaskScene(str, Enum):
    """任务创建时确定的病历场景。"""
    RUNNING = "running"
    FINAL = "final"
    OUTPATIENT = "outpatient"


class SamplingMethod(str, Enum):
    """抽样方式"""
    ALL = "all"                 # 全部
    COUNT = "count"             # 按总数
    PERCENTAGE = "percentage"   # 按百分比


class AssignMethod(str, Enum):
    """分配方式"""
    KEEP = "keep"               # 保持原有分配
    BY_DEPARTMENT = "by_department"  # 按科室
    BY_RATIO = "by_ratio"       # 按比例
    BY_TYPE = "by_type"         # 按类型


class TaskRecordStatus(str, Enum):
    """任务内病历状态"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"


# ============================================================================
# Request Models
# ============================================================================

NonEmptyCaseCoordinate = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
RuleSetKey = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]


class TaskCaseRef(BaseModel):
    """任务指定病历的完整工作台身份。"""

    model_config = ConfigDict(extra="forbid")

    institute_id: NonEmptyCaseCoordinate
    patient_id: NonEmptyCaseCoordinate
    visit_id: NonEmptyCaseCoordinate


class TaskCreateRequest(BaseModel):
    """创建任务请求"""

    model_config = ConfigDict(extra="forbid")

    task_name: str = Field(..., description="任务名称")
    task_type: TaskType = Field(TaskType.ONE_TIME, description="任务类型")
    scene: TaskScene = Field(..., description="任务病历场景")
    rule_set_key: RuleSetKey = Field(..., description="创建时显式选择的规则集 key")
    schedule_config: Optional[Dict[str, Any]] = Field(None, description="定时配置")

    # 病历范围
    date_range: Optional[Dict[str, str]] = Field(None, description="日期范围 { start, end }")
    department_filter: Optional[List[str]] = Field(default_factory=list, description="科室筛选")
    record_ids: Optional[List[str]] = Field(default_factory=list, description="指定病历ID")
    record_refs: List[TaskCaseRef] = Field(default_factory=list, description="指定病历三坐标")

    # 抽样规则
    sampling_method: SamplingMethod = Field(SamplingMethod.ALL, description="抽样方式")
    sampling_config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="抽样配置")

    # 任务分配
    assign_method: AssignMethod = Field(AssignMethod.BY_RATIO, description="分配方式")
    assignee_config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="分配配置")

    # 其他
    deadline: Optional[str] = Field(None, description="截止日期 (ISO 8601)")

    @model_validator(mode="after")
    def validate_creation_scope(self):
        if not self.record_refs:
            return self
        if self.record_ids:
            raise ValueError("record_refs 不得与旧 record_ids 混用")
        identities = [
            (item.institute_id, item.patient_id, item.visit_id)
            for item in self.record_refs
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("record_refs 不得包含重复病例三坐标")
        return self


class TaskUpdateRequest(BaseModel):
    """受领人开始任务；其他变更必须走各自的专用入口。"""

    model_config = ConfigDict(extra="forbid")

    status: Literal["in_progress"]


class TaskAssignee(BaseModel):
    """任务分配人员。"""

    model_config = ConfigDict(extra="forbid")
    user_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=36)]
    user_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    department: Optional[str] = None


class TaskAssignRequest(BaseModel):
    """分配任务请求"""
    assignees: List[TaskAssignee] = Field(
        ...,
        min_length=1,
        description="分配列表 [{ user_id, user_name, department? }]"
    )
    method: AssignMethod = Field(AssignMethod.BY_RATIO, description="分配方式")

    @model_validator(mode="after")
    def unique_assignees(self) -> "TaskAssignRequest":
        ids = [assignee.user_id for assignee in self.assignees]
        if len(ids) != len(set(ids)):
            raise ValueError("分配人员 user_id 不可重复")
        return self


class TaskRecordUpdateRequest(BaseModel):
    """更新任务内病历状态"""
    status: TaskRecordStatus = Field(..., description="新状态")
    qc_result_id: Optional[str] = Field(None, description="关联质控结果ID")
    score: Optional[int] = Field(None, description="质控评分")
    defect_count: Optional[int] = Field(None, description="缺陷数量")


class TaskRecordCompleteRequest(BaseModel):
    """受领质控员显式提交本次已核实的任务病历结果。"""

    model_config = ConfigDict(extra="forbid")

    run_number: int = Field(..., strict=True, gt=0, description="assigned 质控运行序号")


# ============================================================================
# Response Models
# ============================================================================

class TaskResponse(BaseModel):
    """任务响应"""
    id: str
    task_number: str
    task_name: str
    task_type: str
    scene: Optional[TaskScene] = None
    rule_set_key: Optional[str] = None
    rule_set_version: Optional[str] = None
    status: str
    progress: int = 0
    total_records: int = 0
    completed_records: int = 0
    creator_id: str
    creator_name: str = ""
    deadline: Optional[str] = None
    created_at: str
    updated_at: str

    # 可选详情
    sampling_method: Optional[str] = None
    assign_method: Optional[str] = None
    date_range: Optional[Dict[str, str]] = None
    department_filter: Optional[List[str]] = None
    record_refs: Optional[List[TaskCaseRef]] = None


class TaskProgressResponse(BaseModel):
    """任务进度"""
    task_id: str
    task_name: str
    total_records: int = 0
    completed_records: int = 0
    progress_pct: float = 0
    pending_count: int = 0
    working_count: int = 0
    done_count: int = 0
    avg_score: Optional[float] = None
    total_defects: int = 0
