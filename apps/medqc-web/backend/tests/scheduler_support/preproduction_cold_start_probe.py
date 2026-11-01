"""固定冷启动探针；仅由校验入口在子进程隔离安装后执行。"""


def run_probe():

    import json
    import os
    import socket
    import subprocess
    from pathlib import Path
    from tempfile import TemporaryDirectory
    import dotenv
    from pydantic_settings import BaseSettings, SettingsConfigDict
    from sqlalchemy import create_engine
    from tests.scheduler_support.isolation import OfflineIsolationError

    def denied(action):
        try:
            action()
        except OfflineIsolationError:
            return True
        raise AssertionError("cold probe isolation was not installed")

    # .env检查只用临时合成文件，不访问部署配置。
    with TemporaryDirectory(prefix="qc-cold-start-") as folder:
        env_file = Path(folder) / ".env"
        env_file.write_text("probe_value=should-not-load\n", encoding="utf-8")
        assert dotenv.dotenv_values(env_file) == {}

        class DotenvProbe(BaseSettings):
            probe_value: str = "blocked"
            model_config = SettingsConfigDict(env_file=str(env_file), extra="ignore")

        dotenv_denied = DotenvProbe().probe_value == "blocked"
        assert dotenv_denied

    # 在业务导入前用真实边界验证，不访问客户机/Strata或业务端口。
    assert os.environ.get("DATABASE_URL") == ""
    assert os.environ.get("REMOTE_DB_URL") == ""
    assert os.environ.get("MEDQC_QC_SCHEDULER_OFFLINE") == "1"
    assert not any(
        key in os.environ for key in ("LLM_API_KEY", "LLM_GATEWAY_TOKEN", "PGPASSWORD")
    )
    with socket.socket() as sock:
        socket_denied = denied(lambda: sock.connect(("127.0.0.1", 9)))
    dns_denied = denied(lambda: socket.getaddrinfo("provider.example.invalid", 443))
    process_denied = denied(lambda: subprocess.run(["not-allowed"], check=False))
    engine = create_engine("postgresql+psycopg2://offline:offline@127.0.0.1:1/offline")
    try:
        database_denied = denied(engine.connect)
    finally:
        engine.dispose()

    import asyncio
    import sys
    from types import SimpleNamespace

    from app.services.luxian_0609 import preproduction_runner as runner
    from app.services.luxian_0609_rule_master import load_luxian_0609_rule_master

    RULE_IDS = tuple(entry.rule_id for entry in load_luxian_0609_rule_master()[:49])

    assert "app.services.sichuan_qc_service" not in sys.modules

    class Context:
        native_llm_call_count = 0
        native_prompt_tokens = 0
        native_completion_tokens = 0
        native_total_tokens = 0
        native_api_time = 0.0

    async def prepare(**_):
        return [], Context()

    def aggregate(*, orchestrated, **_):
        orchestrated["results"] = [
            {
                "rule_id": rule_id,
                "rule_code": rule_id,
                "status": "not_applicable",
                "is_compliant": True,
            }
            for rule_id in RULE_IDS
        ]
        return orchestrated

    runner.prepare_luxian_0609_execution = prepare
    runner.aggregate_luxian_0609_orchestrated_results = aggregate

    async def main():
        result = await runner.run_luxian_0609_preproduction(
            bundle={"scene": "running"},
            selected_customer_rule_ids=RULE_IDS,
            evaluation_as_of_date="2026-07-17",
            llm_client=object(),
            base_settings=SimpleNamespace(),
            model_name="model",
        )
        assert len(result["results"]) == 49
        assert "app.services.sichuan_qc_service" not in sys.modules

    asyncio.run(main())
    print(
        "COLD_START_PROBE_OK "
        + json.dumps(
            {
                "rule_results": len(RULE_IDS),
                "service_loaded": "app.services.sichuan_qc_service" in sys.modules,
                "socket_denied": socket_denied,
                "dns_denied": dns_denied,
                "database_denied": database_denied,
                "process_denied": process_denied,
                "dotenv_denied": dotenv_denied,
                "model_calls": 0,
                "database_writes": 0,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    run_probe()
