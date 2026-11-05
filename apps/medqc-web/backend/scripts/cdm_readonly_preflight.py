"""DSH只读预检；不导入应用启动代码，不保存配置，不输出连接凭据或患者资料。"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys

from dotenv import dotenv_values
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        values = dotenv_values(args.env_file)
        # 专用CDM配置；绝不回退DATABASE_URL业务库。
        url = make_url(values.get("CDM_DATABASE_URL") or "")
        passfile = Path(values.get("CDM_PGPASSFILE") or "")
        if url.drivername not in {"postgresql", "postgresql+psycopg2"} or url.password or not url.host or not url.database or not url.username:
            raise ValueError("explicit_cdm_url_required")
        if not passfile.is_absolute() or not passfile.is_file():
            raise ValueError("cdm_passfile_required")
        if sys.platform != "win32" and passfile.stat().st_mode & 0o077:
            raise ValueError("cdm_passfile_permissions_unsafe")
        contract = Path(__file__).resolve().parents[1] / "app/services/clinical_source_contract.py"
        spec = importlib.util.spec_from_file_location("cdm_preflight_contract", contract)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        engine = create_engine(url, hide_parameters=True, connect_args={"connect_timeout":5,
            "passfile":str(passfile), "options":"-c default_transaction_read_only=on -c statement_timeout=5000 -c lock_timeout=1000"})
        try:
            with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
                report = module.inspect_source(connection)
        finally:
            engine.dispose()
    except Exception as error:
        # 只暴露固定错误类别；底层SQL/连接字串不可出现在报告。
        report = {"ok":False,"error":"cdm_preflight_unavailable","error_type":type(error).__name__}
    output = json.dumps(report,ensure_ascii=False,indent=2)+"\n"
    if args.output:
        args.output.write_text(output,encoding="utf8")
    print(output,end="")
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
