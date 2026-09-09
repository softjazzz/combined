"""开发机使用：只读提取指定 CDM Excel，客户机无需 openpyxl。"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import openpyxl


def extract(path: Path) -> dict:
    book = openpyxl.load_workbook(path, read_only=True, data_only=True)
    tables = []
    try:
        for row_no, row in enumerate(
            book.worksheets[0].iter_rows(min_row=2, max_col=10, values_only=True), 2
        ):
            if not row[1]:
                continue
            name = str(row[1]).strip()
            title = str(row[0]).strip()
            sheet = book[title] if title in book.sheetnames else None
            fields = []
            notes = []
            if sheet is not None:
                # 字段定义固定在前14列；个别工作表格式延伸到16383列。
                for field_row, cells in enumerate(
                    sheet.iter_rows(min_row=2, max_col=14, values_only=True), 2
                ):
                    if not cells[0]:
                        if any(x is not None for x in cells):
                            notes.append({'row': field_row, 'cells': list(cells)})
                        continue
                    fields.append({
                        'name': str(cells[0]).strip(), 'label': cells[1],
                        'type': cells[4], 'logical_primary_key': cells[9],
                        'logical_foreign_key': cells[10], 'parent_table': cells[11],
                        'sheet_row': field_row, 'raw_cells': list(cells),
                    })
            tables.append({
                'name': name, 'label': title, 'directory_row': row_no,
                'directory_cells': list(row),
                'sheet': sheet.title if sheet else None,
                'sheet_status': 'found' if sheet else 'missing',
                'fields': fields, 'notes': notes,
            })
        return {
            'schema_version': 'medqc-cdm-dictionary-v1',
            'source_file': path.name,
            'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'table_count': len(tables), 'tables': tables,
            'note': '逻辑键和父表按字典原文保留，不等于数据库物理约束或已批准的JOIN。',
        }
    finally:
        book.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('workbook', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = extract(args.workbook)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({
        'tables': result['table_count'],
        'fields': sum(len(t['fields']) for t in result['tables']),
        'missing_sheets': [t['name'] for t in result['tables'] if t['sheet_status'] != 'found'],
        'duplicate_names': sorted({t['name'] for t in result['tables']
                                  if sum(x['name'] == t['name'] for x in result['tables']) > 1}),
    }, ensure_ascii=True))
