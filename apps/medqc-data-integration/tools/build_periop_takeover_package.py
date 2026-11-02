"""生成独立第二批接管交付包；不包含客户数据、运行配置或密码文件。"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULT_SHA = "a23d0833f887470b1c48e70792e7014d1155d481d4a8585be6ebbefe949cf56e"


def build(result_zip, output):
    if output.exists():
        raise ValueError("new_package_output_required")
    if hashlib.sha256(result_zip.read_bytes()).hexdigest() != RESULT_SHA:
        raise ValueError("customer_result_sha256")
    with zipfile.ZipFile(result_zip) as archive:
        entries = archive.namelist()
        checksums = archive.read("CHECKSUMS.txt").decode("utf-8-sig").splitlines()
        verified = 0
        for line in checksums:
            digest, name = line.split(None, 1)
            name = name.strip().lstrip("*")
            if hashlib.sha256(archive.read(name)).hexdigest() != digest:
                raise ValueError("customer_result_checksum")
            verified += 1
        if len(entries) != 25 or verified != 24:
            raise ValueError("customer_result_inventory")
        regression = json.loads(archive.read("metadata-regression.json"))
    selected = list((ROOT / "src/medqc_ingest").rglob("*.py"))
    selected += sorted((ROOT / "migrations").glob("00[1-5]_*.sql"))
    selected += [
        ROOT / relative
        for relative in (
            "contracts/periop-acceptance-contracts.json",
            "tools/prepare_periop_takeover.py",
            "tools/run_periop_replay.py",
            "tools/accept_periop_projection.py",
            "tools/preflight_periop_projection.py",
            "tools/periop_transform.py",
            "tools/major_document_transform.py",
            "tests/test_periop_takeover.py",
            "docs/2026-10-31-periop-metadata-result-and-takeover.md",
        )
    ]
    files = {str(path.relative_to(ROOT)).replace("\\", "/"): path.read_bytes() for path in selected}
    files["DSH_START.txt"] = (ROOT / "docs/DSH_PERIOP_TAKEOVER.txt").read_bytes()
    files["README.md"] = (
        "# 第二批独立归档接管 v1\n\n"
        "执行顺序和范围以 DSH_START.txt 为准。本包不连接Caché、不重抽、不启用任务。\n"
        "独立profile的13个非空来源复用0.3.2正式引擎；原13来源注册表原样保留。\n"
        "日期语义未确认：仅显式日期归档replay，无incremental/automatic入口。\n"
        "客户须在PG16四个新库验收；开发机合成PG18通过不能替代客户验收。\n"
        "已归档的4历史源失败和1故障注入应保留为failed，不清理或伪装成功。\n"
        "后续手工归档重放：\n\n"
        "```powershell\n"
        "& $python (Join-Path $release 'tools\\run_periop_replay.py') "
        "--config (Join-Path $runRoot 'runtime.json') "
        "--interface web.nursing_record --date 2026-10-28\n"
        "```\n\n"
        "这条命令只读已接管快照，然后写入新ingest/CDM，不会查询Caché。\n"
        "本次DSH只执行prepare，不需再运行此命令。\n"
    ).encode()
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    files["manifest.json"] = (
        json.dumps(
            {
                "package": "periop-archive-takeover-v1",
                "core_version": "0.3.2",
                "commit": commit,
                "customer_result_sha256": RESULT_SHA,
                "customer_result_checksums_verified": verified,
                "active_interfaces": 13,
                "disabled_interfaces": 4,
                "raw_rows": 9365,
                "date_semantics": "unverified",
                "automatic_incremental": False,
                "cache_accessed_by_package": False,
                "contains_phi": False,
                "contains_raw_values": False,
                "contains_keys": False,
                "offline_test_command": (
                    "python -m unittest discover -s tests -p test_periop_takeover.py -v"
                ),
                "offline_tests": 18,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    ).encode()
    # 仅留源回归的聚合证据；不携带入口逐病例内容或运行配置。
    files["evidence/metadata-regression.json"] = (
        json.dumps(regression, ensure_ascii=False, indent=2) + "\n"
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
