<template>
  <div class="frontpage-rules-tab space-y-6">
    <div class="kpi-grid">
      <section class="kpi-card">
        <div class="kpi-head">
          <div class="kpi-title-wrap">
            <span class="kpi-kicker">规则总览</span>
            <h3>首页质控</h3>
          </div>
          <span class="kpi-pill">{{ statistics.total }} 条</span>
        </div>
        <div class="kpi-stats">
          <div>
            <div class="kpi-value">{{ statistics.total }}</div>
            <div class="kpi-label">规则总数</div>
          </div>
          <div>
            <div class="kpi-value">{{ statistics.categories }}</div>
            <div class="kpi-label">分类数</div>
          </div>
        </div>
        <p class="kpi-note">统一查看首页质控规则总量与分类覆盖情况。</p>
      </section>

      <section class="kpi-card">
        <div class="kpi-head">
          <div class="kpi-title-wrap">
            <span class="kpi-kicker">严重度分布</span>
            <h3>规则关注结构</h3>
          </div>
        </div>
        <div class="severity-list">
          <div class="severity-item">
            <div class="severity-meta"><span>严重</span><strong>{{ statistics.severity_counts?.error || 0 }}</strong></div>
            <div class="severity-track"><div class="severity-fill severity-error" :style="{ width: severityPercent('error') }"></div></div>
          </div>
          <div class="severity-item">
            <div class="severity-meta"><span>警告</span><strong>{{ statistics.severity_counts?.warning || 0 }}</strong></div>
            <div class="severity-track"><div class="severity-fill severity-warning" :style="{ width: severityPercent('warning') }"></div></div>
          </div>
          <div class="severity-item">
            <div class="severity-meta"><span>提示</span><strong>{{ statistics.severity_counts?.info || 0 }}</strong></div>
            <div class="severity-track"><div class="severity-fill severity-info" :style="{ width: severityPercent('info') }"></div></div>
          </div>
        </div>
      </section>

      <section class="kpi-card">
        <div class="kpi-head">
          <div class="kpi-title-wrap">
            <span class="kpi-kicker">分类分布</span>
            <h3>规则覆盖结构</h3>
          </div>
        </div>
        <div class="category-grid">
          <div><div class="category-value">{{ statistics.category_counts?.required || 0 }}</div><div class="category-label">必填性</div></div>
          <div><div class="category-value">{{ statistics.category_counts?.format || 0 }}</div><div class="category-label">规范性</div></div>
          <div><div class="category-value">{{ statistics.category_counts?.logic || 0 }}</div><div class="category-label">逻辑性</div></div>
          <div><div class="category-value">{{ statistics.category_counts?.consistency || 0 }}</div><div class="category-label">一致性</div></div>
        </div>
      </section>
    </div>

    <section class="table-shell">
      <div class="table-toolbar">
        <label class="field field-search">
          <div class="search-box">
            <svg class="search-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              v-model="searchText"
              @input="handleSearch"
              type="text"
              placeholder="搜索规则编号、名称、字段或说明"
            >
          </div>
        </label>

        <label class="field">
          <select v-model="filterCategory" @change="applyFilter">
            <option :value="undefined">全部分类</option>
            <option value="required">必填校验</option>
            <option value="format">格式校验</option>
            <option value="logic">逻辑校验</option>
            <option value="consistency">一致性</option>
          </select>
        </label>

        <label class="field">
          <select v-model="filterSeverity" @change="applyFilter">
            <option :value="undefined">全部严重度</option>
            <option value="error">严重</option>
            <option value="warning">警告</option>
            <option value="info">提示</option>
          </select>
        </label>

        <div class="toolbar-actions">
          <button @click="fetchRules" class="refresh-btn">
            <svg class="btn-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            刷新
          </button>
        </div>
      </div>

      <div class="table-scroll">
        <div v-if="loading" class="loading-mask">
          <a-spin />
        </div>
        <table class="rules-table">
          <thead>
            <tr>
              <th>编号</th>
              <th>规则名称</th>
              <th>校验字段</th>
              <th>分类</th>
              <th>严重度</th>
              <th class="text-right">状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="record in filteredRules" :key="record.rule_id" class="rule-row" @click="editRule(record)">
              <td><span class="code-pill">{{ record.rule_id }}</span></td>
              <td>
                <div class="rule-name">{{ record.rule_name }}</div>
                <div class="rule-desc" :title="record.description">{{ record.description }}</div>
              </td>
              <td><span class="tag-pill">{{ record.field_name }}</span></td>
              <td><span class="tag-pill">{{ getCategoryLabel(record.category) }}</span></td>
              <td><span :class="['tag-pill', getSeverityBgClass(record.severity)]">{{ getSeverityLabel(record.severity) }}</span></td>
              <td class="text-right" @click.stop>
                <button class="bg-blue-500 border-transparent relative inline-flex h-4 w-7 shrink-0 cursor-pointer rounded-full border-2 transition-colors focus:outline-none">
                  <span class="translate-x-3 inline-block h-3 w-3 transform rounded-full bg-white shadow-sm ring-0 transition"></span>
                </button>
              </td>
            </tr>
            <tr v-if="filteredRules.length === 0 && !loading">
              <td colspan="6" class="empty-row">暂无匹配数据</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <RuleEditorDrawer v-model:open="drawerVisible" :record="currentRecord" @save="handleSaveRule" />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { message } from 'ant-design-vue'
import RuleEditorDrawer from './RuleEditorDrawer.vue'

interface FrontpageRule {
  rule_id: string
  field_name: string
  rule_name: string
  description: string
  severity: string
  category: string
}

const loading = ref(false)
const allRules = ref<FrontpageRule[]>([])
const searchText = ref('')
const filterCategory = ref<string>()
const filterSeverity = ref<string>()

const statistics = reactive({
  total: 0,
  categories: 0,
  severity_counts: {} as Record<string, number>,
  category_counts: {} as Record<string, number>,
})

const filteredRules = computed(() => {
  let result = allRules.value
  if (searchText.value) {
    const kw = searchText.value.toLowerCase()
    result = result.filter((r) =>
      r.rule_id.toLowerCase().includes(kw)
      || r.rule_name.toLowerCase().includes(kw)
      || r.description.toLowerCase().includes(kw)
      || r.field_name.toLowerCase().includes(kw),
    )
  }
  if (filterCategory.value) result = result.filter((r) => r.category === filterCategory.value)
  if (filterSeverity.value) result = result.filter((r) => r.severity === filterSeverity.value)
  return result
})

const drawerVisible = ref(false)
const currentRecord = ref({})

const editRule = (record: FrontpageRule) => {
  currentRecord.value = { ...record }
  drawerVisible.value = true
}

const handleSaveRule = (updatedRecord: FrontpageRule) => {
  message.success(`规则 [${updatedRecord.rule_id}] 配置已保存并发布`)
  const idx = allRules.value.findIndex((r) => r.rule_id === updatedRecord.rule_id)
  if (idx > -1) allRules.value[idx] = { ...allRules.value[idx], ...updatedRecord }
}

const getCategoryLabel = (cat: string) => ({ required: '必填', format: '规范', logic: '逻辑', consistency: '一致性' }[cat] || cat)
const getSeverityBgClass = (s: string) => ({ error: 'severity-error', warning: 'severity-warning', info: 'severity-info' }[s] || 'severity-info')
const getSeverityLabel = (s: string) => ({ error: '严重', warning: '警告', info: '提示' }[s] || s)

const severityPercent = (s: string) => {
  const total = (statistics.severity_counts?.error || 0) + (statistics.severity_counts?.warning || 0) + (statistics.severity_counts?.info || 0) || 1
  const count = statistics.severity_counts?.[s] || 0
  return `${Math.round((count / total) * 100)}%`
}

let searchTimer: ReturnType<typeof setTimeout> | null = null
const handleSearch = () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {}, 300)
}
const applyFilter = () => {}

const fetchRules = async () => {
  loading.value = true
  try {
    const resp = await fetch('/api/v1/qc/formal-qc/rules')
    const data = await resp.json()
    if (data.success && data.data) {
      allRules.value = data.data
      const rules = data.data as FrontpageRule[]
      statistics.total = rules.length
      statistics.categories = new Set(rules.map((r) => r.category)).size
      const sevCounts: Record<string, number> = {}
      const catCounts: Record<string, number> = {}
      for (const r of rules) {
        sevCounts[r.severity] = (sevCounts[r.severity] || 0) + 1
        catCounts[r.category] = (catCounts[r.category] || 0) + 1
      }
      statistics.severity_counts = sevCounts
      statistics.category_counts = catCounts
    }
  } catch (e) {
    console.error('加载首页质控规则失败:', e)
    message.error('加载首页质控规则失败')
  } finally {
    loading.value = false
  }
}

onMounted(fetchRules)
</script>

<style scoped>
.frontpage-rules-tab {
  width: 100%;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.kpi-card {
  min-height: 232px;
  padding: 24px;
  border-radius: 20px;
  border: 1px solid #dce6f5;
  background: linear-gradient(180deg, #ffffff, #f8fbff);
  box-shadow: 0 6px 20px rgba(24, 58, 120, 0.06);
  display: flex;
  flex-direction: column;
}

.kpi-head {
  min-height: 48px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.kpi-title-wrap h3 {
  margin: 6px 0 0;
  font-size: 22px;
  line-height: 30px;
  font-weight: 700;
  color: #0f1f44;
}

.kpi-kicker {
  font-size: 13px;
  line-height: 20px;
  color: #5f7396;
  font-weight: 600;
}

.kpi-pill {
  height: 34px;
  padding: 0 12px;
  border-radius: 999px;
  border: 1px solid #dce6f5;
  background: #eef4ff;
  color: #2f6bff;
  font-size: 13px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
}

.kpi-stats {
  margin-top: 20px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 40px;
}

.kpi-value {
  font-size: 52px;
  line-height: 52px;
  color: #0f1f44;
  font-weight: 700;
}

.kpi-label {
  margin-top: 8px;
  font-size: 15px;
  line-height: 22px;
  color: #5f7396;
}

.kpi-note {
  margin: auto 0 0;
  padding-top: 16px;
  font-size: 13px;
  line-height: 20px;
  color: #8fa2c2;
}

.severity-list {
  margin-top: 20px;
  display: grid;
  gap: 14px;
}

.severity-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 13px;
  color: #5f7396;
}

.severity-meta strong {
  color: #0f1f44;
  font-size: 16px;
  line-height: 22px;
}

.severity-track {
  height: 8px;
  border-radius: 999px;
  background: #e2e8f0;
  overflow: hidden;
}

.severity-fill {
  height: 100%;
  border-radius: inherit;
}

.severity-error {
  background: linear-gradient(90deg, #ef4444, #fb7185);
}

.severity-warning {
  background: linear-gradient(90deg, #f59e0b, #fbbf24);
}

.severity-info {
  background: linear-gradient(90deg, #64748b, #94a3b8);
}

.category-grid {
  margin-top: 20px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px 24px;
}

.category-value {
  font-size: 34px;
  line-height: 1;
  font-weight: 700;
  color: #0f1f44;
}

.category-label {
  margin-top: 8px;
  color: #5f7396;
  font-size: 13px;
  line-height: 20px;
}

.table-shell {
  border: 1px solid rgba(226, 232, 240, 0.9);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.99), rgba(247, 250, 252, 0.97));
  box-shadow: 0 14px 34px rgba(15, 23, 42, 0.05);
  border-radius: 20px;
  overflow: hidden;
}

.table-toolbar {
  padding: 16px 18px 18px;
  border-bottom: 1px solid #e2e8f0;
  display: grid;
  grid-template-columns: 1.4fr repeat(2, minmax(180px, 1fr)) auto;
  gap: 12px;
  align-items: end;
}

.refresh-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 12px;
  border: 1px solid #bfdbfe;
  color: #2563eb;
  font-weight: 700;
  background: #eff6ff;
  cursor: pointer;
}

.field {
  display: grid;
  gap: 8px;
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

.btn-icon {
  width: 16px;
  height: 16px;
}

.table-scroll {
  position: relative;
  min-height: 420px;
  overflow: auto;
}

.loading-mask {
  position: absolute;
  inset: 0;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.6);
}

.rules-table {
  width: 100%;
  min-width: 980px;
  border-collapse: collapse;
}

.rules-table thead {
  position: sticky;
  top: 0;
  background: #f8fafc;
  z-index: 1;
}

.rules-table th {
  padding: 13px 18px;
  text-align: left;
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
  border-bottom: 1px solid #e2e8f0;
}

.rules-table td {
  padding: 14px 18px;
  border-bottom: 1px solid #f1f5f9;
  vertical-align: top;
  color: #334155;
}

.rule-row {
  cursor: pointer;
}

.rule-row:hover {
  background: #f8fafc;
}

.code-pill {
  display: inline-flex;
  align-items: center;
  height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 700;
}

.tag-pill {
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  padding: 0 10px;
  border-radius: 999px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  color: #475569;
  font-size: 11px;
  font-weight: 700;
}

.severity-error {
  background: #fff1f2;
  border-color: #fecdd3;
  color: #dc2626;
}

.severity-warning {
  background: #fff7ed;
  border-color: #fed7aa;
  color: #d97706;
}

.rule-name {
  font-size: 14px;
  line-height: 20px;
  font-weight: 700;
  color: #0f172a;
}

.rule-desc {
  margin-top: 4px;
  font-size: 12px;
  line-height: 18px;
  color: #64748b;
  max-width: 320px;
}

.empty-row {
  text-align: center;
  color: #94a3b8;
  padding: 36px 16px;
}

@media (max-width: 1280px) {
  .kpi-grid {
    grid-template-columns: 1fr;
  }

  .table-toolbar {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 1024px) {
  .table-toolbar {
    grid-template-columns: 1fr;
  }
}
</style>
