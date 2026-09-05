"""生成不含敏感配置的 LX0609 当前运行版本清单。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.settings import get_settings  # noqa: E402
from app.services.luxian_0609.native_package import (  # noqa: E402
    Luxian0609RuleDependency,
    build_luxian_0609_package_plan_from_settings,
    load_luxian_0609_dependency_inventory,
)
from app.services.luxian_0609.rule_decision_settings import (  # noqa: E402
    get_rule_decision_rollout_flag,
    resolve_mainline_rule_decision_settings,
)
from app.services.luxian_0609_rule_catalog import load_luxian_0609_rules  # noqa: E402
from app.services.qc_rule_sets import get_sichuan_rule_set  # noqa: E402
from app.services.sample_validation_rule_sets import (  # noqa: E402
    get_luxian_0609_customer_delivery_rule_ids,
    get_luxian_0609_customer_execution_scope,
)


SCHEMA_VERSION = "lx0609-runtime-manifest-v1"
RULE_SET_KEY = "luxian_0609_qc_v1"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_SCOPES = frozenset({"synthetic", "real", "mixed"})

_SAFE_FLAG_FIELDS: tuple[tuple[str, str], ...] = (
    ("trigger_gate", "LUXIAN_0609_TRIGGER_GATE_ENABLED"),
    ("llm_trigger_gate", "LUXIAN_0609_LLM_TRIGGER_GATE_ENABLED"),
    ("customer_aggregation", "LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED"),
    ("evidence_formatter", "LUXIAN_0609_EVIDENCE_FORMATTER_ENABLED"),
    ("native_execution", "LUXIAN_0609_NATIVE_EXECUTION_ENABLED"),
    ("native_basic_timeliness", "LUXIAN_0609_NATIVE_BASIC_TIMELINESS_ENABLED"),
    ("native_consultation", "LUXIAN_0609_NATIVE_CONSULTATION_ENABLED"),
    (
        "consultation_execution_link",
        "LUXIAN_0609_CONSULTATION_EXECUTION_LINK_ENABLED",
    ),
    ("native_exam_lab", "LUXIAN_0609_NATIVE_EXAM_LAB_ENABLED"),
    ("native_transfusion", "LUXIAN_0609_NATIVE_TRANSFUSION_ENABLED"),
    ("native_tumor_pathology", "LUXIAN_0609_NATIVE_TUMOR_PATHOLOGY_ENABLED"),
    ("native_course_quality", "LUXIAN_0609_NATIVE_COURSE_QUALITY_ENABLED"),
    ("native_surgery_gate", "LUXIAN_0609_NATIVE_SURGERY_GATE_ENABLED"),
    ("native_surgery_document", "LUXIAN_0609_NATIVE_SURGERY_DOCUMENT_ENABLED"),
    ("native_mdt_040", "LUXIAN_0609_NATIVE_MDT_040_ENABLED"),
    (
        "native_extended_document",
        "LUXIAN_0609_NATIVE_EXTENDED_DOCUMENT_ENABLED",
    ),
    ("evidence_snapshot_sidecar", "LUXIAN_0609_EVIDENCE_SNAPSHOT_SIDECAR_ENABLED"),
    ("unified_engine", "LUXIAN_0609_UNIFIED_ENGINE_ENABLED"),
    ("mainline_rule_decision", "LUXIAN_0609_MAINLINE_RULE_DECISION_ENABLED"),
    ("rule_decision_007", "LUXIAN_0609_RULE_DECISION_007_ENABLED"),
    (
        "rule_decision_course_severity",
        "LUXIAN_0609_RULE_DECISION_COURSE_SEVERITY_ENABLED",
    ),
    (
        "rule_decision_basic_timeliness",
        "LUXIAN_0609_RULE_DECISION_BASIC_TIMELINESS_ENABLED",
    ),
    (
        "rule_decision_transfusion",
        "LUXIAN_0609_RULE_DECISION_TRANSFUSION_ENABLED",
    ),
    (
        "rule_decision_consultation",
        "LUXIAN_0609_RULE_DECISION_CONSULTATION_ENABLED",
    ),
    ("rule_decision_course_copy", "LUXIAN_0609_RULE_DECISION_COURSE_COPY_ENABLED"),
    (
        "rule_decision_course_admission",
        "LUXIAN_0609_RULE_DECISION_COURSE_ADMISSION_ENABLED",
    ),
    (
        "rule_decision_tumor_pathology",
        "LUXIAN_0609_RULE_DECISION_TUMOR_PATHOLOGY_ENABLED",
    ),
    ("rule_decision_mdt_040", "LUXIAN_0609_RULE_DECISION_MDT_040_ENABLED"),
    (
        "rule_decision_surgery_timeliness",
        "LUXIAN_0609_RULE_DECISION_SURGERY_TIMELINESS_ENABLED",
    ),
    (
        "rule_decision_surgery_gate_remaining",
        "LUXIAN_0609_RULE_DECISION_SURGERY_GATE_REMAINING_ENABLED",
    ),
    (
        "rule_decision_exam_lab",
        "LUXIAN_0609_RULE_DECISION_EXAM_LAB_ENABLED",
    ),
    (
        "rule_decision_surgery_document",
        "LUXIAN_0609_RULE_DECISION_SURGERY_DOCUMENT_ENABLED",
    ),
    ("runtime_shadow", "LUXIAN_0609_RUNTIME_SHADOW_ENABLED"),
    ("preproduction_api", "LUXIAN_0609_PREPRODUCTION_API_ENABLED"),
)


def _normalized_rule_ids(rule_catalog: Sequence[Mapping[str, Any]]) -> list[str]:
    rule_ids = [
        str(item.get("rule_id") or item.get("rule_code") or "").strip().upper()
        for item in rule_catalog
    ]
    if not rule_ids:
        raise ValueError("LX0609 runtime manifest requires a non-empty rule catalog")
    if any(not rule_id.startswith("LX0609-") for rule_id in rule_ids):
        raise ValueError("LX0609 runtime manifest only accepts LX0609 rule ids")
    if len(rule_ids) != len(set(rule_ids)):
        raise ValueError("LX0609 runtime manifest requires unique rule ids")
    if rule_ids != sorted(rule_ids):
        raise ValueError("LX0609 runtime manifest requires an ordered rule catalog")
    return rule_ids


def _safe_flags(settings: Any) -> dict[str, bool]:
    return {
        output_name: bool(getattr(settings, settings_name, False))
        for output_name, settings_name in _SAFE_FLAG_FIELDS
    }


def build_runtime_manifest(
    *,
    git_head: str,
    settings: Any,
    rule_catalog: Sequence[Mapping[str, Any]],
    inventory: Sequence[Luxian0609RuleDependency] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """构建可发布的安全运行清单；不读取或输出密钥、端点和患者数据。"""

    rule_ids = _normalized_rule_ids(rule_catalog)
    dependencies = tuple(
        inventory
        if inventory is not None
        else load_luxian_0609_dependency_inventory()
    )
    if [item.rule_id for item in dependencies] != rule_ids:
        raise ValueError("LX0609 dependency inventory does not match rule catalog")
    from app.services.luxian_0609.rule_contracts import load_luxian_0609_rule_contracts

    contracts = load_luxian_0609_rule_contracts()
    if [item.rule_id for item in contracts] != rule_ids:
        raise ValueError("LX0609 rule contracts do not match rule catalog")
    contract_by_id = {item.rule_id: item for item in contracts}

    runtime_settings = resolve_mainline_rule_decision_settings(settings)
    package_plan = build_luxian_0609_package_plan_from_settings(
        inventory=dependencies,
        selected_rule_ids=rule_ids,
        settings=runtime_settings,
    )
    native_ids = {
        *package_plan.native_sync_rule_ids,
        *package_plan.native_async_rule_ids,
    }
    rules = [
        {
            "rule_id": item.rule_id,
            "family_key": item.family_key,
            "family_name": item.family_name,
            "dependency_mode": item.execution_mode,
            "executor_key": item.executor_key,
            "active_path": "native" if item.rule_id in native_ids else "compatibility",
            "rule_version": item.rule_version,
            "contract_version": contract_by_id[item.rule_id].contract_version,
            "decision_authority": contract_by_id[item.rule_id].decision_authority,
            "max_llm_calls_per_rule": contract_by_id[
                item.rule_id
            ].max_llm_calls_per_rule,
            "source_contract_state": contract_by_id[item.rule_id].source_contract_state,
            "phase_status": contract_by_id[item.rule_id].phase_status,
            "definition_version": contract_by_id[item.rule_id].definition_version,
            "active_criteria": list(contract_by_id[item.rule_id].active_criteria),
            "pending_criteria": list(contract_by_id[item.rule_id].pending_criteria),
            "pending_reason_code": contract_by_id[item.rule_id].pending_reason_code,
            "decision_rollout_flag": (
                get_rule_decision_rollout_flag(item.rule_id)
                if int(item.rule_id.rsplit("-", 1)[-1]) <= 49
                else None
            ),
        }
        for item in dependencies
    ]

    rule_set = get_sichuan_rule_set(RULE_SET_KEY)
    if rule_set is None:
        raise ValueError("LX0609 rule set is unavailable")
    prompt_versions = sorted(
        {
            str(item.get("prompt_version") or "").strip()
            for item in rule_catalog
            if str(item.get("prompt_version") or "").strip()
        }
    )
    rule_versions = sorted(
        {
            str(item.get("rule_version") or "").strip()
            for item in rule_catalog
            if str(item.get("rule_version") or "").strip()
        }
    )
    flags = _safe_flags(runtime_settings)
    normalized_head = str(git_head or "").strip().lower() or "unknown"
    customer_delivery_ids = get_luxian_0609_customer_delivery_rule_ids()
    executable_ids, withheld_ids = get_luxian_0609_customer_execution_scope()
    if (
        len(customer_delivery_ids) != 70
        or len(executable_ids) != 64
        or len(withheld_ids) != 6
        or not set(customer_delivery_ids).issubset(set(rule_ids))
        or set(executable_ids) | set(withheld_ids) != set(customer_delivery_ids)
        or set(executable_ids) & set(withheld_ids)
    ):
        raise ValueError("invalid LX0609 customer scope partition")

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at
        or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "git_head": normalized_head,
        "customer_rule_count": len(rule_ids),
        "customer_delivery_count": len(customer_delivery_ids),
        "executable_count": len(executable_ids),
        "withheld_count": len(withheld_ids),
        "customer_delivery_rule_ids": list(customer_delivery_ids),
        "executable_rule_ids": list(executable_ids),
        "withheld_rule_ids": list(withheld_ids),
        "flags": flags,
        "rule_set": {
            "key": rule_set.key,
            "version": rule_set.version,
            "rule_count": len(rule_ids),
            "rule_ids": rule_ids,
        },
        "runtime": {
            "flags": flags,
            "models": {
                "primary": str(
                    getattr(runtime_settings, "LLM_MODEL", "") or ""
                ).strip(),
                "adjudicator": str(
                    getattr(runtime_settings, "LLM_ADJUDICATOR_MODEL", "") or ""
                ).strip(),
            },
            "strategies": {
                "execution_strategy": rule_set.execution_strategy,
                "quality_profile": rule_set.quality_profile,
                "bucket_strategy": rule_set.bucket_strategy,
                "rule_versions": rule_versions,
                "prompt_versions": prompt_versions,
            },
            # gate-only 由每次请求的 allowed_rule_ids 决定，不能伪装成静态规则属性。
            "gate_only_is_request_scoped": True,
        },
        "rules": rules,
    }


def runtime_manifest_hash(runtime_manifest: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        dict(runtime_manifest),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current_git_head(project_root: Path = PROJECT_ROOT) -> str:
    try:
        value = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            text=True,
            timeout=5,
        ).strip().lower()
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return (
        value
        if len(value) == 40 and all(char in "0123456789abcdef" for char in value)
        else "unknown"
    )


def validate_runtime_manifest_current(
    runtime_manifest: Mapping[str, Any],
    *,
    observed_git_head: str | None = None,
) -> str:
    manifest_head = str(runtime_manifest.get("git_head") or "").strip().lower()
    current_head = (
        str(observed_git_head).strip().lower()
        if observed_git_head is not None
        else current_git_head()
    )
    if runtime_manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("invalid LX0609 runtime manifest schema")
    if current_head == "unknown" or manifest_head != current_head:
        raise ValueError("LX0609 runtime manifest does not match current git head")
    return current_head


def build_artifact_metadata(
    *,
    runtime_manifest: Mapping[str, Any],
    schema_version: str,
    evidence_scope: str,
    generated_at: str | None = None,
) -> dict[str, str]:
    git_head = str(runtime_manifest.get("git_head") or "").strip().lower()
    if runtime_manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("invalid LX0609 runtime manifest schema")
    if len(git_head) != 40 or any(char not in "0123456789abcdef" for char in git_head):
        raise ValueError("runtime manifest requires a full git head")
    if evidence_scope not in EVIDENCE_SCOPES:
        raise ValueError("invalid LX0609 evidence scope")
    normalized_schema = str(schema_version or "").strip()
    if not normalized_schema:
        raise ValueError("artifact schema version is required")
    return {
        "schema_version": normalized_schema,
        "generated_at": generated_at
        or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "git_head": git_head,
        "runtime_manifest_hash": runtime_manifest_hash(runtime_manifest),
        "evidence_scope": evidence_scope,
    }


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as file:
            temporary_path = Path(file.name)
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    atomic_write_text(
        path,
        json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n",
    )


def _git_head() -> str:
    return current_git_head()


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 LX0609 当前安全运行清单")
    parser.add_argument("--output", type=Path, help="输出 JSON 文件；省略时打印到 stdout")
    args = parser.parse_args()
    manifest = build_runtime_manifest(
        git_head=_git_head(),
        settings=get_settings(),
        rule_catalog=load_luxian_0609_rules(),
    )
    content = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        atomic_write_text(args.output, content)
    else:
        print(content, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
