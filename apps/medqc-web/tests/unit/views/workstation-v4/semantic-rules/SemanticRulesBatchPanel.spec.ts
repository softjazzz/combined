import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import SemanticRulesBatchPanel from '@/views/workstation-v4/semantic-rules/components/SemanticRulesBatchPanel.vue'
import type { SichuanBatchJob } from '@/views/workstation-v4/semantic-rules/types'

const ProStandardTableStub = {
  props: {
    columns: {
      type: Array,
      default: () => [],
    },
    dataSource: {
      type: Array,
      default: () => [],
    },
  },
  emits: ['change'],
  template: `
    <div class="table-stub">
      <template v-for="record in dataSource" :key="record.id">
        <template v-for="column in columns" :key="column.key">
          <slot
            name="bodyCell"
            :column="column"
            :record="record"
            :index="0"
          />
        </template>
      </template>
    </div>
  `,
}

function createJob(status: SichuanBatchJob['status'], id: string): SichuanBatchJob {
  return {
    id,
    rule_code: `SC-${id}`,
    rule_name: `规则-${id}`,
    scope: 'final',
    status,
    rule_count: 2,
    summary: {
      total_records: 10,
      success_count: 8,
      failed_count: 2,
      issue_records: 1,
      compliant_records: 9,
      total_tokens: 100,
      total_processing_time: 12,
      executor_breakdown: {
        program: 1,
        llm: 1,
      },
      cache_breakdown: {
        hit: 1,
        miss: 1,
      },
    },
  }
}

describe('SemanticRulesBatchPanel', () => {
  it('运行中任务显示“停止”，完成/失败任务显示“重试”', async () => {
    const ASelectStub = {
      props: {
        options: {
          type: Array,
          default: () => [],
        },
      },
      template: '<select><slot /></select>',
    }

    const wrapper = mount(SemanticRulesBatchPanel, {
      props: {
        loading: false,
        batchJobs: [
          createJob('running', 'job-running'),
          createJob('completed', 'job-completed'),
          {
            ...createJob('failed', 'job-partial'),
            summary: {
              ...createJob('failed', 'job-partial').summary,
              execution_status: 'partial_failed',
            },
          },
        ],
        total: 3,
        pagination: {
          current: 1,
          pageSize: 5,
          total: 3,
        },
        query: {
          keyword: '',
          status: undefined,
          scope: undefined,
        },
        statusOptions: [{ label: '执行中', value: 'running' }],
        scopeOptions: [{ label: '终末病历', value: 'final' }],
        cancellingBatchJobId: '',
        retryingBatchJobId: '',
        formatDateTime: (value?: string | Date | null) => String(value || '-'),
      },
      global: {
        stubs: {
          ProStandardTable: ProStandardTableStub,
          SearchOutlined: {
            template: '<span class="icon-search" />',
          },
          'a-button': {
            emits: ['click'],
            template: '<button @click="$emit(\'click\')"><slot /></button>',
          },
          'a-input': {
            template: '<input />',
          },
          'a-select': ASelectStub,
          'a-tag': {
            template: '<span><slot /></span>',
          },
        },
      },
    })

    const buttonTexts = wrapper.findAll('button').map((node) => node.text())
    expect(buttonTexts).toContain('重试失败项')
    expect(wrapper.text()).toContain('部分执行失败')
    expect(buttonTexts).toContain('停止')
    expect(buttonTexts).toContain('重试')

    const buttons = wrapper.findAll('button')
    const stopButton = buttons.find((node) => node.text() === '停止')
    const retryButton = buttons.find((node) => node.text() === '重试')
    const retryFailedButton = buttons.find((node) => node.text() === '重试失败项')

    await stopButton?.trigger('click')
    await retryButton?.trigger('click')
    await retryFailedButton?.trigger('click')

    expect(wrapper.emitted('cancelBatchJob')?.[0]).toEqual(['job-running'])
    expect(wrapper.emitted('retryBatchJob')?.[0]).toEqual(['job-completed'])
    expect(wrapper.emitted('retryBatchJob')?.[1]).toEqual(['job-partial'])
  })

  it('只读入口隐藏发起与重试，但保留查看和停止', async () => {
    const wrapper = mount(SemanticRulesBatchPanel, {
      props: {
        loading: false,
        batchJobs: [createJob('running', 'job-running'), createJob('completed', 'job-done')],
        total: 2,
        pagination: { current: 1, pageSize: 5, total: 2 },
        query: { keyword: '', status: undefined, scope: 'final' },
        statusOptions: [],
        scopeOptions: [{ label: '终末病历', value: 'final' }],
        cancellingBatchJobId: '',
        retryingBatchJobId: '',
        formatDateTime: (value?: string | Date | null) => String(value || '-'),
        allowLaunch: false,
        allowRetry: false,
      },
      global: {
        stubs: {
          ProStandardTable: ProStandardTableStub,
          SearchOutlined: { template: '<span />' },
          'a-button': { emits: ['click'], template: '<button @click="$emit(\'click\')"><slot /></button>' },
          'a-input': { template: '<input />' },
          'a-select': { template: '<select />' },
          'a-tag': { template: '<span><slot /></span>' },
        },
      },
    })

    const buttons = wrapper.findAll('button')
    expect(buttons.map((button) => button.text())).toEqual(['查看', '停止', '查看'])
    await buttons[0]?.trigger('click')
    await buttons[1]?.trigger('click')
    expect(wrapper.emitted('openBatchJobDrawer')?.[0]?.[0]).toMatchObject({ id: 'job-running' })
    expect(wrapper.emitted('cancelBatchJob')?.[0]).toEqual(['job-running'])
    expect(wrapper.emitted('openBatchLaunch')).toBeUndefined()
    expect(wrapper.emitted('retryBatchJob')).toBeUndefined()
  })
})
