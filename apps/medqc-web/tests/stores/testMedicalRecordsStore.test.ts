import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const listTestRecords = vi.fn()
const removeTestRecord = vi.fn()
const updateTestRecordRules = vi.fn()
vi.mock('@/services/test-medical-records', () => ({
  listTestRecords: (...args: unknown[]) => listTestRecords(...args),
  removeTestRecord: (...args: unknown[]) => removeTestRecord(...args),
  updateTestRecordRules: (...args: unknown[]) => updateTestRecordRules(...args),
  getCurrentRuleSetCatalog: vi.fn(),
}))

import { useTestMedicalRecordsStore } from '@/stores/testMedicalRecords'

const item = { id: 'ct-1', updated_at: '2026-09-27T08:00:00', rule_ids: [] }

describe('useTestMedicalRecordsStore（真实接口）', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    listTestRecords.mockReset()
    removeTestRecord.mockReset()
    updateTestRecordRules.mockReset()
  })

  it('按分页与筛选读取列表，并剔除不在当前页的已选条目', async () => {
    listTestRecords.mockResolvedValue({ success: true, data: { items: [item], total: 7, page: 2, page_size: 5 } })
    const store = useTestMedicalRecordsStore()
    store.selectedIds = ['ct-1', 'ct-gone']
    store.includeRemoved = true
    await store.changePage(2, 5)
    expect(listTestRecords).toHaveBeenCalledWith({ page: 2, page_size: 5, include_removed: true, q: '' })
    expect(store.total).toBe(7)
    expect(store.selectedIds).toEqual(['ct-1'])
  })

  it('读取失败时清空列表并显示错误，不保留旧数据', async () => {
    listTestRecords.mockResolvedValue({ success: false, message: '获取测试病历失败' })
    const store = useTestMedicalRecordsStore()
    await store.load()
    expect(store.items).toEqual([])
    expect(store.loadError).toBe('获取测试病历失败')
  })

  it('移除成功后刷新列表，失败时不刷新', async () => {
    listTestRecords.mockResolvedValue({ success: true, data: { items: [], total: 0, page: 1, page_size: 20 } })
    removeTestRecord.mockResolvedValueOnce({ success: false, message: '冲突' })
    const store = useTestMedicalRecordsStore()
    await store.remove(item as never)
    expect(listTestRecords).not.toHaveBeenCalled()
    removeTestRecord.mockResolvedValueOnce({ success: true })
    await store.remove(item as never)
    expect(listTestRecords).toHaveBeenCalledTimes(1)
  })
})
