from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "release_baseline_inventory.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "release_baseline_inventory",
        SCRIPT_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载脚本：{SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parse_porcelain_z_supports_spaces_chinese_and_rename() -> None:
    inventory = _load_module()

    entries = inventory.parse_porcelain_z(
        b" M apps/medqc-web/src/a file.ts\0"
        + "?? apps/medqc-web/docs/中文说明.md\0".encode()
        + b"R  apps/medqc-web/src/new.ts\0apps/medqc-web/src/old.ts\0"
    )

    assert entries == [
        {
            "git_status": " M",
            "path": "apps/medqc-web/src/a file.ts",
            "original_path": None,
        },
        {
            "git_status": "??",
            "path": "apps/medqc-web/docs/中文说明.md",
            "original_path": None,
        },
        {
            "git_status": "R ",
            "path": "apps/medqc-web/src/new.ts",
            "original_path": "apps/medqc-web/src/old.ts",
        },
    ]


def test_validate_inventory_rejects_unclassified_entries() -> None:
    inventory = _load_module()
    payload = {
        "schema_version": 1,
        "entries": [
            {
                "path": "src/example.ts",
                "git_status": " M",
                "sha256": "a" * 64,
                "size": 12,
                "category": "F",
                "owner": "",
                "release_required": None,
                "reason": "",
            }
        ],
    }

    with pytest.raises(inventory.InventoryValidationError) as exc_info:
        inventory.validate_inventory(payload)

    assert "未分类" in str(exc_info.value)


def test_validate_inventory_requires_controlled_fields() -> None:
    inventory = _load_module()
    payload = {
        "schema_version": 1,
        "entries": [
            {
                "path": "src/example.ts",
                "git_status": " M",
                "sha256": "a" * 64,
                "size": 12,
                "category": "A",
            }
        ],
    }

    with pytest.raises(inventory.InventoryValidationError) as exc_info:
        inventory.validate_inventory(payload)

    assert "owner" in str(exc_info.value)
    assert "release_required" in str(exc_info.value)
    assert "reason" in str(exc_info.value)


def test_build_entry_records_metadata_but_not_file_content(tmp_path: Path) -> None:
    inventory = _load_module()
    source = tmp_path / "包含密钥字样.txt"
    source.write_text("password=never-write-this-to-inventory", encoding="utf-8")

    entry = inventory.build_entry(
        repo_root=tmp_path,
        change={
            "path": "包含密钥字样.txt",
            "git_status": "??",
            "original_path": None,
        },
    )

    assert entry["path"] == "包含密钥字样.txt"
    assert entry["size"] == source.stat().st_size
    assert len(entry["sha256"]) == 64
    assert "password" not in repr(entry)
    assert "never-write-this" not in repr(entry)
    assert entry["category"] == "F"
    assert entry["release_required"] is None


def test_validate_inventory_accepts_fully_classified_entry() -> None:
    inventory = _load_module()
    payload = {
        "schema_version": 1,
        "entries": [
            {
                "path": "src/example.ts",
                "git_status": " M",
                "sha256": "a" * 64,
                "size": 12,
                "category": "A",
                "owner": "前端",
                "release_required": True,
                "reason": "客户版结果展示修复",
            }
        ],
    }

    inventory.validate_inventory(payload)


def test_classification_rules_use_first_matching_rule() -> None:
    inventory = _load_module()
    rules = [
        {
            "pattern": "apps/medqc-web/tmp-*",
            "category": "D",
            "owner": "本地产物",
            "release_required": False,
            "reason": "临时验证产物",
        },
        {
            "pattern": "apps/medqc-web/*",
            "category": "F",
            "owner": "待确认",
            "release_required": False,
            "reason": "不应命中后续规则",
        },
    ]

    classification = inventory.classify_path(
        "apps/medqc-web/tmp-browser-check.png",
        rules,
    )

    assert classification == {
        "category": "D",
        "owner": "本地产物",
        "release_required": False,
        "reason": "临时验证产物",
    }
