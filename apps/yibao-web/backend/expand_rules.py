#!/usr/bin/env python3
"""
将聚合规则（包含大数组的 in 条件）展开为细粒度规则（每个名称一条），
用于将 4 条聚合规则扩展为 1000+ 条单项规则，便于统计与逐条启停。

用法：
  cd apps/yibao-web/backend
  python3 expand_rules.py

生成：
  - medical_rules.expanded.json  （展开后的规则文件）
  - 自动备份当前 medical_rules.json 为 medical_rules.backup.before_expand.json
  - 用展开后的文件覆盖 medical_rules.json
"""
from __future__ import annotations
import json
import hashlib
import shutil
from pathlib import Path
from typing import Any, Dict, List

SRC = Path(__file__).parent / 'medical_rules.json'
DST = Path(__file__).parent / 'medical_rules.expanded.json'
BACKUP = Path(__file__).parent / 'medical_rules.backup.before_expand.json'

# 识别需要展开的条件（目前针对药品名称等使用 in 数组的场景）
TARGET_FACTS = {
    'order.drug_name',
    'order.service_name',
    'order.item_name',
}


def make_code(base_code: str, idx: int, name: str) -> str:
    # 根据名称生成短hash，避免code过长；确保稳定且可读
    h = hashlib.md5(name.encode('utf-8')).hexdigest()[:8]
    return f"{base_code}_{idx:05d}_{h}"


def clone_rule(rule: Dict[str, Any]) -> Dict[str, Any]:
    # 浅克隆 + 深拷贝常见列表字段
    new_rule = dict(rule)
    new_rule['conditions'] = json.loads(json.dumps(rule.get('conditions', [])))
    new_rule['actions'] = json.loads(json.dumps(rule.get('actions', [])))
    new_rule['triggers'] = list(rule.get('triggers', []))
    return new_rule


def expand_rule(rule: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    若规则包含条件 like { fact, op: 'in', value: [..] } 且 fact 在 TARGET_FACTS 中，
    则按 value 中每个元素复制一条规则，并将该条件改为相等判断。
    否则原样返回。
    """
    conds = rule.get('conditions', [])
    # 查找第一个可展开的 in 条件（目前策略：每条规则仅展开一个大列表）
    target_idx = -1
    for i, c in enumerate(conds):
        if isinstance(c, dict) and c.get('op') == 'in' and c.get('fact') in TARGET_FACTS \
           and isinstance(c.get('value'), list) and len(c['value']) > 1:
            target_idx = i
            break

    if target_idx == -1:
        return [rule]

    fact = conds[target_idx]['fact']
    values = conds[target_idx]['value']

    expanded: List[Dict[str, Any]] = []
    for idx, val in enumerate(values, start=1):
        r = clone_rule(rule)
        # 更新 code / name，使之可区分
        base_code = rule.get('code') or 'RULE'
        base_name = rule.get('name') or '未命名规则'
        r['code'] = make_code(base_code, idx, str(val))
        r['name'] = f"{base_name} - {val}"
        # 将目标条件改为相等判断
        r['conditions'][target_idx] = {
            'fact': fact,
            'op': '==',
            'value': val,
            'description': f"由聚合规则展开：{fact} == {val}"
        }
        expanded.append(r)

    return expanded


def main():
    if not SRC.exists():
        raise SystemExit(f"规则源文件不存在: {SRC}")

    with SRC.open('r', encoding='utf-8') as f:
        rules = json.load(f)
    if not isinstance(rules, list):
        raise SystemExit('规则文件结构应为 JSON 数组')

    print(f"读取到聚合规则: {len(rules)} 条，开始展开...")

    expanded_all: List[Dict[str, Any]] = []
    for rule in rules:
        expanded = expand_rule(rule)
        expanded_all.extend(expanded)

    print(f"展开后规则总数: {len(expanded_all)} 条")

    # 写出展开文件
    with DST.open('w', encoding='utf-8') as f:
        json.dump(expanded_all, f, ensure_ascii=False, indent=2)
    print(f"已生成: {DST}")

    # 备份并覆盖原文件
    shutil.copyfile(SRC, BACKUP)
    shutil.copyfile(DST, SRC)
    print(f"已备份为: {BACKUP}")
    print(f"已用展开结果覆盖: {SRC}")


if __name__ == '__main__':
    main()

