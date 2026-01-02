"""
编码建议顾问服务
处理影子分组试算、编码完整性分析等高级功能
"""

from typing import List, Dict, Optional
try:
    from loguru import logger
except Exception:
    import logging
    logger = logging.getLogger(__name__)

from app.models.schemas import (
    ShadowGroupingBatchRequest,
    ShadowGroupingBatchResponse,
    ShadowGroupingResultItem,
    ShadowGroupingResultData,
    DRGGroupingResult,
    ShadowGroupingCandidate
)
from app.services.drg_grouper import DRGGrouperService
from app.services.cc_mcc_service import get_cc_mcc_service
from app.services.llm_service import llm_service
from app.models.schemas import (
    ShadowGroupingBatchRequest,
    ShadowGroupingBatchResponse,
    ShadowGroupingResultItem,
    ShadowGroupingResultData,
    DRGGroupingResult,
    ShadowGroupingCandidate,
    CodingCompletenessResponse,
    ExtractionResult,
    CodingGap
)

class AdvisorService:
    """顾问服务：负责编码优化建议与影子分组"""

    def __init__(self):
        self.grouper = DRGGrouperService()
        self.cc_mcc_service = get_cc_mcc_service()

    async def batch_shadow_grouping(self, request: ShadowGroupingBatchRequest) -> ShadowGroupingBatchResponse:
        """
        批量执行影子分组试算
        """
        logger.info(f"开始影子分组批处理: {request.request_id}, 候选方案数: {len(request.candidates)}")
        
        # 1. 计算基准分组 (Baseline)
        baseline_data = request.baseline
        try:
            baseline_result = await self.grouper.group(
                primary_diagnosis=baseline_data.primary_diagnosis,
                secondary_diagnoses=baseline_data.secondary_diagnoses,
                procedures=baseline_data.procedures,
                patient_age=baseline_data.patient_age,
                patient_gender=baseline_data.patient_gender,
                total_hospital_days=baseline_data.total_hospital_days
            )
            
            baseline_output = self._convert_to_result_data(baseline_result)
        except Exception as e:
            logger.error(f"基准分组计算失败: {str(e)}")
            # 如果基准都失败了，整个批处理无法进行
            raise Exception(f"基准分组失败: {str(e)}")

        results: List[ShadowGroupingResultItem] = []

        # 2. 遍历候选方案
        for candidate in request.candidates:
            # 检查是否符合试算条件
            if not candidate.eligible:
                results.append(ShadowGroupingResultItem(
                    id=candidate.id,
                    status='skipped',
                    drg_change_type='no_change',
                    notes=["跳过：不符合试算条件"]
                ))
                continue
                
            try:
                # 构造新的诊断列表
                new_sdx = self._apply_diagnosis_changes(
                    baseline_data.secondary_diagnoses,
                    candidate
                )
                
                # 构造新的手术列表
                new_procedures = baseline_data.procedures + candidate.add_procedures
                
                # 执行分组
                candidate_result = await self.grouper.group(
                    primary_diagnosis=baseline_data.primary_diagnosis,
                    secondary_diagnoses=new_sdx,
                    procedures=new_procedures,
                    patient_age=baseline_data.patient_age,
                    patient_gender=baseline_data.patient_gender,
                    total_hospital_days=baseline_data.total_hospital_days
                )
                
                candidate_output = self._convert_to_result_data(candidate_result)
                
                # 分析差异
                diff_analysis = self._analyze_diff(baseline_output, candidate_output)
                
                # 生成结果项
                result_item = ShadowGroupingResultItem(
                    id=candidate.id,
                    status='computed',
                    with_candidate=candidate_output,
                    drg_change_type=diff_analysis['change_type'],
                    rw_delta=diff_analysis['rw_delta'],
                    impact_description=diff_analysis['impact_desc'],
                    notes=diff_analysis['notes']
                )
                results.append(result_item)
                
            except Exception as e:
                logger.error(f"候选方案 {candidate.id} 试算失败: {str(e)}")
                results.append(ShadowGroupingResultItem(
                    id=candidate.id,
                    status='error',
                    drg_change_type='error',
                    error_message=str(e)
                ))

        return ShadowGroupingBatchResponse(
            baseline=baseline_output,
            results=results
        )

    def _apply_diagnosis_changes(self, original_sdx: List[str], candidate: ShadowGroupingCandidate) -> List[str]:
        """应用诊断变更（新增与替换）"""
        current_sdx = original_sdx.copy()
        
        # 1. 处理替换
        for replace_item in candidate.replace_secondary_diagnoses:
            if replace_item.from_code and replace_item.from_code in current_sdx:
                current_sdx.remove(replace_item.from_code)
            current_sdx.append(replace_item.to_code)
            
        # 2. 处理新增
        current_sdx.extend(candidate.add_secondary_diagnoses)
        
        # 去重
        return list(set(current_sdx))

    def _convert_to_result_data(self, grouping_result: dict) -> ShadowGroupingResultData:
        """转换分组结果格式"""
        # 注意：兼容 DRGGrouperService 返回的 dict 结构
        # 它可能返回 {'drg_code': ..., 'drg_name': ..., 'weight': ...}
        return ShadowGroupingResultData(
            drg=grouping_result.get('drg_code', 'Unknow'),
            drg_name=grouping_result.get('drg_name', ''),
            adrg=grouping_result.get('adrg_code'),
            rw=grouping_result.get('weight')
        )

    def _analyze_diff(self, baseline: ShadowGroupingResultData, candidate: ShadowGroupingResultData) -> dict:
        """分析分组差异"""
        notes = []
        change_type = 'no_change'
        impact_desc = "分组无变化"
        rw_delta = None

        # 计算 RW 差异 (虽然 RW 是可选的)
        if baseline.rw is not None and candidate.rw is not None:
            rw_delta = candidate.rw - baseline.rw
            
        # 判断 DRG 是否变化
        if baseline.drg != candidate.drg:
            change_type = 'drg_changed'
            impact_desc = f"DRG 变更为 {candidate.drg}"
            
            # 尝试通过名称推断升级方向 (简易逻辑)
            # 例如: "冠状动脉支架植入" -> "冠状动脉支架植入，伴并发症"
            b_name = baseline.drg_name or ""
            c_name = candidate.drg_name or ""
            
            has_cc_kw = "伴并发症" in c_name or "伴CC" in c_name or "伴合并症" in c_name
            has_mcc_kw = "伴严重的" in c_name or "伴严重并发症" in c_name or "伴MCC" in c_name or "伴严重合并症" in c_name
            
            base_has_cc = "伴并发症" in b_name or "伴CC" in b_name or "伴合并症" in b_name
            base_has_mcc = "伴严重的" in b_name or "伴严重并发症" in b_name or "伴MCC" in b_name or "伴严重合并症" in b_name
            
            if has_mcc_kw and not base_has_mcc:
                change_type = 'cc_to_mcc'
                impact_desc = "升级：分入伴严重并发症或合并症组 (MCC)"
                notes.append(f"DRG {baseline.drg} -> {candidate.drg}")
            elif has_cc_kw and not base_has_cc and not base_has_mcc:
                # 只有当基准既不是 CC 也不是 MCC 时，才算升级到 CC
                # 否则可能是 MCC 降级到 CC，或者 CC 组内变动
                change_type = 'base_to_cc'
                impact_desc = "升级：分入伴并发症或合并症组 (CC)"
                notes.append(f"DRG {baseline.drg} -> {candidate.drg}")
            else:
                # 其他类型的 DRG 变化
                notes.append(f"DRG 变更: {baseline.drg} ({b_name}) -> {candidate.drg} ({c_name})")

        return {
            "change_type": change_type,
            "impact_desc": impact_desc,
            "rw_delta": rw_delta,
            "notes": notes
        }


    async def analyze_coding_completeness(
        self,
        medical_record: str,
        current_data: Dict[str, any]
    ) -> CodingCompletenessResponse:
        """
        执行编码完整性分析 (Layer A -> Layer B)
        """
        # 1. Layer A: 抽取临床实体
        extraction_result = await llm_service.extract_clinical_entities(medical_record)
        
        # 2. 准备上下文信息 (CC/MCC 标注)
        # 为 GAP 分析提供辅助信息，例如抽取的诊断是否属于 CC/MCC
        cc_mcc_info = {}
        for entity in extraction_result.explicit_diagnoses:
            # 尝试模糊匹配或清洗名称后查询 (此处简化处理)
            # 实际生产中可能需要先将实体名称映射为标准编码
            pass

        # 3. Layer B: 差距分析
        suggestions = await llm_service.analyze_coding_gaps(
            extraction_result,
            current_data,
            cc_mcc_info
        )
        
        # 4. (可选) 自动发起影子分组试算
        # 如果建议包含明确的 ICD 编码 (target_code)，可以自动计算 diff
        # 这步作为未来优化的扩展点 (Layer C)
        
        return CodingCompletenessResponse(
            structure_extraction=extraction_result,
            suggestions=suggestions
        )
