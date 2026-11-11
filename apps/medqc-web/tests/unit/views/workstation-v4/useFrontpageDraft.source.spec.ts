import { effectScope, nextTick, ref } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { PatientRecord } from '@/views/workstation-v4/types'
import { useFrontpageDraft } from '@/views/workstation-v4/composables/useFrontpageDraft'

const { get } = vi.hoisted(() => ({ get: vi.fn() }))
vi.mock('@/services/apiService', () => ({ default: {}, apiClient: { get } }))
vi.mock('@/api/frontpage', () => ({ frontpageApi: {} }))
vi.mock('ant-design-vue', () => ({ message: {} }))

function record(sourceId: PatientRecord['sourceId'], visitId = 'V'): PatientRecord {
  return { sourceId, id: visitId, visitId, instituteId: 'H', patientId: 'P',
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
beforeEach(() => { get.mockReset(); get.mockResolvedValue({ data: { draft: null } }) })
afterEach(() => { scopes.splice(0).forEach(scope => scope.stop()) })

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
})
