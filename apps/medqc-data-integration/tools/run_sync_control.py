"""源码交付包入口；无需安装wheel，不执行PowerShell脚本。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from medqc_ingest.control.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
