"""以规则为中心的验收：病例预期、运行、逐例复核、结论与批准。

只读取正式任务结果做比较，不参与医学执行，不改写正式结果，也不修改规则目录；
上线仍由开发按发布单修改 `release_scope` 并随版本发布。
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from functools import lru_cache
import json
from typing import Any, Callable, Iterable
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy import MetaData, Table, select, update

from . import custom_qc_sample_pool_service as pools
from .case_identity import CaseRef
from .luxian_0609_rule_master import load_luxian_0609_rule_master

EXPECTED_STATUSES = ("compliant", "non_compliant", "not_applicable", "data_gap")
PURPOSES = ("development", "acceptance")
DEVELOPMENT_ENVS = frozenset({"development", "dev", "local", "test"})
MAX_CASES_PER_RUN = 50


class RuleValidationConflict(ValueError):
    """并发修改或状态不允许；接口返回 409。"""


def define_tables(metadata: MetaData, schema: str | None = None) -> tuple[Table, Table]:
    """运行表与只追加的事件表（复核、结论、批准）。"""
    runs = Table(
        "rule_validation_runs",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("rule_id", sa.String(64), nullable=False, index=True),
        sa.Column("cases_json", sa.Text, nullable=False),
        sa.Column("job_id", sa.String(36)),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("execution_version_json", sa.Text),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        schema=schema,
    )
    events = Table(
        "rule_validation_events",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("rule_id", sa.String(64), nullable=False, index=True),
        sa.Column("run_id", sa.String(36), index=True),
        sa.Column("item_id", sa.String(36)),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("note", sa.Text, nullable=False),
        sa.Column("payload_json", sa.Text),
        sa.Column("actor", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        schema=schema,
    )
    return runs, events


@lru_cache(maxsize=1)
def _tables() -> tuple[Table, Table]:
    # 沿用样本池表“首次使用建表”的方式。
    if pools.engine is None:
        raise RuntimeError("DATABASE_URL is not configured; rule validation unavailable")
    metadata = MetaData()
    tables = define_tables(metadata, pools._schema())
    metadata.create_all(bind=pools.engine, checkfirst=True)
    return tables


def rule_catalog() -> dict[str, dict]:
    return {
        e.rule_id: {"rule_id": e.rule_id, "name": e.qc_point, "source_document": e.source_document,
                    "release_scope": e.release_scope, "policy_summary": e.policy_summary}
        for e in load_luxian_0609_rule_master()
        if e.implementation_status == "active" and e.phase_status == "phase_1_target"
    }


def build_kind(execution_version: dict | None) -> str:
    implementation = ((execution_version or {}).get("lx0609_task_runtime") or {}).get("implementation") or {}
    return "release" if implementation.get("kind") == "release" else "development"


def compare_cases(rule_id: str, cases: list[dict], job: dict | None) -> list[dict]:
    """按病例三坐标比较已发布状态；一致只代表状态一致，证据和建议仍需人工复核。"""
    status = (job or {}).get("status")
    items = [x for x in (job or {}).get("items") or [] if x.get("rule_id") == rule_id]
    rows = []
    for case in cases:
        ref = CaseRef.from_mapping(case["record_ref"])
        matches = [x for x in items if _item_ref(x) == ref]
        actual = matches[0].get("status") if len(matches) == 1 else None
        outcome = "pending"
        if status == "completed":
            outcome = ("missing" if not matches else "ambiguous" if len(matches) > 1
                       else "same" if actual == case["expected_status"] else "different")
        elif status in {"failed", "canceled", "creation_failed"}:
            outcome = "failed"
        rows.append({**case, "actual_status": actual, "comparison": outcome})
    return rows


class RuleValidationService:
    def __init__(self, *, item_table=None, runs_table=None, events_table=None, session_factory=None,
                 catalog: Callable[[], dict[str, dict]] = rule_catalog, env: str | None = None):
        self.items = item_table if item_table is not None else pools._sample_pool_items_table()
        self.runs = runs_table if runs_table is not None else _tables()[0]
        self.events = events_table if events_table is not None else _tables()[1]
        self.sessions = session_factory or pools._session
        self.catalog = catalog
        self.env = env

    # ---- 规则与病例 ----

    def _rule(self, rule_id: str) -> dict:
        rule = self.catalog().get(rule_id)
        if rule is None:
            raise LookupError("规则不存在或不是当前可执行的四段式规则")
        return rule

    def _customer_items(self, session) -> list[dict]:
        rows = session.execute(select(self.items).where(self.items.c.pool_id == pools.CUSTOMER_TEST_POOL_ID)).mappings()
        return [dict(r) for r in rows]

    def _case_view(self, row: dict, rule_id: str) -> dict | None:
        raw = json.loads(row.get("raw_payload_json") or "{}")
        answer = next((a for a in raw.get("golden_answers") or [] if a.get("qc_point_id") == rule_id), None)
        if answer is None:
            return None
        return {
            "item_id": row["id"],
            "case_title": raw.get("case_title") or row.get("patient_name") or row["id"],
            "record_ref": {k: row.get("matched_" + k) for k in ("institute_id", "patient_id", "visit_id")},
            # 从真实病例复制的测试病例保留真实材料；模板/手工构建的是合成病例，不能冒充客户验收。
            "source_kind": "real_copy" if raw.get("source_record") else "synthetic",
            "evaluation_as_of_date": raw.get("evaluation_as_of_date") or None,
            "expected_status": answer.get("expected_status"),
            "human_reason": answer.get("human_reason") or "",
            "purpose": answer.get("purpose") or "development",
            "answer_revision": int(answer.get("revision") or 0),
            "labeled_by": answer.get("labeled_by"),
            "labeled_at": answer.get("labeled_at"),
        }

    def list_cases(self, rule_id: str) -> list[dict]:
        self._rule(rule_id)
        with self.sessions() as session:
            views = [self._case_view(r, rule_id) for r in self._customer_items(session)]
        return sorted((v for v in views if v), key=lambda v: v["item_id"])

    def list_candidate_cases(self, rule_id: str) -> list[dict]:
        """可关联到本规则的测试病例（尚未为本规则标注预期）。"""
        self._rule(rule_id)
        with self.sessions() as session:
            rows = self._customer_items(session)
        result = []
        for row in rows:
            if self._case_view(row, rule_id) is None:
                raw = json.loads(row.get("raw_payload_json") or "{}")
                result.append({"item_id": row["id"], "case_title": raw.get("case_title") or row.get("patient_name") or row["id"],
                               "source_kind": "real_copy" if raw.get("source_record") else "synthetic",
                               "evaluation_as_of_date": raw.get("evaluation_as_of_date") or None})
        return sorted(result, key=lambda v: v["item_id"])

    def _change_item(self, item_id: str, action):
        with self.sessions() as session:
            row = session.execute(select(self.items).where(self.items.c.id == item_id).with_for_update()).mappings().first()
            if not row or row["pool_id"] != pools.CUSTOMER_TEST_POOL_ID:
                raise LookupError("仅支持客户自建测试病历")
            raw = json.loads(row["raw_payload_json"] or "{}")
            result = action(raw)
            session.execute(update(self.items).where(self.items.c.id == item_id).values(
                raw_payload_json=json.dumps(raw, ensure_ascii=False)))
            session.commit()
            return result

    def upsert_answer(self, rule_id: str, item_id: str, *, revision: int, expected_status: str,
                      human_reason: str, purpose: str, user: str) -> dict:
        self._rule(rule_id)
        if expected_status not in EXPECTED_STATUSES:
            raise ValueError("预期状态仅支持合规、不合规、不适用、资料不足")
        if purpose not in PURPOSES:
            raise ValueError("病例用途仅支持开发集或独立验收集")
        if not human_reason.strip():
            raise ValueError("请填写人工预期依据")

        def change(raw):
            answers = raw.setdefault("golden_answers", [])
            current = next((a for a in answers if a.get("qc_point_id") == rule_id), None)
            current_revision = int(current.get("revision") or 0) if current else 0
            if current_revision != revision:
                raise RuleValidationConflict("预期已被其他操作修改，请刷新后重试")
            # 历史运行保存的是预期快照，这里只更新当前预期并递增该规则自己的修订号。
            answer = {"qc_point_id": rule_id, "expected_status": expected_status,
                      "human_reason": human_reason.strip(), "purpose": purpose,
                      "trigger_facts": (current or {}).get("trigger_facts") or [],
                      "evidence_keywords": (current or {}).get("evidence_keywords") or [],
                      "revision": current_revision + 1, "labeled_by": user, "labeled_at": _now_iso()}
            if current:
                answers[answers.index(current)] = answer
            else:
                answers.append(answer)
            return answer
        return self._change_item(item_id, change)

    def remove_answer(self, rule_id: str, item_id: str, *, revision: int) -> None:
        self._rule(rule_id)

        def change(raw):
            answers = raw.get("golden_answers") or []
            current = next((a for a in answers if a.get("qc_point_id") == rule_id), None)
            if current is None:
                raise LookupError("该病例未关联本规则")
            if int(current.get("revision") or 0) != revision:
                raise RuleValidationConflict("预期已被其他操作修改，请刷新后重试")
            answers.remove(current)
        self._change_item(item_id, change)

    # ---- 运行 ----

    def begin_run(self, rule_id: str, item_ids: Iterable[str] | None, user: str) -> dict:
        cases = self.list_cases(rule_id)
        if item_ids is not None:
            wanted = list(dict.fromkeys(item_ids))
            by_id = {c["item_id"]: c for c in cases}
            if any(i not in by_id for i in wanted):
                raise ValueError("所选病例未关联本规则或不存在")
            cases = [by_id[i] for i in wanted]
        if not cases:
            raise ValueError("请先为本规则关联测试病例并标注预期")
        if len(cases) > MAX_CASES_PER_RUN:
            raise ValueError(f"单次运行最多 {MAX_CASES_PER_RUN} 个病例")
        if any(not all(c["record_ref"].values()) for c in cases):
            raise ValueError("存在住院标识不完整的测试病例")
        with self.sessions() as session:
            creating = session.execute(select(self.runs.c.id).where(
                self.runs.c.rule_id == rule_id, self.runs.c.state == "creating")).first()
            if creating:
                raise RuleValidationConflict("本规则有尚未完成任务绑定的运行，请稍后刷新，避免重复提交")
            run = {"id": str(uuid4()), "rule_id": rule_id, "cases_json": json.dumps(cases, ensure_ascii=False),
                   "job_id": None, "state": "creating", "execution_version_json": None,
                   "created_by": user, "created_at": _now()}
            session.execute(self.runs.insert().values(**run))
            session.commit()
        return self.get_run(run["id"])

    def bind_run(self, run_id: str, job_id: str | None, filters: dict | None) -> None:
        version = None
        if filters is not None:
            version = {k: deepcopy(filters.get(k)) for k in (
                "lx0609_task_runtime", "lx0609_task_settings", "record_evaluation_snapshot",
                "task_frozen_date", "scoped_customer_rule_ids")}
        with self.sessions() as session:
            result = session.execute(update(self.runs).where(
                self.runs.c.id == run_id, self.runs.c.state == "creating").values(
                job_id=job_id, state="bound" if job_id else "creation_failed",
                execution_version_json=json.dumps(version, ensure_ascii=False) if version else None))
            session.commit()
        if result.rowcount != 1:
            raise RuleValidationConflict("运行已经绑定，不能更换任务")

    def get_run(self, run_id: str) -> dict:
        with self.sessions() as session:
            row = session.execute(select(self.runs).where(self.runs.c.id == run_id)).mappings().first()
        if not row:
            raise LookupError("运行不存在")
        return _run_view(dict(row))

    def list_runs(self, rule_id: str) -> list[dict]:
        with self.sessions() as session:
            rows = session.execute(select(self.runs).where(self.runs.c.rule_id == rule_id)
                                   .order_by(self.runs.c.created_at.desc())).mappings().all()
        return [_run_view(dict(r)) for r in rows]

    # ---- 复核、结论、批准 ----

    def _append(self, **event) -> dict:
        record = {"id": str(uuid4()), "created_at": _now(), "run_id": None, "item_id": None, "payload_json": None, **event}
        with self.sessions() as session:
            session.execute(self.events.insert().values(**record))
            session.commit()
        return _event_view(record)

    def list_events(self, rule_id: str) -> list[dict]:
        with self.sessions() as session:
            rows = session.execute(select(self.events).where(self.events.c.rule_id == rule_id)
                                   .order_by(self.events.c.created_at.asc())).mappings().all()
        return [_event_view(dict(r)) for r in rows]

    def review_case(self, run: dict, rows: list[dict], item_id: str, *, decision: str, note: str, user: str) -> dict:
        if decision not in {"confirmed", "problem"} or not note.strip():
            raise ValueError("请选择复核结论并填写核对意见")
        row = next((r for r in rows if r["item_id"] == item_id), None)
        if row is None:
            raise LookupError("该病例不在本次运行中")
        if row["comparison"] in {"pending", "failed"}:
            raise RuleValidationConflict("运行尚未完成，不能复核")
        if decision == "confirmed" and row["comparison"] != "same":
            raise ValueError("状态与预期不一致，不能确认通过；请记录问题")
        return self._append(rule_id=run["rule_id"], run_id=run["id"], item_id=item_id, kind="case_review",
                            decision=decision, note=note.strip(), actor=user,
                            payload_json=json.dumps({"comparison": row}, ensure_ascii=False))

    def conclude(self, run: dict, rows: list[dict], *, decision: str, note: str, gap_ack: str, user: str) -> dict:
        if decision not in {"accepted", "rejected"} or not note.strip():
            raise ValueError("请选择验收结论并填写意见")
        summary = self.summarize(run["rule_id"], run=run, rows=rows)
        if decision == "accepted":
            blockers = summary["acceptance_blockers"]
            if blockers:
                raise ValueError("不能验收通过：" + "；".join(blockers))
            if summary["coverage"]["gaps"] and not gap_ack.strip():
                raise ValueError("存在覆盖缺口，请逐项说明可接受的原因")
        return self._append(rule_id=run["rule_id"], run_id=run["id"], kind="conclusion", decision=decision,
                            note=note.strip(), actor=user, payload_json=json.dumps(
                                {"gap_ack": gap_ack.strip(), "coverage": summary["coverage"],
                                 "build_kind": build_kind(run.get("execution_version"))}, ensure_ascii=False))

    def approve(self, rule_id: str, *, decision: str, note: str, user: str) -> dict:
        if decision not in {"approved", "rejected"} or not note.strip():
            raise ValueError("请选择批准结论并填写意见")
        rule = self._rule(rule_id)
        events = self.list_events(rule_id)
        conclusion = next((e for e in reversed(events) if e["kind"] == "conclusion"), None)
        if decision == "approved":
            if not conclusion or conclusion["decision"] != "accepted":
                raise ValueError("最近一次验收结论不是通过，不能批准")
            runs = self.list_runs(rule_id)
            if runs and runs[0]["id"] != conclusion["run_id"]:
                raise ValueError("验收结论之后又有新的运行，请先对最新运行下结论")
            run = self.get_run(conclusion["run_id"])
            kind = build_kind(run.get("execution_version"))
            if kind != "release" and not self._is_development_env():
                raise ValueError("客户环境只能依据正式构建的验收运行批准；本地进程版本请在固定发布构建上重跑")
            sheet = self._release_sheet(rule, run, events, conclusion, approver=user, note=note.strip(), kind=kind)
            return self._append(rule_id=rule_id, run_id=run["id"], kind="approval", decision="approved",
                                note=note.strip(), actor=user, payload_json=json.dumps(sheet, ensure_ascii=False))
        return self._append(rule_id=rule_id, run_id=conclusion["run_id"] if conclusion else None, kind="approval",
                            decision="rejected", note=note.strip(), actor=user)

    def _is_development_env(self) -> bool:
        env = self.env
        if env is None:
            from ..core.settings import get_settings
            env = get_settings().ENV
        return str(env or "").strip().lower() in DEVELOPMENT_ENVS

    def _release_sheet(self, rule, run, events, conclusion, *, approver, note, kind) -> dict:
        runtime = (run.get("execution_version") or {}).get("lx0609_task_runtime") or {}
        reviews = [e for e in events if e["kind"] == "case_review" and e["run_id"] == run["id"]]
        return {
            "rule": {k: rule[k] for k in ("rule_id", "name", "source_document", "policy_summary")},
            "impact_class": "未声明",
            "version": {"build_kind": kind, "development_version": kind != "release",
                        "implementation": runtime.get("implementation"), "first_pass": runtime.get("first_pass")},
            "inputs": [{k: c[k] for k in ("item_id", "case_title", "source_kind", "expected_status",
                                          "answer_revision", "purpose", "evaluation_as_of_date")} for c in run["cases"]],
            "run": {"run_id": run["id"], "job_id": run["job_id"], "created_at": run["created_at"]},
            "coverage": conclusion.get("payload", {}).get("coverage"),
            "gap_ack": conclusion.get("payload", {}).get("gap_ack"),
            "reviews": [{k: e[k] for k in ("item_id", "decision", "note", "actor", "created_at")} for e in reviews],
            "conclusion": {k: conclusion[k] for k in ("decision", "note", "actor", "created_at")},
            "approval": {"approver": approver, "note": note, "approved_at": _now_iso()},
            "release_action": {"catalog": "luxian_0609_rule_master_v1.json", "rule_id": rule["rule_id"],
                               "release_scope": {"from": "acceptance_only", "to": "default"},
                               "post_release_recheck": "部署后用本发布单病例在发布构建上复验，结果须与本次一致"},
        }

    # ---- 汇总与阶段 ----

    def summarize(self, rule_id: str, *, run: dict | None = None, rows: list[dict] | None = None) -> dict:
        """覆盖、复核完成度与通过阻碍；rows 为该 run 的比较结果。"""
        cases = self.list_cases(rule_id)
        coverage = _coverage(cases)
        blockers: list[str] = []
        if run is not None and rows is not None:
            events = [e for e in self.list_events(rule_id) if e["run_id"] == run["id"] and e["kind"] == "case_review"]
            latest = {}
            for e in events:
                latest[e["item_id"]] = e["decision"]
            if any(r["comparison"] in {"pending"} for r in rows):
                blockers.append("运行尚未完成")
            if any(r["comparison"] not in {"same", "pending"} for r in rows):
                blockers.append("存在状态不一致、缺少结果或执行失败的病例")
            if any(latest.get(r["item_id"]) != "confirmed" for r in rows):
                blockers.append("存在未逐例确认的病例")
            if any(not r.get("evaluation_as_of_date") for r in rows):
                blockers.append("存在未固定评价时间点的历史病例")
            if not run.get("execution_version"):
                blockers.append("运行缺少执行版本记录")
        return {"coverage": coverage, "acceptance_blockers": blockers}


def derive_stage(rule: dict, cases: list[dict], runs: list[dict], events: list[dict], latest_rows: list[dict] | None) -> str:
    if rule["release_scope"] == "default":
        return "released"
    latest_run = runs[0] if runs else None
    # 只看最近一次运行上的最后一条结论/批准；新运行会让旧结论和批准失效。
    decided = next((e for e in reversed(events) if e["kind"] in {"conclusion", "approval"}
                    and latest_run and e["run_id"] == latest_run["id"]), None)
    if decided:
        if decided["kind"] == "approval":
            return "approved_pending_release" if decided["decision"] == "approved" else "rejected"
        return "pending_approval" if decided["decision"] == "accepted" else "rejected"
    if not cases:
        return "preparing"
    if not latest_run:
        return "ready_to_run"
    if latest_run["state"] in {"creating", "creation_failed"} or latest_rows is None or any(
            r["comparison"] == "pending" for r in latest_rows):
        return "running" if latest_run["state"] != "creation_failed" else "ready_to_run"
    reviewed = {e["item_id"] for e in events if e["kind"] == "case_review" and e["run_id"] == latest_run["id"]}
    if any(r["item_id"] not in reviewed for r in latest_rows):
        return "reviewing"
    return "pending_conclusion"


def _item_ref(item: dict) -> CaseRef | None:
    """Canonical 结果条目自带三坐标；缺失或不完整时不匹配任何病例（记为缺少结果，不会误判一致）。"""
    ref = CaseRef.from_mapping(item)
    return ref if all(ref) else None


def _coverage(cases: list[dict]) -> dict:
    counts = {s: {"synthetic": 0, "real_copy": 0} for s in EXPECTED_STATUSES}
    for c in cases:
        if c["expected_status"] in counts:
            counts[c["expected_status"]][c["source_kind"]] += 1
    gaps = [s for s in EXPECTED_STATUSES if not sum(counts[s].values())]
    return {"counts": counts, "gaps": gaps,
            "acceptance_cases": sum(1 for c in cases if c["purpose"] == "acceptance")}


def _run_view(row: dict) -> dict:
    return {"id": row["id"], "rule_id": row["rule_id"], "cases": json.loads(row["cases_json"]),
            "job_id": row["job_id"], "state": row["state"],
            "execution_version": json.loads(row["execution_version_json"]) if row.get("execution_version_json") else None,
            "build_kind": build_kind(json.loads(row["execution_version_json"])) if row.get("execution_version_json") else None,
            "created_by": row["created_by"], "created_at": _iso(row["created_at"])}


def _event_view(row: dict) -> dict:
    return {"id": row["id"], "rule_id": row["rule_id"], "run_id": row.get("run_id"), "item_id": row.get("item_id"),
            "kind": row["kind"], "decision": row["decision"], "note": row["note"],
            "payload": json.loads(row["payload_json"]) if row.get("payload_json") else {},
            "actor": row["actor"], "created_at": _iso(row["created_at"])}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iso(value: Any) -> str:
    return value.isoformat() if isinstance(value, datetime) else str(value or "")
