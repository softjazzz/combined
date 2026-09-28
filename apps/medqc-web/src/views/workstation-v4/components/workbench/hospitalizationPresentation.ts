/**
 * 病历池住院状态与日期的展示口径（列表与右侧预览共用）。
 * 优先使用后端核验的 hospitalizationStatus；缺失时按是否有出院日期推断。
 */
export interface HospitalizationRow {
  dischargeDate?: string
  hospitalizationStatus?: 'inpatient' | 'discharged' | 'unknown'
  hospitalizationStatusVerifiedAt?: string
}

export function displayHospitalDate(value?: string) {
  const normalized = String(value || '').trim()
  return normalized && normalized !== '-' ? normalized : '-'
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
  if (status === 'unknown') return '待核验'
  return '在院'
}

export function dischargeDateLabel(record: HospitalizationRow) {
  if (isDischargedRecord(record)) return displayHospitalDate(record.dischargeDate)
  const status = resolvedHospitalizationStatus(record)
  if (status === 'discharged') return '时间待同步'
  if (status === 'unknown') return '状态待核验'
  return '尚未出院'
}
