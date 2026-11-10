import { flushPromises, mount } from '@vue/test-utils'
import { reactive } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import DataPipelineSettingsPanel from '@/views/workstation-v4/components/system-config/DataPipelineSettingsPanel.vue'
import type { DataPipelineConfiguration, IndependentSyncJob, IndependentCatalog, SyncSchedule, SyncCapabilities } from '@/api/dataPipelines'
import SyncScheduleDraftPanel from '@/views/workstation-v4/components/system-config/SyncScheduleDraftPanel.vue'
import SyncJobDetailDrawer from '@/views/workstation-v4/components/system-config/SyncJobDetailDrawer.vue'

const api = vi.hoisted(() => ({
  configuration: vi.fn(),
  save: vi.fn(),
  check: vi.fn(),
  jobs: vi.fn(),
  submit: vi.fn(),
  action: vi.fn(),
  detail: vi.fn(),
  schedules: vi.fn(),
  schedule: vi.fn(),
  saveDraft: vi.fn(),
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
      stubs: stubs,
    },
  })
}
const stubs = {
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
        'a-drawer': { props: ['open'], template: '<div v-if="open"><slot /></div>' },
        'a-empty': { props: ['description'], template: '<p>{{description}}</p>' },
}
const capabilities: SyncCapabilities = { permissions: ['read', 'run', 'schedule'], timezone: 'Asia/Shanghai', last_complete_date: '2026-11-09', max_manual_days: 3,
  features: { schedule_drafts: true, schedule_controls: false, date_recovery_profiles: ['accepted_manual'] } }
function button(wrapper: Pick<ReturnType<typeof mountPanel>, 'findAll'>, text: string) {
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
      session: structuredClone(capabilities),
    })
    api.save.mockResolvedValue(config(true))
    api.jobs.mockResolvedValue([job])
    api.submit.mockResolvedValue(job)
    api.schedules.mockResolvedValue([])
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
    await button(wrapper, '保存任务入口').trigger('click')
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

  it('日期与权限来自服务能力，超范围或只读令牌不能提交', async () => {
    api.configuration.mockResolvedValue(config(true))
    const wrapper = mountPanel()
    await readyToSubmit(wrapper)
    expect(wrapper.text()).toContain('单次最多 3 天')
    await wrapper.get('[data-testid="pipeline-end"]').setValue('2020-10-29')
    await wrapper.get('.pipeline-confirm input').setValue(true)
    expect(button(wrapper, '提交预检任务').attributes('disabled')).toBeDefined()
    api.check.mockResolvedValue({ profile: 'accepted_manual', interfaces: ['web.mr'], session: { ...capabilities, permissions: ['read'] } })
    await button(wrapper, '检查服务').trigger('click')
    await flushPromises()
    await wrapper.get('.pipeline-confirm input').setValue(true)
    expect(button(wrapper, '提交预检任务').attributes('disabled')).toBeDefined()
    expect(api.submit).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  function catalogFixture(): IndependentCatalog {
    return { profile: 'accepted_manual', interfaces: ['web.mr'], manual_only: true, session: structuredClone(capabilities) }
  }
  function draftRow(enabled = false, version = 1): SyncSchedule {
    return { schedule_id: job.job_id, version, enabled, next_fire_at: null,
      config: { frequency: 'daily', local_time: '02:00', window_days: 1, timezone: 'Asia/Shanghai',
        request: { profile: 'accepted_manual', interfaces: ['web.mr'], mode: 'replay', publish: true } } }
  }
  function mountDraft(catalog = catalogFixture()) {
    return mount(SyncScheduleDraftPanel, { props: { catalog }, global: { stubs } })
  }
  async function newDraft(wrapper: ReturnType<typeof mountDraft>) {
    await button(wrapper, '新建禁用草稿').trigger('click')
    await wrapper.get('select[multiple]').setValue(['web.mr'])
  }
  it('打开草稿面板不读写任务，只有明确保存才提交禁用草稿', async () => {
    const wrapper = mountDraft()
    expect(api.schedules).not.toHaveBeenCalled()
    expect(api.saveDraft).not.toHaveBeenCalled()
    await newDraft(wrapper)
    api.saveDraft.mockResolvedValue(draftRow())
    await button(wrapper, '保存禁用草稿').trigger('click')
    await flushPromises()
    const [id, payload] = api.saveDraft.mock.calls[0]
    expect(id).toMatch(/^[a-f0-9-]{36}$/)
    expect(payload).toEqual({ version: null, config: { frequency: 'daily', local_time: '02:00', window_days: 1, interfaces: ['web.mr'] } })
    expect(wrapper.text()).toContain('保持禁用')
    expect(api.submit).not.toHaveBeenCalled()
    wrapper.unmount()
  })
  it('草稿超时不自动重试，显式重试保持同一编号版本与内容', async () => {
    const wrapper = mountDraft()
    await newDraft(wrapper)
    api.saveDraft.mockRejectedValueOnce(new Error('timeout')).mockResolvedValueOnce(draftRow())
    await button(wrapper, '保存禁用草稿').trigger('click')
    await flushPromises()
    expect(api.saveDraft).toHaveBeenCalledTimes(1)
    expect(wrapper.get('select[multiple]').attributes('disabled')).toBeDefined()
    await button(wrapper, '使用原版本重试').trigger('click')
    await flushPromises()
    expect(api.saveDraft.mock.calls[0]).toEqual(api.saveDraft.mock.calls[1])
    wrapper.unmount()
  })
  it('409版本冲突不自动覆盖，先核对再显式载入服务器版本', async () => {
    const wrapper = mountDraft()
    api.schedules.mockResolvedValue([draftRow()])
    await button(wrapper, '读取计划').trigger('click')
    await flushPromises()
    await button(wrapper, '编辑禁用草稿').trigger('click')
    api.saveDraft.mockRejectedValue({ isAxiosError: true, response: { status: 409 } })
    await button(wrapper, '保存禁用草稿').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('版本冲突')
    expect(api.saveDraft).toHaveBeenCalledTimes(1)
    api.schedule.mockResolvedValue(draftRow(false, 3))
    await button(wrapper, '核对服务器版本').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('服务器版本 3')
    expect(api.saveDraft).toHaveBeenCalledTimes(1)
    await button(wrapper, '载入服务器版本').trigger('click')
    api.saveDraft.mockResolvedValue(draftRow(false, 4))
    await button(wrapper, '保存禁用草稿').trigger('click')
    await flushPromises()
    expect(api.saveDraft.mock.calls[1][1].version).toBe(3)
    wrapper.unmount()
  })
  it('只读令牌不能新建草稿，服务端已启用计划不能编辑', async () => {
    const catalog = catalogFixture()
    catalog.session.permissions = ['read']
    const wrapper = mountDraft(catalog)
    expect(button(wrapper, '新建禁用草稿').attributes('disabled')).toBeDefined()
    api.schedules.mockResolvedValue([draftRow(true)])
    await button(wrapper, '读取计划').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('只读')
    expect(wrapper.text()).not.toContain('编辑禁用草稿')
    expect(api.saveDraft).not.toHaveBeenCalled()
    wrapper.unmount()
  })
  it('任务日期单元详情仅GET，保留失败状态与零计数', async () => {
    api.detail.mockResolvedValue({ ...job, status: 'failed', request: { start_date: '2026-11-01', end_date: '2026-11-01', plan_version: 2 },
      units: [{ unit_id: 'unit-1', source_date: '2026-11-01', interface_name: 'web.mr', phase: 'extract', status: 'failed', execution_attempts: 2,
        error: { code: 'source_error', location: 'extract' }, result: { counts: { fetched: 0 } } }] })
    const wrapper = mount(SyncJobDetailDrawer, { props: { jobId: job.job_id, canRetry: true }, global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('source_error')
    expect(wrapper.text()).toContain('fetched: 0')
    expect(api.action).not.toHaveBeenCalled()
    await button(wrapper, '重试未完成单元').trigger('click')
    expect(wrapper.emitted('retry')?.length).toBe(1)
    expect(api.action).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('草稿写入未确认时不能重新检查服务丢失原请求', async () => {
    const wrapper = mountPanel()
    await flushPromises()
    await button(wrapper, '检查服务').trigger('click')
    await flushPromises()
    await button(wrapper, '新建禁用草稿').trigger('click')
    const selects = wrapper.findAll('select[multiple]')
    await selects[selects.length - 1].setValue(['web.mr'])
    api.saveDraft.mockRejectedValueOnce(new Error('timeout'))
    await button(wrapper, '保存禁用草稿').trigger('click')
    await flushPromises()
    expect(button(wrapper, '检查服务').attributes('disabled')).toBeDefined()
    expect(button(wrapper, '重新加载配置').attributes('disabled')).toBeDefined()
    expect(api.saveDraft).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })
})
