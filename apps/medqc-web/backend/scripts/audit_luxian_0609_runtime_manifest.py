"""只读审计 LX0609 当前规则路由、执行合同与阶段口径。"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.settings import get_settings  # noqa: E402
from app.services.luxian_0609.phase_scope import (  # noqa: E402
    load_luxian_0609_phase_scope,
)
from app.services.luxian_0609.rule_contracts import (  # noqa: E402
    load_luxian_0609_rule_contracts,
)
from app.services.luxian_0609_rule_catalog import load_luxian_0609_rules  # noqa: E402
from app.services.sample_validation_rule_sets import (  # noqa: E402
    get_luxian_0609_customer_delivery_rule_ids,
    get_luxian_0609_customer_execution_scope,
)
from scripts.build_luxian_0609_runtime_manifest import (  # noqa: E402
    build_runtime_manifest,
    current_git_head,
)


SCHEMA_VERSION = "lx0609-engine-convergence-audit-v1"


def _ordered_ids(items: Iterable[Any]) -> tuple[str, ...]:
    return tuple(str(getattr(item, "rule_id", "") or "").strip().upper() for item in items)


def build_runtime_audit(
    *,
    runtime_manifest: Mapping[str, Any],
    contracts: Iterable[Any],
    phase_scope: Iterable[Any],
    approved_formal_target: int | None = None,
    approved_temporary_target: int | None = None,
) -> dict[str, Any]:
    """合并现有权威清单；只报告漂移，不推断或修改医学口径。"""

    manifest_rules = tuple(runtime_manifest.get("rules") or ())
    manifest_ids = tuple(
        str(item.get("rule_id") or "").strip().upper()
        for item in manifest_rules
        if isinstance(item, Mapping)
    )
    contract_items = tuple(contracts)
    # 规则总表保留、但已从规则目录撤下的待定义规则（如 2026-09-22 撤下的 06-03-01）
    # 不进入运行清单；单独列出，不视为漂移。其他不一致仍拒绝。
    manifest_id_set = set(manifest_ids)
    withdrawn_pending_ids = [
        str(getattr(item, "rule_id", "") or "").strip().upper()
        for item in phase_scope
        if str(getattr(item, "rule_id", "") or "").strip().upper() not in manifest_id_set
        and getattr(item, "phase_status", "") == "pending_definition"
    ]
    scope_items = tuple(
        item for item in phase_scope
        if str(getattr(item, "rule_id", "") or "").strip().upper() not in set(withdrawn_pending_ids)
    )
    contract_ids = _ordered_ids(contract_items)
    scope_ids = _ordered_ids(scope_items)
    if not manifest_ids or contract_ids != manifest_ids:
        raise ValueError("LX0609 runtime audit contract ids do not match manifest")
    if scope_ids != manifest_ids:
        raise ValueError("LX0609 runtime audit phase scope ids do not match manifest")
    if approved_formal_target is None:
        approved_formal_target = sum(
            getattr(item, "phase_status", "")
            in {"phase_1_target", "phase_1_partial"}
            for item in scope_items
        )
    if approved_temporary_target is None:
        approved_temporary_target = sum(
            getattr(item, "phase_status", "") == "pending_definition"
            for item in scope_items
        )
    if approved_formal_target < 0 or approved_temporary_target < 0:
        raise ValueError("LX0609 approved definition targets must be non-negative")
    if approved_formal_target + approved_temporary_target != len(manifest_ids):
        raise ValueError("LX0609 approved definition targets must cover the manifest")

    delivery_ids = tuple(
        str(item or "").strip().upper()
        for item in runtime_manifest.get("customer_delivery_rule_ids") or ()
    )
    executable_ids = tuple(
        str(item or "").strip().upper()
        for item in runtime_manifest.get("executable_rule_ids") or ()
    )
    withheld_ids = tuple(
        str(item or "").strip().upper()
        for item in runtime_manifest.get("withheld_rule_ids") or ()
    )
    scope_fields_present = any(
        key in runtime_manifest
        for key in (
            "customer_delivery_count",
            "executable_count",
            "withheld_count",
            "customer_delivery_rule_ids",
            "executable_rule_ids",
            "withheld_rule_ids",
        )
    )
    if scope_fields_present:
        if (
            runtime_manifest.get("customer_delivery_count") != len(delivery_ids)
            or runtime_manifest.get("executable_count") != len(executable_ids)
            or runtime_manifest.get("withheld_count") != len(withheld_ids)
            or len(delivery_ids) != len(set(delivery_ids))
            or len(executable_ids) != len(set(executable_ids))
            or len(withheld_ids) != len(set(withheld_ids))
            or set(executable_ids) | set(withheld_ids) != set(delivery_ids)
            or set(executable_ids) & set(withheld_ids)
            or not set(delivery_ids).issubset(set(manifest_ids))
        ):
            raise ValueError("invalid LX0609 customer scope partition")
    if scope_fields_present:
        expected_delivery = tuple(get_luxian_0609_customer_delivery_rule_ids())
        expected_executable, expected_withheld = get_luxian_0609_customer_execution_scope()
        if (
            delivery_ids != expected_delivery
            or executable_ids != expected_executable
            or withheld_ids != expected_withheld
        ):
            raise ValueError("LX0609 runtime audit customer scope drift")

    contract_by_id = {item.rule_id: item for item in contract_items}
    scope_by_id = {item.rule_id: item for item in scope_items}
    executor_counts = Counter(str(item.get("executor_key") or "") for item in manifest_rules)
    execution_mode_counts = Counter(
        str(item.get("dependency_mode") or "") for item in manifest_rules
    )
    active_path_counts = Counter(str(item.get("active_path") or "") for item in manifest_rules)
    phase_scope_counts = Counter(item.phase_status for item in scope_items)
    decision_authority_counts = Counter(
        item.decision_authority for item in contract_items
    )
    golden_gate_counts = Counter(item.golden_gate_state for item in contract_items)
    current_formal = phase_scope_counts.get("phase_1_target", 0)
    current_temporary = phase_scope_counts.get("pending_definition", 0)
    partial_rules = phase_scope_counts.get("phase_1_partial", 0)
    reconciled = (
        current_formal == approved_formal_target
        and current_temporary == approved_temporary_target
        and partial_rules == 0
    )

    rules: list[dict[str, Any]] = []
    for manifest_rule in manifest_rules:
        rule_id = str(manifest_rule.get("rule_id") or "").strip().upper()
        contract = contract_by_id[rule_id]
        scope = scope_by_id[rule_id]
        rules.append(
            {
                **dict(manifest_rule),
                "contract_version": contract.contract_version,
                "decision_authority": contract.decision_authority,
                "data_dependencies": list(contract.data_dependencies),
                "phase_status": scope.phase_status,
                "definition_version": scope.definition_version,
                "active_criteria": list(scope.active_criteria),
                "pending_criteria": list(scope.pending_criteria),
                "pending_reason_code": scope.pending_reason_code,
            }
        )

    result = {
        "schema_version": SCHEMA_VERSION,
        "runtime_manifest_schema_version": runtime_manifest.get("schema_version"),
        "git_head": runtime_manifest.get("git_head"),
        "rule_count": len(manifest_ids),
        "executor_counts": dict(sorted(executor_counts.items())),
        "execution_mode_counts": dict(sorted(execution_mode_counts.items())),
        "active_path_counts": dict(sorted(active_path_counts.items())),
        "phase_scope_counts": dict(sorted(phase_scope_counts.items())),
        "decision_authority_counts": dict(sorted(decision_authority_counts.items())),
        "golden_gate_counts": dict(sorted(golden_gate_counts.items())),
        "approved_definition_target": {
            "formal": approved_formal_target,
            "temporary": approved_temporary_target,
        },
        "definition_target_reconciled": reconciled,
        "catalog_withdrawn_pending_rule_ids": withdrawn_pending_ids,
        "definition_target_gap": {
            "formal_missing": max(approved_formal_target - current_formal, 0),
            "temporary_unassigned": max(current_temporary - approved_temporary_target, 0),
            "partial_rules": partial_rules,
        },
        "rules": rules,
    }
    if scope_fields_present:
        result.update(
            {
                "customer_delivery_count": len(delivery_ids),
                "executable_count": len(executable_ids),
                "withheld_count": len(withheld_ids),
                "customer_delivery_rule_ids": list(delivery_ids),
                "executable_rule_ids": list(executable_ids),
                "withheld_rule_ids": list(withheld_ids),
            }
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="只读审计 LX0609 当前规则运行清单")
    parser.add_argument("--output", type=Path, help="输出JSON文件；省略时打印到stdout")
    parser.add_argument("--git-head", help="显式指定当前Git提交，供受限环境审计")
    args = parser.parse_args()
    manifest = build_runtime_manifest(
        git_head=str(args.git_head or current_git_head()),
        settings=get_settings(),
        rule_catalog=load_luxian_0609_rules(),
    )
    audit = build_runtime_audit(
        runtime_manifest=manifest,
        contracts=load_luxian_0609_rule_contracts(),
        phase_scope=load_luxian_0609_phase_scope(),
    )
    content = json.dumps(audit, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8", newline="\n")
    else:
        print(content, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
