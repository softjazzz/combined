<template>
  <main class="staff-analysis">
    <header class="page-head">
      <div>
        <h1>质控员工作分析</h1>
      </div>
      <button class="refresh-button" type="button" :disabled="loading" @click="loadReport">
        <RefreshCw :size="16" />刷新
      </button>
    </header>

    <section class="filters" aria-label="工作分析筛选">
      <div class="filter-field">
        <span class="filter-label">统计周期</span>
        <div class="segmented" role="group" aria-label="统计周期">
          <button
            v-for="option in periodOptions"
            :key="option.value"
            type="button"
            :class="{ active: period === option.value }"
            :aria-pressed="period === option.value"
            @click="period = option.value"
          >{{ option.label }}</button>
        </div>
      </div>
      <div class="filter-field">
        <span class="filter-label">质控场景</span>
        <div class="segmented" role="group" aria-label="质控场景">
          <button
            v-for="option in sceneOptions"
            :key="option.value"
            type="button"
            :class="{ active: scene === option.value }"
            :aria-pressed="scene === option.value"
            @click="setScene(option.value)"
          >{{ option.label }}</button>
        </div>
      </div>
    </section>

    <div v-if="loading" class="state-message" role="status">正在读取质控员工作数据…</div>
    <div v-else-if="errorMessage" class="state-message error" role="alert" data-testid="staff-error">
      <CircleAlert :size="18" />{{ errorMessage }}
    </div>
    <template v-else-if="report">
      <div v-if="report.unavailable_reason" class="state-message unavailable" data-testid="staff-unavailable">
        <CircleAlert :size="18" />{{ unavailableText(report.unavailable_reason) }}
      </div>
      <template v-else-if="report.summary && report.staff">
        <section class="overview" aria-label="工作量总览">
          <div class="section-title">
            <h2>工作量总览</h2>
            <span>{{ report.period_label }} · 全部工作记录</span>
          </div>
          <p class="range-label">{{ rangeLabel(report.range) }}</p>
          <div class="metric-grid">
            <div v-for="metric in summaryMetrics" :key="metric.label" class="metric">
              <span>{{ metric.label }}</span>
              <strong>{{ metric.value }}</strong>
              <small>{{ metric.note }}</small>
            </div>
          </div>
          <div class="metric-note">
            病历份数按机构、患者、就诊三坐标去重；审核次数按初审和复审决定计数。
            全局病历份数独立去重，不等于各质控员份数之和。排名按审核次数排列。
          </div>
        </section>

        <section class="details" aria-label="人员明细">
          <div class="section-title">
            <h2>人员明细</h2>
            <span>共 {{ report.staff.length }} 人有工作记录</span>
          </div>
          <div v-if="report.staff.length" class="table-scroll">
            <table>
              <thead>
                <tr>
                  <th scope="col">排名</th>
                  <th scope="col">操作人</th>
                  <th scope="col">病历份数</th>
                  <th scope="col">审核次数</th>
                  <th scope="col">初审</th>
                  <th scope="col">复审</th>
                  <th scope="col">补录缺陷</th>
                  <th scope="col">缺陷审核通过</th>
                  <th scope="col">缺陷驳回</th>
                  <th scope="col">申诉通过</th>
                  <th scope="col">申诉驳回</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="staff in report.staff" :key="staff.user_id">
                  <td class="rank">{{ staff.rank }}</td>
                  <td class="name">{{ staff.name || staff.user_id }}</td>
                  <td>{{ staff.reviewed_case_count }}</td>
                  <td>{{ staff.record_review_count }}</td>
                  <td>{{ staff.initial_count }}</td>
                  <td>{{ staff.recheck_count }}</td>
                  <td>{{ staff.manual_defect_created_count }}</td>
                  <td>{{ staff.manual_review_approved_count }}</td>
                  <td>{{ staff.manual_review_rejected_count }}</td>
                  <td>{{ staff.appeal_approved_count }}</td>
                  <td>{{ staff.appeal_rejected_count }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-else class="empty-state">该周期暂无可核实的工作记录</div>
        </section>
      </template>
      <div v-else class="state-message unavailable">工作数据暂不可用</div>
    </template>
  </main>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { CircleAlert, RefreshCw } from 'lucide-vue-next'
import { getStaffAnalysis } from '@/api/staffAnalysis'
import type {
  StaffAnalysisPeriod,
  StaffAnalysisReport,
  StaffAnalysisScene,
} from '@/api/staffAnalysis'

const periodOptions: Array<{ value: StaffAnalysisPeriod; label: string }> = [
  { value: 'this_week', label: '本周' },
  { value: 'last_week', label: '上周' },
  { value: 'this_month', label: '本月' },
]
const sceneOptions: Array<{ value: StaffAnalysisScene; label: string }> = [
  { value: 'all', label: '全部场景' },
  { value: 'running', label: '运行质控' },
  { value: 'final', label: '终末质控' },
]
const route = useRoute()
const router = useRouter()
const scene = computed<StaffAnalysisScene>(() => {
  if (route.query.scene === 'running' || route.query.scene === 'final') return route.query.scene
  return 'all'
})
const period = ref<StaffAnalysisPeriod>('this_month')
const report = ref<StaffAnalysisReport | null>(null)
const loading = ref(false)
const errorMessage = ref('')
let requestVersion = 0

const summaryMetrics = computed(() => {
  const summary = report.value?.summary
  if (!summary) return []
  return [
    { label: '审核病历', value: summary.reviewed_case_count, note: '全局三坐标去重' },
    { label: '审核次数', value: summary.record_review_count, note: `初审 ${summary.initial_count} · 复审 ${summary.recheck_count}` },
    { label: '人均审核病历', value: summary.avg_reviewed_cases_per_reviewer ?? '不可用', note: `各人病历数合计 / ${summary.record_reviewer_count} 名审核人员` },
    { label: '活跃工作人数', value: summary.active_staff_count, note: '周期内有可核实工作动作' },
    { label: '补录人工缺陷', value: summary.manual_defect_created_count, note: '按创建动作计数' },
    { label: '人工缺陷审核', value: summary.manual_review_approved_count + summary.manual_review_rejected_count, note: `通过 ${summary.manual_review_approved_count} · 驳回 ${summary.manual_review_rejected_count}` },
    { label: '申诉处理', value: summary.appeal_approved_count + summary.appeal_rejected_count, note: `通过 ${summary.appeal_approved_count} · 驳回 ${summary.appeal_rejected_count}` },
  ]
})

function unavailableText(reason: string): string {
  if (reason === 'scene_not_attributable') {
    return '现有审核、人工缺陷和申诉记录不能可靠区分运行与终末场景，暂无该场景的质控员统计。'
  }
  return '该场景的质控员工作分析暂不可用。'
}

function rangeLabel(range: StaffAnalysisReport['range']): string {
  const formatter = new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
    hour12: false,
  })
  const parseUtc = (value: string) => new Date(/[zZ]|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`)
  const start = parseUtc(range.start)
  const end = parseUtc(range.end)
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return '统计时间暂不可用'
  return `统计时间：${formatter.format(start)} 至 ${formatter.format(end)}（北京时间，结束时间不含）`
}

function setScene(value: StaffAnalysisScene) {
  if (scene.value === value) return
  void router.replace({ path: route.path, query: { ...route.query, scene: value } })
}

async function loadReport() {
  const version = ++requestVersion
  const requestedPeriod = period.value
  const requestedScene = scene.value
  report.value = null
  errorMessage.value = ''
  loading.value = true
  const result = await getStaffAnalysis(requestedPeriod, requestedScene)
  if (version !== requestVersion) return
  loading.value = false
  if (!result.success || !result.data) {
    errorMessage.value = result.message || '质控员工作分析暂不可用'
    return
  }
  report.value = result.data
}

watch([period, scene], () => { void loadReport() }, { immediate: true })
</script>

<style scoped>
.staff-analysis { min-height: 100%; padding: 24px; background: #f5f5f7; color: #1d1d1f; font-family: 'Source Han Sans SC', 'Microsoft YaHei UI', 'PingFang SC', sans-serif; }
.page-head, .section-title { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; }
.page-head { margin-bottom: 20px; }
h1, h2, p { margin: 0; }
h1 { font-size: 24px; line-height: 31px; font-weight: 600; }
.section-title span { margin-top: 4px; color: rgba(29, 29, 31, .6); font-size: 14px; line-height: 22px; }
h2 { font-size: 17px; line-height: 22px; font-weight: 600; }
.refresh-button { display: inline-flex; align-items: center; gap: 7px; min-height: 36px; padding: 0 12px; border: 1px solid rgba(0, 0, 0, .1); border-radius: 8px; background: #fff; color: #1d1d1f; cursor: pointer; white-space: nowrap; }
.refresh-button:disabled { opacity: .55; cursor: default; }
.filters { display: flex; flex-wrap: wrap; gap: 14px 28px; align-items: end; padding: 18px 20px; margin-bottom: 20px; border: 1px solid rgba(255, 255, 255, .85); border-radius: 8px; background: rgba(255, 255, 255, .72); box-shadow: 0 4px 18px rgba(38, 58, 86, .04); }
.filter-field { display: grid; gap: 6px; }
.filter-label { font-size: 14px; line-height: 22px; color: rgba(29, 29, 31, .6); }
.segmented { display: flex; padding: 3px; background: #e8e8ed; border-radius: 8px; }
.segmented button { min-height: 32px; padding: 0 12px; border: 0; border-radius: 6px; background: transparent; color: rgba(29, 29, 31, .7); font: inherit; font-size: 14px; cursor: pointer; white-space: nowrap; }
.segmented button.active { background: #fff; color: #007aff; box-shadow: 0 1px 3px rgba(0, 0, 0, .08); }
.state-message { display: flex; align-items: center; gap: 10px; padding: 20px; border-radius: 8px; background: #fff; font-size: 14px; }
.state-message.error { color: #b42318; }
.state-message.unavailable { border: 1px solid rgba(245, 158, 11, .28); color: #875d12; }
.overview { margin-bottom: 24px; }
.section-title { align-items: baseline; margin-bottom: 12px; }
.range-label { margin: 0 0 12px; color: rgba(29, 29, 31, .6); font-size: 13px; line-height: 20px; }
.metric-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
.metric { display: grid; gap: 5px; min-height: 96px; padding: 14px 16px; background: #fff; border: 1px solid rgba(0, 0, 0, .08); border-radius: 8px; }
.metric span { font-size: 14px; color: rgba(29, 29, 31, .6); }
.metric strong { font-size: 22px; line-height: 27px; font-weight: 600; color: #007aff; }
.metric small { font-size: 12px; line-height: 18px; color: rgba(29, 29, 31, .6); }
.metric-note { margin-top: 10px; font-size: 13px; line-height: 20px; color: rgba(29, 29, 31, .6); }
.details { background: #fff; }
.details .section-title { padding: 16px 18px; margin: 0; border-bottom: 1px solid rgba(0, 0, 0, .08); }
.table-scroll { overflow-x: auto; }
table { width: 100%; min-width: 1120px; border-collapse: collapse; font-size: 14px; line-height: 22px; }
th, td { padding: 11px 14px; text-align: right; white-space: nowrap; border-bottom: 1px solid rgba(0, 0, 0, .06); }
th { background: #fafafa; color: rgba(29, 29, 31, .6); font-weight: 400; }
tbody tr:hover { background: rgba(0, 0, 0, .025); }
tbody tr:last-child td { border-bottom: 0; }
th:first-child, td:first-child, th:nth-child(2), td:nth-child(2) { text-align: left; }
.rank { color: rgba(29, 29, 31, .6); }
.name { font-weight: 600; }
.empty-state { padding: 32px; text-align: center; color: rgba(29, 29, 31, .6); }
@media (max-width: 900px) { .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 600px) { .staff-analysis { padding: 16px; } .page-head { align-items: flex-start; } .metric-grid { grid-template-columns: 1fr; } .filters { padding: 14px; } .segmented button { padding: 0 9px; } }
</style>
