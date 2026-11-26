<template>
  <div class="cdm-data-view">
    <header class="cdm-page-header">
      <div>
        <span class="cdm-eyebrow">数据与配置 · 数据中心</span>
        <h1>数据管理</h1>
        <p>查看当前临床来源的病案资料；数据读取不代表材料完整性或质控验收通过。</p>
      </div>
      <a-button
        class="cdm-refresh-btn"
        type="primary"
        :loading="pageLoading"
        @click="loadData"
      >
        刷新数据
      </a-button>
    </header>

    <!-- 顶部概览卡片 -->
    <div class="stats-row">
      <div class="stat-card stat-records">
        <div class="stat-icon">
          <FileTextOutlined />
        </div>
        <div class="stat-body">
          <div class="stat-value">
            {{ connected ? (stats.total_records ?? '未统计') : '—' }}
          </div>
          <div class="stat-label">
            病案总数
          </div>
        </div>
      </div>
      <div class="stat-card stat-diag">
        <div class="stat-icon">
          <MedicineBoxOutlined />
        </div>
        <div class="stat-body">
          <div class="stat-value">
            {{ totalDiagnoses }}
          </div>
          <div class="stat-label">
            诊断条目
          </div>
        </div>
      </div>
      <div class="stat-card stat-surgery">
        <div class="stat-icon">
          <ExperimentOutlined />
        </div>
        <div class="stat-body">
          <div class="stat-value">
            {{ totalSurgeries }}
          </div>
          <div class="stat-label">
            手术记录
          </div>
        </div>
      </div>
      <div class="stat-card stat-dept">
        <div class="stat-icon">
          <ApartmentOutlined />
        </div>
        <div class="stat-body">
          <div class="stat-value">
            {{ departments.length }}
          </div>
          <div class="stat-label">
            覆盖科室
          </div>
        </div>
      </div>
      <div class="stat-card stat-tables">
        <div class="stat-icon">
          <DatabaseOutlined />
        </div>
        <div class="stat-body">
          <div class="stat-value">
            {{ !canShowTableBrowser ? '未提供' : (schema.total_tables ?? '未统计') }}
          </div>
          <div class="stat-label">
            CDM 数据表
          </div>
        </div>
      </div>
    </div>

    <!-- 数据源状态 -->
    <div class="datasource-bar">
      <div class="ds-left">
        <span
          class="ds-dot"
          :class="{ 'ds-active': connected }"
        />
        <span class="ds-text">数据源：<strong>{{ sourceName }}</strong></span>
        <a-tag :color="connected ? 'green' : 'orange'">
          {{ connected ? '读取成功' : '尚未就绪' }}
        </a-tag>
      </div>
      <div class="ds-right">
        <a-tag>只读浏览</a-tag>
        <span class="ds-path">{{ dbPath }}</span>
      </div>
    </div>

    <a-alert
      v-if="loadError"
      type="error"
      :message="loadError"
      show-icon
    />
    <a-alert
      v-if="detailError"
      type="warning"
      :message="detailError"
      show-icon
    />
    <!-- 主体：左表结构/数据 + 右数据预览 -->
    <div class="main-content">
      <!-- 左侧：表浏览面板 -->
      <div
        v-if="canShowTableBrowser"
        class="schema-panel"
        data-testid="cdm-schema-panel"
      >
        <div class="panel-header">
          <TableOutlined />
          <span>表浏览</span>
          <!-- 结构/数据 切换 -->
          <div class="view-toggle">
            <div
              class="toggle-btn"
              :class="{ active: leftView === 'schema' }"
              role="button"
              tabindex="0"
              :aria-pressed="leftView === 'schema'"
              @click="leftView = 'schema'"
              @keydown.enter.prevent="leftView = 'schema'"
              @keydown.space.prevent="leftView = 'schema'"
            >
              <ProfileOutlined /> 结构
            </div>
            <div
              class="toggle-btn"
              :class="{ active: leftView === 'data' }"
              role="button"
              tabindex="0"
              :aria-pressed="leftView === 'data'"
              @click="switchToDataView()"
              @keydown.enter.prevent="switchToDataView()"
              @keydown.space.prevent="switchToDataView()"
            >
              <OrderedListOutlined /> 数据
            </div>
          </div>
        </div>

        <!-- 表名 Tab 列表 -->
        <div class="table-tabs">
          <div
            v-for="table in schema.tables || []"
            :key="table.name"
            class="table-tab"
            :class="{ active: selectedTable === table.name }"
            role="button"
            tabindex="0"
            :aria-pressed="selectedTable === table.name"
            @click="selectTable(table.name)"
            @keydown.enter.prevent="selectTable(table.name)"
            @keydown.space.prevent="selectTable(table.name)"
          >
            <span class="tab-label">{{ table.label }}</span>
            <span class="tab-name">{{ table.name }}</span>
            <a-badge
              :count="table.column_count"
              :number-style="{
                backgroundColor: selectedTable === table.name ? '#0a6cff' : '#59595e',
                fontSize: '11px',
              }"
            />
          </div>
        </div>

        <!-- ===== 结构视图 ===== -->
        <div
          v-if="leftView === 'schema' && currentTableColumns.length"
          class="columns-list"
        >
          <div class="col-header-row">
            <span class="col-h col-h-name">字段名</span>
            <span class="col-h col-h-type">类型</span>
            <span class="col-h col-h-comment">说明</span>
          </div>
          <div
            v-for="col in currentTableColumns"
            :key="col.name"
            class="col-row"
            :class="{ 'col-pk': col.primary_key }"
          >
            <span class="col-name">
              <span
                v-if="col.primary_key"
                class="pk-badge"
              >PK</span>
              {{ col.name }}
            </span>
            <span class="col-type">{{ col.type }}</span>
            <span class="col-comment">{{ col.comment || '—' }}</span>
          </div>
        </div>
        <div
          v-else-if="leftView === 'schema' && !pageLoading"
          class="data-empty"
        >
          暂无表结构信息
        </div>

        <!-- ===== 数据视图 ===== -->
        <div
          v-if="leftView === 'data'"
          class="table-data-view"
        >
          <a-alert
            v-if="tableDataError"
            type="error"
            :message="tableDataError"
            show-icon
          />
          <div
            v-if="tableDataLoading"
            class="data-loading"
          >
            <a-spin /> 加载中...
          </div>
          <div
            v-else-if="tableData.items.length === 0 && !tableDataError"
            class="data-empty"
          >
            暂无数据
          </div>
          <div
            v-else-if="tableData.items.length > 0"
            class="data-table-wrap"
          >
            <div class="data-table-info data-table-toolbar">
              <span>共 <strong>{{ tableData.total }}</strong> 条 · 第 {{ tableData.page }} / {{ tableDataTotalPages }} 页</span>
              <div class="table-pagination-actions">
                <a-button
                  size="small"
                  data-testid="table-page-prev"
                  :disabled="tableDataLoading || tableData.page <= 1"
                  @click="loadTableData(selectedTable, tableData.page - 1)"
                >
                  上一页
                </a-button>
                <a-button
                  size="small"
                  data-testid="table-page-next"
                  :disabled="tableDataLoading || tableData.page >= tableDataTotalPages"
                  @click="loadTableData(selectedTable, tableData.page + 1)"
                >
                  下一页
                </a-button>
              </div>
            </div>
            <div class="data-table-scroll">
              <table class="data-table">
                <thead>
                  <tr>
                    <th
                      v-for="col in tableData.columns"
                      :key="col"
                      class="data-th"
                    >
                      {{ col }}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="(row, idx) in tableData.items"
                    :key="idx"
                    class="data-tr"
                  >
                    <td
                      v-for="col in tableData.columns"
                      :key="col"
                      class="data-td"
                    >
                      <span
                        class="cell-value"
                        :title="String(row[col] ?? '')"
                      >{{
                        formatCell(row[col])
                      }}</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      <div
        v-else
        class="schema-panel"
        data-testid="cdm-readonly-panel"
      >
        <div class="panel-header">
          <TableOutlined />{{ independent ? '东华CDM只读浏览' : '只读病例预览' }}
        </div>
        <div class="data-empty">
          {{
            independent
              ? '当前来源不开放整表结构和原始表浏览。请在右侧选择病例查看首页资料；完整文书请使用病历池的“查看病历”。'
              : '当前账号仅支持只读病例预览，不开放整表结构和原始表浏览。请在右侧选择病例查看首页资料。'
          }}
        </div>
      </div>
      <!-- 右侧：数据预览 -->
      <div class="data-panel">
        <div class="panel-header">
          <UnorderedListOutlined />
          <span>数据预览</span>
          <a-tag
            v-if="patients.length"
            color="blue"
          >
            {{ patients.length }} 条记录
          </a-tag>
        </div>

        <div
          v-if="pageLoading"
          class="data-loading"
          data-testid="cdm-page-loading"
        >
          <a-spin /> 正在加载病例数据...
        </div>

        <div
          v-else-if="!loadError && patients.length === 0"
          class="data-empty"
          data-testid="cdm-patients-empty"
        >
          暂无可预览病例数据
        </div>

        <!-- 病例卡片 -->
        <div
          v-else
          class="patient-cards"
        >
          <div
            v-for="pt in patients"
            :key="patientKey(pt)"
            class="patient-card"
            :class="{ active: selectedPatient && patientKey(selectedPatient) === patientKey(pt) }"
            role="button"
            tabindex="0"
            :aria-pressed="Boolean(selectedPatient && patientKey(selectedPatient) === patientKey(pt))"
            @click="selectPatient(pt)"
            @keydown.enter.self.prevent="selectPatient(pt)"
            @keydown.space.self.prevent="selectPatient(pt)"
          >
            <div class="pt-top">
              <span class="pt-name">{{ pt.name }}</span>
              <a-tag
                :color="pt.sex === '男' ? 'blue' : 'pink'"
                size="small"
              >
                {{ pt.sex }}
              </a-tag>
              <span class="pt-age">{{ pt.age }}</span>
            </div>
            <div class="pt-info">
              <span class="pt-dept">{{ pt.discharge_dept_name }}</span>
              <span class="pt-divider">|</span>
              <span class="pt-mr">{{ pt.mr_no }}</span>
            </div>
            <div class="pt-bottom">
              <span class="pt-dates">
                {{ formatDate(pt.admission_datetime) }} → {{ formatDate(pt.discharge_datetime) }}
                <span class="pt-days">{{ pt.hospital_duration }}天</span>
              </span>
              <a-button
                v-if="canShowTableBrowser"
                size="small"
                type="link"
                class="pt-view-btn"
                data-testid="pt-table-data-btn"
                @click.stop="openRecordModal(pt)"
              >
                <DatabaseOutlined /> 表数据
              </a-button>
            </div>
          </div>
        </div>

        <div
          v-if="detailLoading"
          class="data-loading"
          data-testid="cdm-detail-loading"
        >
          <a-spin /> 正在加载病案详情...
        </div>

        <!-- 选中病例详情 -->
        <div
          v-if="selectedDetail"
          class="detail-panel"
        >
          <div class="detail-header">
            <h3>{{ selectedDetail.name }} — 病案详情</h3>
          </div>
          <!-- 诊断 -->
          <div class="detail-section">
            <div class="section-title">
              <MedicineBoxOutlined /> 诊断 ({{ selectedDetail.diagnoses?.length || 0 }})
            </div>
            <div class="diag-list">
              <div
                v-for="d in selectedDetail.diagnoses"
                :key="d.diagnosis_id"
                class="diag-item"
              >
                <a-tag
                  :color="d.diagnosis_type?.includes('主要') ? 'red' : 'orange'"
                  size="small"
                >
                  {{ d.diagnosis_type?.includes('主要') ? '主诊断' : '其他' }}
                </a-tag>
                <span class="diag-name">{{ d.diagnosis_name }}</span>
                <code class="diag-code">{{ d.diagnosis_code }}</code>
              </div>
            </div>
          </div>
          <!-- 手术 -->
          <div
            v-if="selectedDetail.surgeries?.length"
            class="detail-section"
          >
            <div class="section-title">
              <ExperimentOutlined /> 手术 ({{ selectedDetail.surgeries.length }})
            </div>
            <div class="diag-list">
              <div
                v-for="s in selectedDetail.surgeries"
                :key="s.surgery_id"
                class="diag-item"
              >
                <a-tag
                  color="blue"
                  size="small"
                >
                  {{ s.surgical_level || '手术' }}
                </a-tag>
                <span class="diag-name">{{ s.surgery_name }}</span>
                <code class="diag-code">{{ s.surgery_code }}</code>
              </div>
            </div>
          </div>
          <!-- 费用 -->
          <div
            v-if="selectedDetail.cost"
            class="detail-section"
          >
            <div class="section-title">
              <DollarOutlined /> 费用
            </div>
            <div class="cost-grid">
              <div class="cost-total">
                <span>总费用</span>
                <strong>¥{{ selectedDetail.cost.total_cost }}</strong>
              </div>
              <div
                v-for="(val, key) in costItems"
                :key="key"
                class="cost-item"
              >
                <span>{{ key }}</span>
                <span>¥{{ val }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ===== 病历表数据弹窗 ===== -->
    <a-modal
      v-model:open="recordModalVisible"
      :title="recordModalTitle"
      width="90%"
      :footer="null"
      class="record-modal"
      :body-style="{ padding: '16px', maxHeight: '75vh', overflow: 'auto' }"
    >
      <div
        v-if="recordModalLoading"
        class="modal-loading"
      >
        <a-spin size="large" />
        <span>加载表数据中...</span>
      </div>
      <div v-else>
        <a-alert
          v-if="recordModalError"
          type="warning"
          :message="recordModalError"
          show-icon
          style="margin-bottom: 12px"
        />
        <!-- 表 Tab 切换 -->
        <a-tabs
          v-model:active-key="recordActiveTab"
          size="small"
        >
          <a-tab-pane
            v-for="tab in recordTabs"
            :key="tab.name"
            :tab="`${tab.label} (${tab.error ? '失败' : tab.count})`"
          >
            <div
              v-if="tab.error"
              class="data-empty"
            >
              {{ tab.error }}
            </div>
            <div
              v-else-if="tab.count === 0"
              class="data-empty"
            >
              此表中无该患者数据
            </div>
            <div
              v-else
              class="data-table-scroll modal-table-scroll"
            >
              <table class="data-table">
                <thead>
                  <tr>
                    <th
                      v-for="col in tab.columns"
                      :key="col"
                      class="data-th"
                    >
                      {{ col }}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="(row, idx) in tab.items"
                    :key="idx"
                    class="data-tr"
                  >
                    <td
                      v-for="col in tab.columns"
                      :key="col"
                      class="data-td"
                    >
                      <span
                        class="cell-value"
                        :title="String(row[col] ?? '')"
                      >{{
                        formatCell(row[col])
                      }}</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </a-tab-pane>
        </a-tabs>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { serializeCaseRecordKey } from './utils/caseRecordKey'
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { clinicalSourcesApi } from '@/api/clinicalSources'
import { useAuthStore } from '@/stores/auth'
import { getAccessToken } from '@/utils/auth-token'
import {
  FileTextOutlined,
  MedicineBoxOutlined,
  ExperimentOutlined,
  ApartmentOutlined,
  DatabaseOutlined,
  TableOutlined,
  UnorderedListOutlined,
  DollarOutlined,
  ProfileOutlined,
  OrderedListOutlined,
} from '@ant-design/icons-vue'

const API_BASE = '/api/medical-records'
const TABLE_DATA_ROLES = new Set(['admin', 'sync_admin', 'super_admin'])
const TABLE_PAGE_SIZE = 50

function tryUseAuthStore() {
  try {
    return useAuthStore()
  } catch {
    return null
  }
}

const authStore = tryUseAuthStore()

function isAbortError(err: unknown): boolean {
  return Boolean(err && typeof err === 'object' && (err as { name?: string }).name === 'AbortError')
}

function getAuthHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const token = getAccessToken()
  const headers: Record<string, string> = { ...extra }
  if (token && !headers.Authorization) {
    headers.Authorization = `Bearer ${token}`
  }
  return headers
}

function getSourceHeaders(): Record<string, string> {
  return getAuthHeaders({
    'X-Clinical-Source': independent.value ? 'independent_cdm' : 'legacy_pg',
  })
}

// ===== State =====
const stats = ref<any>({})
const schema = ref<any>({ tables: [], total_tables: 0 })
const patients = ref<any[]>([])
const departments = ref<string[]>([])
const selectedTable = ref('mr')
const selectedPatient = ref<any>(null)
const selectedDetail = ref<any>(null)
const dbPath = ref('')
const independent = ref(true)
const tableAccessDenied = ref(false)
const sourceName = ref('尚未确认')
const connected = ref(false)
const pageLoading = ref(false)
const detailLoading = ref(false)
const loadError = ref('')
const detailError = ref('')
const tableDataError = ref('')
const recordModalError = ref('')

let detailSequence = 0
let loadSequence = 0
let tableDataSequence = 0
let modalSequence = 0
let loadAbortController: AbortController | null = null
let detailAbortController: AbortController | null = null
let tableDataAbortController: AbortController | null = null
let modalAbortController: AbortController | null = null

const canBrowseTables = computed(() => {
  const roles = authStore?.userRoles ?? []
  return roles.some((role) =>
    TABLE_DATA_ROLES.has(
      String(role || '')
        .trim()
        .toLowerCase(),
    ),
  )
})
const canShowTableBrowser = computed(
  () => !independent.value && canBrowseTables.value && !tableAccessDenied.value,
)

function patientKey(pt: Record<string, unknown>) {
  return serializeCaseRecordKey(pt.institute_id, pt.patient_id, pt.visit_id)
}

async function readJson(url: string, signal?: AbortSignal) {
  const resp = await fetch(url, {
    headers: getSourceHeaders(),
    signal,
  })
  if (!resp.ok) {
    const err = new Error(`数据读取失败（HTTP ${resp.status}）`) as Error & { status?: number }
    err.status = resp.status
    throw err
  }
  const body = await resp.json()
  if (body?.success === false) throw new Error('数据接口未返回有效结果')
  return body?.data ?? body
}

// 左侧面板视图：schema / data
const leftView = ref<'schema' | 'data'>('schema')
const tableData = ref<any>({ items: [], columns: [], total: 0, page: 1, page_size: TABLE_PAGE_SIZE })
const tableDataLoading = ref(false)
const tableDataTotalPages = computed(() => {
  const total = Number(tableData.value?.total || 0)
  const pageSize = Number(tableData.value?.page_size || TABLE_PAGE_SIZE) || TABLE_PAGE_SIZE
  return Math.max(1, Math.ceil(total / pageSize))
})

// 病历弹窗
const recordModalVisible = ref(false)
const recordModalTitle = ref('')
const recordModalLoading = ref(false)
const recordActiveTab = ref('mr')
const recordTabs = ref<any[]>([])

// ===== Computed =====
const totalDiagnoses = computed(() => '未统计')
const totalSurgeries = computed(() => '未统计')
const currentTableColumns = computed(() => {
  const table = (schema.value.tables || []).find((t: any) => t.name === selectedTable.value)
  return table ? table.columns : []
})
const costItems = computed(() => {
  if (!selectedDetail.value?.cost) return {}
  const cost = selectedDetail.value.cost
  const labels: Record<string, string> = {
    western_medicine_fee: '西药费',
    surgery_treatment_fee: '手术治疗费',
    laboratory_diagnostic_fee: '检验费',
    imaging_diagnostic_fee: '影像检查费',
    nursing_care_fee: '护理费',
    antibacterial_drug_fee: '抗菌药物费',
    nonsurgical_treatment_fee: '非手术治疗费',
  }
  const result: Record<string, string> = {}
  for (const [key, label] of Object.entries(labels)) {
    if (cost[key] && cost[key] !== '0.00') result[label] = cost[key]
  }
  return result
})

// ===== Methods =====
function formatDate(dt: string | null) {
  if (!dt) return '—'
  return dt.substring(0, 10)
}

function formatCell(val: any): string {
  if (val === null || val === undefined) return '—'
  const s = String(val)
  return s.length > 80 ? s.substring(0, 80) + '…' : s
}

async function selectTable(name: string) {
  selectedTable.value = name
  if (leftView.value === 'data') {
    await loadTableData(name, 1)
  }
}

function switchToDataView() {
  leftView.value = 'data'
  void loadTableData(selectedTable.value, 1)
}

async function loadTableData(tableName: string, page = 1) {
  if (!canShowTableBrowser.value || !tableName) return
  const safePage = Math.max(1, Number(page) || 1)
  const seq = ++tableDataSequence
  tableDataAbortController?.abort()
  const controller = new AbortController()
  tableDataAbortController = controller

  tableDataLoading.value = true
  tableDataError.value = ''
  try {
    const params = new URLSearchParams({
      page: String(safePage),
      page_size: String(TABLE_PAGE_SIZE),
    })
    const resp = await fetch(`${API_BASE}/table-data/${encodeURIComponent(tableName)}?${params.toString()}`, {
      headers: getSourceHeaders(),
      signal: controller.signal,
    })
    if (seq !== tableDataSequence || controller.signal.aborted) return
    if (resp.status === 403) {
      tableAccessDenied.value = true
      tableData.value = { items: [], columns: [], total: 0, page: 1, page_size: TABLE_PAGE_SIZE }
      return
    }
    if (!resp.ok) throw new Error(`表数据读取失败（HTTP ${resp.status}）`)
    const data = await resp.json()
    if (seq !== tableDataSequence || controller.signal.aborted) return
    tableData.value = {
      items: Array.isArray(data?.items) ? data.items : [],
      columns: Array.isArray(data?.columns) ? data.columns : [],
      total: Number(data?.total || 0),
      page: Number(data?.page || safePage),
      page_size: Number(data?.page_size || TABLE_PAGE_SIZE),
    }
  } catch (e) {
    if (seq !== tableDataSequence || controller.signal.aborted || isAbortError(e)) return
    tableDataError.value = '表数据读取失败，不能据此认定表为空'
    console.error('加载表数据失败', e)
  } finally {
    if (seq === tableDataSequence) {
      tableDataLoading.value = false
    }
  }
}

async function selectPatient(pt: Record<string, unknown>) {
  const sequence = ++detailSequence
  detailAbortController?.abort()
  const controller = new AbortController()
  detailAbortController = controller

  selectedPatient.value = pt
  selectedDetail.value = null
  detailError.value = ''
  const identity = [pt.institute_id, pt.patient_id, pt.visit_id]
  if (identity.some(value => value == null || String(value).trim() === '')) {
    detailLoading.value = false
    detailError.value = '病例身份不完整，无法读取详情'
    return
  }
  detailLoading.value = true
  try {
    const value = await readJson(
      `${API_BASE}/frontpage/${identity.map(value => encodeURIComponent(String(value))).join('/')}`,
      controller.signal,
    )
    if (sequence === detailSequence && !controller.signal.aborted) {
      selectedDetail.value = value
    }
  } catch (err) {
    if (sequence === detailSequence && !controller.signal.aborted && !isAbortError(err)) {
      detailError.value = '病案详情读取失败，请重试；此状态不表示没有诊断或文书。'
    }
  } finally {
    if (sequence === detailSequence) {
      detailLoading.value = false
    }
  }
}

// 病历弹窗：加载该患者在所有表中的数据
async function openRecordModal(pt: any) {
  if (!canShowTableBrowser.value) return
  const seq = ++modalSequence
  modalAbortController?.abort()
  const controller = new AbortController()
  modalAbortController = controller

  recordModalTitle.value = `${pt.name} (${pt.mr_no}) — 各表原始数据`
  recordModalVisible.value = true
  recordModalLoading.value = true
  recordModalError.value = ''
  recordActiveTab.value = 'mr'
  recordTabs.value = []

  // 需要查询的表（按顺序）
  const tablesToQuery = [
    { name: 'mr', label: '病案首页' },
    { name: 'diagnosis', label: '诊断' },
    { name: 'mr_surgery', label: '手术' },
    { name: 'mr_cost', label: '费用' },
    { name: 'admission_record', label: '入院记录' },
    { name: 'discharge_record', label: '出院记录' },
    { name: 'inpat_registration', label: '入院登记' },
    { name: 'patient_information', label: '患者信息' },
    { name: 'qc_result', label: '质控结果' },
  ]

  try {
    // 并发请求所有表
    const results = await Promise.all(
      tablesToQuery.map(async (t) => {
        const params = new URLSearchParams({
          page: '1',
          page_size: '100',
        })
        if (pt.institute_id != null && String(pt.institute_id).trim() !== '') {
          params.set('institute_id', String(pt.institute_id))
        }
        if (pt.patient_id != null && String(pt.patient_id).trim() !== '') {
          params.set('patient_id', String(pt.patient_id))
        }
        if (t.name !== 'patient_information' && pt.visit_id != null && String(pt.visit_id).trim() !== '') {
          params.set('visit_id', String(pt.visit_id))
        }

        const resp = await fetch(`${API_BASE}/table-data/${encodeURIComponent(t.name)}?${params.toString()}`, {
          headers: getSourceHeaders(),
          signal: controller.signal,
        })
        if (!resp.ok) {
          return {
            name: t.name,
            label: t.label,
            columns: [],
            items: [],
            count: 0,
            error: `读取失败（HTTP ${resp.status}）`,
          }
        }
        const data = await resp.json()
        const rawItems = Array.isArray(data?.items) ? data.items : []
        const columns = Array.isArray(data?.columns) ? data.columns : []
        // 过滤出这个患者的数据（兼容后端已按三坐标筛选与类型差异）
        const expectedPatient = pt.patient_id != null ? String(pt.patient_id).trim() : ''
        const expectedVisit = pt.visit_id != null ? String(pt.visit_id).trim() : ''
        const expectedInstitute = pt.institute_id != null ? String(pt.institute_id).trim() : ''
        const patientItems = rawItems.filter((item: any) => {
          if (expectedPatient && String(item.patient_id ?? '').trim() !== expectedPatient) {
            return false
          }
          if (expectedInstitute && item.institute_id != null && String(item.institute_id).trim() !== expectedInstitute) {
            return false
          }
          // patient_information 只有 patient_id（无 visit_id）
          if (t.name === 'patient_information') {
            return true
          }
          if (expectedVisit && String(item.visit_id ?? '').trim() !== expectedVisit) {
            return false
          }
          return true
        })
        return {
          name: t.name,
          label: t.label,
          columns,
          items: patientItems,
          count: patientItems.length,
          error: '',
        }
      }),
    )
    if (seq !== modalSequence || controller.signal.aborted) return
    recordTabs.value = results
    const failedTabs = results.filter((r) => Boolean(r.error))
    if (failedTabs.length > 0) {
      recordModalError.value = `部分原始表读取失败（${failedTabs.length}/${results.length}），其余表可正常查看`
    }
    // 自动选中第一个有数据的 tab
    const firstWithData = results.find((r) => r.count > 0)
    if (firstWithData) recordActiveTab.value = firstWithData.name
  } catch (e) {
    if (seq !== modalSequence || controller.signal.aborted || isAbortError(e)) return
    recordModalError.value = '加载病历表数据失败，请稍后重试'
    console.error('加载病历表数据失败', e)
  } finally {
    if (seq === modalSequence) {
      recordModalLoading.value = false
    }
  }
}

async function loadData() {
  const sequence = ++loadSequence
  ++detailSequence
  ++tableDataSequence
  loadAbortController?.abort()
  detailAbortController?.abort()
  tableDataAbortController?.abort()
  const controller = new AbortController()
  loadAbortController = controller

  pageLoading.value = true
  detailLoading.value = false
  connected.value = false
  tableAccessDenied.value = false
  loadError.value = ''
  detailError.value = ''
  tableDataError.value = ''
  patients.value = []
  selectedPatient.value = null
  selectedDetail.value = null
  stats.value = {}
  departments.value = []
  schema.value = { tables: [], total_tables: null }
  try {
    const options = await clinicalSourcesApi.options()
    if (sequence !== loadSequence || controller.signal.aborted) return
    const source = options.sources.find(item => item.id === options.default_source)
    if (!source?.enabled) throw new Error('当前临床来源未启用')
    independent.value = source.id === 'independent_cdm'
    sourceName.value = source.id === 'independent_cdm' ? '东华CDM（PostgreSQL）' : source.name

    const shouldLoadSchema = !independent.value && canBrowseTables.value
    const schemaPromise = shouldLoadSchema
      ? readJson(`${API_BASE}/schema`, controller.signal).catch((err: any) => {
          if (err?.status === 403) {
            tableAccessDenied.value = true
            return { tables: [], total_tables: null }
          }
          throw err
        })
      : Promise.resolve({ tables: [], total_tables: null })

    const [statsData, listData, deptsData, schemaData] = await Promise.all([
      readJson(`${API_BASE}/stats`, controller.signal),
      readJson(`${API_BASE}/list`, controller.signal),
      readJson(`${API_BASE}/departments`, controller.signal),
      schemaPromise,
    ])
    if (sequence !== loadSequence || controller.signal.aborted) return
    stats.value = statsData
    schema.value = schemaData
    if (Array.isArray(schemaData?.tables) && schemaData.tables.length > 0) {
      const exists = schemaData.tables.some((t: any) => t.name === selectedTable.value)
      if (!exists) selectedTable.value = schemaData.tables[0].name
    }
    patients.value = (listData.items || []).map((pt: Record<string, unknown>) => ({
      ...pt,
      institute_id: pt.institute_id ?? pt.instituteId,
      patient_id: pt.patient_id ?? pt.patientId,
      visit_id: pt.visit_id ?? pt.visitId ?? pt.id,
      admission_datetime: pt.admission_datetime ?? pt.admissionDate,
      discharge_datetime: pt.discharge_datetime ?? pt.dischargeDate,
      hospital_duration: pt.hospital_duration ?? pt.days ?? '—',
    }))
    departments.value = deptsData
    connected.value = true
    pageLoading.value = false
    if (patients.value.length) await selectPatient(patients.value[0])
  } catch (error) {
    if (sequence !== loadSequence || controller.signal.aborted || isAbortError(error)) return
    loadError.value = error instanceof Error ? error.message : '数据加载失败，请重试'
  } finally {
    if (sequence === loadSequence) {
      pageLoading.value = false
    }
  }
}

onMounted(loadData)
onBeforeUnmount(() => {
  loadSequence += 1
  detailSequence += 1
  tableDataSequence += 1
  modalSequence += 1
  loadAbortController?.abort()
  detailAbortController?.abort()
  tableDataAbortController?.abort()
  modalAbortController?.abort()
})
</script>

<style scoped>
.cdm-data-view {
  padding: 24px;
  min-height: 100vh;
  background: #f5f5f7;
  color: #1d1d1f;
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
  font-feature-settings:
    'rlig' 1,
    'calt' 1;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

.cdm-page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 18px;
}

.cdm-eyebrow {
  display: block;
  margin-bottom: 6px;
  color: #0a6cff;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  line-height: 1;
}

.cdm-page-header h1 {
  margin: 0;
  color: #1d1d1f;
  font-size: 28px;
  font-weight: 700;
  line-height: 31px;
}

.cdm-page-header p {
  max-width: 760px;
  margin: 8px 0 0;
  color: var(--mq-text-secondary);
  font-size: 14px;
  font-weight: 500;
  line-height: 22px;
}

.cdm-refresh-btn {
  height: 36px;
  border-radius: 10px;
  background: #0a6cff;
  border-color: #0a6cff;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.18),
    0 5px 14px rgba(10, 108, 255, 0.18);
  font-size: 13px;
  font-weight: 600;
}

/* ===== 顶部统计 ===== */
.stats-row {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 16px;
}
.stat-card {
  min-width: 0;
  background: rgba(255, 255, 255, 0.86);
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 18px;
  padding: 18px;
  display: flex;
  align-items: center;
  gap: 14px;
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
  box-shadow:
    0 1px 4px rgba(0, 0, 0, 0.045),
    0 2px 8px rgba(0, 0, 0, 0.035);
  transition:
    border-color 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    box-shadow 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    transform 0.25s cubic-bezier(0.25, 0.1, 0.25, 1);
}
.stat-card:hover {
  border-color: rgba(0, 0, 0, 0.14);
  box-shadow:
    0 2px 12px rgba(0, 0, 0, 0.1),
    0 6px 22px rgba(0, 0, 0, 0.075);
  transform: translateY(-2px);
}
.stat-icon {
  width: 46px;
  height: 46px;
  border-radius: 15px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 21px;
  flex-shrink: 0;
  border: 1px solid rgba(10, 108, 255, 0.14);
  background: rgba(10, 108, 255, 0.07);
  color: #0a6cff;
}
.stat-records .stat-icon {
  background: rgba(10, 108, 255, 0.09);
  color: #0a6cff;
}
.stat-diag .stat-icon {
  background: rgba(10, 108, 255, 0.06);
  color: #0a6cff;
}
.stat-surgery .stat-icon {
  background: rgba(10, 108, 255, 0.06);
  color: #0a6cff;
}
.stat-dept .stat-icon {
  background: rgba(10, 108, 255, 0.06);
  color: #0a6cff;
}
.stat-tables .stat-icon {
  background: rgba(10, 108, 255, 0.06);
  color: #0a6cff;
}
.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #1d1d1f;
  line-height: 1.2;
  font-variant-numeric: tabular-nums;
}
.stat-label {
  font-size: 13px;
  color: var(--mq-text-secondary);
  font-weight: 600;
  margin-top: 2px;
}

/* ===== 数据源 ===== */
.datasource-bar {
  background: rgba(255, 255, 255, 0.86);
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 16px;
  padding: 12px 20px;
  margin-bottom: 16px;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: space-between;
  align-items: center;
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
  box-shadow:
    0 1px 4px rgba(0, 0, 0, 0.045),
    0 2px 8px rgba(0, 0, 0, 0.035);
  transition:
    border-color 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    box-shadow 0.25s cubic-bezier(0.25, 0.1, 0.25, 1);
}
.datasource-bar:hover {
  border-color: rgba(0, 0, 0, 0.14);
  box-shadow:
    0 2px 12px rgba(0, 0, 0, 0.08),
    0 6px 22px rgba(0, 0, 0, 0.06);
}
.ds-left {
  display: flex;
  align-items: center;
  gap: 8px;
}
.ds-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.ds-active {
  background: #22c55e;
  box-shadow: 0 0 6px rgba(34, 197, 94, 0.5);
}
.ds-text {
  font-size: 14px;
  color: var(--mq-text-secondary);
  font-weight: 500;
}
.ds-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.ds-path {
  font-size: 12px;
  color: var(--mq-text-tertiary);
  font-family: 'SF Mono', 'Cascadia Code', ui-monospace, monospace;
}

/* ===== 主体 ===== */
.main-content {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 420px;
  gap: 16px;
  min-height: calc(100vh - 260px);
}

/* ===== 左侧面板 ===== */
.schema-panel {
  min-width: 0;
  background: rgba(255, 255, 255, 0.86);
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 20px;
  overflow: hidden;
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
  box-shadow:
    0 1px 4px rgba(0, 0, 0, 0.045),
    0 2px 8px rgba(0, 0, 0, 0.035);
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  grid-template-rows: auto minmax(0, 1fr);
  transition:
    border-color 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    box-shadow 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    transform 0.25s cubic-bezier(0.25, 0.1, 0.25, 1);
}
.schema-panel:hover,
.data-panel:hover {
  border-color: rgba(0, 0, 0, 0.14);
  box-shadow:
    0 2px 12px rgba(0, 0, 0, 0.1),
    0 6px 22px rgba(0, 0, 0, 0.075);
  transform: translateY(-2px);
}
.panel-header {
  grid-column: 1 / -1;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  font-size: 15px;
  font-weight: 650;
  color: #1d1d1f;
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(255, 255, 255, 0.76);
}

/* 结构/数据 切换按钮 */
.view-toggle {
  margin-left: auto;
  display: flex;
  background: rgba(0, 0, 0, 0.04);
  border-radius: 8px;
  padding: 2px;
  gap: 2px;
}
.toggle-btn {
  padding: 4px 12px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  color: var(--mq-text-secondary);
  display: flex;
  align-items: center;
  gap: 4px;
  transition: all 0.2s;
}
.toggle-btn:hover {
  color: var(--mq-text-primary);
}
.toggle-btn.active {
  background: rgba(255, 255, 255, 0.92);
  color: #0a6cff;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}
.toggle-btn:focus-visible,
.table-tab:focus-visible,
.patient-card:focus-visible {
  outline: 2px solid var(--mq-brand-600);
  outline-offset: 2px;
}

.table-tabs {
  min-width: 0;
  min-height: 0;
  border-right: 1px solid rgba(0, 0, 0, 0.08);
  overflow-y: auto;
}

.columns-list,
.table-data-view {
  min-width: 0;
  min-height: 0;
  overflow: auto;
}

.table-tabs {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.table-tab {
  width: 100%;
  min-width: 0;
  padding: 9px 10px;
  border-radius: 8px;
  font-size: 12px;
  cursor: pointer;
  background: rgba(0, 0, 0, 0.025);
  border: 1px solid rgba(0, 0, 0, 0.06);
  display: flex;
  align-items: center;
  gap: 6px;
  transition: all 0.2s;
}
.table-tab:hover {
  background: rgba(10, 108, 255, 0.06);
  border-color: rgba(10, 108, 255, 0.22);
}
.table-tab.active {
  background: rgba(10, 108, 255, 0.1);
  color: #0a6cff;
  border-color: rgba(10, 108, 255, 0.24);
}
.tab-label {
  font-weight: 600;
  white-space: nowrap;
}
.tab-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--mq-text-tertiary);
  font-family: 'SF Mono', 'Cascadia Code', ui-monospace, monospace;
  font-size: 11px;
}
.table-tab.active .tab-name {
  color: var(--mq-brand-700);
}

/* 结构视图 */
.columns-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 12px;
}
.col-header-row {
  display: grid;
  grid-template-columns: 2fr 1fr 2fr;
  gap: 8px;
  padding: 8px 12px;
  font-size: 11px;
  font-weight: 700;
  color: var(--mq-text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}
.col-row {
  display: grid;
  grid-template-columns: 2fr 1fr 2fr;
  gap: 8px;
  padding: 7px 12px;
  font-size: 13px;
  border-radius: 6px;
  transition: background 0.15s;
}
.col-row:hover {
  background: rgba(0, 0, 0, 0.025);
}
.col-pk {
  background: rgba(10, 108, 255, 0.06);
}
.col-name {
  font-family: 'SF Mono', 'Cascadia Code', ui-monospace, monospace;
  color: var(--mq-text-primary);
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 6px;
}
.col-type {
  color: #0a6cff;
  font-family: 'SF Mono', 'Cascadia Code', ui-monospace, monospace;
  font-size: 12px;
}
.col-comment {
  color: var(--mq-text-secondary);
  font-size: 12px;
}
.pk-badge {
  background: #0a6cff;
  color: white;
  font-size: 9px;
  padding: 1px 5px;
  border-radius: 4px;
  font-weight: 700;
  letter-spacing: 0.5px;
}

/* ===== 数据视图（表格）===== */
.table-data-view {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.data-loading,
.data-empty {
  padding: 40px;
  text-align: center;
  color: var(--mq-text-tertiary);
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}
.data-table-info {
  padding: 8px 16px;
  font-size: 12px;
  color: var(--mq-text-secondary);
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}
.data-table-scroll {
  flex: 1;
  overflow: auto;
}
.modal-table-scroll {
  max-height: 50vh;
}
.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  table-layout: auto;
  white-space: nowrap;
}
.data-th {
  position: sticky;
  top: 0;
  z-index: 1;
  background: rgba(255, 255, 255, 0.94);
  padding: 8px 12px;
  text-align: left;
  font-weight: 700;
  color: var(--mq-text-tertiary);
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  font-family: 'SF Mono', 'Cascadia Code', ui-monospace, monospace;
  font-size: 11px;
}
.data-tr:hover {
  background: rgba(0, 0, 0, 0.025);
}
.data-tr:nth-child(even) {
  background: rgba(0, 0, 0, 0.014);
}
.data-td {
  padding: 6px 12px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.05);
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cell-value {
  color: var(--mq-text-secondary);
}
.data-table-wrap {
  display: flex;
  flex-direction: column;
  flex: 1;
  overflow: hidden;
}

/* ===== 右侧 ===== */
.data-panel {
  min-width: 0;
  background: rgba(255, 255, 255, 0.86);
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 20px;
  overflow: hidden;
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
  box-shadow:
    0 1px 4px rgba(0, 0, 0, 0.045),
    0 2px 8px rgba(0, 0, 0, 0.035);
  display: flex;
  flex-direction: column;
  transition:
    border-color 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    box-shadow 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    transform 0.25s cubic-bezier(0.25, 0.1, 0.25, 1);
}
.patient-cards {
  padding: 12px;
  display: flex;
  gap: 8px;
  overflow-x: auto;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
}
.patient-card {
  min-width: 220px;
  padding: 12px 16px;
  border-radius: 12px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.64);
  cursor: pointer;
  transition: all 0.2s;
  flex-shrink: 0;
}
.patient-card:hover {
  border-color: rgba(10, 108, 255, 0.24);
  background: rgba(255, 255, 255, 0.9);
}
.patient-card.active {
  border-color: rgba(10, 108, 255, 0.32);
  background: rgba(10, 108, 255, 0.08);
  box-shadow: 0 0 0 2px rgba(10, 108, 255, 0.1);
}
.pt-top {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}
.pt-name {
  font-weight: 700;
  font-size: 15px;
  color: #1d1d1f;
}
.pt-age {
  font-size: 12px;
  color: var(--mq-text-tertiary);
}
.pt-info {
  font-size: 12px;
  color: var(--mq-text-secondary);
  margin-bottom: 4px;
}
.pt-dept {
  font-weight: 600;
}
.pt-divider {
  color: var(--mq-text-tertiary);
  margin: 0 4px;
}
.pt-mr {
  font-family: 'SF Mono', 'Cascadia Code', ui-monospace, monospace;
}
.pt-bottom {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.pt-dates {
  font-size: 11px;
  color: var(--mq-text-tertiary);
}
.pt-days {
  background: rgba(0, 0, 0, 0.05);
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: 600;
  margin-left: 6px;
}
.pt-view-btn {
  font-size: 11px !important;
  padding: 0 4px !important;
  color: #0a6cff !important;
  font-weight: 600;
}
.pt-view-btn:hover {
  color: #0a5fd6 !important;
}

/* 详情 */
.detail-panel {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
}
.detail-header h3 {
  font-size: 16px;
  font-weight: 700;
  color: #1d1d1f;
  margin: 0 0 16px 0;
}
.detail-section {
  margin-bottom: 20px;
}
.section-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--mq-text-secondary);
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.diag-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.diag-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: rgba(0, 0, 0, 0.025);
  border-radius: 8px;
}
.diag-name {
  flex: 1;
  font-size: 14px;
  color: var(--mq-text-primary);
  font-weight: 500;
}
.diag-code {
  font-family: 'SF Mono', 'Cascadia Code', ui-monospace, monospace;
  font-size: 13px;
  color: #0a6cff;
  background: rgba(10, 108, 255, 0.08);
  padding: 2px 8px;
  border-radius: 4px;
}
.cost-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}
.cost-total {
  grid-column: 1 / -1;
  border: 1px solid rgba(10, 108, 255, 0.16);
  background: rgba(10, 108, 255, 0.08);
  color: #0a6cff;
  padding: 16px;
  border-radius: 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 14px;
}
.cost-total strong {
  font-size: 24px;
  font-weight: 700;
}
.cost-item {
  background: rgba(0, 0, 0, 0.025);
  padding: 10px 12px;
  border-radius: 8px;
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 13px;
  color: var(--mq-text-secondary);
}

/* 弹窗 */
.modal-loading {
  padding: 60px;
  text-align: center;
  color: var(--mq-text-secondary);
  font-size: 15px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

/* 响应式 */
@media (max-width: 1400px) {
  .stats-row {
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  }
  .main-content {
    grid-template-columns: minmax(0, 1fr) 360px;
  }
  .schema-panel {
    grid-template-columns: 200px minmax(0, 1fr);
  }
  .cost-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .cost-total {
    grid-column: 1 / -1;
  }
}

@media (max-width: 1200px) {
  .main-content {
    grid-template-columns: 1fr;
  }
}

/* ===== v7.1 液态玻璃覆盖（同选择器后写生效） ===== */
.cdm-data-view {
  max-width: 1440px;
  margin: 0 auto;
  padding: 8px 28px 32px 22px;
  background: transparent;
  color: var(--mq-text-primary);
  font-family: var(--mq-font-family);
}

.cdm-page-header {
  align-items: flex-end;
  margin-bottom: 20px;
  padding: 0 4px;
}

.cdm-eyebrow {
  margin-bottom: 4px;
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-13);
  font-weight: 600;
  letter-spacing: 0;
  line-height: 1.4;
}

.cdm-page-header h1 {
  font-family: var(--mq-font-display);
  font-size: var(--mq-font-title);
  letter-spacing: -0.03em;
  line-height: 1.1;
}

.cdm-page-header p {
  margin-top: 4px;
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-13);
  font-weight: 400;
}

.cdm-refresh-btn {
  height: 38px;
  padding: 0 20px;
  border: 0;
  border-radius: 999px;
  background: var(--mq-brand-gradient);
  box-shadow: var(--mq-brand-shadow);
}

.stat-card,
.datasource-bar,
.schema-panel,
.data-panel {
  border: 1px solid var(--mq-glass-border);
  border-radius: var(--mq-radius-card);
  background: var(--mq-glass-bg);
  -webkit-backdrop-filter: var(--mq-glass-blur);
  backdrop-filter: var(--mq-glass-blur);
  box-shadow: var(--mq-glass-shadow);
}

.stat-card:hover {
  border-color: var(--mq-glass-border);
  transform: none;
}

.stat-value {
  font-family: var(--mq-font-display);
  letter-spacing: -0.03em;
}

.stat-icon {
  border-radius: 12px;
}

.data-table-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
}

.table-pagination-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}
</style>
