"""按预计输出配对数和真实输入长度装批；不改变事件编号、候选或引文。"""

from dataclasses import dataclass
from typing import Any, Callable, Mapping


OUTPUT_PROTOCOL_VERSION = 'exam-doc-output-batches-v3'
MAX_CHECK_CALLS = 8
OUTPUT_HEADROOM_TOKENS = 256
ESTIMATED_PAIR_TOKENS = 400


@dataclass
class CallBudget:
    maximum: int = MAX_CHECK_CALLS
    used: int = 0

    def take(self) -> bool:
        if self.used >= self.maximum:
            return False
        self.used += 1
        return True


def partition_targets(
    targets: Mapping[int, Any], *, refs: Callable, subset: Callable, prompt: Callable,
    max_completion_tokens: int, max_prompt_chars: int,
    pair_tokens: int = ESTIMATED_PAIR_TOKENS, reserved_tokens: int = OUTPUT_HEADROOM_TOKENS,
) -> list[dict[int, Any]]:
    """pair_tokens 为单个配对的平均输出估算（截断时二分兜底）；reserved_tokens 含 JSON 外壳与思考预留。"""
    pair_limit = max(1, (max_completion_tokens - reserved_tokens) // pair_tokens)

    def fits(items):
        return sum(len(refs(value)) for value in items.values()) <= pair_limit and len(prompt(items)) <= max_prompt_chars

    batches = []
    pending = {}
    for position, target in targets.items():
        candidate = {**pending, position: target}
        if fits(candidate):
            pending = candidate
            continue
        if pending:
            batches.append(pending)
            pending = {}
        if fits({position: target}):
            pending = {position: target}
            continue
        # 同次检查自身超额才拆病程，所有配对仍使用原始事件编号。
        group = []
        for ref in refs(target):
            candidate = {position: subset(target, tuple((*group, ref)))}
            if not fits(candidate):
                if not group:
                    raise ValueError('single exam-document pair exceeds input capacity')
                batches.append({position: subset(target, tuple(group))})
                group = []
                if not fits({position: subset(target, (ref,))}):
                    raise ValueError('single exam-document pair exceeds input capacity')
            group.append(ref)
        if group:
            pending = {position: subset(target, tuple(group))}
    if pending:
        batches.append(pending)
    return batches


def bisect_targets(targets: Mapping[int, Any], *, refs: Callable, subset: Callable) -> list[dict[int, Any]]:
    pairs = [(position, ref) for position, target in targets.items() for ref in refs(target)]
    if len(pairs) < 2:
        return []
    middle = len(pairs) // 2
    output = []
    for half in (pairs[:middle], pairs[middle:]):
        grouped = {}
        for position, ref in half:
            grouped.setdefault(position, []).append(ref)
        output.append({position: subset(targets[position], tuple(values)) for position, values in grouped.items()})
    return output
