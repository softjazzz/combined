from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query

from ..services.drg_demo_store import get_demo_drg_store

router = APIRouter(prefix="/api/v1/case-front-page", tags=["drg_case_front_page"])


@router.get("")
async def list_case_front_pages(limit: int = Query(100, ge=1, le=500)) -> List[Dict[str, Any]]:
    store = get_demo_drg_store()
    return store.list_cases(limit=limit)


@router.get("/{admission_id}")
async def get_case_front_page_detail(admission_id: str) -> Dict[str, Any]:
    store = get_demo_drg_store()
    item = store.get_case_detail(admission_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"未找到住院号 {admission_id} 的病案首页")
    return item


@router.post("")
async def upsert_case_front_page(payload: Dict[str, Any]) -> Dict[str, Any]:
    admission_id = payload.get("admission_id")
    if not admission_id or not isinstance(admission_id, str):
        raise HTTPException(status_code=400, detail="admission_id is required")

    store = get_demo_drg_store()
    return store.upsert_case(admission_id=admission_id, patch=payload)


from pydantic import BaseModel

class ExtractCodingRequest(BaseModel):
    medical_text: str
    patient_age: int = 0
    patient_gender: str = "M"

@router.post("/extract-coding")
async def extract_coding(payload: ExtractCodingRequest) -> Dict[str, Any]:
    from ..services.external_coding_service import get_external_coding_service
    
    service = get_external_coding_service()
    
    try:
        result = await service.extract_coding(
            medical_text=payload.medical_text,
            patient_context={
                "age": payload.patient_age,
                "gender": payload.patient_gender
            }
        )
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ExtractRequest(BaseModel):
    medical_text: str


@router.post("/extract")
async def extract_frontpage(payload: ExtractRequest) -> Dict[str, Any]:
    """
    从病历文本中提取首页信息 (诊断、手术等)
    用于事前分析的 AI 智能抽取功能

    流程：LLM 抽取诊断/手术文本 → LLM 建议 ICD 编码 → 本地 ICD 编码库精确匹配
    """
    from ..services.frontpage_extraction_service import default_frontpage_service
    import uuid
    import logging
    import re

    logger = logging.getLogger(__name__)
    service = default_frontpage_service

    def _to_plain_dict(value: Any) -> Dict[str, Any]:
        if isinstance(value, dict):
            return dict(value)
        if value is None:
            return {}
        if hasattr(value, "model_dump"):
            try:
                dumped = value.model_dump()
                if isinstance(dumped, dict):
                    return dumped
            except Exception:
                logger.exception("extract: model_dump failed for type=%s", type(value).__name__)
        if hasattr(value, "dict"):
            try:
                dumped = value.dict()
                if isinstance(dumped, dict):
                    return dumped
            except Exception:
                logger.exception("extract: dict() failed for type=%s", type(value).__name__)
        try:
            casted = dict(value)
            if isinstance(casted, dict):
                return casted
        except Exception:
            pass
        logger.warning("extract: cannot coerce object to dict, type=%s", type(value).__name__)
        return {}

    def _dedupe_non_empty(values: List[str]) -> List[str]:
        seen = set()
        out: List[str] = []
        for item in values:
            text = str(item or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            out.append(text)
        return out

    def _split_compound_diag_line(text: str) -> List[str]:
        value = str(text or "").strip()
        if not value:
            return []
        # Strong delimiters first.
        parts = [p.strip() for p in re.split(r"[；;、，,]+", value) if p and p.strip()]
        if len(parts) == 1:
            # Conservative whitespace split fallback for compound lines like:
            # "冠状动脉粥样硬化性心脏病 不稳定型心绞痛 冠脉支架植入后状态"
            tokens = [t.strip() for t in re.split(r"\s+", value) if t and t.strip()]
            if len(tokens) >= 2 and all(len(t) >= 4 for t in tokens):
                parts = tokens
        return parts

    def _is_placeholder_text(value: Any) -> bool:
        text = str(value or "").strip()
        if not text:
            return True
        lowered = text.lower()
        placeholder_tokens = (
            "待编码",
            "待补充",
            "未知",
            "n/a",
            "na",
            "none",
            "null",
            "未提供",
            "请补充",
            "出院主要诊断",
            "主诊断选择依据",
            "主要手术名称",
        )
        if any(token in lowered for token in placeholder_tokens):
            return True
        # 模板回显常见占位词
        if re.fullmatch(r"(其他诊断\d*|门/急诊诊断\d*|其他手术\d*)", text):
            return True
        return False

    def _extract_diagnoses_from_text(medical_text: str) -> List[str]:
        if not medical_text:
            return []

        diag_titles = r"(?:\u521d\u6b65\u8bca\u65ad|\u5165\u9662\u8bca\u65ad|\u95e8\u8bca\u8bca\u65ad|\u6025\u8bca\u8bca\u65ad|\u51fa\u9662\u8bca\u65ad)"
        stop_titles = r"(?:\u8bca\u7597\u8ba1\u5212|\u6cbb\u7597\u8ba1\u5212|\u6cbb\u7597\u65b9\u6848|\u62df\u884c|\u624b\u672f|\u7b7e\u540d|\u533b\u5e08|$)"
        section_patterns = [
            rf"{diag_titles}\s*[:\uff1a]\s*([\s\S]*?)(?={stop_titles})",
        ]
        block = ""
        for pattern in section_patterns:
            m = re.search(pattern, medical_text, re.IGNORECASE)
            if m and m.group(1).strip():
                block = m.group(1)
                break

        if not block:
            # Fallback 1: global numbered diagnosis lines (not depending on section header).
            global_numbered = re.findall(r"(?:^|\n)\s*\d{1,2}[\.\u3001\)]\s*([^\n\r]+)", medical_text)
            if global_numbered:
                return _dedupe_non_empty(global_numbered)
            # Fallback 2: one-line generic diagnosis after any "诊断:" marker.
            generic = re.search(r"(?:\u8bca\u65ad)\s*[:\uff1a]\s*([^\n\r]+)", medical_text, re.IGNORECASE)
            if generic and generic.group(1).strip():
                return _dedupe_non_empty([generic.group(1).strip()])
            return []

        numbered_items = re.findall(r"(?:^|\n)\s*\d{1,2}[\.\u3001\)]\s*([^\n]+)", block)
        if numbered_items:
            expanded: List[str] = []
            for line in numbered_items:
                split_items = _split_compound_diag_line(line)
                if split_items:
                    expanded.extend(split_items)
                else:
                    expanded.append(line)
            return _dedupe_non_empty(expanded)

        raw_lines = re.split(r"[\n\uff1b;]", block)
        cleaned = []
        for line in raw_lines:
            text = re.sub(r"^\s*\d{1,2}[\.\u3001\)]\s*", "", line).strip()
            if text:
                split_items = _split_compound_diag_line(text)
                if split_items:
                    cleaned.extend(split_items)
                else:
                    cleaned.append(text)
        return _dedupe_non_empty(cleaned)

    def _extract_main_procedure_from_text(medical_text: str) -> str | None:
        if not medical_text:
            return None

        planned = re.search(
            "(?:\u62df\u884c|\u8ba1\u5212\u884c|\u62df\u4e8e)\s*([^\n\uff1b;]+)",
            medical_text,
            re.IGNORECASE,
        )
        if planned and planned.group(1).strip():
            text = planned.group(1).strip(" ?:?,?.?;")
            if text:
                return text

        surgery_line = re.search(
            "(?:\u4e3b\u8981\u624b\u672f|\u624b\u672f|\u64cd\u4f5c)\s*[:\uff1a]\s*([^\n]+)",
            medical_text,
            re.IGNORECASE,
        )
        if surgery_line and surgery_line.group(1).strip():
            candidate = surgery_line.group(1).strip(" ?:?,?.?;")
            if candidate:
                return candidate

        return None

    try:
        # 1) LLM 抽取诊断/手术文本
        draft = await service.extract_from_text(payload.medical_text)
        result = _to_plain_dict(draft)

        # 2) Compatibility for pre-analysis: allow fallback mapping from ED/admission text.
        diagnoses = _to_plain_dict(result.get("diagnoses"))
        procedures = _to_plain_dict(result.get("procedures"))
        logger.info(
            "extract: diagnoses keys=%s procedures keys=%s",
            list(diagnoses.keys()),
            list(procedures.keys()),
        )
        logger.info("extract: diagnoses snapshot after dump=%s", diagnoses)

        if isinstance(diagnoses, dict):
            ed_texts = diagnoses.get("ed_diagnosis_texts") or []
            if _is_placeholder_text(diagnoses.get("discharge_main_diagnosis_text")) and ed_texts:
                promoted_parts = _split_compound_diag_line(ed_texts[0]) or [ed_texts[0]]
                diagnoses["discharge_main_diagnosis_text"] = promoted_parts[0]

                promoted_others = promoted_parts[1:]
                if len(ed_texts) > 1:
                    promoted_others.extend(ed_texts[1:])
                existing_others = diagnoses.get("discharge_other_diagnoses_texts") or []
                diagnoses["discharge_other_diagnoses_texts"] = _dedupe_non_empty(
                    [*promoted_others, *existing_others]
                )
                logger.info(f"extract: 事前分析兼容 - 将门急诊诊断提升为主诊断: {ed_texts[0]}")
            else:
                logger.info(
                    "extract: no promotion needed, main=%s, ed_count=%d",
                    diagnoses.get("discharge_main_diagnosis_text"),
                    len(ed_texts) if isinstance(ed_texts, list) else 0,
                )

            # Fallback: if LLM gives no discharge main diagnosis, parse from medical_text.
            if _is_placeholder_text(diagnoses.get("discharge_main_diagnosis_text")):
                parsed_diags = _extract_diagnoses_from_text(payload.medical_text)
                if parsed_diags:
                    diagnoses["discharge_main_diagnosis_text"] = parsed_diags[0]
                    diagnoses["discharge_other_diagnoses_texts"] = parsed_diags[1:]
                    if not diagnoses.get("ed_diagnosis_texts"):
                        diagnoses["ed_diagnosis_texts"] = parsed_diags
                    logger.info(
                        "extract: fallback text parse filled diagnoses, main=%s, other_count=%d",
                        parsed_diags[0],
                        max(len(parsed_diags) - 1, 0),
                    )
                else:
                    logger.warning("extract: fallback text parse found no diagnosis candidates")

        if isinstance(procedures, dict) and _is_placeholder_text(procedures.get("main_procedure_text")):
            parsed_proc = _extract_main_procedure_from_text(payload.medical_text)
            if parsed_proc:
                procedures["main_procedure_text"] = parsed_proc
                logger.info("extract: fallback text parse filled main_procedure_text=%s", parsed_proc)

        if isinstance(diagnoses, dict) and diagnoses and not diagnoses.get("discharge_main_icd"):
            try:
                diagnoses = await service._suggest_diagnosis_codes(diagnoses)
                logger.info("extract: LLM 诊断编码建议完成")
            except Exception:
                logger.exception("extract: LLM 诊断编码建议失败")

        if isinstance(procedures, dict) and procedures and not procedures.get("main_procedure_code"):
            try:
                procedures = await service._suggest_procedure_codes(procedures)
                logger.info("extract: LLM 手术编码建议完成")
            except Exception:
                logger.exception("extract: LLM 手术编码建议失败")

        # 3) 本地 ICD 编码库精确匹配（替换/校正 LLM 输出的编码）
        try:
            from ..services.local_icd_service import resolve_diagnosis_codes, resolve_procedure_codes
            if isinstance(diagnoses, dict) and diagnoses:
                diagnoses = resolve_diagnosis_codes(diagnoses)
                logger.info("extract: 本地 ICD 诊断编码匹配完成")
            if isinstance(procedures, dict) and procedures:
                procedures = resolve_procedure_codes(procedures)
                logger.info("extract: 本地 ICD 手术编码匹配完成")
        except Exception:
            logger.exception("extract: 本地 ICD 编码匹配失败")

        evidence = _to_plain_dict(result.get("evidence"))
        if not isinstance(evidence, dict):
            evidence = {}
        has_main_llm = isinstance(evidence.get("main_diagnosis_llm"), dict)
        has_audit_llm = isinstance(evidence.get("coding_audit_llm"), dict)
        if not (has_main_llm and has_audit_llm):
            try:
                merged = await service._build_main_and_audit_llm_evidence(
                    medical_text=payload.medical_text,
                    diagnoses=diagnoses,
                    procedures=procedures,
                    clinician_main_diagnosis=evidence.get("clinician_main_diagnosis"),
                    main_diagnosis_llm=evidence.get("main_diagnosis_llm")
                    if has_main_llm
                    else None,
                )
                if not has_main_llm and isinstance(merged.get("main_diagnosis_llm"), dict):
                    evidence["main_diagnosis_llm"] = merged.get("main_diagnosis_llm")
                if not has_audit_llm and isinstance(merged.get("coding_audit_llm"), dict):
                    evidence["coding_audit_llm"] = merged.get("coding_audit_llm")
            except Exception:
                logger.exception("extract: build merged llm evidence failed")
        try:
            evidence["diagnoses"] = service._build_diagnosis_evidence(
                payload.medical_text,
                diagnoses,
                procedures,
                guideline_rule_trace=evidence.get("guideline_rule_trace"),
                clinician_main_diagnosis=evidence.get("clinician_main_diagnosis"),
            )
        except Exception:
            logger.exception("extract: build diagnosis evidence failed")

        result["diagnoses"] = diagnoses
        result["procedures"] = procedures
        result["evidence"] = evidence

        # 生成 admission_id 用于后续 DRG 分组
        admission_id = f"PRE_{uuid.uuid4().hex[:8]}"

        # 保存到 demo store 以便按 admission_id 查询
        store = get_demo_drg_store()
        store.upsert_case(admission_id=admission_id, patch={
            "admission_id": admission_id,
            "diagnoses": diagnoses,
            "surgeries": procedures,
            "basic_info": result.get("basic_info", {}),
            "costs": result.get("costs", {}),
        })

        result["admission_id"] = admission_id

        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extract-pre-group")
async def extract_for_pre_group(payload: ExtractRequest) -> Dict[str, Any]:
    """
    Pre-group extraction endpoint (admission-oriented).
    This endpoint is designed for DRG pre-grouping and does NOT require discharge diagnosis.
    """
    from ..services.icd_coding_service import get_icd_coding_service
    import uuid
    import logging
    import re
    import time
    import asyncio

    logger = logging.getLogger(__name__)
    start = time.perf_counter()

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

    def _extract_diag_candidates(medical_text: str) -> List[str]:
        if not medical_text:
            return []
        diag_titles = r"(?:\u521d\u6b65\u8bca\u65ad|\u5165\u9662\u8bca\u65ad|\u95e8\u8bca\u8bca\u65ad|\u6025\u8bca\u8bca\u65ad|\u51fa\u9662\u8bca\u65ad)"
        stop_titles = r"(?:\u8bca\u7597\u8ba1\u5212|\u6cbb\u7597\u8ba1\u5212|\u6cbb\u7597\u65b9\u6848|\u62df\u884c|\u624b\u672f|\u7b7e\u540d|\u533b\u5e08|$)"
        m = re.search(rf"{diag_titles}\s*[:\uff1a]\s*([\s\S]*?)(?={stop_titles})", medical_text, re.IGNORECASE)
        block = (m.group(1) or "") if m else ""
        if not block:
            # Fallback 1: global numbered diagnosis lines.
            global_numbered = re.findall(r"(?:^|\n)\s*\d{1,2}[\.\u3001\)]\s*([^\n\r]+)", medical_text)
            if global_numbered:
                return _dedupe_non_empty(global_numbered)
            # Fallback 2: one-line generic diagnosis after any "诊断:" marker.
            generic = re.search(r"(?:\u8bca\u65ad)\s*[:\uff1a]\s*([^\n\r]+)", medical_text, re.IGNORECASE)
            if generic and generic.group(1).strip():
                return _dedupe_non_empty([generic.group(1).strip()])
            return []
        numbered_items = re.findall(r"(?:^|\n)\s*\d{1,2}[\.\u3001\)]\s*([^\n]+)", block)
        if numbered_items:
            return _dedupe_non_empty(numbered_items)
        raw_lines = re.split(r"[\n\uff1b;]", block)
        cleaned = []
        for line in raw_lines:
            text = re.sub(r"^\s*\d{1,2}[\.\u3001\)]\s*", "", line).strip()
            if text:
                cleaned.append(text)
        return _dedupe_non_empty(cleaned)

    def _extract_main_proc_candidate(medical_text: str) -> str | None:
        if not medical_text:
            return None
        m = re.search(
            r"(?:\u62df\u884c|\u8ba1\u5212\u884c|\u62df\u4e8e)\s*([^\n\uff0c,。\uff1b;]+)",
            medical_text,
            re.IGNORECASE,
        )
        if m and m.group(1).strip():
            return m.group(1).strip()
        m2 = re.search(r"(?:\u624b\u672f|\u64cd\u4f5c)\s*[:\uff1a]\s*([^\n]+)", medical_text, re.IGNORECASE)
        if m2 and m2.group(1).strip():
            return m2.group(1).strip()
        return None

    def _extract_basic_info(medical_text: str) -> Dict[str, Any]:
        age_years = 0
        age_match = re.search(r"(\d{1,3})\s*岁", medical_text)
        if age_match:
            try:
                age_years = int(age_match.group(1))
            except Exception:
                age_years = 0

        gender = "0"
        gender_text = ""
        gender_match = re.search(r"(男|女)", medical_text)
        if gender_match:
            gender_text = gender_match.group(1)
            gender = "1" if gender_text == "男" else "2"

        return {
            "age_years": age_years,
            "gender": gender,
            "gender_text": gender_text,
        }

    def _fast_map_procedure_code(main_procedure_text: str | None) -> str | None:
        if not main_procedure_text:
            return None
        t = main_procedure_text.strip()
        if not t:
            return None

        # Fast in-process fallback mapping for common pre-group scenarios.
        rules = [
            (r"冠状动脉造影|冠脉造影", "88.56"),
            (r"支架|PCI|经皮冠状动脉介入", "36.0701"),
            (r"球囊扩张|PTCA", "36.0601"),
            (r"阑尾切除", "47.0900"),
            (r"胆囊切除", "51.2101"),
            (r"血液透析|透析", "39.9501"),
        ]
        for pattern, code in rules:
            if re.search(pattern, t, re.IGNORECASE):
                return code
        return None

    def _fast_map_diagnosis_code(main_diagnosis_text: str | None) -> str | None:
        if not main_diagnosis_text:
            return None
        t = main_diagnosis_text.strip()
        if not t:
            return None

        rules = [
            (r"急性心肌梗死", "I21.901"),
            (r"不稳定型心绞痛", "I20.0"),
            (r"冠状动脉粥样硬化性心脏病|冠心病", "I25.103"),
            (r"高血压", "I10.x05"),
            (r"2型糖尿病|Ⅱ型糖尿病", "E11.901"),
            (r"肺炎", "J18.901"),
            (r"慢性阻塞性肺疾病|慢阻肺", "J44.101"),
            (r"急性阑尾炎", "K35.901"),
        ]
        for pattern, code in rules:
            if re.search(pattern, t, re.IGNORECASE):
                return code
        return None

    try:
        medical_text = payload.medical_text or ""
        basic_info = _extract_basic_info(medical_text)

        diagnoses: Dict[str, Any] = {
            "ed_diagnosis_texts": [],
            "admission_main_diagnosis_text": None,
            "admission_other_diagnoses_texts": [],
            "admission_main_icd": None,
            "admission_other_icds": [],
            "discharge_main_diagnosis_text": None,
            "discharge_other_diagnoses_texts": [],
            "discharge_main_icd": None,
            "discharge_other_icds": [],
        }

        procedures: Dict[str, Any] = {
            "main_procedure_text": None,
            "main_procedure_code": None,
            "other_procedure_texts": [],
            "other_procedure_codes": [],
        }

        # ========== 第一层：LLM 主路抽取 ==========
        llm_diags_ok = False
        try:
            from ..services.frontpage_extraction_service import (
                DIAGNOSES_PROMPT,
                default_frontpage_service,
            )
            service = default_frontpage_service
            prompt = DIAGNOSES_PROMPT.format(medical_text=medical_text)
            llm_diagnoses = await asyncio.wait_for(
                service._extract_json(prompt), timeout=30
            )
            if isinstance(llm_diagnoses, dict):
                # 从 LLM 结果中提取诊断列表（优先 ed_diagnosis_texts）
                ed_texts = _dedupe_non_empty(
                    [str(x) for x in llm_diagnoses.get("ed_diagnosis_texts", []) if x]
                )
                if not ed_texts:
                    # LLM 可能填了 discharge 字段
                    main_d = str(llm_diagnoses.get("discharge_main_diagnosis_text") or "").strip()
                    others_d = [str(x).strip() for x in (llm_diagnoses.get("discharge_other_diagnoses_texts") or []) if x]
                    if main_d:
                        ed_texts = _dedupe_non_empty([main_d] + others_d)

                if ed_texts:
                    diagnoses["ed_diagnosis_texts"] = ed_texts
                    diagnoses["admission_main_diagnosis_text"] = ed_texts[0]
                    diagnoses["admission_other_diagnoses_texts"] = ed_texts[1:]
                    diagnoses["discharge_main_diagnosis_text"] = ed_texts[0]
                    diagnoses["discharge_other_diagnoses_texts"] = ed_texts[1:]
                    llm_diags_ok = True
                    logger.info(
                        "extract-pre-group: LLM 诊断抽取成功, main=%s, other_count=%d",
                        ed_texts[0], len(ed_texts) - 1,
                    )
        except asyncio.TimeoutError:
            logger.warning("extract-pre-group: LLM 诊断抽取超时(30s)，回退到正则")
        except Exception:
            logger.exception("extract-pre-group: LLM 诊断抽取失败，回退到正则")

        # ========== 第二层：正则交叉验证 / 兜底 ==========
        parsed_diags = _extract_diag_candidates(medical_text)
        if llm_diags_ok and parsed_diags:
            # LLM 成功但可能漏掉诊断，用正则补全
            existing = set(d.lower().replace(" ", "") for d in diagnoses.get("ed_diagnosis_texts", []))
            added = []
            for pd in parsed_diags:
                if pd.lower().replace(" ", "") not in existing:
                    added.append(pd)
                    existing.add(pd.lower().replace(" ", ""))
            if added:
                diagnoses["ed_diagnosis_texts"].extend(added)
                diagnoses["admission_other_diagnoses_texts"].extend(added)
                diagnoses["discharge_other_diagnoses_texts"].extend(added)
                logger.info("extract-pre-group: 正则交叉补全 %d 条漏掉的诊断: %s", len(added), added)
        elif not llm_diags_ok and parsed_diags:
            # LLM 失败，完全用正则
            diagnoses["ed_diagnosis_texts"] = parsed_diags
            diagnoses["admission_main_diagnosis_text"] = parsed_diags[0]
            diagnoses["admission_other_diagnoses_texts"] = parsed_diags[1:]
            diagnoses["discharge_main_diagnosis_text"] = parsed_diags[0]
            diagnoses["discharge_other_diagnoses_texts"] = parsed_diags[1:]
            logger.info(
                "extract-pre-group: 正则兜底诊断成功, main=%s, other_count=%d",
                parsed_diags[0], max(len(parsed_diags) - 1, 0),
            )
        elif not llm_diags_ok:
            logger.warning("extract-pre-group: 正则兜底也未找到诊断")

        # ========== 手术抽取（正则） ==========
        parsed_proc = _extract_main_proc_candidate(medical_text)
        if parsed_proc:
            procedures["main_procedure_text"] = parsed_proc
            mapped_proc = _fast_map_procedure_code(parsed_proc)
            procedures["main_procedure_code"] = mapped_proc
            logger.info("extract-pre-group: fallback procedure filled main=%s", parsed_proc)
        else:
            logger.warning("extract-pre-group: no procedure candidate parsed from text")

        # ========== ICD 编码：本地编码库查询（医保版优先，用于入组） ==========
        from ..services.local_icd_service import lookup_diagnosis_code, lookup_procedure_code

        def _code_diagnosis(text: str) -> str:
            """本地编码库查诊断编码（医保版优先）"""
            if not text:
                return ""
            result = lookup_diagnosis_code(text, prefer_insurance=True)
            if result:
                logger.info("extract-pre-group: 编码库匹配 '%s' -> %s", text, result["code"])
                return result["code"]
            # 编码库未匹配时，再尝试 LLM 兜底
            logger.warning("extract-pre-group: 编码库未匹配 '%s'，尝试 LLM 兜底", text)
            return ""

        def _code_proc(text: str) -> str:
            """本地编码库查手术编码"""
            if not text:
                return ""
            result = lookup_procedure_code(text)
            if result:
                logger.info("extract-pre-group: 手术编码匹配 '%s' -> %s", text, result["code"])
                return result["code"]
            logger.warning("extract-pre-group: 手术编码库未匹配 '%s'", text)
            return ""

        # 编码所有诊断
        main_diag_text = diagnoses.get("admission_main_diagnosis_text") or ""
        main_icd = _code_diagnosis(main_diag_text)

        other_diag_texts = diagnoses.get("admission_other_diagnoses_texts") or []
        other_icds = [_code_diagnosis(t) for t in other_diag_texts]

        # 编码手术
        proc_text = procedures.get("main_procedure_text") or ""
        proc_code = _code_proc(proc_text)

        # 写入结果
        if main_icd:
            diagnoses["admission_main_icd"] = main_icd
            diagnoses["discharge_main_icd"] = main_icd
        if other_icds:
            diagnoses["admission_other_icds"] = other_icds
            diagnoses["discharge_other_icds"] = other_icds
        if proc_code:
            procedures["main_procedure_code"] = proc_code

        logger.info(
            "extract-pre-group: 并发编码完成 main_icd=%s other_icds=%s proc_code=%s",
            main_icd, other_icds, proc_code,
        )

        result = {
            "basic_info": basic_info,
            "diagnoses": diagnoses,
            "procedures": procedures,
            "costs": {"total_cost": None, "self_paid": None, "categories": {}},
        }

        admission_id = f"PRE_{uuid.uuid4().hex[:8]}"
        store = get_demo_drg_store()
        store.upsert_case(admission_id=admission_id, patch={
            "admission_id": admission_id,
            "diagnoses": diagnoses,
            "surgeries": procedures,
            "basic_info": basic_info,
            "costs": result["costs"],
        })
        result["admission_id"] = admission_id
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        logger.info(
            "extract-pre-group: completed elapsed_ms=%d diag_found=%d proc_found=%s main_icd=%s main_proc_code=%s",
            elapsed_ms,
            len(diagnoses.get("ed_diagnosis_texts", [])),
            bool(parsed_proc),
            diagnoses.get("admission_main_icd"),
            procedures.get("main_procedure_code"),
        )

        return {"success": True, "data": result}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
