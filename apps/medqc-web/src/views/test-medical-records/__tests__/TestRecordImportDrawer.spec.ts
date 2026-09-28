import { defineComponent } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  downloadTemplate: vi.fn(),
  importRecords: vi.fn(),
  downloadBlob: vi.fn(),
  success: vi.fn(),
  error: vi.fn(),
  warning: vi.fn(),
}))

vi.mock('@/services/test-medical-records', () => ({
  TEST_RECORD_IMPORT_MAX_BYTES: 5 * 1024 * 1024,
  downloadTestRecordImportTemplate: mocks.downloadTemplate,
  importTestRecords: mocks.importRecords,
}))
vi.mock('@/views/workstation-v4/customer-sample-validation/batchExport', () => ({
  downloadBlob: mocks.downloadBlob,
}))
vi.mock('ant-design-vue', () => ({
  message: { success: mocks.success, error: mocks.error, warning: mocks.warning },
}))

import TestRecordImportDrawer from '@/views/test-medical-records/components/TestRecordImportDrawer.vue'

const DrawerStub = defineComponent({
  props: { open: Boolean },
  template: '<section v-if="open"><slot/><footer><slot name="footer"/></footer></section>',
})
const ButtonStub = defineComponent({
  props: { disabled: Boolean, loading: Boolean },
  template: '<button :disabled="disabled || loading"><slot name="icon"/><slot/></button>',
})
const CheckboxStub = defineComponent({
  props: { checked: Boolean, disabled: Boolean },
  emits: ['update:checked'],
  template: '<label><input type="checkbox" :checked="checked" :disabled="disabled" @change="$emit(\'update:checked\', $event.target.checked)"/><slot/></label>',
})
const AlertStub = defineComponent({
  props: { message: String, description: String },
  template: '<div><strong>{{ message }}</strong><span>{{ description }}</span><slot/></div>',
})

const global = {
  stubs: {
    'a-drawer': DrawerStub,
    'a-button': ButtonStub,
    'a-checkbox': CheckboxStub,
    'a-alert': AlertStub,
  },
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((next) => { resolve = next })
  return { promise, resolve }
}

function sampleFile(name = 'records.xlsx', size?: number) {
  const file = new File(['xlsx'], name, {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  })
  if (size !== undefined) Object.defineProperty(file, 'size', { value: size })
  return file
}

async function chooseFile(wrapper: ReturnType<typeof mount>, file: File) {
  const input = wrapper.get('[data-testid="test-record-import-file"]')
  Object.defineProperty(input.element, 'files', { value: [file], configurable: true })
  await input.trigger('change')
}

async function confirmSynthetic(wrapper: ReturnType<typeof mount>) {
  await wrapper
    .get('[data-testid="test-record-import-synthetic-confirmation"] input')
    .setValue(true)
}

function partialResult() {
  return {
    success: true,
    message: '导入完成',
    validationErrors: [],
    resultUnknown: false,
    data: {
      total: 2,
      created: 1,
      unknown: 1,
      results: [
        {
          case_key: 'CASE-1', case_row: 2, document_rows: [2], status: 'created' as const,
          message: '病历已创建', item_id: 'item-1', institute_id: 'CUSTOMER_TEST',
          patient_id: 'patient-1', visit_id: 'visit-1', bundle_status: 'ready',
        },
        {
          case_key: 'CASE-2', case_row: 3, document_rows: [3], status: 'unknown' as const,
          message: '创建结果未知',
        },
      ],
    },
  }
}

describe('测试病历 Excel 导入抽屉', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    mocks.downloadTemplate.mockResolvedValue({ success: true, data: new Blob(['xlsx']) })
    mocks.importRecords.mockResolvedValue(partialResult())
  })

  it('下载 xlsx 模板', async () => {
    const wrapper = mount(TestRecordImportDrawer, { props: { open: true }, global })

    await wrapper.get('[data-testid="test-record-import-template"]').trigger('click')
    await flushPromises()

    expect(mocks.downloadTemplate).toHaveBeenCalledOnce()
    expect(mocks.downloadBlob).toHaveBeenCalledWith(expect.any(Blob), 'V3.6-测试病历导入模板.xlsx')
  })

  it('必须确认合成数据，并展示 created/unknown 逐病例结果', async () => {
    const wrapper = mount(TestRecordImportDrawer, { props: { open: true }, global })
    await chooseFile(wrapper, sampleFile())
    expect(wrapper.get('[data-testid="test-record-import-submit"]').attributes('disabled')).toBeDefined()

    await confirmSynthetic(wrapper)
    await wrapper.get('[data-testid="test-record-import-submit"]').trigger('click')
    await flushPromises()

    expect(mocks.importRecords).toHaveBeenCalledOnce()
    expect(wrapper.get('[data-testid="test-record-import-results"]').text()).toContain('已创建 1 / 2')
    expect(wrapper.get('[data-testid="test-record-import-results"]').text()).toContain('CASE-1')
    expect(wrapper.get('[data-testid="test-record-import-results"]').text()).toContain('结果未知')
    expect(wrapper.emitted('imported')).toHaveLength(1)
    expect(wrapper.get('[data-testid="test-record-import-submit"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-testid="test-record-import-file"]').attributes('disabled')).toBeDefined()
  })

  it('展示 422 的 Sheet、行号、字段错误', async () => {
    mocks.importRecords.mockResolvedValueOnce({
      success: false,
      message: '模板校验失败',
      resultUnknown: false,
      validationErrors: [
        { sheet: '病历', row: 4, field: '入院时间', message: '必须是有效的日期时间' },
      ],
    })
    const wrapper = mount(TestRecordImportDrawer, { props: { open: true }, global })
    await chooseFile(wrapper, sampleFile())
    await confirmSynthetic(wrapper)

    await wrapper.get('[data-testid="test-record-import-submit"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('病历 第 4 行')
    expect(wrapper.text()).toContain('入院时间')
    expect(wrapper.text()).toContain('必须是有效的日期时间')
    expect(wrapper.emitted('imported')).toBeUndefined()
  })

  it('网络结果未知时刷新父列表并锁定重复提交', async () => {
    mocks.importRecords.mockResolvedValueOnce({
      success: false,
      message: '导入请求未获得确认，请勿盲目重试',
      resultUnknown: true,
      validationErrors: [],
    })
    const wrapper = mount(TestRecordImportDrawer, { props: { open: true }, global })
    await chooseFile(wrapper, sampleFile())
    await confirmSynthetic(wrapper)

    await wrapper.get('[data-testid="test-record-import-submit"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="test-record-import-submit"]').trigger('click')

    expect(mocks.importRecords).toHaveBeenCalledOnce()
    expect(wrapper.get('[data-testid="test-record-import-error"]').text()).toContain('导入结果未知')
    expect(wrapper.emitted('imported')).toHaveLength(1)
    expect(wrapper.get('[data-testid="test-record-import-submit"]').attributes('disabled')).toBeDefined()
  })

  it('全部创建成功后同文件不能再次提交', async () => {
    mocks.importRecords.mockResolvedValueOnce({
      success: true,
      message: '导入完成',
      resultUnknown: false,
      validationErrors: [],
      data: {
        total: 1,
        created: 1,
        unknown: 0,
        results: [{
          case_key: 'CASE-1', case_row: 2, document_rows: [2], status: 'created',
          message: '病历已创建', item_id: 'item-1', institute_id: 'CUSTOMER_TEST',
          patient_id: 'patient-1', visit_id: 'visit-1', bundle_status: 'ready',
        }],
      },
    })
    const file = sampleFile()
    const wrapper = mount(TestRecordImportDrawer, { props: { open: true }, global })
    await chooseFile(wrapper, file)
    await confirmSynthetic(wrapper)
    await wrapper.get('[data-testid="test-record-import-submit"]').trigger('click')
    await flushPromises()

    await wrapper.get('[data-testid="test-record-import-submit"]').trigger('click')
    await chooseFile(wrapper, file)

    expect(mocks.importRecords).toHaveBeenCalledOnce()
    expect(mocks.warning).toHaveBeenCalledWith(expect.stringContaining('该文件已提交过'))
    expect(wrapper.find('[data-testid="test-record-import-results"]').exists()).toBe(true)
  })

  it('导入中禁止重复提交和关闭', async () => {
    const pending = deferred<ReturnType<typeof partialResult>>()
    mocks.importRecords.mockReturnValueOnce(pending.promise)
    const wrapper = mount(TestRecordImportDrawer, { props: { open: true }, global })
    await chooseFile(wrapper, sampleFile())
    await confirmSynthetic(wrapper)

    await wrapper.get('[data-testid="test-record-import-submit"]').trigger('click')
    expect(mocks.importRecords).toHaveBeenCalledOnce()
    expect(wrapper.get('[data-testid="test-record-import-submit"]').attributes('disabled')).toBeDefined()
    const close = wrapper.findAll('button').find((button) => button.text() === '关闭')
    expect(close?.attributes('disabled')).toBeDefined()
    expect(wrapper.emitted('close')).toBeUndefined()

    pending.resolve(partialResult())
    await flushPromises()
  })

  it('非 xlsx 和超过 5 MiB 的文件不进入导入请求', async () => {
    const wrapper = mount(TestRecordImportDrawer, { props: { open: true }, global })
    await chooseFile(wrapper, sampleFile('records.xls'))
    expect(wrapper.text()).toContain('仅支持 .xlsx')

    await chooseFile(wrapper, sampleFile('records.xlsx', 5 * 1024 * 1024 + 1))
    expect(wrapper.text()).toContain('文件不能超过 5 MiB')
    expect(mocks.importRecords).not.toHaveBeenCalled()
  })
})
