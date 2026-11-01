"""用既有合成应答重放正式结果链；始终启用原严格 offline 护栏，无真实调用选项。"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args(argv)
    artifact, report = args.artifact.resolve(), args.report.resolve()
    if artifact == report or artifact.suffix != ".json" or report.suffix != ".json":
        parser.error("input and output must be distinct JSON paths")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.run_qc_scheduler_tests import main as run_offline

    keys = {"MEDQC_EXAM_POC_ARTIFACT": str(artifact), "MEDQC_EXAM_POC_REPORT": str(report)}
    previous = {key: os.environ.get(key) for key in keys}
    os.environ.update(keys)
    try:
        return run_offline(["--profile", "offline",
                            "tests/unit/test_exam_poc_acceptance.py::test_existing_recording_full_offline_chain"])
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


if __name__ == "__main__":
    raise SystemExit(main())
