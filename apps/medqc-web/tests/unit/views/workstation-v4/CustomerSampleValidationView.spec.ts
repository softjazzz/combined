/* eslint-disable vue/one-component-per-file */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, nextTick } from 'vue'
import CustomerSampleValidationView from '@/views/workstation-v4/CustomerSampleValidationView.vue'

const {
  message,
  listManualSamplePools,
  getLatestManualSamplePoolSyncJob,
  getManualSamplePoolSyncJob,
  getManualSamplePoolRecords,
  importManualSamplePoolByUpload,
  matchManualSamplePool,
  runManualSamplePool,
  syncManualSamplePoolRecords,
  getSichuanWorkspaceBatchJob,
  exportSichuanWorkspaceBatchJob,
  writeFile,
  bookNew,
  aoaToSheet,
  bookAppendSheet,
} = vi.hoisted(() => ({
  message: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  },
  listManualSamplePools: vi.fn(),
  getLatestManualSamplePoolSyncJob: vi.fn(),
  getManualSamplePoolSyncJob: vi.fn(),
  getManualSamplePoolRecords: vi.fn(),
  importManualSamplePoolByUpload: vi.fn(),
  matchManualSamplePool: vi.fn(),
  runManualSamplePool: vi.fn(),
  syncManualSamplePoolRecords: vi.fn(),
  getSichuanWorkspaceBatchJob: vi.fn(),
  exportSichuanWorkspaceBatchJob: vi.fn(),
  writeFile: vi.fn(),
  bookNew: vi.fn(() => ({ sheets: [] })),
  aoaToSheet: vi.fn(() => ({})),
  bookAppendSheet: vi.fn(),
}))

vi.mock('ant-design-vue', () => ({
  message,
}))

vi.mock('@/services/manual-case-sample-service', () => ({
  listManualSamplePools,
  getLatestManualSamplePoolSyncJob,
  getManualSamplePoolSyncJob,
  getManualSamplePoolRecords,
  importManualSamplePoolByUpload,
  matchManualSamplePool,
  runManualSamplePool,
  syncManualSamplePoolRecords,
}))

vi.mock('@/services/sichuan-rule-workspace-service', () => ({
  getSichuanWorkspaceBatchJob,
  exportSichuanWorkspaceBatchJob,
}))

vi.mock('xlsx', () => ({
  utils: {
    book_new: bookNew,
    aoa_to_sheet: aoaToSheet,
    book_append_sheet: bookAppendSheet,
  },
  writeFile,
}))

vi.mock('@ant-design/icons-vue', () => ({
  InboxOutlined: defineComponent({
    name: 'InboxOutlinedStub',
    setup() {
      return () => h('span', { class: 'inbox-icon-stub' })
    },
  }),
}))

const AButtonStub = defineComponent({
  name: 'AButtonStub',
  props: {
    disabled: Boolean,
    loading: Boolean,
  },
  emits: ['click'],
  setup(props, { slots, emit, attrs }) {
    return () =>
      h(
        'button',
        {
          ...attrs,
          disabled: props.disabled,
          onClick: () => {
            if (!props.disabled) emit('click')
          },
        },
        slots.default?.(),
      )
  },
})

const ATagStub = defineComponent({
  name: 'ATagStub',
  setup(_, { slots }) {
    return () => h('span', { class: 'a-tag-stub' }, slots.default?.())
  },
})

const ACardStub = defineComponent({
  name: 'ACardStub',
  setup(_, { slots }) {
    return () => h('div', { class: 'a-card-stub' }, slots.default?.())
  },
})

const ASelectStub = defineComponent({
  name: 'ASelectStub',
  props: {
    value: {
      type: [String, Number],
      default: undefined,
    },
    options: {
      type: Array,
      default: () => [],
    },
    placeholder: {
      type: String,
      default: '',
    },
  },
  emits: ['update:value', 'change'],
  setup(props, { emit, attrs }) {
    return () =>
      h(
        'select',
        {
          ...attrs,
          'data-placeholder': props.placeholder,
          value: props.value as string | number | undefined,
          onChange: (event: Event) => {
            const target = event.target as HTMLSelectElement
            const selected = target.value
            const matched = (props.options as Array<{ value: string | number }>).find(
              (item) => String(item.value) === selected,
            )
            const nextValue = matched ? matched.value : selected
            emit('update:value', nextValue)
            emit('change', nextValue)
          },
        },
        (props.options as Array<{ label: string; value: string | number }>).map((option) =>
          h('option', { value: option.value }, option.label),
        ),
      )
  },
})

const AInputStub = defineComponent({
  name: 'AInputStub',
  props: {
    value: {
      type: String,
      default: '',
    },
    size: {
      type: String,
      default: undefined,
    },
    placeholder: {
      type: String,
      default: '',
    },
  },
  emits: ['update:value', 'press-enter'],
  setup(props, { emit, attrs }) {
    return () =>
      h('input', {
        ...attrs,
        placeholder: props.placeholder,
        value: props.value,
        onInput: (event: Event) => {
          const target = event.target as HTMLInputElement
          emit('update:value', target.value)
        },
        onKeydown: (event: KeyboardEvent) => {
          if (event.key === 'Enter') emit('press-enter')
        },
      })
  },
})

const ATextareaStub = defineComponent({
  name: 'ATextareaStub',
  props: {
    value: {
      type: String,
      default: '',
    },
    size: {
      type: String,
      default: undefined,
    },
  },
  emits: ['update:value'],
  setup(props, { emit }) {
    return () =>
      h('textarea', {
        value: props.value,
        onInput: (event: Event) =>
          emit('update:value', (event.target as HTMLTextAreaElement).value),
      })
  },
})

const ASwitchStub = defineComponent({
  name: 'ASwitchStub',
  props: {
    checked: Boolean,
  },
  emits: ['update:checked'],
  setup(props, { emit }) {
    return () =>
      h('input', {
        type: 'checkbox',
        checked: props.checked,
        onChange: (event: Event) =>
          emit('update:checked', (event.target as HTMLInputElement).checked),
      })
  },
})

const ATableStub = defineComponent({
  name: 'ATableStub',
  props: {
    columns: {
      type: Array,
      default: () => [],
    },
    dataSource: {
      type: Array,
      default: () => [],
    },
    rowSelection: {
      type: Object,
      default: () => ({}),
    },
  },
  setup(props) {
    const toggle = (recordId: string, checked: boolean) => {
      const selectedKeys = Array.isArray((props.rowSelection as any).selectedRowKeys)
        ? [...(props.rowSelection as any).selectedRowKeys]
        : []
      const nextKeys = checked
        ? Array.from(new Set([...selectedKeys, recordId]))
        : selectedKeys.filter((key: string) => key !== recordId)
      ;(props.rowSelection as any).onChange?.(nextKeys)
    }

    return () =>
      h(
        'div',
        { class: 'a-table-stub' },
        (props.dataSource as Array<any>).map((record) =>
          h('div', { class: 'record-row', 'data-record-id': record.id }, [
            h('label', [
              h('input', {
                type: 'checkbox',
                class: 'record-checkbox',
                checked: ((props.rowSelection as any).selectedRowKeys || []).includes(record.id),
                onChange: (event: Event) =>
                  toggle(record.id, (event.target as HTMLInputElement).checked),
              }),
              h('span', { class: 'record-name' }, record.patient_name || record.mr_no || record.id),
            ]),
            h(
              'div',
              { class: 'record-actions' },
              (props.columns as Array<any>)
                .filter((column) => typeof column?.customRender === 'function')
                .map((column, index) =>
                  h('div', { class: `column-${index}` }, [
                    column.customRender({ record, value: record[column.dataIndex] }),
                  ]),
                ),
            ),
          ]),
        ),
      )
  },
})

const AModalStub = defineComponent({
  name: 'AModalStub',
  props: {
    open: Boolean,
  },
  emits: ['update:open', 'ok', 'cancel'],
  setup(props, { slots, emit }) {
    return () =>
      props.open
        ? h('div', { class: 'a-modal-stub' }, [
            h('div', { class: 'modal-body' }, slots.default?.()),
            h('button', { class: 'modal-ok', onClick: () => emit('ok') }, '开始导入'),
            h('button', { class: 'modal-cancel', onClick: () => emit('cancel') }, '取消'),
          ])
        : null
  },
})

const AUploadDraggerStub = defineComponent({
  name: 'AUploadDraggerStub',
  props: {
    beforeUpload: {
      type: Function,
      default: undefined,
    },
  },
  setup(props, { slots }) {
    return () =>
      h('div', { class: 'a-upload-dragger-stub' }, [
        slots.default?.(),
        h(
          'button',
          {
            class: 'upload-trigger',
            onClick: () =>
              props.beforeUpload?.({
                uid: 'file-1',
                name: 'demo.xlsx',
                size: 12,
                type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
              }),
          },
          'mock-upload',
        ),
      ])
  },
})

const ADrawerStub = defineComponent({
  name: 'ADrawerStub',
  props: {
    open: Boolean,
  },
  emits: ['close'],
  setup(props, { slots }) {
    return () => (props.open ? h('div', { class: 'a-drawer-stub' }, slots.default?.()) : null)
  },
})

const QCReviewDrawerStub = defineComponent({
  name: 'QCReviewDrawerStub',
  props: {
    visible: Boolean,
  },
  setup(props) {
    return () => (props.visible ? h('div', { class: 'qc-review-drawer-stub' }) : null)
  },
})

const SemanticRulesBatchResultDrawerStub = defineComponent({
  name: 'SemanticRulesBatchResultDrawerStub',
  props: {
    open: Boolean,
  },
  setup(props) {
    return () => (props.open ? h('div', { class: 'batch-result-drawer-stub' }) : null)
  },
})

function buildPool() {
  return {
    id: 'pool-1',
    name: '手工问题样本池-首轮验证',
    source_file: 'D:/docs/demo.xlsx',
    source_sheet: 'Sheet2',
    scene: 'running',
    created_by: 'tester',
    total_items: 2,
    llm_intrinsic_items: 2,
    programmatic_items: 0,
    unsupported_items: 0,
    matched_items: 2,
    ambiguous_items: 0,
    unmatched_items: 0,
    ready_items: 2,
    latest_job_id: 'job-1',
    latest_job_status: 'completed',
  }
}

function buildRecord(overrides: Record<string, unknown> = {}) {
  return {
    id: 'V001',
    matched_institute_id: 'H1',
    matched_patient_id: 'P001',
    matched_visit_id: 'V001',
    patient_name: '张三',
    mr_no: '2248248',
    department: '普外科',
    match_status: 'matched',
    sync_status: 'synced',
    bundle_status: 'ready',
    coverage_types: ['llm_intrinsic'],
    candidate_rule_ids: ['SC-026'],
    issue_count: 1,
    issue_preview: ['首次病程记录鉴别诊断不全面'],
    issue_preview_text: '首次病程记录鉴别诊断不全面',
    sample_item_ids: ['item-1'],
    sample_items: [],
    ...overrides,
  }
}

async function mountView() {
  const wrapper = mount(CustomerSampleValidationView, {
    global: {
      stubs: {
        AButton: AButtonStub,
        ATag: ATagStub,
        ACard: ACardStub,
        ASelect: ASelectStub,
        AInput: AInputStub,
        ATextarea: ATextareaStub,
        ASwitch: ASwitchStub,
        ATable: ATableStub,
        AModal: AModalStub,
        AUploadDragger: AUploadDraggerStub,
        ADrawer: ADrawerStub,
        QCReviewDrawer: QCReviewDrawerStub,
        SemanticRulesBatchResultDrawer: SemanticRulesBatchResultDrawerStub,
      },
    },
  })
  await flushPromises()
  await nextTick()
  return wrapper
}

describe('CustomerSampleValidationView', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  beforeEach(() => {
    vi.clearAllMocks()
    listManualSamplePools.mockResolvedValue({
      success: true,
      data: { items: [buildPool()], total: 1, page: 1, page_size: 50 },
    })
    getLatestManualSamplePoolSyncJob.mockResolvedValue({ success: true, data: null })
    getManualSamplePoolSyncJob.mockResolvedValue({
      success: true,
      data: {
        id: 'sync-job-1',
        pool_id: 'pool-1',
        status: 'running',
        summary: { progress: { step_label: '正在同步', total_candidates: 2, eligible_visits: 2 } },
      },
    })
    getManualSamplePoolRecords.mockResolvedValue({
      success: true,
      data: {
        pool: buildPool(),
        items: [
          buildRecord(),
          buildRecord({
            id: 'V002',
            matched_visit_id: 'V002',
            mr_no: '2249001',
            patient_name: '李四',
          }),
        ],
        total: 2,
        page: 1,
        page_size: 20,
      },
    })
    runManualSamplePool.mockResolvedValue({
      success: true,
      data: {
        pool_id: 'pool-1',
        job_id: 'job-2',
        sample_item_count: 1,
        selected_record_count: 1,
        record_count: 1,
        rule_count: 5,
        record_ids: ['V001'],
        rule_ids: ['SC-023'],
        validation_mode: 'customer',
        rule_set_name: '客户专项规则包 v1',
      },
    })
    syncManualSamplePoolRecords.mockResolvedValue({
      success: true,
      data: { job_id: 'sync-job-1', pool_id: 'pool-1', status: 'queued' },
    })
    importManualSamplePoolByUpload.mockResolvedValue({
      success: true,
      data: { id: 'pool-2', name: '第二轮', imported_rows: 2 },
    })
    getSichuanWorkspaceBatchJob.mockResolvedValue({
      success: true,
      data: { id: 'job-2', status: 'completed' },
    })
    exportSichuanWorkspaceBatchJob.mockResolvedValue({ success: true, data: new Blob() })
  })

  it('按病历勾选并透传并发病历数', async () => {
    const wrapper = await mountView()

    const recordCheckboxes = wrapper.findAll('input.record-checkbox')
    await recordCheckboxes[0].setValue(true)

    const selectElements = wrapper.findAll('select')
    const parallelSelect = selectElements.find((node) =>
      node.findAll('option').some((option) => option.text() === '4'),
    )
    expect(parallelSelect).toBeTruthy()
    await parallelSelect!.setValue('2')

    const runButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('发起选中病历验证'))
    expect(runButton).toBeTruthy()
    await runButton!.trigger('click')
    await flushPromises()

    expect(runManualSamplePool).toHaveBeenCalledWith('pool-1', {
      record_ids: ['V001'],
      max_parallel_records: 2,
      validation_mode: 'customer',
    })
    expect(message.success).toHaveBeenCalled()
  })

  it('点击同步样本病历后展示同步进度区块', async () => {
    const wrapper = await mountView()

    const syncButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('同步样本病历'))
    expect(syncButton).toBeTruthy()
    await syncButton!.trigger('click')
    await flushPromises()

    expect(syncManualSamplePoolRecords).toHaveBeenCalledWith('pool-1', {
      only_intrinsic: true,
      include_in_batch_1: true,
    })
    expect(wrapper.text()).toContain('样本病历同步进度')
    expect(wrapper.text()).toContain('正在同步')
  })

  it('同步任务轮询时应更新进度并在完成后刷新列表', async () => {
    vi.useFakeTimers()
    getManualSamplePoolSyncJob
      .mockResolvedValueOnce({
        success: true,
        data: {
          id: 'sync-job-1',
          pool_id: 'pool-1',
          status: 'running',
          summary: {
            progress: {
              step_label: '正在同步病历文书',
              total_candidates: 3,
              eligible_visits: 2,
              processed_tables: 1,
              total_tables: 3,
            },
          },
        },
      })
      .mockResolvedValueOnce({
        success: true,
        data: {
          id: 'sync-job-1',
          pool_id: 'pool-1',
          status: 'running',
          summary: {
            progress: {
              step_label: '继续同步病历文书',
              total_candidates: 3,
              eligible_visits: 2,
              processed_tables: 2,
              total_tables: 3,
            },
          },
        },
      })
      .mockResolvedValueOnce({
        success: true,
        data: {
          id: 'sync-job-1',
          pool_id: 'pool-1',
          status: 'completed',
          summary: {
            progress: {
              step_label: '同步完成',
              total_candidates: 3,
              eligible_visits: 2,
              processed_tables: 3,
              total_tables: 3,
            },
          },
        },
      })

    const wrapper = await mountView()

    const initialPoolCalls = listManualSamplePools.mock.calls.length
    const initialRecordCalls = getManualSamplePoolRecords.mock.calls.length

    const syncButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('同步样本病历'))
    expect(syncButton).toBeTruthy()
    await syncButton!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('1/3')
    expect(wrapper.text()).toContain('正在同步病历文书')

    await vi.advanceTimersByTimeAsync(3000)
    await flushPromises()

    expect(wrapper.text()).toContain('2/3')
    expect(wrapper.text()).toContain('继续同步病历文书')

    await vi.advanceTimersByTimeAsync(3000)
    await flushPromises()

    expect(getManualSamplePoolSyncJob).toHaveBeenCalledTimes(3)
    expect(listManualSamplePools.mock.calls.length).toBeGreaterThan(initialPoolCalls)
    expect(getManualSamplePoolRecords.mock.calls.length).toBeGreaterThan(initialRecordCalls)
  })

  it('支持下载简化后的客户样本导入模板', async () => {
    const wrapper = await mountView()

    const importButton = wrapper.findAll('button').find((node) => node.text().includes('导入模板'))
    expect(importButton).toBeTruthy()
    await importButton!.trigger('click')
    await flushPromises()

    const downloadButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('下载模板'))
    expect(downloadButton).toBeTruthy()
    await downloadButton!.trigger('click')
    await flushPromises()

    expect(writeFile).toHaveBeenCalled()
    const args = writeFile.mock.calls[0]
    expect(args[1]).toBe('客户样本导入模板.xlsx')
    expect(aoaToSheet).toHaveBeenCalledWith([
      ['住院号', 'visit_id', '存在问题'],
      ['2248248', '', ''],
      ['', 'VISIT-001', '首次病程记录鉴别诊断不全面'],
    ])
  })

  it('导入模板成功后应切换到新样本池并刷新病历池', async () => {
    listManualSamplePools
      .mockResolvedValueOnce({
        success: true,
        data: { items: [buildPool()], total: 1, page: 1, page_size: 50 },
      })
      .mockResolvedValueOnce({
        success: true,
        data: {
          items: [
            buildPool(),
            {
              ...buildPool(),
              id: 'pool-2',
              name: '第二轮样本池',
              latest_job_id: undefined,
              latest_job_status: undefined,
            },
          ],
          total: 2,
          page: 1,
          page_size: 50,
        },
      })
    getManualSamplePoolRecords
      .mockResolvedValueOnce({
        success: true,
        data: {
          pool: buildPool(),
          items: [buildRecord()],
          total: 1,
          page: 1,
          page_size: 20,
        },
      })
      .mockResolvedValueOnce({
        success: true,
        data: {
          pool: {
            ...buildPool(),
            id: 'pool-2',
            name: '第二轮样本池',
            latest_job_id: undefined,
            latest_job_status: undefined,
          },
          items: [
            buildRecord({
              id: 'V010',
              matched_visit_id: 'V010',
              mr_no: '300001',
              patient_name: '新患者',
            }),
          ],
          total: 1,
          page: 1,
          page_size: 20,
        },
      })

    const wrapper = await mountView()

    const importButton = wrapper.findAll('button').find((node) => node.text().includes('导入模板'))
    expect(importButton).toBeTruthy()
    await importButton!.trigger('click')
    await flushPromises()

    const inputs = wrapper.findAll('input')
    const poolNameInput = inputs.find((node) =>
      node.attributes('placeholder')?.includes('手工问题样本池'),
    )
    expect(poolNameInput).toBeTruthy()
    await poolNameInput!.setValue('第二轮样本池')

    const uploadTrigger = wrapper.find('button.upload-trigger')
    expect(uploadTrigger.exists()).toBe(true)
    await uploadTrigger.trigger('click')
    await flushPromises()

    const confirmButton = wrapper.find('button.modal-ok')
    await confirmButton.trigger('click')
    await flushPromises()

    expect(importManualSamplePoolByUpload).toHaveBeenCalledWith({
      pool_name: '第二轮样本池',
      source_sheet: 'Sheet2',
      description: '',
      scene: 'running',
      file: expect.objectContaining({
        name: 'demo.xlsx',
      }),
    })
    expect(message.success).toHaveBeenCalledWith('导入成功，共写入 2 条样本')
    expect(wrapper.text()).toContain('当前样本池')
    expect(wrapper.text()).toContain('第二轮样本池')
    expect(wrapper.text()).toContain('新患者')
  })

  it('点击查看病历后打开病历联审抽屉', async () => {
    const wrapper = await mountView()

    const reviewAction = [...wrapper.findAll('button'), ...wrapper.findAll('a')].find(
      (node) => node.text() === '查看病历',
    )
    expect(reviewAction).toBeTruthy()
    await reviewAction!.trigger('click')
    await flushPromises()

    expect(wrapper.find('.qc-review-drawer-stub').exists()).toBe(true)
  })

  it('点击查看结果后打开批量任务结果抽屉', async () => {
    const wrapper = await mountView()

    const resultLink = wrapper.findAll('a').find((node) => node.text() === '查看结果')
    expect(resultLink).toBeTruthy()
    await resultLink!.trigger('click')
    await flushPromises()

    expect(getSichuanWorkspaceBatchJob).toHaveBeenCalledWith('job-1')
    expect(wrapper.find('.batch-result-drawer-stub').exists()).toBe(true)
  })

  it('只选中不可执行病历时提示并阻止发起验证', async () => {
    getManualSamplePoolRecords.mockResolvedValueOnce({
      success: true,
      data: {
        pool: buildPool(),
        items: [
          buildRecord({
            id: 'V003',
            matched_visit_id: 'V003',
            mr_no: '2250001',
            patient_name: '王五',
            sync_status: 'missing',
            bundle_status: 'pending',
          }),
        ],
        total: 1,
        page: 1,
        page_size: 20,
      },
    })
    const wrapper = await mountView()

    const recordCheckboxes = wrapper.findAll('input.record-checkbox')
    await recordCheckboxes[0].setValue(true)

    const runButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('发起选中病历验证'))
    expect(runButton).toBeTruthy()
    await runButton!.trigger('click')
    await flushPromises()

    expect(message.warning).toHaveBeenCalledWith(
      '当前选中的病历还未完成匹配、同步或 bundle 准备，暂时无法发起验证',
    )
    expect(runManualSamplePool).not.toHaveBeenCalled()
  })

  it('选中部分不可执行病历时仅提交可执行病历并提示跳过数量', async () => {
    getManualSamplePoolRecords.mockResolvedValueOnce({
      success: true,
      data: {
        pool: buildPool(),
        items: [
          buildRecord(),
          buildRecord({
            id: 'V004',
            matched_visit_id: 'V004',
            mr_no: '2250002',
            patient_name: '赵六',
            sync_status: 'missing',
            bundle_status: 'pending',
          }),
        ],
        total: 2,
        page: 1,
        page_size: 20,
      },
    })
    const wrapper = await mountView()

    const recordCheckboxes = wrapper.findAll('input.record-checkbox')
    await recordCheckboxes[0].setValue(true)
    await recordCheckboxes[1].setValue(true)

    const runButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('发起选中病历验证'))
    expect(runButton).toBeTruthy()
    await runButton!.trigger('click')
    await flushPromises()

    expect(message.info).toHaveBeenCalledWith('已选 2 份病历，其中 1 份可执行，1 份将自动跳过')
    expect(runManualSamplePool).toHaveBeenCalledWith('pool-1', {
      record_ids: ['V001'],
      max_parallel_records: 4,
      validation_mode: 'customer',
    })
  })

  it('发起验证成功后应自动打开结果抽屉并显示成功提示', async () => {
    const wrapper = await mountView()

    const recordCheckboxes = wrapper.findAll('input.record-checkbox')
    await recordCheckboxes[0].setValue(true)

    const runButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('发起选中病历验证'))
    expect(runButton).toBeTruthy()
    await runButton!.trigger('click')
    await flushPromises()

    expect(message.success).toHaveBeenCalledWith(
      '已创建客户专项规则包 v1验证任务，覆盖 1 条样本 / 1 份病历 / 5 条规则，并发 4 份病历',
    )
    expect(getSichuanWorkspaceBatchJob).toHaveBeenCalledWith('job-2')
    expect(wrapper.find('.batch-result-drawer-stub').exists()).toBe(true)
  })

  it('切换到 SC 样本规则模式后应按 sc 模式提交', async () => {
    const wrapper = await mountView()

    const selectElements = wrapper.findAll('select')
    const modeSelect = selectElements.find((node) =>
      node.findAll('option').some((option) => option.text() === 'SC 样本规则模式'),
    )
    expect(modeSelect).toBeTruthy()
    await modeSelect!.setValue('sc')

    const recordCheckboxes = wrapper.findAll('input.record-checkbox')
    await recordCheckboxes[0].setValue(true)

    const runButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('发起选中病历验证'))
    expect(runButton).toBeTruthy()
    await runButton!.trigger('click')
    await flushPromises()

    expect(runManualSamplePool).toHaveBeenCalledWith('pool-1', {
      record_ids: ['V001'],
      max_parallel_records: 4,
      validation_mode: 'sc',
    })
  })
})
