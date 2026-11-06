import { flushPromises, mount } from '@vue/test-utils'
import { reactive } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import DataPipelineSettingsPanel from '@/views/workstation-v4/components/system-config/DataPipelineSettingsPanel.vue'
import type { DataPipelineConfiguration, IndependentSyncJob } from '@/api/dataPipelines'

const api = vi.hoisted(() => ({
  configuration: vi.fn(),
  save: vi.fn(),
  check: vi.fn(),
  jobs: vi.fn(),
  submit: vi.fn(),
  action: vi.fn(),
}))
vi.mock('@/api/dataPipelines', () => ({ dataPipelinesApi: api }))
const auth = reactive({ user: { id: 'admin' }, userRoles: ['admin'] })
vi.mock('@/stores/auth', () => ({ useAuthStore: () => auth }))

function config(independent = false): DataPipelineConfiguration {
  return {
    settings: {
      version: 1,
      default_pipeline: independent ? 'independent_cdm' : 'legacy_pg',
      independent_enabled: independent,
    },
    runtime: {
      control_configured: true,
      control_profile: 'accepted_manual',
      clinical_read_source: 'business_cdm',
      cdm_url_configured: false,
      read_scope: '已适配Bundle/LX0609；其他入口待验收',
      pdf_source: 'original_business_database',
      automatic_extraction: false,
      automatic_qc: false,
    },
  }
}
const job: IndependentSyncJob = {
  job_id: '00112233-4455-6677-8899-aabbccddeeff',
  status: 'queued',
  counts: {},
  cancel_requested: false,
}
function mountPanel() {
  return mount(DataPipelineSettingsPanel, {
    global: {
      stubs: {
        'a-button': {
          props: ['disabled', 'loading'],
          template: '<button :disabled="disabled"><slot /></button>',
        },
        'a-alert': { props: ['message'], template: '<div role="alert">{{ message }}</div>' },
        'a-select': {
          props: ['value', 'options', 'disabled'],
          emits: ['update:value'],
          template:
            '<select multiple :disabled="disabled" @change="$emit(\'update:value\', Array.from($event.target.selectedOptions).map(o => o.value))"><option v-for="option in options" :key="option.value" :value="option.value" :selected="value.includes(option.value)">{{option.label}}</option></select>',
        },
      },
    },
  })
}
function button(wrapper: ReturnType<typeof mountPanel>, text: string) {
  const result = wrapper.findAll('button').find((item) => item.text().includes(text))
  if (!result) throw new Error(`缺少按钮：${text}`)
  return result
}
async function readyToSubmit(wrapper: ReturnType<typeof mountPanel>) {
  await flushPromises()
  await button(wrapper, '检查服务').trigger('click')
  await flushPromises()
  await wrapper.get('[data-testid="pipeline-start"]').setValue('2020-10-26')
  await wrapper.get('[data-testid="pipeline-end"]').setValue('2020-10-28')
  await wrapper.get('select[multiple]').setValue(['web.mr'])
  await wrapper.get('.pipeline-confirm input').setValue(true)
  await flushPromises()
}

describe('独立同步控制面板', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    vi.stubGlobal(
      'fetch',
      vi.fn(() => {
        throw new Error('此保护集禁止网络')
      }),
    )
    auth.user.id = 'admin'
    auth.userRoles = ['admin']
    api.configuration.mockResolvedValue(config())
    api.check.mockResolvedValue({
      profile: 'accepted_manual',
      interfaces: ['web.mr'],
      manual_only: true,
    })
    api.save.mockResolvedValue(config(true))
    api.jobs.mockResolvedValue([job])
    api.submit.mockResolvedValue(job)
  })
  it('初始只加载配置，不联网检查、读取任务或启动抽取', async () => {
    const wrapper = mountPanel()
    await flushPromises()
    expect(api.configuration).toHaveBeenCalledTimes(1)
    expect(api.check).not.toHaveBeenCalled()
    expect(api.jobs).not.toHaveBeenCalled()
    expect(api.submit).not.toHaveBeenCalled()
    expect(wrapper.emitted('selection')?.at(-1)).toEqual(['independent_cdm'])
    expect(wrapper.text()).toContain('原业务库CDM')
    wrapper.unmount()
  })
  it('选择和保存独立链路不会冒充已切换读取库或触发任务', async () => {
    const wrapper = mountPanel()
    await flushPromises()
    await wrapper.get('[data-testid="pipeline-independent_cdm"]').trigger('click')
    await wrapper.get('.pipeline-toolbar input[type="checkbox"]').setValue(true)
    await button(wrapper, '保存为默认').trigger('click')
    await flushPromises()
    expect(api.save).toHaveBeenCalledWith({
      version: 1,
      default_pipeline: 'independent_cdm',
      independent_enabled: true,
    })
    expect(wrapper.text()).toContain('已保存；未启动同步或质控')
    expect(wrapper.text()).toContain('原业务库CDM')
    expect(api.submit).not.toHaveBeenCalled()
    wrapper.unmount()
  })
  it('配置失败保持错误，不发出已就绪或默认链路信号', async () => {
    api.configuration.mockRejectedValue(new Error('503'))
    const wrapper = mountPanel()
    await flushPromises()
    expect(wrapper.text()).toContain('读取失败')
    expect(wrapper.emitted('ready')?.at(-1)).toEqual([false])
    expect(wrapper.emitted('selection')).toBeUndefined()
    wrapper.unmount()
  })
  it('显式检查和确认后仅提交人工预检，保留真实未返回计数', async () => {
    api.configuration.mockResolvedValue(config(true))
    const wrapper = mountPanel()
    await readyToSubmit(wrapper)
    await button(wrapper, '提交预检任务').trigger('click')
    await flushPromises()
    expect(api.submit).toHaveBeenCalledTimes(1)
    expect(api.submit.mock.calls[0]?.[0]).toMatchObject({
      start_date: '2020-10-26',
      end_date: '2020-10-28',
      interfaces: ['web.mr'],
      mode: 'dry',
      publish: false,
    })
    expect(wrapper.text()).toContain('排队中')
    expect(wrapper.text()).toContain('未返回 / 未返回')
    wrapper.unmount()
  })
  it('不确定提交保留原请求和幂等ID，重试不改范围', async () => {
    api.configuration.mockResolvedValue(config(true))
    api.submit.mockRejectedValueOnce(new Error('timeout')).mockResolvedValueOnce(job)
    const wrapper = mountPanel()
    await readyToSubmit(wrapper)
    await button(wrapper, '提交预检任务').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('提交未确认')
    expect(wrapper.get('[data-testid="pipeline-start"]').attributes('disabled')).toBeDefined()
    await button(wrapper, '使用原操作标识重试').trigger('click')
    await flushPromises()
    expect(api.submit.mock.calls[0]?.[0]).toEqual(api.submit.mock.calls[1]?.[0])
    wrapper.unmount()
  })
  it('历史读取临时失败保留原状态，手动刷新可恢复', async () => {
    api.configuration.mockResolvedValue(config(true))
    const wrapper = mountPanel()
    await flushPromises()
    await button(wrapper, '刷新任务').trigger('click')
    await flushPromises()
    api.jobs.mockRejectedValueOnce(new Error('503'))
    await button(wrapper, '刷新任务').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('保留上次已读取状态')
    expect(wrapper.text()).toContain('排队中')
    api.jobs.mockResolvedValue([{ ...job, status: 'completed_with_source_limitations' }])
    await button(wrapper, '刷新任务').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('完成（来源受限）')
    wrapper.unmount()
  })
  it('未启用链路不能提交，但仍能查看或取消旧任务', async () => {
    const wrapper = mountPanel()
    await flushPromises()
    await wrapper.get('[data-testid="pipeline-independent_cdm"]').trigger('click')
    await readyToSubmit(wrapper)
    expect(button(wrapper, '提交预检任务').attributes('disabled')).toBeDefined()
    await button(wrapper, '刷新任务').trigger('click')
    await flushPromises()
    api.action.mockResolvedValue({ ...job, cancel_requested: true })
    await button(wrapper, '取消任务').trigger('click')
    await flushPromises()
    expect(api.action).toHaveBeenCalledWith(job.job_id, 'cancel')
    expect(wrapper.text()).toContain('取消已请求')
    wrapper.unmount()
  })
  it('账号变化和卸载使旧成功响应失效', async () => {
    let resolve: ((value: DataPipelineConfiguration) => void) | undefined
    api.configuration.mockImplementation(
      () =>
        new Promise<DataPipelineConfiguration>((done) => {
          resolve = done
        }),
    )
    const wrapper = mountPanel()
    await flushPromises()
    auth.user.id = 'other'
    await flushPromises()
    resolve?.(config(true))
    await flushPromises()
    expect(wrapper.text()).toContain('账号权限已变化')
    expect(wrapper.emitted('selection')).toBeUndefined()
    wrapper.unmount()
  })
})
