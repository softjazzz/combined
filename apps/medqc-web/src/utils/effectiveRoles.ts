/** sync_admin为超级管理员；只计算授权角色，不改账号或增加业务身份。 */
export function effectiveRoles(roles: readonly string[]): string[] {
  return roles.includes('sync_admin')
    ? [...new Set([...roles, 'admin', 'qc_manager', 'developer', 'super_admin'])]
    : [...roles]
}
