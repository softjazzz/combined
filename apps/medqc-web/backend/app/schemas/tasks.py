"""
任务管理相关 Schema

用于质控抽查任务的创建、分配、执行等操作
"""

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator
from typing import Annotated, Optional, List, Dict, Any, Literal
from enum import Enum
from uuid import UUID
from datetime import date, datetime


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
    """分配方式（可执行：by_ratio / by_original_reviewer / by_department）"""
    KEEP = "keep"               # 保持原有分配（不可用）
    BY_DEPARTMENT = "by_department"  # 按科室
    BY_RATIO = "by_ratio"       # 按比例
    BY_ORIGINAL_REVIEWER = "by_original_reviewer"  # 按原质控员
    BY_RECORD_TYPE = "by_record_type"  # 按病历类型（无权威事实，创建时 422 method_unavailable）
    BY_TYPE = "by_type"         # 旧值：按类型（不可用）


class OriginalReviewerFallback(str, Enum):
    """按原质控员分配时，无原质控员或原质控员不在选定人中的处理方式"""
    BY_RATIO = "by_ratio"
    REJECT = "reject"


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
TaskId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
TaskEditName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
TaskDeadline = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)]


class TaskQCRunCreateRequest(BaseModel):
    """可选的病例级质控范围；无请求体时沿用整范围运行。"""

    model_config = ConfigDict(extra="forbid")

    task_record_ids: List[UUID] = Field(..., min_length=1, max_length=500)

    @field_validator("task_record_ids")
    @classmethod
    def validate_unique_record_ids(cls, value: List[UUID]) -> List[UUID]:
        if len(value) != len(set(value)):
            raise ValueError("所选病历存在重复")
        return value


class TaskCaseRef(BaseModel):
    """任务指定病历的完整工作台身份。"""

    model_config = ConfigDict(extra="forbid")

    institute_id: NonEmptyCaseCoordinate
    patient_id: NonEmptyCaseCoordinate
    visit_id: NonEmptyCaseCoordinate


TaskTemplateName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
TaskTemplateDepartment = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class TaskTemplateDateRange(BaseModel):
    """模板保存的绝对日期窗，不解释为相对周期。"""

    model_config = ConfigDict(extra="forbid")

    start: Optional[str] = None
    end: Optional[str] = None

    @field_validator("start", "end")
    @classmethod
    def validate_iso_date(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        if not isinstance(value, str) or len(value) != 10 or value[4] != "-" or value[7] != "-":
            raise ValueError("日期必须使用 YYYY-MM-DD")
        try:
            return date.fromisoformat(value).isoformat()
        except (TypeError, ValueError):
            raise ValueError("日期必须使用 YYYY-MM-DD") from None

    @model_validator(mode="after")
    def validate_order(self) -> "TaskTemplateDateRange":
        if self.start and self.end and self.start > self.end:
            raise ValueError("日期范围起始时间不能晚于结束时间")
        return self


class TaskTemplateConfig(BaseModel):
    """仅包含可复用创建配置；动态任务信息和病例/人员身份一律禁止。"""

    model_config = ConfigDict(extra="forbid")

    scene: TaskScene
    rule_set_key: RuleSetKey
    date_range: Optional[TaskTemplateDateRange] = None
    department_filter: List[TaskTemplateDepartment] = Field(default_factory=list, max_length=100)
    sampling_method: SamplingMethod = SamplingMethod.ALL
    sampling_config: Dict[str, Any] = Field(default_factory=dict)
    assign_method: AssignMethod = AssignMethod.BY_RATIO
    assignee_config: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("department_filter")
    @classmethod
    def validate_departments(cls, value: List[str]) -> List[str]:
        if len(value) != len(set(value)):
            raise ValueError("科室筛选不得重复")
        return value

    @model_validator(mode="after")
    def validate_reusable_config(self) -> "TaskTemplateConfig":
        method = self.sampling_method
        allowed_sampling_keys = {
            SamplingMethod.ALL: {"case_scope"},
            SamplingMethod.COUNT: {"case_scope", "total", "by_department"},
            SamplingMethod.PERCENTAGE: {"case_scope", "percentage", "group_by"},
        }[method]
        unknown_sampling = sorted(set(self.sampling_config) - allowed_sampling_keys)
        if unknown_sampling:
            raise ValueError(f"抽样配置含不支持的字段：{', '.join(unknown_sampling)}")
        case_scope = self.sampling_config.get("case_scope")
        if self.scene == TaskScene.RUNNING:
            if case_scope != "active":
                raise ValueError("运行病历模板当前仅支持当前在院范围")
        elif self.scene == TaskScene.FINAL:
            # 终末口径 B：终末任务可选“期间出院”（未核验归档）；未选范围的历史配置保持兼容。
            if case_scope not in (None, "discharged"):
                raise ValueError("终末病历模板仅支持已出院范围")
        elif case_scope is not None:
            raise ValueError("当前场景不支持 case_scope")
        if method == SamplingMethod.COUNT:
            total = self.sampling_config.get("total")
            if isinstance(total, bool) or not isinstance(total, int) or not 1 <= total <= 10000:
                raise ValueError("抽样数量必须为 1 到 10000 的整数")
            if not isinstance(self.sampling_config.get("by_department", False), bool):
                raise ValueError("按科室抽样参数必须是布尔值")
        elif method == SamplingMethod.PERCENTAGE:
            percentage = self.sampling_config.get("percentage")
            if (
                isinstance(percentage, bool)
                or not isinstance(percentage, (int, float))
                or not 0 < percentage <= 100
            ):
                raise ValueError("抽样比例必须在 0 到 100 之间")
            if self.sampling_config.get("group_by") not in (None, "department"):
                raise ValueError("当前仅支持按科室分组")

        if self.assign_method not in {
            AssignMethod.BY_RATIO,
            AssignMethod.BY_ORIGINAL_REVIEWER,
            AssignMethod.BY_DEPARTMENT,
        }:
            raise ValueError("模板包含不可用的分配方式")
        unknown_assignee = sorted(set(self.assignee_config) - {"fallback"})
        if unknown_assignee:
            raise ValueError(f"分配配置含不支持的字段：{', '.join(unknown_assignee)}")
        fallback = self.assignee_config.get("fallback")
        if self.assign_method == AssignMethod.BY_ORIGINAL_REVIEWER:
            if fallback not in {"by_ratio", "reject"}:
                raise ValueError("按原质控员分配必须指定 fallback")
        elif self.assignee_config:
            raise ValueError("当前分配方式不支持 assignee_config")
        return self


class TaskTemplateCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: TaskTemplateName
    config: TaskTemplateConfig


class TaskTemplateUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(..., ge=1)
    name: Optional[TaskTemplateName] = None
    config: Optional[TaskTemplateConfig] = None

    @model_validator(mode="after")
    def require_change(self) -> "TaskTemplateUpdateRequest":
        if self.name is None and self.config is None:
            raise ValueError("没有需要更新的字段")
        return self


class TaskTemplateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    config: Optional[TaskTemplateConfig]
    usable: bool
    unavailable_reason: Optional[str] = None
    version: int
    created_at: datetime
    updated_at: datetime


class TaskTemplateListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: List[TaskTemplateResponse]
    max_templates: int


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


class TaskDraftConfigurationUpdateRequest(BaseModel):
    """完整替换尚未抽样的单次任务规划；任务身份和冻结规则不在接口内。"""

    model_config = ConfigDict(extra="forbid")

    configuration_version: int = Field(..., ge=1)
    task_name: TaskEditName
    deadline: Optional[TaskDeadline]
    date_range: Optional[TaskTemplateDateRange]
    department_filter: List[TaskTemplateDepartment] = Field(..., max_length=100)
    record_refs: List[TaskCaseRef] = Field(..., max_length=10000)
    sampling_method: SamplingMethod
    sampling_config: Dict[str, Any]
    assign_method: AssignMethod
    assignee_config: Dict[str, Any]

    @field_validator("deadline")
    @classmethod
    def validate_deadline(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        try:
            if len(value) == 10:
                return date.fromisoformat(value).isoformat()
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("截止时间必须是 ISO 日期或时间") from None
        if parsed.tzinfo is None:
            raise ValueError("截止时间包含时刻时必须携带时区")
        return parsed.isoformat()

    @field_validator("department_filter")
    @classmethod
    def validate_departments(cls, value: List[str]) -> List[str]:
        if len(value) != len(set(value)):
            raise ValueError("科室筛选不得重复")
        return value

    @model_validator(mode="after")
    def validate_scope(self) -> "TaskDraftConfigurationUpdateRequest":
        identities = [
            (item.institute_id, item.patient_id, item.visit_id)
            for item in self.record_refs
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("record_refs 不得包含重复病例三坐标")
        if self.record_refs and self.department_filter:
            raise ValueError("指定病历不得与科室筛选混用")
        if self.record_refs and self.date_range is not None and self.sampling_config.get("case_scope") != "discharged":
            raise ValueError("指定病历不得与日期范围混用，终末已出院范围除外")
        return self


class TaskMetadataUpdateRequest(BaseModel):
    """修改不改变任务范围或执行事实的名称、截止时间。"""

    model_config = ConfigDict(extra="forbid")

    configuration_version: int = Field(..., ge=1)
    task_name: Optional[TaskEditName] = None
    deadline: Optional[TaskDeadline] = None

    @field_validator("deadline")
    @classmethod
    def validate_deadline(cls, value: Optional[str]) -> Optional[str]:
        return TaskDraftConfigurationUpdateRequest.validate_deadline(value)

    @model_validator(mode="after")
    def require_change(self) -> "TaskMetadataUpdateRequest":
        if not ({"task_name", "deadline"} & self.model_fields_set):
            raise ValueError("没有需要更新的字段")
        if "task_name" in self.model_fields_set and self.task_name is None:
            raise ValueError("任务名称不能为空")
        return self


class TaskEditResponse(BaseModel):
    """任务编辑读取及写后回读的同一响应合同。"""

    model_config = ConfigDict(extra="forbid")

    id: str
    task_number: str
    task_name: str
    task_type: str
    status: str
    scene: Optional[TaskScene]
    rule_set_key: Optional[str]
    rule_set_version: Optional[str]
    deadline: Optional[str]
    date_range: Optional[Dict[str, Any]]
    department_filter: Optional[List[str]]
    record_refs: Optional[List[TaskCaseRef]]
    sampling_method: Optional[str]
    sampling_config: Optional[Dict[str, Any]]
    assign_method: Optional[str]
    assignee_config: Optional[Dict[str, Any]]
    configuration_version: int = Field(..., ge=1)
    editable_fields: List[str]
    updated_at: Optional[str]


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
    fallback: Optional[OriginalReviewerFallback] = Field(
        None, description="仅 by_original_reviewer 使用且必填：by_ratio | reject"
    )

    @model_validator(mode="after")
    def unique_assignees(self) -> "TaskAssignRequest":
        ids = [assignee.user_id for assignee in self.assignees]
        if len(ids) != len(set(ids)):
            raise ValueError("分配人员 user_id 不可重复")
        if self.method == AssignMethod.BY_ORIGINAL_REVIEWER:
            if self.fallback is None:
                raise ValueError("按原质控员分配须指定 fallback（by_ratio 或 reject）")
        elif self.fallback is not None:
            raise ValueError("fallback 仅适用于按原质控员分配")
        return self


class TaskBatchAssignTarget(BaseModel):
    """批量分配中的单个任务及其创建时分配策略。"""

    model_config = ConfigDict(extra="forbid")

    task_id: TaskId
    method: AssignMethod
    fallback: Optional[OriginalReviewerFallback] = None

    @model_validator(mode="after")
    def validate_fallback(self) -> "TaskBatchAssignTarget":
        if self.method == AssignMethod.BY_ORIGINAL_REVIEWER:
            if self.fallback is None:
                raise ValueError("按原质控员分配须指定 fallback（by_ratio 或 reject）")
        elif self.fallback is not None:
            raise ValueError("fallback 仅适用于按原质控员分配")
        return self


class TaskBatchAssignRequest(BaseModel):
    """最多二十个任务的显式逐项分配；每个任务保持独立事务。"""

    model_config = ConfigDict(extra="forbid")

    tasks: List[TaskBatchAssignTarget] = Field(..., min_length=1, max_length=20)
    assignees: List[TaskAssignee] = Field(..., min_length=1)

    @model_validator(mode="after")
    def unique_targets_and_assignees(self) -> "TaskBatchAssignRequest":
        task_ids = [target.task_id for target in self.tasks]
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("批量分配任务 ID 不可重复")
        assignee_ids = [assignee.user_id for assignee in self.assignees]
        if len(assignee_ids) != len(set(assignee_ids)):
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


class TaskManualDefectCreateRequest(BaseModel):
    """受领质控员基于已核实的本次任务运行补录缺陷。"""

    model_config = ConfigDict(extra="forbid")

    defect_id: UUID
    run_number: int = Field(..., strict=True, gt=0)
    rule_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    description: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
    severity: Literal["info", "warning", "error", "critical"]
    suggestion: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]] = None
    evidence: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]] = None


class TaskManualDefectResponse(BaseModel):
    """人工缺陷自身状态；不代表病历审核或整改状态。"""

    model_config = ConfigDict(extra="forbid")

    id: str
    task_id: str
    task_record_id: str
    run_number: int
    rule_name: str
    description: str
    severity: Literal["info", "warning", "error", "critical"]
    suggestion: Optional[str] = None
    evidence: Optional[str] = None
    manual_review_status: Literal["pending", "approved", "rejected"]
    created_at: datetime
    idempotent: Optional[bool] = None


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
