"""病历排名审核人合同：历史工作量不随当前用户角色变化而改写。"""

from __future__ import annotations

import json
from typing import Any

from app.database.models.qc import QCRecordReview, SysUser
from app.services import performance_ranking_service as service
from tests.unit.test_performance_ranking_service import NOW, _review, build_env, utc


def _reviewer_row(data: dict[str, Any], reviewer_id: str) -> dict[str, Any]:
    return next(
        row for row in data["record_ranking"]
        if row["user_id"] == reviewer_id
    )


def test_historical_reviewer_work_survives_current_role_change(monkeypatch):
    """排名认已保存审核事件，不按用户当前角色重新解释历史工作量。"""
    engine, sessions = build_env(monkeypatch)
    reviewer_id = "reviewer-role-history"
    try:
        with sessions.begin() as session:
            session.execute(SysUser.__table__.insert(), {
                "id": reviewer_id,
                "username": "reviewer-role-history",
                "display_name": "历史审核员",
                "role": "qc_manager",
                "roles_json": json.dumps(["qc_manager"]),
                "created_at": utc(0),
                "updated_at": utc(0),
            })
            session.execute(QCRecordReview.__table__.insert(), [
                _review(
                    "role-initial-task", reviewer_id, 200,
                    patient="P-role", visit="V-role", scene="running",
                ),
                _review(
                    "role-initial-workspace", reviewer_id, 201,
                    patient="P-role", visit="V-role", scene="running",
                    context="workspace",
                ),
                _review(
                    "role-recheck-task", reviewer_id, 202,
                    patient="P-role", visit="V-role", scene="running",
                    stage="recheck",
                ),
            ])

        before = _reviewer_row(
            service.get_performance_ranking(
                period="this_week", scene="running", now=NOW,
            ),
            reviewer_id,
        )
        assert before == {
            "user_id": reviewer_id,
            "name": "历史审核员",
            "count": 1,
            "initial_count": 1,
            "recheck_count": 1,
            "rank": 1,
        }

        with sessions.begin() as session:
            session.execute(
                SysUser.__table__.update()
                .where(SysUser.id == reviewer_id)
                .values(role="doctor", roles_json=json.dumps(["doctor"]), updated_at=utc(300))
            )

        after = _reviewer_row(
            service.get_performance_ranking(
                period="this_week", scene="running", now=NOW,
            ),
            reviewer_id,
        )
        assert after == before
    finally:
        engine.dispose()
