<template>
  <a-drawer
    :open="open"
    title="导入测试病历"
    placement="right"
    width="min(760px, 100vw)"
    :closable="!importing"
    @close="requestClose"
  >
    <div class="import-drawer">
      <section class="import-drawer__section">
        <div class="import-drawer__section-heading">
          <div>
            <h3>V3.6 测试病历模板</h3>
            <p>病历 Sheet 一行一病例，文书 Sheet 可用多行病例编号关联多份文书。</p>
          </div>
          <a-button data-testid="test-record-import-template" :loading="downloading" @click="downloadTemplate">
            <template #icon><Download :size="15" /></template>
            下载模板
          </a-button>
        </div>
        <a-alert
          type="info"
          show-icon
          message="仅导入合成测试病历"
          description="固定使用 luxian_0609_qc_v1 规则集。不得上传真实病例身份或患者原文；每次最多 20 份病例，文件不超过 5 MiB。"
        />
      </section>

      <section class="import-drawer__section">
        <h3>选择文件</h3>
        <input
          ref="fileInput"
          class="import-drawer__file-input"
          type="file"
          accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          :disabled="importing || resultUnknown"
          data-testid="test-record-import-file"
          @change="selectFile"
        />
        <button
          class="import-drawer__file-picker"
          type="button"
          :disabled="importing || resultUnknown"
          @click="fileInput?.click()"
        >
          <FileSpreadsheet :size="20" aria-hidden="true" />
          <span>{{ selectedFile?.name || '选择填写完成的 .xlsx 模板' }}</span>
        </button>
        <p v-if="selectedFile" class="import-drawer__file-meta">
          {{ formatFileSize(selectedFile.size) }} · 只有重新选择不同文件才会清除当前结果
        </p>
        <a-checkbox
          v-model:checked="syntheticConfirmed"
          :disabled="importing || resultUnknown"
          data-testid="test-record-import-synthetic-confirmation"
        >
          我确认文件仅包含合成测试病历，不含真实患者身份或病历原文
        </a-checkbox>
      </section>

      <a-alert
        v-if="requestError"
        :type="resultUnknown ? 'warning' : 'error'"
        show-icon
        :message="resultUnknown ? '导入结果未知' : '导入未执行'"
        :description="requestError"
        data-testid="test-record-import-error"
      />

      <section v-if="validationErrors.length" class="import-drawer__section">
        <h3>模板校验问题（{{ validationErrors.length }}）</h3>
        <div class="import-drawer__table-wrap">
          <table>
            <thead>
              <tr><th>位置</th><th>字段</th><th>问题</th></tr>
            </thead>
            <tbody>
              <tr v-for="(issue, index) in validationErrors" :key="`${issue.sheet}-${issue.row}-${issue.field}-${index}`">
                <td>{{ issue.sheet }}{{ issue.row > 0 ? ` 第 ${issue.row} 行` : '' }}</td>
                <td>{{ issue.field }}</td>
                <td>{{ issue.message }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section v-if="importResult" class="import-drawer__section" data-testid="test-record-import-results">
        <div class="import-drawer__result-heading">
          <h3>逐病例结果</h3>
          <span>已创建 {{ importResult.created }} / {{ importResult.total }}</span>
        </div>
        <a-alert
          v-if="importResult.unknown > 0"
          type="warning"
          show-icon
          message="存在结果未知的病例"
          description="请先刷新测试病历列表并按名称核对，不要直接重复导入整个文件。"
        />
        <div class="import-drawer__table-wrap">
          <table>
            <thead>
              <tr><th>病例行</th><th>病例编号</th><th>状态</th><th>说明</th></tr>
            </thead>
            <tbody>
              <tr v-for="row in importResult.results" :key="`${row.case_row}-${row.case_key}`">
                <td>病历第 {{ row.case_row }} 行</td>
                <td>{{ row.case_key }}</td>
                <td>
                  <span :class="['import-drawer__status', `import-drawer__status--${row.status}`]">
                    {{ row.status === 'created' ? '已创建' : '结果未知' }}
                  </span>
                </td>
                <td>{{ row.message }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>

    <template #footer>
      <div class="import-drawer__footer">
        <a-button :disabled="importing" @click="requestClose">关闭</a-button>
        <a-button
          type="primary"
          :loading="importing"
          :disabled="!selectedFile || !syntheticConfirmed || importing || resultUnknown || importResult !== null"
          data-testid="test-record-import-submit"
          @click="submitImport"
        >
          <template #icon><Upload :size="15" /></template>
          开始导入
        </a-button>
      </div>
    </template>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { Download, FileSpreadsheet, Upload } from 'lucide-vue-next'

import {
  downloadTestRecordImportTemplate,
  importTestRecords,
  TEST_RECORD_IMPORT_MAX_BYTES,
} from '@/services/test-medical-records'
import type {
  TestRecordImportResult,
  TestRecordImportValidationIssue,
} from '@/types/test-medical-records'
import { downloadBlob } from '@/views/workstation-v4/customer-sample-validation/batchExport'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{
  close: []
  imported: []
}>()

const fileInput = ref<HTMLInputElement | null>(null)
const selectedFile = ref<File | null>(null)
const syntheticConfirmed = ref(false)
const downloading = ref(false)
const importing = ref(false)
const requestError = ref('')
const resultUnknown = ref(false)
const validationErrors = ref<TestRecordImportValidationIssue[]>([])
const importResult = ref<TestRecordImportResult | null>(null)
const lockedFileSignature = ref('')

watch(
  () => props.open,
  (open) => {
    if (!open) reset()
  },
)

function reset() {
  selectedFile.value = null
  syntheticConfirmed.value = false
  requestError.value = ''
  resultUnknown.value = false
  validationErrors.value = []
  importResult.value = null
  lockedFileSignature.value = ''
  if (fileInput.value) fileInput.value.value = ''
}

function requestClose() {
  if (importing.value) {
    message.warning('导入处理中，请等待当前请求完成')
    return
  }
  emit('close')
}

function selectFile(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0] || null
  if (file && lockedFileSignature.value && fileSignature(file) === lockedFileSignature.value) {
    message.warning('该文件已提交过，请先刷新列表核对，不要盲目重复导入')
    if (fileInput.value) fileInput.value.value = ''
    return
  }
  requestError.value = ''
  resultUnknown.value = false
  validationErrors.value = []
  importResult.value = null
  syntheticConfirmed.value = false
  if (!file) {
    selectedFile.value = null
    return
  }
  if (!file.name.toLowerCase().endsWith('.xlsx')) {
    selectedFile.value = null
    requestError.value = '仅支持 .xlsx 测试病历模板'
    return
  }
  if (file.size > TEST_RECORD_IMPORT_MAX_BYTES) {
    selectedFile.value = null
    requestError.value = '文件不能超过 5 MiB'
    return
  }
  selectedFile.value = file
}

async function downloadTemplate() {
  if (downloading.value) return
  downloading.value = true
  const result = await downloadTestRecordImportTemplate()
  downloading.value = false
  if (!result.success || !result.data) {
    message.error(result.message || '下载测试病历导入模板失败')
    return
  }
  downloadBlob(result.data, 'V3.6-测试病历导入模板.xlsx')
}

async function submitImport() {
  const file = selectedFile.value
  if (!file
    || !syntheticConfirmed.value
    || importing.value
    || resultUnknown.value
    || importResult.value !== null) return
  importing.value = true
  requestError.value = ''
  resultUnknown.value = false
  validationErrors.value = []
  importResult.value = null
  const result = await importTestRecords(file)
  importing.value = false
  validationErrors.value = result.validationErrors
  resultUnknown.value = result.resultUnknown
  if (!result.success || !result.data) {
    requestError.value = result.message
    if (result.resultUnknown) {
      lockedFileSignature.value = fileSignature(file)
      emit('imported')
    }
    return
  }
  importResult.value = result.data
  resultUnknown.value = result.data.unknown > 0
  lockedFileSignature.value = fileSignature(file)
  if (result.data.total > 0) emit('imported')
  if (result.data.unknown === 0) message.success(`已创建 ${result.data.created} 份测试病历`)
}

function formatFileSize(size: number): string {
  return size < 1024 * 1024 ? `${Math.ceil(size / 1024)} KiB` : `${(size / 1024 / 1024).toFixed(1)} MiB`
}

function fileSignature(file: File): string {
  return `${file.name}:${file.size}:${file.lastModified}`
}
</script>

<style scoped>
.import-drawer {
  display: grid;
  gap: 18px;
  color: #1d1d1f;
  font-family: 'Source Han Sans SC', 'Microsoft YaHei UI', 'PingFang SC', sans-serif;
}

.import-drawer__section {
  display: grid;
  gap: 12px;
}

.import-drawer__section h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  line-height: 22px;
}

.import-drawer__section-heading,
.import-drawer__result-heading,
.import-drawer__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.import-drawer__section-heading p,
.import-drawer__file-meta {
  margin: 4px 0 0;
  color: rgba(29, 29, 31, 0.6);
  font-size: 13px;
  line-height: 20px;
}

.import-drawer__file-input {
  display: none;
}

.import-drawer__file-picker {
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

.import-drawer__file-picker:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.import-drawer__table-wrap {
  overflow-x: auto;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 8px;
}

.import-drawer__table-wrap table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.import-drawer__table-wrap th,
.import-drawer__table-wrap td {
  padding: 10px 12px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  line-height: 20px;
  text-align: left;
  vertical-align: top;
}

.import-drawer__table-wrap th {
  background: #f8fafc;
  color: rgba(29, 29, 31, 0.6);
  font-weight: 600;
  white-space: nowrap;
}

.import-drawer__status {
  white-space: nowrap;
}

.import-drawer__status--created {
  color: #067647;
}

.import-drawer__status--unknown {
  color: #b54708;
}
</style>
