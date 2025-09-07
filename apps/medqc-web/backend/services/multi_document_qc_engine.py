#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分文书类型质控引擎
为每种文书类型创建专门的质控prompt，提高质控准确性
"""

import json
import time
import asyncio
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

from .document_separator import DocumentSeparator, DocumentSection

logger = logging.getLogger(__name__)

@dataclass
class DocumentQCResult:
    """单个文书的质控结果"""
    document_type: str
    total_rules: int
    compliant_rules: int
    evaluation_results: List[Dict[str, Any]]
    processing_time: float
    token_usage: int
    confidence: float
    critical_violations: List[str]

@dataclass
class MultiDocumentQCResult:
    """多文书质控结果"""
    document_id: str
    document_results: Dict[str, DocumentQCResult]
    overall_summary: Dict[str, Any]
    total_processing_time: float
    total_token_usage: int
    overall_grade: str
    optimization_metrics: Dict[str, Any]

class MultiDocumentQCEngine:
    """分文书类型质控引擎"""
    
    def __init__(self, llm_client):
        self.llm_client = llm_client
        self.document_separator = DocumentSeparator()
        
        # 专门化的prompt模板
        self.document_prompts = {
            '入院记录': self._build_admission_prompt,
            '病程记录': self._build_progress_prompt,
            '手术记录': self._build_surgery_prompt,
            '出院记录': self._build_discharge_prompt
        }
        
        # 文书类型权重（用于总体评分）
        self.document_weights = {
            '入院记录': 0.25,
            '病程记录': 0.35,
            '手术记录': 0.25,
            '出院记录': 0.15
        }
        
        logger.info("多文书质控引擎初始化完成")
    
    async def evaluate_multi_document(
        self,
        document_id: str,
        document_content: str,
        applicable_rules: Dict[str, List[Dict[str, Any]]],
        preclassified_documents: Optional[Dict[str, Any]] = None
    ) -> MultiDocumentQCResult:
        """
        评估多文书病历

        Args:
            document_id: 文档ID
            document_content: 完整病历内容
            applicable_rules: 按文书类型分组的适用规则
            preclassified_documents: 预分类的文书映射（可选）。
                形如 { '入院记录': [ '文本1', '文本2' ], '病程记录': ['...'] }
                也兼容 { '入院记录': '合并后的文本' } 形式

        Returns:
            MultiDocumentQCResult: 多文书质控结果
        """
        logger.info(f"🚀 开始多文书质控评估: {document_id}")
        start_time = time.time()

        try:
            # 1. 获取文书内容：优先使用预分类映射，其次自动分离
            separated_documents: Dict[str, DocumentSection] = {}
            if preclassified_documents and len(preclassified_documents) > 0:
                logger.info("📋 使用前端提供的预分类文书映射，跳过自动分离")
                separated_documents = self._build_sections_from_preclassified(preclassified_documents)
            else:
                logger.info("📋 未提供预分类映射，执行智能文书分离...")
                separated_documents = self.document_separator.separate_document(document_content)

            if not separated_documents:
                raise Exception("未能识别到任何有效的文书类型")

            logger.info(f"✅ 已获得 {len(separated_documents)} 种文书类型用于评估")

            # 2. 并行评估各文书类型
            logger.info("🔄 第二步: 并行评估各文书类型...")
            document_results = await self._evaluate_documents_parallel(
                document_id, separated_documents, applicable_rules
            )

            # 检查是否有可评估的结果
            if not document_results:
                raise Exception("没有可评估的文书类型，请检查文书内容和类型配置")

            # 3. 计算总体统计
            logger.info("📊 第三步: 计算总体统计...")
            overall_summary = self._calculate_overall_summary(document_results)

            # 4. 确定总体等级
            overall_grade = self._determine_overall_grade(document_results, overall_summary)

            # 5. 计算优化指标
            total_processing_time = time.time() - start_time
            total_token_usage = sum(result.token_usage for result in document_results.values())

            optimization_metrics = self._calculate_optimization_metrics(
                document_results, total_processing_time, total_token_usage
            )

            result = MultiDocumentQCResult(
                document_id=document_id,
                document_results=document_results,
                overall_summary=overall_summary,
                total_processing_time=total_processing_time,
                total_token_usage=total_token_usage,
                overall_grade=overall_grade,
                optimization_metrics=optimization_metrics
            )

            logger.info(f"✅ 多文书质控评估完成: {document_id}")
            logger.info(f"📊 总体等级: {overall_grade}, 处理时间: {total_processing_time:.2f}s")

            return result

        except Exception as e:
            logger.error(f"❌ 多文书质控评估失败: {document_id}, 错误: {e}")
            raise

    def _build_sections_from_preclassified(self, preclassified_documents: Dict[str, Any]) -> Dict[str, DocumentSection]:
        """将前端预分类的文书映射转换为内部的DocumentSection结构"""
        sections: Dict[str, DocumentSection] = {}

        for doc_type, value in preclassified_documents.items():
            if not value:
                continue

            # value可以是字符串或列表
            if isinstance(value, str):
                content = value.strip()
            elif isinstance(value, list):
                # 合并列表内容
                content = "\n\n".join([str(v or '').strip() for v in value if v])
            elif isinstance(value, dict) and 'content' in value:
                content = str(value.get('content', '')).strip()
            else:
                # 未知格式，跳过
                logger.warning(f"⚠️ 预分类文书格式不支持: {doc_type} -> {type(value)}")
                continue

            if len(content) < 1:
                continue

            # 置信度：预分类视为高置信度0.9，后续可随前端传值增强
            section = DocumentSection(
                document_type=doc_type,
                content=content,
                start_position=0,
                end_position=len(content),
                confidence=0.9,
                keywords_found=[]
            )
            sections[doc_type] = section

        return sections
    
    async def _evaluate_documents_parallel(
        self,
        document_id: str,
        separated_documents: Dict[str, DocumentSection],
        applicable_rules: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, DocumentQCResult]:
        """并行评估各文书类型"""

        # 创建评估任务
        tasks = []
        for doc_type, section in separated_documents.items():
            # 只评估后端已知prompt的类型
            if doc_type not in self.document_prompts:
                logger.warning(f"⚠️ 未配置prompt的文书类型: {doc_type}，已跳过")
                continue

            if doc_type in applicable_rules and applicable_rules[doc_type]:
                task = self._evaluate_single_document(
                    document_id, doc_type, section, applicable_rules[doc_type]
                )
                tasks.append((doc_type, task))

        # 并行执行
        results = {}
        if tasks:
            logger.info(f"🔄 并行执行 {len(tasks)} 个文书类型的质控评估...")

            # 使用asyncio.gather进行并行处理
            task_results = await asyncio.gather(
                *[task for _, task in tasks],
                return_exceptions=True
            )

            # 处理结果
            for i, (doc_type, _) in enumerate(tasks):
                result = task_results[i]
                if isinstance(result, Exception):
                    logger.error(f"❌ {doc_type} 评估失败: {result}")
                    continue
                results[doc_type] = result
        else:
            logger.warning("⚠️ 没有可评估的文书类型任务")

        return results
    
    async def _evaluate_single_document(
        self,
        document_id: str,
        document_type: str,
        section: DocumentSection,
        rules: List[Dict[str, Any]]
    ) -> DocumentQCResult:
        """评估单个文书类型"""
        logger.info(f"📋 开始评估 {document_type} ({len(section.content)}字符, {len(rules)}条规则)")
        start_time = time.time()
        
        try:
            # 构建专门化的prompt
            prompt = self._build_specialized_prompt(document_type, section.content, rules)
            
            # 调用LLM API
            llm_response = await self.llm_client.generate_response(prompt)
            
            if llm_response["status"] != "success":
                raise Exception(f"LLM API调用失败: {llm_response.get('error', 'Unknown error')}")
            
            # 解析评估结果
            evaluation_results = self._parse_llm_response(llm_response["content"])
            
            # 计算统计信息
            total_rules = len(rules)
            compliant_rules = sum(1 for result in evaluation_results if result.get('is_compliant', False))
            
            # 查找严重违规
            critical_violations = []
            for result in evaluation_results:
                if not result.get('is_compliant', False):
                    for rule in rules:
                        if rule["rule_id"] == result.get('rule_id'):
                            if rule["defect_level"] in ["单项否决丙级", "严重缺陷"]:
                                critical_violations.append(f"{result['rule_id']}: {result.get('findings', '')}")
                            break
            
            processing_time = time.time() - start_time
            token_usage = llm_response.get("token_usage", {}).get("total_tokens", 0)
            
            result = DocumentQCResult(
                document_type=document_type,
                total_rules=total_rules,
                compliant_rules=compliant_rules,
                evaluation_results=evaluation_results,
                processing_time=processing_time,
                token_usage=token_usage,
                confidence=section.confidence,
                critical_violations=critical_violations
            )
            
            logger.info(f"✅ {document_type} 评估完成: {compliant_rules}/{total_rules} 合规 ({processing_time:.2f}s)")
            return result
            
        except Exception as e:
            logger.error(f"❌ {document_type} 评估失败: {e}")
            raise
    
    def _build_specialized_prompt(self, document_type: str, content: str, rules: List[Dict[str, Any]]) -> str:
        """构建专门化的质控prompt"""
        if document_type in self.document_prompts:
            return self.document_prompts[document_type](content, rules)
        else:
            # 使用通用prompt
            return self._build_generic_prompt(document_type, content, rules)
    
    def _build_admission_prompt(self, content: str, rules: List[Dict[str, Any]]) -> str:
        """构建入院记录专门化prompt"""
        rules_schema = [
            {
                "rule_id": rule["rule_id"],
                "description": rule["description"],
                "category": rule["category"],
                "defect_level": rule["defect_level"]
            }
            for rule in rules
        ]
        
        return f"""你是一名专业的入院记录质控专家，具有丰富的临床经验和入院记录规范知识。

请仔细阅读以下【入院记录】，并根据【质控规则】进行专业评估。

【入院记录内容】:
{content}

【质控规则】:
{json.dumps(rules_schema, ensure_ascii=False, indent=2)}

## 入院记录质控要点：
1. **主诉完整性**: 检查主诉是否简明扼要，时间明确
2. **现病史逻辑性**: 评估现病史的时间顺序和逻辑关系
3. **既往史相关性**: 确认既往史与现病史的关联性
4. **体格检查系统性**: 验证体格检查的系统性和完整性
5. **诊断合理性**: 评估入院诊断的合理性和依据充分性

## 评估输出格式：
```json
[
  {{
    "rule_id": "规则ID",
    "is_compliant": true/false,
    "findings": "针对入院记录的具体评估发现，详细说明为什么合规或不合规",
    "evidence": "从入院记录中提取的具体证据文本片段，用分号分隔多个证据",
    "confidence": 0.0-1.0,
    "evidence_locations": ["入院记录第1段", "入院记录第3段"],
    "suggestions": ["改进建议1", "改进建议2"]
  }}
]
```

请基于入院记录的专业标准进行评估："""
    
    def _build_progress_prompt(self, content: str, rules: List[Dict[str, Any]]) -> str:
        """构建病程记录专门化prompt"""
        rules_schema = [
            {
                "rule_id": rule["rule_id"],
                "description": rule["description"],
                "category": rule["category"],
                "defect_level": rule["defect_level"]
            }
            for rule in rules
        ]
        
        return f"""你是一名专业的病程记录质控专家，具有丰富的临床经验和病程记录规范知识。

请仔细阅读以下【病程记录】，并根据【质控规则】进行专业评估。

【病程记录内容】:
{content}

【质控规则】:
{json.dumps(rules_schema, ensure_ascii=False, indent=2)}

## 病程记录质控要点：
1. **时间连续性**: 检查病程记录的时间连续性和规律性
2. **病情变化**: 评估病情变化的记录完整性和准确性
3. **治疗方案**: 验证治疗方案的合理性和调整依据
4. **医师查房**: 确认上级医师查房记录的完整性
5. **护理配合**: 评估医护配合和护理措施的记录

## 评估输出格式：
```json
[
  {{
    "rule_id": "规则ID",
    "is_compliant": true/false,
    "findings": "针对病程记录的具体评估发现，详细说明为什么合规或不合规",
    "evidence": "从病程记录中提取的具体证据文本片段，用分号分隔多个证据",
    "confidence": 0.0-1.0,
    "evidence_locations": ["病程记录第1条", "病程记录第3条"],
    "suggestions": ["改进建议1", "改进建议2"]
  }}
]
```

请基于病程记录的专业标准进行评估："""
    
    def _build_surgery_prompt(self, content: str, rules: List[Dict[str, Any]]) -> str:
        """构建手术记录专门化prompt"""
        rules_schema = [
            {
                "rule_id": rule["rule_id"],
                "description": rule["description"],
                "category": rule["category"],
                "defect_level": rule["defect_level"]
            }
            for rule in rules
        ]
        
        return f"""你是一名专业的手术记录质控专家，具有丰富的外科临床经验和手术记录规范知识。

请仔细阅读以下【手术记录】，并根据【质控规则】进行专业评估。

【手术记录内容】:
{content}

【质控规则】:
{json.dumps(rules_schema, ensure_ascii=False, indent=2)}

## 手术记录质控要点：
1. **术前准备**: 检查术前诊断、手术指征和准备工作
2. **手术过程**: 评估手术步骤的详细性和规范性
3. **麻醉记录**: 验证麻醉方式和监测记录的完整性
4. **术中情况**: 确认术中发现和处理措施的记录
5. **术后处理**: 评估术后诊断和处理措施的合理性

## 评估输出格式：
```json
[
  {{
    "rule_id": "规则ID",
    "is_compliant": true/false,
    "findings": "针对手术记录的具体评估发现，详细说明为什么合规或不合规",
    "evidence": "从手术记录中提取的具体证据文本片段，用分号分隔多个证据",
    "confidence": 0.0-1.0,
    "evidence_locations": ["手术记录术前部分", "手术记录术中部分"],
    "suggestions": ["改进建议1", "改进建议2"]
  }}
]
```

请基于手术记录的专业标准进行评估："""
    
    def _build_discharge_prompt(self, content: str, rules: List[Dict[str, Any]]) -> str:
        """构建出院记录专门化prompt"""
        rules_schema = [
            {
                "rule_id": rule["rule_id"],
                "description": rule["description"],
                "category": rule["category"],
                "defect_level": rule["defect_level"]
            }
            for rule in rules
        ]
        
        return f"""你是一名专业的出院记录质控专家，具有丰富的临床经验和出院记录规范知识。

请仔细阅读以下【出院记录】，并根据【质控规则】进行专业评估。

【出院记录内容】:
{content}

【质控规则】:
{json.dumps(rules_schema, ensure_ascii=False, indent=2)}

## 出院记录质控要点：
1. **诊疗经过**: 检查住院期间诊疗经过的完整性
2. **诊断一致性**: 评估入院诊断与出院诊断的一致性
3. **治疗效果**: 验证治疗效果和病情转归的记录
4. **出院医嘱**: 确认出院医嘱的合理性和完整性
5. **随访安排**: 评估随访计划和健康指导的充分性

## 评估输出格式：
```json
[
  {{
    "rule_id": "规则ID",
    "is_compliant": true/false,
    "findings": "针对出院记录的具体评估发现，详细说明为什么合规或不合规",
    "evidence": "从出院记录中提取的具体证据文本片段，用分号分隔多个证据",
    "confidence": 0.0-1.0,
    "evidence_locations": ["出院记录诊疗经过部分", "出院记录出院医嘱部分"],
    "suggestions": ["改进建议1", "改进建议2"]
  }}
]
```

请基于出院记录的专业标准进行评估："""

    def _build_generic_prompt(self, document_type: str, content: str, rules: List[Dict[str, Any]]) -> str:
        """构建通用质控prompt"""
        rules_schema = [
            {
                "rule_id": rule["rule_id"],
                "description": rule["description"],
                "category": rule["category"],
                "defect_level": rule["defect_level"]
            }
            for rule in rules
        ]

        return f"""你是一名经验丰富的病历质控专家，具有丰富的临床经验和质控标准知识。

请仔细阅读以下【{document_type}】，并根据【质控规则】进行专业评估。

【{document_type}内容】:
{content}

【质控规则】:
{json.dumps(rules_schema, ensure_ascii=False, indent=2)}

## 评估要求：
1. 对每一条规则进行独立评估，不得遗漏任何规则
2. 仔细查找原文中的相关证据
3. 基于医学专业知识和质控标准进行判断
4. 提供具体的发现和证据支持

## 输出格式：
```json
[
  {{
    "rule_id": "规则ID",
    "is_compliant": true/false,
    "findings": "详细的评估发现",
    "evidence": "从原文中提取的具体证据",
    "confidence": 0.0-1.0
  }}
]
```

请开始评估："""

    def _parse_llm_response(self, response_content: str) -> List[Dict[str, Any]]:
        """解析LLM响应"""
        try:
            # 提取JSON部分
            json_start = response_content.find('[')
            json_end = response_content.rfind(']') + 1

            if json_start == -1 or json_end == 0:
                raise ValueError("未找到JSON格式的响应")

            json_content = response_content[json_start:json_end]
            results_data = json.loads(json_content)

            return results_data

        except Exception as e:
            logger.error(f"解析LLM响应失败: {e}")
            logger.error(f"响应内容: {response_content}")
            raise Exception(f"解析LLM响应失败: {e}")

    def _calculate_overall_summary(self, document_results: Dict[str, DocumentQCResult]) -> Dict[str, Any]:
        """计算总体统计摘要"""
        total_rules = sum(result.total_rules for result in document_results.values())
        total_compliant = sum(result.compliant_rules for result in document_results.values())

        # 加权合规率计算
        weighted_compliance = 0
        total_weight = 0

        for doc_type, result in document_results.items():
            weight = self.document_weights.get(doc_type, 0.25)
            if result.total_rules > 0:
                compliance_rate = result.compliant_rules / result.total_rules
                weighted_compliance += compliance_rate * weight
                total_weight += weight

        overall_compliance_rate = weighted_compliance / total_weight if total_weight > 0 else 0

        # 收集所有严重违规
        all_critical_violations = []
        for result in document_results.values():
            all_critical_violations.extend(result.critical_violations)

        return {
            "total_rules": total_rules,
            "compliant_rules": total_compliant,
            "compliance_rate": overall_compliance_rate * 100,
            "weighted_compliance_rate": overall_compliance_rate * 100,
            "document_count": len(document_results),
            "critical_violations": all_critical_violations,
            "document_breakdown": {
                doc_type: {
                    "rules": result.total_rules,
                    "compliant": result.compliant_rules,
                    "rate": (result.compliant_rules / result.total_rules * 100) if result.total_rules > 0 else 0
                }
                for doc_type, result in document_results.items()
            }
        }

    def _determine_overall_grade(self, document_results: Dict[str, DocumentQCResult], summary: Dict[str, Any]) -> str:
        """确定总体等级"""
        # 检查严重违规
        if summary["critical_violations"]:
            return "丙级"

        # 基于加权合规率
        weighted_rate = summary["weighted_compliance_rate"]

        if weighted_rate >= 95:
            return "甲级"
        elif weighted_rate >= 80:
            return "乙级"
        else:
            return "丙级"

    def _calculate_optimization_metrics(
        self,
        document_results: Dict[str, DocumentQCResult],
        total_time: float,
        total_tokens: int
    ) -> Dict[str, Any]:
        """计算优化指标"""

        # 估算单一prompt模式的成本
        estimated_single_prompt_tokens = total_tokens * 2.5  # 单一prompt通常更长
        estimated_single_prompt_time = total_time * 1.8     # 单一prompt处理时间更长

        token_savings_rate = 1 - (total_tokens / estimated_single_prompt_tokens) if estimated_single_prompt_tokens > 0 else 0
        time_savings_rate = 1 - (total_time / estimated_single_prompt_time) if estimated_single_prompt_time > 0 else 0

        # 成本计算 (基于Qwen 2.5 14B定价)
        cost_per_1k_tokens = 0.002  # ¥0.002/1K tokens
        actual_cost = (total_tokens / 1000) * cost_per_1k_tokens
        estimated_single_cost = (estimated_single_prompt_tokens / 1000) * cost_per_1k_tokens
        cost_savings = estimated_single_cost - actual_cost

        return {
            "token_usage": total_tokens,
            "estimated_single_prompt_tokens": estimated_single_prompt_tokens,
            "token_savings_rate": max(0, token_savings_rate),
            "processing_time": total_time,
            "estimated_single_prompt_time": estimated_single_prompt_time,
            "time_savings_rate": max(0, time_savings_rate),
            "actual_cost": actual_cost,
            "estimated_single_cost": estimated_single_cost,
            "cost_savings": max(0, cost_savings),
            "parallel_efficiency": len(document_results) / total_time if total_time > 0 else 0,
            "average_document_time": total_time / len(document_results) if document_results and len(document_results) > 0 else 0
        }
