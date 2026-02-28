"""
分段质控流水线

串联 段落切割 → 规则路由 → 并发 LLM 评估 → 结果合并。
"""
import asyncio
import time
import logging
from typing import Dict, Any, List, Optional

from .document_segmenter import split_document, merge_small_sections, DocumentSection
from .rule_router import RuleRouter
from .qc_llm_client import SichuanQCLLMClient
from .qc_prompt_builder import QCPromptBuilder

logger = logging.getLogger(__name__)


class SegmentedQCPipeline:
    """
    分段质控流水线。

    相比 evaluate_document_fast（整篇病历 + 所有规则一次调用），
    本流水线先将病历切段、每段只关联相关规则，再并发调用 LLM，
    从而降低 token 消耗、提升精准度、缩短延迟。

    核心区别：本流水线直接使用 QCPromptBuilder + LLMClient，
    不通过 SichuanQCService 加载规则，因为路由器已经完成了规则分配。
    """

    # 每次 LLM 调用的最大规则数（超出自动拆批，避免注意力衰减）
    MAX_RULES_PER_BATCH = 15

    def __init__(
        self,
        llm_client: Optional[SichuanQCLLMClient] = None,
        prompt_builder: Optional[QCPromptBuilder] = None,
        router: Optional[RuleRouter] = None,
        max_concurrency: int = 5,
    ):
        self.client = llm_client or SichuanQCLLMClient()
        self.prompt_builder = prompt_builder or QCPromptBuilder(
            enable_truncate=False,  # 分段后每段已经很短，不需要截断
            max_content_length=8000,
        )
        self.router = router or RuleRouter()
        self.max_concurrency = max_concurrency

    async def evaluate(
        self,
        document_id: str,
        content: str,
        prompt_mode: str = "plan_a",
        min_section_chars: int = 100,
    ) -> Dict[str, Any]:
        """
        对完整病历执行分段质控。

        Args:
            document_id: 文档 ID
            content: 完整病历文本
            prompt_mode: 提示词模式
            min_section_chars: 短段落合并阈值

        Returns:
            质控结果字典
        """
        pipeline_start = time.time()

        # ── Step 1: 段落切割 ──
        sections = split_document(content)
        sections = merge_small_sections(sections, min_chars=min_section_chars)

        logger.info(f"[Pipeline] 切割为 {len(sections)} 个段落")

        # ── Step 2: 规则路由 + 自动分批 ──
        tasks_info: List[Dict[str, Any]] = []
        total_rules = 0

        for sec in sections:
            rules = self.router.get_rules_for_section(sec.section_type)
            if not rules:
                continue

            # 自动分批：超过 MAX_RULES_PER_BATCH 时拆成多个任务
            if len(rules) > self.MAX_RULES_PER_BATCH:
                batches = [
                    rules[i:i + self.MAX_RULES_PER_BATCH]
                    for i in range(0, len(rules), self.MAX_RULES_PER_BATCH)
                ]
                for batch_idx, batch in enumerate(batches, 1):
                    tasks_info.append({
                        'section': sec,
                        'rules': batch,
                    })
                    total_rules += len(batch)
                logger.info(
                    f"  [{sec.section_type}] {sec.title[:25]} -> "
                    f"{len(rules)} 条规则 (拆为 {len(batches)} 批)"
                )
            else:
                tasks_info.append({
                    'section': sec,
                    'rules': rules,
                })
                total_rules += len(rules)
                logger.info(
                    f"  [{sec.section_type}] {sec.title[:25]} -> {len(rules)} 条规则"
                )

        logger.info(
            f"[Pipeline] {len(tasks_info)} 个任务 (含分批), "
            f"共 {total_rules} 条规则评估"
        )


        if not tasks_info:
            return self._empty_result(document_id)

        # ── Step 2.5: 构建跨段上下文摘要 ──
        # 让每段 LLM 知道完整病历包含哪些文书，避免因上下文隔离导致误报
        overview_lines = ["【本病历文书目录】"]
        for i, sec in enumerate(sections, 1):
            ts = f" ({sec.timestamp})" if sec.timestamp else ""
            overview_lines.append(
                f"  {i}. [{sec.section_type}] {sec.title}{ts} — {sec.char_count}字"
            )
        overview_lines.append(
            "注意：你当前只看到其中一段文书的内容。"
            "如果某条规则要求的内容属于其他文书类型（如入院记录、术前小结、手术同意书等），"
            "且该文书已在上述目录中列出，请判定为'合规'并说明该内容在其他文书中。"
        )
        document_overview = "\n".join(overview_lines)
        logger.info(f"[Pipeline] 跨段上下文: {len(overview_lines)} 行")

        # ── Step 3: 并发 LLM 评估 ──
        sem = asyncio.Semaphore(self.max_concurrency)

        async def evaluate_one(task: Dict[str, Any]) -> Dict[str, Any]:
            sec: DocumentSection = task['section']
            rules: List[Dict[str, Any]] = task['rules']

            async with sem:
                # 在段落内容前注入全文书目录，避免上下文隔离误报
                enriched_content = (
                    document_overview + "\n\n"
                    "【当前评估的文书内容】\n" + sec.content
                )

                # 直接构建 prompt 并调用 LLM（不经过 SichuanQCService）
                prompt = await self.prompt_builder.build_prompt(
                    rules=rules,
                    content=enriched_content,
                    document_type=sec.section_type,
                    prompt_mode=prompt_mode,
                )

                api_start = time.time()
                llm_response = await self.client.generate(prompt)
                api_time = time.time() - api_start

                llm_output = (
                    llm_response.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                )
                token_usage = llm_response.get("usage", {}).get("total_tokens", 0)

                # 解析 JSON 结果
                evaluation_results = self._parse_llm_response(llm_output, rules)

                # 标记来源段落
                for er in evaluation_results:
                    er['source_section'] = sec.title
                    er['source_section_type'] = sec.section_type

                logger.info(
                    f"  ✅ [{sec.section_type}] {sec.title[:20]} -> "
                    f"{len(evaluation_results)} 结果, {token_usage} tokens, {api_time:.1f}s"
                )

                return {
                    'evaluation_results': evaluation_results,
                    'performance_metrics': {
                        'token_usage': token_usage,
                        'api_time': api_time,
                    },
                }

        chunk_results = await asyncio.gather(
            *[evaluate_one(t) for t in tasks_info]
        )

        # ── Step 4: 合并结果 ──
        return self._merge_results(
            document_id=document_id,
            chunk_results=chunk_results,
            sections=sections,
            total_rules=total_rules,
            elapsed=time.time() - pipeline_start,
        )

    def _parse_llm_response(
        self, llm_output: str, rules: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """解析 LLM 的 JSON 输出"""
        import json
        import re

        # 尝试提取 JSON 数组
        # 方法 1: 查找 [ ... ] 的边界
        start = llm_output.find('[')
        end = llm_output.rfind(']')

        if start != -1 and end != -1 and end > start:
            json_str = llm_output[start:end + 1]
            try:
                results = json.loads(json_str)
                if isinstance(results, list):
                    return results
            except json.JSONDecodeError:
                pass

        # 方法 2: 尝试用正则提取各个 JSON 对象
        pattern = r'\{[^{}]*"rule_id"[^{}]*\}'
        matches = re.findall(pattern, llm_output, re.DOTALL)
        if matches:
            results = []
            for m in matches:
                try:
                    obj = json.loads(m)
                    results.append(obj)
                except json.JSONDecodeError:
                    continue
            if results:
                return results

        # 方法 3: 降级 - 为每条规则生成默认结果
        logger.warning(f"LLM 输出解析失败，使用降级结果 ({len(llm_output)} 字符)")
        return [
            {
                'rule_id': r.get('rule_id', ''),
                'rule_name': r.get('name', ''),
                'is_compliant': True,
                'findings': '模型输出解析失败，无法评估',
                'confidence': 0.0,
            }
            for r in rules
        ]

    def _merge_results(
        self,
        document_id: str,
        chunk_results: List[Dict[str, Any]],
        sections: List[DocumentSection],
        total_rules: int,
        elapsed: float,
    ) -> Dict[str, Any]:
        """合并多个段落的质控结果"""

        all_evaluation_results: List[Dict[str, Any]] = []
        total_tokens = 0
        total_api_time = 0.0

        for cr in chunk_results:
            all_evaluation_results.extend(cr.get('evaluation_results', []))
            pm = cr.get('performance_metrics', {})
            total_tokens += pm.get('token_usage', 0)
            total_api_time += pm.get('api_time', 0)

        # 去重（同一 rule_id 只保留第一个「不合规」结果，若全部合规则保留第一个）
        seen_ids: Dict[str, Dict[str, Any]] = {}
        for er in all_evaluation_results:
            rid = er.get('rule_id', '')
            if not rid:
                continue
            if rid not in seen_ids:
                seen_ids[rid] = er
            elif not er.get('is_compliant', True) and seen_ids[rid].get('is_compliant', True):
                # 如果新结果是不合规，覆盖之前的合规结果
                seen_ids[rid] = er

        deduped = list(seen_ids.values())

        # 统计
        compliant = sum(
            1 for r in deduped
            if r.get('is_compliant') is True
            or r.get('status') in ('compliant', 'not_applicable')
        )
        issues = len(deduped) - compliant
        rate = (compliant / len(deduped) * 100) if deduped else 100.0

        logger.info(
            f"[Pipeline] 完成: {len(deduped)} 条规则 (去重前 {len(all_evaluation_results)}), "
            f"{compliant} 合规, {issues} 问题, "
            f"合规率 {rate:.1f}%, "
            f"token {total_tokens}, "
            f"耗时 {elapsed:.1f}s"
        )

        return {
            'document_id': document_id,
            'pipeline_mode': 'segmented',
            'total_rules': len(deduped),
            'sections_count': len(sections),
            'sections_summary': [
                {
                    'title': s.title,
                    'type': s.section_type,
                    'chars': s.char_count,
                    'timestamp': s.timestamp,
                }
                for s in sections
            ],
            'evaluation_summary': {
                'total_rules': len(deduped),
                'compliant_rules': compliant,
                'issues_found': issues,
                'compliance_rate': round(rate, 2),
                'model': self.client.model,
            },
            'evaluation_results': deduped,
            'performance_metrics': {
                'token_usage': total_tokens,
                'api_time': round(total_api_time, 2),
                'pipeline_time': round(elapsed, 2),
                'llm_calls': len(chunk_results),
            },
        }

    def _empty_result(self, document_id: str) -> Dict[str, Any]:
        return {
            'document_id': document_id,
            'pipeline_mode': 'segmented',
            'total_rules': 0,
            'evaluation_summary': {
                'compliance_rate': 100.0,
                'issues_found': 0,
            },
            'evaluation_results': [],
            'performance_metrics': {},
        }
