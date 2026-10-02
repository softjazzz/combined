"""业务只读工具：复用正式 API，不生成另一套质控或统计事实。"""
from __future__ import annotations

from urllib.parse import quote
from uuid import uuid4
from collections import Counter
from typing import Literal
from datetime import datetime, timedelta

import httpx
from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.services.qc_agent import business_drafts, business_rule_validation
from app.services.qc_agent.business_source_gaps import project_saved_source_gaps, source_gaps_card_text

from .business_store import BusinessSessionStore


class ToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReadResults(ToolInput):
    record_reference: str | None = Field(default=None, max_length=160)
    statuses: list[Literal["non_compliant", "data_gap", "compliant", "not_applicable", "not_executed", "needs_review", "uncertain", "technical_error"]] = Field(default_factory=list, max_length=8)
    page: int = Field(default=1, ge=1, le=100)
    page_size: int = Field(default=10, ge=1, le=10)
    detail: Literal["index", "saved_text"] = "index"
    expected_job_id: str | None = Field(default=None, min_length=1, max_length=128)

    @model_validator(mode="after")
    def require_page_version(self):
        if self.page > 1 and not self.expected_job_id:
            raise ValueError("后续页需要上一页返回的 expected_job_id")
        return self


class ReadIssue(ToolInput):
    result_id: str = Field(min_length=1, max_length=200)


class ReadRule(ToolInput):
    rule_id: str = Field(pattern=r"^LX0609-\d{2}-\d{2}-\d{2}$")


class SearchRules(ToolInput):
    query: str = Field(min_length=1, max_length=100)
    page: int = Field(default=1, ge=1, le=100)
    page_size: int = Field(default=5, ge=1, le=10)

    @model_validator(mode="after")
    def require_keywords(self):
        self.query = self.query.strip()
        if not self.query:
            raise ValueError("请输入规则名称或关键词")
        return self


class QueryStatistics(ToolInput):
    rule_id: str | None = Field(default=None, pattern=r"^LX0609-\d{2}-\d{2}-\d{2}$")
    result_status: str | None = Field(default=None, pattern=r"^(non_compliant|data_gap|compliant|not_applicable|not_executed|uncertain)$")
    page: int = Field(default=1, ge=1, le=100)
    rule_limit: int = Field(default=5, ge=1, le=75)


def comparison_range(start_text: str, end_text: str) -> tuple[datetime, datetime]:
    start = datetime.fromisoformat(start_text.replace("Z", "+00:00"))
    end = datetime.fromisoformat(end_text.replace("Z", "+00:00"))
    if start.utcoffset() is None or end.utcoffset() is None or start > end or end - start > timedelta(days=366):
        raise ValueError("比较需要带时区、顺序正确且不超过366天的完整起止日期")
    return start, end


def statistics_scope_text(filters: dict) -> str:
    def display(text):
        try:
            value = datetime.fromisoformat((text or "").replace("Z", "+00:00"))
            offset = value.strftime("%z")
            if not offset:
                return "未提供带时区的日期"
            return value.strftime("%Y年%m月%d日 %H:%M:%S") + f"（UTC{offset[:3]}:{offset[3:]}）"
        except ValueError:
            return "未提供完整日期"
    phase = {"inpatient": "在院", "discharged": "出院"}.get(filters.get("care_phase"), "未提供")
    return (f"机构：{filters.get('institute_id', '未提供')}；科室：{filters.get('department', '未提供')}；病例范围：{phase}\n"
            f"规则：{filters.get('rule_id') or '全部规则'}\n"
            f"质控完成期间（含起止）：{display(filters.get('completed_from'))} 至 {display(filters.get('completed_to'))}\n"
            "读取当前最新权威保存结果，不是期间历史快照；未验证两期历史版本相同或完整覆盖。\n"
            "范围病例数和结果不可用数为当前范围数量，未按期间过滤；期间内有效保存结果数量才按完成时间筛选。\n"
            "已评价数量包含未执行和不适用，不能视为真实执行覆盖率。\n")


class CompareStatistics(ToolInput):
    rule_id: str = Field(pattern=r"^LX0609-\d{2}-\d{2}-\d{2}$")
    baseline_completed_from: str = Field(min_length=1, max_length=64)
    baseline_completed_to: str = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def require_explicit_period(self):
        comparison_range(self.baseline_completed_from, self.baseline_completed_to)
        return self


class QueryFollowups(ToolInput):
    kind: Literal["notifications", "remediations"]
    page: int = Field(default=1, ge=1, le=100)
    page_size: int = Field(default=5, ge=1, le=10)


TOOL_DEFINITIONS = {
    "read_draft_facts": (ReadIssue, "仅医生视图：用户明确要求参考补充文字时，按已查看的不合规问题 result_id（用户已选卡片时写 @selected）读取正式建议及来源：序号0为保存结论原文，1起为前5条保存证据摘录。不读取当前文书全文，不判定是否已整改。"),
    "compose_reference_draft": (business_drafts.ComposeDraft, "仅医生视图：先用read_draft_facts取得来源后提交参考草稿。草稿是医生可写入病历的补充段落，只针对正式建议所指缺项，通常1至4段，不复述整条结论或其他已完成项。fact段只写所引来源（0为保存结论，1起为证据）明确出现的事实，必须填evidence_positions；来源未写明的临床意义、检查、诊疗、签名、时间或数值写成placeholder段（说明需医生填写什么；数字只可用正式建议或来源已有的时限等）。服务端校验数值来源，422时按原因改写一次重交。草稿卡完整展示，回答只简述，不复述全文，不称已整改。"),
    "read_rule_validation": (ReadRule, "仅管理视图读取现有规则验收阶段、样本覆盖、保存运行结论和验收入口。不读取测试病例原文，不执行验收；目录启用不表示验收通过，历史运行不证明当前部署已验收。"),
    "read_saved_results": (ReadResults, "分页读取正式保存结果。statuses为空查全类别；仅列不合规时指定non_compliant。每页最多10条，index和saved_text均在卡片完整展示结论建议，模型只收到索引；列清单无需另查证据或规则。追问具体原因或依据才用read_saved_issue。后续页带已看到的expected_job_id；管理下钻用统计返回record_reference。"),
    "read_saved_issue": (ReadIssue, "按稳定 result_id 读取同一任务的具体问题、正式建议和已保存病历证据。"),
    "read_rule": (ReadRule, "读取权威规则目录中的当前启用状态和院内实施口径；不是规范原文。"),
    "search_rules": (SearchRules, "不知道编号时按名称或关键词查当前权威目录。多个关键词用空格分开且必须全部匹配，支持中文及CT等英文；不做语义推断。选定候选后用read_rule读取口径；未命中不表示没有规范要求。"),
    "query_followups": (QueryFollowups, "读取既有通知或整改台账；医生仅当前病例，管理者仅授权科室。按源列表分页，无法证明病例授权的条目排除，空页不代表没有待办。仅展示保存状态与期限，不执行标记已读、催办或整改；没有全局总量。"),
    "query_statistics": (QueryStatistics, "沿用会话机构/科室、病例范围和质控完成日期读取正式统计，不改口径。规则概览按不合规次数降序默认前5条；rule_limit可指定1至75。page是病例页，返回record_reference用于选择具体病例。"),
    "compare_statistics": (CompareStatistics, "管理者跨期描述：同一明确规则，当前期间沿用会话筛选，基线起止必须来自用户明确期间，带时区且跨度不超过366天。缺少基线日期或规则时先追问，不自行推断上月/同期日界。机构、科室、病例范围固定；只读取两期正式原值，不计算差值、百分比或因果。来源是当前最新保存结果，不是历史快照；不得声称历史版本相同或覆盖率改善。基线不提供病例下钻。"),
}


def tool_specs(view: Literal["doctor", "manager"]) -> list[dict]:
    return [{"name": name, "description": description, "parameters": model.model_json_schema()}
            for name, (model, description) in TOOL_DEFINITIONS.items()
            if (name not in MANAGER_ONLY or view == "manager") and (name not in DOCTOR_ONLY or view == "doctor")]


MANAGER_ONLY = {"query_statistics", "compare_statistics", "read_rule_validation"}
DOCTOR_ONLY = {"read_draft_facts", "compose_reference_draft"}


def statistics_text(payload: dict) -> str:
    kpis = payload.get("kpis")
    kpis = kpis if isinstance(kpis, dict) else {}
    distribution = payload.get("rule_distribution")
    rows = [row for row in distribution if isinstance(row, dict)] if isinstance(distribution, list) else []
    def value(row, field):
        count = row.get(field)
        return "未提供" if count is None else count
    return (
        f"范围病例 {value(kpis, 'scoped_record_total')} 份\n"
        f"已保存结果 {value(kpis, 'ready_record_total')} 份\n"
        f"结果不可用 {value(kpis, 'unavailable_result_total')} 份\n"
        + "\n".join(
            f"{row.get('rule_name') or row.get('rule_id') or '未提供规则名称'}：不合规 {value(row, 'non_compliant_count')}；"
            f"资料不足 {value(row, 'data_gap_count')}；已评价 {value(row, 'evaluated_count')}"
            for row in rows
        )
    )


class BusinessTools:
    def __init__(self, store: BusinessSessionStore, client: httpx.AsyncClient):
        self.store, self.client = store, client

    async def read_api(self, path: str, params: dict | None = None) -> dict:
        try:
            response = await self.client.get(path, params=params)
        except httpx.HTTPError as exc:
            raise HTTPException(503, "业务服务连接失败，未取得有效数据") from exc
        if response.status_code >= 400:
            raise HTTPException(response.status_code, "业务读取失败，请核对访问范围或材料状态")
        try:
            payload = response.json()
        except ValueError as exc:
            raise HTTPException(502, "业务接口未返回有效数据") from exc
        if not isinstance(payload, dict) or payload.get("success") is False:
            raise HTTPException(502, "业务接口未返回有效数据")
        data = payload.get("data", payload)
        if not isinstance(data, dict):
            raise HTTPException(502, "业务接口数据格式不完整")
        return data

    def identity(self, metadata: dict, record_reference: str | None) -> dict:
        context = metadata["context"]
        if context["view"] == "doctor":
            current = {key: context[key] for key in ("institute_id", "patient_id", "visit_id")}
            if record_reference:
                binding = metadata["references"].get(record_reference, {})
                if binding.get("kind") != "record" or binding.get("identity") != current:
                    raise HTTPException(422, "当前医生会话只能读取已选病例")
            return current
        binding = metadata["references"].get(record_reference or "", {})
        if binding.get("kind") != "record":
            raise HTTPException(422, "请先从当前统计下钻选择病例")
        if binding["identity"].get("institute_id") != context.get("institute_id"):
            raise HTTPException(403, "病例来源不属于当前会话机构")
        return binding["identity"]

    async def saved_results(self, metadata: dict, user: dict, record_reference: str | None, params: ReadResults | None = None) -> dict:
        params = params or ReadResults(record_reference=record_reference)
        identity = self.identity(metadata, record_reference)
        visit = quote(identity["visit_id"], safe="")
        payload = await self.read_api(f"/api/v1/qc-agent/business/records/{visit}/latest-result", {
            "institute_id": identity["institute_id"], "patient_id": identity["patient_id"],
            "view": metadata["context"]["view"], "department": metadata["context"].get("department", ""),
        })
        if payload.get("state") != "ready":
            return {"state": payload.get("state"), "reason_code": payload.get("reason_code"), "references": []}
        if params.expected_job_id:
            seen = [binding for binding in metadata["references"].values() if binding.get("kind") == "saved_result" and binding.get("identity") == identity and binding.get("job_id") == params.expected_job_id]
            if not seen:
                raise HTTPException(404, "本会话尚未查看所选保存版本")
            if payload["job_id"] != params.expected_job_id or not any(binding.get("record_ref") == payload["record_ref"] for binding in seen):
                raise HTTPException(409, "保存版本已变化，请从第一页重新查看；本次未合并新旧页面")
        items = payload.get("items", [])
        matched = [item for item in items if not params.statuses or item.get("status") in params.statuses]
        offset = (params.page - 1) * params.page_size
        references = []
        for index, item in enumerate(matched[offset:offset + params.page_size], offset + 1):
            rule_id = item.get("rule_id") or item.get("rule_code")
            result_id = f"result:{payload['job_id']}:{payload['record_ref']}:{rule_id}"
            self.store.bind(metadata["session_id"], user, result_id, {
                "kind": "saved_result", "identity": identity, "job_id": payload["job_id"],
                "record_ref": payload["record_ref"], "rule_id": rule_id,
            })
            references.append({**self.issue_reference(result_id, item, payload), "position": index})
        return {
            "state": "ready", "job_id": payload["job_id"], "rule_set_version": payload.get("rule_set_version"),
            "is_complete": payload.get("is_complete"), "missing_rule_ids": payload.get("missing_rule_ids", []),
            "conflicting_rule_ids": payload.get("conflicting_rule_ids", []),
            "result_time": payload.get("completed_at"),
            "result_time_note": "正式接口未提供保存时间" if not payload.get("completed_at") else "",
            "references": references,
            # 只数保存状态并筛选展示，不生成新的医学结论。
            "result_page": {"job_id": payload["job_id"], "record_ref": payload["record_ref"], "detail": params.detail, "statuses": list(dict.fromkeys(params.statuses)) if params.statuses else [], "page": params.page, "page_size": params.page_size, "total": len(items), "matched_total": len(matched), "returned": len(references), "has_more": offset + len(references) < len(matched), "status_counts": dict(Counter(item.get("status") or "unknown" for item in items)), "reference_ids": [ref["id"] for ref in references]},
        }

    @staticmethod
    def issue_reference(result_id: str, item: dict, payload: dict) -> dict:
        return {
            "id": result_id, "kind": "saved_result", "rule_id": item.get("rule_id") or item.get("rule_code"),
            "title": item.get("qc_point") or item.get("rule_name") or item.get("rule_id", "质控结果"),
            "status": item.get("status"), "conclusion": item.get("conclusion", ""),
            "suggestion": item.get("suggestion", ""),
            "locator": f"已保存任务 {payload['job_id']} · 规则版本 {payload.get('rule_set_version', '未提供')}",
        }

    async def issue(self, metadata: dict, result_id: str) -> dict:
        binding = metadata["references"].get(result_id)
        if not binding or binding.get("kind") != "saved_result":
            raise HTTPException(404, "问题不属于本会话已查看的结果；请原样使用结果卡片或列表返回的完整 result_id（形如 result:任务:病例:规则），不要改写")
        identity = binding["identity"]
        context = metadata["context"]
        if context["view"] == "doctor" and any(identity.get(key) != context.get(key) for key in ("institute_id", "patient_id", "visit_id")):
            raise HTTPException(403, "问题来源不属于当前会话病例")
        if context["view"] == "manager" and identity.get("institute_id") != context.get("institute_id"):
            raise HTTPException(403, "问题来源不属于当前会话机构")
        payload = await self.read_api(f"/api/v1/qc-agent/business/records/{quote(identity['visit_id'], safe='')}/latest-result", {
            "institute_id": identity["institute_id"], "patient_id": identity["patient_id"],
            "view": metadata["context"]["view"], "department": metadata["context"].get("department", ""),
        })
        if payload.get("job_id") != binding["job_id"] or payload.get("record_ref") != binding["record_ref"]:
            raise HTTPException(409, "结果版本已变化，请重新查看问题；本次未把旧问题替换为新判定")
        item = next((row for row in payload.get("items", []) if (row.get("rule_id") or row.get("rule_code")) == binding["rule_id"]), None)
        if item is None:
            raise HTTPException(404, "当前保存结果中未找到这条问题")
        reference = self.issue_reference(result_id, item, payload)
        evidence = item.get("evidence") or item.get("customer_evidence") or []
        reference["evidence"] = evidence
        reference["text"] = "\n\n".join(filter(None, [
            reference.get("conclusion"), reference.get("suggestion"),
            *[f"{row.get('source_type', '')} · {row.get('source_ref', '')} · {row.get('record_time', '')} · {row.get('field_path', '')}\n{row.get('evidence_excerpt', '未提供原文摘录')}" for row in evidence if isinstance(row, dict)],
        ]))
        # 仅资料不足或保存了缺口字段时附带安全投影；其它结论不加缺口说明，避免模型据此重判。
        has_gaps = item.get("status") == "data_gap" or any(key in item for key in ("missing_sources", "missing_fields", "source_availability", "data_gap_details"))
        if has_gaps:
            reference["text"] += "\n\n" + source_gaps_card_text(item)
        return {"references": [reference], "evidence": evidence, "evidence_scope": "执行时保存的证据摘录；不是重新读取的完整文书", "reason_code": item.get("reason_code"),
                **({"source_gaps": project_saved_source_gaps(item)} if has_gaps else {}),
                "job_id": payload.get("job_id"), "rule_set_version": payload.get("rule_set_version"), "result_time": payload.get("completed_at"),
                "version_note": "规则版本仅为正式保存结果的执行版本标识；未读取该版本的历史规则正文，不得用当前目录冒充当时判据"}

    async def compare_statistics(self, params: CompareStatistics, metadata: dict, user: dict) -> dict:
        context = metadata["context"]
        if context["view"] != "manager":
            raise HTTPException(422, "跨期比较仅适用于已限定范围的管理工作台")
        try:
            comparison_range(context.get("completed_from") or "", context.get("completed_to") or "")
        except ValueError as exc:
            raise HTTPException(422, "当前比较期间需要带时区、顺序正确且不超过366天的完整起止日期") from exc
        if not context.get("institute_id") or not context.get("department") or context.get("care_phase") not in {"inpatient", "discharged"}:
            raise HTTPException(422, "比较需要当前会话的完整机构、科室和病例范围")
        fixed = {key: context[key] for key in ("institute_id", "department", "care_phase")}
        requests = [("current", "当前期间", context["completed_from"], context["completed_to"]),
                    ("baseline", "基线期间", params.baseline_completed_from, params.baseline_completed_to)]
        periods = []
        # 先取得两期原始响应；读取失败不保存半组来源，不自动用其他期间替代。
        for key, label, start, end in requests:
            filters = {**fixed, "rule_id": params.rule_id, "completed_from": start, "completed_to": end, "page": 1}
            payload = await self.read_api("/api/v1/qc-agent/business/statistics", filters)
            notes = []
            kpis = payload.get("kpis")
            ready = kpis.get("ready_record_total") if isinstance(kpis, dict) else None
            if not isinstance(ready, int) or isinstance(ready, bool) or ready < 0:
                notes.append("正式接口未提供期间内有效保存结果数量，不能判断该期数据是否完整")
            elif ready == 0:
                notes.append("该期没有期间内有效保存结果，不能将缺结果解释为零问题或改善")
            distribution = payload.get("rule_distribution")
            rows = [row for row in distribution if isinstance(row, dict) and row.get("rule_id") == params.rule_id] if isinstance(distribution, list) else []
            if not rows:
                notes.append("该期未返回所选规则统计，不能补零或据此判断规则未执行")
            elif any(row.get(field) is None for row in rows for field in ("evaluated_count", "non_compliant_count", "data_gap_count", "uncertain_count")):
                notes.append("该期所选规则统计字段不完整，只能描述已返回字段")
            periods.append({"key": key, "label": label, "filters": filters,
                            "statistics": {field: payload[field] for field in ("scope", "kpis", "status_distribution", "rule_distribution") if field in payload},
                            "data_notes": notes})
        references = []
        for period in periods:
            title = f"{period['label']}规则统计 · {params.rule_id}"
            reference_id = f"statistics:{uuid4()}"
            self.store.bind(metadata["session_id"], user, reference_id, {"kind": "statistics", "filters": period["filters"], "title": title})
            period["source_reference"] = reference_id
            references.append({"id": reference_id, "kind": "statistics", "title": title,
                               "locator": statistics_scope_text(period["filters"]),
                               "text": statistics_scope_text(period["filters"]) + statistics_text(period["statistics"]) + "\n" + "\n".join(period["data_notes"])})
        return {"comparison": {"rule_id": params.rule_id, "periods": periods, "same_rule_version_verified": False,
                               "limitations": ["两期均读取当前授权范围内每份病例最新权威保存结果，再按完成时间筛选；不是期间历史快照，较新复检可能使旧期间结果不再入选。",
                                               "范围病例数和结果不可用数是当前科室及病例范围的数量，不是各期间病例总量或失败数；期间内有效保存结果数量才按完成时间筛选。",
                                               "已评价数量包含所选规则返回的所有状态，包括未执行和不适用，不能当作真实执行覆盖率。",
                                               "正式接口未提供两期历史执行版本、历史规则正文、完整执行覆盖和同步状态，无法验证同规则版本或完整覆盖；不得归因或把缺失补零。",
                                               "只描述两期原值；期间长度可能不同，不计算差值、同比、环比或百分比；基线不自动提供病例下钻。"]},
                "references": references, "metric_owner": "LX0609 正式结果分析接口"}

    async def draft_reference(self, metadata: dict, result_id: str, segments: list, draft_id: str) -> dict:
        """每次生成或回读都重新读取同一保存问题并校验；版本变化由 issue 返回409。"""
        if metadata["context"]["view"] != "doctor":
            raise HTTPException(422, "参考草稿仅在医生当前病例会话中提供")
        issue = await self.issue(metadata, result_id)
        reference = business_drafts.require_draftable(issue)
        segments = [business_drafts.DraftSegment.model_validate(segment) for segment in segments]
        business_drafts.validate_segments(segments, business_drafts.draft_evidence(issue["evidence"], reference.get("conclusion")), reference.get("suggestion"))
        return {"id": draft_id, "kind": "draft", "rule_id": reference.get("rule_id"), "title": f"参考草稿 · {reference.get('title')}",
                "locator": "参考草稿，不替代正式保存建议", "text": business_drafts.draft_card_text(reference, segments)}

    async def execute(self, name: str, arguments: dict, metadata: dict, user: dict) -> dict:
        if name not in TOOL_DEFINITIONS:
            raise HTTPException(404, "工具未提供")
        model, _ = TOOL_DEFINITIONS[name]
        params = model.model_validate(arguments)
        if name == "read_draft_facts":
            if metadata["context"]["view"] != "doctor":
                raise HTTPException(422, "参考草稿仅在医生当前病例会话中提供")
            issue = await self.issue(metadata, params.result_id)
            reference = business_drafts.require_draftable(issue)
            return {"result_id": params.result_id, "rule_id": reference.get("rule_id"), "title": reference.get("title"),
                    "conclusion": reference.get("conclusion"), "suggestion": reference.get("suggestion"),
                    "evidence": business_drafts.draft_evidence(issue["evidence"], reference.get("conclusion")), "job_id": issue.get("job_id"),
                    "scope_note": "仅前5条保存证据摘录且每条截断至300字；不是当前文书全文，不能证明病历未书写或已整改", "references": []}
        if name == "compose_reference_draft":
            draft_id = f"draft:{uuid4()}"
            segments = [segment.model_dump() for segment in params.segments]
            reference = await self.draft_reference(metadata, params.result_id, segments, draft_id)
            self.store.bind(metadata["session_id"], user, draft_id, {"kind": "draft", "result_id": params.result_id, "segments": segments})
            return {"draft": {"result_id": params.result_id, "segment_count": len(segments),
                              "placeholder_count": sum(segment["kind"] == "placeholder" for segment in segments)},
                    "references": [reference]}
        if name == "read_rule_validation":
            record = await run_in_threadpool(business_rule_validation.read_rule_validation, params.rule_id, metadata, user)
            reference_id = f"rule-validation:{params.rule_id}"
            self.store.bind(metadata["session_id"], user, reference_id, {"kind": "rule_validation", "rule_id": params.rule_id})
            reference = {"id": reference_id, "kind": "rule", "rule_id": params.rule_id,
                         "title": f"规则验收记录 · {params.rule_id}", "locator": "已保存的规则验收摘要（只读）",
                         "entry_path": record["entry_path"], "text": business_rule_validation.rule_validation_card_text(record)}
            return {"validation_record": record, "references": [reference]}
        if name == "read_saved_results":
            return await self.saved_results(metadata, user, params.record_reference, params)
        if name == "read_saved_issue":
            return await self.issue(metadata, params.result_id)
        if name == "compare_statistics":
            return await self.compare_statistics(params, metadata, user)
        if name == "query_followups":
            session_id = quote(metadata["session_id"], safe="")
            payload = await self.read_api(f"/api/v1/qc-agent/business/sessions/{session_id}/followups", params.model_dump())
            references = []
            bound_cases = {}
            items = []
            for item in payload.get("items", []):
                identity = item["identity"]
                key = tuple(identity[field] for field in ("institute_id", "patient_id", "visit_id"))
                if key not in bound_cases:
                    reference_id = f"record:{uuid4()}"
                    self.store.bind(metadata["session_id"], user, reference_id, {"kind": "record", "identity": identity})
                    bound_cases[key] = reference_id
                    references.append({"id": reference_id, "kind": "record", "title": f"提醒/整改关联病例 · {identity['visit_id']}",
                                       "locator": "已核验授权的提醒/整改关联病例；打开后读取当前保存质控结果"})
                items.append({**item, "record_reference": bound_cases[key]})
            return {**payload, "items": items, "references": references}
        if name == "search_rules":
            from app.services.luxian_0609_rule_master import LUXIAN_0609_RULE_MASTER_VERSION, load_luxian_0609_rule_master
            keywords = params.query.casefold().split()
            # 目录是唯一事实来源；仅匹配文本，不推断医学同义词或发布状态。
            rules = sorted((row for row in load_luxian_0609_rule_master()
                            if all(word in " ".join((row.rule_id, row.title, row.policy_summary, row.definition_note)).casefold()
                                   for word in keywords)), key=lambda row: row.rule_id)
            offset = (params.page - 1) * params.page_size
            candidates = [{"rule_id": row.rule_id, "title": row.title,
                           "implementation_status": row.implementation_status, "phase_status": row.phase_status,
                           "release_scope": row.release_scope} for row in rules[offset:offset + params.page_size]]
            return {"rule_candidates": candidates, "catalog_version": LUXIAN_0609_RULE_MASTER_VERSION,
                    "rule_search": {"query": params.query, "page": params.page, "page_size": params.page_size,
                                    "total": len(rules), "returned": len(candidates), "has_more": offset + len(candidates) < len(rules)},
                    "scope_note": "仅当前权威目录文本匹配候选，不是历史执行版本或规范原文；选定后用read_rule读取口径，多候选不得默认视为同一规则", "references": []}
        if name == "read_rule":
            from app.services.luxian_0609_rule_master import LUXIAN_0609_RULE_MASTER_VERSION, load_luxian_0609_rule_master
            from dataclasses import asdict
            rule = next((row for row in load_luxian_0609_rule_master() if row.rule_id == params.rule_id), None)
            if rule is None:
                raise HTTPException(404, "规则目录未找到该规则")
            reference_id = f"rule:{rule.rule_id}"
            self.store.bind(metadata["session_id"], user, reference_id, {"kind": "rule", "rule_id": rule.rule_id})
            return {"rule": asdict(rule), "catalog_version": LUXIAN_0609_RULE_MASTER_VERSION, "historical_definition_available": False, "scope_note": "当前系统目录注册状态与实施口径；active_criteria/pending_criteria 是发布范围字段，空数组不表示医学判据缺失。历史执行版本及规范原文需另行核对", "references": [{"id": reference_id, "kind": "rule", "title": rule.title, "rule_id": rule.rule_id, "text": f"目录注册状态：{rule.implementation_status}\n发布阶段：{rule.phase_status}\n发布范围：{rule.release_scope}\n已发布子项（目录标识）：{'、'.join(rule.active_criteria) or '未单列'}\n待发布子项（目录标识）：{'、'.join(rule.pending_criteria) or '未单列'}\n待发布原因（目录代码）：{rule.pending_reason_code or '未单列'}\n实施口径：{rule.policy_summary}\n{rule.definition_note}", "locator": "当前规则目录；不是历史执行版本或规范原文"}]}
        context = metadata["context"]
        if context["view"] != "manager":
            raise HTTPException(422, "请在管理工作台限定范围后问数")
        filters = {key: context[key] for key in ("institute_id", "department", "care_phase", "completed_from", "completed_to") if key in context}
        filters.setdefault("care_phase", "discharged")
        filters.update(params.model_dump(exclude_none=True, exclude={"rule_limit"}))
        payload = await self.read_api("/api/v1/qc-agent/business/statistics", filters)
        references = []
        for record in payload.get("record_page", {}).get("items", []):
            reference_id = f"record:{uuid4()}"
            identity = {key: record[key] for key in ("institute_id", "patient_id", "visit_id")}
            self.store.bind(metadata["session_id"], user, reference_id, {"kind": "record", "identity": identity})
            references.append({"id": reference_id, "kind": "record", "title": f"{record.get('patient_name') or '病例'} · {record['visit_id']}", "locator": f"{record.get('department', '')} · 当前统计病例下钻"})
        statistics_id = f"statistics:{uuid4()}"
        self.store.bind(metadata["session_id"], user, statistics_id, {"kind": "statistics", "filters": filters})
        references.insert(0, {"id": statistics_id, "kind": "statistics", "title": "当前范围质控统计", "locator": "按质控完成时间；每份病例最新 Canonical 结果", "text": statistics_text(payload)})
        # 正式统计值与明细原样搬运，不在助手中另行聚合。
        return {"statistics": payload, "filters": filters, "metric_owner": "LX0609 正式结果分析接口", "references": references, "statistics_page": {"rule_limit": params.rule_limit}}
