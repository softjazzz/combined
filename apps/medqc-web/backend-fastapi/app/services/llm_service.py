"""
LLM 服务封装
使用 DeepSeek-V3 进行医疗编码辅助
"""

import json
import httpx
from typing import List, Optional, Dict, Any
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

try:
    from loguru import logger
except Exception:
    import logging

    logger = logging.getLogger(__name__)

from app.config import settings
from app.models.schemas import (
    ICDSuggestion, 
    ValidationWarning,
    ExtractionResult,
    ClinicalEntity,
    CodingGap,
    Evidence
)


class LLMService:
    """LLM 服务类"""

    def __init__(self):
        """初始化 OpenAI 客户端（兼容 DeepSeek API）"""
        self.client = None
        if OpenAI and settings.DEEPSEEK_API_KEY:
            http_client = httpx.Client(trust_env=False)
            self.client = OpenAI(
                api_key=settings.DEEPSEEK_API_KEY,
                base_url=settings.DEEPSEEK_API_URL,
                http_client=http_client
            )
        self.model = settings.DEEPSEEK_MODEL

    async def suggest_icd_codes(
        self,
        diagnosis_name: str,
        context: Optional[str] = None,
        category: str = 'diagnosis',
        top_k: int = 3
    ) -> List[ICDSuggestion]:
        """
        推荐 ICD 编码

        Args:
            diagnosis_name: 诊断名称
            context: 病历上下文
            category: 编码类型（diagnosis/procedure）
            top_k: 返回推荐数量

        Returns:
            ICD 编码推荐列表
        """
        try:
            if not self.client:
                return [
                    ICDSuggestion(
                        code="MOCK.001",
                        name=f"（演示）{diagnosis_name}",
                        confidence=0.75,
                        note="未配置 LLM Key，返回演示结果"
                    )
                ]
            # 构建系统提示
            system_prompt = self._build_coding_system_prompt(category)

            # 构建用户提示
            user_prompt = self._build_coding_user_prompt(
                diagnosis_name, context, category
            )

            logger.info(f"LLM 编码推荐: {diagnosis_name}, 类型: {category}")

            # 调用 LLM
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,  # 降低随机性，提高准确度
                max_tokens=1000,
                response_format={"type": "json_object"}  # 强制 JSON 输出
            )

            # 解析响应
            content = response.choices[0].message.content
            result = json.loads(content)

            # 转换为 Pydantic 模型
            suggestions = []
            for item in result.get('candidates', [])[:top_k]:
                suggestions.append(ICDSuggestion(
                    code=item.get('code', ''),
                    name=item.get('name', ''),
                    confidence=float(item.get('confidence', 0.0)),
                    note=item.get('note')
                ))

            logger.info(f"LLM 返回 {len(suggestions)} 条推荐")
            return suggestions

        except Exception as e:
            logger.error(f"LLM 编码推荐失败: {str(e)}")
            # 返回空列表而不是抛出异常
            return []

    async def validate_coding(
        self,
        primary_diagnosis: Dict[str, str],
        secondary_diagnoses: List[Dict[str, str]],
        procedures: List[Dict[str, str]],
        medical_record: Optional[str] = None
    ) -> List[ValidationWarning]:
        """
        编码校验

        Args:
            primary_diagnosis: 主诊断
            secondary_diagnoses: 次诊断列表
            procedures: 手术操作列表
            medical_record: 病历摘要（可选）

        Returns:
            校验警告列表
        """
        try:
            if not self.client:
                return [
                    ValidationWarning(
                        type='missing_diagnosis',
                        message='（演示）建议补充完善次诊断/合并症编码，以提升分组准确性',
                        evidence='（演示）病历摘要：...（未配置 LLM Key）',
                        severity='info'
                    )
                ]
            # 构建系统提示
            system_prompt = """你是一位经验丰富的病案编码质控专家。
你的任务是检查病案编码的完整性和准确性。

重点检查：
1. 诊断编码完整性（是否遗漏重要诊断）
2. 手术操作编码完整性
3. 并发症标记是否准确
4. 主诊断和次诊断的逻辑关系
5. 诊断与手术操作的匹配性

输出格式为 JSON：
{
  "warnings": [
    {
      "type": "missing_diagnosis",  // 类型：missing_diagnosis, procedure_missing, complication_marking, logic_conflict
      "message": "具体的警告信息",
      "evidence": "病历中的依据（如果有）",
      "severity": "info"  // info, warning, error
    }
  ]
}
"""

            # 构建用户提示
            user_prompt = f"""请检查以下编码：

主诊断：
- {primary_diagnosis['code']}: {primary_diagnosis['name']}

次诊断（{len(secondary_diagnoses)}个）：
"""
            for i, diag in enumerate(secondary_diagnoses, 1):
                user_prompt += f"{i}. {diag['code']}: {diag['name']}\n"

            if procedures:
                user_prompt += f"\n手术操作（{len(procedures)}个）：\n"
                for i, proc in enumerate(procedures, 1):
                    user_prompt += f"{i}. {proc['code']}: {proc['name']}\n"

            if medical_record:
                user_prompt += f"\n病历摘要：\n{medical_record}\n"

            user_prompt += "\n请分析以上编码是否完整、准确，给出建议。"

            logger.info("LLM 编码校验开始")

            # 调用 LLM
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=2000,
                response_format={"type": "json_object"}
            )

            # 解析响应
            content = response.choices[0].message.content
            result = json.loads(content)

            # 转换为 Pydantic 模型
            warnings = []
            for item in result.get('warnings', []):
                warnings.append(ValidationWarning(
                    type=item.get('type', 'missing_diagnosis'),
                    message=item.get('message', ''),
                    evidence=item.get('evidence'),
                    severity=item.get('severity', 'info')
                ))

            logger.info(f"LLM 返回 {len(warnings)} 条校验警告")
            return warnings

        except Exception as e:
            logger.error(f"LLM 编码校验失败: {str(e)}")
            return []

    def _build_coding_system_prompt(self, category: str) -> str:
        """构建编码推荐的系统提示"""
        if category == 'diagnosis':
            return """你是一位经验丰富的医疗编码专家，精通 ICD-10 国家临床版 2.0。
你的任务是根据诊断名称推荐最合适的 ICD-10 编码。

注意事项：
1. 优先推荐最具体、最准确的编码
2. 考虑编码的临床意义和 DRG 分组影响
3. 提供置信度评估（0-1）
4. 给出简短的推荐说明

输出格式为 JSON：
{
  "candidates": [
    {
      "code": "I21.001",
      "name": "急性前壁ST段抬高型心肌梗死",
      "confidence": 0.92,
      "note": "根据'前壁'和'ST段抬高'特征推荐"
    }
  ]
}
"""
        else:  # procedure
            return """你是一位经验丰富的医疗编码专家，精通 ICD-9-CM-3 手术操作编码。
你的任务是根据手术操作名称推荐最合适的 ICD-9-CM-3 编码。

注意事项：
1. 优先推荐最具体的手术操作编码
2. 考虑手术入路、方法等细节
3. 提供置信度评估（0-1）
4. 给出简短的推荐说明

输出格式为 JSON：
{
  "candidates": [
    {
      "code": "36.0700",
      "name": "经皮冠状动脉介入术",
      "confidence": 0.95,
      "note": "PCI 手术的标准编码"
    }
  ]
}
"""

    def _build_coding_user_prompt(
        self,
        diagnosis_name: str,
        context: Optional[str],
        category: str
    ) -> str:
        """构建编码推荐的用户提示"""
        if category == 'diagnosis':
            prompt = f"请为以下诊断推荐 ICD-10 编码：\n\n诊断名称：{diagnosis_name}\n"
        else:
            prompt = f"请为以下手术操作推荐 ICD-9-CM-3 编码：\n\n操作名称：{diagnosis_name}\n"

        if context:
            prompt += f"\n病历上下文：\n{context}\n"

        prompt += "\n请推荐最合适的编码（最多3个），并按置信度降序排列。"
        return prompt


    # ============================================
    # 3.5 编码完整性分析 (Layer A: 实体抽取)
    # ============================================

    async def extract_clinical_entities(
        self,
        medical_record: str
    ) -> ExtractionResult:
        """
        Layer A: 从病历中抽取临床实体
        """
        try:
            if not self.client:
                return ExtractionResult()

            system_prompt = self._build_extraction_system_prompt()
            user_prompt = f"病历文本：\n{medical_record}\n\n请抽取其中的临床实体。"

            logger.info("LLM 实体抽取开始 (Layer A)")
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1, # 抽取任务需要极低随机性
                max_tokens=2000,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)
            
            # 转换模型
            entities = ExtractionResult(
                explicit_diagnoses=[ClinicalEntity(**item) for item in result.get('explicit_diagnoses', [])],
                clinical_indicators=[ClinicalEntity(**item) for item in result.get('clinical_indicators', [])],
                procedure_mentions=[ClinicalEntity(**item) for item in result.get('procedure_mentions', [])]
            )
            
            logger.info(f"LLM 抽取完成: 诊断={len(entities.explicit_diagnoses)}, 指标={len(entities.clinical_indicators)}")
            return entities

        except Exception as e:
            logger.error(f"LLM 实体抽取失败: {str(e)}")
            return ExtractionResult()

    def _build_extraction_system_prompt(self) -> str:
        return """你是一个医疗文本结构化专家。任务是从病历中精准抽取临床实体。
需抽取三类信息：
1. explicit_diagnoses: 文中明确提到的疾病诊断（如"急性心肌梗死"）。
2. clinical_indicators: 异常的检验检查指标（如"肌钙蛋白T升高"、"EF 35%"）。
3. procedure_mentions: 提及的手术或治疗操作（如"PCI术后"、"行冠脉造影"）。

对于每个实体，必须提取原文证据（evidence），格式如下：
{
  "explicit_diagnoses": [
    {
      "text": "实体名称",
      "category": "diagnosis",
      "evidence": {
        "source": "admission_note",
        "text": "原文片段",
        "evidence_type": "explicit_statement",
        "strength": "strong"
      }
    }
  ],
  ...
}
"""

    # ============================================
    # 3.5 编码完整性分析 (Layer B: 差距分析)
    # ============================================

    async def analyze_coding_gaps(
        self,
        extraction_result: ExtractionResult,
        current_codes: Dict[str, Any],
        cc_mcc_info: Dict[str, Any]
    ) -> List[CodingGap]:
        """
        Layer B: 分析编码差距
        """
        try:
            if not self.client:
                return []

            system_prompt = self._build_gap_analysis_system_prompt()
            user_prompt = self._build_gap_analysis_user_prompt(
                extraction_result, current_codes, cc_mcc_info
            )

            logger.info("LLM 差距分析开始 (Layer B)")
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                max_tokens=2000,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)
            
            gaps = []
            for item in result.get('suggestions', []):
                # 确保 required_documentation 是列表
                if 'required_documentation' in item and isinstance(item['required_documentation'], str):
                     item['required_documentation'] = [item['required_documentation']]
                
                gaps.append(CodingGap(**item))
                
            return gaps

        except Exception as e:
            logger.error(f"LLM 差距分析失败: {str(e)}")
            return []

    def _build_gap_analysis_system_prompt(self) -> str:
        return """你是一位DRG编码专家和临床文档改进(CDI)专家。
任务：对比"已编码数据"和"临床抽取实体"，发现编码遗漏或优化空间。

重点关注：
1. CC/MCC 遗漏：临床有证据（如指标异常），但未编码为并发症。
2. 编码特异性：已编码但不具体（如"心力衰竭" vs "慢性收缩性心力衰竭"）。
3. 手术遗漏：病历提及手术但未编码。

规则：
- 仅建议有强证据支持的编码。
- 区分 action: 'add_code' (补充) 或 'needs_doc_update' (需医生澄清).
- 如果建议添加编码，risk_level 应基于证据强度。

输出 JSON 格式：
{
  "suggestions": [
    {
      "id": "gap_1",
      "category": "diagnosis",
      "subtype": "missing_code",
      "action": "add_code",
      "risk_level": "low",
      "target_name": "建议的诊断名称",
      "target_code": "建议的ICD编码(可选)",
      "confidence": 0.95,
      "evidence": [...],
      "justification_points": ["理由1", "理由2"],
      "required_documentation": []
    }
  ]
}
"""

    def _build_gap_analysis_user_prompt(
        self,
        extraction: ExtractionResult,
        current: Dict[str, Any],
        cc_mcc: Dict[str, Any]
    ) -> str:
        prompt = "【已编码数据】\n"
        prompt += f"主诊断: {current.get('primary_diagnosis', {}).get('code')} {current.get('primary_diagnosis', {}).get('name')}\n"
        prompt += "次诊断:\n"
        for d in current.get('secondary_diagnoses', []):
            prompt += f"- {d.get('code')} {d.get('name')}\n"
        prompt += "手术操作:\n"
        for p in current.get('procedures', []):
            prompt += f"- {p.get('code')} {p.get('name')}\n"
            
        prompt += "\n【临床抽取实体 (Layer A)】\n"
        prompt += "明确诊断:\n"
        for e in extraction.explicit_diagnoses:
            prompt += f"- {e.text} (证据: {e.evidence.text})\n"
        prompt += "临床指标:\n"
        for e in extraction.clinical_indicators:
            prompt += f"- {e.text} (证据: {e.evidence.text})\n"
            
        return prompt
# 全局 LLM 服务实例
llm_service = LLMService()
