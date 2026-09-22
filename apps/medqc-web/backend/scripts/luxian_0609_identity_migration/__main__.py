"""命令入口：默认只盘点；--apply 只接受受控计划，且需要显式确认。"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from .service import (
    MAPPING_VERSION,
    MigrationBlocked,
    apply_plan,
    build_plan,
    load_mapping,
    read_private_plan,
    write_private_plan,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="LX0609 历史规则身份离线迁移（默认 dry-run）")
    parser.add_argument("--database-url", required=True, help="必须是隔离的数据库快照 URL")
    parser.add_argument("--schema")
    parser.add_argument("--mapping-version", default=MAPPING_VERSION)
    parser.add_argument("--summary-out")
    parser.add_argument("--plan-out", help="只能写入 .tmp/0910-full-audit/*-private.json")
    parser.add_argument("--plan-in", help="apply 时读取已审阅的私有计划")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-apply", action="store_true")
    args = parser.parse_args()
    try:
        plan = (
            read_private_plan(args.plan_in)
            if args.plan_in
            else build_plan(
                args.database_url,
                schema=args.schema,
                expected_mapping_version=args.mapping_version,
            )
        )
        summary = plan.safe_summary()
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        if args.summary_out:
            Path(args.summary_out).write_text(
                json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        if args.plan_out:
            write_private_plan(plan, args.plan_out)
        if args.apply:
            if not args.confirm_apply:
                raise MigrationBlocked("apply_requires_confirm_apply")
            if not args.plan_in:
                raise MigrationBlocked("apply_requires_reviewed_plan_in")
            mapping = load_mapping(expected_version=args.mapping_version)
            apply_plan(
                args.database_url,
                plan,
                schema=args.schema,
                expected_mapping_version=args.mapping_version,
                expected_mapping_digest=mapping.digest,
            )
        return 0 if plan.ready else 2
    except MigrationBlocked as exc:
        print(json.dumps({"ready": False, "blocked": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
