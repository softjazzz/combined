import pytest

from app.services import rule_set_version_service as service
from app.services import rule_set_version_excel_service as excel
from tests.unit.test_rule_set_version_service import (
    ACTOR,
    BUILTIN,
    EXCLUDED_RULE,
    KEY,
    _builtin_entries,
    _prepare_filters,
    _with_state,
    sessions,  # noqa: F401 - 复用无真实数据库访问的 SQLite fixture。
)


def _publish_deleted():
    entries = _with_state(_builtin_entries(), EXCLUDED_RULE, "deleted")
    service.create_draft(KEY, actor=ACTOR, entries=entries)
    service.publish_draft(KEY, actor=ACTOR, version="2026-09-28.deleted")


def test_deletion_preserves_historical_version_and_excludes_current_execution(sessions):  # noqa: F811
    historical = service.get_version_detail(KEY, BUILTIN)
    _publish_deleted()
    reread = service.get_version_detail(KEY, BUILTIN)
    for field in ("entries", "version", "content_digest"):
        assert reread[field] == historical[field]
    current = service.resolve_rule_set_version(KEY, service.current_version(KEY))
    assert EXCLUDED_RULE in current["deleted_rule_ids"]
    assert EXCLUDED_RULE in current["excluded_rule_ids"]
    assert EXCLUDED_RULE not in current["active_rule_ids"]
    copied = service.create_draft(KEY, actor=ACTOR)
    assert {"rule_id": EXCLUDED_RULE, "state": "deleted"} in copied["entries"]


def test_actual_prepare_excludes_deleted_rule(sessions):  # noqa: F811
    _publish_deleted()
    filters = _prepare_filters(KEY)
    assert filters["rule_set_version"] == "2026-09-28.deleted"
    assert EXCLUDED_RULE not in filters["rule_ids"]
    assert EXCLUDED_RULE not in filters["paused_customer_rule_ids"]


def test_published_deleted_excel_roundtrip_preserves_tombstone(sessions):  # noqa: F811
    _publish_deleted()
    version = service.current_version(KEY)
    detail = service.get_version_detail(KEY, version)
    content = excel.build_workbook(
        detail, base_version=version, base_content_digest=detail["content_digest"],
    )
    parsed = excel.parse_workbook(content, expected_rule_set_key=KEY)
    imported = service.import_draft_snapshot(
        KEY, actor=ACTOR, base_version=parsed.base_version,
        base_content_digest=parsed.base_content_digest, entries=parsed.entries,
    )
    assert {"rule_id": EXCLUDED_RULE, "state": "deleted"} in imported["entries"]
    service.publish_draft(KEY, actor=ACTOR, version="2026-09-28.roundtrip")
    assert EXCLUDED_RULE in service.resolve_rule_set_version(
        KEY, "2026-09-28.roundtrip",
    )["deleted_rule_ids"]


@pytest.mark.parametrize("restored_state", ["active", "paused", "offline"])
def test_old_base_cannot_resurrect_current_deleted_rule(sessions, restored_state):  # noqa: F811
    _publish_deleted()
    old_entries = _with_state(_builtin_entries(), EXCLUDED_RULE, restored_state)
    with pytest.raises((service.RuleSetVersionInvalid, service.RuleSetVersionConflict)):
        service.create_draft(KEY, actor=ACTOR, base_version=BUILTIN, entries=old_entries)
        service.publish_draft(KEY, actor=ACTOR, version="2026-09-28.restore")
    current = service.resolve_rule_set_version(KEY, service.current_version(KEY))
    assert EXCLUDED_RULE in current["deleted_rule_ids"]
