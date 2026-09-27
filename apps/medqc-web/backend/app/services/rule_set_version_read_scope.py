"""规则集版本读取侧范围（V3.6 P1-E1c，规则集版本发布合同第 8 节）。

职责边界：只回答读取侧的三个问题，不判定规则状态、不重写结果：

- ``read_rule_set_versions``：读取入口按哪些规则集版本选择 job/Envelope。默认取
  ``rule_set_version_service.known_versions``（唯一 owner），显式传入版本时只用该版本（兼容旧参数）。
- ``excluded_rule_ids_for_job``：某个 job 的客户排除条目。带 ``rule_set_content_digest`` 的
  新 job 以 filters 冻结的 ``excluded_customer_rule_ids`` 为准；历史 job 沿用静态客户排除名单。
- ``job_rule_set_version``：展示用版本号，取所选 job 的 filters（兼容 summary 回退）。

被版本暂停的规则由 worker 投影为 not_executed 并原样写入结果，读取侧不再重新判定。
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from .luxian_0609.record_result_read_model import _rule_set_value
from .luxian_0609_result_schema import RULE_SET_VERSION
from .luxian_0609_rule_catalog import LUXIAN_0609_RULE_SET_KEY
from .rule_set_version_service import current_version, known_versions, resolve_rule_set_version
from .sample_validation_rule_sets import LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS


def _clean(value: Any) -> str:
    return str(value or "").strip()


def read_rule_set_versions(
    rule_set_key: Any, rule_set_version: Optional[str] = None,
) -> frozenset[str]:
    """读取侧候选版本集合。

    - 显式传入 ``rule_set_version``：只用该版本（空串得到空集合，由调用方按原语义报参数错误）；
    - 未传入且为 LX0609：已知版本集合（内置 + published/retired），同一请求只调用一次；
    - 未传入且为其他规则集：保持旧默认值（静态 ``RULE_SET_VERSION``），兼容路径不变。
    """
    if rule_set_version is not None:
        explicit = _clean(rule_set_version)
        return frozenset({explicit}) if explicit else frozenset()
    if _clean(rule_set_key) == LUXIAN_0609_RULE_SET_KEY:
        return known_versions(LUXIAN_0609_RULE_SET_KEY)
    return frozenset({RULE_SET_VERSION})


def _job_filters(job_or_filters: Any) -> Mapping[str, Any]:
    if not isinstance(job_or_filters, Mapping):
        return {}
    filters = job_or_filters.get("filters")
    if isinstance(filters, Mapping):
        return filters
    return job_or_filters


def excluded_rule_ids_for_job(job_or_filters: Any) -> frozenset[str]:
    """job（或其 filters）的客户排除条目；所有读取侧投影点只调用本函数。"""
    filters = _job_filters(job_or_filters)
    if _clean(filters.get("rule_set_content_digest")):
        return frozenset(
            _clean(rule_id).upper()
            for rule_id in list(filters.get("excluded_customer_rule_ids") or [])
            if _clean(rule_id)
        )
    return LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS


def job_rule_set_version(job: Mapping[str, Any]) -> str:
    """所选 job 的规则集版本（filters 优先，兼容已聚合父任务的 summary）。"""
    return _rule_set_value(job, "rule_set_version")


def current_excluded_rule_ids(rule_set_key: Any) -> frozenset[str]:
    """规则目录展示用：当前版本的客户排除条目（表为空时即静态客户排除名单）。"""
    resolution = resolve_rule_set_version(rule_set_key, current_version(rule_set_key))
    return frozenset(_clean(rule_id).upper() for rule_id in resolution["excluded_rule_ids"])
