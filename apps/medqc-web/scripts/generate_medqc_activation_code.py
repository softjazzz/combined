"""离线产品激活码签发工具（仅供发行方使用）。

私钥必须放在仓库外的受控目录；本脚本不会生成、保存或打印私钥。
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

# 允许从仓库根目录直接运行签发工具；客户包不会复制 scripts/。
BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.product_activation import (  # noqa: E402
    ACTIVATION_PRODUCT,
    ACTIVATION_SCHEMA_VERSION,
    build_activation_code,
)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_expiry(value: str) -> str:
    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("--expires-at 必须包含时区，例如 2027-08-19T00:00:00Z")
    return _iso(parsed)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成 MedQC 离线激活码")
    parser.add_argument("--private-key", required=True, type=Path)
    parser.add_argument("--customer", required=True)
    parser.add_argument("--edition", default="customer")
    parser.add_argument("--serial", required=True)
    parser.add_argument("--expires-at", required=True, help="RFC3339 时间，例如 2027-08-19T00:00:00Z")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    private_key = serialization.load_pem_private_key(args.private_key.read_bytes(), password=None)
    if not isinstance(private_key, Ed25519PrivateKey):
        raise SystemExit("私钥必须是 Ed25519 PKCS8 PEM")
    issued_at = datetime.now(timezone.utc)
    payload = {
        "version": ACTIVATION_SCHEMA_VERSION,
        "product": ACTIVATION_PRODUCT,
        "customer": args.customer.strip(),
        "edition": args.edition.strip(),
        "serial": args.serial.strip(),
        "issued_at": _iso(issued_at),
        "expires_at": _parse_expiry(args.expires_at),
    }
    if not payload["customer"] or not payload["edition"] or not payload["serial"]:
        raise SystemExit("客户、版本和序列号不能为空")
    print(build_activation_code(private_key, payload))


if __name__ == "__main__":
    main()
