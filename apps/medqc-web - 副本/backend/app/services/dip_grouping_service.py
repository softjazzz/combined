"""
DIP 分组服务。

运行时读取已生成的泸州市 DIP 病种库 JSON，不再依赖 Excel 或硬编码 mock 规则。
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .drg_config_store import get_runtime_grouping_config

logger = logging.getLogger(__name__)

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "luzhou_dip_groups.json"


def _normalize_code(code: str | None) -> str:
    return (code or "").strip().upper()


def _split_codes(value: str | Iterable[str] | None) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_items = value.replace("，", ",").split(",")
    else:
        raw_items = list(value)
    return [_normalize_code(item) for item in raw_items if _normalize_code(str(item))]


@lru_cache(maxsize=1)
def _load_dataset() -> Dict[str, Any]:
    with DATA_PATH.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    core = payload.get("core_diseases") or []
    comprehensive = payload.get("comprehensive_diseases") or []
    core_by_key = {item.get("matchKey"): item for item in core if item.get("matchKey")}
    diagnosis_names: Dict[str, str] = {}
    valid_diagnoses = set()
    for item in core:
        code = _normalize_code(item.get("diagnosisCode"))
        if not code:
            continue
        valid_diagnoses.add(code)
        diagnosis_names.setdefault(code, item.get("diagnosisName") or "")

    return {
        "meta": payload.get("meta") or {},
        "core": core,
        "comprehensive": comprehensive,
        "core_by_key": core_by_key,
        "valid_diagnoses": valid_diagnoses,
        "diagnosis_names": diagnosis_names,
    }


def _try_fuzzy_diagnosis_match(code: str, valid_diagnoses: set[str]) -> Optional[str]:
    if "." not in code:
        return None

    prefix, suffix = code.split(".", 1)
    for length in range(len(suffix), 0, -1):
        candidate = f"{prefix}.{suffix[:length]}"
        if candidate in valid_diagnoses:
            return candidate

    category_prefix = f"{prefix}."
    candidates = sorted(item for item in valid_diagnoses if item.startswith(category_prefix))
    if candidates:
        return candidates[-1]

    return None


def _build_success(
    *,
    entry: Dict[str, Any],
    pdx_code: str,
    original_pdx_code: str,
    proc_code: str,
    matched_proc_code: str = "",
    matched_related_proc_code: str = "",
    match_type: str,
    messages: List[str],
    city_name: str,
    los: int,
    total_fee: float,
    runtime_config: Dict[str, Any],
) -> Dict[str, Any]:
    disease_attribute = entry.get("diseaseAttribute") or ""
    grassroots_flag = entry.get("primaryCareFlag") or ""
    score = float(entry.get("score") or 0)
    simulated_payment = round(
        score
        * float(runtime_config.get("base_rate") or 0)
        * float(runtime_config.get("hospital_coefficient") or 1)
        * float(runtime_config.get("region_coefficient") or 1),
        2,
    )
    cost_ratio = round(total_fee / simulated_payment, 4) if simulated_payment > 0 else 0
    high_threshold = float(runtime_config.get("high_rate_threshold") or 3)
    low_threshold = float(runtime_config.get("low_rate_threshold") or 0.5)
    cost_group = "base"
    if cost_ratio >= high_threshold:
        cost_group = "high_cost"
    elif simulated_payment > 0 and cost_ratio <= low_threshold:
        cost_group = "low_cost"
    return {
        "success": True,
        "status": "分组成功",
        "dip_code": entry.get("dipCode") or "",
        "dip_name": entry.get("dipName") or "",
        "dip_type": entry.get("source") or "",
        "score": score,
        "disease_property": disease_attribute,
        "disease_attribute": disease_attribute,
        "grassroots_disease_flag": grassroots_flag,
        "primary_care_flag": grassroots_flag,
        "grouping_path": "；".join(messages),
        "match_type": match_type,
        "city_name": city_name,
        "pdx_code": original_pdx_code or pdx_code,
        "matched_pdx_code": pdx_code,
        "proc_code": proc_code,
        "matched_proc_code": matched_proc_code,
        "matched_related_proc_code": matched_related_proc_code,
        "los": los,
        "total_fee": total_fee,
        "simulated_payment": simulated_payment,
        "cost_ratio": cost_ratio,
        "cost_group": cost_group,
        "config_version_id": runtime_config.get("config_version_id"),
        "runtime_config": {
            "base_rate": runtime_config.get("base_rate"),
            "hospital_coefficient": runtime_config.get("hospital_coefficient"),
            "region_coefficient": runtime_config.get("region_coefficient"),
            "high_rate_threshold": runtime_config.get("high_rate_threshold"),
            "low_rate_threshold": runtime_config.get("low_rate_threshold"),
        },
        "messages": messages,
        "data_source": "backend/app/data/luzhou_dip_groups.json",
    }


class DIPGrouperService:
    """泸州市 DIP 分组服务。"""

    async def group_dip(
        self,
        city_name: str,
        pdx_code: str,
        adx_code: str = "",
        proc_code: str = "",
        patient_gender: str = "M",
        patient_age: int = 50,
        los: int = 7,
        total_fee: float = 0,
    ) -> Dict[str, Any]:
        del adx_code, patient_gender, patient_age

        logger.info("DIP 分组请求: city=%s, pdx=%s, proc=%s", city_name, pdx_code, proc_code)
        dataset = _load_dataset()
        runtime_config = get_runtime_grouping_config()
        core_by_key: Dict[str, Dict[str, Any]] = dataset["core_by_key"]
        valid_diagnoses: set[str] = dataset["valid_diagnoses"]
        diagnosis_names: Dict[str, str] = dataset["diagnosis_names"]

        original_pdx = _normalize_code(pdx_code)
        if not original_pdx:
            return {
                "success": False,
                "status": "未入组",
                "error": "主诊断编码不能为空",
                "messages": ["主诊断编码不能为空"],
                "data_source": str(DATA_PATH),
            }

        messages: List[str] = []
        matched_pdx = original_pdx
        if matched_pdx not in valid_diagnoses:
            fuzzy = _try_fuzzy_diagnosis_match(matched_pdx, valid_diagnoses)
            if fuzzy:
                messages.append(f"主诊断 {matched_pdx} 不在病种库中，模糊匹配到 {fuzzy}")
                matched_pdx = fuzzy
            else:
                diagnosis_name = diagnosis_names.get(matched_pdx, "未知诊断")
                return {
                    "success": False,
                    "status": "未入组",
                    "pdx_code": original_pdx,
                    "primary_diagnosis_name": diagnosis_name,
                    "error": f"主诊断 {original_pdx} 不在泸州 DIP 病种库中",
                    "messages": [f"主诊断 {original_pdx} 不在泸州 DIP 病种库中"],
                    "data_source": str(DATA_PATH),
                }

        procedures = _split_codes(proc_code)
        main_proc = procedures[0] if procedures else ""

        if main_proc and len(procedures) > 1:
            for rel_proc in procedures[1:]:
                key = f"{matched_pdx}|{main_proc}|{rel_proc}"
                entry = core_by_key.get(key)
                if entry:
                    messages.append(f"精确匹配: {matched_pdx} + {main_proc} + 相关手术 {rel_proc}")
                    return _build_success(
                        entry=entry,
                        pdx_code=matched_pdx,
                        original_pdx_code=original_pdx,
                        proc_code=proc_code,
                        matched_proc_code=main_proc,
                        matched_related_proc_code=rel_proc,
                        match_type="诊断+手术+相关手术",
                        messages=messages,
                        city_name=city_name,
                        los=los,
                        total_fee=total_fee,
                        runtime_config=runtime_config,
                    )

        if main_proc:
            key = f"{matched_pdx}|{main_proc}"
            entry = core_by_key.get(key)
            if entry:
                messages.append(f"标准匹配: {matched_pdx} + {main_proc}")
                return _build_success(
                    entry=entry,
                    pdx_code=matched_pdx,
                    original_pdx_code=original_pdx,
                    proc_code=proc_code,
                    matched_proc_code=main_proc,
                    match_type="诊断+手术",
                    messages=messages,
                    city_name=city_name,
                    los=los,
                    total_fee=total_fee,
                    runtime_config=runtime_config,
                )

            for alt_proc in procedures[1:]:
                alt_key = f"{matched_pdx}|{alt_proc}"
                entry = core_by_key.get(alt_key)
                if entry:
                    messages.append(f"备选手术匹配: {matched_pdx} + {alt_proc}")
                    return _build_success(
                        entry=entry,
                        pdx_code=matched_pdx,
                        original_pdx_code=original_pdx,
                        proc_code=proc_code,
                        matched_proc_code=alt_proc,
                        match_type="诊断+手术",
                        messages=messages,
                        city_name=city_name,
                        los=los,
                        total_fee=total_fee,
                        runtime_config=runtime_config,
                    )

            messages.append(f"诊断+手术组合未匹配: {matched_pdx} + {main_proc}")

        entry = core_by_key.get(matched_pdx)
        if entry:
            messages.append(f"纯诊断分组: {matched_pdx}")
            return _build_success(
                entry=entry,
                pdx_code=matched_pdx,
                original_pdx_code=original_pdx,
                proc_code=proc_code,
                match_type="纯诊断",
                messages=messages,
                city_name=city_name,
                los=los,
                total_fee=total_fee,
                runtime_config=runtime_config,
            )

        diagnosis_name = diagnosis_names.get(matched_pdx, "未知诊断")
        messages.append(f"主诊断 {matched_pdx}（{diagnosis_name}）存在，但无法匹配当前编码组合")
        return {
            "success": False,
            "status": "未入组",
            "pdx_code": original_pdx,
            "matched_pdx_code": matched_pdx,
            "primary_diagnosis_name": diagnosis_name,
            "proc_code": proc_code,
            "error": "无法匹配当前编码组合",
            "messages": messages,
            "data_source": str(DATA_PATH),
        }
