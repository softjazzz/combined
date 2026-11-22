import { describe, expect, it, vi } from 'vitest'
import { handleWorkstationLaunchFlow } from '../workstationLaunchController'
import type { PatientRecord } from '../types'

const RECORD = { id: 'C01', visitId: 'C01', patientId: 'P-C01' } as PatientRecord

function buildParams(action: string) {
  return {
    routeQuery: { source: 'dashboard', record_id: 'C01', action },
    allRecords: [RECORD],
    validLaunchActions: [
      'open_record',
      'generate_frontpage',
      'qc_coding',
      'qc_frontpage',
      'qc_settlement',
    ] as any,
    validStages: ['frontpage_qc'] as any,
    handledLaunchKey: '',
    launchHandling: false,
    setHandledLaunchKey: vi.fn(),
    setLaunchHandling: vi.fn(),
    clearLaunchQueryParams: vi.fn(),
    openRecord: vi.fn(),
    setDetailMainTab: vi.fn(),
    setAssistPanelVisible: vi.fn(),
    setAssistTab: vi.fn(),
    nextTick: () => Promise.resolve(),
    handleGenerateFrontpage: vi.fn(),
    showWarning: vi.fn(),
  }
}

describe('workstationLaunchController', () => {
  it('asks for reselection and does not run a dashboard action for a shared visit', async () => {
    const params = buildParams('generate_frontpage')
    params.allRecords = [
      { ...RECORD, instituteId: 'H-1' },
      { ...RECORD, instituteId: 'H-2', patientId: 'P-2' },
    ]

    await handleWorkstationLaunchFlow(params)

    expect(params.openRecord).not.toHaveBeenCalled()
    expect(params.handleGenerateFrontpage).not.toHaveBeenCalled()
    expect(params.showWarning).toHaveBeenCalledWith(expect.stringContaining('重新选择'))
    expect(params.clearLaunchQueryParams).toHaveBeenCalled()
  })

  it('opens only the exact case requested by a complete dashboard key', async () => {
    const params = buildParams('open_record')
    const exact = { ...RECORD, instituteId: 'H-2', patientId: 'P-2' }
    params.allRecords = [{ ...RECORD, instituteId: 'H-1' }, exact]
    params.routeQuery.record_id = '["H-2","P-2","C01"]'

    await handleWorkstationLaunchFlow(params)

    expect(params.openRecord).toHaveBeenCalledTimes(1)
    expect(params.openRecord).toHaveBeenCalledWith(exact)
  })

  it.each([
    ['qc_frontpage', 'frontpage', 'form'],
    ['qc_coding', 'frontpage', 'coding'],
    ['qc_settlement', 'settlement', 'cost'],
  ])('%s 只定位面板，不自动发起质控', async (action, mainTab, assistTab) => {
    const params = buildParams(action)
    // 旧实现会调用这些回调触发正式质控与大模型；即使调用方仍传入，也不得被调用
    const forbidden = {
      runFormQc: vi.fn(),
      runCodingQc: vi.fn(),
      runSettlementQc: vi.fn(),
    }

    await handleWorkstationLaunchFlow({ ...params, ...forbidden } as any)

    expect(params.openRecord).toHaveBeenCalledWith(RECORD)
    expect(params.setDetailMainTab).toHaveBeenCalledWith(mainTab)
    expect(params.setAssistPanelVisible).toHaveBeenCalledWith(true)
    expect(params.setAssistTab).toHaveBeenCalledWith(assistTab)
    expect(forbidden.runFormQc).not.toHaveBeenCalled()
    expect(forbidden.runCodingQc).not.toHaveBeenCalled()
    expect(forbidden.runSettlementQc).not.toHaveBeenCalled()
    expect(params.clearLaunchQueryParams).toHaveBeenCalled()
  })
})
