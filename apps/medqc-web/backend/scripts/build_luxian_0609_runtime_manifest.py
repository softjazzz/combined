"""生成不含敏感配置的 LX0609 当前运行版本清单。"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
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
    resolve_mainline_rule_decision_settings,
)
from app.services.luxian_0609_rule_catalog import load_luxian_0609_rules  # noqa: E402
from app.services.qc_rule_sets import get_sichuan_rule_set  # noqa: E402


SCHEMA_VERSION = "lx0609-runtime-manifest-v1"
RULE_SET_KEY = "luxian_0609_qc_v1"
PROJECT_ROOT = Path(__file__).resolve().parents[2]

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
    expected = [f"LX0609-{index:03d}" for index in range(1, 50)]
    if rule_ids != expected:
        raise ValueError("LX0609 runtime manifest requires the ordered 49-rule catalog")
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

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at
        or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "git_head": normalized_head,
        "customer_rule_count": len(rule_ids),
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


def _git_head() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            text=True,
            timeout=5,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


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
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", encoding="utf-8", newline="\n") as file:
            file.write(content)
    else:
        print(content, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
