import { beforeEach, describe, expect, it, vi } from 'vitest'
import { getUserScopeOptions, listAdminUsers, updateUserScope } from '@/api/adminUsers'
import { ApiService } from '@/services/apiService'

const user = {
  id: 'doctor-1',
  username: 'doctor-1',
  display_name: '医生甲',
  institute_id: 'H1',
  department: '心内科',
  roles: ['doctor'],
  is_active: true,
  updated_at: '2026-09-30T08:00:00Z',
}

function envelope(data: unknown) {
  return { status: 200, data: { success: true, data } } as Awaited<
    ReturnType<typeof ApiService.requestRaw>
  >
}

describe('admin users scope API', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('读取账号的医院科室归属', async () => {
    vi.spyOn(ApiService, 'requestRaw').mockResolvedValueOnce(
      envelope({
        items: [user],
        total: 1,
        page: 1,
        page_size: 20,
        departments: ['心内科'],
      }),
    )

    const result = await listAdminUsers({ page: 1, page_size: 20 })

    expect(result.success && result.data.items[0]).toMatchObject({
      institute_id: 'H1',
      department: '心内科',
    })
  })

  it('读取真实院科组合选项', async () => {
    const request = vi.spyOn(ApiService, 'requestRaw').mockResolvedValueOnce(
      envelope({
        institutes: ['H1'],
        items: [{ institute_id: 'H1', department: '心内科' }],
      }),
    )

    const result = await getUserScopeOptions()

    expect(request).toHaveBeenCalledWith({
      method: 'GET',
      url: '/api/v1/admin/users/scope-options',
    })
    expect(result).toEqual({
      success: true,
      data: { institutes: ['H1'], items: [{ institute_id: 'H1', department: '心内科' }] },
    })
  })

  it('管理员保存时显式传医院、科室与 CAS 版本', async () => {
    const request = vi.spyOn(ApiService, 'requestRaw').mockResolvedValueOnce(envelope(user))

    const result = await updateUserScope('doctor-1', {
      institute_id: ' H1 ',
      department: ' 心内科 ',
      expected_updated_at: user.updated_at,
    })

    expect(result.success).toBe(true)
    expect(request).toHaveBeenCalledWith({
      method: 'PUT',
      url: '/api/v1/admin/users/doctor-1/department',
      data: { institute_id: 'H1', department: '心内科', expected_updated_at: user.updated_at },
    })
  })

  it('院科单边值在发请前失败关闭', async () => {
    const request = vi.spyOn(ApiService, 'requestRaw')

    const result = await updateUserScope('doctor-1', {
      institute_id: 'H1',
      department: '',
      expected_updated_at: user.updated_at,
    })

    expect(result).toMatchObject({ success: false, resultUnknown: false })
    expect(request).not.toHaveBeenCalled()
  })

  it('保存回执必须与请求院科精确一致', async () => {
    vi.spyOn(ApiService, 'requestRaw').mockResolvedValueOnce(
      envelope({ ...user, department: '骨科' }),
    )

    const result = await updateUserScope('doctor-1', {
      institute_id: 'H1',
      department: '心内科',
      expected_updated_at: user.updated_at,
    })

    expect(result).toMatchObject({ success: false, resultUnknown: true })
  })

  it('503 可能发生在提交后，按结果未知要求刷新核对', async () => {
    vi.spyOn(ApiService, 'requestRaw').mockRejectedValueOnce({ response: { status: 503 } })

    const result = await updateUserScope('doctor-1', {
      institute_id: 'H1',
      department: '心内科',
      expected_updated_at: user.updated_at,
    })

    expect(result).toMatchObject({ success: false, resultUnknown: true, conflict: false })
  })
})
