import { describe, expect, it } from 'vitest'

import { canManageSystemConfig } from '@/utils/systemConfigAccess'

describe('系统配置管理权限', () => {
  it.each(['admin', 'sync_admin', 'super_admin'])('%s 可以管理系统配置', (role) => {
    expect(canManageSystemConfig([role])).toBe(true)
  })

  it.each(['qc_manager', 'doctor', ''])('%s 不可管理系统配置', (role) => {
    expect(canManageSystemConfig([role])).toBe(false)
  })
})
