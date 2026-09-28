import { defineComponent, nextTick } from 'vue'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  downloadTemplate: vi.fn(), importDefinitions: vi.fn(), downloadBlob: vi.fn(),
  success: vi.fn(), error: vi.fn(), warning: vi.fn(),
  authStore: null as null | { user: { id: string } | null; userRoles: string[] },
}))

vi.mock('@/api/documentDefinitions', () => ({
  DOCUMENT_DEFINITION_IMPORT_MAX_BYTES: 2 * 1024 * 1024,
  DOCUMENT_DEFINITION_IMPORT_TEMPLATE_FILENAME: 'V3.6-document-definition-import-template.xlsx',
  downloadDocumentDefinitionImportTemplate: mocks.downloadTemplate,
  importDocumentDefinitions: mocks.importDefinitions,
}))
vi.mock('@/views/workstation-v4/customer-sample-validation/batchExport', () => ({ downloadBlob: mocks.downloadBlob }))
vi.mock('ant-design-vue', () => ({ message: { success: mocks.success, error: mocks.error, warning: mocks.warning } }))
vi.mock('@/stores/auth', async () => {
  const { reactive } = await import('vue')
  return {
    useAuthStore: () => {
      if (!mocks.authStore) mocks.authStore = reactive({ user: { id: 'user-1' }, userRoles: ['admin'] })
      return mocks.authStore
    },
  }
})

import DocumentDefinitionImportDrawer from '@/views/document-definitions/components/DocumentDefinitionImportDrawer.vue'

const DrawerStub = defineComponent({
  props: { open: Boolean }, emits: ['close'],
  template: '<section v-if="open"><slot/><footer><slot name="footer"/></footer></section>',
})
const ButtonStub = defineComponent({
  props: { disabled: Boolean, loading: Boolean },
  emits: ['click'],
  template: '<button :disabled="disabled || loading" @click="$emit(\'click\')"><slot name="icon"/><slot/></button>',
})
const AlertStub = defineComponent({
  props: { message: String, description: String },
  template: '<div><strong>{{ message }}</strong><span>{{ description }}</span></div>',
})
const global = { stubs: { 'a-drawer': DrawerStub, 'a-button': ButtonStub, 'a-alert': AlertStub } }

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => { resolve = done })
  return { promise, resolve }
}

function importSuccess() {
  return { success: true as const, resultUnknown: false as const, problems: [] as [], data: {
    import_batch_id: 'batch-1', imported_count: 1, items: [],
  } }
}

async function chooseFile(wrapper: VueWrapper, name = 'definitions.xlsx') {
  const input = wrapper.get('[data-testid="definition-import-file"]')
  Object.defineProperty(input.element, 'files', { value: [new File(['xlsx'], name)], configurable: true })
  await input.trigger('change')
}

describe('DocumentDefinitionImportDrawer', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    mocks.authStore = null
    mocks.downloadTemplate.mockResolvedValue({ success: true, data: new Blob(['xlsx']) })
    mocks.importDefinitions.mockResolvedValue(importSuccess())
  })

  it('下载固定模板并只在确认成功后发出 imported', async () => {
    const wrapper = mount(DocumentDefinitionImportDrawer, { props: { open: true }, global })
    await wrapper.get('[data-testid="definition-template-download"]').trigger('click')
    await chooseFile(wrapper)
    await wrapper.get('[data-testid="definition-import-submit"]').trigger('click')
    await flushPromises()
    expect(mocks.downloadBlob).toHaveBeenCalledWith(expect.any(Blob), 'V3.6-document-definition-import-template.xlsx')
    expect(wrapper.emitted('imported')).toHaveLength(1)
    expect(wrapper.text()).toContain('成功导入 1 条')
  })

  it('展示逐行问题且失败时不刷新父列表，row=0 显示文件', async () => {
    mocks.importDefinitions.mockResolvedValueOnce({
      success: false, message: '模板校验失败', resultUnknown: false,
      problems: [
        { sheet: '文书定义', row: 3, field: '文书编码', code: 'duplicate', message: '编码重复' },
        { sheet: '文书定义', row: 0, field: '工作表', code: 'missing_sheet', message: '缺少工作表' },
      ],
    })
    const wrapper = mount(DocumentDefinitionImportDrawer, { props: { open: true }, global })
    await chooseFile(wrapper)
    await wrapper.get('[data-testid="definition-import-submit"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('文书定义 第 3 行')
    expect(wrapper.text()).toContain('文书定义 文件')
    expect(wrapper.text()).toContain('编码重复')
    expect(wrapper.emitted('imported')).toBeUndefined()
  })

  it('关闭后重新打开会清理旧文件、错误和成功状态', async () => {
    const wrapper = mount(DocumentDefinitionImportDrawer, { props: { open: true }, global })
    await chooseFile(wrapper)
    await wrapper.get('[data-testid="definition-import-submit"]').trigger('click')
    await flushPromises()
    await wrapper.setProps({ open: false })
    await wrapper.setProps({ open: true })
    expect(wrapper.text()).toContain('请选择填写完成的 .xlsx 模板')
    expect(wrapper.text()).not.toContain('成功导入 1 条')
    expect(wrapper.get('[data-testid="definition-import-submit"]').attributes('disabled')).toBeDefined()
  })

  it('模板下载与导入并发时各自收口，不互相卡住', async () => {
    const downloadPending = deferred<{ success: true; data: Blob }>()
    const importPending = deferred<ReturnType<typeof importSuccess>>()
    mocks.downloadTemplate.mockReturnValueOnce(downloadPending.promise)
    mocks.importDefinitions.mockReturnValueOnce(importPending.promise)
    const wrapper = mount(DocumentDefinitionImportDrawer, { props: { open: true }, global })
    await wrapper.get('[data-testid="definition-template-download"]').trigger('click')
    await chooseFile(wrapper)
    await wrapper.get('[data-testid="definition-import-submit"]').trigger('click')
    importPending.resolve(importSuccess())
    downloadPending.resolve({ success: true, data: new Blob(['xlsx']) })
    await flushPromises()
    expect(wrapper.emitted('imported')).toHaveLength(1)
    expect(mocks.downloadBlob).toHaveBeenCalledOnce()
    expect(wrapper.findAll('button').every((button) => button.attributes('disabled') === undefined || button.text().includes('开始导入'))).toBe(true)
  })

  it('账号或角色变化后丢弃在途成功回执', async () => {
    const pending = deferred<ReturnType<typeof importSuccess>>()
    mocks.importDefinitions.mockReturnValueOnce(pending.promise)
    const wrapper = mount(DocumentDefinitionImportDrawer, { props: { open: true }, global })
    await chooseFile(wrapper)
    await wrapper.get('[data-testid="definition-import-submit"]').trigger('click')
    if (!mocks.authStore) throw new Error('auth store missing')
    mocks.authStore.user = { id: 'user-2' }
    await nextTick()
    pending.resolve(importSuccess())
    await flushPromises()
    expect(wrapper.emitted('imported')).toBeUndefined()
    expect(mocks.success).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('请选择填写完成的 .xlsx 模板')
  })

  it('卸载后不处理迟到导入回执', async () => {
    const pending = deferred<ReturnType<typeof importSuccess>>()
    mocks.importDefinitions.mockReturnValueOnce(pending.promise)
    const wrapper = mount(DocumentDefinitionImportDrawer, { props: { open: true }, global })
    await chooseFile(wrapper)
    await wrapper.get('[data-testid="definition-import-submit"]').trigger('click')
    wrapper.unmount()
    pending.resolve(importSuccess())
    await flushPromises()
    expect(mocks.success).not.toHaveBeenCalled()
  })
})
