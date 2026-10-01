<template>
  <div
    class="quality-control-point-management"
    :class="{ 'quality-control-point-management--embedded': embedded }"
  >
    <!-- 页面标题与规则集 -->
    <div class="page-header mb-6">
      <h2 class="page-title">
        {{ pageTitle }}
      </h2>
      <div class="rule-set-bar">
        <span class="bar-label">规则集</span>
        <a-select
          v-if="!isCodingMode"
          v-model:value="ruleSetKey"
          class="rule-set-select"
          :options="ruleSetOptions"
          :disabled="saving"
        />
        <span v-else class="coding-rule-set-label">编码质控规则</span>
        <span class="current-version">
          当前生效版本：<strong>{{ versionList?.current_version || UNKNOWN_TEXT }}</strong>
        </span>
        <a-button
          class="action-btn history-btn"
          :disabled="!versionList"
          @click="historyOpen = true"
        >
          版本历史
        </a-button>
        <a-button
          class="action-btn"
          :loading="exportingCurrent"
          :disabled="!versionList?.current_version"
          @click="downloadCurrentVersion"
        >
          导出当前版本
        </a-button>
        <a-button v-if="editable" type="primary" class="action-btn" @click="importOpen = true">
          导入草稿
        </a-button>
      </div>
    </div>

    <a-alert
      v-if="versionList && !versionList.versionable"
      type="info"
      show-icon
      class="page-alert"
      message="该规则集暂仅内置版本，质控点状态只读展示。"
    />
    <a-alert
      v-else-if="versionList && !canManage"
      type="info"
      show-icon
      class="page-alert"
      message="当前角色只读：仅管理员或质控管理员可调整质控点状态并发布版本。"
    />
    <a-alert v-if="loadError" type="error" show-icon class="page-alert" :message="loadError" />

    <!-- 草稿面板 -->
    <RuleSetDraftPanel
      v-if="draft && versionList"
      :rule-set-key="ruleSetKey"
      :draft="draft"
      :diff="draftDiff"
      :current-version="versionList.current_version"
      :can-write="editable"
      @refresh="load"
    />

    <!-- 标签页 -->
    <div class="tabs-container">
      <a-tabs v-model:active-key="activeTab" class="custom-tabs">
        <a-tab-pane key="online" :tab="`已上线（${onlineCount}）`" />
        <a-tab-pane key="offline" :tab="`未上线（${offlineCount}）`" />
      </a-tabs>
    </div>

    <!-- 操作栏 -->
    <div class="action-bar mb-4">
      <div class="batch-actions">
        <template v-if="editable">
          <a-tooltip :title="enableBlockedReason">
            <a-button
              :disabled="selectedRowKeys.length === 0 || Boolean(enableBlockedReason) || saving"
              class="batch-btn batch-enable"
              @click="applyBatch('active')"
            >
              批量开启
            </a-button>
          </a-tooltip>
          <a-button
            :disabled="selectedRowKeys.length === 0 || saving"
            class="batch-btn batch-pause"
            @click="applyBatch('paused')"
          >
            批量暂停
          </a-button>
          <a-button
            :disabled="selectedRowKeys.length === 0 || saving"
            class="batch-btn batch-offline"
            @click="applyBatch('offline')"
          >
            批量下线
          </a-button>
          <a-popconfirm
            title="确认从后续版本删除所选质控点？删除发布后不能恢复，历史版本仍保留记录。"
            ok-text="删除"
            cancel-text="取消"
            @open-change="handleDeleteConfirmOpen"
            @confirm="confirmDelete"
          >
            <a-button
              danger
              :disabled="selectedRowKeys.length === 0 || Boolean(deleteBlockedReason) || saving"
              class="batch-btn batch-delete"
            >
              批量删除
            </a-button>
          </a-popconfirm>
          <a-button
            :disabled="selectedRowKeys.length === 0 || saving"
            class="batch-btn"
            @click="openSelectedApplicability"
          >
            配置适用范围
          </a-button>
          <span class="batch-hint">改动先写入草稿，发布新版本后生效</span>
        </template>
        <a-button
          v-if="canManage && !isCodingMode"
          type="primary"
          class="create-btn"
          @click="handleCreateNew"
        >
          新建质控点
        </a-button>
      </div>

      <!-- 右侧搜索 -->
      <div class="search-area">
        <a-select v-model:value="searchType" class="search-type-select">
          <a-select-option value="id"> 质控点ID </a-select-option>
          <a-select-option value="name"> 质控点名称 </a-select-option>
        </a-select>
        <a-input-search
          v-model:value="searchKeyword"
          placeholder="请输入"
          class="search-input"
          enter-button
          allow-clear
          @search="handleSearch"
        />
      </div>
    </div>

    <!-- 数据表格 -->
    <div class="table-container">
      <a-table
        :columns="tableColumns"
        :data-source="tableData"
        :row-selection="editable ? rowSelection : undefined"
        :pagination="paginationConfig"
        :loading="loading"
        row-key="rule_id"
        size="middle"
        class="quality-point-table"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'name'">
            <div class="name-cell">
              <div class="name-text">
                {{ asRow(record).name || UNKNOWN_TEXT }}
              </div>
              <div class="source-text">
                <template v-if="isCodingMode">
                  分类：{{ asRow(record).category || UNKNOWN_TEXT }}
                </template>
                <template v-else> 文书：{{ asRow(record).document || UNKNOWN_TEXT }} </template>
              </div>
            </div>
          </template>

          <template v-else-if="column.key === 'state'">
            <div class="state-cell">
              <a-tag :color="ENTRY_STATE_COLOR[asRow(record).state]">
                {{ ENTRY_STATE_LABEL[asRow(record).state] }}
              </a-tag>
              <a-tag v-if="asRow(record).draftState" color="blue" class="draft-state-tag">
                草稿：{{ ENTRY_STATE_LABEL[asRow(record).draftState as RuleSetEntryState] }}
              </a-tag>
            </div>
          </template>

          <template v-else-if="column.key === 'executable'">
            <a-tag v-if="asRow(record).executable === true" color="green"> 可执行 </a-tag>
            <a-tooltip
              v-else-if="asRow(record).executable === false"
              title="执行器未实现或规则未就绪，只能暂停或下线"
            >
              <a-tag color="red"> 不可执行 </a-tag>
            </a-tooltip>
            <span v-else class="unknown-text">{{ UNKNOWN_TEXT }}</span>
          </template>

          <template v-else-if="column.key === 'visibility'">
            <div class="state-cell">
              <a-tag :color="asRow(record).departmentScopeMode ? 'blue' : 'orange'">
                {{ scopeLabel(asRow(record)) }}
              </a-tag>
              <a-tag
                :color="
                  asRow(record).doctorVisible === true
                    ? 'green'
                    : asRow(record).doctorVisible === false
                      ? 'default'
                      : 'orange'
                "
              >
                {{ doctorVisibilityLabel(asRow(record).doctorVisible) }}
              </a-tag>
            </div>
          </template>

          <template v-else-if="column.key === 'operation'">
            <a-button
              type="link"
              size="small"
              class="view-btn"
              @click="openBuiltinDetail(asRow(record))"
            >
              查看
            </a-button>
          </template>
        </template>
      </a-table>
    </div>

    <CustomDraftPointsPanel
      v-if="!isCodingMode && activeTab === 'offline' && canManage"
      :actor-key="actorKey"
      :can-manage="canManage"
    />

    <a-drawer
      :open="Boolean(builtinDetail)"
      title="质控点详情"
      width="420"
      @close="builtinDetail = null"
    >
      <dl v-if="builtinDetail" class="builtin-detail">
        <dt>质控点ID</dt>
        <dd>{{ builtinDetail.rule_id }}</dd>
        <dt>质控点名称</dt>
        <dd>{{ builtinDetail.name || UNKNOWN_TEXT }}</dd>
        <dt>来源文书</dt>
        <dd>{{ builtinDetail.document || UNKNOWN_TEXT }}</dd>
        <dt>当前版本状态</dt>
        <dd>{{ ENTRY_STATE_LABEL[builtinDetail.state] }}</dd>
        <dt>草稿状态</dt>
        <dd>
          {{ builtinDetail.draftState ? ENTRY_STATE_LABEL[builtinDetail.draftState] : '无变更' }}
        </dd>
        <dt>是否可执行</dt>
        <dd>
          {{
            builtinDetail.executable === true
              ? '可执行'
              : builtinDetail.executable === false
                ? '不可执行'
                : UNKNOWN_TEXT
          }}
        </dd>
        <dt>生效科室</dt>
        <dd>{{ scopeLabel(builtinDetail) }}</dd>
        <dt>医生端</dt>
        <dd>{{ doctorVisibilityLabel(builtinDetail.doctorVisible) }}</dd>
        <dt>核心制度归属</dt>
        <dd>
          {{
            builtinDetail.coreSystemIds === null
              ? '未知'
              : builtinDetail.coreSystemIds.length
                ? builtinDetail.coreSystemIds.join('、')
                : '非核心制度'
          }}
        </dd>
      </dl>
      <div v-if="builtinDetail && editable" class="applicability-editor">
        <label>科室范围</label>
        <a-radio-group v-model:value="scopeMode">
          <a-radio-button value="all"> 全部科室 </a-radio-button>
          <a-radio-button value="selected"> 指定科室 </a-radio-button>
        </a-radio-group>
        <template v-if="scopeMode === 'selected'">
          <label>指定科室（每行“医院ID|科室名”）</label>
          <a-textarea v-model:value="scopeRefsText" :rows="5" placeholder="HOSP-001|心内科" />
        </template>
        <label>医生端结果</label>
        <a-radio-group v-model:value="doctorVisibleChoice">
          <a-radio-button value="visible"> 开放 </a-radio-button>
          <a-radio-button value="hidden"> 不开放 </a-radio-button>
        </a-radio-group>
        <a-button type="primary" :loading="saving" @click="saveApplicability()">
          保存到草稿
        </a-button>
        <label>医疗质量安全核心制度归属</label>
        <a-radio-group v-model:value="coreClassification">
          <a-radio-button value="unknown"> 未分类 </a-radio-button>
          <a-radio-button value="none"> 非核心制度 </a-radio-button>
          <a-radio-button value="selected"> 指定制度 </a-radio-button>
        </a-radio-group>
        <a-select
          v-if="coreClassification === 'selected'"
          v-model:value="coreIds"
          mode="multiple"
          :options="coreSystems.map((item) => ({ value: item.id, label: item.name }))"
        />
        <p v-if="coreCatalogError" role="alert">{{ coreCatalogError }}</p>
        <a-button :loading="saving" @click="saveApplicability(true)"
          >保存核心制度归属到草稿</a-button
        >
      </div>
      <p class="builtin-detail-note">
        内置质控点由规则执行器实现，判定逻辑不支持在线编辑；可通过批量操作调整上线状态或删除。
      </p>
    </a-drawer>

    <RuleSetVersionHistoryDrawer
      v-model:open="historyOpen"
      :rule-set-key="ruleSetKey"
      :items="versionList?.items ?? []"
      :can-retire="editable"
      @refresh="load"
    />
    <RuleSetVersionImportDrawer
      v-model:open="importOpen"
      :rule-set-key="ruleSetKey"
      @refresh="load"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import type { TableColumnsType, TableProps } from 'ant-design-vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import {
  createRuleSetDraft,
  exportRuleSetVersion,
  getRuleSetVersion,
  getMedicalCoreSystems,
  listRuleSetVersions,
  updateRuleSetDraft,
  type RuleSetEntryState,
  type RuleSetVersionDetail,
  type RuleSetVersionList,
} from '@/api/ruleSetVersions'
import RuleSetDraftPanel from './components/RuleSetDraftPanel.vue'
import CustomDraftPointsPanel from './components/CustomDraftPointsPanel.vue'
import RuleSetVersionHistoryDrawer from './components/RuleSetVersionHistoryDrawer.vue'
import RuleSetVersionImportDrawer from './components/RuleSetVersionImportDrawer.vue'
import { downloadBlob } from '@/views/workstation-v4/customer-sample-validation/batchExport'
import {
  CODING_QC_RULE_SET_KEY,
  ENTRY_STATE_COLOR,
  ENTRY_STATE_LABEL,
  LX0609_RULE_SET_KEY,
  RULE_SET_OPTIONS,
  UNKNOWN_TEXT,
  applyStateToEntries,
  buildPointRows,
  describeFailure,
  diffEntries,
  filterRows,
  needsRefresh,
  nonExecutableRuleIds,
  rowsForTab,
  toRuleSetEntry,
  type EntryDiffItem,
  type PointTab,
  type QualityPointRow,
} from './ruleSetVersionModel'

const router = useRouter()
const authStore = useAuthStore()

const props = withDefaults(
  defineProps<{
    managementMode?: 'noncoding' | 'coding'
    embedded?: boolean
  }>(),
  {
    managementMode: 'noncoding',
    embedded: false,
  },
)

const isCodingMode = computed(() => props.managementMode === 'coding')
const pageTitle = computed(() => (isCodingMode.value ? '编码质控点管理' : '非编码质控点管理'))

const ruleSetOptions = RULE_SET_OPTIONS.map((item) => ({ ...item }))
const ruleSetKey = ref<string>(isCodingMode.value ? CODING_QC_RULE_SET_KEY : LX0609_RULE_SET_KEY)
const activeTab = ref<PointTab>('online')
const selectedRowKeys = ref<string[]>([])
const deleteConfirmContext = ref<{
  ruleSetKey: string
  actorKey: string
  ruleIds: string[]
} | null>(null)
const searchType = ref<'id' | 'name'>('id')
const searchKeyword = ref('')
const appliedKeyword = ref('')
const historyOpen = ref(false)
const importOpen = ref(false)
const exportingCurrent = ref(false)
/** 内置质控点只读详情；编码模式按手册不提供单项查看。 */
const builtinDetail = ref<QualityPointRow | null>(null)
const scopeMode = ref<'all' | 'selected' | ''>('')
const scopeRefsText = ref('')
const doctorVisibleChoice = ref<'visible' | 'hidden' | ''>('')
const scopeTargetIds = ref<string[]>([])
const coreClassification = ref<'unknown' | 'none' | 'selected'>('unknown')
const coreIds = ref<string[]>([])
const coreSystems = ref<Array<{ id: string; name: string }>>([])
const coreCatalogError = ref('')

const loading = ref(false)
const saving = ref(false)
const loadError = ref('')
const versionList = ref<RuleSetVersionList | null>(null)
const currentDetail = ref<RuleSetVersionDetail | null>(null)
/** 草稿基础版本不是当前版本时单独读取的基础版本详情。 */
const baseDetail = ref<RuleSetVersionDetail | null>(null)
let contextGeneration = 0
let loadGeneration = 0
let mutationGeneration = 0
let disposed = false

const actorKey = computed(() => {
  const userId = String(authStore.user?.id ?? '').trim()
  const roles = Array.isArray(authStore.userRoles)
    ? authStore.userRoles
        .map((role) => role.trim())
        .filter(Boolean)
        .sort()
    : []
  return userId ? `${userId}|${roles.join(',')}` : ''
})

/** 写权限沿用规则管理路由：admin / qc_manager。 */
const canManage = computed(() => authStore.hasRole('admin') || authStore.hasRole('qc_manager'))
/** 可写 = 角色可写且规则集支持版本发布（本批仅 LX0609）。 */
const editable = computed(() => canManage.value && versionList.value?.versionable === true)
const draft = computed(() => versionList.value?.draft ?? null)

const rows = computed<QualityPointRow[]>(() =>
  currentDetail.value
    ? buildPointRows(currentDetail.value.entries, draft.value?.entries ?? null)
    : [],
)
const onlineCount = computed(() => rowsForTab(rows.value, 'online').length)
const offlineCount = computed(() => rowsForTab(rows.value, 'offline').length)
const tableData = computed(() =>
  filterRows(rowsForTab(rows.value, activeTab.value), searchType.value, appliedKeyword.value),
)

const draftDiff = computed<EntryDiffItem[] | null>(() => {
  const current = draft.value
  if (!current) return []
  const base =
    current.base_version === currentDetail.value?.version ? currentDetail.value : baseDetail.value
  return base ? diffEntries(base.entries, current.entries) : null
})

const enableBlockedReason = computed(() => {
  const blocked = nonExecutableRuleIds(rows.value, selectedRowKeys.value)
  if (!blocked.length) return ''
  return `所选质控点中 ${blocked.join('、')} 当前不可执行（执行器未实现或规则未就绪），不能开启`
})

const deleteBlockedReason = computed(() => {
  const selected = new Set(selectedRowKeys.value)
  const blocked = rows.value.filter(
    (row) =>
      selected.has(row.rule_id) &&
      ((row.state !== 'paused' && row.state !== 'offline') || row.draftState === 'deleted'),
  )
  if (!blocked.length) return ''
  return '只能删除当前版本中已暂停或已下线、且草稿中尚未删除的质控点'
})

const tableColumns = computed<TableColumnsType<QualityPointRow>>(() => [
  { title: '质控点ID', dataIndex: 'rule_id', key: 'rule_id', width: 140 },
  {
    title: isCodingMode.value ? '质控点名称 / 分类' : '质控点名称 / 文书',
    dataIndex: 'name',
    key: 'name',
  },
  {
    title: activeTab.value === 'online' ? '状态' : '状态（暂停 / 下线）',
    dataIndex: 'state',
    key: 'state',
    width: 220,
  },
  { title: '是否可执行', dataIndex: 'executable', key: 'executable', width: 120 },
  { title: '适用范围 / 医生端', key: 'visibility', width: 230 },
  ...(isCodingMode.value ? [] : [{ title: '操作', key: 'operation', width: 90 }]),
])

const rowSelection = computed<TableProps['rowSelection']>(() => ({
  selectedRowKeys: selectedRowKeys.value,
  getCheckboxProps: (record: QualityPointRow) => ({
    disabled: record.draftState === 'deleted',
  }),
  onChange: (keys: Array<string | number>) => {
    selectedRowKeys.value = keys.map((key) => String(key))
  },
}))

const paginationConfig = reactive({
  pageSize: 20,
  showSizeChanger: true,
  showQuickJumper: true,
  showTotal: (total: number) => `共 ${total} 条`,
  pageSizeOptions: ['10', '20', '50', '100'],
})

function asRow(record: Record<string, unknown>): QualityPointRow {
  return record as unknown as QualityPointRow
}

async function load() {
  const key = ruleSetKey.value
  const actor = actorKey.value
  const context = contextGeneration
  const request = ++loadGeneration
  if (!actor) return
  loading.value = true
  loadError.value = ''
  selectedRowKeys.value = []
  try {
    const listResult = await listRuleSetVersions(key)
    if (!contextCurrent(context, actor, key) || request !== loadGeneration) return
    if (!listResult.success || !listResult.data) {
      versionList.value = null
      currentDetail.value = null
      baseDetail.value = null
      loadError.value = listResult.message || '读取规则集版本失败'
      return
    }
    const list = listResult.data
    const detailResult = await getRuleSetVersion(key, list.current_version)
    const draftBase = list.draft?.base_version
    const baseResult =
      draftBase && draftBase !== list.current_version
        ? await getRuleSetVersion(key, draftBase)
        : null
    if (!contextCurrent(context, actor, key) || request !== loadGeneration) return
    versionList.value = list
    currentDetail.value = detailResult.success ? (detailResult.data ?? null) : null
    baseDetail.value = baseResult?.success ? (baseResult.data ?? null) : null
    if (!detailResult.success) loadError.value = detailResult.message || '读取当前版本详情失败'
  } finally {
    if (contextCurrent(context, actor, key) && request === loadGeneration) loading.value = false
  }
}

async function downloadCurrentVersion() {
  const version = versionList.value?.current_version
  if (!version || exportingCurrent.value) return
  exportingCurrent.value = true
  const result = await exportRuleSetVersion(ruleSetKey.value, version)
  exportingCurrent.value = false
  if (!result.success || !result.data) {
    message.error(result.message || '导出当前规则集版本失败')
    return
  }
  downloadBlob(result.data, `${ruleSetKey.value}-${version}.xlsx`)
}

/** 批量修改质控点状态：只写草稿；无草稿时先以当前版本为基础创建草稿。 */
async function applyBatch(
  state: RuleSetEntryState,
  frozenRuleIds: readonly string[] = selectedRowKeys.value,
) {
  const list = versionList.value
  const key = ruleSetKey.value
  const actor = actorKey.value
  const context = contextGeneration
  const ruleIds = [...frozenRuleIds]
  if (!actor || !editable.value || !list || ruleIds.length === 0) return
  const currentRows = new Map(rows.value.map((row) => [row.rule_id, row]))
  if (ruleIds.some((ruleId) => currentRows.get(ruleId)?.draftState === 'deleted')) {
    message.warning('已在草稿中删除的质控点不能恢复或再次修改')
    return
  }
  if (
    state === 'deleted' &&
    ruleIds.some((ruleId) => {
      const current = currentRows.get(ruleId)?.state
      return current !== 'paused' && current !== 'offline'
    })
  ) {
    message.warning('只能删除当前版本中已暂停或已下线的质控点；当前在线规则请先下线并发布')
    return
  }
  if (state === 'active' && enableBlockedReason.value) {
    message.warning(enableBlockedReason.value)
    return
  }
  const request = ++mutationGeneration
  saving.value = true
  try {
    let working = list.draft
    if (!working) {
      const created = await createRuleSetDraft(key, { base_version: list.current_version })
      if (!contextCurrent(context, actor, key) || request !== mutationGeneration) return
      if (!created.success || !created.data) {
        message.warning(describeFailure(created, '创建草稿失败'))
        if (needsRefresh(created)) await load()
        return
      }
      working = created.data
      versionList.value = { ...list, draft: working }
    }
    const { entries, changed } = applyStateToEntries(working.entries, ruleIds, state)
    if (changed === 0) {
      message.info(`所选质控点在草稿中已是“${ENTRY_STATE_LABEL[state]}”`)
      return
    }
    const updated = await updateRuleSetDraft(key, { version_seq: working.version_seq, entries })
    if (!contextCurrent(context, actor, key) || request !== mutationGeneration) return
    if (!updated.success || !updated.data) {
      message.warning(describeFailure(updated, '保存草稿失败'))
      if (needsRefresh(updated) || updated.status === 404) await load()
      return
    }
    versionList.value = { ...list, draft: updated.data }
    selectedRowKeys.value = []
    message.success(
      `已写入草稿：${changed} 个质控点改为“${ENTRY_STATE_LABEL[state]}”，发布新版本后生效`,
    )
  } finally {
    if (contextCurrent(context, actor, key) && request === mutationGeneration) saving.value = false
  }
}

function handleDeleteConfirmOpen(open: boolean) {
  if (open) {
    deleteConfirmContext.value = {
      ruleSetKey: ruleSetKey.value,
      actorKey: actorKey.value,
      ruleIds: [...selectedRowKeys.value],
    }
  }
}

function confirmDelete() {
  const frozen = deleteConfirmContext.value
  deleteConfirmContext.value = null
  if (!frozen || frozen.ruleSetKey !== ruleSetKey.value || frozen.actorKey !== actorKey.value) {
    message.warning('操作上下文已变化，请重新选择质控点')
    return
  }
  void applyBatch('deleted', frozen.ruleIds)
}

function openBuiltinDetail(row: QualityPointRow) {
  if (isCodingMode.value) return
  builtinDetail.value = row
  coreClassification.value =
    row.coreSystemIds === null ? 'unknown' : row.coreSystemIds.length ? 'selected' : 'none'
  coreIds.value = [...(row.coreSystemIds ?? [])]
  const context = contextGeneration
  const actor = actorKey.value
  const key = ruleSetKey.value
  void (async () => {
    try {
      const result = await getMedicalCoreSystems()
      if (!contextCurrent(context, actor, key)) return
      coreSystems.value = result.data?.items ?? []
      coreCatalogError.value = result.success ? '' : result.message || '核心制度字典不可用'
    } catch {
      if (contextCurrent(context, actor, key)) coreCatalogError.value = '核心制度字典不可用'
    }
  })()
  scopeTargetIds.value = [row.rule_id]
  scopeMode.value = row.departmentScopeMode ?? ''
  scopeRefsText.value = (row.departmentRefs ?? [])
    .map((ref) => `${ref.institute_id}|${ref.department_name}`)
    .join('\n')
  doctorVisibleChoice.value =
    row.doctorVisible === true ? 'visible' : row.doctorVisible === false ? 'hidden' : ''
}

function openSelectedApplicability() {
  const target = rows.value.find((row) => selectedRowKeys.value.includes(row.rule_id))
  if (!target) return
  openBuiltinDetail(target)
  scopeTargetIds.value = [...selectedRowKeys.value]
}

function scopeLabel(row: QualityPointRow) {
  if (row.departmentScopeMode === 'all') return '全部科室'
  if (row.departmentScopeMode === 'selected')
    return `指定科室（${row.departmentRefs?.length ?? 0}）`
  return '科室范围未配置'
}

function doctorVisibilityLabel(value: boolean | null) {
  return value === true ? '医生端开放' : value === false ? '医生端不开放' : '医生端未配置'
}

function parseDepartmentRefs() {
  if (scopeMode.value === 'all') return []
  const refs = scopeRefsText.value
    .split(/\r?\n/u)
    .filter((line) => line.trim())
    .map((line) => {
      const [instituteId, departmentName, ...extra] = line.split('|').map((part) => part.trim())
      if (!instituteId || !departmentName || extra.length)
        throw new Error('指定科室格式应为“医院ID|科室名”，每行一组')
      return { institute_id: instituteId, department_name: departmentName }
    })
  if (!refs.length) throw new Error('指定科室模式至少需要一组医院与科室')
  return refs
}

async function saveApplicability(coreOnly = false) {
  const row = builtinDetail.value
  const list = versionList.value
  if (!row || !list || !editable.value) return
  if (!coreOnly && (!scopeMode.value || !doctorVisibleChoice.value)) {
    message.warning('请明确选择科室范围和医生端开关')
    return
  }
  const configuredScopeMode = scopeMode.value || undefined
  let departmentRefs: Array<{ institute_id: string; department_name: string }>
  try {
    departmentRefs = coreOnly ? [] : parseDepartmentRefs()
  } catch (error) {
    message.warning(error instanceof Error ? error.message : '科室范围格式无效')
    return
  }
  const key = ruleSetKey.value
  if (
    coreOnly &&
    coreClassification.value === 'selected' &&
    (!coreIds.value.length || coreCatalogError.value)
  ) {
    message.warning('请选择可信字典中的核心制度')
    return
  }
  const selectedCoreIds =
    coreClassification.value === 'unknown'
      ? null
      : coreClassification.value === 'none'
        ? []
        : [...coreIds.value]
  const actor = actorKey.value
  const context = contextGeneration
  const request = ++mutationGeneration
  saving.value = true
  try {
    let working = list.draft
    if (!working) {
      const created = await createRuleSetDraft(key, { base_version: list.current_version })
      if (!contextCurrent(context, actor, key) || request !== mutationGeneration) return
      if (!created.success || !created.data) {
        message.warning(describeFailure(created, '创建草稿失败'))
        return
      }
      working = created.data
    }
    const targets = new Set(scopeTargetIds.value.length ? scopeTargetIds.value : [row.rule_id])
    const entries = working.entries.map((entry) =>
      toRuleSetEntry(
        targets.has(entry.rule_id)
          ? coreOnly
            ? { ...entry, core_system_ids: selectedCoreIds }
            : {
                ...entry,
                department_scope_mode: configuredScopeMode,
                department_refs: departmentRefs,
                doctor_visible: doctorVisibleChoice.value === 'visible',
              }
          : entry,
      ),
    )
    const updated = await updateRuleSetDraft(key, { version_seq: working.version_seq, entries })
    if (!contextCurrent(context, actor, key) || request !== mutationGeneration) return
    if (!updated.success || !updated.data) {
      message.warning(describeFailure(updated, '保存适用配置失败'))
      if (needsRefresh(updated) || updated.status === 404) await load()
      return
    }
    versionList.value = { ...list, draft: updated.data }
    builtinDetail.value = null
    message.success(
      `已为 ${targets.size} 个质控点保存${coreOnly ? '核心制度归属' : '适用范围与医生端开关'}，发布新版本后生效`,
    )
  } finally {
    if (contextCurrent(context, actor, key) && request === mutationGeneration) saving.value = false
  }
}

function handleCreateNew() {
  router.push('/dashboard/quality-control/create')
}

function handleSearch() {
  appliedKeyword.value = searchKeyword.value
}

function contextCurrent(generation: number, actor: string, key: string) {
  return (
    !disposed &&
    generation === contextGeneration &&
    actor === actorKey.value &&
    key === ruleSetKey.value
  )
}

function invalidateContext() {
  contextGeneration += 1
  loadGeneration += 1
  mutationGeneration += 1
  loading.value = false
  saving.value = false
  selectedRowKeys.value = []
  deleteConfirmContext.value = null
  builtinDetail.value = null
  scopeTargetIds.value = []
  versionList.value = null
  currentDetail.value = null
  baseDetail.value = null
  loadError.value = ''
}

watch(ruleSetKey, () => {
  invalidateContext()
  if (actorKey.value) void load()
})

watch(isCodingMode, (coding) => {
  const nextKey = coding ? CODING_QC_RULE_SET_KEY : LX0609_RULE_SET_KEY
  if (ruleSetKey.value !== nextKey) ruleSetKey.value = nextKey
})

watch(actorKey, () => {
  invalidateContext()
  if (actorKey.value) void load()
})

watch(activeTab, () => {
  selectedRowKeys.value = []
})

onMounted(() => {
  if (actorKey.value) void load()
})

onBeforeUnmount(() => {
  disposed = true
  invalidateContext()
})
</script>

<style scoped lang="less">
.quality-control-point-management {
  padding: 24px;
  background: #f5f5f5;
  min-height: 100vh;

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;

    .page-title {
      font-size: 20px;
      font-weight: 600;
      color: #333333;
      margin: 0;
    }

    .rule-set-bar {
      display: flex;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;

      .bar-label {
        color: #666666;
      }

      .rule-set-select {
        width: 200px;
      }

      .current-version {
        color: #666666;

        strong {
          color: #333333;
        }
      }
    }
  }

  .page-alert {
    margin-bottom: 16px;
  }

  .action-btn {
    height: 32px;
    padding: 0 16px;
    font-size: 14px;
    border-radius: 6px;
    border-color: #d9d9d9;
    color: #666666;

    &:hover {
      border-color: #2b6cf6;
      color: #2b6cf6;
    }
  }

  .tabs-container {
    background: #ffffff;
    border-radius: 8px 8px 0 0;

    :deep(.ant-tabs) {
      margin: 0;

      .ant-tabs-nav {
        margin: 0;
        padding: 0 24px;

        .ant-tabs-tab {
          padding: 16px 24px;
          font-size: 14px;
          font-weight: 500;

          &.ant-tabs-tab-active {
            color: #2b6cf6;
          }
        }
      }

      .ant-tabs-content-holder {
        display: none;
      }
    }
  }

  .action-bar {
    background: #ffffff;
    padding: 16px 24px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-top: 1px solid #f0f0f0;

    .batch-actions {
      display: flex;
      gap: 8px;
      align-items: center;
      flex-wrap: wrap;

      .batch-btn {
        height: 32px;
        padding: 0 16px;
        font-size: 14px;
        border-radius: 6px;

        &:disabled {
          opacity: 0.5;
        }
      }

      .batch-hint {
        font-size: 12px;
        color: #999999;
      }

      .create-btn {
        height: 32px;
        padding: 0 16px;
        font-size: 14px;
        border-radius: 6px;
        background: #2b6cf6;
        border-color: #2b6cf6;
      }
    }

    .search-area {
      display: flex;
      gap: 8px;
      align-items: center;

      .search-type-select {
        width: 120px;

        :deep(.ant-select-selector) {
          height: 32px;
          border-radius: 6px;
        }
      }

      .search-input {
        width: 240px;
      }
    }
  }

  .table-container {
    background: #ffffff;
    border-radius: 0 0 8px 8px;
    overflow: hidden;

    .quality-point-table {
      :deep(.ant-table-thead > tr > th) {
        background: #fafafa;
        font-weight: 500;
        color: #333333;
        border-bottom: 1px solid #f0f0f0;
      }

      :deep(.ant-table-tbody > tr > td) {
        border-bottom: 1px solid #f0f0f0;
        padding: 12px 16px;
      }

      :deep(.ant-table-tbody > tr:hover > td) {
        background: #f5f5f5;
      }

      .name-cell {
        .name-text {
          font-size: 14px;
          color: #333333;
          margin-bottom: 4px;
        }

        .source-text {
          font-size: 12px;
          color: #999999;
        }
      }

      .state-cell {
        display: flex;
        flex-wrap: wrap;
        gap: 4px;
      }

      .unknown-text {
        color: #999999;
      }
    }
  }
}

.applicability-editor {
  display: grid;
  gap: 12px;
  margin-top: 20px;
  padding-top: 18px;
  border-top: 1px solid #e5e7eb;

  label {
    color: #334155;
    font-size: 13px;
    font-weight: 600;
  }

  > button {
    justify-self: start;
    margin-top: 4px;
  }
}

.quality-control-point-management--embedded {
  min-height: auto;
  padding: 0;
  background: transparent;
}

.coding-rule-set-label {
  color: #1d1d1f;
  font-size: 14px;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .quality-control-point-management {
    padding: 16px;

    .action-bar {
      flex-direction: column;
      gap: 16px;
      align-items: stretch;

      .search-area {
        justify-content: stretch;

        .search-type-select {
          flex: 1;
        }

        .search-input {
          flex: 2;
        }
      }
    }
  }
}

.builtin-detail {
  display: grid;
  grid-template-columns: 96px minmax(0, 1fr);
  gap: 10px 12px;
  margin: 0;

  dt {
    color: rgba(0, 0, 0, 0.45);
  }

  dd {
    margin: 0;
    overflow-wrap: anywhere;
  }
}

.builtin-detail-note {
  margin: 18px 0 0;
  padding: 10px 12px;
  border-radius: 6px;
  background: #f7f8fa;
  color: rgba(0, 0, 0, 0.6);
  font-size: 13px;
}
</style>
