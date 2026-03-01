/**
 * useWorkstationBridge.ts
 * 桥接 composable：将工作站的 MedicalRecord 格式转换为 frontpage-demo 的 DemoCaseLike 格式
 * 这样可以复用 useMedicalTextExtraction 和 useDRGGrouping composables
 */
import { ref, computed, watch, type Ref } from 'vue'
import type { MedicalRecord } from './mockData'
import { useMedicalTextExtraction, type DemoCaseLike } from '../demo/frontpage/composables/useMedicalTextExtraction'
import { useDRGGrouping } from '../demo/frontpage/composables/useDRGGrouping'

export function useWorkstationBridge(selectedRecord: Ref<MedicalRecord | null>) {
    // ===== 核心状态：DemoCaseLike ref =====
    const demoCase = ref<DemoCaseLike | null>(null)

    // ===== MedicalRecord → DemoCaseLike 格式转换 =====
    function buildMedicalText(record: MedicalRecord): string {
        const parts: string[] = []
        if (record.admissionNote) parts.push('【入院记录】\n' + record.admissionNote)
        if (record.progressNote) parts.push('【病程记录】\n' + record.progressNote)
        if (record.surgeryNote) parts.push('【手术记录】\n' + record.surgeryNote)
        if (record.dischargeNote) parts.push('【出院记录】\n' + record.dischargeNote)
        return parts.join('\n\n')
    }

    // 当选中的病历变化时，重置 demoCase
    watch(selectedRecord, (newRecord) => {
        if (newRecord) {
            demoCase.value = {
                case_id: newRecord.visitId,
                description: `${newRecord.patientName} - ${newRecord.deptName}`,
                medical_text: buildMedicalText(newRecord),
                frontpage: null,
                insurance_claim: null,
            }
        } else {
            demoCase.value = null
        }
    }, { immediate: true })

    // ===== 复用 useMedicalTextExtraction =====
    const { extracting, extractStructuredData } = useMedicalTextExtraction({
        demoCase,
        onStartExtract: () => {
            console.log('[workstation-bridge] AI 提取开始')
        },
        onExtracted: () => {
            console.log('[workstation-bridge] AI 提取完成', demoCase.value?.frontpage)
        },
    })

    // ===== 复用 useDRGGrouping =====
    const drg = useDRGGrouping()

    // ===== 透传的计算属性 =====
    const frontpage = computed(() => demoCase.value?.frontpage || null)
    const hasMedicalText = computed(() => !!demoCase.value?.medical_text)
    const hasFrontpage = computed(() => !!frontpage.value)

    // 从 frontpage 中提取诊断/手术编码（DRGGroupingTab 需要）
    const mainDiagnosisCode = computed(() =>
        frontpage.value?.primary_diagnosis_code ||
        frontpage.value?.diagnoses?.discharge_main_icd || ''
    )
    const mainDiagnosisText = computed(() =>
        frontpage.value?.primary_diagnosis_name ||
        frontpage.value?.diagnoses?.discharge_main_diagnosis_text || ''
    )
    const mainProcedureCode = computed(() =>
        frontpage.value?.main_procedure_code ||
        frontpage.value?.procedures?.main_procedure_code ||
        frontpage.value?.procedures?.main?.code || ''
    )
    const mainProcedureName = computed(() =>
        frontpage.value?.main_procedure_name ||
        frontpage.value?.procedures?.main_procedure_text ||
        frontpage.value?.procedures?.main?.name || ''
    )

    // ===== DRG 分组 =====
    async function performDRGGrouping() {
        if (!demoCase.value?.case_id) return
        const totalCost = frontpage.value?.costs?.total_cost ||
            demoCase.value?.insurance_claim?.total_cost
        await drg.performDRGGrouping(demoCase.value.case_id, totalCost)
    }

    function openOptimizationDrawer() {
        if (!demoCase.value?.case_id) return
        drg.openOptimizationDrawer(demoCase.value.case_id)
    }

    function handleSuggestion(id: number, action: 'accept' | 'reject') {
        if (!demoCase.value?.case_id) return
        drg.handleSuggestion(id, action, demoCase.value.case_id)
    }

    return {
        // 首页提取
        demoCase,
        extracting,
        extractStructuredData,
        frontpage,
        hasMedicalText,
        hasFrontpage,

        // DRG 分组
        drgLoading: drg.drgLoading,
        drgResult: drg.drgResult,
        performDRGGrouping,
        suggestionDrawerVisible: drg.suggestionDrawerVisible,
        suggestionsLoading: drg.suggestionsLoading,
        suggestions: drg.suggestions,
        openOptimizationDrawer,
        handleSuggestion,
        getSuggestionTitle: drg.getSuggestionTitle,

        // 诊断/手术编码（DRGGroupingTab 需要）
        mainDiagnosisCode,
        mainDiagnosisText,
        mainProcedureCode,
        mainProcedureName,
    }
}
