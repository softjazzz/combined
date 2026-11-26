const SUPER_ADMIN_ROLES: readonly string[] = ['sync_admin', 'super_admin']

/** sync_admin 与 super_admin 为超级管理员；只计算授权角色，不改账号或增加业务身份。 */
export function effectiveRoles(roles: readonly string[]): string[] {
  return roles.some((role) => SUPER_ADMIN_ROLES.includes(role))
    ? [...new Set([...roles, 'admin', 'qc_manager', 'developer', 'super_admin'])]
    : [...roles]
}
