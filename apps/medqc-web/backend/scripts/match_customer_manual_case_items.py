from __future__ import annotations

import argparse
import os
import sys


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.services.custom_qc_sample_pool_service import CustomQCSamplePoolService  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="按住院号匹配客户人工问题样本池到系统病历")
    parser.add_argument("--pool-id", required=True, help="样本池 ID")
    args = parser.parse_args()

    service = CustomQCSamplePoolService()
    result = service.match_pool_items(pool_id=args.pool_id)
    print(result)


if __name__ == "__main__":
    main()
