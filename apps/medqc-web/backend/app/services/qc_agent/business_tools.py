"""业务只读工具：复用正式 API，不生成另一套质控或统计事实。"""
from __future__ import annotations

from urllib.parse import quote
from uuid import uuid4

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .business_store import BusinessSessionStore


class ToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReadResults(ToolInput):
    record_reference: str | None = Field(default=None, max_length=160)


class ReadIssue(ToolInput):
    result_id: str = Field(min_length=1, max_length=200)


class ReadRule(ToolInput):
    rule_id: str = Field(pattern=r"^LX0609-\d{2}-\d{2}-\d{2}$")


class QueryStatistics(ToolInput):
    rule_id: str | None = Field(default=None, pattern=r"^LX0609-\d{2}-\d{2}-\d{2}$")
    result_status: str | None = Field(default=None, pattern=r"^(non_compliant|data_gap|compliant|not_applicable|not_executed|uncertain)$")
    page: int = Field(default=1, ge=1, le=100)


TOOL_DEFINITIONS = {
    "read_saved_results": (ReadResults, "读取当前病例的正式保存结果，不执行新质控。管理者须使用统计返回的 record_reference 下钻。"),
    "read_saved_issue": (ReadIssue, "按稳定 result_id 读取同一任务的具体问题、正式建议和已保存病历证据。"),
    "read_rule": (ReadRule, "读取权威规则目录中的当前启用状态和院内实施口径；不是规范原文。"),
    "query_statistics": (QueryStatistics, "按会话确定的科室、病例范围和质控完成时间读取既有统计与病例下钻；不改统计口径。"),
}


def tool_specs() -> list[dict]:
    return [{"name": name, "description": description, "parameters": model.model_json_schema()}
            for name, (model, description) in TOOL_DEFINITIONS.items()]


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
        return binding["identity"]

    async def saved_results(self, metadata: dict, user: dict, record_reference: str | None) -> dict:
        identity = self.identity(metadata, record_reference)
        visit = quote(identity["visit_id"], safe="")
        payload = await self.read_api(f"/api/v1/qc/sichuan/workspace/records/{visit}/latest-result", {
            "institute_id": identity["institute_id"], "patient_id": identity["patient_id"],
        })
        if payload.get("state") != "ready":
            return {"state": payload.get("state"), "reason_code": payload.get("reason_code"), "references": []}
        references = []
        for item in payload.get("items", []):
            rule_id = item.get("rule_id") or item.get("rule_code")
            result_id = f"result:{payload['job_id']}:{payload['record_ref']}:{rule_id}"
            self.store.bind(metadata["session_id"], user, result_id, {
                "kind": "saved_result", "identity": identity, "job_id": payload["job_id"],
                "record_ref": payload["record_ref"], "rule_id": rule_id,
            })
            references.append(self.issue_reference(result_id, item, payload))
        return {
            "state": "ready", "job_id": payload["job_id"], "rule_set_version": payload.get("rule_set_version"),
            "is_complete": payload.get("is_complete"), "missing_rule_ids": payload.get("missing_rule_ids", []),
            "result_time": payload.get("completed_at"),
            "result_time_note": "正式接口未提供保存时间" if not payload.get("completed_at") else "",
            "references": references,
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
        payload = await self.read_api(f"/api/v1/qc/sichuan/workspace/records/{quote(identity['visit_id'], safe='')}/latest-result", {
            "institute_id": identity["institute_id"], "patient_id": identity["patient_id"],
        })
        if payload.get("job_id") != binding["job_id"] or payload.get("record_ref") != binding["record_ref"]:
            raise HTTPException(409, "结果版本已变化，请重新查看问题；本次未把旧问题替换为新判定")
        item = next((row for row in payload.get("items", []) if (row.get("rule_id") or row.get("rule_code")) == binding["rule_id"]), None)
        if item is None:
            raise HTTPException(404, "当前保存结果中未找到这条问题")
        reference = self.issue_reference(result_id, item, payload)
        evidence = item.get("evidence") or item.get("customer_evidence") or []
        reference["text"] = "\n\n".join(filter(None, [
            reference.get("conclusion"), reference.get("suggestion"),
            *[f"{row.get('source_type', '')} · {row.get('source_ref', '')} · {row.get('record_time', '')} · {row.get('field_path', '')}\n{row.get('evidence_excerpt', '未提供原文摘录')}" for row in evidence if isinstance(row, dict)],
        ]))
        return {"references": [reference], "evidence": evidence, "evidence_scope": "执行时保存的证据摘录；不是重新读取的完整文书", "reason_code": item.get("reason_code")}

    async def execute(self, name: str, arguments: dict, metadata: dict, user: dict) -> dict:
        if name not in TOOL_DEFINITIONS:
            raise HTTPException(404, "工具未提供")
        model, _ = TOOL_DEFINITIONS[name]
        params = model.model_validate(arguments)
        if name == "read_saved_results":
            return await self.saved_results(metadata, user, params.record_reference)
        if name == "read_saved_issue":
            return await self.issue(metadata, params.result_id)
        if name == "read_rule":
            from app.services.luxian_0609_rule_master import load_luxian_0609_rule_master
            from dataclasses import asdict
            rule = next((row for row in load_luxian_0609_rule_master() if row.rule_id == params.rule_id), None)
            if rule is None:
                raise HTTPException(404, "规则目录未找到该规则")
            reference_id = f"rule:{rule.rule_id}"
            self.store.bind(metadata["session_id"], user, reference_id, {"kind": "rule", "rule_id": rule.rule_id})
            return {"rule": asdict(rule), "scope_note": "当前系统目录注册状态与实施口径；active_criteria/pending_criteria 是发布范围字段，空数组不表示医学判据缺失。历史执行版本及规范原文需另行核对", "references": [{"id": reference_id, "kind": "rule", "title": rule.title, "rule_id": rule.rule_id, "text": f"目录注册状态：{rule.implementation_status}\n发布阶段：{rule.phase_status}\n实施口径：{rule.policy_summary}\n{rule.definition_note}", "locator": "当前规则目录；不是历史执行版本或规范原文"}]}
        context = metadata["context"]
        if context["view"] != "manager":
            raise HTTPException(422, "请在管理工作台限定范围后问数")
        filters = {key: context[key] for key in ("department", "care_phase", "completed_from", "completed_to") if key in context}
        filters.setdefault("care_phase", "discharged")
        filters.update(params.model_dump(exclude_none=True))
        payload = await self.read_api("/api/v1/workstation/qc-result-analysis/luxian-0609", filters)
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
        return {"statistics": payload, "filters": filters, "metric_owner": "LX0609 正式结果分析接口", "references": references}
