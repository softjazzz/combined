<template>
  <a-drawer :open="open" title="导入文书定义" width="min(760px, 100vw)" :closable="!importing" @close="close">
    <div class="definition-import">
      <section>
        <div class="definition-import__heading">
          <div>
            <h3>V3.6 文书定义模板</h3>
            <p>固定 Sheet“文书定义”，字段为文书编码、文书名称、分类、模板内容；模板内容仅作为文本保存。</p>
          </div>
          <a-button data-testid="definition-template-download" :loading="downloading" @click="downloadTemplate">
            <template #icon><Download :size="15" /></template>下载模板
          </a-button>
        </div>
        <a-alert type="info" show-icon message="一次最多 500 行，文件不超过 2 MiB；已有编码或批内重复编码会拒绝整批覆盖。" />
      </section>

      <section>
        <h3>选择文件</h3>
        <input ref="fileInput" data-testid="definition-import-file" type="file" accept=".xlsx" :disabled="importing || resultUnknown" @change="selectFile" />
        <p>{{ file?.name || '请选择填写完成的 .xlsx 模板' }}</p>
      </section>

      <a-alert v-if="error" :type="resultUnknown ? 'warning' : 'error'" show-icon :message="resultUnknown ? '导入结果未知' : '导入未执行'" :description="error" />

      <section v-if="problems.length">
        <h3>字段校验问题（{{ problems.length }}）</h3>
        <div class="definition-import__table-wrap">
          <table>
            <thead><tr><th>位置</th><th>字段</th><th>问题</th></tr></thead>
            <tbody>
              <tr v-for="(problem, index) in problems" :key="`${problem.row}-${problem.field}-${index}`">
                <td>{{ problem.sheet }} {{ problem.row > 0 ? `第 ${problem.row} 行` : '文件' }}</td><td>{{ problem.field }}</td><td>{{ problem.message }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <a-alert v-if="importedCount !== null" type="success" show-icon :message="`成功导入 ${importedCount} 条文书定义`" />
    </div>
    <template #footer>
      <div class="definition-import__footer">
        <a-button :disabled="importing" @click="close">关闭</a-button>
        <a-button type="primary" data-testid="definition-import-submit" :loading="importing" :disabled="!file || importing || resultUnknown || importedCount !== null" @click="submit">
          <template #icon><Upload :size="15" /></template>开始导入
        </a-button>
      </div>
    </template>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { Download, Upload } from 'lucide-vue-next'
import {
  DOCUMENT_DEFINITION_IMPORT_MAX_BYTES,
  DOCUMENT_DEFINITION_IMPORT_TEMPLATE_FILENAME,
  downloadDocumentDefinitionImportTemplate,
  importDocumentDefinitions,
  type DocumentDefinitionImportProblem,
} from '@/api/documentDefinitions'
import { useAuthStore } from '@/stores/auth'
import { downloadBlob } from '@/views/workstation-v4/customer-sample-validation/batchExport'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: []; imported: [] }>()
const auth = useAuthStore()
const actorKey = computed(() => `${auth.user?.id || ''}|${[...auth.userRoles].sort().join(',')}`)
const fileInput = ref<HTMLInputElement | null>(null)
const file = ref<File | null>(null)
const importing = ref(false)
const downloading = ref(false)
const resultUnknown = ref(false)
const error = ref('')
const problems = ref<DocumentDefinitionImportProblem[]>([])
const importedCount = ref<number | null>(null)
let importSequence = 0
let downloadSequence = 0

function reset() {
  file.value = null; importing.value = false; downloading.value = false; resultUnknown.value = false
  error.value = ''; problems.value = []; importedCount.value = null
  if (fileInput.value) fileInput.value.value = ''
}
function close() {
  if (importing.value) return message.warning('导入处理中，请等待当前请求完成')
  emit('close')
}
function selectFile(event: Event) {
  const selected = (event.target as HTMLInputElement).files?.[0] || null
  file.value = null
  error.value = ''; problems.value = []; importedCount.value = null; resultUnknown.value = false
  if (!selected) return void (file.value = null)
  if (!selected.name.toLowerCase().endsWith('.xlsx')) return void (error.value = '仅支持 .xlsx 文书定义模板')
  if (selected.size > DOCUMENT_DEFINITION_IMPORT_MAX_BYTES) return void (error.value = '文件不能超过 2 MiB')
  file.value = selected
}
async function downloadTemplate() {
  const sequence = ++downloadSequence
  downloading.value = true
  const result = await downloadDocumentDefinitionImportTemplate()
  if (sequence !== downloadSequence) return
  downloading.value = false
  if (result.success === false) return message.error(result.message)
  downloadBlob(result.data, DOCUMENT_DEFINITION_IMPORT_TEMPLATE_FILENAME)
}
async function submit() {
  if (!file.value || importing.value || resultUnknown.value || importedCount.value !== null) return
  const sequence = ++importSequence
  importing.value = true; error.value = ''; problems.value = []
  const result = await importDocumentDefinitions(file.value)
  if (sequence !== importSequence) return
  importing.value = false
  if (result.success === false) {
    error.value = result.message; problems.value = result.problems; resultUnknown.value = result.resultUnknown
    return
  }
  importedCount.value = result.data.imported_count
  message.success(`成功导入 ${result.data.imported_count} 条文书定义`)
  emit('imported')
}
watch(() => props.open, (open) => {
  if (!open) return
  importSequence += 1
  downloadSequence += 1
  reset()
})
watch(actorKey, () => {
  importSequence += 1
  downloadSequence += 1
  downloading.value = false
  reset()
})
onBeforeUnmount(() => {
  importSequence += 1
  downloadSequence += 1
})
</script>

<style scoped>
.definition-import { display: grid; gap: 20px; color: #1d1d1f; font-family: 'Source Han Sans SC','Microsoft YaHei UI','PingFang SC',sans-serif; }
.definition-import section { display: grid; gap: 12px; }
.definition-import h3 { margin: 0; font-size: 16px; }
.definition-import p { margin: 4px 0 0; color: rgba(29,29,31,.6); }
.definition-import__heading,.definition-import__footer { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.definition-import__table-wrap { max-height: 320px; overflow: auto; border: 1px solid rgba(0,0,0,.08); border-radius: 8px; }
table { width: 100%; border-collapse: collapse; } th,td { padding: 9px 12px; border-bottom: 1px solid rgba(0,0,0,.06); text-align: left; }
</style>
