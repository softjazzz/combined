import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import Antd, { message, Modal } from 'ant-design-vue'

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  exportRecords: vi.fn(),
  copyRecord: vi.fn(),
  downloadBlob: vi.fn(),
  routerPush: vi.fn(),
}))
const authControl = vi.hoisted(() => ({
  set: null as null | ((user: { id: string; roles: string[] } | null) => void),
}))

vi.mock('@/stores/auth', async () => {
  const { reactive } = await import('vue')
  const state = reactive<{
    user: { id: string; roles: string[] } | null
    userRoles: string[]
  }>({ user: null, userRoles: [] })
  authControl.set = (user) => {
    state.user = user
    state.userRoles = user ? [...user.roles] : []
  }
  return { useAuthStore: () => state }
})

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mocks.routerPush }),
}))

vi.mock('@/services/test-medical-records', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/services/test-medical-records')>()
  return {
    ...actual,
    listTestRecords: (...args: unknown[]) => mocks.list(...args),
    exportTestRecords: (...args: unknown[]) => mocks.exportRecords(...args),
    copyTestRecord: (...args: unknown[]) => mocks.copyRecord(...args),
  }
})

vi.mock('@/views/workstation-v4/customer-sample-validation/batchExport', () => ({
  downloadBlob: (...args: unknown[]) => mocks.downloadBlob(...args),
}))

import TestMedicalRecordsView from '@/views/test-medical-records/TestMedicalRecordsView.vue'
import { useTestMedicalRecordsStore } from '@/stores/testMedicalRecords'
import type { TestRecordItem } from '@/types/test-medical-records'

window.matchMedia = window.matchMedia || ((query: string) => ({
  matches: false,
  media: query,
  onchange: null,
  addListener: vi.fn(),
  removeListener: vi.fn(),
  addEventListener: vi.fn(),
  removeEventListener: vi.fn(),
  dispatchEvent: vi.fn(),
}) as unknown as MediaQueryList)
const getComputedStyle = window.getComputedStyle.bind(window)
window.getComputedStyle = (element: Element) => getComputedStyle(element)

function makeItem(): TestRecordItem {
  return {
    id: 'ct-1',
    institute_id: 'CUSTOMER_TEST',
    patient_id: 'CUSTOMER_PATIENT_1',
    visit_id: 'CUSTOMER_TEST_1',
    case_title: '测试病历一',
    patient_name: '测试患者',
    department: '心内科',
    mr_no: 'MR-1',
    document_count: 1,
    rule_ids: ['LX0609-001'],
    rule_count: 1,
    latest_job_id: '',
    bundle_status: 'ready',
    origin: 'created',
    source_item_id: '',
    sex: '女',
    age: 45,
    admission_time: '2026-09-01T08:00:00',
    state: 'active',
    removed: false,
    superseded_by: null,
    created_at: '2026-09-27T08:00:00',
    updated_at: '2026-09-27T08:00:00.123456',
  }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => {
    resolve = done
  })
  return { promise, resolve }
}

async function mountView() {
  const pinia = createPinia()
  setActivePinia(pinia)
  authControl.set?.({ id: 'user-1', roles: ['admin'] })
  const wrapper = mount(TestMedicalRecordsView, {
    global: {
      plugins: [pinia, Antd],
      stubs: {
        TestRecordRulePickerModal: true,
        TestRecordEditDrawer: true,
        TestRecordImportDrawer: true,
        QCRecordCompareWorkbench: true,
        QCRecordResultComparisonDrawer: true,
      },
    },
    attachTo: document.body,
  })
  await flushPromises()
  return { wrapper, store: useTestMedicalRecordsStore() }
}

describe('测试病历固定池导出与复制', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
    vi.restoreAllMocks()
    Object.values(mocks).forEach((mock) => mock.mockReset())
    mocks.list.mockResolvedValue({
      success: true,
      data: { items: [makeItem()], total: 1, page: 1, page_size: 20 },
    })
  })

  it('按勾选 ID 导出可回导 XLSX，服务未确认时不触发下载', async () => {
    const blob = new Blob(['xlsx'], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    })
    mocks.exportRecords.mockResolvedValueOnce({ success: true, data: blob })
    const { wrapper, store } = await mountView()
    store.selectedIds = ['ct-1']
    await flushPromises()

    await wrapper.get('[data-testid="export-selected-records"]').trigger('click')
    await flushPromises()

    expect(mocks.exportRecords).toHaveBeenCalledWith(['ct-1'])
    expect(mocks.downloadBlob).toHaveBeenCalledWith(blob, 'V3.6-test-records.xlsx')

    mocks.exportRecords.mockResolvedValueOnce({ success: false, message: '导出失败' })
    await wrapper.get('[data-testid="export-selected-records"]').trigger('click')
    await flushPromises()
    expect(mocks.downloadBlob).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })

  it('账号失去管理角色后不再显示导出和复制命令', async () => {
    const { wrapper } = await mountView()
    authControl.set?.({ id: 'user-1', roles: ['qc_reviewer'] })
    await flushPromises()

    expect(wrapper.find('[data-testid="export-selected-records"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="copy-record-ct-1"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('选中集合包含不可导出条目时不静默少导', async () => {
    const { wrapper, store } = await mountView()
    store.selectedIds = ['ct-1', 'stale-id']
    await flushPromises()

    await wrapper.get('[data-testid="export-selected-records"]').trigger('click')
    await flushPromises()

    expect(mocks.exportRecords).not.toHaveBeenCalled()
    expect(mocks.downloadBlob).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('页面卸载后丢弃迟到导出结果，不下载文件', async () => {
    const pending = deferred<{ success: true; data: Blob }>()
    mocks.exportRecords.mockReturnValue(pending.promise)
    const { wrapper, store } = await mountView()
    store.selectedIds = ['ct-1']
    await flushPromises()

    await wrapper.get('[data-testid="export-selected-records"]').trigger('click')
    wrapper.unmount()
    pending.resolve({ success: true, data: new Blob(['xlsx']) })
    await flushPromises()

    expect(mocks.downloadBlob).not.toHaveBeenCalled()
  })

  it('复制确认后按源版本创建新病例并刷新，不修改原列表项', async () => {
    const source = makeItem()
    const confirm = vi.spyOn(Modal, 'confirm').mockImplementation((options) => options as never)
    vi.spyOn(message, 'success').mockImplementation(() => ({}) as never)
    mocks.copyRecord.mockResolvedValue({
      success: true,
      data: {
        visit_id: 'CUSTOMER_TEST_COPY_1',
        patient_id: 'CUSTOMER_PATIENT_COPY_1',
        source_item_id: source.id,
        source_updated_at: source.updated_at,
        bundle_status: 'ready',
      },
    })
    const { wrapper } = await mountView()

    await wrapper.get('[data-testid="copy-record-ct-1"]').trigger('click')
    const options = confirm.mock.calls[0][0]
    await options.onOk?.()
    await flushPromises()

    expect(mocks.copyRecord).toHaveBeenCalledWith(source)
    expect(mocks.list).toHaveBeenCalledTimes(2)
    expect(source).toEqual(makeItem())
    wrapper.unmount()
  })

  it('切换账号后丢弃旧账号的迟到复制回执，不提示成功也不刷新', async () => {
    const pending = deferred<{ success: true; data: Record<string, string> }>()
    const confirm = vi.spyOn(Modal, 'confirm').mockImplementation((options) => options as never)
    const success = vi.spyOn(message, 'success').mockImplementation(() => ({}) as never)
    mocks.copyRecord.mockReturnValue(pending.promise)
    const { wrapper } = await mountView()
    authControl.set?.({ id: 'user-1', roles: ['admin'] })
    await flushPromises()

    await wrapper.get('[data-testid="copy-record-ct-1"]').trigger('click')
    const options = confirm.mock.calls[0][0]
    const copyPromise = options.onOk?.()
    authControl.set?.({ id: 'user-2', roles: ['admin'] })
    await flushPromises()
    pending.resolve({
      success: true,
      data: {
        visit_id: 'CUSTOMER_TEST_COPY_1',
        patient_id: 'CUSTOMER_PATIENT_COPY_1',
        source_item_id: 'ct-1',
        source_updated_at: '2026-09-27T08:00:00.123456',
        bundle_status: 'ready',
      },
    })
    await copyPromise
    await flushPromises()

    expect(success).not.toHaveBeenCalled()
    expect(mocks.list).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })

  it('复制与导出并发完成时互不留下永久忙状态', async () => {
    const pendingCopy = deferred<{ success: true; data: Record<string, string> }>()
    const pendingExport = deferred<{ success: true; data: Blob }>()
    const confirm = vi.spyOn(Modal, 'confirm').mockImplementation((options) => options as never)
    vi.spyOn(message, 'success').mockImplementation(() => ({}) as never)
    mocks.copyRecord.mockReturnValue(pendingCopy.promise)
    mocks.exportRecords.mockReturnValue(pendingExport.promise)
    const { wrapper, store } = await mountView()
    store.selectedIds = ['ct-1']
    await flushPromises()

    await wrapper.get('[data-testid="copy-record-ct-1"]').trigger('click')
    const copyPromise = confirm.mock.calls[0][0].onOk?.()
    await wrapper.get('[data-testid="export-selected-records"]').trigger('click')
    pendingExport.resolve({ success: true, data: new Blob(['xlsx']) })
    await flushPromises()
    expect(wrapper.get('[data-testid="export-selected-records"]').attributes('disabled')).toBeUndefined()

    pendingCopy.resolve({
      success: true,
      data: {
        visit_id: 'CUSTOMER_TEST_COPY_1',
        patient_id: 'CUSTOMER_PATIENT_COPY_1',
        source_item_id: 'ct-1',
        source_updated_at: '2026-09-27T08:00:00.123456',
        bundle_status: 'ready',
      },
    })
    await copyPromise
    await flushPromises()
    expect(wrapper.get('[data-testid="copy-record-ct-1"]').attributes('disabled')).toBeUndefined()

    const reverseCopy = deferred<{ success: true; data: Record<string, string> }>()
    const reverseExport = deferred<{ success: true; data: Blob }>()
    mocks.copyRecord.mockReturnValue(reverseCopy.promise)
    mocks.exportRecords.mockReturnValue(reverseExport.promise)
    await wrapper.get('[data-testid="export-selected-records"]').trigger('click')
    await wrapper.get('[data-testid="copy-record-ct-1"]').trigger('click')
    const reverseCopyPromise = confirm.mock.calls[1][0].onOk?.()
    reverseCopy.resolve({
      success: true,
      data: {
        visit_id: 'CUSTOMER_TEST_COPY_2',
        patient_id: 'CUSTOMER_PATIENT_COPY_2',
        source_item_id: 'ct-1',
        source_updated_at: '2026-09-27T08:00:00.123456',
        bundle_status: 'ready',
      },
    })
    await reverseCopyPromise
    reverseExport.resolve({ success: true, data: new Blob(['xlsx']) })
    await flushPromises()
    expect(wrapper.get('[data-testid="export-selected-records"]').attributes('disabled')).toBeUndefined()
    expect(wrapper.get('[data-testid="copy-record-ct-1"]').attributes('disabled')).toBeUndefined()
    wrapper.unmount()
  })
})
