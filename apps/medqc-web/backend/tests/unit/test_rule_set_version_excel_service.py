"""规则集版本 Excel 文件与事务导入合同（SQLite/内存工作簿，不连真实库）。"""

from __future__ import annotations

import io
from copy import deepcopy

import pytest
import sqlalchemy as sa
from openpyxl import load_workbook
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.qc import QCRuleSetVersion
from app.services import rule_set_version_excel_service as excel
from app.services import rule_set_version_service as service


KEY = "luxian_0609_qc_v1"
BUILTIN = "2026-06-09"
ACTOR = "manager-1"


@pytest.fixture
def sessions(monkeypatch):
    engine = sa.create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    QCRuleSetVersion.__table__.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(service, "SessionLocal", factory)
    yield factory
    engine.dispose()


def builtin_entries():
    resolution = service.resolve_rule_set_version(KEY, BUILTIN)
    return sorted([
        *({"rule_id": rule_id, "state": "active"} for rule_id in resolution["active_rule_ids"]),
        *({"rule_id": rule_id, "state": "paused"} for rule_id in resolution["paused_rule_ids"]),
        *({"rule_id": rule_id, "state": "offline"} for rule_id in resolution["excluded_rule_ids"]),
    ], key=lambda item: item["rule_id"])


def snapshot(entries=None, *, status="builtin", seq=None):
    entries = entries or builtin_entries()
    return {
        "rule_set_key": KEY,
        "version": None if status == "draft" else BUILTIN,
        "status": status,
        "version_seq": seq,
        "draft_version": "draft:test-draft-id" if status == "draft" else None,
        "entries": [
            {
                **item,
                "qc_point": f"质控点 {item['rule_id']}",
                "source_document": "入院记录",
            }
            for item in entries
        ],
    }


def workbook_bytes(data=None, *, status="builtin", seq=None):
    resolution = service.resolve_rule_set_version(KEY, BUILTIN)
    return excel.build_workbook(
        snapshot(data, status=status, seq=seq),
        base_version=BUILTIN,
        base_content_digest=resolution["content_digest"],
    )


def edit_workbook(content: bytes, edit) -> bytes:
    workbook = load_workbook(io.BytesIO(content), data_only=False)
    edit(workbook)
    output = io.BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def test_generated_workbook_roundtrips_formula_like_metadata_as_text():
    rows = snapshot()["entries"]
    rows[0]["qc_point"] = "=不是公式"
    rows[0]["source_document"] = "+也不是公式"
    content = excel.build_workbook(
        {**snapshot(), "entries": rows},
        base_version=BUILTIN,
        base_content_digest=service.resolve_rule_set_version(KEY, BUILTIN)["content_digest"],
    )
    workbook = load_workbook(io.BytesIO(content), data_only=False)
    assert workbook[excel.ENTRY_SHEET]["C2"].data_type == "s"
    assert workbook[excel.ENTRY_SHEET]["C2"].value == "=不是公式"
    workbook.close()
    parsed = excel.parse_workbook(content, expected_rule_set_key=KEY)
    assert parsed.entries == builtin_entries()
    excel.validate_readonly_metadata(parsed, rows)


def test_draft_roundtrip_carries_base_digest_and_version_seq():
    content = workbook_bytes(status="draft", seq=7)
    parsed = excel.parse_workbook(content, expected_rule_set_key=KEY)
    assert parsed.exported_status == "draft"
    assert parsed.exported_version == "draft:test-draft-id"
    assert parsed.expected_draft_version == "draft:test-draft-id"
    assert parsed.base_version == BUILTIN
    assert parsed.expected_draft_version_seq == 7
    assert parsed.base_content_digest == service.resolve_rule_set_version(KEY, BUILTIN)["content_digest"]


@pytest.mark.parametrize(
    "edit,code",
    [
        (lambda wb: wb.create_sheet("额外数据"), "invalid_sheets"),
        (lambda wb: setattr(wb[excel.ENTRY_SHEET], "sheet_state", "hidden"), "hidden_sheet"),
        (lambda wb: setattr(wb[excel.ENTRY_SHEET]["B2"], "value", "=1+1"), "formula_not_allowed"),
        (lambda wb: setattr(wb[excel.INFO_SHEET]["A2"], "value", "old"), "template_version"),
        (lambda wb: setattr(wb[excel.INFO_SHEET]["B2"], "value", "another"), "rule_set_mismatch"),
    ],
)
def test_invalid_workbook_contract_is_rejected(edit, code):
    with pytest.raises(excel.RuleSetVersionExcelInvalid) as error:
        excel.parse_workbook(edit_workbook(workbook_bytes(), edit), expected_rule_set_key=KEY)
    assert code in {issue.code for issue in error.value.issues}


def test_readonly_metadata_change_is_rejected():
    content = workbook_bytes()
    parsed = excel.parse_workbook(content, expected_rule_set_key=KEY)
    catalog = snapshot()["entries"]
    changed = deepcopy(catalog)
    changed[0]["qc_point"] = "服务端真实名称"
    with pytest.raises(excel.RuleSetVersionExcelInvalid) as error:
        excel.validate_readonly_metadata(parsed, changed)
    assert error.value.issues[0].code == "readonly_metadata_changed"


def test_worksheet_external_hyperlink_is_rejected():
    content = edit_workbook(
        workbook_bytes(),
        lambda workbook: setattr(
            workbook[excel.ENTRY_SHEET]["C2"], "hyperlink", "https://example.com/external",
        ),
    )
    with pytest.raises(excel.RuleSetVersionExcelInvalid) as error:
        excel.parse_workbook(content, expected_rule_set_key=KEY)
    assert "external_link" in {issue.code for issue in error.value.issues}


def test_editing_states_does_not_need_to_match_base_digest(sessions):
    entries = builtin_entries()
    first_active = next(item for item in entries if item["state"] == "active")
    first_active["state"] = "paused"
    base = service.resolve_rule_set_version(KEY, BUILTIN)
    preflight = service.preflight_draft_import_snapshot(
        KEY,
        base_version=BUILTIN,
        base_content_digest=base["content_digest"],
        entries=entries,
    )
    assert preflight["base"]["content_digest"] == base["content_digest"]
    created = service.import_draft_snapshot(
        KEY,
        actor=ACTOR,
        base_version=BUILTIN,
        base_content_digest=base["content_digest"],
        entries=entries,
    )
    assert created["status"] == "draft" and created["version_seq"] == 1
    assert next(item for item in created["entries"] if item["rule_id"] == first_active["rule_id"])["state"] == "paused"
    assert service.current_version(KEY) == BUILTIN


def test_import_existing_draft_requires_matching_cas_and_base(sessions):
    base = service.resolve_rule_set_version(KEY, BUILTIN)
    entries = builtin_entries()
    service.import_draft_snapshot(
        KEY, actor=ACTOR, base_version=BUILTIN,
        base_content_digest=base["content_digest"], entries=entries,
    )
    draft_version = service.get_draft_export_snapshot(KEY)["snapshot"]["draft_version"]
    updated_entries = deepcopy(entries)
    next(item for item in updated_entries if item["state"] == "active")["state"] = "paused"
    updated = service.import_draft_snapshot(
        KEY, actor=ACTOR, base_version=BUILTIN,
        base_content_digest=base["content_digest"], entries=updated_entries,
        expected_draft_version=draft_version,
        expected_draft_version_seq=1,
    )
    assert updated["version_seq"] == 2
    with pytest.raises(service.RuleSetVersionConflict) as stale:
        service.import_draft_snapshot(
            KEY, actor=ACTOR, base_version=BUILTIN,
            base_content_digest=base["content_digest"], entries=entries,
            expected_draft_version=draft_version,
            expected_draft_version_seq=1,
        )
    assert stale.value.code == "version_conflict"
    with pytest.raises(service.RuleSetVersionConflict) as frozen_file:
        service.import_draft_snapshot(
            KEY, actor=ACTOR, base_version=BUILTIN,
            base_content_digest=base["content_digest"], entries=entries,
        )
    assert frozen_file.value.code == "draft_exists"


def test_deleted_draft_workbook_cannot_overwrite_recreated_seq_one_draft(sessions):
    base = service.resolve_rule_set_version(KEY, BUILTIN)
    entries = builtin_entries()
    first = service.import_draft_snapshot(
        KEY, actor=ACTOR, base_version=BUILTIN,
        base_content_digest=base["content_digest"], entries=entries,
    )
    old_identity = service.get_draft_export_snapshot(KEY)["snapshot"]["draft_version"]
    service.delete_draft(KEY, actor=ACTOR, version_seq=first["version_seq"])
    recreated = service.import_draft_snapshot(
        KEY, actor=ACTOR, base_version=BUILTIN,
        base_content_digest=base["content_digest"], entries=entries,
    )
    assert recreated["version_seq"] == 1
    assert service.get_draft_export_snapshot(KEY)["snapshot"]["draft_version"] != old_identity
    with pytest.raises(service.RuleSetVersionConflict) as error:
        service.import_draft_snapshot(
            KEY, actor=ACTOR, base_version=BUILTIN,
            base_content_digest=base["content_digest"], entries=entries,
            expected_draft_version=old_identity, expected_draft_version_seq=1,
        )
    assert error.value.code == "draft_changed"


def test_preflight_rejects_missing_rule_and_digest_drift_without_write(sessions):
    base = service.resolve_rule_set_version(KEY, BUILTIN)
    with pytest.raises(service.RuleSetVersionInvalid) as missing:
        service.preflight_draft_import_snapshot(
            KEY, base_version=BUILTIN, base_content_digest=base["content_digest"],
            entries=builtin_entries()[:-1],
        )
    assert missing.value.code == "publish_validation_failed"
    with pytest.raises(service.RuleSetVersionInvalid) as digest:
        service.preflight_draft_import_snapshot(
            KEY, base_version=BUILTIN, base_content_digest="0" * 64,
            entries=builtin_entries(),
        )
    assert digest.value.code == "base_digest_mismatch"
    with pytest.raises(service.RuleSetVersionNotFound):
        service.get_draft(KEY)


def test_transactional_reread_failure_rolls_back_new_draft(sessions, monkeypatch):
    base = service.resolve_rule_set_version(KEY, BUILTIN)
    original = service._draft_row
    calls = 0

    def fail_final_read(session, rule_set_key, *, for_update=False):
        nonlocal calls
        calls += 1
        if calls == 2:
            return None
        return original(session, rule_set_key, for_update=for_update)

    monkeypatch.setattr(service, "_draft_row", fail_final_read)
    with pytest.raises(service.RuleSetVersionUnavailable):
        service.import_draft_snapshot(
            KEY, actor=ACTOR, base_version=BUILTIN,
            base_content_digest=base["content_digest"], entries=builtin_entries(),
        )
    with sessions() as session:
        assert session.execute(sa.select(sa.func.count()).select_from(QCRuleSetVersion.__table__)).scalar_one() == 0
