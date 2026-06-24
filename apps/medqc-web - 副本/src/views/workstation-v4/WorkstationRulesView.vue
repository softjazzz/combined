<template>
  <div class="rules-shell min-h-screen bg-[#f5f9fc] px-4 pb-6 pt-4 font-sans xl:px-5">
    <div class="mx-auto w-full max-w-[1440px]">
      <section
        class="mb-5 rounded-[18px] border border-slate-200/80 bg-white/95 p-5 shadow-[0_14px_34px_rgba(15,23,42,0.05)]"
      >
        <div class="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div class="text-[11px] font-black uppercase tracking-[0.14em] text-slate-500">
              RULE CONTROL
            </div>
            <h1 class="mt-1 text-[28px] font-black leading-9 tracking-tight text-slate-900">
              质控规则管理
            </h1>
            <p class="mt-1 text-sm font-medium text-slate-500">
              统一管理编码、首页、结算清单和语义质控规则，支持筛选、查看和发布复核。
            </p>
          </div>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="tab in tabs"
              :key="tab.key"
              class="rules-tab"
              :class="{ active: activeTab === tab.key }"
              @click="activeTab = tab.key"
            >
              <span>{{ tab.label }}</span>
              <strong>{{ tab.count }}</strong>
            </button>
          </div>
        </div>
        <div class="mt-5 grid grid-cols-1 gap-3 md:grid-cols-4">
          <div
            v-for="metric in metrics"
            :key="metric.label"
            class="rules-metric"
          >
            <span>{{ metric.label }}</span>
            <strong>{{ metric.value }}</strong>
            <small>{{ metric.desc }}</small>
          </div>
        </div>
        <div class="coverage-audit-panel">
          <div class="coverage-audit-head">
            <div>
              <strong>规则覆盖审计</strong>
              <span>首页与医保结算清单正式规则按标准来源、适用对象、分类和字段维度统计。</span>
            </div>
            <button
              type="button"
              class="coverage-refresh"
              @click="loadRuleCoverage"
            >
              刷新覆盖
            </button>
          </div>
          <div class="coverage-audit-grid">
            <div
              v-for="item in coverageCards"
              :key="item.label"
              class="coverage-card"
            >
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
              <small>{{ item.desc }}</small>
            </div>
          </div>
          <div
            v-if="coverageGapItems.length"
            class="coverage-gap-list"
          >
            <span>待补覆盖</span>
            <i
              v-for="gap in coverageGapItems"
              :key="gap"
            >{{ gap }}</i>
          </div>
        </div>
      </section>
      <div class="rules-panel-shell">
        <CodingRulesTab v-if="activeTab === 'coding'" />
        <FrontpageRulesTab v-else-if="activeTab === 'frontpage'" />
        <WorkstationSemanticRulesView v-else-if="activeTab === 'semantic'" />
        <SettlementRulesTab v-else />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ApiService } from '@/services/apiService'
import CodingRulesTab from '@/components/rules/CodingRulesTab.vue'
import FrontpageRulesTab from '@/components/rules/FrontpageRulesTab.vue'
import SettlementRulesTab from '@/components/rules/SettlementRulesTab.vue'
import WorkstationSemanticRulesView from '@/views/workstation-v4/WorkstationSemanticRulesView.vue'

const route = useRoute()

type TabKey = 'coding' | 'frontpage' | 'settlement' | 'semantic'
const SUPPORTED_TABS: TabKey[] = ['coding', 'frontpage', 'settlement', 'semantic']

interface RuleCoverageSummary {
  total?: number
  by_applies_to?: Record<string, number>
  by_category?: Record<string, number>
  by_field?: Record<string, number>
  missing_required_categories?: Record<string, string[]>
}

interface RuleCoverageReport {
  summary?: RuleCoverageSummary
}

const activeTab = ref<TabKey>('coding')
const ruleCoverage = ref<RuleCoverageReport | null>(null)

const tabs: Array<{ key: TabKey; label: string; count: string }> = [
  { key: 'coding', label: '编码规则', count: 'ICD' },
  { key: 'frontpage', label: '首页规则', count: 'FP' },
  { key: 'settlement', label: '结算规则', count: 'SET' },
  { key: 'semantic', label: '语义规则', count: 'SC' },
]

const metrics = computed(() => [
  { label: '规则类型', value: '4', desc: '编码 / 首页 / 结算 / 语义' },
  {
    label: '正式规则',
    value: String(ruleCoverage.value?.summary?.total ?? '-'),
    desc: '首页 + 医保结算清单',
  },
  {
    label: '覆盖字段',
    value: String(Object.keys(ruleCoverage.value?.summary?.by_field || {}).length || '-'),
    desc: '按字段审计覆盖',
  },
  { label: '安全边界', value: '不写病历', desc: '规则管理不改业务数据' },
])

const coverageCards = computed(() => {
  const summary = ruleCoverage.value?.summary || {}
  const byTarget = summary.by_applies_to || {}
  const byCategory = summary.by_category || {}
  return [
    { label: '病案首页规则', value: String(byTarget.frontpage ?? 0), desc: '卫健委首页标准' },
    { label: '结算清单规则', value: String(byTarget.settlement ?? 0), desc: '医保结算待遇清单' },
    { label: '完整性规则', value: String(byCategory.required ?? 0), desc: '必填字段覆盖' },
    {
      label: '逻辑/一致性',
      value: String((byCategory.logic ?? 0) + (byCategory.consistency ?? 0)),
      desc: '字段间内涵审查',
    },
  ]
})

const coverageGapItems = computed(() => {
  const missing = ruleCoverage.value?.summary?.missing_required_categories || {}
  return Object.entries(missing).flatMap(([target, categories]) =>
    Array.isArray(categories) ? categories.map((category) => `${target}: ${category}`) : [],
  )
})

const resolveTab = (tab: string | undefined): TabKey => {
  if (tab && SUPPORTED_TABS.includes(tab as TabKey)) {
    return tab as TabKey
  }
  return 'coding'
}

async function loadRuleCoverage() {
  try {
    const response = await ApiService.get('/api/v1/qc/formal-qc/rule-coverage')
    ruleCoverage.value = response?.data || response || null
  } catch (error) {
    ruleCoverage.value = null
  }
}

onMounted(() => {
  activeTab.value = resolveTab(route.query.tab as string | undefined)
  void loadRuleCoverage()
})

watch(
  () => route.query.tab,
  (newTab) => {
    activeTab.value = resolveTab(newTab as string | undefined)
  },
)
</script>

<style scoped>
.rules-shell :deep(.ant-card),
.rules-shell :deep(.rule-card) {
  border-radius: 18px;
  border-color: rgba(226, 232, 240, 0.85);
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.04);
}

.rules-panel-shell {
  min-width: 0;
}

.rules-tab {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 36px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #f8fbff;
  padding: 0 12px;
  color: #64748b;
  font-size: 13px;
  font-weight: 800;
  transition: all 0.18s ease;
}

.rules-tab.active {
  border-color: #bfdbfe;
  background: #eaf2ff;
  color: #2563eb;
}

.rules-tab strong {
  color: inherit;
  font-size: 12px;
  font-weight: 900;
}

.rules-metric {
  display: flex;
  min-height: 82px;
  flex-direction: column;
  justify-content: center;
  border: 1px solid rgba(226, 232, 240, 0.9);
  border-radius: 14px;
  background: #ffffff;
  padding: 14px 16px;
}

.rules-metric span {
  color: #64748b;
  font-size: 13px;
  font-weight: 800;
}

.rules-metric strong {
  margin-top: 3px;
  color: #0f172a;
  font-size: 24px;
  font-weight: 900;
  line-height: 30px;
}

.rules-metric small {
  margin-top: 2px;
  color: #94a3b8;
  font-size: 12px;
  font-weight: 600;
}

.coverage-audit-panel {
  margin-top: 14px;
  border: 1px solid rgba(191, 219, 254, 0.95);
  border-radius: 14px;
  background: #f8fbff;
  padding: 14px;
}

.coverage-audit-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.coverage-audit-head strong {
  display: block;
  color: #0f172a;
  font-size: 15px;
  font-weight: 900;
}

.coverage-audit-head span {
  display: block;
  margin-top: 2px;
  color: #64748b;
  font-size: 13px;
  font-weight: 600;
}

.coverage-refresh {
  min-height: 32px;
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  background: #ffffff;
  color: #2563eb;
  cursor: pointer;
  font-size: 13px;
  font-weight: 800;
  padding: 0 12px;
}

.coverage-audit-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-top: 12px;
}

.coverage-card {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #ffffff;
  padding: 12px;
}

.coverage-card span,
.coverage-card small {
  display: block;
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
}

.coverage-card strong {
  display: block;
  margin: 4px 0 2px;
  color: #2563eb;
  font-size: 22px;
  font-weight: 900;
  line-height: 28px;
}

.coverage-gap-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.coverage-gap-list span,
.coverage-gap-list i {
  border-radius: 999px;
  font-size: 12px;
  font-style: normal;
  font-weight: 800;
  padding: 4px 9px;
}

.coverage-gap-list span {
  background: #fff7ed;
  color: #c2410c;
}

.coverage-gap-list i {
  background: #ffffff;
  color: #64748b;
}

@media (max-width: 980px) {
  .coverage-audit-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>

<style>
@import './styles/workstation-v4-view.css';
</style>
