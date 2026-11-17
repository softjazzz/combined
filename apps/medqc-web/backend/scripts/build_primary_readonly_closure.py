"""从固定交接 ZIP 逐定义提取只读闭包；不导入同步模块，不包含数据库写入口。"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import zipfile


SOURCE_COMMIT = "7a8c4bb424189a10e97f49e2df7d4b5c1a8abafe"
ZIP_SHA256 = "ce63db287061bc9e479c7bb833879ba7a1c52e6f47c0b064ef468e3cae89cab3"
ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "app/services/primary_material_readonly.py"
DATA = ROOT / "app/data/clinical_primary_contracts"

HEADER = '''"""固定 7a8c4bb42 的四类合同只读定义闭包。

由 scripts/build_primary_readonly_closure.py 提取；来源及裁剪见固定指纹清单。
只借调用者的独立 CDM 只读 RR 连接；不携带同步连接工厂或写入口。
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any

SOURCE_COMMIT = "7a8c4bb424189a10e97f49e2df7d4b5c1a8abafe"
CONTRACT_DIRECTORY = Path(__file__).resolve().parents[1] / "data/clinical_primary_contracts"
'''

BRIDGE = '''
def contracts_for_mode(
    lifecycle_mode: str | None = None,
    lifecycle_approvals: dict[str, list | tuple] | None = None,
) -> dict[str, MetadataContract]:
    """显式选合同；缺省保留旧strict，审批仅用于固定四类并交原合同校验。"""
    require(lifecycle_mode is None or lifecycle_mode == MODE, "primary_lifecycle_mode")
    approvals = {} if lifecycle_approvals is None else lifecycle_approvals
    require(isinstance(approvals, dict) and set(approvals) <= set(KINDS),
            "primary_lifecycle_approvals")
    for rows in approvals.values():
        require(isinstance(rows, (list, tuple)) and all(
            isinstance(row, (list, tuple)) and len(row) == 4
            and all(isinstance(value, str) for value in row) for row in rows
        ), "primary_lifecycle_approvals")
    contracts = real_contracts() if lifecycle_mode is None else record_contracts()
    return {kind: replace(contract, lifecycle_approvals=tuple(
        tuple(row) for row in approvals.get(kind, ())
    )) for kind, contract in contracts.items()}


PRIMARY_REQUIRED_OBJECTS = (
    "sync_material.primary_policy",
    "sync_material.primary_head",
    "sync_material.primary_manifest",
    "sync_material.primary_coverage",
    "sync_delivery.contract",
    "sync_delivery.receipt",
)


def primary_objects_available(sqlalchemy_connection: Any) -> bool:
    """同事务无异常探测可选对象；缺对象返回 False，权限/连接失败继续抛出。"""
    connection = sqlalchemy_connection.connection.driver_connection
    with connection.cursor() as q:
        for name in PRIMARY_REQUIRED_OBJECTS:
            q.execute("SELECT to_regclass(%s)", (name,))
            if q.fetchone()[0] is None:
                return False
    return True


def read_primary_in_transaction(
    sqlalchemy_connection: Any, policy: PrimaryPolicy, contracts: dict[str, PrimaryContract]
) -> dict[str, Any]:
    """仅借已有同步 SQLAlchemy Connection 的同一 DBAPI 连接，不拥有事务。"""
    return read_in_transaction(
        sqlalchemy_connection.connection.driver_connection, policy, contracts
    )
'''

# 逐项列出所需定义，避免导入源模块时拖入同步写仓储。
SELECTION = {
    "domain.py": ["ERROR_KINDS", "ErrorKind", "IngestError", "FieldMapping", "DerivedDocumentId",
                  "PublishSpec", "InterfaceSpec", "canonical_json", "sha256_hex", "normalize", "denormalize"],
    "daily_materials.py": ["digest"],
    "clinical_daily.py": ["KEYS", "COLUMNS", "require", "ClinicalContract"],
    "clinical_primary.py": ["CONTRACT", "KINDS", "SURGERY_FIELDS", "TARGETS", "PrimaryContract",
                            "PrimaryPolicy", "select_materials"],
    "primary_metadata.py": ["REVISION", "METADATA_SHA256", "metadata_document", "_mappings",
                            "MetadataContract", "real_contracts"],
    "record_lifecycle.py": ["MODE", "REVISION", "RecordLifecycleContract", "record_contracts"],
    "control/models.py": ["ControlError"],
    "control/profiles.py": ["Profile", "ProfileCatalog"],
    "control/accepted.py": ["PROFILE", "CONTRACT_SHA", "FINANCIAL", "contract_path", "AcceptedManualCatalog"],
    "repositories/postgres.py": ["_ident"],
    "primary_store.py": ["SURGERY_REFERENCE_SHA", "cache_spec", "_registered", "_target", "_receipt",
                         "_health", "read_in_transaction"],
}


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def node_name(node):
    if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
        return node.name
    if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
        return node.targets[0].id
    return None


def prune_methods(source, node, retained):
    lines = source.splitlines()
    for member in reversed(node.body):
        if isinstance(member, ast.FunctionDef) and member.name not in retained:
            first = min([member.lineno] + [d.lineno for d in member.decorator_list])
            del lines[first - 1:member.end_lineno]
    return "\n".join(lines)


def adapt(source, name, filename):
    note = None
    if filename == "record_lifecycle.py" and name in {"REVISION", "RecordLifecycleContract"}:
        # 合并原模块命名空间时只改全局名称；保留旧元数据REVISION及其摘要。
        source = source.replace("REVISION", "LIFECYCLE_REVISION")
        note = "原record_lifecycle.REVISION改名LIFECYCLE_REVISION，避免覆盖metadata.REVISION"
    elif name == "metadata_document":
        start = source.index('    path = Path(')
        end = source.index('    content = path.read_bytes()')
        source = source[:start] + '    path = CONTRACT_DIRECTORY / "clinical-primary-real-fields-v2.json"\n' + source[end:]
        note = "仅固定 JSON 路径改为业务随包目录，删除外部路径回退"
    elif name == "cache_spec":
        start = source.index('    root = Path(')
        end = source.index('    content = path.read_bytes()')
        source = source[:start] + '    path = CONTRACT_DIRECTORY / "clinical-primary-cache-surgery-reference.json"\n' + source[end:]
        note = "仅手术固定 JSON 路径改为业务随包目录，删除外部路径回退"
    elif name == "contract_path":
        source = '''def contract_path(projection_revision: str = "baseline") -> Path:
    if projection_revision != "baseline":
        raise ControlError("configuration_error", "accepted_projection_revision", 503)
    return CONTRACT_DIRECTORY / "accepted-manual-contract.json"'''
        note = "固定 baseline 路径，拒绝可选出院时间分支，防止扩展本次四类范围"
    elif name == "AcceptedManualCatalog":
        first = source.index('        expected_hash = (')
        last = source.index('        body = ', first)
        source = source[:first] + '        expected_hash = CONTRACT_SHA\n' + source[last:]
        first = source.index('        if projection_revision == DISCHARGE_TIME_REVISION:')
        last = source.index('        specs = {}', first)
        source = source[:first] + source[last:]
        note = "仅保留构造/get，构造固定 baseline；删除出院时间 overlay 和调度/同步控制方法"
    return source, note


def build(path):
    body = path.read_bytes()
    if sha(body) != ZIP_SHA256:
        raise ValueError("primary_readonly_candidate_zip_hash")
    DATA.mkdir(parents=True, exist_ok=True)
    manifest = {"source_commit": SOURCE_COMMIT, "candidate_zip_sha256": ZIP_SHA256,
                "fingerprint_algorithm": "SHA256(ast.get_source_segment UTF-8), decorators excluded",
                "source_files": {}, "runtime_definitions": {}, "json_files": {},
                "runtime_methods": {}, "runtime_constants": {},
                "excluded_capabilities": ["migration", "poll", "extract", "publication write",
                                          "source metadata queries", "connection factories"],
                "audit_only_source_definitions": {}}
    sections = [HEADER]
    origins = {}
    method_origins = {}
    with zipfile.ZipFile(path) as z:
        source_fingerprints = json.loads(z.read("SOURCE_FINGERPRINTS.json"))
        for filename, names in SELECTION.items():
            original = z.read("runtime/medqc_ingest/" + filename)
            if filename in source_fingerprints and sha(original) != source_fingerprints[filename]["sha256"]:
                raise ValueError("primary_readonly_source_fingerprint:" + filename)
            source = original.decode("utf-8")
            tree = ast.parse(source)
            if set(names) - {node_name(node) for node in tree.body}:
                raise ValueError("primary_readonly_definition_missing:" + filename)
            manifest["source_files"][filename] = {"sha256": sha(original), "definitions": {}, "class_methods": {}}
            for node in tree.body:
                name = node_name(node)
                if name not in names:
                    continue
                segment = ast.get_source_segment(source, node)
                manifest["source_files"][filename]["definitions"][name] = sha(segment.encode())
                note = None
                if isinstance(node, ast.ClassDef):
                    for member in node.body:
                        if isinstance(member, ast.FunctionDef):
                            qualified = name + "." + member.name
                            original_sha = sha(ast.get_source_segment(source, member).encode())
                            manifest["source_files"][filename]["class_methods"][qualified] = original_sha
                            method_origins[qualified] = {"source": filename + ":" + qualified,
                                                         "source_sha256": original_sha}
                    retain = {
                        "ClinicalContract": set(),
                        "PrimaryContract": {"output_columns", "body_field", "__post_init__", "digest", "spec"},
                        "MetadataContract": {"__post_init__", "native_primary_key", "lifecycle_admission", "validate_lifecycle", "material_metadata"},
                        "ProfileCatalog": {"resolve_spec"},
                        "AcceptedManualCatalog": {"__init__", "get"},
                    }.get(name)
                    if retain is not None:
                        # 在整份源文本上按原行号裁剪，以保留被保留定义的逐字内容。
                        removed = prune_methods(source, node, retain)
                        new_node = next(n for n in ast.parse(removed).body if node_name(n) == name)
                        segment = ast.get_source_segment(removed, new_node)
                        note = "裁剪类，仅保留方法 " + ",".join(sorted(retain))
                    if node.decorator_list:
                        segment = "\n".join("@" + ast.get_source_segment(source, d) for d in node.decorator_list) + "\n" + segment
                segment, adapted = adapt(segment, name, filename)
                note = adapted or note
                sections.append("# 固定源：" + filename + ":" + name + "\n" + segment)
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    origins[name] = {"source": filename + ":" + name,
                                     "source_sha256": manifest["source_files"][filename]["definitions"][name],
                                     "adaptation": note}
            if filename in {"clinical_primary.py", "primary_metadata.py"}:
                for node in tree.body:
                    if isinstance(node, ast.FunctionDef) and node.name == "make_material":
                        manifest["audit_only_source_definitions"][filename + ":" + node.name] = sha(ast.get_source_segment(source, node).encode())
        for name in ("accepted-manual-contract.json", "clinical-primary-cache-surgery-reference.json",
                     "clinical-primary-real-fields-v2.json", "SOURCE_FINGERPRINTS.json"):
            content = z.read(name if name == "SOURCE_FINGERPRINTS.json" else "contracts/" + name)
            (DATA / name).write_bytes(content)
            manifest["json_files"][name] = sha(content)
    sections.append('METADATA_REVISION = REVISION\n' + BRIDGE)
    runtime = "\n\n\n".join(sections).rstrip() + "\n"
    for node in ast.parse(runtime).body:
        if isinstance(node, ast.Assign) and node_name(node):
            manifest["runtime_constants"][node_name(node)] = sha(
                ast.get_source_segment(runtime, node).encode()
            )
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
            manifest["runtime_definitions"][node.name] = {
                **origins.get(node.name, {"source": "business SQLAlchemy bridge", "adaptation": "新增只借连接桥"}),
                "sha256": sha(ast.get_source_segment(runtime, node).encode()),
            }
            if isinstance(node, ast.ClassDef):
                for member in node.body:
                    if isinstance(member, ast.FunctionDef):
                        qualified = node.name + "." + member.name
                        manifest["runtime_methods"][qualified] = {
                            **method_origins[qualified],
                            "adaptation": (
                                origins[node.name]["adaptation"]
                                if sha(ast.get_source_segment(runtime, member).encode())
                                != method_origins[qualified]["source_sha256"] else None
                            ),
                            "sha256": sha(ast.get_source_segment(runtime, member).encode()),
                        }
    DESTINATION.write_text(runtime, encoding="utf-8", newline="\n")
    (DATA / "READONLY_FINGERPRINTS.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate_zip", type=Path)
    build(parser.parse_args().candidate_zip)
