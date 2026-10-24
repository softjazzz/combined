"""只在显式安装验收补丁后，冻结当前进程实际加载的 P0 函数一致性。"""

import hashlib
import json
from pathlib import Path
from types import CodeType


def code_digest(code: CodeType) -> str:
    def shape(value):
        if isinstance(value, CodeType):
            return [value.co_code.hex(), value.co_argcount, value.co_kwonlyargcount,
                    value.co_names, value.co_varnames, [shape(item) for item in value.co_consts]]
        if isinstance(value, bytes):
            return value.hex()
        return repr(value)
    return hashlib.sha256(json.dumps(shape(code), ensure_ascii=True).encode()).hexdigest()


def find_code(code: CodeType, path: tuple[str, ...]) -> CodeType:
    if not path:
        return code
    matches = [item for item in code.co_consts if isinstance(item, CodeType) and item.co_name == path[0]]
    if len(matches) != 1:
        raise ValueError("runtime_function_missing_or_ambiguous")
    return find_code(matches[0], path[1:])


def loaded_p0_proof():
    backend = Path(__file__).resolve().parents[3]
    marker = backend / ".p0-chain-installed.json"
    if not marker.exists():
        return None
    installation = json.loads(marker.read_text(encoding="utf8"))
    files_unchanged = installation.get("protocol") == "medqc-p0-chain-v1"
    for relative, expected in installation.get("source_sha256", {}).items():
        target = (backend / relative).resolve()
        target.relative_to(backend)
        files_unchanged = files_unchanged and target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == expected
    from ..custom_qc_workspace_service import CustomQCWorkspaceService
    from ..luxian_0609.native_transfusion_execution import _programmatic_044_status
    from ..bundles.assembly import _inventory_entry
    functions = (
        ("completion", CustomQCWorkspaceService.complete_batch_job, ("CustomQCWorkspaceService", "complete_batch_job")),
        ("transfusion", _programmatic_044_status, ("_programmatic_044_status",)),
        ("bundle", _inventory_entry, ("_inventory_entry",)),
    )
    checks = {}
    for name, function, path in functions:
        disk = compile(Path(function.__code__.co_filename).read_bytes(), function.__code__.co_filename, "exec")
        actual = code_digest(function.__code__)
        checks[name] = {"loaded_equals_disk": actual == code_digest(find_code(disk, path)), "loaded_code_sha256": actual}
    return {"protocol": "medqc-p0-chain-v1", "loaded_equals_disk": files_unchanged and all(row["loaded_equals_disk"] for row in checks.values()),
            "recovery_supported": "recovery_baseline" in CustomQCWorkspaceService.complete_batch_job.__code__.co_varnames,
            "functions": checks}
