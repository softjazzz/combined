from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

TARGET_FILES = [
    ROOT / "backend" / "data" / "db_config.json",
    ROOT / "backend" / "app" / "data" / "db_config.json",
]

SENSITIVE_KEYWORDS = ("password", "secret", "token", "api_key", "apikey")
REF_VALUE_PATTERN = re.compile(r"^(env:[A-Z0-9_]+|vault:[\w\-/]+|ref:[\w\-/]+)$")
MASKED_VALUE_PATTERN = re.compile(r"^\*{3,}$")


def _looks_like_plain_secret(key: str, value: str) -> bool:
    key_lower = key.lower()
    if not any(item in key_lower for item in SENSITIVE_KEYWORDS):
        return False
    if key_lower.endswith("_ref"):
        return False
    normalized = value.strip()
    if not normalized:
        return False
    if REF_VALUE_PATTERN.match(normalized):
        return False
    if MASKED_VALUE_PATTERN.match(normalized):
        return False
    return True


def _scan_node(node: Any, path: str, findings: list[str]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            node_path = f"{path}.{key}" if path else str(key)
            if isinstance(value, str):
                if _looks_like_plain_secret(key, value):
                    findings.append(f"{node_path}: contains plaintext secret value")
            _scan_node(value, node_path, findings)
        return
    if isinstance(node, list):
        for idx, item in enumerate(node):
            _scan_node(item, f"{path}[{idx}]", findings)


def _scan_file(path: Path) -> list[str]:
    findings: list[str] = []
    if not path.exists():
        return findings
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"{path.as_posix()}: invalid JSON ({exc})"]
    _scan_node(payload, "", findings)
    return [f"{path.as_posix()} -> {item}" for item in findings]


def main() -> int:
    findings: list[str] = []
    for file_path in TARGET_FILES:
        findings.extend(_scan_file(file_path))

    if findings:
        print("Secret hygiene check failed:")
        for item in findings:
            print(f"- {item}")
        return 1

    print("Secret hygiene check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
