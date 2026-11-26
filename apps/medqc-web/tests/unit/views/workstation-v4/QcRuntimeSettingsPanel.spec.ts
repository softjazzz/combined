import { flushPromises, mount } from '@vue/test-utils'
import { reactive } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Panel from '@/views/workstation-v4/components/system-config/QcRuntimeSettingsPanel.vue'
import type { QcRuntimeSettings } from '@/api/qcRuntimeSettings'

const api = vi.hoisted(() => ({ get: vi.fn(), check: vi.fn(), save: vi.fn() }))
const auth = reactive({ user: { id: 'admin-a', is_demo_account: false }, userRoles: ['sync_admin'] })
vi.mock('@/stores/auth', () => ({ useAuthStore: () => auth }))
vi.mock('@/api/qcRuntimeSettings', () => ({
  getQcRuntimeSettings: api.get, checkQcRuntimeSettings: api.check, saveQcRuntimeSettings: api.save,
}))
function config(enabled = false): QcRuntimeSettings {
  return { rabbitmq_enabled: enabled, effective_mode: enabled ? 'rabbitmq' : 'legacy', source: 'file', revision: 2,
    updated_at: null, readiness: { ready: false, gateway_checked: false, checks: {
      broker_config: false, gateway_config: false, publisher: false, worker: false, gateway: false,
    } } }
}
function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej })
  return { promise, resolve, reject }
}
const button = (wrapper: ReturnType<typeof mount>, text: string) => wrapper.findAll('button').find((item) => item.text() === text)!

describe('质控运行设置', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    auth.user.id = 'admin-a'
    auth.user.is_demo_account = false
    auth.userRoles = ['sync_admin']
    api.get.mockResolvedValue(config())
  })

  it('未启用MQ显示Web执行，修改草稿不改变生效值', async () => {
    const wrapper = mount(Panel)
    await flushPromises()
    expect(wrapper.get('[data-testid="effective-mode"]').text()).toContain('Web 后端')
    expect(wrapper.text()).toContain('未检查')
    await wrapper.get('input').setValue(true)
    expect(api.save).not.toHaveBeenCalled()
    expect(wrapper.get('[data-testid="effective-mode"]').text()).toContain('Web 后端')
    wrapper.unmount()
  })

  it('保存成功更新执行模式及版本，关闭可正常保存', async () => {
    const wrapper = mount(Panel)
    await flushPromises()
    api.save.mockResolvedValue(config(true))
    await wrapper.get('input').setValue(true)
    await button(wrapper, '保存设置').trigger('click')
    await flushPromises()
    expect(api.save).toHaveBeenCalledWith(true, 2, expect.any(AbortSignal))
    expect(wrapper.get('[data-testid="effective-mode"]').text()).toContain('独立 Worker')
    expect(wrapper.text()).toContain('已保存，仅影响新建任务')
    api.save.mockResolvedValue(config(false))
    await wrapper.get('input').setValue(false)
    await button(wrapper, '保存设置').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="effective-mode"]').text()).toContain('Web 后端')
    wrapper.unmount()
  })

  it('服务检查不通过和保存失败不伪装开启，loading恢复', async () => {
    const wrapper = mount(Panel)
    await flushPromises()
    api.check.mockResolvedValue(config())
    await button(wrapper, '检查配套服务').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('尚未全部就绪')
    api.save.mockRejectedValue(new Error('private-connection-detail'))
    await wrapper.get('input').setValue(true)
    await button(wrapper, '保存设置').trigger('click')
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('未保存')
    expect(wrapper.text()).not.toContain('private-connection-detail')
    expect((wrapper.get('input').element as HTMLInputElement).checked).toBe(false)
    expect(button(wrapper, '刷新配置').attributes('disabled')).toBeUndefined()
    wrapper.unmount()
  })

  it('读取失败不提供可保存的默认关闭值', async () => {
    api.get.mockRejectedValue(new Error('unavailable'))
    const wrapper = mount(Panel)
    await flushPromises()
    expect(wrapper.find('input').exists()).toBe(false)
    expect(wrapper.find('[role="alert"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('切换账号后旧成功或失败不能污染新账号', async () => {
    const old = deferred<QcRuntimeSettings>()
    api.get.mockReturnValueOnce(old.promise)
    const wrapper = mount(Panel)
    auth.user.id = 'admin-b'
    await flushPromises()
    old.resolve(config(true))
    await flushPromises()
    expect(wrapper.get('[data-testid="effective-mode"]').text()).toContain('Web 后端')
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('撤销权限或卸载使请求失效并取消，不提交任何设置', async () => {
    const old = deferred<QcRuntimeSettings>()
    api.get.mockReturnValueOnce(old.promise)
    const wrapper = mount(Panel)
    const signal: AbortSignal = api.get.mock.calls[0][0]
    auth.userRoles = ['doctor']
    await flushPromises()
    expect(signal.aborted).toBe(true)
    old.reject(new Error('old-failure'))
    await flushPromises()
    expect(wrapper.find('input').exists()).toBe(false)
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    wrapper.unmount()
    expect(api.save).not.toHaveBeenCalled()
  })

  it('检查配套服务不覆盖未保存的开关，未检查不标红，409冲突刷新就绪状态', async () => {
    const wrapper = mount(Panel)
    await flushPromises()

    const uncheckedSpan = wrapper.findAll('li span').find((el) => el.text() === '未检查')
    expect(uncheckedSpan).toBeTruthy()
    expect(uncheckedSpan?.classes()).not.toContain('runtime-error')

    await wrapper.get('input').setValue(true)
    api.check.mockResolvedValueOnce({
      ...config(false),
      readiness: {
        ready: false,
        gateway_checked: true,
        checks: {
          broker_config: true,
          gateway_config: true,
          publisher: true,
          worker: false,
          gateway: true,
        },
      },
    })
    await button(wrapper, '检查配套服务').trigger('click')
    await flushPromises()
    expect((wrapper.get('input').element as HTMLInputElement).checked).toBe(true)

    api.save.mockRejectedValueOnce({
      isAxiosError: true,
      response: {
        status: 409,
        data: {
          detail: {
            message: '配套服务未就绪',
            readiness: {
              ready: false,
              gateway_checked: true,
              checks: {
                broker_config: true,
                gateway_config: true,
                publisher: true,
                worker: true,
                gateway: false,
              },
            },
          },
        },
      },
    })
    await button(wrapper, '保存设置').trigger('click')
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('未保存')
    const gatewayItem = wrapper.findAll('li').find((li) => li.text().includes('Gateway 健康及授权'))
    expect(gatewayItem?.text()).toContain('未就绪')
    wrapper.unmount()
  })
})
