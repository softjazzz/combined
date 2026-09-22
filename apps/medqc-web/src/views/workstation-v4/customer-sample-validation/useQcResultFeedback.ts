import { computed, ref, toValue, watch, type MaybeRefOrGetter } from 'vue'
import { useAuthStore } from '@/stores/auth'
import {
  getQcResultFeedbackDemo,
  saveQcResultFeedbackDemo,
  type QcResultFeedbackRecord,
  type SaveQcResultFeedbackInput,
} from '@/api/qc-result-feedback-demo'

function clean(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

const LUXIAN_0609_RULE_ID_PATTERN = /^LX0609-\d{2}-\d{2}-\d{2}$/u
const LUXIAN_0609_PREFIX_PATTERN = /^LX0609-/iu

function normalizeFeedbackRuleId(value: unknown): string {
  const ruleId = clean(value)
  if (LUXIAN_0609_PREFIX_PATTERN.test(ruleId) && !LUXIAN_0609_RULE_ID_PATTERN.test(ruleId)) {
    return ''
  }
  return ruleId
}

export function useQcResultFeedback(
  rootJobIdSource: MaybeRefOrGetter<string | undefined>,
  recordRefSource: MaybeRefOrGetter<string | undefined>,
) {
  const feedbackByRule = ref<Record<string, QcResultFeedbackRecord>>({})
  const loading = ref(false)
  const error = ref('')
  const savingRuleId = ref('')
  const requestGeneration = ref(0)

  // 结果页可能在没有 Pinia 的独立单测中挂载；生产页面始终由认证路由提供 Pinia。
  // 捕获该场景只会关闭反馈入口，不影响原质控结果展示。
  let authStore: ReturnType<typeof useAuthStore> | null = null
  try {
    authStore = useAuthStore()
  } catch {
    authStore = null
  }

  const rootJobId = computed(() => clean(toValue(rootJobIdSource)))
  const recordRef = computed(() => clean(toValue(recordRefSource)))
  const isDemoAccount = computed(
    () =>
      authStore?.user?.is_demo_account === true &&
      String(authStore.user?.id || '').trim() === 'admin-001' &&
      String(authStore.user?.email || '')
        .trim()
        .toLowerCase() === 'admin@medqc.com',
  )
  const isEnabled = computed(
    () => isDemoAccount.value && Boolean(rootJobId.value && recordRef.value),
  )

  async function load() {
    const generation = ++requestGeneration.value
    feedbackByRule.value = {}
    error.value = ''
    if (!isEnabled.value) return

    loading.value = true
    const result = await getQcResultFeedbackDemo({
      rootJobId: rootJobId.value,
      recordRef: recordRef.value,
    })
    if (generation !== requestGeneration.value) return
    loading.value = false
    if (!result.success || !result.data) {
      error.value = '反馈暂时无法使用，质控结果仍可正常查看。'
      return
    }
    feedbackByRule.value = Object.fromEntries(
      Object.entries(result.data).filter(([ruleId]) => Boolean(normalizeFeedbackRuleId(ruleId))),
    )
  }

  async function save(ruleId: string, input: SaveQcResultFeedbackInput) {
    const normalizedRuleId = normalizeFeedbackRuleId(ruleId)
    if (!isEnabled.value || !normalizedRuleId) {
      return { success: false, message: '当前账号暂不支持结果反馈' }
    }

    savingRuleId.value = normalizedRuleId
    error.value = ''
    const result = await saveQcResultFeedbackDemo({
      rootJobId: rootJobId.value,
      recordRef: recordRef.value,
      ruleId: normalizedRuleId,
      input,
    })
    if (result.success && result.data) {
      const returnedRuleId = normalizeFeedbackRuleId(result.data.rule_id)
      if (returnedRuleId) {
        feedbackByRule.value = {
          ...feedbackByRule.value,
          [returnedRuleId]: result.data,
        }
      }
    } else {
      error.value = '反馈暂时无法保存，质控结果仍可正常查看。'
    }
    savingRuleId.value = ''
    return result
  }

  watch(
    [isDemoAccount, rootJobId, recordRef],
    () => {
      void load()
    },
    { immediate: true },
  )

  return {
    feedbackByRule: computed(() => feedbackByRule.value),
    loading: computed(() => loading.value),
    error: computed(() => error.value),
    savingRuleId: computed(() => savingRuleId.value),
    isDemoAccount,
    isEnabled,
    load,
    save,
  }
}
