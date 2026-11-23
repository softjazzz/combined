import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/utils/auth-token', () => ({
  getAccessToken: () => 'test-token',
}))

import EMRViewer from '../EMRViewer.vue'

function makeRenderResponse(content: string, contentType: 'text' | 'html' = 'text') {
  return {
    ok: true,
    status: 200,
    json: async () => ({
      success: true,
      data: {
        content,
        content_type: contentType,
        metadata: { doc_name: '入院记录', doc_type: 'admission_record' },
        defect_annotations: [],
        layout_version: '',
        render_blocks: [],
      },
    }),
  } as Response
}

describe('EMRViewer P2-G1 三键上下文与快照签名 + 零 v-html 回归测试', () => {
  const originalFetch = globalThis.fetch

  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    globalThis.fetch = originalFetch
  })

  it('受控目录跨院同号切换（相同 visitId/recordId、不同 instituteId）必须刷新正文', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('institute_id=H1')) {
        return makeRenderResponse('医院H1患者正文')
      }
      return makeRenderResponse('医院H2患者正文')
    })
    globalThis.fetch = fetchMock as unknown as typeof fetch

    const doc = {
      id: 'DOC-1',
      doc_type: 'admission_record',
      doc_name: '入院记录',
      doc_key: 'admission_record::DOC-1',
      has_content: true,
    }

    const wrapper = mount(EMRViewer, {
      props: {
        instituteId: 'H1',
        patientId: 'P1',
        visitId: 'V100',
        recordId: 'V100',
        documentsManaged: true,
        documents: [doc],
      },
      global: { stubs: { 'a-spin': true, FileTextOutlined: true } },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('医院H1患者正文')
    expect(fetchMock).toHaveBeenCalledTimes(1)

    // 切换到 H2，但 visitId/recordId 和 doc_key 完全相同
    await wrapper.setProps({
      instituteId: 'H2',
      patientId: 'P1',
      visitId: 'V100',
      recordId: 'V100',
      documents: [{ ...doc }],
    })
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(String(fetchMock.mock.calls[1][0])).toContain('institute_id=H2')
    expect(wrapper.text()).toContain('医院H2患者正文')
    wrapper.unmount()
  })

  it('同三键后台补齐 props.documents 时同步目录标签但不重复请求当前文书，版本变化时重新拉取', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('DOC-2')) return makeRenderResponse('出院记录正文')
      return makeRenderResponse(`入院记录正文#${fetchMock.mock.calls.length}`)
    })
    globalThis.fetch = fetchMock as unknown as typeof fetch

    const doc1 = {
      id: 'DOC-1',
      doc_type: 'admission_record',
      doc_name: '入院记录',
      doc_key: 'admission_record::DOC-1',
      version_id: 'v1',
      has_content: true,
    }
    const doc2 = {
      id: 'DOC-2',
      doc_type: 'discharge_record',
      doc_name: '出院记录',
      doc_key: 'discharge_record::DOC-2',
      version_id: 'v1',
      has_content: true,
    }

    const wrapper = mount(EMRViewer, {
      props: {
        instituteId: 'H1',
        patientId: 'P1',
        visitId: 'V100',
        documentsManaged: true,
        documents: [doc1],
      },
      global: { stubs: { 'a-spin': true, FileTextOutlined: true } },
    })
    await flushPromises()
    expect(fetchMock).toHaveBeenCalledTimes(1)

    // 后台补齐 doc2：目录应同步显示两个按钮，但当前 doc1 快照未变不重拉
    await wrapper.setProps({
      documents: [doc1, doc2],
    })
    await flushPromises()
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const tabButtons = wrapper.findAll('button')
    expect(tabButtons.some((btn) => btn.text().includes('出院记录'))).toBe(true)

    // 当前文书 version_id 升级为 v2 -> 快照签名变化，触发刷新
    await wrapper.setProps({
      documents: [{ ...doc1, version_id: 'v2' }, doc2],
    })
    await flushPromises()
    expect(fetchMock).toHaveBeenCalledTimes(2)
    wrapper.unmount()
  })

  it('保留 Batch 1 零 v-html 语义：HTML 响应剥离脚本并以纯文本安全渲染', async () => {
    globalThis.fetch = vi.fn(async () =>
      makeRenderResponse('<p>安全诊断</p><script>window.__xss = 1</script><img src=x onerror=alert(1)>', 'html'),
    ) as unknown as typeof fetch

    const wrapper = mount(EMRViewer, {
      props: {
        instituteId: 'H1',
        patientId: 'P1',
        visitId: 'V100',
        documentsManaged: true,
        documents: [
          {
            id: 'DOC-1',
            doc_type: 'admission_record',
            doc_name: '入院记录',
            doc_key: 'admission_record::DOC-1',
            has_content: true,
          },
        ],
      },
      global: { stubs: { 'a-spin': true, FileTextOutlined: true } },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('安全诊断')
    expect(wrapper.find('script').exists()).toBe(false)
    expect(wrapper.find('img').exists()).toBe(false)
    wrapper.unmount()
  })
})
