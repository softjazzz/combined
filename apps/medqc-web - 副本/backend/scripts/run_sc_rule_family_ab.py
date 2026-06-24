from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path


CURRENT_FILE = Path(__file__).resolve()
BACKEND_ROOT = CURRENT_FILE.parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.sc_rule_family_ab import (
    DEFAULT_COHORT_SIZE,
    DEFAULT_REPLAY_ROUNDS,
    build_sc_rule_family_manifest,
    run_sc_rule_family_ab_experiment,
)


def _load_manifest(manifest_path: Path) -> list[dict[str, str]]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("manifest 文件必须是数组")
    return [dict(item) for item in payload if isinstance(item, dict)]


def main() -> int:
    parser = argparse.ArgumentParser(description="运行四川规则 rule_family A/B 离线回放实验")
    parser.add_argument("--schema", default="public", help="bundle schema，默认 public")
    parser.add_argument("--rounds", type=int, default=DEFAULT_REPLAY_ROUNDS, help="回放轮次，默认 2")
    parser.add_argument("--cohort-size", type=int, default=DEFAULT_COHORT_SIZE, help="每个 cohort 样本数，默认 10")
    parser.add_argument("--limit-per-scene", type=int, default=500, help="每个 scene 最大候选数，默认 500")
    parser.add_argument("--manifest", default="", help="已冻结 manifest JSON 路径；未传时现场构建")
    parser.add_argument("--output-dir", default="", help="输出目录；未传时自动生成时间戳目录")
    args = parser.parse_args()

    if args.manifest:
        manifest_path = Path(args.manifest).resolve()
        manifest = _load_manifest(manifest_path)
    else:
        manifest = build_sc_rule_family_manifest(
            schema=str(args.schema or "public"),
            cohort_size=max(1, int(args.cohort_size or DEFAULT_COHORT_SIZE)),
            limit_per_scene=max(50, int(args.limit_per_scene or 500)),
        )

    output_dir = (
        Path(args.output_dir).resolve()
        if args.output_dir
        else BACKEND_ROOT
        / "release-gate-artifacts"
        / "sc_rule_family_ab"
        / datetime.now().strftime("%Y%m%d-%H%M%S")
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    result = asyncio.run(
        run_sc_rule_family_ab_experiment(
            manifest=manifest,
            schema=str(args.schema or "public"),
            rounds=max(1, int(args.rounds or DEFAULT_REPLAY_ROUNDS)),
            output_dir=output_dir,
        )
    )

    print(f"[OK] output dir: {output_dir}")
    for file_name, file_path in dict(result.get('paths') or {}).items():
        print(f"[OK] {file_name}: {file_path}")
    print(f"[OK] manifest size: {result.get('manifest_size')}")
    print(f"[OK] rule count: {result.get('rule_count')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
