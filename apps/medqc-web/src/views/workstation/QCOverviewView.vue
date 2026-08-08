<template>
  <div class="qc-home-shell workstation-shell min-h-screen">
    <div class="custom-scrollbar h-screen overflow-y-auto px-5 py-7 xl:px-8">
      <main class="qc-home-canvas mx-auto w-full max-w-[1440px]">
        <section class="qc-home-header workstation-surface-enter">
          <div>
            <h1>质控首页概览</h1>
            <p>查看全院病历的泸县0609质控结果，并优先处理需要复核的病历。</p>
          </div>
          <HomeHeroBar
            v-model:keyword="keyword"
            v-model:department-filter="departmentFilter"
            :selected-date="selectedDate"
            workflow-filter="all"
            :department-options="departmentOptions"
            :loading="loading"
            :disabled-future-date="disabledFutureDate"
            :show-date="false"
            :show-workflow="false"
            @refresh="void fetchHome()"
          />
        </section>

        <section
          v-if="loadError"
          class="qc-home-notice qc-home-notice--error"
          data-testid="home-load-error"
        >
          <strong>暂时无法加载质控首页</strong>
          <span>请稍后刷新；不会以旧任务或缓存数据替代当前结果。</span>
          <a-button
            size="small"
            @click="void fetchHome()"
          >
            重新加载
          </a-button>
        </section>

        <template v-else-if="clinicalQc">
          <section
            class="qc-home-scope workstation-surface-enter"
            data-testid="home-scope"
          >
            <span class="qc-home-scope__label">当前范围</span>
            <span>{{ scopeHospitalText }}</span>
            <i />
            <span>{{ scopeDepartmentText }}</span>
            <i />
            <span>{{ scopeSceneText }}</span>
            <i />
            <span>{{ clinicalQc.scope.rule_set_key }} · {{ clinicalQc.scope.rule_set_version }}</span>
            <span class="qc-home-scope__time">生成于 {{ formatDateTime(clinicalQc.scope.generated_at) }}</span>
          </section>

          <section
            class="qc-home-kpis workstation-surface-enter"
            data-testid="home-kpis"
          >
            <article
              v-for="card in kpiCards"
              :key="card.key"
              :class="['qc-home-kpi', `is-${card.tone}`]"
            >
              <component
                :is="card.icon"
                class="qc-home-kpi__icon"
              />
              <div>
                <span>{{ card.label }}</span>
                <strong>{{ card.value }}</strong>
                <small>{{ card.desc }}</small>
              </div>
            </article>
          </section>

          <section class="qc-home-grid workstation-surface-enter">
            <section
              class="qc-home-panel"
              data-testid="priority-queue"
            >
              <header class="qc-home-panel__head">
                <div>
                  <h2>优先复核</h2>
                  <p>按确定问题、资料待核实、待判断的结构化结果排序。</p>
                </div>
                <a-button
                  type="link"
                  @click="openRecordPool"
                >
                  查看病历池
                </a-button>
              </header>

              <div
                v-if="clinicalQc.priority_items.length"
                class="qc-home-priority-list"
              >
                <article
                  v-for="item in clinicalQc.priority_items"
                  :key="item.record_key"
                  class="qc-home-priority-row"
                >
                  <div class="qc-home-priority-row__identity">
                    <strong>{{ item.patient_name || '未返回患者姓名' }}</strong>
                    <span>{{ item.department || '未分科室' }} · 住院号 {{ item.visit_id }}</span>
                  </div>
                  <div class="qc-home-priority-row__counts">
                    <span
                      v-if="countOf(item, 'non_compliant')"
                      class="is-danger"
                    >
                      确定问题 {{ countOf(item, 'non_compliant') }} 项
                    </span>
                    <span
                      v-if="countOf(item, 'data_gap')"
                      class="is-warning"
                    >
                      资料待核实 {{ countOf(item, 'data_gap') }} 项
                    </span>
                    <span
                      v-if="countOf(item, 'uncertain')"
                      class="is-neutral"
                    >
                      待判断 {{ countOf(item, 'uncertain') }} 项
                    </span>
                  </div>
                  <button
                    type="button"
                    class="qc-home-text-action"
                    @click="openRecordPool"
                  >
                    进入病历池
                  </button>
                </article>
              </div>
              <a-empty
                v-else
                description="当前范围内没有需要优先复核的病历"
                :image-style="{ height: '72px' }"
              />
            </section>

            <aside class="qc-home-side-stack">
              <section
                class="qc-home-panel qc-home-panel--health"
                data-testid="data-health"
              >
                <header class="qc-home-panel__head">
                  <div>
                    <h2>数据运行状态</h2>
                    <p>系统数据状态不等同于医疗质控结论。</p>
                  </div>
                </header>
                <dl class="qc-home-health-list">
                  <div>
                    <dt>资料同步状态</dt>
                    <dd>{{ sourceStateText }}</dd>
                  </div>
                  <div>
                    <dt>运行中任务</dt>
                    <dd>{{ runningTaskText }}</dd>
                  </div>
                  <div>
                    <dt>技术异常</dt>
                    <dd :class="{ 'is-danger': clinicalQc.data_health.technical_error_total > 0 }">
                      技术异常 {{ clinicalQc.data_health.technical_error_total }} 份
                    </dd>
                  </div>
                  <div>
                    <dt>最近成功质控</dt>
                    <dd>{{ formatDateTime(clinicalQc.data_health.last_successful_qc_at) }}</dd>
                  </div>
                </dl>
              </section>

              <section
                class="qc-home-panel"
                data-testid="department-distribution"
              >
                <header class="qc-home-panel__head">
                  <div>
                    <h2>科室分布</h2>
                    <p>高风险待复核按科室汇总。</p>
                  </div>
                </header>
                <div
                  v-if="clinicalQc.department_distribution.length"
                  class="qc-home-department-list"
                >
                  <div
                    v-for="item in clinicalQc.department_distribution"
                    :key="item.department"
                    class="qc-home-department-row"
                  >
                    <div>
                      <strong>{{ item.department }}</strong>
                      <span>纳入 {{ item.records_total }} 份病历</span>
                    </div>
                    <div>
                      <em>待复核 {{ item.high_risk_review_total }}</em>
                      <span v-if="item.data_gap_record_total">资料待核实 {{ item.data_gap_record_total }}</span>
                    </div>
                  </div>
                </div>
                <a-empty
                  v-else
                  description="当前范围内暂无科室汇总"
                  :image-style="{ height: '58px' }"
                />
              </section>
            </aside>
          </section>

          <section
            v-if="clinicalQc.trend"
            class="qc-home-panel workstation-surface-enter"
            data-testid="home-trend"
          >
            <header class="qc-home-panel__head">
              <div><h2>质控趋势</h2><p>仅在后端返回真实时间序列时展示。</p></div>
            </header>
          </section>
        </template>

        <section
          v-else-if="!loading"
          class="qc-home-empty workstation-surface-enter"
          data-testid="home-empty"
        >
          <a-empty description="当前暂无可展示的全病历质控汇总">
            <template #description>
              <p>请先在病历池完成质控；系统不会用旧工作流数据代替正式质控结果。</p>
            </template>
            <a-button
              type="primary"
              @click="openRecordPool"
            >
              进入病历池
            </a-button>
          </a-empty>
        </section>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, type Component } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import dayjs, { type Dayjs } from 'dayjs'
import { ApiService } from '@/services/apiService'
import type { ClinicalQcHomePriorityItem, WorkstationHomePayload } from '@/views/workstation-v2/types'
import { FileDoneOutlined, SafetyCertificateOutlined, SyncOutlined, WarningOutlined } from '@ant-design/icons-vue'
import HomeHeroBar from './components/HomeHeroBar.vue'

interface KpiCard {
  key: string
  label: string
  value: number
  desc: string
  tone: 'brand' | 'warning' | 'success' | 'danger'
  icon: Component
}

const router = useRouter()
const route = useRoute()
const loading = ref(false)
const loadError = ref(false)
const selectedDate = ref<Dayjs>(dayjs())
const departmentFilter = ref('all')
const keyword = ref('')
const syncingFromRoute = ref(false)
const homeData = ref<WorkstationHomePayload | null>(null)

const clinicalQc = computed(() => homeData.value?.clinical_qc ?? null)
const departmentOptions = computed(() => homeData.value?.department_options ?? [])
const scopeHospitalText = computed(() => (clinicalQc.value?.scope.hospital_scope === 'all' ? '全院' : '当前范围'))
const scopeDepartmentText = computed(() => clinicalQc.value?.scope.department || '全部科室')
const scopeSceneText = computed(() => (clinicalQc.value?.scope.scene === 'final' ? '最终结果' : clinicalQc.value?.scope.scene || '场景待确认'))

const kpiCards = computed<KpiCard[]>(() => {
  const kpis = clinicalQc.value?.kpis
  return [
    { key: 'records', label: '纳入病历', value: Number(kpis?.records_total || 0), desc: '当前范围内三坐标完整的病历', tone: 'brand', icon: FileDoneOutlined },
    { key: 'pending', label: '待质控', value: Number(kpis?.qc_pending_total || 0), desc: '尚未形成可用最终结论', tone: 'warning', icon: SyncOutlined },
    { key: 'completed', label: '已完成', value: Number(kpis?.qc_completed_total || 0), desc: '已交付 Canonical 最终结论', tone: 'success', icon: SafetyCertificateOutlined },
    { key: 'risk', label: '高风险待复核', value: Number(kpis?.high_risk_review_total || 0), desc: '至少含一项确定问题的病历', tone: 'danger', icon: WarningOutlined },
  ]
})

const sourceStateText = computed(() => clinicalQc.value?.data_health.source_sync_status === 'unknown' ? '资料同步状态待核实' : '资料同步状态待核实')
const runningTaskText = computed(() => clinicalQc.value?.data_health.running_task_state === 'unknown' ? '运行状态待接入' : '运行状态待接入')

function countOf(item: ClinicalQcHomePriorityItem, status: string): number {
  return Math.max(0, Number(item.status_counts?.[status] || 0))
}

function formatDateTime(value?: string | null): string {
  if (!value) return '暂未返回'
  const parsed = dayjs(value)
  return parsed.isValid() ? parsed.format('YYYY-MM-DD HH:mm') : '暂未返回'
}

function disabledFutureDate(current: Dayjs) {
  return current.isAfter(dayjs(), 'day')
}

function applyRouteFilters() {
  const department = typeof route.query.department === 'string' ? route.query.department : 'all'
  const queryKeyword = typeof route.query.keyword === 'string' ? route.query.keyword : ''
  syncingFromRoute.value = true
  departmentFilter.value = department || 'all'
  keyword.value = queryKeyword
  syncingFromRoute.value = false
}

function openRecordPool() {
  void router.push({
    path: '/workstation-v4',
    query: {
      source: 'dashboard',
      department: departmentFilter.value !== 'all' ? departmentFilter.value : undefined,
      keyword: keyword.value.trim() || undefined,
    },
  })
}

async function fetchHome() {
  loading.value = true
  loadError.value = false
  try {
    const res = await ApiService.get<WorkstationHomePayload>('/api/v1/workstation/home', {
      department: departmentFilter.value !== 'all' ? departmentFilter.value : undefined,
      keyword: keyword.value.trim() || undefined,
      hotspot_limit: 20,
      todo_limit: 1,
    })
    if (!res.success || !res.data?.clinical_qc) throw new Error(String(res.error || '首页聚合未返回'))
    homeData.value = res.data
  } catch {
    homeData.value = null
    loadError.value = true
  } finally {
    loading.value = false
  }
}

watch(
  () => route.fullPath,
  () => {
    applyRouteFilters()
    void fetchHome()
  },
  { immediate: true },
)

watch([departmentFilter, keyword], () => {
  if (syncingFromRoute.value) return
  void fetchHome()
})
</script>

<style scoped>
@import '../workstation-v4/styles/workstation-v4-view.css';

.qc-home-shell { background: #f5f5f7; color: #1d1d1f; }
.qc-home-canvas { display: grid; gap: 18px; min-height: calc(100vh - 64px); }
.qc-home-header, .qc-home-panel, .qc-home-scope, .qc-home-notice, .qc-home-empty {
  border: 1px solid rgba(0, 0, 0, .08); border-radius: 20px; background: rgba(255,255,255,.88); box-shadow: 0 2px 12px rgba(0,0,0,.035); backdrop-filter: blur(18px);
}
.qc-home-header { display: flex; align-items: center; justify-content: space-between; gap: 24px; padding: 22px 24px; }
.qc-home-header h1, .qc-home-panel h2 { margin: 0; font-weight: 700; }
.qc-home-header h1 { font-size: 28px; line-height: 31px; }
.qc-home-header p, .qc-home-panel p { margin: 7px 0 0; color: rgba(29,29,31,.60); font-size: 13px; line-height: 20px; }
.qc-home-scope { display: flex; align-items: center; flex-wrap: wrap; gap: 9px; padding: 12px 16px; color: rgba(29,29,31,.72); font-size: 12px; font-weight: 600; }
.qc-home-scope i { width: 3px; height: 3px; border-radius: 50%; background: rgba(29,29,31,.28); }
.qc-home-scope__label { color: #0066cc; }.qc-home-scope__time { margin-left: auto; color: rgba(29,29,31,.48); font-weight: 500; }
.qc-home-kpis { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); overflow: hidden; border: 1px solid rgba(0,0,0,.08); border-radius: 18px; background: #fff; }
.qc-home-kpi { display: flex; gap: 12px; min-height: 118px; padding: 21px; border-right: 1px solid rgba(0,0,0,.07); }.qc-home-kpi:last-child { border: 0; }
.qc-home-kpi__icon { width: 34px; height: 34px; padding: 8px; border-radius: 10px; background: rgba(0,102,204,.09); color: #0066cc; }
.qc-home-kpi.is-warning .qc-home-kpi__icon { background: rgba(245,158,11,.12); color: #b45309; }.qc-home-kpi.is-success .qc-home-kpi__icon { background: rgba(16,185,129,.11); color: #047857; }.qc-home-kpi.is-danger .qc-home-kpi__icon { background: rgba(239,68,68,.11); color: #dc2626; }
.qc-home-kpi span, .qc-home-kpi small { display:block; color: rgba(29,29,31,.6); font-size:12px; line-height:18px; }.qc-home-kpi strong { display:block; margin:3px 0; font-size:25px; line-height:30px; }.qc-home-kpi small { color: rgba(29,29,31,.48); }
.qc-home-grid { display:grid; grid-template-columns:minmax(0,1.55fr) minmax(310px,.85fr); gap:18px; }.qc-home-panel { padding:20px 22px; }.qc-home-side-stack { display:grid; gap:18px; align-content:start; }.qc-home-panel__head { display:flex; align-items:flex-start; justify-content:space-between; gap:16px; padding-bottom:15px; border-bottom:1px solid rgba(0,0,0,.08); }.qc-home-panel h2 { font-size:17px; line-height:22px; }
.qc-home-priority-list { display:grid; }.qc-home-priority-row { display:grid; grid-template-columns:minmax(0,1fr) auto auto; align-items:center; gap:18px; padding:16px 0; border-bottom:1px solid rgba(0,0,0,.07); }.qc-home-priority-row:last-child { border-bottom:0; }.qc-home-priority-row__identity { min-width:0; }.qc-home-priority-row__identity strong, .qc-home-priority-row__identity span { display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }.qc-home-priority-row__identity strong { font-size:14px; }.qc-home-priority-row__identity span { margin-top:4px; color:rgba(29,29,31,.55); font-size:12px; }.qc-home-priority-row__counts { display:flex; flex-wrap:wrap; justify-content:flex-end; gap:6px; }.qc-home-priority-row__counts span { padding:3px 7px; border-radius:7px; background:rgba(0,0,0,.04); color:rgba(29,29,31,.68); font-size:12px; white-space:nowrap; }.qc-home-priority-row__counts .is-danger { background:rgba(239,68,68,.09); color:#c2410c; }.qc-home-priority-row__counts .is-warning { background:rgba(245,158,11,.11); color:#a16207; }.qc-home-text-action { border:0; background:none; color:#0066cc; font-size:13px; font-weight:600; cursor:pointer; }
.qc-home-health-list { display:grid; gap:0; margin:0; }.qc-home-health-list > div { display:flex; justify-content:space-between; gap:12px; padding:11px 0; border-bottom:1px solid rgba(0,0,0,.07); }.qc-home-health-list > div:last-child { border-bottom:0; }.qc-home-health-list dt, .qc-home-health-list dd { margin:0; font-size:13px; }.qc-home-health-list dt { color:rgba(29,29,31,.6); }.qc-home-health-list dd { text-align:right; font-weight:600; }.qc-home-health-list .is-danger { color:#dc2626; }
.qc-home-department-list { display:grid; }.qc-home-department-row { display:flex; align-items:center; justify-content:space-between; gap:14px; padding:11px 0; border-bottom:1px solid rgba(0,0,0,.07); }.qc-home-department-row:last-child { border-bottom:0; }.qc-home-department-row strong, .qc-home-department-row span, .qc-home-department-row em { display:block; font-size:12px; font-style:normal; }.qc-home-department-row strong { font-size:13px; }.qc-home-department-row span { margin-top:3px; color:rgba(29,29,31,.48); }.qc-home-department-row > div:last-child { text-align:right; }.qc-home-department-row em { color:#b45309; font-weight:650; }
.qc-home-notice { display:flex; align-items:center; gap:12px; padding:14px 18px; }.qc-home-notice span { flex:1; color:rgba(29,29,31,.6); font-size:13px; }.qc-home-notice--error { border-color:rgba(239,68,68,.2); }.qc-home-notice--error strong { color:#b91c1c; }.qc-home-empty { display:grid; min-height:280px; place-items:center; padding:28px; }
@media (max-width: 980px) { .qc-home-header { align-items:flex-start; flex-direction:column; }.qc-home-header :deep(.flex.min-w-\[280px\]) { width:100%; }.qc-home-kpis { grid-template-columns:repeat(2,1fr); }.qc-home-kpi:nth-child(2) { border-right:0; }.qc-home-kpi:nth-child(-n+2) { border-bottom:1px solid rgba(0,0,0,.07); }.qc-home-grid { grid-template-columns:1fr; } }
@media (max-width: 620px) { .qc-home-canvas { gap:12px; }.qc-home-header, .qc-home-panel { padding:17px; }.qc-home-header h1 { font-size:23px; }.qc-home-kpis { grid-template-columns:1fr; }.qc-home-kpi, .qc-home-kpi:nth-child(2) { border-right:0; border-bottom:1px solid rgba(0,0,0,.07); }.qc-home-kpi:last-child { border-bottom:0; }.qc-home-priority-row { grid-template-columns:1fr; gap:9px; }.qc-home-priority-row__counts { justify-content:flex-start; }.qc-home-text-action { justify-self:start; }.qc-home-scope__time { width:100%; margin-left:0; } }
</style>
