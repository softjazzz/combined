import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import EMRViewer from '@/components/qc/EMRViewer.vue'

function jsonResponse(data: unknown) {
  return {
    status: 200,
    json: async () => ({ success: true, data }),
  }
}

describe('EMRViewer', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('全文搬运来源版本与HELD限制，空正文不显示技术失败', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ content: '', metadata: { material_source_label: 'clinical', version_id: 'v-held', material_selected: false, material_rule_usable: false, material_notice: '状态待核（HELD）' }, empty_reason: 'document_empty', render_blocks: [] })))
    const wrapper = mount(EMRViewer, {
      props: { visitId: 'V', patientId: 'P', instituteId: 'I', documentsManaged: true, documents: [{ id: 'D', doc_type: 'surgery_record', doc_name: '手术记录', doc_key: 'surgery_record::R::v-held', version_id: 'v-held' }] },
      global: { stubs: { 'a-spin': true, FileTextOutlined: true } },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('clinical · 版本：v-held · 仅展示，未选用 · 规则暂不可用 · 状态待核（HELD）')
    expect(wrapper.text()).toContain('本文书正文为空')
    expect(wrapper.text()).not.toContain('读取失败')
  })

  it('技术读取失败清除上一版本正文并区别于空正文', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(jsonResponse({ content: '上一版本正文', metadata: {}, render_blocks: [] })).mockResolvedValueOnce({ status: 503, json: async () => ({ success: false, message: 'clinical_source_read_unavailable' }) })
    vi.stubGlobal('fetch', fetchMock)
    const documents = [{ id: 'A', doc_type: 'surgery_record', doc_name: '手术记录', doc_key: 'surgery_record::R::a', version_id: 'a' }, { id: 'B', doc_type: 'surgery_record', doc_name: '手术记录', doc_key: 'surgery_record::R::b', version_id: 'b' }]
    const wrapper = mount(EMRViewer, { props: { visitId: 'V', patientId: 'P', instituteId: 'I', documentsManaged: true, documents, activeDocKey: documents[0].doc_key }, global: { stubs: { 'a-spin': true, FileTextOutlined: true } } })
    await flushPromises()
    await wrapper.setProps({ activeDocKey: documents[1].doc_key })
    await flushPromises()
    expect(wrapper.text()).toContain('文书内容读取失败，请稍后重试')
    expect(wrapper.text()).not.toContain('上一版本正文')
    expect(wrapper.text()).not.toContain('本文书正文为空')
  })

  it('同源类型同号文书使用完整版本键请求全文', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ content: '合成版本正文', content_type: 'text', metadata: {}, defect_annotations: [], render_blocks: [] }))
    vi.stubGlobal('fetch', fetchMock)
    const documents = [
      { id: 'SHARED', doc_type: 'daily_course_record', doc_name: '补充版本', doc_key: 'daily_course_record::clinical-record::v1', version_id: 'v1', has_content: true },
      { id: 'SHARED', doc_type: 'daily_course_record', doc_name: '基础版本', doc_key: 'daily_course_record::cache-record::v2', version_id: 'v2', has_content: true },
    ]
    const wrapper = mount(EMRViewer, {
      props: { visitId: 'V', patientId: 'P', instituteId: 'I', documents, documentsManaged: true, activeDocKey: documents[0].doc_key },
      global: { stubs: { 'a-spin': true, FileTextOutlined: true } },
    })
    await flushPromises()
    await wrapper.setProps({ activeDocKey: documents[1].doc_key })
    await flushPromises()
    expect(new URL(String(fetchMock.mock.calls[0]?.[0]), 'http://synthetic.invalid').searchParams.get('doc_id')).toBe(documents[0].doc_key)
    expect(new URL(String(fetchMock.mock.calls[1]?.[0]), 'http://synthetic.invalid').searchParams.get('doc_id')).toBe(documents[1].doc_key)
  })

  it('在文书详情顶部展示受控元信息和投影截断提示', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          documents: [
            {
              id: 'LAB-001',
              doc_type: 'labtest_item_report',
              doc_name: '血常规检验报告',
              doc_key: 'labtest_item_report::LAB-001',
              has_content: true,
            },
          ],
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          layout_version: 'bundle_struct_v1',
          content: '白细胞计数：4.5',
          content_type: 'text',
          metadata: {
            doc_type: 'labtest_item_report',
            doc_name: '血常规检验报告',
            document_id: 'LAB-001',
            record_time: '2026-08-01 09:00:00',
            authors: [{ role: 'reporter', name: '检验师' }],
            signatures: [{ role: 'verifier', name: '审核医师', signed_at: '2026-08-01 09:05:00' }],
            projection_incomplete: true,
            projection_notice: '已展示3条，仍有更多。',
          },
          defect_annotations: [],
          render_blocks: [
            {
              block_id: 'LAB-001:paragraph',
              block_type: 'paragraph',
              title: '正文',
              text: '白细胞计数：4.5',
            },
          ],
        }),
      )
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(EMRViewer, {
      props: {
        recordId: 'V1',
        visitId: 'V1',
        patientId: 'P1',
        instituteId: 'H1',
      },
      global: {
        stubs: {
          'a-spin': true,
          FileTextOutlined: true,
        },
      },
    })
    await flushPromises()
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('文书ID：LAB-001')
    expect(text).toContain('记录时间：2026-08-01 09:00:00')
    expect(text).toContain('录入/修改人：检验师')
    expect(text).toContain('签名：审核医师')
    expect(text).toContain('已展示3条，仍有更多。')
    expect(text).not.toContain('资料缺失')
  })

  it('复用父层轻量目录并按文书领域直接渲染，不重复请求目录', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        layout_version: 'bundle_struct_v1',
        content: '首份病程正文',
        content_type: 'text',
        metadata: { doc_type: 'daily_course_record', doc_name: '日常病程记录' },
        defect_annotations: [],
        render_blocks: [],
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    mount(EMRViewer, {
      props: {
        recordId: 'V1',
        visitId: 'V1',
        patientId: 'P1',
        instituteId: 'H1',
        documents: [
          {
            id: 'DOC-1',
            doc_type: 'daily_course_record',
            doc_name: '日常病程记录',
            doc_key: 'daily_course_record::DOC-1',
            execution_domain: 'course',
            has_content: true,
          },
        ],
        documentsManaged: true,
        documentsLoading: false,
      },
      global: {
        stubs: {
          'a-spin': true,
          FileTextOutlined: true,
        },
      },
    })
    await flushPromises()
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const url = String(fetchMock.mock.calls[0]?.[0] || '')
    expect(url).toContain('/render?')
    expect(url).toContain('execution_domain=course')
    expect(url).not.toContain('/documents')
  })

  it('父层目录加载期间保持等待，目录到达后才请求首篇文书', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        content: '到达后的首篇正文',
        content_type: 'text',
        metadata: {},
        defect_annotations: [],
        render_blocks: [],
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(EMRViewer, {
      props: {
        recordId: 'V1',
        visitId: 'V1',
        patientId: 'P1',
        instituteId: 'H1',
        documents: [],
        documentsManaged: true,
        documentsLoading: true,
      },
      global: { stubs: { 'a-spin': true, FileTextOutlined: true } },
    })
    await flushPromises()
    expect(fetchMock).not.toHaveBeenCalled()

    await wrapper.setProps({
      documentsLoading: false,
      documents: [
        {
          id: 'DOC-2',
          doc_type: 'daily_course_record',
          doc_name: '日常病程记录',
          execution_domain: 'course',
          has_content: true,
        },
      ],
    })
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(String(fetchMock.mock.calls[0]?.[0] || '')).toContain('/render?')
  })

  it('同一原始编号的不同文书按唯一键切换并重新加载正文', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          layout_version: 'bundle_struct_v1',
          content: '第一份查房正文',
          content_type: 'text',
          metadata: { doc_type: 'daily_course_record', doc_name: '主治医师查房' },
          defect_annotations: [],
          render_blocks: [],
          empty_reason: '',
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          layout_version: 'bundle_struct_v1',
          content: '第二份查房正文',
          content_type: 'text',
          metadata: { doc_type: 'senior_course_record', doc_name: '上级医师查房' },
          defect_annotations: [],
          render_blocks: [],
          empty_reason: '',
        }),
      )
    vi.stubGlobal('fetch', fetchMock)

    const documents = [
      {
        id: 'SHARED-DOC-ID',
        doc_type: 'daily_course_record',
        doc_name: '主治医师查房',
        doc_key: 'daily_course_record::SHARED-DOC-ID',
        execution_domain: 'course',
        has_content: true,
      },
      {
        id: 'SHARED-DOC-ID',
        doc_type: 'senior_course_record',
        doc_name: '上级医师查房',
        doc_key: 'senior_course_record::SHARED-DOC-ID',
        execution_domain: 'course',
        has_content: true,
      },
    ]
    const wrapper = mount(EMRViewer, {
      props: {
        visitId: 'V-CUSTOMER',
        patientId: 'P-CUSTOMER',
        instituteId: 'H-CUSTOMER',
        documents,
        documentsManaged: true,
        activeDocKey: documents[0].doc_key,
      },
      global: { stubs: { 'a-spin': true, FileTextOutlined: true } },
    })
    await flushPromises()

    await wrapper.setProps({ activeDocKey: documents[1].doc_key })
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(String(fetchMock.mock.calls[1]?.[0] || '')).toContain('doc_type=senior_course_record')
    expect(wrapper.text()).toContain('第二份查房正文')
  })

  it('后端返回未找到文书的空结构块时显示明确空态', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        layout_version: 'bundle_struct_v1',
        content: '',
        content_type: 'text',
        metadata: {},
        defect_annotations: [],
        render_blocks: [
          {
            block_id: 'empty',
            block_type: 'paragraph',
            title: '文书内容',
            text: '',
            empty: true,
            empty_text: '当前病历暂无可展示内容',
          },
        ],
        empty_reason: 'document_not_found',
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(EMRViewer, {
      props: {
        visitId: 'V-CUSTOMER',
        patientId: 'P-CUSTOMER',
        instituteId: 'H-CUSTOMER',
        documents: [
          {
            id: 'DOC-MISSING',
            doc_type: 'daily_course_record',
            doc_name: '查房记录',
            doc_key: 'daily_course_record::DOC-MISSING',
            execution_domain: 'course',
            has_content: true,
          },
        ],
        documentsManaged: true,
      },
      global: { stubs: { 'a-spin': true, FileTextOutlined: true } },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('暂无文书内容')
    expect(wrapper.emitted('loaded')).toBeUndefined()
    expect(wrapper.emitted('error')?.at(-1)).toEqual(['document_not_found'])
  })

  it('纯结构化文书无拼接正文时仍视为加载成功', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        layout_version: 'bundle_struct_v1',
        content: '',
        content_type: 'text',
        metadata: { doc_type: 'surgery_record', doc_name: '手术记录' },
        defect_annotations: [],
        render_blocks: [
          {
            block_id: 'surgery:kv',
            block_type: 'kv_section',
            title: '手术信息',
            fields: [{ key: 'operation_name', label: '手术名称', value: '颅内血肿清除术' }],
            empty: false,
          },
        ],
        empty_reason: '',
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(EMRViewer, {
      props: {
        visitId: 'V-CUSTOMER',
        patientId: 'P-CUSTOMER',
        instituteId: 'H-CUSTOMER',
        documents: [
          {
            id: 'SURGERY-1',
            doc_type: 'surgery_record',
            doc_name: '手术记录',
            doc_key: 'surgery_record::SURGERY-1',
            execution_domain: 'surgery',
            has_content: true,
          },
        ],
        documentsManaged: true,
      },
      global: { stubs: { 'a-spin': true, FileTextOutlined: true } },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('颅内血肿清除术')
    expect(wrapper.emitted('loaded')).toHaveLength(1)
    expect(wrapper.emitted('error')).toBeUndefined()
  })
})


it.each([
  ['source_submit_time', '提交时间'],
  ['fallback_display_time', '显示时间（回退）'],
])('显示源状态与 %s 来源并完整保留手术经过', async (source, label) => {
  const body = '步骤：切开\n术中：合成内容' + '缝合。'.repeat(200)
  vi.stubGlobal('fetch', vi.fn()
    .mockResolvedValueOnce(jsonResponse({ documents: [{ id: 'S1', doc_type: 'surgery_record', has_content: true }] }))
    .mockResolvedValueOnce(jsonResponse({ layout_version: 'bundle_struct_v1', content: body,
      metadata: { doc_type: 'surgery_record', document_id: 'S1', document_status: 'Save',
        record_time: '2026-11-01 10:00', record_time_source: source },
      render_blocks: [{ block_id: 's1', block_type: 'kv_section', fields: [{ key: 'surgery_process', label: '手术经过', value: body }] }] })))
  const wrapper = mount(EMRViewer, { props: { recordId: 'V1', visitId: 'V1', patientId: 'P1', instituteId: 'H1' },
    global: { stubs: { 'a-spin': true } } })
  await flushPromises()
  await flushPromises()
  expect(wrapper.text()).toContain('源文书状态：Save')
  expect(wrapper.text()).toContain(`${label}：2026-11-01 10:00`)
  expect(wrapper.text()).not.toContain('记录时间：2026-11-01 10:00')
  expect(wrapper.find('.emr-struct__field-value').element.textContent?.trim()).toBe(body)
  wrapper.unmount()
  vi.unstubAllGlobals()
})


it('展示补充冲突和来源覆盖提示，不把待核材料当成正式材料', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({content:'合成正文', metadata:{material_source_label:'临床补充',material_notice:'内容冲突；未纳入正式材料',material_scope_notice:'来源覆盖待核'},render_blocks:[]})))
  const wrapper = mount(EMRViewer, {props:{visitId:'V',patientId:'P',instituteId:'I',documentsManaged:true,documents:[{id:'D',doc_type:'daily_course_record',doc_name:'日常病程',has_content:true}]},global:{stubs:{'a-spin':true}}})
  await flushPromises()
  expect(wrapper.text()).toContain('临床补充')
  expect(wrapper.text()).toContain('内容冲突；未纳入正式材料')
  expect(wrapper.text()).toContain('来源覆盖待核')
  wrapper.unmount()
  vi.unstubAllGlobals()
})

it('空目录仍显示来源未批准和待更新提示', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({documents:[],daily_material_status:{notice:'补充来源尚未批准关联；材料选择待更新'}})))
  const wrapper = mount(EMRViewer, {props:{visitId:'V',patientId:'P',instituteId:'I'},global:{stubs:{'a-spin':true}}})
  await flushPromises()
  expect(wrapper.text()).toContain('补充来源尚未批准关联；材料选择待更新')
  wrapper.unmount()
  vi.unstubAllGlobals()
})
