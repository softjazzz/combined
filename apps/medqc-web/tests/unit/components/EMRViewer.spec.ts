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
})
