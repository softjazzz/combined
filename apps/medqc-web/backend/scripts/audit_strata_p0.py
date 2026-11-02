"""严格离线的 P0 接线与实际 Prompt 分组探针；仅合成输入和固定响应。"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys
from unittest.mock import patch


BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


async def run_probe():
    import httpx
    from app.core.settings import Settings
    from app.llm_gateway.config import GatewaySettings, ProfileConfig, ResourceConfig
    from app.llm_gateway.main import create_app
    from app.services import llm_observability, qc_llm_client
    from app.services.llm_dispatch import client as dispatch_module
    from app.services.llm_dispatch.client import GatewayDispatchClient
    from app.services.strata_observation import capture_strata_observations
    from tests.scheduler_support.strata_synthetic import build_requests

    settings = Settings(
        _env_file=None, JWT_SECRET="synthetic-p0-only-secret", STRATA_CASE_CACHE_MODE="observe",
        LLM_DISPATCH_MODE="gateway", LLM_GATEWAY_URL="http://gateway.test",
        LLM_GATEWAY_TOKEN="synthetic-gateway-token-at-least-32-chars", LLM_GATEWAY_PROFILE="strata_first_pass",
    )
    sent = []

    def fixed(request):
        payload = json.loads(request.content)
        assert set(payload) == {"model", "messages", "temperature", "top_p", "max_tokens", "stream", "chat_template_kwargs"}
        sent.append(payload)
        return httpx.Response(200, json={
            "choices": [{"finish_reason": "stop", "message": {"content": '{"synthetic":true}'}}],
            "usage": {"prompt_tokens": 1000, "completion_tokens": 10, "total_tokens": 1010,
                      "prompt_tokens_details": {"cached_tokens": 0}},
            "timings": {"cache_n": 0, "prompt_n": 1000, "prompt_ms": 20,
                        "predicted_n": 10, "predicted_ms": 30},
        })

    profile = ProfileConfig("strata_first_pass", "gpu", "strata", "synthetic-model",
                            "http://strata.test/v1/chat/completions")
    app = create_app(GatewaySettings(
        token=settings.LLM_GATEWAY_TOKEN, resources={"gpu": ResourceConfig("gpu", 2, 4)},
        profiles={profile.name: profile}, allowed_hosts=frozenset({"strata.test"}),
        state_dir=BACKEND / ".tmp" / "unused-synthetic-sentinel", startup_isolation_seconds=0,
    ), http_transport=httpx.MockTransport(fixed), enforce_single_instance=False)
    recorder = llm_observability.LLMObservabilityRecorder(store=llm_observability.NullLLMCallEventStore())
    examples = build_requests()
    try:
        with patch.object(qc_llm_client, "get_settings", return_value=settings), \
             patch.object(llm_observability, "get_settings", return_value=settings), \
             patch.object(dispatch_module, "get_settings", return_value=settings), \
             capture_strata_observations() as captured:
            client = qc_llm_client.SichuanQCLLMClient({
                "provider_code": "strata", "dispatch_mode": "gateway", "gateway_profile": profile.name,
                "api_endpoint": "http://strata.test/v1", "model": profile.model,
            }, observability_recorder=recorder,
                gateway_dispatch_client=GatewayDispatchClient(transport=httpx.ASGITransport(app=app)))
            for label, case, prompt in examples:
                with llm_observability.llm_observation_context(
                    business_scene="synthetic_p0", root_job_id="synthetic-job",
                    record_identity=("synthetic-institution", case, "synthetic-visit"),
                    rule_set_key="synthetic", rule_set_version="v1", executor_key="exam_lab",
                ):
                    result = await client.generate(prompt)
                assert sent[-1]["messages"] == [{"role": "user", "content": prompt}]
                assert result["choices"][0]["message"]["content"] == '{"synthetic":true}'
            report = captured.report()
            report["requests"] = [
                {"fixture": example[0], **event["groups"]}
                for example, event in zip(examples, captured.events)
            ]
        report.update(real_model_calls=0, strata_connections=0, business_database_writes=0,
                      synthetic_transport_requests=len(sent),
                      evidence_kind="actual_prompt_builders_with_fixed_synthetic_response",
                      metrics_note="Token and Prefill/Decode numbers are fixtures, not measured Strata performance")
        return report
    finally:
        assert await app.state.gateway_runtime.shutdown()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="仅写安全合成报告，不包含提示词或响应正文")
    args = parser.parse_args(argv)
    from tests.scheduler_support import OfflineIsolation

    with OfflineIsolation():
        report = asyncio.run(run_probe())
    body = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(body, encoding="utf-8")
    print(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
