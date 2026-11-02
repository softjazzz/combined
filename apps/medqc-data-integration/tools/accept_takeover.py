"""接管库真实发布、回滚恢复和备份指纹入口。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from medqc_ingest.config import PassfilePostgresSettings
from medqc_ingest.deployment_acceptance import (
    fingerprints,
    publish_twice,
    rollback_and_recovery,
    verify_published,
)
from medqc_ingest.domain import IngestError
from medqc_ingest.takeover import validate_target_database


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("accept", "publish-check", "fingerprint"))
    parser.add_argument("--ingest-db", required=True)
    parser.add_argument("--cdm-db")
    parser.add_argument("--user", default="medqc_sync")
    parser.add_argument("--passfile", required=True, type=Path)
    parser.add_argument("--port", default=5432, type=int)
    parser.add_argument("--kind", choices=("ingest", "cdm"), default="ingest")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        ingest = PassfilePostgresSettings(
            "127.0.0.1", args.port, args.ingest_db, args.user, args.passfile
        )
        if args.mode == "fingerprint":
            report = {"tables": fingerprints(ingest, args.kind)}
        else:
            validate_target_database(args.ingest_db)
            validate_target_database(args.cdm_db or "", "cdm")
            cdm = PassfilePostgresSettings(
                "127.0.0.1", args.port, args.cdm_db, args.user, args.passfile
            )
            report = {
                "rollback_recovery": rollback_and_recovery(ingest)
                if args.mode == "accept"
                else "not_repeated",
                "publish_rounds": publish_twice(ingest, cdm),
                "field_equality": verify_published(ingest, cdm),
                "real_postgres_executed": True,
                "cache_accessed": False,
                "full_rule_engine_executed": False,
            }
        report.update(contains_phi=False, contains_raw_values=False)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        print(f"{args.mode} succeeded")
        return 0
    except IngestError as exc:
        print(f"failed kind={exc.kind} location={exc.location}", file=sys.stderr)
        return 1
    except Exception:
        print("failed kind=unexpected_error location=takeover_acceptance", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
