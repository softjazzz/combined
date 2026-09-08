"""读取发布过程写入的小型版本声明；客户运行时不调用 Git 或扫描源码。

这是发布声明而非签名或安装目录防篡改证明，缺失时不能推测原执行版本。
"""

import json
from pathlib import Path
import re

_BUILD_PATH = Path(__file__).resolve().parents[2] / "data" / "runtime_build.json"


def validate_runtime_build(value: object) -> dict:
    if type(value) is not dict or set(value) != {"schema_version", "git_commit", "build_id", "inventory_schema_version"}:
        raise ValueError("invalid_runtime_build")
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise ValueError("invalid_runtime_build")
    if type(value["inventory_schema_version"]) is not int or value["inventory_schema_version"] != 1:
        raise ValueError("invalid_runtime_build")
    if type(value["git_commit"]) is not str or re.fullmatch(r"[0-9a-f]{40}", value["git_commit"]) is None:
        raise ValueError("invalid_runtime_build")
    if type(value["build_id"]) is not str or re.fullmatch(r"medqc-web-customer-[0-9]{8}-[0-9]{6}", value["build_id"]) is None:
        raise ValueError("invalid_runtime_build")
    return dict(value)


def _unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("invalid_runtime_build")
        result[key] = value
    return result


def load_runtime_build() -> dict:
    try:
        if _BUILD_PATH.is_symlink():
            raise ValueError("invalid_runtime_build")
        with _BUILD_PATH.open("rb") as stream:
            data = stream.read(8193)
        if len(data) > 8192:
            raise ValueError("invalid_runtime_build")
        parsed = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_fields)
        return {"available": True, **validate_runtime_build(parsed)}
    except (OSError, ValueError, UnicodeError, RecursionError):
        return {"available": False, "reason": "build_version_unavailable"}
