"""仅恢复原失败配对；离线重放和正式保存共用的范围与成功结果保护。"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Mapping

from .failed_rule_retry import build_failed_rule_retry_scope, merge_failed_rule_retry_results


def result_key(row: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(str(row.get(key) or "").strip() for key in ("institute_id", "patient_id", "visit_id")) + (str(row.get("rule_id") or row.get("rule_code") or "").upper(),)


def content_digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def validate_material_recovery_gate(material, cases, failures, *, now=None):
    """恢复只接受本次同范围实时源验收，失败病例的输血和医嘱四张表均须通过。"""
    captured = datetime.fromisoformat(material.get("captured_at_utc") or "")
    age = ((now or datetime.now(timezone.utc)) - captured).total_seconds()
    if material.get("source_mode") != "live_readonly" or material.get("error_phase") or not 0 <= age <= 1800:
        raise ValueError("fresh_live_material_acceptance_required")
    if len(cases) != 27 or len({tuple(case[key] for key in ("institute_id", "patient_id", "visit_id")) for case in cases}) != 27 or content_digest(cases) != material.get("scope_digest"):
        raise ValueError("material_acceptance_scope_changed")
    aliases = {tuple(case[key] for key in ("institute_id", "patient_id", "visit_id")): case["sample"] for case in cases}
    allowed = {("C15", "LX0609-07-04-01"), ("C18", "LX0609-07-01-02")}
    required = {"bloodtrans_record", "blood_application", "inpat_drug_order", "inpat_nondrug_order"}
    for failure in failures:
        alias = aliases.get(result_key(failure)[:3])
        if (alias, result_key(failure)[3]) not in allowed:
            raise ValueError("failed_case_outside_p0_scope")
        relevant = [check for check in material["checks"] if check["sample"] == alias and check["category"] in {"transfusion", "orders"}]
        if len(relevant) != 4 or {check["table"] for check in relevant} != required or not all(check["passed"] for check in relevant):
            raise ValueError("failed_case_material_chain_not_verified")


def validate_recovery_merge(baseline: Mapping[str, Any], *, items, failures) -> set[tuple[str, ...]]:
    """已有成功结果逐项原样保留，只允许追加原失败配对的可交付结论。"""
    old_items = json.loads(baseline.get("items_json") or "[]")
    old_failures = json.loads(baseline.get("failed_records_json") or "[]")
    if baseline.get("status") != "failed" or baseline.get("parent_job_id") or baseline.get("job_kind") == "parent" or not old_failures:
        raise ValueError("recovery_requires_failed_leaf_root")
    if list(items[:len(old_items)]) != old_items:
        raise ValueError("successful_results_changed")
    keys = [result_key(item) for item in items]
    if any(not all(key) for key in keys) or len(keys) != len(set(keys)):
        raise ValueError("duplicate_or_incomplete_result_identity")
    added = list(items[len(old_items):])
    if not added or any(item.get("status") not in {"compliant", "non_compliant", "data_gap", "not_applicable"} for item in added):
        raise ValueError("recovery_requires_deliverable_new_results")
    merged, remaining = merge_failed_rule_retry_results(base_items=old_items, base_failures=old_failures,
        retry_items=added, retry_failures=[])
    if merged != list(items) or remaining != list(failures):
        raise ValueError("recovery_scope_or_remaining_failures_changed")
    return {result_key(item)[:3] for item in added}


def replay_response(recordings, prompt):
    matches = [row for row in recordings if row.get("prompt") == prompt and isinstance(row.get("response"), dict)]
    if len(matches) != 1:
        raise ValueError("recorded_prompt_not_uniquely_matched")
    response = deepcopy(matches[0]["response"])
    # 复用旧应答没有新的模型费用，不将旧 token 再累计到原任务。
    response["usage"] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    return response


class ReadonlyRetryWorkspace:
    """真实 Worker 的进程内预演适配器；只有读操作委托真实 workspace。"""

    def __init__(self, workspace, job, *, replay_runtime=None):
        scope = build_failed_rule_retry_scope(job)
        if scope is None:
            raise ValueError("job_has_no_failed_pairs")
        self.owner = workspace
        self.current = deepcopy(job)
        self.runtime_transition = None
        if replay_runtime is not None:
            from ..luxian_0609.rule_decision_settings import LX0609_TASK_RUNTIME_FILTER_KEY
            original = self.current["filters"].get(LX0609_TASK_RUNTIME_FILTER_KEY)
            if (not isinstance(original, dict) or set(original) != set(replay_runtime)
                    or any(original.get(key) != replay_runtime.get(key) for key in ("schema_version", "first_pass", "adjudicator"))):
                raise ValueError("offline_recovery_model_configuration_changed")
            # 只允许显式离线工具在进程内重绑定实现版本；原任务filters及模型配置不写回。
            self.runtime_transition = {"original_implementation": original["implementation"],
                                       "replay_implementation": replay_runtime["implementation"],
                                       "model_identity_preserved": True}
            self.current["filters"][LX0609_TASK_RUNTIME_FILTER_KEY] = deepcopy(replay_runtime)
        self.current["filters"]["failed_rule_retry"] = scope[0]
        self.current["status"] = "queued"
        self.completion = None
        self.failure = None

    def get_batch_job_for_processing(self, **kwargs):
        return deepcopy(self.current)

    def mark_batch_job_running(self, **kwargs):
        self.current["status"] = "running"
        return True

    def collect_records(self, **kwargs):
        return self.owner.collect_records(**kwargs)

    def hydrate_records_with_medical_text(self, records):
        return self.owner.hydrate_records_with_medical_text(records)

    def update_batch_job_progress(self, **kwargs):
        return None

    def is_batch_job_canceled_or_missing(self, **kwargs):
        return False

    def complete_batch_job(self, **kwargs):
        if self.completion is not None:
            raise ValueError("duplicate_recovery_completion")
        self.completion = deepcopy(kwargs)
        return True

    def fail_batch_job(self, **kwargs):
        self.failure = {"stage": "worker_failed", "private_reason": kwargs.get("error_message")}

    def retry_batch_job(self, **kwargs):
        # 禁止自动重试再发起执行；缺应答时保留原任务，不构造新队列。
        return None
