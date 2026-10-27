import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  queryRegistrationStatus,
  reviewRegistration,
  submitRegistration,
  getRegistrationDepartments,
} from '@/api/accountRegistration'

const request = vi.hoisted(() => vi.fn())
vi.mock('@/services/apiService', () => ({ ApiService: { requestRaw: request } }))
beforeEach(() => {
  vi.clearAllMocks()
})
describe('注册审批API合同', () => {
  it('未登录读取精简科室目录，申请无需邮箱和机构ID', async () => {
    const options = { items: [{ key: 'a'.repeat(64), name: '内科', label: '内科' }] }
    request.mockResolvedValueOnce({ data: { success: true, data: options } })
    expect(await getRegistrationDepartments()).toEqual(options)
    expect(request).toHaveBeenCalledWith({
      url: '/api/v1/auth/registration-departments',
      method: 'GET',
    })
    request.mockResolvedValueOnce({ data: { success: true, data: { status: 'pending' } } })
    await submitRegistration({
      username: 'doctor2',
      display_name: '合成医生',
      department_key: 'a'.repeat(64),
      password: 'synthetic-only-secret!',
    })
    expect(request.mock.lastCall?.[0].data).not.toHaveProperty('email')
    expect(request.mock.lastCall?.[0].data).not.toHaveProperty('institute_id')
  })
  it('申请只发送正式字段，解开结果而不是把它当已登录用户', async () => {
    const result = { user_id: 'user', status: 'pending', version: 1 }
    request.mockResolvedValue({ data: { success: true, data: result } })
    const application = {
      username: 'doctor1',
      email: 'synthetic@example.com',
      display_name: '合成医生',
      institute_id: 'A',
      department: '内科',
      password: 'synthetic-only-secret!',
    }
    expect(await submitRegistration(application)).toEqual(result)
    expect(request).toHaveBeenCalledWith({
      url: '/api/v1/auth/register',
      method: 'POST',
      data: application,
    })
  })
  it('查询口令只放POST正文，不放URL或存储', async () => {
    request.mockResolvedValue({ data: { success: true, data: { status: 'rejected' } } })
    await queryRegistrationStatus('doctor1', 'synthetic-only-secret!')
    expect(request).toHaveBeenCalledWith({
      url: '/api/v1/auth/registration-status',
      method: 'POST',
      data: { account: 'doctor1', password: 'synthetic-only-secret!' },
    })
  })
  it('200失败壳和409明确失败，不展示成功', async () => {
    request.mockResolvedValueOnce({ data: { success: false, message: '申请未保存' } })
    await expect(queryRegistrationStatus('doctor1', 'secret')).rejects.toThrow('申请未保存')
    request.mockRejectedValueOnce({ response: { status: 409, data: { detail: '申请已被处理' } } })
    await expect(
      reviewRegistration('user', {
        expected_version: 1,
        decision: 'reject',
        comment: '资料需核实',
      }),
    ).rejects.toThrow('申请已被处理')
  })
})
