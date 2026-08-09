const SYSTEM_CONFIG_WRITE_ROLES = new Set(['admin', 'sync_admin', 'super_admin'])

export function canManageSystemConfig(roles: readonly unknown[]): boolean {
  return roles.some((role) =>
    SYSTEM_CONFIG_WRITE_ROLES.has(
      String(role || '')
        .trim()
        .toLowerCase(),
    ),
  )
}
