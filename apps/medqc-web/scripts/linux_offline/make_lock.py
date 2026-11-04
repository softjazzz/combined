"""从已经完整解析的Linux wheel集合生成精确版本/哈希锁及交付清单。"""

import argparse
import hashlib
from pathlib import Path

try:
    from packaging.utils import parse_wheel_filename
except ImportError:
    from pip._vendor.packaging.utils import parse_wheel_filename


def digest(p):
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


p = argparse.ArgumentParser()
p.add_argument("root", type=Path)
p.add_argument("--manifest-only", action="store_true")
a = p.parse_args()
if not a.manifest_only:
    selected = {}
    for wheel in (a.root / "wheelhouse").glob("*.whl"):
        name, version, _, tags = parse_wheel_filename(wheel.name)
        if str(name) in selected:
            raise RuntimeError("duplicate_distribution_in_wheelhouse")
        selected[str(name)] = (str(version), digest(wheel))
    if not selected or "pip" not in selected:
        raise RuntimeError("wheelhouse_missing_bootstrap_pip")
    (a.root / "requirements-linux.lock").write_text(
        "".join(
            f"{name}=={ver} --hash=sha256:{sha}\n"
            for name, (ver, sha) in sorted(selected.items())
        )
    )
files = sorted(
    p
    for p in a.root.rglob("*")
    if p.is_file()
    and p.name != "SHA256SUMS"
    and "__pycache__" not in p.parts
    and p.suffix not in {".pyc", ".pyo"}
)
(a.root / "SHA256SUMS").write_text(
    "".join(f"{digest(p)}  {p.relative_to(a.root).as_posix()}\n" for p in files)
)
