import { computed, ref } from 'vue'
import { getSheet2ExactReviewAcceptancePackage } from '@/services/manual-case-sample-service'
import type { Sheet2ExactReviewAcceptancePackage } from './types'

export function useCustomerSampleExactReview() {
  const exactReviewAcceptance = ref<Sheet2ExactReviewAcceptancePackage | null>(null)
  const exactReviewLoading = ref(false)
  const exactReviewError = ref('')

  const exactReviewStatusCards = computed(() => {
    const acceptance = exactReviewAcceptance.value
    const status = acceptance?.status_breakdown
    const explanations = acceptance?.explanations
    return [
      {
        label: '精确命中',
        value: status?.exact_confirmed ?? 0,
        help: explanations?.exact_confirmed || '已与人工问题精确对齐的条目。',
        cardClass: 'border-emerald-200 bg-emerald-50/70',
      },
      {
        label: '已复核阻塞',
        value: status?.blocked_with_reason ?? 0,
        help:
          explanations?.blocked_with_reason || '已复核，但当前规则或证据链还不能精确复现人工问题。',
        cardClass: 'border-amber-200 bg-amber-50/80',
      },
      {
        label: '缺文书跳过',
        value: status?.skip ?? 0,
        help: explanations?.skip || '原始正文缺失，按既定口径归入 skip。',
        cardClass: 'border-slate-200 bg-slate-50/90',
      },
      {
        label: '复核总量',
        value: acceptance?.total_rows ?? 0,
        help: 'Sheet2 全量逐条精确复核样本规模。',
        cardClass: 'border-sky-200 bg-sky-50/70',
      },
    ]
  })

  const exactReviewReasonTags = computed(() => {
    const breakdown = exactReviewAcceptance.value?.blocked_reason_breakdown || {}
    const order = ['规则不支持', '证据链不足', '人工问题原文不可判']
    return order
      .filter((label) => typeof breakdown[label] === 'number')
      .map((label) => ({
        label,
        value: breakdown[label],
        className:
          label === '规则不支持'
            ? 'border-sky-200 bg-sky-50 text-sky-700'
            : label === '证据链不足'
              ? 'border-orange-200 bg-orange-50 text-orange-700'
              : 'border-rose-200 bg-rose-50 text-rose-700',
      }))
  })

  const exactReviewBacklogBuckets = computed(
    () => exactReviewAcceptance.value?.blocked_backlog_breakdown || [],
  )

  function backlogBucketCardClass(category: string): string {
    if (category === '可补规则') {
      return 'border-sky-200 bg-[linear-gradient(180deg,rgba(239,246,255,0.95),rgba(255,255,255,0.98))]'
    }
    if (category === '需补源文书') {
      return 'border-orange-200 bg-[linear-gradient(180deg,rgba(255,247,237,0.95),rgba(255,255,255,0.98))]'
    }
    if (category === '需客户确认口径') {
      return 'border-fuchsia-200 bg-[linear-gradient(180deg,rgba(253,244,255,0.95),rgba(255,255,255,0.98))]'
    }
    return 'border-rose-200 bg-[linear-gradient(180deg,rgba(255,241,242,0.95),rgba(255,255,255,0.98))]'
  }

  function backlogBucketTagClass(category: string): string {
    if (category === '可补规则') {
      return 'border-sky-200 bg-sky-50 text-sky-700'
    }
    if (category === '需补源文书') {
      return 'border-orange-200 bg-orange-50 text-orange-700'
    }
    if (category === '需客户确认口径') {
      return 'border-fuchsia-200 bg-fuchsia-50 text-fuchsia-700'
    }
    return 'border-rose-200 bg-rose-50 text-rose-700'
  }

  async function loadExactReviewAcceptance() {
    exactReviewLoading.value = true
    exactReviewError.value = ''
    const result = await getSheet2ExactReviewAcceptancePackage()
    exactReviewLoading.value = false
    if (!result.success || !result.data) {
      exactReviewAcceptance.value = null
      exactReviewError.value = result.message || '获取 Sheet2 精确复核验收包失败'
      return
    }
    exactReviewAcceptance.value = result.data
  }

  async function ensureExactReviewAcceptanceLoaded() {
    if (exactReviewLoading.value || exactReviewAcceptance.value) return
    await loadExactReviewAcceptance()
  }

  return {
    exactReviewAcceptance,
    exactReviewLoading,
    exactReviewError,
    exactReviewStatusCards,
    exactReviewReasonTags,
    exactReviewBacklogBuckets,
    backlogBucketCardClass,
    backlogBucketTagClass,
    ensureExactReviewAcceptanceLoaded,
  }
}
