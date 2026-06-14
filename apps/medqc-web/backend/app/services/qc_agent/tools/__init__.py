from __future__ import annotations

# 兼容入口：外部仍从 app.services.qc_agent.tools 导入工具。
# 领域模块逐步从 _legacy.py 下沉，避免一次性重构破坏现有行为。
from typing import Any

from . import _legacy
from ._legacy import (  # noqa: F401
    assert_no_sensitive_output,
    contains_sensitive_keys,
    create_default_registry,
    list_qc_rules,
    predict_dip_group,
    predict_drg_group,
    register_default_tools,
    resolve_rule_scope,
    search_icd_codes,
    search_records,
)

_read_cdm_detail_documents = _legacy._read_cdm_detail_documents


def _sync_patchable_internals() -> None:
    # 兼容旧测试和外部调试脚本对 app.services.qc_agent.tools 内部函数的 monkeypatch。
    _legacy._read_cdm_detail_documents = globals().get("_read_cdm_detail_documents", _legacy._read_cdm_detail_documents)


def get_record_context(*args: Any, **kwargs: Any):
    _sync_patchable_internals()
    return _legacy.get_record_context(*args, **kwargs)


def run_frontpage_qc(*args: Any, **kwargs: Any):
    _sync_patchable_internals()
    return _legacy.run_frontpage_qc(*args, **kwargs)


def select_record_documents(*args: Any, **kwargs: Any):
    _sync_patchable_internals()
    return _legacy.select_record_documents(*args, **kwargs)


def run_document_qc(*args: Any, **kwargs: Any):
    _sync_patchable_internals()
    return _legacy.run_document_qc(*args, **kwargs)


def suggest_record_icd_codes(*args: Any, **kwargs: Any):
    _sync_patchable_internals()
    return _legacy.suggest_record_icd_codes(*args, **kwargs)
