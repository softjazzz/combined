"""保存来源缺口的窄安全投影；不重判数据采集、同步或医生书写。"""

from collections.abc import Mapping


# 尚无统一来源/字段枚举，只支持已核实的规范代码与标签，不接受任意标识符。
SOURCE_LABELS = {
    "daily_course_record": "病程记录",
    "bloodtrans_record": "输血记录",
    "surgery_record": "手术记录",
    "anesthesia_record": "麻醉记录",
    "postsurg_firstcourse_record": "术后首次病程记录",
    "检验结果明细": "检验结果明细",
    "质控所需数据源": "质控所需数据源",
    "质控所需资料": "质控所需资料",
    "超出读取范围的后续资料": "超出读取范围的后续资料",
    "需要相互核对的事件与文书": "需要相互核对的事件与文书",
    "对应的正式检查检验报告": "对应的正式检查检验报告",
    "判断质控点是否适用的关键资料": "判断质控点是否适用的关键资料",
}
FIELD_LABELS = {
    "report_time": "报告时间",
    "危急值标志": "危急值标志",
    "有效出院时间": "有效出院时间",
    "完成判定所需的关键字段": "完成判定所需的关键字段",
    "用于计算质控时限的权威时间": "用于计算质控时限的权威时间",
    "检查检验报告的权威报告时间": "检查检验报告的权威报告时间",
    "相互一致的报告时间与评价截止时间": "相互一致的报告时间与评价截止时间",
}
REASON_CODES = frozenset({
    "required_source_unavailable", "required_field_missing", "source_unavailable",
    "source_empty", "source_truncated", "source_readiness_unproven", "association_failed",
    "linkage_unresolved", "authoritative_time_missing", "target_report_missing",
    "authoritative_report_time_missing", "authoritative_time_conflict",
    "evaluation_window_not_mature", "applicability_source_gap",
})
AVAILABILITY_LABELS = {"unavailable": "不可用"}

_LIMIT = (
    "仅展示已保存且已核实代码的来源缺口，不读取文书正文；"
    "空列表或未提供字段不证明来源齐全，不能据此判断同步成功、同步失败或医生漏写。"
)
_OMITTED = "部分保存缺口信息不属于已核实的安全代码，未纳入本次投影。"


def project_saved_source_gaps(saved: Mapping) -> dict:
    """仅搬运受控保存字段；缺键不补值，未知自由文本与嵌套字段不透传。"""
    result = {}
    omitted = False
    if "reason_code" in saved:
        value = saved["reason_code"]
        if isinstance(value, str) and value in REASON_CODES:
            result["reason_code"] = value
        else:
            omitted = True
    for key, allowed in (("missing_sources", SOURCE_LABELS), ("missing_fields", FIELD_LABELS)):
        if key not in saved:
            continue
        value = saved[key]
        if not isinstance(value, list):
            omitted = True
            continue
        result[key] = [item for item in value if isinstance(item, str) and item in allowed]
        omitted |= len(result[key]) != len(value)
        if value and not result[key]:
            del result[key]
    if "source_availability" in saved:
        value = saved["source_availability"]
        if isinstance(value, Mapping):
            result["source_availability"] = {
                key: state for key, state in value.items()
                if key in SOURCE_LABELS and isinstance(state, str) and state in AVAILABILITY_LABELS
            }
            omitted |= len(result["source_availability"]) != len(value)
            if value and not result["source_availability"]:
                del result["source_availability"]
        else:
            omitted = True
    if "data_gap_details" in saved:
        value = saved["data_gap_details"]
        if isinstance(value, Mapping):
            result["data_gap_details"] = {}
            state = value.get("availability")
            if isinstance(state, str) and state in AVAILABILITY_LABELS:
                result["data_gap_details"]["availability"] = state
            omitted |= len(result["data_gap_details"]) != len(value)
            if value and not result["data_gap_details"]:
                del result["data_gap_details"]
        else:
            omitted = True
    result["projection_notes"] = [_LIMIT, *([_OMITTED] if omitted else [])]
    return result


def source_gaps_card_text(saved: Mapping) -> str:
    """短来源卡只使用安全投影及固定中文标签，不能拼接原始文本。"""
    gaps = project_saved_source_gaps(saved)
    lines = ["保存来源缺口信息（本次未重判）"]
    if gaps.get("missing_sources"):
        lines.append("保存标记的缺口来源：" + "、".join(SOURCE_LABELS[item] for item in gaps["missing_sources"]))
    if gaps.get("missing_fields"):
        lines.append("保存标记的缺口字段：" + "、".join(FIELD_LABELS[item] for item in gaps["missing_fields"]))
    for source, state in gaps.get("source_availability", {}).items():
        lines.append(f"保存的来源可用性：{SOURCE_LABELS[source]}，{AVAILABILITY_LABELS[state]}")
    state = gaps.get("data_gap_details", {}).get("availability")
    if state:
        lines.append("保存的缺口可用性：" + AVAILABILITY_LABELS[state])
    if len(lines) == 1:
        lines.append("本次未取得可展示的受控来源或字段代码，无法确认具体缺口。")
    return "\n".join([*lines, *gaps["projection_notes"]])
