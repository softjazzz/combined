import { nextTick, ref } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { PatientRecord } from '../types'
import { useFrontpageDraft } from '../composables/useFrontpageDraft'

const { getMock, settingsMock, successMock, errorMock } = vi.hoisted(() => ({
  getMock: vi.fn(),
  settingsMock: vi.fn(),
  successMock: vi.fn(),
  errorMock: vi.fn(),
}))

vi.mock('@/services/apiService', () => ({
  default: { refreshToken: vi.fn() },
  apiClient: { get: getMock },
}))
vi.mock('@/api/frontpage', () => ({
  frontpageApi: { getExtractionSettings: settingsMock },
}))
vi.mock('ant-design-vue', () => ({
  message: { success: successMock, error: errorMock, warning: vi.fn() },
}))

function record(patientId: string): PatientRecord {
  return {
    id: 'shared-visit',
    recordKey: `hospital-1::${patientId}::shared-visit`,
    visitId: 'shared-visit',
    instituteId: 'hospital-1',
    patientId,
    bedNo: '',
    name: patientId,
    sex: '',
    age: 0,
    insurance: '',
    department: '',
    admissionDate: '',
    dischargeDate: '',
    days: 0,
    diagnosis: '',
    diagnosisCode: '',
    doctor: '',
    status: 'pending',
  }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise
  })
  return { promise, resolve }
}

function responseWithDelayedChunk() {
  const pending = deferred<{ done: boolean; value: Uint8Array }>()
  const cancel = vi.fn().mockResolvedValue(undefined)
  const read = vi.fn().mockReturnValueOnce(pending.promise).mockResolvedValue({ done: true })
  const response = {
    ok: true,
    body: { getReader: () => ({ read, cancel }) },
  } as unknown as Response
  return {
    response,
    cancel,
    send(frontpage: object) {
      const lines = ['diagnoses', 'procedures'].map(
        (module) => `data: ${JSON.stringify({ frontpage, module })}\n`,
      )
      pending.resolve({ done: false, value: new TextEncoder().encode(lines.join('')) })
    },
  }
}

describe('useFrontpageDraft case identity', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getMock.mockResolvedValue({ data: { draft: null } })
    settingsMock.mockResolvedValue({ settings: { default_preview_tab: 'preview' } })
  })

  afterEach(() => vi.unstubAllGlobals())

  it('切换到相同 visit 的另一患者后丢弃迟到的粘贴病历流', async () => {
    const selectedId = ref<string | null>('shared-visit')
    const selectedRecord = ref<PatientRecord | undefined>(record('patient-a'))
    const changed = vi.fn()
    const draft = useFrontpageDraft(selectedId, selectedRecord, ref(''), changed)
    await nextTick()
    const stream = responseWithDelayedChunk()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(stream.response))

    const generating = draft.generateFrontpageFromText('患者 A 病历原文')
    await vi.waitFor(() => expect(draft.frontpagePostProcessing.value).toBe(true))
    selectedRecord.value = record('patient-b')
    await nextTick()
    stream.send({ basic_info: { patient_name: '患者 A' } })

    expect(await generating).toBe(false)
    expect(stream.cancel).toHaveBeenCalled()
    expect(draft.frontpageDraft.value).toBeNull()
    expect(draft.completedModules.value).toEqual([])
    expect(changed).not.toHaveBeenCalled()
    expect(successMock).not.toHaveBeenCalled()
  })

  it('同一病例正常保留模块预览与完成草稿', async () => {
    const selectedId = ref<string | null>('shared-visit')
    const selectedRecord = ref<PatientRecord | undefined>(record('patient-a'))
    const changed = vi.fn()
    const draft = useFrontpageDraft(selectedId, selectedRecord, ref(''), changed)
    await nextTick()
    const stream = responseWithDelayedChunk()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(stream.response))
    const previewReady = vi.fn()

    const generating = draft.generateFrontpageFromText('患者 A 病历原文', 'combined', {
      onPreviewReady: previewReady,
    })
    await vi.waitFor(() => expect(draft.frontpagePostProcessing.value).toBe(true))
    stream.send({ diagnoses: { discharge_main_diagnosis_text: '肺炎' }, procedures: {} })

    expect(await generating).toBe(true)
    expect(draft.frontpageDraft.value?.diagnoses?.discharge_main_diagnosis_text).toBe('肺炎')
    expect(draft.completedModules.value.some((module) => module.name === 'diagnoses')).toBe(true)
    expect(previewReady).toHaveBeenCalledOnce()
    expect(changed).toHaveBeenCalled()
    expect(successMock).toHaveBeenCalledOnce()
  })

  it('普通生成在切换病例后也不应用迟到模块', async () => {
    const selectedId = ref<string | null>('shared-visit')
    const selectedRecord = ref<PatientRecord | undefined>(record('patient-a'))
    const changed = vi.fn()
    const draft = useFrontpageDraft(selectedId, selectedRecord, ref(''), changed)
    await nextTick()
    const stream = responseWithDelayedChunk()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(stream.response))

    const generating = draft.generateFrontpage()
    await vi.waitFor(() => expect(draft.frontpagePostProcessing.value).toBe(true))
    selectedRecord.value = record('patient-b')
    await nextTick()
    stream.send({ basic_info: { patient_name: '患者 A' } })
    await generating

    expect(draft.frontpageDraft.value).toBeNull()
    expect(changed).not.toHaveBeenCalled()
    expect(errorMock).not.toHaveBeenCalled()
  })

  it('切换后不应用旧病例的已保存草稿 GET 响应', async () => {
    const oldGet = deferred<{ data: { draft: object } }>()
    getMock.mockReturnValueOnce(oldGet.promise).mockResolvedValue({ data: { draft: null } })
    const selectedId = ref<string | null>('shared-visit')
    const selectedRecord = ref<PatientRecord | undefined>(record('patient-a'))
    const changed = vi.fn()
    const draft = useFrontpageDraft(selectedId, selectedRecord, ref(''), changed)

    selectedRecord.value = record('patient-b')
    await nextTick()
    oldGet.resolve({ data: { draft: { basic_info: { patient_name: '患者 A' } } } })
    await nextTick()

    expect(draft.frontpageDraft.value).toBeNull()
    expect(changed).not.toHaveBeenCalled()
  })
})
