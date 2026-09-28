<template>
  <div class="test-records-page">
    <a-card
      :bordered="false"
      class="test-records-page__header"
    >
      <div class="test-records-page__title-row">
        <div>
          <h2 class="test-records-page__title">
            测试病历管理
          </h2>
          <p class="test-records-page__subtitle">
            客户自建测试病历（固定池 {{ CUSTOMER_TEST_POOL_ID }}），用于验证质控点。
          </p>
        </div>
        <a-space>
          <a-button @click="importOpen = true">
            <template #icon><FileUp :size="15" aria-hidden="true" /></template>
            导入 Excel
          </a-button>
          <a-button
            type="primary"
            @click="goCreate"
          >
            新建测试病历
          </a-button>
        </a-space>
      </div>
      <a-alert
        type="info"
        show-icon
        class="test-records-page__blocked"
        message="以下能力缺少权威数据，暂未提供"
      >
        <template #description>
          <ul class="test-records-page__blocked-list">
            <li
              v-for="note in BLOCKED_NOTES"
              :key="note"
            >
              {{ note }}
            </li>
          </ul>
        </template>
      </a-alert>
    </a-card>

    <a-card :bordered="false">
      <div class="test-records-page__toolbar">
        <a-space wrap>
          <a-input-search
            v-model:value="keyword"
            allow-clear
            placeholder="患者姓名 / 住院号 / 就诊号 / 科室"
            class="test-records-page__search"
            @search="store.search()"
          />
          <a-checkbox
            v-model:checked="includeRemoved"
            @change="store.search()"
          >
            显示已移除和已被替换
          </a-checkbox>
        </a-space>
        <a-space>
          <span class="test-records-page__muted">已选 {{ selectedIds.length }} 条</span>
          <a-button
            v-if="canTransferRecords"
            data-testid="export-selected-records"
            :disabled="!selectedRunnable.length || exporting"
            :loading="exporting"
            @click="exportSelected"
          >
            <template #icon><Download :size="15" aria-hidden="true" /></template>
            导出所选
          </a-button>
          <a-button
            :disabled="!selectedRunnable.length"
            @click="openRun(selectedRunnable)"
          >
            运行所选病历
          </a-button>
        </a-space>
      </div>

      <a-alert
        v-if="loadError"
        type="error"
        show-icon
        :message="loadError"
        class="test-records-page__error"
      />

      <a-table
        row-key="id"
        :loading="loading"
        :columns="columns"
        :data-source="items"
        :pagination="pagination"
        :row-selection="rowSelection"
        :scroll="{ x: 1280 }"
        @change="handleTableChange"
      >
        <template #bodyCell="{ column, record: rawRecord }">
          <template v-for="record in [asItem(rawRecord)]" :key="record.id">
          <template v-if="column.key === 'title'">
            <div class="test-records-page__cell-stack">
              <strong>{{ record.case_title || '未命名测试病历' }}</strong>
              <a-space
                size="small"
                wrap
              >
                <a-tag :color="resolveStateTag(record).color">
                  {{ resolveStateTag(record).text }}
                </a-tag>
                <span class="test-records-page__muted">{{ resolveOriginText(record) }}</span>
              </a-space>
            </div>
          </template>
          <template v-else-if="column.key === 'patient'">
            <div class="test-records-page__cell-stack">
              <span>{{ record.patient_name || '未知' }}</span>
              <span class="test-records-page__muted">{{ record.department || '未知科室' }}</span>
            </div>
          </template>
          <template v-else-if="column.key === 'identity'">
            <div class="test-records-page__cell-stack test-records-page__mono">
              <span>{{ record.visit_id || '未知' }}</span>
              <span class="test-records-page__muted">{{ record.institute_id }} / {{ record.patient_id }}</span>
            </div>
          </template>
          <template v-else-if="column.key === 'documents'">
            {{ formatDocumentCount(record.document_count) }}
          </template>
          <template v-else-if="column.key === 'rules'">
            <div class="test-records-page__cell-stack">
              <span>{{ record.rule_count }} 个</span>
              <span class="test-records-page__muted">{{ record.rule_ids.slice(0, 3).join('、') }}{{ record.rule_ids.length > 3 ? ' …' : '' }}</span>
            </div>
          </template>
          <template v-else-if="column.key === 'job'">
            <span class="test-records-page__mono">{{ record.latest_job_id || '—' }}</span>
          </template>
          <template v-else-if="column.key === 'createdAt'">
            {{ formatDateTime(record.created_at) }}
          </template>
          <template v-else-if="column.key === 'actions'">
            <a-space
              size="small"
              wrap
            >
              <a @click="openDocuments(record)">查看文书</a>
              <a @click="openResult(record)">查看结果</a>
              <template v-if="record.state === 'active'">
                <a @click="openEdit(record)">编辑</a>
                <a-button
                  v-if="canTransferRecords"
                  type="link"
                  size="small"
                  class="test-records-page__link-button"
                  :data-testid="`copy-record-${record.id}`"
                  :disabled="copyingId !== null"
                  :loading="copyingId === record.id"
                  @click="confirmCopy(record)"
                >
                  复制
                </a-button>
                <a @click="openRules(record)">关联质控点</a>
                <a @click="openRun([record])">运行</a>
                <a
                  class="test-records-page__danger"
                  @click="confirmRemove(record)"
                >移除</a>
              </template>
            </a-space>
          </template>
          </template>
        </template>
      </a-table>
    </a-card>

    <TestRecordRulePickerModal
      :open="rulesTarget !== null"
      title="关联质控点"
      ok-text="保存关联"
      :catalog="ruleCatalog"
      :catalog-error="ruleCatalogError"
      :initial-rule-ids="rulesTarget?.rule_ids || []"
      :submitting="rulesSaving"
      hint="规则范围为当前规则集版本的全部规则（含暂停、下线）；保存后写入该病历的关联质控点。"
      @confirm="saveRules"
      @cancel="rulesTarget = null"
    />

    <TestRecordRulePickerModal
      :open="runTargets.length > 0"
      :title="`运行质控点（${runTargets.length} 份病历）`"
      ok-text="创建运行任务"
      :catalog="ruleCatalog"
      :catalog-error="ruleCatalogError"
      :initial-rule-ids="runInitialRuleIds"
      :submitting="running"
      require-selection
      hint="默认勾选所选病历关联质控点的并集；此处临时调整只影响本次运行，不修改关联。"
      @confirm="submitRun"
      @cancel="runTargets = []"
    />

    <TestRecordEditDrawer
      :open="editTarget !== null"
      :item="editTarget"
      @close="editTarget = null"
      @saved="handleEditSaved"
    />

    <TestRecordImportDrawer
      :open="importOpen"
      @close="importOpen = false"
      @imported="handleImported"
    />

    <a-drawer
      :open="documentsTarget !== null"
      placement="right"
      width="min(1380px, 100vw)"
      title="病历文书"
      :body-style="{ padding: 0 }"
      @close="documentsTarget = null"
    >
      <QCRecordCompareWorkbench
        v-if="documentsTarget"
        :visit-id="documentsTarget.visit_id"
        :institute-id="documentsTarget.institute_id"
        :patient-id="documentsTarget.patient_id"
        :issues="[]"
        document-only
      />
    </a-drawer>

    <QCRecordResultComparisonDrawer
      :open="resultFocus !== null"
      :focus="resultFocus"
      presentation-mode="grouped"
      @close="resultFocus = null"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Download, FileUp } from 'lucide-vue-next'
import { useRouter } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import type { ColumnsType } from 'ant-design-vue/es/table'
import { storeToRefs } from 'pinia'
import { useTestMedicalRecordsStore } from '@/stores/testMedicalRecords'
import { useAuthStore } from '@/stores/auth'
import {
  CUSTOMER_TEST_POOL_ID,
  TEST_RECORD_EXPORT_FILENAME,
  copyTestRecord,
  exportTestRecords,
  isRunnableTestRecord,
  runTestRecords,
  unionTestRecordRuleIds,
} from '@/services/test-medical-records'
import type { TestRecordItem } from '@/types/test-medical-records'
import QCRecordResultComparisonDrawer, {
  type QCRecordResultFocus,
} from '@/views/workstation-v4/customer-sample-validation/QCRecordResultComparisonDrawer.vue'
import QCRecordCompareWorkbench from '@/views/workstation-v4/semantic-rules/components/QCRecordCompareWorkbench.vue'
import { downloadBlob } from '@/views/workstation-v4/customer-sample-validation/batchExport'
import TestRecordRulePickerModal from './components/TestRecordRulePickerModal.vue'
import TestRecordEditDrawer from './components/TestRecordEditDrawer.vue'
import TestRecordImportDrawer from './components/TestRecordImportDrawer.vue'
import {
  formatDateTime,
  formatDocumentCount,
  resolveOriginText,
  resolveStateTag,
} from './components/testRecordPresentation'

/** 合同第 3 节阻塞项：只做说明，不提供假功能。 */
const BLOCKED_NOTES = [
  '预期结果比对：人工预期结果目前只写入、没有权威读取来源。',
  '文书类型“其他”的归属：目前映射到日常病程，待客户确认口径。',
  '新建质控点时的测试病历验证：新质控点需先有执行器实现。',
]

const router = useRouter()
const store = useTestMedicalRecordsStore()
const authStore = useAuthStore()
const {
  items,
  total,
  page,
  pageSize,
  keyword,
  includeRemoved,
  loading,
  loadError,
  selectedIds,
  selectedItems,
  ruleCatalog,
  ruleCatalogError,
} = storeToRefs(store)

const columns: ColumnsType<TestRecordItem> = [
  { title: '测试病历', key: 'title', width: 260 },
  { title: '患者 / 科室', key: 'patient', width: 150 },
  { title: '就诊号 / 机构 / 患者 ID', key: 'identity', width: 260 },
  { title: '文书数', key: 'documents', width: 80 },
  { title: '关联质控点', key: 'rules', width: 200 },
  { title: '最近任务', key: 'job', width: 150 },
  { title: '创建时间', key: 'createdAt', width: 150 },
  { title: '操作', key: 'actions', width: 260, fixed: 'right' },
]

const pagination = computed(() => ({
  current: page.value,
  pageSize: pageSize.value,
  total: total.value,
  showSizeChanger: true,
  showTotal: (count: number) => `共 ${count} 条`,
}))

const rowSelection = computed(() => ({
  selectedRowKeys: selectedIds.value,
  onChange: (keys: (string | number)[]) => {
    selectedIds.value = keys.map((key) => String(key))
  },
  getCheckboxProps: (record: TestRecordItem) => ({ disabled: !isRunnableTestRecord(record) }),
}))

/** 表格插槽的 record 类型为宽泛对象；数据源即 TestRecordItem[]，此处收窄。 */
function asItem(record: Record<string, unknown>): TestRecordItem {
  return record as unknown as TestRecordItem
}

const selectedRunnable = computed(() => selectedItems.value.filter(isRunnableTestRecord))
const importOpen = ref(false)
const exporting = ref(false)
const copyingId = ref<string | null>(null)
const exportRevision = ref(0)
const copyRevision = ref(0)
const actorKey = computed(() => {
  const actor = authStore.user
  const roles = [...authStore.userRoles].sort()
  return `${actor?.id || ''}|${roles.join(',')}`
})
const canTransferRecords = computed(() => (
  authStore.userRoles.includes('admin') || authStore.userRoles.includes('qc_manager')
))

function invalidatePendingActions() {
  exportRevision.value += 1
  copyRevision.value += 1
  exporting.value = false
  copyingId.value = null
}

async function exportSelected() {
  if (!selectedRunnable.value.length || exporting.value) return
  if (selectedRunnable.value.length !== selectedIds.value.length) {
    message.warning('所选病历中包含不可导出的条目，请刷新后重新选择')
    return
  }
  const revision = ++exportRevision.value
  exporting.value = true
  const result = await exportTestRecords(selectedRunnable.value.map((item) => item.id))
  if (revision !== exportRevision.value) return
  exporting.value = false
  if (!result.success || !result.data) {
    message.error(result.message || '导出测试病历失败')
    return
  }
  downloadBlob(result.data, TEST_RECORD_EXPORT_FILENAME)
}

function confirmCopy(item: TestRecordItem) {
  if (copyingId.value !== null) return
  Modal.confirm({
    title: '复制该测试病历？',
    content: '将按当前源版本创建一份全新测试病例；原病历、历史质控结果和最近任务不会修改或复制。',
    okText: '确认复制',
    cancelText: '取消',
    onOk: async () => {
      const revision = ++copyRevision.value
      copyingId.value = item.id
      const result = await copyTestRecord(item)
      if (revision !== copyRevision.value) return
      copyingId.value = null
      if (!result.success || !result.data) {
        message.error(result.message || '复制测试病历失败')
        return
      }
      if (result.data.bundle_status === 'ready') {
        message.success(`测试病历已复制：${result.data.visit_id}`)
      } else if (result.data.bundle_status === 'pending') {
        message.info(`测试病历已创建：${result.data.visit_id}，资料准备中`)
      } else {
        message.warning(`测试病历已创建：${result.data.visit_id}，资料状态尚未就绪，请刷新核对`)
      }
      await store.load()
    },
  })
}

async function handleImported() {
  await store.load()
}

function handleTableChange(info: { current?: number; pageSize?: number }) {
  void store.changePage(info.current || 1, info.pageSize || pageSize.value)
}

function goCreate() {
  void router.push({ name: 'WorkstationV4SyntheticCaseNew' })
}

// 查看文书 / 结果
const documentsTarget = ref<TestRecordItem | null>(null)
const resultFocus = ref<QCRecordResultFocus | null>(null)

function openDocuments(item: TestRecordItem) {
  documentsTarget.value = item
}

function openResult(item: TestRecordItem) {
  if (!item.institute_id || !item.patient_id || !item.visit_id) {
    message.warning('病例三坐标不完整，无法读取质控结果')
    return
  }
  resultFocus.value = {
    visitId: item.visit_id,
    instituteId: item.institute_id,
    patientId: item.patient_id,
    recordId: item.id,
    patientName: item.patient_name,
    label: [item.case_title || item.patient_name || '测试病历', item.department || '未分科室', `就诊号 ${item.visit_id}`].join(' · '),
  }
}

// 编辑
const editTarget = ref<TestRecordItem | null>(null)

function openEdit(item: TestRecordItem) {
  editTarget.value = item
}

async function handleEditSaved() {
  editTarget.value = null
  await store.load()
}

// 关联质控点
const rulesTarget = ref<TestRecordItem | null>(null)
const rulesSaving = ref(false)

async function openRules(item: TestRecordItem) {
  rulesTarget.value = item
  await store.ensureRuleCatalog()
}

async function saveRules(ruleIds: string[]) {
  const item = rulesTarget.value
  if (!item) return
  rulesSaving.value = true
  const result = await store.saveRules(item, ruleIds)
  rulesSaving.value = false
  if (!result.success) {
    message.error(result.message || '更新关联质控点失败')
    return
  }
  message.success('关联质控点已更新')
  rulesTarget.value = null
}

// 运行
const runTargets = ref<TestRecordItem[]>([])
const running = ref(false)
const runInitialRuleIds = computed(() => unionTestRecordRuleIds(runTargets.value))

async function openRun(targets: TestRecordItem[]) {
  runTargets.value = targets.filter(isRunnableTestRecord)
  if (!runTargets.value.length) {
    message.warning('所选病历均不可运行')
    return
  }
  await store.ensureRuleCatalog()
}

async function submitRun(ruleIds: string[]) {
  running.value = true
  let result
  try {
    result = await runTestRecords(runTargets.value, ruleIds)
  } catch (error) {
    running.value = false
    message.warning(error instanceof Error ? error.message : '运行参数不完整')
    return
  }
  running.value = false
  if (!result.success || !result.data) {
    message.error(result.message || '创建运行任务失败')
    return
  }
  message.success(`运行任务已创建：${result.data.job_id}，完成后可点击“查看结果”`)
  runTargets.value = []
}

// 移除
function confirmRemove(item: TestRecordItem) {
  Modal.confirm({
    title: '确认移除该测试病历？',
    content: '移除后不再出现在列表和批次中；病历数据与已运行结果保留，可在“显示已移除”中追溯。',
    okText: '确认移除',
    okType: 'danger',
    cancelText: '取消',
    onOk: async () => {
      const result = await store.remove(item)
      if (!result.success) {
        message.error(result.message || '移除测试病历失败')
        return
      }
      message.success('测试病历已移除')
    },
  })
}

onMounted(() => {
  void store.load()
})

watch(actorKey, invalidatePendingActions)

onBeforeUnmount(invalidatePendingActions)
</script>

<style scoped>
.test-records-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
  background: var(--ant-color-bg-layout, #f5f7fa);
}

.test-records-page__title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.test-records-page__title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.test-records-page__subtitle,
.test-records-page__muted {
  margin: 4px 0 0;
  color: var(--ant-color-text-secondary, #64748b);
  font-size: 12px;
}

.test-records-page__blocked {
  margin-top: 12px;
}

.test-records-page__blocked-list {
  margin: 0;
  padding-left: 18px;
}

.test-records-page__toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.test-records-page__search {
  width: 300px;
}

.test-records-page__error {
  margin-bottom: 12px;
}

.test-records-page__cell-stack {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.test-records-page__mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
  word-break: break-all;
}

.test-records-page__danger {
  color: var(--ant-color-error, #dc2626);
}

.test-records-page__link-button {
  height: auto;
  padding: 0;
}
</style>
