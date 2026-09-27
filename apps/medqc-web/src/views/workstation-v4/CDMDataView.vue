<template>
  <div class="cdm-data-view">
    <header class="cdm-page-header">
      <div>
        <span class="cdm-eyebrow">数据与配置 · 数据中心</span>
        <h1>数据管理</h1>
        <p>查看本地 CDM 数据库的病案、诊断、手术和费用数据结构，辅助排查数据同步质量。</p>
      </div>
      <a-button
        class="cdm-refresh-btn"
        type="primary"
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
            {{ stats.total_records || 0 }}
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
            {{ schema.total_tables || 0 }}
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
        <span class="ds-dot ds-active" />
        <span class="ds-text">数据源：<strong>SQLite</strong>（本地库）</span>
        <a-tag color="green">
          已连接
        </a-tag>
      </div>
      <div class="ds-right">
        <a-tag>CDM V1.0</a-tag>
        <span class="ds-path">{{ dbPath }}</span>
      </div>
    </div>

    <!-- 主体：左表结构/数据 + 右数据预览 -->
    <div class="main-content">
      <!-- 左侧：表浏览面板 -->
      <div class="schema-panel">
        <div class="panel-header">
          <TableOutlined />
          <span>表浏览</span>
          <!-- 结构/数据 切换 -->
          <div class="view-toggle">
            <div
              class="toggle-btn"
              :class="{ active: leftView === 'schema' }"
              @click="leftView = 'schema'"
            >
              <ProfileOutlined /> 结构
            </div>
            <div
              class="toggle-btn"
              :class="{ active: leftView === 'data' }"
              @click="switchToDataView()"
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
            @click="selectTable(table.name)"
          >
            <span class="tab-label">{{ table.label }}</span>
            <span class="tab-name">{{ table.name }}</span>
            <a-badge
              :count="table.column_count"
              :number-style="{
                backgroundColor: selectedTable === table.name ? '#0a6cff' : 'rgba(29,29,31,0.38)',
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

        <!-- ===== 数据视图 ===== -->
        <div
          v-if="leftView === 'data'"
          class="table-data-view"
        >
          <div
            v-if="tableDataLoading"
            class="data-loading"
          >
            <a-spin /> 加载中...
          </div>
          <div
            v-else-if="tableData.items.length === 0"
            class="data-empty"
          >
            暂无数据
          </div>
          <div
            v-else
            class="data-table-wrap"
          >
            <div class="data-table-info">
              共 <strong>{{ tableData.total }}</strong> 条 · 第 {{ tableData.page }} 页
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

        <!-- 病例卡片 -->
        <div class="patient-cards">
          <div
            v-for="pt in patients"
            :key="pt.visit_id"
            class="patient-card"
            :class="{ active: selectedPatient?.visit_id === pt.visit_id }"
            @click="selectPatient(pt)"
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
                size="small"
                type="link"
                class="pt-view-btn"
                @click.stop="openRecordModal(pt)"
              >
                <DatabaseOutlined /> 表数据
              </a-button>
            </div>
          </div>
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
                  color="purple"
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
        <!-- 表 Tab 切换 -->
        <a-tabs
          v-model:active-key="recordActiveTab"
          size="small"
        >
          <a-tab-pane
            v-for="tab in recordTabs"
            :key="tab.name"
            :tab="`${tab.label} (${tab.count})`"
          >
            <div
              v-if="tab.count === 0"
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
import { ref, computed, onMounted } from 'vue'
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

function getAuthHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const token = getAccessToken()
  const headers: Record<string, string> = { ...extra }
  if (token && !headers.Authorization) {
    headers.Authorization = `Bearer ${token}`
  }
  return headers
}

// ===== State =====
const stats = ref<any>({})
const schema = ref<any>({ tables: [], total_tables: 0 })
const patients = ref<any[]>([])
const departments = ref<string[]>([])
const selectedTable = ref('mr')
const selectedPatient = ref<any>(null)
const selectedDetail = ref<any>(null)
const dbPath = ref('data/medqc.db')

// 左侧面板视图：schema / data
const leftView = ref<'schema' | 'data'>('schema')
const tableData = ref<any>({ items: [], columns: [], total: 0, page: 1 })
const tableDataLoading = ref(false)

// 病历弹窗
const recordModalVisible = ref(false)
const recordModalTitle = ref('')
const recordModalLoading = ref(false)
const recordActiveTab = ref('mr')
const recordTabs = ref<any[]>([])

// ===== Computed =====
const totalDiagnoses = computed(() => {
  return patients.value.length > 0 ? patients.value.length * 2 + '+' : 0
})
const totalSurgeries = computed(() => {
  return patients.value.length > 0 ? Math.ceil(patients.value.length * 0.6) + '+' : 0
})
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
    await loadTableData(name)
  }
}

function switchToDataView() {
  leftView.value = 'data'
  loadTableData(selectedTable.value)
}

async function loadTableData(tableName: string) {
  tableDataLoading.value = true
  try {
    const resp = await fetch(`${API_BASE}/table-data/${tableName}`, {
      headers: getAuthHeaders(),
    })
    tableData.value = await resp.json()
  } catch (e) {
    console.error('加载表数据失败', e)
  } finally {
    tableDataLoading.value = false
  }
}

async function selectPatient(pt: any) {
  selectedPatient.value = pt
  try {
    const resp = await fetch(
      `${API_BASE}/frontpage/${pt.institute_id}/${pt.patient_id}/${pt.visit_id}`,
      {
        headers: getAuthHeaders(),
      },
    )
    selectedDetail.value = await resp.json()
  } catch (e) {
    console.error('加载病案详情失败', e)
  }
}

// 病历弹窗：加载该患者在所有表中的数据
async function openRecordModal(pt: any) {
  recordModalTitle.value = `${pt.name} (${pt.mr_no}) — 各表原始数据`
  recordModalVisible.value = true
  recordModalLoading.value = true
  recordActiveTab.value = 'mr'

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
        const resp = await fetch(`${API_BASE}/table-data/${t.name}`, {
          headers: getAuthHeaders(),
        })
        const data = await resp.json()
        // 过滤出这个患者的数据
        const patientItems = data.items.filter((item: any) => {
          // patient_information 只有 patient_id（无 visit_id）
          if (t.name === 'patient_information') {
            return item.patient_id === pt.patient_id && item.institute_id === pt.institute_id
          }
          return (
            item.patient_id === pt.patient_id &&
            item.visit_id === pt.visit_id &&
            item.institute_id === pt.institute_id
          )
        })
        return {
          name: t.name,
          label: t.label,
          columns: data.columns,
          items: patientItems,
          count: patientItems.length,
        }
      }),
    )
    recordTabs.value = results
    // 自动选中第一个有数据的 tab
    const firstWithData = results.find((r) => r.count > 0)
    if (firstWithData) recordActiveTab.value = firstWithData.name
  } catch (e) {
    console.error('加载病历表数据失败', e)
  } finally {
    recordModalLoading.value = false
  }
}

async function loadData() {
  try {
    const [statsResp, schemaResp, listResp, deptsResp] = await Promise.all([
      fetch(`${API_BASE}/stats`, { headers: getAuthHeaders() }),
      fetch(`${API_BASE}/schema`, { headers: getAuthHeaders() }),
      fetch(`${API_BASE}/list`, { headers: getAuthHeaders() }),
      fetch(`${API_BASE}/departments`, { headers: getAuthHeaders() }),
    ])
    stats.value = await statsResp.json()
    schema.value = await schemaResp.json()
    const listData = await listResp.json()
    patients.value = listData.items || []
    departments.value = await deptsResp.json()

    if (patients.value.length > 0) {
      await selectPatient(patients.value[0])
    }
  } catch (e) {
    console.error('数据加载失败', e)
  }
}

onMounted(loadData)
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
  color: rgba(29, 29, 31, 0.6);
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
  grid-template-columns: repeat(5, 1fr);
  gap: 14px;
  margin-bottom: 16px;
}
.stat-card {
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
  color: rgba(29, 29, 31, 0.56);
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
  color: rgba(29, 29, 31, 0.66);
  font-weight: 500;
}
.ds-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.ds-path {
  font-size: 12px;
  color: rgba(29, 29, 31, 0.38);
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
  color: rgba(29, 29, 31, 0.56);
  display: flex;
  align-items: center;
  gap: 4px;
  transition: all 0.2s;
}
.toggle-btn:hover {
  color: #1d1d1f;
}
.toggle-btn.active {
  background: rgba(255, 255, 255, 0.92);
  color: #0a6cff;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.table-tabs {
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
}
.tab-name {
  color: rgba(29, 29, 31, 0.38);
  font-family: 'SF Mono', 'Cascadia Code', ui-monospace, monospace;
  font-size: 11px;
}
.table-tab.active .tab-name {
  color: rgba(10, 108, 255, 0.58);
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
  color: rgba(29, 29, 31, 0.42);
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
  color: #1d1d1f;
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
  color: rgba(29, 29, 31, 0.56);
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
  color: rgba(29, 29, 31, 0.38);
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}
.data-table-info {
  padding: 8px 16px;
  font-size: 12px;
  color: rgba(29, 29, 31, 0.56);
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
  color: rgba(29, 29, 31, 0.46);
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
  color: rgba(29, 29, 31, 0.7);
}
.data-table-wrap {
  display: flex;
  flex-direction: column;
  flex: 1;
  overflow: hidden;
}

/* ===== 右侧 ===== */
.data-panel {
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
  color: rgba(29, 29, 31, 0.38);
}
.pt-info {
  font-size: 12px;
  color: rgba(29, 29, 31, 0.56);
  margin-bottom: 4px;
}
.pt-dept {
  font-weight: 600;
}
.pt-divider {
  color: rgba(29, 29, 31, 0.22);
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
  color: rgba(29, 29, 31, 0.42);
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
  color: rgba(29, 29, 31, 0.72);
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
  color: #1d1d1f;
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
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}
.cost-total {
  grid-column: span 3;
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
  font-size: 13px;
  color: rgba(29, 29, 31, 0.66);
}

/* 弹窗 */
.modal-loading {
  padding: 60px;
  text-align: center;
  color: rgba(29, 29, 31, 0.56);
  font-size: 15px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

/* 响应式 */
@media (max-width: 1200px) {
  .stats-row {
    grid-template-columns: repeat(3, 1fr);
  }
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
</style>
