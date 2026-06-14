from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import openpyxl


ROOT = Path(__file__).resolve().parents[2]
EXCEL_PATH = ROOT / "docs" / "0602" / "质控点及规则.xlsx"
COVERAGE_MATRIX_PATH = ROOT / "docs" / "0602" / "客户第一批质控点-语义规则覆盖矩阵.md"
DEPENDENCY_MATRIX_PATH = ROOT / "docs" / "0602" / "泸县0609质控点-执行依赖矩阵.md"
CATALOG_PATH = ROOT / "docs" / "0602" / "luxian_0609_formal_rule_catalog.json"
CATALOG_MD_PATH = ROOT / "docs" / "0602" / "泸县0609质控点-正式上线规则清单.md"
CATALOG_CSV_PATH = ROOT / "docs" / "0602" / "luxian_0609_formal_rule_catalog.csv"

RULE_SOURCE_PATHS = (
    ROOT / "backend" / "app" / "data" / "sichuan_rules_146.json",
    ROOT / "backend" / "app" / "data" / "custom_rules_33.json",
    ROOT / "backend" / "app" / "data" / "customer_rules_luxian_v1.json",
)
PROGRAMMATIC_EXECUTOR_PATH = ROOT / "backend" / "app" / "services" / "programmatic_rule_executor.py"

REQUIRED_CATALOG_FIELDS = (
    "qc_point_id",
    "source_index",
    "source_document",
    "customer_text",
    "standardized_rule",
    "issue_title",
    "applicable_documents",
    "data_dependencies",
    "trigger_condition",
    "non_trigger_condition",
    "rule_basis",
    "evidence_fields",
    "evidence_summary_template",
    "recommendation",
    "suggestion_template",
    "risk_level",
    "executor_type",
    "implementation_status",
    "coverage_level",
    "rule_ids",
    "allowed_result_statuses",
)

ALLOWED_IMPLEMENTATION_STATUSES = {
    "formal_ready",
    "needs_cross_document",
    "needs_data_linkage",
    "needs_evidence_hardening",
    "needs_rule_implementation",
    "needs_review",
    "ready_with_data_gap",
    "blocked_by_source",
}

ALLOWED_RESULT_STATUSES = {
    "hit",
    "not_hit",
    "data_quality_gap",
    "not_applicable",
    "needs_manual_review",
}


def read_customer_points() -> list[dict[str, Any]]:
    workbook = openpyxl.load_workbook(EXCEL_PATH, data_only=True)
    sheet = workbook.active
    points: list[dict[str, Any]] = []
    for source_index, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=1):
        source_document = str(row[0] or "").strip()
        customer_text = str(row[1] or "").strip()
        if not source_document and not customer_text:
            continue
        points.append(
            {
                "source_index": source_index,
                "qc_point_id": f"LX0609-{source_index:03d}",
                "source_document": source_document,
                "customer_text": customer_text,
            }
        )
    return points


def parse_markdown_table(path: Path, expected_columns: int) -> dict[int, list[str]]:
    rows: dict[int, list[str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or not re.match(r"^\|\s*\d+", line):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < expected_columns:
            continue
        try:
            source_index = int(cells[0])
        except ValueError:
            continue
        rows[source_index] = cells
    return rows


def split_rule_ids(value: str) -> list[str]:
    ids: list[str] = []
    for part in re.split(r"\s*/\s*|[,，、]\s*", value or ""):
        normalized = part.strip()
        if not normalized or normalized in {"-", "无"}:
            continue
        ids.append(normalized)
    return ids


def collect_rule_id(item: dict[str, Any]) -> str:
    for key in ("rule_id", "ruleId", "id", "code", "rule_code"):
        value = str(item.get(key) or "").strip()
        if value:
            return value.upper()
    return ""


def load_json_rule_ids() -> dict[str, dict[str, Any]]:
    rules: dict[str, dict[str, Any]] = {}
    for path in RULE_SOURCE_PATHS:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            continue
        for item in data:
            if not isinstance(item, dict):
                continue
            rule_id = collect_rule_id(item)
            if not rule_id:
                continue
            rules[rule_id] = {**item, "_source_file": path.name, "_execution_source": "json_rule"}
    return rules


def load_programmatic_rule_ids() -> dict[str, dict[str, Any]]:
    if not PROGRAMMATIC_EXECUTOR_PATH.exists():
        return {}
    text = PROGRAMMATIC_EXECUTOR_PATH.read_text(encoding="utf-8")
    rule_ids = sorted(set(re.findall(r'"([A-Z]+-\d+)"\s*:\s*ProgrammaticRuleSpec\(', text)))
    return {
        rule_id.upper(): {
            "rule_id": rule_id.upper(),
            "_source_file": PROGRAMMATIC_EXECUTOR_PATH.name,
            "_execution_source": "programmatic_executor",
            "executor_type": "program",
        }
        for rule_id in rule_ids
    }


def load_rule_catalog() -> dict[str, dict[str, Any]]:
    rules = load_json_rule_ids()
    for rule_id, item in load_programmatic_rule_ids().items():
        rules.setdefault(rule_id, item)
    return rules


def infer_status(*, coverage_level: str, included: str, dependency_type: str, chain_status: str, gap: str) -> str:
    if "数据缺口" in chain_status or "样本池缺" in gap or "当前样本池缺" in gap:
        return "ready_with_data_gap"
    if "数据联查" in coverage_level or "跨表联查" in dependency_type or "待数据联查" in chain_status:
        return "needs_data_linkage"
    if "待补规则" in coverage_level or "待补" in chain_status:
        return "needs_rule_implementation"
    if "跨文书" in dependency_type or "同域多文书" in dependency_type:
        if coverage_level == "精确覆盖" and included == "已纳入" and gap == "无":
            return "formal_ready"
        return "needs_cross_document"
    if coverage_level == "精确覆盖" and included == "已纳入" and chain_status == "已纳入" and gap == "无":
        return "formal_ready"
    if included in {"已纳入", "近似纳入"}:
        return "needs_evidence_hardening"
    return "needs_review"


def infer_executor_type(dependency_type: str, rule_ids: list[str], rule_catalog: dict[str, dict[str, Any]]) -> str:
    if "跨表联查" in dependency_type:
        return "cross_table"
    if "跨文书" in dependency_type or "同域多文书" in dependency_type:
        return "cross_document"
    executors = {str(rule_catalog.get(rule_id, {}).get("executor_type") or "").strip() for rule_id in rule_ids}
    executors.discard("")
    if "program" in executors and len(executors) == 1:
        return "program"
    if "llm" in executors:
        return "llm"
    return "program_or_llm"


def normalize_documents(*, source_document: str, coverage_rule_ids: list[str], rule_catalog: dict[str, dict[str, Any]]) -> list[str]:
    documents: list[str] = []
    for rule_id in coverage_rule_ids:
        raw_documents = rule_catalog.get(rule_id, {}).get("applicable_documents")
        if isinstance(raw_documents, list):
            documents.extend(str(item).strip() for item in raw_documents if str(item).strip())
        elif isinstance(raw_documents, str) and raw_documents.strip():
            documents.append(raw_documents.strip())
    if not documents and source_document:
        documents.append(source_document)
    return sorted(dict.fromkeys(documents))


def build_trigger_condition(*, point_text: str, required_docs: str, required_data: str) -> str:
    scope_parts = []
    if required_docs:
        scope_parts.append(f"存在或应存在 {required_docs}")
    if required_data:
        scope_parts.append(f"需要读取 {required_data}")
    scope = "，".join(scope_parts) or "病历属于该客户质控点适用场景"
    return f"当{scope}，且出现“{point_text}”所描述的不合规情形时触发。"


def build_non_trigger_condition(*, required_docs: str, required_data: str) -> str:
    normal_parts = []
    if required_docs:
        normal_parts.append(f"{required_docs}齐全且内容符合规则口径")
    if required_data:
        normal_parts.append(f"{required_data}可取得且比对结果一致")
    normal = "；".join(normal_parts) or "文书内容符合客户质控点口径"
    return f"{normal}时不触发；缺少必要文书或结构化数据时返回 data_quality_gap，不得误判为合格或不合格。"


def build_rule_basis(*, source_document: str, point_text: str) -> str:
    return f"泸县0609客户质控点：{point_text}；适用文书：{source_document or '按规则目录定义'}；依据病历书写规范和客户专项验收口径执行。"


def build_evidence_fields(*, dependency_type: str, required_data: str) -> list[str]:
    fields = [
        "visit_id",
        "patient_name",
        "department",
        "document_type",
        "document_name",
        "document_time",
        "hit_field",
        "matched_text",
        "rule_basis",
        "evidence_summary",
        "suggestion",
        "risk_level",
    ]
    if "跨文书" in dependency_type or "同域多文书" in dependency_type:
        fields.extend(["comparison_document_type", "comparison_document_time", "comparison_summary"])
    if "跨表" in dependency_type or "检查" in required_data or "检验" in required_data or "医嘱" in required_data or "费用" in required_data:
        fields.extend(["related_order_or_report_time", "related_data_source", "data_gap_reason"])
    return sorted(dict.fromkeys(fields))


def build_catalog() -> list[dict[str, Any]]:
    points = read_customer_points()
    coverage_rows = parse_markdown_table(COVERAGE_MATRIX_PATH, 10)
    dependency_rows = parse_markdown_table(DEPENDENCY_MATRIX_PATH, 9)
    rule_catalog = load_rule_catalog()
    catalog: list[dict[str, Any]] = []

    for point in points:
        source_index = int(point["source_index"])
        coverage = coverage_rows.get(source_index, [])
        dependency = dependency_rows.get(source_index, [])
        rule_ids = split_rule_ids(coverage[3] if len(coverage) > 3 else "")
        coverage_level = coverage[6] if len(coverage) > 6 else "待复核"
        included = coverage[7] if len(coverage) > 7 else "待复核"
        judgment = coverage[8] if len(coverage) > 8 else ""
        recommendation = coverage[9] if len(coverage) > 9 else ""
        dependency_type = dependency[2] if len(dependency) > 2 else ""
        required_docs = dependency[3] if len(dependency) > 3 else ""
        required_data = dependency[4] if len(dependency) > 4 else ""
        data_status = dependency[5] if len(dependency) > 5 else ""
        chain_status = dependency[6] if len(dependency) > 6 else ""
        gap = dependency[7] if len(dependency) > 7 else ""
        suggested_version = dependency[8] if len(dependency) > 8 else ""
        implementation_status = infer_status(
            coverage_level=coverage_level,
            included=included,
            dependency_type=dependency_type,
            chain_status=chain_status,
            gap=gap,
        )
        applicable_documents = normalize_documents(
            source_document=str(point["source_document"]),
            coverage_rule_ids=rule_ids,
            rule_catalog=rule_catalog,
        )
        entry = {
            **point,
            "standardized_rule": coverage[4] if len(coverage) > 4 else point["customer_text"],
            "issue_title": f"{point['source_document']}：{point['customer_text']}",
            "recommended_rule_names": coverage[4] if len(coverage) > 4 else "",
            "rule_source": coverage[5] if len(coverage) > 5 else "",
            "coverage_level": coverage_level,
            "included_in_v1": included,
            "judgment_note": judgment,
            "recommendation": recommendation or "按客户质控点口径补齐规则证据与整改建议。",
            "dependency_type": dependency_type or "待补充",
            "applicable_documents": applicable_documents,
            "required_documents_label": required_docs,
            "data_dependencies": [item.strip() for item in re.split(r"[、,，]", required_data) if item.strip()],
            "data_status": data_status,
            "chain_status": chain_status,
            "gap": gap,
            "suggested_version": suggested_version,
            "trigger_condition": build_trigger_condition(
                point_text=point["customer_text"],
                required_docs=required_docs,
                required_data=required_data,
            ),
            "non_trigger_condition": build_non_trigger_condition(
                required_docs=required_docs,
                required_data=required_data,
            ),
            "rule_basis": build_rule_basis(source_document=str(point["source_document"]), point_text=point["customer_text"]),
            "evidence_fields": build_evidence_fields(dependency_type=dependency_type, required_data=required_data),
            "evidence_summary_template": "输出命中文书、记录时间、命中字段或片段、跨文书/跨表比较对象、判定理由；数据不足时输出缺失数据源和无法判定原因。",
            "risk_level": "P0" if source_index in {1, 2, 3, 4, 5, 6, 29, 30, 32, 33, 34, 39, 40, 41} else "普通",
            "suggestion_template": recommendation or "按客户质控点口径补齐病历记录、签名、时间或关联文书，并由质控人员复核。",
            "executor_type": infer_executor_type(dependency_type, rule_ids, rule_catalog),
            "implementation_status": implementation_status,
            "rule_ids": rule_ids,
            "missing_rule_ids": [rule_id for rule_id in rule_ids if rule_id.upper() not in rule_catalog],
            "rule_execution_sources": sorted(
                {
                    str(rule_catalog.get(rule_id.upper(), {}).get("_execution_source") or "")
                    for rule_id in rule_ids
                    if rule_id.upper() in rule_catalog
                }
            ),
            "allowed_result_statuses": ["hit", "not_hit", "data_quality_gap", "not_applicable", "needs_manual_review"],
            "golden_cases": {
                "positive": [],
                "negative": [],
                "boundary": [],
            },
            "accuracy_threshold": {
                "precision": 0.9 if source_index in {1, 2, 3, 4, 5, 6, 29, 30, 32, 33, 34, 39, 40, 41} else 0.85,
                "recall": 0.85 if source_index in {1, 2, 3, 4, 5, 6, 29, 30, 32, 33, 34, 39, 40, 41} else 0.8,
            },
        }
        catalog.append(entry)
    return catalog


def validate_catalog(catalog: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    source_indexes = [int(item.get("source_index") or 0) for item in catalog]
    duplicate_indexes = [index for index, count in Counter(source_indexes).items() if count > 1]
    if len(catalog) != 49:
        errors.append(f"规则目录应包含 49 条，当前为 {len(catalog)} 条。")
    if sorted(source_indexes) != list(range(1, 50)):
        missing = sorted(set(range(1, 50)) - set(source_indexes))
        errors.append(f"source_index 不连续或缺失，缺失: {missing}。")
    if duplicate_indexes:
        errors.append(f"source_index 重复: {duplicate_indexes}。")
    for item in catalog:
        qc_point_id = str(item.get("qc_point_id") or "")
        for field in REQUIRED_CATALOG_FIELDS:
            value = item.get(field)
            if value in (None, "", []):
                errors.append(f"{qc_point_id} 缺少必填字段 {field}。")
        missing_rule_ids = item.get("missing_rule_ids") or []
        if missing_rule_ids:
            errors.append(f"{qc_point_id} 引用了不存在的规则 ID: {', '.join(missing_rule_ids)}。")
        implementation_status = str(item.get("implementation_status") or "")
        if implementation_status not in ALLOWED_IMPLEMENTATION_STATUSES:
            errors.append(f"{qc_point_id} implementation_status 非法: {implementation_status}。")
        result_statuses = item.get("allowed_result_statuses") or []
        if not isinstance(result_statuses, list) or not result_statuses:
            errors.append(f"{qc_point_id} allowed_result_statuses 必须是非空列表。")
        else:
            illegal_statuses = [status for status in result_statuses if status not in ALLOWED_RESULT_STATUSES]
            if illegal_statuses:
                errors.append(f"{qc_point_id} allowed_result_statuses 包含非法状态: {', '.join(illegal_statuses)}。")
            for required_status in ("hit", "not_hit", "data_quality_gap"):
                if required_status not in result_statuses:
                    errors.append(f"{qc_point_id} allowed_result_statuses 缺少 {required_status}。")
        evidence_fields = item.get("evidence_fields") or []
        for evidence_field in ("visit_id", "document_type", "matched_text", "evidence_summary", "suggestion", "risk_level"):
            if evidence_field not in evidence_fields:
                errors.append(f"{qc_point_id} evidence_fields 缺少 {evidence_field}。")
        if item.get("executor_type") in {"cross_document", "cross_table"} and str(item.get("dependency_type") or "") != "单文书":
            if item.get("executor_type") == "cross_document" and "comparison_summary" not in evidence_fields:
                errors.append(f"{qc_point_id} 跨文书规则缺少 comparison_summary 证据字段。")
            if item.get("executor_type") == "cross_table" and "data_gap_reason" not in evidence_fields:
                errors.append(f"{qc_point_id} 跨表规则缺少 data_gap_reason 证据字段。")
        if item.get("implementation_status") == "formal_ready":
            if not item.get("rule_ids"):
                errors.append(f"{qc_point_id} 标记 formal_ready 但没有可执行 rule_ids。")
            if not item.get("evidence_fields"):
                errors.append(f"{qc_point_id} 标记 formal_ready 但没有 evidence_fields。")
    return errors


def write_catalog(catalog: list[dict[str, Any]]) -> None:
    CATALOG_PATH.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with CATALOG_CSV_PATH.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = [
            "qc_point_id",
            "source_index",
            "source_document",
            "customer_text",
            "issue_title",
            "standardized_rule",
            "coverage_level",
            "included_in_v1",
            "implementation_status",
            "dependency_type",
            "applicable_documents",
            "data_dependencies",
            "trigger_condition",
            "non_trigger_condition",
            "rule_basis",
            "evidence_fields",
            "evidence_summary_template",
            "suggestion_template",
            "chain_status",
            "gap",
            "rule_ids",
            "executor_type",
            "allowed_result_statuses",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in catalog:
            writer.writerow({key: "; ".join(item[key]) if isinstance(item.get(key), list) else item.get(key, "") for key in fieldnames})
    write_markdown(catalog)


def write_markdown(catalog: list[dict[str, Any]]) -> None:
    status_counts = Counter(str(item.get("implementation_status") or "") for item in catalog)
    lines = [
        "# 泸县0609质控点-正式上线规则清单",
        "",
        "生成来源：`docs/0602/质控点及规则.xlsx`、覆盖矩阵、执行依赖矩阵。",
        "",
        "## 状态汇总",
        "",
            "| 状态 | 数量 | 说明 |",
        "|---|---:|---|",
    ]
    descriptions = {
        "formal_ready": "规则口径、执行规则和证据字段基本齐全，可进入正式版候选，但仍需 golden case 评测。",
        "needs_evidence_hardening": "已有规则可执行，但证据链、阈值或客户口径还需增强。",
        "needs_cross_document": "需要构建跨文书 bundle 或多文书比对逻辑。",
        "needs_data_linkage": "需要医嘱、费用、检查、检验等结构化数据联查。",
        "needs_rule_implementation": "当前没有足够贴合的可执行规则，需要新增规则。",
        "needs_review": "需要人工复核规则口径。",
    }
    for status, count in sorted(status_counts.items()):
        lines.append(f"| `{status}` | {count} | {descriptions.get(status, '')} |")
    lines.extend(
        [
            "",
            "## 规则清单",
            "",
            "| 编号 | 质控文书 | 客户质控点 | 上线状态 | 执行类型 | 数据依赖 | 证据要求 | 建议处理 | 缺口 |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for item in catalog:
        rule_ids = ", ".join(item.get("rule_ids") or [])
        gap = str(item.get("gap") or "无").replace("|", "/")
        customer_text = str(item.get("customer_text") or "").replace("|", "/")
        data_dependencies = "、".join(item.get("data_dependencies") or [])
        evidence_fields = "、".join(item.get("evidence_fields") or [])
        suggestion = str(item.get("suggestion_template") or item.get("recommendation") or "").replace("|", "/")
        lines.append(
            "| {qc_point_id} | {source_document} | {customer_text} | `{implementation_status}` | {executor_type} | {data_dependencies} | {evidence_fields} | {suggestion} | {gap} |".format(
                qc_point_id=item.get("qc_point_id", ""),
                source_document=item.get("source_document", ""),
                customer_text=customer_text,
                implementation_status=item.get("implementation_status", ""),
                executor_type=item.get("executor_type", ""),
                data_dependencies=data_dependencies.replace("|", "/"),
                evidence_fields=evidence_fields.replace("|", "/"),
                suggestion=suggestion[:80],
                rule_ids=rule_ids,
                gap=gap,
            )
        )
    lines.extend(
        [
            "",
            "## 后续要求",
            "",
            "- `formal_ready` 只是正式版候选，必须通过 golden case 和样本池评测后才能进入正式上线规则集。",
            "- `needs_data_linkage` 规则在结构化数据不足时必须输出“数据不足无法判定”，不能误报。",
            "- 所有规则都必须补齐阳性、阴性、边界样本后再做准确性统计。",
            "",
        ]
    )
    CATALOG_MD_PATH.write_text("\n".join(lines), encoding="utf-8")


def print_summary(catalog: list[dict[str, Any]], errors: list[str]) -> None:
    print(f"catalog_count={len(catalog)}")
    for status, count in sorted(Counter(str(item.get("implementation_status") or "") for item in catalog).items()):
        print(f"status.{status}={count}")
    print(f"errors={len(errors)}")
    for error in errors[:30]:
        print(f"ERROR: {error}")
    if len(errors) > 30:
        print(f"... {len(errors) - 30} more errors")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate and validate Luxian 0609 formal QC catalog.")
    parser.add_argument("--write", action="store_true", help="write catalog json/csv/markdown")
    args = parser.parse_args()

    catalog = build_catalog()
    errors = validate_catalog(catalog)
    if args.write:
        write_catalog(catalog)
    print_summary(catalog, errors)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
