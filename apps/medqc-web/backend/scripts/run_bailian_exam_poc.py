"""独立百炼合成POC；默认预览，显式--run-real才可发送，禁止业务数据库连接。"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import sys
from time import perf_counter
from urllib.parse import urlsplit

import httpx


MODELS = ("qwen3.8-flash", "qwen3.6-35b-a3b")
BACKEND = Path(__file__).resolve().parents[1]


class BailianPocTransport(httpx.AsyncBaseTransport):
    """只放行显式选定的百炼文本接口、两个模型和最多12个实际HTTP请求。"""

    def __init__(self, endpoint: str, *, inner=None):
        parsed = urlsplit(endpoint)
        if (parsed.scheme != "https" or parsed.hostname not in {
                "dashscope.aliyuncs.com", "dashscope-intl.aliyuncs.com"}
                or parsed.port not in (None, 443) or parsed.username or parsed.password
                or parsed.query or parsed.fragment or parsed.path != "/compatible-mode/v1/chat/completions"):
            raise ValueError("unsupported explicit Bailian endpoint")
        self.endpoint, self.inner = endpoint, inner
        self.requests: list[dict] = []
        self.fatal = False

    async def handle_async_request(self, request):
        body = json.loads(request.content)
        if (self.fatal or request.method != "POST" or str(request.url) != self.endpoint
                or body.get("model") not in MODELS or body.get("stream") is not False
                or body.get("enable_thinking") is not False
                or body.get("max_tokens", 0) > 4096 or len(request.content) > 512_000
                or set(body) & {"tools", "strata_prefix", "chat_template_kwargs"}
                or len(self.requests) >= 12):
            raise RuntimeError("POC request outside the authorized bound")
        item = {"model": body["model"], "status": "started", "enable_thinking_sent": False,
                "max_tokens_sent": body.get("max_tokens")}
        self.requests.append(item)
        started = perf_counter()
        try:
            if self.inner is not None:
                response = await self.inner.handle_async_request(request)
            else:
                async with httpx.AsyncHTTPTransport(retries=0, trust_env=False) as transport:
                    response = await transport.handle_async_request(request)
                    await response.aread()
            item["http_status"] = response.status_code
            if response.status_code in {401, 403}:
                self.fatal = True
            if response.is_success:
                payload = response.json()
                item.update(status="success", returned_model=payload.get("model"), usage=payload.get("usage"),
                            finish_reason=(payload.get("choices") or [{}])[0].get("finish_reason"))
                # 只保留合成材料的答案以供离线复用；不保存headers、凭据或reasoning_content。
                item["completion"] = {"model": payload.get("model"), "usage": payload.get("usage"),
                    "choices": [{"finish_reason": choice.get("finish_reason"),
                                 "message": {"content": (choice.get("message") or {}).get("content")}}
                                for choice in payload.get("choices", [])]}
            else:
                item["status"] = "http_error"
            return response
        except Exception as error:
            item.update(status="failed", error_type=type(error).__name__)
            raise
        finally:
            item["elapsed_seconds"] = perf_counter() - started


def forbid_databases() -> None:
    import sqlalchemy
    import sqlalchemy.engine
    import sqlalchemy.ext.asyncio
    import sqlite3

    def deny(*_args, **_kwargs):
        raise RuntimeError("POC_DATABASE_ACCESS_BLOCKED")

    sqlalchemy.create_engine = deny
    sqlalchemy.engine.create_engine = deny
    sqlalchemy.ext.asyncio.create_async_engine = deny
    sqlite3.connect = deny
    try:
        import psycopg2
        psycopg2.connect = deny
    except ImportError:
        pass


def cases():
    from app.services.luxian_0609.exam_lab_fact_extraction import build_exam_lab_text_projection

    for name, course, expected in (
        ("result_paraphrase", "已阅本次胸部CT：右肺下叶小结节，倾向炎性，继续观察。", True),
        ("plan_only", "拟完善胸部CT检查，进一步了解病变情况。", False),
        ("external_prior_exam", "外院既往胸部CT曾见右肺下叶结节，本次检查结果尚待回报。", False),
    ):
        projection = build_exam_lab_text_projection(rows_by_source={
            "exam_master": ({"exam_id": "SYN-EX-1", "exam_name": "胸部CT平扫",
                             "exam_time": "2026-01-02 10:00:00", "report_time": "2026-01-02 11:00:00",
                             "exam_conclusion": "右肺下叶见8mm结节影，考虑炎性结节；建议随访。"},),
            "daily_course_record": ({"document_id": "SYN-DOC-1", "record_time": "2026-01-02 15:00:00",
                                     "record_content": course},),
        })
        yield name, projection, expected


async def run(args) -> int:
    if not args.run_real:
        print(json.dumps({"mode": "preview", "models": MODELS, "synthetic_cases": args.cases,
                          "planned_arms": ["reference", "cascade"], "http_calls": 0, "database_writes": 0}))
        return 0
    from dotenv import dotenv_values

    values = dotenv_values(Path(args.env_file).resolve())
    is_bailian_default = values.get("LLM_DEFAULT_PROVIDER", "alibaba").strip().lower() == "alibaba"
    key = values.get("DASHSCOPE_API_KEY") or (values.get("LLM_API_KEY") if is_bailian_default else None)
    base = str(values.get("DASHSCOPE_BASE_URL") or (values.get("LLM_API_ENDPOINT") if is_bailian_default else "") or "").rstrip("/")
    if not key or not base:
        raise ValueError("explicit Bailian deployment credentials are unavailable")
    sender = BailianPocTransport(base + "/chat/completions")
    # 仅此进程使用最小环境；不继承业务DSN、不加载项目.env，也不修改任何.env文件。
    keep = {k: v for k, v in os.environ.items() if k.upper() in {
        "PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "USERPROFILE", "APPDATA", "LOCALAPPDATA"}}
    os.environ.clear()
    os.environ.update(keep, DATABASE_URL="", REMOTE_DB_URL="", PYTHONIOENCODING="utf-8")
    forbid_databases()
    sys.path.insert(0, str(BACKEND))
    from app.core import settings as settings_module

    token = secrets.token_urlsafe(36)
    settings = settings_module.Settings(_env_file=None, JWT_SECRET=secrets.token_urlsafe(32),
        LLM_DEFAULT_PROVIDER="alibaba", LLM_VISIBLE_PROVIDERS=["alibaba"],
        LLM_DISPATCH_MODE="gateway", LLM_GATEWAY_URL="http://poc-gateway.invalid",
        LLM_GATEWAY_TOKEN=token, LLM_GATEWAY_PROFILES={"alibaba": {
            MODELS[0]: "alibaba_reference", MODELS[1]: "alibaba_candidate"}})
    settings_module.get_settings = lambda: settings
    from app.llm_gateway.config import GatewaySettings, ProfileConfig, ResourceConfig
    from app.llm_gateway.main import create_app
    from app.services import exam_result_model_route as route, qc_llm_client
    from app.services.llm_dispatch.client import GatewayDispatchClient
    from app.services.llm_observability import LLMObservabilityRecorder, NullLLMCallEventStore
    from app.services.luxian_0609 import exam_result_record_check as check

    route.get_settings = lambda: settings
    gateway = create_app(GatewaySettings(token=token,
        resources={"bailian": ResourceConfig("bailian", 1, 4)},
        profiles={name: ProfileConfig(name, "bailian", "alibaba", model, sender.endpoint, key)
                  for name, model in (("alibaba_reference", MODELS[0]), ("alibaba_candidate", MODELS[1]))},
        allowed_hosts=frozenset({urlsplit(sender.endpoint).hostname}),
        state_dir=Path(args.output_dir).resolve(), startup_isolation_seconds=0),
        http_transport=sender, enforce_single_instance=False)
    reference = qc_llm_client.SichuanQCLLMClient({"provider_code": "alibaba", "model": MODELS[0],
        "api_endpoint": base, "dispatch_mode": "gateway", "gateway_profile": "alibaba_reference",
        "timeout_seconds": 120, "custom_parameters": {"temperature": 0.0, "top_p": 0.9, "max_tokens": 4096}},
        gateway_dispatch_client=GatewayDispatchClient(transport=httpx.ASGITransport(app=gateway)),
        observability_recorder=LLMObservabilityRecorder(store=NullLLMCallEventStore()))
    experiment = "A1-bailian-" + secrets.token_hex(6)
    results = []
    print(json.dumps({"event": "scope", "models": MODELS, "cases": args.cases,
                      "max_http_calls": 12, "synthetic_only": True, "database_writes": 0}), flush=True)
    try:
        for name, projection, expected in list(cases())[:args.cases]:
            for arm in ("reference", "cascade"):
                settings.LLM_EXAM_RESULT_ROUTING = {} if arm == "reference" else {
                    "mode": "cascade", "experiment": experiment,
                    "candidate_provider": "alibaba", "candidate_profile": "alibaba_candidate",
                    "candidate_model": MODELS[1], "candidate_revision": "bailian-api-alias-" + MODELS[1],
                    "reference_revision": "bailian-api-alias-" + MODELS[0],
                    "candidate_parameters": {"temperature": 0.0, "top_p": 0.9}}
                before = len(sender.requests)
                checked = await check.check_exam_result_record(projection, reference)
                recorded = bool(checked.recorded_refs.get(1)) if checked.state == "ready" else None
                item = {"event": "case", "case": name, "arm": arm, "state": checked.state,
                        "expected_recorded": expected, "recorded": recorded,
                        "matches_synthetic_expectation": recorded is expected,
                        "http_calls": len(sender.requests) - before, "logical_calls": checked.llm_call_count,
                        "prompt_tokens": checked.prompt_tokens, "completion_tokens": checked.completion_tokens,
                        "total_tokens": checked.total_tokens, "elapsed_seconds": checked.api_time}
                results.append(item)
                print(json.dumps(item), flush=True)
                if sender.fatal:
                    return 2
    finally:
        await gateway.state.gateway_runtime.shutdown()
        directory = Path(args.output_dir).resolve()
        directory.mkdir(parents=True, exist_ok=True)
        report = directory / ("bailian-exam-poc-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-private.json")
        report.write_text(json.dumps({"models": MODELS, "synthetic_only": True, "database_writes": 0,
            "results": results, "requests": sender.requests}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"event": "report", "path": str(report), "http_calls": len(sender.requests),
                          "database_writes": 0}), flush=True)
    return 0 if all(item["matches_synthetic_expectation"] for item in results) else 3


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-real", action="store_true")
    parser.add_argument("--env-file", default=str(BACKEND / ".env"))
    parser.add_argument("--cases", type=int, choices=(1, 2, 3), default=3)
    parser.add_argument("--output-dir", default=str(BACKEND / ".tmp" / "bailian-exam-poc"))
    try:
        return asyncio.run(run(parser.parse_args(argv)))
    except Exception as error:
        print(json.dumps({"event": "error", "error_type": type(error).__name__, "database_writes": 0}), flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
