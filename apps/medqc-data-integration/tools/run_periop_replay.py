"""第二批归档 replay 工作入口；必须显式指定单个接口与日期，无自动/增量模式。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from prepare_periop_takeover import (  # noqa: E402
    archived_batches,
    check_acl,
    publish,
    replay,
    write_report,
)

from medqc_ingest.domain import IngestError  # noqa: E402
from medqc_ingest.periop_replay import (  # noqa: E402
    PROFILE,
    explicit_window,
    load_profile,
    require,
    select_spec,
    validate_database,
)


def read_runtime(path):
    doc = json.loads(path.read_text(encoding="utf-8"))
    require(
        set(doc)
        == {
            "profile",
            "databases",
            "port",
            "runtime_passfile",
            "contract_sha256",
            "date_semantics",
            "source",
            "automatic_incremental",
        },
        "periop_runtime_keys",
    )
    require(
        doc["profile"] == PROFILE
        and doc["date_semantics"] == "unverified"
        and doc["source"] == "archive"
        and doc["automatic_incremental"] is False,
        "periop_runtime_profile",
    )
    require(
        set(doc["databases"]) == {"ingest", "cdm", "restore_ingest", "restore_cdm"},
        "periop_runtime_databases",
    )
    for role, name in doc["databases"].items():
        validate_database(name, role)
    require(type(doc["port"]) is int and 0 < doc["port"] < 65536, "periop_runtime_port")
    require(
        hashlib.sha256(
            (ROOT / "contracts/periop-acceptance-contracts.json").read_bytes()
        ).hexdigest()
        == doc["contract_sha256"],
        "periop_runtime_contract_hash",
    )
    return doc


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--interface", required=True)
    parser.add_argument("--date", required=True)
    args = parser.parse_args(argv)
    try:
        # 接口、日期先校验；拒绝未知来源时不读取任何运行配置/凭据。
        _contract, specs = load_profile(ROOT / "contracts/periop-acceptance-contracts.json")
        spec = select_spec(specs, args.interface)
        explicit_window(args.date)
        doc = read_runtime(args.config)
        require(not os.getenv("PGPASSWORD"), "periop_pgpassword_forbidden")
        require(os.name == "nt", "periop_customer_platform")
        check_acl(Path(doc["runtime_passfile"]))
        os.environ["MEDQC_PG_DRIVER"] = "psycopg2"
        runtime = SimpleNamespace(**dict(doc, runtime_passfile=Path(doc["runtime_passfile"])))
        runtime.admin_user = "postgres"  # 此入口从不请求管理员连接。
        runtime.synthetic = False
        runtime.pg_major = 16
        runtime.output = args.config.parent
        batches = [
            b
            for b in archived_batches(runtime)
            if b["interface_name"] == spec.name and b["source_date"] == args.date
        ]
        require(bool(batches), "periop_date_not_archived")
        batch = max(batches, key=lambda b: b["round_no"])
        result = replay(runtime, spec, batch)
        published = publish(runtime, spec)
        write_report(
            runtime,
            "replay-" + datetime.now().strftime("%Y%m%d%H%M%S%f") + ".json",
            {
                "interface": spec.name,
                "date": args.date,
                "source": "archive",
                "fetched": result.counts["fetched"],
                "changed": published.written,
                "checkpoint_state": result.checkpoint_state,
                "cache_accessed": False,
            },
        )
        print("PERIOP_ARCHIVE_REPLAY_PASSED")
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "exception_type": type(exc).__name__,
                    "sqlstate": getattr(exc, "pgcode", None),
                    "location": exc.location if isinstance(exc, IngestError) else None,
                }
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
