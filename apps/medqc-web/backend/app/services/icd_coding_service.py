"""
ICD 编码推荐服务

功能：
- 根据诊断/手术名称推荐 ICD-10/ICD-9-CM-3 编码
- 支持 LLM 智能推荐和关键词匹配
- 复用 DRG/DIP 模块的编码库
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import logging
import json

from ..core.settings import get_settings
from ..core.http import safe_post_json
from .llm_observability import observe_llm_http_attempt

logger = logging.getLogger(__name__)


# 常用 ICD-10 诊断编码 Mock 数据（用于 demo 和 LLM 参考）
COMMON_ICD10_CODES = [
    {"code": "I21.001", "name": "急性前壁ST段抬高型心肌梗死", "category": "循环系统疾病"},
    {"code": "I21.101", "name": "急性下壁ST段抬高型心肌梗死", "category": "循环系统疾病"},
    {"code": "I21.901", "name": "急性心肌梗死", "category": "循环系统疾病"},
    {"code": "I10.x01", "name": "高血压3级（极高危）", "category": "循环系统疾病"},
    {"code": "I50.001", "name": "心力衰竭", "category": "循环系统疾病"},
    {"code": "E11.901", "name": "2型糖尿病", "category": "内分泌疾病"},
    {"code": "J18.901", "name": "肺炎", "category": "呼吸系统疾病"},
    {"code": "J44.101", "name": "慢性阻塞性肺疾病伴急性加重", "category": "呼吸系统疾病"},
    {"code": "K35.901", "name": "急性阑尾炎", "category": "消化系统疾病"},
    {"code": "N18.500", "name": "慢性肾脏病5期", "category": "泌尿系统疾病"},
    {"code": "C34.901", "name": "肺恶性肿瘤", "category": "肿瘤"},
    {"code": "K80.101", "name": "胆囊结石伴急性胆囊炎", "category": "消化系统疾病"},
]

# 常用 ICD-9-CM-3 手术编码 Mock 数据
COMMON_ICD9_PROCEDURES = [
    {"code": "36.0601", "name": "经皮冠状动脉球囊扩张术(PTCA)", "category": "心血管手术"},
    {"code": "36.0701", "name": "经皮冠状动脉支架植入术(PCI)", "category": "心血管手术"},
    {"code": "51.2101", "name": "腹腔镜胆囊切除术", "category": "消化系统手术"},
    {"code": "47.0900", "name": "阑尾切除术", "category": "消化系统手术"},
    {"code": "81.5400", "name": "全髋关节置换术", "category": "骨科手术"},
    {"code": "81.5100", "name": "全膝关节置换术", "category": "骨科手术"},
    {"code": "39.9501", "name": "血液透析", "category": "治疗性操作"},
    {"code": "32.4100", "name": "肺叶切除术", "category": "胸外科手术"},
]


ICD_SUGGEST_PROMPT = """你是一位专业的病案编码专家。请根据以下诊断/手术名称，推荐最合适的 ICD 编码。

【待编码内容】
类型：{category}
名称：{name}

【编码库参考】
{code_reference}

【任务】
从参考编码库或你的专业知识中，推荐 1-3 个最匹配的编码。

【输出格式】
```json
{{
  "suggestions": [
    {{"code": "编码", "name": "标准名称", "confidence": 0.95, "match_reason": "匹配理由"}}
  ]
}}
```

直接输出 JSON："""


class ICDCodingService:
    """ICD 编码推荐服务"""

    def __init__(self, llm_config: Optional[Dict[str, Any]] = None) -> None:
        if llm_config:
            self.api_endpoint = llm_config.get("api_endpoint")
            self.api_key = llm_config.get("api_key")
            self.model = llm_config.get("model", "qwen-max")
            self.provider_code = str(llm_config.get("provider_code") or "unknown")
        else:
            s = get_settings()
            self.api_endpoint = str(s.LLM_API_ENDPOINT) if s.LLM_API_ENDPOINT else None
            self.api_key = s.LLM_API_KEY
            self.model = s.LLM_MODEL
            self.provider_code = str(
                getattr(s, "LLM_DEFAULT_PROVIDER", None) or "unknown"
            )

        self._use_llm = bool(self.api_endpoint and self.api_key)
        logger.info(f"ICDCodingService 初始化: use_llm={self._use_llm}")

    async def suggest_diagnosis_codes(
        self, diagnosis_name: str, top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        根据诊断名称推荐 ICD-10 编码
        
        Args:
            diagnosis_name: 诊断名称
            top_k: 返回 top K 个推荐
            
        Returns:
            推荐列表 [{"code": "I21.001", "name": "...", "confidence": 0.95}]
        """
        if not diagnosis_name:
            return []

        # 首先尝试关键词匹配
        keyword_matches = self._keyword_match(diagnosis_name, COMMON_ICD10_CODES)
        if keyword_matches:
            return keyword_matches[:top_k]

        # 如果没有匹配且 LLM 可用，使用 LLM 推荐
        if self._use_llm:
            try:
                return await self._llm_suggest(diagnosis_name, "diagnosis", top_k)
            except Exception as e:
                logger.error(f"LLM 编码推荐失败: {e}")

        # 回退到空结果
        return []

    async def suggest_procedure_codes(
        self, procedure_name: str, top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        根据手术名称推荐 ICD-9-CM-3 编码
        
        Args:
            procedure_name: 手术名称
            top_k: 返回 top K 个推荐
            
        Returns:
            推荐列表 [{"code": "36.0701", "name": "...", "confidence": 0.95}]
        """
        if not procedure_name:
            return []

        # 首先尝试关键词匹配
        keyword_matches = self._keyword_match(procedure_name, COMMON_ICD9_PROCEDURES)
        if keyword_matches:
            return keyword_matches[:top_k]

        # 如果没有匹配且 LLM 可用，使用 LLM 推荐
        if self._use_llm:
            try:
                return await self._llm_suggest(procedure_name, "procedure", top_k)
            except Exception as e:
                logger.error(f"LLM 编码推荐失败: {e}")

        return []

    def _keyword_match(
        self, name: str, code_pool: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """关键词匹配编码"""
        results = []
        name_lower = name.lower()

        for item in code_pool:
            item_name = item.get("name", "").lower()
            # 计算匹配度
            if name_lower in item_name or item_name in name_lower:
                confidence = 0.95 if name_lower == item_name else 0.85
                results.append({
                    "code": item["code"],
                    "name": item["name"],
                    "confidence": confidence,
                    "match_type": "keyword"
                })
            else:
                # 检查关键词重叠
                name_keywords = set(name_lower.replace("、", " ").split())
                item_keywords = set(item_name.replace("、", " ").split())
                overlap = name_keywords & item_keywords
                if overlap:
                    confidence = min(0.8, 0.3 + 0.2 * len(overlap))
                    results.append({
                        "code": item["code"],
                        "name": item["name"],
                        "confidence": confidence,
                        "match_type": "keyword_overlap"
                    })

        # 按置信度排序
        results.sort(key=lambda x: x["confidence"], reverse=True)
        return results

    async def _llm_suggest(
        self, name: str, category: str, top_k: int
    ) -> List[Dict[str, Any]]:
        """使用 LLM 推荐编码"""
        code_pool = COMMON_ICD10_CODES if category == "diagnosis" else COMMON_ICD9_PROCEDURES
        code_reference = "\n".join(
            f"- {c['code']}: {c['name']}" for c in code_pool
        )

        prompt = ICD_SUGGEST_PROMPT.format(
            category="诊断" if category == "diagnosis" else "手术/操作",
            name=name,
            code_reference=code_reference
        )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "你是专业的病案编码专家。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 1000,
            "stream": False,
            "enable_thinking": False,
        }

        result = await observe_llm_http_attempt(
            lambda: safe_post_json(
                url=f"{self.api_endpoint}/chat/completions",
                headers=headers,
                payload=payload,
                timeout_seconds=30,
            ),
            provider_code=self.provider_code,
            model=self.model,
            business_scene="icd_coding",
            executor_key="icd_coding",
        )

        choices = result.get("choices", [])
        if not choices:
            return []

        content = choices[0].get("message", {}).get("content", "")
        return self._parse_suggestions(content, top_k)

    def _parse_suggestions(self, content: str, top_k: int) -> List[Dict[str, Any]]:
        """解析 LLM 返回的编码推荐"""
        import re
        json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_start = content.find('{')
            json_end = content.rfind('}')
            if json_start != -1 and json_end != -1:
                json_str = content[json_start:json_end + 1]
            else:
                return []

        try:
            data = json.loads(json_str)
            suggestions = data.get("suggestions", [])
            return suggestions[:top_k]
        except json.JSONDecodeError:
            return []


# 单例
_icd_service: Optional[ICDCodingService] = None


def get_icd_coding_service() -> ICDCodingService:
    """获取 ICD 编码服务单例"""
    global _icd_service
    if _icd_service is None:
        _icd_service = ICDCodingService()
    return _icd_service
