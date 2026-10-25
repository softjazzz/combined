"""审核写入后，报表明确读取同一个qc owner，不依赖search_path。"""

from types import SimpleNamespace

import pytest

from app.services.record_review_service import _batch_case_decisions
from app.services import staff_work_analysis_service as staff


class CapturingSession:
    def __init__(self, dialect):
        self.dialect = dialect
        self.calls = []

    def get_bind(self):
        return SimpleNamespace(dialect=SimpleNamespace(name=self.dialect))

    def execute(self, statement, **kwargs):
        self.calls.append((statement, kwargs))
        return SimpleNamespace(all=lambda: [])


@pytest.mark.parametrize("dialect", ["postgresql", "sqlite"])
def test_current_review_projection_declares_statement_owner(dialect):
    session = CapturingSession(dialect)
    assert _batch_case_decisions(session, {("H", "P", "V"): ("J", "E")}) == {}
    expected = {"schema_translate_map": {None: "qc"}} if dialect == "postgresql" else {}
    assert session.calls[0][1] == {"execution_options": expected}


def test_staff_review_loader_declares_qc_owner_before_any_other_lookup():
    session = CapturingSession("postgresql")
    scope = SimpleNamespace(
        window=SimpleNamespace(utc_start="2026-10-24", utc_end="2026-10-26"),
        scene="all", institute_id=None,
    )

    def stop(statement, **kwargs):
        session.calls.append((statement, kwargs))
        raise RuntimeError("stop_after_first_query")

    session.execute = stop
    with pytest.raises(RuntimeError, match="stop_after_first_query"):
        staff._load_base_events(session, scope)
    assert session.calls[0][1] == {"execution_options": {"schema_translate_map": {None: "qc"}}}
