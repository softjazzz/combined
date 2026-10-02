"""验收对照的只读比较：客户安全结果及任务级资源统计，不参与医学判定。"""
from math import isfinite

from .case_identity import CaseRef

RESULT_FIELDS = (
    "status", "reason_code", "customer_display_facts", "criterion_results", "findings", "evidence",
    "customer_conclusion", "conclusion", "customer_suggestion", "suggestion",
)


def _number(value):
    return value if type(value) in (int, float) and isfinite(value) and value >= 0 else None


def _metrics(job):
    profile = ((job or {}).get("summary") or {}).get("performance_profile") or {}
    return {
        "llm_calls": _number(profile.get("llm_call_count"))
        if profile.get("llm_call_count_basis") == "record_execution_attribution" else None,
        "tokens": _number(profile.get("tokens_total")),
        "elapsed_seconds": _number(profile.get("wall_clock_time_seconds")),
    }


def _scope(job):
    rules = sorted(set(((job or {}).get("filters") or {}).get("scoped_customer_rule_ids") or []))
    records = {CaseRef.from_mapping(item) for item in (job or {}).get("items") or []}
    return rules, records


def compare_metrics(current, baseline):
    """共享抽取只展示整任务观测，不把参与次数或分摊数声称为单规则模型成本。"""
    before, after = _metrics(baseline), _metrics(current)
    old_rules, old_records = _scope(baseline)
    new_rules, new_records = _scope(current)
    if any(v is None for v in (*before.values(), *after.values())):
        reason = "任务调用量、Token或耗时统计不完整；未记录不等于零"
    elif not old_rules or not new_rules or not old_records or not new_records:
        reason = "任务范围未记录，不能直接比较"
    elif old_rules != new_rules or old_records != new_records:
        reason = "新旧任务的规则或病例范围不同，仅并列展示，不计算成本增减"
    else:
        reason = "同规则范围、同病例集合的整任务观测；耗时含调度开销，不代表单规则耗时"
    comparable = (bool(old_rules and old_records) and old_rules == new_rules and old_records == new_records
                  and all(v is not None for v in (*before.values(), *after.values())))
    return {"basis": "whole_job", "baseline": before, "current": after,
            "baseline_scope": {"rule_ids": old_rules, "record_count": len(old_records)},
            "current_scope": {"rule_ids": new_rules, "record_count": len(new_records)},
            "comparable": comparable, "reason": reason,
            "delta": {k: round(after[k] - before[k], 4) for k in after} if comparable else None}


def compare_regression(case, actual, current_job, baseline_job, project):
    ref = CaseRef.from_mapping(case["record_ref"])
    matches = [item for item in (baseline_job or {}).get("items") or []
               if item.get("rule_id") == case["rule_id"] and CaseRef.from_mapping(item) == ref]
    data = {"baseline_run_id": case.get("baseline_run_id"), "baseline_job_id": case.get("baseline_job_id"),
            "baseline": None, "changed_fields": [], "metrics": compare_metrics(current_job, baseline_job)}
    if ((baseline_job or {}).get("status") != "completed" or len(matches) != 1 or project is None):
        data["status"] = "baseline_missing"
        return data
    # 基线与本次均经同一客户安全投影；不返回内部事实、病例身份、Prompt或响应。
    before = project(matches[0])
    data["baseline"] = {k: before.get(k) for k in RESULT_FIELDS}
    data["changed_fields"] = [k for k in RESULT_FIELDS if before.get(k) != actual.get(k)]
    data["status"] = "different" if data["changed_fields"] else "same"
    return data
