"""开发侧匿名诊断包检查/文案回放；不加载 FastAPI，不连接数据库或模型。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.services.qc_diagnostics.contracts import DiagnosticPackageError
from app.services.qc_diagnostics.package import load_diagnostic_package
from app.services.qc_diagnostics.replay import inspect_documents, replay_documents


def _local_commit() -> str:
    """版本来自本地仓库；只读 Git 命令不接受包内参数。"""
    try:
        def git(*args: str) -> str:
            result = subprocess.run(
                ["git", "-c", "core.fsmonitor=false", "-C", str(BACKEND), *args],
                capture_output=True, text=True, check=True, timeout=10,
            )
            return result.stdout.strip()

        commit = git("rev-parse", "HEAD")
        # UI 未提交改动不影响本批；所有后端生产代码必须处于可标识版本。
        changed = git("status", "--porcelain", "--untracked-files=all", "--", "app", "scripts/qc_diagnostic.py")
        if changed:
            raise DiagnosticPackageError("local_backend_dirty")
        return commit
    except (OSError, subprocess.SubprocessError):
        raise DiagnosticPackageError("local_version_unavailable") from None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="只读检查匿名诊断包；不证明临床正确性或脱敏完成。")
    parser.add_argument("command", choices=("inspect", "replay"))
    parser.add_argument("package", type=Path)
    parser.add_argument("--compare-current", action="store_true", help="明确比较不同代码版本，不标为原版本复现")
    args = parser.parse_args(argv)
    try:
        documents = load_diagnostic_package(args.package)
        if args.command == "inspect":
            result = inspect_documents(documents)
        else:
            result = replay_documents(
                documents, local_git_commit=_local_commit(), compare_current=args.compare_current,
            )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except DiagnosticPackageError as error:
        print(json.dumps({"error": error.code}), file=sys.stderr)
        return 2
    except Exception:
        # 不把外来包、路径或异常上下文输出到客户可粘贴的诊断信息。
        print(json.dumps({"error": "diagnostic_failed"}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
