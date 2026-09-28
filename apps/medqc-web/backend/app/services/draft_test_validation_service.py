from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

VALIDATION_SCHEMA_VERSION = "fixed_test_records_v1"
_DETERMINATE_STATUSES = {"compliant", "non_compliant"}


class DraftTestValidationInvalid(ValueError):
    pass


class DraftTestValidationNotFound(LookupError):
    pass


class DraftTestValidationConflict(RuntimeError):
    pass


class DraftTestValidationResultUnknown(RuntimeError):
    pass


def _text(value: Any) -> str:
    return str(value or "").strip()


def _utc_datetime(value: Any) -> datetime | None:
    if not isinstance(value, datetime):
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            value = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _iso_utc(value: Any) -> str:
    parsed = _utc_datetime(value)
    if parsed is None:
        raise DraftTestValidationInvalid("版本时间无效")
    return parsed.isoformat()


def _uses_visual_condition(draft: Mapping[str, Any]) -> bool:
    check_logic = draft.get("check_logic")
    return isinstance(check_logic, Mapping) and "visual_condition" in check_logic


def _rule_payload(draft: Mapping[str, Any]) -> dict[str, Any]:
    check_logic = dict(draft.get("check_logic") or {})
    applicable_documents = draft.get("applicable_documents")
    if not isinstance(applicable_documents, list) or not applicable_documents:
        applicable_documents = check_logic.get("applicable_documents")
    if not isinstance(applicable_documents, list):
        applicable_documents = []
    return {
        "rule_code": _text(draft.get("rule_code") or draft.get("id") or "INLINE-DRAFT"),
        "name": _text(draft.get("name")),
        "description": _text(draft.get("description")),
        "prompt_template": _text(draft.get("prompt_template")),
        "severity": _text(draft.get("severity")) or "major",
        "document_type": _text(draft.get("document_type")) or "日常病程记录",
        "applicable_documents": applicable_documents,
        "scene": _text(draft.get("scene")) or "running",
        "execution_domain": _text(check_logic.get("execution_domain")),
        "doc_scope": _text(check_logic.get("doc_scope")) or "primary",
        "check_logic": check_logic,
    }


def _definition_is_executable(draft: Mapping[str, Any]) -> bool:
    return _uses_visual_condition(draft) or bool(_text(draft.get("prompt_template")))


def fixed_test_validation_state(draft: Mapping[str, Any]) -> tuple[bool, str | None]:
    if not _definition_is_executable(draft):
        return False, "draft_not_executable"
    if _text(draft.get("status")) != "draft":
        return False, "draft_changed"
    validation = draft.get("last_test_summary")
    if not isinstance(validation, Mapping) or validation.get("schema_version") != VALIDATION_SCHEMA_VERSION:
        return False, "not_tested"
    if _text(validation.get("draft_id")) != _text(draft.get("id")):
        return False, "validation_incomplete"
    if not _text(validation.get("validation_id")) or _utc_datetime(
        validation.get("validated_revision")
    ) is None:
        return False, "validation_incomplete"
    proof_revision = _utc_datetime(validation.get("proof_revision"))
    current_revision = _utc_datetime(draft.get("updated_at"))
    if proof_revision is None or current_revision is None or proof_revision != current_revision:
        return False, "draft_changed"
    results = validation.get("results")
    failures = validation.get("failures")
    selected = validation.get("selected_items")
    item_count = validation.get("item_count")
    if (
        type(item_count) is not int
        or not 1 <= item_count <= 20
        or not isinstance(results, list)
        or not isinstance(failures, list)
        or not isinstance(selected, list)
        or len(results) != item_count
        or len(selected) != item_count
        or failures
    ):
        return False, "validation_incomplete"

    def item_key(item: Any) -> tuple[str, str, str, str, str] | None:
        if not isinstance(item, Mapping):
            return None
        record_ref = item.get("record_ref")
        if not isinstance(record_ref, Mapping):
            return None
        item_id = _text(item.get("item_id"))
        item_updated_at = _utc_datetime(item.get("item_updated_at"))
        identity = tuple(
            _text(record_ref.get(key))
            for key in ("institute_id", "patient_id", "visit_id")
        )
        if not item_id or item_updated_at is None or not all(identity):
            return None
        return (item_id, item_updated_at.isoformat(), *identity)

    selected_keys = [item_key(item) for item in selected]
    result_keys = [item_key(item) for item in results]
    if (
        any(key is None for key in selected_keys)
        or any(key is None for key in result_keys)
        or len(set(selected_keys)) != item_count
        or set(selected_keys) != set(result_keys)
    ):
        return False, "validation_incomplete"
    result_statuses = [
        _text(item.get("status"))
        for item in results
        if isinstance(item, Mapping)
    ]
    statuses = set(result_statuses)
    if not statuses or not statuses <= _DETERMINATE_STATUSES:
        return False, "validation_incomplete"
    expected_counts = {
        "success_count": item_count,
        "failed_count": 0,
        "issue_records": result_statuses.count("non_compliant"),
        "compliant_records": result_statuses.count("compliant"),
        "unknown_count": 0,
        "technical_error_count": 0,
    }
    if any(
        type(validation.get(field)) is not int
        or validation.get(field) < 0
        or validation.get(field) != expected
        for field, expected in expected_counts.items()
    ):
        return False, "validation_incomplete"
    return True, None


def validation_view(draft: Mapping[str, Any]) -> dict[str, Any]:
    validation = draft.get("last_test_summary")
    if not isinstance(validation, dict) or validation.get("schema_version") != VALIDATION_SCHEMA_VERSION:
        validation = None
    publish_ready, unavailable_reason = fixed_test_validation_state(draft)
    return {
        "draft_id": _text(draft.get("id")),
        "draft_status": _text(draft.get("status")) or "draft",
        "draft_updated_at": draft.get("updated_at"),
        "published_rule_id": _text(draft.get("published_rule_id")) or None,
        "validation": validation,
        "publish_ready": publish_ready,
        "unavailable_reason": unavailable_reason,
    }


def _record_from_payload(payload: Mapping[str, Any], *, visual: bool) -> dict[str, Any]:
    record_ref = payload.get("record_ref")
    if not isinstance(record_ref, Mapping):
        raise DraftTestValidationInvalid("测试病历身份不可信")
    institute_id = _text(record_ref.get("institute_id"))
    patient_id = _text(record_ref.get("patient_id"))
    visit_id = _text(record_ref.get("visit_id"))
    if not all((institute_id, patient_id, visit_id)):
        raise DraftTestValidationInvalid("测试病历身份不可信")
    record = {
        "institute_id": institute_id,
        "patient_id": patient_id,
        "visit_id": visit_id,
        "record_id": visit_id,
    }
    if not visual:
        documents = payload.get("documents")
        if not isinstance(documents, list) or not documents:
            raise DraftTestValidationInvalid("测试病历缺少文书")
        segments = []
        for document in documents:
            if not isinstance(document, Mapping):
                continue
            content = _text(document.get("content"))
            if content:
                segments.append(f"【{_text(document.get('title')) or '病历文书'}】\n{content}")
        if not segments:
            raise DraftTestValidationInvalid("测试病历缺少文书")
        record["medical_text"] = "\n\n".join(segments)
    return record


def _bounded_text(value: Any, *, limit: int = 300) -> str:
    return " ".join(str(value or "").split())[:limit]


def _condition_trace_summaries(result: Mapping[str, Any]) -> list[str]:
    metadata = result.get("metadata")
    groups = metadata.get("visual_condition_trace") if isinstance(metadata, Mapping) else None
    if not isinstance(groups, list):
        return []
    summaries: list[str] = []
    for group in groups:
        conditions = group.get("conditions") if isinstance(group, Mapping) else None
        if not isinstance(conditions, list):
            continue
        for condition in conditions:
            if not isinstance(condition, Mapping):
                continue
            parts = [
                f"条件 {_bounded_text(condition.get('condition_id'), limit=60)}",
                f"判定 {_bounded_text(condition.get('truth'), limit=20)}",
            ]
            fact_key = condition.get("fact_key") or condition.get("document_type")
            if fact_key:
                parts.append(f"字段 {_bounded_text(fact_key, limit=100)}")
            if "actual" in condition:
                parts.append(f"实际值 {_bounded_text(condition.get('actual'), limit=100)}")
            if "expected" in condition:
                parts.append(f"期望值 {_bounded_text(condition.get('expected'), limit=100)}")
            if "actual_seconds" in condition:
                parts.append(f"实际秒数 {_bounded_text(condition.get('actual_seconds'), limit=40)}")
            if "threshold" in condition:
                parts.append(f"阈值 {_bounded_text(condition.get('threshold'), limit=80)}")
            summaries.append("；".join(parts)[:300])
            if len(summaries) >= 20:
                return summaries
    return summaries


class DraftTestValidationService:
    def __init__(self, *, workspace: Any, sample_pool: Any, qc_service: Any) -> None:
        self.workspace = workspace
        self.sample_pool = sample_pool
        self.qc_service = qc_service

    def get(self, *, draft_id: str, created_by: str) -> dict[str, Any]:
        draft = self.workspace.get_draft(draft_id=draft_id, created_by=created_by)
        if not draft:
            raise DraftTestValidationNotFound("草稿不存在或无权限")
        return validation_view(draft)

    async def run(
        self,
        *,
        draft_id: str,
        created_by: str,
        items: Sequence[Mapping[str, Any]],
        expected_updated_at: datetime,
    ) -> dict[str, Any]:
        if not 1 <= len(items) <= 20:
            raise DraftTestValidationInvalid("请选择 1 至 20 条测试病历")
        item_ids = [_text(item.get("item_id")) for item in items]
        if any(not item_id for item_id in item_ids) or len(set(item_ids)) != len(item_ids):
            raise DraftTestValidationInvalid("测试病历 ID 不能为空或重复")
        draft = self.workspace.get_draft(draft_id=draft_id, created_by=created_by)
        if not draft:
            raise DraftTestValidationNotFound("草稿不存在或无权限")
        if _text(draft.get("status")) != "draft":
            raise DraftTestValidationConflict("只有草稿状态可执行测试验证")
        expected_revision = _utc_datetime(expected_updated_at)
        if expected_revision is None or _utc_datetime(draft.get("updated_at")) != expected_revision:
            raise DraftTestValidationConflict("草稿已被修改，请刷新后重试")
        if not _definition_is_executable(draft):
            raise DraftTestValidationInvalid("请先配置可执行条件或非空 Prompt")

        payloads = []
        for item in items:
            expected_item_revision = item.get("expected_updated_at")
            loaded = self.sample_pool.load_customer_test_record_transfer_payloads(
                item_ids=[_text(item.get("item_id"))],
                expected_updated_at=expected_item_revision,
            )
            if len(loaded) != 1:
                raise DraftTestValidationInvalid("测试病历读取结果不唯一")
            payloads.append(loaded[0])

        visual = _uses_visual_condition(draft)
        records = [_record_from_payload(payload, visual=visual) for payload in payloads]
        if visual:
            records = self.workspace.hydrate_records_with_visual_evidence(records)
        if len(records) != len(payloads):
            raise DraftTestValidationInvalid("测试病历服务端水合结果数量不一致")
        for payload, record in zip(payloads, records):
            expected_ref = payload.get("record_ref")
            actual_ref = {
                key: _text(record.get(key))
                for key in ("institute_id", "patient_id", "visit_id")
            }
            if not isinstance(expected_ref, Mapping) or any(
                actual_ref[key] != _text(expected_ref.get(key))
                for key in actual_ref
            ):
                raise DraftTestValidationInvalid("测试病历服务端身份水合不一致")
        rule = _rule_payload(draft)
        from .custom_qc_service import evaluate_inline_rule_orchestrated

        results: list[dict[str, Any]] = []
        failures: list[dict[str, str]] = []
        selected_items: list[dict[str, Any]] = []
        for payload, record in zip(payloads, records):
            item_id = _text(payload.get("source_item_id"))
            item_updated_at = _iso_utc(payload.get("source_updated_at"))
            record_ref = dict(payload.get("record_ref") or {})
            selected_items.append({
                "item_id": item_id,
                "item_updated_at": item_updated_at,
                "record_ref": record_ref,
            })
            try:
                result = await evaluate_inline_rule_orchestrated(
                    qc_service=self.qc_service,
                    rule=rule,
                    record=record,
                )
                status = _text(result.get("status"))
                issues = result.get("issues")
                results.append({
                    "item_id": item_id,
                    "item_updated_at": item_updated_at,
                    "record_ref": record_ref,
                    "status": status,
                    "issue_count": len(issues) if isinstance(issues, list) else 0,
                    "finding": {
                        "description": _bounded_text(result.get("findings")),
                        "evidence": _bounded_text(result.get("evidence")),
                    },
                    "condition_trace": _condition_trace_summaries(result),
                })
            except Exception:
                failures.append({
                    "item_id": item_id,
                    "code": "execution_failed",
                    "message": "测试执行失败",
                })

        statuses = [_text(item.get("status")) for item in results]
        summary = {
            "schema_version": VALIDATION_SCHEMA_VERSION,
            "validation_id": str(uuid.uuid4()),
            "draft_id": draft_id,
            "validated_revision": expected_revision.isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "item_count": len(items),
            "success_count": sum(status in _DETERMINATE_STATUSES for status in statuses),
            "failed_count": len(failures),
            "issue_records": sum(status == "non_compliant" for status in statuses),
            "compliant_records": sum(status == "compliant" for status in statuses),
            "unknown_count": sum(status == "data_gap" for status in statuses),
            "technical_error_count": sum(status == "technical_error" for status in statuses),
            "selected_items": selected_items,
            "results": results,
            "failures": failures,
        }
        try:
            confirmed = self.workspace.save_fixed_test_validation_summary(
                draft_id=draft_id,
                created_by=created_by,
                expected_updated_at=expected_revision,
                summary=summary,
            )
        except (DraftTestValidationNotFound, DraftTestValidationConflict):
            raise
        except Exception as exc:
            raise DraftTestValidationResultUnknown(
                "测试验证结果未确认，请刷新后核对，不要盲目重试"
            ) from exc
        return validation_view(confirmed)


__all__ = [
    "DraftTestValidationConflict",
    "DraftTestValidationInvalid",
    "DraftTestValidationNotFound",
    "DraftTestValidationResultUnknown",
    "DraftTestValidationService",
    "VALIDATION_SCHEMA_VERSION",
    "fixed_test_validation_state",
    "validation_view",
]
