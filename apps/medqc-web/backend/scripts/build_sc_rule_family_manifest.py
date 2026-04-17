from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


CURRENT_FILE = Path(__file__).resolve()
BACKEND_ROOT = CURRENT_FILE.parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.sc_rule_family_ab import build_sc_rule_family_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="构建四川规则 rule_family POC manifest")
    parser.add_argument("--schema", default="public", help="bundle schema，默认 public")
    parser.add_argument("--cohort-size", type=int, default=10, help="每个 cohort 样本数，默认 10")
    parser.add_argument("--limit-per-scene", type=int, default=500, help="每个 scene 最大候选数，默认 500")
    parser.add_argument(
        "--output",
        default="",
        help="输出 manifest JSON 文件路径；未传时写入 release-gate-artifacts/sc_rule_family_ab/",
    )
    args = parser.parse_args()

    manifest = build_sc_rule_family_manifest(
        schema=str(args.schema or "public"),
        cohort_size=max(1, int(args.cohort_size or 10)),
        limit_per_scene=max(50, int(args.limit_per_scene or 500)),
    )

    if args.output:
        output_path = Path(args.output).resolve()
    else:
        output_dir = BACKEND_ROOT / "release-gate-artifacts" / "sc_rule_family_ab"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"manifest-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"[OK] manifest written: {output_path}")
    print(f"[OK] manifest size: {len(manifest)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
