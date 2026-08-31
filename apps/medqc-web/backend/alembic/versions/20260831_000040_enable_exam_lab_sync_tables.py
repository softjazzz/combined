"""Ensure examination and laboratory evidence tables are included in ordinary sync."""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260831_000040"
down_revision: Union[str, None] = "20260827_000039"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_EVIDENCE_TABLES = {
    "exam_master",
    "exam_item_report",
    "labtest_master",
    "labtest_item_report",
}


def upgrade() -> None:
    """启用已纳管的检验检查主表/报告表，保留其它同步表配置不变。

    旧版本客户机曾把这四张表持久化为 enabled=false，导致源库有报告、
    本地 CDM 却没有对应行。仅更新已有配置项，不凭空创建不存在的表配置。
    """

    for table_name in sorted(_EVIDENCE_TABLES):
        statement = sa.text(
            """
            UPDATE qc.sync_config_registry
            SET payload_json = (
                SELECT COALESCE(json_agg(
                    CASE
                        WHEN elem->>'name' = :table_name
                        THEN (elem::jsonb || '{"enabled": true}'::jsonb)::json
                        ELSE elem
                    END
                    ORDER BY ord
                ), '[]'::json)::text
                FROM json_array_elements(payload_json::json) WITH ORDINALITY AS items(elem, ord)
            ),
                updated_by = 'migration',
                source = 'alembic',
                change_reason = 'enable examination and laboratory evidence sync tables',
                updated_at = CURRENT_TIMESTAMP
            WHERE namespace = 'sync'
              AND config_key = 'sync_tables'
              AND json_typeof(payload_json::json) = 'array'
              AND EXISTS (
                  SELECT 1
                  FROM json_array_elements(payload_json::json) AS existing(elem)
                  WHERE elem->>'name' = :table_name
              )
            """
        )
        op.execute(statement.bindparams(table_name=table_name))


def downgrade() -> None:
    # 不回退客户已确认的同步开关，避免降级再次丢失检验检查资料。
    pass
