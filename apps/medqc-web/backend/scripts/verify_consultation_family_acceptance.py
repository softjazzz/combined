"""会诊族离线合同复放；不读取数据库、不调用真实模型。"""

from __future__ import annotations

import argparse
import asyncio
from contextlib import contextmanager
import hashlib
import hmac
import http.client
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
from typing import Any, Mapping, Sequence
from types import SimpleNamespace


_RESULT_MARKER = "CONSULTATION_REPLAY_RESULT="
_PROMPT_HMAC_ENV = "CONSULTATION_REPLAY_PROMPT_HMAC_KEY"


class ReplayFixtureError(ValueError):
    """受控复放夹具不符合最小合同。"""


def _prompt_marker(*, prompts: Sequence[str], session_hmac_key: bytes) -> str:
    """跨子进程精确比较 Prompt，marker 只用于本次会话且绝不写入业务结果。"""

    if not session_hmac_key:
        raise ReplayFixtureError("prompt HMAC key is required")
    payload = b"\0".join(prompt.encode("utf-8") for prompt in prompts)
    return hmac.new(session_hmac_key, payload, hashlib.sha256).hexdigest()


def _backend_root(variant_root: Path | None) -> Path:
    if variant_root is None:
        return Path(__file__).resolve().parents[1]
    root = variant_root.resolve()
    candidates = (root, root / "backend", root / "apps" / "medqc-web" / "backend")
    for candidate in candidates:
        if (candidate / "app").is_dir():
            return candidate
    raise ReplayFixtureError("variant root does not contain backend/app")


def _use_variant_root(variant_root: Path | None) -> None:
    backend_root = _backend_root(variant_root)
    backend_text = str(backend_root)
    if backend_text in sys.path:
        sys.path.remove(backend_text)
    sys.path.insert(0, backend_text)


def _load_fixture(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReplayFixtureError("fixture is unreadable") from exc
    if not isinstance(value, dict):
        raise ReplayFixtureError("fixture must be an object")
    if value.get("fixture_kind") != "synthetic_contract_branch_replay":
        raise ReplayFixtureError("fixture is not a synthetic contract replay")
    if value.get("historical_b3_response") is not False:
        raise ReplayFixtureError("fixture must not claim to be a historical B3 response")
    if not isinstance(value.get("coordinates"), dict):
        raise ReplayFixtureError("fixture coordinates are required")
    if not isinstance(value.get("rule_ids"), list) or not value["rule_ids"]:
        raise ReplayFixtureError("fixture rule_ids are required")
    if not isinstance(value.get("source_rows"), dict):
        raise ReplayFixtureError("fixture source_rows are required")
    if not isinstance(value.get("responses"), list) or not value["responses"]:
        raise ReplayFixtureError("fixture responses are required")
    return value


@contextmanager
def _offline_execution_guards():
    """让零网络/零数据库声明由可恢复的运行时哨兵约束。"""

    network_used = False
    database_used = False

    def block_network(*_args: Any, **_kwargs: Any) -> None:
        nonlocal network_used
        network_used = True
        raise ReplayFixtureError("network access is forbidden during replay")

    def block_database(*_args: Any, **_kwargs: Any) -> None:
        nonlocal database_used
        database_used = True
        raise ReplayFixtureError("database access is forbidden during replay")

    original_socket = socket.socket
    original_create_connection = socket.create_connection
    original_http = http.client.HTTPConnection
    original_https = http.client.HTTPSConnection
    try:
        from sqlalchemy.engine import Engine
    except ImportError as exc:
        raise ReplayFixtureError("SQLAlchemy Engine guard is unavailable") from exc
    original_engine_connect = Engine.connect
    socket.socket = block_network
    socket.create_connection = block_network
    http.client.HTTPConnection = block_network
    http.client.HTTPSConnection = block_network
    Engine.connect = block_database
    def activity() -> dict[str, bool]:
        return {
            "network_used": network_used,
            "database_used": database_used,
        }
    try:
        yield activity
    finally:
        socket.socket = original_socket
        socket.create_connection = original_create_connection
        http.client.HTTPConnection = original_http
        http.client.HTTPSConnection = original_https
        Engine.connect = original_engine_connect


def _minimal_child_environment(*, session_hmac_key: bytes) -> dict[str, str]:
    allowed = (
        "ComSpec",
        "PATHEXT",
        "Path",
        "SystemRoot",
        "TEMP",
        "TMP",
        "WINDIR",
        "PYTHONHOME",
        "PYTHONPATH",
    )
    environment = {
        key: os.environ[key]
        for key in allowed
        if os.environ.get(key)
    }
    environment["PYTHONIOENCODING"] = "utf-8"
    environment[_PROMPT_HMAC_ENV] = session_hmac_key.hex()
    return environment


class _RecordedResponseClient:
    """只消费夹具中的受控响应，并在内存中保留 Prompt 用于字节比较。"""

    def __init__(self, responses: Sequence[Mapping[str, Any]]) -> None:
        self._responses = [dict(item) for item in responses]
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> dict[str, Any]:
        self.prompts.append(prompt)
        if not self._responses:
            raise ReplayFixtureError("fixture response sequence exhausted")
        response = self._responses.pop(0)
        payload = response.get("payload")
        usage = response.get("usage")
        if not isinstance(payload, Mapping) or not isinstance(usage, Mapping):
            raise ReplayFixtureError("fixture response shape is invalid")
        api_time = response.get("api_time", 0.0)
        if not isinstance(api_time, (int, float)) or api_time < 0:
            raise ReplayFixtureError("fixture api_time is invalid")
        return {
            "content": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            "usage": dict(usage),
            "_api_time": float(api_time),
        }

    def assert_consumed(self) -> None:
        if self._responses:
            raise ReplayFixtureError("fixture has unused controlled responses")


def _source_reader(
    *,
    source_rows: Mapping[str, Any],
    snapshot_source_rows: Any,
):
    def read(**kwargs: Any) -> Any:
        source_key = str(kwargs.get("source_key") or "")
        rows = source_rows.get(source_key, [])
        if not isinstance(rows, list) or not all(isinstance(row, Mapping) for row in rows):
            raise ReplayFixtureError("fixture source rows are invalid")
        return snapshot_source_rows.create(
            source_key=source_key,
            rows=rows,
            truncated=False,
            limit_rows=50,
        )

    return read


def _allowlisted_public_facts(*, rule_id: str, raw: Any) -> dict[str, Any]:
    """只输出 020–023 已声明的客户字段，未知字段默认丢弃。"""

    if not isinstance(raw, Mapping):
        return {}

    def select(item: Any, keys: Sequence[str]) -> dict[str, Any]:
        return {
            key: item[key]
            for key in keys
            if isinstance(item, Mapping) and key in item
        }

    if rule_id in {"LX0609-020", "LX0609-023"}:
        facts = select(
            raw,
            (
                "verification_kind",
                "completed_opinion_episode_count",
                "recommendation_count",
                "specific_execution_count",
                "generic_execution_count",
                "missing_execution_count",
                "relation_state",
            ),
        )
        if rule_id == "LX0609-020" and isinstance(raw.get("recommendation_results"), list):
            facts["recommendation_results"] = [
                select(
                    item,
                    (
                        "episode_index",
                        "recommendation_index",
                        "action_type",
                        "execution_state",
                    ),
                )
                for item in raw["recommendation_results"]
                if isinstance(item, Mapping)
            ]
        if isinstance(raw.get("recommendation_evidence"), list):
            evidence_items = []
            for item in raw["recommendation_evidence"]:
                if not isinstance(item, Mapping):
                    continue
                projected = select(
                    item,
                    ("episode_index", "recommendation_index", "execution_state"),
                )
                for field in ("opinion_evidence", "execution_evidence"):
                    if isinstance(item.get(field), list):
                        projected[field] = [
                            select(reference, ("source_type",))
                            for reference in item[field]
                            if isinstance(reference, Mapping)
                        ]
                evidence_items.append(projected)
            facts["recommendation_evidence"] = evidence_items
        return facts
    if rule_id in {"LX0609-021", "LX0609-022"}:
        facts = select(
            raw,
            (
                "verification_kind",
                "episode_count",
                "document_count",
                "semantic_state",
                "checked_requirement",
            ),
        )
        if isinstance(raw.get("episode_results"), list):
            facts["episode_results"] = [
                select(
                    item,
                    (
                        "episode_index",
                        "semantic_state",
                        "record_time",
                        "document_title",
                    ),
                )
                for item in raw["episode_results"]
                if isinstance(item, Mapping)
            ]
        return facts
    return {}


def _public_aggregate_result(*, result: Mapping[str, Any], decision: Any) -> dict[str, Any]:
    """只读取正式聚合出口；不在 replay 中再次投影或 Finalize。"""

    evidence = result.get("customer_evidence")
    evidence = evidence if isinstance(evidence, list) else []
    coordinates = [
        {
            "source_type": str(item.get("source_type") or ""),
            "source_document_id": str(item.get("source_document_id") or ""),
            "field_path": str(
                item.get("field_path") or item.get("source_field") or ""
            ),
            "record_time": str(item.get("record_time") or ""),
        }
        for item in evidence
        if isinstance(item, Mapping)
        and item.get("source_type")
        and item.get("source_document_id")
    ]

    rule_id = str(result.get("rule_id") or "").strip().upper()
    return {
        "rule_id": rule_id,
        "status": str(result.get("status") or ""),
        "reason_code": str(result.get("reason_code") or ""),
        "facts": _allowlisted_public_facts(
            rule_id=rule_id,
            raw=result.get("customer_display_facts"),
        ),
        "fact_ref_count": len(tuple(getattr(decision, "fact_refs", ()))),
        "evidence_coordinates": coordinates,
    }


async def _run_replay_unchecked(
    fixture_path: Path,
    *,
    variant_root: Path | None = None,
    activity: Any,
    llm_client: Any | None = None,
) -> dict[str, Any]:
    """在已经安装离线哨兵的前提下运行正式聚合链。"""

    _use_variant_root(variant_root)
    fixture = _load_fixture(fixture_path)
    try:
        from app.services.luxian_0609 import native_consultation_episode_execution as episode
        from app.services.luxian_0609.decision_reducer import (
            reduce_luxian_0609_rule_decision,
        )
        from app.services.luxian_0609.evidence_snapshot_provider import (
            SnapshotSourceRows,
            build_luxian_0609_evidence_read_session,
        )
        from app.services.luxian_0609_result_aggregator import (
            aggregate_luxian_0609_results,
        )
    except ImportError as exc:
        raise ReplayFixtureError("required formal aggregation contract unavailable") from exc

    coordinates = fixture["coordinates"]
    if not all(isinstance(coordinates.get(key), str) and coordinates[key] for key in ("institute_id", "patient_id", "visit_id")):
        raise ReplayFixtureError("fixture coordinates are invalid")
    rule_ids = tuple(str(item).strip().upper() for item in fixture["rule_ids"])
    if len(set(rule_ids)) != len(rule_ids):
        raise ReplayFixtureError("fixture rule_ids must be unique")
    read = _source_reader(source_rows=fixture["source_rows"], snapshot_source_rows=SnapshotSourceRows)
    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=rule_ids,
        institute_id=coordinates["institute_id"],
        patient_id=coordinates["patient_id"],
        visit_id=coordinates["visit_id"],
        source_schema=None,
        created_at="2026-09-05T00:00:00+08:00",
        evaluation_as_of_date="2026-07-03",
        row_reader=read,
    )
    client = llm_client or _RecordedResponseClient(fixture["responses"])
    original_reader = episode.read_luxian_0609_native_source_rows
    episode.read_luxian_0609_native_source_rows = read
    try:
        execution = await episode.execute_luxian_0609_native_consultation_episode_rules(
            rule_ids=rule_ids,
            institute_id=coordinates["institute_id"],
            patient_id=coordinates["patient_id"],
            visit_id=coordinates["visit_id"],
            source_schema=None,
            llm_client=client,
            evidence_materials=session.materials,
            evidence_snapshot=session.snapshot,
            decision_rule_ids=rule_ids,
        )
    finally:
        episode.read_luxian_0609_native_source_rows = original_reader
    if isinstance(client, _RecordedResponseClient):
        client.assert_consumed()
    decision_by_rule = {decision.rule_id: decision for decision in execution.decisions}
    # typed 会诊执行的唯一正式出口是 RuleDecision；必须经过 reducer、聚合器的
    # 客户事实投影和 Finalizer，不能在 replay 中手工构造 Canonical 结果。
    from app.services.qc_workspace import canonical_result_store

    original_get_settings = canonical_result_store.get_settings
    canonical_result_store.get_settings = lambda: SimpleNamespace(
        JWT_SECRET="offline-consultation-replay-fixture-key"
    )
    try:
        canonical_results = aggregate_luxian_0609_results(
            wrapper_rules=[{"rule_id": rule_id, "name": rule_id} for rule_id in rule_ids],
            execution_results=list(execution.results),
            format_evidence=False,
            audit_context={
                "evidence_snapshot": session.snapshot,
                "evidence_materials": session.materials,
            },
            reduced_decisions=tuple(
                reduce_luxian_0609_rule_decision(decision)
                for decision in execution.decisions
            ),
            customer_display_facts=execution.customer_display_facts,
        )
    finally:
        canonical_result_store.get_settings = original_get_settings
    results = []
    for result in canonical_results:
        rule_id = str(result.get("rule_id") or "")
        decision = decision_by_rule.get(rule_id)
        if decision is None:
            raise ReplayFixtureError("formal aggregation omitted typed decision")
        results.append(
            _public_aggregate_result(
                result=result,
                decision=decision,
            )
        )
    return {
        "fixture_kind": fixture["fixture_kind"],
        "historical_b3_response": False,
        **activity(),
        "llm_call_count": execution.llm_call_count,
        "prompt_count": len(tuple(getattr(client, "prompts", ()))),
        "prompt_tokens": execution.prompt_tokens,
        "completion_tokens": execution.completion_tokens,
        "total_tokens": execution.total_tokens,
        "api_time": execution.api_time,
        "results": results,
        # 只在同一 Python 进程内保留 Prompt，供调用方逐字比较；公共输出会过滤
        # 此字段，绝不序列化或持久化 Prompt。
        "_prompt_bytes": tuple(getattr(client, "prompts", ())),
    }


async def run_replay(
    fixture_path: Path,
    *,
    variant_root: Path | None = None,
    session_hmac_key: bytes | None = None,
) -> dict[str, Any]:
    """在离线哨兵内运行，不读取真实配置、数据库或网络。"""

    key = session_hmac_key or secrets.token_bytes(32)
    with _offline_execution_guards() as activity:
        replay = await _run_replay_unchecked(
            fixture_path,
            variant_root=variant_root,
            activity=activity,
        )
    replay["_prompt_session_marker"] = _prompt_marker(
        prompts=tuple(replay.get("_prompt_bytes") or ()),
        session_hmac_key=key,
    )
    return replay


async def run_formal_synthetic_chain(
    fixture_path: Path,
    *,
    llm_client: Any,
) -> dict[str, Any]:
    """以合成资料走正式会诊主链，供显式授权的真实模型手工基准使用。"""

    return await _run_replay_unchecked(
        fixture_path,
        # 直接链本身不暴露 HTTP attempt；调用方只能如实报告网络观测未知，
        # 不能将“允许真实模型”误写成“已观察到网络请求”。
        activity=lambda: {"network_used": "unknown", "database_used": False},
        llm_client=llm_client,
    )


def _public_replay(replay: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in replay.items() if not key.startswith("_")}


def _result_index(replay: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    raw_results = replay.get("results")
    if not isinstance(raw_results, list):
        raise ReplayFixtureError("replay public results are invalid")
    indexed: dict[str, Mapping[str, Any]] = {}
    for item in raw_results:
        if not isinstance(item, Mapping):
            raise ReplayFixtureError("replay public result is invalid")
        rule_id = str(item.get("rule_id") or "").strip().upper()
        if not rule_id or rule_id in indexed:
            raise ReplayFixtureError("replay result rule ids are invalid")
        indexed[rule_id] = item
    return indexed


def _coordinate_set(result: Mapping[str, Any]) -> frozenset[tuple[str, str, str, str]]:
    raw_coordinates = result.get("evidence_coordinates")
    if not isinstance(raw_coordinates, list):
        return frozenset()
    return frozenset(
        (
            str(item.get("source_type") or ""),
            str(item.get("source_document_id") or ""),
            str(item.get("field_path") or item.get("source_field") or ""),
            str(item.get("record_time") or ""),
        )
        for item in raw_coordinates
        if isinstance(item, Mapping)
    )


def compare_replays(replays: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if len(replays) < 2:
        raise ReplayFixtureError("at least two variant replays are required")
    prompt_values: list[tuple[str, Any] | None] = []
    for replay in replays:
        prompts = replay.get("_prompt_bytes")
        if isinstance(prompts, tuple) and all(isinstance(prompt, str) for prompt in prompts):
            prompt_values.append(("memory", prompts))
            continue
        marker = replay.get("_prompt_session_marker")
        if isinstance(marker, str) and marker:
            prompt_values.append(("session_hmac", marker))
            continue
        prompt_values.append(None)
    prompt_available = all(value is not None for value in prompt_values)
    indexes = [_result_index(replay) for replay in replays]
    rule_ids = sorted({rule_id for index in indexes for rule_id in index})
    comparisons: list[dict[str, Any]] = []
    for rule_id in rule_ids:
        by_variant = [index.get(rule_id) for index in indexes]
        statuses = [str(item.get("status") or "") if item else None for item in by_variant]
        reasons = [str(item.get("reason_code") or "") if item else None for item in by_variant]
        facts = [item.get("facts") if item else None for item in by_variant]
        coordinates = [
            _coordinate_set(item) if item is not None else None
            for item in by_variant
        ]
        counts = [
            item.get("fact_ref_count") if item is not None else None
            for item in by_variant
        ]
        status_equal = all(value == statuses[0] for value in statuses[1:])
        reason_equal = all(value == reasons[0] for value in reasons[1:])
        facts_equal = all(value == facts[0] for value in facts[1:])
        coordinates_equal = all(value == coordinates[0] for value in coordinates[1:])
        fact_ref_count_equal = all(value == counts[0] for value in counts[1:])
        comparisons.append(
            {
                "rule_id": rule_id,
                "status_by_variant": statuses,
                "reason_code_by_variant": reasons,
                "status_equal": status_equal,
                "reason_code_equal": reason_equal,
                "facts_equal": facts_equal,
                "evidence_coordinates_set_equal": coordinates_equal,
                "fact_ref_count_by_variant": counts,
                "fact_ref_count_equal": fact_ref_count_equal,
                "exact_equal": (
                    status_equal
                    and reason_equal
                    and facts_equal
                    and coordinates_equal
                    and fact_ref_count_equal
                ),
            }
        )
    return {
        "network_used": False,
        "prompts_byte_equal": (
            all(value == prompt_values[0] for value in prompt_values[1:])
            if prompt_available
            else None
        ),
        "prompt_count_by_variant": [
            int(replay.get("prompt_count") or 0)
            for replay in replays
        ],
        "rule_comparisons": comparisons,
        "acceptance_projection_exact_equal": bool(comparisons) and all(
            item["exact_equal"] for item in comparisons
        ),
        "variants": [_public_replay(replay) for replay in replays],
    }


def _run_variant_subprocess(
    *,
    fixture_path: Path,
    variant_root: Path,
    session_hmac_key: bytes | None = None,
) -> dict[str, Any]:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--fixture",
        str(fixture_path.resolve()),
        "--variant-root",
        str(variant_root.resolve()),
        "--single-variant",
    ]
    key = session_hmac_key or secrets.token_bytes(32)
    environment = _minimal_child_environment(session_hmac_key=key)
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        encoding="utf-8",
        errors="strict",
        env=environment,
    )
    if completed.returncode != 0:
        raise ReplayFixtureError("variant replay subprocess failed")
    lines = [line for line in completed.stdout.splitlines() if line.startswith(_RESULT_MARKER)]
    if len(lines) != 1:
        raise ReplayFixtureError("variant replay produced no controlled result")
    value = json.loads(lines[0].removeprefix(_RESULT_MARKER))
    if not isinstance(value, dict):
        raise ReplayFixtureError("variant replay result is invalid")
    marker = value.get("_prompt_session_marker")
    if not isinstance(marker, str) or not marker:
        raise ReplayFixtureError("variant replay prompt marker is invalid")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="LX0609 会诊族离线合同复放")
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--variant-root", type=Path, action="append", default=[])
    parser.add_argument("--single-variant", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.single_variant:
        if len(args.variant_root) != 1:
            raise ReplayFixtureError("single variant mode requires exactly one variant root")
        try:
            child_key = bytes.fromhex(os.environ.get(_PROMPT_HMAC_ENV, ""))
            replay = asyncio.run(
                run_replay(
                    args.fixture,
                    variant_root=args.variant_root[0],
                    session_hmac_key=child_key,
                )
            )
        except ReplayFixtureError:
            replay = {
                "fixture_kind": "synthetic_contract_branch_replay",
                "historical_b3_response": False,
                "network_used": False,
                "variant_run_status": "blocked",
                "blocked_stage": "formal_aggregation_contract_import",
                "reason_code": "required_formal_aggregation_contract_unavailable",
                "results": [],
                "_prompt_bytes": (),
            }
        child_output = _public_replay(replay)
        child_output["_prompt_session_marker"] = str(
            replay.get("_prompt_session_marker") or ""
        )
        print(_RESULT_MARKER + json.dumps(child_output, ensure_ascii=False, sort_keys=True))
        return 0
    if args.variant_root:
        session_hmac_key = secrets.token_bytes(32)
        replays = [
            _run_variant_subprocess(
                fixture_path=args.fixture,
                variant_root=root,
                session_hmac_key=session_hmac_key,
            )
            for root in args.variant_root
        ]
        if len(replays) == 1:
            print(json.dumps(_public_replay(replays[0]), ensure_ascii=False, sort_keys=True))
            return 0
        print(json.dumps(compare_replays(replays), ensure_ascii=False, sort_keys=True))
        return 0
    print(
        json.dumps(
            _public_replay(
                asyncio.run(
                    run_replay(
                        args.fixture,
                    )
                )
            ),
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
