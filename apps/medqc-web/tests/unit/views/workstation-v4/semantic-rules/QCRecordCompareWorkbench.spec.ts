import { ApiService } from '@/services/apiService'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import QCRecordCompareWorkbench from '@/views/workstation-v4/semantic-rules/components/QCRecordCompareWorkbench.vue'
import SingleRecordQcResultPanel from '@/views/workstation-v4/customer-sample-validation/SingleRecordQcResultPanel.vue'
import type { QCRecordCompareIssue } from '@/views/workstation-v4/semantic-rules/types'

import { defineComponent, h, ref } from 'vue'
import { useQcResultFeedback } from '@/views/workstation-v4/customer-sample-validation/useQcResultFeedback'

const { getDocumentsMock, getDocumentMock, getFeedbackMock, saveFeedbackMock } = vi.hoisted(() => ({
  getDocumentsMock: vi.fn(),
  getDocumentMock: vi.fn(),
  getFeedbackMock: vi.fn(async () => ({ success: true, data: {} })),
  saveFeedbackMock: vi.fn(async () => ({ success: true })),
}))

vi.mock('@/services/manual-case-sample-service', () => ({
  getEditableMedicalRecordDocuments: getDocumentsMock,
  getEditableMedicalRecordDocument: getDocumentMock,
}))

vi.mock('@/api/qc-result-feedback-demo', () => ({
  getQcResultFeedbackDemo: getFeedbackMock,
  listQcResultFeedbackDemo: vi.fn(async () => ({ success: true, data: [] })),
  saveQcResultFeedbackDemo: saveFeedbackMock,
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
  getFeedbackMock.mockReset()
  saveFeedbackMock.mockReset()
  getFeedbackMock.mockResolvedValue({ success: true, data: {} })
  saveFeedbackMock.mockResolvedValue({ success: true })
  vi.spyOn(ApiService, 'isAuthenticated').mockReturnValue(true)
  vi.spyOn(ApiService, 'getCurrentUser').mockResolvedValue({
    success: true,
    data: { id: 'test-developer', roles: ['sync_admin'], is_demo_account: true },
  })
  await useAuthStore().initialize()
})

describe('QCRecordCompareWorkbench', () => {
  it('初步诊断去掉生成标签后仍高亮同一句原文证据', async () => {
    const key = 'admission_record_diagnosis'
    const quote = '2、合成诊断乙的原文条目'
    const text = `入院记录诊断\n诊断类型: 初步诊断\n其他诊断: 1、合成甲${quote}`
    getDocumentsMock.mockResolvedValue({
      success: true,
      data: {
        documents: [{
          key: 'synthetic-admission',
          source_document_id: 'synthetic-admission',
          document_type: 'admission_record',
          title: '入院记录',
          content: text,
          sections: [{ key, label: '入院记录诊断', text }],
        }],
      },
    })
    const wrapper = mount(QCRecordCompareWorkbench, {
      props: {
        visitId: 'synthetic-diagnosis-visit',
        issues: [{
          ...issues[1]!,
          target_document_type: 'admission_record',
          evidences: [{
            key: 'synthetic-diagnosis-evidence',
            source_document_type: 'admission_record',
            source_document_id: 'synthetic-admission',
            section_field_path: key,
            quote,
          }],
        }],
      },
    })
    await flushPromises()

    const section = wrapper.get(`[data-section-key="${key}"]`)
    expect(section.get('h3').text()).toBe('初步诊断')
    expect(section.get('p').text()).toBe(`1、合成甲\n${quote}`)
    expect(section.get('mark').text()).toBe(quote)
    wrapper.unmount()
  })

  it('PDF正文版本按父文书展开，点击后能读到独立保留的PDF全文', async () => {
    const wrapper = mount(QCRecordCompareWorkbench, {
      props: {
        visitId: 'synthetic-version-visit',
        issues: [],
        documentOnly: true,
        providedDocuments: [
          {
            key: 'original',
            document_type: 'consultation_record',
            title: '会诊记录',
            content: '原PG会诊正文',
          },
          {
            key: 'pdf-text',
            document_type: 'pdf_candidate',
            title: '请会诊执行记录（PDF待核对）',
            content: '独立保留的PDF全文',
            pdf_review_parent_key: 'original',
            pdf_review_relation: 'version_difference',
          },
        ],
      },
    })
    await flushPromises()
    expect(wrapper.get('.readonly-medical-document-directory-head span').text()).toBe('1 / 1')
    await wrapper.get('[data-testid="pdf-versions-toggle-original"]').trigger('click')
    await wrapper.get('[data-testid="pdf-version-pdf-text"]').trigger('click')
    expect(wrapper.get('.record-content-scroll').text()).toContain('独立保留的PDF全文')
    expect(wrapper.get('.record-content-scroll').text()).not.toContain('原PG会诊正文')
    expect(wrapper.get('select').element.value).toBe('pdf-text')
    expect(wrapper.get('optgroup').attributes('label')).toContain('PDF对照版本')
    wrapper.unmount()
  })

  it.each([
    ['daily_course_record', '输血前评估', '输血前评估'],
    ['daily_course_record', '输血后评价记录', '输血后评价记录'],
    ['consultation_record', '会诊记录', '请会诊执行记录'],
  ])('查看病历的目录和正文标题一致：%s/%s', async (documentType, title, expected) => {
    const wrapper = mount(QCRecordCompareWorkbench, {
      props: {
        visitId: 'synthetic-title-visit',
        issues: [],
        documentOnly: true,
        providedDocuments: [
          { key: 'synthetic-title', document_type: documentType, title, content: '合成正文' },
        ],
      },
    })
    await flushPromises()
    expect(wrapper.get('.record-document-nav').text()).toContain(expected)
    expect(wrapper.get('.record-content-toolbar strong').text()).toBe(expected)
    expect(wrapper.get('.record-content-column').text()).toContain('合成正文')
    wrapper.unmount()
  })

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
    expect(
      wrapper.get('[data-testid="record-document-group-toggle-order"]').attributes('aria-expanded'),
    ).toBe('true')
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
    expect(resultItems[0]?.text()).toContain('首次病程记录及时性')
    expect(resultItems[1]?.text()).toContain('首次病程记录完整性')
    expect(wrapper.find('.record-result-list').text()).not.toContain('LX0609-01-')
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

  it('结果页默认打开入院记录，CT 证据和医嘱各自按需读取', async () => {
    const sourceRef = 'src_ct_master'
    const admission = {
      key: 'admission_record::admission-id',
      source_document_id: 'admission-id',
      document_type: 'admission_record',
      title: '入院记录',
      execution_domain: 'admission',
      content_loaded: false,
    }
    const report = {
      key: 'exam_item_report::ct-report',
      source_document_id: 'ct-report',
      source_ref: 'src_ct_report',
      source_table: 'exam_item_report',
      document_type: 'exam_item_report',
      title: '胸部 CT 检查报告',
      execution_domain: 'course',
      content_loaded: false,
      source_document_aliases: [
        { source_document_id: 'ct-report', source_ref: sourceRef, source_document_type: 'exam_master' },
      ],
    }
    getDocumentsMock.mockResolvedValue({
      success: true,
      data: {
        visit_id: 'visit-1',
        documents: [{
          key: 'unrelated',
          source_ref: sourceRef,
          source_table: 'daily_course_record',
          document_type: 'daily_course_record',
          title: '其他文书',
          content: '合成病程',
          content_loaded: true,
        }, {
          ...admission,
          key: 'diagnosis',
          source_document_id: 'diagnosis',
          document_type: 'admission_record_diagnosis',
          title: '入院记录诊断',
        }, report, admission],
      },
    })
    getDocumentMock.mockResolvedValueOnce({
      success: true,
      data: { ...admission, content: '合成入院正文', content_loaded: true },
    }).mockResolvedValue({
      success: true,
      data: { ...report, content: '合成 CT 报告正文', content_loaded: true },
    })
    const wrapper = mount(QCRecordCompareWorkbench, {
      props: {
        visitId: 'visit-1', instituteId: 'inst-1', patientId: 'patient-1', jobId: 'saved-job',
        issues: [],
        lazyResultDocuments: true,
        singleRecordItems: [{
          rule_id: 'LX0609-06-01-02',
          rule_name: 'CT/MRI 检查前病程记录',
          status: 'non_compliant',
          evidence: [{ source_ref: sourceRef, source_type: 'exam_master' }],
        }],
      },
    })
    expect(wrapper.get('.hospital-loading[role="status"]').text()).toBe('正在读取文书目录')
    await flushPromises()
    expect(wrapper.find('.hospital-loading').exists()).toBe(false)
    expect(getDocumentsMock).toHaveBeenCalledTimes(1)
    expect(getDocumentsMock).toHaveBeenLastCalledWith(
      'visit-1',
      expect.objectContaining({ job_id: 'saved-job', view: 'summary', document_scope: 'clinical' }),
    )
    expect(getDocumentMock).toHaveBeenCalledTimes(1)
    expect(getDocumentMock).toHaveBeenLastCalledWith(
      'visit-1',
      expect.objectContaining({ source_document_id: admission.key, document_type: 'admission_record' }),
      expect.objectContaining({ job_id: 'saved-job', visit_id: 'visit-1' }),
    )
    expect(wrapper.text()).toContain('合成入院正文')
    await wrapper.get('[data-testid="single-record-result-toggle"]').trigger('click')
    await wrapper.get('[data-testid="single-record-evidence"]').trigger('click')
    await flushPromises()
    expect(getDocumentMock).toHaveBeenLastCalledWith(
      'visit-1',
      expect.objectContaining({ source_document_id: report.key, source_ref: 'src_ct_report' }),
      expect.objectContaining({ job_id: 'saved-job', visit_id: 'visit-1' }),
    )
    expect(wrapper.text()).toContain('合成 CT 报告正文')
    expect(wrapper.text()).toContain('已定位到文书，未定位到具体片段')
    getDocumentsMock.mockResolvedValueOnce({
      success: true,
      data: { documents: [{
        key: 'order-key', document_type: 'inpat_drug_order', source_document_id: 'order-id',
        title: '合成医嘱', has_content: true, content: '',
      }] },
    })
    await wrapper.get('[data-testid="record-document-filter-order"]').trigger('click')
    await flushPromises()
    expect(getDocumentsMock).toHaveBeenCalledTimes(2)
    expect(getDocumentsMock).toHaveBeenLastCalledWith(
      'visit-1',
      expect.objectContaining({ job_id: 'saved-job', view: 'summary', document_scope: 'orders' }),
    )
    expect(wrapper.text()).toContain('医嘱（1条）')
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


it('当前病历与历史任务快照参数互斥', async () => {
  getDocumentsMock.mockResolvedValue({ success: true, data: { documents: [] } })
  const wrapper = mount(QCRecordCompareWorkbench, { props: {
    visitId: 'V', instituteId: 'I', patientId: 'P', jobId: 'HISTORICAL',
    recordRef: 'SAFE-REF', sourceView: 'current', issues: [], documentOnly: true,
  } })
  await flushPromises()
  expect(getDocumentsMock).toHaveBeenLastCalledWith('V', expect.objectContaining({ source_view: 'current' }))
  expect(getDocumentsMock.mock.calls.at(-1)?.[1]).not.toHaveProperty('job_id')
  await wrapper.setProps({ sourceView: 'saved' })
  await flushPromises()
  expect(getDocumentsMock).toHaveBeenLastCalledWith('V', expect.objectContaining({ job_id: 'HISTORICAL' }))
  wrapper.unmount()
})

describe('P1-14/15/16 robustness regressions', () => {
  it('P1-14: 目录、正文和医嘱请求 reject 时清理加载态并允许重试', async () => {
    getDocumentsMock.mockRejectedValueOnce(new Error('network down'))
    const wrapper = mount(QCRecordCompareWorkbench, {
      props: {
        visitId: 'visit-reject',
        jobId: 'job-reject',
        issues: [],
        lazyResultDocuments: true,
      },
    })
    await flushPromises()
    expect(wrapper.find('.hospital-loading').exists()).toBe(false)
    expect(wrapper.text()).toContain('读取病历文书失败')

    // 重试目录成功，但正文请求 reject
    getDocumentsMock.mockResolvedValueOnce({
      success: true,
      data: {
        documents: [
          {
            key: 'doc-1',
            source_document_id: 'doc-1',
            document_type: 'first_course_record',
            execution_domain: 'course',
            title: '首次病程记录',
            has_content: true,
            content_loaded: false,
            content: '',
          },
        ],
      },
    })
    getDocumentMock.mockRejectedValueOnce(new Error('doc timeout'))
    await wrapper.get('.readonly-medical-document-state.is-error button').trigger('click')
    await flushPromises()
    expect(wrapper.find('.hospital-loading').exists()).toBe(false)
    expect(wrapper.text()).toContain('当前文书读取失败')

    // 重试正文成功（documentRequests 已清理）
    getDocumentMock.mockResolvedValueOnce({
      success: true,
      data: { key: 'doc-1', content: '重试后的正文', content_loaded: true },
    })
    await wrapper.get('.record-content-retry').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('重试后的正文')

    // 医嘱加载 reject 后进入 failed，可点击重试恢复
    getDocumentsMock.mockRejectedValueOnce(new Error('orders timeout'))
    await wrapper.get('[data-testid="record-document-filter-order"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('医嘱读取失败')

    getDocumentsMock.mockResolvedValueOnce({
      success: true,
      data: {
        documents: [
          {
            key: 'order-1',
            document_type: 'inpat_drug_order',
            source_document_id: 'order-1',
            title: '临时医嘱',
            order_item: '生理盐水',
            has_content: true,
            content: '',
          },
        ],
      },
    })
    await wrapper.get('.readonly-medical-document-state.is-error button').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('医嘱（1条）')
    wrapper.unmount()
  })

  it('P1-14: useQcResultFeedback 在网络异常、跨病历切换、按规则隔离错误和延迟 sync_admin 角色下保持一致', async () => {
    setActivePinia(createPinia())
    let resolveCurrentUser!: (value: unknown) => void
    vi.spyOn(ApiService, 'isAuthenticated').mockReturnValue(true)
    vi.spyOn(ApiService, 'getCurrentUser').mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveCurrentUser = resolve
        }) as ReturnType<typeof ApiService.getCurrentUser>,
    )
    const authStore = useAuthStore()
    const initPromise = authStore.initialize()
    const jobId = ref('job-1')
    const recordRef = ref('rec-1')
    let api!: ReturnType<typeof useQcResultFeedback>
    const Harness = defineComponent({
      setup() {
        api = useQcResultFeedback(jobId, recordRef)
        return () => h('div', api.isEnabled.value ? 'on' : 'off')
      },
    })

    // 1. 延迟水合 sync_admin 角色后自动触发加载，且 load reject 不会永久卡住 loading
    getFeedbackMock.mockRejectedValueOnce(new Error('load failed'))
    const wrapper = mount(Harness)
    await flushPromises()
    expect(api.isEnabled.value).toBe(false)
    expect(getFeedbackMock).not.toHaveBeenCalled()

    resolveCurrentUser({
      success: true,
      data: { id: 'sync-late', email: 'sync@example.com', roles: ['sync_admin'], is_demo_account: false },
    })
    await initPromise
    await flushPromises()
    expect(api.isEnabled.value).toBe(true)
    expect(getFeedbackMock).toHaveBeenCalledTimes(1)
    expect(api.loading.value).toBe(false)
    expect(api.error.value).toContain('反馈暂时无法使用')

    // 2. save reject 不会永久卡住 savingRuleId，且错误按规则隔离
    saveFeedbackMock.mockRejectedValueOnce(new Error('save failed'))
    const failedSave = await api.save('LX0609-01-01-01', { feedback_type: 'correct' })
    expect(failedSave.success).toBe(false)
    expect(api.savingRuleId.value).toBe('')
    expect(api.errorByRule.value['LX0609-01-01-01']).toContain('反馈暂时无法保存')
    expect(api.errorByRule.value['LX0609-01-01-02']).toBeUndefined()

    // 3. save 进行中切换病历时，旧病历的迟到成功响应不会污染新病历
    let resolveStaleSave!: (value: unknown) => void
    saveFeedbackMock.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveStaleSave = resolve
        }),
    )
    const pendingSave = api.save('LX0609-01-01-01', { feedback_type: 'correct' })
    expect(api.savingRuleId.value).toBe('LX0609-01-01-01')

    getFeedbackMock.mockResolvedValueOnce({ success: true, data: {} })
    recordRef.value = 'rec-2'
    await flushPromises()
    expect(api.savingRuleId.value).toBe('')

    resolveStaleSave({
      success: true,
      data: {
        rule_id: 'LX0609-01-01-01',
        original_status: 'non_compliant',
        feedback_type: 'correct',
      },
    })
    await pendingSave
    expect(api.feedbackByRule.value['LX0609-01-01-01']).toBeUndefined()
    wrapper.unmount()
  })

  it('P1-15: 章节视图未渲染出高亮片段时降级状态；report_items 无正文时渲染结构化报告；医嘱定位滚动高亮行', async () => {
    const scrollIntoViewMock = vi.fn()
    const originalScrollIntoView = Element.prototype.scrollIntoView
    Element.prototype.scrollIntoView = scrollIntoViewMock
    try {
      getDocumentsMock.mockResolvedValueOnce({
        success: true,
        data: {
          visit_id: 'visit-p15',
          documents: [
            {
              key: 'admission-cross',
              source_document_id: 'admission-cross',
              source_ref: 'src_admission_cross',
              document_type: 'admission_record',
              title: '入院记录',
              content: '腹痛3天\n伴恶心呕吐2天',
              sections: [
                { key: 'chief_complaint', label: '主诉', text: '腹痛3天', source_field: 'chief_complaint' },
                { key: 'hpi', label: '现病史', text: '伴恶心呕吐2天', source_field: 'hpi' },
              ],
            },
            {
              key: 'lab-structured',
              source_document_id: 'lab-structured',
              source_ref: 'src_lab_structured',
              document_type: 'labtest_item_report',
              title: '血常规检验报告',
              content: '',
              sections: [],
              report_items: [
                {
                  item_id: 'wbc',
                  item_name: '白细胞计数',
                  result: '12.5',
                  unit: '10^9/L',
                  reference_range: '3.5-9.5',
                  abnormal_indicator: '↑',
                },
              ],
            },
            {
              key: 'order-target',
              source_document_id: 'order-target',
              source_ref: 'src_order_target',
              source_table: 'inpat_drug_order',
              document_type: 'inpat_drug_order',
              title: '临时医嘱',
              order_item: '头孢曲松钠',
              order_start_time: '2026-07-24 10:00:00',
              content: '临时医嘱：头孢曲松钠',
            },
          ],
        },
      })
      const wrapper = mount(QCRecordCompareWorkbench, {
        props: {
          visitId: 'visit-p15',
          issues: [
            {
              ...issues[1]!,
              key: 'issue-cross-section',
              evidences: [
                {
                  key: 'ev-cross',
                  source_ref: 'src_admission_cross',
                  source_document_type: 'admission_record',
                  section_field_path: 'chief_complaint',
                  quote: '腹痛3天\n伴恶心呕吐2天',
                },
              ],
            },
            {
              ...issues[1]!,
              key: 'issue-order',
              evidences: [
                {
                  key: 'ev-order',
                  source_ref: 'src_order_target',
                  source_document_type: 'inpat_drug_order',
                  quote: '临时医嘱：头孢曲松钠',
                },
              ],
            },
          ],
        },
      })
      await flushPromises()

      // 跨章节 quote 在任一单节都无法渲染 <mark>，不能显示“已定位到证据段落”，应降级到章节定位
      expect(wrapper.find('mark').exists()).toBe(false)
      expect(wrapper.find('.record-location-chip').text()).toBe('已定位到主诉章节')
      expect(wrapper.find('.record-location-chip').classes()).not.toContain('is-matched')

      // 切换到仅含 report_items 的检验报告应渲染 ReadonlyMedicalDocumentContent 而非空白 <pre>
      await wrapper.get('.record-document-select select').setValue('lab-structured')
      await flushPromises()
      expect(wrapper.find('[data-testid="readonly-medical-document-content"]').exists()).toBe(true)
      expect(wrapper.text()).toContain('白细胞计数')
      expect(wrapper.text()).toContain('12.5')

      // 定位到医嘱证据时，滚动激活的医嘱行进入视野
      scrollIntoViewMock.mockClear()
      await wrapper.findAll('.record-result-item')[1]!.trigger('click')
      await flushPromises()
      expect(wrapper.find('.editable-copy-order-table-wrap tbody tr.is-active').exists()).toBe(true)
      expect(scrollIntoViewMock).toHaveBeenCalled()
      wrapper.unmount()
    } finally {
      Element.prototype.scrollIntoView = originalScrollIntoView
    }
  })

  it('P1-15: locateSelectedIssue 在异步读取期间被新点击打断时不会回写过期定位状态', async () => {
    let resolveSlowDoc!: (value: unknown) => void
    getDocumentsMock.mockResolvedValueOnce({
      success: true,
      data: {
        documents: [
          {
            key: 'doc-slow',
            source_document_id: 'doc-slow',
            source_ref: 'src_slow',
            document_type: 'first_course_record',
            execution_domain: 'course',
            title: '首次病程记录',
            has_content: true,
            content_loaded: false,
            content: '',
          },
          {
            key: 'doc-fast',
            source_document_id: 'doc-fast',
            source_ref: 'src_fast',
            document_type: 'daily_course_record',
            execution_domain: 'course',
            title: '日常病程记录',
            has_content: true,
            content_loaded: true,
            content: '手动切换的日常病程正文',
          },
        ],
      },
    })
    getDocumentMock.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveSlowDoc = resolve
        }),
    )

    const wrapper = mount(QCRecordCompareWorkbench, {
      props: {
        visitId: 'visit-race',
        issues: [
          {
            ...issues[1]!,
            key: 'issue-slow',
            evidences: [
              {
                key: 'ev-slow',
                source_ref: 'src_slow',
                source_document_type: 'first_course_record',
                quote: '慢文书证据片段',
              },
            ],
          },
        ],
      },
    })
    await flushPromises()

    // 在 doc-slow 仍在加载时，用户手动切换到 doc-fast
    await wrapper.get('.record-document-select select').setValue('doc-fast')
    await flushPromises()
    expect(wrapper.text()).toContain('手动切换的日常病程正文')

    // doc-slow 迟到失败返回，不能覆盖当前 doc-fast 的定位状态为 missing
    resolveSlowDoc({ success: false, message: 'slow failed' })
    await flushPromises()
    expect((wrapper.get('.record-document-select select').element as HTMLSelectElement).value).toBe('doc-fast')
    expect(wrapper.find('.record-location-chip').text()).not.toContain('未找到对应文书')
    wrapper.unmount()
  })

  it('P1-16: lazyResultDocuments 模式缺少入院记录时回退加载首篇文书', async () => {
    const firstCourse = {
      key: 'first_course_record::fc-1',
      source_document_id: 'fc-1',
      document_type: 'first_course_record',
      title: '首次病程记录',
      execution_domain: 'course',
      has_content: true,
      content_loaded: false,
      content: '',
    }
    getDocumentsMock.mockResolvedValueOnce({
      success: true,
      data: { visit_id: 'visit-no-adm', documents: [firstCourse] },
    })
    getDocumentMock.mockResolvedValueOnce({
      success: true,
      data: { ...firstCourse, content: '无入院记录时的首篇文书正文', content_loaded: true },
    })

    const wrapper = mount(QCRecordCompareWorkbench, {
      props: {
        visitId: 'visit-no-adm',
        jobId: 'job-no-adm',
        issues: [],
        lazyResultDocuments: true,
      },
    })
    await flushPromises()

    expect(getDocumentMock).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('无入院记录时的首篇文书正文')
    expect(wrapper.text()).not.toContain('请选择文书查看原文')
    wrapper.unmount()
  })
})
