"""定时任务计划的严格请求与响应合同。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from .tasks import AssignMethod, SamplingMethod, TaskScene, TaskTemplateDepartment


ScheduleId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=36)]
ScheduleState = Literal["active", "paused", "ended", "cancelled"]
ScheduleRunStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]
ScheduleTriggerType = Literal["scheduled", "manual"]


class _TimingBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timezone: Literal["Asia/Shanghai"] = "Asia/Shanghai"


class TaskScheduleTimingOnce(_TimingBase):
    kind: Literal["once"]
    run_at: datetime

    @field_validator("run_at")
    @classmethod
    def require_shanghai_offset(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("单次执行时间必须包含时区")
        if value.utcoffset().total_seconds() != 8 * 60 * 60:
            raise ValueError("单次执行时间必须使用 Asia/Shanghai 时区")
        if value.second or value.microsecond:
            raise ValueError("单次执行时间仅支持精确到分钟")
        return value


class _RecurringTimingBase(_TimingBase):
    time: str
    start_date: date
    end_date: date | None = None

    @field_validator("time")
    @classmethod
    def validate_time(cls, value: str) -> str:
        if len(value) != 5 or value[2] != ":":
            raise ValueError("执行时间必须使用 HH:MM")
        try:
            hour, minute = (int(part) for part in value.split(":"))
        except (TypeError, ValueError):
            raise ValueError("执行时间必须使用 HH:MM") from None
        if not 0 <= hour <= 23 or not 0 <= minute <= 59:
            raise ValueError("执行时间必须使用 HH:MM")
        return f"{hour:02d}:{minute:02d}"

    @model_validator(mode="after")
    def validate_date_order(self) -> "_RecurringTimingBase":
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("结束日期不能早于开始日期")
        return self


class TaskScheduleTimingDaily(_RecurringTimingBase):
    kind: Literal["daily"]


class TaskScheduleTimingWeekly(_RecurringTimingBase):
    kind: Literal["weekly"]
    weekdays: list[int] = Field(..., min_length=1, max_length=7)

    @field_validator("weekdays")
    @classmethod
    def validate_weekdays(cls, value: list[int]) -> list[int]:
        if any(type(item) is not int or not 1 <= item <= 7 for item in value):
            raise ValueError("星期必须为 1 到 7 的整数")
        if value != sorted(set(value)):
            raise ValueError("星期必须升序且不得重复")
        return value


class TaskScheduleTimingMonthly(_RecurringTimingBase):
    kind: Literal["monthly"]
    day: int = Field(..., ge=1, le=31)


TaskScheduleTimingConfig = Annotated[
    Union[
        TaskScheduleTimingOnce,
        TaskScheduleTimingDaily,
        TaskScheduleTimingWeekly,
        TaskScheduleTimingMonthly,
    ],
    Field(discriminator="kind"),
]


class TaskScheduleCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_task_id: ScheduleId
    source_configuration_version: int = Field(..., ge=1)
    timing_config: TaskScheduleTimingConfig


class TaskScheduleActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(..., ge=1)


class TaskScheduleValidityRequest(TaskScheduleActionRequest):
    start_date: date
    end_date: date | None

    @model_validator(mode="after")
    def validate_date_order(self) -> "TaskScheduleValidityRequest":
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("结束日期不能早于开始日期")
        return self


class TaskScheduleTaskConfig(BaseModel):
    """从源草稿冻结的子任务创建配置；不包含动态病例或截止时间。"""

    model_config = ConfigDict(extra="forbid")

    date_range: None = None
    department_filter: list[TaskTemplateDepartment] = Field(default_factory=list, max_length=100)
    sampling_method: SamplingMethod
    sampling_config: dict
    assign_method: AssignMethod
    assignee_config: dict


class TaskScheduleResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    source_task_id: str
    owner_id: str
    name: str
    scene: TaskScene
    rule_set_key: str
    rule_set_version: str
    task_config: TaskScheduleTaskConfig
    timing_config: TaskScheduleTimingConfig
    state: ScheduleState
    next_fire_at: datetime | None
    last_fire_at: datetime | None
    version: int
    created_at: datetime
    updated_at: datetime


class TaskScheduleListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[TaskScheduleResponse]
    total: int
    page: int
    page_size: int


class TaskScheduleRunResponse(BaseModel):
    """succeeded 仅表示子任务抽样已持久化，不表示质控或分配完成。"""

    model_config = ConfigDict(extra="forbid")

    id: str
    schedule_id: str
    trigger_type: ScheduleTriggerType
    scheduled_fire_at: datetime
    idempotency_key: str
    status: ScheduleRunStatus
    generated_task_id: str | None
    async_job_id: str | None
    attempt_count: int
    heartbeat_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class TaskScheduleRunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[TaskScheduleRunResponse]
    total: int
    page: int
    page_size: int
