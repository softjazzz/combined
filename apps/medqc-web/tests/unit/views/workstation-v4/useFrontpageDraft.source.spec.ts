import { effectScope, nextTick, ref } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { PatientRecord } from '@/views/workstation-v4/types'
import { useFrontpageDraft } from '@/views/workstation-v4/composables/useFrontpageDraft'

const { get, post, messageMock } = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  messageMock: {
    success: vi.fn(),
    warning: vi.fn(),
    error: vi.fn(),
  },
}))
vi.mock('@/services/apiService', () => ({ default: { refreshToken: vi.fn() }, apiClient: { get, post } }))
vi.mock('@/api/frontpage', () => ({
  frontpageApi: {
    getExtractionSettings: vi.fn().mockResolvedValue({
      settings: { allow_force_llm_regenerate: true, default_preview_tab: 'preview' },
    }),
  },
}))
vi.mock('ant-design-vue', () => ({ message: messageMock }))

function record(
  sourceId: PatientRecord['sourceId'],
  visitId = 'V',
  patientId = 'P',
  instituteId = 'H',
): PatientRecord {
  return { sourceId, id: visitId, visitId, instituteId, patientId,
    bedNo: '', name: '合成病例', sex: '', age: 1, insurance: '', department: '',
    admissionDate: '', dischargeDate: '', days: 1, diagnosis: '', diagnosisCode: '',
    doctor: '', status: 'pending' }
}
const scopes: ReturnType<typeof effectScope>[] = []
function setup(value: PatientRecord | undefined) {
  const scope = effectScope(); scopes.push(scope)
  const id = ref<string | null>(value?.visitId || 'V')
  const selected = ref<PatientRecord | undefined>(value)
  const draft = scope.run(() => useFrontpageDraft(id, selected, ref('原始CDM正文')))!
  return { id, selected, ...draft }
}
async function settle() { await Promise.resolve(); await nextTick() }
beforeEach(() => {
  get.mockReset()
  post.mockReset()
  messageMock.success.mockReset()
  messageMock.warning.mockReset()
  messageMock.error.mockReset()
  get.mockResolvedValue({ data: { draft: null } })
  post.mockResolvedValue({ data: { success: true } })
})
afterEach(() => {
  scopes.splice(0).forEach(scope => scope.stop())
  vi.unstubAllGlobals()
})

describe('病历查看的草稿来源隔离', () => {
  it('东华病历不请求不支持的AI草稿接口', async () => {
    const state = setup(record('independent_cdm'))
    await settle()
    expect(get).not.toHaveBeenCalled()
    expect(state.frontpageDraft.value).toBeNull()
  })
  it('病例身份尚未就绪时不按visit号猜来源', async () => {
    const state = setup(undefined)
    await settle()
    expect(get).not.toHaveBeenCalled()
    state.selected.value = record('independent_cdm')
    await settle()
    expect(get).not.toHaveBeenCalled()
  })
  it('旧来源没有草稿仍正常返回空状态', async () => {
    const state = setup(record('legacy_pg'))
    await settle()
    expect(get).toHaveBeenCalledWith('/api/medical-records/ai-frontpage-draft/V')
    expect(state.frontpageDraft.value).toBeNull()
  })
  it('选中号与尚未更新的旧病例不一致时不请求新号草稿', async () => {
    const state = setup(record('legacy_pg'))
    await settle()
    get.mockClear()
    state.id.value = 'NEXT'
    await settle()
    expect(get).not.toHaveBeenCalled()
  })
  it('同号切换东华后清空已有旧草稿', async () => {
    get.mockResolvedValue({ data: { draft: { basic_info: { name: '旧草稿' } } } })
    const state = setup(record('legacy_pg'))
    await settle()
    expect(state.frontpageDraft.value).not.toBeNull()
    state.selected.value = record('independent_cdm')
    await settle()
    expect(state.frontpageDraft.value).toBeNull()
    expect(get).toHaveBeenCalledTimes(1)
  })
  it('旧来源延迟响应不能覆盖东华当前病例', async () => {
    let resolve!: (value: unknown) => void
    get.mockReturnValue(new Promise(done => { resolve = done }))
    const state = setup(record('legacy_pg'))
    state.selected.value = record('independent_cdm')
    await nextTick()
    resolve({ data: { draft: { basic_info: { name: '旧响应' } } } })
    await settle()
    expect(state.frontpageDraft.value).toBeNull()
    expect(get).toHaveBeenCalledTimes(1)
  })

  it('患者 A 流式生成中途切至患者 B，晚到流式分片被丢弃且不会串写保存到患者 B', async () => {
    const encoder = new TextEncoder()
    let releaseChunk!: () => void
    let capturedSignal: AbortSignal | undefined
    const cancelSpy = vi.fn().mockResolvedValue(undefined)
    let readCount = 0

    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((_url: string, init?: RequestInit) => {
        capturedSignal = init?.signal ?? undefined
        return Promise.resolve({
          ok: true,
          status: 200,
          body: {
            getReader: () => ({
              cancel: cancelSpy,
              read: () => {
                readCount += 1
                if (readCount === 1) {
                  return new Promise((resolve) => {
                    releaseChunk = () =>
                      resolve({
                        done: false,
                        value: encoder.encode(
                          `data: ${JSON.stringify({ module: 'basic_info', frontpage: { basic_info: { patient_name: '患者A' } } })}\n\n`,
                        ),
                      })
                  })
                }
                return Promise.resolve({ done: true, value: undefined })
              },
            }),
          },
        })
      }),
    )

    const patientA = record('legacy_pg', 'V-A', 'P-A', 'H-1')
    const patientB = record('legacy_pg', 'V-B', 'P-B', 'H-1')
    const state = setup(patientA)
    await settle()

    const genPromise = state.generateFrontpage()
    await settle()
    await Promise.resolve()

    // 切到患者 B：应立即中止患者 A 的流并清空草稿
    state.id.value = 'V-B'
    state.selected.value = patientB
    await settle()
    expect(capturedSignal?.aborted).toBe(true)

    // 即使患者 A 的迟到分片随后返回，也不能写入患者 B 的 frontpageDraft
    releaseChunk?.()
    await genPromise
    await settle()
    expect(state.frontpageDraft.value).toBeNull()
    expect(cancelSpy).toHaveBeenCalled()

    // 若人工误触保存，绝不把空或错配草稿写入患者 B
    await state.handleSaveFrontpage()
    expect(post).not.toHaveBeenCalled()
  })

  it('生成、返回与保存三键完全一致时正常保存，三键不一致时拒绝保存', async () => {
    const encoder = new TextEncoder()
    let readCount = 0
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        body: {
          getReader: () => ({
            cancel: vi.fn().mockResolvedValue(undefined),
            read: () => {
              readCount += 1
              if (readCount === 1) {
                return Promise.resolve({
                  done: false,
                  value: encoder.encode(
                    `data: ${JSON.stringify({ module: 'basic_info', frontpage: { basic_info: { patient_name: '患者A' } } })}\n\n`,
                  ),
                })
              }
              return Promise.resolve({ done: true, value: undefined })
            },
          }),
        },
      }),
    )

    const patientA = record('legacy_pg', 'V-A', 'P-A', 'H-1')
    const state = setup(patientA)
    await settle()

    await state.generateFrontpage()
    await settle()
    expect(state.frontpageDraft.value?.basic_info?.patient_name).toBe('患者A')

    // 1) 三键一致时保存成功并携带完整三键
    await state.handleSaveFrontpage()
    expect(post).toHaveBeenCalledTimes(1)
    expect(post).toHaveBeenCalledWith(
      '/api/medical-records/ai-frontpage-draft',
      expect.objectContaining({
        institute_id: 'H-1',
        patient_id: 'P-A',
        visit_id: 'V-A',
      }),
    )

    // 2) 若无合法归属三键（如手动注入游离草稿），保存必须拒绝
    post.mockClear()
    state.setDraftEmpty()
    state.frontpageDraft.value = { basic_info: { patient_name: '无主草稿' } }
    await state.handleSaveFrontpage()
    expect(post).not.toHaveBeenCalled()
    expect(messageMock.error).toHaveBeenCalled()
  })
})
