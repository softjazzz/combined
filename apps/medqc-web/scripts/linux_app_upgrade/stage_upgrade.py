"""仅复制新release并保存回滚记录，不切current、不改venv/配置、不启停服务。"""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys

from check_compat import check


def stage(kit: Path, root: Path, expected_current: Path) -> dict:
    report = check(kit, root)
    if not report["ok"]:
        return report
    root = root.resolve(strict=True)
    releases = root / "releases"
    old = (root / "current").resolve(strict=True)
    if not (root / "current").is_symlink() or releases.is_symlink() or old.parent != releases or old != expected_current.resolve(strict=True):
        raise ValueError("current_release_changed_or_outside_root")
    config = root / "config/business.env"
    if not config.is_file() or config.is_symlink():
        raise ValueError("existing_regular_business_env_required")
    destination = releases / report["build_id"]
    receipt = root / "state" / ("app-upgrade-" + report["build_id"] + ".json")
    if destination.exists() or receipt.exists():
        raise ValueError("target_release_or_receipt_already_exists")
    shutil.copytree(kit / "application", destination, symlinks=False)
    (destination / "backend/.env").symlink_to(config)
    record = {"previous_current": str(old), "staged_current": str(destination), "unchanged_venv": str((root / "venv").resolve()),
              "application_commit": report["commit"], "build_id": report["build_id"], "activated": False}
    receipt.parent.mkdir(exist_ok=True)
    with receipt.open("x", encoding="utf-8") as file:
        json.dump(record, file, indent=2)
        file.write("\n")
    assert (root / "current").resolve() == old
    return {"ok": True, "staged": True, "activated": False, "receipt": str(receipt), "release": str(destination), "database_connections": 0}


def main():
    sys.dont_write_bytecode = True
    os.umask(0o027)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("/data/medqc/business"))
    parser.add_argument("--expected-current", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = stage(Path(__file__).resolve().parent, args.root, args.expected_current)
    except Exception as error:
        report = {"ok": False, "error": str(error) if isinstance(error, ValueError) else type(error).__name__}
    print(json.dumps(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
