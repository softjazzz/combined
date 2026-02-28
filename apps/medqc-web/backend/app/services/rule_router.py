"""
质控规则路由器

基于映射表将文书类型与适用规则匹配，零 LLM 调用。
"""
import json
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# section_type → applicable_documents 的映射
# 左侧是 document_segmenter 输出的类型，右侧是规则 JSON 中的类型
# 注意：保持精准映射，不要过度扩展，否则一个段落会匹配太多规则
SECTION_TO_RULE_TYPES = {
    'admission_record':     ['admission_record'],
    'progress_note':        ['progress_note', 'course_record'],
    'operation_record':     ['operation_record'],
    'discharge_record':     ['discharge_record', 'discharge_summary'],
    'consultation_record':  ['consultation_record'],
    'case_discussion':      ['case_discussion'],
    'examination_report':   ['examination_report', 'lab_report'],
    'medical_order':        ['medical_order'],
    'consent_form':         ['consent_form', 'informed_consent'],
    'anesthesia_record':    ['anesthesia_record'],
    'transfusion_record':   ['transfusion_record'],
    # 新增细粒度类型
    'preop_summary':        ['preop_summary', 'operation_record'],
    'preop_discussion':     ['preop_discussion', 'case_discussion'],
}



class RuleRouter:
    """
    根据段落的文书类型，筛选出适用的质控规则。
    """

    def __init__(self, rules: Optional[List[Dict[str, Any]]] = None):
        """
        Args:
            rules: 规则列表。如果为 None，自动从 JSON 文件加载。
        """
        if rules is not None:
            self._all_rules = rules
        else:
            self._all_rules = self._load_rules()

        # 预构建索引: doc_type → [rule, ...]
        self._index: Dict[str, List[Dict[str, Any]]] = {}
        self._universal_rules: List[Dict[str, Any]] = []

        for rule in self._all_rules:
            applicable = rule.get('applicable_documents', [])
            if not applicable:
                self._universal_rules.append(rule)
            else:
                for doc_type in applicable:
                    self._index.setdefault(doc_type, []).append(rule)

        logger.info(
            f"RuleRouter 初始化: {len(self._all_rules)} 条规则, "
            f"{len(self._universal_rules)} 条通用规则, "
            f"{len(self._index)} 个文书类型索引"
        )

    def _load_rules(self) -> List[Dict[str, Any]]:
        """从 JSON 文件加载规则"""
        json_path = Path(__file__).parent.parent / 'data' / 'sichuan_rules_146.json'
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载规则文件失败: {e}")
            return []

    def get_rules_for_section(self, section_type: str) -> List[Dict[str, Any]]:
        """
        根据段落文书类型返回适用的规则。

        Args:
            section_type: 段落文书类型 (document_segmenter 输出的)

        Returns:
            适用规则列表（已去重）
        """
        # 获取对应的规则文书类型
        rule_doc_types = SECTION_TO_RULE_TYPES.get(section_type, [section_type])

        # 收集匹配的规则
        seen_ids = set()
        matched_rules: List[Dict[str, Any]] = []

        # 先加类型匹配的
        for rdt in rule_doc_types:
            for rule in self._index.get(rdt, []):
                rid = rule.get('rule_id', '')
                if rid not in seen_ids:
                    seen_ids.add(rid)
                    matched_rules.append(rule)

        # 再加通用规则
        for rule in self._universal_rules:
            rid = rule.get('rule_id', '')
            if rid not in seen_ids:
                seen_ids.add(rid)
                matched_rules.append(rule)

        return matched_rules

    def route_all(
        self,
        section_types: List[str],
        deduplicate: bool = True,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        批量路由：为多个段落类型返回各自适用的规则。

        Args:
            section_types: 段落类型列表
            deduplicate: 如果某条规则在多个段落中都适用，
                         是否只在第一个匹配的段落中保留（避免重复评估）

        Returns:
            {section_type: [rule, ...]} 映射
        """
        result: Dict[str, List[Dict[str, Any]]] = {}
        assigned_rule_ids = set()

        for st in section_types:
            rules = self.get_rules_for_section(st)

            if deduplicate:
                # 只保留尚未分配过的规则
                new_rules = []
                for rule in rules:
                    rid = rule.get('rule_id', '')
                    if rid not in assigned_rule_ids:
                        assigned_rule_ids.add(rid)
                        new_rules.append(rule)
                result[st] = new_rules
            else:
                result[st] = rules

        return result
