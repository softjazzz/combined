/**
 * 病历池住院状态与日期的展示口径（列表与右侧预览共用）。
 * 优先使用后端核验的 hospitalizationStatus；缺失时按是否有出院日期推断。
 */
export interface HospitalizationRow {
  sourceId?: 'legacy_pg' | 'independent_cdm'
  dischargeDate?: string
  hospitalizationStatus?: 'inpatient' | 'discharged' | 'unknown'
  hospitalizationStatusVerifiedAt?: string
}

export function displayHospitalDate(value?: string) {
  const normalized = String(value || '').trim()
  // 仅替换 ISO 日期与时间的分隔符，不按浏览器时区转换，不给日期补零点。
  return normalized && normalized !== '-'
    ? normalized.replace(/^(\d{4}-\d{2}-\d{2})T(?=\d{2}:\d{2})/, '$1 ')
    : '-'
}

export function isDischargedRecord(record: Pick<HospitalizationRow, 'dischargeDate'>) {
  return displayHospitalDate(record.dischargeDate) !== '-'
}

export function resolvedHospitalizationStatus(record: HospitalizationRow) {
  if (record.hospitalizationStatus) return record.hospitalizationStatus
  return isDischargedRecord(record) ? 'discharged' : 'inpatient'
}

export function hospitalizationStatusLabel(record: HospitalizationRow) {
  const status = resolvedHospitalizationStatus(record)
  if (status === 'discharged') return '已出院'
  if (status === 'unknown') return record.sourceId === 'independent_cdm' ? '状态未知' : '待核验'
  return '在院'
}

export function dischargeDateLabel(record: HospitalizationRow) {
  if (isDischargedRecord(record)) return displayHospitalDate(record.dischargeDate)
  const status = resolvedHospitalizationStatus(record)
  if (status === 'discharged') return '时间待同步'
  if (status === 'unknown') return '状态待核验'
  return '尚未出院'
}
