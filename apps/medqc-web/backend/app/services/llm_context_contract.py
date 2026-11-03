"""Context执行能力错误的机械合同；不定义临床状态或医学判据。"""
from types import MappingProxyType

CONTEXT_REASON_CODES = MappingProxyType({
    'OVER_BUDGET': 'llm_context_over_budget',
    'COUNT_UNAVAILABLE': 'llm_context_count_unavailable',
    'CAPABILITY_UNVERIFIED': 'llm_context_capability_unverified',
    'BUDGET_EXHAUSTED': 'llm_context_budget_exhausted',
})
CONTEXT_FAILURE_REASON_CODES = frozenset(CONTEXT_REASON_CODES.values())
