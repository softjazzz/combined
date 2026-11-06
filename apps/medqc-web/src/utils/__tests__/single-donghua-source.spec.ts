import { describe, it, expect, beforeEach } from 'vitest'
import { clinicalSourceForRequest, setPageClinicalSource } from '../clinical-source'

describe('固定东华来源，历史与材料专用入口保持中立', () => {
  beforeEach(() => window.history.replaceState({}, '', '/workstation-v5/running-records?source_id=legacy_pg'))
  it('普通请求忽略URL里的旧来源选择', () => {
    expect(clinicalSourceForRequest('/api/medical-records/workstation')).toBe('independent_cdm')
    expect(clinicalSourceForRequest('/api/v1/emr/V/documents')).toBe('independent_cdm')
    setPageClinicalSource('legacy_pg')
    expect(new URL(window.location.href).searchParams.get('source_id')).toBe('independent_cdm')
  })
  it('历史任务和带job_id的原文请求由后端保存身份决定', () => {
    expect(clinicalSourceForRequest('/api/v1/qc/sichuan/workspace/batch-jobs/old')).toBeUndefined()
    expect(clinicalSourceForRequest('/api/v1/emr/V/documents?job_id=old')).toBeUndefined()
  })
  it('客户材料页不把材料伪标为东华', () => {
    window.history.replaceState({}, '', '/workstation-v5/customer-sample-validation?source_id=legacy_pg')
    expect(clinicalSourceForRequest('/api/v1/emr/V/documents')).toBeUndefined()
    setPageClinicalSource('independent_cdm')
    expect(new URL(window.location.href).searchParams.get('source_id')).toBe('legacy_pg')
  })
  it('登录和普通业务配置不附加临床来源', () => {
    expect(clinicalSourceForRequest('/api/v1/auth/login')).toBeUndefined()
    expect(clinicalSourceForRequest('/api/v1/clinical-sources')).toBeUndefined()
  })
})
