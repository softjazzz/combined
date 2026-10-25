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
      let source = readFileSync(file, 'utf8')
      // 本轮用户要求主管独立入口；只允许这一段铃铛路由，医生弹出层与外壳样式不变。
      const managerEntry = [
        '            <a-tooltip v-if="useFullMessageCenter" title="消息中心" placement="right">',
        '              <router-link class="ws-icon-button" to="/workstation-v5/messages" aria-label="消息中心">',
        '                <Bell aria-hidden="true" />',
        '              </router-link>',
        '            </a-tooltip>',
        '            <a-popover v-else placement="rightBottom" trigger="click">',
      ].join('\n')
      const entryChanges = [
        [
          "import { canUseReminderPanel, WORKSTATION_REMINDER_PANEL } from '@/views/workstation/notificationNavigation'\n",
          '',
        ],
        [
          'provide(WORKSTATION_REMINDER_PANEL, computed(() => canUseReminderPanel(authStore.userRoles)))\n',
          '',
        ],
        [managerEntry, '            <a-popover placement="rightBottom" trigger="click">'],
        ["import { canUseMessageCenter } from '@/views/workstation/notificationNavigation'\n", ''],
        [
          'const useFullMessageCenter = computed(() => canUseMessageCenter(authStore.userRoles))\n',
          '',
        ],
      ]
      for (const [allowedChange, previous] of entryChanges) {
        expect(source.split(allowedChange)).toHaveLength(2)
        source = source.replace(allowedChange, previous)
      }
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
      const reminderPolicy = [
        'const reminderPanelEnabled = inject(WORKSTATION_REMINDER_PANEL, computed(() => true))',
        'const availableAssistTabs = computed(() => {',
        '  const tabs: AssistTabKey[] | undefined = !props.selectedRecord',
        "    ? ['message']",
        '    : props.chatEnabled ? undefined : ANALYSIS_TABS',
        '  return reminderPanelEnabled.value',
        '    ? tabs',
        "    : (tabs ?? ['chat', ...ANALYSIS_TABS]).filter((tab) => tab !== 'message')",
        '})',
        '',
      ].join('\n')
      const reminderChanges = [
        [
          "    v-if=\"(selectedRecord || assistTab === 'message') && (reminderPanelEnabled || assistTab !== 'message')\"",
          '    v-if="selectedRecord || assistTab === \'message\'"',
        ],
        [
          ':available-tabs="availableAssistTabs"',
          ':available-tabs="!selectedRecord ? [\'message\'] : chatEnabled ? undefined : ANALYSIS_TABS"',
        ],
        [
          ':message-count="reminderPanelEnabled ? notificationUnreadCount : 0"',
          ':message-count="notificationUnreadCount"',
        ],
        ['<template v-if="reminderPanelEnabled" #message>', '<template #message>'],
        [
          "import { computed, defineAsyncComponent, inject, onMounted, ref } from 'vue'",
          "import { computed, defineAsyncComponent, onMounted, ref } from 'vue'",
        ],
        [
          "import { WORKSTATION_REMINDER_PANEL } from '@/views/workstation/notificationNavigation'\n",
          '',
        ],
        [reminderPolicy, ''],
      ]
      for (const [allowed, previous] of reminderChanges) {
        expect(source.split(allowed)).toHaveLength(2)
        source = source.replace(allowed, previous)
      }
      // 只允许消息插槽的样式挂点，不允许改原事件、数据和其他业务页签。
      const hooks: Array<[string, string, number]> = [
        ['class="assist-message-inbox"', 'class="space-y-3 p-3"', 1],
        [
          'class="assist-message-inbox__toolbar"',
          'class="flex items-center justify-between gap-2 rounded-[16px] border border-slate-200/80 bg-white/72 px-3 py-2"',
          1,
        ],
        [
          'class="assist-message-inbox__filters"',
          'class="grid grid-cols-3 gap-2 rounded-[16px] border border-slate-200/70 bg-white/72 p-2"',
          1,
        ],
        [
          'class="assist-message-inbox__read-filter"',
          'class="rounded-[16px] border border-slate-200/70 bg-white/72 p-2"',
          1,
        ],
        [
          'class="assist-message-inbox__list"',
          'class="space-y-2 max-h-[440px] overflow-y-auto custom-scrollbar pr-1"',
          1,
        ],
        [
          'class="assist-message-inbox__item"',
          'class="rounded-[16px] border p-3 shadow-[0_4px_12px_rgba(15,23,42,0.025)]"',
          2,
        ],
        ['class="assist-message-inbox__subject"', 'class="truncate"', 2],
        ['class="assist-message-inbox__body"', 'class="mt-1 text-xs text-slate-500 leading-5"', 2],
        [
          'class="assist-message-inbox__meta assist-message-inbox__meta--overview"',
          'class="mt-1 flex items-center gap-2 text-[11px] text-slate-400"',
          1,
        ],
        ['class="assist-message-inbox__meta"', 'class="mt-1 text-[11px] text-slate-400"', 1],
        ['\n<style scoped src="../styles/assist-message-inbox.css"></style>\n', '', 1],
      ]
      for (const [hook, previous, count] of hooks) {
        expect(source.split(hook)).toHaveLength(count + 1)
        source = source.split(hook).join(previous)
      }
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
    } else if (file.endsWith('/WorkstationAssistPanel.vue')) {
      let source = readFileSync(file, 'utf8')
      const allowedChanges = [
        [
          ":class=\"['assist-panel', { 'assist-panel--wide': currentTab === 'chat', 'assist-panel--message mq-card': currentTab === 'message' }]\"",
          ":class=\"['assist-panel', { 'assist-panel--wide': currentTab === 'chat' }]\"",
        ],
        [
          '<NotificationOutlined v-if="currentTab === \'message\'" class="assist-panel__title-icon" />\n            <RobotOutlined v-else class="assist-panel__title-icon" />',
          '<RobotOutlined class="assist-panel__title-icon" />',
        ],
        ["{{ currentTab === 'message' ? '消息提醒' : panelTitle }}", '{{ panelTitle }}'],
        ['              aria-label="刷新当前面板"\n', ''],
        ['              aria-label="关闭当前面板"\n', ''],
        [
          '}\n\n.assist-panel:not(.assist-panel--message) {\n  border-radius: 22px;',
          '  border-radius: 22px;',
        ],
        ['\n<style scoped src="../styles/assist-message-panel.css"></style>\n', ''],
      ]
      for (const [allowed, previous] of allowedChanges) {
        expect(source.split(allowed)).toHaveLength(2)
        source = source.replace(allowed, previous)
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
