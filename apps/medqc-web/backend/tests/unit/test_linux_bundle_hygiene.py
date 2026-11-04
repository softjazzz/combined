"""交付清单不应要求部署账号读取构建机的私有Python缓存。"""

from pathlib import Path
import runpy
import sys


def test_manifest_excludes_python_cache_and_keeps_runtime_sources(tmp_path, monkeypatch):
    (tmp_path / "deploy/__pycache__").mkdir(parents=True)
    (tmp_path / "deploy/__pycache__/private.pyc").write_bytes(b"synthetic-cache")
    (tmp_path / "stray.pyo").write_bytes(b"synthetic-cache")
    (tmp_path / "deploy/run.py").write_text("# synthetic runtime\n", encoding="utf-8")
    script = Path(__file__).resolve().parents[3] / "scripts/linux_offline/make_lock.py"
    monkeypatch.setattr(sys, "argv", [str(script), str(tmp_path), "--manifest-only"])
    runpy.run_path(str(script), run_name="__main__")
    manifest = (tmp_path / "SHA256SUMS").read_text()
    assert "deploy/run.py" in manifest
    assert (
        "__pycache__" not in manifest
        and ".pyc" not in manifest
        and ".pyo" not in manifest
    )
