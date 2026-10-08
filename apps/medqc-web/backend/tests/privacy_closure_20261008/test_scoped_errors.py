"""PRIV005合成错误反例；运行时不导入应用/config，不发送网络请求。"""
import ast
import asyncio
import logging

import pytest

from offline_support import SERVICES, load_client_methods, load_pure_privacy, selected_ast


@pytest.mark.parametrize("body", [
    "合成患者甲 sk-test-secret raw-text",
    {"code": "合成患者甲", "message": "合成患者甲", "request_id": "合成患者甲"},
    {"error": {"code": "合成患者甲", "type": "合成患者甲", "message": "合成患者甲"}},
    {"code": [], "error": {"code": {"private": "合成患者甲"}}},
    ["合成患者甲"],
])
def test_scoped_upstream_errors_never_publish_body_or_untrusted_status(body):
    _, scope = load_pure_privacy()
    cls, _ = load_client_methods(scope)
    client = object.__new__(cls)

    @scope.luxian_0609_privacy_scope
    async def run(*, rule_set_key):
        with pytest.raises(RuntimeError) as caught:
            client._raise_for_upstream_error({"__error__": True, "__status__": "合成患者甲", "body": body})
        assert str(caught.value) == "upstream_http_error upstream_http_status=unknown upstream_error_summary=upstream_response_error"
        assert caught.value.__cause__ is None
        assert caught.value.__suppress_context__ is True

    asyncio.run(run(rule_set_key="luxian_0609_qc_v1"))
    assert scope.is_luxian_0609_privacy_scope_active() is False


def test_scoped_error_keeps_whitelisted_category_and_http_status():
    _, scope = load_pure_privacy()
    cls, _ = load_client_methods(scope)
    client = object.__new__(cls)

    @scope.luxian_0609_privacy_scope
    async def run(*, rule_set_key):
        with pytest.raises(RuntimeError) as caught:
            client._raise_for_upstream_error({"__error__": True, "__status__": 400, "body": {"code": "InvalidParameter", "message": "合成患者甲"}})
        assert str(caught.value) == "upstream_http_error upstream_http_status=400 upstream_error_summary=invalid_parameter"
        assert client._raise_for_upstream_error({"choices": []}) is None
    asyncio.run(run(rule_set_key="luxian_0609_qc_v1"))


def test_non0609_error_keeps_existing_compatibility():
    import re
    from urllib.parse import urlparse
    _, scope = load_pure_privacy()
    cls, namespace = load_client_methods(scope)
    namespace.update(re=re, urlparse=urlparse)
    client = object.__new__(cls)
    client.model = "synthetic-model"
    client.provider_code = "synthetic"
    client.api_endpoint = "https://offline.invalid"
    with pytest.raises(RuntimeError) as caught:
        client._raise_for_upstream_error({"__error__": True, "__status__": 400, "body": {"code": "InvalidParameter", "message": "model not found"}})
    assert "model not found" in str(caught.value)
    assert "provider_code=synthetic" in str(caught.value)


def test_snapshot_failure_log_executes_fixed_handler_without_private_exception(caplog):
    function = selected_ast(SERVICES / "luxian_0609/execution.py", names={"prepare_luxian_0609_execution"})[0]
    handler = next(node for node in ast.walk(function) if isinstance(node, ast.ExceptHandler) and any(isinstance(item, ast.Call) and isinstance(item.func, ast.Attribute) and item.func.attr in {"error", "exception"} and item.args and isinstance(item.args[0], ast.Constant) and "evidence snapshot" in str(item.args[0].value) for item in ast.walk(node)))
    namespace = {"logger": logging.getLogger("privacy-closure-snapshot")}
    with caplog.at_level(logging.ERROR):
        try:
            raise RuntimeError("合成患者甲 connection-secret")
        except RuntimeError:
            exec(compile(ast.Module(body=handler.body, type_ignores=[]), "current-snapshot-handler", "exec"), namespace)
    assert len(caplog.records) == 1
    assert caplog.records[0].exc_info is None
    assert caplog.records[0].getMessage() == "LX0609 evidence snapshot 构建失败 error_kind=snapshot_build_error"
    assert "合成患者甲" not in caplog.text and "connection-secret" not in caplog.text
    assert namespace["evidence_snapshot_build_failed"] is True
    assert namespace["evidence_snapshot"] is None
