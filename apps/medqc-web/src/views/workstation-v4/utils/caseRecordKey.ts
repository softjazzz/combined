// 既有列表键和请求比对需要保留接口返回的原始坐标。
export function serializeCaseRecordKey(
  instituteId: unknown,
  patientId: unknown,
  visitId: unknown,
): string {
  return JSON.stringify([instituteId, patientId, visitId])
}

export function buildCaseRecordKey(
  instituteId: string | null | undefined,
  patientId: string | null | undefined,
  visitId: string | null | undefined,
): string | undefined {
  const institute = instituteId?.trim()
  const patient = patientId?.trim()
  const visit = visitId?.trim()
  if (institute && patient && visit) return serializeCaseRecordKey(institute, patient, visit)
}
