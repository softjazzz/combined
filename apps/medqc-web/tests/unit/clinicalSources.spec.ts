import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  getRaw: vi.fn(),
  options: vi.fn(),
  configuration: vi.fn(),
  save: vi.fn(),
  check: vi.fn(),
}))
vi.mock('@/services/apiService', () => ({ ApiService: { getRaw: mocks.getRaw } }))
vi.mock('@/api/clinicalSources', () => ({ clinicalSourcesApi: mocks }))
import ClinicalSourceSettingsPanel from '@/views/workstation-v4/components/system-config/ClinicalSourceSettingsPanel.vue'
import { usePatientRecords } from '@/views/workstation-v4/composables/usePatientRecords'
import { clinicalSourceForRequest } from '@/utils/clinical-source'

const settings = () => ({
  version: 0,
  default_source: 'legacy_pg',
  legacy_name: '原有数据源',
  legacy_enabled: true,
  cdm: {
    name: '服务器CDM',
    enabled: true,
    host: '127.0.0.1',
    port: 5432,
    database: 'synthetic_cdm',
    username: 'reader',
  },
})

beforeEach(() => {
  vi.clearAllMocks()
  window.history.replaceState({}, '', '/workstation-v5/records/running')
  mocks.options.mockResolvedValue({
    default_source: 'independent_cdm',
    sources: [
      { id: 'legacy_pg', name: '原有数据源', enabled: true },
      { id: 'independent_cdm', name: '服务器CDM', enabled: true },
    ],
  })
  mocks.getRaw.mockResolvedValue({
    data: {
      records: [{ institute_id: 'I', patient_id: 'P', visit_id: 'V', name: '合成新源' }],
      total: 1,
    },
  })
  mocks.configuration.mockResolvedValue(settings())
  mocks.save.mockImplementation(async (value) => ({ ...value, version: 1 }))
  mocks.check.mockResolvedValue({ connected: true, read_only: true })
})

describe('双数据源页面隔离', () => {
  it('默认来源只在初始化取用，切换清除旧行并携带显式来源', async () => {
    const records = usePatientRecords('inpatient')
    await records.fetchData()
    expect(records.sourceId.value).toBe('independent_cdm')
    expect(mocks.getRaw.mock.lastCall?.[1]).toMatchObject({ source_id: 'independent_cdm' })
    records.selectSource('legacy_pg')
    expect(records.allRecords.value).toEqual([])
    await flushPromises()
    expect(mocks.getRaw.mock.lastCall?.[1]).toMatchObject({
      source_id: 'legacy_pg',
      hospital_status: 'inpatient',
    })
    expect(records.allRecords.value[0]?.sourceId).toBe('legacy_pg')
    expect(mocks.options).toHaveBeenCalledTimes(1)
  })

  it('数据源失联或未启用不能显示上一来源结果或默默切回旧源', async () => {
    const records = usePatientRecords()
    await records.fetchData()
    mocks.getRaw.mockRejectedValueOnce(new Error('fixed source unavailable'))
    records.selectSource('legacy_pg')
    await flushPromises()
    expect(records.loadError.value).toBe(true)
    expect(records.allRecords.value).toEqual([])
    mocks.options.mockRejectedValueOnce(new Error('fixed settings unavailable'))
    const next = usePatientRecords()
    const calls = mocks.getRaw.mock.calls.length
    await next.fetchData()
    expect(next.loadError.value).toBe(true)
    expect(mocks.getRaw).toHaveBeenCalledTimes(calls)
  })

  it('按页签URL归属请求，客户样本强制旧源，管理API不携带来源', () => {
    window.history.replaceState({}, '', '/workstation-v5/records/final?source_id=independent_cdm')
    expect(clinicalSourceForRequest('/api/v1/emr/V/documents')).toBe('independent_cdm')
    expect(clinicalSourceForRequest('/api/medical-records/workstation')).toBe('independent_cdm')
    expect(clinicalSourceForRequest('/api/v1/clinical-sources')).toBeUndefined()
    window.history.replaceState(
      {},
      '',
      '/workstation-v5/customer-sample-validation?source_id=independent_cdm',
    )
    expect(clinicalSourceForRequest('/api/v1/emr/V/documents')).toBe('legacy_pg')
  })

  it('设置读取和保存不探测，只有点击只读检查才连接', async () => {
    const wrapper = mount(ClinicalSourceSettingsPanel)
    await flushPromises()
    expect(mocks.check).not.toHaveBeenCalled()
    expect(wrapper.find('input[type=password]').exists()).toBe(false)
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(mocks.save).toHaveBeenCalledTimes(1)
    expect(mocks.check).not.toHaveBeenCalled()
    const button = wrapper.findAll('button').find((item) => item.text() === '只读检查 CDM')
    await button?.trigger('click')
    await flushPromises()
    expect(mocks.check).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('未保存配置')
    wrapper.unmount()
  })
})
