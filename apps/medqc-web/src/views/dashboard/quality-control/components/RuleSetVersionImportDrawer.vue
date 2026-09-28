<template>
  <a-drawer
    :open="open"
    title="导入规则集草稿"
    width="min(720px, 100vw)"
    :closable="!importing"
    @close="requestClose"
  >
    <div class="import-drawer">
      <a-alert
        type="info"
        show-icon
        message="导入只保存草稿，不会发布或运行质控"
        description="请先导出当前版本或当前草稿，在“质控点”工作表中仅修改状态列。质控点名称、来源文书和规则定义均为只读。"
      />

      <section class="import-section">
        <h3>选择 .xlsx 文件</h3>
        <input
          ref="fileInput"
          type="file"
          class="file-input"
          accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          :disabled="importing || resultUnknown"
          data-testid="rule-version-import-file"
          @change="selectFile"
        >
        <button
          type="button"
          class="file-picker"
          :disabled="importing || resultUnknown"
          @click="fileInput?.click()"
        >
          <FileSpreadsheet :size="20" aria-hidden="true" />
          <span>{{ selectedFile?.name || '选择规则集版本工作簿' }}</span>
        </button>
        <p v-if="selectedFile" class="file-meta">
          {{ formatSize(selectedFile.size) }} · 文件最大 2 MiB
        </p>
        <a-checkbox
          v-model:checked="confirmed"
          :disabled="importing || resultUnknown"
          data-testid="rule-version-import-confirm"
        >
          我确认只修改既有质控点状态，导入后仍需单独发布才会生效
        </a-checkbox>
      </section>

      <a-alert
        v-if="requestError"
        :type="resultUnknown ? 'warning' : 'error'"
        show-icon
        :message="resultUnknown ? '导入结果未知' : '导入未执行'"
        :description="requestError"
        data-testid="rule-version-import-error"
      />

      <section v-if="issues.length" class="import-section">
        <h3>文件校验问题（{{ issues.length }}）</h3>
        <div class="issue-table-wrap">
          <table>
            <thead><tr><th>位置</th><th>字段</th><th>问题</th></tr></thead>
            <tbody>
              <tr v-for="(issue, index) in issues" :key="`${issue.sheet}-${issue.row}-${issue.field}-${index}`">
                <td>{{ issue.sheet }}{{ issue.row ? ` 第 ${issue.row} 行` : '' }}</td>
                <td>{{ issue.field || '整体' }}</td>
                <td>{{ issue.message }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <a-alert
        v-if="successText"
        type="success"
        show-icon
        message="草稿已导入"
        :description="successText"
      />
    </div>

    <template #footer>
      <div class="drawer-footer">
        <a-button :disabled="importing" @click="requestClose">
          关闭
        </a-button>
        <a-button
          type="primary"
          :loading="importing"
          :disabled="!selectedFile || !confirmed || importing || resultUnknown || Boolean(successText)"
          data-testid="rule-version-import-submit"
          @click="submit"
        >
          <template #icon><Upload :size="15" /></template>
          导入草稿
        </a-button>
      </div>
    </template>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { FileSpreadsheet, Upload } from 'lucide-vue-next'

import { importRuleSetDraft, type RuleSetVersionExcelIssue } from '@/api/ruleSetVersions'

const MAX_FILE_BYTES = 2 * 1024 * 1024

const props = defineProps<{ open: boolean; ruleSetKey: string }>()
const emit = defineEmits<{
  (event: 'update:open', value: boolean): void
  (event: 'refresh'): void
}>()

const fileInput = ref<HTMLInputElement | null>(null)
const selectedFile = ref<File | null>(null)
const confirmed = ref(false)
const importing = ref(false)
const requestError = ref('')
const resultUnknown = ref(false)
const issues = ref<RuleSetVersionExcelIssue[]>([])
const successText = ref('')
const lockedSignature = ref('')

watch(() => [props.open, props.ruleSetKey] as const, ([open]) => {
  if (!open) reset()
})

function reset() {
  selectedFile.value = null
  confirmed.value = false
  requestError.value = ''
  resultUnknown.value = false
  issues.value = []
  successText.value = ''
  lockedSignature.value = ''
  if (fileInput.value) fileInput.value.value = ''
}

function requestClose() {
  if (importing.value) {
    message.warning('导入处理中，请等待当前请求完成')
    return
  }
  emit('update:open', false)
}

function signature(file: File): string {
  return `${file.name}:${file.size}:${file.lastModified}`
}

function selectFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0] || null
  if (file && lockedSignature.value === signature(file)) {
    message.warning('该文件已提交过，请先刷新草稿核对，不要盲目重复导入')
    input.value = ''
    return
  }
  requestError.value = ''
  resultUnknown.value = false
  issues.value = []
  successText.value = ''
  confirmed.value = false
  selectedFile.value = null
  if (!file) return
  if (!file.name.toLowerCase().endsWith('.xlsx')) {
    requestError.value = '仅支持 .xlsx 规则集版本工作簿'
    return
  }
  if (file.size > MAX_FILE_BYTES) {
    requestError.value = '文件不能超过 2 MiB'
    return
  }
  selectedFile.value = file
}

async function submit() {
  const file = selectedFile.value
  if (!file || !confirmed.value || importing.value || resultUnknown.value || successText.value) return
  importing.value = true
  requestError.value = ''
  issues.value = []
  const result = await importRuleSetDraft(props.ruleSetKey, file)
  importing.value = false
  if (result.success && result.data) {
    lockedSignature.value = signature(file)
    successText.value = `修订号 ${result.data.version_seq}，基于版本 ${result.data.base_version}。发布前请核对页面差异。`
    emit('refresh')
    return
  }
  issues.value = result.issues ?? []
  resultUnknown.value = result.resultUnknown
  requestError.value = resultUnknown.value
    ? '服务端可能已保存草稿。请关闭抽屉并刷新版本列表核对修订号，再决定是否重新导出；不要直接重试同一文件。'
    : (result.message || '导入校验失败，请修正后重新选择文件')
  if (resultUnknown.value) lockedSignature.value = signature(file)
  if (result.status === 409) emit('refresh')
}

function formatSize(size: number): string {
  return size < 1024 * 1024 ? `${Math.ceil(size / 1024)} KiB` : `${(size / 1024 / 1024).toFixed(1)} MiB`
}
</script>

<style scoped>
.import-drawer {
  display: grid;
  gap: 18px;
  color: #1d1d1f;
  font-family: 'Source Han Sans SC', 'Microsoft YaHei UI', 'PingFang SC', sans-serif;
}

.import-section {
  display: grid;
  gap: 12px;
}

.import-section h3 {
  margin: 0;
  font-size: 16px;
  line-height: 22px;
  font-weight: 600;
}

.file-input { display: none; }

.file-picker {
  display: flex;
  min-height: 72px;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 14px;
  border: 1px dashed rgba(0, 122, 255, 0.38);
  border-radius: 8px;
  background: rgba(0, 122, 255, 0.04);
  color: #2456c7;
  cursor: pointer;
  font: inherit;
}

.file-picker:disabled { cursor: not-allowed; opacity: 0.55; }
.file-meta { margin: 0; color: rgba(29, 29, 31, 0.6); font-size: 13px; }
.issue-table-wrap { overflow-x: auto; border: 1px solid rgba(0, 0, 0, 0.08); border-radius: 8px; }
.issue-table-wrap table { width: 100%; border-collapse: collapse; font-size: 13px; }
.issue-table-wrap th, .issue-table-wrap td { padding: 10px 12px; border-bottom: 1px solid rgba(0, 0, 0, 0.06); text-align: left; vertical-align: top; }
.issue-table-wrap th { background: #f8fafc; color: rgba(29, 29, 31, 0.6); white-space: nowrap; }
.drawer-footer { display: flex; justify-content: flex-end; gap: 8px; }
</style>
