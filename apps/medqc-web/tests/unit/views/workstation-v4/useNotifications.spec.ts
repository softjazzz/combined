import { describe, expect, it, beforeEach, vi } from 'vitest'
import { ref } from 'vue'

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  put: vi.fn(),
  isAuthenticated: vi.fn(),
  messageInfo: vi.fn(),
  messageWarning: vi.fn(),
  messageError: vi.fn(),
  messageSuccess: vi.fn(),
}))

vi.mock('@/services/apiService', () => ({
  ApiService: {
    get: mocks.get,
    put: mocks.put,
    isAuthenticated: mocks.isAuthenticated,
  },
}))

vi.mock('ant-design-vue', () => ({
  message: {
    info: mocks.messageInfo,
    warning: mocks.messageWarning,
    error: mocks.messageError,
    success: mocks.messageSuccess,
  },
}))

import { useNotifications } from '@/views/workstation-v4/composables/useNotifications'
import type { PatientRecord } from '@/views/workstation-v4/types'

async function flushPromises() {
  await Promise.resolve()
  await Promise.resolve()
}

describe('useNotifications overview acceptance', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.isAuthenticated.mockReturnValue(true)
    mocks.put.mockResolvedValue({ success: true })
  })

  it('falls back to local same-record aggregation and opens linked record', async () => {
    mocks.get
      .mockResolvedValueOnce({
        success: true,
        data: {
          items: [
            {
              id: 'n1',
              type: 'defect_urge',
              severity: 'warning',
              record_id: 'V001',
              title: '缺陷催办',
              content: '请处理缺陷 A',
              created_at: '2026-03-23T10:00:00Z',
              is_read: false,
            },
            {
              id: 'n2',
              type: 'defect_urge',
              severity: 'warning',
              record_id: 'V001',
              title: '缺陷催办',
              content: '请处理缺陷 A-2',
              created_at: '2026-03-23T11:00:00Z',
              is_read: true,
            },
            {
              id: 'batch',
              type: 'frontpage_qc_batch_summary',
              title: '批量汇总',
              content: '不进入问题集中点',
              created_at: '2026-03-23T12:00:00Z',
              is_read: false,
            },
          ],
        },
      })
      .mockResolvedValueOnce({ success: false, data: null })
      .mockResolvedValueOnce({ success: false, data: null })

    const records = ref<PatientRecord[]>([
      {
        id: 'V001',
        visitId: 'V001',
        name: '张三',
        bedNo: '12',
        sex: '男',
        department: '内科',
        age: 45,
        insurance: '职工医保',
        admissionDate: '2026-03-20',
        dischargeDate: '2026-03-25',
        days: 5,
        diagnosis: '高血压',
        diagnosisCode: 'I10.x00',
        doctor: '李医生',
        status: 'pending',
      },
    ])
    const opened: string[] = []
    const assistPanelVisible = ref(false)
    const assistTab = ref('overview')
    const frontpageTab = ref('summary')

    const notifications = useNotifications(
      records,
      (id) => opened.push(id),
      assistPanelVisible,
      assistTab,
      frontpageTab,
    )

    await notifications.fetchAssistNotifications()
    await flushPromises()

    expect(notifications.notificationUnreadCount.value).toBe(1)
    expect(notifications.notificationOverviewItems.value).toHaveLength(1)
    const overview = notifications.notificationOverviewItems.value[0]
    expect(overview.type).toBe('defect_urge')
    expect(overview.record_id).toBe('V001')
    expect(overview.occurrence_count).toBe(2)
    expect(overview.unread_count).toBe(1)
    expect(overview.source_notification_ids).toEqual(['n1', 'n2'])
    expect(overview.summary).toBe('请处理缺陷 A-2')

    await notifications.handleAssistOverviewClick(overview)
    await flushPromises()

    expect(mocks.put).toHaveBeenCalledWith('/api/v1/notifications/n1/read')
    expect(opened).toEqual(['V001'])
    expect(assistPanelVisible.value).toBe(true)
    expect(assistTab.value).toBe('form')
    expect(frontpageTab.value).toBe('fields')
  })
})
