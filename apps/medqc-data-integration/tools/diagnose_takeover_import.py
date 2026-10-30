"""只给冻结0.3导入加安全异常观察；不改原包，不执行初始化/发布或创建数据库。"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

BASE_COMMIT = "df543a8f4d6d3fdfa402b98af10337d391910db4"
SOURCE = "medqc_bundle_time_clone_20261029180906"


def safe_exception_chain(error: BaseException, root: Path) -> list[dict[str, Any]]:
    """from None只隐藏显示，__context__仍在；不访问消息、args、SQL、diag或locals。"""
    result = []
    visited: set[int] = set()
    while error is not None and id(error) not in visited and len(result) < 8:
        visited.add(id(error))
        name = type(error).__name__
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,79}", name):
            name = "UnrecognizedException"
        code = getattr(error, "sqlstate", None) or getattr(error, "pgcode", None)
        if not isinstance(code, str) or not re.fullmatch(r"[0-9A-Z]{5}", code):
            code = None
        frames = []
        trace = error.__traceback__
        while trace is not None:
            path = Path(trace.tb_frame.f_code.co_filename).resolve()
            if path.is_relative_to(root.resolve()):
                frames.append(
                    {
                        "file": path.relative_to(root.resolve()).as_posix(),
                        "line": trace.tb_lineno,
                        "function": trace.tb_frame.f_code.co_name,
                    }
                )
            trace = trace.tb_next
        result.append({"exception_type": name, "sqlstate": code, "frames": frames[-12:]})
        error = error.__cause__ if error.__cause__ is not None else error.__context__
    return result


def verify_frozen_package(root: Path) -> None:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("commit") != BASE_COMMIT or manifest.get("version") != "0.3.0":
        raise RuntimeError("base_package_version")
    seen = set()
    for line in (root / "CHECKSUMS.txt").read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        path = (root / name).resolve()
        if (
            not re.fullmatch(r"[0-9a-f]{64}", digest)
            or name in seen
            or not path.is_relative_to(root)
            or hashlib.sha256(path.read_bytes()).hexdigest() != digest
        ):
            raise RuntimeError("base_package_checksum")
        seen.add(name)
    required = {"manifest.json", "tools/run_takeover.py", "src/medqc_ingest/takeover.py"}
    if len(seen) != 72 or not required <= seen:
        raise RuntimeError("base_package_inventory")


def observe_import(function: Any, report: dict[str, Any], root: Path) -> Any:
    def execute(*args: Any, **kwargs: Any) -> Any:
        report["import_called"] = True
        try:
            result = function(*args, **kwargs)
            report["import_succeeded"] = True
            return result
        except Exception as error:
            report["exception_chain"] = safe_exception_chain(error, root)
            raise

    return execute


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--user", default="postgres")
    parser.add_argument("--port", type=int, default=5432)
    args = parser.parse_args(argv)
    root, run = args.package_root.resolve(), args.run_root.resolve()
    previous = {key: os.environ.get(key) for key in ("PGPASSWORD", "MEDQC_PG_DRIVER")}
    report: dict[str, Any] = {
        "diagnostic_version": "takeover-import-observer-1",
        "base_commit": BASE_COMMIT,
        "source_writes": False,
        "creates_databases": False,
        "package_modified": False,
        "import_called": False,
        "import_succeeded": False,
        "contains_phi": False,
        "contains_raw_values": False,
    }
    try:
        verify_frozen_package(root)
        plan = json.loads((run / "reports/database-plan.json").read_text(encoding="utf-8"))
        database = plan.get("ingest", "")
        if (
            plan.get("source") != SOURCE
            or not re.fullmatch(r"medqc_ingest_takeover_[0-9]{14}", database)
            or not 1 <= args.port <= 65535
        ):
            raise RuntimeError("database_plan")
        admin = run / "secrets/deployment-admin.pgpass"
        runtime = run / "secrets/runtime.pgpass"
        if not admin.is_file() or not runtime.is_file():
            raise RuntimeError("existing_passfiles_required")
        output = run / "reports/takeover-import-diagnostic.json"
        imported = run / "reports/takeover-import.json"
        if imported.exists():
            raise RuntimeError("existing_import_report_verify_only")
        # 先以排他方式保留输出位置；已有诊断不覆盖，避免无意反复重试。
        with output.open("x", encoding="utf-8", newline="\n") as destination:
            try:
                os.environ.pop("PGPASSWORD", None)
                os.environ["MEDQC_PG_DRIVER"] = "psycopg2"
                sys.path.insert(0, str(root / "src"))
                spec = importlib.util.spec_from_file_location(
                    "frozen_takeover_import_observed", root / "tools/run_takeover.py"
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                module.import_legacy = observe_import(module.import_legacy, report, root)
                result = module.main(
                    [
                        "import",
                        "--database",
                        database,
                        "--user",
                        args.user,
                        "--passfile",
                        str(admin),
                        "--source-passfile",
                        str(runtime),
                        "--port",
                        str(args.port),
                        "--output",
                        str(imported),
                    ]
                )
                report["exit_code"] = result
            except Exception as error:
                report["observer_exception_chain"] = safe_exception_chain(error, root)
                report["exit_code"] = 1
            finally:
                destination.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print("DIAGNOSTIC_WRITTEN: reports/takeover-import-diagnostic.json")
        return int(report["exit_code"])
    except Exception as error:
        print("diagnostic_setup_failed", file=sys.stderr)
        print(json.dumps(safe_exception_chain(error, root)), file=sys.stderr)
        return 2
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


if __name__ == "__main__":
    raise SystemExit(main())
