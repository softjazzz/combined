import { describe, expect, it } from 'vitest'
import { canViewAllQcResults } from '@/utils/qcResultVisibility'

describe('质控结果账号展示范围', () => {
  it.each(['sync_admin', 'developer', 'super_admin'])('开发权限%s优先于演示标记', (role) => {
    expect(canViewAllQcResults({ roles: [role], is_demo_account: true })).toBe(true)
  })
  it('普通演示管理员仅看确定问题，不能由admin角色绕过', () => {
    expect(canViewAllQcResults({ roles: ['admin'], is_demo_account: true })).toBe(false)
  })
  it('非演示账号保持原有完整结果视图', () => {
    expect(canViewAllQcResults({ roles: ['qc_manager'], is_demo_account: false })).toBe(true)
  })
  it('认证未就绪或缺标记时默认只显示确定问题', () => {
    expect(canViewAllQcResults(null)).toBe(false)
    expect(canViewAllQcResults({ roles: ['admin'] })).toBe(false)
  })
})
