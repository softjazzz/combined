/** 只决定结果面板的展示范围，不改变后端判定、持久化或数据授权。 */
export interface QcResultViewer {
  is_demo_account?: boolean
  roles?: readonly unknown[]
  role?: string
}

const FULL_RESULT_ROLES = new Set(['sync_admin', 'super_admin', 'developer'])

export function canViewAllQcResults(user: QcResultViewer | null | undefined): boolean {
  if (!user) return false
  const roles = Array.isArray(user.roles) ? user.roles : user.role ? [user.role] : []
  // 内置sync_admin也带演示标记，开发权限必须优先判断。
  if (roles.some((role) => FULL_RESULT_ROLES.has(String(role).trim().toLowerCase()))) return true
  return user.is_demo_account === false
}
