<template>
  <div class="settlement-rules-workbench">
    <section class="toolbar-shell">
      <div class="toolbar-grid">
        <label class="field field-search">
          <div class="search-box">
            <svg class="search-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              v-model="searchText"
              type="text"
              placeholder="搜索规则编号、名称、字段或说明"
            />
          </div>
        </label>

        <label class="field">
          <select v-model="filterCategory">
            <option :value="undefined">全部分类</option>
            <option v-for="cat in categoryOptions" :key="cat.value" :value="cat.value">{{ cat.label }}</option>
          </select>
        </label>

        <label class="field">
          <select v-model="filterSeverity">
            <option :value="undefined">全部严重度</option>
            <option value="error">严重</option>
            <option value="warning">警告</option>
            <option value="info">提示</option>
          </select>
        </label>

        <label class="field">
          <select v-model="filterGrouping">
            <option :value="undefined">全部</option>
            <option :value="true">影响分组</option>
            <option :value="false">不影响分组</option>
          </select>
        </label>

        <div class="toolbar-actions">
          <button class="refresh-btn" @click="fetchRules">
            <svg class="btn-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            刷新
          </button>
        </div>
      </div>
    </section>

    <section class="summary-grid">
      <article class="summary-card">
        <div class="summary-head">
          <div>
            <div class="summary-kicker">规则总览</div>
            <h3>结算清单质控</h3>
          </div>
          <span class="summary-pill">{{ statistics.total }} 条</span>
        </div>

        <div class="summary-stats">
          <div class="summary-stat">
            <span class="summary-stat-value">{{ statistics.total }}</span>
            <span class="summary-stat-label">规则总数</span>
          </div>
          <div class="summary-stat">
            <span class="summary-stat-value">{{ statistics.affects_grouping }}</span>
            <span class="summary-stat-label">影响分组</span>
          </div>
        </div>
        <div class="summary-note">统一查看结算规则总量与分组影响范围。</div>
      </article>

      <article class="summary-card">
        <div class="summary-head">
          <div>
            <div class="summary-kicker">严重度分布</div>
            <h3>规则关注结构</h3>
          </div>
          <span class="summary-pill summary-pill-neutral">{{ severityTotal }} 条</span>
        </div>

        <div class="progress-list">
          <div class="progress-item">
            <div class="progress-meta">
              <span>严重</span>
              <strong>{{ statistics.severity_counts?.error || 0 }}</strong>
            </div>
            <div class="progress-track">
              <div class="progress-fill progress-fill-strong" :style="{ width: severityPercent('error') }"></div>
            </div>
          </div>
          <div class="progress-item">
            <div class="progress-meta">
              <span>警告</span>
              <strong>{{ statistics.severity_counts?.warning || 0 }}</strong>
            </div>
            <div class="progress-track">
              <div class="progress-fill progress-fill-medium" :style="{ width: severityPercent('warning') }"></div>
            </div>
          </div>
          <div class="progress-item">
            <div class="progress-meta">
              <span>提示</span>
              <strong>{{ statistics.severity_counts?.info || 0 }}</strong>
            </div>
            <div class="progress-track">
              <div class="progress-fill progress-fill-soft" :style="{ width: severityPercent('info') }"></div>
            </div>
          </div>
        </div>
      </article>

      <article class="summary-card">
        <div class="summary-head">
          <div>
            <div class="summary-kicker">分类分布</div>
            <h3>规则覆盖结构</h3>
          </div>
          <span class="summary-pill">{{ categoryTotal }} 类</span>
        </div>

        <div class="source-list">
          <div class="source-row">
            <span class="source-name">完整性</span>
            <strong>{{ statistics.category_counts?.required || 0 }}</strong>
          </div>
          <div class="source-row source-row-accent">
            <span class="source-name">规范性</span>
            <strong>{{ statistics.category_counts?.format || 0 }}</strong>
          </div>
          <div class="source-row">
            <span class="source-name">合理性</span>
            <strong>{{ statistics.category_counts?.logic || 0 }}</strong>
          </div>
          <div class="source-row source-row-accent">
            <span class="source-name">逻辑质控</span>
            <strong>{{ statistics.category_counts?.consistency || 0 }}</strong>
          </div>
        </div>
      </article>
    </section>

    <section class="table-shell">
      <div class="table-head">
        <div>
          <div class="table-kicker">规则明细</div>
          <div class="table-title-row">
            <h3>规则列表</h3>
            <span class="table-chip">{{ filteredRules.length }} 条已筛选</span>
          </div>
        </div>
        <div class="table-meta">点击任意行可编辑，右侧按钮显示影响分组状态</div>
      </div>

      <div class="table-scroll">
        <div v-if="loading" class="loading-mask">
          <a-spin />
        </div>

        <table class="rules-table">
          <thead>
            <tr>
              <th class="col-code">编号</th>
              <th class="col-name">规则名称</th>
              <th class="col-field">校验字段</th>
              <th class="col-category">分类</th>
              <th class="col-severity">严重度</th>
              <th class="col-group text-center">分组影响</th>
              <th class="col-action text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="record in pagedRules"
              :key="record.rule_id"
              @click="editRule(record)"
              class="rule-row"
            >
              <td class="code-cell">
                <span class="rule-code">{{ record.rule_id }}</span>
              </td>
              <td class="name-cell">
                <div class="rule-name">{{ record.rule_name }}</div>
                <div class="rule-desc" :title="record.description">{{ record.description }}</div>
              </td>
              <td>
                <span class="pill pill-neutral">{{ record.field_name }}</span>
              </td>
              <td>
                <span class="pill pill-neutral">{{ getCategoryLabel(record.category) }}</span>
              </td>
              <td>
                <span :class="['pill', severityClass(record.severity)]">{{ getSeverityLabel(record.severity) }}</span>
              </td>
              <td class="text-center">
                <span v-if="record.affects_grouping" class="pill pill-strong">影响分组</span>
                <span v-else class="pill pill-soft">不影响</span>
              </td>
              <td class="text-right" @click.stop>
                  <button class="edit-btn" @click="editRule(record)">编辑</button>
              </td>
            </tr>
            <tr v-if="filteredRules.length === 0 && !loading">
              <td colspan="7" class="empty-row">暂无匹配数据</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="filteredRules.length > 0" class="pagination-bar">
        <div class="pagination-meta">
          第 {{ currentPage }} / {{ totalPages }} 页 · 共 {{ filteredRules.length }} 条
        </div>
        <div class="pagination-actions">
          <label class="page-size-wrap">
            每页
            <select v-model.number="pageSize" class="page-size-select">
              <option v-for="size in pageSizeOptions" :key="size" :value="size">{{ size }}</option>
            </select>
            条
          </label>
          <button class="page-btn" :disabled="currentPage <= 1" @click="prevPage">上一页</button>
          <button class="page-btn" :disabled="currentPage >= totalPages" @click="nextPage">下一页</button>
        </div>
      </div>
    </section>

    <RuleEditorDrawer
      v-model:open="drawerVisible"
      :record="currentRecord"
      @save="handleSaveRule"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import RuleEditorDrawer from './RuleEditorDrawer.vue'

interface SettlementRule {
  rule_id: string
  field_name: string
  rule_name: string
  description: string
  severity: string
  category: string
  affects_grouping: boolean
}

const loading = ref(false)
const allRules = ref<SettlementRule[]>([])
const searchText = ref('')
const filterCategory = ref<string>()
const filterSeverity = ref<string>()
const filterGrouping = ref<boolean>()
const currentPage = ref(1)
const pageSize = ref(10)
const pageSizeOptions = [10, 20, 50]

const statistics = reactive({
  total: 0,
  affects_grouping: 0,
  severity_counts: {} as Record<string, number>,
  category_counts: {} as Record<string, number>,
})

const drawerVisible = ref(false)
const currentRecord = ref<SettlementRule | null>(null)

const categoryOptions = computed(() => {
  const labels: Record<string, string> = {
    required: '完整性',
    format: '规范性',
    logic: '合理性',
    consistency: '逻辑质控',
  }
  return Object.entries(labels).map(([value, label]) => ({ value, label }))
})

const filteredRules = computed(() => {
  let result = allRules.value

  if (searchText.value.trim()) {
    const keyword = searchText.value.trim().toLowerCase()
    result = result.filter((rule) =>
      [rule.rule_id, rule.rule_name, rule.description, rule.field_name].some((field) =>
        field.toLowerCase().includes(keyword),
      ),
    )
  }

  if (filterCategory.value) result = result.filter((rule) => rule.category === filterCategory.value)
  if (filterSeverity.value) result = result.filter((rule) => rule.severity === filterSeverity.value)
  if (filterGrouping.value !== undefined) {
    result = result.filter((rule) => rule.affects_grouping === filterGrouping.value)
  }

  return result
})

const totalPages = computed(() => Math.max(1, Math.ceil(filteredRules.value.length / pageSize.value)))

const pagedRules = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredRules.value.slice(start, start + pageSize.value)
})

const severityTotal = computed(() =>
  (statistics.severity_counts?.error || 0)
  + (statistics.severity_counts?.warning || 0)
  + (statistics.severity_counts?.info || 0),
)

const categoryTotal = computed(() => Object.values(statistics.category_counts || {}).reduce((sum, n) => sum + n, 0))

watch([searchText, filterCategory, filterSeverity, filterGrouping, pageSize], () => {
  currentPage.value = 1
})

watch(totalPages, (maxPage) => {
  if (currentPage.value > maxPage) {
    currentPage.value = maxPage
  }
})

const prevPage = () => {
  if (currentPage.value > 1) currentPage.value -= 1
}

const nextPage = () => {
  if (currentPage.value < totalPages.value) currentPage.value += 1
}

const editRule = (record: SettlementRule) => {
  currentRecord.value = { ...record }
  drawerVisible.value = true
}

const handleSaveRule = (updatedRecord: Partial<SettlementRule> & { rule_id: string }) => {
  message.success(`规则 [${updatedRecord.rule_id}] 已保存`)
  const idx = allRules.value.findIndex((r) => r.rule_id === updatedRecord.rule_id)
  if (idx > -1) {
    allRules.value[idx] = { ...allRules.value[idx], ...updatedRecord }
  }
}

const getCategoryLabel = (category: string) => {
  return {
    required: '完整性',
    format: '规范性',
    logic: '合理性',
    consistency: '逻辑质控',
  }[category] || category
}

const severityClass = (severity: string) => {
  return {
    error: 'pill-severity-strong',
    warning: 'pill-severity-medium',
    info: 'pill-severity-soft',
  }[severity] || 'pill-severity-soft'
}

const getSeverityLabel = (severity: string) => {
  return { error: '严重', warning: '警告', info: '提示' }[severity] || severity
}

const severityPercent = (severity: string) => {
  const total = severityTotal.value || 1
  const count = statistics.severity_counts?.[severity] || 0
  return `${Math.round((count / total) * 100)}%`
}

const fetchRules = async () => {
  loading.value = true
  try {
    const resp = await fetch('/api/medical-records/settlement/rules/list')
    const data = await resp.json()
    if (data.success && data.data) {
      const sorted = (data.data as SettlementRule[]).slice().sort((a, b) => a.rule_id.localeCompare(b.rule_id, 'zh-Hans-CN', { numeric: true }))
      allRules.value = sorted
      currentPage.value = 1

      statistics.total = sorted.length
      statistics.affects_grouping = sorted.filter((rule) => rule.affects_grouping).length

      const severityCounts: Record<string, number> = {}
      const categoryCounts: Record<string, number> = {}
      for (const rule of sorted) {
        severityCounts[rule.severity] = (severityCounts[rule.severity] || 0) + 1
        categoryCounts[rule.category] = (categoryCounts[rule.category] || 0) + 1
      }
      statistics.severity_counts = severityCounts
      statistics.category_counts = categoryCounts
    }
  } catch (error) {
    console.error('加载结算清单质控规则失败:', error)
    message.error('加载结算清单质控规则失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchRules()
})
</script>

<style scoped>
.settlement-rules-workbench {
  --rule-primary: #2563eb;
  --rule-primary-soft: #dbeafe;
  --rule-text-strong: #0f172a;
  --rule-text-body: #334155;
  --rule-border: #e2e8f0;
  --rule-surface: #ffffff;
  --rule-surface-subtle: #f8fafc;
  --rule-severity-error: #ef4444;
  --rule-severity-warning: #f59e0b;
  --rule-severity-info: #64748b;
  --rule-severity-error-soft: #fff1f2;
  --rule-severity-warning-soft: #fff7ed;
  --rule-severity-info-soft: #f8fafc;
  display: grid;
  gap: 16px;
  color: var(--rule-text-strong);
}

.settlement-rules-workbench > .summary-grid {
  order: 1;
}

.settlement-rules-workbench > .toolbar-shell {
  order: 2;
}

.settlement-rules-workbench > .table-shell {
  order: 3;
}

.toolbar-shell,
.summary-card,
.table-shell {
  border: 1px solid rgba(226, 232, 240, 0.9);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.99), rgba(247, 250, 252, 0.97));
  box-shadow: 0 14px 34px rgba(15, 23, 42, 0.05);
  border-radius: 20px;
}

.toolbar-shell {
  padding: 16px 18px 18px;
}

.toolbar-head,
.summary-head,
.table-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.toolbar-kicker,
.summary-kicker,
.table-kicker {
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0;
  color: #5f7396;
  text-transform: none;
}

.toolbar-head h3,
.summary-head h3,
.table-head h3 {
  margin: 6px 0 0;
  font-size: 22px;
  line-height: 30px;
  font-weight: 700;
  color: #0f1f44;
  letter-spacing: -0.03em;
}

.toolbar-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  justify-content: flex-end;
}

.toolbar-meta-chip,
.summary-pill,
.table-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 34px;
  padding: 0 12px;
  border-radius: 999px;
  border: 1px solid #dce6f5;
  background: #eef4ff;
  color: #2f6bff;
  font-size: 13px;
  font-weight: 600;
}

.toolbar-meta-chip-ghost,
.summary-pill-neutral {
  border-color: rgba(226, 232, 240, 0.9);
  background: #fff;
  color: #64748b;
}

.toolbar-grid {
  display: grid;
  grid-template-columns: 1.3fr repeat(3, minmax(180px, 1fr)) auto;
  gap: 12px;
  align-items: end;
  margin-top: 14px;
}

.field {
  display: grid;
  gap: 8px;
}

.field-label {
  font-size: 12px;
  font-weight: 700;
  color: #64748b;
}

.search-box,
.field select {
  height: 42px;
  border-radius: 14px;
  border: 1px solid rgba(226, 232, 240, 0.95);
  background: #fff;
}

.search-box {
  position: relative;
  display: flex;
  align-items: center;
}

.search-icon {
  position: absolute;
  left: 14px;
  width: 16px;
  height: 16px;
  color: #94a3b8;
}

.search-box input,
.field select {
  width: 100%;
  border: 0;
  outline: none;
  background: transparent;
  color: #0f172a;
  font-size: 13px;
}

.search-box input {
  padding: 0 16px 0 42px;
}

.field select {
  padding: 0 14px;
}

.toolbar-actions {
  display: flex;
  justify-content: flex-end;
}

.refresh-btn,
.edit-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 42px;
  padding: 0 14px;
  border-radius: 14px;
  border: 1px solid rgba(191, 219, 254, 0.95);
  background: linear-gradient(180deg, #fff, #eff6ff);
  color: #2563eb;
  font-weight: 700;
  cursor: pointer;
}

.btn-icon {
  width: 16px;
  height: 16px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.summary-card {
  padding: 24px;
  min-height: 232px;
}

.summary-stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 40px;
  margin-top: 20px;
}

.summary-stat {
  display: grid;
  gap: 6px;
}

.summary-stat-value {
  font-size: 52px;
  line-height: 52px;
  font-weight: 700;
  color: #0f1f44;
}

.summary-stat-label {
  font-size: 15px;
  line-height: 22px;
  color: #5f7396;
  font-weight: 500;
}

.summary-note {
  margin-top: auto;
  padding-top: 16px;
  font-size: 13px;
  line-height: 20px;
  color: #8fa2c2;
}

.progress-list,
.source-list {
  display: grid;
  gap: 14px;
  margin-top: 20px;
}

.progress-meta,
.source-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-size: 12px;
}

.progress-meta span,
.source-name {
  color: #64748b;
  font-weight: 600;
}

.progress-meta strong,
.source-row strong {
  color: #0f172a;
  font-size: 14px;
  font-weight: 800;
}

.progress-track {
  height: 8px;
  border-radius: 999px;
  overflow: hidden;
  background: #e2e8f0;
  margin-top: 8px;
}

.progress-fill {
  height: 100%;
  border-radius: inherit;
}

.progress-fill-strong {
  background: linear-gradient(90deg, var(--rule-severity-error), #fb7185);
}

.progress-fill-medium {
  background: linear-gradient(90deg, var(--rule-severity-warning), #fbbf24);
}

.progress-fill-soft {
  background: linear-gradient(90deg, var(--rule-severity-info), #94a3b8);
}

.source-row-accent {
  padding: 10px 12px;
  border-radius: 16px;
  background: rgba(239, 246, 255, 0.8);
}

.table-shell {
  padding: 18px;
  overflow: hidden;
  border-radius: 20px;
}

.table-head {
  padding: 0 0 14px;
  align-items: flex-start;
}

.table-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 6px;
}

.table-meta {
  border-radius: 999px;
  border: 1px solid rgba(191, 219, 254, 0.9);
  background: rgba(239, 246, 255, 0.82);
  padding: 7px 12px;
  color: #1d4ed8;
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
}

.table-scroll {
  position: relative;
  min-height: 400px;
  overflow: auto;
  border-radius: 18px;
  border: 1px solid rgba(226, 232, 240, 0.82);
  background: #fff;
}

.loading-mask {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.55);
  backdrop-filter: blur(2px);
  z-index: 1;
}

.rules-table {
  width: 100%;
  min-width: 1100px;
  border-collapse: collapse;
}

.rules-table thead {
  position: sticky;
  top: 0;
  z-index: 1;
  background: #f8fafc;
}

.rules-table th {
  padding: 13px 18px;
  font-size: 12px;
  font-weight: 700;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  border-bottom: 1px solid rgba(226, 232, 240, 0.9);
  text-align: left;
}

.rules-table td {
  padding: 15px 18px;
  border-bottom: 1px solid rgba(241, 245, 249, 0.9);
  vertical-align: top;
  color: #334155;
}

.rule-row {
  cursor: pointer;
  transition: background-color 0.18s ease, transform 0.18s ease;
}

.rule-row:hover {
  background: rgba(248, 250, 252, 0.9);
}

.rule-code {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  background: #eff6ff;
  border: 1px solid rgba(191, 219, 254, 0.95);
  color: #1d4ed8;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  font-weight: 700;
}

.rule-name {
  font-size: 14px;
  font-weight: 800;
  color: #0f172a;
  line-height: 1.35;
}

.rule-desc {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.6;
  color: #64748b;
  max-width: 320px;
}

.pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
}

.pill-neutral {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  color: #475569;
}

.pill-severity-strong,
.pill-strong {
  background: var(--rule-severity-error-soft);
  border: 1px solid #fecdd3;
  color: #dc2626;
}

.pill-severity-medium {
  background: var(--rule-severity-warning-soft);
  border: 1px solid #fed7aa;
  color: #d97706;
}

.pill-severity-soft,
.pill-soft {
  background: var(--rule-severity-info-soft);
  border: 1px solid var(--rule-border);
  color: var(--rule-severity-info);
}

.empty-row {
  padding: 28px 18px;
  text-align: center;
  color: #94a3b8;
  font-size: 13px;
}

.edit-btn {
  height: 32px;
  padding: 0 14px;
  border-radius: 12px;
}

.pagination-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 4px 2px;
}

.pagination-meta {
  color: #64748b;
  font-size: 13px;
}

.pagination-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.page-size-wrap {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #64748b;
  font-size: 13px;
}

.page-size-select {
  min-width: 66px;
  height: 32px;
  border-radius: 10px;
  border: 1px solid #dbe5f3;
  background: #fff;
  padding: 0 8px;
  color: #0f172a;
  font-size: 13px;
}

.page-btn {
  height: 32px;
  padding: 0 12px;
  border-radius: 10px;
  border: 1px solid #bfdbfe;
  background: #eff6ff;
  color: #2563eb;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.page-btn:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

@media (max-width: 1280px) {
  .toolbar-grid {
    grid-template-columns: 1fr 1fr 1fr 1fr;
  }

  .toolbar-actions {
    justify-content: stretch;
  }
}

@media (max-width: 1024px) {
  .summary-grid {
    grid-template-columns: 1fr;
  }

  .toolbar-grid {
    grid-template-columns: 1fr 1fr;
  }
}
</style>

