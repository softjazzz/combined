from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from .dip_grouping_service import _load_dataset


def _text(value: object) -> str:
    return str(value or "").strip()


def _normalize_code(value: object) -> str:
    return _text(value).upper()


def _split_codes(value: str | Iterable[str] | None) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw = value.replace("，", ",").split(",")
    else:
        raw = list(value)
    return [_normalize_code(item) for item in raw if _normalize_code(item)]


class GroupingCorrectionService:
    """DRG/DIP 预入组修正建议服务。

    仅返回编码修正候选和依据，不写正式病案首页、医保结算清单或正式分组结果。
    """

    safety_warning = "仅为预入组编码修正建议，不自动写入病案首页、医保结算清单或正式 DRG/DIP 结果。"

    def suggest_corrections(
        self,
        *,
        pdx_code: str,
        proc_codes: str | Iterable[str] | None = None,
        grouping_result: Optional[Dict[str, Any]] = None,
        diagnosis_candidates: Optional[Iterable[str]] = None,
        procedure_candidates: Optional[Iterable[str]] = None,
    ) -> Dict[str, Any]:
        dataset = _load_dataset()
        core: List[Dict[str, Any]] = list(dataset["core"])
        valid_diagnoses: set[str] = dataset["valid_diagnoses"]
        normalized_pdx = _normalize_code(pdx_code)
        procedures = _split_codes(proc_codes)
        procedure_candidate_set = set(_split_codes(procedure_candidates))
        diagnosis_candidate_set = set(_split_codes(diagnosis_candidates))
        result = grouping_result or {}
        current_success = bool(result.get("success")) or result.get("status") == "分组成功"
        current_score = self._score(result)

        suggestions: List[Dict[str, Any]] = []
        if not normalized_pdx:
            suggestions.append(
                self._suggestion(
                    suggestion_type="missing_main_diagnosis",
                    severity="high",
                    title="补充主诊断编码后再执行 DRG/DIP 预入组",
                    reason="当前输入缺少主诊断编码，分组器无法完成预入组。",
                    candidates=[],
                )
            )
        elif normalized_pdx not in valid_diagnoses:
            candidates = self._diagnosis_candidates(normalized_pdx, core, diagnosis_candidate_set)
            suggestions.append(
                self._suggestion(
                    suggestion_type="diagnosis_not_in_dip_catalog",
                    severity="high",
                    title=f"主诊断 {normalized_pdx} 未命中泸州 DIP 病种库",
                    reason="建议核对医保版 ICD 编码或选择病种库内的相近诊断编码。",
                    candidates=candidates,
                )
            )

        if normalized_pdx in valid_diagnoses and not current_success:
            candidates = self._procedure_candidates(
                normalized_pdx,
                core,
                procedures,
                procedure_candidate_set,
                min_score=None,
            )
            if candidates:
                suggestions.append(
                    self._suggestion(
                        suggestion_type="procedure_candidate_for_ungrouped",
                        severity="medium",
                        title="可尝试补充或调整手术操作编码",
                        reason="当前诊断存在病种库记录，但现有手术组合未能入组。",
                        candidates=candidates,
                    )
                )

        if normalized_pdx in valid_diagnoses and current_success:
            better_candidates = self._procedure_candidates(
                normalized_pdx,
                core,
                procedures,
                procedure_candidate_set,
                min_score=current_score,
            )
            if better_candidates:
                suggestions.append(
                    self._suggestion(
                        suggestion_type="higher_score_grouping_option",
                        severity="low",
                        title="存在可人工复核的更高分值入组选项",
                        reason="同一主诊断下存在分值更高的手术/操作组合，仅在病历确有对应操作证据时才可采纳。",
                        candidates=better_candidates,
                    )
                )

        return {
            "result_type": "grouping_correction_suggestions",
            "pdx_code": normalized_pdx,
            "proc_codes": procedures,
            "grouped": current_success,
            "suggestions": suggestions,
            "safety_warning": self.safety_warning,
            "writes_formal_tables": False,
            "blocked_fields": [
                "medical_text",
                "documents",
                "bundle",
                "record_content",
                "internal_data",
                "prompt",
                "raw_response",
                "embedding",
                "vector",
            ],
        }

    def _suggestion(
        self,
        *,
        suggestion_type: str,
        severity: str,
        title: str,
        reason: str,
        candidates: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        return {
            "suggestion_type": suggestion_type,
            "severity": severity,
            "title": title,
            "reason": reason,
            "candidates": candidates[:5],
            "action": "人工复核后作为草稿建议使用",
        }

    def _score(self, result: Dict[str, Any]) -> float:
        for key in ("score", "dip_score", "weight"):
            try:
                return float(result.get(key) or 0)
            except Exception:
                continue
        return 0.0

    def _diagnosis_candidates(
        self,
        pdx_code: str,
        core: List[Dict[str, Any]],
        diagnosis_candidate_set: set[str],
    ) -> List[Dict[str, Any]]:
        prefix = pdx_code.split(".", 1)[0]
        candidates = []
        for item in core:
            diagnosis_code = _normalize_code(item.get("diagnosisCode"))
            if not diagnosis_code:
                continue
            if diagnosis_candidate_set and diagnosis_code not in diagnosis_candidate_set:
                continue
            if diagnosis_code.startswith(f"{prefix}.") or diagnosis_code.startswith(prefix):
                candidates.append(
                    {
                        "code": diagnosis_code,
                        "name": item.get("diagnosisName") or "",
                        "score": item.get("score"),
                        "match_type": "same_category",
                        "source": "泸州 DIP 病种库",
                    }
                )
        return self._dedupe_candidates(candidates, key="code")

    def _procedure_candidates(
        self,
        pdx_code: str,
        core: List[Dict[str, Any]],
        current_procedures: List[str],
        procedure_candidate_set: set[str],
        min_score: Optional[float],
    ) -> List[Dict[str, Any]]:
        current_set = set(current_procedures)
        candidates: List[Dict[str, Any]] = []
        for item in core:
            if _normalize_code(item.get("diagnosisCode")) != pdx_code:
                continue
            procedure_code = _normalize_code(item.get("mainProcedureCode"))
            if not procedure_code or procedure_code in current_set:
                continue
            if procedure_candidate_set and procedure_code not in procedure_candidate_set:
                continue
            score = self._score(item)
            if min_score is not None and score <= min_score:
                continue
            candidates.append(
                {
                    "code": procedure_code,
                    "name": item.get("mainProcedureName") or "",
                    "dip_code": item.get("dipCode") or "",
                    "dip_name": item.get("dipName") or "",
                    "score": item.get("score"),
                    "disease_property": item.get("diseaseAttribute") or "",
                    "grassroots_disease_flag": item.get("primaryCareFlag") or "",
                    "source": "泸州 DIP 病种库",
                }
            )
        return sorted(
            self._dedupe_candidates(candidates, key="code"),
            key=lambda item: float(item.get("score") or 0),
            reverse=True,
        )

    def _dedupe_candidates(self, candidates: List[Dict[str, Any]], *, key: str) -> List[Dict[str, Any]]:
        seen = set()
        result: List[Dict[str, Any]] = []
        for item in candidates:
            value = _normalize_code(item.get(key))
            if not value or value in seen:
                continue
            seen.add(value)
            result.append(item)
        return result
