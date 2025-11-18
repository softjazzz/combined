#!/usr/bin/env python3
"""
Generate positive/negative medical record examples for custom QC rules by
calling Alibaba DashScope (Qwen) compatible OpenAI API.

Usage examples:
  python scripts/aliyun_generate_rule_examples.py --range 001-005 --out /tmp/examples_001_005.json
  ALIYUN_API_KEY=sk-xxx python scripts/aliyun_generate_rule_examples.py --rule LX-010
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Dict, Any, Optional

DEFAULT_RULE_PATH = (
    Path(__file__).resolve().parent.parent
    / "apps"
    / "medqc-web"
    / "backend"
    / "app"
    / "data"
    / "custom_rules_33.json"
)

DEFAULT_MODEL = os.environ.get("ALIYUN_MODEL", "qwen3-235b-a22b-instruct-2507")
DEFAULT_ENDPOINT = os.environ.get(
    "ALIYUN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
)

PROMPT_TEMPLATE = """你是一名资深的病历质控专家和医疗文书撰写专家。

请为以下质控规则设计一个正例和一个反例病历示例：

规则信息：
- 规则ID: {rule_id}
- 规则名称: {name}
- 规则描述: {description}
- 适用文书: {documents}
- 缺陷级别: {defect_level}
- 复杂度: {complexity}

要求：
1. 正例：完全符合该质控规则要求的标准病历片段
2. 反例：明显违反该质控规则的缺陷病历片段
3. 病历内容必须真实可信，符合临床实际，语气为正式医疗文书
4. 不要包含任何说明性、评论性、分析性文字
5. 只输出纯粹的病历正文，可分章节（如“主诉”“现病史”等）
6. 根据规则复杂度调整示例长度：
   - 低复杂度：300-500字
   - 中复杂度：500-800字
   - 高复杂度：800-1200字

输出格式（JSON）：
{{
  "positive": {{
    "title": "正例标题",
    "summary": "一句话说明为何合规",
    "sections": [
      {{"heading": "章节标题", "content": "章节内容"}}
    ],
    "focusPoints": ["关注点1", "关注点2"]
  }},
  "negative": {{
    "title": "反例标题",
    "summary": "一句话说明缺陷特征",
    "sections": [
      {{"heading": "章节标题", "content": "章节内容"}}
    ],
    "focusPoints": ["缺陷点1", "缺陷点2"]
  }}
}}

请严格按照上述 JSON 结构回答。
"""


@dataclass
class Rule:
    rule_id: str
    name: str
    description: str
    applicable_documents: List[str]
    defect_level: str
    complexity: str


def load_rules(path: Path) -> Dict[str, Rule]:
    data = json.loads(path.read_text("utf-8"))
    rules: Dict[str, Rule] = {}
    for item in data:
        rules[item["rule_id"]] = Rule(
            rule_id=item["rule_id"],
            name=item.get("name", ""),
            description=item.get("description", ""),
            applicable_documents=item.get("applicable_documents", []),
            defect_level=item.get("defect_level", ""),
            complexity=item.get("complexity", ""),
        )
    return rules


def iter_rule_ids(rule_map: Dict[str, Rule], args: argparse.Namespace) -> Iterable[str]:
    if args.rule:
        rid = args.rule.upper()
        if rid not in rule_map:
            raise ValueError(f"Rule {rid} not found in dataset.")
        return [rid]
    if not args.range:
        return sorted(rule_map.keys())
    start, end = args.range.split("-", 1)
    start = start.strip()
    end = end.strip()
    if not (start.isdigit() and end.isdigit()):
        raise ValueError("Range must be like 001-037")
    prefix = args.prefix or "LX-"
    start_num = int(start)
    end_num = int(end)
    return [
        f"{prefix}{i:03d}"
        for i in range(start_num, end_num + 1)
        if f"{prefix}{i:03d}" in rule_map
    ]


def call_dashscope(
    api_key: str,
    messages: List[Dict[str, str]],
    model: str,
    endpoint: str,
    max_tokens: int,
    temperature: float,
) -> str:
    url = f"{endpoint.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
    }
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTPError {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"URLError: {exc}") from exc

    try:
        response = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to decode response JSON: {raw}") from exc

    choices = response.get("choices")
    if not choices:
        raise RuntimeError(f"No choices in response: {response}")
    content = choices[0].get("message", {}).get("content", "")
    if not content:
        raise RuntimeError(f"No content in response: {response}")
    return content


def ensure_json_output(text: str) -> Dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        # Strip potential fenced code blocks
        parts = text.split("```")
        if len(parts) >= 3:
            text = parts[1]
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Model output不是有效JSON: {text}") from exc


def generate_for_rule(
    rule: Rule,
    api_key: str,
    model: str,
    endpoint: str,
    max_tokens: int,
    temperature: float,
    delay: float,
) -> Dict[str, Any]:
    user_prompt = PROMPT_TEMPLATE.format(
        rule_id=rule.rule_id,
        name=rule.name,
        description=rule.description,
        documents="、".join(rule.applicable_documents),
        defect_level=rule.defect_level,
        complexity=rule.complexity,
    )
    messages = [
        {
            "role": "system",
            "content": "You are an experienced Chinese medical documentation writer. "
            "Return JSON only.",
        },
        {"role": "user", "content": user_prompt},
    ]
    content = call_dashscope(
        api_key=api_key,
        messages=messages,
        model=model,
        endpoint=endpoint,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    data = ensure_json_output(content)
    time.sleep(delay)
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate QC rule medical examples via Aliyun DashScope.")
    parser.add_argument("--rules-path", type=Path, default=DEFAULT_RULE_PATH, help="Path to rules JSON file")
    parser.add_argument("--range", type=str, help="Rule ID range like 001-037")
    parser.add_argument("--rule", type=str, help="Single rule id (e.g., LX-010)")
    parser.add_argument("--prefix", type=str, default="LX-", help="Rule id prefix when using --range")
    parser.add_argument("--out", type=Path, required=True, help="Output JSON file")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL, help="DashScope model name")
    parser.add_argument("--endpoint", type=str, default=DEFAULT_ENDPOINT, help="DashScope base URL")
    parser.add_argument("--temperature", type=float, default=0.2, help="Sampling temperature")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay (seconds) between requests")
    parser.add_argument("--max-tokens", type=int, default=2048, help="Max tokens per completion")
    parser.add_argument("--dry-run", action="store_true", help="Do not call API, just show prompts")
    args = parser.parse_args()

    api_key = os.environ.get("ALIYUN_API_KEY")
    if not api_key and not args.dry_run:
        print("ERROR: 请先设置 ALIYUN_API_KEY 环境变量。", file=sys.stderr)
        sys.exit(1)

    if args.rules_path and not args.rules_path.exists():
        print(f"ERROR: Rules file not found: {args.rules_path}", file=sys.stderr)
        sys.exit(1)

    rule_map = load_rules(args.rules_path)
    results: Dict[str, Any] = {}

    try:
        target_ids = list(iter_rule_ids(rule_map, args))
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"即将处理 {len(target_ids)} 条规则。输出文件: {args.out}")

    for rid in target_ids:
        rule = rule_map[rid]
        print(f"=== 处理 {rid} {rule.name} ===")
        if args.dry_run:
            prompt = PROMPT_TEMPLATE.format(
                rule_id=rule.rule_id,
                name=rule.name,
                description=rule.description,
                documents="、".join(rule.applicable_documents),
                defect_level=rule.defect_level,
                complexity=rule.complexity,
            )
            print(prompt)
            continue
        try:
            data = generate_for_rule(
                rule=rule,
                api_key=api_key,
                model=args.model,
                endpoint=args.endpoint,
                max_tokens=args.max_tokens,
                temperature=args.temperature,
                delay=args.delay,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"!! 生成失败: {exc}", file=sys.stderr)
            results[rid] = {"error": str(exc)}
            continue
        results[rid] = data
        print(f"✓ 已生成 {rid}")

    if not args.dry_run:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(results, ensure_ascii=False, indent=2), "utf-8")
        print(f"结果已写入 {args.out}")


if __name__ == "__main__":
    main()
