import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, ref } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import RuntimeBuildStatus from '@/components/layout/RuntimeBuildStatus.vue'
import {
  fetchRuntimeBuild,
  getFrontendBuildIdentity,
  type RuntimeBuildResult,
} from '@/services/runtime-build-service'

vi.mock('@/services/runtime-build-service', async (original) => ({
  ...(await original<typeof import('@/services/runtime-build-service')>()),
  fetchRuntimeBuild: vi.fn(),
  getFrontendBuildIdentity: vi.fn(),
}))
vi.mock('@/services/apiService', () => ({ apiClient: { get: vi.fn() } }))

const ready: RuntimeBuildResult = {
  kind: 'ready',
  data: {
    available: true,
    build_id: 'customer-20260909-160657',
    git_commit: 'commit-one',
    started_at: '2026-09-09T08:00:00Z',
    pid: 123,
  },
}
const PopoverStub = defineComponent({
  setup() {
    return { open: ref(false) }
  },
  template:
    '<div><div @click="open = !open"><slot /></div><div v-if="open"><slot name="content" /></div></div>',
})
const ButtonStub = defineComponent({
  props: { loading: Boolean },
  template: '<button :disabled="loading"><slot /></button>',
})
const wrappers: ReturnType<typeof mount>[] = []
function render() {
  const wrapper = mount(RuntimeBuildStatus, {
    global: { stubs: { APopover: PopoverStub, AButton: ButtonStub } },
  })
  wrappers.push(wrapper)
  return wrapper
}
beforeEach(() => {
  vi.useFakeTimers()
  vi.mocked(getFrontendBuildIdentity).mockReturnValue({
    development: false,
    buildId: 'customer-20260909-160657',
    gitCommit: 'commit-one',
  })
  vi.mocked(fetchRuntimeBuild).mockResolvedValue(ready)
  vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible')
})
afterEach(() => {
  wrappers.splice(0).forEach((wrapper) => wrapper.unmount())
  vi.restoreAllMocks()
})

describe('头部运行版本状态', () => {
  it('显示短构建号，点击展开完整版本和本地启动时间，手动刷新替换PID', async () => {
    const wrapper = render()
    await flushPromises()
    expect(wrapper.get('.runtime-build-status').text()).toContain('版本一致')
    expect(wrapper.get('.runtime-build-short').text()).toBe('20260909-160657')
    await wrapper.get('.runtime-build-status').trigger('click')
    expect(wrapper.text()).toContain('customer-20260909-160657')
    expect(wrapper.text()).toContain('PID 123')
    expect(wrapper.text()).toContain(
      new Date('2026-09-09T08:00:00Z').toLocaleString('zh-CN', { hour12: false }),
    )
    vi.mocked(fetchRuntimeBuild).mockResolvedValue({
      kind: 'ready',
      data: { ...ready.data, pid: 456 },
    })
    await wrapper.get('.runtime-build-details button').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('PID 456')
    expect(wrapper.text()).not.toContain('PID 123')
  })
  it('错误或不一致替换之前的绿灯，开发环境永不显示一致', async () => {
    const wrapper = render()
    await flushPromises()
    vi.mocked(fetchRuntimeBuild).mockResolvedValue({
      kind: 'connection_error',
      message: '无法连接后端',
    })
    await vi.advanceTimersByTimeAsync(60000)
    expect(wrapper.get('.runtime-build-status').classes()).not.toContain('is-matching')
    expect(wrapper.text()).toContain('连接失败')
    vi.mocked(fetchRuntimeBuild).mockResolvedValue({
      kind: 'ready',
      data: { ...ready.data, git_commit: 'other' },
    })
    await vi.advanceTimersByTimeAsync(60000)
    expect(wrapper.get('.runtime-build-status').classes()).toContain('is-mismatch')
    vi.mocked(getFrontendBuildIdentity).mockReturnValue({
      development: true,
      buildId: null,
      gitCommit: null,
    })
    const dev = render()
    await flushPromises()
    expect(dev.text()).toContain('开发环境')
    expect(dev.text()).not.toContain('版本一致')
  })
  it('只在可见时轮询，恢复可见刷新，卸载清理监听和计时器', async () => {
    const wrapper = render()
    await flushPromises()
    vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('hidden')
    await vi.advanceTimersByTimeAsync(60000)
    expect(fetchRuntimeBuild).toHaveBeenCalledTimes(1)
    vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible')
    document.dispatchEvent(new Event('visibilitychange'))
    await flushPromises()
    expect(fetchRuntimeBuild).toHaveBeenCalledTimes(2)
    wrapper.unmount()
    document.dispatchEvent(new Event('visibilitychange'))
    await vi.advanceTimersByTimeAsync(120000)
    expect(fetchRuntimeBuild).toHaveBeenCalledTimes(2)
    expect(vi.getTimerCount()).toBe(0)
  })
  it('请求未完成时不并发，卸载后的响应不再发起刷新', async () => {
    let resolve: (result: RuntimeBuildResult) => void = () => undefined
    vi.mocked(fetchRuntimeBuild).mockReturnValue(
      new Promise((done) => {
        resolve = done
      }),
    )
    const wrapper = render()
    document.dispatchEvent(new Event('visibilitychange'))
    await vi.advanceTimersByTimeAsync(120000)
    expect(fetchRuntimeBuild).toHaveBeenCalledTimes(1)
    wrapper.unmount()
    resolve(ready)
    await flushPromises()
    await vi.advanceTimersByTimeAsync(120000)
    expect(fetchRuntimeBuild).toHaveBeenCalledTimes(1)
  })
})
