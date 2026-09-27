"""死亡文书族已发布事实读取不得重新投影或静默去除内部字段。"""

from __future__ import annotations

import copy

import pytest

from app.services.luxian_0609.death_document_result_mapping import (
    safe_death_document_customer_display_facts,
    validate_published_death_document_facts,
)


DEATH = "2026-09-01 08:00:00"
RULE_051 = "LX0609-09-02-01"
RULE_060 = "LX0609-04-02-06"


@pytest.mark.parametrize("rid", [RULE_051, RULE_060])
@pytest.mark.parametrize("raw", [None, {}])
def test_published_death_missing_facts_stay_missing(rid, raw):
    assert validate_published_death_document_facts(rule_id=rid, raw=raw) is None


@pytest.mark.parametrize("rule_id,raw", [
    (RULE_051, {"verification_kind": "death_discussion_timeliness_check", "death_time": DEATH,
                "discussion_time": "2026-09-02 08:00:00", "threshold_hours": 168, "actual_interval_hours": 24.125}),
    (RULE_051, {"failure_kind": "death_discussion_missing_after_deadline", "death_time": DEATH,
                "threshold_hours": 168, "discussion_count": 0}),
    (RULE_051, {"verification_kind": "death_discussion_window_not_mature", "death_time": DEATH,
                "deadline_time": "2026-09-08 08:00:00", "evaluation_time": "2026-09-02 08:00:00", "remaining_seconds": 518400.6}),
    (RULE_051, {"verification_kind": "death_discussion_window_not_mature", "death_time": DEATH,
                "deadline_time": "2026-09-08 08:00:00", "evaluation_date": "2026-09-02"}),
    (RULE_051, {"verification_kind": "death_discussion_evaluation_horizon_unavailable", "death_time": DEATH,
                "issue": "authoritative_time_conflict"}),
    (RULE_060, {"verification_kind": "death_record_presence_check", "death_confirmed": True,
                "death_record_count": 0}),
    (RULE_060, {"verification_kind": "death_record_presence_check", "death_confirmed": True,
                "death_record_count": 1, "death_time": DEATH}),
])
def test_published_death_forms_read_exactly(rule_id, raw):
    published = safe_death_document_customer_display_facts(rule_id=rule_id, raw=raw)
    assert published is not None
    assert validate_published_death_document_facts(rule_id=rule_id, raw=published) == published


@pytest.mark.parametrize("rule_id,raw", [
    (RULE_060, {"verification_kind": "death_record_presence_check", "death_confirmed": True,
                "death_record_count": 1, "source_document_id": "SYNTHETIC"}),
    (RULE_060, {"verification_kind": "death_record_presence_check", "death_confirmed": True,
                "death_record_count": True}),
    (RULE_051, {"verification_kind": "death_discussion_timeliness_check", "death_time": DEATH,
                "discussion_time": "2026-09-02 08:00:00", "threshold_hours": 168,
                "actual_interval_hours": float("nan")}),
    (RULE_051, {"verification_kind": "death_discussion_window_not_mature", "death_time": DEATH,
                "deadline_time": "2026-09-08 08:00:00", "evaluation_time": "2026-09-02 08:00:00",
                "remaining_seconds": 1.5}),
    (RULE_051, {"verification_kind": "death_discussion_evaluation_horizon_unavailable", "death_time": DEATH,
                "issue": []}),
])
def test_published_death_pollution_is_rejected(rule_id, raw):
    before = copy.deepcopy(raw)
    assert validate_published_death_document_facts(rule_id=rule_id, raw=raw) is None
    assert raw == before or (isinstance(raw.get("actual_interval_hours"), float)
                              and str(raw["actual_interval_hours"]) == "nan")
