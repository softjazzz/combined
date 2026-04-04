import { ref, computed, type Ref } from 'vue'
import { message } from 'ant-design-vue'
import { useRouter, useRoute } from 'vue-router'
import { drgApi } from '@/api/drg'
import type { CaseFrontPage, DRGGroupingResult, CodingSuggestionItem } from '@/types/drg'
import type { FeeMonitoringRow, ListTabKey, GroupingStatus, ActiveDrawerTab } from '@/types/drg-fee'
import {
  getMockFeeDetails,
  type FeeComposition,
  type FeeTrendPoint,
  type HighValueMaterial,
  type FeeWarningRecord,
} from '@/data/drg/mock-fee-monitoring'
import {
  calculateCostRate,
  calculateProfitMargin,
  formatCurrency,
  formatDateTime,
} from '@/utils/drg'
import { useDrgDatasetStore } from '@/stores/drgDataset'
import { mapCaseRecordsToFeeMonitoringRows } from '@/utils/drg-aggregation'

export function useFeeMonitoring() {
  const router = useRouter()
  const route = useRoute()

  // 状态
  const loading = ref(false)
  const rows = ref<FeeMonitoringRow[]>([])
  const keyword = ref('')
  const activeListTab = ref<ListTabKey>('ungrouped')

  // 抽屉状态
  const drawerOpen = ref(false)
  const selectedRow = ref<FeeMonitoringRow | null>(null)
  const activeDrawerTab = ref<ActiveDrawerTab>('basic')
  const drawerLoading = ref(false)

  // 费用详情数据
  const feeComposition = ref<FeeComposition | null>(null)
  const feeTrend = ref<FeeTrendPoint[]>([])
  const highValueMaterials = ref<HighValueMaterial[]>([])
  const feeWarningRecords = ref<FeeWarningRecord[]>([])

  // 辅助计算函数
  const inferDepartment = (fp: CaseFrontPage): string => {
    const d = `${fp.primary_diagnosis_name || ''}`
    if (d.includes('心') || d.includes('冠状') || d.includes('心肌')) return '心内科'
    if (d.includes('肺') || d.includes('呼吸')) return '呼吸内科'
    if (d.includes('脑') || d.includes('梗')) return '神经内科'
    if (d.includes('骨') || d.includes('骨折')) return '骨科'
    return '综合内科'
  }

  const buildUngroupedReason = (fp: CaseFrontPage, groupingStatus: GroupingStatus): string => {
    if (groupingStatus !== 'ungrouped') return ''
    if (fp.coding_status !== 'completed') return '编码未完成，无法预入组'
    return '主要诊断与主要手术及操作不一致（演示）'
  }

  const buildFixSuggestion = (
    fp: CaseFrontPage,
    groupingStatus: GroupingStatus,
    suggestions: CodingSuggestionItem[],
  ): string => {
    if (groupingStatus === 'ungrouped') {
      return '建议核对主要诊断/主要手术（主手术未填写或选择错误常见导致未入组），完善并发症标记后重试入组。'
    }
    const pending = suggestions.filter((s) => s.status === 'pending')
    if (pending.length === 0) return ''
    return pending
      .slice(0, 2)
      .map((s, idx) => `${idx + 1}. ${s.message}`)
      .join('\n')
  }

  const inferIsBaseGroup = (
    costRate: number | null,
    groupingStatus: GroupingStatus,
  ): boolean | null => {
    if (groupingStatus !== 'grouped') return null
    if (typeof costRate !== 'number') return null
    return costRate >= 80 && costRate < 120
  }

  const inferSettlementType = (
    costRate: number | null,
    profitMargin: number | null,
    groupingStatus: GroupingStatus,
  ): string => {
    if (groupingStatus !== 'grouped') return '未入组'
    if (typeof costRate !== 'number') return '-'
    if (costRate >= 120) return '费用极高'
    if (costRate < 50) return '费用极低'
    if (typeof profitMargin === 'number' && profitMargin < 0) return '亏损'
    return '正常倍率'
  }

  // 加载数据
  const loadData = async () => {
    loading.value = true
    try {
      // 优先从上传数据 Store 映射，绕过三路 API 拼装
      const datasetStore = useDrgDatasetStore()
      if (datasetStore.hasUploadedData) {
        rows.value = mapCaseRecordsToFeeMonitoringRows(datasetStore.records)
        return
      }

      // 无上传数据 → 走原有三路 API 拼装逻辑
      const caseFrontPages = await drgApi.getCaseFrontPages()

      const enriched = await Promise.all(
        caseFrontPages.map(async (fp) => {
          const actualCost = typeof fp.total_cost === 'number' ? fp.total_cost : 0

          let grouping: DRGGroupingResult | null = null
          let baselinePayment: number | null = null
          let costRate: number | null = null
          let profitMargin: number | null = null
          let groupingStatus: GroupingStatus = 'ungrouped'

          if (fp.coding_status === 'completed') {
            try {
              grouping = await drgApi.predictDRGGrouping({
                admission_id: fp.admission_id,
                region: 'sichuan',
              })
              baselinePayment = grouping?.baseline_payment ?? null
              costRate = calculateCostRate(baselinePayment, actualCost)
              profitMargin = calculateProfitMargin(baselinePayment, actualCost)
              groupingStatus = 'grouped'
            } catch {
              groupingStatus = 'ungrouped'
            }
          }

          const suggestionRes = await drgApi.getCodingSuggestions({
            admission_id: fp.admission_id,
            limit: 20,
          })

          const department = inferDepartment(fp)
          const admitAt = fp.created_at
          const dischargeAt = fp.updated_at
          const selfPay = Math.max(0, Math.round(actualCost * 0.01 * 100) / 100)
          const isBaseGroup = inferIsBaseGroup(costRate, groupingStatus)
          const settlementType = inferSettlementType(costRate, profitMargin, groupingStatus)
          const settlementMethod = groupingStatus === 'grouped' ? '按DRG付费' : '-'
          const ungroupedReason = buildUngroupedReason(fp, groupingStatus)
          const fixSuggestion = buildFixSuggestion(fp, groupingStatus, suggestionRes.suggestions)

          return {
            ...(fp as any),
            grouping,
            groupingStatus,
            baselinePayment,
            actualCost,
            costRate,
            profitMargin,
            suggestions: suggestionRes.suggestions,
            department,
            admitAt,
            dischargeAt,
            selfPay,
            isBaseGroup,
            settlementType,
            settlementMethod,
            ungroupedReason,
            fixSuggestion,
          } as FeeMonitoringRow
        }),
      )

      rows.value = enriched
    } catch (error) {
      console.error('加载付费监测数据失败:', error)
      message.error('加载失败')
    } finally {
      loading.value = false
    }
  }

  // 筛选逻辑
  const filteredRows = computed(() => {
    const kw = keyword.value.trim().toLowerCase()
    const base = rows.value.filter((r) => {
      if (!kw) return true
      return (
        r.admission_id.toLowerCase().includes(kw) ||
        r.patient_name.toLowerCase().includes(kw) ||
        (r.department || '').toLowerCase().includes(kw) ||
        (r.settlementType || '').toLowerCase().includes(kw) ||
        (r.settlementMethod || '').toLowerCase().includes(kw) ||
        (r.primary_diagnosis_name || '').toLowerCase().includes(kw)
      )
    })

    const byTab = base.filter((r) => {
      if (activeListTab.value === 'ungrouped') return r.groupingStatus === 'ungrouped'
      if (activeListTab.value === 'loss')
        return (
          r.groupingStatus === 'grouped' && typeof r.profitMargin === 'number' && r.profitMargin < 0
        )
      if (activeListTab.value === 'highRate')
        return r.groupingStatus === 'grouped' && typeof r.costRate === 'number' && r.costRate >= 120
      if (activeListTab.value === 'base') {
        return (
          r.groupingStatus === 'grouped' &&
          typeof r.costRate === 'number' &&
          r.costRate >= 80 &&
          r.costRate < 120
        )
      }
      const hasPending = (r.suggestions || []).some((s) => s.status === 'pending')
      return r.groupingStatus === 'grouped' && hasPending
    })

    return byTab
  })

  // 交互方法
  const openDrawer = async (record: FeeMonitoringRow, tab: ActiveDrawerTab = 'basic') => {
    selectedRow.value = record
    activeDrawerTab.value = tab
    drawerOpen.value = true

    // Reset data
    feeComposition.value = null
    feeTrend.value = []
    highValueMaterials.value = []
    feeWarningRecords.value = []

    drawerLoading.value = true

    // 模拟网络延迟以展示骨架屏
    setTimeout(() => {
      const feeDetails = getMockFeeDetails(
        record.admission_id,
        record.actualCost,
        record.baselinePayment || null,
      )

      feeComposition.value = feeDetails.composition
      feeTrend.value = feeDetails.trend
      highValueMaterials.value = feeDetails.highValueMaterials
      feeWarningRecords.value = feeDetails.warningRecords
      drawerLoading.value = false
    }, 800)
  }

  const goFix = (admissionId: string) => {
    // 路由跳转保持原样
    const query = { ...(route.query || {}) }
    router.push({ name: 'CodingDetail', params: { admissionId }, query })
  }

  return {
    loading,
    rows,
    keyword,
    activeListTab,
    drawerOpen,
    selectedRow,
    activeDrawerTab,
    drawerLoading,
    feeComposition,
    feeTrend,
    highValueMaterials,
    feeWarningRecords,
    loadData,
    filteredRows,
    openDrawer,
    goFix,
  }
}
