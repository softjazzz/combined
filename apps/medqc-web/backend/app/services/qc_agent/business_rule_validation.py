"""规则验收记录只读摘要；不搬运测试病例、原文或自由文本复核意见。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from uuid import UUID

from fastapi import HTTPException
import sqlalchemy as sa
from sqlalchemy.exc import SQLAlchemyError


RULE_PATTERN = re.compile(r"LX0609-\d{2}-\d{2}-\d{2}\Z")
STAGES = frozenset({"preparing", "ready_to_run", "running", "reviewing", "pending_conclusion",
                    "pending_approval", "approved_pending_release", "released", "rejected"})
STATUSES = ("compliant", "non_compliant", "not_applicable", "data_gap")
RUN_LIMIT = 5
HOSPITAL_TZ = timezone(timedelta(hours=8))
STAGE_LABELS = {"preparing": "准备中", "ready_to_run": "待运行", "running": "验证中", "reviewing": "逐例复核中",
                "pending_conclusion": "待保存结论", "pending_approval": "待审批", "approved_pending_release": "已批准待发布",
                "released": "已发布", "rejected": "已拒绝"}
STATUS_LABELS = {"compliant": "合规", "non_compliant": "不合规", "not_applicable": "不适用", "data_gap": "资料不足"}
SCOPE_NOTE = "规则验收记录及测试样本覆盖，不是当前病例或科室质控结果；保存结论不代表当前部署规则已经验收通过。入口继续受管理员/质控管理者权限控制。"


def validate_rule_id(rule_id: str) -> str:
    if not isinstance(rule_id, str) or not RULE_PATTERN.fullmatch(rule_id):
        raise HTTPException(422, "请提供有效的四段式规则编号")
    return rule_id


def require_validation_reader(metadata: dict, user: dict) -> None:
    # 与现成验收 GET 的角色门禁相同；医生视图也不开放全局验收记录。
    if metadata.get("context", {}).get("view") != "manager" or not set(user.get("roles") or []).intersection({"admin", "qc_manager"}):
        raise HTTPException(403, "规则验收记录仅向管理视图的管理员或质控管理者开放")


def _uuid(value):
    try:
        return str(UUID(value)) if isinstance(value, str) else None
    except ValueError:
        return None


def _time(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return value if parsed.utcoffset() is not None else None


def _token(value):
    return value if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.:/@+-]{1,160}", value) else None


def _version(value):
    runtime = value.get("lx0609_task_runtime") if isinstance(value, dict) else None
    implementation = runtime.get("implementation") if isinstance(runtime, dict) else None
    if not isinstance(implementation, dict):
        return None
    projected = {key: _token(implementation[key]) for key in ("kind", "build_id", "git_commit", "id") if key in implementation}
    projected = {key: value for key, value in projected.items() if value is not None}
    return {"lx0609_task_runtime": {"implementation": projected}} if projected else None


def project_rule_validation(payload: dict, rule_id: str) -> dict:
    """消费正式 owner 的详情结构；未知字段默认拒绝输出，不重判验收状态。"""
    validate_rule_id(rule_id)
    if not isinstance(payload, dict):
        raise HTTPException(502, "规则验收接口未返回有效记录")
    rule = payload.get("rule")
    if not isinstance(rule, dict) or rule.get("rule_id") != rule_id or not isinstance(payload.get("stage"), str) or payload["stage"] not in STAGES:
        raise HTTPException(502, "规则验收接口未返回所选规则的有效阶段，不能确认验收记录")
    projected_rule = {"rule_id": rule_id}
    for key in ("name", "source_document"):
        if isinstance(rule.get(key), str):
            projected_rule[key] = rule[key]
    if isinstance(rule.get("release_scope"), str) and rule["release_scope"] in {"default", "acceptance_only"}:
        projected_rule["release_scope"] = rule["release_scope"]
    result = {"rule": projected_rule, "stage": payload["stage"]}
    notes = []
    coverage = payload.get("coverage")
    if isinstance(coverage, dict):
        safe_coverage = {}
        counts = coverage.get("counts")
        if isinstance(counts, dict):
            safe_coverage["counts"] = {}
            for status in STATUSES:
                source_counts = counts.get(status)
                if isinstance(source_counts, dict):
                    safe_coverage["counts"][status] = {kind: number for kind, number in source_counts.items()
                                                      if kind in {"synthetic", "real_copy"} and type(number) is int and number >= 0}
        if isinstance(coverage.get("gaps"), list) and all(isinstance(status, str) and status in STATUSES for status in coverage["gaps"]):
            safe_coverage["gaps"] = list(coverage["gaps"])
        if type(coverage.get("acceptance_cases")) is int and coverage["acceptance_cases"] >= 0:
            safe_coverage["acceptance_cases"] = coverage["acceptance_cases"]
        result["coverage"] = safe_coverage
        if (not all(set(safe_coverage.get("counts", {}).get(status, {})) == {"synthetic", "real_copy"} for status in STATUSES)
                or "gaps" not in safe_coverage or "acceptance_cases" not in safe_coverage):
            notes.append("验收覆盖字段不完整，本摘要不补零或判定覆盖充分")
    else:
        notes.append("正式记录未提供覆盖字段，不能按零覆盖或完整覆盖解读")
    runs = payload.get("runs")
    events = payload.get("events")
    if isinstance(runs, list):
        safe_runs = []
        for run in runs[:RUN_LIMIT]:
            if not isinstance(run, dict) or run.get("rule_id") != rule_id or not _uuid(run.get("id")):
                notes.append("存在无法安全定位的运行元数据，本摘要未展示该条记录")
                continue
            safe = {"id": run["id"]}
            if isinstance(run.get("state"), str) and run["state"] in {"creating", "bound", "creation_failed"}:
                safe["state"] = run["state"]
            if _time(run.get("created_at")):
                safe["created_at"] = run["created_at"]
            if isinstance(run.get("build_kind"), str) and run["build_kind"] in {"release", "development"}:
                safe["build_kind"] = run["build_kind"]
            safe["execution_version"] = _version(run.get("execution_version"))
            implementation = ((safe["execution_version"] or {}).get("lx0609_task_runtime") or {}).get("implementation") or {}
            safe["version_note"] = ("仅为该保存运行的执行标识；未验证与当前部署版本一致，不能证明当前规则已通过验收"
                                    if any(key in implementation for key in ("build_id", "git_commit", "id"))
                                    else "该运行未提供可用执行版本；不得用当前目录或模型配置补足")
            if isinstance(events, list):
                decisions = []
                for event in events:
                    if not isinstance(event, dict) or event.get("rule_id") != rule_id or event.get("run_id") != run["id"]:
                        continue
                    allowed = {"conclusion": {"accepted", "rejected"}, "approval": {"approved", "rejected"}}
                    if not isinstance(event.get("kind"), str) or not isinstance(event.get("decision"), str) or event["decision"] not in allowed.get(event["kind"], set()):
                        continue
                    decision = {"kind": event["kind"], "decision": event["decision"]}
                    if _time(event.get("created_at")):
                        decision["created_at"] = event["created_at"]
                    decisions.append(decision)
                safe["saved_decisions"] = decisions
            else:
                notes.append("正式记录未提供保存结论字段，不能据此判断该运行是否已通过")
            safe_runs.append(safe)
        result["runs"] = safe_runs
        result["run_limit"] = RUN_LIMIT
        result["has_more_runs"] = len(runs) > RUN_LIMIT
    else:
        notes.append("正式记录未提供运行列表，不能按没有运行或已通过解读")
    result["data_notes"] = list(dict.fromkeys(notes))
    result["entry_path"] = f"/workstation-v4/rules/validation/{rule_id}"
    result["scope_note"] = SCOPE_NOTE
    return result


def rule_validation_card_text(projected: dict) -> str:
    """仅从摘要白名单生成中文来源；不拼接原始事件、病例或复核自由文本。"""
    def number(value):
        return str(value) if type(value) is int and value >= 0 else "未提供"
    def time_text(value):
        if not _time(value):
            return "未提供时间"
        # owner 按 UTC 保存；来源卡统一换算为医院所在时区展示，并保留偏移标注。
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(HOSPITAL_TZ)
        offset = parsed.strftime("%z")
        return parsed.strftime("%Y年%m月%d日 %H:%M:%S") + f"（UTC{offset[:3]}:{offset[3:]}）"
    rule = projected.get("rule")
    rule_id = rule.get("rule_id") if isinstance(rule, dict) else None
    lines = [f"规则验收记录：{rule_id if isinstance(rule_id, str) and RULE_PATTERN.fullmatch(rule_id) else '未提供有效编号'}",
             f"记录阶段：{STAGE_LABELS.get(projected.get('stage'), '未提供有效阶段')}", SCOPE_NOTE,
             "测试样本覆盖（保存计数，不是执行覆盖率）："]
    coverage = projected.get("coverage")
    if isinstance(coverage, dict):
        counts = coverage.get("counts")
        counts = counts if isinstance(counts, dict) else {}
        for status, label in STATUS_LABELS.items():
            values = counts.get(status)
            values = values if isinstance(values, dict) else {}
            lines.append(f"{label}：合成样本 {number(values.get('synthetic'))}；真实病历副本样本 {number(values.get('real_copy'))}")
        lines.append(f"用于验收的样本数：{number(coverage.get('acceptance_cases'))}")
        gaps = coverage.get("gaps")
        if isinstance(gaps, list) and all(isinstance(status, str) and status in STATUS_LABELS for status in gaps):
            lines.append("保存的状态覆盖缺口：" + ("、".join(STATUS_LABELS[status] for status in gaps) or "未列出缺口（不代表当前部署已通过验收）"))
        else:
            lines.append("状态覆盖缺口字段未提供或不完整，不能按覆盖充分解读")
    else:
        lines.append("未提供覆盖字段，不能按零覆盖或完整覆盖解读")
    lines.append("最近保存运行（最多5条）：")
    runs = projected.get("runs")
    if not isinstance(runs, list):
        lines.append("未提供运行列表，不能判断是否已运行或已通过")
    elif not runs:
        lines.append("本摘要未展示保存运行；不能据此确认当前规则验收通过")
    else:
        for index, run in enumerate(runs[:RUN_LIMIT], 1):
            if not isinstance(run, dict):
                continue
            state = {"creating": "创建中", "bound": "已绑定任务", "creation_failed": "创建失败"}.get(run.get("state"), "未提供有效状态")
            lines.append(f"运行{index}：{state}；保存时间：{time_text(run.get('created_at'))}")
            version = _version(run.get("execution_version"))
            implementation = ((version or {}).get("lx0609_task_runtime") or {}).get("implementation") or {}
            identifiers = [f"{label}：{implementation[key]}" for key, label in (("build_id", "构建标识"), ("git_commit", "代码版本"), ("id", "版本标识")) if key in implementation]
            lines.append("；".join(identifiers) if identifiers else "未提供可定位的执行版本，不能用当前目录或模型配置补足")
            lines.append("该记录的版本与当前部署的一致性尚未验证")
            decisions = run.get("saved_decisions")
            if not isinstance(decisions, list):
                lines.append("未提供保存结论或批准记录，不能据此判断已通过")
            elif not decisions:
                lines.append("本摘要未展示该运行的已保存结论或批准")
            else:
                labels = {("conclusion", "accepted"): "保存结论：已接受", ("conclusion", "rejected"): "保存结论：已拒绝",
                          ("approval", "approved"): "保存审批：已批准", ("approval", "rejected"): "保存审批：已拒绝"}
                for decision in decisions:
                    if not isinstance(decision, dict):
                        continue
                    kind, value = decision.get("kind"), decision.get("decision")
                    label = labels.get((kind, value)) if isinstance(kind, str) and isinstance(value, str) else None
                    if label:
                        lines.append(f"{label}；时间：{time_text(decision.get('created_at'))}")
    if projected.get("has_more_runs") is True:
        lines.append("还有更早运行未在本摘要展示，可到受权限控制的规则验收入口查看")
    return "\n".join(lines)


def _readonly_service():
    from app.database.connection import DB_SCHEMA_MODE, SessionLocal
    from app.services.rule_validation import RuleValidationService, define_tables, rule_catalog
    if SessionLocal is None:
        raise HTTPException(503, "验收记录数据库尚未配置，未取得有效记录")
    schema = "qc" if DB_SCHEMA_MODE == "split" else None
    # 显式定义读取所需列，禁止进入旧样本池及验收表的首次使用 create_all。
    items = sa.Table("manual_problem_sample_pool_items", sa.MetaData(),
                     sa.Column("id", sa.String), sa.Column("pool_id", sa.String),
                     sa.Column("raw_payload_json", sa.Text), sa.Column("patient_name", sa.String),
                     sa.Column("department", sa.String), sa.Column("matched_institute_id", sa.String),
                     sa.Column("matched_patient_id", sa.String), sa.Column("matched_visit_id", sa.String), schema=schema)
    runs, events = define_tables(sa.MetaData(), schema)
    return RuleValidationService(item_table=items, runs_table=runs, events_table=events, session_factory=SessionLocal, catalog=rule_catalog)


def _latest_rows(rule_id: str, run: dict):
    from app.services.custom_qc_workspace_service import CustomQCWorkspaceService
    from app.services.rule_validation import compare_cases
    from app.routers.qc_sichuan import _hydrate_luxian_canonical_batch_job_or_409
    if run.get("job_id"):
        workspace = CustomQCWorkspaceService(readonly=True)
        job = workspace.get_batch_job_for_processing(job_id=run["job_id"])
        if job is None:
            raise HTTPException(404, "验收运行对应的质控任务不存在")
        job = _hydrate_luxian_canonical_batch_job_or_409(workspace=workspace, job=job)
    else:
        job = {"status": "creation_failed" if run["state"] == "creation_failed" else "creating"}
    # 与正式 owner 同样比较，仅供 derive_stage；病例/结果比较行不离开模块。
    return compare_cases(rule_id, run["cases"] + run["regression_cases"], job)


def read_rule_validation(rule_id: str, metadata: dict, user: dict) -> dict:
    """管理员读取已有记录；只读 owner 注入，缺表明确503，不初始化、不运行验收。"""
    require_validation_reader(metadata, user)
    validate_rule_id(rule_id)
    from app.services.rule_validation import derive_stage
    try:
        service = _readonly_service()
        rule = service._rule(rule_id)
        cases = service.list_cases(rule_id)
        runs = service.list_runs(rule_id)
        events = service.list_events(rule_id)
        rows = _latest_rows(rule_id, runs[0]) if runs else None
        summary = service.summarize(rule_id, run=runs[0] if runs else None, rows=rows)
        return project_rule_validation({"rule": rule, "stage": derive_stage(rule, cases, runs, events, rows),
                                        "coverage": summary["coverage"], "runs": runs, "events": events}, rule_id)
    except LookupError as exc:
        raise HTTPException(404, "所选规则不存在可读取的验收记录") from exc
    except SQLAlchemyError as exc:
        raise HTTPException(503, "验收记录存储尚未就绪或暂不可用，未确认读取成功") from exc
