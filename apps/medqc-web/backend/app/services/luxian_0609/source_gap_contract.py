"""LX0609 资料观测到受控缺口语义的唯一映射。

本模块不读取资料、不产生医学结论，只把既有 ``SourceObservation`` 的
查询状态转换为 Decision 层允许消费的缺口原因，并提供客户可懂的固定文案。
"""

from __future__ import annotations

from dataclasses import dataclass

from .evidence_snapshot import SourceCompleteness, SourceObservation
from .source_manifest import QueryStatus


@dataclass(frozen=True)
class CustomerGapMessage:
    findings: str
    evidence: str
    suggestion: str


CUSTOMER_GAP_MESSAGES = {
    "source_unavailable": CustomerGapMessage(
        "当前系统尚未接入核对所需的资料",
        "本次质控无法读取完成该项核对所需的数据来源。",
        "请确认相关数据源已接入并完成同步后重新评估。",
    ),
    "source_empty": CustomerGapMessage(
        "当前病历中未同步到核对所需的记录",
        "数据来源可以正常读取，但本次病历未返回所需记录。",
        "请确认该记录是否已产生并已同步后重新评估。",
    ),
    "source_truncated": CustomerGapMessage(
        "当前资料内容不完整，暂时无法完成核对",
        "本次只读取到部分相关资料，不能据此形成确定结论。",
        "请确认完整资料已同步后重新评估。",
    ),
    "required_field_missing": CustomerGapMessage(
        "当前记录缺少完成核对所需的关键信息",
        "已读取到相关记录，但其中缺少本项判断所需的字段。",
        "请核对相关记录内容是否填写并同步完整。",
    ),
    "authoritative_time_missing": CustomerGapMessage(
        "当前记录缺少可用于计算时限的明确时间",
        "已读取到相关记录，但缺少可靠的起始、完成或报告时间。",
        "请核对相关记录时间是否填写并同步完整。",
    ),
    "association_failed": CustomerGapMessage(
        "已找到相关资料，但暂时无法确认属于同一次诊疗事件",
        "现有资料缺少可用于相互对应的事件标识、时间或对象信息。",
        "请核对相关记录的事件标识和时间后重新评估。",
    ),
}


def source_observation_reason(observation: SourceObservation) -> str | None:
    """将来源观测归一为缺口原因；查询错误保持为技术异常。"""

    if not isinstance(observation, SourceObservation):
        raise TypeError("observation must be SourceObservation")
    if observation.query_state is QueryStatus.ERROR:
        return "source_query_error"
    if observation.query_state is QueryStatus.UNAVAILABLE:
        return "source_unavailable"
    if observation.query_state is QueryStatus.EMPTY:
        return "source_empty"
    if observation.completeness is SourceCompleteness.TRUNCATED:
        return "source_truncated"
    return None


def _normalize_missing_items(missing_items: tuple[str, ...]) -> tuple[str, ...]:
    if not isinstance(missing_items, tuple):
        raise TypeError("missing_items must be tuple")
    normalized = tuple(dict.fromkeys(item.strip() for item in missing_items))
    if any(
        not item
        or len(item) > 40
        or any(ord(char) < 32 for char in item)
        for item in normalized
    ):
        raise ValueError("invalid missing item")
    return normalized


def customer_gap_message(
    reason_code: str,
    *,
    missing_items: tuple[str, ...] = (),
) -> CustomerGapMessage | None:
    """返回受控客户文案；未知原因不得在这里被猜测或改写。"""

    if not isinstance(reason_code, str):
        raise TypeError("reason_code must be str")
    message = CUSTOMER_GAP_MESSAGES.get(reason_code)
    if message is None or not missing_items:
        return message
    items = _normalize_missing_items(missing_items)
    item_text = "、".join(items)
    evidence_by_reason = {
        "source_unavailable": f"本次质控无法读取{item_text}所在的数据来源。",
        "source_empty": f"数据来源可以正常读取，但本次病历未返回{item_text}。",
        "source_truncated": f"本次只读取到部分相关资料，无法确认{item_text}是否完整。",
        "required_field_missing": f"已读取到相关记录，但其中缺少{item_text}。",
        "authoritative_time_missing": f"当前缺少{item_text}，无法计算质控时限。",
        "association_failed": f"已找到相关资料，但缺少能够确认{item_text}属于同一次诊疗事件的关联信息。",
    }
    return CustomerGapMessage(
        findings=f"当前缺少{item_text}，暂时无法完成核对",
        evidence=evidence_by_reason[reason_code],
        suggestion=message.suggestion,
    )


__all__ = [
    "CUSTOMER_GAP_MESSAGES",
    "CustomerGapMessage",
    "customer_gap_message",
    "source_observation_reason",
]
