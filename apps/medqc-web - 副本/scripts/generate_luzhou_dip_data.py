from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openpyxl import load_workbook


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "0602" / "泸市医保函〔2025〕3号附件-泸州市DIP核心和综合组.xlsx"
TARGET = ROOT / "src" / "views" / "drg-grouper" / "luzhouDipData.ts"
BACKEND_TARGET = ROOT / "backend" / "app" / "data" / "luzhou_dip_groups.json"


def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def score_value(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    return round(float(value), 2)


def build_match_key(diagnosis_code: str, procedure_code: str, related_procedure_code: str) -> str:
    parts = [diagnosis_code]
    if procedure_code:
        parts.append(procedure_code)
    if related_procedure_code:
        parts.append(related_procedure_code)
    return "|".join(parts)


def main() -> None:
    workbook = load_workbook(SOURCE, read_only=True, data_only=True)

    core_entries: list[dict[str, Any]] = []
    core_sheet = workbook["核心病种"]
    for row in core_sheet.iter_rows(min_row=4, values_only=True):
        if not row or row[0] is None:
            continue
        (
            serial_no,
            diagnosis_code,
            diagnosis_name,
            procedure_code,
            procedure_name,
            related_procedure_code,
            related_procedure_name,
            score,
            disease_attribute,
            primary_care_flag,
        ) = row[:10]

        diagnosis_code_text = clean(diagnosis_code)
        procedure_code_text = clean(procedure_code)
        related_procedure_code_text = clean(related_procedure_code)
        diagnosis_name_text = clean(diagnosis_name)
        procedure_name_text = clean(procedure_name)
        related_procedure_name_text = clean(related_procedure_name)
        dip_name = diagnosis_name_text
        if procedure_name_text:
            dip_name = f"{dip_name}:{procedure_name_text}"
        if related_procedure_name_text:
            dip_name = f"{dip_name}+{related_procedure_name_text}"

        core_entries.append(
            {
                "source": "核心病种",
                "serialNo": int(serial_no),
                "dipCode": build_match_key(
                    diagnosis_code_text,
                    procedure_code_text,
                    related_procedure_code_text,
                ),
                "dipName": dip_name,
                "matchKey": build_match_key(
                    diagnosis_code_text,
                    procedure_code_text,
                    related_procedure_code_text,
                ),
                "diagnosisCode": diagnosis_code_text,
                "diagnosisName": diagnosis_name_text,
                "mainProcedureCode": procedure_code_text,
                "mainProcedureName": procedure_name_text,
                "relatedProcedureCode": related_procedure_code_text,
                "relatedProcedureName": related_procedure_name_text,
                "score": score_value(score),
                "diseaseAttribute": clean(disease_attribute),
                "primaryCareFlag": clean(primary_care_flag),
            },
        )

    comprehensive_entries: list[dict[str, Any]] = []
    comprehensive_sheet = workbook["综合病种"]
    for row in comprehensive_sheet.iter_rows(min_row=4, values_only=True):
        if not row or row[0] is None:
            continue
        serial_no, combo_code, combo_name, score, disease_attribute = row[:5]
        combo_code_text = clean(combo_code)
        diagnosis_scope = combo_code_text
        operation_category = ""
        if ":" in combo_code_text:
            diagnosis_scope, operation_category = combo_code_text.split(":", 1)

        comprehensive_entries.append(
            {
                "source": "综合病种",
                "serialNo": int(serial_no),
                "dipCode": combo_code_text,
                "dipName": clean(combo_name),
                "diagnosisScope": diagnosis_scope,
                "operationCategory": operation_category,
                "score": score_value(score),
                "diseaseAttribute": clean(disease_attribute),
            },
        )

    target_text = render_ts(core_entries, comprehensive_entries)
    TARGET.write_text(target_text, encoding="utf-8", newline="\n")
    BACKEND_TARGET.write_text(
        json.dumps(
            {
                "meta": {
                    "region": "泸州市",
                    "year": 2025,
                    "source_file": SOURCE.name,
                    "core_count": len(core_entries),
                    "comprehensive_count": len(comprehensive_entries),
                },
                "core_diseases": core_entries,
                "comprehensive_diseases": comprehensive_entries,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        f"Generated {TARGET.relative_to(ROOT)} "
        f"and {BACKEND_TARGET.relative_to(ROOT)} "
        f"core={len(core_entries)} comprehensive={len(comprehensive_entries)}",
    )


def render_ts(core_entries: list[dict[str, Any]], comprehensive_entries: list[dict[str, Any]]) -> str:
    core_json = json.dumps(core_entries, ensure_ascii=False, indent=2)
    comprehensive_json = json.dumps(comprehensive_entries, ensure_ascii=False, indent=2)
    return f"""/**
 * 泸州市 DIP 核心和综合病种库
 * 来源：docs/0602/泸市医保函〔2025〕3号附件-泸州市DIP核心和综合组.xlsx
 *
 * 由 scripts/generate_luzhou_dip_data.py 生成。
 * 请勿手工编辑本文件；源 Excel 更新后重新运行生成脚本。
 */

export interface LuzhouDipCoreDisease {{
  source: '核心病种'
  serialNo: number
  dipCode: string
  dipName: string
  matchKey: string
  diagnosisCode: string
  diagnosisName: string
  mainProcedureCode: string
  mainProcedureName: string
  relatedProcedureCode: string
  relatedProcedureName: string
  score: number
  diseaseAttribute: string
  primaryCareFlag: string
}}

export interface LuzhouDipComprehensiveDisease {{
  source: '综合病种'
  serialNo: number
  dipCode: string
  dipName: string
  diagnosisScope: string
  operationCategory: string
  score: number
  diseaseAttribute: string
}}

export const LUZHOU_DIP_DATASET_META = {{
  region: '泸州市',
  year: 2025,
  sourceFile: '泸市医保函〔2025〕3号附件-泸州市DIP核心和综合组.xlsx',
  coreCount: {len(core_entries)},
  comprehensiveCount: {len(comprehensive_entries)},
}} as const

export const LUZHOU_DIP_CORE_DISEASES: LuzhouDipCoreDisease[] = {core_json}

export const LUZHOU_DIP_COMPREHENSIVE_DISEASES: LuzhouDipComprehensiveDisease[] = {comprehensive_json}

export const LUZHOU_DIP_CORE_BY_KEY: Record<string, LuzhouDipCoreDisease> = buildCoreEntryMap()

export const LUZHOU_DIP_COMPREHENSIVE_BY_CODE: Record<string, LuzhouDipComprehensiveDisease> =
  buildComprehensiveEntryMap()

/** 纯诊断 → 病种名称（无手术操作的病种） */
export const ZD_ONLY_MAP: Record<string, string> = buildNameMap((item) => !item.mainProcedureCode)

/** 诊断+手术 → 病种名称 key: "ZD|SS" */
export const ZD_SS_MAP: Record<string, string> = buildNameMap(
  (item) => !!item.mainProcedureCode && !item.relatedProcedureCode,
)

/** 诊断+手术+相关手术 → 病种名称 key: "ZD|SS|REL_SS" */
export const ZD_SS_REL_MAP: Record<string, string> = buildNameMap(
  (item) => !!item.mainProcedureCode && !!item.relatedProcedureCode,
)

/** 所有有效的诊断编码集合 */
export const VALID_ZD_CODES: Set<string> = new Set(
  LUZHOU_DIP_CORE_DISEASES.map((item) => item.diagnosisCode),
)

/** 诊断编码 → 诊断名称 */
export const ZD_NAMES: Record<string, string> = buildDiagnosisNameMap()

function buildCoreEntryMap(): Record<string, LuzhouDipCoreDisease> {{
  const map: Record<string, LuzhouDipCoreDisease> = {{}}
  for (const item of LUZHOU_DIP_CORE_DISEASES) {{
    if (!map[item.matchKey]) {{
      map[item.matchKey] = item
    }}
  }}
  return map
}}

function buildComprehensiveEntryMap(): Record<string, LuzhouDipComprehensiveDisease> {{
  const map: Record<string, LuzhouDipComprehensiveDisease> = {{}}
  for (const item of LUZHOU_DIP_COMPREHENSIVE_DISEASES) {{
    if (!map[item.dipCode]) {{
      map[item.dipCode] = item
    }}
  }}
  return map
}}

function buildNameMap(
  predicate: (item: LuzhouDipCoreDisease) => boolean,
): Record<string, string> {{
  const map: Record<string, string> = {{}}
  for (const item of LUZHOU_DIP_CORE_DISEASES) {{
    if (predicate(item) && !map[item.matchKey]) {{
      map[item.matchKey] = item.dipName
    }}
  }}
  return map
}}

function buildDiagnosisNameMap(): Record<string, string> {{
  const map: Record<string, string> = {{}}
  for (const item of LUZHOU_DIP_CORE_DISEASES) {{
    if (!map[item.diagnosisCode]) {{
      map[item.diagnosisCode] = item.diagnosisName
    }}
  }}
  return map
}}
"""


if __name__ == "__main__":
    main()
