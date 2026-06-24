import { ref } from 'vue'
import { message } from 'ant-design-vue'

export interface DRGResult {
  code: string
  name: string
  weight: number
  payment: number
  actual_cost: number
  profit: number
  messages?: string[]
  drg_code?: string
  drg_name?: string
  baseline_payment?: number
}

export interface Suggestion {
  suggestion_id: number
  admission_id: string
  suggestion_type: string
  diagnosis_code?: string
  diagnosis_name?: string
  message: string
  evidence?: string
  severity: string
  status: string
  created_at?: string
}

export function useDRGGrouping() {
  const drgLoading = ref(false)
  const drgResult = ref<DRGResult | null>(null)
  const suggestionDrawerVisible = ref(false)
  const suggestionsLoading = ref(false)
  const suggestions = ref<Suggestion[]>([])

  const performDRGGrouping = async (caseId: string, insuranceTotalCost?: number) => {
    if (!caseId) {
      message.warning('请先加载并提取病历数据')
      return
    }

    drgLoading.value = true
    try {
      const response = await fetch('/api/v1/drg/predict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          admission_id: caseId,
          region: '四川省',
        }),
      })

      const data = await response.json()

      if (response.ok && data.data) {
        drgResult.value = {
          code: data.data.drg_code || data.data.code,
          name: data.data.drg_name || data.data.name,
          weight: data.data.weight,
          payment: data.data.baseline_payment || data.data.payment,
          actual_cost: data.data.actual_cost,
          profit: (data.data.baseline_payment || data.data.payment) - data.data.actual_cost,
          messages: data.data.messages || [],
        }
        message.success('DRG 分组预测成功')
        if (data.data.messages?.length > 0) {
          fetchSuggestions(caseId)
        }
      } else {
        console.warn('Backend DRG call failed, using mock', data)
        drgResult.value = {
          code: 'FM19',
          name: '心力衰竭，伴主要并发症或合并症',
          weight: 1.25,
          payment: 14500.0,
          actual_cost: insuranceTotalCost || 12580.5,
          profit: 14500.0 - (insuranceTotalCost || 12580.5),
          messages: ['主诊断匹配成功', '无手术编码影响', '并发症增加权重'],
        }
        message.success('DRG 分组预测成功 (模拟)')
      }
    } catch (error) {
      console.error('DRG grouping error:', error)
      message.error('分组服务暂不可用')
    } finally {
      drgLoading.value = false
    }
  }

  const openOptimizationDrawer = (caseId: string) => {
    suggestionDrawerVisible.value = true
    fetchSuggestions(caseId)
  }

  const fetchSuggestions = async (caseId: string) => {
    if (!caseId) return
    suggestionsLoading.value = true
    try {
      const response = await fetch(`/api/v1/drg/suggestions?admission_id=${caseId}`)
      const data = await response.json()
      if (data.suggestions) {
        suggestions.value = data.suggestions.filter((s: Suggestion) => s.status === 'pending')
      }
    } catch (error) {
      console.error('Fetch suggestions error:', error)
      message.error('获取优化建议失败')
    } finally {
      suggestionsLoading.value = false
    }
  }

  const handleSuggestion = async (id: number, action: 'accept' | 'reject', caseId: string) => {
    try {
      const response = await fetch('/api/v1/drg/suggestions/handle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ suggestion_id: id, action }),
      })
      if (response.ok) {
        message.success(action === 'accept' ? '已采纳建议' : '已忽略建议')
        suggestions.value = suggestions.value.filter((s) => s.suggestion_id !== id)

        if (action === 'accept') {
          message.loading('正在根据建议重新计算分组...', 1)
          setTimeout(() => performDRGGrouping(caseId), 1000)
        }
      }
    } catch {
      message.error('操作失败')
    }
  }

  const getSuggestionTitle = (type: string): string => {
    const map: Record<string, string> = {
      missing_diagnosis: '疑似漏诊',
      procedure_missing: '手术/操作遗漏',
      choice_error: '编码选择错误',
      logic_conflict: '逻辑校验冲突',
      complication_marking: '并发症标记建议',
    }
    return map[type] || '优化建议'
  }

  return {
    drgLoading,
    drgResult,
    suggestionDrawerVisible,
    suggestionsLoading,
    suggestions,
    performDRGGrouping,
    openOptimizationDrawer,
    fetchSuggestions,
    handleSuggestion,
    getSuggestionTitle,
  }
}
