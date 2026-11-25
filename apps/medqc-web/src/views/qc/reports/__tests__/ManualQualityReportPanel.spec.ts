import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { reactive } from 'vue'
import ManualQualityReportPanel from '../ManualQualityReportPanel.vue'
import ManualDefectWorkflowDrawer from '@/components/qc/ManualDefectWorkflowDrawer.vue'
import CaseRectificationCreate from '@/components/qc/CaseRectificationCreate.vue'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
const mocks = vi.hoisted(() => ({
  report: vi.fn(),
  export: vi.fn(),
  auth: { user: { id: 'synthetic-user', roles: ['qc_manager'], is_demo_account: false } },
}))
vi.mock('@/api/manualQualityReport', () => ({
  getManualQualityReport: mocks.report,
  exportManualQualityReport: mocks.export,
}))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => mocks.auth }))
const data = {
  assumption: '已确认统计口径',
  summary: {
    entered: 1,
    review: { pending: 1, approved: 0, rejected: 0, unknown: 0 },
    rectification: {
      pending: 0,
      submitted: 1,
      approved: 0,
      rejected: 0,
      unassigned: 0,
      unknown: 0,
    },
  },
  filter_options: {
    institutes: ['H1', 'H2'],
    departments: [
      { institute_id: 'H1', department: '内科' },
      { institute_id: 'H2', department: '内科' },
    ],
    creators: [{ id: 'u1', name: '合成人员' }],
    tasks: [{ id: 'T1', name: '合成任务' }],
  },
  items: [
    {
      id: 'd1',
      institute_id: 'H1',
      department: '内科',
      creator_name: '合成人员',
      review_status: 'pending',
      rectification_status: 'submitted',
    },
  ],
  total: 21,
}
function make() {
  return mount(ManualQualityReportPanel, {
    global: {
      stubs: {
        CaseRectificationCreate: {
          name: 'CaseRectificationCreate',
          props: ['instituteId', 'patientId', 'visitId', 'jobId', 'initialTarget'],
          template: '<button>整改处理</button>',
        },
        'a-alert': {
          props: ['message', 'type'],
          template: '<p :data-type="type">{{ message }}</p>',
        },
        'a-button': { template: '<button><slot/></button>' },
        'a-spin': { template: '<div><slot/></div>' },
        'a-table': {
          props: ['dataSource'],
          template: `<div class="rows"><div v-for="row in dataSource" :key="row.id">
            <slot name="bodyCell" :column="{dataIndex: 'creator_name'}" :record="row" :text="row.creator_name" />
            <slot name="bodyCell" :column="{key: 'detail'}" :record="{id: row.id}" />
          </div></div>`,
        },
        'a-pagination': {
          emits: ['change'],
          template: '<button class="next" @click="$emit(\'change\', 2)">下一页</button>',
        },
        'a-drawer': { props: ['open'], template: '<aside v-if="open"><slot/></aside>' },
        'a-descriptions': { template: '<dl><slot/></dl>' },
        'a-descriptions-item': { template: '<dd><slot/></dd>' },
      },
    },
  })
}
beforeEach(() => {
  vi.clearAllMocks()
  mocks.auth = reactive({
    user: { id: 'synthetic-user', roles: ['qc_manager'], is_demo_account: false },
  })
  mocks.report.mockResolvedValue(data)
  mocks.export.mockResolvedValue(new Blob(['synthetic csv']))
})
describe('人工质控报表', () => {
  it.each(['pending', 'rejected', 'approved'])(
    '仅可信且审核通过的%s缺陷可进入冻结整改链',
    async (status) => {
      const row = {
        ...data.items[0],
        patient_id: 'P1',
        visit_id: 'V1',
        scene: 'running',
        review_status: status,
        source_verified: true,
        root_job_id: 'J1',
        envelope_id: 'E1',
      }
      mocks.report.mockResolvedValue({ ...data, items: [row] })
      const wrapper = make()
      await flushPromises()
      await wrapper.get('.rows button').trigger('click')
      const form = wrapper.findComponent(CaseRectificationCreate)
      expect(form.exists()).toBe(status === 'approved')
      if (status === 'approved') {
        expect(form.props()).toMatchObject({
          jobId: 'J1',
          initialTarget: { source: 'manual', defectId: 'd1', rootJobId: 'J1', envelopeId: 'E1' },
        })
        form.vm.$emit('created')
        await flushPromises()
        expect(mocks.report).toHaveBeenCalledTimes(2)
        expect(wrapper.emitted('changed')).toHaveLength(1)
        expect(wrapper.findComponent(CaseRectificationCreate).exists()).toBe(false)
      }
      wrapper.unmount()
    },
  )
  it('来源不全时不开放整改入口', async () => {
    mocks.report.mockResolvedValue({
      ...data,
      items: [
        {
          ...data.items[0],
          review_status: 'approved',
          source_verified: false,
          root_job_id: null,
          envelope_id: null,
        },
      ],
    })
    const wrapper = make()
    await flushPromises()
    await wrapper.get('.rows button').trigger('click')
    expect(wrapper.findComponent(CaseRectificationCreate).exists()).toBe(false)
    wrapper.unmount()
  })
  it('人工操作成功后刷新当前页并通知工作分析，不重置筛选', async () => {
    const wrapper = make()
    await flushPromises()
    const before = mocks.report.mock.calls[0][0]
    wrapper.getComponent(ManualDefectWorkflowDrawer).vm.$emit('changed')
    await flushPromises()
    expect(mocks.report).toHaveBeenCalledTimes(2)
    expect(mocks.report.mock.calls[1][0]).toEqual(before)
    expect(wrapper.emitted('changed')).toHaveLength(1)
    wrapper.unmount()
  })
  it('根网格允许收缩，非空长表格不能撑宽整页筛选', () => {
    // JSDOM 不计算网格尺寸；真实数据的 390px 浏览器断言另见交付记录。
    const styles = readFileSync(
      resolve(process.cwd(), 'src/views/qc/reports/styles/manual-quality-report.css'),
      'utf8',
    )
    const rootRule = styles.match(/\.manual-report\s*\{([^}]+)\}/)?.[1]
    expect(rootRule).toMatch(/grid-template-columns:\s*minmax\(0,\s*1fr\)/)
  })
  it('表格显示单元格文本，明细从已校验行读取，翻页清理旧明细', async () => {
    const wrapper = make()
    await flushPromises()
    expect(wrapper.get('.rows').text()).toContain('合成人员')
    await wrapper.get('.rows button').trigger('click')
    expect(wrapper.get('aside').text()).toContain('合成人员')
    expect(wrapper.get('aside').text()).toContain('待验收')
    await wrapper.get('.next').trigger('click')
    await flushPromises()
    expect(wrapper.find('aside').exists()).toBe(false)
    wrapper.unmount()
  })
  it('账户改变后丢弃迟到查询，不能显示前账户病例', async () => {
    let resolve!: (value: unknown) => void
    mocks.report.mockImplementationOnce(
      () =>
        new Promise((done) => {
          resolve = done
        }),
    )
    const wrapper = make()
    mocks.auth.user.id = 'other-user'
    await flushPromises()
    resolve({ ...data, summary: { ...data.summary, entered: 999 } })
    await flushPromises()
    expect(wrapper.text()).not.toContain('录入 999 条')
    expect(wrapper.text()).toContain('录入 1 条')
    wrapper.unmount()
  })
  it('审核整改分列、完整院科人员任务场景筛选及分页', async () => {
    const wrapper = make()
    await flushPromises()
    expect(wrapper.text()).toContain('已确认统计口径')
    expect(wrapper.text()).not.toContain('待确认')
    // 统计口径折叠在details内，正文仍完整保留在DOM中
    const assumption = wrapper.get('[data-testid="manual-assumption"]')
    expect(assumption.element.tagName).toBe('DETAILS')
    expect(assumption.text()).toContain('已确认统计口径')
    expect(wrapper.find('.mq-status--warning').text()).toBe('待审核 1')
    expect(wrapper.text()).toContain('待审核 1')
    expect(wrapper.text()).toContain('待验收 1')
    const selects = wrapper.findAll('select')
    await selects[0].setValue('H1')
    await selects[1].setValue('内科')
    await selects[2].setValue('u1')
    await selects[3].setValue('T1')
    await selects[4].setValue('final')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(mocks.report).toHaveBeenLastCalledWith(
      expect.objectContaining({
        institute_id: 'H1',
        department: '内科',
        creator_id: 'u1',
        task_id: 'T1',
        scene: 'final',
      }),
      1,
      expect.any(AbortSignal),
    )
    await wrapper.get('.next').trigger('click')
    await flushPromises()
    expect(mocks.report).toHaveBeenLastCalledWith(
      expect.objectContaining({ task_id: 'T1' }),
      2,
      expect.any(AbortSignal),
    )
    wrapper.unmount()
  })
  it('新查询失败清掉旧统计，不伪造零；导出使用已应用筛选', async () => {
    const create = vi.fn(() => 'blob:synthetic'),
      revoke = vi.fn()
    vi.stubGlobal('URL', { createObjectURL: create, revokeObjectURL: revoke })
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    const wrapper = make()
    await flushPromises()
    await wrapper
      .findAll('button')
      .find((button) => button.text() === '导出 CSV')!
      .trigger('click')
    await flushPromises()
    expect(mocks.export).toHaveBeenCalledWith(
      expect.objectContaining({ scene: 'all' }),
      expect.any(AbortSignal),
    )
    expect(create).toHaveBeenCalledTimes(1)
    mocks.report.mockRejectedValue(new Error('来源读取失败'))
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.text()).toContain('来源读取失败')
    expect(wrapper.text()).not.toContain('录入 1 条')
    wrapper.unmount()
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })
})
