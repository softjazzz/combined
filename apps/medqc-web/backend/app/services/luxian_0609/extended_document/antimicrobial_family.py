"""LX0609 抗菌药规则族（05-01-02..06 / 05-03-01）独立执行器。

由 `native_extended_document_execution.py` 拆出（Batch 4 · Family #2）：
- 拥有抗菌药启用/停用理由、48–72h 疗效评估、病原学送检依据、特殊级抗菌药专家
  会诊授权与围术期预防用药相关正则、辅助判定、组内共享缓存（`order_reason_cache`）
  与模型 token/调用统计；
- 仅读取抗菌药规则族自身所需来源（通过共享 `SourceRowsCache` 避免组内重复复制），
  不反向依赖 `native_extended_document_execution.py`。
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
import re
from typing import Any, Mapping, Sequence

from ..decision_model import RuleDecision
from ..evaluation_horizon import after_frozen_horizon, frozen_window_is_mature
from ..evidence_material import (
    EvidenceMaterialTruncated,
    EvidenceMaterialUnavailable,
    Luxian0609EvidenceMaterialStore,
)
from ..evidence_snapshot import Luxian0609EvidenceSnapshot
from ..key_antimicrobial_catalog import key_antimicrobials_in_order
from ..prophylactic_antimicrobial_duration import is_local_route_drug_order
from ..source_evidence_reader import authoritative_document_time_value
from .antimicrobial_action_extraction import (
    SPECIAL_ANTIMICROBIALS as _SPECIAL_ANTIMICROBIALS,
    AntimicrobialOrderEvent as _AntimicrobialOrderEvent,
    antimicrobial_names_in as _antimicrobial_names_in,
    antimicrobial_names_in_rows as _antimicrobial_names_in_rows,
    linked_order_id as _linked_order_id,
)
from .antimicrobial_effect_extraction import (
    extract_antimicrobial_effect_pairs,
    extract_antimicrobial_effects,
)
from .antimicrobial_order_reason import (
    WindowDocument,
    derive_antimicrobial_use_events,
    extract_antimicrobial_reasons,
    extract_special_antimicrobial_approvals,
    is_excluded_antimicrobial_order,
    is_planned_stop,
    order_start_time,
    planned_duration,
    window_documents,
)
from .family_runtime import (
    ExtendedDocumentFamilyOutcome,
    SourceRowsCache,
    build_extended_decision as _decision,
    discharge_time as _discharge_time,
    fact_refs as _fact_refs,
    has_any_text as _has_any_text,
    material_text as _material_text,
    parse_hospital_datetime as _parse_lx0609_058_datetime,
    precise_datetime as _precise_datetime,
    resolve_evaluation_horizon as _resolve_evaluation_horizon,
    resolve_horizon_rows,
    source_rows as _source_rows,
)
from .shared import _clean, _parse_datetime, _row_time, row_time_upper_bound

ANTIMICROBIAL_RULE_IDS = (
    "LX0609-05-01-02",
    "LX0609-05-01-03",
    "LX0609-05-01-04",
    "LX0609-05-01-05",
    "LX0609-05-01-06",
    "LX0609-05-03-01",
)
_ANTIMICROBIAL_HORIZON_RULES = frozenset({
    "LX0609-05-01-02",
    "LX0609-05-01-03",
    "LX0609-05-01-05",
    "LX0609-05-01-06",
})
_ANTIMICROBIAL_REASON_RULES = frozenset({
    "LX0609-05-01-02",
    "LX0609-05-01-05",
})

# 058（05-01-06）业务基线：紧急越级使用特殊级抗菌药须在 24 小时内补办专家会诊/查房。
# 用户口径（2026-10-17）：启用前或启用后 24 小时内有可关联的专家支持即合规，指征不单独核对。
_LX0609_058_SUPPORT_WINDOW = timedelta(hours=24)

_SPECIAL_ANTIMICROBIAL_EXPERT_SUPPORT_MARKERS = (
    "感染专家", "专家会诊", "专家查房",
)
# 感染科副主任医师及以上的会诊署名（用户口径 2026-10-17：主治医师、临床药师不算授权专家）。
# 兼容“感染性疾病科”、署名括号、“副主任/主任”简写、署名后直接接“会诊/意见/指出/建议/查房/冒号/逗号”等写法；
# 科室与职称之间不得出现其他科室或药师/药学字样，且职称后不得紧跟“药师/药学”（排除副主任药师/主任药师）。
_SPECIAL_ANTIMICROBIAL_INFECTION_EXPERT_PATTERN = re.compile(
    r"感染(?:性疾病)?科(?:(?!药师|药学)[^。；;\n科]){0,24}?"
    r"(?:副主任(?:医师)?|主任(?:医师)?)(?!药师|药学)"
    r"[\]】）)]?\s*(?:会诊|意见|指出|建议|查房|[:：,，])"
)
# 医院电子《请会诊执行记录》常写作“感染性疾病科[姓名],2026-04-07,09:59:00病史敬悉同意使用”
# 而省略职称字样；仅在带有时间戳电子会诊落款（且非明确初级/主治/药师职称）时认定为感染科专项会诊。
_SPECIAL_ANTIMICROBIAL_INFECTION_ECONSULT_PATTERN = re.compile(
    r"感染(?:性疾病)?科"
    r"(?![^,\s，\r\n。；;]{0,16}(?:主治医师|住院医师|实习医师|规培医师|药师|药学))"
    r"[\s:：,，(（\[]*(?![\u4e00-\u9fff]{0,2}(?:药师|药学))[\u4e00-\u9fff]{2,4}[\]）)]?"
    r"(?!\s*(?:主治医师|住院医师|实习医师|规培医师|药师|药学))"
    r"\s*[,，\s]+\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?\s*[,，\sT]*\d{1,2}[:：]\d{2}"
)
# 重症医学科(ICU)主任/副主任医师行抗生素/抗菌药物使用权限专项会诊。
_SPECIAL_ANTIMICROBIAL_ICU_EXPERT_PATTERN = re.compile(
    r"(?:ICU|重症医学科)(?:(?!药师|药学)[^。；;\n科]){0,20}?(?:副主任医师|主任医师)"
    r"[\]】）)]?[^。；;\n]{0,20}?(?:抗生素|抗菌药(?:物)?|特殊级)[^。；;\n]{0,12}?会诊"
)
# 医院电子特殊级抗菌药用药申请会诊单（常无 document_title，以“本病人建议使用…使用目的为…”起头）
# 紧接高级职称医师（主任/副主任医师，排除明确他科或初级/主治/药师）会诊意见。
_SPECIAL_ANTIMICROBIAL_REQUEST_SENIOR_APPROVAL_PATTERN = re.compile(
    r"本病人建议使用[^。；;\n]{0,80}?使用目的为[^。\n]{0,120}?[。；;\n,，]\s*"
    r"(?!(?:呼吸|心血管|消化|神经|普外|胸外|泌尿|骨|妇产|儿|耳鼻喉|眼|皮肤|肾内|内分泌|肿瘤|血液|临床药学|药学|药剂)[^。；;\n]{0,8}?(?:科|学|部))"
    r"(?P<speaker>[\u4e00-\u9fff]{2,4}(?:副主任医师|主任医师)[\]】）)]?\s*(?:会诊(?:意见)?|意见|[:：]))"
)
# 正式《请会诊执行记录》中邀请感染科或重症医学科/ICU医师协助诊治（省略打印职称但非主治/住院/规培/实习医师/药师）。
_SPECIAL_ANTIMICROBIAL_INVITED_EXPERT_CONSULT_PATTERN = re.compile(
    r"(?:故)?邀请\s*(?:感染(?:性疾病)?科|重症医学科|ICU)"
    r"(?![^\r\n。；;：:]{0,16}(?:主治医师|住院医师|实习医师|规培医师|药师|药学))"
    r"[\u4e00-\u9fff]{2,4}(?:医生|医师)?\s*(?:协助诊治|会诊(?:意见)?)\s*[:：]"
)
_SPECIAL_ANTIMICROBIAL_NON_AUTHORIZED_SPEAKER_PATTERN = re.compile(
    r"本病人建议使用|"
    r"(?<!请)(?<!请临床)(?<!请主管)(?<!请主任)(?<!请副主任)(?:(?:临床|主管|副主任|主任)?药师)|"
    r"临床药师(?:[^。；;\r\n后]{0,8}?[：:])|临床药师(?:会诊)?意见|"
    r"临床药学(?:(?:会诊)?意见|会诊\s*[：:]|[：:])|"
    r"药学部|"
    r"主治医师|住院医师|实习医师|规培医师|经治医师|管床医师|申请医师|"
    r"(?:\r?\n)\s*[^\r\n]{0,20}(?:药师|药学|主治|住院|规培|实习|经治|管床|申请|医师|医生|科)[^\r\n]{0,10}[：:]|"
    r"[。；;]\s*(?!(?:感染(?:性疾病)?科|重症医学科|ICU))[^\r\n。；;]{0,20}"
    r"(?:呼吸|心血管|消化|神经|普外|胸外|泌尿|骨|妇产|儿|耳鼻喉|眼|皮肤|肾内|内分泌|肿瘤|血液|药学|药剂)"
    r"[^\r\n。；;]{0,12}(?:科|部|学)[^\r\n。；;]{0,10}[：:]"
)
_SPECIAL_ANTIMICROBIAL_GOVERNING_NON_AUTH_PATTERN = re.compile(
    _SPECIAL_ANTIMICROBIAL_NON_AUTHORIZED_SPEAKER_PATTERN.pattern
    + r"|^\s*(?!(?:感染(?:性疾病)?科|重症医学科|ICU))[^\r\n。；;]{0,20}"
    r"(?:呼吸|心血管|消化|神经|普外|胸外|泌尿|骨|妇产|儿|耳鼻喉|眼|皮肤|肾内|内分泌|肿瘤|血液|药学|药剂)"
    r"[^\r\n。；;]{0,12}(?:科|部|学)[^\r\n。；;]{0,10}[：:]"
)
_LAB_ORDER_CLASS_VALUES = frozenset({"检验", "检验类", "化验"})
_LAB_ORDER_CANCELLED_STATUSES = ("取消", "作废", "撤销", "未执行")
_LAB_ORDER_NAME_PATTERN = re.compile(
    r"培养|药敏|病原|涂片|血常规|尿常规|尿液分析|血气分析|降钙素原|G试验|GM试验|真菌|细菌|微生物"
    r"|(?:病毒|细菌|真菌|支原体|衣原体|结核|HBV|HCV|HIV).{0,20}(?:核酸|DNA|RNA)",
    re.IGNORECASE,
)


def _antimicrobial_effect_window_state(
    *,
    start_time: datetime,
    horizon_date: date | None,
    horizon_time: datetime | None,
) -> tuple[str, float | None, Mapping[str, Any]]:
    """按单次抗菌药启用事件判断 055 的 48～72 小时观察窗口。

    日期粒度的冻结终点不能断言当天已经跨过具体时刻，故仅在截止日后
    才进入成熟状态；这与现有检查检验时间窗的保守口径一致。
    """

    window_start = start_time + timedelta(hours=48)
    window_end = start_time + timedelta(hours=72)
    facts: dict[str, Any] = {
        "start_time": start_time.isoformat(sep=" "),
        "window_start_time": window_start.isoformat(sep=" "),
        "window_end_time": window_end.isoformat(sep=" "),
    }
    if horizon_time is not None:
        facts["evaluation_time"] = horizon_time.isoformat(sep=" ")
        elapsed_hours = (horizon_time - start_time).total_seconds() / 3600
        facts["elapsed_hours"] = round(elapsed_hours, 2)
        if elapsed_hours < 0:
            return "conflict", elapsed_hours, facts
        if elapsed_hours < 48:
            return "not_started", elapsed_hours, facts
        if elapsed_hours < 72:
            return "not_mature", elapsed_hours, facts
        return "mature", elapsed_hours, facts
    if horizon_date is None:
        return "missing", None, facts
    facts["evaluation_date"] = horizon_date.isoformat()
    if horizon_date < start_time.date():
        return "conflict", None, facts
    if horizon_date < window_start.date():
        return "not_started", None, facts
    if horizon_date > window_end.date():
        return "mature", None, facts
    return "not_mature", None, facts


def _antimicrobial_orders(rows: Sequence[Mapping[str, Any]]) -> tuple[Mapping[str, Any], ...]:
    # 用户口径（2026-10-22）：滴眼、外用、冲洗等局部用药不算抗菌药使用。
    return tuple(row for row in rows if _antimicrobial_names_in(row) and not is_local_route_drug_order(row))


def _has_performed_antimicrobial_administration(
    text: str, names: Sequence[str],
) -> bool:
    """取消与已实施冲突时保留事件；计划、否定和历史给药不是本次实施。"""

    target = "|".join(re.escape(name) for name in names)
    action = re.compile(
        r"已给予|已使用|已启用|已输注|实际给予|实际使用"
        + (rf"|(?:已予以|予以|已予|给予|(?<![给不未])予)(?=\s*(?:{target}))" if target else "")
    )
    for clause in re.split(r"[，,。；;！!？?\n]", text):
        for match in action.finditer(clause):
            prefix = clause[:match.start()]
            if re.search(
                r"(?:未|未曾|未能|不|并非|否认)\s*$"
                r"|(?:考虑|需|应|将|待)\s*$"
                r"|拟|计划|建议|准备|尚待|等待|需待|是否|若|如果"
                r"|既往|曾经|曾用|院外|外院|入院前|用药史",
                prefix,
            ):
                continue
            following = clause[match.end():]
            following_names = _antimicrobial_names_in({"record_content": following})
            if following_names:
                nearest = min(following_names, key=following.index)
                if nearest not in names:
                    continue
            else:
                preceding_names = _antimicrobial_names_in({"record_content": prefix})
                if preceding_names and max(preceding_names, key=prefix.rindex) not in names:
                    continue
            return True
    return False


def _exclude_unperformed_antimicrobial_orders(
    orders: Sequence[Mapping[str, Any]],
    course_rows: Sequence[Mapping[str, Any]],
) -> tuple[tuple[Mapping[str, Any], ...], tuple[Mapping[str, Any], ...]]:
    """仅排除明确未实施事件；停用不等于从未给药，同名多医嘱不猜归属。"""

    kept: list[Mapping[str, Any]] = []
    excluded_evidence: list[Mapping[str, Any]] = []
    for order in orders:
        names = _antimicrobial_names_in(order)
        order_id = _linked_order_id(order)
        linked_rows = []
        for row in course_rows:
            row_id = _linked_order_id(row)
            row_names = _antimicrobial_names_in(row)
            if row_id:
                matches = bool(order_id and row_id == order_id)
            else:
                matches = bool(
                    len(names) == 1 and row_names == names
                    and sum(names[0] in _antimicrobial_names_in(item) for item in orders) == 1
                )
            if matches:
                linked_rows.append(row)
        texts = tuple(_material_text(row) for row in (order, *linked_rows))
        # 明确已实施与取消信息冲突时，不把已用药事件静默删去。
        performed = any(
            _has_performed_antimicrobial_administration(text, names)
            for text in texts
        )
        unperformed_rows = tuple(
            row for row in (order, *linked_rows)
            if re.search(r"(?:未实际给药|未实际使用|从未给药|未曾给药)", _material_text(row))
        )
        cancelled = _clean(order.get("order_status")) in {
            "取消", "已取消", "作废", "已作废", "撤销", "未执行",
        }
        cancelled = cancelled or any(_clean(order.get(field)) for field in ("canceled_datetime", "cancel_datetime", "cancel_time", "revoke_time"))
        if not performed and (cancelled or unperformed_rows):
            excluded_evidence.extend((order, *unperformed_rows))
        else:
            kept.append(order)
    return tuple(kept), tuple(excluded_evidence)


def _055_treatment_orders(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], ...]:
    """055 只为实际抗菌治疗建窗；皮试医嘱不是治疗起点。"""

    return tuple(
        row for row in rows
        if _clean(row.get("drug_apply_method")) != "皮试"
    )



def _lx0609_058_row_time(row: Mapping[str, Any]) -> datetime | None:
    value = authoritative_document_time_value(row)
    return _parse_lx0609_058_datetime(
        value
        or row.get("death_datetime")
        or row.get("death_time")
        or row.get("discharge_datetime")
        or row.get("discharge_time")
    )


def _has_authorized_special_antimicrobial_expert(text: str) -> bool:
    """结构识别授权专家会诊/查房（感染科副高及以上、电子感染科会诊落款、ICU高年资抗菌药权限会诊、
    电子用药申请单副高及以上会诊意见、正式《请会诊执行记录》邀请感染科/ICU医师会诊）。"""

    return bool(
        _SPECIAL_ANTIMICROBIAL_INFECTION_EXPERT_PATTERN.search(text)
        or _SPECIAL_ANTIMICROBIAL_INFECTION_ECONSULT_PATTERN.search(text)
        or _SPECIAL_ANTIMICROBIAL_ICU_EXPERT_PATTERN.search(text)
        or _SPECIAL_ANTIMICROBIAL_REQUEST_SENIOR_APPROVAL_PATTERN.search(text)
        or (
            "请会诊执行记录" in text
            and _SPECIAL_ANTIMICROBIAL_INVITED_EXPERT_CONSULT_PATTERN.search(text)
        )
        or any(marker in text for marker in _SPECIAL_ANTIMICROBIAL_EXPERT_SUPPORT_MARKERS)
    )


def _authorized_special_antimicrobial_header_spans(
    text: str,
    *,
    window_start: int,
    quote_end: int,
) -> tuple[tuple[int, int], ...]:
    """返回窗口内所有真实授权专家发言人落款区间（不含“同意特殊级”等非身份短语）。"""

    scan_start = max(0, window_start - 160)
    segment = text[scan_start:quote_end]
    spans: list[tuple[int, int]] = []

    def _extend_header_tail(abs_end: int) -> int:
        tail_match = re.match(
            r"(?:会诊|意见|指出|建议|查房){0,2}\s*[:：]?",
            text[abs_end:quote_end],
        )
        if tail_match:
            return abs_end + tail_match.end()
        return abs_end

    for pattern in (
        _SPECIAL_ANTIMICROBIAL_INFECTION_EXPERT_PATTERN,
        _SPECIAL_ANTIMICROBIAL_INFECTION_ECONSULT_PATTERN,
        _SPECIAL_ANTIMICROBIAL_ICU_EXPERT_PATTERN,
    ):
        for match in pattern.finditer(segment):
            spans.append(
                (scan_start + match.start(), _extend_header_tail(scan_start + match.end()))
            )
    for match in _SPECIAL_ANTIMICROBIAL_REQUEST_SENIOR_APPROVAL_PATTERN.finditer(text[:quote_end]):
        spans.append((match.start("speaker"), _extend_header_tail(match.end())))
    if "请会诊执行记录" in text:
        for match in _SPECIAL_ANTIMICROBIAL_INVITED_EXPERT_CONSULT_PATTERN.finditer(text[:quote_end]):
            spans.append((match.start(), _extend_header_tail(match.end())))
    return tuple(spans)


def _is_governed_by_non_authorized_speaker(
    text: str,
    position: int,
    quote_end: int,
) -> bool:
    """检查引文之前的直接支配发言人是否为非授权人员（如临床药师/药师/主治/住院/他科医师）。

    若在引文前 600 字内（同段，至多回溯到空行 \\n\\n）存在非授权发言人落款，
    且在该非授权发言人与引文起点之间（含引文起点自身携带的授权专家落款）未再出现新的授权专家落款，
    则该引文归属非授权发言人，任何分支均不得放行。
    """

    window_start = max(0, position - 600)
    para_break = text.rfind("\n\n", window_start, position)
    if para_break >= 0:
        window_start = para_break + 2
    preceding = text[window_start:position]
    if not preceding:
        return False

    auth_spans = _authorized_special_antimicrobial_header_spans(
        text,
        window_start=window_start,
        quote_end=quote_end,
    )
    for match in _SPECIAL_ANTIMICROBIAL_GOVERNING_NON_AUTH_PATTERN.finditer(preceding):
        na_start = window_start + match.start()
        na_end = window_start + match.end()
        # 通用换行落款分支会同时命中“\n感染科副主任医师会诊意见：”本身；若该区间即被授权专家落款覆盖则跳过。
        if any(
            na_start <= a_start < na_end
            and "\n" not in text[a_end:na_end]
            and not _SPECIAL_ANTIMICROBIAL_NON_AUTHORIZED_SPEAKER_PATTERN.search(text[a_end:na_end])
            for a_start, a_end in auth_spans
        ):
            continue
        # 若该非授权发言人之后、且不晚于引文起点（允许引文以授权专家落款起头）出现新授权专家落款，则已切换回授权专家。
        superseded_by_auth = any(
            na_end <= a_start <= position and a_end <= quote_end
            for a_start, a_end in auth_spans
        )
        if not superseded_by_auth:
            return True
    return False


def _special_approval_by_authorized_expert(text: str, quote: str) -> bool:
    """同意引文本身或其紧邻前文须出现授权专家身份，不能借同文书其他段落或非授权发言人的意见。"""

    if "本病人建议使用" in quote:
        return False
    position = text.find(quote)
    if position < 0:
        return False
    quote_end = position + len(quote)
    # 无论引文本身是否含“同意特殊级”等支持短语，只要紧邻前文的直接支配发言人为非授权人员，立即拒绝。
    if _is_governed_by_non_authorized_speaker(text, position, quote_end):
        return False
    prefix_text = text[:quote_end]

    def _span_has_no_speaker_switch(header_start: int, header_end: int, *, allow_prefix_before_header: bool) -> bool:
        if header_end > quote_end:
            return False
        if header_start > position:
            if not allow_prefix_before_header:
                return False
            prefix_in_quote = text[position:header_start]
            if (
                "使用目的为" in prefix_in_quote
                or "\n\n" in prefix_in_quote
                or _SPECIAL_ANTIMICROBIAL_GOVERNING_NON_AUTH_PATTERN.search(prefix_in_quote)
            ):
                return False
            if not text[header_end:quote_end].strip():
                return False
        span_after_header = text[header_end:quote_end]
        if "\n\n" in span_after_header:
            return False
        return not _SPECIAL_ANTIMICROBIAL_NON_AUTHORIZED_SPEAKER_PATTERN.search(span_after_header)

    # 身份优先看引文及其前80字：感染科副主任医师意见中“请临床药学会诊后同意加用”仍出自授权专家（C04）；
    # 无授权专家署名的药学会诊、用药申请单文字，或专家意见之后切换为临床药师/其他非授权发言人，均严格拒绝（C05）。
    short_start = max(0, position - 80)
    short_context = text[short_start:quote_end]
    for pattern in (
        _SPECIAL_ANTIMICROBIAL_INFECTION_EXPERT_PATTERN,
        _SPECIAL_ANTIMICROBIAL_INFECTION_ECONSULT_PATTERN,
        _SPECIAL_ANTIMICROBIAL_ICU_EXPERT_PATTERN,
    ):
        for match in pattern.finditer(short_context):
            header_start = short_start + match.start()
            header_end = short_start + match.end()
            if position <= header_end + 80 and _span_has_no_speaker_switch(
                header_start, header_end, allow_prefix_before_header=True
            ):
                return True
    for marker in _SPECIAL_ANTIMICROBIAL_EXPERT_SUPPORT_MARKERS:
        search_from = 0
        while True:
            idx = short_context.find(marker, search_from)
            if idx < 0:
                break
            header_start = short_start + idx
            header_end = header_start + len(marker)
            if position <= header_end + 80 and _span_has_no_speaker_switch(
                header_start, header_end, allow_prefix_before_header=True
            ):
                return True
            search_from = idx + len(marker)
    # 医院抗生素使用权限专项会诊（如 ICU 主任医师会诊后粘贴培养药敏再写“故同意使用”）
    # 在同一会诊意见段落内可达 ~160 字；若中间出现新用药申请段或切换非授权发言人则不跨段借用（保护 C05）。
    extended_start = max(0, position - 160)
    extended_context = text[extended_start:quote_end]
    for pattern in (
        _SPECIAL_ANTIMICROBIAL_ICU_EXPERT_PATTERN,
        _SPECIAL_ANTIMICROBIAL_INFECTION_ECONSULT_PATTERN,
    ):
        for match in pattern.finditer(extended_context):
            header_start = extended_start + match.start()
            header_end = extended_start + match.end()
            if position <= header_end + 160 and _span_has_no_speaker_switch(
                header_start, header_end, allow_prefix_before_header=True
            ):
                return True
    # 电子特殊级抗菌药申请单（常无 document_title）紧接副主任/主任医师会诊意见，
    # 允许“本病人建议使用…使用目的为…”在会诊意见前文出现，也允许引文以该副高/主任医师署名起头，
    # 但引文本身不得为申请段且专家落款不得晚于引文结尾，且落款至引文结尾不得切换为非授权发言人。
    for match in _SPECIAL_ANTIMICROBIAL_REQUEST_SENIOR_APPROVAL_PATTERN.finditer(prefix_text):
        speaker_start = match.start("speaker")
        if speaker_start <= position <= match.end() + 160 and _span_has_no_speaker_switch(
            speaker_start, match.end(), allow_prefix_before_header=False
        ):
            return True
    # 正式《请会诊执行记录》中邀请感染科/ICU医师协助诊治（正文中常粘贴数百字影像与检验摘要后再写给药建议）；
    # 同一会诊意见内未切换至申请段或非授权发言人时，归属该受邀专项医师（允许引文以邀请/会诊落款起头）。
    if "请会诊执行记录" in text:
        for match in _SPECIAL_ANTIMICROBIAL_INVITED_EXPERT_CONSULT_PATTERN.finditer(prefix_text):
            if match.start() <= position <= match.end() + 600 and _span_has_no_speaker_switch(
                match.start(), match.end(), allow_prefix_before_header=False
            ):
                return True
    return False


def _is_pathogen_lab(row: Mapping[str, Any]) -> bool:
    """病原学项目身份只取检验名称，不把任意核酸检测等同于病原学。"""
    text = " ".join(_clean(row.get(field)) for field in (
        "labtest_subject", "lab_item_name", "item_name", "record_content",
    ))
    return bool(
        re.search(r"培养|药敏|病原", text)
        or re.search(r"(?:病毒|细菌|真菌|支原体|衣原体|结核|HBV|HCV|HIV).{0,20}(?:核酸|DNA|RNA)", text, re.I)
    )


def _has_unsynced_lab_orders(nondrug_order_rows: Sequence[Mapping[str, Any]]) -> bool:
    """检测非药品医嘱中是否存在有效检验/病原学/培养医嘱（用于 labtest_master=0 时的未同步守卫）。"""
    for row in nondrug_order_rows:
        status = _clean(row.get("order_status"))
        if any(marker in status for marker in _LAB_ORDER_CANCELLED_STATUSES):
            continue
        order_type = _clean(row.get("order_type"))
        order_class = _clean(row.get("order_class"))
        if order_type in _LAB_ORDER_CLASS_VALUES or order_class in _LAB_ORDER_CLASS_VALUES:
            return True
        name = _clean(row.get("order_name") or row.get("record_content"))
        if name and _LAB_ORDER_NAME_PATTERN.search(name):
            return True
    return False


def _is_prophylactic_antimicrobial_clause(clause: str) -> bool:
    """预防用药只按抗菌药所在的并列项判断。

    “予以头孢曲松抗感染、奥美拉唑抑酸护胃（预防应激性溃疡）”中的“预防”属于
    抑酸药，不能把同句的抗感染治疗排除（1019 C11）；“预防感染”仍视为预防用药。
    """

    for segment in re.split(r"、", clause):
        if not re.search(r"预防|围术期", segment):
            continue
        if (re.search(r"抗感染|抗菌", segment)
                or _antimicrobial_names_in({"record_content": segment})
                or re.search(r"预防[^、]{0,8}感染", segment)):
            return True
    return False


def _pathogen_basis_state(
    start: datetime,
    lab_master_rows: Sequence[Mapping[str, Any]],
    lab_item_rows: Sequence[Mapping[str, Any]],
) -> str:
    """开药时是否已有病原学结果：prior 已有、unknown 结果时间不明、none 尚无。"""

    pathogen_ids = {
        _clean(item.get("test_id")) for item in (*lab_master_rows, *lab_item_rows)
        if _clean(item.get("test_id")) and _is_pathogen_lab(item)
    }
    unknown = False
    for report in (*lab_master_rows, *lab_item_rows):
        if _clean(report.get("test_id")) not in pathogen_ids:
            continue
        moment = _parse_datetime(report.get("report_datetime") or report.get("report_time"))
        if moment is not None and moment <= start:
            return "prior"
        unknown = unknown or (bool(_clean(report.get("result"))) and moment is None)
    return "unknown" if unknown else "none"


def _order_reason_rule_outcome(
    *,
    rule_id: str,
    events: Sequence[Any],
    time_missing_names: Sequence[str],
    documents: Mapping[str, Any],
    per_event: Mapping[str, Sequence[str]],
    untimed: frozenset[str],
    extraction: Any,
    lab_master_rows: Sequence[Mapping[str, Any]],
    lab_item_rows: Sequence[Mapping[str, Any]],
    pathogen_sources_complete: bool,
    evaluation_horizon: datetime | date | None,
    horizon_error: str,
    daily_scope_complete: bool = True,
) -> tuple[str, str, Mapping[str, Any] | None, tuple[Mapping[str, Any], ...]]:
    """按医嘱事件映射054/057状态；模型只提供带引文的事实。

    054：每个开始/联合/更换事件须在开医嘱当日病程写明感染判断、选药理由或预防用途。
    057：仅开药时尚无病原学结果的治疗性事件；用户口径（2026-10-22）感染判断与选药理由
    都须记录，选药理由一句话即可（如“经验性覆盖革兰阴性菌”“按指南首选”）；写明“经验性用药/
    经验性抗感染”也算选药理由。
    """

    is_057 = rule_id == "LX0609-05-01-05"
    if time_missing_names:
        return "data_gap", "authoritative_time_missing", None, ()
    if not events:
        return "not_applicable", "trigger_absent_complete", None, ()
    if extraction is None or extraction.state == "technical_error":
        return "technical_error", getattr(extraction, "reason_code", "model_transport_error"), None, ()
    if extraction.state != "ready":
        return "data_gap", extraction.reason_code, None, ()
    facts_by_event = {item.event_id: item for item in extraction.facts}
    evaluated: list[tuple[Any, str]] = []
    for event in events:
        facts = facts_by_event.get(event.event_id)
        if event.kind == "stop":
            if is_057:
                continue
            start_facts = facts_by_event.get(event.start_event_id)
            if start_facts is not None and start_facts.has("planned_duration") and is_planned_stop(
                event, planned_duration(start_facts.quotes["planned_duration"][1]),
            ):
                continue
            if facts is not None and facts.has("stop_reason"):
                evaluated.append((event, "documented"))
            elif event.event_id in untimed or (facts is not None and facts.documented_use == "unknown"):
                evaluated.append((event, "unresolved"))
            else:
                evaluated.append((event, "missing" if daily_scope_complete else "unresolved"))
            continue
        if is_057:
            if facts is not None and facts.has("prophylaxis"):
                continue
            basis = _pathogen_basis_state(event.time, lab_master_rows, lab_item_rows)
            if not pathogen_sources_complete or basis == "unknown":
                evaluated.append((event, "unresolved"))
                continue
            if basis == "prior":
                continue
        documented = facts is not None and (
            (facts.has("infection_judgment") and facts.has("selection_reason")) if is_057
            else (facts.has("infection_judgment") or facts.has("selection_reason") or facts.has("prophylaxis"))
        )
        if documented:
            evaluated.append((event, "documented"))
        elif event.event_id in untimed or (facts is not None and facts.documented_use == "unknown"):
            evaluated.append((event, "unresolved"))
        else:
            evaluated.append((event, "missing" if daily_scope_complete else "unresolved"))
    if not evaluated:
        return "not_applicable", "trigger_absent_complete", None, ()
    window_outcome: tuple[str, str] | None = None
    missing = [event for event, state in evaluated if state == "missing"]
    if missing:
        mature_missing = [event for event in missing if not horizon_error and evaluation_horizon is not None
                          and frozen_window_is_mature(evaluation_horizon, event.window_end)]
        if mature_missing:
            # 未到期的另一事件不能成为本轮确定缺陷，成功/未知事实仍保留。
            evaluated = [(event, state) for event, state in evaluated
                         if state != "missing" or event in mature_missing]
        elif any(state == "unresolved" for _, state in evaluated):
            window_outcome = ("data_gap", "association_failed")
        elif horizon_error or evaluation_horizon is None:
            window_outcome = ("data_gap", horizon_error or "authoritative_time_missing")
        else:
            window_outcome = ("not_applicable", "evaluation_window_not_mature")
    names = list(dict.fromkeys(event.antimicrobial for event, _ in evaluated))
    unmatched = list(dict.fromkeys(event.antimicrobial for event, state in evaluated if state != "documented"))
    evidence: list[Mapping[str, Any]] = []
    for event, state in evaluated:
        evidence.extend(event.orders)
        facts = facts_by_event.get(event.event_id)
        refs = (
            [ref for ref, _quote in facts.quotes.values()] if state == "documented" and facts is not None
            else list(per_event.get(event.event_id, ()))
        )
        evidence.extend(documents[ref].row for ref in dict.fromkeys(refs) if ref in documents)
    evidence = list({id(row): row for row in evidence}.values())
    if window_outcome is not None:
        return *window_outcome, None, tuple(evidence)
    states = {state for _event, state in evaluated}
    if "missing" in states:
        final_state, reason_code = "non_compliant", "requirement_violated"
    elif "unresolved" in states:
        final_state, reason_code = "data_gap", "association_failed"
    else:
        final_state, reason_code = "compliant", "requirement_satisfied"
    if is_057:
        if final_state == "data_gap":
            return final_state, reason_code, None, tuple(evidence)
        return final_state, reason_code, {
            "verification_kind": "empiric_antimicrobial_reason_check",
            "antimicrobials": names,
            "empiric_use_confirmed": True,
            "reason_or_no_specimen_documented": final_state == "compliant",
        }, tuple(evidence)
    return final_state, reason_code, {
        "verification_kind": "antimicrobial_reason_documentation_check",
        "antimicrobials": names,
        "action_count": len(evaluated),
        "reason_documented": final_state == "compliant",
        "unmatched_antimicrobials": [] if final_state == "compliant" else unmatched,
        "association_ambiguous": final_state == "data_gap",
    }, tuple(evidence)


def _antimicrobial_document_refs(
    *,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
    selected_rows: Sequence[Mapping[str, Any]],
) -> tuple[str, ...]:
    """仅把执行器实际消费的抗菌药行映射为同快照、逐文书引用。

    选择结果必须在允许来源中唯一命中；重复或无法定位时返回空集。调用方会把
    “已消费却不能精确坐标化”交给 Binding 判为技术错误，绝不回退为整类文书或
    投影内部 ``source_document_refs``。未消费任何文书的否定结论则另行使用受控
    的源级判定锚点，不能与前一种技术失败混淆。
    """

    allowed_sources = (
        "inpat_drug_order",
        "first_course_record",
        "transfer_in_record",
        "daily_course_record",
        "senior_course_record",
        "consultation_record",
        "surgery_record",
        "anesthesia_record",
    )
    refs: list[str] = []
    for selected_row in selected_rows:
        matches: list[str] = []
        for source_key in allowed_sources:
            try:
                document_rows = materials.document_rows(source_key, snapshot=snapshot)
            except (EvidenceMaterialUnavailable, EvidenceMaterialTruncated):
                # 未消费该来源时，它的不可用不应抹掉另一来源已精确定位的文书。
                continue
            matches.extend(
                reference
                for reference, material_row in document_rows
                if material_row == selected_row
            )
        if len(matches) != 1:
            return ()
        refs.append(matches[0])
    return tuple(dict.fromkeys(refs))


async def execute_antimicrobial_family(
    *,
    rule_ids: Sequence[str],
    evidence_snapshot: Luxian0609EvidenceSnapshot,
    evidence_materials: Luxian0609EvidenceMaterialStore,
    llm_client: Any = None,
    source_cache: SourceRowsCache | None = None,
) -> ExtendedDocumentFamilyOutcome:
    """执行 LX0609 抗菌药规则族（05-01-02..06 / 05-03-01），独立维护理由/审批/疗效缓存。"""

    selected = tuple(
        rule_id for rule_id in rule_ids if rule_id in ANTIMICROBIAL_RULE_IDS
    )
    if not selected:
        return ExtendedDocumentFamilyOutcome(decisions=(), display_facts=())

    selected_set = set(selected)
    if selected_set == {"LX0609-05-03-01"}:
        decisions_only = tuple(
            _decision(
                rule_id=rule_id,
                snapshot=evidence_snapshot,
                source_keys=(),
                final_state="technical_error",
                reason_code="decision_contract_violation",
            )
            for rule_id in selected
        )
        return ExtendedDocumentFamilyOutcome(decisions=decisions_only, display_facts=())

    horizon_rows, horizon_error = (
        resolve_horizon_rows(
            evidence_snapshot, evidence_materials, cache=source_cache
        )
        if _ANTIMICROBIAL_HORIZON_RULES.intersection(selected_set)
        else ((), "")
    )
    (
        antimicrobial_horizon_date,
        antimicrobial_horizon_datetime,
        antimicrobial_horizon_error,
    ) = (
        _resolve_evaluation_horizon(horizon_rows, horizon_error)
        if _ANTIMICROBIAL_HORIZON_RULES.intersection(selected_set)
        else (None, None, None)
    )
    antimicrobial_evaluation_horizon = (
        antimicrobial_horizon_datetime or antimicrobial_horizon_date
    )

    registration_rows, _registration_error = _source_rows(
        evidence_materials, "inpat_registration", cache=source_cache
    )
    drug_order_rows, drug_order_error = _source_rows(
        evidence_materials, "inpat_drug_order", cache=source_cache
    )
    daily_rows, daily_error = _source_rows(
        evidence_materials, "daily_course_record", cache=source_cache
    )
    daily_scope_complete = evidence_materials.permits_absence("daily_course_record")
    senior_rows, senior_error = _source_rows(
        evidence_materials, "senior_course_record", cache=source_cache
    )
    consultation_rows, consultation_error = _source_rows(
        evidence_materials, "consultation_record", cache=source_cache
    )
    surgery_record_rows, _surgery_record_error = _source_rows(
        evidence_materials, "surgery_record", cache=source_cache
    )
    transfer_in_rows, transfer_in_error = _source_rows(
        evidence_materials, "transfer_in_record", cache=source_cache
    )
    nondrug_order_rows, _nondrug_order_error = _source_rows(
        evidence_materials, "inpat_nondrug_order", cache=source_cache
    )
    lab_item_rows, lab_item_error = _source_rows(
        evidence_materials, "labtest_item_report", cache=source_cache
    )
    lab_master_rows, lab_master_error = _source_rows(
        evidence_materials, "labtest_master", cache=source_cache
    )
    anesthesia_record_rows, _anesthesia_record_error = (
        _source_rows(evidence_materials, "anesthesia_record", cache=source_cache)
        if _ANTIMICROBIAL_REASON_RULES.intersection(selected_set)
        else ((), "")
    )
    first_course_rows, first_course_error = (
        _source_rows(evidence_materials, "first_course_record", cache=source_cache)
        if _ANTIMICROBIAL_REASON_RULES.intersection(selected_set)
        else ((), "")
    )

    antimicrobial_order_reason_extraction = None
    special_approval_extraction = None
    antimicrobial_effect_extraction = None
    decisions: list[RuleDecision] = []
    display: list[tuple[str, Mapping[str, Any]]] = []

    order_reason_cache: dict[str, Any] = {}

    async def special_approval_outcome(
    ) -> tuple[str, str, Mapping[str, Any] | None, tuple[Mapping[str, Any], ...]]:
        """058 医嘱驱动：特殊级药物首次使用 → 专家身份候选会诊/查房 → 模型确认同意使用。"""

        nonlocal special_approval_extraction
        resolution = derive_antimicrobial_use_events(
            _exclude_unperformed_antimicrobial_orders(_antimicrobial_orders(drug_order_rows), (*daily_rows, *senior_rows, *consultation_rows))[0],
            lambda row: _antimicrobial_names_in(row, _SPECIAL_ANTIMICROBIALS),
            exclusions_checked=True,
        )
        if resolution.time_missing_names:
            return "data_gap", "authoritative_time_missing", None, ()
        first_events: dict[str, Any] = {}
        for event in resolution.events:
            # 用户口径（2026-10-17）：同药后续续开或调整沿用首次使用时的专家支持。
            if event.kind != "stop" and (
                event.antimicrobial not in first_events or event.time < first_events[event.antimicrobial].time
            ):
                first_events[event.antimicrobial] = event
        events = tuple(first_events.values())
        if not events:
            return "not_applicable", "trigger_absent_complete", None, ()
        documents: list[WindowDocument] = []
        for source_key, rows in (("consultation_record", consultation_rows), ("senior_course_record", senior_rows)):
            for row in rows:
                text = _material_text(row)
                # 专家身份是结构事实：感染科副主任医师及以上署名、电子感染科会诊落款、
                # ICU高年资抗菌药权限会诊或专家会诊/查房标记；
                # 是否“同意使用该药”交给模型判定，不再用肯定/否定正则。
                if text and _has_authorized_special_antimicrobial_expert(text):
                    documents.append(WindowDocument(
                        f"D{len(documents) + 1}", source_key, row, _lx0609_058_row_time(row), text,
                    ))
        # 文书带关联医嘱号时只能支持该医嘱所属药物，不能借给其他事件。
        # 当首次用药24小时窗内已存在明确提及该目标药的授权专家会诊/查房时，优先只送审窗内候选，
        # 避免数周后的续用/调整会诊覆盖启用前或24小时内的有效会诊。
        per_event: dict[str, tuple[str, ...]] = {}
        for event in events:
            order_ids = {_clean(order.get("order_id")) for order in event.orders}
            eligible_docs = tuple(
                doc for doc in documents
                if not (linked := _linked_order_id(doc.row)) or linked in order_ids
            )
            timely_named_docs = tuple(
                doc for doc in eligible_docs
                if event.antimicrobial in doc.text
                and (doc.time is None or doc.time <= event.time + _LX0609_058_SUPPORT_WINDOW)
            )
            chosen_docs = timely_named_docs or eligible_docs
            per_event[event.event_id] = tuple(doc.doc_ref for doc in chosen_docs)
        referenced_doc_refs = {ref for refs in per_event.values() for ref in refs}
        prompt_documents = [doc for doc in documents if doc.doc_ref in referenced_doc_refs]
        special_approval_extraction = await extract_special_antimicrobial_approvals(
            events, prompt_documents, per_event, llm_client,
        )
        extraction = special_approval_extraction
        if extraction.state == "technical_error":
            return "technical_error", extraction.reason_code, None, ()
        if extraction.state != "ready":
            return "data_gap", extraction.reason_code, None, ()
        by_ref = {doc.doc_ref: doc for doc in documents}
        facts_by_event = {item.event_id: item for item in extraction.facts}
        unmatched: list[str] = []
        confirmed_unmatched: list[str] = []
        late = untimed = ambiguous = pending = mature_missing = False
        support_times: list[datetime] = []
        evidence: list[Mapping[str, Any]] = []
        for event in events:
            event_late = False
            evidence.extend(event.orders)
            facts = facts_by_event.get(event.event_id)
            approval = facts.quotes.get("approval") if facts is not None else None
            # 笼统同意“特殊级方案”无法归属到多个特殊级药物中的某一种：关联不明，不判缺失。
            ambiguous = ambiguous or (approval is None and facts is not None and facts.documented_use == "unknown")
            doc = by_ref.get(approval[0]) if approval else None
            if doc is not None and not _special_approval_by_authorized_expert(doc.text, approval[1]):
                # 用户口径（2026-10-17）：同意须出自感染科副主任医师及以上或感染专家会诊/查房；
                # 临床药师、主治医师意见及用药申请单文字不算（1019 C05）。
                doc = None
            if doc is not None:
                evidence.append(doc.row)
                if doc.time is None:
                    untimed = True
                    unmatched.append(event.antimicrobial)
                    continue
                support_times.append(doc.time)
                if doc.time <= event.time + _LX0609_058_SUPPORT_WINDOW:
                    continue
                late = True
                event_late = True
            unmatched.append(event.antimicrobial)
            mature = (not antimicrobial_horizon_error and antimicrobial_evaluation_horizon is not None
                      and frozen_window_is_mature(antimicrobial_evaluation_horizon, event.time + _LX0609_058_SUPPORT_WINDOW))
            pending = pending or (antimicrobial_evaluation_horizon is not None and not mature)
            mature_missing = mature_missing or mature
            if event_late or mature:
                confirmed_unmatched.append(event.antimicrobial)
        if not unmatched:
            final_state, reason_code = "compliant", "requirement_satisfied"
        elif ambiguous:
            final_state, reason_code = "data_gap", "association_failed"
        elif untimed:
            final_state, reason_code = "data_gap", "authoritative_time_missing"
        elif consultation_error or senior_error:
            final_state, reason_code = "data_gap", consultation_error or senior_error
        elif late or mature_missing:
            final_state, reason_code = "non_compliant", "requirement_violated" if late else "required_document_missing"
        elif antimicrobial_horizon_error or antimicrobial_evaluation_horizon is None:
            return "data_gap", antimicrobial_horizon_error or "authoritative_time_missing", None, tuple(evidence)
        elif pending:
            if any(after_frozen_horizon(event.time, antimicrobial_evaluation_horizon) for event in events):
                return "data_gap", "authoritative_time_conflict", None, tuple(evidence)
            return "not_applicable", "evaluation_window_not_mature", None, tuple(evidence)
        else:
            final_state, reason_code = "non_compliant", "required_document_missing"
        first_time = min(event.time for event in events)
        return final_state, reason_code, {
            "verification_kind": "special_antimicrobial_expert_support_check",
            "special_antimicrobials": [event.antimicrobial for event in events],
            "expert_support_present": bool(support_times) or untimed,
            "first_antimicrobial_time": first_time.isoformat(sep=" "),
            "expert_support_time": min(support_times).isoformat(sep=" ") if support_times else None,
            "support_before_use": final_state == "compliant",
            "unmatched_special_antimicrobials": (
                [] if reason_code == "association_failed" else
                list(dict.fromkeys(confirmed_unmatched if final_state == "non_compliant" else unmatched))
            ),
            "association_ambiguous": final_state == "data_gap" and reason_code == "association_failed",
        }, tuple({id(row): row for row in evidence}.values())

    async def order_reason_outcome(
        rule_id: str,
    ) -> tuple[str, str, Mapping[str, Any] | None, tuple[Mapping[str, Any], ...]]:
        nonlocal antimicrobial_order_reason_extraction
        raw_orders = _antimicrobial_orders(drug_order_rows)
        effective_orders = (_exclude_unperformed_antimicrobial_orders(raw_orders, (*daily_rows, *senior_rows, *consultation_rows))[0] if rule_id == "LX0609-05-01-05" else raw_orders)
        exclusions_differ = rule_id == "LX0609-05-01-05" and any(
            is_excluded_antimicrobial_order(row) and _clean(row.get("drug_apply_method")) != "皮试"
            for row in effective_orders
        )
        cache_key = "performed" if effective_orders != raw_orders or exclusions_differ else "all"
        if cache_key not in order_reason_cache:
            resolution = derive_antimicrobial_use_events(
                effective_orders, _antimicrobial_names_in,
                exclusions_checked=rule_id == "LX0609-05-01-05",
                discharge_time=_discharge_time(registration_rows, (), horizon_rows, horizon_error),
            )
            # 正面证据可提前证明合规；只有缺失否定需要等待窗口成熟。
            events = resolution.events
            documents, per_event, untimed = window_documents(
                events,
                (
                    ("first_course_record", first_course_rows),
                    ("transfer_in_record", transfer_in_rows),
                    ("daily_course_record", daily_rows),
                    ("senior_course_record", senior_rows),
                    ("consultation_record", consultation_rows),
                    # 只认预防用药引文；缺记录时间的不进窗口，以免把事件拖成无法定位。
                    ("surgery_record", tuple(row for row in surgery_record_rows if _row_time(row) is not None)),
                    ("anesthesia_record", tuple(row for row in anesthesia_record_rows if _row_time(row) is not None)),
                ),
                _material_text,
            )
            antimicrobial_order_reason_extraction = await extract_antimicrobial_reasons(
                events, documents, per_event, llm_client,
            )
            order_reason_cache[cache_key] = dict(
                events=events, missing=resolution.time_missing_names,
                extraction=antimicrobial_order_reason_extraction, documents={doc.doc_ref: doc for doc in documents},
                per_event=per_event, untimed=untimed,
            )
        outcome = _order_reason_rule_outcome(
            rule_id=rule_id,
            events=order_reason_cache[cache_key]["events"],
            time_missing_names=order_reason_cache[cache_key]["missing"],
            documents=order_reason_cache[cache_key]["documents"],
            per_event=order_reason_cache[cache_key]["per_event"],
            untimed=order_reason_cache[cache_key]["untimed"],
            extraction=order_reason_cache[cache_key]["extraction"],
            lab_master_rows=lab_master_rows,
            lab_item_rows=lab_item_rows,
            pathogen_sources_complete=not (lab_master_error or lab_item_error),
            evaluation_horizon=antimicrobial_evaluation_horizon,
            horizon_error=antimicrobial_horizon_error or "",
            daily_scope_complete=daily_scope_complete,
        )
        return outcome

    for rule_id in selected:
        if rule_id == "LX0609-05-03-01":
            # 059 仍处于 pending_definition。正式编排不会派发它；若低层
            # 兼容入口收到该规则，只能报告执行合同错误，不能交付临床缺陷。
            decisions.append(
                _decision(
                    rule_id=rule_id,
                    snapshot=evidence_snapshot,
                    source_keys=(),
                    final_state="technical_error",
                    reason_code="decision_contract_violation",
                )
            )
            continue

        if rule_id in {
            "LX0609-05-01-02", "LX0609-05-01-03", "LX0609-05-01-04",
            "LX0609-05-01-05", "LX0609-05-01-06", "LX0609-05-03-01",
        }:
            antimicrobial_orders = _antimicrobial_orders(drug_order_rows)
            excluded_antimicrobial_evidence: tuple[Mapping[str, Any], ...] = ()
            if rule_id in {"LX0609-05-01-03", "LX0609-05-01-05", "LX0609-05-01-06"}:
                antimicrobial_orders, excluded_antimicrobial_evidence = (
                    _exclude_unperformed_antimicrobial_orders(
                        antimicrobial_orders,
                        (*senior_rows, *consultation_rows)
                        if rule_id == "LX0609-05-01-06"
                        else (*daily_rows, *senior_rows, *consultation_rows),
                    )
                )
            rule_antimicrobial_orders = (
                _055_treatment_orders(antimicrobial_orders)
                if rule_id == "LX0609-05-01-03"
                else antimicrobial_orders
            )
            course_rows = (
                # 转入记录是转科后首份病程性文书，其诊疗计划记载抗菌药使用及理由（1019 C10）。
                (*first_course_rows, *transfer_in_rows, *daily_rows, *senior_rows)
                if rule_id in {"LX0609-05-01-02", "LX0609-05-01-05"}
                else (*daily_rows, *senior_rows)
            )
            selected_antimicrobial_evidence_rows: list[Mapping[str, Any]] = list(
                excluded_antimicrobial_evidence
            )
            source_error = drug_order_error or (
                "" if rule_id in {"LX0609-05-01-04", "LX0609-05-01-06"} else daily_error or senior_error
            )
            if rule_id in {"LX0609-05-01-02", "LX0609-05-01-05"}:
                source_error = source_error or first_course_error or transfer_in_error
            if source_error:
                final_state, reason_code = "data_gap", source_error
            elif rule_id == "LX0609-05-01-02":
                outcome = await order_reason_outcome(rule_id)
                final_state, reason_code = outcome[0], outcome[1]
                if outcome[2] is not None:
                    display.append((rule_id, outcome[2]))
                selected_antimicrobial_evidence_rows.extend(outcome[3])
            elif not rule_antimicrobial_orders:
                final_state, reason_code = "not_applicable", "trigger_absent_complete"
            elif rule_id == "LX0609-05-01-03":
                # 客户确认口径（2026-10-20），基线055：按客户允许的计划开始/开医嘱时间起算，
                # 续开不另建48–72小时窗。用户口径（2026-10-21）改为医嘱驱动：疗程与054/057
                # 共用同一推导——撤销、皮试医嘱不算；同药停用超过24小时后再开为新疗程，另建窗口；
                # 疗程不满48小时即停用的不要求48–72小时评价。
                course_resolution = derive_antimicrobial_use_events(
                    rule_antimicrobial_orders, _antimicrobial_names_in,
                    # 已按本次实际给药证据核对取消/未实施，不能在建疗程时再次仅凭状态排除。
                    exclusions_checked=True,
                )
                order_events = tuple(
                    (_AntimicrobialOrderEvent(event.orders, (event.antimicrobial,)), event.antimicrobial, event.time)
                    for event in course_resolution.events
                    if event.kind != "stop"
                    and (event.course_end is None or event.course_end >= event.time + timedelta(hours=48))
                ) + tuple(
                    (_AntimicrobialOrderEvent(
                        tuple(order for order in rule_antimicrobial_orders if name in _antimicrobial_names_in(order)),
                        (name,),
                    ), name, None)
                    for name in course_resolution.time_missing_names
                )
                # 即使评价窗尚未成熟，开始医嘱仍是这项否定结论实际消费的
                # 业务事实；horizon 仅决定窗口状态，绝不成为客户证据。
                selected_antimicrobial_evidence_rows.extend(
                    row
                    for event, _name, start in order_events
                    if start is not None
                    for row in event.orders
                )
                event_windows: list[dict[str, Any]] = []
                mature_events: list[tuple[_AntimicrobialOrderEvent, str, datetime]] = []
                immature_states: list[str] = []
                if not order_events:
                    final_state, reason_code = "not_applicable", "trigger_absent_complete"
                elif any(start is None for _, _, start in order_events):
                    final_state, reason_code = "data_gap", "authoritative_time_missing"
                elif antimicrobial_horizon_error:
                    final_state, reason_code = "data_gap", antimicrobial_horizon_error
                else:
                    for order, name, start in order_events:
                        assert start is not None
                        state, _, window_facts = _antimicrobial_effect_window_state(
                            start_time=start,
                            horizon_date=antimicrobial_horizon_date,
                            horizon_time=antimicrobial_horizon_datetime,
                        )
                        event_windows.append({
                            "antimicrobial": name,
                            "event_state": state,
                            **window_facts,
                        })
                        if state == "conflict":
                            final_state, reason_code = (
                                "data_gap", "authoritative_time_conflict"
                            )
                            break
                        if state == "missing":
                            final_state, reason_code = (
                                "data_gap", "authoritative_time_missing"
                            )
                            break
                        if state == "mature":
                            mature_events.append((order, name, start))
                        else:
                            immature_states.append(state)
                    else:
                        final_state = reason_code = ""
                # 先由程序确定窗口，再完整抽取各目标药的评价；不以结果词筛正文。
                effect_rows_by_name: dict[str, list[Mapping[str, Any]]] = {}
                safety_rows_by_name: dict[str, list[Mapping[str, Any]]] = {}
                unknown_effect_rows_by_name: dict[str, list[Mapping[str, Any]]] = {}
                unknown_safety_rows_by_name: dict[str, list[Mapping[str, Any]]] = {}
                unassigned_effect_rows: list[Mapping[str, Any]] = []
                unassigned_safety_rows: list[Mapping[str, Any]] = []
                evaluation_resolution = "ready"
                if not final_state and mature_events:
                    targets = tuple(dict.fromkeys(name for _, name, _ in mature_events))
                    # 用户口径（2026-10-20）：空白病程的时间（无权威时间时取最后修改时间作上限）
                    # 早于全部评价窗或已在窗外时，不可能是窗内评价，不再使整例资料不足。
                    earliest_window = min(start + timedelta(hours=48) for _, _, start in mature_events)
                    # 医嘱驱动：只把落在某个48–72小时评价窗内的病程交给模型；无权威时间的病程
                    # 以最后修改时间为上限，上限早于最早评价窗的必然不在窗内。
                    effect_course_rows = tuple(
                        row for row in course_rows
                        if (
                            (value := _row_time(row)) is not None
                            and any(48 <= (value - start).total_seconds() / 3600 <= 72
                                    for _, _, start in mature_events)
                        )
                        or (
                            value is None
                            and not ((bound := row_time_upper_bound(row)) is not None and bound < earliest_window)
                        )
                    )
                    antimicrobial_effect_extraction = await extract_antimicrobial_effects(
                        effect_course_rows, targets, llm_client,
                        max_prompt_bytes=65536, max_completion_tokens=16384,
                    )
                    if antimicrobial_effect_extraction.reason_code == "source_capacity_exceeded":
                        # 全住院笛卡尔配对超限时，按权威时间排除不可能满足窗口的配对。
                        # 保留所有无时间病程及窗口内全文，不按药名或评价词筛选、截断正文。
                        candidate_pairs = tuple(
                            (row_index, target_index)
                            for row_index, row in enumerate(effect_course_rows)
                            for target_index, target in enumerate(targets)
                            if (value := _row_time(row)) is None
                            or any(
                                name == target and 48 <= (value - start).total_seconds() / 3600 <= 72
                                for _order, name, start in mature_events
                            )
                        )
                        antimicrobial_effect_extraction = await extract_antimicrobial_effect_pairs(
                            effect_course_rows, targets, candidate_pairs, llm_client,
                            max_prompt_bytes=65536, max_completion_tokens=16384,
                        )
                    extraction = antimicrobial_effect_extraction
                    if extraction.state != "ready":
                        final_state = extraction.state
                        reason_code = (
                            "candidate_scope_incomplete"
                            if extraction.reason_code == "source_capacity_exceeded"
                            else extraction.reason_code
                        )
                        evaluation_resolution = (
                            "capacity_exceeded" if reason_code == "candidate_scope_incomplete"
                            else "unavailable" if final_state == "data_gap" else "invalid"
                        )
                    else:
                        for assertion in extraction.assertions:
                            row = effect_course_rows[assertion.row_index]
                            name = targets[assertion.target_index]
                            for state, rows_by_name, unknown_rows_by_name, unassigned_rows in (
                                (
                                    assertion.effect_state,
                                    effect_rows_by_name,
                                    unknown_effect_rows_by_name,
                                    unassigned_effect_rows,
                                ),
                                (
                                    assertion.safety_state,
                                    safety_rows_by_name,
                                    unknown_safety_rows_by_name,
                                    unassigned_safety_rows,
                                ),
                            ):
                                if state == "present":
                                    rows_by_name.setdefault(name, []).append(row)
                                elif state == "regimen":
                                    # 未点药名的整体方案评价：只用一种药（可有多个疗程）时按评价窗归属；
                                    # 多药同用时仍无法确定评价的是哪种药。
                                    row_time = _row_time(row)
                                    window_names = {
                                        event_name for _, event_name, start in mature_events
                                        if row_time is not None
                                        and 48 <= (row_time - start).total_seconds() / 3600 <= 72
                                    }
                                    single_drug = {event_name for _, event_name, _ in order_events} == {name}
                                    if len(order_events) == 1 or (single_drug and window_names == {name}):
                                        rows_by_name.setdefault(name, []).append(row)
                                    elif row not in unassigned_rows:
                                        unassigned_rows.append(row)
                                elif state == "unknown":
                                    unknown_rows_by_name.setdefault(name, []).append(row)
                # 同药多个疗程时按评价窗归属：只有同一份病程同时落入两个同药疗程的
                # 评价窗（或缺时无法定位）才无法归属。
                ambiguous_evaluation = any(
                    not _linked_order_id(row)
                    and sum(
                        name == event_name and (
                            (value := _row_time(row)) is None
                            or 48 <= (value - start).total_seconds() / 3600 <= 72
                        )
                        for _, event_name, start in mature_events
                    ) > 1
                    for rows_by_name in (effect_rows_by_name, safety_rows_by_name)
                    for name, rows in rows_by_name.items() for row in rows
                )
                effect_intervals: list[float] = []
                safety_intervals: list[float] = []
                unmatched_effect_names: list[str] = []
                unmatched_safety_names: list[str] = []
                unmatched_names: list[str] = []
                has_untimed_match = False
                has_unresolved_unknown = False
                has_unassigned_regimen = False
                if final_state in {"data_gap", "technical_error", "not_applicable"}:
                    pass
                elif ambiguous_evaluation:
                    final_state, reason_code = "data_gap", "association_failed"
                else:
                    for order, name, start in mature_events:
                        order_ids = order.order_ids
                        for (
                            rows_by_name,
                            unknown_rows_by_name,
                            unassigned_rows,
                            dimension_intervals,
                            unmatched_names,
                        ) in (
                            (
                                effect_rows_by_name,
                                unknown_effect_rows_by_name,
                                unassigned_effect_rows,
                                effect_intervals,
                                unmatched_effect_names,
                            ),
                            (
                                safety_rows_by_name,
                                unknown_safety_rows_by_name,
                                unassigned_safety_rows,
                                safety_intervals,
                                unmatched_safety_names,
                            ),
                        ):
                            matching_rows = tuple(
                                row for row in rows_by_name.get(name, ())
                                if not _linked_order_id(row)
                                or _linked_order_id(row) in order_ids
                            )
                            event_intervals = [
                                (value - start).total_seconds() / 3600
                                for row in matching_rows
                                if (value := _row_time(row)) is not None and value >= start
                            ]
                            selected_antimicrobial_evidence_rows.extend(
                                row
                                for row in matching_rows
                                if (value := _row_time(row)) is not None
                                and 48 <= (value - start).total_seconds() / 3600 <= 72
                            )
                            dimension_intervals.extend(event_intervals)
                            if not any(48 <= value <= 72 for value in event_intervals):
                                matching_unknown_rows = tuple(
                                    row for row in unknown_rows_by_name.get(name, ())
                                    if not _linked_order_id(row)
                                    or _linked_order_id(row) in order_ids
                                )
                                unknown_is_relevant = any(
                                    (value := _row_time(row)) is None
                                    or 48 <= (value - start).total_seconds() / 3600 <= 72
                                    for row in matching_unknown_rows
                                )
                                unassigned_is_relevant = any(
                                    (value := _row_time(row)) is None
                                    or 48 <= (value - start).total_seconds() / 3600 <= 72
                                    for row in unassigned_rows
                                )
                                if unknown_is_relevant:
                                    has_unresolved_unknown = True
                                elif unassigned_is_relevant:
                                    has_unassigned_regimen = True
                                else:
                                    unmatched_names.append(name)
                                    has_untimed_match = has_untimed_match or any(
                                        _row_time(row) is None for row in matching_rows
                                    )
                    unmatched_names = list(dict.fromkeys(
                        (*unmatched_effect_names, *unmatched_safety_names)
                    ))
                    # 已有药物确定缺评价（有权威时间、窗口内无评价）时直接判不合规，不因其他药物
                    # 评价不确定而降为资料不足；与054“缺失优先于不明”一致（2026-10-23，C08）。
                    confirmed_missing = bool(unmatched_names) and not has_untimed_match and daily_scope_complete
                    if has_unresolved_unknown and not confirmed_missing:
                        final_state, reason_code = (
                            "data_gap", "semantic_extraction_unresolved"
                        )
                        evaluation_resolution = "unknown"
                    elif has_unassigned_regimen and not confirmed_missing:
                        final_state, reason_code = "data_gap", "association_failed"
                        ambiguous_evaluation = True
                    elif not unmatched_names:
                        if immature_states:
                            final_state = "not_applicable"
                            reason_code = (
                                "evaluation_window_not_mature"
                                if "not_mature" in immature_states
                                else "evaluation_window_not_started"
                            )
                        else:
                            final_state, reason_code = (
                                "compliant", "requirement_within_threshold"
                            )
                    elif has_untimed_match:
                        final_state, reason_code = "data_gap", "authoritative_time_missing"
                    elif not daily_scope_complete:
                        final_state, reason_code = "data_gap", "source_unavailable"
                        evaluation_resolution = "unknown"
                    else:
                        final_state, reason_code = "non_compliant", "threshold_exceeded"
                if final_state == "data_gap" and reason_code in {
                    "authoritative_time_missing", "authoritative_time_conflict"
                }:
                    evaluation_resolution = "time_unresolved"
                display_facts: dict[str, Any] = {
                    "verification_kind": "antimicrobial_effect_evaluation_check",
                    "evaluation_resolution": evaluation_resolution,
                    "antimicrobials": list(dict.fromkeys(
                        name for _, name, _ in order_events
                    )),
                    "window_hours": [48, 72],
                    "evaluation_intervals": [round(value, 2) for value in effect_intervals],
                    "effect_evaluation_intervals": [round(value, 2) for value in effect_intervals],
                    "safety_evaluation_intervals": [round(value, 2) for value in safety_intervals],
                    "unmatched_antimicrobials": unmatched_names,
                    "unmatched_effect_antimicrobials": list(dict.fromkeys(unmatched_effect_names)),
                    "unmatched_safety_antimicrobials": list(dict.fromkeys(unmatched_safety_names)),
                    "association_ambiguous": ambiguous_evaluation,
                    "event_windows": event_windows,
                }
                if final_state == "not_applicable" and reason_code == "trigger_absent_complete":
                    pass
                else:
                    if final_state == "not_applicable":
                        display_facts["window_state"] = reason_code
                    display.append((rule_id, display_facts))
            elif rule_id == "LX0609-05-01-04":
                # 院方口径（2026-10-11）：重点抗菌药物按院方七类清单识别；“两种及以上”
                # 按药品种数计，同一药多条医嘱只算一种。
                # 用户口径（2026-10-21）医嘱驱动：皮试、撤销医嘱不算使用；使用起点取计划开始时间，
                # 缺失才回退开医嘱时间，与054/055/057/058一致。
                special_orders = tuple(
                    row for row in drug_order_rows
                    if key_antimicrobials_in_order(row) and not is_excluded_antimicrobial_order(row)
                    and not is_local_route_drug_order(row)
                )
                key_drugs = {
                    name for row in special_orders for name in key_antimicrobials_in_order(row)
                }
                if len(key_drugs) < 2:
                    final_state, reason_code = "not_applicable", "trigger_absent_complete"
                elif lab_master_error or lab_item_error:
                    final_state, reason_code = "data_gap", lab_master_error or lab_item_error
                elif not lab_master_rows and _has_unsynced_lab_orders(nondrug_order_rows):
                    # 检验主表为 0 行但非药品医嘱中存在有效检验/培养医嘱，说明检验报告数据源未同步，
                    # 不得误判为“未送检病原学”不合规，规范降级为资料不足。
                    final_state, reason_code = "data_gap", "source_unavailable"
                else:
                    special_order_times = tuple(order_start_time(row) for row in special_orders)
                    first_order = (
                        None if any(value is None for value in special_order_times)
                        else min(special_order_times, default=None)
                    )
                    # 项目身份常在明细、申请/采样时间在主表；只用同一 test_id
                    # 关联，不能把其他检验的时间借给病原学项目。
                    pathogen_test_ids = {
                        _clean(row.get("test_id"))
                        for row in lab_item_rows
                        if _clean(row.get("test_id"))
                        and _is_pathogen_lab(row)
                    }
                    pathogen_rows = tuple(row for row in lab_master_rows if _is_pathogen_lab(row) or _clean(row.get("test_id")) in pathogen_test_ids)
                    specimen_times = tuple(
                        value
                        for row in lab_master_rows
                        if (
                            _is_pathogen_lab(row)
                            or _clean(row.get("test_id")) in pathogen_test_ids
                        )
                        and (value := _precise_datetime(row.get("sample_datetime")))
                        is not None
                    )
                    if first_order is None or ((pathogen_rows or pathogen_test_ids) and len(specimen_times) != len(pathogen_rows) and not any(value <= first_order for value in specimen_times)):
                        final_state, reason_code = "data_gap", "authoritative_time_missing"
                    elif not any(value <= first_order for value in specimen_times) and any(
                        (request := _precise_datetime(row.get("request_datetime"))) is not None
                        and (sample := _precise_datetime(row.get("sample_datetime"))) is not None
                        and request <= first_order < sample for row in pathogen_rows
                    ):
                        # 申请与采样跨越用药起点，口径未确认时不选其中一个制造确定缺陷。
                        final_state, reason_code = "data_gap", "authoritative_time_conflict"
                    else:
                        complete = any(value <= first_order for value in specimen_times)
                        final_state = "compliant" if complete else "non_compliant"
                        reason_code = "requirement_satisfied" if complete else "requirement_violated"
                        display.append((rule_id, {
                            "verification_kind": "key_antimicrobial_specimen_check",
                            "key_drug_count": len(key_drugs),
                            "specimen_before_first_order": complete,
                        }))
            elif rule_id == "LX0609-05-01-05":
                outcome = await order_reason_outcome(rule_id)
                final_state, reason_code = outcome[0], outcome[1]
                if outcome[2] is not None:
                    display.append((rule_id, outcome[2]))
                selected_antimicrobial_evidence_rows.extend(outcome[3])
            elif rule_id == "LX0609-05-01-06":
                outcome = await special_approval_outcome()
                final_state, reason_code = outcome[0], outcome[1]
                if outcome[2] is not None:
                    display.append((rule_id, outcome[2]))
                selected_antimicrobial_evidence_rows.extend(outcome[3])
            else:
                used_names = _antimicrobial_names_in_rows(antimicrobial_orders)
                complete = bool(used_names) and all(
                    _has_any_text(course_rows, (name,)) for name in used_names
                )
                final_state = "compliant" if complete else "non_compliant"
                reason_code = "requirement_satisfied" if complete else "requirement_violated"
                display.append((rule_id, {
                    (
                        "verification_kind"
                        if complete
                        else "failure_kind"
                    ): (
                        "antimicrobial_course_documentation_complete"
                        if complete
                        else "antimicrobial_course_documentation_missing"
                    ),
                    "antimicrobials": list(used_names),
                    "course_documented": complete,
                }))
            antimicrobial_document_refs = _antimicrobial_document_refs(
                snapshot=evidence_snapshot,
                materials=evidence_materials,
                selected_rows=selected_antimicrobial_evidence_rows,
            )
            has_selected_antimicrobial_evidence = bool(
                selected_antimicrobial_evidence_rows
            )
            is_pending_window = (
                rule_id in {"LX0609-05-01-03", "LX0609-05-01-06"}
                and final_state == "not_applicable"
                and reason_code in {"evaluation_window_not_started", "evaluation_window_not_mature"}
            )
            horizon_refs = _fact_refs(evidence_snapshot, ("evaluation_context.horizon",))
            uses_horizon = (
                is_pending_window
                or reason_code == "evaluation_window_not_mature"
                or (rule_id in {"LX0609-05-01-02", "LX0609-05-01-05"} and final_state == "non_compliant")
                or (rule_id == "LX0609-05-01-06" and reason_code == "required_document_missing")
            )
            affirmative_window = is_pending_window and bool(antimicrobial_document_refs and horizon_refs)
            if uses_horizon:
                antimicrobial_document_refs = (*antimicrobial_document_refs, *horizon_refs)
            decisions.append(_decision(
                rule_id=rule_id,
                snapshot=evidence_snapshot,
                # 没有实际消费文书的“触发未发生”结论只保留单一源级锚点；
                # 一旦消费了行，则必须使用精确文书坐标，空/非法坐标由 Binding
                # 明确作为技术失败处理，不能伪装为原业务状态。
                source_keys=(
                    () if has_selected_antimicrobial_evidence
                    else ("inpat_drug_order",)
                ),
                document_refs=antimicrobial_document_refs,
                exact_document_refs=has_selected_antimicrobial_evidence,
                final_state=final_state,
                reason_code=reason_code,
                affirmative_applicability=affirmative_window,
            ))
            continue


    extractions = tuple(
        item
        for item in (
            *(entry["extraction"] for entry in order_reason_cache.values()),
            special_approval_extraction,
            antimicrobial_effect_extraction,
        )
        if item is not None
    )
    return ExtendedDocumentFamilyOutcome(
        decisions=tuple(decisions),
        display_facts=tuple(display),
        llm_call_count=sum(item.llm_call_count for item in extractions),
        prompt_tokens=sum(item.prompt_tokens for item in extractions),
        completion_tokens=sum(item.completion_tokens for item in extractions),
        total_tokens=sum(item.total_tokens for item in extractions),
        api_time=sum(item.api_time for item in extractions),
    )
