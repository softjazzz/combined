"""PR8报表只读消费子集，来源88e8f864b；不移植写入口与执行链。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from ..database.models.v36_reports import SysUser
from .user_scope_owner import user_owner_options


def _display_names(session: Any, actor_ids: set[str]) -> dict[str, str]:
    if not actor_ids:
        return {}
    rows = session.execute(
        select(SysUser.id, SysUser.display_name).where(
            SysUser.id.in_(sorted(actor_ids))
        ),
        execution_options=user_owner_options(session),
    ).all()
    return {str(row.id): row.display_name for row in rows if row.display_name}
