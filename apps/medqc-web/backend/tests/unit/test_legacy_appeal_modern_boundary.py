from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.supabase_client import _Query
from app.routers import appeals
from app.schemas.appeals import AppealReviewCreate, AppealUpdate, AppealWithdraw


@pytest.fixture
def old_client(monkeypatch):
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        # 只有旧字段：证明边界过滤不依赖迁移72及其现代来源列。
        c.execute(
            text(
                "CREATE TABLE qc_appeals (id TEXT PRIMARY KEY, qc_result_id TEXT, record_id TEXT, appellant_id TEXT, status TEXT, created_at TEXT, reason TEXT)"
            )
        )
        c.execute(
            text(
                "INSERT INTO qc_appeals VALUES ('modern',NULL,NULL,'doctor','pending','2026-10-24','合成理由'), ('legacy','result','record','doctor','pending','2026-10-24','合成旧理由')"
            )
        )
    sessions = sessionmaker(engine)
    monkeypatch.setattr(
        appeals,
        "get_supabase",
        lambda: SimpleNamespace(table=lambda name: _Query(sessions, name)),
    )
    yield engine
    engine.dispose()


@pytest.mark.asyncio
async def test_legacy_list_count_and_pagination_exclude_modern_before_query(old_client):
    result = await appeals.list_appeals(
        Request({"type": "http"}), current_user={"id": "doctor"}
    )
    assert [row["id"] for row in result["data"]["items"]] == ["legacy"]
    assert result["data"]["total"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["detail", "update", "withdraw", "review"])
async def test_legacy_routes_cannot_read_or_mutate_modern_appeal(old_client, operation):
    request = Request({"type": "http"})
    user = {"id": "doctor"}
    with pytest.raises(HTTPException) as error:
        if operation == "detail":
            await appeals.get_appeal(request, "modern", user)
        elif operation == "update":
            await appeals.update_appeal(
                request, "modern", AppealUpdate(reason="合成更新理由已经超过十个字"), user
            )
        elif operation == "withdraw":
            await appeals.withdraw_appeal(
                request, "modern", AppealWithdraw(reason="合成撤回"), user
            )
        else:
            await appeals.review_appeal(
                request,
                "modern",
                AppealReviewCreate(action="approve", comment="合成审核"),
                user,
            )
    assert error.value.status_code == 404
    with old_client.connect() as c:
        assert (
            c.execute(
                text("SELECT status FROM qc_appeals WHERE id='modern'")
            ).scalar_one()
            == "pending"
        )
