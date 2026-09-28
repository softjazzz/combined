import { defineComponent, nextTick, reactive } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  listDefinitions: vi.fn(),
  authStore: null as null | { user: { id: string } | null; userRoles: string[] },
}))

vi.mock('@/api/documentDefinitions', () => ({ listDocumentDefinitions: mocks.listDefinitions }))
vi.mock('@/stores/auth', async () => {
  const { reactive } = await import('vue')
  return {
    useAuthStore: () => {
      if (!mocks.authStore) mocks.authStore = reactive({ user: { id: 'admin-1' }, userRoles: ['admin'] })
      return mocks.authStore
    },
  }
})

import DocumentDefinitionsView from '@/views/document-definitions/DocumentDefinitionsView.vue'

const definition = {
  id: 'definition-1', code: 'DOC-001', name: '入院记录', category: '住院文书',
  template_content: '  <img src=x onerror=alert(1)>\n主诉：  ', import_batch_id: 'batch-1',
  created_by: 'admin-1', created_at: '2026-09-28T12:00:00Z',
}

const ButtonStub = defineComponent({
  props: { disabled: Boolean }, emits: ['click'],
  template: '<button :disabled="disabled" @click="$emit(\'click\')"><slot name="icon"/><slot/></button>',
})
const SpinStub = defineComponent({ props: { spinning: Boolean }, template: '<div><span v-if="spinning">读取中</span><slot/></div>' })
const PaginationStub = defineComponent({
  props: { current: Number, total: Number, pageSize: Number }, emits: ['change'],
  template: '<button data-testid="next-page" @click="$emit(\'change\', 2)">下一页</button>',
})
const DrawerStub = defineComponent({
  props: { open: Boolean }, emits: ['close', 'imported'],
  template: '<div><button v-if="open" data-testid="complete-import" @click="$emit(\'imported\')">完成导入</button></div>',
})
const global = {
  stubs: {
    'a-button': ButtonStub, 'a-alert': true, 'a-spin': SpinStub, 'a-pagination': PaginationStub,
    DocumentDefinitionImportDrawer: DrawerStub,
  },
}

function page(items = [definition], overrides: Partial<{ total: number; page: number; page_size: number }> = {}) {
  return { success: true as const, data: { items, total: 21, page: 1, page_size: 20, ...overrides } }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => { resolve = done })
  return { promise, resolve }
}

describe('DocumentDefinitionsView', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    mocks.authStore = null
    mocks.listDefinitions.mockResolvedValue(page())
  })

  it('展示可信总数和正式定义，模板内容仅作为文本且保留空白', async () => {
    const wrapper = mount(DocumentDefinitionsView, { global })
    await flushPromises()
    expect(wrapper.get('[data-testid="definition-total"]').text()).toContain('21')
    expect(wrapper.get('[data-testid="definition-row"]').text()).toContain('DOC-001')
    const template = wrapper.get('pre')
    expect(template.text()).toContain('<img src=x onerror=alert(1)>')
    expect(wrapper.find('img').exists()).toBe(false)
    expect(template.element.textContent).toBe(definition.template_content)
  })

  it('失败时不伪造空列表或总数，并可重试', async () => {
    mocks.listDefinitions.mockResolvedValueOnce({ success: false, message: '文书定义服务暂不可用' })
    const wrapper = mount(DocumentDefinitionsView, { global })
    await flushPromises()
    expect(wrapper.get('[data-testid="definition-list-error"]').text()).toContain('暂不可用')
    expect(wrapper.find('[data-testid="definition-total"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('暂无已导入')
  })

  it('分页使用服务端页码，确认导入成功后回第一页重拉', async () => {
    mocks.listDefinitions
      .mockResolvedValueOnce(page())
      .mockResolvedValueOnce(page([{ ...definition, id: 'definition-2', code: 'DOC-002' }], { page: 2 }))
      .mockResolvedValueOnce(page([{ ...definition, id: 'definition-3', code: 'DOC-003' }], { total: 1 }))
    const wrapper = mount(DocumentDefinitionsView, { global })
    await flushPromises()
    await wrapper.get('[data-testid="next-page"]').trigger('click')
    await flushPromises()
    expect(mocks.listDefinitions).toHaveBeenNthCalledWith(2, { page: 2, page_size: 20 })
    await wrapper.get('[data-testid="definition-import-open"]').trigger('click')
    await wrapper.get('[data-testid="complete-import"]').trigger('click')
    await flushPromises()
    expect(mocks.listDefinitions).toHaveBeenNthCalledWith(3, { page: 1, page_size: 20 })
    expect(wrapper.text()).toContain('DOC-003')
  })

  it('同角色切换账号时废弃旧列表并按新账号重读', async () => {
    const oldRequest = deferred<ReturnType<typeof page>>()
    const newRequest = deferred<ReturnType<typeof page>>()
    mocks.listDefinitions.mockReturnValueOnce(oldRequest.promise).mockReturnValueOnce(newRequest.promise)
    const wrapper = mount(DocumentDefinitionsView, { global })
    if (!mocks.authStore) throw new Error('auth store missing')
    mocks.authStore.user = { id: 'admin-2' }
    await nextTick()
    newRequest.resolve(page([{ ...definition, id: 'new', code: 'DOC-NEW' }], { total: 1 }))
    await flushPromises()
    oldRequest.resolve(page([{ ...definition, id: 'old', code: 'DOC-OLD' }], { total: 1 }))
    await flushPromises()
    expect(mocks.listDefinitions).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('DOC-NEW')
    expect(wrapper.text()).not.toContain('DOC-OLD')
  })

  it('无权限账号不请求列表且明确显示无权访问', async () => {
    mocks.authStore = reactive({ user: { id: 'doctor-1' }, userRoles: ['doctor'] })
    const wrapper = mount(DocumentDefinitionsView, { global })
    await flushPromises()
    expect(wrapper.text()).toContain('无权访问文书定义')
    expect(wrapper.find('[data-testid="definition-import-open"]').exists()).toBe(false)
    expect(mocks.listDefinitions).not.toHaveBeenCalled()
  })

  it('卸载后丢弃迟到列表响应', async () => {
    const pending = deferred<ReturnType<typeof page>>()
    mocks.listDefinitions.mockReturnValueOnce(pending.promise)
    const wrapper = mount(DocumentDefinitionsView, { global })
    wrapper.unmount()
    pending.resolve(page())
    await flushPromises()
    expect(wrapper.find('[data-testid="definition-row"]').exists()).toBe(false)
  })
})
