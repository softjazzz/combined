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


def load_identity_namespace():
    load_pure_privacy()
    name = PACKAGE + ".case_identity"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, SERVICES / "case_identity.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    path = SERVICES / "luxian_0609/privacy_identity_context.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    tree.body = [node for node in tree.body if not isinstance(node, ast.ImportFrom) or node.level == 0]
    namespace = {
        "CaseRef": sys.modules[name].CaseRef,
        "Luxian0609EvidenceMaterialStore": type("Materials", (), {}),
        "Luxian0609EvidenceSnapshot": type("Snapshot", (), {}),
    }
    exec(compile(tree, str(path), "exec"), namespace)
    return namespace


def load_provider():
    return load_identity_namespace()["build_luxian_0609_identity_provider"]


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


def load_repository_methods():
    from datetime import date, datetime
    identity = load_identity_namespace()
    case_module = sys.modules[PACKAGE + ".case_identity"]
    path = SERVICES / "qc_workspace/record_repository.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in {
        "_safe_text", "_as_date", "_to_iso_date", "_to_iso_datetime", "_normalize_scope", "_normalize_date_field", "_record_dates_match_range", "_capture_private_orm_identities",
    }]
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "RecordRepository")
    cls.body = [node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name in {
        "collect_records", "_serialize_record_row", "_collect_explicit_anchor_records", "_collect_explicit_anchor_records_by_refs",
    }]
    class Column:
        def __eq__(self, other):
            return True
        def in_(self, other):
            return True
    def model(name):
        return type(name, (), {key: Column() for key in ("institute_id", "patient_id", "visit_id", "admission_datetime", "discharge_datetime")})
    namespace = {
        "CaseRef": identity["CaseRef"], "normalize_case_refs": case_module.normalize_case_refs,
        "date": date, "datetime": datetime, "desc": lambda value: value,
        "and_": lambda *values: values, "or_": lambda *values: values,
        "MedicalRecordFrontpage": model("MedicalRecordFrontpage"), "InpatRegistration": model("InpatRegistration"),
        "AdmissionRecord": model("AdmissionRecord"), "DischargeRecord": model("DischargeRecord"),
    }
    exec(compile(ast.fix_missing_locations(ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), *functions, cls], type_ignores=[])), str(path), "exec"), namespace)
    return namespace["RecordRepository"], namespace


def load_worker_case_wrapper(*, collector, impl, source_text=None):
    from contextlib import nullcontext
    from datetime import datetime, timezone
    import time
    _, scope = load_pure_privacy()
    path = SERVICES / "sichuan_workspace_batch_worker.py"
    tree = ast.parse(source_text if source_text is not None else path.read_text(encoding="utf-8"))
    function = next(node for node in ast.walk(tree) if isinstance(node, ast.AsyncFunctionDef) and node.name == "_evaluate_single_record")
    identity = load_identity_namespace()
    namespace = {
        "CaseRef": identity["CaseRef"], "nullcontext": nullcontext,
        "datetime": datetime, "timezone": timezone, "time": time,
        "identity_collector": collector, "luxian_0609_case_identity_scope": scope.luxian_0609_case_identity_scope,
        "current": {}, "filters": {}, "job_id": "offline", "rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "offline",
        "llm_observation_context": lambda **kwargs: nullcontext(), "diagnostic_capture": None,
        "is_failed_rule_retry": False, "record_timing_attempts": [], "_evaluate_single_record_impl": impl,
    }
    exec(compile(ast.fix_missing_locations(ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), function], type_ignores=[])), str(path), "exec"), namespace)
    return namespace["_evaluate_single_record"]


def load_bundle_runtime(loader):
    path = SERVICES / "qc_input_adapters/running_final_bundle_runtime.py"
    nodes = selected_ast(path, names={"_normalize_scene", "_loads_json", "load_running_final_bundle"})
    import json
    namespace = {"engine": object(), "_SCENE_TABLE": {"running": "running_record_bundle", "final": "final_record_bundle"}, "load_or_assemble_scene_bundle": loader, "json": json}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), *nodes], type_ignores=[])), str(path), "exec"), namespace)
    return namespace["load_running_final_bundle"]


def load_script_namespace(script_name, **overrides):
    """仅AST载入脚本定义；app/scripts导入不执行，所有外部接缝须显式替身。"""
    import argparse
    import asyncio
    from collections import Counter, defaultdict
    from collections.abc import Mapping, Sequence
    from dataclasses import dataclass, field
    from datetime import datetime, timezone
    import json
    import re
    from time import perf_counter
    from typing import Any, Callable

    path = BACKEND / "scripts" / script_name
    tree = ast.parse(path.read_text(encoding="utf-8"))
    tree.body = [node for node in tree.body if isinstance(node, (
        ast.Assign, ast.AnnAssign, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
    ))]
    tree.body.insert(0, ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0))
    privacy, scope = load_pure_privacy()
    identities = load_identity_namespace()
    namespace = dict(
        __name__=PACKAGE + ".script", __file__=str(path), Path=Path,
        Any=Any, Callable=Callable, Mapping=Mapping, Sequence=Sequence,
        dataclass=dataclass, field=field, datetime=datetime, timezone=timezone,
        Counter=Counter, defaultdict=defaultdict, argparse=argparse, asyncio=asyncio,
        json=json, re=re, sys=sys, perf_counter=perf_counter,
        read_luxian_0609_native_source_rows=lambda **kwargs: [],
        CaseRef=identities["CaseRef"],
        _Luxian0609IdentityCollector=identities["_Luxian0609IdentityCollector"],
        PrivacyIdentityContextUnavailable=identities["PrivacyIdentityContextUnavailable"],
        build_luxian_0609_identity_provider=identities["build_luxian_0609_identity_provider"],
        bind_luxian_0609_identity_provider=scope.bind_luxian_0609_identity_provider,
        luxian_0609_case_identity_scope=scope.luxian_0609_case_identity_scope,
        PrivacyIdentityContextError=scope.PrivacyIdentityContextError,
        wrap_luxian_0609_llm_client=privacy.wrap_luxian_0609_llm_client,
        PatientPrivacyViolation=privacy.PatientPrivacyViolation,
        protect_current_payload=scope.protect_current_payload,
    )
    namespace.update(overrides)
    module_name = PACKAGE + ".script_" + path.stem
    module = ModuleType(module_name)
    module.__dict__.update(namespace, __name__=module_name)
    sys.modules[module_name] = module
    namespace = module.__dict__
    exec(compile(ast.fix_missing_locations(tree), str(path), "exec"), namespace)
    return namespace


def load_pure_function_seams(relative, names, **overrides):
    """递归选取当前源码的纯文本函数/常量依赖，不执行模块导入。"""
    from collections.abc import Mapping, Sequence
    import re
    from typing import Any
    path = BACKEND / relative
    tree = ast.parse(path.read_text(encoding="utf-8"))
    definitions = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            definitions[node.name] = node
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    definitions[target.id] = node
    wanted = set(names)
    pending = set(names)
    while pending:
        key = pending.pop()
        if key not in definitions:
            continue
        for child in ast.walk(definitions[key]):
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load) and child.id in definitions and child.id not in wanted:
                wanted.add(child.id)
                pending.add(child.id)
    nodes = [node for node in tree.body if any(node is definitions.get(key) for key in wanted)]
    namespace = dict(Any=Any, Mapping=Mapping, Sequence=Sequence, re=re)
    namespace.update(overrides)
    nodes.insert(0, ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0))
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), str(path), "exec"), namespace)
    return namespace


def load_semantic_legacy_tests():
    """原10业务测试函数/断言原样AST执行，跳过app/config/DB导入。"""
    from collections import Counter
    from difflib import SequenceMatcher
    from hashlib import sha256
    import json
    import pytest
    import re
    common = load_pure_function_seams(
        "app/services/luxian_0609/course_quality/shared.py",
        {"row_text", "DATE_PATTERN", "TIME_PATTERN"},
    )
    copy = load_pure_function_seams(
        "app/services/luxian_0609/course_quality/rules_016_017.py",
        {"_normalized_for_similarity"}, _DATE_PATTERN=common["DATE_PATTERN"], _TIME_PATTERN=common["TIME_PATTERN"],
    )
    context = load_pure_function_seams(
        "app/services/luxian_0609/native_consultation_execution.py", {"_context"},
    )
    semantic = load_script_namespace(
        "review_luxian_0609_semantic20.py", consultation_context=context["_context"],
        _normalized_for_similarity=copy["_normalized_for_similarity"], _row_text=common["row_text"],
        _COPY_MAX_CONTEXT_CHARS=18000, _COPY_MAX_ROW_CHARS=1400,
        SequenceMatcher=SequenceMatcher, sha256=sha256, Counter=Counter,
    )
    module_name = PACKAGE + ".published_rule_master"
    spec = importlib.util.spec_from_file_location(module_name, SERVICES / "luxian_0609_rule_master.py")
    master = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = master
    spec.loader.exec_module(master)
    def published_rule_ids(start, end):
        return tuple(entry.rule_id for entry in master.load_luxian_0609_rule_master())[start - 1:end]
    path = BACKEND / "tests/unit/test_luxian_0609_semantic20_review.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    tree.body = [node for node in tree.body if not isinstance(node, (ast.Import, ast.ImportFrom))]
    tree.body.insert(0, ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0))
    namespace = dict(
        __file__=str(path), Path=Path, json=json, re=re, pytest=pytest, SimpleNamespace=SimpleNamespace,
        published_rule_ids=published_rule_ids, build_semantic20_review=semantic["build_semantic20_review"],
        SemanticReviewContractError=semantic["SemanticReviewContractError"],
        _Luxian0609IdentityCollector=semantic["_Luxian0609IdentityCollector"],
    )
    exec(compile(ast.fix_missing_locations(tree), str(path), "exec"), namespace)
    return namespace
