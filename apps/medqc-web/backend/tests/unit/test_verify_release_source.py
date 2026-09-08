from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "verify_release_source.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "verify_release_source",
        SCRIPT_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载脚本：{SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _classified_inventory() -> dict:
    return {
        "schema_version": 1,
        "entries": [
            {
                "path": "apps/medqc-web/src/example.ts",
                "git_status": " M",
                "sha256": "a" * 64,
                "size": 10,
                "category": "A",
                "owner": "前端",
                "release_required": True,
                "reason": "发布功能",
            }
        ],
    }


def test_formal_source_verification_rejects_dirty_tree(tmp_path: Path) -> None:
    verifier = _load_module()

    report = verifier.verify_source_state(
        repo_root=tmp_path,
        inventory=_classified_inventory(),
        changed_paths=["apps/medqc-web/src/example.ts"],
        allow_dirty=False,
    )

    assert report["passed"] is False
    assert report["non_releasable"] is False
    assert "dirty_git_tree" in report["reason_codes"]


def test_allow_dirty_marks_package_as_non_releasable(tmp_path: Path) -> None:
    verifier = _load_module()

    report = verifier.verify_source_state(
        repo_root=tmp_path,
        inventory=_classified_inventory(),
        changed_paths=["apps/medqc-web/src/example.ts"],
        allow_dirty=True,
    )

    assert report["passed"] is True
    assert report["non_releasable"] is True
    assert "dirty_git_tree_allowed_for_development" in report["warnings"]


def test_unclassified_inventory_blocks_even_development_mode(
    tmp_path: Path,
) -> None:
    verifier = _load_module()
    inventory = _classified_inventory()
    inventory["entries"][0]["category"] = "F"
    inventory["entries"][0]["owner"] = ""
    inventory["entries"][0]["release_required"] = None
    inventory["entries"][0]["reason"] = ""

    report = verifier.verify_source_state(
        repo_root=tmp_path,
        inventory=inventory,
        changed_paths=[],
        allow_dirty=True,
    )

    assert report["passed"] is False
    assert "unclassified_inventory" in report["reason_codes"]


def test_forbidden_local_paths_are_reported_without_file_content(
    tmp_path: Path,
) -> None:
    verifier = _load_module()
    secret_file = tmp_path / "apps" / "medqc-web" / "backend" / ".env"
    secret_file.parent.mkdir(parents=True)
    secret_file.write_text("PASSWORD=do-not-echo-this", encoding="utf-8")

    report = verifier.verify_source_state(
        repo_root=tmp_path,
        inventory=_classified_inventory(),
        changed_paths=[
            "apps/medqc-web/.release-packages/customer.zip",
            "apps/medqc-web/backend/.env",
        ],
        allow_dirty=True,
    )

    serialized = repr(report)
    assert report["passed"] is False
    assert "forbidden_local_path" in report["reason_codes"]
    assert "sensitive_source_file" in report["reason_codes"]
    assert "do-not-echo-this" not in serialized


def test_safe_env_example_is_allowed(tmp_path: Path) -> None:
    verifier = _load_module()
    example = tmp_path / "apps" / "medqc-web" / "backend" / ".env.example"
    example.parent.mkdir(parents=True)
    example.write_text("DATABASE_URL=${DATABASE_URL}\n", encoding="utf-8")

    report = verifier.verify_source_state(
        repo_root=tmp_path,
        inventory=_classified_inventory(),
        changed_paths=[],
        scan_paths=["apps/medqc-web/backend/.env.example"],
        allow_dirty=False,
    )

    assert report["passed"] is True
    assert report["reason_codes"] == []


@pytest.mark.parametrize("address", ["https://api.medqc.com", "http://124.220.6.136:8001"])
def test_public_api_domain_in_frontend_runtime_source_is_blocked(
    tmp_path: Path, address: str,
) -> None:
    verifier = _load_module()
    config = tmp_path / "apps" / "medqc-web" / "src" / "api-base.ts"
    config.parent.mkdir(parents=True)
    config.write_text(
        f'export const apiBase = "{address}/api/v1"\n',
        encoding="utf-8",
    )

    report = verifier.verify_source_state(
        repo_root=tmp_path,
        inventory=_classified_inventory(),
        changed_paths=[],
        scan_paths=["apps/medqc-web/src/api-base.ts"],
        allow_dirty=False,
    )

    assert report["passed"] is False
    assert "forbidden_public_api_domain" in report["reason_codes"]
