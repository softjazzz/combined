import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
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
    // 本批用户明确要求统一医生消息入口：仅允许消息无病例打开及限制无病例页签。
    let actual: string
    if (file.endsWith('/WorkstationLayout.vue')) {
      const source = readFileSync(file, 'utf8')
      const allowed =
        '<router-link class="ws-notice__empty" to="/workstation-v5/worklist?assist=message">查看消息与待办</router-link>'
      expect(source.split(allowed)).toHaveLength(2)
      const restored = source.replace(allowed, '<p class="ws-notice__empty">暂无通知</p>')
      actual = execFileSync('git', ['hash-object', `--path=${prefix}${file}`, '--stdin'], {
        encoding: 'utf8',
        input: restored,
      }).trim()
    } else if (file.endsWith('/WorkstationV4AssistView.vue')) {
      let source = readFileSync(file, 'utf8')
      const replacements = [
        ['    v-if="selectedRecord || assistTab === \'message\'"', '    v-if="selectedRecord"'],
        [
          ':available-tabs="!selectedRecord ? [\'message\'] : chatEnabled ? undefined : ANALYSIS_TABS"',
          ':available-tabs="chatEnabled ? undefined : ANALYSIS_TABS"',
        ],
      ]
      for (const [allowed, originalLine] of replacements) {
        expect(source.split(allowed)).toHaveLength(2)
        source = source.replace(allowed, originalLine)
      }
      actual = execFileSync('git', ['hash-object', `--path=${prefix}${file}`, '--stdin'], {
        encoding: 'utf8',
        input: source,
      }).trim()
    } else {
      actual = execFileSync('git', ['hash-object', `--path=${prefix}${file}`, file], {
        encoding: 'utf8',
      }).trim()
    }
    expect(actual).toBe(original)
  })
})
