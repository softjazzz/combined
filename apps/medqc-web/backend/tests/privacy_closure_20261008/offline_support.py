"""只加载当前纯隐私模块/指定AST接缝；不导入app启动、配置、PG或患者材料。"""
from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock

BACKEND = Path(__file__).resolve().parents[2]
SERVICES = BACKEND / "app/services"
PACKAGE = "_privacy_closure_offline.services"


def load_pure_privacy():
    for name in ("_privacy_closure_offline", PACKAGE, PACKAGE + ".luxian_0609"):
        if name not in sys.modules:
            module = ModuleType(name)
            module.__path__ = []
            sys.modules[name] = module
    modules = []
    for short in ("llm_prompt_privacy", "privacy_request_scope"):
        name = PACKAGE + ".luxian_0609." + short
        if name not in sys.modules:
            spec = importlib.util.spec_from_file_location(name, SERVICES / "luxian_0609" / (short + ".py"))
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
        modules.append(sys.modules[name])
    return tuple(modules)


def selected_ast(path, *, names):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name in names]


def load_client_methods(scope):
    path = SERVICES / "qc_llm_client.py"
    cls = selected_ast(path, names={"SichuanQCLLMClient"})[0]
    cls.body = [node for node in cls.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in {
        "_summarize_upstream_body", "_raise_for_upstream_error", "_endpoint_host", "_perform_observed_attempt",
    }]
    namespace = {"__name__": PACKAGE + ".client", "__package__": PACKAGE}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), cls], type_ignores=[])), str(path), "exec"), namespace)
    return namespace["SichuanQCLLMClient"], namespace


def client_with_counters(scope):
    cls, namespace = load_client_methods(scope)
    events = []
    async def transport(**kwargs):
        events.append(("transport", kwargs["payload"]))
        return {"choices": [], "usage": {"total_tokens": 0}}
    async def start(**kwargs):
        events.append(("observation", kwargs["attempt_no"]))
        return None, 0
    def capture(**kwargs):
        events.append(("capture", kwargs["payload"]))
    namespace.update(
        safe_post_json=transport, begin_diagnostic_attempt=capture,
        finish_diagnostic_attempt=lambda *args, **kwargs: None,
        observed_usage=lambda result: None,
        safe_status_for_http_result=lambda result: ("success", None),
        safe_status_for_exception=lambda error: ("error", "safe_error"),
    )
    client = object.__new__(cls)
    client.provider_code = "synthetic"
    client.model = "synthetic"
    client.model_role = "first_pass"
    client.api_endpoint = "https://offline.invalid"
    client.timeout_seconds = 1
    client._observability_recorder = SimpleNamespace(start_attempt=start, finish_attempt=AsyncMock())
    return client, events


def load_provider():
    path = SERVICES / "luxian_0609/privacy_identity_context.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    tree.body = [node for node in tree.body if not isinstance(node, ast.ImportFrom) or node.level == 0]
    namespace = {"Luxian0609EvidenceMaterialStore": type("Materials", (), {}), "Luxian0609EvidenceSnapshot": type("Snapshot", (), {})}
    exec(compile(tree, str(path), "exec"), namespace)
    return namespace["build_luxian_0609_identity_provider"]


def bind_execution_source(*, scope, privacy, kwargs):
    path = SERVICES / "luxian_0609/execution.py"
    function = selected_ast(path, names={"prepare_luxian_0609_execution"})[0]
    nodes = []
    for node in function.body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "identity_provider" for target in node.targets):
            nodes.append(node)
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == "bind_luxian_0609_identity_provider":
            nodes.append(node)
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == "wrap_luxian_0609_llm_client":
            nodes.append(node)
    assert len(nodes) == 3
    namespace = dict(kwargs, evidence_snapshot=None, evidence_materials=None, evidence_snapshot_build_failed=False)
    namespace.update(build_luxian_0609_identity_provider=load_provider(), bind_luxian_0609_identity_provider=scope.bind_luxian_0609_identity_provider, wrap_luxian_0609_llm_client=privacy.wrap_luxian_0609_llm_client)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)
    return namespace["llm_client"]


def load_runner(scope, *, prepare):
    # 执行当前runner函数及真实入口装饰器；业务合同/适配/聚合均限定内存替身。
    path = SERVICES / "luxian_0609/preproduction_runner.py"
    function = selected_ast(path, names={"run_luxian_0609_preproduction"})[0]
    adapter_package = ModuleType(PACKAGE + ".qc_input_adapters")
    adapter_package.__path__ = []
    sys.modules[adapter_package.__name__] = adapter_package
    adapter_name = PACKAGE + ".qc_input_adapters.running_final_bundle_adapter"
    adapter = ModuleType(adapter_name)
    adapter.adapt_bundle_to_sichuan_eval_args = lambda bundle, **kwargs: {"content": bundle.get("medical_text", ""), "evidence_payload": {"patient_name": bundle.get("synthetic_name", "")}}
    sys.modules[adapter_name] = adapter
    from collections import Counter
    from time import perf_counter
    from typing import Mapping
    metrics = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    namespace = {
        "__package__": PACKAGE + ".luxian_0609", "luxian_0609_case_privacy_scope": scope.luxian_0609_case_privacy_scope,
        "Mapping": Mapping, "Counter": Counter, "perf_counter": perf_counter,
        "_validate_selected_rule_ids": tuple, "_validate_evaluation_as_of_date": lambda value: value,
        "_collect_private_terms": lambda value: set(), "build_full_rule_decision_settings": lambda value, **kwargs: value,
        "_observed_usage_metrics": lambda *args: dict(metrics), "LUXIAN_0609_RULE_SET_KEY": "luxian_0609_qc_v1",
        "prepare_luxian_0609_execution": prepare,
        "aggregate_luxian_0609_orchestrated_results": lambda **kwargs: kwargs["orchestrated"].update(results=[{"rule_id": "LX0609-04-01-04", "status": "compliant"}]),
        "_validate_usage_accounting": lambda **kwargs: (), "_validate_result_scope": lambda *args, **kwargs: None,
        "_sanitize_customer_result": lambda value, **kwargs: value,
        "_technical_results": lambda selected, **kwargs: [{"rule_id": rule, "status": "technical_error"} for rule in selected],
        "_UsageAccountingError": type("UsageAccountingError", (ValueError,), {}),
        "_contract_maturity": lambda: {}, "PREPRODUCTION_RUNNER_SCHEMA_VERSION": "offline",
    }
    exec(compile(ast.fix_missing_locations(ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), function], type_ignores=[])), str(path), "exec"), namespace)
    return namespace["run_luxian_0609_preproduction"]
