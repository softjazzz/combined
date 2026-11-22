export function buildCaseRecordKey(
  instituteId: string | null | undefined,
  patientId: string | null | undefined,
  visitId: string | null | undefined,
): string | undefined {
  const coordinates = [instituteId?.trim(), patientId?.trim(), visitId?.trim()]
  if (coordinates.every(Boolean)) return JSON.stringify(coordinates)
}
