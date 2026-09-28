<template>
  <div class="document-definitions-page">
    <header class="document-definitions-page__header">
      <div>
        <h2>文书管理</h2>
      </div>
      <a-button v-if="canWrite" type="primary" data-testid="definition-import-open" @click="importOpen = true">
        <template #icon><FileUp :size="16" /></template>
        导入文书定义
      </a-button>
    </header>

    <a-alert
      v-if="!canWrite"
      type="info"
      show-icon
      message="当前账号无权访问文书定义。"
    />

    <div v-if="loadError" class="document-definitions-page__error" role="alert" data-testid="definition-list-error">
      <span>{{ loadError }}</span>
      <a-button size="small" @click="loadDefinitions">重试</a-button>
    </div>

    <section class="document-definitions-page__panel">
      <div class="document-definitions-page__toolbar">
        <strong>文书定义列表</strong>
        <span v-if="listLoaded" data-testid="definition-total">共 {{ total }} 条</span>
      </div>

      <div class="document-definitions-page__filters">
        <label>
          <span>文书名称</span>
          <a-input
            v-model:value="searchDraft"
            data-testid="definition-name-query"
            placeholder="输入文书名称"
            :maxlength="200"
            allow-clear
            @press-enter="applySearch"
          />
        </label>
        <div class="document-definitions-page__filter-actions">
          <a-button type="primary" data-testid="definition-search" @click="applySearch">
            <template #icon><Search :size="15" /></template>
            查询
          </a-button>
          <a-button data-testid="definition-search-reset" :disabled="!searchDraft && !appliedQuery" @click="resetSearch">
            <template #icon><RotateCcw :size="15" /></template>
            重置
          </a-button>
        </div>
      </div>

      <a-spin :spinning="loading" tip="正在读取文书定义">
        <div class="document-definitions-page__table-wrap">
          <table :aria-busy="loading">
          <thead>
            <tr>
              <th>文书编码</th>
              <th>文书名称</th>
              <th>分类</th>
              <th>模板内容</th>
              <th>导入批次</th>
              <th>创建人</th>
              <th>导入时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="definition in definitions" :key="definition.id" data-testid="definition-row">
              <td><code>{{ displayText(definition.code) }}</code></td>
              <td>{{ displayText(definition.name) }}</td>
              <td>{{ displayText(definition.category) }}</td>
              <td class="document-definitions-page__template">
                <pre>{{ definition.template_content.length ? definition.template_content : '未知' }}</pre>
              </td>
              <td><code>{{ displayText(definition.import_batch_id) }}</code></td>
              <td>{{ displayText(definition.created_by) }}</td>
              <td>{{ formatTime(definition.created_at) }}</td>
            </tr>
            <tr v-if="listLoaded && definitions.length === 0">
              <td colspan="7" class="document-definitions-page__empty">
                {{ appliedQuery ? '未找到匹配的文书定义' : '暂无已导入的文书定义' }}
              </td>
            </tr>
          </tbody>
          </table>
        </div>
      </a-spin>

      <a-pagination
        v-if="listLoaded && total > pageSize"
        :current="page"
        :page-size="pageSize"
        :total="total"
        :show-size-changer="false"
        @change="changePage"
      />
    </section>

    <DocumentDefinitionImportDrawer
      :open="importOpen"
      @close="importOpen = false"
      @imported="handleImported"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { FileUp, RotateCcw, Search } from 'lucide-vue-next'
import { listDocumentDefinitions, type DocumentDefinition } from '@/api/documentDefinitions'
import { useAuthStore } from '@/stores/auth'
import DocumentDefinitionImportDrawer from './components/DocumentDefinitionImportDrawer.vue'

const auth = useAuthStore()
const canWrite = computed(() => auth.userRoles.some((role) => ['admin', 'qc_manager'].includes(role)))
const actorKey = computed(() => `${auth.user?.id || ''}|${[...auth.userRoles].sort().join(',')}`)
const definitions = ref<DocumentDefinition[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)
const listLoaded = ref(false)
const loadError = ref('')
const importOpen = ref(false)
const searchDraft = ref('')
const appliedQuery = ref('')
let requestSequence = 0
let mounted = false

function clearList() {
  definitions.value = []
  total.value = 0
  listLoaded.value = false
  loadError.value = ''
}

async function loadDefinitions() {
  if (!canWrite.value) {
    clearList()
    loadError.value = '当前账号无权访问文书定义'
    return
  }
  if (!auth.user?.id) {
    clearList()
    loadError.value = '当前账号不可用，请重新登录后重试'
    return
  }
  const sequence = ++requestSequence
  const actor = actorKey.value
  loading.value = true
  loadError.value = ''
  const params = appliedQuery.value
    ? { page: page.value, page_size: pageSize, q: appliedQuery.value }
    : { page: page.value, page_size: pageSize }
  const result = await listDocumentDefinitions(params)
  if (sequence !== requestSequence || actor !== actorKey.value) return
  loading.value = false
  if (result.success === false) {
    clearList()
    loadError.value = result.message
    return
  }
  definitions.value = result.data.items
  total.value = result.data.total
  page.value = result.data.page
  listLoaded.value = true
}

function changePage(nextPage: number) {
  if (!Number.isInteger(nextPage) || nextPage < 1 || nextPage === page.value) return
  page.value = nextPage
  void loadDefinitions()
}

function applySearch() {
  const query = searchDraft.value.trim()
  if (query.length > 200) {
    requestSequence += 1
    loading.value = false
    clearList()
    loadError.value = '文书名称不能超过 200 个字符'
    return
  }
  searchDraft.value = query
  appliedQuery.value = query
  page.value = 1
  void loadDefinitions()
}

function resetSearch() {
  searchDraft.value = ''
  appliedQuery.value = ''
  page.value = 1
  void loadDefinitions()
}

async function handleImported() {
  importOpen.value = false
  page.value = 1
  await loadDefinitions()
}

function displayText(value: string) {
  return value.trim() || '未知'
}

function formatTime(value: string) {
  const timestamp = Date.parse(value)
  if (!Number.isFinite(timestamp)) return '未知'
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(new Date(timestamp))
}

watch(actorKey, () => {
  requestSequence += 1
  loading.value = false
  importOpen.value = false
  page.value = 1
  clearList()
  searchDraft.value = ''
  appliedQuery.value = ''
  if (mounted && auth.user?.id) void loadDefinitions()
  else if (mounted) loadError.value = '当前账号不可用，请重新登录后重试'
})

onMounted(() => {
  mounted = true
  void loadDefinitions()
})
onBeforeUnmount(() => {
  mounted = false
  requestSequence += 1
})
</script>

<style scoped>
.document-definitions-page {
  min-height: 100%;
  padding: 24px;
  background: #f5f7fa;
  color: #1d1d1f;
  font-family: 'Source Han Sans SC', 'Microsoft YaHei UI', 'PingFang SC', sans-serif;
}
.document-definitions-page__header,
.document-definitions-page__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.document-definitions-page__header { margin-bottom: 18px; }
.document-definitions-page__header h2 { margin: 0; font-size: 24px; line-height: 1.35; }
.document-definitions-page__panel {
  margin-top: 16px;
  padding: 18px;
  background: #fff;
  border: 1px solid rgba(0, 0, 0, .08);
  border-radius: 8px;
  box-shadow: 0 2px 10px rgba(15, 23, 42, .04);
}
.document-definitions-page__toolbar { margin-bottom: 14px; }
.document-definitions-page__toolbar span { color: rgba(29, 29, 31, .62); }
.document-definitions-page__filters {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  margin-bottom: 16px;
}
.document-definitions-page__filters label { display: grid; gap: 6px; width: min(360px, 100%); color: rgba(29, 29, 31, .68); font-size: 13px; }
.document-definitions-page__filter-actions { display: flex; gap: 8px; }
.document-definitions-page__table-wrap { max-width: 100%; overflow-x: auto; }
table { width: 100%; min-width: 1120px; border-collapse: collapse; table-layout: fixed; }
th, td { padding: 11px 12px; border-bottom: 1px solid rgba(0, 0, 0, .07); overflow-wrap: anywhere; text-align: left; vertical-align: top; }
th { background: #fafbfc; color: rgba(29, 29, 31, .68); font-size: 13px; font-weight: 600; }
th:nth-child(1) { width: 130px; } th:nth-child(2) { width: 150px; } th:nth-child(3) { width: 120px; }
th:nth-child(4) { width: 310px; } th:nth-child(5) { width: 170px; } th:nth-child(6) { width: 120px; } th:nth-child(7) { width: 160px; }
code { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 12px; }
.document-definitions-page__template pre {
  max-height: 112px;
  margin: 0;
  overflow: auto;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font: inherit;
  line-height: 1.55;
}
.document-definitions-page__empty { padding: 36px; color: rgba(29, 29, 31, .48); text-align: center; }
.document-definitions-page__error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  padding: 10px 12px;
  color: #a8071a;
  background: #fff2f0;
  border: 1px solid #ffccc7;
  border-radius: 6px;
}
.document-definitions-page :deep(.ant-pagination) { margin-top: 16px; text-align: right; }
@media (max-width: 720px) {
  .document-definitions-page { padding: 16px; }
  .document-definitions-page__header { align-items: flex-start; }
  .document-definitions-page__filters { align-items: stretch; flex-direction: column; }
}
</style>
