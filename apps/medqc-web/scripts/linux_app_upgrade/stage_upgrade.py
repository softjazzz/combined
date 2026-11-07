"""只读预检材料路径后复制新release；不切current、改配置或启停服务。"""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys

from check_compat import check


def material_storage_preflight(config: Path, root: Path, old: Path, destination: Path) -> dict:
    # 与应用load_dotenv保持相同插值和进程环境优先级；不导入app，不输出其他配置。
    try:
        from dotenv.main import DotEnv
    except ImportError:
        raise ValueError("existing_business_venv_python_dotenv_required; use_root_venv_bin_python; do_not_install_dependencies") from None

    values = {**DotEnv(config, override=False, encoding="utf-8").dict(), **os.environ}
    explicit = (values.get("QC_CASE_MATERIAL_DIR") or "").strip()
    dispatch = (values.get("QC_DISPATCH_STATE_DIR") or "").strip()
    if explicit:
        path, source = Path(explicit), "QC_CASE_MATERIAL_DIR"
    elif dispatch:
        dispatch_path = Path(dispatch)
        if not dispatch_path.is_absolute():
            raise ValueError("absolute_material_storage_required")
        path, source = dispatch_path.parent / "case-materials", "QC_DISPATCH_STATE_DIR"
    else:
        path, source = old / "backend/data/case-materials", "release_default"
    if not path.is_absolute():
        raise ValueError("absolute_material_storage_required")
    resolved = path.resolve()
    # resolve同时识别current或任意符号链接别名，不能只比较输入字符串前缀。
    for application in (root / "releases", root / "current", old, destination):
        application = application.resolve()
        if resolved == application or application in resolved.parents:
            raise ValueError("material_storage_inside_release; preserve_history_before_upgrade")
    return {"material_storage_dir": str(resolved), "material_storage_source": source}


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
    material = material_storage_preflight(config, root, old, destination)
    shutil.copytree(kit / "application", destination, symlinks=False)
    (destination / "backend/.env").symlink_to(config)
    record = {"previous_current": str(old), "staged_current": str(destination), "unchanged_venv": str((root / "venv").resolve()),
              "application_commit": report["commit"], "build_id": report["build_id"], "activated": False, **material}
    receipt.parent.mkdir(exist_ok=True)
    with receipt.open("x", encoding="utf-8") as file:
        json.dump(record, file, indent=2)
        file.write("\n")
    assert (root / "current").resolve() == old
    return {"ok": True, "staged": True, "activated": False, "receipt": str(receipt), "release": str(destination), "database_connections": 0, **material}


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
