import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useTestMedicalRecordsStore } from '@/stores/testMedicalRecords'

describe('useTestMedicalRecordsStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('initializes with data and templates', async () => {
    const store = useTestMedicalRecordsStore()
    await store.initialize()

    expect(store.records.length).toBeGreaterThan(0)
    expect(store.filterTemplates.length).toBeGreaterThan(0)
    expect(store.pagination.total).toBe(store.records.length)
  })

  it('applies status filter to narrow results', async () => {
    const store = useTestMedicalRecordsStore()
    await store.initialize()

    store.updateConditions({ status: ['draft'] })
    await store.applyFilters()

    expect(store.records.length).toBe(1)
    expect(store.records[0].status).toBe('draft')
  })

  it('performs batch status update', async () => {
    const store = useTestMedicalRecordsStore()
    await store.initialize()

    const targetId = 'rec-004'
    await store.performBatchAction({
      action: 'updateStatus',
      recordIds: [targetId],
      targetStatus: 'verified'
    })

    const detail = await store.fetchDetail(targetId)
    expect(detail.status).toBe('verified')
  })
})
