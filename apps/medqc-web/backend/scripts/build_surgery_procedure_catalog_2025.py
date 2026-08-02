"""从院内 Excel 生成可随客户版本发布的手术/操作确定性目录。"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

from openpyxl import load_workbook


DEFAULT_SOURCE = (
    Path(__file__).resolve().parents[4]
    / "docs"
    / "手术操作分类代码国家临床版3.0（2025绩效手术分级目录）.xlsx"
)
DEFAULT_OUTPUT = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "data"
    / "surgery_procedure_catalog_2025.csv"
)
CATALOG_SHEET = "2025年手术分级目录"
PERFORMANCE_SHEET = "手术绩效分配"


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _effective_level(raw_level: str) -> str:
    normalized = _clean(raw_level).upper()
    if normalized in {"国考四级手术", "院内四级", "条件四级", "介入四级", "四级", "4", "Ⅳ", "IV"}:
        return "四级"
    if normalized in {"院内三级", "介入三级", "三级", "3", "Ⅲ", "III"}:
        return "三级"
    if normalized in {"二级", "2", "Ⅱ", "II"}:
        return "二级"
    if normalized in {"一级", "1", "Ⅰ", "I"}:
        return "一级"
    return ""


def _read_rows(workbook, sheet_name: str, *, level_index: int, source: str):
    rows: dict[str, tuple[str, str, str, str, str]] = {}
    worksheet = workbook[sheet_name]
    for values in worksheet.iter_rows(min_row=2, max_col=5, values_only=True):
        code = _clean(values[0])
        name = _clean(values[1])
        category = _clean(values[2])
        raw_level = _clean(values[level_index])
        if not code or not name or not category:
            continue
        rows[code.upper()] = (
            name,
            category,
            _effective_level(raw_level),
            raw_level,
            source,
        )
    return rows


def build_catalog(source: Path, output: Path) -> int:
    workbook = load_workbook(source, read_only=True, data_only=True)
    merged = _read_rows(
        workbook,
        CATALOG_SHEET,
        level_index=3,
        source="national_catalog",
    )
    # 院内绩效分配是本院正式优先口径，同编码无条件覆盖国家目录。
    merged.update(
        _read_rows(
            workbook,
            PERFORMANCE_SHEET,
            level_index=4,
            source="hospital_performance",
        )
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(
            ("code", "name", "category", "effective_level", "raw_level", "source")
        )
        for code in sorted(merged):
            writer.writerow((code, *merged[code]))
    return len(merged)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    count = build_catalog(args.source, args.output)
    print(f"generated {count} surgery/procedure catalog rows: {args.output}")


if __name__ == "__main__":
    main()
