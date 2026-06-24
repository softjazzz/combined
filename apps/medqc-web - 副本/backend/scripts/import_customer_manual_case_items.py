from __future__ import annotations

import argparse
import os
import sys


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.services.custom_qc_sample_pool_service import (  # noqa: E402
    CustomQCSamplePoolService,
    load_manual_case_rows_from_excel,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="导入客户人工问题样本池（Sheet2）")
    parser.add_argument("--file", required=True, help="Excel 文件路径")
    parser.add_argument("--sheet", default="Sheet2", help="Sheet 名称")
    parser.add_argument("--name", required=True, help="样本池名称")
    parser.add_argument("--scene", default="running", help="场景，默认 running")
    parser.add_argument("--created-by", default="script", help="创建人")
    parser.add_argument("--description", default="", help="备注")
    args = parser.parse_args()

    file_path = os.path.abspath(args.file)
    rows = load_manual_case_rows_from_excel(file_path=file_path, sheet_name=args.sheet)
    if not rows:
        raise SystemExit("未读取到有效样本行")

    service = CustomQCSamplePoolService()
    pool = service.create_pool_with_items(
        name=args.name,
        source_file=file_path,
        source_sheet=args.sheet,
        created_by=args.created_by,
        rows=rows,
        description=args.description,
        scene=args.scene,
    )
    print(
        {
            "pool_id": pool["id"],
            "pool_name": pool["name"],
            "source_file": pool["source_file"],
            "imported_rows": len(rows),
            "llm_intrinsic_items": pool["llm_intrinsic_items"],
            "programmatic_items": pool["programmatic_items"],
            "unsupported_items": pool["unsupported_items"],
        }
    )


if __name__ == "__main__":
    main()
