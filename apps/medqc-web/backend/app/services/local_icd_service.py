"""
本地 ICD 编码查询服务

在 LLM 抽取出诊断/手术名称后，通过本地编码库进行精确匹配，
以国临版（clinical）编码为准，替换 LLM 直接输出的编码。

复用 icd_search.py 中的数据缓存，避免重复加载。
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


def _get_icd_data():
    """获取已加载的 ICD 编码数据（延迟导入避免循环依赖）"""
    from ..routers.icd_search import (
        _load_data,
        _icd10_clinical_data,
        _icd10_data,
        _icd9cm3_data,
        _code_mapping,
    )
    _load_data()
    return _icd10_clinical_data, _icd10_data, _icd9cm3_data, _code_mapping


def lookup_diagnosis_code(diagnosis_name: str) -> Optional[Dict[str, str]]:
    """
    根据诊断名称查询 ICD-10 国临版编码

    Args:
        diagnosis_name: 诊断名称（如"冠状动脉粥样硬化性心脏病"）

    Returns:
        {"code": "I25.103", "name": "冠状动脉粥样硬化性心脏病"} 或 None
    """
    if not diagnosis_name or not diagnosis_name.strip():
        return None

    clinical_data, insurance_data, _, _ = _get_icd_data()

    # 优先使用国临版
    source = clinical_data if clinical_data else insurance_data
    if not source:
        logger.warning("ICD-10 编码数据未加载")
        return None

    query = diagnosis_name.strip().lower()

    # 1. 精确匹配名称
    for item in source:
        if item['name_lower'] == query:
            return {'code': item['code'], 'name': item['name']}

    # 2. 名称包含匹配（取最高分）
    candidates = []
    for item in source:
        score = 0
        name_lower = item['name_lower']

        if name_lower == query:
            score = 100
        elif query in name_lower:
            # 名称以关键词开头得更高分
            if name_lower.startswith(query):
                score = 90
            else:
                score = 80
        elif name_lower in query:
            # 编码库名称是输入的子串（如"冠心病"在"冠状动脉粥样硬化性心脏病"中）
            score = 70

        if score > 0:
            candidates.append({
                'code': item['code'],
                'name': item['name'],
                '_score': score,
                '_len_diff': abs(len(item['name']) - len(diagnosis_name))
            })

    if candidates:
        # 按分数降序，同分则取名称长度最接近的
        candidates.sort(key=lambda x: (-x['_score'], x['_len_diff']))
        best = candidates[0]
        return {'code': best['code'], 'name': best['name']}

    return None


def lookup_procedure_code(procedure_name: str) -> Optional[Dict[str, str]]:
    """
    根据手术名称查询 ICD-9-CM-3 编码

    Args:
        procedure_name: 手术名称（如"经皮冠状动脉支架植入术"）

    Returns:
        {"code": "36.0700x003", "name": "经皮冠状动脉支架植入术"} 或 None
    """
    if not procedure_name or not procedure_name.strip():
        return None

    _, _, icd9_data, _ = _get_icd_data()
    if not icd9_data:
        logger.warning("ICD-9-CM-3 编码数据未加载")
        return None

    query = procedure_name.strip().lower()

    # 1. 精确匹配
    for item in icd9_data:
        if item['name_lower'] == query:
            return {'code': item['code'], 'name': item['name']}

    # 2. 模糊匹配
    candidates = []
    for item in icd9_data:
        score = 0
        name_lower = item['name_lower']

        if name_lower == query:
            score = 100
        elif query in name_lower:
            if name_lower.startswith(query):
                score = 90
            else:
                score = 80
        elif name_lower in query:
            score = 70

        if score > 0:
            candidates.append({
                'code': item['code'],
                'name': item['name'],
                '_score': score,
                '_len_diff': abs(len(item['name']) - len(procedure_name))
            })

    if candidates:
        candidates.sort(key=lambda x: (-x['_score'], x['_len_diff']))
        best = candidates[0]
        return {'code': best['code'], 'name': best['name']}

    return None


def resolve_diagnosis_codes(diagnoses: Dict[str, Any]) -> Dict[str, Any]:
    """
    用本地 ICD 编码库校正字典中所有诊断的编码

    修改并返回 diagnoses dict：
    - discharge_main_diagnosis_text → 查询 → 更新 discharge_main_icd
    - discharge_other_diagnoses_texts → 查询 → 更新 discharge_other_icds
    - admission_main_diagnosis_text → 查询 → 更新对应编码
    """
    if not diagnoses:
        return diagnoses

    resolved_count = 0

    # 主诊断
    main_text = diagnoses.get("discharge_main_diagnosis_text")
    if main_text:
        result = lookup_diagnosis_code(main_text)
        if result:
            old_code = diagnoses.get("discharge_main_icd")
            diagnoses["discharge_main_icd"] = result["code"]
            resolved_count += 1
            if old_code and old_code != result["code"]:
                logger.info(f"主诊断编码校正: {old_code} → {result['code']} ({main_text})")

    # 其他诊断
    other_texts = diagnoses.get("discharge_other_diagnoses_texts") or []
    if other_texts:
        other_codes = []
        for text in other_texts:
            result = lookup_diagnosis_code(text)
            if result:
                other_codes.append(result["code"])
                resolved_count += 1
            else:
                # 保留原编码（如果有的话）
                old_codes = diagnoses.get("discharge_other_icds") or []
                idx = other_texts.index(text)
                if idx < len(old_codes) and old_codes[idx]:
                    other_codes.append(old_codes[idx])
                else:
                    other_codes.append(None)
        diagnoses["discharge_other_icds"] = other_codes

    # 入院诊断
    adm_text = diagnoses.get("admission_main_diagnosis_text")
    if adm_text:
        result = lookup_diagnosis_code(adm_text)
        if result:
            diagnoses["admission_main_icd"] = result["code"]
            resolved_count += 1

    logger.info(f"本地 ICD-10 编码查询完成: 成功匹配 {resolved_count} 个诊断")
    return diagnoses


def resolve_procedure_codes(procedures: Dict[str, Any]) -> Dict[str, Any]:
    """
    用本地 ICD 编码库校正手术操作的编码

    修改并返回 procedures dict：
    - main_procedure_text → 查询 → 更新 main_procedure_code
    - other_procedures → 查询 → 更新各项 code
    """
    if not procedures:
        return procedures

    resolved_count = 0

    # 主手术
    main_text = procedures.get("main_procedure_text")
    if main_text:
        result = lookup_procedure_code(main_text)
        if result:
            old_code = procedures.get("main_procedure_code")
            procedures["main_procedure_code"] = result["code"]
            resolved_count += 1
            if old_code and old_code != result["code"]:
                logger.info(f"主手术编码校正: {old_code} → {result['code']} ({main_text})")

    # 其他手术
    others = procedures.get("other_procedures") or []
    for proc in others:
        text = proc.get("text") or proc.get("name")
        if text:
            result = lookup_procedure_code(text)
            if result:
                proc["code"] = result["code"]
                resolved_count += 1

    logger.info(f"本地 ICD-9-CM-3 编码查询完成: 成功匹配 {resolved_count} 个手术")
    return procedures
