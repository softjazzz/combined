import { computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { canViewAllQcResults } from '@/utils/qcResultVisibility'

export function useQcResultVisibility() {
  // 与独立结果组件已有的反馈入口一致；无认证上下文时仅显示确定问题。
  let authStore: ReturnType<typeof useAuthStore> | null = null
  try {
    authStore = useAuthStore()
  } catch {
    authStore = null
  }
  const confirmedResultsOnly = computed(() => !canViewAllQcResults(authStore?.user))
  return { confirmedResultsOnly }
}
