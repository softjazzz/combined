"""LX0609-12-01-01、LX0609-12-01-02 病程复制判定：确定性比较与单次受控语义复核。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
import hashlib
import heapq
import re
from typing import Any, Mapping, Protocol

from ..cache_document_source_adapter import explicit_sections
from ..decision_model import (
    ApplicabilityState,
    EvidenceState,
    QcDirection,
    RuleDecision,
)
from ..evidence_material import Luxian0609EvidenceMaterialStore
from ..evidence_snapshot import Luxian0609EvidenceSnapshot
from ..source_evidence_reader import authoritative_document_time_value
from .shared import (
    DATE_PATTERN as _DATE_PATTERN,
    MAX_ROWS_PER_SOURCE as _MAX_ROWS_PER_SOURCE,
    TIME_PATTERN as _TIME_PATTERN,
    authoritative_course_time as _authoritative_course_time,
    clean_text as _clean,
    source_rows as _source_rows,
    substantive_rows as _substantive_rows,
)


class CourseQualityLLMClient(Protocol):
    async def generate(
        self,
        prompt: str,
        *,
        max_completion_tokens: int | None = None,
        allow_length_retry: bool = True,
    ) -> dict[str, Any]:
        ...


RULE_017_COPY_SOURCES = (
    "daily_course_record",
    "senior_course_record",
)
_MIN_COMPARABLE_CHARS = 24
_MIN_FIRST_COURSE_BODY_CHARS = 6
_COPY_SIMILARITY_THRESHOLD = 0.70
_COPY_SEMANTIC_REVIEW_PASSED_REASON = "copy_semantic_review_passed"
_COPY_TEMPLATE_SHELL_ONLY_REASON = "copy_template_shell_only"
# 院方口径（2026-10-10）：同类病程同日数分钟内几乎相同，更像同一记录重复保存，
# 不算复制病历，但须向客户提出疑点。
_COPY_DUPLICATE_SAVE_SUSPECTED_REASON = "copy_duplicate_save_suspected"
_COPY_DUPLICATE_SAVE_MAX_SECONDS = 30 * 60
_COPY_FAST_SHINGLE_CHARS = 5
_COPY_PRECISE_CANDIDATE_LIMIT = 20
_COPY_DISPLAY_PAIR_LIMIT = 4
_COPY_TEMPLATE_SHELL_PHRASES = (
    "患者病情稳定",
    "病情稳定",
    "患者病情平稳",
    "病情平稳",
    "一般情况良好",
    "一般情况可",
    "生命体征平稳",
    "生命体征稳定",
    "查体无明显异常",
    "无明显异常查体",
    "继续当前治疗",
    "继续原治疗",
    "观察病情",
)
_RULE_016_EXACT_MATCH = 1.0
_RULE_016_ADMISSION_HEADINGS = (
    "个人史", "婚姻史", "婚育史", "婚姻及生育史", "月经史", "生育史", "月经生育史", "家族史",
)
# 未识别的独立短行后若还有正文，可能是下一栏标题，不能当作当前栏原文。
_RULE_016_UNRESOLVED_HEADING = re.compile(
    r"(?:^|[\r\n]|(?<=[。；;]))[ \t]*(?:[一二三四五六七八九十]+[、.．][ \t]*)?"
    r"[【\[]?[\u4e00-\u9fff]{2,10}[】\]]?[ \t]*[:：]"
    r"|(?:^|[\r\n])[ \t]*(?:[一二三四五六七八九十]+[、.．][ \t]*)?"
    r"(?:[【\[][\u4e00-\u9fff]{2,16}[】\]]|[\u4e00-\u9fff]{0,12}"
    r"(?:情况|记录|资料|信息|栏目|摘要|概述|说明|计划|意见|内容|备注|事项|检查|报告|史))"
    r"[ \t]*(?=[\r\n]|$)"
    r"|(?:^|[\r\n])[ \t]*[\u4e00-\u9fff]{2,12}[ \t]*(?=[\r\n]+[ \t]*\S)"
)
_RULE_016_SECTION_PLACEHOLDER = re.compile(
    r"(?:请填写|待填写|未填写|待补充|请输入)(?:现病史|病例特点)?"
)


def _first_course_body_text(row: Mapping[str, Any]) -> str:
    """只返回首次病程实质正文，不把界面预览当作正文。"""

    content = _clean(
        row.get("case_characteristic")
        or row.get("record_content")
        or row.get("content")
        or row.get("assembled_text")
        or row.get("raw_text")
    )
    if not content:
        return ""
    normalized = re.sub(r"[\W_]+", "", content, flags=re.UNICODE)
    shell_remainder = re.sub(
        r"(?:首次病程记录|首次病程|记录时间|提交时间|文书类型|文书编号|正文|"
        r"sourcetable|firstcourserecord|assemblystatus|partial|"
        r"年|月|日|时|分|秒|\d+)",
        "",
        normalized,
        flags=re.IGNORECASE,
    )
    return content if len(shell_remainder) >= _MIN_FIRST_COURSE_BODY_CHARS else ""


def _admission_body_text(row: Mapping[str, Any]) -> str:
    """只接受入院记录正文承载字段，拒绝标题、时间和预览壳。"""

    content = _clean(
        row.get("history_of_present_illness")
        or row.get("record_content")
        or row.get("content")
        or row.get("assembled_text")
        or row.get("raw_text")
    )
    if not content:
        return ""
    normalized = re.sub(r"[\W_]+", "", content, flags=re.UNICODE)
    shell_remainder = re.sub(
        r"(?:入院记录|记录时间|提交时间|文书类型|文书编号|正文|"
        r"sourcetable|admissionrecord|assemblystatus|partial|"
        r"年|月|日|时|分|秒|\d+)",
        "",
        normalized,
        flags=re.IGNORECASE,
    )
    return content if len(shell_remainder) >= _MIN_FIRST_COURSE_BODY_CHARS else ""


def _substantive_first_course_rows(
    documents: Mapping[str, Any],
) -> tuple[tuple[str, Mapping[str, Any], str], ...]:
    return tuple(
        ("first_course_record", row, content)
        for row in _source_rows(documents, "first_course_record")
        if (content := _first_course_body_text(row))
    )


def _substantive_admission_rows(
    documents: Mapping[str, Any],
) -> tuple[tuple[str, Mapping[str, Any], str], ...]:
    return tuple(
        ("admission_record", row, content)
        for row in _source_rows(documents, "admission_record")
        if (content := _admission_body_text(row))
    )


def _rule_016_comparison_material_state(documents: Mapping[str, Any]) -> str:
    """区分 016 的“无可比文书”与“文书存在但正文不可用”。"""

    admission_rows = _source_rows(documents, "admission_record")
    first_course_rows = _source_rows(documents, "first_course_record")
    # 任一端完全没有文书时都无法构成“入院记录 vs 首次病程”的比较对象，
    # 属于规则不适用；只有文书行存在但正文不可比时才是资料不足。
    if not admission_rows or not first_course_rows:
        return "absent"
    if (
        not _substantive_admission_rows(documents)
        or not _substantive_first_course_rows(documents)
    ):
        return "unavailable"
    return "ready"
def _normalized_for_similarity(content: str) -> str:
    value = _DATE_PATTERN.sub("", content)
    value = _TIME_PATTERN.sub("", value)
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]", "", value).lower()


def _normalized_for_exact_section_comparison(content: str) -> str:
    """016 仅忽略空白与普通句读，保留临床日期、数值及医学符号。"""

    value = re.sub(r"\s+", "", content)
    # 逗号夹在数字之间可能是数值分隔符，不能当作普通句读删除。
    value = re.sub(r"(?<![0-9])[,，]|[,，](?![0-9])", "", value)
    return re.sub(r"[；;。]", "", value)


def _rule_016_frozen_sections(
    snapshot: Luxian0609EvidenceSnapshot, materials: Luxian0609EvidenceMaterialStore,
) -> tuple[dict[str, Any], tuple[str, ...]] | None:
    """只为自动冻结材料补读明确的整段栏目，结构化值始终优先。"""
    documents: dict[str, Any] = {}
    refs: list[str] = []
    used_body_section = False
    for source_key, field, label, substantive_body in (
        ("admission_record", "history_of_present_illness", "现病史", _admission_body_text),
        ("first_course_record", "case_characteristic", "病例特点", _first_course_body_text),
    ):
        scope_status = (materials.scope(source_key) or {}).get("status")
        if scope_status not in {"available", "body_empty"}:
            return None
        pairs = materials.document_rows(source_key, snapshot=snapshot)
        if len(pairs) != 1:
            return None
        ref, row = pairs[0]
        if not _clean(row.get("document_id")):
            return None
        value = _clean(row.get(field))
        if not value:
            additional_headings = _RULE_016_ADMISSION_HEADINGS if source_key == "admission_record" else ()
            sections = [
                text for heading, text in explicit_sections(
                    row.get("record_content"), additional_headings=additional_headings,
                ) if heading == label
            ]
            if scope_status != "available" or len(sections) != 1:
                return None
            value = sections[0]
            if (
                not substantive_body({field: value})
                or _RULE_016_UNRESOLVED_HEADING.search(value)
                or _RULE_016_SECTION_PLACEHOLDER.fullmatch(re.sub(r"[\W_]+", "", value))
            ):
                return None
            used_body_section = True
        refs.append(ref)
        documents[source_key] = [{**row, field: value}]
    return (documents, tuple(refs)) if used_body_section else None


def _rule_016_copy_coverage(documents: Mapping[str, Any]) -> float | None:
    """只比较已定位的现病史与病例特点；1.0仅表示规范化后完全相同。"""

    admission_texts = tuple(
        _clean(row.get("history_of_present_illness"))
        for row in _source_rows(documents, "admission_record")
        if _clean(row.get("history_of_present_illness"))
    )
    first_course_texts = tuple(
        _clean(row.get("case_characteristic"))
        for row in _source_rows(documents, "first_course_record")
        if _clean(row.get("case_characteristic"))
    )
    if not admission_texts or not first_course_texts:
        return None
    maximum = 0.0
    for admission_text in admission_texts:
        normalized_admission = _normalized_for_exact_section_comparison(admission_text)
        if not normalized_admission:
            continue
        for first_course_text in first_course_texts:
            normalized_first = _normalized_for_exact_section_comparison(first_course_text)
            if not normalized_first:
                continue
            maximum = max(
                maximum,
                SequenceMatcher(
                    None, normalized_admission, normalized_first, autojunk=False
                ).ratio(),
            )
    return maximum


def _rule_016_customer_display_facts(
    documents: Mapping[str, Any],
    *,
    copy_coverage: float,
) -> Mapping[str, Any]:
    """仅投影比对范围、完全相同结论和可定位文书 ID，不返回正文。"""

    source_document_ids = [
        document_id
        for source_key in ("admission_record", "first_course_record")
        for row in _source_rows(documents, source_key)
        if (document_id := _clean(row.get("document_id")))
    ]
    return {
        "failure_kind": (
            "admission_first_course_copy_detected"
            if copy_coverage >= _RULE_016_EXACT_MATCH
            else "admission_first_course_not_identical"
        ),
        "copy_similarity": round(copy_coverage, 4),
        "copy_relation": (
            "completely_identical"
            if copy_coverage >= _RULE_016_EXACT_MATCH
            else "not_completely_identical"
        ),
        "compared_sections": ["入院记录现病史", "首次病程记录病例特点"],
        "source_document_ids": list(dict.fromkeys(source_document_ids)),
    }


def _is_copy_template_shell(normalized_content: str) -> bool:
    """只识别经人工确认的通用模板壳，未知内容一律不作豁免。"""

    remaining = normalized_content
    for phrase in _COPY_TEMPLATE_SHELL_PHRASES:
        remaining = remaining.replace(phrase, "")
    return not remaining


def _material_for_copy_coverage(normalized_content: str) -> str:
    """从相似度中排除已确认的模板壳，避免模板重复掩盖实质变化。"""

    remaining = normalized_content
    for phrase in _COPY_TEMPLATE_SHELL_PHRASES:
        remaining = remaining.replace(phrase, "")
    return remaining


@dataclass(frozen=True)
class _CopyRuleOutcome:
    status: str
    reason_code: str
    executor_type: str
    safe_metadata: Mapping[str, Any]
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    api_time: float = 0.0
    findings: str = ""
    evidence: str = ""
    suggestion: str = ""
    confidence: float | None = None
    copy_match_document_fingerprints: tuple[tuple[str, str], ...] = ()
def _copy_similarity_band(value: float) -> str:
    return "threshold_exceeded" if value >= _COPY_SIMILARITY_THRESHOLD else "within_threshold"


def _copy_fast_signature(normalized_content: str) -> frozenset[str]:
    """生成轻量字符指纹；只用于候选排序，不参与最终质控结论。"""

    material = _material_for_copy_coverage(normalized_content)
    if len(material) <= _COPY_FAST_SHINGLE_CHARS:
        return frozenset({material}) if material else frozenset()
    return frozenset(
        material[index : index + _COPY_FAST_SHINGLE_CHARS]
        for index in range(len(material) - _COPY_FAST_SHINGLE_CHARS + 1)
    )


def _copy_fast_similarity(left: frozenset[str], right: frozenset[str]) -> float:
    """以 Dice 系数筛出疑似重复组合；精确相似度仍由 SequenceMatcher 裁决。"""

    if not left or not right:
        return 0.0
    return (2.0 * len(left.intersection(right))) / (len(left) + len(right))


def _assess_copy(
    documents: Mapping[str, Any],
    *,
    source_complete: bool = False,
) -> _CopyRuleOutcome:
    """先全组合轻量筛选，再对最高疑似组合执行受控精确比较。"""

    rows = _substantive_rows(
        documents,
        RULE_017_COPY_SOURCES,
        limit_per_source=None if source_complete else _MAX_ROWS_PER_SOURCE,
    )
    comparable: list[
        tuple[datetime, str, str, bool, str, str, Mapping[str, Any]]
    ] = []
    seen_document_ids: set[str] = set()
    missing_time_count = 0
    for source_key, row, content in rows:
        if _clean(row.get("document_title")) == "长期医嘱":
            continue
        normalized = _normalized_for_similarity(content)
        if len(normalized) < _MIN_COMPARABLE_CHARS:
            continue
        record_time = _authoritative_course_time(
            authoritative_document_time_value(row)
        )
        if record_time is None:
            missing_time_count += 1
            continue
        document_id = _clean(row.get("document_id"))
        if document_id and document_id in seen_document_ids:
            continue
        if document_id:
            seen_document_ids.add(document_id)
        comparable.append(
            (
                record_time,
                source_key,
                normalized,
                _is_copy_template_shell(normalized),
                content,
                document_id,
                row,
            )
        )

    safe_metadata: dict[str, Any] = {
        "comparable_document_count": len(comparable),
        "missing_time_document_count": missing_time_count,
        "maximum_similarity": 0.0,
        "similarity_threshold": _COPY_SIMILARITY_THRESHOLD,
        "similarity_band": "unknown",
        "best_match_source_types": [],
        "best_match_record_times": [],
        "best_match_pairs": [],
        "screened_pair_count": 0,
        "precise_pair_count": 0,
        "template_shell_only": False,
    }
    if len(comparable) < 2:
        return _CopyRuleOutcome(
            status="data_gap" if missing_time_count else "not_applicable",
            reason_code="copy_authoritative_time_missing" if missing_time_count else "insufficient_independent_course_records",
            executor_type="program",
            safe_metadata=safe_metadata,
        )

    ordered = sorted(comparable, key=lambda item: (item[0], item[1], item[2]))
    signatures = [_copy_fast_signature(item[2]) for item in ordered]
    candidate_heap: list[tuple[float, int, int, int, int]] = []
    screened_pair_count = 0
    for left_index in range(len(ordered) - 1):
        for right_index in range(left_index + 1, len(ordered)):
            # 017 的可比边界是同一次住院内两份独立病程的权威记录时间，
            # 不是自然日。相同日期但先后完成的两份文书仍需比较；完全同一
            # 时间戳则没有权威先后关系，不能借内存排序伪造相邻顺序。
            if ordered[left_index][0] >= ordered[right_index][0]:
                continue
            screened_pair_count += 1
            fast_score = _copy_fast_similarity(
                signatures[left_index], signatures[right_index]
            )
            candidate = (
                fast_score,
                -left_index,
                -right_index,
                left_index,
                right_index,
            )
            if len(candidate_heap) < _COPY_PRECISE_CANDIDATE_LIMIT:
                heapq.heappush(candidate_heap, candidate)
            elif candidate[:3] > candidate_heap[0][:3]:
                heapq.heapreplace(candidate_heap, candidate)

    if not candidate_heap:
        # 有两份独立、可比较的病程，但权威时间完全相同，无法建立先后关系。
        # 这不是规则不适用；不得用内存或文本排序伪造顺序。
        if len(comparable) >= 2 and screened_pair_count == 0:
            return _CopyRuleOutcome(
                status="data_gap",
                reason_code="copy_authoritative_time_missing" if missing_time_count else "copy_authoritative_time_ambiguous",
                executor_type="program",
                safe_metadata=safe_metadata,
            )
        return _CopyRuleOutcome(
            status="not_applicable",
            reason_code="copy_adjacent_day_pair_unavailable",
            executor_type="program",
            safe_metadata=safe_metadata,
        )

    precise_pairs: list[
        tuple[
            float,
            tuple[datetime, str, str, bool, str, str, Mapping[str, Any]],
            tuple[datetime, str, str, bool, str, str, Mapping[str, Any]],
        ]
    ] = []
    for _, _, _, left_index, right_index in candidate_heap:
        left = ordered[left_index]
        right = ordered[right_index]
        similarity = SequenceMatcher(None, left[2], right[2], autojunk=False).ratio()
        precise_pairs.append((similarity, left, right))
    precise_pairs.sort(
        key=lambda item: (
            -item[0],
            item[1][0],
            item[2][0],
            item[1][1],
            item[2][1],
        )
    )

    maximum = -1.0
    best_pair: tuple[
        tuple[datetime, str, str, bool, str, str, Mapping[str, Any]],
        tuple[datetime, str, str, bool, str, str, Mapping[str, Any]],
    ] | None = None
    longest_block = 0
    substantial_coverage = 0.0
    template_shell_only = False
    for similarity, left, right in precise_pairs:
        matcher = SequenceMatcher(None, left[2], right[2], autojunk=False)
        if similarity <= maximum:
            continue
        maximum = similarity
        best_pair = (left, right)
        template_shell_only = left[3] and right[3]
        blocks = [block.size for block in matcher.get_matching_blocks() if block.size]
        longest_block = max(blocks, default=0)
        material_matcher = SequenceMatcher(
            None,
            _material_for_copy_coverage(left[2]),
            _material_for_copy_coverage(right[2]),
            autojunk=False,
        )
        material_chars = sum(
            block.size for block in material_matcher.get_matching_blocks() if block.size
        )
        material_min_length = min(
            len(_material_for_copy_coverage(left[2])),
            len(_material_for_copy_coverage(right[2])),
        )
        substantial_coverage = material_chars / max(1, material_min_length)

    maximum = max(maximum, 0.0)
    best_match_pairs = [
        {
            "source_types": [left[1], right[1]],
            "record_times": [
                left[0].strftime("%Y-%m-%d %H:%M:%S"),
                right[0].strftime("%Y-%m-%d %H:%M:%S"),
            ],
            "similarity": round(similarity, 4),
        }
        for similarity, left, right in precise_pairs
        if similarity >= _COPY_SIMILARITY_THRESHOLD
    ][:_COPY_DISPLAY_PAIR_LIMIT]
    evidence_pairs = [
        (left, right)
        for similarity, left, right in precise_pairs
        if similarity >= _COPY_SIMILARITY_THRESHOLD
    ][:_COPY_DISPLAY_PAIR_LIMIT]
    if not evidence_pairs and best_pair is not None:
        evidence_pairs = [best_pair]
    occurrence_counts: dict[tuple[str, datetime], int] = {}
    for item in comparable:
        key = (item[1], item[0])
        occurrence_counts[key] = occurrence_counts.get(key, 0) + 1
    ambiguous_selected_time = any(
        occurrence_counts.get((item[1], item[0]), 0) > 1
        for pair in evidence_pairs
        for item in pair
    )
    copy_match_document_fingerprints = (
        tuple(
            tuple(
                _copy_document_fingerprint(
                    source_key=item[1],
                    document_id=item[5],
                )
                for item in pair
            )
            for pair in evidence_pairs
        )
        if ambiguous_selected_time
        else ()
    )
    safe_metadata.update(
        {
            "maximum_similarity": round(maximum, 4),
            "similarity_band": _copy_similarity_band(maximum),
            "best_match_source_types": [best_pair[0][1], best_pair[1][1]] if best_pair else [],
            "best_match_record_times": [
                best_pair[0][0].strftime("%Y-%m-%d %H:%M:%S"),
                best_pair[1][0].strftime("%Y-%m-%d %H:%M:%S"),
            ] if best_pair else [],
            "best_match_pairs": best_match_pairs,
            "screened_pair_count": screened_pair_count,
            "precise_pair_count": len(precise_pairs),
            "longest_matching_block_chars": longest_block,
            "substantial_matching_coverage": round(substantial_coverage, 4),
            "template_shell_only": template_shell_only,
        }
    )
    assert best_pair is not None

    def duplicate_save(left: Any, right: Any) -> bool:
        return (
            left[1] == right[1]
            and left[0].date() == right[0].date()
            and abs((left[0] - right[0]).total_seconds()) <= _COPY_DUPLICATE_SAVE_MAX_SECONDS
        )

    duplicate_pairs = [
        (similarity, left, right)
        for similarity, left, right in precise_pairs
        if similarity >= _COPY_SIMILARITY_THRESHOLD and duplicate_save(left, right)
    ]
    precise_pairs = [
        item for item in precise_pairs
        if not (item[0] >= _COPY_SIMILARITY_THRESHOLD and duplicate_save(item[1], item[2]))
    ]
    if duplicate_pairs and not any(
        similarity >= _COPY_SIMILARITY_THRESHOLD for similarity, _left, _right in precise_pairs
    ) and not missing_time_count:
        similarity, left, right = max(duplicate_pairs, key=lambda item: item[0])
        safe_metadata.update({
            "maximum_similarity": round(similarity, 4),
            "best_match_source_types": [left[1], right[1]],
            "best_match_record_times": [
                left[0].strftime("%Y-%m-%d %H:%M:%S"),
                right[0].strftime("%Y-%m-%d %H:%M:%S"),
            ],
            "best_match_pairs": [],
        })
        return _CopyRuleOutcome(
            status="compliant",
            reason_code=_COPY_DUPLICATE_SAVE_SUSPECTED_REASON,
            executor_type="program",
            safe_metadata=safe_metadata,
        )
    if duplicate_pairs and best_pair is not None and duplicate_save(best_pair[0], best_pair[1]):
        # 最高相似对为疑似重复保存时，不能据其走“全文完全相同即复制”的程序分支。
        best_pair = None
    # 用户口径（2026-10-20）：按客户原文“2次以上病程记录完全相同（相似度大于70%）”判定，
    # 不再区分模板与实质内容，也不调用模型复核；任一组独立病程相似度达到阈值即不合规。
    threshold_pairs = [
        (similarity, left, right)
        for similarity, left, right in precise_pairs
        if similarity >= _COPY_SIMILARITY_THRESHOLD
    ]
    if threshold_pairs:
        top_similarity, top_left, top_right = threshold_pairs[0]
        safe_metadata.update({
            "maximum_similarity": round(top_similarity, 4),
            "similarity_band": _copy_similarity_band(top_similarity),
            "best_match_source_types": [top_left[1], top_right[1]],
            "best_match_record_times": [
                top_left[0].strftime("%Y-%m-%d %H:%M:%S"),
                top_right[0].strftime("%Y-%m-%d %H:%M:%S"),
            ],
            "best_match_pairs": [
                {
                    "source_types": [left[1], right[1]],
                    "record_times": [
                        left[0].strftime("%Y-%m-%d %H:%M:%S"),
                        right[0].strftime("%Y-%m-%d %H:%M:%S"),
                    ],
                    "similarity": round(similarity, 4),
                }
                for similarity, left, right in threshold_pairs[:_COPY_DISPLAY_PAIR_LIMIT]
            ],
        })
        return _CopyRuleOutcome(
            status="non_compliant",
            reason_code="copy_similarity_threshold_exceeded",
            executor_type="program",
            safe_metadata=safe_metadata,
            copy_match_document_fingerprints=copy_match_document_fingerprints,
        )

    # 未达阈值时其余文书缺时不能据部分材料放行；本分支保持零模型调用。
    if missing_time_count:
        return _CopyRuleOutcome(
            status="data_gap",
            reason_code="copy_authoritative_time_missing",
            executor_type="program",
            safe_metadata=safe_metadata,
        )
    return _CopyRuleOutcome(
        status="compliant",
        reason_code="copy_similarity_within_threshold",
        executor_type="program",
        safe_metadata=safe_metadata,
        copy_match_document_fingerprints=copy_match_document_fingerprints,
    )


def _copy_customer_display_facts(outcome: _CopyRuleOutcome) -> Mapping[str, Any] | None:
    """017 仅投影可复核的比较对象和阈值，正文始终留在请求内材料仓。"""

    metadata = outcome.safe_metadata
    source_types = metadata.get("best_match_source_types")
    record_times = metadata.get("best_match_record_times")
    maximum = metadata.get("maximum_similarity")
    threshold = metadata.get("similarity_threshold")
    if (
        outcome.status not in {"compliant", "non_compliant"}
        or not isinstance(source_types, list)
        or len(source_types) != 2
        or any(value not in RULE_017_COPY_SOURCES for value in source_types)
        or not isinstance(record_times, list)
        or len(record_times) != 2
        or not all(isinstance(value, str) and value for value in record_times)
        or not isinstance(maximum, (int, float))
        or not isinstance(threshold, (int, float))
    ):
        return None
    if outcome.status == "non_compliant":
        if float(maximum) < float(threshold):
            return None
        failure_kind = "copy_similarity_threshold_exceeded"
    elif outcome.reason_code == _COPY_SEMANTIC_REVIEW_PASSED_REASON:
        if float(maximum) < float(threshold):
            return None
        failure_kind = _COPY_SEMANTIC_REVIEW_PASSED_REASON
    elif outcome.reason_code == _COPY_TEMPLATE_SHELL_ONLY_REASON:
        if float(maximum) < float(threshold):
            return None
        failure_kind = _COPY_TEMPLATE_SHELL_ONLY_REASON
    elif outcome.reason_code == _COPY_DUPLICATE_SAVE_SUSPECTED_REASON:
        if float(maximum) < float(threshold):
            return None
        failure_kind = _COPY_DUPLICATE_SAVE_SUSPECTED_REASON
    elif outcome.reason_code == "copy_similarity_within_threshold":
        if float(maximum) >= float(threshold):
            return None
        failure_kind = "copy_similarity_within_threshold"
    else:
        return None
    facts = {
        "failure_kind": failure_kind,
        "copy_similarity": round(float(maximum), 4),
        "copy_similarity_threshold": round(float(threshold), 4),
        "copy_document_sources": list(source_types),
        "copy_document_record_times": list(record_times),
        "copy_match_pairs": [dict(item) for item in metadata.get("best_match_pairs", [])],
    }
    if outcome.copy_match_document_fingerprints:
        facts["copy_match_document_fingerprints"] = [
            list(pair) for pair in outcome.copy_match_document_fingerprints
        ]
    return facts


def _copy_document_fingerprint(*, source_key: str, document_id: Any) -> str:
    """复用既有复制匹配指纹，仅用于同源同刻的内部消歧。"""

    document_id = _clean(document_id)
    if not document_id:
        return ""
    return "sha256:" + hashlib.sha256(
        f"{source_key}\0{document_id}".encode("utf-8")
    ).hexdigest()


def _selected_copy_document_refs(
    *,
    outcome: _CopyRuleOutcome,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
) -> tuple[str, ...]:
    """把实际命中的复制文书对收敛为公共投影可消费的 material refs。

    ``best_match_pairs`` 已经是本规则作出结论时的最多四组候选。相同来源、
    相同权威时间的多份文书只在结果携带既有内部指纹时消歧；不能消歧时宁可
    不投影，避免聚合器再按日期/指纹反查或猜测客户证据。
    """

    rows_by_coordinate: dict[tuple[str, str], list[tuple[str, Mapping[str, Any]]]] = {}
    try:
        for source_key in RULE_017_COPY_SOURCES:
            for document_ref, row in materials.document_rows(
                source_key,
                snapshot=snapshot,
            ):
                record_time = _authoritative_course_time(
                    authoritative_document_time_value(row)
                )
                if record_time is None:
                    continue
                coordinate = (
                    source_key,
                    record_time.strftime("%Y-%m-%d %H:%M:%S"),
                )
                rows_by_coordinate.setdefault(coordinate, []).append(
                    (document_ref, row)
                )
    except Exception:
        return ()

    metadata = outcome.safe_metadata
    raw_pairs = metadata.get("best_match_pairs")
    pairs = raw_pairs if isinstance(raw_pairs, list) else []
    if not pairs:
        source_types = metadata.get("best_match_source_types")
        record_times = metadata.get("best_match_record_times")
        if (
            isinstance(source_types, list)
            and isinstance(record_times, list)
            and len(source_types) == len(record_times) == 2
        ):
            pairs = [{"source_types": source_types, "record_times": record_times}]

    refs: list[str] = []
    fingerprints = outcome.copy_match_document_fingerprints
    for pair_index, pair in enumerate(pairs[:_COPY_DISPLAY_PAIR_LIMIT]):
        if not isinstance(pair, Mapping):
            continue
        source_types = pair.get("source_types")
        record_times = pair.get("record_times")
        if (
            not isinstance(source_types, list)
            or not isinstance(record_times, list)
            or len(source_types) != 2
            or len(record_times) != 2
        ):
            continue
        pair_fingerprints = (
            fingerprints[pair_index]
            if pair_index < len(fingerprints)
            else ()
        )
        for position, (source_key, record_time) in enumerate(
            zip(source_types, record_times)
        ):
            candidates = rows_by_coordinate.get(
                (str(source_key), str(record_time)),
                [],
            )
            if len(candidates) == 1:
                refs.append(candidates[0][0])
                continue
            fingerprint = (
                pair_fingerprints[position]
                if position < len(pair_fingerprints)
                else ""
            )
            matched = [
                document_ref
                for document_ref, row in candidates
                if fingerprint
                and _copy_document_fingerprint(
                    source_key=str(source_key),
                    document_id=row.get("document_id"),
                )
                == fingerprint
            ]
            if len(matched) == 1:
                refs.append(matched[0])
    return tuple(dict.fromkeys(refs))


def _rule_017_decision(
    *,
    outcome: _CopyRuleOutcome,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
) -> RuleDecision:
    """从同一材料仓计算出的复制 outcome 直接构造决策。"""

    if (
        type(snapshot) is not Luxian0609EvidenceSnapshot
        or type(materials) is not Luxian0609EvidenceMaterialStore
        or materials.snapshot_hash != snapshot.snapshot_hash
    ):
        raise ValueError("typed 017 evidence session mismatch")
    required_copy_sources = set(RULE_017_COPY_SOURCES)
    observations = tuple(
        item
        for item in snapshot.observations
        if item.source_key in required_copy_sources
    )
    if not required_copy_sources.issubset({item.source_key for item in observations}):
        return RuleDecision(
            rule_id="LX0609-12-01-02",
            snapshot_hash=snapshot.snapshot_hash,
            applicability=ApplicabilityState.ERROR,
            evidence_state=EvidenceState.TECHNICAL_ERROR,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="snapshot_mismatch",
            fact_refs=(),
            evaluator_version="rule017-copy-similarity-v2",
            confidence=None,
        )
    if any(item.query_state.value == "error" for item in observations):
        dimensions = (
            ApplicabilityState.ERROR,
            EvidenceState.TECHNICAL_ERROR,
            QcDirection.UNKNOWN,
            "source_query_error",
        )
    elif any(item.query_state.value == "unavailable" for item in observations):
        dimensions = (
            ApplicabilityState.UNKNOWN,
            EvidenceState.DATA_GAP,
            QcDirection.UNKNOWN,
            "source_unavailable",
        )
    elif any(item.completeness.value == "truncated" for item in observations):
        dimensions = (
            ApplicabilityState.UNKNOWN,
            EvidenceState.DATA_GAP,
            QcDirection.UNKNOWN,
            "source_truncated",
        )
    elif outcome.status == "compliant":
        dimensions = (
            ApplicabilityState.APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.SATISFIED,
            (
                "requirement_satisfied"
                if outcome.reason_code
                in {
                    _COPY_SEMANTIC_REVIEW_PASSED_REASON,
                    _COPY_TEMPLATE_SHELL_ONLY_REASON,
                    _COPY_DUPLICATE_SAVE_SUSPECTED_REASON,
                }
                else "requirement_within_threshold"
            ),
        )
    elif outcome.status == "non_compliant":
        dimensions = (
            ApplicabilityState.APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.DEFECT,
            "threshold_exceeded",
        )
    elif outcome.status == "not_applicable":
        dimensions = (
            ApplicabilityState.NOT_APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.UNKNOWN,
            "eligibility_not_met",
        )
    elif outcome.status == "evaluation_unknown":
        dimensions = (
            ApplicabilityState.APPLICABLE,
            EvidenceState.CONFLICT,
            QcDirection.UNKNOWN,
            "semantic_low_confidence",
        )
    elif outcome.status == "technical_error":
        dimensions = (
            ApplicabilityState.ERROR,
            EvidenceState.TECHNICAL_ERROR,
            QcDirection.UNKNOWN,
            outcome.reason_code,
        )
    else:
        dimensions = (
            ApplicabilityState.UNKNOWN,
            EvidenceState.DATA_GAP,
            QcDirection.UNKNOWN,
            "required_field_missing",
        )
    applicability, evidence_state, qc_direction, reason_code = dimensions
    selected_refs = _selected_copy_document_refs(
        outcome=outcome,
        snapshot=snapshot,
        materials=materials,
    )
    if not selected_refs and applicability is ApplicabilityState.NOT_APPLICABLE:
        # 完整来源为空时没有真实文书坐标；这里仅保留来源 observation 作为
        # “无第二份独立病程”的否定事实，不能由 Aggregator 再猜测文书。
        selected_refs = tuple(
            item.snapshot_ref.removeprefix("sha256:") for item in observations
        )
    return RuleDecision(
        rule_id="LX0609-12-01-02",
        snapshot_hash=snapshot.snapshot_hash,
        applicability=applicability,
        evidence_state=evidence_state,
        qc_direction=qc_direction,
        reason_code=reason_code,
        fact_refs=selected_refs,
        positive_document_refs=selected_refs if qc_direction is QcDirection.DEFECT else (),
        evaluator_version="rule017-copy-similarity-v2",
        confidence=outcome.confidence,
    )
