"""业务只读工具：复用正式 API，不生成另一套质控或统计事实。"""
from __future__ import annotations

from urllib.parse import quote
from uuid import uuid4
from collections import Counter
from typing import Literal

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

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


TOOL_DEFINITIONS = {
    "read_saved_results": (ReadResults, "分页读取正式保存结果。statuses为空查全类别；仅列不合规时指定non_compliant。每页最多10条，index和saved_text均在卡片完整展示结论建议，模型只收到索引；列清单无需另查证据或规则。追问具体原因或依据才用read_saved_issue。后续页带已看到的expected_job_id；管理下钻用统计返回record_reference。"),
    "read_saved_issue": (ReadIssue, "按稳定 result_id 读取同一任务的具体问题、正式建议和已保存病历证据。"),
    "read_rule": (ReadRule, "读取权威规则目录中的当前启用状态和院内实施口径；不是规范原文。"),
    "search_rules": (SearchRules, "不知道编号时按名称或关键词查当前权威目录。多个关键词用空格分开且必须全部匹配，支持中文及CT等英文；不做语义推断。选定候选后用read_rule读取口径；未命中不表示没有规范要求。"),
    "query_statistics": (QueryStatistics, "沿用会话机构/科室、病例范围和质控完成日期读取正式统计，不改口径。规则概览按不合规次数降序默认前5条；rule_limit可指定1至75。page是病例页，返回record_reference用于选择具体病例。"),
}


def tool_specs(view: Literal["doctor", "manager"]) -> list[dict]:
    return [{"name": name, "description": description, "parameters": model.model_json_schema()}
            for name, (model, description) in TOOL_DEFINITIONS.items()
            if name != "query_statistics" or view == "manager"]


def statistics_text(payload: dict) -> str:
    kpis = payload.get("kpis", {})
    return (
        f"范围病例 {kpis.get('scoped_record_total', '未提供')} 份\n"
        f"已保存结果 {kpis.get('ready_record_total', '未提供')} 份\n"
        f"结果不可用 {kpis.get('unavailable_result_total', '未提供')} 份\n"
        + "\n".join(
            f"{row.get('rule_name') or row.get('rule_id')}：不合规 {row.get('non_compliant_count', '未提供')}；"
            f"资料不足 {row.get('data_gap_count', '未提供')}；已评价 {row.get('evaluated_count', '未提供')}"
            for row in payload.get("rule_distribution", [])
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
            if record_reference:
                raise HTTPException(422, "当前医生会话只能读取已选病例")
            return {key: context[key] for key in ("institute_id", "patient_id", "visit_id")}
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
            raise HTTPException(404, "问题不属于本会话已查看的结果")
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
        return {"references": [reference], "evidence": evidence, "evidence_scope": "执行时保存的证据摘录；不是重新读取的完整文书", "reason_code": item.get("reason_code"),
                "job_id": payload.get("job_id"), "rule_set_version": payload.get("rule_set_version"), "result_time": payload.get("completed_at"),
                "version_note": "规则版本仅为正式保存结果的执行版本标识；未读取该版本的历史规则正文，不得用当前目录冒充当时判据"}

    async def execute(self, name: str, arguments: dict, metadata: dict, user: dict) -> dict:
        if name not in TOOL_DEFINITIONS:
            raise HTTPException(404, "工具未提供")
        model, _ = TOOL_DEFINITIONS[name]
        params = model.model_validate(arguments)
        if name == "read_saved_results":
            return await self.saved_results(metadata, user, params.record_reference, params)
        if name == "read_saved_issue":
            return await self.issue(metadata, params.result_id)
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
