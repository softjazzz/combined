"""打包只读正式入口验收工具及原样模块，不包含迁移/抽取/发布启动器。"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
BACKEND = REPO / "apps/medqc-web/backend"


def build(output, baseline_zip):
    if output.exists():
        raise RuntimeError("refuse_existing_package")
    expected_baseline = "170691116e5275bbd2f46afb67e0ad1654aa0d35abfa775afbdbbcf39f793483"
    if hashlib.sha256(baseline_zip.read_bytes()).hexdigest() != expected_baseline:
        raise RuntimeError("baseline_result_zip_mismatch")
    data = {}
    with zipfile.ZipFile(baseline_zip) as source:
        for filename in [
            "field-visibility.json",
            "source-registration.json",
            "time-equality.json",
            "manifest.json",
        ]:
            data["baseline/" + filename] = source.read(filename)
    for name in [
        "contracts/periop-acceptance-contracts.json",
        "tools/audit_periop_readers.py",
        "tools/periop_transform.py",
        "tools/major_document_transform.py",
        "tests/test_periop_reader_audit.py",
        "tests/test_periop_metadata.py",
        "tests/test_periop_reader_regression.py",
        "contracts/periop-reader-metadata-fix.json",
        "tools/periop_reader_regression.py",
        "docs/periop-reader-gap-disposition.csv",
        "docs/periop-reader-source-limitations.csv",
    ]:
        data[name] = (ROOT / name).read_bytes()
    data["DSH_START.txt"] = (ROOT / "docs/DSH_PERIOP_READER_AUDIT.txt").read_bytes()
    data["README.md"] = (ROOT / "docs/2026-10-31-periop-reader-audit.md").read_bytes()
    helpers = [
        "app/__init__.py",
        "app/database/__init__.py",
        "app/database/connection.py",
        "app/database/models/__init__.py",
        "app/database/models/cdm.py",
        "app/database/models/qc.py",
        "app/services/__init__.py",
        "app/services/document_assembly/__init__.py",
        "app/services/document_assembly/assembler.py",
        "app/services/document_assembly/signatures.py",
        "app/services/bundles/__init__.py",
        "app/services/bundles/assembly.py",
        "app/services/bundles/contracts.py",
        "app/services/bundles/factory.py",
        "app/services/bundles/masking.py",
        "app/services/bundles/refresh_manager.py",
        "app/services/luxian_0609/__init__.py",
        "app/services/luxian_0609/source_evidence_reader.py",
        "app/services/luxian_0609/surgery_procedure_catalog.py",
        "app/services/validation_material_source.py",
        "app/data/surgery_procedure_catalog_2025.csv",
    ]
    for name in helpers:
        data["backend/" + name] = (BACKEND / name).read_bytes()
    data["manifest.json"] = (
        json.dumps(
            {
                "package_kind": "periop-reader-readonly-v2",
                "base_commit": subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=REPO, text=True
                ).strip(),
                "database": "medqc_periop_cdm_acceptance_20261031212605",
                "readonly": True,
                "inventory_count": len(data) + 1,
                "contains_phi": False,
                "contains_raw_values": False,
                "contains_credentials": False,
                "official_modules_copied_verbatim": True,
                "creates_databases": False,
                "modifies_registration": False,
                "baseline_result_zip_sha256": expected_baseline,
                "bundle_metadata_fields_added": 14,
                "required_nonempty_field_repairs": 12,
                "production_code_change": "document_assembly.assembler.INDEPENDENT_DOCUMENT_FIELDS",
            },
            indent=2,
        )
        + "\n"
    ).encode()
    data["CHECKSUMS.txt"] = "".join(
        f"{hashlib.sha256(b).hexdigest()}  {name}\n" for name, b in sorted(data.items())
    ).encode()
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as z:
        for name, b in sorted(data.items()):
            z.writestr(name, b)
    print(
        json.dumps(
            {
                "path": str(output),
                "bytes": output.stat().st_size,
                "files": len(data),
                "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline-zip", type=Path, required=True)
    args = parser.parse_args()
    build(args.output, args.baseline_zip)
