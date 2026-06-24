export type DocumentTypeSelectGroup = {
  label: string
  options: Array<{ label: string; value: string }>
}

const LEGACY_DOCUMENT_TYPE_ALIASES: Record<string, string> = {
  病程记录: '日常病程记录',
  上级医师查房记录: '上级查房记录',
  病例讨论: '疑难病例讨论记录',
  手术相关记录: '手术记录',
  检查报告: '检查检验报告',
}

export const STANDARD_DOCUMENT_TYPE_OPTIONS: DocumentTypeSelectGroup[] = [
  {
    label: '入院域',
    options: [{ label: '入院记录', value: '入院记录' }],
  },
  {
    label: '病程域',
    options: [
      { label: '首次病程记录', value: '首次病程记录' },
      { label: '日常病程记录', value: '日常病程记录' },
      { label: '上级查房记录', value: '上级查房记录' },
      { label: '抢救记录', value: '抢救记录' },
      { label: '阶段小结', value: '阶段小结' },
      { label: '转科记录', value: '转科记录' },
      { label: '医嘱', value: '医嘱' },
      { label: '检查检验报告', value: '检查检验报告' },
      { label: '检验报告', value: '检验报告' },
    ],
  },
  {
    label: '手术域',
    options: [
      { label: '术前小结', value: '术前小结' },
      { label: '术前讨论', value: '术前讨论' },
      { label: '手术记录', value: '手术记录' },
      { label: '麻醉记录', value: '麻醉记录' },
      { label: '知情同意书', value: '知情同意书' },
      { label: '术后首次病程记录', value: '术后首次病程记录' },
      { label: '手术安全核查', value: '手术安全核查' },
      { label: '手术风险评估', value: '手术风险评估' },
    ],
  },
  {
    label: '会诊讨论域',
    options: [
      { label: '会诊记录', value: '会诊记录' },
      { label: '疑难病例讨论记录', value: '疑难病例讨论记录' },
      { label: '死亡病例讨论记录', value: '死亡病例讨论记录' },
      { label: '交接班记录', value: '交接班记录' },
    ],
  },
  {
    label: '终末域',
    options: [
      { label: '出院记录', value: '出院记录' },
      { label: '死亡记录', value: '死亡记录' },
    ],
  },
]

const STANDARD_DOCUMENT_TYPE_VALUE_SET = new Set(
  STANDARD_DOCUMENT_TYPE_OPTIONS.flatMap((group) => group.options.map((option) => option.value)),
)

export function normalizeWorkspaceDocumentType(input?: string, fallback = '日常病程记录'): string {
  const raw = String(input || '').trim()
  if (!raw) return fallback
  const normalized = LEGACY_DOCUMENT_TYPE_ALIASES[raw] || raw
  return STANDARD_DOCUMENT_TYPE_VALUE_SET.has(normalized) ? normalized : fallback
}

export function defaultDocumentTypeByScene(scene: 'running' | 'final'): string {
  return scene === 'final' ? '出院记录' : '日常病程记录'
}
