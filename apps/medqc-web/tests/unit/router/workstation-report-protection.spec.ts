import { execFileSync } from 'node:child_process'
import { describe, expect, it } from 'vitest'

// 固定在本地七个产品提交之后；允许新增报表，不允许把gap外壳覆盖回来。
const baseline = '754fa2f7af23e9d60209f3cbbcf96e3d59d9813f'
const prefix = 'apps/medqc-web/'
const protectedFiles = [
  'src/components/layout/WorkstationLayout.vue',
  'src/components/icons/MqIcon.vue',
  'src/components/icons/MqIconTile.vue',
  'src/components/icons/mqIcons.ts',
  'src/main.ts',
  'src/styles/tokens-v2.css',
  'src/styles/mq-components.css',
  'src/components/layout/workstationTheme.ts',
  'src/components/layout/WorkstationConfirmDialog.vue',
  'src/components/layout/workstationConfirmation.ts',
  'src/views/workstation-v4/components/GlobalAssistantHost.vue',
  'src/views/workstation-v4/components/WorkstationAssistPanel.vue',
  'src/views/workstation-v4/components/WorkstationV4AssistView.vue',
  'src/views/workstation-v4/components/RecordDetailWorkspace.vue',
  'src/views/workstation-v4/customer-sample-validation/CustomerSampleTaskHistoryView.vue',
  'src/views/workstation-v4/customer-sample-validation/taskHistoryPresentation.ts',
  'src/views/workstation-v4/semantic-rules/components/BatchResultOverview.vue',
  'src/views/workstation-v4/semantic-rules/components/SemanticRulesBatchResultDrawer.vue',
]

describe('V7.1与未推送产品成果保护集', () => {
  it.each(protectedFiles)('%s 与适配起点内容完全一致', (file) => {
    const original = execFileSync('git', ['rev-parse', `${baseline}:${prefix}${file}`], {
      encoding: 'utf8',
    }).trim()
    const actual = execFileSync('git', ['hash-object', `--path=${prefix}${file}`, file], {
      encoding: 'utf8',
    }).trim()
    expect(actual).toBe(original)
  })
})
