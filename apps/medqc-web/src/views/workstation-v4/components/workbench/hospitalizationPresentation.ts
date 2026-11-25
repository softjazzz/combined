/**
 * 病历池住院状态与日期的展示口径（列表与右侧预览共用）。
 * 存在明确出院日期时统一归为已出院；否则优先使用后端核验的 hospitalizationStatus，缺失时默认在院。
 */
export interface HospitalizationRow {
  sourceId?: 'legacy_pg' | 'independent_cdm'
  dischargeDate?: string
  hospitalizationStatus?: 'inpatient' | 'discharged' | 'unknown'
  hospitalizationStatusVerifiedAt?: string
}

const EMPTY_HOSPITAL_DATE_PLACEHOLDERS = new Set(['-', '--', '—', 'null', 'none', 'undefined'])

export function displayHospitalDate(value?: string) {
  const normalized = String(value || '').trim()
  // 仅替换 ISO 日期与时间的分隔符，不按浏览器时区转换，不给日期补零点。
  return normalized && !EMPTY_HOSPITAL_DATE_PLACEHOLDERS.has(normalized.toLowerCase())
    ? normalized.replace(/^(\d{4}-\d{2}-\d{2})T(?=\d{2}:\d{2})/, '$1 ')
    : '-'
}

export function isDischargedRecord(record: Pick<HospitalizationRow, 'dischargeDate'>) {
  return displayHospitalDate(record.dischargeDate) !== '-'
}

export function resolvedHospitalizationStatus(record: HospitalizationRow) {
  if (isDischargedRecord(record)) return 'discharged'
  if (record.hospitalizationStatus) return record.hospitalizationStatus
  return 'inpatient'
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
