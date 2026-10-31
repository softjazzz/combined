"""冻结真实源验证包；仅包含代码、合同和非PHI基线证据。"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from medqc_ingest.periop_live import (  # noqa: E402
    BASELINE_RESULT_SHA,
    verify_baseline_evidence,
)


def build(result_zip, output):
    if output.exists():
        raise ValueError("new_package_required")
    if hashlib.sha256(result_zip.read_bytes()).hexdigest() != BASELINE_RESULT_SHA:
        raise ValueError("baseline_result_hash")
    with zipfile.ZipFile(result_zip) as archive:
        names = archive.namelist()
        checks = archive.read("CHECKSUMS.txt").decode("utf-8-sig").splitlines()
        if len(names) != 9 or len(checks) != 8:
            raise ValueError("baseline_result_inventory")
        for line in checks:
            digest, name = line.split(None, 1)
            if hashlib.sha256(archive.read(name.strip().lstrip("*"))).hexdigest() != digest:
                raise ValueError("baseline_result_checksum")
        acceptance = archive.read("acceptance.json")
        plan = archive.read("database-plan.json")
        verify_baseline_evidence(json.loads(acceptance), json.loads(plan))
    selected = list((ROOT / "src/medqc_ingest").rglob("*.py"))
    selected += [
        ROOT / item
        for item in (
            "contracts/periop-acceptance-contracts.json",
            "tools/validate_periop_live.py",
            "tools/prepare_periop_takeover.py",
            "tools/accept_periop_projection.py",
            "tools/preflight_periop_projection.py",
            "tools/periop_transform.py",
            "tools/major_document_transform.py",
            "tests/test_periop_live.py",
            "docs/2026-11-01-periop-live-source-validation.md",
        )
    ]
    files = {str(path.relative_to(ROOT)).replace("\\", "/"): path.read_bytes() for path in selected}
    files["DSH_START.txt"] = (ROOT / "docs/DSH_PERIOP_LIVE.txt").read_bytes()
    files["evidence/baseline-acceptance.json"] = acceptance
    files["evidence/baseline-database-plan.json"] = plan
    files["README.md"] = (
        "# 第二批真实源显式日期验证 v1\n\n"
        "严格按DSH_START.txt一次执行。固定2026-10-28、第二批13活动来源、4禁用来源不变。\n"
        "只读已接受第二批基线，所有写入四个全新独立库。原13接口/业务库不访问。\n"
        "原runtime.json仅作Caché连接字段只读输入，不运行其服务或使用其PG配置。\n"
        "客户CLI无虚构来源/自动增量开关，不生成或启用任务。\n"
        "允许源端迟到修改，第一次写入按实测；其后两轮发布幂等，逐字段核验与备份恢复。\n"
        "已知厂商失败按接口+日期+实际错误码严格处理；有未刷新来源则输出带限制验收，不能冒充全量刷新。\n"
        "开发机合成PG18/虚构来源测试不代表客户真实Caché/PG16已通过。\n"
    ).encode()
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    files["manifest.json"] = (
        json.dumps(
            {
                "package": "periop-live-source-validation-v1",
                "commit": commit,
                "core_version": "0.3.2",
                "baseline_result_sha256": BASELINE_RESULT_SHA,
                "baseline_checksums_verified": 8,
                "active_interfaces": 13,
                "disabled_interfaces": 4,
                "explicit_date_required": True,
                "customer_date": "2026-10-28",
                "automatic_incremental": False,
                "scheduled_task_created": False,
                "offline_tests": 16,
                "contains_phi": False,
                "contains_raw_values": False,
                "contains_keys": False,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    ).encode()
    files["CHECKSUMS.txt"] = "".join(
        hashlib.sha256(data).hexdigest() + "  " + name + "\n"
        for name, data in sorted(files.items())
    ).encode()
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            archive.writestr(name, data)
    print(
        json.dumps(
            {
                "path": str(output),
                "bytes": output.stat().st_size,
                "files": len(files),
                "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-zip", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    build(args.result_zip, args.output)
