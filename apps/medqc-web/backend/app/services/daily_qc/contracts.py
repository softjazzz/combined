"""计划参数、明确时区和稳定逐日身份。"""

from datetime import date, datetime, time, timedelta, timezone
from typing import Literal
from uuid import UUID, uuid5, NAMESPACE_URL
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PlanInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    enabled: bool = False
    time_of_day: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    timezone: str = "Asia/Shanghai"
    institute_id: str = Field(min_length=1, max_length=128)
    scope: Literal["running", "final"] = "final"
    department: str = Field(default="", max_length=100)
    date_field: Literal["admission", "discharge"] = "discharge"
    lookback_days: int = Field(default=1, ge=1, le=365)
    end_offset_days: int = Field(default=1, ge=0, le=365)
    rule_set_key: str = Field(min_length=1, max_length=100)
    rule_ids: list[str] = Field(default_factory=list, max_length=200)
    max_records: int = Field(default=200, ge=1, le=1000)

    @field_validator("name", "institute_id", "rule_set_key")
    @classmethod
    def nonblank(cls, value):
        if value != value.strip() or not value.strip():
            raise ValueError("名称与身份不可为空或含首尾空白")
        return value

    @field_validator("timezone")
    @classmethod
    def known_timezone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("请选择有效的IANA时区") from None
        return value


def utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("调度时间必须含时区")
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def occurrence(day: date, hhmm: str, timezone_name: str) -> datetime:
    zone = ZoneInfo(timezone_name)
    nominal = datetime.combine(day, time.fromisoformat(hhmm))
    # DST回拨取首次发生；跳时取该日第一个有效分钟，不重复执行同一当地日期。
    for minutes in range(181):
        candidate = (nominal + timedelta(minutes=minutes)).replace(tzinfo=zone, fold=0)
        normalized = candidate.astimezone(timezone.utc).astimezone(zone)
        if normalized.replace(tzinfo=None) == candidate.replace(tzinfo=None):
            return utc_naive(candidate)
    raise ValueError("该日计划时间无法解析")


def next_occurrence(now: datetime, plan: dict) -> datetime:
    current = utc_naive(now)
    day = now.astimezone(ZoneInfo(plan["timezone"])).date()
    result = occurrence(day, plan["time_of_day"], plan["timezone"])
    return (
        result
        if result > current
        else occurrence(day + timedelta(days=1), plan["time_of_day"], plan["timezone"])
    )


def run_identity(plan_id: str, local_date: str) -> str:
    return str(
        uuid5(
            NAMESPACE_URL,
            f"medqc:daily-qc:{UUID(plan_id)}:{date.fromisoformat(local_date)}",
        )
    )


def job_identity(run_id: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"medqc:daily-qc-job:{UUID(run_id)}"))


def date_window(local_day: date, plan: dict) -> tuple[str, str]:
    end = local_day - timedelta(days=plan["end_offset_days"])
    return (
        end - timedelta(days=plan["lookback_days"] - 1)
    ).isoformat(), end.isoformat()
