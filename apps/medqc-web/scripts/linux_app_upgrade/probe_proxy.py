"""仅验证实际.env代理策略与发布身份，不发HTTP或模型请求。"""
import argparse
import json
from pathlib import Path
import sys
import socket

def denied(*args, **kwargs):
    raise RuntimeError("probe_network_denied")
socket.socket.connect = denied
socket.create_connection = denied
socket.getaddrinfo = denied

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.backend))
    from dotenv import dotenv_values
    from app.core.llm_http_proxy import LLMHTTPProxyPolicy
    values = dotenv_values(args.env_file)
    policy = LLMHTTPProxyPolicy.load(values.get("LLM_HTTP_PROXY"), values.get("LLM_HTTP_PROXY_HOSTS"))
    ok = not policy.error_code and policy.url == "http://192.168.118.99:18090" and policy.hosts == frozenset({"dashscope.aliyuncs.com"}) and policy.matches("https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions") and not policy.matches("http://127.0.0.1:18083/v1")
    print(json.dumps({"ok": ok, "configuration_error": policy.error_code,
                      "bailian_route": "proxy" if ok else "not_verified", "network_calls": 0,
                      "model_calls": 0, "connectivity_tested": False}))
    raise SystemExit(0 if ok else 1)
