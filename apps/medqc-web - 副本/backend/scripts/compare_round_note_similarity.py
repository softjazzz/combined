from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from typing import Dict, Iterable, List

from app.services.bundles import load_or_assemble_domain_bundle


DEFAULT_INSTITUTE_ID = "泸县人民医院"
DEFAULT_PATIENT_ID = "0000072496"
DEFAULT_VISIT_ID = "2207717"
DEFAULT_TIME_A = "2026-02-03 11:07:40"
DEFAULT_TIME_B = "2026-02-04 11:08:49"
ROUND_SOURCE_TABLES = {"daily_course_record", "senior_course_record"}
SECTION_PATTERNS: List[tuple[str, str]] = [
    ("入院症见", r"入院症见[:：]"),
    ("体格检查", r"体格检查[:：]"),
    ("辅助检查", r"(?:院内)?辅助检查[:：]"),
    ("诊断", r"(?:目前患者)?诊断[:：]|初步诊断[:：]"),
    ("诊断依据", r"诊断依据[:：]"),
    ("鉴别诊断", r"鉴别诊断[:：]"),
    ("治疗经过", r"入院后给予|目前治疗上|治疗上给予|治疗上"),
    ("病情变化", r"患者神清，精神可"),
    ("查体", r"查体[:：]"),
    ("会诊建议", r"请感染科会诊"),
]
SECTION_WEIGHTS: Dict[str, float] = {
    "入院症见": 1.0,
    "体格检查": 1.0,
    "辅助检查": 1.0,
    "诊断": 1.5,
    "诊断依据": 1.5,
    "鉴别诊断": 1.0,
    "治疗经过": 1.5,
    "病情变化": 2.0,
    "查体": 2.0,
    "会诊建议": 0.8,
}


@dataclass
class SentenceMatch:
    source_sentence: str
    matched_sentence: str
    similarity: float


@dataclass
class SectionCoverage:
    name: str
    weight: float
    sentence_count: int
    coverage_ratio: float
    source_excerpt: str
    target_excerpt: str


def _normalize_for_full_ratio(text: str) -> str:
    normalized = text or ""
    normalized = normalized.replace("\r", "\n")
    normalized = re.sub(r"\s+", "", normalized)
    return normalized


def _normalize_for_sentence(text: str) -> str:
    normalized = text or ""
    normalized = normalized.replace("\r", "\n")
    normalized = re.sub(r"医生签名[:：].*$", "", normalized)
    normalized = re.sub(r"[ \t]+", "", normalized)
    normalized = re.sub(r"\n+", "\n", normalized)
    normalized = re.sub(r"^\:+", "", normalized)
    return normalized.strip()


def _split_sentences(text: str) -> List[str]:
    normalized = _normalize_for_sentence(text)
    parts = re.split(r"[。；;\n]+", normalized)
    sentences: List[str] = []
    for part in parts:
        sentence = part.strip("：:，, ")
        if not sentence:
            continue
        if len(sentence) < 8:
            continue
        sentences.append(sentence)
    return sentences


def _sentence_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _coverage_matches(
    source_sentences: Iterable[str],
    target_sentences: Iterable[str],
    *,
    threshold: float,
) -> List[SentenceMatch]:
    target_list = list(target_sentences)
    matches: List[SentenceMatch] = []
    for source_sentence in source_sentences:
        best_sentence = ""
        best_ratio = 0.0
        for target_sentence in target_list:
            ratio = _sentence_similarity(source_sentence, target_sentence)
            if ratio > best_ratio:
                best_ratio = ratio
                best_sentence = target_sentence
        if best_ratio >= threshold:
            matches.append(
                SentenceMatch(
                    source_sentence=source_sentence,
                    matched_sentence=best_sentence,
                    similarity=best_ratio,
                )
            )
    return matches


def _coverage_ratio(source_sentences: List[str], target_sentences: List[str], *, threshold: float) -> float:
    if not source_sentences:
        return 0.0
    matches = _coverage_matches(source_sentences, target_sentences, threshold=threshold)
    return len(matches) / len(source_sentences)


def _parse_display_time(value: str) -> datetime:
    return datetime.strptime(str(value or "").strip(), "%Y-%m-%d %H:%M:%S")


def _extract_sections(text: str) -> Dict[str, str]:
    normalized = _normalize_for_sentence(text)
    located: List[tuple[int, int, str]] = []
    used_starts: set[tuple[int, str]] = set()
    for name, pattern in SECTION_PATTERNS:
        match = re.search(pattern, normalized)
        if not match:
            continue
        key = (match.start(), name)
        if key in used_starts:
            continue
        used_starts.add(key)
        located.append((match.start(), match.end(), name))

    located.sort(key=lambda item: item[0])
    sections: Dict[str, str] = {}
    for index, (start, _end, name) in enumerate(located):
        next_start = located[index + 1][0] if index + 1 < len(located) else len(normalized)
        section_text = normalized[start:next_start].strip()
        if section_text:
            sections[name] = section_text
    return sections


def _weighted_section_coverages(
    source_text: str,
    target_text: str,
    *,
    threshold: float,
) -> List[SectionCoverage]:
    source_sections = _extract_sections(source_text)
    target_sections = _extract_sections(target_text)
    rows: List[SectionCoverage] = []
    for name, source_section in source_sections.items():
        target_section = target_sections.get(name, "")
        source_sentences = _split_sentences(source_section)
        target_sentences = _split_sentences(target_section)
        coverage = _coverage_ratio(source_sentences, target_sentences, threshold=threshold)
        rows.append(
            SectionCoverage(
                name=name,
                weight=float(SECTION_WEIGHTS.get(name, 1.0)),
                sentence_count=len(source_sentences),
                coverage_ratio=coverage,
                source_excerpt=source_section[:120],
                target_excerpt=target_section[:120],
            )
        )
    return rows


def _weighted_average(rows: List[SectionCoverage]) -> float:
    effective_rows = [row for row in rows if row.sentence_count > 0]
    if not effective_rows:
        return 0.0
    total_weight = sum(row.weight for row in effective_rows)
    if total_weight <= 0:
        return 0.0
    return sum(row.coverage_ratio * row.weight for row in effective_rows) / total_weight


def _load_document_by_time(*, institute_id: str, patient_id: str, visit_id: str, display_time: str) -> dict:
    bundle = load_or_assemble_domain_bundle(
        execution_domain="course",
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
        source_schema="cdm",
        bundle_schema="public",
        force_refresh=False,
    )
    for doc in bundle.get("source_documents") or []:
        if str(doc.get("source_table") or "") not in ROUND_SOURCE_TABLES:
            continue
        if str(doc.get("display_time") or "") == display_time:
            return dict(doc)
    raise LookupError(f"未找到 display_time={display_time} 的查房文书")


def main() -> None:
    parser = argparse.ArgumentParser(description="比较两条查房记录的全文相似度与句子覆盖率")
    parser.add_argument("--institute-id", default=DEFAULT_INSTITUTE_ID)
    parser.add_argument("--patient-id", default=DEFAULT_PATIENT_ID)
    parser.add_argument("--visit-id", default=DEFAULT_VISIT_ID)
    parser.add_argument("--time-a", default=DEFAULT_TIME_A)
    parser.add_argument("--time-b", default=DEFAULT_TIME_B)
    parser.add_argument("--threshold", type=float, default=0.85, help="句子匹配阈值，默认 0.85")
    parser.add_argument("--show-matches", action="store_true", help="打印命中的句子对")
    parser.add_argument("--show-sections", action="store_true", help="打印核心段落覆盖率明细")
    args = parser.parse_args()

    doc_a = _load_document_by_time(
        institute_id=args.institute_id,
        patient_id=args.patient_id,
        visit_id=args.visit_id,
        display_time=args.time_a,
    )
    doc_b = _load_document_by_time(
        institute_id=args.institute_id,
        patient_id=args.patient_id,
        visit_id=args.visit_id,
        display_time=args.time_b,
    )

    content_a = str(doc_a.get("content") or "")
    content_b = str(doc_b.get("content") or "")

    full_ratio = SequenceMatcher(
        None,
        _normalize_for_full_ratio(content_a),
        _normalize_for_full_ratio(content_b),
    ).ratio()

    sentences_a = _split_sentences(content_a)
    sentences_b = _split_sentences(content_b)
    cover_a_to_b = _coverage_ratio(sentences_a, sentences_b, threshold=args.threshold)
    cover_b_to_a = _coverage_ratio(sentences_b, sentences_a, threshold=args.threshold)
    average_cover = (cover_a_to_b + cover_b_to_a) / 2 if sentences_a and sentences_b else 0.0
    earlier_doc, later_doc = (doc_a, doc_b)
    earlier_content, later_content = (content_a, content_b)
    if _parse_display_time(str(doc_a.get("display_time") or "")) > _parse_display_time(str(doc_b.get("display_time") or "")):
        earlier_doc, later_doc = (doc_b, doc_a)
        earlier_content, later_content = (content_b, content_a)

    later_to_earlier_cover = _coverage_ratio(
        _split_sentences(later_content),
        _split_sentences(earlier_content),
        threshold=args.threshold,
    )
    weighted_rows = _weighted_section_coverages(
        later_content,
        earlier_content,
        threshold=args.threshold,
    )
    weighted_cover = _weighted_average(weighted_rows)

    print(f"A: {doc_a.get('document_title')} @ {doc_a.get('display_time')}")
    print(f"B: {doc_b.get('document_title')} @ {doc_b.get('display_time')}")
    print(f"全文 SequenceMatcher 相似度: {full_ratio:.4f}")
    print(f"A 句子数: {len(sentences_a)}")
    print(f"B 句子数: {len(sentences_b)}")
    print(f"A→B 句子覆盖率(threshold={args.threshold:.2f}): {cover_a_to_b:.4f}")
    print(f"B→A 句子覆盖率(threshold={args.threshold:.2f}): {cover_b_to_a:.4f}")
    print(f"双向平均句子覆盖率: {average_cover:.4f}")
    print(
        "后一天被前一天覆盖率: "
        f"{later_to_earlier_cover:.4f} "
        f"(later={later_doc.get('display_time')} -> earlier={earlier_doc.get('display_time')})"
    )
    print(f"核心段落加权覆盖率(后一天→前一天): {weighted_cover:.4f}")

    if args.show_matches:
        print("\nA→B 命中句子：")
        for match in _coverage_matches(sentences_a, sentences_b, threshold=args.threshold):
            print(f"- {match.similarity:.3f} | A={match.source_sentence}")
            print(f"           B={match.matched_sentence}")
        print("\nB→A 命中句子：")
        for match in _coverage_matches(sentences_b, sentences_a, threshold=args.threshold):
            print(f"- {match.similarity:.3f} | B={match.source_sentence}")
            print(f"           A={match.matched_sentence}")

    if args.show_sections:
        print("\n核心段落覆盖率（后一天→前一天）：")
        for row in weighted_rows:
            print(
                f"- {row.name}: coverage={row.coverage_ratio:.4f}, "
                f"weight={row.weight:.1f}, sentences={row.sentence_count}"
            )


if __name__ == "__main__":
    main()
