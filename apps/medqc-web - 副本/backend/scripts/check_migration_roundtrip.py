from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = ROOT / "alembic.ini"


def _run(cmd: list[str], env: dict[str, str]) -> str:
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        output = (proc.stdout or "") + (proc.stderr or "")
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{output}")
    return (proc.stdout or "") + (proc.stderr or "")


def _extract_heads(text: str) -> list[str]:
    heads: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        match = re.match(r"^([0-9a-zA-Z_]+)\s+\(head\)$", line)
        if match:
            heads.append(match.group(1))
    return heads


def main() -> int:
    if not ALEMBIC_INI.exists():
        print(f"Missing alembic config: {ALEMBIC_INI.as_posix()}")
        return 1

    env = os.environ.copy()
    env.setdefault("DATABASE_URL", "postgresql://ci_user:ci_pass@127.0.0.1:5432/medqc_ci")

    python = sys.executable
    heads_output = _run([python, "-m", "alembic", "-c", "alembic.ini", "heads"], env)
    heads = _extract_heads(heads_output)
    if len(heads) != 1:
        print("Expected exactly one Alembic head.")
        print(heads_output)
        return 1
    head = heads[0]
    print(f"Alembic head: {head}")

    upgrade_sql = _run([python, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head", "--sql"], env)
    if "CREATE TABLE alembic_version" not in upgrade_sql:
        print("Upgrade SQL validation failed: missing alembic_version create.")
        return 1
    if f"Running upgrade  -> " not in upgrade_sql:
        print("Upgrade SQL validation failed: missing upgrade trace.")
        return 1
    print("Upgrade SQL generation passed.")

    downgrade_sql = _run(
        [python, "-m", "alembic", "-c", "alembic.ini", "downgrade", f"{head}:base", "--sql"],
        env,
    )
    if "DROP TABLE alembic_version" not in downgrade_sql:
        print("Downgrade SQL validation failed: missing alembic_version drop.")
        return 1
    if f"Running downgrade {head}" not in downgrade_sql:
        print("Downgrade SQL validation failed: missing downgrade trace.")
        return 1
    print("Downgrade SQL generation passed.")
    print("Migration roundtrip check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
