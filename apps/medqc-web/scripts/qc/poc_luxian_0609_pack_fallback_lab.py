from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Sequence


ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.custom_qc_workspace_service import CustomQCWorkspaceService  # noqa: E402
from app.services.effect_priority_qc import BATCH_OUTPUT_MODE_MINIMAL, QUALITY_PROFILE_THROUGHPUT  # noqa: E402
from app.services.medical_records.detail_service import get_documents  # noqa: E402
from app.services.programmatic_rule_executor import ProgrammaticRuleExecutor  # noqa: E402
from app.services.qc_rule_orchestrator import resolve_rule_execution_meta  # noqa: E402
from app.services.qc_rule_sets import get_sichuan_rule_set  # noqa: E402
from app.services.sichuan_qc_service import SichuanQCService  # noqa: E402


DEFAULT_VISIT_ID = "2313364"
DEFAULT_RULE_SET_KEY = "luxian_0609_qc_v1"
DEFAULT_STRATEGIES = (
    "baseline_current",
    "partial_accept",
    "homogeneous_small_pack",
    "network_retry_first",
)
CUSTOMER_RULE_CATALOG_PATH = ROOT / "backend" / "app" / "data" / "luxian_0609_rules_v1.json"


def _now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _rule_id(rule: dict[str, Any]) -> str:
    return _safe_text(rule.get("rule_id") or rule.get("rule_code") or rule.get("id")).upper()


def _to_int(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def _to_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except Exception:
        return 0.0


def _slug(value: str) -> str:
    normalized = re.sub(r"[^0-9A-Za-z_\-]+", "-", value.strip())
    return normalized.strip("-") or "generic"


def _chunks(items: Sequence[dict[str, Any]], size: int) -> Iterable[list[dict[str, Any]]]:
    chunk_size = max(1, int(size or 1))
    for start in range(0, len(items), chunk_size):
        yield list(items[start : start + chunk_size])


def _normalize_strategy_list(value: str) -> list[str]:
    if not value:
        return list(DEFAULT_STRATEGIES)
    raw = [item.strip() for item in value.split(",")]
    selected = [item for item in raw if item]
    invalid = sorted(set(selected) - set(DEFAULT_STRATEGIES))
    if invalid:
        raise ValueError(f"未知策略: {', '.join(invalid)}")
    return selected or list(DEFAULT_STRATEGIES)


def _load_customer_point_count() -> int:
    if not CUSTOMER_RULE_CATALOG_PATH.exists():
        return 0
    data = json.loads(CUSTOMER_RULE_CATALOG_PATH.read_text(encoding="utf-8"))
    return len(data) if isinstance(data, list) else 0


def _compact_counter(counter: Counter[str], limit: int = 10) -> list[dict[str, Any]]:
    return [{"key": key, "count": count} for key, count in counter.most_common(limit)]


@dataclass
class LabConfig:
    visit_id: str
    rule_set_key: str
    strategies: list[str]
    output_dir: Path
    pack_size: int
    small_pack_size: int
    network_retry: int
    low_confidence_threshold: float
    dry_run: bool
    max_rules: int


class Luxian0609PackFallbackLab:
    def __init__(self, config: LabConfig) -> None:
        self.config = config
        self.workspace = CustomQCWorkspaceService()
        self.qc_service = SichuanQCService()
        self.program_executor = ProgrammaticRuleExecutor()
        self._pack_counter = 0

    def load_record(self) -> dict[str, Any]:
        records = self.workspace.collect_records(
            scope="all",
            department=None,
            doctor=None,
            date_field="discharge",
            start_date=None,
            end_date=None,
            keyword=None,
            record_ids=[self.config.visit_id],
        )
        hydrated = self.workspace.hydrate_records_with_medical_text(records)
        if not hydrated:
            raise RuntimeError(f"未找到病历或病历正文为空: visit_id={self.config.visit_id}")

        record = dict(hydrated[0])
        medical_text = _safe_text(record.get("medical_text") or record.get("content"))
        if not medical_text:
            concat_bundle = get_documents(self.config.visit_id, mode="concat")
            medical_text = _safe_text((concat_bundle or {}).get("text"))
            record["document_count"] = _to_int((concat_bundle or {}).get("document_count"))
            record["medical_text_source"] = "documents_concat"
        else:
            record["medical_text_source"] = "frontpage_record_content"
        if not medical_text:
            raise RuntimeError(f"病历正文为空: visit_id={self.config.visit_id}")
        record["medical_text"] = medical_text
        record["content"] = medical_text
        # 旁路 POC 评估的是全病历 pack/fallback 可靠性，不绑定单一文书类型；
        # 留空可避免 ApplicabilityChecker 把“全病历”误判为不适用文书。
        record["document_type"] = ""
        record.setdefault("record_id", self.config.visit_id)
        record.setdefault("visit_id", self.config.visit_id)
        return record

    def load_rules(self) -> tuple[list[dict[str, Any]], list[str]]:
        rule_set = get_sichuan_rule_set(self.config.rule_set_key)
        if rule_set is None:
            raise RuntimeError(f"未找到规则集: {self.config.rule_set_key}")

        missing_rule_ids: list[str] = []
        rules: list[dict[str, Any]] = []
        for rule_id in rule_set.rule_ids:
            rule = self.qc_service.get_rule_by_id(rule_id)
            if not rule:
                missing_rule_ids.append(str(rule_id))
                continue
            rules.append(dict(rule))

        if self.config.max_rules > 0:
            rules = rules[: self.config.max_rules]
        return rules, missing_rule_ids

    def split_executor_types(self, rules: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
        program_rules: list[dict[str, Any]] = []
        llm_rules: list[dict[str, Any]] = []
        program_fallback_rule_ids: list[str] = []
        for rule in rules:
            meta = resolve_rule_execution_meta(rule)
            if meta.executor_type == "program" and self.program_executor.can_execute(rule):
                program_rules.append(rule)
                continue
            if meta.executor_type == "program":
                program_fallback_rule_ids.append(_rule_id(rule))
            llm_rules.append(rule)
        return program_rules, llm_rules, program_fallback_rule_ids

    def bucket_key(self, rule: dict[str, Any], *, strategy: str) -> str:
        meta = resolve_rule_execution_meta(rule)
        if strategy == "homogeneous_small_pack":
            return f"{meta.execution_domain}::{meta.doc_scope}::{meta.rule_family}"
        return f"{meta.execution_domain}::{meta.doc_scope}"

    def build_packs(self, rules: list[dict[str, Any]], *, strategy: str) -> list[tuple[str, list[dict[str, Any]]]]:
        buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for rule in rules:
            buckets[self.bucket_key(rule, strategy=strategy)].append(rule)

        pack_size = self.config.small_pack_size if strategy == "homogeneous_small_pack" else self.config.pack_size
        packs: list[tuple[str, list[dict[str, Any]]]] = []
        for bucket in sorted(buckets.keys()):
            for chunk in _chunks(buckets[bucket], pack_size):
                packs.append((bucket, chunk))
        return packs

    async def call_pack(
        self,
        *,
        strategy: str,
        bucket_key: str,
        pack_rules: list[dict[str, Any]],
        retry_count: int,
        mode: str,
    ) -> dict[str, Any]:
        self._pack_counter += 1
        pack_id = f"{strategy}-{_slug(bucket_key)}-{self._pack_counter}"
        expected_ids = [_rule_id(rule) for rule in pack_rules]

        if self.config.dry_run:
            return {
                "pack_id": pack_id,
                "strategy": strategy,
                "bucket_key": bucket_key,
                "rule_ids": expected_ids,
                "pack_size": len(pack_rules),
                "accepted_rule_ids": [],
                "parsed_rule_ids": [],
                "missing_rule_ids": [],
                "low_confidence_rule_ids": [],
                "parse_error": False,
                "provider_error": "",
                "fallback_reason": "",
                "retry_count": retry_count,
                "tokens": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "elapsed_ms": 0,
                "context_tokens_estimate": 0,
                "mode": mode,
                "skipped": True,
            }

        started = time.perf_counter()
        response: dict[str, Any] = {}
        provider_error = ""
        try:
            first_meta = resolve_rule_execution_meta(pack_rules[0]) if pack_rules else None
            options = {
                "pack_id": pack_id,
                "pack_size": len(pack_rules),
                "prompt_strategy": "batch_compact_v1",
                "quality_profile": QUALITY_PROFILE_THROUGHPUT,
                "batch_output_mode": BATCH_OUTPUT_MODE_MINIMAL,
                "low_confidence_threshold": self.config.low_confidence_threshold,
                "execution_domain": first_meta.execution_domain if first_meta else "generic",
                "doc_scope": first_meta.doc_scope if first_meta else "primary",
                "rule_family": first_meta.rule_family if first_meta else "",
                "mode": mode,
            }
            response = await self.qc_service._llm_evaluate_batch_compact(pack_rules, self._record, options)
        except Exception as exc:  # noqa: BLE001 - POC 需要完整记录 provider 异常类型和信息
            provider_error = f"{type(exc).__name__}: {exc}"

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        results = list(response.get("results") or [])
        parsed_map: dict[str, dict[str, Any]] = {}
        for item in results:
            rid = _rule_id(dict(item))
            if rid and rid in expected_ids and rid not in parsed_map:
                parsed_map[rid] = dict(item)

        missing_ids = {
            _safe_text(item).upper()
            for item in (response.get("missing_rule_ids") or [])
            if _safe_text(item)
        }
        missing_ids.update(set(expected_ids) - set(parsed_map.keys()))

        low_ids = {
            _safe_text(item).upper()
            for item in (response.get("low_confidence_rule_ids") or [])
            if _safe_text(item)
        }
        for rid, item in parsed_map.items():
            if _to_float(item.get("confidence")) and _to_float(item.get("confidence")) < self.config.low_confidence_threshold:
                low_ids.add(rid)

        parse_error = bool(response.get("parse_error") is True)
        reasons: list[str] = []
        if provider_error:
            reasons.append("provider_error")
        else:
            if parse_error:
                reasons.append("parse_error")
            if missing_ids:
                reasons.append("missing_rule_ids")
            if low_ids:
                reasons.append("low_confidence_rule_ids")

        accepted_ids = sorted(set(parsed_map.keys()) - missing_ids - low_ids)
        if provider_error or parse_error:
            accepted_ids = []

        return {
            "pack_id": pack_id,
            "strategy": strategy,
            "bucket_key": bucket_key,
            "rule_ids": expected_ids,
            "pack_size": len(pack_rules),
            "accepted_rule_ids": accepted_ids,
            "parsed_rule_ids": sorted(parsed_map.keys()),
            "missing_rule_ids": sorted(missing_ids),
            "low_confidence_rule_ids": sorted(low_ids),
            "parse_error": parse_error,
            "provider_error": provider_error,
            "fallback_reason": "+".join(reasons),
            "retry_count": retry_count,
            "tokens": _to_int(response.get("tokens_used")),
            "prompt_tokens": _to_int(response.get("prompt_tokens")),
            "completion_tokens": _to_int(response.get("completion_tokens")),
            "elapsed_ms": elapsed_ms,
            "context_tokens_estimate": _to_int(response.get("context_tokens_estimate")),
            "mode": mode,
            "skipped": False,
        }

    async def run_baseline_like_pack(
        self,
        *,
        strategy: str,
        bucket_key: str,
        pack_rules: list[dict[str, Any]],
        diagnostics: list[dict[str, Any]],
        retry_count: int = 0,
        network_retry_first: bool = False,
    ) -> None:
        diag = await self.call_pack(
            strategy=strategy,
            bucket_key=bucket_key,
            pack_rules=pack_rules,
            retry_count=retry_count,
            mode="execute",
        )
        diagnostics.append(diag)
        if diag.get("skipped") or not diag.get("fallback_reason"):
            return

        if network_retry_first and diag.get("provider_error") and retry_count < self.config.network_retry:
            await self.run_baseline_like_pack(
                strategy=strategy,
                bucket_key=bucket_key,
                pack_rules=pack_rules,
                diagnostics=diagnostics,
                retry_count=retry_count + 1,
                network_retry_first=network_retry_first,
            )
            return

        if len(pack_rules) <= 1:
            return
        mid = max(1, len(pack_rules) // 2)
        await self.run_baseline_like_pack(
            strategy=strategy,
            bucket_key=bucket_key,
            pack_rules=pack_rules[:mid],
            diagnostics=diagnostics,
            retry_count=retry_count,
            network_retry_first=network_retry_first,
        )
        await self.run_baseline_like_pack(
            strategy=strategy,
            bucket_key=bucket_key,
            pack_rules=pack_rules[mid:],
            diagnostics=diagnostics,
            retry_count=retry_count,
            network_retry_first=network_retry_first,
        )

    async def run_partial_accept_pack(
        self,
        *,
        bucket_key: str,
        pack_rules: list[dict[str, Any]],
        diagnostics: list[dict[str, Any]],
        retry_count: int = 0,
    ) -> None:
        diag = await self.call_pack(
            strategy="partial_accept",
            bucket_key=bucket_key,
            pack_rules=pack_rules,
            retry_count=retry_count,
            mode="execute",
        )
        diagnostics.append(diag)
        if diag.get("skipped") or not diag.get("fallback_reason"):
            return

        if diag.get("provider_error") or diag.get("parse_error"):
            if len(pack_rules) <= 1:
                return
            mid = max(1, len(pack_rules) // 2)
            await self.run_partial_accept_pack(bucket_key=bucket_key, pack_rules=pack_rules[:mid], diagnostics=diagnostics)
            await self.run_partial_accept_pack(bucket_key=bucket_key, pack_rules=pack_rules[mid:], diagnostics=diagnostics)
            return

        retry_ids = set(diag.get("missing_rule_ids") or []) | set(diag.get("low_confidence_rule_ids") or [])
        remaining = [rule for rule in pack_rules if _rule_id(rule) in retry_ids]
        if not remaining:
            return
        if len(remaining) == len(pack_rules):
            if len(remaining) <= 1:
                return
            mid = max(1, len(remaining) // 2)
            await self.run_partial_accept_pack(bucket_key=bucket_key, pack_rules=remaining[:mid], diagnostics=diagnostics)
            await self.run_partial_accept_pack(bucket_key=bucket_key, pack_rules=remaining[mid:], diagnostics=diagnostics)
            return
        await self.run_partial_accept_pack(
            bucket_key=bucket_key,
            pack_rules=remaining,
            diagnostics=diagnostics,
            retry_count=retry_count + 1,
        )

    async def run_strategy(self, strategy: str, llm_rules: list[dict[str, Any]]) -> dict[str, Any]:
        self._pack_counter = 0
        diagnostics: list[dict[str, Any]] = []
        packs = self.build_packs(llm_rules, strategy=strategy)
        started = time.perf_counter()

        for bucket_key, pack_rules in packs:
            if strategy == "partial_accept":
                await self.run_partial_accept_pack(bucket_key=bucket_key, pack_rules=pack_rules, diagnostics=diagnostics)
            else:
                await self.run_baseline_like_pack(
                    strategy=strategy,
                    bucket_key=bucket_key,
                    pack_rules=pack_rules,
                    diagnostics=diagnostics,
                    network_retry_first=(strategy == "network_retry_first"),
                )

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return self.build_strategy_summary(
            strategy=strategy,
            planned_packs=packs,
            diagnostics=diagnostics,
            elapsed_ms=elapsed_ms,
            llm_rule_count=len(llm_rules),
        )

    def build_strategy_summary(
        self,
        *,
        strategy: str,
        planned_packs: list[tuple[str, list[dict[str, Any]]]],
        diagnostics: list[dict[str, Any]],
        elapsed_ms: int,
        llm_rule_count: int,
    ) -> dict[str, Any]:
        rejected = [item for item in diagnostics if item.get("fallback_reason")]
        accepted_rule_ids: set[str] = set()
        for item in diagnostics:
            accepted_rule_ids.update(str(rule_id) for rule_id in item.get("accepted_rule_ids") or [])

        reason_counter: Counter[str] = Counter()
        missing_counter: Counter[str] = Counter()
        low_counter: Counter[str] = Counter()
        for item in rejected:
            for reason in str(item.get("fallback_reason") or "").split("+"):
                if reason:
                    reason_counter[reason] += 1
            missing_counter.update(item.get("missing_rule_ids") or [])
            low_counter.update(item.get("low_confidence_rule_ids") or [])

        pack_sizes = [len(pack_rules) for _, pack_rules in planned_packs]
        return {
            "strategy": strategy,
            "planned_pack_count": len(planned_packs),
            "pack_count": len(diagnostics),
            "fallback_pack_count": len(rejected),
            "fallback_rate": round(len(rejected) / len(diagnostics), 4) if diagnostics else 0.0,
            "accepted_rule_count": len(accepted_rule_ids),
            "accepted_rule_ratio": round(len(accepted_rule_ids) / max(1, llm_rule_count), 4),
            "fallback_reason_distribution": dict(reason_counter),
            "missing_rule_topn": _compact_counter(missing_counter),
            "low_confidence_rule_topn": _compact_counter(low_counter),
            "network_error_count": reason_counter.get("provider_error", 0),
            "tokens": sum(_to_int(item.get("tokens")) for item in diagnostics),
            "prompt_tokens": sum(_to_int(item.get("prompt_tokens")) for item in diagnostics),
            "completion_tokens": sum(_to_int(item.get("completion_tokens")) for item in diagnostics),
            "elapsed_ms": elapsed_ms,
            "api_elapsed_ms_sum": sum(_to_int(item.get("elapsed_ms")) for item in diagnostics),
            "average_planned_pack_size": round(sum(pack_sizes) / len(pack_sizes), 2) if pack_sizes else 0.0,
            "average_observed_pack_size": round(
                sum(_to_int(item.get("pack_size")) for item in diagnostics) / len(diagnostics),
                2,
            )
            if diagnostics
            else 0.0,
            "diagnostics": diagnostics,
        }

    def add_improvement(self, strategy_summaries: dict[str, dict[str, Any]]) -> None:
        baseline = strategy_summaries.get("baseline_current") or {}
        baseline_rate = _to_float(baseline.get("fallback_rate"))
        baseline_accepted = _to_int(baseline.get("accepted_rule_count"))
        for name, summary in strategy_summaries.items():
            current_rate = _to_float(summary.get("fallback_rate"))
            if baseline_rate > 0:
                summary["fallback_rate_improvement_vs_baseline"] = round((baseline_rate - current_rate) / baseline_rate, 4)
            else:
                summary["fallback_rate_improvement_vs_baseline"] = 0.0
            summary["accepted_rule_delta_vs_baseline"] = _to_int(summary.get("accepted_rule_count")) - baseline_accepted

    async def run(self) -> dict[str, Any]:
        self._record = self.load_record()
        rules, missing_configured_rule_ids = self.load_rules()
        program_rules, llm_rules, program_fallback_rule_ids = self.split_executor_types(rules)

        strategy_summaries: dict[str, dict[str, Any]] = {}
        for strategy in self.config.strategies:
            strategy_summaries[strategy] = await self.run_strategy(strategy, llm_rules)
        self.add_improvement(strategy_summaries)

        return {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "dry_run": self.config.dry_run,
            "visit_id": self.config.visit_id,
            "rule_set_key": self.config.rule_set_key,
            "customer_qc_point_count": _load_customer_point_count(),
            "configured_execution_rule_count": len(get_sichuan_rule_set(self.config.rule_set_key).rule_ids),  # type: ignore[union-attr]
            "loaded_execution_rule_count": len(rules),
            "missing_configured_rule_ids": missing_configured_rule_ids,
            "llm_rule_count": len(llm_rules),
            "program_rule_count": len(program_rules),
            "program_rule_ids": [_rule_id(rule) for rule in program_rules],
            "program_fallback_rule_ids": program_fallback_rule_ids,
            "record": {
                "visit_id": self._record.get("visit_id"),
                "patient_name": self._record.get("patient_name"),
                "department": self._record.get("department"),
                "scope": self._record.get("scope"),
                "medical_text_length": len(_safe_text(self._record.get("medical_text"))),
                "medical_text_source": self._record.get("medical_text_source"),
                "document_count": self._record.get("document_count"),
            },
            "config": {
                "pack_size": self.config.pack_size,
                "small_pack_size": self.config.small_pack_size,
                "network_retry": self.config.network_retry,
                "low_confidence_threshold": self.config.low_confidence_threshold,
                "max_rules": self.config.max_rules,
                "strategies": self.config.strategies,
            },
            "strategies": strategy_summaries,
        }


def render_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# 泸县0609质控集 fallback 旁路 POC 报告")
    lines.append("")
    lines.append(f"- 生成时间：{report.get('generated_at')}")
    lines.append(f"- dry-run：{'是' if report.get('dry_run') else '否'}")
    lines.append(f"- 病历：`{report.get('visit_id')}`")
    lines.append(f"- 规则集：`{report.get('rule_set_key')}`")
    lines.append(f"- 客户质控点数：{report.get('customer_qc_point_count')}")
    lines.append(f"- 底层执行规则数：{report.get('configured_execution_rule_count')}")
    lines.append(f"- LLM 规则数 / 程序规则数：{report.get('llm_rule_count')} / {report.get('program_rule_count')}")
    lines.append("")
    lines.append("## 策略对比")
    lines.append("")
    lines.append("| 策略 | pack总数 | fallback pack数 | fallback率 | 接收规则数 | token | 耗时(ms) | 较baseline改善 |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for name, summary in (report.get("strategies") or {}).items():
        lines.append(
            "| "
            f"{name} | {summary.get('pack_count')} | {summary.get('fallback_pack_count')} | "
            f"{summary.get('fallback_rate')} | {summary.get('accepted_rule_count')} | "
            f"{summary.get('tokens')} | {summary.get('elapsed_ms')} | "
            f"{summary.get('fallback_rate_improvement_vs_baseline')} |"
        )
    lines.append("")

    for name, summary in (report.get("strategies") or {}).items():
        lines.append(f"## {name}")
        lines.append("")
        lines.append(f"- 计划 pack 数：{summary.get('planned_pack_count')}")
        lines.append(f"- 实际 pack 调用数：{summary.get('pack_count')}")
        lines.append(f"- fallback pack 数：{summary.get('fallback_pack_count')}")
        lines.append(f"- fallback 原因分布：`{json.dumps(summary.get('fallback_reason_distribution') or {}, ensure_ascii=False)}`")
        lines.append(f"- 缺失规则 TopN：`{json.dumps(summary.get('missing_rule_topn') or [], ensure_ascii=False)}`")
        lines.append(f"- 低置信度规则 TopN：`{json.dumps(summary.get('low_confidence_rule_topn') or [], ensure_ascii=False)}`")
        lines.append(f"- 网络错误次数：{summary.get('network_error_count')}")
        lines.append(f"- 平均计划 pack size：{summary.get('average_planned_pack_size')}")
        lines.append("")
    lines.append("## 说明")
    lines.append("")
    lines.append("- 本报告由旁路脚本生成，不创建正式批量任务，不写正式质控结果表。")
    lines.append("- `partial_accept` 的接收规则数用于观察“合法结果先接收，只重试失败规则”的潜在收益。")
    lines.append("- 若 `provider_error` 占比高，应优先做同包网络重试，而不是把问题归因于规则组合。")
    return "\n".join(lines) + "\n"


def write_report(report: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = _now_stamp()
    json_path = output_dir / f"luxian_0609_pack_fallback_poc_{stamp}.json"
    md_path = output_dir / f"泸县0609质控集-fallback旁路POC报告-{stamp}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, md_path


def parse_args() -> LabConfig:
    parser = argparse.ArgumentParser(description="泸县0609质控集 pack/fallback 旁路 POC")
    parser.add_argument("--visit-id", default=DEFAULT_VISIT_ID)
    parser.add_argument("--rule-set-key", default=DEFAULT_RULE_SET_KEY)
    parser.add_argument("--strategies", default=",".join(DEFAULT_STRATEGIES))
    parser.add_argument("--output-dir", default=str(ROOT / ".runtime-logs" / "qc-test"))
    parser.add_argument("--pack-size", type=int, default=8)
    parser.add_argument("--small-pack-size", type=int, default=3)
    parser.add_argument("--network-retry", type=int, default=1)
    parser.add_argument("--low-confidence-threshold", type=float, default=0.45)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-rules", type=int, default=0, help="调试用；0 表示不限制规则数")
    args = parser.parse_args()
    return LabConfig(
        visit_id=str(args.visit_id),
        rule_set_key=str(args.rule_set_key),
        strategies=_normalize_strategy_list(str(args.strategies)),
        output_dir=Path(args.output_dir),
        pack_size=max(1, int(args.pack_size)),
        small_pack_size=max(1, int(args.small_pack_size)),
        network_retry=max(0, int(args.network_retry)),
        low_confidence_threshold=float(args.low_confidence_threshold),
        dry_run=bool(args.dry_run),
        max_rules=max(0, int(args.max_rules)),
    )


async def main_async() -> int:
    config = parse_args()
    lab = Luxian0609PackFallbackLab(config)
    report = await lab.run()
    json_path, md_path = write_report(report, config.output_dir)
    print(f"POC JSON: {json_path}")
    print(f"POC Markdown: {md_path}")
    for strategy, summary in (report.get("strategies") or {}).items():
        print(
            f"{strategy}: packs={summary.get('pack_count')} "
            f"fallback={summary.get('fallback_pack_count')} "
            f"rate={summary.get('fallback_rate')} "
            f"accepted={summary.get('accepted_rule_count')} "
            f"tokens={summary.get('tokens')}"
        )
    return 0


def main() -> int:
    return asyncio.run(main_async())


if __name__ == "__main__":
    raise SystemExit(main())
