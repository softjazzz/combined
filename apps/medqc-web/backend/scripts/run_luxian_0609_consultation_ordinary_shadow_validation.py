"""只读复跑普通会诊20例，并仅输出可人工复核的安全台账。"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database.connection import DB_SCHEMA_MODE
from app.services.qc_llm_client import SichuanQCLLMClient
from app.services.luxian_0609 import native_consultation_episode_execution as episode
from app.services.luxian_0609.evidence_snapshot_provider import (
    build_luxian_0609_evidence_read_session,
)
from scripts.run_luxian_0609_consultation_ordinary_validation import (
    _coordinate_hash,
    read_ordinary_consultation_source_rows,
    select_ordinary_consultation_cases,
)


from app.services.case_identity import CaseRef
from app.services.luxian_0609.llm_prompt_privacy import (
    PatientPrivacyViolation, PrivacyIdentityContextError, wrap_luxian_0609_llm_client,
)
from app.services.luxian_0609.privacy_identity_context import (
    _Luxian0609IdentityCollector, PrivacyIdentityContextUnavailable,
    build_luxian_0609_identity_provider,
)
from app.services.luxian_0609.privacy_request_scope import (
    bind_luxian_0609_identity_provider, luxian_0609_case_identity_scope,
)


RULE_IDS = (
    "LX0609-03-01-01",
    "LX0609-03-01-02",
    "LX0609-03-01-03",
    "LX0609-03-01-04",
)
SAFE_LEDGER_FIELDS = frozenset((
    "case_label",
    "selector_fingerprint",
    "rule_id",
    "final_state",
    "reason_code",
    "action_types",
    "execution_states",
    "confidence",
    "related_source_coverage",
    "llm_call_count",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "latency_seconds",
))
_SAFE_FINAL_STATES = frozenset((
    "compliant", "non_compliant", "not_applicable", "data_gap",
    "technical_error", "evaluation_unknown",
))
_SAFE_REASON_CODES = frozenset((
    "requirement_satisfied", "requirement_violated", "trigger_absent_complete",
    "non_target_document",
    "candidate_scope_incomplete", "linkage_unresolved", "source_unavailable",
    "source_query_error", "semantic_low_confidence", "semantic_output_unknown",
    "model_transport_error",
))
_CASE_LABEL = re.compile(r"case-[0-9]{2}\Z")
_FINGERPRINT = re.compile(r"[0-9a-f]{64}\Z")


class _SafeStageCapture:
    """只保留模型受控枚举；响应正文始终只存在于调用栈内。"""

    def __init__(self) -> None:
        self.action_types: set[str] = set()
        self.execution_states: set[str] = set()
        self.confidence: set[str] = set()

    def capture_response(self, response: Mapping[str, Any]) -> None:
        try:
            payload = episode._payload(response)
        except Exception:
            return
        raw_episodes = payload.get("episodes")
        if isinstance(raw_episodes, list):
            for item in raw_episodes:
                if not isinstance(item, Mapping):
                    continue
                confidence = str(item.get("confidence") or "").strip().lower()
                if confidence in episode._CONFIDENCE:
                    self.confidence.add(confidence)
                recommendations = item.get("recommendations")
                if not isinstance(recommendations, list):
                    continue
                for recommendation in recommendations:
                    if not isinstance(recommendation, Mapping):
                        continue
                    action_type = str(recommendation.get("action_type") or "").strip().lower()
                    if action_type in episode._RECOMMENDATION_TYPES:
                        self.action_types.add(action_type)
        raw_executions = payload.get("executions")
        if isinstance(raw_executions, list):
            for item in raw_executions:
                if not isinstance(item, Mapping):
                    continue
                execution_state = str(item.get("execution_state") or "").strip().lower()
                if execution_state in episode._EXECUTION_STATES:
                    self.execution_states.add(execution_state)
                confidence = str(item.get("confidence") or "").strip().lower()
                if confidence in episode._CONFIDENCE:
                    self.confidence.add(confidence)


class _RecordingClient:
    def __init__(self, client: SichuanQCLLMClient, capture: _SafeStageCapture) -> None:
        self._client = client
        self._capture = capture

    async def generate(self, prompt: str) -> dict[str, Any]:
        response = await self._client.generate(prompt)
        if isinstance(response, Mapping):
            self._capture.capture_response(response)
        return response


def _safe_reason(value: Any) -> str:
    normalized = str(value or "").strip()
    return normalized if normalized in _SAFE_REASON_CODES else "unclassified"


def _safe_final_state(value: Any) -> str:
    normalized = str(value or "").strip()
    return normalized if normalized in _SAFE_FINAL_STATES else "evaluation_unknown"


def _related_source_coverage(
    *,
    action_types: Sequence[str],
    source_complete_keys: frozenset[str],
    source_incomplete_keys: frozenset[str],
) -> list[str]:
    coverage: list[str] = []
    for action_type in sorted(set(action_types)):
        required = episode._ACTION_TYPE_SOURCE_KEYS.get(action_type)
        if required is None:
            continue
        if required.issubset(source_complete_keys):
            coverage.append(f"{action_type}:complete")
        elif required.intersection(source_incomplete_keys):
            coverage.append(f"{action_type}:incomplete")
        else:
            coverage.append(f"{action_type}:unavailable")
    return coverage


def build_safe_ledger_rows(
    *,
    case_label: str,
    selector_fingerprint: str,
    results: Sequence[Mapping[str, Any]],
    capture: _SafeStageCapture,
    source_complete_keys: frozenset[str],
    source_incomplete_keys: frozenset[str],
    llm_call_count: int,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    latency_seconds: float,
) -> list[dict[str, Any]]:
    if not _CASE_LABEL.fullmatch(case_label) or not _FINGERPRINT.fullmatch(selector_fingerprint):
        raise ValueError("invalid safe ledger identity")
    action_types = sorted(capture.action_types)
    coverage = _related_source_coverage(
        action_types=action_types,
        source_complete_keys=source_complete_keys,
        source_incomplete_keys=source_incomplete_keys,
    )
    rows: list[dict[str, Any]] = []
    for result in results:
        rule_id = str(result.get("rule_id") or "").strip().upper()
        if rule_id not in RULE_IDS:
            raise ValueError("unsupported ledger rule")
        metadata = result.get("metadata")
        metadata = metadata if isinstance(metadata, Mapping) else {}
        row = {
            "case_label": case_label,
            "selector_fingerprint": selector_fingerprint,
            "rule_id": rule_id,
            "final_state": _safe_final_state(metadata.get("source_state")),
            "reason_code": _safe_reason(metadata.get("reason_code")),
            "action_types": action_types,
            "execution_states": sorted(capture.execution_states),
            "confidence": sorted(capture.confidence),
            "related_source_coverage": coverage,
            "llm_call_count": max(0, int(llm_call_count)),
            "prompt_tokens": max(0, int(prompt_tokens)),
            "completion_tokens": max(0, int(completion_tokens)),
            "total_tokens": max(0, int(total_tokens)),
            "latency_seconds": round(max(0.0, float(latency_seconds)), 3),
        }
        if set(row) != SAFE_LEDGER_FIELDS:
            raise ValueError("unsafe ledger shape")
        rows.append(row)
    return rows


def _source_identity_provider(collector, coordinates):
    # 只借用已审查collect操作内存对象；不接受字符串、字典或任意provider。
    if not isinstance(collector, _Luxian0609IdentityCollector):
        raise PrivacyIdentityContextUnavailable()
    try:
        return collector.provider_for_case(CaseRef(*coordinates))
    except Exception:
        raise PrivacyIdentityContextUnavailable() from None


def _bind_script_identity(source_provider, coordinates, **material_kwargs):
    material_provider = build_luxian_0609_identity_provider(
        **dict(zip(("institute_id", "patient_id", "visit_id"), coordinates)),
        **material_kwargs,
    )

    def combined():
        # 原值只在每次调用的临时集合；不能将来源预检当作发送时校验。
        return tuple(sorted(set(source_provider()) | set(material_provider())))

    return bind_luxian_0609_identity_provider(combined, case_coordinates=coordinates)


async def _run(*, snapshot_as_of: str, limit_rows: int, llm_client=None,
               _private_identity_collector: _Luxian0609IdentityCollector | None = None) -> list[dict[str, Any]]:
    # 当前CLI没有合法原身份入口，缺源时必须在任何现有读取/配置构造之前拒绝。
    if not isinstance(_private_identity_collector, _Luxian0609IdentityCollector):
        raise PrivacyIdentityContextUnavailable()
    source_rows = read_ordinary_consultation_source_rows(limit_rows=limit_rows)
    selected = select_ordinary_consultation_cases(
        source_rows,
        schema_mode=str(DB_SCHEMA_MODE or "").strip().lower() or "single",
        snapshot_as_of=snapshot_as_of,
    )
    by_coordinate_hash = {_coordinate_hash(row): row for row in source_rows}
    client = llm_client
    ledger: list[dict[str, Any]] = []
    for case in selected["cases"]:
        source = by_coordinate_hash.get(case["coordinate_hash"])
        if source is None:
            raise ValueError("selected source missing")
        coordinates = tuple(str(source[key]) for key in ("institute_id", "patient_id", "visit_id"))
        source_provider = _source_identity_provider(_private_identity_collector, coordinates)
        source_provider()
        with luxian_0609_case_identity_scope(case_coordinates=coordinates, identity_provider=source_provider):
            session = build_luxian_0609_evidence_read_session(
                selected_rule_ids=RULE_IDS,
                institute_id=coordinates[0], patient_id=coordinates[1], visit_id=coordinates[2],
                source_schema=None,
                created_at=datetime.now(timezone.utc).isoformat(),
                evaluation_as_of_date=snapshot_as_of,
            )
            identity_provider = _bind_script_identity(
                source_provider, coordinates, snapshot=session.snapshot, materials=session.materials,
            )
            identity_provider()
            if client is None:
                client = SichuanQCLLMClient()
            guarded_client = wrap_luxian_0609_llm_client(client, identity_provider=identity_provider)
            projection = episode._candidate_documents(
                institute_id=coordinates[0], patient_id=coordinates[1], visit_id=coordinates[2],
                source_schema=None,
                evidence_materials=session.materials,
                evidence_snapshot=session.snapshot,
                stay_window=episode._resolve_execution_stay_window(
                    evidence_materials=session.materials,
                    evidence_snapshot=session.snapshot,
                ),
            )
            capture = _SafeStageCapture()
            result = await episode.execute_luxian_0609_native_consultation_episode_rules(
                rule_ids=RULE_IDS,
                institute_id=coordinates[0], patient_id=coordinates[1], visit_id=coordinates[2],
                source_schema=None,
                llm_client=_RecordingClient(guarded_client, capture),
                evidence_materials=session.materials,
                evidence_snapshot=session.snapshot,
            )
            ledger.extend(build_safe_ledger_rows(
                case_label=str(case["case_label"]), selector_fingerprint=str(selected["selector_fingerprint"]),
                results=result.results, capture=capture,
                source_complete_keys=projection.source_complete_keys,
                source_incomplete_keys=projection.source_incomplete_keys,
                llm_call_count=result.llm_call_count, prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens, total_tokens=result.total_tokens,
                latency_seconds=result.api_time,
            ))
    return ledger


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="只读复跑LX0609普通会诊20例安全台账")
    parser.add_argument("--snapshot-as-of", required=True)
    parser.add_argument("--limit-rows", type=int, default=5000)
    args = parser.parse_args(argv)
    try:
        rows = asyncio.run(_run(
            snapshot_as_of=str(args.snapshot_as_of),
            limit_rows=int(args.limit_rows),
        ))
    except (PrivacyIdentityContextUnavailable, PrivacyIdentityContextError, PatientPrivacyViolation):
        print("LX0609 ordinary shadow requires trusted in-memory identity source", file=sys.stderr)
        return 1
    for row in rows:
        print(json.dumps(row, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
