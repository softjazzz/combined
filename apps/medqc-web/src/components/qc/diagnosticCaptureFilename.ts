import type { QcResultDebugContext } from '@/views/workstation-v4/customer-sample-validation/qcResultDebugExport'

function filenamePart(value: string | undefined, fallback: string): string {
  return (
    Array.from(value ?? '', (char) => (char.charCodeAt(0) < 32 ? '-' : char))
      .join('')
      .replace(/[<>:"/\\|?*]/g, '-')
      .trim()
      .replace(/[. ]+$/g, '')
      .slice(0, 64) || fallback
  )
}

export function diagnosticCaptureFilename(
  context: QcResultDebugContext | undefined,
  captureJobId: string,
): string {
  const patient = filenamePart(context?.patientName, '未命名患者')
  const visit = filenamePart(
    context?.visitId || context?.recordId || context?.recordRef,
    '未知病历',
  )
  const task = filenamePart(captureJobId, '未知任务')
  return `质控排障包_${patient}_就诊-${visit}_任务-${task}.zip`
}
