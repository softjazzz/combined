from __future__ import annotations

"""
Non-SSE admission diagnosis extraction script.

This script reuses the same diagnosis prompt + JSON parser path used by
homepage generation, but only runs diagnosis extraction (single call),
then maps output into admission-oriented fields.
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple


# Some environments require this setting on import.
os.environ.setdefault("JWT_SECRET", "dev-script-secret")

# Ensure `backend/app` is importable when script is executed from repo root.
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = SCRIPT_DIR.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.frontpage_extraction_service import (  # noqa: E402
    DIAGNOSES_PROMPT,
    default_frontpage_service,
)


def _dedupe_non_empty(values: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in values:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _extract_admission_diagnoses_from_text(medical_text: str) -> List[str]:
    if not medical_text:
        return []

    diag_titles = r"(?:初步诊断|入院诊断|门诊诊断|急诊诊断|目前诊断)"
    stop_titles = r"(?:诊疗计划|治疗计划|治疗方案|拟行|手术|签名|医师|$)"
    m = re.search(rf"{diag_titles}\s*[:：]\s*([\s\S]*?)(?={stop_titles})", medical_text, re.IGNORECASE)
    block = (m.group(1) or "") if m else ""

    if block:
        numbered = re.findall(r"(?:^|\n)\s*\d{1,2}[\.、\)]\s*([^\n\r]+)", block)
        if numbered:
            return _dedupe_non_empty(numbered)

        raw_lines = re.split(r"[\n；;]", block)
        cleaned = []
        for line in raw_lines:
            text = re.sub(r"^\s*\d{1,2}[\.、\)]\s*", "", line).strip()
            if text:
                cleaned.append(text)
        deduped = _dedupe_non_empty(cleaned)
        if deduped:
            return deduped

    # Fallback: global numbered diagnosis lines.
    global_numbered = re.findall(r"(?:^|\n)\s*\d{1,2}[\.、\)]\s*([^\n\r]+)", medical_text)
    if global_numbered:
        return _dedupe_non_empty(global_numbered)

    return []


def _pick_admission_diagnoses(
    llm_diagnoses: Dict[str, Any],
    medical_text: str,
) -> Tuple[List[str], str]:
    # Preferred source from homepage prompt contract.
    ed_texts = llm_diagnoses.get("ed_diagnosis_texts")
    if isinstance(ed_texts, list):
        ed_clean = _dedupe_non_empty([str(x) for x in ed_texts])
        if ed_clean:
            return ed_clean, "llm.ed_diagnosis_texts"

    # Secondary source from discharge fields, if LLM only filled those.
    main = str(llm_diagnoses.get("discharge_main_diagnosis_text") or "").strip()
    others_raw = llm_diagnoses.get("discharge_other_diagnoses_texts")
    others = [str(x).strip() for x in others_raw] if isinstance(others_raw, list) else []
    others = _dedupe_non_empty(others)
    if main:
        return _dedupe_non_empty([main, *others]), "llm.discharge_fields"

    # Last resort from raw text.
    parsed = _extract_admission_diagnoses_from_text(medical_text)
    if parsed:
        return parsed, "text.regex_fallback"

    return [], "empty"


async def extract_admission_diagnosis_non_sse(medical_text: str) -> Dict[str, Any]:
    service = default_frontpage_service
    t0 = time.perf_counter()

    prompt = DIAGNOSES_PROMPT.format(medical_text=medical_text)
    llm_diagnoses = await service._extract_json(prompt) or {}
    if not isinstance(llm_diagnoses, dict):
        llm_diagnoses = {}

    selected, source = _pick_admission_diagnoses(llm_diagnoses, medical_text)
    main_diag = selected[0] if selected else None
    other_diags = selected[1:] if len(selected) > 1 else []

    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    return {
        "success": True,
        "mode": "non_sse_single_llm_call",
        "source": source,
        "elapsed_ms": elapsed_ms,
        "diagnoses": {
            "admission_main_diagnosis_text": main_diag,
            "admission_other_diagnoses_texts": other_diags,
        },
        "llm_raw_diagnoses": llm_diagnoses,
    }


def _load_medical_text(args: argparse.Namespace) -> str:
    if args.text:
        return args.text
    if args.text_file:
        return Path(args.text_file).read_text(encoding="utf-8")
    raise ValueError("Either --text or --text-file is required.")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract admission diagnoses from admission record (non-SSE)."
    )
    parser.add_argument("--text", type=str, help="Medical text inline.")
    parser.add_argument("--text-file", type=str, help="Path to UTF-8 text file.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    parser.add_argument(
        "--fail-on-empty",
        action="store_true",
        help="Exit with code 2 when admission main diagnosis is empty.",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        medical_text = _load_medical_text(args)
    except Exception as exc:
        print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False))
        return 1

    result = asyncio.run(extract_admission_diagnosis_non_sse(medical_text))
    if args.pretty:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False))

    if args.fail_on_empty and not result["diagnoses"]["admission_main_diagnosis_text"]:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
