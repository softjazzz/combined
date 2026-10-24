"""构建无患者资料/凭据的客户 P0 工具包，补丁仅定位已知 AST 节点。"""

import argparse
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import zipfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--staging", type=Path, required=True)
    args = parser.parse_args()
    app = Path(__file__).resolve().parents[2]
    backend = app / "backend"
    root = app.parents[1]
    spec = importlib.util.spec_from_file_location("p0_installer_builder", backend / "scripts/install_p0_chain_fix.py")
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    entries = {
        "app/services/custom_qc_workspace_service.py": [("CustomQCWorkspaceService", "complete_batch_job")],
        "app/routers/runtime_build.py": [("initialize_runtime_build",)],
        "app/services/luxian_0609/native_transfusion_execution.py": [("_programmatic_044_status",)],
        "app/services/bundles/assembly.py": [("_inventory_entry",), ("load_domain_bundle_document_index",)],
        "app/services/bundles/emr_view.py": [("_normalize_source_document",), ("_normalize_source_document_summary",)],
        "app/services/document_assembly/assembler.py": [("INDEPENDENT_DOCUMENT_FIELDS",), ("_SECTION_LABELS",), ("_MULTI_FIELD_RULES",), ("build_document_select_columns",), ("assemble_document",)],
        "app/services/luxian_0609/source_evidence_reader.py": [("_NATIVE_SOURCE_FIELDS",)],
        "app/services/dual_source_write_policy.py": [("build_write_batch",)],
    }
    manifest = {"protocol": "medqc-p0-chain-v1", "nodes": {}, "new_files": {}}
    args.staging.mkdir(parents=True, exist_ok=False)
    for relative, paths in entries.items():
        current = (backend / relative).read_text(encoding="utf8")
        variants = [current]
        for commit in ("366d8b7af", "56c05f05c"):
            variants.append(subprocess.check_output(["git", "show", f"{commit}:apps/medqc-web/backend/{relative}"], cwd=root).decode("utf8"))
        changes = []
        for path in paths:
            node = installer.node_at(ast.parse(current), path)
            new = installer.segment(current, node)
            if relative in {"app/services/bundles/assembly.py", "app/services/bundles/emr_view.py"} and "INDEPENDENT_DOCUMENT_FIELDS" in new:
                # 局部导入避免为整个旧模块重写 import 区域。
                lines = new.splitlines(keepends=True)
                insert = node.body[0].lineno - node.lineno
                lines.insert(insert, "    from ..document_assembly.assembler import INDEPENDENT_DOCUMENT_FIELDS\n")
                new = "".join(lines)
            hashes = []
            for text in variants:
                old_node = installer.node_at(ast.parse(text), path)
                value = installer.digest(installer.segment(text, old_node).encode()) if old_node else None
                if value not in hashes:
                    hashes.append(value)
            change = {"path": list(path), "new": new, "old_sha256": hashes}
            if path == ("INDEPENDENT_DOCUMENT_FIELDS",):
                change["insert_before"] = "_SPECIAL_SELECT_FIELDS"
            changes.append(change)
        manifest["nodes"][relative] = changes
    new_files = (
        "app/services/qc_workspace/offline_failure_recovery.py", "app/services/qc_workspace/material_chain_acceptance.py",
        "app/services/qc_workspace/p0_runtime.py", "app/services/document_assembly/signature_sync.py",
    )
    for relative in new_files:
        data = (backend / relative).read_bytes()
        target = args.staging / "assets" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        manifest["new_files"][relative] = hashlib.sha256(data).hexdigest()
    (args.staging / "p0-patch-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf8")
    for filename in ("install_p0_chain_fix.py", "verify_p0_material_chain.py", "repair_p0_materials.py", "recover_p0_failed_results.py", "check_p0_restart_safety.py"):
        (args.staging / filename).write_bytes((backend / "scripts" / filename).read_bytes())
    # 只读验收也能在安装前运行；使用工具包 owner 比较真实已安装规则取数。
    (args.staging / "material_chain_acceptance.py").write_bytes((backend / new_files[1]).read_bytes())
    (args.staging / "accept-medqc-p0.ps1").write_bytes((app / "scripts/accept-medqc-p0.ps1").read_bytes())
    (args.staging / "upgrade-medqc-pg-053.ps1").write_bytes((app / "scripts/upgrade-medqc-pg-053.ps1").read_bytes())
    (args.staging / "upgrade_customer_pg_053.py").write_bytes((app / "tools/deployment/upgrade_customer_pg_053.py").read_bytes())
    migrations = {}
    (args.staging / "migrations").mkdir()
    for filename in ("20261023_000052_death_structured_fields.py", "20261023_000053_visit_index_resolved_sync_fields.py"):
        data = (backend / "alembic/versions" / filename).read_bytes()
        (args.staging / "migrations" / filename).write_bytes(data)
        migrations[filename] = hashlib.sha256(data).hexdigest()
    (args.staging / "migration-sha256.json").write_text(json.dumps(migrations, indent=2), encoding="utf8")
    (args.staging / "README.txt").write_text(
        "P0 closeout: five material categories and original failed-pair recovery.\n"
        "No credentials, case coordinates, patient text or recorded model responses are bundled.\n"
        "Closeout: backup/upgrade 053; backup/patch known source nodes; restart backend in existing acceptance mode; "
        "backup/fill empty clinical fields and refresh bundles; readonly live-source acceptance; offline original-failure replay; "
        "backup/CAS merge only recoverable failures. Stop on gaps or missing exact recordings.\n"
        "Existing successful results and unrelated canonical envelopes must be preserved. No network model fallback or 27-case QC rerun.\n"
        "Source-only Save documents without existing approval remain pending; never auto-approve them.\n"
        "Requires no active QC tasks. PostgreSQL and frontend remain running; only backend port 8001 is restarted.\n", encoding="utf8")
    with zipfile.ZipFile(args.output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(args.staging.rglob("*")):
            if file.is_file():
                archive.write(file, file.relative_to(args.staging).as_posix())
    with zipfile.ZipFile(args.output) as archive:
        assert archive.testzip() is None
    print(json.dumps({"package": str(args.output), "bytes": args.output.stat().st_size,
                      "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(), "database_writes": 0}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
