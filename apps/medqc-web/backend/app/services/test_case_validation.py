"""测试验收元数据；不参与医学执行或正式结果生成。"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from uuid import uuid4

from sqlalchemy import select, update

from . import custom_qc_sample_pool_service as pools
from .luxian_0609_rule_master import load_luxian_0609_rule_master


class ValidationConflict(ValueError):
    pass


def rule_options() -> list[dict]:
    return [
        {"rule_id": e.rule_id, "name": e.qc_point, "release_scope": e.release_scope}
        for e in load_luxian_0609_rule_master()
        if e.implementation_status == "active" and e.phase_status == "phase_1_target"
    ]


def validate_answers(answers: list[dict]) -> list[dict]:
    allowed = {r["rule_id"] for r in rule_options()}
    statuses = {"compliant", "non_compliant", "not_applicable", "data_gap"}
    seen: set[str] = set()
    if not 1 <= len(answers) <= 20:
        raise ValueError("请填写1至20条预期答案")
    for a in answers:
        rid = a.get("qc_point_id")
        if rid not in allowed or rid in seen:
            raise ValueError("预期必须使用当前可执行的四段式编号，且不能重复；旧答案请重新核对")
        seen.add(rid)
        if a.get("expected_status") not in statuses:
            raise ValueError("第一版仅支持合规、不合规、不适用、资料不足的确定性预期")
        if not str(a.get("human_reason") or "").strip():
            raise ValueError("请填写人工预期依据")
    return deepcopy(answers)


def compare(run: dict, job: dict) -> list[dict]:
    """仅比较已发布状态；一致不代表通过人工验收。"""
    result = []
    for answer in run["answers"]:
        matches = [x for x in job.get("items", []) if x.get("rule_id") == answer["qc_point_id"]]
        actual = matches[0].get("status") if len(matches) == 1 else None
        outcome = "pending"
        if job.get("status") == "completed":
            outcome = "missing" if not matches else "ambiguous" if len(matches) > 1 else (
                "same" if actual == answer["expected_status"] else "different"
            )
        elif job.get("status") in {"failed", "canceled"}:
            outcome = "failed"
        result.append({**answer, "actual_status": actual, "comparison": outcome})
    return result


class TestCaseValidationService:
    def __init__(self, table=None, session_factory=None):
        self.table = table if table is not None else pools._sample_pool_items_table()
        self.sessions = session_factory or pools._session

    def _change(self, item_id: str, action):
        with self.sessions() as session:
            row = session.execute(select(self.table).where(self.table.c.id == item_id).with_for_update()).mappings().first()
            if not row or row["pool_id"] != pools.CUSTOMER_TEST_POOL_ID:
                raise LookupError("仅支持客户自建测试病历")
            raw = json.loads(row["raw_payload_json"] or "{}")
            state = deepcopy(raw.get("rule_validation") or {"revision": 0, "runs": []})
            value = action(raw, state, dict(row))
            if action is not _read:
                raw["rule_validation"] = state
                session.execute(update(self.table).where(self.table.c.id == item_id).values(
                    raw_payload_json=json.dumps(raw, ensure_ascii=False)))
                session.commit()
            return value

    def read(self, item_id: str) -> dict:
        return self._change(item_id, _read)

    def save_answers(self, item_id: str, revision: int, answers: list[dict], user: str) -> dict:
        answers = validate_answers(answers)
        def change(raw, state, row):
            if state["revision"] != revision:
                raise ValidationConflict("预期已被其他操作修改，请刷新后重试")
            raw["golden_answers"] = answers
            state.update(revision=revision + 1, updated_by=user, updated_at=_now())
            return _read(raw, state, row)
        return self._change(item_id, change)

    def begin(self, item_id: str, revision: int, user: str) -> dict:
        def change(raw, state, row):
            if state["revision"] != revision:
                raise ValidationConflict("预期版本已变化，请刷新后运行")
            if len(state["runs"]) >= 50:
                raise ValidationConflict("已保留50次验收记录，请创建新的测试副本；历史记录不会删除")
            if any(r["state"] == "creating" for r in state["runs"]):
                raise ValidationConflict("本病例有尚未完成任务绑定的验收，请先核查，避免重复提交")
            run = {"id": str(uuid4()), "revision": revision, "answers": validate_answers(raw.get("golden_answers") or []),
                   "created_by": user, "created_at": _now(), "state": "creating", "job_id": None, "reviews": [],
                   "record_ref": {k: row.get("matched_" + k) for k in ("institute_id", "patient_id", "visit_id")},
                   # 测试病例固定的评价时间点；为空表示历史病例未固定，只能记录不通过。
                   "evaluation_as_of_date": raw.get("evaluation_as_of_date") or None}
            if not all(run["record_ref"].values()):
                raise ValueError("测试病历住院标识不完整")
            state["runs"].append(run)
            return deepcopy(run)
        return self._change(item_id, change)

    def bind(self, item_id: str, run_id: str, user: str, job_id: str | None, filters: dict | None = None):
        def change(raw, state, row):
            run = _owned_run(state, run_id, user)
            if run["state"] != "creating":
                raise ValidationConflict("验收已经绑定，不能更换任务")
            run.update(job_id=job_id, state="bound" if job_id else "creation_failed")
            if filters is not None:
                run["execution_version"] = {k: deepcopy(filters.get(k)) for k in (
                    "lx0609_task_runtime", "lx0609_task_settings", "record_evaluation_snapshot",
                    "task_frozen_date", "scoped_customer_rule_ids")}

        self._change(item_id, change)

    def fail_unbound(self, item_id: str, run_id: str, user: str):
        def change(raw, state, row):
            run = _owned_run(state, run_id, user)
            if run["state"] == "creating":
                run["state"] = "creation_failed"
        self._change(item_id, change)

    def review(self, item_id: str, run_id: str, user: str, decision: str, note: str, rows: list[dict]):
        if decision not in {"accepted", "rejected"} or not note.strip():
            raise ValueError("请选择复核结论并填写证据、建议核对意见")
        if decision == "accepted" and (not rows or any(x["comparison"] != "same" for x in rows)):
            raise ValueError("存在差异或未完成项，不能标记通过；请修正后重新运行")
        def change(raw, state, row):
            run = _owned_run(state, run_id, user)
            if decision == "accepted" and not run.get("execution_version"):
                raise ValueError("本次运行缺少执行版本记录，请重新运行后验收")
            if decision == "accepted" and not run.get("evaluation_as_of_date"):
                raise ValueError("该测试病例未固定评价时间点，结果随运行日期变化，不能验收通过；请复制为新病例并设定评价时间点")
            run["reviews"].append({"decision": decision, "note": note.strip(), "reviewed_by": user,
                                   "reviewed_at": _now(), "comparisons": deepcopy(rows)})
        self._change(item_id, change)


def _owned_run(state, run_id, user):
    run = next((r for r in state["runs"] if r["id"] == run_id and r["created_by"] == user), None)
    if run is None:
        raise LookupError("验收不存在或无权限")
    return run


def _read(raw, state, row):
    return {"revision": state["revision"], "answers": deepcopy(raw.get("golden_answers") or []),
            "evaluation_as_of_date": raw.get("evaluation_as_of_date") or None,
            "runs": deepcopy(state["runs"])}


def _now():
    return datetime.now(timezone.utc).isoformat()
