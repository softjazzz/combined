"""
Local ICD lookup service.

Behavior:
- Exact/fuzzy lookup from local ICD datasets (clinical first by default).
- Optional semantic fallback (disabled by default, guarded by confidence threshold).
- Used to normalize diagnosis/procedure codes after extraction.
"""

from __future__ import annotations

import logging
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..core.settings import get_settings
logger = logging.getLogger(__name__)

_LOCAL_ICD_CACHE: Optional[Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]] = None


def get_icd_semantic_retrieval_service() -> Any:
    """仅在语义兜底实际执行时加载可选的向量检索依赖。"""
    from .icd_semantic_retrieval_service import get_icd_semantic_retrieval_service as factory

    return factory()


_DIAG_ALIAS_MAP = {
    "冠脉": "冠状动脉",
    "支架置入": "支架植入",
    "PCI": "经皮冠状动脉介入",
    "CABG": "冠状动脉旁路移植",
}


def _normalize_diagnosis_text(text: str) -> str:
    value = str(text or "").strip()
    if not value:
        return ""
    value = value.replace("（", "(").replace("）", ")")
    value = re.sub(r"\s+", "", value)
    for src, dst in _DIAG_ALIAS_MAP.items():
        value = value.replace(src, dst)
    return value.lower()


def _get_icd_data():
    """Load only local coding datasets needed by frontpage coding.

    Do not call `icd_search._load_data()` here: that router also loads tree
    browsing JSON, which makes the first frontpage coding request visibly slow.
    """
    global _LOCAL_ICD_CACHE
    if _LOCAL_ICD_CACHE is not None:
        return _LOCAL_ICD_CACHE

    data_dir = Path(__file__).resolve().parents[2] / "data"

    def _read_json(name: str, default: Any) -> Any:
        path = data_dir / name
        if not path.exists():
            logger.warning("ICD data file not found: %s", path)
            return default
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _prepare_items(raw: Any) -> List[Dict[str, Any]]:
        items = raw if isinstance(raw, list) else []
        for item in items:
            if not isinstance(item, dict):
                continue
            item["name_lower"] = str(item.get("name") or "").lower()
            item["code_lower"] = str(item.get("code") or "").lower()
        return [item for item in items if isinstance(item, dict)]

    insurance_data = _prepare_items(_read_json("icd10_diagnoses.json", []))
    clinical_data = _prepare_items(_read_json("icd10_clinical_diagnoses.json", []))
    icd9_data = _prepare_items(_read_json("icd9cm3_procedures.json", []))
    code_mapping = _read_json("icd10_code_mapping.json", {})
    if not isinstance(code_mapping, dict):
        code_mapping = {}

    if clinical_data and code_mapping:
        c2i = code_mapping.get("clinical_to_insurance", {})
        i2c = code_mapping.get("insurance_to_clinical", {})
        existing_codes = {str(item.get("code") or "") for item in clinical_data}
        if isinstance(c2i, dict) and isinstance(i2c, dict):
            for clinical_code, ins_info in c2i.items():
                if clinical_code in existing_codes or not isinstance(ins_info, dict):
                    continue
                clinical_name = ""
                if not ins_info.get("diff", False):
                    clinical_name = str(ins_info.get("name") or "")
                else:
                    ins_code = str(ins_info.get("code") or "")
                    mapped = i2c.get(ins_code) if ins_code else None
                    if isinstance(mapped, dict) and mapped.get("code") == clinical_code:
                        clinical_name = str(mapped.get("name") or "")
                if clinical_name:
                    clinical_data.append(
                        {
                            "code": clinical_code,
                            "name": clinical_name,
                            "name_lower": clinical_name.lower(),
                            "code_lower": str(clinical_code).lower(),
                            "_from_mapping": True,
                        }
                    )
                    existing_codes.add(clinical_code)

    _LOCAL_ICD_CACHE = (clinical_data, insurance_data, icd9_data, code_mapping)
    logger.info(
        "local ICD datasets loaded: clinical=%d insurance=%d icd9=%d mapping=%s",
        len(clinical_data),
        len(insurance_data),
        len(icd9_data),
        bool(code_mapping),
    )
    return _LOCAL_ICD_CACHE


def _search_in_dataset(source: List[Dict[str, Any]], name: str) -> Optional[Dict[str, str]]:
    if not source:
        return None
    query_raw = str(name or "").strip()
    query = query_raw.lower()
    query_norm = _normalize_diagnosis_text(query_raw)
    if not query and not query_norm:
        return None

    for item in source:
        item_name = str(item.get("name") or "")
        item_name_lower = str(item.get("name_lower") or "").strip().lower()
        if item_name_lower == query:
            return {"code": item["code"], "name": item["name"]}
        if query_norm and _normalize_diagnosis_text(item_name) == query_norm:
            return {"code": item["code"], "name": item["name"]}

    candidates: List[Dict[str, Any]] = []
    for item in source:
        item_name = str(item.get("name") or "")
        nm = str(item.get("name_lower") or "")
        nm_norm = _normalize_diagnosis_text(item_name)
        score = 0
        if nm == query:
            score = 100
        elif query_norm and nm_norm == query_norm:
            score = 99
        elif query in nm:
            score = 90 if nm.startswith(query) else 80
        elif query_norm and query_norm in nm_norm:
            score = 88 if nm_norm.startswith(query_norm) else 78
        elif nm and nm in query:
            score = 70
        elif query_norm and nm_norm and nm_norm in query_norm:
            score = 68
        if score > 0:
            candidates.append(
                {
                    "code": item["code"],
                    "name": item["name"],
                    "_score": score,
                    "_len_diff": abs(len(str(item.get("name") or "")) - len(str(name or ""))),
                }
            )
    if not candidates:
        return None
    candidates.sort(key=lambda x: (-x["_score"], x["_len_diff"]))
    best = candidates[0]
    return {"code": best["code"], "name": best["name"]}


def _semantic_fallback(diagnosis_name: str, prefer_insurance: bool) -> Optional[Dict[str, str]]:
    """
    Semantic fallback used only when exact/fuzzy lookup misses.
    Auto-apply only when score >= ICD_SEMANTIC_T_HIGH.
    """
    try:
        settings = get_settings()
    except Exception:
        return None
    if not settings.ICD_SEMANTIC_ENABLED:
        return None

    candidates = _semantic_candidates(diagnosis_name, prefer_insurance=prefer_insurance)
    if not candidates:
        return None
    best = candidates[0]
    score = float(best.get("score") or 0.0)
    if score < float(settings.ICD_SEMANTIC_T_HIGH):
        logger.info(
            "ICD semantic fallback low confidence skipped: '%s' -> %s(score=%.4f)",
            diagnosis_name,
            best.get("code"),
            score,
        )
        return None
    logger.info(
        "ICD semantic fallback hit: '%s' -> %s(score=%.4f)",
        diagnosis_name,
        best.get("code"),
        score,
    )
    return {
        "code": str(best.get("code") or ""),
        "name": str(best.get("name") or ""),
        "source": "semantic",
        "score": f"{score:.4f}",
    }


def _semantic_candidates(diagnosis_name: str, prefer_insurance: bool) -> List[Dict[str, Any]]:
    """
    Retrieve semantic candidates above low threshold.
    """
    try:
        settings = get_settings()
    except Exception:
        return []
    if not settings.ICD_SEMANTIC_ENABLED:
        return []

    try:
        service = get_icd_semantic_retrieval_service()
        candidates = service.search_diagnosis(
            diagnosis_name,
            prefer_insurance=prefer_insurance,
            top_k=max(1, int(settings.ICD_SEMANTIC_TOP_K)),
            min_score=float(settings.ICD_SEMANTIC_T_LOW),
        )
        if not isinstance(candidates, list):
            return []
        return candidates
    except Exception:
        logger.exception("ICD semantic retrieval failed")
        return []


def _format_semantic_suggestions(
    candidates: List[Dict[str, Any]],
    high_threshold: float,
    exclude_top_when_high_hit: bool,
) -> List[Dict[str, Any]]:
    suggestions: List[Dict[str, Any]] = []
    for idx, item in enumerate(candidates):
        score = float(item.get("score") or 0.0)
        if exclude_top_when_high_hit and idx == 0:
            continue
        if score >= high_threshold:
            continue
        suggestions.append(
            {
                "code": str(item.get("code") or ""),
                "name": str(item.get("name") or ""),
                "score": score,
                "source": str(item.get("source") or "semantic"),
            }
        )
    return suggestions


def _lookup_diagnosis_code_with_semantic_suggestions(
    diagnosis_name: str,
    prefer_insurance: bool = False,
) -> Tuple[Optional[Dict[str, str]], List[Dict[str, Any]]]:
    """
    Lookup diagnosis code and return low-confidence semantic suggestions for UI.
    """
    if not diagnosis_name or not str(diagnosis_name).strip():
        return None, []

    settings = None
    try:
        settings = get_settings()
    except Exception:
        settings = None

    # Exact/fuzzy hit path.
    exact = lookup_diagnosis_code(diagnosis_name, prefer_insurance=prefer_insurance)
    if exact and exact.get("source") != "semantic":
        return exact, []

    # Semantic path (exact is either None or semantic hit).
    high_threshold = float(getattr(settings, "ICD_SEMANTIC_T_HIGH", 0.9)) if settings else 0.9
    candidates = _semantic_candidates(diagnosis_name, prefer_insurance=prefer_insurance)
    if not candidates:
        return exact, []

    best = candidates[0]
    best_score = float(best.get("score") or 0.0)
    best_as_result: Optional[Dict[str, str]] = None
    if best_score >= high_threshold:
        best_as_result = {
            "code": str(best.get("code") or ""),
            "name": str(best.get("name") or ""),
            "source": str(best.get("source") or "semantic"),
            "score": f"{best_score:.4f}",
        }

    if exact and exact.get("source") == "semantic":
        # Keep existing semantic behavior if already decided by lookup.
        best_as_result = exact

    suggestions = _format_semantic_suggestions(
        candidates=candidates,
        high_threshold=high_threshold,
        exclude_top_when_high_hit=best_score >= high_threshold,
    )

    return best_as_result or exact, suggestions


def lookup_diagnosis_code(diagnosis_name: str, prefer_insurance: bool = False) -> Optional[Dict[str, str]]:
    """
    Lookup ICD-10 code by diagnosis text.
    Returns dict with at least {"code", "name"} when matched.
    """
    if not diagnosis_name or not str(diagnosis_name).strip():
        return None

    clinical_data, insurance_data, _, code_mapping = _get_icd_data()

    if prefer_insurance:
        c2i = code_mapping.get("clinical_to_insurance", {}) if code_mapping else {}

        def _ensure_insurance_code(result: Optional[Dict[str, str]]) -> Optional[Dict[str, str]]:
            if not result:
                return None
            mapped = c2i.get(result["code"])
            if mapped:
                return {"code": mapped["code"], "name": mapped.get("name", result["name"])}
            return result

        exact = _search_in_dataset(insurance_data, diagnosis_name) if insurance_data else None
        exact = _ensure_insurance_code(exact)
        if exact:
            return exact
        exact = _search_in_dataset(clinical_data, diagnosis_name) if clinical_data else None
        exact = _ensure_insurance_code(exact)
        if exact:
            return exact
        return _semantic_fallback(diagnosis_name, prefer_insurance=True)

    exact = _search_in_dataset(clinical_data, diagnosis_name) if clinical_data else None
    if exact:
        return exact
    exact = _search_in_dataset(insurance_data, diagnosis_name) if insurance_data else None
    if exact:
        return exact
    return _semantic_fallback(diagnosis_name, prefer_insurance=False)


def lookup_procedure_code(procedure_name: str) -> Optional[Dict[str, str]]:
    """Lookup ICD-9-CM-3 code by procedure text (exact/fuzzy only)."""
    if not procedure_name or not str(procedure_name).strip():
        return None

    _, _, icd9_data, _ = _get_icd_data()
    if not icd9_data:
        logger.warning("ICD-9-CM-3 dataset is empty")
        return None

    query = str(procedure_name).strip().lower()
    for item in icd9_data:
        if item.get("name_lower") == query:
            return {"code": item["code"], "name": item["name"]}

    candidates: List[Dict[str, Any]] = []
    for item in icd9_data:
        nm = str(item.get("name_lower") or "")
        score = 0
        if nm == query:
            score = 100
        elif query in nm:
            score = 90 if nm.startswith(query) else 80
        elif nm and nm in query:
            score = 70
        if score > 0:
            candidates.append(
                {
                    "code": item["code"],
                    "name": item["name"],
                    "_score": score,
                    "_len_diff": abs(len(str(item.get("name") or "")) - len(str(procedure_name or ""))),
                }
            )
    if not candidates:
        return None
    candidates.sort(key=lambda x: (-x["_score"], x["_len_diff"]))
    best = candidates[0]
    return {"code": best["code"], "name": best["name"]}


def resolve_diagnosis_codes(diagnoses: Dict[str, Any]) -> Dict[str, Any]:
    """
    Resolve diagnosis codes in-place.
    """
    if not diagnoses:
        return diagnoses

    diagnoses["_diagnosis_code_source"] = "local_icd_lookup"
    resolved_count = 0

    main_text = diagnoses.get("discharge_main_diagnosis_text")
    if main_text:
        result, low_conf_suggestions = _lookup_diagnosis_code_with_semantic_suggestions(main_text)
        if result:
            old_code = diagnoses.get("discharge_main_icd")
            diagnoses["discharge_main_icd"] = result["code"]
            resolved_count += 1
            if old_code and old_code != result["code"]:
                logger.info("main diagnosis code corrected: %s -> %s (%s)", old_code, result["code"], main_text)
        if low_conf_suggestions:
            diagnoses["discharge_main_icd_suggestions"] = low_conf_suggestions

    other_texts = diagnoses.get("discharge_other_diagnoses_texts") or []
    if other_texts:
        other_codes: List[Optional[str]] = []
        old_codes = diagnoses.get("discharge_other_icds") or []
        existing_other_suggestions = diagnoses.get("discharge_other_icd_suggestions") or []
        existing_by_text: Dict[str, Dict[str, Any]] = {}
        if isinstance(existing_other_suggestions, list):
            for item in existing_other_suggestions:
                if not isinstance(item, dict):
                    continue
                txt = str(item.get("diagnosis_text") or "").strip()
                if txt:
                    existing_by_text[txt] = item
        merged_other_suggestions: List[Dict[str, Any]] = list(existing_by_text.values())

        for idx, text in enumerate(other_texts):
            result, low_conf_suggestions = _lookup_diagnosis_code_with_semantic_suggestions(text)
            if result:
                other_codes.append(result["code"])
                resolved_count += 1
            elif idx < len(old_codes) and old_codes[idx]:
                other_codes.append(old_codes[idx])
            else:
                other_codes.append(None)
            if low_conf_suggestions:
                existing_by_text[str(text)] = {
                    "diagnosis_text": str(text),
                    "suggestions": low_conf_suggestions,
                }

        # Rebuild suggestions in diagnosis order for better frontend rendering.
        ordered_suggestions: List[Dict[str, Any]] = []
        for text in other_texts:
            entry = existing_by_text.get(str(text))
            if entry:
                ordered_suggestions.append(entry)
        # Keep any leftover suggestions not in current text list.
        for item in merged_other_suggestions:
            txt = str(item.get("diagnosis_text") or "")
            if txt and txt not in {str(t) for t in other_texts}:
                ordered_suggestions.append(item)

        diagnoses["discharge_other_icd_suggestions"] = ordered_suggestions
        diagnoses["discharge_other_icds"] = other_codes

    adm_text = diagnoses.get("admission_main_diagnosis_text")
    if adm_text:
        result = lookup_diagnosis_code(adm_text)
        if result:
            diagnoses["admission_main_icd"] = result["code"]
            resolved_count += 1

    logger.info("local ICD-10 lookup done: resolved %d diagnosis entries", resolved_count)
    return diagnoses


def resolve_procedure_codes(procedures: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve procedure codes in-place."""
    if not procedures:
        return procedures

    resolved_count = 0

    main_text = procedures.get("main_procedure_text")
    if main_text:
        result = lookup_procedure_code(main_text)
        if result:
            old_code = procedures.get("main_procedure_code")
            procedures["main_procedure_code"] = result["code"]
            resolved_count += 1
            if old_code and old_code != result["code"]:
                logger.info("main procedure code corrected: %s -> %s (%s)", old_code, result["code"], main_text)

    others = procedures.get("other_procedures") or []
    for proc in others:
        text = proc.get("text") or proc.get("name")
        if not text:
            continue
        result = lookup_procedure_code(text)
        if result:
            proc["code"] = result["code"]
            resolved_count += 1

    logger.info("local ICD-9-CM-3 lookup done: resolved %d procedure entries", resolved_count)
    return procedures
