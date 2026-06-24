#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.custom_qc_sample_pool_service import CustomQCSamplePoolService


def _resolve_pool_id(service: CustomQCSamplePoolService, identifier: str) -> str:
    text = str(identifier or "").strip()
    if not text:
        raise ValueError("pool 标识不能为空")
    pool = service.get_pool(pool_id=text)
    if pool:
        return text
    result = service.list_pools(page=1, page_size=200, query=text)
    for item in list(result.items or []):
        if str(item.get("name") or "").strip() == text:
            return str(item.get("id") or "").strip()
    raise RuntimeError(f"未找到样本池: {text}")


def main() -> None:
    parser = argparse.ArgumentParser(description="刷新已有样本池 item 的问题分类与候选规则")
    parser.add_argument("--pool", required=True, help="样本池 id 或名称，例如 0426")
    parser.add_argument("--only-unclassified", action="store_true", help="仅重刷当前 issue_category=unclassified 的 item")
    args = parser.parse_args()

    service = CustomQCSamplePoolService()
    pool_id = _resolve_pool_id(service, args.pool)
    result = service.refresh_pool_item_classifications(
        pool_id=pool_id,
        only_unclassified=bool(args.only_unclassified),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
