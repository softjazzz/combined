"""已验证的医嘱、检验来源适配；其他文书仍由原同步来源负责。"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from psycopg2.extensions import make_dsn

from .case_identity import CaseRef


HOMOLOGY_TABLE_KEYS = {
    "inpat_drug_order": ("order_id",),
    "inpat_nondrug_order": ("order_id",),
    "labtest_master": ("test_id",),
    "labtest_item": ("test_id", "test_item_id"),
    "labtest_item_report": ("test_id", "print_order_id"),
}
ORDER_EVIDENCE_TIMES = ("reviewed_datetime", "carried_datetime", "canceled_datetime")
_HOSPITAL_TIMEZONE = timezone(timedelta(hours=8))


@dataclass(frozen=True)
class HomologySource:
    remote_url: str = field(repr=False)
    database: str
    schema: str
    table: str
    source_institute_id: str
    target_institute_id: str

    @property
    def required_target_columns(self) -> tuple[str, ...]:
        if self.table.startswith("inpat_"):
            return (*ORDER_EVIDENCE_TIMES, "planned_end_datetime")
        if self.table == "labtest_item_report":
            return ("report_status", "item_id", "report_time")
        return ()

    def source_case_refs(self, case_refs: Sequence[CaseRef]) -> list[CaseRef]:
        if any(ref.institute_id != self.target_institute_id for ref in case_refs):
            raise ValueError("homology 请求机构与本部署显式机构映射不一致")
        return [
            CaseRef(self.source_institute_id, ref.patient_id, ref.visit_id)
            for ref in case_refs
        ]

    def adapt_rows(
        self, rows: Sequence[Mapping[str, Any]], case_refs: Sequence[CaseRef]
    ) -> list[dict[str, Any]]:
        allowed = set(self.source_case_refs(case_refs))
        adapted = []
        seen = set()
        for original in rows:
            row = dict(original)
            if CaseRef.from_mapping(row) not in allowed:
                raise ValueError("homology 返回了请求病例范围外的记录")
            keys = HOMOLOGY_TABLE_KEYS[self.table]
            identity = tuple(str(row.get(key) or "").strip() for key in keys)
            if not all(identity):
                raise ValueError(f"homology {self.table} 缺少稳定标识：{', '.join(keys)}")
            unique_key = (row["patient_id"], row["visit_id"], *identity)
            if unique_key in seen:
                raise ValueError(f"homology {self.table} 存在重复稳定标识，未替换本地快照")
            seen.add(unique_key)
            row["institute_id"] = self.target_institute_id
            if not row.get("inpat_no") and row.get("inpatno"):
                row["inpat_no"] = row["inpatno"]
            if self.table.startswith("inpat_"):
                # 源计划时间是医院本地时间；本地计划列为 timestamptz。
                # 不把开立/计划/执行/撤销时间相互顶替，也不重写状态。
                for name in ("planned_start_datetime", "planned_end_datetime"):
                    value = row.get(name)
                    if isinstance(value, datetime) and value.tzinfo is None:
                        row[name] = value.replace(tzinfo=_HOSPITAL_TIMEZONE)
            elif self.table == "labtest_item_report":
                # 打印序号只在一次检验申请内唯一；用可逆的复合标识避免跨申请覆盖。
                row["document_id"] = "lab:" + json.dumps(
                    list(identity), ensure_ascii=False, separators=(",", ":")
                )
                if len(row["document_id"]) > 100:
                    raise ValueError("homology 检验复合文档标识超过本地字段长度")
                row["item_id"] = row.get("test_item_id")
                row["report_time"] = row.get("report_datetime")
            adapted.append(row)
        return adapted


def resolve_homology_source(*, table_name: str, remote_url: str) -> HomologySource | None:
    if table_name not in HOMOLOGY_TABLE_KEYS:
        return None
    enabled = os.getenv("HOMOLOGY_SYNC_ENABLED", "false").strip().lower()
    if enabled in {"", "0", "false", "no", "off"}:
        return None
    if enabled not in {"1", "true", "yes", "on"}:
        raise ValueError("HOMOLOGY_SYNC_ENABLED 必须是布尔值")
    source_institute = os.getenv("HOMOLOGY_SOURCE_INSTITUTE_ID", "").strip()
    target_institute = os.getenv("HOMOLOGY_TARGET_INSTITUTE_ID", "").strip()
    if not source_institute or not target_institute:
        raise ValueError("启用 homology 同步须显式配置来源和本地机构标识")
    database = os.getenv("HOMOLOGY_DATABASE", "homology").strip()
    schema = os.getenv("HOMOLOGY_SCHEMA", "graph3_homology").strip()
    if not database or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", schema):
        raise ValueError("homology 数据库或 schema 配置无效")
    try:
        # 与已配置的源 PG 共用连接身份；不复制或持久化另一份口令。
        source_url = make_dsn(remote_url, dbname=database)
    except Exception:
        raise ValueError("无法构造 homology 连接，请检查源 PG 连接配置") from None
    return HomologySource(
        source_url, database, schema, table_name, source_institute, target_institute
    )
