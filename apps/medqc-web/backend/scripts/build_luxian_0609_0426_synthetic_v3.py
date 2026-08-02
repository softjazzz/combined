from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import sys
from collections import Counter, defaultdict
from dataclasses import replace
from pathlib import Path
from types import ModuleType
from typing import Any, Iterable, Sequence


ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.luxian_0609_rule_master import (  # noqa: E402
    Luxian0609RuleMasterEntry,
    load_luxian_0609_rule_master,
)


SOURCE_POOL_NAME = "0426"
TARGET_POOL_ID = "luxian-0609-0426-syn-v3"
TARGET_POOL_NAME = "泸县0609真实结构合成验证集 v3（38）"
TARGET_SOURCE_FILE = "derived://0426/luxian_0609_0426_synthetic_v3"
TARGET_SOURCE_SHEET = "0426-derived-v3"
TARGET_INSTITUTE_ID = "LX0609_0426_SYN_V3"
TARGET_VISIT_PREFIX = "LX0609_0426_SYN_V3_"
TARGET_MR_PREFIX = "LX0609V3-"
TARGET_ITEM_PREFIX = "lx0609-v3"
BUNDLE_POLICY_VERSION = "luxian_0609_0426_syn_v3"
DEFAULT_OUTPUT_DIR = ROOT / "tmp-lx0609-0426-synthetic-v3"


FAMILY_RULE_NUMBERS: dict[str, tuple[int, ...]] = {
    "时限": (1, 2, 4, 5, 6),
    "查房/病重病危": (7, 8, 9, 16, 17, 18),
    "检查检验": (10, 11, 12, 14, 15, 52, 53),
    "会诊": (20, 21, 22, 23, 69),
    "手术麻醉": (3, 24, 25, *range(28, 41), 64, 65, 66, 75),
    "输血": (*range(41, 50), 70),
    "肿瘤病理/化疗": (13, 19, 26, 27),
    "出院死亡": (50, 51, 60, 61, 62, 63, 67, 68),
    "抗菌药物/医嘱": (*range(54, 60),),
    "交接转科": (71, 72, 73, 74),
}

FAMILY_QUOTAS: dict[str, int] = {
    "时限": 4,
    "查房/病重病危": 4,
    "检查检验": 4,
    "会诊": 4,
    "手术麻醉": 6,
    "输血": 5,
    "肿瘤病理/化疗": 3,
    "出院死亡": 3,
    "抗菌药物/医嘱": 2,
    "交接转科": 3,
}

FAMILY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "时限": ("入院记录", "首次病程", "48小时", "24小时", "8小时", "时限", "超时"),
    "查房/病重病危": ("查房", "病重", "病危", "病程记录", "复制", "重复"),
    "检查检验": ("CT", "MRI", "检查", "检验", "培养", "阳性", "报告", "危急值", "PL", "PH"),
    "会诊": ("会诊", "会诊申请", "会诊记录", "会诊意见"),
    "手术麻醉": ("手术", "麻醉", "术前", "术后", "安全核查", "知情同意"),
    "输血": ("输血", "红细胞", "血浆", "配血", "输血同意", "血型"),
    "肿瘤病理/化疗": ("肿瘤", "病理", "化疗", "癌", "恶性", "取材"),
    "出院死亡": ("出院", "死亡", "死亡讨论", "带药", "出院诊断"),
    "抗菌药物/医嘱": ("抗菌", "抗生素", "美罗培南", "亚胺培南", "万古霉素", "医嘱"),
    "交接转科": ("交班", "接班", "交接班", "转科", "转入", "转出", "补充诊断"),
}

FAMILY_KEYWORD_ORDER = (
    "输血",
    "肿瘤病理/化疗",
    "手术麻醉",
    "会诊",
    "出院死亡",
    "交接转科",
    "抗菌药物/医嘱",
    "查房/病重病危",
    "检查检验",
    "时限",
)


def _load_v2_module() -> ModuleType:
    path = Path(__file__).with_name("build_luxian_0609_0426_synthetic_v2.py")
    module_name = "build_luxian_0609_0426_synthetic_v2_for_v3"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载 LX0609 0426 v2 兼容构建器")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


V2 = _load_v2_module()


def build_master_family_rule_ids(
    entries: Sequence[Luxian0609RuleMasterEntry] | None = None,
    *,
    statuses: Iterable[str] | None = None,
) -> dict[str, list[str]]:
    master = tuple(entries or load_luxian_0609_rule_master())
    entries_by_id = {entry.rule_id: entry for entry in master}
    all_family_ids = tuple(
        f"LX0609-{number:03d}"
        for numbers in FAMILY_RULE_NUMBERS.values()
        for number in numbers
    )
    if len(all_family_ids) != len(set(all_family_ids)):
        raise ValueError("LX0609 v3 validation families contain duplicate rules")
    if set(all_family_ids) != set(entries_by_id):
        raise ValueError("LX0609 v3 validation families drifted from the 75-rule master")

    wanted_statuses = set(statuses or ())
    return {
        family: [
            rule_id
            for number in numbers
            if (
                (rule_id := f"LX0609-{number:03d}")
                and (not wanted_statuses or entries_by_id[rule_id].implementation_status in wanted_statuses)
            )
        ]
        for family, numbers in FAMILY_RULE_NUMBERS.items()
    }


def _configure_v2_compatibility() -> None:
    V2.TARGET_POOL_ID = TARGET_POOL_ID
    V2.TARGET_POOL_NAME = TARGET_POOL_NAME
    V2.TARGET_SOURCE_FILE = TARGET_SOURCE_FILE
    V2.TARGET_SOURCE_SHEET = TARGET_SOURCE_SHEET
    V2.TARGET_INSTITUTE_ID = TARGET_INSTITUTE_ID
    V2.TARGET_VISIT_PREFIX = TARGET_VISIT_PREFIX
    V2.TARGET_MR_PREFIX = TARGET_MR_PREFIX
    V2.TARGET_ITEM_PREFIX = TARGET_ITEM_PREFIX
    V2.BUNDLE_POLICY_VERSION = BUNDLE_POLICY_VERSION
    V2.FAMILY_QUOTAS = dict(FAMILY_QUOTAS)
    V2.FAMILY_RULE_IDS = build_master_family_rule_ids(statuses={"active"})
    V2.FAMILY_KEYWORDS = dict(FAMILY_KEYWORDS)
    V2.FAMILY_KEYWORD_ORDER = FAMILY_KEYWORD_ORDER


def _assign_full_active_family_scope(cases: Sequence[Any]) -> list[Any]:
    active_rules = build_master_family_rule_ids(statuses={"active"})
    return [
        replace(case, selected_rule_ids=list(active_rules[case.family]))
        for case in cases
    ]


def build_coverage_ledger(
    cases: Sequence[Any],
    entries: Sequence[Luxian0609RuleMasterEntry] | None = None,
) -> list[dict[str, Any]]:
    master = tuple(entries or load_luxian_0609_rule_master())
    family_by_rule_id = {
        rule_id: family
        for family, rule_ids in build_master_family_rule_ids(master).items()
        for rule_id in rule_ids
    }
    cases_by_family: dict[str, list[Any]] = defaultdict(list)
    for case in cases:
        cases_by_family[case.family].append(case)

    ledger: list[dict[str, Any]] = []
    for entry in master:
        family = family_by_rule_id[entry.rule_id]
        family_cases = cases_by_family.get(family, [])
        assigned_cases = [
            case
            for case in family_cases
            if entry.rule_id in set(case.selected_rule_ids)
        ]
        if entry.implementation_status == "active":
            coverage_status = "assigned_pending_golden_review" if assigned_cases else "coverage_gap"
            candidate_cases = assigned_cases
            required_variants = ["compliant", "non_compliant"]
        elif entry.implementation_status == "contract_ready":
            coverage_status = (
                "candidate_family_available_executor_inactive"
                if family_cases
                else "candidate_family_gap_executor_inactive"
            )
            candidate_cases = family_cases
            required_variants = ["compliant", "non_compliant"]
        else:
            coverage_status = "blocked_definition"
            candidate_cases = []
            required_variants = []
        ledger.append(
            {
                "rule_id": entry.rule_id,
                "source_document": entry.source_document,
                "qc_point": entry.qc_point,
                "implementation_status": entry.implementation_status,
                "validation_family": family,
                "coverage_status": coverage_status,
                "required_variants": required_variants,
                "candidate_visit_ids": [case.target_visit_id for case in candidate_cases],
                "definition_note": entry.definition_note,
            }
        )
    return ledger


def _write_coverage_csv(path: Path, ledger: Sequence[dict[str, Any]]) -> None:
    fields = (
        "rule_id",
        "source_document",
        "qc_point",
        "implementation_status",
        "validation_family",
        "coverage_status",
        "required_variants",
        "candidate_visit_ids",
        "definition_note",
    )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in ledger:
            writer.writerow(
                {
                    **row,
                    "required_variants": "、".join(row["required_variants"]),
                    "candidate_visit_ids": "、".join(row["candidate_visit_ids"]),
                }
            )


def _render_report(
    *,
    source_pool: dict[str, Any],
    cases: Sequence[Any],
    selection_summary: dict[str, Any],
    clone_audit: dict[str, Any],
    forbidden_hits: dict[str, int],
    ledger: Sequence[dict[str, Any]],
    write_summary: dict[str, Any] | None,
) -> str:
    coverage_counts = Counter(row["coverage_status"] for row in ledger)
    implementation_counts = Counter(row["implementation_status"] for row in ledger)
    lines = [
        "# LX0609 0426 派生合成验证集 v3 构建报告",
        "",
        f"- 目标标识：`{TARGET_POOL_ID}` / {TARGET_POOL_NAME}",
        f"- 源样本池：`{source_pool.get('id')}` / {source_pool.get('name')}",
        f"- 候选病历：{len(cases)} 份",
        f"- 写库状态：{'已写入' if write_summary else 'dry-run，未写数据库'}",
        "- 黄金答案：全部待人工复核，不声明准确率",
        "",
        "## 唯一规则总表口径",
        "",
        f"- 总规则：{len(ledger)}",
        f"- 当前启用：{implementation_counts['active']}",
        f"- 合同就绪、执行器未启用：{implementation_counts['contract_ready']}",
        f"- 待定义：{implementation_counts['pending_definition']}",
        f"- 已分配候选、待黄金复核：{coverage_counts['assigned_pending_golden_review']}",
        f"- 当前启用规则覆盖缺口：{coverage_counts['coverage_gap']}",
        "",
        "## 分层抽样",
        "",
        "| 规则族 | 配额 | 已选 |",
        "|---|---:|---:|",
    ]
    selected_counts = Counter(case.family for case in cases)
    for family, quota in FAMILY_QUOTAS.items():
        lines.append(f"| {family} | {quota} | {selected_counts[family]} |")
    lines.extend(
        [
            "",
            "## 数据质量边界",
            "",
            f"- 禁止词命中：`{json.dumps(forbidden_hits, ensure_ascii=False)}`",
            f"- 空壳核心文书过滤：{len(clone_audit.get('skipped_shell_documents') or [])} 条",
            f"- 派生证据补全：{len(clone_audit.get('supplemental_evidence_rows') or [])} 条",
            f"- 来源配额缺口：`{json.dumps(selection_summary.get('source_gaps') or {}, ensure_ascii=False)}`",
            "",
            "## 使用限制",
            "",
            "- `assigned_pending_golden_review` 只表示已分配真实结构候选，不表示规则已通过验证。",
            "- `contract_ready` 规则不得加入当前执行请求，直到执行器接入并完成回归。",
            "- `pending_definition` 规则不生成占位结果，也不计入完成率。",
            "- 未使用 `--write-db` 时仅生成审计产物；确认后可显式写入本机验证库。",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the master-driven LX0609 0426 synthetic validation set v3 (dry-run only)."
    )
    parser.add_argument("--source-pool", default=SOURCE_POOL_NAME)
    parser.add_argument("--target-size", type=int, default=sum(FAMILY_QUOTAS.values()))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--write-db", action="store_true", help="Write audited v3 rows and sample pool items to local DB.")
    parser.add_argument("--replace-items", action="store_true", help="Replace existing v3 rows and sample pool items.")
    args = parser.parse_args(argv)
    if args.target_size < sum(FAMILY_QUOTAS.values()):
        raise ValueError(f"v3 target-size must be at least {sum(FAMILY_QUOTAS.values())}")

    _configure_v2_compatibility()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    source_pool, source_items = V2.load_source_pool_items(args.source_pool)
    raw_cases, selection_summary = V2.build_selection(
        source_pool=source_pool,
        source_items=source_items,
        target_size=args.target_size,
    )
    cases = _assign_full_active_family_scope(raw_cases)
    rows_by_table, clone_audit = V2.build_clone_rows(cases)
    forbidden_hits = V2.forbidden_token_hits(rows_by_table)
    ledger = build_coverage_ledger(cases)
    write_summary = None
    if args.write_db:
        write_summary = V2.write_pool_and_items(
            source_pool=source_pool,
            cases=cases,
            rows_by_table=rows_by_table,
            supplemental_rows=clone_audit.get("supplemental_evidence_rows") or [],
            replace_items=bool(args.replace_items),
        )

    V2.write_selection_csv(output_dir / "selection.csv", cases)
    V2.write_text_lf(
        output_dir / "deid-audit.json",
        json.dumps(
            {
                "selection_summary": selection_summary,
                "clone_audit": clone_audit,
                "forbidden_token_hits": forbidden_hits,
                "write_summary": write_summary,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
        + "\n",
    )
    V2.write_text_lf(
        output_dir / "rule-coverage-ledger.json",
        json.dumps(ledger, ensure_ascii=False, indent=2) + "\n",
    )
    _write_coverage_csv(output_dir / "rule-coverage-ledger.csv", ledger)
    V2.write_text_lf(
        output_dir / "validation-report.md",
        _render_report(
            source_pool=source_pool,
            cases=cases,
            selection_summary=selection_summary,
            clone_audit=clone_audit,
            forbidden_hits=forbidden_hits,
            ledger=ledger,
            write_summary=write_summary,
        ),
    )

    coverage_counts = Counter(row["coverage_status"] for row in ledger)
    print(f"selected={len(cases)}")
    print(f"selected_counts={dict(Counter(case.family for case in cases))}")
    print(f"master_rules={len(ledger)}")
    print(f"coverage_counts={dict(coverage_counts)}")
    print(f"forbidden_token_hits={forbidden_hits}")
    print(f"wrote={output_dir}")
    print(f"db_write={'yes' if args.write_db else 'no'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
