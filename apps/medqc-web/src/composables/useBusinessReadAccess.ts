import { computed } from 'vue'
import { useAuthStore } from '@/stores/auth'

/** 同步角色新增的是查看入口；已有业务管理角色的操作权限不变。 */
export function useBusinessReadAccess() {
  let auth: ReturnType<typeof useAuthStore> | null = null
  try {
    auth = useAuthStore()
  } catch {
    // 独立组件测试可能未挂载Pinia；不额外改变既有组件行为。
  }
  const isBusinessReadOnly = computed(() => {
    const roles = auth?.userRoles || []
    return roles.includes('sync_admin') && !roles.some((role) => ['admin', 'qc_manager'].includes(role))
  })
  return { isBusinessReadOnly }
}
