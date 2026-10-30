"""新建专属一次性容器后执行真实 M2 验收；不接受外部 DSN，不启动本机已有服务。"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import time
import uuid


BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from tests.scheduler_support.infra import InfraSpec, LABEL, inspect_owned, load_spec  # noqa: E402


IMAGES = {"pg": "postgres:16.15-alpine", "mq": "rabbitmq:4.1.8-management-alpine"}


def docker(*args):
    result = subprocess.run(["docker", *args], capture_output=True, text=True,
                            encoding="utf-8", timeout=180, check=False)
    if result.returncode:
        raise RuntimeError("dedicated Docker operation failed")
    return result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    run_id, password = uuid.uuid4().hex, secrets.token_hex(24)
    containers, versions = [], {}
    report = {"run_id": run_id, "business_database_writes": 0, "real_model_calls": 0,
              "images": IMAGES, "complete": False}
    try:
        override = os.environ.get("DOCKER_HOST", "")
        if override and not override.startswith(("unix://", "npipe://")):
            raise RuntimeError("remote Docker overrides are forbidden")
        context = json.loads(docker("context", "inspect"))[0]
        endpoint = context.get("Endpoints", {}).get("docker", {}).get("Host", "")
        if not endpoint.startswith(("unix://", "npipe://")):
            raise RuntimeError("isolated infrastructure requires a local Docker endpoint")
        docker("info", "--format", "{{.ServerVersion}}")
        with tempfile.TemporaryDirectory(prefix="medqc-qc-infra-") as temp:
            temp_path = Path(temp)
            username, database = "qc_" + run_id[:12], "medqc_qc_infra_" + run_id
            for role in ("pg", "mq"):
                env_file = temp_path / (role + ".env")
                content = (f"POSTGRES_DB={database}\nPOSTGRES_USER={username}\nPOSTGRES_PASSWORD={password}\n"
                           if role == "pg" else
                           f"RABBITMQ_DEFAULT_VHOST=medqc-qc-infra-{run_id}\nRABBITMQ_DEFAULT_USER={username}\nRABBITMQ_DEFAULT_PASS={password}\n")
                env_file.write_text(content, encoding="utf-8")
                env_file.chmod(0o600)
                ports = ("5432",) if role == "pg" else ("5672", "15672")
                command = ["create", "--label", f"{LABEL}={run_id}", "--env-file", str(env_file)]
                for port in ports:
                    command.extend(["-p", f"127.0.0.1::{port}"])
                container = docker(*command, IMAGES[role])
                containers.append(container)
                docker("start", container)
                row = inspect_owned(container, run_id)
                versions[role] = row["Image"]
            def port(container, number):
                row = inspect_owned(container, run_id)
                return int(row["NetworkSettings"]["Ports"][f"{number}/tcp"][0]["HostPort"])
            spec = InfraSpec(run_id, containers[0], containers[1], port(containers[0], 5432),
                             port(containers[1], 5672), port(containers[1], 15672), password)
            manifest = temp_path / "owner-private.json"
            raw = asdict(spec)
            raw.pop("manifest_path")
            manifest.write_text(json.dumps(raw), encoding="utf-8")
            manifest.chmod(0o600)
            spec = load_spec(str(manifest))
            import httpx
            import psycopg2
            deadline = time.monotonic() + 120
            while True:
                try:
                    with psycopg2.connect(host="127.0.0.1", port=spec.pg_port, dbname=database,
                                          user=username, password=password, connect_timeout=2):
                        pass
                    r = httpx.get(f"http://127.0.0.1:{spec.management_port}/api/overview",
                                  auth=(username, password), timeout=2)
                    r.raise_for_status()
                    report["rabbitmq_version"] = r.json()["rabbitmq_version"]
                    break
                except Exception:
                    if time.monotonic() >= deadline:
                        raise RuntimeError("dedicated infrastructure readiness timeout") from None
                    time.sleep(1)
            result = subprocess.run(
                [sys.executable, "-B", "scripts/run_qc_scheduler_tests.py", "--profile", "isolated-infra",
                 "--suite", "m2-infra", "--infra-manifest", str(manifest)],
                cwd=BACKEND, env=spec.environment(), capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=600, check=False,
            )
            safe_output = (result.stdout + result.stderr).replace(password, "<REDACTED>")
            print(safe_output)
            report.update(complete=result.returncode == 0, test_exit_code=result.returncode,
                          image_ids=versions)
    except Exception as exc:
        report.update(error_type=type(exc).__name__, error_code="isolated_infra_failed")
    finally:
        cleanup = True
        for container in reversed(containers):
            try:
                inspect_owned(container, run_id)
                docker("rm", "--force", "--volumes", container)
            except Exception:
                cleanup = False
        report["owned_containers_removed"] = cleanup
        (output / "m2-infra-result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, sort_keys=True))
    return 0 if report["complete"] and report["owned_containers_removed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
