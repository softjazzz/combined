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
    expect(text).toContain('作者：检验师')
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
})
