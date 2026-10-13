"""LX0609固定20例语义二审；只输出安全裁决与聚合指标。"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
from typing import Any, Callable, Mapping, Sequence

from app.services.luxian_0609.native_consultation_execution import _context as consultation_context
from app.services.luxian_0609.native_course_quality_execution import (
    _MAX_CONTEXT_CHARS as _COPY_MAX_CONTEXT_CHARS,
    _MAX_ROW_CHARS as _COPY_MAX_ROW_CHARS,
    _normalized_for_similarity,
    _row_text,
)
from app.services.luxian_0609.source_evidence_reader import read_luxian_0609_native_source_rows


from app.services.case_identity import CaseRef
from app.services.luxian_0609.llm_prompt_privacy import (
    PatientPrivacyViolation, PrivacyIdentityContextError, wrap_luxian_0609_llm_client,
)
from app.services.luxian_0609.privacy_identity_context import (
    _Luxian0609IdentityCollector, PrivacyIdentityContextUnavailable,
    build_luxian_0609_identity_provider,
)
from app.services.luxian_0609.privacy_request_scope import (
    bind_luxian_0609_identity_provider, luxian_0609_case_identity_scope, protect_current_payload,
)


SCHEMA_VERSION = "lx0609-semantic20-review-v1"
REVIEW_VERSION = "lx0609-semantic-second-review-v1"
_TARGET_COUNTS = {
    "LX0609-12-01-02": 20,
    "LX0609-03-01-01": 14,
    "LX0609-03-01-02": 16,
    "LX0609-03-01-03": 16,
    "LX0609-03-01-04": 14,
}
_TARGET_RULES = frozenset(_TARGET_COUNTS)
_BUSINESS_STATES = frozenset(
    {"compliant", "non_compliant", "not_applicable", "data_gap", "evaluation_unknown"}
)
_CONFIDENCE_BUCKETS = frozenset({"high", "medium", "low"})
_PARSE_ERROR_CODES = frozenset(
    {
        "parse_invalid_json",
        "parse_missing",
        "parse_invalid_state",
        "parse_invalid_confidence",
        "parse_invalid_reason",
        "privacy_boundary_error", "transport_error",
        "source_error",
    }
)
_REASONS_BY_RULE = {
    "LX0609-12-01-02": frozenset(
        {
            "substantive_dynamic_update_present",
            "unreasonable_copy_present",
            "unreasonable_copy_not_established",
            "insufficient_comparable_records",
            "source_incomplete",
        }
    ),
    "LX0609-03-01-01": frozenset(
        {
            "execution_record_present",
            "execution_record_missing",
            "execution_link_uncertain",
            "source_incomplete",
        }
    ),
    "LX0609-03-01-02": frozenset(
        {"purpose_clear", "purpose_vague", "purpose_missing", "source_incomplete"}
    ),
    "LX0609-03-01-03": frozenset(
        {"opinion_clear", "opinion_vague", "opinion_missing", "source_incomplete"}
    ),
    "LX0609-03-01-04": frozenset(
        {
            "execution_specific",
            "execution_vague_or_copied",
            "execution_record_absent",
            "execution_link_uncertain",
            "source_incomplete",
        }
    ),
}
_CASE_RE = re.compile(r"^case-(?:0[1-9]|1[0-9]|20)$")
_RULE_RE = re.compile(r"^LX0609-\d{2}-\d{2}-\d{2}$")
_CODE_RE = re.compile(r"^[a-z][a-z0-9_]{0,127}$")
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_FORBIDDEN_KEYS = frozenset(
    {
        "institute_id", "patient_id", "visit_id", "record_content", "record_time",
        "prompt", "raw_response", "medical_text", "sql", "coordinates",
    }
)
_ROW_KEYS = frozenset(
    {
        "case_label", "rule_id", "candidate_state", "candidate_reason_code",
        "review_status", "review_state", "review_reason_code", "confidence_bucket",
        "agreement", "evidence_ref_hashes",
    }
)

RowLoader = Callable[..., Sequence[Mapping[str, Any]]]


class SemanticReviewContractError(ValueError):
    """固定20例二审合同错误；消息不回显输入。"""


def _case_rows(case_map: Mapping[str, Any]) -> tuple[dict[str, str], ...]:
    rows = case_map.get("cases") if isinstance(case_map, Mapping) else None
    if not isinstance(rows, list) or len(rows) != 20:
        raise SemanticReviewContractError("case map must contain exactly 20 cases")
    result: list[dict[str, str]] = []
    for index, raw in enumerate(rows, start=1):
        if not isinstance(raw, Mapping):
            raise SemanticReviewContractError("invalid case map")
        label = str(raw.get("case_label") or "").strip()
        coordinates = {
            key: str(raw.get(key) or "").strip()
            for key in ("institute_id", "patient_id", "visit_id")
        }
        if label != f"case-{index:02d}" or not _CASE_RE.fullmatch(label):
            raise SemanticReviewContractError("invalid case labels")
        if any(not value or len(value) > 256 for value in coordinates.values()):
            raise SemanticReviewContractError("invalid case coordinates")
        result.append({"case_label": label, **coordinates})
    return tuple(result)


def _review_rows(review_queue: Sequence[Mapping[str, Any]]) -> tuple[dict[str, str], ...]:
    if not isinstance(review_queue, Sequence) or isinstance(review_queue, (str, bytes)):
        raise SemanticReviewContractError("invalid review queue")
    selected: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for raw in review_queue:
        if not isinstance(raw, Mapping) or raw.get("review_status") != "needs_second_review":
            continue
        label = str(raw.get("case_label") or "").strip()
        rule_id = str(raw.get("rule_id") or "").strip().upper()
        key = (label, rule_id)
        if rule_id not in _TARGET_RULES or not _CASE_RE.fullmatch(label) or key in seen:
            raise SemanticReviewContractError("invalid second review queue")
        seen.add(key)
        selected.append({"case_label": label, "rule_id": rule_id})
    counts = Counter(row["rule_id"] for row in selected)
    if len(selected) != 80 or dict(sorted(counts.items())) != _TARGET_COUNTS:
        raise SemanticReviewContractError("second review queue must contain exact 80 rows")
    return tuple(selected)


def _candidate_index(candidate: Mapping[str, Any]) -> dict[tuple[str, str], Mapping[str, Any]]:
    rows = candidate.get("rows") if isinstance(candidate, Mapping) else None
    if not isinstance(rows, list) or len(rows) != 980:
        raise SemanticReviewContractError("candidate must contain exact 980 rows")
    result: dict[tuple[str, str], Mapping[str, Any]] = {}
    for raw in rows:
        if not isinstance(raw, Mapping):
            raise SemanticReviewContractError("invalid candidate row")
        key = (
            str(raw.get("case_label") or "").strip(),
            str(raw.get("rule_id") or "").strip().upper(),
        )
        if not _CASE_RE.fullmatch(key[0]) or not _RULE_RE.fullmatch(key[1]) or key in result:
            raise SemanticReviewContractError("invalid candidate identity")
        result[key] = raw
    return result


def _response_content(response: Mapping[str, Any]) -> str:
    choices = response.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], Mapping):
        message = choices[0].get("message")
        if isinstance(message, Mapping):
            return str(message.get("content") or "")
    return str(response.get("content") or response.get("text") or "")


def _extract_json_payload(content: str) -> Mapping[str, Any] | list[Any] | None:
    """只提取完整JSON值；兼容think/围栏/首尾杂文，不从自由文本猜状态。"""

    cleaned = re.sub(r"<think>[\s\S]*?</think>", "", str(content or "")).strip()
    cleaned = re.sub(r"```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
    try:
        payload = json.loads(cleaned)
    except (TypeError, ValueError):
        decoder = json.JSONDecoder()
        payload = None
        for index, character in enumerate(cleaned):
            if character not in "[{":
                continue
            try:
                candidate, _end = decoder.raw_decode(cleaned[index:])
            except ValueError:
                continue
            if isinstance(candidate, (Mapping, list)):
                payload = candidate
                break
    return payload if isinstance(payload, (Mapping, list)) else None


def _parse_reviews(response: Mapping[str, Any], expected: Sequence[str]) -> dict[str, dict[str, Any]]:
    payload = _extract_json_payload(_response_content(response))
    if payload is None:
        return {rule_id: {"error_code": "parse_invalid_json"} for rule_id in expected}
    rows = payload.get("reviews") if isinstance(payload, Mapping) else payload
    if not isinstance(rows, list):
        return {rule_id: {"error_code": "parse_invalid_json"} for rule_id in expected}
    selected_rows: dict[str, Mapping[str, Any]] = {}
    for raw in rows:
        if not isinstance(raw, Mapping):
            continue
        rule_id = str(raw.get("rule_id") or "").strip().upper()
        # 未选规则可能由模型多答；忽略但绝不进入安全输出。
        if rule_id not in expected or rule_id in selected_rows:
            continue
        selected_rows[rule_id] = raw

    parsed: dict[str, dict[str, Any]] = {}
    for rule_id in expected:
        raw = selected_rows.get(rule_id)
        if raw is None:
            parsed[rule_id] = {"error_code": "parse_missing"}
            continue
        state = str(raw.get("state") or "").strip().lower()
        confidence = str(raw.get("confidence_bucket") or "").strip().lower()
        reason = str(raw.get("reason_code") or "").strip().lower()
        if confidence not in _CONFIDENCE_BUCKETS:
            parsed[rule_id] = {"error_code": "parse_invalid_confidence"}
            continue
        if rule_id == "LX0609-12-01-02":
            # 无可比材料仍允许模型按先前合同返回明确NA。
            if state == "not_applicable" and reason == "insufficient_comparable_records":
                parsed[rule_id] = {
                    "state": state, "confidence": confidence, "reason": reason,
                }
                continue
            updates = raw.get("substantive_updates")
            if not isinstance(updates, Mapping) or set(updates) != {
                "symptom", "objective", "assessment", "plan"
            } or any(not isinstance(updates[key], bool) for key in updates):
                parsed[rule_id] = {"error_code": "parse_invalid_state"}
                continue
            template_only = raw.get("template_only_overlap")
            unreasonable_copy = raw.get("unreasonable_copy")
            if not isinstance(template_only, bool) or unreasonable_copy not in {True, False, None}:
                parsed[rule_id] = {"error_code": "parse_invalid_state"}
                continue
            if reason not in _REASONS_BY_RULE[rule_id]:
                parsed[rule_id] = {"error_code": "parse_invalid_reason"}
                continue
            has_dynamic_update = any(bool(updates[key]) for key in updates)
            # 文书自身已证明有动态更新或仅模板重叠时，优先确认合规；
            # 不允许模型对“是否复制”的低置信结论覆盖这些强事实。
            if template_only or has_dynamic_update:
                state = "compliant"
                reason = (
                    "substantive_dynamic_update_present"
                    if has_dynamic_update
                    else "unreasonable_copy_not_established"
                )
            elif confidence != "high" or unreasonable_copy is None:
                state, reason = "evaluation_unknown", "semantic_low_confidence"
            elif unreasonable_copy:
                state, reason = "non_compliant", "unreasonable_copy_present"
            else:
                state, reason = "compliant", "unreasonable_copy_not_established"
            parsed[rule_id] = {"state": state, "confidence": confidence, "reason": reason}
            continue
        if state not in _BUSINESS_STATES:
            parsed[rule_id] = {"error_code": "parse_invalid_state"}
            continue
        if reason not in _REASONS_BY_RULE[rule_id]:
            parsed[rule_id] = {"error_code": "parse_invalid_reason"}
            continue
        parsed[rule_id] = {"state": state, "confidence": confidence, "reason": reason}
    return parsed


def _usage(response: Mapping[str, Any]) -> dict[str, int]:
    raw = response.get("usage")
    raw = raw if isinstance(raw, Mapping) else {}
    def safe_int(value: Any) -> int:
        try:
            return max(0, int(value or 0))
        except (TypeError, ValueError):
            return 0
    return {key: safe_int(raw.get(key)) for key in (
        "prompt_tokens", "completion_tokens", "total_tokens"
    )}


def _evidence_hashes(*, case_label: str, sources: Mapping[str, Sequence[Mapping[str, Any]]]) -> list[str]:
    hashes: list[str] = []
    for source_key in sorted(sources):
        material = json.dumps(
            list(sources[source_key]), ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            default=str,
        )
        hashes.append(sha256(f"{REVIEW_VERSION}|{case_label}|{source_key}|{material}".encode()).hexdigest())
    return hashes


def _copy_review_context(
    rows_by_source: Mapping[str, Sequence[Mapping[str, Any]]],
) -> tuple[str, dict[str, Any]]:
    """始终选择最高相似的一对受控病程，避免生产强判路径丢失二审材料。"""

    comparable: list[tuple[str, str, str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for source_key in ("daily_course_record", "senior_course_record"):
        for raw in rows_by_source.get(source_key) or ():
            if not isinstance(raw, Mapping):
                continue
            content = _row_text(raw)
            normalized = _normalized_for_similarity(content)
            if not normalized:
                continue
            document_id = str(raw.get("document_id") or "").strip()
            identity = (
                source_key,
                "document_id" if document_id else str(raw.get("record_time") or "").strip(),
                document_id or normalized,
            )
            if identity in seen:
                continue
            seen.add(identity)
            comparable.append((source_key, normalized, content, identity[1]))
    metrics: dict[str, Any] = {
        "comparable_document_count": len(comparable),
        "maximum_similarity": 0.0,
        "best_match_source_types": [],
    }
    if len(comparable) < 2:
        return "无可比材料：当前就诊少于两份实质日常病程/上级医师查房记录。", metrics
    maximum = -1.0
    best_pair: tuple[str, str, str, str] | None = None
    for index, (left_source, left, left_content, _left_identity) in enumerate(comparable):
        for right_source, right, right_content, _right_identity in comparable[index + 1 :]:
            similarity = SequenceMatcher(None, left, right, autojunk=False).ratio()
            if similarity > maximum:
                maximum = similarity
                best_pair = (left_source, left_content, right_source, right_content)
    if best_pair is None:
        return "无可比材料：当前就诊未形成有效文书对。", metrics
    metrics.update(
        {
            "maximum_similarity": round(max(maximum, 0.0), 4),
            "best_match_source_types": [best_pair[0], best_pair[2]],
        }
    )
    context = (
        f"[Python候选] 两份当前就诊病程的精确全文相似度={max(maximum, 0.0) * 100:.2f}%。\n"
        f"[文书A:{best_pair[0]}]\n{best_pair[1][:_COPY_MAX_ROW_CHARS]}\n"
        f"[文书B:{best_pair[2]}]\n{best_pair[3][:_COPY_MAX_ROW_CHARS]}"
    )[:_COPY_MAX_CONTEXT_CHARS]
    return context, metrics


def _copy_prompt(context: str, safe_metrics: Mapping[str, Any]) -> str:
    return (
        "本次规则=[LX0609-12-01-02]。你是LX0609独立语义二审器。只复核LX0609-12-01-02，不参考候选结果。"
        "模板重复不等于复制；只有核心临床内容大段复用且缺少当日变化才是不合规。"
        "空白、签名、标题和固定格式壳本身不是复制证据。不得输出正文、引文或时间。\n"
        f"安全指标={json.dumps(dict(safe_metrics), ensure_ascii=False, sort_keys=True)}\n"
        f"裁剪上下文={context or '无可用灰区上下文'}\n"
        "只输出JSON：{\"reviews\":[{\"rule_id\":\"LX0609-12-01-02\","
        "\"substantive_updates\":{\"symptom\":true/false,\"objective\":true/false,"
        "\"assessment\":true/false,\"plan\":true/false},"
        "\"template_only_overlap\":true/false,\"unreasonable_copy\":true/false/null,"
        "\"confidence_bucket\":\"high|medium|low\",\"reason_code\":"
        "\"substantive_dynamic_update_present|unreasonable_copy_present|"
        "unreasonable_copy_not_established|insufficient_comparable_records|source_incomplete\"}]}"
    )


def _consultation_prompt(rule_ids: Sequence[str], context: str) -> str:
    return (
        "本次规则=[" + ",".join(rule_ids) + "]。"
        + "你是LX0609独立语义二审器。只复核下列会诊规则，不参考候选结果："
        + ",".join(rule_ids)
        + "。仅使用当前就诊裁剪会诊记录与相关病程；不得输出正文、引文或时间。\n"
        + "业务口径：LX0609-03-01-01逐张会诊判断是否存在可唯一绑定的执行记录；笼统‘遵会诊意见’算有执行记录，"
        + "但其质量由LX0609-03-01-04判断。LX0609-03-01-02只看申请段，具体症状、检查、诊断或评估任一项即目的明确。"
        + "LX0609-03-01-03只看意见段，明确诊断或可执行的检查、治疗、用药、复查任一项即意见明确。"
        + "LX0609-03-01-04逐张判断执行质量，笼统执行或照抄意见=non_compliant，完全没有执行记录=not_applicable；"
        + "关联不唯一=evaluation_unknown而不是data_gap；只有来源读取失败或正文缺失=data_gap。\n"
        + "只能返回本次规则列表中的ID，不能返回任何未选规则。\n"
        + f"裁剪上下文={context or '无可用裁剪上下文'}\n"
        + "只输出JSON对象reviews数组；每条必须含rule_id、state、confidence_bucket、reason_code。"
        + "state仅compliant/non_compliant/not_applicable/data_gap/evaluation_unknown；confidence_bucket仅high/medium/low。"
        + "规则原因严格限定：020=execution_record_present/execution_record_missing/execution_link_uncertain/source_incomplete；"
        + "021=purpose_clear/purpose_vague/purpose_missing/source_incomplete；"
        + "022=opinion_clear/opinion_vague/opinion_missing/source_incomplete；"
        + "023=execution_specific/execution_vague_or_copied/execution_record_absent/"
        + "execution_link_uncertain/source_incomplete。"
    )


def _review_error_rows(
    targets: Sequence[Mapping[str, str]], candidates: Mapping[tuple[str, str], Mapping[str, Any]],
    evidence_hashes: Sequence[str], reason_code: str,
) -> list[dict[str, Any]]:
    if reason_code not in _PARSE_ERROR_CODES:
        raise SemanticReviewContractError("invalid review error code")
    return [
        _output_row(
            target=target, candidate=candidates[(target["case_label"], target["rule_id"])],
            review_status="review_error", review_state="evaluation_unknown",
            review_reason=reason_code, confidence="low", evidence_hashes=evidence_hashes,
        )
        for target in targets
    ]


def _output_row(
    *, target: Mapping[str, str], candidate: Mapping[str, Any], review_status: str,
    review_state: str, review_reason: str, confidence: str, evidence_hashes: Sequence[str],
) -> dict[str, Any]:
    candidate_state = str(candidate.get("observed_state") or "").strip().lower()
    candidate_reason = str(candidate.get("observed_reason_code") or "").strip().lower()
    return {
        "case_label": target["case_label"],
        "rule_id": target["rule_id"],
        "candidate_state": candidate_state,
        "candidate_reason_code": candidate_reason,
        "review_status": review_status,
        "review_state": review_state,
        "review_reason_code": review_reason,
        "confidence_bucket": confidence,
        "agreement": candidate_state == review_state if review_status == "completed" else None,
        "evidence_ref_hashes": list(evidence_hashes),
    }


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


async def build_semantic20_review(
    *, case_map: Mapping[str, Any], candidate: Mapping[str, Any],
    review_queue: Sequence[Mapping[str, Any]], llm_client: Any,
    row_loader: RowLoader = read_luxian_0609_native_source_rows,
    _private_identity_collector: _Luxian0609IdentityCollector | None = None,
) -> dict[str, Any]:
    cases = _case_rows(case_map)
    targets = _review_rows(review_queue)
    candidates = _candidate_index(candidate)
    if any((row["case_label"], row["rule_id"]) not in candidates for row in targets):
        raise SemanticReviewContractError("candidate is missing a review target")
    targets_by_case: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in targets:
        targets_by_case[row["case_label"]].append(row)

    output_rows: list[dict[str, Any]] = []
    token_usage = Counter()
    call_count = 0
    for case in cases:
        case_targets = targets_by_case.get(case["case_label"], [])
        coordinates = tuple(case[key] for key in ("institute_id", "patient_id", "visit_id"))
        try:
            source_provider = _source_identity_provider(_private_identity_collector, coordinates)
            source_provider()
        except PrivacyIdentityContextUnavailable:
            output_rows.extend(_review_error_rows(case_targets, candidates, [], "privacy_boundary_error"))
            continue
        with luxian_0609_case_identity_scope(case_coordinates=coordinates, identity_provider=source_provider):
            cache: dict[str, list[Mapping[str, Any]]] = {}

            def rows(source_key: str) -> list[Mapping[str, Any]]:
                if source_key not in cache:
                    cache[source_key] = list(
                        row_loader(
                            source_key=source_key, institute_id=case["institute_id"],
                            patient_id=case["patient_id"], visit_id=case["visit_id"], source_schema=None,
                        )
                    )
                return cache[source_key]

            copy_targets = [row for row in case_targets if row["rule_id"] == "LX0609-12-01-02"]
            if copy_targets:
                try:
                    source_rows = {
                        key: rows(key) for key in ("daily_course_record", "senior_course_record")
                    }
                    review_context, safe_metrics = _copy_review_context(source_rows)
                    hashes = _evidence_hashes(case_label=case["case_label"], sources=source_rows)
                except Exception:
                    output_rows.extend(
                        _review_error_rows(copy_targets, candidates, [], "source_error")
                    )
                else:
                    try:
                        identity_provider = _bind_script_identity(
                            source_provider, coordinates,
                            evidence_payload={"programmatic_timeline": {"structured_source_rows": dict(cache)}},
                        )
                        identity_provider()
                        guarded_client = wrap_luxian_0609_llm_client(llm_client, identity_provider=identity_provider)
                        protected = protect_current_payload({"messages": [{"role": "user", "content": _copy_prompt(review_context, safe_metrics)}]})
                        call_count += 1
                        response = await guarded_client.generate(protected["messages"][0]["content"])
                    except (PrivacyIdentityContextUnavailable, PrivacyIdentityContextError, PatientPrivacyViolation):
                        output_rows.extend(_review_error_rows(copy_targets, candidates, hashes, "privacy_boundary_error"))
                    except Exception:
                        output_rows.extend(
                            _review_error_rows(copy_targets, candidates, hashes, "transport_error")
                        )
                    else:
                        token_usage.update(_usage(response))
                        parsed = _parse_reviews(response, ("LX0609-12-01-02",))["LX0609-12-01-02"]
                        error_code = parsed.get("error_code")
                        if error_code:
                            output_rows.extend(
                                _review_error_rows(copy_targets, candidates, hashes, str(error_code))
                            )
                        else:
                            output_rows.append(
                                _output_row(
                                    target=copy_targets[0],
                                    candidate=candidates[(case["case_label"], "LX0609-12-01-02")],
                                    review_status="completed", review_state=str(parsed["state"]),
                                    review_reason=str(parsed["reason"]),
                                    confidence=str(parsed["confidence"]), evidence_hashes=hashes,
                                )
                            )

            consultation_targets = [row for row in case_targets if row["rule_id"] != "LX0609-12-01-02"]
            if consultation_targets:
                try:
                    source_rows = {
                        key: rows(key)
                        for key in ("consultation_record", "daily_course_record", "senior_course_record")
                    }
                    hashes = _evidence_hashes(case_label=case["case_label"], sources=source_rows)
                    rule_ids = tuple(row["rule_id"] for row in consultation_targets)
                except Exception:
                    output_rows.extend(
                        _review_error_rows(consultation_targets, candidates, [], "source_error")
                    )
                else:
                    try:
                        identity_provider = _bind_script_identity(
                            source_provider, coordinates,
                            evidence_payload={"programmatic_timeline": {"structured_source_rows": dict(cache)}},
                        )
                        identity_provider()
                        guarded_client = wrap_luxian_0609_llm_client(llm_client, identity_provider=identity_provider)
                        protected = protect_current_payload({"messages": [{"role": "user", "content": _consultation_prompt(rule_ids, consultation_context(source_rows))}]})
                        call_count += 1
                        response = await guarded_client.generate(protected["messages"][0]["content"])
                    except (PrivacyIdentityContextUnavailable, PrivacyIdentityContextError, PatientPrivacyViolation):
                        output_rows.extend(_review_error_rows(consultation_targets, candidates, hashes, "privacy_boundary_error"))
                    except Exception:
                        output_rows.extend(
                            _review_error_rows(
                                consultation_targets, candidates, hashes, "transport_error"
                            )
                        )
                    else:
                        token_usage.update(_usage(response))
                        parsed = _parse_reviews(response, rule_ids)
                        for target in consultation_targets:
                            result = parsed[target["rule_id"]]
                            error_code = result.get("error_code")
                            if error_code:
                                output_rows.extend(
                                    _review_error_rows(
                                        [target], candidates, hashes, str(error_code)
                                    )
                                )
                                continue
                            state, reason = str(result["state"]), str(result["reason"])
                            if result["confidence"] != "high":
                                state, reason = "evaluation_unknown", "semantic_low_confidence"
                            output_rows.append(
                                _output_row(
                                    target=target,
                                    candidate=candidates[(case["case_label"], target["rule_id"])],
                                    review_status="completed", review_state=state,
                                    review_reason=reason, confidence=str(result["confidence"]),
                                    evidence_hashes=hashes,
                                )
                            )

    order = {(row["case_label"], row["rule_id"]): index for index, row in enumerate(targets)}
    output_rows.sort(key=lambda row: order[(row["case_label"], row["rule_id"])])
    state_counts = Counter(row["review_state"] for row in output_rows)
    output = {
        "schema_version": SCHEMA_VERSION,
        "review_version": REVIEW_VERSION,
        "rows": output_rows,
        "summary": {
            "review_count": len(output_rows),
            "completed_count": sum(row["review_status"] == "completed" for row in output_rows),
            "review_error_count": sum(row["review_status"] == "review_error" for row in output_rows),
            "agreement_count": sum(row["agreement"] is True for row in output_rows),
            "rule_counts": dict(sorted(Counter(row["rule_id"] for row in output_rows).items())),
            "state_counts": dict(sorted(state_counts.items())),
            "review_error_reason_counts": dict(
                sorted(
                    Counter(
                        row["review_reason_code"]
                        for row in output_rows
                        if row["review_status"] == "review_error"
                    ).items()
                )
            ),
        },
        "usage": {
            "call_count": call_count,
            "prompt_tokens": token_usage["prompt_tokens"],
            "completion_tokens": token_usage["completion_tokens"],
            "total_tokens": token_usage["total_tokens"],
        },
    }
    _validate_safe_output(output)
    return output


def _validate_safe_output(output: Mapping[str, Any]) -> None:
    if set(output) != {"schema_version", "review_version", "rows", "summary", "usage"}:
        raise SemanticReviewContractError("unsafe output shape")
    rows = output.get("rows")
    if not isinstance(rows, list) or len(rows) != 80:
        raise SemanticReviewContractError("unsafe output shape")
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != _ROW_KEYS:
            raise SemanticReviewContractError("unsafe output row")
        if not _CASE_RE.fullmatch(str(row["case_label"])) or not _RULE_RE.fullmatch(str(row["rule_id"])):
            raise SemanticReviewContractError("unsafe output identity")
        for key in ("candidate_state", "candidate_reason_code", "review_status", "review_state", "review_reason_code", "confidence_bucket"):
            value = str(row[key] or "")
            if value and not _CODE_RE.fullmatch(value):
                raise SemanticReviewContractError("unsafe output code")
        if any(not _HASH_RE.fullmatch(str(item)) for item in row["evidence_ref_hashes"]):
            raise SemanticReviewContractError("unsafe evidence reference")

    def visit(value: Any) -> None:
        if isinstance(value, Mapping):
            if any(str(key).lower() in _FORBIDDEN_KEYS for key in value):
                raise SemanticReviewContractError("unsafe output key")
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)
    visit(output)


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        raise SemanticReviewContractError("input unavailable or invalid") from None


def _build_llm_client() -> Any:
    from app.services.llm_config_loader import build_adjudicator_runtime_config
    from app.services.qc_llm_client import SichuanQCLLMClient
    return SichuanQCLLMClient(build_adjudicator_runtime_config())


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LX0609固定20例语义二审")
    parser.add_argument("--case-map", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--review-queue", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    _parse_args(argv)
    # 独立CLI无合法collect内存来源，不能读JSON中的三ID后直接外发。
    print("LX0609 semantic20 requires trusted in-memory identity source", file=sys.stderr)
    return 1



if __name__ == "__main__":
    raise SystemExit(main())
