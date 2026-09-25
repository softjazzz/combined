"""qc-detail 正式 0609 交付边界：只从已发布 Canonical Envelope 读取。

覆盖合同：

1. ``items_json`` 里的 0609 原始项永不进入客户可见结果（红→绿）；
2. Canonical ``state == "ready"`` 时只搬运 ``conclusion``/``suggestion``/``status``，
   缺必需字段或条目非 dict 时受控无结果，不用旧内部字段兜底；
3. 身份以当前规则集/版本的 Envelope 唯一三坐标为准，CDM 只做一致性核对；
4. Canonical 缺失、损坏、身份缺失或歧义时受控返回无 0609 结果；
5. 非 0609 legacy 结果保持原行为；
6. 受控失败不会经路由总 catch 变成 500，响应不回显原文，只透传受控状态。

全部使用合成记录，不连接任何数据库。
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any

import pytest

import app.routers.records as records


MALICIOUS_TEXT = "恶意篡改文本-绝不应出现在客户结果"
RULE_SET_KEY = "luxian_0609_qc_v1"
RULE_SET_VERSION = "2026-06-09"
ENVELOPE_IDENTITY = ("inst-1", "patient-1", "visit-1")


class _FakeRows:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def mappings(self) -> "_FakeRows":
        return self

    def all(self) -> list[dict[str, Any]]:
        return self._rows


class _FakeConnection:
    def __init__(self, engine: "_FakeEngine") -> None:
        self._engine = engine

    def execute(self, statement: Any, params: Any = None) -> _FakeRows:
        self._engine.executed.append((str(statement), dict(params or {})))
        return _FakeRows(self._engine.rows)

    def __enter__(self) -> "_FakeConnection":
        return self

    def __exit__(self, *_exc: Any) -> bool:
        return False


class _FakeEngine:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.executed: list[tuple[str, dict[str, Any]]] = []

    def connect(self) -> _FakeConnection:
        return _FakeConnection(self)


def _raw_0609_item(**overrides: Any) -> dict[str, Any]:
    item = {
        "record_id": "visit-1",
        "visit_id": "visit-1",
        "rule_code": "LX0609-06-01-02",
        "rule_name": "CT/MRI 检查记录",
        "status": "non_compliant",
        "findings": MALICIOUS_TEXT,
        "evidence": MALICIOUS_TEXT,
        "suggestion": MALICIOUS_TEXT,
    }
    item.update(overrides)
    return item


def _published_canonical_item(**overrides: Any) -> dict[str, Any]:
    item = {
        "record_id": "visit-1",
        "visit_id": "visit-1",
        "rule_id": "LX0609-06-01-02",
        "rule_name": "CT/MRI 检查记录：报告后 24 小时内病程未记录",
        "qc_point": "CT/MRI 检查记录符合率",
        "source_document": "CT/MRI 检查记录",
        "status": "non_compliant",
        "result_status": "non_compliant",
        "display_status": "non_compliant",
        "is_compliant": False,
        "reason_code": "course_record_missing",
        "conclusion": "已发布结论：报告出具后 24 小时内病程未记录",
        "suggestion": "已发布建议：请在病程中补充记录",
        "evidence": [
            {
                "source_type": "exam_report",
                "source_label": "CT 报告",
                "record_time": "2025-08-12 18:59:19",
                "evidence_excerpt": "报告时间 2025-08-12 18:59:19",
                "excerpt_kind": "文书级依据",
            }
        ],
        "customer_display_facts": {},
    }
    item.update(overrides)
    return item


def _install_engine(
    monkeypatch: pytest.MonkeyPatch, rows: list[dict[str, Any]]
) -> _FakeEngine:
    engine = _FakeEngine(rows)
    monkeypatch.setattr(records, "engine", engine)
    return engine


def _patch_identity(
    monkeypatch: pytest.MonkeyPatch,
    *,
    record_id: str = "visit-1",
    envelope: bool = True,
    cdm: bool = True,
) -> None:
    """默认让当前 Envelope 与 CDM 三坐标一致。"""

    monkeypatch.setattr(
        records,
        "_resolve_visit_identity",
        lambda _rid: (
            {
                "institute_id": "inst-1",
                "patient_id": "patient-1",
                "visit_id": record_id,
            }
            if cdm
            else {}
        ),
    )
    monkeypatch.setattr(
        records,
        "_luxian_0609_envelope_identities",
        lambda _rid, **_kw: {("inst-1", "patient-1", record_id)} if envelope else set(),
    )


def _patch_canonical_result(
    monkeypatch: pytest.MonkeyPatch, result: Any, *, raises: bool = False
) -> list[dict[str, Any]]:
    import app.services.custom_qc_workspace_service as workspace_module

    calls: list[dict[str, Any]] = []

    def _fake(_self: Any, **kwargs: Any) -> Any:
        calls.append(kwargs)
        if raises:
            raise RuntimeError(f"canonical unavailable: {MALICIOUS_TEXT}")
        return result

    monkeypatch.setattr(
        workspace_module.CustomQCWorkspaceService,
        "get_latest_luxian_0609_record_result",
        _fake,
    )
    return calls


async def _call_qc_detail(record_id: str) -> dict[str, Any]:
    request = SimpleNamespace(state=SimpleNamespace())
    return await records.get_record_qc_detail(
        request=request,
        record_id=record_id,
        current_user={"id": "u-1", "roles": ["admin"]},
    )


# --- 1. 原始 items_json 交付边界 ------------------------------------------------


def test_raw_luxian_0609_items_json_is_never_returned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """红测试：修复前原始 0609 项会带篡改文本直接进入客户结果。"""

    _install_engine(
        monkeypatch,
        [
            {
                "id": "job-raw",
                "created_at": "2026-09-01T00:00:00",
                "items_json": json.dumps([_raw_0609_item()], ensure_ascii=False),
            }
        ],
    )

    payload = records._load_review_items_from_latest_batch("visit-1")

    assert payload["review_items"] == []
    assert MALICIOUS_TEXT not in json.dumps(payload, ensure_ascii=False)


def test_mixed_items_json_only_filters_luxian_0609_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_engine(
        monkeypatch,
        [
            {
                "id": "job-mixed",
                "created_at": "2026-09-01T00:00:00",
                "items_json": json.dumps(
                    [
                        _raw_0609_item(),
                        {
                            "record_id": "visit-1",
                            "rule_code": "SC-014",
                            "rule_name": "细菌培养结果在病程中未记录",
                            "status": "non_compliant",
                            "findings": "legacy 结论",
                        },
                    ],
                    ensure_ascii=False,
                ),
            }
        ],
    )

    payload = records._load_review_items_from_latest_batch("visit-1")

    assert [item["rule_code"] for item in payload["review_items"]] == ["SC-014"]
    assert MALICIOUS_TEXT not in json.dumps(payload, ensure_ascii=False)


def test_non_luxian_legacy_items_keep_original_mapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_engine(
        monkeypatch,
        [
            {
                "id": "job-legacy",
                "created_at": "2026-09-02T00:00:00",
                "items_json": json.dumps(
                    [
                        {
                            "record_id": "visit-legacy",
                            "rule_code": "SC-020",
                            "rule_name": "会诊记录",
                            "status": "未知状态",
                            "findings": "legacy 判定说明",
                        }
                    ],
                    ensure_ascii=False,
                ),
            }
        ],
    )

    payload = records._load_review_items_from_latest_batch("visit-legacy")

    assert len(payload["review_items"]) == 1
    legacy_item = payload["review_items"][0]
    assert legacy_item["source"] == "batch_job"
    assert legacy_item["rule_code"] == "SC-020"
    # 既有 legacy 归一化行为保持不变：未知状态仍收敛为 uncertain。
    assert legacy_item["status"] == "uncertain"
    assert payload["review_job"]["id"] == "job-legacy"


# --- 2. Canonical ready 只搬运已发布字段 ----------------------------------------


def test_canonical_ready_maps_published_fields_without_regeneration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_identity(monkeypatch)
    calls = _patch_canonical_result(
        monkeypatch,
        {"state": "ready", "job_id": "job-canonical", "items": [_published_canonical_item()]},
    )

    payload = records._load_luxian_0609_review_items_from_canonical("visit-1")

    assert calls and calls[0]["visit_id"] == "visit-1"
    assert payload["state"] == "ready"
    assert payload["review_job"]["id"] == "job-canonical"
    item = payload["review_items"][0]
    assert item["source"] == "canonical_result_envelope"
    assert item["rule_code"] == "LX0609-06-01-02"
    assert item["rule_name"] == "CT/MRI 检查记录符合率"
    assert item["document_type"] == "CT/MRI 检查记录"
    assert item["status"] == "non_compliant"
    assert item["findings"] == "已发布结论：报告出具后 24 小时内病程未记录"
    assert item["suggestion"] == "已发布建议：请在病程中补充记录"
    # 证据是已发布摘要字符串，不是内部 evidence 的 str(list)。
    assert isinstance(item["evidence"], str)
    assert "报告时间 2025-08-12 18:59:19" in item["evidence"]
    assert "[{" not in item["evidence"]


@pytest.mark.parametrize("status", ["data_gap", "uncertain", "not_executed"])
def test_canonical_wider_status_is_passed_through_verbatim(
    monkeypatch: pytest.MonkeyPatch, status: str
) -> None:
    """共享 wider status 不得被后端强行改写成 uncertain。"""

    _patch_identity(monkeypatch)
    _patch_canonical_result(
        monkeypatch,
        {
            "state": "ready",
            "job_id": "job-wider",
            "items": [
                _published_canonical_item(
                    status=status,
                    result_status=status,
                    display_status=status,
                    is_compliant=None,
                )
            ],
        },
    )

    payload = records._load_luxian_0609_review_items_from_canonical("visit-1")

    assert payload["review_items"][0]["status"] == status


@pytest.mark.parametrize(
    "broken_item",
    [
        {"customer_conclusion": MALICIOUS_TEXT, "detail": MALICIOUS_TEXT},
        {"findings": MALICIOUS_TEXT, "conclusion": "   "},
        "非 dict 条目：" + MALICIOUS_TEXT,
    ],
    ids=["legacy_keys_only", "blank_conclusion", "non_dict_item"],
)
def test_canonical_ready_requires_published_fields_without_legacy_fallback(
    monkeypatch: pytest.MonkeyPatch, broken_item: Any
) -> None:
    """缺必需字段或条目非 dict 时受控无结果，不拼旧内部形状。"""

    _patch_identity(monkeypatch)
    if isinstance(broken_item, dict):
        item = dict(_published_canonical_item())
        item.pop("conclusion", None)
        item.update(broken_item)
        items: list[Any] = [item]
    else:
        items = [_published_canonical_item(), broken_item]
    _patch_canonical_result(monkeypatch, {"state": "ready", "job_id": "job-x", "items": items})

    payload = records._load_luxian_0609_review_items_from_canonical("visit-1")

    assert payload["review_items"] == []
    assert payload["state"] == "technical_error"
    assert MALICIOUS_TEXT not in json.dumps(payload, ensure_ascii=False)


# --- 3. Canonical 缺失 / 损坏 / 身份边界 ---------------------------------------


@pytest.mark.parametrize(
    ("state", "expected"),
    [("not_found", "not_found"), ("technical_error", "technical_error"),
     ("multiple_candidates", "technical_error")],
)
def test_canonical_not_ready_returns_no_0609_result(
    monkeypatch: pytest.MonkeyPatch, state: str, expected: str
) -> None:
    _patch_identity(monkeypatch)
    _patch_canonical_result(monkeypatch, {"state": state, "items": []})

    payload = records._load_luxian_0609_review_items_from_canonical("visit-1")

    assert payload["review_items"] == []
    assert payload["review_job"] is None
    assert payload["state"] == expected


@pytest.mark.parametrize(
    "result",
    [["unexpected", MALICIOUS_TEXT], {"state": "ready", "items": []}],
    ids=["malformed_shape", "empty_ready"],
)
def test_canonical_malformed_or_empty_result_is_contained(
    monkeypatch: pytest.MonkeyPatch, result: Any
) -> None:
    _patch_identity(monkeypatch)
    _patch_canonical_result(monkeypatch, result)

    payload = records._load_luxian_0609_review_items_from_canonical("visit-1")

    assert payload["review_items"] == []
    assert payload["state"] in {"technical_error", "unavailable"}
    assert MALICIOUS_TEXT not in json.dumps(payload, ensure_ascii=False)


def test_canonical_service_exception_is_contained_without_echoing_raw_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_identity(monkeypatch)
    _patch_canonical_result(monkeypatch, {}, raises=True)

    payload = records._load_luxian_0609_review_items_from_canonical("visit-1")

    assert payload["review_items"] == []
    assert payload["state"] == "technical_error"
    assert MALICIOUS_TEXT not in json.dumps(payload, ensure_ascii=False)


def test_envelope_identity_query_is_scoped_and_limited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """身份反查必须限当前规则集/版本，并以 LIMIT 2 限定扫描范围。"""

    engine = _install_engine(
        monkeypatch,
        [{"institute_id": "inst-1", "patient_id": "patient-1", "visit_id": "visit-1"}],
    )

    identities = records._luxian_0609_envelope_identities(
        "visit-1", rule_set_key=RULE_SET_KEY, rule_set_version=RULE_SET_VERSION
    )

    assert identities == {ENVELOPE_IDENTITY}
    statement, params = engine.executed[0]
    assert "luxian_0609_record_result_envelopes" in statement
    assert "rule_set_key = :rule_set_key" in statement
    assert "rule_set_version = :rule_set_version" in statement
    assert "LIMIT 2" in statement
    assert params == {
        "record_id": "visit-1",
        "rule_set_key": RULE_SET_KEY,
        "rule_set_version": RULE_SET_VERSION,
    }


def test_no_current_envelope_cannot_be_accepted_as_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CDM 命中但没有当前 Envelope 时，不得仅凭 CDM 身份接受 fake ready。"""

    _patch_identity(monkeypatch, envelope=False)
    calls = _patch_canonical_result(
        monkeypatch,
        {"state": "ready", "job_id": "job-fake", "items": [_published_canonical_item()]},
    )

    payload = records._load_luxian_0609_review_items_from_canonical("visit-1")

    assert payload["review_items"] == []
    assert payload["state"] == "identity_unresolved"
    assert calls == []


def test_identity_conflict_between_cdm_and_envelope_is_controlled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        records,
        "_resolve_visit_identity",
        lambda _rid: {
            "institute_id": "inst-1",
            "patient_id": "patient-OTHER",
            "visit_id": "visit-1",
        },
    )
    monkeypatch.setattr(
        records,
        "_luxian_0609_envelope_identities",
        lambda _rid, **_kw: {ENVELOPE_IDENTITY},
    )
    calls = _patch_canonical_result(monkeypatch, {"state": "ready", "items": []})

    payload = records._load_luxian_0609_review_items_from_canonical("visit-1")

    assert payload["review_items"] == []
    assert payload["state"] == "identity_conflict"
    assert calls == []


def test_ambiguous_envelope_identity_is_controlled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(records, "_resolve_visit_identity", lambda _rid: {})
    monkeypatch.setattr(
        records,
        "_luxian_0609_envelope_identities",
        lambda _rid, **_kw: {ENVELOPE_IDENTITY, ("inst-1", "patient-2", "visit-1")},
    )
    calls = _patch_canonical_result(monkeypatch, {"state": "ready", "items": []})

    payload = records._load_luxian_0609_review_items_from_canonical("visit-1")

    assert payload["review_items"] == []
    assert payload["state"] == "identity_ambiguous"
    assert calls == []


def test_controlled_review_state_rejects_arbitrary_text() -> None:
    assert records._controlled_review_state("technical_error") == "technical_error"
    assert records._controlled_review_state("") == "unavailable"
    assert records._controlled_review_state(MALICIOUS_TEXT) == "technical_error"


# --- 4. 路由级受控行为 ----------------------------------------------------------


def _prepare_endpoint(monkeypatch: pytest.MonkeyPatch, *, raw_rows: Any = None) -> None:
    monkeypatch.setattr(records, "get_supabase", lambda: None)
    monkeypatch.setattr(
        records, "medical_records_db", SimpleNamespace(get=lambda _rid: None)
    )
    monkeypatch.setattr(records, "_load_bundle_payload_for_record", lambda _rid: {})
    if raw_rows is not None:
        _install_engine(monkeypatch, raw_rows)


def _raw_rows(items: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": "job-raw",
            "created_at": "2026-09-01T00:00:00",
            "items_json": json.dumps(items, ensure_ascii=False),
        }
    ]


def test_endpoint_prefers_canonical_and_sets_ready_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _prepare_endpoint(monkeypatch, raw_rows=_raw_rows([_raw_0609_item()]))
    _patch_identity(monkeypatch)
    _patch_canonical_result(
        monkeypatch,
        {"state": "ready", "job_id": "job-canonical", "items": [_published_canonical_item()]},
    )

    response = asyncio.run(_call_qc_detail("visit-1"))

    assert response["success"] is True
    assert response["data"]["review_result_state"] == "ready"
    assert MALICIOUS_TEXT not in json.dumps(response, ensure_ascii=False)
    review_items = response["data"]["review_items"]
    assert len(review_items) == 1
    assert review_items[0]["source"] == "canonical_result_envelope"
    assert review_items[0]["findings"] == "已发布结论：报告出具后 24 小时内病程未记录"


@pytest.mark.parametrize("mode", ["not_found", "raises"])
def test_endpoint_without_canonical_returns_no_raw_0609_and_is_not_500(
    monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    _prepare_endpoint(monkeypatch, raw_rows=_raw_rows([_raw_0609_item()]))
    _patch_identity(monkeypatch)
    if mode == "not_found":
        _patch_canonical_result(monkeypatch, {"state": "not_found", "items": []})
        expected_state = "not_found"
    else:
        _patch_canonical_result(monkeypatch, {}, raises=True)
        expected_state = "technical_error"

    response = asyncio.run(_call_qc_detail("visit-1"))

    assert response["success"] is True
    assert response["data"]["review_items"] == []
    assert response["data"]["review_result_state"] == expected_state
    assert MALICIOUS_TEXT not in json.dumps(response, ensure_ascii=False)


def test_endpoint_keeps_legacy_non_luxian_items(monkeypatch: pytest.MonkeyPatch) -> None:
    _prepare_endpoint(
        monkeypatch,
        raw_rows=_raw_rows(
            [
                {
                    "record_id": "visit-legacy",
                    "rule_code": "SC-020",
                    "rule_name": "会诊记录",
                    "status": "non_compliant",
                    "findings": "legacy 判定说明",
                }
            ]
        ),
    )
    _patch_identity(monkeypatch, record_id="visit-legacy")
    _patch_canonical_result(monkeypatch, {"state": "not_found", "items": []})

    response = asyncio.run(_call_qc_detail("visit-legacy"))

    assert response["data"]["review_result_state"] == "legacy"
    review_items = response["data"]["review_items"]
    assert len(review_items) == 1
    assert review_items[0]["source"] == "batch_job"
    assert review_items[0]["rule_code"] == "SC-020"
