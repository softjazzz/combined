import { describe, expect, it, beforeEach, vi } from 'vitest'
import { ref } from 'vue'
import { readFileSync } from 'node:fs'

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  put: vi.fn(),
  isAuthenticated: vi.fn(),
  messageInfo: vi.fn(),
  messageWarning: vi.fn(),
  messageError: vi.fn(),
  messageSuccess: vi.fn(),
  auth: { user: { id: 'doctor' }, userRoles: ['doctor'] },
}))

vi.mock('@/services/apiService', () => ({
  ApiService: {
    get: mocks.get,
    put: mocks.put,
    isAuthenticated: mocks.isAuthenticated,
  },
}))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => mocks.auth }))

vi.mock('ant-design-vue', () => ({
  message: {
    info: mocks.messageInfo,
    warning: mocks.messageWarning,
    error: mocks.messageError,
    success: mocks.messageSuccess,
  },
}))

import { messageTime } from '@/views/workstation/useMessageCenter'
import { useNotifications } from '@/views/workstation-v4/composables/useNotifications'
import { normalizeNotification } from '@/views/workstation-v4/normalize'
import type { PatientRecord } from '@/views/workstation-v4/types'

async function flushPromises() {
  await Promise.resolve()
  await Promise.resolve()
}

describe('useNotifications overview acceptance', () => {
  it('质控结果通知把无时区时间按 UTC 解读，并在北京时间跨日展示', () => {
    expect(messageTime('2026-10-22 16:00:00', 'qc_result_ready')).toBe('2026/10/23 00:00')
    expect(messageTime('2026-10-23T01:00:00+09:00', 'qc_result_ready')).toBe('2026/10/23 00:00')
    expect(messageTime('invalid', 'qc_result_ready')).toBe('时间未知')
  })

  it.each(['account_registration', 'account_registration_result', 'qc_result_ready'])('现代消息%s保持精确目标，不按病历号下钻', async (kind) => {
    const open = vi.fn().mockResolvedValue(undefined)
    const legacyOpen = vi.fn()
    const notify = useNotifications(ref([]), legacyOpen, ref(false), ref('message'), ref('fields'), open)
    const notice = normalizeNotification({ id: 'registration-notice', record_id: 'registration:user:1', is_read: false, interaction_target: { kind, id: 'user-id' } }, 0)
    await notify.handleAssistNotificationClick(notice)
    expect(open).toHaveBeenCalledWith({ kind, id: 'user-id' })
    expect(legacyOpen).not.toHaveBeenCalled()
  })
  it('病历级沟通沿原消息入口按事件ID定位，不复用缺陷任务或申诉ID', async () => {
    const open = vi.fn().mockResolvedValue(undefined)
    const legacyOpen = vi.fn()
    const notify = useNotifications(
      ref([]),
      legacyOpen,
      ref(false),
      ref('message'),
      ref('fields'),
      open,
    )
    const notice = normalizeNotification(
      {
        id: 'notice',
        record_id: 'feedback:case_communication:event',
        is_read: false,
        interaction_target: { kind: 'case_communication', id: 'event' },
      },
      0,
    )
    await notify.handleAssistNotificationClick(notice)
    expect(open).toHaveBeenCalledWith({ kind: 'case_communication', id: 'event' })
    expect(legacyOpen).not.toHaveBeenCalled()
  })
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.isAuthenticated.mockReturnValue(true)
    mocks.put.mockResolvedValue({ success: true })
  })

  it('消息入口不预加载仅管理角色可读的首页配置', () => {
    const view = readFileSync('src/views/workstation-v4/WorkstationV4View.vue', 'utf8')
    expect(view).toContain(
      "if (route.query.assist !== 'message') void ensureExtractionSettingsLoaded()",
    )
  })

  it('消息已读失败不跳转、不伪造已读，概览错误可恢复', async () => {
    const open = vi.fn()
    const notify = useNotifications(
      ref([]),
      vi.fn(),
      ref(false),
      ref('message'),
      ref('fields'),
      open,
    )
    const notice = {
      id: 'notice',
      record_id: 'feedback:rectification:task',
      title: '整改提醒',
      content: '',
      message: '',
      created_at: '',
      is_read: false,
      interaction_target: { kind: 'rectification' as const, id: 'task' },
    }
    mocks.put.mockResolvedValueOnce({ success: false })
    await notify.handleAssistNotificationClick(notice)
    expect(notice.is_read).toBe(false)
    expect(open).not.toHaveBeenCalled()
    mocks.put.mockRejectedValueOnce(new Error('network'))
    await notify.handleAssistOverviewClick({
      overview_id: 'summary',
      type: 'remediation',
      severity: 'warning',
      department: '',
      record_id: '',
      title: '',
      summary: '',
      occurrence_count: 1,
      unread_count: 1,
      latest_created_at: '',
      source_notification_ids: ['notice'],
      interaction_target: { kind: 'rectification', id: 'task' },
    })
    expect(open).not.toHaveBeenCalled()
    expect(mocks.messageError).toHaveBeenCalledWith('消息状态未核实，请刷新核对')
  })

  it('整改与申诉在原消息列表定位精确对象，不按同号就诊找病例', async () => {
    const open = vi.fn().mockResolvedValue(undefined)
    const records = ref<PatientRecord[]>([])
    const notify = useNotifications(
      records,
      vi.fn(),
      ref(false),
      ref('message'),
      ref('fields'),
      open,
    )
    const item = {
      id: 'notice',
      record_id: 'feedback:rectification:task',
      title: '整改驳回',
      content: '请重提',
      message: '请重提',
      created_at: '2026-10-25T00:00:00Z',
      is_read: false,
      interaction_target: { kind: 'rectification' as const, id: 'task' },
    }
    await notify.handleAssistNotificationClick(item)
    expect(open).toHaveBeenCalledWith({ kind: 'rectification', id: 'task' })
    expect(mocks.put).toHaveBeenCalledWith('/api/v1/notifications/notice/read')
    await notify.handleAssistOverviewClick({
      overview_id: 'summary',
      type: 'appeal_result',
      severity: 'info',
      department: '内科',
      record_id: 'feedback:modern_appeal:appeal',
      title: '申诉通过',
      summary: '已通过',
      occurrence_count: 1,
      unread_count: 1,
      latest_created_at: '2026-10-25T00:00:00Z',
      source_notification_ids: ['history-not-in-page'],
      interaction_target: { kind: 'modern_appeal', id: 'appeal' },
    })
    expect(mocks.put).toHaveBeenCalledWith('/api/v1/notifications/history-not-in-page/read')
    expect(open).toHaveBeenLastCalledWith({ kind: 'modern_appeal', id: 'appeal' })
  })

  it('服务器全量未读数不被当前30条分页的本地数覆盖，读取失败保留旧记录', async () => {
    mocks.get
      .mockResolvedValueOnce({ success: true, data: { items: [], unread_count: 45 } })
      .mockResolvedValueOnce({ success: true, data: { items: [] } })
      .mockRejectedValueOnce(new Error('network'))
    const notify = useNotifications(ref([]), vi.fn(), ref(false), ref('message'), ref('fields'))
    await notify.fetchAssistNotifications()
    expect(notify.notificationUnreadCount.value).toBe(45)
    await notify.fetchAssistNotifications()
    expect(notify.notificationUnreadCount.value).toBe(45)
    expect(mocks.messageError).toHaveBeenCalled()
  })

  it('缺少可信处理目标的反馈消息不退回旧病例定位', async () => {
    const legacyOpen = vi.fn()
    const notify = useNotifications(ref([]), legacyOpen, ref(false), ref('message'), ref('fields'))
    await notify.handleAssistNotificationClick({
      id: 'n',
      record_id: 'feedback:rectification:unknown',
      title: '提醒',
      content: '',
      message: '',
      created_at: '',
      is_read: true,
    })
    expect(legacyOpen).not.toHaveBeenCalled()
    expect(mocks.messageError).toHaveBeenCalledWith('消息处理对象未核实，请刷新核对')
  })

  it('rejects an ambiguous legacy notification and opens a complete case key', async () => {
    const records = ref(
      ['P-1', 'P-2'].map((patientId) => ({
        id: patientId,
        visitId: 'V-100',
        instituteId: 'H-1',
        patientId,
      })) as PatientRecord[],
    )
    const open = vi.fn()
    const assistPanelVisible = ref(false)
    const notify = useNotifications(records, open, assistPanelVisible, ref('message'), ref('fields'))
    const notice = { id: 'legacy', is_read: true }

    await notify.handleAssistNotificationClick(
      normalizeNotification({ ...notice, record_id: 'V-100' }, 0),
    )
    expect(open).not.toHaveBeenCalled()
    expect(assistPanelVisible.value).toBe(false)
    expect(mocks.messageWarning).toHaveBeenCalledWith(expect.stringContaining('重新选择'))

    await notify.handleAssistNotificationClick(
      normalizeNotification({ ...notice, record_id: '["H-1","P-2","V-100"]' }, 0),
    )
    expect(open).toHaveBeenCalledTimes(1)
    expect(open).toHaveBeenCalledWith(records.value[1])
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
    const opened: PatientRecord[] = []
    const assistPanelVisible = ref(false)
    const assistTab = ref('overview')
    const frontpageTab = ref('summary')

    const notifications = useNotifications(
      records,
      (record) => opened.push(record),
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
    expect(opened).toEqual([records.value[0]])
    expect(assistPanelVisible.value).toBe(true)
    expect(assistTab.value).toBe('form')
    expect(frontpageTab.value).toBe('fields')
  })
})
