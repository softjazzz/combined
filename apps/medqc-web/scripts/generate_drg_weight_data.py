from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from openpyxl import load_workbook


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "2024年度三级公立医院绩效监测DRG权重和低风险组列表(2).xlsx"
TARGET = ROOT / "src" / "views" / "drg-grouper" / "drgWeightData.ts"
BACKEND_TARGET = ROOT / "backend" / "app" / "data" / "drg_weights.json"


def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def number_value(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    return round(float(value), 4)


def parse_drg_group(value: str) -> tuple[str, str]:
    match = re.match(r"^([A-Z]{2}\d{2})[-－](.+)$", value.strip())
    if not match:
        raise ValueError(f"无法解析 DRG 组: {value}")
    return match.group(1), match.group(2).strip()


def main() -> None:
    workbook = load_workbook(SOURCE, read_only=True, data_only=True)
    sheet = workbook["2024年度"]

    entries: list[dict[str, Any]] = []
    for row_number, row in enumerate(sheet.iter_rows(min_row=3, values_only=True), 3):
        if not row or row[0] is None:
            continue

        group_text = clean(row[0])
        drg_code, drg_name = parse_drg_group(group_text)
        entries.append(
            {
                "sourceRow": row_number,
                "drgCode": drg_code,
                "drgName": drg_name,
                "weight": number_value(row[1]),
                "isLowRisk": clean(row[2]) == "是",
            },
        )

    target_text = render_ts(entries)
    TARGET.write_text(target_text, encoding="utf-8", newline="\n")
    low_risk_count = sum(1 for item in entries if item["isLowRisk"])
    BACKEND_TARGET.write_text(
        json.dumps(
            {
                "meta": {
                    "country": "中国",
                    "year": 2024,
                    "source_file": SOURCE.name,
                    "group_count": len(entries),
                    "low_risk_count": low_risk_count,
                },
                "entries": entries,
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
        f"count={len(entries)} lowRisk={low_risk_count}",
    )


def render_ts(entries: list[dict[str, Any]]) -> str:
    entries_json = json.dumps(entries, ensure_ascii=False, indent=2)
    low_risk_count = sum(1 for item in entries if item["isLowRisk"])
    return f"""/**
 * 2024 年度三级公立医院绩效监测 DRG 权重和低风险组列表
 * 来源：docs/2024年度三级公立医院绩效监测DRG权重和低风险组列表(2).xlsx
 *
 * 由 scripts/generate_drg_weight_data.py 生成。
 * 请勿手工编辑本文件；源 Excel 更新后重新运行生成脚本。
 */

export interface DrgWeightEntry {{
  sourceRow: number
  drgCode: string
  drgName: string
  weight: number
  isLowRisk: boolean
}}

export const DRG_WEIGHT_DATASET_META = {{
  country: '中国',
  year: 2024,
  sourceFile: '2024年度三级公立医院绩效监测DRG权重和低风险组列表(2).xlsx',
  groupCount: {len(entries)},
  lowRiskCount: {low_risk_count},
}} as const

export const DRG_WEIGHT_ENTRIES: DrgWeightEntry[] = {entries_json}

export const DRG_WEIGHT_BY_CODE: Record<string, DrgWeightEntry> = buildDrgWeightMap()

export const LOW_RISK_DRG_CODES: Set<string> = new Set(
  DRG_WEIGHT_ENTRIES.filter((item) => item.isLowRisk).map((item) => item.drgCode),
)

export function getDrgWeightInfo(drgCode: string | undefined): DrgWeightEntry | undefined {{
  if (!drgCode) return undefined
  return DRG_WEIGHT_BY_CODE[drgCode.trim().toUpperCase()]
}}

function buildDrgWeightMap(): Record<string, DrgWeightEntry> {{
  const map: Record<string, DrgWeightEntry> = {{}}
  for (const item of DRG_WEIGHT_ENTRIES) {{
    if (!map[item.drgCode]) {{
      map[item.drgCode] = item
    }}
  }}
  return map
}}
"""


if __name__ == "__main__":
    main()
