import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  list: vi.fn(), remove: vi.fn(), publish: vi.fn(), push: vi.fn(),
}))

vi.mock('vue-router', () => ({ useRouter: () => ({ push: mocks.push }) }))
vi.mock('@/services/custom-rule-workspace-service', () => ({
  listWorkspaceDrafts: mocks.list,
  deleteWorkspaceDraftChecked: mocks.remove,
  publishWorkspaceDraftsBatch: mocks.publish,
}))

import CustomDraftPointsPanel from '../CustomDraftPointsPanel.vue'

function draft(id: string, overrides: Record<string, unknown> = {}) {
  return {
    id, rule_code: `LXE-${id}`, name: `草稿${id}`, category: '诊疗规范', rule_type: '完整性',
    document_type: '入院记录', status: 'draft', updated_at: `2026-09-30T0${id}:00:00`,
    check_logic: { basic_info: { version: 1 } }, last_test_summary: { validation_id: `v-${id}` },
    publish_ready: true, publish_blocked_reason: null,
    ...overrides,
  }
}

function listOf(items: unknown[]) {
  return { success: true, data: { items, total: items.length, page: 1, page_size: 20 } }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => { resolve = done })
  return { promise, resolve }
}

const stubs = {
  'a-alert': { props: ['message', 'description'], template: '<div class="alert">{{ message }} {{ description }}</div>' },
  'a-tag': { template: '<span class="tag"><slot /></span>' },
  'a-popconfirm': { emits: ['confirm'], template: '<span><slot /><button class="pop-ok" @click="$emit(\'confirm\')">确认</button></span>' },
}

function render(props: { actorKey?: string; canManage?: boolean } = {}) {
  return mount(CustomDraftPointsPanel, {
    props: { actorKey: 'manager-1|qc_manager', canManage: true, ...props },
    global: { stubs },
  })
}

async function confirmBatch(wrapper: ReturnType<typeof render>) {
  await wrapper.get('[data-testid="custom-draft-batch-publish"]').element.parentElement!
    .querySelector<HTMLButtonElement>('.pop-ok')!.click()
  await flushPromises()
}

describe('CustomDraftPointsPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.list.mockResolvedValue(listOf([
      draft('1'),
      draft('2', { publish_ready: false, publish_blocked_reason: 'draft_changed' }),
      draft('3', { publish_ready: undefined }),
    ]))
  })

  it('只读取本人未上线草稿，仅有可上线证明的草稿可选', async () => {
    const wrapper = render()
    await flushPromises()
    expect(mocks.list).toHaveBeenCalledWith({ status: 'draft', page: 1, page_size: 20 })
    expect(wrapper.get('[data-testid="custom-draft-select-1"]').attributes('disabled')).toBeUndefined()
    expect(wrapper.get('[data-testid="custom-draft-select-2"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-testid="custom-draft-select-3"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('tr[data-id="2"]').text()).toContain('草稿已修改，需重测')
    expect(wrapper.get('tr[data-id="3"]').text()).toContain('未知')
    expect(wrapper.get('[data-testid="custom-draft-batch-publish"]').attributes('disabled')).toBeDefined()
  })

  it('批量上线提交每项版本与测试证明，成功后回读列表', async () => {
    mocks.list
      .mockResolvedValueOnce(listOf([draft('1'), draft('4')]))
      .mockResolvedValueOnce(listOf([]))
    mocks.publish.mockResolvedValue({
      success: true, resultUnknown: false, conflict: false,
      data: [
        { draft_id: '1', rule_code: 'LXE-1', published_rule_id: 'r1', status: 'published' },
        { draft_id: '4', rule_code: 'LXE-4', published_rule_id: 'r4', status: 'published' },
      ],
    })
    const wrapper = render()
    await flushPromises()
    await wrapper.get('[data-testid="custom-draft-select-1"]').trigger('change')
    await wrapper.get('[data-testid="custom-draft-select-4"]').trigger('change')
    await confirmBatch(wrapper)
    expect(mocks.publish).toHaveBeenCalledWith([
      { draft_id: '1', expected_updated_at: '2026-09-30T01:00:00', validation_id: 'v-1' },
      { draft_id: '4', expected_updated_at: '2026-09-30T04:00:00', validation_id: 'v-4' },
    ])
    expect(mocks.list).toHaveBeenCalledTimes(2)
    expect(wrapper.get('[data-testid="custom-draft-notice"]').text()).toContain('LXE-1、LXE-4')
  })

  it('批量上线被拒绝时提示整批未上线并刷新', async () => {
    mocks.publish.mockResolvedValue({
      success: false, resultUnknown: false, conflict: true, message: '草稿 1：草稿或测试证明已更新，请刷新后重试',
    })
    const wrapper = render()
    await flushPromises()
    await wrapper.get('[data-testid="custom-draft-select-1"]').trigger('change')
    await confirmBatch(wrapper)
    expect(wrapper.get('[data-testid="custom-draft-notice"]').text()).toContain('草稿 1')
    expect(mocks.list).toHaveBeenCalledTimes(2)
  })

  it('批量上线结果未知时锁定写操作且不自动重试', async () => {
    mocks.publish.mockResolvedValue({
      success: false, resultUnknown: true, conflict: false, message: '批量上线结果无法确认',
    })
    const wrapper = render()
    await flushPromises()
    await wrapper.get('[data-testid="custom-draft-select-1"]').trigger('change')
    await confirmBatch(wrapper)
    expect(wrapper.find('[data-testid="custom-draft-result-unknown"]').exists()).toBe(true)
    expect(mocks.list).toHaveBeenCalledTimes(1)
    expect(wrapper.get('[data-testid="custom-draft-delete-1"]').attributes('disabled')).toBeDefined()
    await confirmBatch(wrapper)
    expect(mocks.publish).toHaveBeenCalledTimes(1)
    await wrapper.get('[data-testid="custom-draft-refresh"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="custom-draft-result-unknown"]').exists()).toBe(false)
  })

  it('删除按草稿版本 CAS 提交并回读', async () => {
    mocks.remove.mockResolvedValue({ success: true, resultUnknown: false, conflict: false })
    const wrapper = render()
    await flushPromises()
    await wrapper.get('[data-testid="custom-draft-delete-2"]').element.parentElement!
      .querySelector<HTMLButtonElement>('.pop-ok')!.click()
    await flushPromises()
    expect(mocks.remove).toHaveBeenCalledWith('2', '2026-09-30T02:00:00')
    expect(mocks.list).toHaveBeenCalledTimes(2)
    expect(wrapper.get('[data-testid="custom-draft-notice"]').text()).toContain('LXE-2 已删除')
  })

  it('查看编辑跳转到新建页并携带草稿ID', async () => {
    const wrapper = render()
    await flushPromises()
    await wrapper.get('[data-testid="custom-draft-open-1"]').trigger('click')
    expect(mocks.push).toHaveBeenCalledWith({ path: '/dashboard/quality-control/create', query: { draftId: '1' } })
  })

  it('无管理权限时只读，不显示选择、删除与批量上线', async () => {
    const wrapper = render({ canManage: false })
    await flushPromises()
    expect(wrapper.find('[data-testid="custom-draft-select-1"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="custom-draft-delete-1"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="custom-draft-batch-publish"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="custom-draft-open-1"]').text()).toBe('查看')
  })

  it('切换操作人后丢弃旧账号的迟到列表响应', async () => {
    const stale = deferred<ReturnType<typeof listOf>>()
    mocks.list.mockReset()
    mocks.list
      .mockReturnValueOnce(stale.promise)
      .mockResolvedValueOnce(listOf([draft('9')]))
    const wrapper = render()
    await flushPromises()
    await wrapper.setProps({ actorKey: 'manager-2|qc_manager' })
    await flushPromises()
    stale.resolve(listOf([draft('1')]))
    await flushPromises()
    expect(wrapper.find('tr[data-id="1"]').exists()).toBe(false)
    expect(wrapper.find('tr[data-id="9"]').exists()).toBe(true)
  })
})
