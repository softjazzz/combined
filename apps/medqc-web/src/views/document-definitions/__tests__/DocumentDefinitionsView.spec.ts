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
const InputStub = defineComponent({
  props: { value: String, maxlength: Number },
  emits: ['update:value', 'pressEnter'],
  template: '<input :value="value" :maxlength="maxlength" @input="$emit(\'update:value\', $event.target.value)" @keyup.enter="$emit(\'pressEnter\')" />',
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
    'a-button': ButtonStub, 'a-input': InputStub, 'a-alert': true, 'a-spin': SpinStub, 'a-pagination': PaginationStub,
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

  it('名称草稿仅在查询时应用，翻页保持已应用查询，重置回第一页', async () => {
    mocks.listDefinitions
      .mockResolvedValueOnce(page())
      .mockResolvedValueOnce(page([{ ...definition, id: 'matched' }]))
      .mockResolvedValueOnce(page([], { total: 21, page: 2 }))
      .mockResolvedValueOnce(page([], { total: 21, page: 1 }))
      .mockResolvedValueOnce(page([], { total: 0 }))
    const wrapper = mount(DocumentDefinitionsView, { global })
    await flushPromises()
    const input = wrapper.get('[data-testid="definition-name-query"]')
    await input.setValue('  入院记录  ')
    expect(mocks.listDefinitions).toHaveBeenCalledOnce()
    await wrapper.get('[data-testid="definition-search"]').trigger('click')
    await flushPromises()
    expect(mocks.listDefinitions).toHaveBeenNthCalledWith(2, { page: 1, page_size: 20, q: '入院记录' })

    await input.setValue('正在编辑但未应用')
    await wrapper.get('[data-testid="next-page"]').trigger('click')
    await flushPromises()
    expect(mocks.listDefinitions).toHaveBeenNthCalledWith(3, { page: 2, page_size: 20, q: '入院记录' })

    await wrapper.get('[data-testid="definition-import-open"]').trigger('click')
    await wrapper.get('[data-testid="complete-import"]').trigger('click')
    await flushPromises()
    expect(mocks.listDefinitions).toHaveBeenNthCalledWith(4, { page: 1, page_size: 20, q: '入院记录' })

    await wrapper.get('[data-testid="definition-search-reset"]').trigger('click')
    await flushPromises()
    expect(mocks.listDefinitions).toHaveBeenNthCalledWith(5, { page: 1, page_size: 20 })
  })

  it('已应用名称没有结果时不误报为空库', async () => {
    mocks.listDefinitions.mockResolvedValueOnce(page()).mockResolvedValueOnce(page([], { total: 0 }))
    const wrapper = mount(DocumentDefinitionsView, { global })
    await flushPromises()
    await wrapper.get('[data-testid="definition-name-query"]').setValue('不存在的名称')
    await wrapper.get('[data-testid="definition-search"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('未找到匹配的文书定义')
    expect(wrapper.text()).not.toContain('暂无已导入')
  })

  it('回车查询且旧查询迟到时不能覆盖新查询结果', async () => {
    const oldSearch = deferred<ReturnType<typeof page>>()
    const newSearch = deferred<ReturnType<typeof page>>()
    mocks.listDefinitions
      .mockResolvedValueOnce(page())
      .mockReturnValueOnce(oldSearch.promise)
      .mockReturnValueOnce(newSearch.promise)
    const wrapper = mount(DocumentDefinitionsView, { global })
    await flushPromises()
    const input = wrapper.get('[data-testid="definition-name-query"]')
    await input.setValue('旧名称')
    await input.trigger('keyup.enter')
    await input.setValue('新名称')
    await input.trigger('keyup.enter')
    newSearch.resolve(page([{ ...definition, id: 'new-query', code: 'DOC-NEW' }], { total: 1 }))
    await flushPromises()
    oldSearch.resolve(page([{ ...definition, id: 'old-query', code: 'DOC-OLD' }], { total: 1 }))
    await flushPromises()
    expect(mocks.listDefinitions).toHaveBeenNthCalledWith(2, { page: 1, page_size: 20, q: '旧名称' })
    expect(mocks.listDefinitions).toHaveBeenNthCalledWith(3, { page: 1, page_size: 20, q: '新名称' })
    expect(wrapper.text()).toContain('DOC-NEW')
    expect(wrapper.text()).not.toContain('DOC-OLD')
  })

  it('超过 200 字符明确拒绝且不发请求', async () => {
    const wrapper = mount(DocumentDefinitionsView, { global })
    await flushPromises()
    await wrapper.get('[data-testid="definition-name-query"]').setValue('病'.repeat(201))
    await wrapper.get('[data-testid="definition-search"]').trigger('click')
    expect(mocks.listDefinitions).toHaveBeenCalledOnce()
    expect(wrapper.get('[data-testid="definition-list-error"]').text()).toContain('200')
    expect(wrapper.find('[data-testid="definition-total"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('DOC-001')
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
    expect(wrapper.get('[data-testid="definition-name-query"]').element).toHaveProperty('value', '')
    expect(wrapper.text()).toContain('DOC-NEW')
    expect(wrapper.text()).not.toContain('DOC-OLD')
  })

  it('账号切换清空草稿和已应用名称，新账号请求不继承旧查询', async () => {
    mocks.listDefinitions
      .mockResolvedValueOnce(page())
      .mockResolvedValueOnce(page([{ ...definition, id: 'searched' }]))
      .mockResolvedValueOnce(page([{ ...definition, id: 'new-actor' }]))
    const wrapper = mount(DocumentDefinitionsView, { global })
    await flushPromises()
    const input = wrapper.get('[data-testid="definition-name-query"]')
    await input.setValue('入院记录')
    await wrapper.get('[data-testid="definition-search"]').trigger('click')
    await flushPromises()
    if (!mocks.authStore) throw new Error('auth store missing')
    mocks.authStore.user = { id: 'admin-2' }
    await nextTick()
    await flushPromises()
    expect(mocks.listDefinitions).toHaveBeenNthCalledWith(2, { page: 1, page_size: 20, q: '入院记录' })
    expect(mocks.listDefinitions).toHaveBeenNthCalledWith(3, { page: 1, page_size: 20 })
    expect(input.element).toHaveProperty('value', '')
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
