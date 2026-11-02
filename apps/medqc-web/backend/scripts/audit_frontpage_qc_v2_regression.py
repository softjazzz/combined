"""首页质控 V2 只读回归：对库中全部正式首页执行规则，输出按规则聚合的结论分布。

- 只读：连接设置 default_transaction_read_only=on，不写任何表
- 不调用模型
- 输出只含聚合计数与分数分布，不含病历原文、患者标识

用法（在 apps/medqc-web/backend 下）：
    DATABASE_URL=... python scripts/audit_frontpage_qc_v2_regression.py [--real-institute 泸县人民医院] [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.services.frontpage_qc_v2 import (  # noqa: E402
    RULES,
    RULESET_VERSION,
    FrontpageRef,
    build_frontpage_doc,
    evaluate_frontpage,
    load_frontpage_raw,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--schema", default="cdm", help="CDM 所在 schema，单 schema 库传空串")
    parser.add_argument("--real-institute", default="", help="按机构号区分真实同步数据与测试数据")
    parser.add_argument("--json", default="", help="把聚合结果另存为 JSON")
    args = parser.parse_args()

    url = os.environ.get("DATABASE_URL", "")
    if not url:
        print("缺少 DATABASE_URL", file=sys.stderr)
        return 2
    connect_args = {"options": "-cdefault_transaction_read_only=on"} if url.startswith("postgresql") else {}
    engine = create_engine(url, connect_args=connect_args)
    schema = args.schema or None
    table = f'"{schema}"."mr"' if schema else '"mr"'

    groups = ("real", "other") if args.real_institute else ("all",)
    verdicts = {g: defaultdict(Counter) for g in groups}
    scores = {g: [] for g in groups}
    grades = {g: Counter() for g in groups}
    durations = []
    started = time.time()
    with sessionmaker(bind=engine)() as session:
        refs = [
            FrontpageRef(*row)
            for row in session.execute(text(f"SELECT institute_id, patient_id, visit_id FROM {table} ORDER BY 1, 2, 3"))
        ]
        for ref in refs:
            t0 = time.perf_counter()
            raw = load_frontpage_raw(session, ref, schema=schema)
            if raw is None:
                continue
            outcome = evaluate_frontpage(build_frontpage_doc(raw))
            durations.append(time.perf_counter() - t0)
            group = groups[0] if not args.real_institute else ("real" if ref.institute_id == args.real_institute else "other")
            scores[group].append(outcome.score)
            grades[group][outcome.grade] += 1
            for rule_id, verdict in outcome.rule_verdicts.items():
                verdicts[group][rule_id][verdict] += 1

    durations.sort()
    summary = {
        "ruleset_version": RULESET_VERSION,
        "records": len(durations),
        "total_seconds": round(time.time() - started, 2),
        "p95_ms": round(durations[int(len(durations) * 0.95)] * 1000, 2) if durations else None,
        "groups": {},
    }
    for group in groups:
        values = scores[group]
        summary["groups"][group] = {
            "records": len(values),
            "avg_score": round(sum(values) / len(values), 2) if values else None,
            "min_score": min(values) if values else None,
            "grades": dict(grades[group]),
            "rules": {
                rule.rule_id: dict(verdicts[group][rule.rule_id])
                for rule in RULES
                if rule.enabled and verdicts[group].get(rule.rule_id)
            },
        }

    print(f"规则集 {RULESET_VERSION}：{summary['records']} 份首页，耗时 {summary['total_seconds']} 秒，单份 P95 {summary['p95_ms']} ms")
    names = {rule.rule_id: (rule.name, rule.severity.value) for rule in RULES}
    for group, data in summary["groups"].items():
        print(f"\n[{group}] {data['records']} 份，平均 {data['avg_score']} 分，最低 {data['min_score']} 分，等级 {data['grades']}")
        print("规则 | 严重程度 | 不合规 | 资料不足 | 不适用 | 合规 | 名称")
        for rule_id, counts in data["rules"].items():
            name, severity = names[rule_id]
            print(
                f"{rule_id} | {severity} | {counts.get('fail', 0)} | {counts.get('data_gap', 0)} | "
                f"{counts.get('not_applicable', 0)} | {counts.get('pass', 0)} | {name}"
            )
    if args.json:
        Path(args.json).write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
