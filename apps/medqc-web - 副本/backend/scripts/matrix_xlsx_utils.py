#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Any

from openpyxl import Workbook


def write_matrix_xlsx(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "matrix"
    sheet.append(fieldnames)
    for row in rows:
        sheet.append([row.get(field, "") for field in fieldnames])
    workbook.save(path)
