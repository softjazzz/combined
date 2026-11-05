"""显式应用交付代理默认值；仅改两项，先备份，不重启或访问网络。"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

VALUES = {"LLM_HTTP_PROXY": "http://192.168.118.99:18090", "LLM_HTTP_PROXY_HOSTS": "dashscope.aliyuncs.com"}


def apply(env_file: Path, backup_dir: Path):
    if env_file.is_symlink() or not env_file.is_file() or backup_dir.is_symlink():
        raise ValueError("regular_env_and_backup_directory_required")
    original = env_file.read_bytes()
    text = original.decode("utf-8")
    for key in VALUES:
        pattern = re.compile(r"^(?:export[ \t]+)?" + key + r"[ \t]*=", re.MULTILINE)
        if len(pattern.findall(text)) > 1:
            raise ValueError("duplicate_proxy_key")
    backup_dir.mkdir(parents=True, exist_ok=True)
    name = "business.env.before-proxy-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup = backup_dir / name
    fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as file:
        file.write(original)
    for key, value in VALUES.items():
        pattern = re.compile(r"^(?:export[ \t]+)?" + key + r"[ \t]*=[^\r\n]*", re.MULTILINE)
        text, count = pattern.subn(key + "=" + value, text)
        if not count:
            text = text.rstrip("\r\n") + "\n" + key + "=" + value + "\n"
    fd, temporary = tempfile.mkstemp(prefix=".proxy-config-", dir=env_file.parent)
    with os.fdopen(fd, "wb") as file:
        file.write(text.encode("utf-8"))
        file.flush()
        os.fsync(file.fileno())
    os.chmod(temporary, 0o600)
    if env_file.read_bytes() != original:
        raise ValueError("configuration_changed_during_update")
    os.replace(temporary, env_file)
    return {"ok": True, "backup": str(backup), "before_sha256": hashlib.sha256(original).hexdigest(),
            "proxy_enabled": True, "changed_keys": list(VALUES), "network_calls": 0, "database_connections": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--backup-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(apply(args.env_file, args.backup_dir)))
    except Exception as error:
        print(json.dumps({"ok": False, "error": str(error) if isinstance(error, ValueError) else type(error).__name__}))
        raise SystemExit(1)
