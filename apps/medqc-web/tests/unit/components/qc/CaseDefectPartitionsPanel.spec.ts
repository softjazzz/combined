import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import CaseDefectPartitionsPanel from '@/components/qc/CaseDefectPartitionsPanel.vue'

const { getPartitions, getManual, getCoding, getAnchor } = vi.hoisted(() => ({
  getPartitions: vi.fn(),
  getManual: vi.fn(),
  getCoding: vi.fn(),
  getAnchor: vi.fn(),
}))

vi.mock('@/services/sichuan-rule-workspace-service', () => ({
  getLatestLuxian0609RecordDefectPartitions: getPartitions,
}))
vi.mock('@/api/manualDefectReviews', () => ({ getCaseManualDefects: getManual, getManualDefectDocumentAnchor: getAnchor }))
vi.mock('@/api/modernCaseQcResult', () => ({ getModernCaseQcSnapshot: getCoding }))

const canonicalItems = [
  {
    rule_id: 'LX0609-001',
    rule_name: '确认缺陷一',
    status: 'non_compliant',
    conclusion: 'Canonical 结论',
    source_document: '入院记录',
  },
  {
    rule_id: 'LX0609-002',
    rule_name: '单否缺陷二',
    status: 'non_compliant',
    conclusion: '单否结论',
  },
]

function partitionPayload(overrides: Record<string, unknown> = {}) {
  return {
    schema_version: 'case-defect-partitions-v1',
    institute_id: 'H-1',
    patient_id: 'P-1',
    visit_id: 'V-1',
    state: 'ready',
    job_id: 'job-1',
    confirmed: {
      status: 'ready',
      source: 'luxian_0609_canonical_projection',
      rule_ids: ['LX0609-001'],
      reason_code: null,
    },
    veto: {
      status: 'ready',
      source: 'scoring_deductions',
      rule_ids: ['LX0609-002'],
      standard_name: '运行默认标准',
      reason_code: null,
    },
    core: {
      status: 'not_integrated',
      source: 'core_system_classification',
      reason_code: 'core_system_classification_missing',
    },
    ...overrides,
  }
}

function codingPayload(result: object | null = { id: 'coding-result', defect_count: 1 }) {
  return {
    identity_status: 'verified',
    source_key: 'coding_qc',
    institute_id: 'H-1',
    patient_id: 'P-1',
    visit_id: 'V-1',
    latest_qc_result: result,
    recent_results: [],
    active_defects: [],
    current_result_defects: result
      ? [{ id: 'coding-1', rule_code: 'CODE-1', rule_name: '编码缺陷', description: '编码说明' }]
      : [],
    active_defects_has_more: false,
    current_result_defects_has_more: false,
    active_defects_next_offset: null,
    current_result_defects_next_offset: null,
    latest_notification: null,
  }
}

function mountPanel(extraProps: Record<string, unknown> = {}) {
  return mount(CaseDefectPartitionsPanel, {
    props: {
      instituteId: 'H-1',
      patientId: 'P-1',
      visitId: 'V-1',
      jobId: 'job-1',
      scene: 'running',
      canonicalItems,
      ...extraProps,
    },
  })
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => {
    resolve = done
  })
  return { promise, resolve }
}

function tab(wrapper: ReturnType<typeof mountPanel>, label: string) {
  return wrapper.findAll('[role="tab"]').find((button) => button.text().includes(label))!
}

describe('CaseDefectPartitionsPanel', () => {
  it.each([
    ['frozen_content', undefined], ['frozen_content', ''], ['frozen_content', 123],
    ['source_ref', 'invalid source'], ['source_type', null], ['field_path', ''], ['quote', '   '],
  ])('损坏人工锚点 %s=%j 不发送定位，不能跳过冻结全文核验', async (field, value) => {
    const anchor = { source_ref: 'src_' + 'a'.repeat(24), source_type: 'course_record',
      field_path: 'text', quote: '摘录', frozen_content: '原文摘录' }
    getManual.mockResolvedValue({ success: true, data: { items: [{
      id: 'manual-1', institute_id: 'H-1', patient_id: 'P-1', visit_id: 'V-1', job_id: 'job-1',
      manual_review_status: 'approved', rule_name: '合成问题', document_anchor: anchor,
    }], total: 1, offset: 0, limit: 200 } })
    getAnchor.mockResolvedValue({ success: true, data: {
      available: true, defect_id: 'manual-1', job_id: 'job-1', institute_id: 'H-1',
      patient_id: 'P-1', visit_id: 'V-1', scene: 'running', source: 'task_manual_defect',
      anchor: { ...anchor, [field]: value },
    } })
    const wrapper = mountPanel({ initialTab: 'manual' })
    await flushPromises()
    await wrapper.findAll('button').find((button) => button.text().includes('人工录入原文'))!.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('人工文书证据缺少完整来源或冻结正文')
    expect(wrapper.emitted('locate-evidence')).toBeUndefined()
    wrapper.unmount()
  })

  it('完整人工锚点保留录入时冻结全文并发送定位', async () => {
    const anchor = { source_ref: 'src_' + 'a'.repeat(24), source_type: 'course_record',
      field_path: 'text', quote: '摘录', frozen_content: '原文摘录' }
    getManual.mockResolvedValue({ success: true, data: { items: [{
      id: 'manual-1', institute_id: 'H-1', patient_id: 'P-1', visit_id: 'V-1', job_id: 'job-1',
      manual_review_status: 'approved', rule_name: '合成问题', document_anchor: anchor,
    }], total: 1, offset: 0, limit: 200 } })
    getAnchor.mockResolvedValue({ success: true, data: {
      available: true, defect_id: 'manual-1', job_id: 'job-1', institute_id: 'H-1',
      patient_id: 'P-1', visit_id: 'V-1', scene: 'running', source: 'task_manual_defect', anchor,
    } })
    const wrapper = mountPanel({ initialTab: 'manual' })
    await flushPromises()
    await wrapper.findAll('button').find((button) => button.text().includes('人工录入原文'))!.trigger('click')
    await flushPromises()
    expect(wrapper.emitted('locate-evidence')?.[0]?.[0]).toMatchObject({
      source: 'task_manual_defect', manualDefectId: 'manual-1',
      evidence: { manual_frozen_content: '原文摘录', evidence_excerpt: '摘录' },
    })
    wrapper.unmount()
  })

  it('人工锚点点击才读取单条正文，当前文书变化不发送定位', async () => {
    getManual.mockResolvedValue({ success: true, data: { items: [{
      id: 'manual-1', institute_id: 'H-1', patient_id: 'P-1', visit_id: 'V-1', job_id: 'job-1',
      manual_review_status: 'pending', rule_name: '合成问题',
      document_anchor: { source_ref: 'src_' + 'a'.repeat(24), source_type: 'course_record', field_path: 'text', quote: '摘录' },
    }], total: 1, offset: 0, limit: 200 } })
    getAnchor.mockResolvedValue({ success: true, data: { available: false, reason: '当前文书已变化', anchor: null } })
    const wrapper = mountPanel({ initialTab: 'manual' })
    await flushPromises()
    expect(getAnchor).not.toHaveBeenCalled()
    await wrapper.findAll('button').find((button) => button.text().includes('人工录入原文'))!.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('当前文书已变化')
    expect(wrapper.emitted('locate-evidence')).toBeUndefined()
  })
  it.each([null, {}, [{ id: 'CORE-15', name: '病历管理制度', rule_ids: null }]])(
    '核心制度分组回执损坏时不渲染为正常分类 %j',
    async (systems) => {
      getPartitions.mockResolvedValue({
        success: true,
        data: partitionPayload({
          core: {
            status: 'ready',
            source: 'core_system_classification',
            rule_ids: ['LX0609-001'],
            unknown_rule_ids: [],
            systems,
          },
        }),
      })
      const wrapper = mountPanel()
      await flushPromises()
      await tab(wrapper, '核心制度').trigger('click')
      expect(wrapper.text()).toContain('核心制度分区引用不可用')
      expect(wrapper.find('[data-testid="partition-locate-evidence"]').exists()).toBe(false)
      wrapper.unmount()
    },
  )
  it('核心制度显示冻结归属的确认缺陷并复用文书定位，不展示未确认规则', async () => {
    const evidence = {
      source_ref: 'safe-admission-ref',
      source_type: 'admission_record',
      field_path: 'chief_complaint',
      quote: '合成证据',
    }
    getPartitions.mockResolvedValue({
      success: true,
      data: partitionPayload({
        core: {
          status: 'ready',
          source: 'core_system_classification',
          reason_code: null,
          rule_ids: ['LX0609-001'],
          unknown_rule_ids: [],
          systems: [{ id: 'CORE-15', name: '病历管理制度', rule_ids: ['LX0609-001'] }],
        },
      }),
    })
    const wrapper = mountPanel({
      canonicalItems: [{ ...canonicalItems[0], evidence: [evidence] }, canonicalItems[1]],
    })
    await flushPromises()
    await tab(wrapper, '核心制度').trigger('click')
    expect(wrapper.text()).toContain('病历管理制度')
    expect(wrapper.text()).toContain('确认缺陷一')
    expect(wrapper.text()).not.toContain('单否缺陷二')
    await wrapper.get('[data-testid="partition-locate-evidence"]').trigger('click')
    expect(wrapper.emitted('locate-evidence')?.[0]?.[0]).toMatchObject({
      jobId: 'job-1',
      ruleId: 'LX0609-001',
    })
  })
  it('只把当前确认缺陷的既有文书依据连同三坐标和作业传给联审', async () => {
    const evidence = {
      source_ref: 'safe-admission-ref',
      source_type: 'admission_record',
      field_path: 'chief_complaint',
    }
    const wrapper = mountPanel({ canonicalItems: [{ ...canonicalItems[0], evidence: [evidence] }] })
    await flushPromises()
    await wrapper.get('[data-testid="partition-locate-evidence"]').trigger('click')
    expect(wrapper.emitted('locate-evidence')?.[0]).toEqual([
      {
        instituteId: 'H-1',
        patientId: 'P-1',
        visitId: 'V-1',
        jobId: 'job-1',
        ruleId: 'LX0609-001',
        evidence,
      },
    ])
    wrapper.unmount()
  })

  it('没有可信文书依据时不以规则目录文书名伪造定位', async () => {
    const wrapper = mountPanel()
    await flushPromises()
    expect(wrapper.find('[data-testid="partition-locate-evidence"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('未提供可定位的文书依据')
    wrapper.unmount()
  })

  beforeEach(() => {
    getPartitions.mockReset().mockResolvedValue({ success: true, data: partitionPayload() })
    getManual.mockReset().mockResolvedValue({
      success: true,
      data: {
        total: 1,
        items: [
          {
            id: 'manual-1',
            institute_id: 'H-1',
            patient_id: 'P-1',
            visit_id: 'V-1',
            rule_name: '人工缺陷',
            description: '人工说明',
            manual_review_status: 'approved',
          },
        ],
      },
    })
    getCoding.mockReset().mockResolvedValue(codingPayload())
  })

  it('并行读取三个既有 owner，并按五分区切换真实条目', async () => {
    const wrapper = mountPanel()
    await flushPromises()

    expect(getPartitions).toHaveBeenCalledWith({
      instituteId: 'H-1',
      patientId: 'P-1',
      visitId: 'V-1',
      scene: 'running',
    })
    expect(getManual).toHaveBeenCalledWith({
      institute_id: 'H-1',
      patient_id: 'P-1',
      visit_id: 'V-1',
      scene: 'running',
    })
    expect(getCoding).toHaveBeenCalledWith(
      { institute_id: 'H-1', patient_id: 'P-1', visit_id: 'V-1', source_key: 'coding_qc' },
      { defects_limit: 50 },
    )
    expect(wrapper.text()).toContain('确认缺陷一')
    expect(wrapper.text()).toContain('入院记录')
    expect(wrapper.text()).not.toContain('各分区按权威来源读取')
    expect(wrapper.text()).not.toContain('可在下方文书对照')
    expect(wrapper.text()).not.toContain('单否缺陷二')

    await tab(wrapper, '单否').trigger('click')
    expect(wrapper.text()).toContain('单否缺陷二')
    expect(wrapper.text()).toContain('评分标准：运行默认标准')
    await tab(wrapper, '人工').trigger('click')
    expect(wrapper.text()).toContain('人工缺陷')
    expect(wrapper.text()).toContain('审核通过')
    await tab(wrapper, '编码').trigger('click')
    expect(wrapper.text()).toContain('编码缺陷')
    await tab(wrapper, '核心制度').trigger('click')
    expect(wrapper.text()).toContain('未配置核心制度归属（未知）')
  })

  it('未配置评分标准与未做编码质控均不伪造零', async () => {
    getPartitions.mockResolvedValue({
      success: true,
      data: partitionPayload({
        veto: {
          status: 'no_standard',
          source: 'scoring_deductions',
          rule_ids: [],
          standard_name: null,
          reason_code: null,
        },
      }),
    })
    getCoding.mockResolvedValue(codingPayload(null))
    const wrapper = mountPanel()
    await flushPromises()

    await tab(wrapper, '单否').trigger('click')
    expect(wrapper.text()).toContain('未配置评分标准')
    expect(tab(wrapper, '单否').text()).toContain('—')
    await tab(wrapper, '编码').trigger('click')
    expect(wrapper.text()).toContain('未做编码质控')
    expect(tab(wrapper, '编码').text()).toContain('—')
  })

  it('单否为零条时仍展示实际使用的默认评分标准', async () => {
    getPartitions.mockResolvedValue({
      success: true,
      data: partitionPayload({
        veto: {
          status: 'ready',
          source: 'scoring_deductions',
          rule_ids: [],
          standard_name: '运行默认标准',
          reason_code: null,
        },
      }),
    })
    const wrapper = mountPanel()
    await flushPromises()

    await tab(wrapper, '单否').trigger('click')
    expect(wrapper.text()).toContain('评分标准：运行默认标准')
    expect(wrapper.text()).toContain('当前分区暂无缺陷')
  })

  it('人工显示分页总数，编码保留既有预览行为', async () => {
    getManual.mockResolvedValue({
      success: true,
      data: {
        total: 2,
        items: [
          {
            id: 'manual-1',
            institute_id: 'H-1',
            patient_id: 'P-1',
            visit_id: 'V-1',
            manual_review_status: 'pending',
          },
        ],
      },
    })
    getCoding.mockResolvedValue({
      ...codingPayload({ id: 'coding-result', defect_count: 3 }),
      current_result_defects_has_more: true,
    })
    const wrapper = mountPanel()
    await flushPromises()

    await tab(wrapper, '人工').trigger('click')
    expect(wrapper.text()).toContain('第 1 页，共 2 条')
    await tab(wrapper, '编码').trigger('click')
    expect(wrapper.text()).toContain('预览本次前 1 条，共 3 条')
  })

  it('按具体人工缺陷ID定位，当前页没有目标时提示翻页', async () => {
    getManual.mockResolvedValue({
      success: true,
      data: {
        total: 201,
        items: [
          {
            id: 'manual-1',
            institute_id: 'H-1',
            patient_id: 'P-1',
            visit_id: 'V-1',
            manual_review_status: 'approved',
          },
        ],
      },
    })
    const wrapper = mountPanel({
      initialTab: 'manual',
      initialTarget: { source: 'manual', defectId: 'manual-201' },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('目标人工缺陷 manual-201 不在当前页，可翻页查找')
    expect(wrapper.find('.case-defect-partitions__item.is-target').exists()).toBe(false)
    getManual.mockResolvedValue({
      success: true,
      data: {
        total: 201,
        offset: 200,
        limit: 200,
        items: [
          {
            id: 'manual-201',
            institute_id: 'H-1',
            patient_id: 'P-1',
            visit_id: 'V-1',
            manual_review_status: 'approved',
          },
        ],
      },
    })
    await wrapper.get('[aria-label="下一页人工缺陷"]').trigger('click')
    await flushPromises()
    expect(getManual).toHaveBeenLastCalledWith({
      institute_id: 'H-1',
      patient_id: 'P-1',
      visit_id: 'V-1',
      scene: 'running',
      offset: 200,
      limit: 200,
    })
    expect(wrapper.find('.case-defect-partitions__item.is-target').exists()).toBe(true)
    expect(wrapper.get('[aria-label="下一页人工缺陷"]').attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('第 2 页，共 201 条')
    wrapper.unmount()
  })

  it('翻页后病例切换丢弃旧人工缺陷响应', async () => {
    getManual.mockResolvedValueOnce({ success: true, data: { items: [], total: 201 } })
    const wrapper = mountPanel({ initialTab: 'manual' })
    await flushPromises()
    const late = deferred<unknown>()
    getManual
      .mockReturnValueOnce(late.promise)
      .mockResolvedValue({ success: true, data: { items: [], total: 0 } })
    await wrapper.get('[aria-label="下一页人工缺陷"]').trigger('click')
    await wrapper.setProps({ patientId: 'P-2', jobId: 'job-2' })
    await flushPromises()
    late.resolve({
      success: true,
      data: {
        offset: 200,
        limit: 200,
        total: 201,
        items: [{ institute_id: 'H-1', patient_id: 'P-1', visit_id: 'V-1', id: 'old' }],
      },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('第 1 页，共 0 条')
    expect(wrapper.text()).not.toContain('201 条')
    wrapper.unmount()
  })

  it('翻页回执游标不一致时保留错误而不冒认新页', async () => {
    getManual.mockResolvedValueOnce({ success: true, data: { items: [], total: 201 } })
    const wrapper = mountPanel({ initialTab: 'manual' })
    await flushPromises()
    getManual.mockResolvedValueOnce({
      success: true,
      data: { items: [], total: 201, offset: 0, limit: 200 },
    })
    await wrapper.get('[aria-label="下一页人工缺陷"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('人工缺陷读取失败')
    expect(wrapper.text()).toContain('第 1 页，共 201 条')
    wrapper.unmount()
  })

  it('按具体Canonical规则定位并高亮', async () => {
    const wrapper = mountPanel({
      initialTarget: { source: 'auto', ruleId: 'LX0609-001' },
    })
    await flushPromises()

    expect(wrapper.get('.case-defect-partitions__item.is-target').text()).toContain('确认缺陷一')
  })

  it('各 owner 错误独立展示，刷新可恢复', async () => {
    getPartitions.mockResolvedValueOnce({ success: false, message: 'Canonical 暂不可用' })
    getManual.mockResolvedValueOnce({ success: false, message: '人工来源暂不可用' })
    getCoding.mockRejectedValueOnce(new Error('coding failed'))
    const wrapper = mountPanel()
    await flushPromises()
    expect(wrapper.text()).toContain('Canonical 暂不可用')

    await tab(wrapper, '人工').trigger('click')
    expect(wrapper.text()).toContain('人工来源暂不可用')
    await tab(wrapper, '编码').trigger('click')
    expect(wrapper.text()).toContain('编码质控结果暂时不可用')

    await wrapper.get('.case-defect-partitions__refresh').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('编码缺陷')
  })

  it('三坐标或job不一致时拒绝展示Canonical分区', async () => {
    getPartitions.mockResolvedValue({
      success: true,
      data: partitionPayload({ job_id: 'other-job' }),
    })
    const wrapper = mountPanel()
    await flushPromises()
    expect(wrapper.text()).toContain('与当前病例结果不一致')
    expect(wrapper.text()).not.toContain('Canonical 结论')
  })

  it('人工缺陷身份串案时失败关闭', async () => {
    getManual.mockResolvedValue({
      success: true,
      data: {
        total: 1,
        items: [
          {
            id: 'bad',
            institute_id: 'H-2',
            patient_id: 'P-1',
            visit_id: 'V-1',
            manual_review_status: 'pending',
          },
        ],
      },
    })
    const wrapper = mountPanel()
    await flushPromises()
    await tab(wrapper, '人工').trigger('click')
    expect(wrapper.text()).toContain('身份校验失败')
  })

  it('快速切换到新结果后丢弃旧job的迟到分区响应', async () => {
    const first = deferred<{ success: boolean; data: ReturnType<typeof partitionPayload> }>()
    getPartitions.mockReturnValueOnce(first.promise).mockResolvedValueOnce({
      success: true,
      data: partitionPayload({
        patient_id: 'P-2',
        job_id: 'job-2',
        confirmed: {
          status: 'ready',
          source: 'luxian_0609_canonical_projection',
          rule_ids: ['LX0609-002'],
          reason_code: null,
        },
      }),
    })
    const wrapper = mountPanel()
    await wrapper.setProps({
      patientId: 'P-2',
      jobId: 'job-2',
      canonicalItems: canonicalItems.slice(1, 2),
    })
    await flushPromises()
    expect(wrapper.text()).toContain('单否缺陷二')

    first.resolve({ success: true, data: partitionPayload() })
    await flushPromises()
    expect(wrapper.text()).toContain('单否缺陷二')
    expect(wrapper.text()).not.toContain('确认缺陷一')
  })
})
