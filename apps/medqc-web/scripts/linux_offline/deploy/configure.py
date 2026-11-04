"""现场交互配置，只写新业务目录；密码和JWT不进入命令行或输出。"""

import argparse
import getpass
import os
from pathlib import Path
import secrets
from urllib.parse import quote

from dotenv import dotenv_values, set_key

p = argparse.ArgumentParser()
p.add_argument("--root", type=Path, default=Path("/data/medqc/business"))
p.add_argument("--host-ip", default="192.168.140.177")
a = p.parse_args()
os.umask(0o077)
path = a.root / "config/business.env"
if not path.is_file():
    raise SystemExit("Run install.sh first")
cfg = dotenv_values(path)
password = getpass.getpass("Existing medqc_business_app database password: ")
if not password or getpass.getpass("Repeat database password: ") != password:
    raise SystemExit("Password mismatch; no config written")
url = (
    "postgresql://medqc_business_app:"
    + quote(password, safe="")
    + "@127.0.0.1:5432/medqc_business"
)
secret = cfg.get("JWT_SECRET", "")
if secret.startswith("REPLACE") or len(secret) < 32:
    secret = secrets.token_hex(32)
for key, value in {
    "DATABASE_URL": url,
    "JWT_SECRET": secret,
    "CORS_ORIGINS": "http://" + a.host_ip,
    "PRODUCT_ACTIVATION_STATE_PATH": str(a.root / "state/activation.json"),
    "QC_DISPATCH_STATE_DIR": str(a.root / "state/dispatch"),
}.items():
    set_key(str(path), key, value)
path.chmod(0o600)
print(
    "Business config saved. No database or service changes. Credentials were not printed."
)
