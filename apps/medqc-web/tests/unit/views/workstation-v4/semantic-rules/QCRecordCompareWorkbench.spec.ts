import { ApiService } from '@/services/apiService'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import QCRecordCompareWorkbench from '@/views/workstation-v4/semantic-rules/components/QCRecordCompareWorkbench.vue'
import SingleRecordQcResultPanel from '@/views/workstation-v4/customer-sample-validation/SingleRecordQcResultPanel.vue'
import type { QCRecordCompareIssue } from '@/views/workstation-v4/semantic-rules/types'

const { getDocumentsMock, getDocumentMock } = vi.hoisted(() => ({
  getDocumentsMock: vi.fn(),
  getDocumentMock: vi.fn(),
}))

vi.mock('@/services/manual-case-sample-service', () => ({
  getEditableMedicalRecordDocuments: getDocumentsMock,
  getEditableMedicalRecordDocument: getDocumentMock,
}))

const issues: QCRecordCompareIssue[] = [
  {
    key: 'issue-compliant',
    rule_code: 'LX0609-01-02-01',
    rule_name: '首次病程记录完整性',
    status: 'compliant',
    status_text: '合规',
    result_kind_text: '合规',
    conclusion: '首次病程记录内容完整。',
    suggestion: '无需处理。',
    target_document_type: 'first_course_record',
    evidences: [],
  },
  {
    key: 'issue-danger',
    rule_code: 'LX0609-01-01-01',
    rule_name: '首次病程记录及时性',
    status: 'non_compliant',
    status_text: '不合规',
    result_kind_text: '确定问题',
    conclusion: '首次病程记录超过时限。',
    suggestion: '请及时完成首次病程记录。',
    target_document_type: 'first_course_record',
    evidences: [
      {
        key: 'evidence-1',
        source_document_id: 'doc-first-course',
        source_document_type: 'first_course_record',
        source_document_name: '首次病程记录',
        record_time: '2026-07-24 11:00:00',
        quote: '患者入院后第九小时完成首次病程记录',
      },
    ],
  },
]

// 原有完整视图用例固定为开发身份；演示身份在专项用例中显式切换。
beforeEach(async () => {
  setActivePinia(createPinia())
  vi.spyOn(ApiService, 'isAuthenticated').mockReturnValue(true)
  vi.spyOn(ApiService, 'getCurrentUser').mockResolvedValue({
    success: true,
    data: { id: 'test-developer', roles: ['sync_admin'], is_demo_account: true },
  })
  await useAuthStore().initialize()
})

describe('QCRecordCompareWorkbench', () => {
  it('查看病历实际阅读入口优先渲染系统首页表单而非普通分节正文', async () => {
    const wrapper = mount(QCRecordCompareWorkbench, {
      props: {
        visitId: 'frontpage-visit',
        issues: [],
        documentOnly: true,
        providedDocuments: [
          {
            key: 'frontpage',
            document_type: 'mr',
            title: '病案首页',
            content: '旧版字段拼接正文',
            sections: [{ key: 'basic', label: '首页基本信息', text: '旧版字段拼接正文' }],
            frontpage_display: {
              groups: [
                {
                  key: 'basic',
                  label: '首页基本信息',
                  fields: [{ key: 'mr_no', label: '病案号', value: 'TEST-MR' }],
                },
              ],
              diagnoses: { columns: [], rows: [] },
              surgeries: { columns: [], rows: [] },
            },
          },
        ],
      },
    })
    await flushPromises()
    expect(wrapper.find('[data-testid="readonly-frontpage"]').exists()).toBe(true)
    expect(wrapper.find('.fp-wrapper').exists()).toBe(true)
    expect(wrapper.find('.record-content-sections').exists()).toBe(false)
    expect(wrapper.find('.record-content-column').text()).toContain('TEST-MR')
    expect(wrapper.find('.record-content-column').text()).not.toContain('AI辅助')
    wrapper.unmount()
  })

  it('缺记录时间时显示提交时间及其来源标签', async () => {
    const wrapper = mount(QCRecordCompareWorkbench, {
      props: {
        visitId: 'V1',
        issues: [],
        documentOnly: true,
        providedDocuments: [
          {
            key: 'consult-1',
            document_type: 'consultation_record',
            title: '会诊记录',
            content: '会诊意见',
            record_time: '2026-06-01 09:10:00',
            submit_time: '2026-06-01 09:10:00',
            record_time_source: 'source_submit_time',
          },
        ],
      },
    })
    await flushPromises()
    expect(wrapper.find('.record-content-time').text()).toContain('提交时间')
    expect(wrapper.find('.record-content-time').text()).toContain('2026-06-01 09:10:00')
    wrapper.unmount()
  })
  beforeEach(() => {
    getDocumentsMock.mockReset()
    getDocumentMock.mockReset()
    getDocumentsMock.mockResolvedValue({
      success: true,
      data: {
        visit_id: 'visit-1',
        documents: [
          {
            key: 'first-course-key',
            source_document_id: 'doc-first-course',
            source_table: 'first_course_record',
            document_type: 'first_course_record',
            title: '首次病程记录',
            record_time: '2026-07-24 11:00:00',
            content: '患者入院后第九小时完成首次病程记录，已超过规定时限。',
          },
          {
            key: 'daily-course-key',
            source_document_id: 'doc-daily',
            source_table: 'daily_course_record',
            document_type: 'daily_course_record',
            title: '日常病程记录',
            record_time: '2026-07-25 09:00:00',
            content: '患者今日病情稳定，继续原治疗方案。',
          },
        ],
      },
    })
  })

  it('结果对照读取当前完整文书，历史目录为空也能显示原文', async () => {
    getDocumentsMock.mockImplementation(async (_visit, params) => ({
      success: true,
      data: {
        documents:
          params.source_view === 'current' && params.view === 'full'
            ? [
                {
                  key: 'current-admission',
                  title: '入院记录',
                  document_type: 'admission_record',
                  content: '当前文书完整正文及末尾内容',
                },
              ]
            : [],
      },
    }))
    const wrapper = mount(QCRecordCompareWorkbench, {
      props: {
        visitId: 'V1',
        instituteId: 'H1',
        patientId: 'P1',
        issues: [],
        sourceView: 'current',
      },
    })
    await flushPromises()
    expect(wrapper.find('.record-content-column').text()).toContain('当前文书完整正文及末尾内容')
    expect(wrapper.text()).toContain('当前病历可能已更新，质控结果仍为执行时结果')
    expect(getDocumentMock).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('只读文书复用目录与正文，优先入院记录并禁止回退历史接口', async () => {
    const wrapper = mount(QCRecordCompareWorkbench, {
      props: {
        visitId: 'visit-current',
        issues: [],
        documentOnly: true,
        providedDocuments: [
          {
            key: 'current-order',
            title: '长期医嘱',
            document_type: 'inpat_drug_order',
            source_table: 'inpat_drug_order',
            content: '观察生命体征',
            content_loaded: false,
          },
          {
            key: 'current-admission',
            title: '入院记录',
            document_type: 'admission_record',
            source_table: 'admission_record',
            content: '当前入院主诉',
            content_loaded: false,
          },
        ],
      },
    })
    await flushPromises()

    expect(wrapper.find('.record-content-column').text()).toContain('当前入院主诉')
    expect(wrapper.find('.record-result-column').exists()).toBe(false)
    expect(wrapper.find('.record-compare-mobile-tabs').exists()).toBe(false)
    expect(wrapper.find('.record-location-chip').exists()).toBe(false)
    await wrapper.find('[data-testid="record-document-filter-order"]').trigger('click')
    await wrapper.find('[data-testid="record-document-group-toggle-order"]').trigger('click')
    await wrapper.find('.record-document-item').trigger('click')
    expect(wrapper.find('.record-content-column').text()).toContain('观察生命体征')

    await wrapper.setProps({
      providedDocuments: [
        {
          key: 'next-admission',
          title: '入院记录',
          document_type: 'admission_record',
          content: '更新后的入院内容',
        },
      ],
    })
    await flushPromises()
    expect(wrapper.find('.record-content-column').text()).toContain('更新后的入院内容')
    await wrapper.setProps({ providedDocuments: [] })
    expect(wrapper.text()).toContain('暂无病历文书')
    expect(getDocumentsMock).not.toHaveBeenCalled()
    expect(getDocumentMock).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('出院记录分别显示出院时间与文书记录时间，缺值不替代', async () => {
    const wrapper = mount(QCRecordCompareWorkbench, {
      props: {
        visitId: 'visit-discharge',
        issues: [],
        documentOnly: true,
        dischargeTime: '2026-07-24 10:00:00',
        providedDocuments: [
          {
            key: 'discharge',
            document_type: 'discharge_record',
            title: '出院记录',
            record_time: '2026-07-24 11:30:00',
            content: '出院情况',
          },
        ],
      },
    })
    await flushPromises()
    expect(wrapper.get('[data-testid="record-discharge-time"]').text()).toContain(
      '2026-07-24 10:00:00',
    )
    expect(wrapper.get('.record-content-toolbar').text()).toContain('2026-07-24 11:30:00')
    await wrapper.setProps({ dischargeTime: '' })
    expect(wrapper.find('[data-testid="record-discharge-time"]').exists()).toBe(false)
    await wrapper.setProps({
      dischargeTime: '2026-07-24 10:00:00',
      providedDocuments: [
        {
          key: 'admission',
          document_type: 'admission_record',
          title: '入院记录',
          content: '入院情况',
        },
      ],
    })
    await flushPromises()
    expect(wrapper.find('[data-testid="record-discharge-time"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('先读取轻量目录并只按需加载证据文书正文', async () => {
    getDocumentsMock.mockResolvedValue({
      success: true,
      data: {
        visit_id: 'visit-1',
        documents: [
          {
            key: 'admission-key',
            source_document_id: 'doc-admission',
            source_table: 'admission_record',
            document_type: 'admission_record',
            execution_domain: 'admission',
            title: '入院记录',
            record_time: '2026-07-24 08:00:00',
            has_content: true,
            content_loaded: false,
            content: '',
          },
          {
            key: 'first-course-key',
            source_document_id: 'doc-first-course',
            source_table: 'first_course_record',
            document_type: 'first_course_record',
            execution_domain: 'course',
            title: '首次病程记录',
            record_time: '2026-07-24 11:00:00',
            has_content: true,
            content_loaded: false,
            content: '',
          },
        ],
      },
    })
    getDocumentMock.mockResolvedValue({
      success: true,
      data: {
        key: 'first-course-key',
        source_document_id: 'doc-first-course',
        source_table: 'first_course_record',
        document_type: 'first_course_record',
        execution_domain: 'course',
        title: '首次病程记录',
        record_time: '2026-07-24 11:00:00',
        has_content: true,
        content_loaded: true,
        content: '患者入院后第九小时完成首次病程记录，已超过规定时限。',
      },
    })

    const wrapper = mount(QCRecordCompareWorkbench, {
      props: {
        visitId: 'visit-1',
        instituteId: 'inst-1',
        patientId: 'patient-1',
        issues,
      },
    })

    await flushPromises()
    await wrapper.vm.$nextTick()

    expect(getDocumentsMock).toHaveBeenCalledTimes(1)
    expect(getDocumentsMock).toHaveBeenCalledWith('visit-1', {
      institute_id: 'inst-1',
      patient_id: 'patient-1',
      visit_id: 'visit-1',
      view: 'summary',
    })
    expect(getDocumentMock).toHaveBeenCalledTimes(1)
    expect(getDocumentMock).toHaveBeenCalledWith(
      'visit-1',
      expect.objectContaining({
        key: 'first-course-key',
        execution_domain: 'course',
      }),
      {
        institute_id: 'inst-1',
        patient_id: 'patient-1',
        visit_id: 'visit-1',
      },
    )
    expect(wrapper.find('mark').text()).toBe('患者入院后第九小时完成首次病程记录')
    expect(wrapper.text()).toContain('已定位到证据段落')
  })

  it('按问题优先级排列，并用文书ID精确定位及高亮证据', async () => {
    const wrapper = mount(QCRecordCompareWorkbench, {
      props: {
        visitId: 'visit-1',
        instituteId: 'inst-1',
        patientId: 'patient-1',
        issues,
      },
    })

    await flushPromises()
    await wrapper.vm.$nextTick()

    expect(getDocumentsMock).toHaveBeenCalledWith('visit-1', {
      institute_id: 'inst-1',
      patient_id: 'patient-1',
      visit_id: 'visit-1',
      view: 'summary',
    })
    const resultItems = wrapper.findAll('.record-result-item')
    expect(resultItems[0]?.text()).toContain('LX0609-01-01-01')
    expect(resultItems[1]?.text()).toContain('LX0609-01-02-01')
    expect(wrapper.find('.record-content-toolbar').text()).toContain('首次病程记录')
    expect(wrapper.find('.record-content-toolbar').text()).toContain('记录时间')
    expect(wrapper.find('.record-content-toolbar').text()).toContain('2026-07-24 11:00:00')
    expect(wrapper.find('mark').text()).toBe('患者入院后第九小时完成首次病程记录')
    expect(wrapper.text()).toContain('已定位到证据段落')
    expect(wrapper.text()).not.toContain('first_course_record')
    expect(wrapper.text()).not.toContain('daily_course_record')
  })

  it('使用客户安全文书引用精确定位文书且没有片段时不伪造高亮', async () => {
    getDocumentsMock.mockResolvedValue({
      success: true,
      data: {
        visit_id: 'visit-1',
        documents: [
          {
            key: 'wrong-key',
            source_document_id: 'raw-document-id-must-not-be-required',
            source_ref: 'src_1234567890abcdef12345678',
            source_table: 'first_course_record',
            document_type: 'first_course_record',
            title: '首次病程记录',
            record_time: '2026-07-24 11:00:00',
            content: '患者入院后完成首次病程记录。',
          },
          {
            key: 'right-key',
            source_ref: 'src_abcdef1234567890abcdef12',
            source_table: 'first_course_record',
            document_type: 'first_course_record',
            title: '首次病程记录',
            record_time: '2026-07-24 11:00:00',
            content: '患者今日病情稳定。',
          },
        ],
      },
    })

    const wrapper = mount(QCRecordCompareWorkbench, {
      props: {
        visitId: 'visit-1',
        instituteId: 'inst-1',
        patientId: 'patient-1',
        jobId: 'job-safe-1',
        recordRef: 'rec_1234567890abcdef12345678',
        issues: [
          {
            ...issues[1]!,
            key: 'issue-safe-ref',
            evidences: [
              {
                key: 'safe-evidence',
                source_ref: 'src_abcdef1234567890abcdef12',
                source_document_type: 'first_course_record',
                quote: '',
              },
            ],
          },
        ],
      },
    })

    await flushPromises()

    expect(getDocumentsMock).toHaveBeenCalledWith('visit-1', {
      institute_id: 'inst-1',
      patient_id: 'patient-1',
      visit_id: 'visit-1',
      job_id: 'job-safe-1',
      record_ref: 'rec_1234567890abcdef12345678',
      view: 'summary',
    })
    expect(
      (wrapper.find('.record-document-select select').element as HTMLSelectElement).value,
    ).toBe('right-key')
    expect(wrapper.text()).toContain('已定位到文书，未定位到具体片段')
    expect(wrapper.find('mark').exists()).toBe(false)
  })

  it('检验申请汇总通过原始文书安全别名加载并定位证据', async () => {
    getDocumentsMock.mockResolvedValue({
      success: true,
      data: {
        visit_id: 'visit-1',
        documents: [
          {
            key: 'labtest_master::summary',
            source_document_id: 'labtest-master-summary',
            source_ref: 'src_labtest_summary',
            source_table: 'labtest_master',
            document_type: 'labtest_master',
            title: '检验申请汇总（2）',
            execution_domain: 'course',
            has_content: true,
            content_loaded: false,
            content: '',
            source_document_aliases: [
              {
                source_document_id: 'LAB-M-2',
                source_ref: 'src_labtest_m2',
                source_document_type: 'labtest_master',
              },
            ],
          },
        ],
      },
    })
    getDocumentMock.mockResolvedValue({
      success: true,
      data: {
        key: 'labtest_master::summary',
        source_document_id: 'LAB-M-2',
        source_table: 'labtest_master',
        document_type: 'labtest_master',
        title: '检验申请单',
        execution_domain: 'course',
        has_content: true,
        content_loaded: true,
        content: '检验项目：肝功能；申请原因：评估肝功能。',
      },
    })

    const wrapper = mount(QCRecordCompareWorkbench, {
      props: {
        visitId: 'visit-1',
        instituteId: 'inst-1',
        patientId: 'patient-1',
        issues: [
          {
            ...issues[1]!,
            key: 'issue-lab-alias',
            target_document_type: 'labtest_master',
            evidences: [
              {
                key: 'lab-alias-evidence',
                source_ref: 'src_labtest_m2',
                source_document_type: 'labtest_master',
                quote: '检验项目：肝功能；申请原因：评估肝功能。',
              },
            ],
          },
        ],
      },
    })

    await flushPromises()

    expect(getDocumentMock).toHaveBeenCalledWith(
      'visit-1',
      expect.objectContaining({
        key: 'labtest_master::summary',
        source_document_id: 'LAB-M-2',
        source_ref: 'src_labtest_m2',
      }),
      {
        institute_id: 'inst-1',
        patient_id: 'patient-1',
        visit_id: 'visit-1',
      },
    )
    expect(wrapper.find('mark').text()).toBe('检验项目：肝功能；申请原因：评估肝功能。')
    expect(wrapper.text()).toContain('已定位到证据段落')
  })

  it('单病历固定结果模型只使用安全证据引用定位原文，不走批量结果旧卡片', async () => {
    getDocumentsMock.mockResolvedValue({
      success: true,
      data: {
        visit_id: 'visit-1',
        documents: [
          {
            key: 'admission-key',
            source_ref: 'src_admission_018',
            source_table: 'admission_record',
            document_type: 'admission_record',
            title: '入院记录',
            record_time: '2026-07-24 11:00:00',
            content: '主诉：反复咳嗽，咳痰，气促。',
          },
        ],
      },
    })

    const wrapper = mount(QCRecordCompareWorkbench, {
      props: {
        visitId: 'visit-1',
        jobId: 'job-safe-1',
        recordRef: 'rec_1234567890abcdef12345678',
        issues: [],
        singleRecordItems: [
          {
            rule_id: 'LX0609-01-01-02',
            rule_name: '主诉能导出第一诊断',
            status: 'non_compliant',
            conclusion: '主诉字数超过20字。',
            criterion_results: [
              {
                criterion_id: 'chief_complaint_length',
                kind: 'text_length',
                status: 'failed',
                reason_code: 'complaint_too_long',
                actual_value: 21,
                expected_value: 20,
              },
            ],
            evidence: [
              {
                source_ref: 'src_admission_018',
                source_type: 'admission_record',
                source_label: '入院记录—主诉',
                field_path: 'chief_complaint',
                evidence_excerpt: '反复咳嗽，咳痰，气促',
              },
            ],
          },
        ],
      },
    })

    await flushPromises()
    await wrapper.find('.single-record-result-panel .result-trigger').trigger('click')
    await flushPromises()

    expect(wrapper.find('.single-record-result-panel').exists()).toBe(true)
    expect(wrapper.find('.record-result-list').exists()).toBe(false)
    expect(wrapper.find('mark').text()).toBe('反复咳嗽，咳痰，气促')
    expect(wrapper.text()).toContain('已定位到证据段落')
  })

  it('只把单病历报告展示模式透传给结果面板，不改写固定结果条目', async () => {
    const singleRecordItems = [
      {
        rule_id: 'LX0609-04-02-04',
        rule_name: '植入物相关记录',
        source_document: '手术记录',
        status: 'non_compliant',
        conclusion: '植入物记录不完整。',
      },
    ]
    const wrapper = mount(QCRecordCompareWorkbench, {
      props: {
        visitId: 'visit-1',
        issues: [],
        singleRecordItems,
        presentationMode: 'grouped',
        debugContext: { patientId: 'patient-1', visitId: 'visit-1', jobId: 'job-1' },
      },
    })

    await flushPromises()

    const panel = wrapper.getComponent(SingleRecordQcResultPanel)
    expect(panel.props('presentationMode')).toBe('grouped')
    expect(panel.props('items')).toEqual(singleRecordItems)
    expect(panel.props('debugContext')).toEqual({
      patientId: 'patient-1',
      visitId: 'visit-1',
      jobId: 'job-1',
    })
  })

  it('客户安全文书引用未命中时不得按相同片段猜测其他文书', async () => {
    const wrapper = mount(QCRecordCompareWorkbench, {
      props: {
        visitId: 'visit-1',
        issues: [
          {
            ...issues[1]!,
            key: 'issue-missing-safe-ref',
            evidences: [
              {
                key: 'missing-safe-evidence',
                source_ref: 'src_ffffffffffffffffffffffff',
                source_document_type: 'first_course_record',
                quote: '患者入院后第九小时完成首次病程记录',
              },
              {
                key: 'unsafe-quote-fallback',
                source_document_type: 'daily_course_record',
                quote: '患者今日病情稳定，继续原治疗方案。',
              },
            ],
          },
        ],
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('未找到对应文书，请手动核对')
    expect(wrapper.find('mark').exists()).toBe(false)
  })

  it('只返回内部文书类型时应转换成中文名称并突出记录时间', async () => {
    getDocumentsMock.mockResolvedValue({
      success: true,
      data: {
        visit_id: 'visit-1',
        documents: [
          {
            key: 'senior-course-key',
            source_document_id: 'doc-senior',
            source_table: 'senior_course_record',
            document_type: 'senior_course_record',
            title: '',
            record_time: '2026-03-01 09:20:28',
            content: '患者病情稳定，继续当前治疗。',
          },
        ],
      },
    })

    const wrapper = mount(QCRecordCompareWorkbench, {
      props: {
        visitId: 'visit-1',
        issues: [],
      },
    })
    await flushPromises()

    const documentItem = wrapper.find('.record-document-item')
    expect(documentItem.text()).toContain('上级医师查房记录')
    expect(documentItem.text()).not.toContain('记录时间')
    expect(documentItem.text()).toContain('03月01日')
    expect(documentItem.find('small').attributes('title')).toContain('2026-03-01 09:20:28')
    expect(wrapper.text()).not.toContain('senior_course_record')
  })

  it('结果页文书目录沿用查看病历的搜索筛选、树形分组和文书摘要', async () => {
    getDocumentsMock.mockResolvedValue({
      success: true,
      data: {
        visit_id: 'visit-1',
        documents: [
          {
            key: 'admission-key',
            source_table: 'admission_record',
            document_type: 'admission_record',
            title: '入院记录',
            record_time: '2026-06-01 09:00:00',
            content: '主诉腹痛3小时。',
          },
          {
            key: 'order-key',
            source_table: 'inpat_drug_order',
            document_type: 'inpat_drug_order',
            title: '长期医嘱',
            record_time: '2026-06-01 10:00:00',
            content: '静脉滴注抗菌药物。',
          },
          {
            key: 'empty-course-key',
            source_table: 'daily_course_record',
            document_type: 'daily_course_record',
            title: '日常病程记录',
            record_time: '',
            content: '',
          },
        ],
      },
    })

    const wrapper = mount(QCRecordCompareWorkbench, {
      props: {
        visitId: 'visit-1',
        issues: [],
      },
    })
    await flushPromises()

    const directory = wrapper.find('.record-document-nav')
    expect(directory.text()).toContain('文书目录')
    expect(directory.text()).toContain('3 / 3')
    expect(directory.find('.record-document-groups.is-tree').exists()).toBe(true)
    expect(directory.text()).toContain('06月01日')
    expect(directory.find('.record-document-item small').attributes('title')).toContain(
      '2026-06-01 09:00:00',
    )
    expect(directory.text()).not.toContain('8字')
    expect(directory.text()).not.toContain('源文书')

    await directory.find('[data-testid="record-document-filter-content"]').trigger('click')
    expect(directory.text()).toContain('2 / 3')
    expect(directory.text()).not.toContain('日常病程记录')

    await directory.find('[data-testid="record-document-filter-order"]').trigger('click')
    expect(directory.text()).toContain('1 / 3')
    expect(directory.text()).toContain('医嘱')
    expect(directory.text()).not.toContain('入院记录')

    await directory.find('[data-testid="record-document-filter-all"]').trigger('click')
    await directory.find('[data-testid="record-document-search"]').setValue('腹痛')
    expect(directory.text()).toContain('1 / 3')
    expect(directory.text()).toContain('入院记录')
    expect(directory.text()).not.toContain('长期医嘱')
  })

  it('结果页选择医嘱后按长期和临时分类展示医嘱列表', async () => {
    getDocumentsMock.mockResolvedValue({
      success: true,
      data: {
        visit_id: 'visit-1',
        documents: [
          {
            key: 'long-order-1',
            source_table: 'inpat_drug_order',
            document_type: 'inpat_drug_order',
            title: '长期医嘱',
            record_time: '2026-06-01 10:00:00',
            order_start_time: '2026-06-01 10:00:00',
            order_category: '用药',
            order_item: '奥美拉唑肠溶胶囊',
            order_status: '新开',
            content: '长期医嘱：奥美拉唑肠溶胶囊。',
          },
          {
            key: 'temporary-order-older',
            source_table: 'inpat_nondrug_order',
            document_type: 'inpat_nondrug_order',
            title: '临时医嘱',
            record_time: '2026-06-02 09:00:00',
            order_start_time: '2026-06-02 09:00:00',
            order_category: '检查',
            order_item: '腹部CT检查',
            order_status: '已执行',
            content: '临时医嘱：腹部CT检查。',
          },
          {
            key: 'temporary-order-newer',
            source_table: 'inpat_drug_order',
            document_type: 'inpat_drug_order',
            title: '临时医嘱',
            record_time: '2026-06-02 16:30:00',
            order_start_time: '2026-06-02 16:30:00',
            order_stop_time: '2026-06-02 18:00:00',
            order_category: '用药',
            order_item: '头孢曲松',
            order_status: '停止',
            content: '临时医嘱：头孢曲松。',
          },
        ],
      },
    })

    const wrapper = mount(QCRecordCompareWorkbench, {
      props: {
        visitId: 'visit-1',
        issues: [],
      },
    })
    await flushPromises()

    await wrapper.find('[data-testid="record-document-filter-order"]').trigger('click')
    const temporaryOrder = wrapper
      .findAll('.record-document-item')
      .find((node) => node.text().includes('临时医嘱'))
    expect(temporaryOrder).toBeTruthy()
    await temporaryOrder!.trigger('click')

    const table = wrapper.find('[data-testid="readonly-medical-order-table"]')
    expect(table.exists()).toBe(true)
    expect(table.text()).toContain('开始时间')
    expect(table.text()).toContain('医嘱类型')
    expect(table.text()).toContain('医嘱项目')
    expect(table.text()).toContain('停止时间')
    expect(table.text()).toContain('医嘱状态')
    const temporaryButton = table
      .findAll('.editable-copy-order-type-switch button')
      .find((node) => node.text() === '临时医嘱')
    await temporaryButton!.trigger('click')
    expect(table.find('.editable-copy-order-type-switch button.is-active').text()).toBe('临时医嘱')
    const temporaryRows = table.findAll('tbody tr')
    expect(temporaryRows).toHaveLength(2)
    expect(temporaryRows[0].text()).toContain('2026-06-02 16:30:00')
    expect(temporaryRows[0].text()).toContain('头孢曲松')
    expect(temporaryRows[0].text()).toContain('2026-06-02 18:00:00')
    expect(temporaryRows[0].text()).toContain('停止')

    const longButton = table
      .findAll('.editable-copy-order-type-switch button')
      .find((node) => node.text() === '长期医嘱')
    await longButton!.trigger('click')
    expect(table.text()).toContain('奥美拉唑肠溶胶囊')
    expect(table.text()).not.toContain('头孢曲松')
  })

  it('入院记录按结构化章节展示并在对应章节内高亮证据', async () => {
    getDocumentsMock.mockResolvedValue({
      success: true,
      data: {
        visit_id: 'visit-1',
        documents: [
          {
            key: 'admission-key',
            source_document_id: 'doc-admission',
            source_table: 'admission_record',
            document_type: 'admission_record',
            title: '入院记录',
            record_time: '2026-02-28 09:01:09',
            content: '腹痛3天\n患者3天前出现腹痛，伴恶心。',
            sections: [
              {
                key: 'chief_complaint',
                label: '主诉',
                text: '腹痛3天',
                source_field: 'chief_complaint',
                order_index: 0,
              },
              {
                key: 'history_of_present_illness',
                label: '现病史',
                text: '患者3天前出现腹痛，伴恶心。',
                source_field: 'history_of_present_illness',
                order_index: 1,
              },
            ],
          },
        ],
      },
    })

    const wrapper = mount(QCRecordCompareWorkbench, {
      props: {
        visitId: 'visit-1',
        issues: [
          {
            ...issues[1]!,
            key: 'issue-admission',
            target_document_type: 'admission_record',
            evidences: [
              {
                key: 'evidence-admission',
                source_document_id: 'doc-admission',
                source_document_type: 'admission_record',
                quote: '患者3天前出现腹痛，伴恶心。',
              },
            ],
          },
        ],
      },
    })
    await flushPromises()

    const sections = wrapper.findAll('.record-content-section')
    expect(sections).toHaveLength(2)
    expect(sections[0]?.find('.record-content-section-title').text()).toBe('主诉')
    expect(sections[1]?.find('.record-content-section-title').text()).toBe('现病史')
    expect(sections[1]?.find('mark').text()).toBe('患者3天前出现腹痛，伴恶心。')
    expect(wrapper.text()).not.toContain('chief_complaint')
    expect(wrapper.text()).not.toContain('history_of_present_illness')
  })

  it('只有字段级安全引用时定位并高亮对应章节，不要求携带病历正文', async () => {
    getDocumentsMock.mockResolvedValue({
      success: true,
      data: {
        visit_id: 'visit-1',
        documents: [
          {
            key: 'admission-key',
            source_ref: 'safe-admission-ref',
            source_table: 'admission_record',
            document_type: 'admission_record',
            title: '入院记录',
            record_time: '2026-02-28 09:01:09',
            content: '腹痛3天\n患者3天前出现腹痛，伴恶心。',
            sections: [
              {
                key: 'chief_complaint',
                label: '主诉',
                text: '腹痛3天',
                source_field: 'chief_complaint',
                order_index: 0,
              },
              {
                key: 'history_of_present_illness',
                label: '现病史',
                text: '患者3天前出现腹痛，伴恶心。',
                source_field: 'history_of_present_illness',
                order_index: 1,
              },
            ],
          },
        ],
      },
    })

    const wrapper = mount(QCRecordCompareWorkbench, {
      props: {
        visitId: 'visit-1',
        issues: [
          {
            ...issues[1]!,
            key: 'issue-chief-complaint',
            target_document_type: 'admission_record',
            evidences: [
              {
                key: 'evidence-chief-complaint',
                source_ref: 'safe-admission-ref',
                source_document_type: 'admission_record',
                section_field_path: 'chief_complaint',
                quote: '',
              },
            ],
          },
        ],
      },
    })
    await flushPromises()

    const sections = wrapper.findAll('.record-content-section')
    expect(sections[0]?.classes()).toContain('is-evidence-target')
    expect(sections[1]?.classes()).not.toContain('is-evidence-target')
    expect(wrapper.find('.record-location-chip').text()).toBe('已定位到主诉章节')
    await wrapper.find('.record-result-item').trigger('click')
    await flushPromises()
    expect(wrapper.find('.record-evidence-button').text()).toContain('原文摘录 · 主诉')
    expect(wrapper.find('.record-evidence-button').text()).toContain('腹痛3天')
    expect(wrapper.find('mark').exists()).toBe(false)
  })

  it('字段缺失类结果仅展示精确绑定文书的核对节选，不伪造缺失字段原文', async () => {
    getDocumentsMock.mockResolvedValue({
      success: true,
      data: {
        visit_id: 'visit-1',
        documents: [
          {
            key: 'surgery-key',
            source_ref: 'safe-surgery-ref',
            source_table: 'surgery_record',
            document_type: 'surgery_record',
            title: '手术记录',
            content: '患者在全麻下行右膝关节置换术，术中使用金属对聚乙烯关节面。',
          },
        ],
      },
    })

    const wrapper = mount(QCRecordCompareWorkbench, {
      props: {
        visitId: 'visit-1',
        issues: [
          {
            ...issues[1]!,
            key: 'issue-implant-missing',
            rule_code: 'LX0609-04-02-04',
            evidences: [
              {
                key: 'evidence-surgery-record',
                source_ref: 'safe-surgery-ref',
                source_document_type: 'surgery_record',
                quote: '',
              },
            ],
          },
        ],
      },
    })
    await flushPromises()
    await wrapper.find('.record-result-item').trigger('click')
    await flushPromises()

    const evidence = wrapper.find('.record-evidence-button')
    expect(evidence.text()).toContain('核对文书 · 手术记录')
    expect(evidence.text()).toContain('术中使用金属对聚乙烯关节面')
    expect(evidence.text()).not.toContain('条码/批号')
  })

  it('相同安全引用关联诊断与入院记录时，优先按文书类型定位带章节锚点的入院记录', async () => {
    getDocumentsMock.mockResolvedValue({
      success: true,
      data: {
        visit_id: 'visit-1',
        documents: [
          {
            key: 'diagnosis-key',
            source_ref: 'shared-admission-ref',
            source_table: 'admission_record_diagnosis',
            document_type: 'admission_record_diagnosis',
            title: '入院记录诊断',
            content: '第一诊断：急性胃肠炎',
          },
          {
            key: 'admission-key',
            source_ref: 'shared-admission-ref',
            source_table: 'admission_record',
            document_type: 'admission_record',
            title: '入院记录',
            content: '腹痛3天',
            sections: [
              {
                key: 'chief_complaint',
                label: '主诉',
                text: '腹痛3天',
                source_field: 'chief_complaint',
                order_index: 0,
              },
            ],
          },
        ],
      },
    })

    const wrapper = mount(QCRecordCompareWorkbench, {
      props: {
        visitId: 'visit-1',
        issues: [
          {
            ...issues[1]!,
            key: 'issue-shared-admission-ref',
            evidences: [
              {
                key: 'evidence-diagnosis',
                source_ref: 'shared-admission-ref',
                source_document_type: 'admission_record_diagnosis',
                quote: '',
              },
              {
                key: 'evidence-chief-complaint',
                source_ref: 'shared-admission-ref',
                source_document_type: 'admission_record',
                section_field_path: 'chief_complaint',
                quote: '',
              },
            ],
          },
        ],
      },
    })
    await flushPromises()

    expect(wrapper.find('[data-section-key="chief_complaint"]').classes()).toContain(
      'is-evidence-target',
    )
    expect(wrapper.find('.record-location-chip').text()).toBe('已定位到主诉章节')
  })

  it('普通展示字段不得获得章节定位权限', async () => {
    getDocumentsMock.mockResolvedValue({
      success: true,
      data: {
        visit_id: 'visit-1',
        documents: [
          {
            key: 'admission-key',
            source_ref: 'safe-admission-ref',
            source_table: 'admission_record',
            document_type: 'admission_record',
            title: '入院记录',
            content: '腹痛3天',
            sections: [
              {
                key: 'chief_complaint',
                label: '主诉',
                text: '腹痛3天',
                source_field: 'chief_complaint',
                order_index: 0,
              },
            ],
          },
        ],
      },
    })

    const wrapper = mount(QCRecordCompareWorkbench, {
      props: {
        visitId: 'visit-1',
        issues: [
          {
            ...issues[1]!,
            key: 'issue-untrusted-field',
            evidences: [
              {
                key: 'evidence-untrusted-field',
                source_ref: 'safe-admission-ref',
                source_document_type: 'admission_record',
                field_path: '主诉',
                quote: '',
              },
            ],
          },
        ],
      },
    })
    await flushPromises()

    expect(wrapper.find('.record-content-section').classes()).not.toContain('is-evidence-target')
    expect(wrapper.find('.record-location-chip').text()).toBe('已定位到文书，未定位到具体片段')
  })

  it('质控详情应在对应结果条目内展开且允许收起，不再渲染下方独立详情区', async () => {
    const wrapper = mount(QCRecordCompareWorkbench, {
      props: {
        visitId: 'visit-1',
        issues,
      },
    })
    await flushPromises()

    expect(wrapper.find('.record-result-column > .record-result-detail').exists()).toBe(false)
    expect(wrapper.findAll('.record-result-entry .record-result-detail')).toHaveLength(0)

    const resultItems = wrapper.findAll('.record-result-item')
    await resultItems[0]!.trigger('click')
    expect(wrapper.findAll('.record-result-entry .record-result-detail')).toHaveLength(1)
    expect(wrapper.findAll('.record-result-entry')[0]!.classes()).toContain('is-expanded')

    await resultItems[0]!.trigger('click')
    expect(wrapper.findAll('.record-result-entry .record-result-detail')).toHaveLength(0)

    await resultItems[1]!.trigger('click')
    expect(wrapper.findAll('.record-result-entry .record-result-detail')).toHaveLength(1)
    expect(wrapper.findAll('.record-result-entry')[1]!.classes()).toContain('is-expanded')
  })

  it('优先展示客户安全结果汇总、核对标准和处理建议', async () => {
    const wrapper = mount(QCRecordCompareWorkbench, {
      props: {
        visitId: 'visit-1',
        issues: [
          {
            ...issues[1]!,
            summary: '手术记录中的植入物信息不完整。',
            detail:
              '本项按两个独立子项完成核对：\n1. 已核对手术记录。\n2. 植入物字段存在缺项。\n综合判定：植入物信息不完整。',
            actual_value: '已记录植入物名称；规格、材质和数量未记录。',
            requirement: '植入物名称、种类、规格/型号、材质和数量应记录完整。',
            suggestion: '请核对并补充手术记录中的植入物信息。',
          },
        ],
      },
    })
    await flushPromises()

    expect(wrapper.find('.record-result-detail').exists()).toBe(false)
    expect(wrapper.find('.record-result-item').text()).toContain('手术记录中的植入物信息不完整。')

    await wrapper.find('.record-result-item').trigger('click')

    expect(wrapper.find('.record-result-detail').text()).toContain('完整判定说明')
    expect(wrapper.find('.record-result-detail').text()).toContain('已核对手术记录')
    expect(wrapper.find('.record-result-detail').text()).toContain('核对标准')
    expect(wrapper.find('.record-result-detail').text()).toContain(
      '请核对并补充手术记录中的植入物信息。',
    )
    expect(wrapper.find('.record-result-analysis').exists()).toBe(true)
    expect(wrapper.find('.record-result-comparison').exists()).toBe(true)
    expect(wrapper.find('.record-result-guidance').exists()).toBe(true)
    expect(wrapper.findAll('.record-result-narrative-line')).toHaveLength(4)
    expect(wrapper.findAll('.record-result-narrative-line')[3]!.classes()).toContain('is-decision')
  })

  it('元数据能定位文书但原文没有证据片段时明确降级且不伪造高亮', async () => {
    const wrapper = mount(QCRecordCompareWorkbench, {
      props: {
        visitId: 'visit-1',
        issues: [
          {
            ...issues[1]!,
            key: 'issue-document-only',
            evidences: [
              {
                key: 'evidence-document-only',
                source_document_type: 'daily_course_record',
                source_document_name: '日常病程记录',
                record_time: '2026-07-25 09:00:00',
                quote: '原文中不存在的证据片段',
              },
            ],
          },
        ],
      },
    })

    await flushPromises()

    expect(wrapper.find('.record-content-toolbar').text()).toContain('日常病程记录')
    expect(wrapper.text()).toContain('已定位到文书，未定位到具体片段')
    expect(wrapper.find('mark').exists()).toBe(false)
  })

  it('缺少文书ID和元数据时可按规范化证据片段定位', async () => {
    const wrapper = mount(QCRecordCompareWorkbench, {
      props: {
        visitId: 'visit-1',
        issues: [
          {
            ...issues[1]!,
            key: 'issue-quote-only',
            target_document_type: '',
            evidences: [
              {
                key: 'evidence-quote-only',
                quote: '患者今日病情稳定， 继续原治疗方案。',
              },
            ],
          },
        ],
      },
    })

    await flushPromises()

    expect(wrapper.find('.record-content-toolbar').text()).toContain('日常病程记录')
    expect(wrapper.find('mark').text()).toContain('患者今日病情稳定')
    expect(wrapper.text()).toContain('已定位到证据段落')
  })

  it('点击质控结果时跳过不可定位摘要并切换到可定位原文', async () => {
    const multiEvidenceIssue: QCRecordCompareIssue = {
      ...issues[0]!,
      key: 'issue-multi-evidence',
      rule_code: 'LX0609-02-01-03',
      rule_name: '查房记录频次',
      evidences: [
        {
          key: 'evidence-summary',
          source_document_name: '质控摘要',
          quote: '受控摘要无法直接对应原始病历。',
        },
        {
          key: 'evidence-daily-course',
          source_document_type: 'daily_course_record',
          source_document_name: '日常病程记录',
          quote: '证据说明：患者今日病情稳定，继续原治疗方案；符合查房记录要求。',
        },
      ],
    }
    const wrapper = mount(QCRecordCompareWorkbench, {
      props: {
        visitId: 'visit-1',
        issues: [issues[1]!, multiEvidenceIssue],
      },
    })

    await flushPromises()
    expect(wrapper.find('.record-content-toolbar').text()).toContain('首次病程记录')

    await wrapper.findAll('.record-result-item')[1]!.trigger('click')
    await flushPromises()

    expect(wrapper.find('.record-content-toolbar').text()).toContain('日常病程记录')
    expect(wrapper.find('mark').text()).toContain('患者今日病情稳定')
  })

  it('没有证据引用时按规则文书域跳转且不伪造段落高亮', async () => {
    const wrapper = mount(QCRecordCompareWorkbench, {
      props: {
        visitId: 'visit-1',
        issues: [
          {
            ...issues[0]!,
            key: 'issue-course-document',
            rule_code: 'LX0609-03-01-01',
            rule_name: '日常病程记录：记录内容是否符合要求',
            target_document_type: '',
            evidences: [],
          },
        ],
      },
    })

    await flushPromises()

    expect(wrapper.find('.record-content-toolbar').text()).toContain('日常病程记录')
    expect(wrapper.text()).toContain('已定位到文书，未定位到具体片段')
    expect(wrapper.find('mark').exists()).toBe(false)
  })
})
