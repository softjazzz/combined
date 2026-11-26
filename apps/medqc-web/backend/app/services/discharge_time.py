"""新取材的出院业务时间选择；不读取数据库，不判定医学规则。"""
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from .validation_material_source import is_explicitly_invalid_document_status


HOSPITAL_TIMEZONE = ZoneInfo("Asia/Shanghai")
DISCHARGE_TIME_POLICY = "hospital-discharge-v1"


def hospital_business_time(value: Any) -> Any:
    """显式偏移归一到医院本地；无偏移沿用本地时刻，日期不补精度。"""
    if value is None or not str(value).strip():
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    text = str(value).strip()
    if len(text) == 10:
        return date.fromisoformat(text)
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(HOSPITAL_TIMEZONE).replace(tzinfo=None)
    return parsed


@dataclass(frozen=True)
class DischargeTime:
    value: Any = None
    source: str = ""
    conflict: bool = False


def select_discharge_time(*, registration=None, frontpage=None,
                          document_date=None, document_time=None, document_status=None,
                          death_time=None, death_status=None) -> DischargeTime:
    """登记 > 首页 > 出院文书 > 死亡文书；同一文书日期与精确时刻须同日。

    非空但无效的高优先级值不能被低优先级值掩盖；不取同步、打印或提交时间。
    """
    for source, raw in (("inpat_registration.discharge_datetime", registration),
                        ("mr.discharge_datetime", frontpage)):
        if raw is not None and str(raw).strip():
            try:
                return DischargeTime(hospital_business_time(raw), source)
            except (TypeError, ValueError, OverflowError):
                return DischargeTime(raw, source, True)
    source = "discharge_record.discharge_time"
    if is_explicitly_invalid_document_status(document_status):
        # 新任务不能冻结作废文书的终点；保留候选值仅供来源冲突说明。
        return DischargeTime(document_time or document_date, source, True)
    try:
        precise = hospital_business_time(document_time)
        day = hospital_business_time(document_date)
        if day is not None and precise is not None:
            day_date = day.date() if isinstance(day, datetime) else day
            precise_date = precise.date() if isinstance(precise, datetime) else precise
            if day_date != precise_date:
                return DischargeTime(day, source, True)
        if precise is not None:
            return DischargeTime(precise, source)
        if day is not None:
            return DischargeTime(day, "discharge_record.discharge_date")
    except (TypeError, ValueError, OverflowError):
        return DischargeTime(document_time or document_date, source, True)
    if death_time is not None and str(death_time).strip():
        death_source = "death_record.death_datetime"
        if is_explicitly_invalid_document_status(death_status):
            return DischargeTime(death_time, death_source, True)
        try:
            return DischargeTime(hospital_business_time(death_time), death_source)
        except (TypeError, ValueError, OverflowError):
            return DischargeTime(death_time, death_source, True)
    return DischargeTime()
