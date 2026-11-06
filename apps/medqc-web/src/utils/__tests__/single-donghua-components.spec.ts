import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { AxiosHeaders } from 'axios'
import Panel from '@/views/workstation-v4/components/system-config/ClinicalSourceSettingsPanel.vue'
import { clinicalSourcesApi } from '@/api/clinicalSources'
import { ApiService } from '@/services/apiService'
import { usePatientRecords } from '@/views/workstation-v4/composables/usePatientRecords'
import type { ClinicalSourceSettings } from '@/api/clinicalSources'

vi.mock('@/api/clinicalSources', () => ({ clinicalSourcesApi: { configuration: vi.fn(), save: vi.fn(), check: vi.fn(), options: vi.fn() } }))
vi.mock('@/services/apiService', () => ({ ApiService: { getRaw: vi.fn() } }))
const settings: ClinicalSourceSettings = {
  version: 1, default_source: 'legacy_pg', legacy_name: '原来源', legacy_enabled: true,
  cdm: { name: '东华CDM', enabled: true, host: 'localhost', port: 62997, database: 'synthetic', username: 'readonly' },
}
beforeEach(() => {
  vi.resetAllMocks()
  window.history.replaceState({}, '', '/workstation-v5/running-records?source_id=legacy_pg')
  vi.mocked(clinicalSourcesApi.configuration).mockResolvedValue(structuredClone(settings))
  vi.mocked(clinicalSourcesApi.save).mockResolvedValue(structuredClone(settings))
})
describe('真实面板及病历池单源行为', () => {
  it('没有切源控件，保存强制东华，不自动连接源库', async () => {
    const panel = mount(Panel)
    await flushPromises()
    expect(panel.text()).toContain('普通临床来源：东华CDM')
    expect(panel.find('select').exists()).toBe(false)
    expect(panel.findAll('input[type=checkbox]')).toHaveLength(1)
    expect(clinicalSourcesApi.check).not.toHaveBeenCalled()
    await panel.get('form').trigger('submit')
    await flushPromises()
    expect(clinicalSourcesApi.save).toHaveBeenCalledWith(expect.objectContaining({ default_source: 'independent_cdm', legacy_enabled: false }))
    panel.unmount()
  })
  it('过期默认配置及URL不能改变列表请求，行身份继续传给详情与任务', async () => {
    vi.mocked(clinicalSourcesApi.options).mockResolvedValue({ default_source: 'legacy_pg', sources: [{ id: 'legacy_pg', name: 'old', enabled: true }, { id: 'independent_cdm', name: '东华CDM', enabled: true }] })
    vi.mocked(ApiService.getRaw).mockResolvedValue({ data: { records: [{ id: 'R', institute_id: 'I', patient_id: 'P', visit_id: 'V' }], total: 1 }, status: 200, statusText: 'OK', headers: new AxiosHeaders(), config: { headers: new AxiosHeaders() } })
    const records = usePatientRecords()
    await records.fetchData()
    expect(ApiService.getRaw).toHaveBeenCalledWith('/api/medical-records/workstation', expect.objectContaining({ source_id: 'independent_cdm' }))
    expect(records.allRecords.value[0].sourceId).toBe('independent_cdm')
    expect(new URL(window.location.href).searchParams.get('source_id')).toBe('independent_cdm')
  })
  it('停用东华时显示失败，不请求或回退legacy', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined)
    vi.mocked(clinicalSourcesApi.options).mockResolvedValue({ default_source: 'legacy_pg', sources: [{ id: 'legacy_pg', name: 'old', enabled: true }, { id: 'independent_cdm', name: '东华CDM', enabled: false }] })
    const records = usePatientRecords()
    await records.fetchData()
    expect(records.loadError.value).toBe(true)
    expect(ApiService.getRaw).not.toHaveBeenCalled()
    expect(records.allRecords.value).toEqual([])
    vi.restoreAllMocks()
  })
})
