from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]


def _must_contain(path: Path, text: str) -> tuple[bool, str]:
    content = path.read_text(encoding="utf-8")
    ok = text in content
    return ok, f"{path}: {'OK' if ok else 'MISSING'} -> {text}"


def main() -> int:
    checks = [
        (
            ROOT / "backend" / "app" / "main.py",
            "dependencies=[Depends(enforce_default_auth)]",
        ),
        (
            ROOT / "backend" / "app" / "routers" / "system_config.py",
            "dependencies=[Depends(require_admin)]",
        ),
        (
            ROOT / "backend" / "app" / "routers" / "system_config.py",
            '_reject_legacy_write_endpoint("/api/system/db/config")',
        ),
        (
            ROOT / "backend" / "app" / "routers" / "system_config.py",
            '_reject_legacy_write_endpoint("/api/system/sync/trigger")',
        ),
        (
            ROOT / "backend" / "app" / "routers" / "medical_records.py",
            "dependencies=[Depends(require_roles(",
        ),
        (
            ROOT / "backend" / "app" / "routers" / "drg.py",
            "dependencies=[Depends(require_roles(",
        ),
        (
            ROOT / "backend" / "app" / "routers" / "settlement.py",
            "dependencies=[Depends(require_roles(",
        ),
    ]
    failed = []
    for path, needle in checks:
        ok, msg = _must_contain(path, needle)
        print(msg)
        if not ok:
            failed.append(path.as_posix())
    if failed:
        print("Auth guard checks failed:")
        for item in failed:
            print(f"- {item}")
        return 1
    print("Auth guard checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
