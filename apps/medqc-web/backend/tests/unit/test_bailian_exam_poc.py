"""真实POC的默认预览、网络边界与请求预算；本测试始终严格offline。"""

import json

import httpx
import pytest

from scripts.run_bailian_exam_poc import BailianPocTransport, MODELS, main


ENDPOINT = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"


def test_default_preview_does_not_read_credentials_or_send(capsys):
    assert main(["--env-file", "does-not-exist.env"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["http_calls"] == output["database_writes"] == 0
    assert output["models"] == list(MODELS)


def test_real_flag_still_cannot_bypass_offline_dotenv_guard(tmp_path, capsys):
    env = tmp_path / "backend.env"
    env.write_text("DASHSCOPE_API_KEY=synthetic-never-print\n", encoding="utf-8")
    assert main(["--run-real", "--env-file", str(env)]) == 2
    output = capsys.readouterr().out
    assert "synthetic-never-print" not in output
    assert '"database_writes": 0' in output


@pytest.mark.asyncio
async def test_only_explicit_models_endpoint_parameters_and_twelve_requests_are_allowed():
    transport = BailianPocTransport(ENDPOINT, inner=httpx.MockTransport(
        lambda _: httpx.Response(200, json={"choices": [], "model": MODELS[0]})))
    body = {"model": MODELS[0], "messages": [{"role": "user", "content": "synthetic"}],
            "enable_thinking": False, "stream": False, "max_tokens": 4096}
    for change in ({"model": "other-model"}, {"enable_thinking": True}, {"stream": True},
                   {"max_tokens": 8192}, {"tools": []}):
        with pytest.raises(RuntimeError):
            await transport.handle_async_request(httpx.Request("POST", ENDPOINT, json={**body, **change}))
    with pytest.raises(RuntimeError):
        await transport.handle_async_request(httpx.Request("POST", "https://other.test/chat/completions", json=body))
    for _ in range(12):
        await transport.handle_async_request(httpx.Request("POST", ENDPOINT, json=body))
    with pytest.raises(RuntimeError):
        await transport.handle_async_request(httpx.Request("POST", ENDPOINT, json=body))
    assert len(transport.requests) == 12


@pytest.mark.parametrize("endpoint", ["http://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
    "https://other.test/compatible-mode/v1/chat/completions", ENDPOINT + "?key=secret"])
def test_non_bailian_or_ambiguous_endpoint_rejected(endpoint):
    with pytest.raises(ValueError):
        BailianPocTransport(endpoint)
