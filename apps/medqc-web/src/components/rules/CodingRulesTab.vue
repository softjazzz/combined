<template>
  <div class="coding-rules-tab space-y-6">
    <!-- 一体化数据看板 -->
    <div
      class="bg-white rounded-[20px] border border-[#dce6f5] shadow-[0_6px_20px_rgba(24,58,120,0.06)] flex flex-col md:flex-row overflow-hidden"
    >
      <!-- 规则大盘总览 -->
      <div
        class="flex-1 p-6 border-b md:border-b-0 md:border-r border-slate-100 min-h-[232px] flex flex-col"
      >
        <div class="flex items-center justify-between gap-3 h-12">
          <div class="flex items-center gap-2 text-[13px] font-semibold text-slate-500">
            <svg
              class="w-4 h-4 text-slate-300"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
              />
            </svg>
            <span>规则总览</span>
          </div>
          <span
            class="h-[34px] px-3 inline-flex items-center rounded-full border border-[#dce6f5] bg-[#eef4ff] text-[#2f6bff] text-[13px] font-semibold"
          >{{ formatNumberCount(statistics.total_rule_count) }} 条</span>
        </div>
        <div class="mt-2 text-[22px] leading-[30px] font-bold text-[#0f1f44]">
          编码质控
        </div>
        <div class="mt-5 grid grid-cols-2 gap-10">
          <div>
            <div class="flex items-end gap-1">
              <span class="text-[52px] leading-[52px] font-bold text-[#0f1f44]">{{
                formatNumberSplit(statistics.total_rule_count)[0]
              }}</span>
              <span class="text-[24px] leading-6 font-bold text-[#5f7396]">{{
                formatNumberSplit(statistics.total_rule_count)[1]
              }}</span>
            </div>
            <div class="mt-2 text-[15px] leading-[22px] text-[#5f7396]">
              规则总数
            </div>
          </div>
          <div>
            <div class="text-[52px] leading-[52px] font-bold text-[#0f1f44]">
              {{ statistics.total_types }}
            </div>
            <div class="mt-2 text-[15px] leading-[22px] text-[#5f7396]">
              分类数
            </div>
          </div>
        </div>
        <div class="mt-auto pt-4 text-[13px] leading-5 text-[#8fa2c2]">
          统一查看编码规则总量与分类覆盖情况。
        </div>
      </div>

      <!-- 严重度分布 -->
      <div
        class="flex-1 p-6 border-b md:border-b-0 md:border-r border-slate-100 min-h-[232px] flex flex-col"
      >
        <div class="h-12 flex items-center text-[13px] font-semibold text-slate-500">
          严重度分布
        </div>
        <div class="space-y-4 mt-2">
          <div>
            <div class="flex justify-between items-center text-[13px] text-slate-600 mb-1.5">
              <span>严重</span>
              <strong class="text-[16px] text-slate-800">{{
                statistics.severity_counts?.error || 0
              }}</strong>
            </div>
            <div class="h-2 w-full bg-slate-100 rounded-full overflow-hidden">
              <div
                class="h-full bg-rose-500 rounded-full transition-all duration-700"
                :style="{ width: severityPercent('error') }"
              />
            </div>
          </div>
          <div>
            <div class="flex justify-between items-center text-[13px] text-slate-600 mb-1.5">
              <span>警告</span>
              <strong class="text-[16px] text-slate-800">{{
                statistics.severity_counts?.warning || 0
              }}</strong>
            </div>
            <div class="h-2 w-full bg-slate-100 rounded-full overflow-hidden">
              <div
                class="h-full bg-amber-400 rounded-full transition-all duration-700"
                :style="{ width: severityPercent('warning') }"
              />
            </div>
          </div>
          <div>
            <div class="flex justify-between items-center text-[13px] text-slate-600 mb-1.5">
              <span>提示</span>
              <strong class="text-[16px] text-slate-800">{{
                statistics.severity_counts?.info || 0
              }}</strong>
            </div>
            <div class="h-2 w-full bg-slate-100 rounded-full overflow-hidden">
              <div
                class="h-full bg-slate-400 rounded-full transition-all duration-700"
                :style="{ width: severityPercent('info') }"
              />
            </div>
          </div>
        </div>
      </div>

      <!-- 来源结构 -->
      <div class="flex-1 p-6 min-h-[232px] flex flex-col">
        <div class="h-12 flex items-center text-[13px] font-semibold text-slate-500">
          来源分布
        </div>
        <div class="mt-2 grid grid-cols-2 gap-x-8 gap-y-4">
          <div class="flex flex-col">
            <span class="text-[34px] leading-none font-bold text-[#0f1f44]">{{
              statistics.source_counts?.rule_engine || 0
            }}</span>
            <div class="mt-2 text-[13px] text-[#5f7396]">
              规则引擎
            </div>
          </div>
          <div class="flex flex-col">
            <span class="text-[34px] leading-none font-bold text-[#0f1f44]">{{
              statistics.source_counts?.ai_review || 0
            }}</span>
            <div class="mt-2 text-[13px] text-[#5f7396]">
              AI 审核
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 聚合列表容器 -->
    <section class="table-shell">
      <!-- 头部操作栏 -->
      <div class="table-toolbar">
        <label class="field field-search">
          <div class="search-box">
            <svg
              class="search-icon"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
              />
            </svg>
            <input
              v-model="searchText"
              type="text"
              placeholder="搜索规则编号、名称、字段或说明"
              @input="handleSearch"
            >
          </div>
        </label>

        <label class="field">
          <select
            v-model="filterCategory"
            @change="fetchRules"
          >
            <option :value="undefined">全部分类</option>
            <option
              v-for="cat in categoryOptions"
              :key="cat.value"
              :value="cat.value"
            >
              {{ cat.label }}
            </option>
          </select>
        </label>

        <label class="field">
          <select
            v-model="filterSeverity"
            @change="fetchRules"
          >
            <option :value="undefined">全部严重度</option>
            <option value="error">严重</option>
            <option value="warning">警告</option>
            <option value="info">提示</option>
          </select>
        </label>

        <div class="toolbar-actions">
          <button
            class="refresh-btn"
            @click="fetchRules"
          >
            <svg
              class="btn-icon"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
              />
            </svg>
            刷新
          </button>
        </div>
      </div>

      <!-- 数据表格 -->
      <div class="table-scroll">
        <div
          v-if="loading"
          class="absolute inset-0 bg-white/60 backdrop-blur-[1px] z-10 flex items-center justify-center"
        >
          <a-spin />
        </div>
        <table class="rules-table">
          <thead>
            <tr>
              <th class="px-5 py-3 w-20">
                编号
              </th>
              <th class="px-5 py-3 w-[28%]">
                规则名称
              </th>
              <th class="px-5 py-3">
                分类
              </th>
              <th class="px-5 py-3">
                严重度
              </th>
              <th class="px-5 py-3">
                条目数
              </th>
              <th class="px-5 py-3 w-[25%]">
                数据示例
              </th>
              <th class="px-5 py-3 text-right">
                状态
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100 text-[13px] text-slate-700">
            <tr
              v-for="record in filteredRules"
              :key="record.rule_id"
              class="rule-row"
              @click="editRule(record)"
            >
              <td class="px-5 py-4 align-top">
                <span class="code-pill">{{ record.rule_id }}</span>
              </td>

              <td class="px-5 py-4 align-top">
                <div class="font-bold text-slate-900 mb-0.5">
                  {{ record.name }}
                </div>
                <div
                  class="text-[12px] text-slate-400 leading-snug truncate max-w-xs"
                  :title="record.description"
                >
                  {{ record.description }}
                </div>
              </td>

              <td class="px-5 py-4 align-top">
                <span class="tag-pill">{{ record.category_name }}</span>
              </td>

              <td class="px-5 py-4 align-top">
                <span
                  :class="getSeverityBgClass(record.severity)"
                  class="tag-pill whitespace-nowrap"
                >
                  {{ getSeverityLabel(record.severity) }}
                </span>
              </td>

              <td class="px-5 py-4 align-top">
                <span
                  v-if="record.rule_count > 0"
                  class="font-medium text-slate-700"
                >{{
                  formatNumberCount(record.rule_count)
                }}</span>
                <span
                  v-else
                  class="text-[12px] text-indigo-500/80 font-medium flex items-center gap-1"
                >
                  <svg
                    class="w-3.5 h-3.5"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path
                      d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"
                    />
                  </svg>
                  AI 动态
                </span>
              </td>

              <td class="px-5 py-4 align-top">
                <div
                  v-if="record.example"
                  class="flex flex-col gap-1.5 text-[12px] font-mono"
                >
                  <template
                    v-for="(item, idx) in parseExamples(record.example)"
                    :key="idx"
                  >
                    <div
                      v-if="item.type === 'pass'"
                      class="flex items-center gap-1.5 w-fit px-1.5 py-0.5 rounded bg-slate-50 border border-slate-100/80 text-slate-600"
                    >
                      <svg
                        class="w-3 h-3 text-emerald-500/80 shrink-0"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          stroke-linecap="round"
                          stroke-linejoin="round"
                          stroke-width="2.5"
                          d="M5 13l4 4L19 7"
                        />
                      </svg>
                      <span
                        class="line-clamp-1"
                        :title="item.text"
                      >{{ item.text }}</span>
                    </div>
                    <div
                      v-else
                      class="flex items-center gap-1.5 w-fit px-1.5 py-0.5 rounded bg-slate-50 border border-slate-100/80 text-slate-500"
                    >
                      <svg
                        class="w-3 h-3 text-rose-400/80 shrink-0"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          stroke-linecap="round"
                          stroke-linejoin="round"
                          stroke-width="2.5"
                          d="M6 18L18 6M6 6l12 12"
                        />
                      </svg>
                      <span
                        class="line-through decoration-slate-300 line-clamp-1"
                        :title="item.text"
                      >{{ item.text }}</span>
                    </div>
                  </template>
                </div>
                <span
                  v-else
                  class="text-slate-300"
                >—</span>
              </td>

              <td
                class="px-5 py-4 align-top text-right"
                @click.stop
              >
                <button
                  :class="
                    record.is_active
                      ? 'bg-blue-500 border-transparent'
                      : 'bg-slate-200 border-transparent'
                  "
                  class="relative inline-flex h-4 w-7 shrink-0 cursor-pointer rounded-full border-2 transition-colors focus:outline-none"
                  @click="record.is_active = !record.is_active"
                >
                  <span
                    :class="record.is_active ? 'translate-x-3' : 'translate-x-0'"
                    class="inline-block h-3 w-3 transform rounded-full bg-white shadow-sm ring-0 transition"
                  />
                </button>
              </td>
            </tr>

            <tr v-if="filteredRules.length === 0 && !loading">
              <td
                colspan="7"
                class="px-5 py-12 text-center text-slate-400 text-sm"
              >
                暂无匹配数据
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- 规则编辑器抽屉 -->
    <RuleEditorDrawer
      v-model:open="drawerVisible"
      :record="currentRecord"
      @save="handleSaveRule"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { message } from 'ant-design-vue'
import RuleEditorDrawer from './RuleEditorDrawer.vue'

interface CodingRule {
  rule_id: string
  name: string
  category: string
  category_name: string
  description: string
  severity: string
  source: string
  source_name: string
  is_active: boolean
  example: string
  rule_count: number
  version: string
}

interface Statistics {
  total_types: number
  total_rule_count: number
  categories: number
  severity_counts: Record<string, number>
  source_counts: Record<string, number>
}

// 响应式数据
const loading = ref(false)
const allRules = ref<CodingRule[]>([]) // Store all rules
const statistics = reactive<Statistics>({
  total_types: 0,
  total_rule_count: 0,
  categories: 0,
  severity_counts: {},
  source_counts: {},
})
const searchText = ref('')
const filterCategory = ref<string>()
const filterSeverity = ref<string>()
const filterSource = ref<string>()

const drawerVisible = ref(false)
const currentRecord = ref<CodingRule | {}>({})

const editRule = (record: CodingRule) => {
  currentRecord.value = { ...record }
  drawerVisible.value = true
}

const handleSaveRule = (updatedRecord: any) => {
  message.success(`规则 [${updatedRecord.rule_id}] 配置已保存并发布！`)
  const idx = allRules.value.findIndex((r) => r.rule_id === updatedRecord.rule_id)
  if (idx > -1) {
    allRules.value[idx] = { ...allRules.value[idx], ...updatedRecord }
  }
}

// 分类选项（从数据动态生成）
const categoryOptions = computed(() => {
  const cats = new Map<string, string>()
  allRules.value.forEach((r) => {
    if (!cats.has(r.category)) {
      cats.set(r.category, r.category_name)
    }
  })
  return Array.from(cats.entries()).map(([value, label]) => ({ value, label }))
})

// 过滤后的规则列表
const filteredRules = computed(() => {
  let filtered = allRules.value

  if (searchText.value) {
    const keyword = searchText.value.toLowerCase()
    filtered = filtered.filter(
      (rule) =>
        rule.rule_id.toLowerCase().includes(keyword) ||
        rule.name.toLowerCase().includes(keyword) ||
        rule.description.toLowerCase().includes(keyword),
    )
  }

  if (filterCategory.value) {
    filtered = filtered.filter((rule) => rule.category === filterCategory.value)
  }

  if (filterSeverity.value) {
    filtered = filtered.filter((rule) => rule.severity === filterSeverity.value)
  }

  if (filterSource.value) {
    filtered = filtered.filter((rule) => rule.source === filterSource.value)
  }

  return filtered
})

// 表格列
const columns = [
  { title: '编号', dataIndex: 'rule_id', key: 'rule_id', width: 100 },
  { title: '规则名称', dataIndex: 'name', key: 'name', ellipsis: true },
  { title: '分类', dataIndex: 'category_name', key: 'category_name', width: 110 },
  { title: '严重度', dataIndex: 'severity', key: 'severity', width: 90 },
  { title: '来源', dataIndex: 'source_name', key: 'source_name', width: 110 },
  {
    title: '条目数',
    dataIndex: 'rule_count',
    key: 'rule_count',
    width: 90,
    align: 'right' as const,
  },
  { title: '示例', dataIndex: 'example', key: 'example', ellipsis: true, width: 200 },
  { title: '状态', dataIndex: 'is_active', key: 'is_active', width: 70, align: 'center' as const },
]

// 工具函数
const formatNumberSplit = (n: number) => {
  if (n >= 10000) return [(n / 10000).toFixed(1), '万+']
  if (n >= 1000) return [(n / 1000).toFixed(1), 'k+']
  return [String(n), '']
}

const formatNumberCount = (n: number) => {
  if (n >= 10000) return `${(n / 10000).toFixed(1)}万+`
  return String(n)
}

const PASS_MARKERS = ['✅', '✔', '☑️']
const FAIL_MARKERS = ['❌', '✘', '✗', '❎', '×']

const stripMarkerPrefix = (text: string, markers: string[]) => {
  const marker = markers.find((prefix) => text.startsWith(prefix))
  return marker ? text.slice(marker.length).trim() : text
}

// 解析示例文本为结构化数组
// 支持格式: "✅ E11.900 (正确格式) | ❌ e11.900 (大小写错误) | ❌ 11.900"
// 也支持: "✅ ... VS ❌ ..." 和纯文本
const parseExamples = (text: string): Array<{ type: 'pass' | 'fail'; text: string }> => {
  if (!text) return []

  // 先按竖线分隔
  const parts = text.split(/\s*[|｜]\s*/).filter(Boolean)

  const results: Array<{ type: 'pass' | 'fail'; text: string }> = []

  for (const part of parts) {
    const trimmed = part.trim()
    if (!trimmed) continue

    // 检测 ✅/✔/正确 前缀 → pass
    if (PASS_MARKERS.some((prefix) => trimmed.startsWith(prefix))) {
      results.push({ type: 'pass', text: stripMarkerPrefix(trimmed, PASS_MARKERS) })
    }
    // 检测 ❌/✘/✗/❎ 前缀 → fail
    else if (FAIL_MARKERS.some((prefix) => trimmed.startsWith(prefix))) {
      results.push({ type: 'fail', text: stripMarkerPrefix(trimmed, FAIL_MARKERS) })
    }
    // 无前缀 → 基于位置推断（第一个是 pass，其余 fail）
    else {
      results.push({ type: results.length === 0 ? 'pass' : 'fail', text: trimmed })
    }
  }

  // 只显示前两个示例，避免过于拥挤
  return results.slice(0, 2)
}

const getSeverityBgClass = (s: string) => {
  return (
    {
      error: 'bg-rose-50 text-rose-600',
      warning: 'bg-amber-50 text-amber-600',
      info: 'bg-blue-50 text-blue-600',
    }[s] || 'bg-slate-50 text-slate-600'
  )
}

const getCategoryColor = (cat: string) => {
  const map: Record<string, string> = {
    format: 'blue',
    existence: 'cyan',
    consistency: 'green',
    primary_diagnosis: 'orange',
    merge: 'purple',
    exclusion: 'red',
    specificity: 'geekblue',
    additional: 'magenta',
    primary_surgery: 'volcano',
    cost_logic: 'gold',
    ai_semantic: 'purple',
  }
  return map[cat] || 'default'
}

const getSeverityColor = (s: string) => {
  return { error: 'red', warning: 'orange', info: 'blue' }[s] || 'default'
}

const getSeverityLabel = (s: string) => {
  return { error: '严重', warning: '警告', info: '提示' }[s] || s
}

const severityPercent = (s: string) => {
  const total =
    (statistics.severity_counts?.error || 0) +
      (statistics.severity_counts?.warning || 0) +
      (statistics.severity_counts?.info || 0) || 1
  const count = statistics.severity_counts?.[s] || 0
  return `${Math.round((count / total) * 100)}%`
}

// 搜索防抖
let searchTimer: ReturnType<typeof setTimeout> | null = null
const handleSearch = () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => fetchRules(), 300)
}

// 加载数据
const fetchRules = async () => {
  loading.value = true
  try {
    const params = new URLSearchParams()
    if (searchText.value) params.set('keyword', searchText.value)
    if (filterCategory.value) params.set('category', filterCategory.value)
    if (filterSeverity.value) params.set('severity', filterSeverity.value)
    if (filterSource.value) params.set('source', filterSource.value)

    const resp = await fetch(`/api/v1/qc/coding-rules?${params.toString()}`)
    const data = await resp.json()
    if (data.success && data.data) {
      allRules.value = data.data.items || []
      if (data.data.statistics) {
        Object.assign(statistics, data.data.statistics)
      }
    }
  } catch (e) {
    console.error('加载编码规则失败:', e)
    message.error('加载编码规则失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchRules()
})
</script>

<style scoped>
.coding-rules-tab {
  width: 100%;
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

.refresh-btn {
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

.table-scroll {
  position: relative;
  min-height: 420px;
  overflow: auto;
}

.rules-table {
  width: 100%;
  min-width: 1000px;
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

@media (max-width: 1280px) {
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
