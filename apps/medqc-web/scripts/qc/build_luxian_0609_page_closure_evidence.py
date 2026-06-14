from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT / "docs" / "0602"

PAGE_PATH = ROOT / "src" / "views" / "workstation-v4" / "CustomerSampleValidationView.vue"
PAGE_TEST_PATH = ROOT / "tests" / "unit" / "views" / "workstation-v4" / "CustomerSampleValidationView.spec.ts"
SERVICE_PATH = ROOT / "src" / "services" / "manual-case-sample-service.ts"
ROUTER_PATH = ROOT / "backend" / "app" / "routers" / "qc_sample_pools.py"
BATCH_DRAWER_PATH = (
    ROOT
    / "src"
    / "views"
    / "workstation-v4"
    / "semantic-rules"
    / "components"
    / "SemanticRulesBatchResultDrawer.vue"
)

OUTPUT_JSON_PATH = DOCS_DIR / "luxian_0609_customer_sample_page_evidence.json"
OUTPUT_MD_PATH = DOCS_DIR / "泸县0609质控点-客户样本验证页面闭环证据.md"


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def has_all(text: str, needles: list[str]) -> bool:
    return all(needle in text for needle in needles)


def capability(
    *,
    key: str,
    title: str,
    status: str,
    evidence: list[str],
    missing: list[str] | None = None,
    recommendation: str,
) -> dict[str, Any]:
    return {
        "key": key,
        "title": title,
        "status": status,
        "evidence": evidence,
        "missing": missing or [],
        "recommendation": recommendation,
    }


def build_evidence() -> dict[str, Any]:
    page = read_text(PAGE_PATH)
    page_test = read_text(PAGE_TEST_PATH)
    service = read_text(SERVICE_PATH)
    router = read_text(ROUTER_PATH)
    batch_drawer = read_text(BATCH_DRAWER_PATH)

    capabilities: list[dict[str, Any]] = []

    rule_set_selection_ready = has_all(
        page,
        [
            "LUXIAN_0609_RULE_SET_KEY",
            "luxian_0609_qc_v1",
            "data-rule-set-key",
            "handleRuleSetChange",
        ],
    ) and has_all(
        page_test,
        [
            "默认选中泸县0609规则集并展示规则集摘要",
            "泸县0609质控点验证 v1",
        ],
    )
    capabilities.append(
        capability(
            key="rule_set_selection",
            title="规则集选择与摘要展示",
            status="pass" if rule_set_selection_ready else "fail",
            evidence=[
                "页面包含泸县0609规则集 key、规则集切换按钮和默认摘要展示。",
                "单测覆盖默认选中泸县0609规则集并展示闸门/评估/覆盖摘要。",
            ]
            if rule_set_selection_ready
            else [],
            missing=[] if rule_set_selection_ready else ["缺少规则集选择或摘要展示测试证据。"],
            recommendation="保持页面默认选择泸县0609规则集，并继续从后端目录动态读取闸门指标。",
        )
    )

    batch_creation_ready = has_all(
        page,
        [
            "runManualSamplePool",
            "selectedRuleSetPayloadKey",
            "handleRunPool",
            "rule_set_key",
        ],
    ) and has_all(
        page_test,
        [
            "发起验证成功后应自动打开结果抽屉并显示成功提示",
            "luxian_0609_qc_v1",
        ],
    )
    capabilities.append(
        capability(
            key="batch_job_creation",
            title="发起泸县0609批量验证任务",
            status="pass" if batch_creation_ready else "fail",
            evidence=[
                "页面按 selectedRuleSetPayloadKey 提交 rule_set_key。",
                "单测覆盖泸县0609任务创建成功、提示和结果抽屉打开。",
            ]
            if batch_creation_ready
            else [],
            missing=[] if batch_creation_ready else ["缺少发起批量验证任务的单测或 rule_set_key 透传。"],
            recommendation="下一步需要用真实后端任务补充端到端运行证据。",
        )
    )

    result_drawer_ready = has_all(
        page,
        [
            "SemanticRulesBatchResultDrawer",
            "batchResultOpen",
            "getSichuanWorkspaceBatchJob",
        ],
    ) and "点击查看结果后打开批量任务结果抽屉" in page_test
    capabilities.append(
        capability(
            key="result_drawer",
            title="批量结果抽屉入口",
            status="pass" if result_drawer_ready else "fail",
            evidence=[
                "客户样本验证页复用 SemanticRulesBatchResultDrawer 展示批量任务结果。",
                "单测覆盖点击查看结果后打开批量任务结果抽屉。",
            ]
            if result_drawer_ready
            else [],
            missing=[] if result_drawer_ready else ["缺少批量结果抽屉入口或测试证据。"],
            recommendation="需要继续补充结果抽屉内按规则、病历、科室查看的专项测试。",
        )
    )

    report_export_ready = has_all(
        page,
        [
            "exportLuxian0609EvaluationReport",
            "export-luxian-md",
            "export-luxian-csv",
            "export-luxian-json",
        ],
    ) and has_all(
        service,
        [
            "exportLuxian0609EvaluationReport",
            "/api/v1/qc/sample-pools/reports/luxian-0609",
        ],
    ) and has_all(
        router,
        [
            "download_luxian_0609_evaluation_report",
            "_LUXIAN_0609_REPORT_FILES",
        ],
    ) and "可从更多操作导出泸县0609专项评估报告" in page_test
    capabilities.append(
        capability(
            key="evaluation_report_export",
            title="泸县0609评估报告导出",
            status="pass" if report_export_ready else "fail",
            evidence=[
                "前端更多操作支持 Markdown/CSV/JSON 三种泸县0609报告导出。",
                "服务层和后端路由提供只读评估报告下载接口。",
                "单测覆盖 Markdown 报告导出成功提示。",
            ]
            if report_export_ready
            else [],
            missing=[] if report_export_ready else ["缺少报告导出入口、服务或后端路由证据。"],
            recommendation="等真实评估数据生成后，导出的报告会成为客户验收材料。",
        )
    )

    status_taxonomy_supported = has_all(
        batch_drawer,
        [
            "data_quality_gap",
            "not_applicable",
            "uncertain",
            "rejected_by_system",
        ],
    )
    capabilities.append(
        capability(
            key="status_taxonomy",
            title="结果状态区分",
            status="partial" if status_taxonomy_supported else "fail",
            evidence=[
                "共享批量结果抽屉已支持数据缺口、不适用、待复核、系统驳回等状态展示。",
            ]
            if status_taxonomy_supported
            else [],
            missing=[
                "尚未在客户样本验证页用泸县0609真实任务结果证明已命中、未命中、数据不足、规则不适用、需人工复核五类状态完整展示。",
            ],
            recommendation="补充包含五类状态的后端 fixture 或端到端任务，并在结果抽屉做断言。",
        )
    )

    evidence_supported = has_all(
        batch_drawer,
        [
            "evidence",
            "resolveDeepReviewText",
            "matched_text",
        ],
    ) or has_all(batch_drawer, ["evidence", "深度复核", "文书"])
    capabilities.append(
        capability(
            key="evidence_trace",
            title="证据链追溯",
            status="partial" if evidence_supported else "fail",
            evidence=[
                "共享批量结果抽屉包含证据字段、深度复核和文书相关展示逻辑。",
            ]
            if evidence_supported
            else [],
            missing=[
                "缺少泸县0609真实结果项到原始文书片段的端到端定位验收证据。",
            ],
            recommendation="为泸县0609结果项补充 evidence/matched_text/document_name，并增加页面测试验证证据片段可见。",
        )
    )

    grouping_supported = has_all(batch_drawer, ["ruleLevelSummary", "rule_results", "record_id", "visit_id"])
    department_grouping_supported = "department" in batch_drawer or "科室" in batch_drawer
    capabilities.append(
        capability(
            key="grouping_views",
            title="按规则、病历、科室查看",
            status="partial" if grouping_supported else "fail",
            evidence=[
                "共享批量结果抽屉已有规则级摘要与病历标识字段。",
            ]
            if grouping_supported
            else [],
            missing=[
                "尚未证明泸县0609结果可按规则、病历、科室三种视角完整查看。",
            ]
            + ([] if department_grouping_supported else ["当前静态扫描未发现明确的科室分组视角。"]),
            recommendation="补充泸县0609专项结果分组测试，必要时在抽屉中增加科室维度聚合。",
        )
    )

    record_position_ready = "点击查看病历后打开病历联审抽屉" in page_test and has_all(
        page,
        ["reviewDrawerRecord", "病历关联问题", "matched_visit_id"],
    )
    capabilities.append(
        capability(
            key="record_positioning",
            title="查看病历与原文定位入口",
            status="partial" if record_position_ready else "fail",
            evidence=[
                "客户样本验证页可打开病历联审抽屉，并展示 visit_id 等病历关联信息。",
            ]
            if record_position_ready
            else [],
            missing=[
                "尚未证明从单条质控结果可直接定位到命中文书原文片段。",
            ],
            recommendation="把批量结果中的文书定位字段与病历详情/文书定位入口打通，并增加端到端测试。",
        )
    )

    status_counts: dict[str, int] = {}
    for item in capabilities:
        status = str(item["status"])
        status_counts[status] = status_counts.get(status, 0) + 1

    blocking = [
        {
            "key": item["key"],
            "title": item["title"],
            "status": item["status"],
            "missing": item["missing"],
            "recommendation": item["recommendation"],
        }
        for item in capabilities
        if item["status"] != "pass"
    ]

    return {
        "version": "2026-06-10",
        "page": "/workstation-v4/customer-sample-validation",
        "rule_set_key": "luxian_0609_qc_v1",
        "summary": {
            "capability_count": len(capabilities),
            "status_counts": status_counts,
            "passed_capabilities": status_counts.get("pass", 0),
            "partial_capabilities": status_counts.get("partial", 0),
            "failed_capabilities": status_counts.get("fail", 0),
            "page_verified": not blocking,
            "blocking_count": len(blocking),
        },
        "capabilities": capabilities,
        "blocking": blocking,
        "inputs": {
            "page": str(PAGE_PATH),
            "page_test": str(PAGE_TEST_PATH),
            "service": str(SERVICE_PATH),
            "router": str(ROUTER_PATH),
            "batch_result_drawer": str(BATCH_DRAWER_PATH),
        },
    }


def build_markdown(evidence: dict[str, Any]) -> str:
    summary = evidence["summary"]
    lines = [
        "# 泸县0609质控点-客户样本验证页面闭环证据",
        "",
        f"- 页面：`{evidence['page']}`",
        f"- 规则集：`{evidence['rule_set_key']}`",
        f"- 结论：{'页面闭环已验证' if summary['page_verified'] else '页面闭环尚未完全验证'}",
        f"- 能力项：通过 {summary['passed_capabilities']}，部分 {summary['partial_capabilities']}，失败 {summary['failed_capabilities']}",
        "",
        "## 能力矩阵",
        "",
        "| 能力 | 状态 | 已有证据 | 缺口 | 建议 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in evidence["capabilities"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    item["title"],
                    item["status"],
                    "<br>".join(item["evidence"]) or "-",
                    "<br>".join(item["missing"]) or "-",
                    item["recommendation"],
                ]
            )
            + " |"
        )
    lines.extend(["", "## 阻塞项", ""])
    if evidence["blocking"]:
        for index, item in enumerate(evidence["blocking"], start=1):
            lines.append(f"{index}. **{item['title']}**：{'; '.join(item['missing']) or item['recommendation']}")
    else:
        lines.append("无。")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Luxian 0609 customer sample page closure evidence.")
    parser.add_argument("--write", action="store_true", help="Write JSON and Markdown evidence files.")
    args = parser.parse_args()

    evidence = build_evidence()
    if args.write:
        OUTPUT_JSON_PATH.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
        OUTPUT_MD_PATH.write_text(build_markdown(evidence), encoding="utf-8")
    print(json.dumps(evidence["summary"], ensure_ascii=False, indent=2))
    return 0 if evidence["summary"]["page_verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
