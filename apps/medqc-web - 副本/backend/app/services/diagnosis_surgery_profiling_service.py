from __future__ import annotations

"""
疾病诊断和手术操作画像服务 (F13)

功能：
1. 诊断发生发展时间轴 - 聚合全病历诊断实体，构建时间轴
2. 手术操作闭环验证 - 对比计划与执行，验证状态
3. 首页书写差异分析 - 校验首页与病历画像一致性
"""

from typing import Any, Dict, List, Literal, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
import logging
import json

from ..core.settings import get_settings
from ..core.http import safe_post_json

logger = logging.getLogger(__name__)


# ============================================================================
# 数据结构
# ============================================================================

@dataclass
class TimelineEvent:
    """时间轴事件"""
    time: str
    event: str
    source: str
    event_type: str = ""  # admission, exam, surgery, complication, discharge


@dataclass
class DiagnosisTimeline:
    """诊断时间轴"""
    diagnosis_name: str
    first_mention_time: Optional[str] = None
    first_mention_source: Optional[str] = None
    status: Literal["suspected", "confirmed", "ruled_out"] = "suspected"
    icd_code: Optional[str] = None
    timeline_events: List[TimelineEvent] = field(default_factory=list)


@dataclass
class SurgeryVerification:
    """手术闭环验证"""
    surgery_name: str
    plan_source: Optional[str] = None
    plan_time: Optional[str] = None
    execution_source: Optional[str] = None
    execution_time: Optional[str] = None
    verification_status: Literal["verified", "planned_only", "executed_only"] = "verified"
    icd9_code: Optional[str] = None


@dataclass
class Discrepancy:
    """首页差异"""
    type: Literal["missing_in_frontpage", "not_supported_by_record", "inconsistent"]
    item_category: Literal["diagnosis", "procedure"]
    item_name: str
    suggestion: str
    severity: Literal["warning", "error"] = "warning"


@dataclass
class MedicalProfile:
    """医疗画像"""
    diagnosis_timeline: List[DiagnosisTimeline] = field(default_factory=list)
    surgery_verification: List[SurgeryVerification] = field(default_factory=list)
    discrepancies: List[Discrepancy] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "diagnosis_timeline": [asdict(d) for d in self.diagnosis_timeline],
            "surgery_verification": [asdict(s) for s in self.surgery_verification],
            "discrepancies": [asdict(d) for d in self.discrepancies],
        }


# ============================================================================
# Prompt 模板
# ============================================================================

DIAGNOSIS_TIMELINE_PROMPT = """你是一位专业的病案分析专家。请从以下病历中提取诊断时间轴信息。

【病历内容】
{medical_text}

【任务】
提取所有出现的诊断，包括：
1. 诊断名称
2. 首次出现时间
3. 首次出现的文书来源
4. 状态（suspected=疑诊, confirmed=确诊, ruled_out=排除）
5. 关键时间节点

【输出格式】
```json
{{
  "diagnoses": [
    {{
      "diagnosis_name": "急性阑尾炎",
      "first_mention_time": "2023-10-01 09:00",
      "first_mention_source": "入院记录",
      "status": "confirmed",
      "events": [
        {{"time": "2023-10-01 09:00", "event": "入院初步诊断", "source": "入院记录"}},
        {{"time": "2023-10-01 10:30", "event": "B超确诊", "source": "检查报告"}}
      ]
    }}
  ]
}}
```

直接输出 JSON："""


SURGERY_VERIFICATION_PROMPT = """你是一位专业的病案分析专家。请从以下病历中提取手术计划与执行信息，进行闭环验证。

【病历内容】
{medical_text}

【任务】
1. 提取所有手术计划（来源：术前小结、手术审批单、医嘱）
2. 提取所有手术执行记录（来源：手术记录、麻醉记录）
3. 进行匹配验证：
   - verified：有计划且有执行记录
   - planned_only：有计划但无执行记录（可能取消）
   - executed_only：有执行但无计划记录（质控缺陷）

【输出格式】
```json
{{
  "surgeries": [
    {{
      "surgery_name": "腹腔镜下阑尾切除术",
      "plan_source": "术前小结",
      "plan_time": "2023-10-01",
      "execution_source": "手术记录",
      "execution_time": "2023-10-01 14:00",
      "verification_status": "verified"
    }}
  ]
}}
```

直接输出 JSON："""


class DiagnosisSurgeryProfilingService:
    """疾病诊断和手术操作画像服务"""

    def __init__(self, llm_config: Optional[Dict[str, Any]] = None) -> None:
        if llm_config:
            self.api_endpoint = llm_config.get("api_endpoint")
            self.api_key = llm_config.get("api_key")
            self.model = llm_config.get("model", "qwen-max")
        else:
            s = get_settings()
            self.api_endpoint = str(s.LLM_API_ENDPOINT) if s.LLM_API_ENDPOINT else None
            self.api_key = s.LLM_API_KEY
            self.model = s.LLM_MODEL

        self._use_llm = bool(self.api_endpoint and self.api_key)
        logger.info(f"DiagnosisSurgeryProfilingService 初始化: use_llm={self._use_llm}")

    async def analyze_medical_profile(
        self,
        medical_text: str,
        frontpage_diagnoses: Optional[List[str]] = None,
        frontpage_procedures: Optional[List[str]] = None,
    ) -> MedicalProfile:
        """
        分析病历生成医疗画像
        
        Args:
            medical_text: 病历全文
            frontpage_diagnoses: 首页已填诊断列表
            frontpage_procedures: 首页已填手术列表
            
        Returns:
            MedicalProfile 包含时间轴、手术验证和差异分析
        """
        profile = MedicalProfile()
        
        if not self._use_llm or not medical_text:
            logger.warning("LLM 未配置或病历为空，返回空画像")
            return profile
        
        # 1. 提取诊断时间轴
        try:
            profile.diagnosis_timeline = await self._extract_diagnosis_timeline(medical_text)
            logger.info(f"诊断时间轴提取完成: {len(profile.diagnosis_timeline)} 个诊断")
        except Exception as e:
            logger.error(f"诊断时间轴提取失败: {e}")
        
        # 2. 手术闭环验证
        try:
            profile.surgery_verification = await self._verify_surgeries(medical_text)
            logger.info(f"手术验证完成: {len(profile.surgery_verification)} 个手术")
        except Exception as e:
            logger.error(f"手术验证失败: {e}")
        
        # 3. 差异分析
        try:
            profile.discrepancies = self._analyze_discrepancies(
                profile, frontpage_diagnoses, frontpage_procedures
            )
            logger.info(f"差异分析完成: {len(profile.discrepancies)} 个问题")
        except Exception as e:
            logger.error(f"差异分析失败: {e}")
        
        return profile

    async def _extract_diagnosis_timeline(self, medical_text: str) -> List[DiagnosisTimeline]:
        """提取诊断时间轴"""
        prompt = DIAGNOSIS_TIMELINE_PROMPT.format(medical_text=medical_text)
        response = await self._call_llm(prompt)
        result = self._parse_json(response)
        
        if not result or "diagnoses" not in result:
            return []
        
        timelines = []
        for diag in result["diagnoses"]:
            events = [
                TimelineEvent(
                    time=e.get("time", ""),
                    event=e.get("event", ""),
                    source=e.get("source", ""),
                    event_type=e.get("event_type", "")
                )
                for e in diag.get("events", [])
            ]
            
            timelines.append(DiagnosisTimeline(
                diagnosis_name=diag.get("diagnosis_name", ""),
                first_mention_time=diag.get("first_mention_time"),
                first_mention_source=diag.get("first_mention_source"),
                status=diag.get("status", "suspected"),
                timeline_events=events
            ))
        
        return timelines

    async def _verify_surgeries(self, medical_text: str) -> List[SurgeryVerification]:
        """手术闭环验证"""
        prompt = SURGERY_VERIFICATION_PROMPT.format(medical_text=medical_text)
        response = await self._call_llm(prompt)
        result = self._parse_json(response)
        
        if not result or "surgeries" not in result:
            return []
        
        verifications = []
        for surg in result["surgeries"]:
            verifications.append(SurgeryVerification(
                surgery_name=surg.get("surgery_name", ""),
                plan_source=surg.get("plan_source"),
                plan_time=surg.get("plan_time"),
                execution_source=surg.get("execution_source"),
                execution_time=surg.get("execution_time"),
                verification_status=surg.get("verification_status", "verified")
            ))
        
        return verifications

    def _analyze_discrepancies(
        self,
        profile: MedicalProfile,
        frontpage_diagnoses: Optional[List[str]],
        frontpage_procedures: Optional[List[str]],
    ) -> List[Discrepancy]:
        """首页差异分析"""
        discrepancies = []
        
        # 诊断差异
        profile_diag_names = {d.diagnosis_name.lower().strip() for d in profile.diagnosis_timeline}
        frontpage_diag_names = {d.lower().strip() for d in (frontpage_diagnoses or [])}
        
        # 病历中有但首页未填
        for diag in profile.diagnosis_timeline:
            diag_name = diag.diagnosis_name.lower().strip()
            if diag_name and diag_name not in frontpage_diag_names:
                if diag.status == "confirmed":
                    discrepancies.append(Discrepancy(
                        type="missing_in_frontpage",
                        item_category="diagnosis",
                        item_name=diag.diagnosis_name,
                        suggestion=f"建议补充诊断：{diag.diagnosis_name}（来源：{diag.first_mention_source}）",
                        severity="warning"
                    ))
        
        # 首页填写但病历无据
        for diag in (frontpage_diagnoses or []):
            if diag.lower().strip() not in profile_diag_names:
                discrepancies.append(Discrepancy(
                    type="not_supported_by_record",
                    item_category="diagnosis",
                    item_name=diag,
                    suggestion=f"首页诊断'{diag}'在病历中未找到支持依据，请核实",
                    severity="error"
                ))
        
        # 手术差异
        profile_proc_names = {s.surgery_name.lower().strip() for s in profile.surgery_verification}
        frontpage_proc_names = {p.lower().strip() for p in (frontpage_procedures or [])}
        
        # 病历中有但首页未填
        for surg in profile.surgery_verification:
            surg_name = surg.surgery_name.lower().strip()
            if surg.verification_status == "verified" and surg_name not in frontpage_proc_names:
                discrepancies.append(Discrepancy(
                    type="missing_in_frontpage",
                    item_category="procedure",
                    item_name=surg.surgery_name,
                    suggestion=f"建议补充手术：{surg.surgery_name}（执行时间：{surg.execution_time}）",
                    severity="warning"
                ))
        
        # 计划未执行提醒
        for surg in profile.surgery_verification:
            if surg.verification_status == "planned_only":
                discrepancies.append(Discrepancy(
                    type="inconsistent",
                    item_category="procedure",
                    item_name=surg.surgery_name,
                    suggestion=f"手术'{surg.surgery_name}'有计划但未找到执行记录，请确认是否取消",
                    severity="warning"
                ))
            elif surg.verification_status == "executed_only":
                discrepancies.append(Discrepancy(
                    type="inconsistent",
                    item_category="procedure",
                    item_name=surg.surgery_name,
                    suggestion=f"手术'{surg.surgery_name}'有执行但未找到计划/审批记录，属于质控缺陷",
                    severity="error"
                ))
        
        return discrepancies

    async def _call_llm(self, prompt: str) -> str:
        """调用 LLM"""
        if not self._use_llm:
            return ""
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "你是专业的病案分析专家。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 4000,
            "stream": False,
        }
        
        try:
            # 确保 endpoint 以 /v1 结尾（兼容不同配置方式）
            base = self.api_endpoint.rstrip("/")
            if not base.endswith("/v1"):
                base = f"{base}/v1"
            result = await safe_post_json(
                url=f"{base}/chat/completions",
                headers=headers,
                payload=payload,
                timeout_seconds=60,
            )
            choices = result.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "")
            return ""
        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            raise

    def _parse_json(self, response: str) -> Optional[Dict[str, Any]]:
        """解析 JSON 响应"""
        if not response:
            return None
        
        import re
        json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_start = response.find('{')
            json_end = response.rfind('}')
            if json_start != -1 and json_end != -1:
                json_str = response[json_start:json_end + 1]
            else:
                return None
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            return None


# 单例
_profiling_service: Optional[DiagnosisSurgeryProfilingService] = None


def get_profiling_service() -> DiagnosisSurgeryProfilingService:
    """获取画像服务单例"""
    global _profiling_service
    if _profiling_service is None:
        _profiling_service = DiagnosisSurgeryProfilingService()
    return _profiling_service
