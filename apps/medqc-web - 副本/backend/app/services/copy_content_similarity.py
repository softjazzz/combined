from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any, Dict, Iterable, List, Optional, Sequence


ROUND_SOURCE_TABLES = {"daily_course_record", "senior_course_record"}
FIRST_COURSE_SOURCE_TABLES = {"first_course_record"}
ADMISSION_SOURCE_TABLES = {"admission_record"}

ROUND_SENTENCE_MATCH_THRESHOLD = 0.85

FIRST_COURSE_SECTION_PATTERNS: Dict[str, tuple[str, ...]] = {
    "case_features": (r"(?:病例特点|病例特征)[:：]",),
    "reasoning": (
        r"拟诊讨论[:：]",
        r"诊断依据[:：]",
        r"鉴别诊断[:：]",
        r"(?:结合病史|目前考虑|初步分析)[:：]?",
    ),
    "diagnosis_basis": (r"诊断依据[:：]",),
    "differential": (r"鉴别诊断[:：]",),
    "plan": (r"(?:诊疗计划|治疗计划|处理计划|下一步计划)[:：]",),
}

ADMISSION_SECTION_PATTERNS: Dict[str, tuple[str, ...]] = {
    "chief_complaint": (r"主诉[:：]",),
    "present_illness": (r"现病史[:：]",),
    "physical_exam": (r"(?:体格检查|专科检查|查体)[:：]",),
    "assist_exam": (r"辅助检查[:：]",),
}


@dataclass(frozen=True)
class TextSimilarityMetrics:
    full_similarity_ratio: float
    source_to_target_sentence_coverage: float
    target_to_source_sentence_coverage: float

    @property
    def average_sentence_coverage(self) -> float:
        return round(
            (self.source_to_target_sentence_coverage + self.target_to_source_sentence_coverage) / 2.0,
            4,
        )


def normalize_for_full_ratio(text: str) -> str:
    normalized = str(text or "")
    normalized = normalized.replace("\r", "\n")
    normalized = re.sub(r"\s+", "", normalized)
    return normalized


def normalize_for_sentence(text: str) -> str:
    normalized = str(text or "")
    normalized = normalized.replace("\r", "\n")
    normalized = re.sub(r"医生签名[:：].*$", "", normalized)
    normalized = re.sub(r"[ \t]+", "", normalized)
    normalized = re.sub(r"\n+", "\n", normalized)
    normalized = re.sub(r"^\:+", "", normalized)
    return normalized.strip()


def split_sentences(text: str) -> List[str]:
    normalized = normalize_for_sentence(text)
    parts = re.split(r"[。；;\n]+", normalized)
    sentences: List[str] = []
    for part in parts:
        sentence = part.strip("：:，, ")
        if not sentence or len(sentence) < 8:
            continue
        sentences.append(sentence)
    return sentences


def sentence_similarity(source_text: str, target_text: str) -> float:
    return SequenceMatcher(None, source_text, target_text).ratio()


def sentence_coverage_ratio(
    source_sentences: Sequence[str],
    target_sentences: Sequence[str],
    *,
    threshold: float = ROUND_SENTENCE_MATCH_THRESHOLD,
) -> float:
    if not source_sentences or not target_sentences:
        return 0.0
    matched = 0
    for source_sentence in list(source_sentences):
        best_ratio = 0.0
        for target_sentence in list(target_sentences):
            ratio = sentence_similarity(source_sentence, target_sentence)
            if ratio > best_ratio:
                best_ratio = ratio
        if best_ratio >= threshold:
            matched += 1
    return round(matched / len(list(source_sentences)), 4)


def compare_text_segments(
    source_text: str,
    target_text: str,
    *,
    threshold: float = ROUND_SENTENCE_MATCH_THRESHOLD,
) -> TextSimilarityMetrics:
    source_sentences = split_sentences(source_text)
    target_sentences = split_sentences(target_text)
    return TextSimilarityMetrics(
        full_similarity_ratio=round(
            SequenceMatcher(
                None,
                normalize_for_full_ratio(source_text),
                normalize_for_full_ratio(target_text),
            ).ratio(),
            4,
        ),
        source_to_target_sentence_coverage=sentence_coverage_ratio(
            source_sentences,
            target_sentences,
            threshold=threshold,
        ),
        target_to_source_sentence_coverage=sentence_coverage_ratio(
            target_sentences,
            source_sentences,
            threshold=threshold,
        ),
    )


def parse_document_datetime(value: Any) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _locate_section_ranges(
    text: str,
    section_patterns: Dict[str, tuple[str, ...]],
) -> List[tuple[int, int, str]]:
    normalized = normalize_for_sentence(text)
    located: List[tuple[int, int, str]] = []
    used_starts: set[tuple[int, str]] = set()
    for key, patterns in section_patterns.items():
        for pattern in patterns:
            match = re.search(pattern, normalized)
            if not match:
                continue
            dedupe_key = (match.start(), key)
            if dedupe_key in used_starts:
                continue
            used_starts.add(dedupe_key)
            located.append((match.start(), match.end(), key))
            break
    located.sort(key=lambda item: item[0])
    return located


def _extract_sections(
    text: str,
    section_patterns: Dict[str, tuple[str, ...]],
) -> Dict[str, str]:
    normalized = normalize_for_sentence(text)
    located = _locate_section_ranges(normalized, section_patterns)
    sections: Dict[str, str] = {}
    for index, (_start, end, key) in enumerate(located):
        next_start = located[index + 1][0] if index + 1 < len(located) else len(normalized)
        section_text = normalized[end:next_start].strip()
        if section_text:
            sections[key] = section_text
    return sections


def extract_first_course_sections(text: str) -> Dict[str, str]:
    sections = _extract_sections(text, FIRST_COURSE_SECTION_PATTERNS)
    reasoning_parts: List[str] = []
    for key in ("reasoning", "diagnosis_basis", "differential"):
        content = str(sections.get(key) or "").strip()
        if content:
            reasoning_parts.append(content)
    sections["reasoning_candidate"] = "\n".join(reasoning_parts).strip()
    sections["case_features_candidate"] = str(sections.get("case_features") or "").strip()
    sections["plan_candidate"] = str(sections.get("plan") or "").strip()
    return sections


def extract_admission_sections(text: str) -> Dict[str, str]:
    sections = _extract_sections(text, ADMISSION_SECTION_PATTERNS)
    symptom_parts: List[str] = []
    for key in ("chief_complaint", "present_illness", "physical_exam"):
        content = str(sections.get(key) or "").strip()
        if content:
            symptom_parts.append(content)
    sections["symptom_body_signs_candidate"] = "\n".join(symptom_parts).strip()
    sections["present_illness_candidate"] = str(sections.get("present_illness") or "").strip()
    return sections


def select_best_lookback_match(
    *,
    primary_document: Dict[str, Any],
    candidate_documents: Sequence[Dict[str, Any]],
    allowed_source_tables: Iterable[str],
    lookback_count: int,
    sentence_threshold: float = ROUND_SENTENCE_MATCH_THRESHOLD,
    min_full_similarity: float = 0.3,
) -> Optional[Dict[str, Any]]:
    allowed = {str(item or "").strip() for item in allowed_source_tables if str(item or "").strip()}
    primary_source_table = str(primary_document.get("source_table") or primary_document.get("document_type") or "").strip()
    primary_content = str(primary_document.get("content") or primary_document.get("text_preview") or "").strip()
    if allowed and primary_source_table not in allowed:
        return None
    if not primary_content:
        return None

    primary_dt = parse_document_datetime(primary_document.get("display_time") or primary_document.get("record_time"))
    primary_id = str(primary_document.get("document_id") or primary_document.get("id") or "").strip()

    prior_documents: List[tuple[Optional[datetime], Dict[str, Any]]] = []
    for item in list(candidate_documents or []):
        source_table = str(item.get("source_table") or item.get("document_type") or "").strip()
        if allowed and source_table not in allowed:
            continue
        compare_content = str(item.get("content") or item.get("text_preview") or "").strip()
        if not compare_content:
            continue
        compare_id = str(item.get("document_id") or item.get("id") or "").strip()
        compare_time = str(item.get("display_time") or item.get("record_time") or "").strip()
        if compare_id and primary_id and compare_id == primary_id:
            continue
        compare_dt = parse_document_datetime(compare_time)
        if primary_dt is not None and compare_dt is not None:
            delta_seconds = (primary_dt - compare_dt).total_seconds()
            if delta_seconds <= 0:
                continue
        prior_documents.append((compare_dt, dict(item)))

    if not prior_documents:
        return None

    prior_documents.sort(
        key=lambda pair: pair[0] or datetime.min,
        reverse=True,
    )
    lookback_documents = [item for _dt, item in prior_documents[: max(1, int(lookback_count or 1))]]

    candidates: List[Dict[str, Any]] = []
    for item in lookback_documents:
        compare_content = str(item.get("content") or item.get("text_preview") or "").strip()
        metrics = compare_text_segments(
            primary_content,
            compare_content,
            threshold=sentence_threshold,
        )
        if metrics.full_similarity_ratio < min_full_similarity:
            continue
        compare_time = str(item.get("display_time") or item.get("record_time") or "").strip()
        compare_dt = parse_document_datetime(compare_time)
        time_gap_hours = None
        if primary_dt is not None and compare_dt is not None:
            time_gap_hours = round(abs((primary_dt - compare_dt).total_seconds()) / 3600.0, 2)
        candidates.append(
            {
                "compare_document": dict(item),
                "full_similarity_ratio": metrics.full_similarity_ratio,
                "source_to_target_sentence_coverage": metrics.source_to_target_sentence_coverage,
                "target_to_source_sentence_coverage": metrics.target_to_source_sentence_coverage,
                "average_sentence_coverage": metrics.average_sentence_coverage,
                "time_gap_hours": time_gap_hours,
            }
        )

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: (
            float(item.get("source_to_target_sentence_coverage") or 0.0),
            float(item.get("full_similarity_ratio") or 0.0),
            -float(item.get("time_gap_hours") or 9999.0),
        ),
        reverse=True,
    )
    return candidates[0]
