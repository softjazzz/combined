export interface SceneAdmissionRejectedCase {
  selection_index?: unknown
  code?: unknown
  scene?: unknown
  discharge_state?: unknown
  discharge_time_status?: unknown
}

export interface SelectedCaseLabelSource {
  patientName?: string | null
  visitId?: string | null
}

function reasonText(item: SceneAdmissionRejectedCase): string {
  const code = String(item.code || '').trim()
  const timeStatus = String(item.discharge_time_status || '').trim()
  if (code === 'case_scene_scope_mismatch') {
    const scene = String(item.scene || '').trim()
    if (scene === 'running') return '当前为在院病历，与所选质控范围不符'
    if (scene === 'final') return '当前为已出院病历，与所选质控范围不符'
    return '与当前质控范围不符'
  }
  if (timeStatus === 'conflict') {
    return '出院时间存在冲突，需人工核对'
  }
  return '缺少原始出院/死亡时间，无法确认在院或终末场景'
}

function caseLabel(source: SelectedCaseLabelSource | undefined, index: number): string {
  const name = String(source?.patientName || '').trim()
  const visitId = String(source?.visitId || '').trim()
  if (name && visitId) return `${name}（${visitId}）`
  if (visitId) return `就诊号 ${visitId}`
  if (name) return name
  return `第 ${index + 1} 份病历`
}

export function formatCaseSceneAdmissionError(
  errorDetail: Record<string, unknown> | undefined,
  selectedCases: ReadonlyArray<SelectedCaseLabelSource>,
  fallbackMessage: string,
): string {
  if (!errorDetail || errorDetail.code !== 'case_scene_admission_failed') {
    return fallbackMessage
  }
  const rawCases = Array.isArray(errorDetail.cases)
    ? (errorDetail.cases as SceneAdmissionRejectedCase[])
    : []
  if (!rawCases.length) {
    const detailMessage = String(errorDetail.message || '').trim()
    return detailMessage || fallbackMessage
  }

  const maxListed = 3
  const formattedItems: string[] = []
  for (const item of rawCases.slice(0, maxListed)) {
    const index = Number(item.selection_index)
    const source =
      Number.isInteger(index) && index >= 0 && index < selectedCases.length
        ? selectedCases[index]
        : undefined
    const label = caseLabel(source, Number.isInteger(index) && index >= 0 ? index : 0)
    formattedItems.push(`${label}：${reasonText(item)}`)
  }
  const extraSuffix = rawCases.length > maxListed ? ` 等共 ${rawCases.length} 份病历` : ''
  const actionHint =
    selectedCases.length > rawCases.length
      ? '。取消勾选上述病历后，可对其余病历继续质控。'
      : '。'
  return `无法启动质控（${rawCases.length} 份病历未通过场景校验）：${formattedItems.join('；')}${extraSuffix}${actionHint}`
}
