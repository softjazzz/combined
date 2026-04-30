from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable, List

from app.services.bundles import load_or_assemble_domain_bundle


DEFAULT_INSTITUTE_ID = "泸县人民医院"
DEFAULT_PATIENT_ID = "0000072496"
DEFAULT_VISIT_ID = "2207717"
DEFAULT_TIME_A = "2026-02-03 11:07:40"
DEFAULT_TIME_B = "2026-02-04 11:08:49"
ROUND_SOURCE_TABLES = {"daily_course_record", "senior_course_record"}


@dataclass
class SentenceMatch:
    source_sentence: str
    matched_sentence: str
    similarity: float


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

    print(f"A: {doc_a.get('document_title')} @ {doc_a.get('display_time')}")
    print(f"B: {doc_b.get('document_title')} @ {doc_b.get('display_time')}")
    print(f"全文 SequenceMatcher 相似度: {full_ratio:.4f}")
    print(f"A 句子数: {len(sentences_a)}")
    print(f"B 句子数: {len(sentences_b)}")
    print(f"A→B 句子覆盖率(threshold={args.threshold:.2f}): {cover_a_to_b:.4f}")
    print(f"B→A 句子覆盖率(threshold={args.threshold:.2f}): {cover_b_to_a:.4f}")
    print(f"双向平均句子覆盖率: {average_cover:.4f}")

    if args.show_matches:
        print("\nA→B 命中句子：")
        for match in _coverage_matches(sentences_a, sentences_b, threshold=args.threshold):
            print(f"- {match.similarity:.3f} | A={match.source_sentence}")
            print(f"           B={match.matched_sentence}")
        print("\nB→A 命中句子：")
        for match in _coverage_matches(sentences_b, sentences_a, threshold=args.threshold):
            print(f"- {match.similarity:.3f} | B={match.source_sentence}")
            print(f"           A={match.matched_sentence}")


if __name__ == "__main__":
    main()
