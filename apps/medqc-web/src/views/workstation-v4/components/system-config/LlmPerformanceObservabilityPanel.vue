<template>
  <div class="llm-observability">
    <header class="llm-observability__header">
      <div>
        <span class="llm-observability__eyebrow">模型运行观测</span>
        <h2>模型性能</h2>
        <p>
          统计真实模型调用、Token 与响应表现，不记录模型输入、输出和明文病历身份；不含独立部署的
          SQLBot。
        </p>
      </div>
      <a-button
        class="llm-observability__refresh"
        :loading="loading"
        @click="loadOverview()"
      >
        <RefreshCw :size="15" />
        刷新
      </a-button>
    </header>

    <section
      class="llm-observability__filters"
      aria-label="模型性能统计范围"
    >
      <label>
        <span>统计范围</span>
        <a-select
          v-model:value="rangeKey"
          :options="rangeOptions"
          popup-class-name="llm-observability-popup"
          @change="handleFilterChange"
        />
      </label>
      <label>
        <span>服务商</span>
        <a-select
          v-model:value="providerCode"
          data-testid="provider-filter"
          :options="providerOptions"
          popup-class-name="llm-observability-popup"
          @change="handleProviderChange"
        />
      </label>
      <label>
        <span>模型</span>
        <a-select
          v-model:value="modelCode"
          data-testid="model-filter"
          :options="modelOptions"
          popup-class-name="llm-observability-popup"
          @change="handleFilterChange"
        />
      </label>
      <label>
        <span>业务场景</span>
        <a-select
          v-model:value="businessScene"
          data-testid="business-scene-filter"
          :options="sceneOptions"
          popup-class-name="llm-observability-popup"
          @change="handleFilterChange"
        />
      </label>
      <div
        v-if="overview"
        class="llm-observability__range-note"
      >
        <Clock3 :size="14" />
        {{ formatRange(overview.range.start_at, overview.range.end_at) }}
      </div>
    </section>

    <section
      v-if="errorMessage"
      class="llm-observability__state llm-observability__state--error"
      role="alert"
    >
      <CircleAlert :size="22" />
      <div>
        <strong>模型性能数据暂不可用</strong>
        <p>未展示任何推测数据。请稍后重试或确认观测服务已经接入。</p>
      </div>
      <a-button
        data-testid="retry-overview"
        @click="loadOverview()"
      >
        重新加载
      </a-button>
    </section>

    <a-spin
      v-else
      :spinning="loading"
    >
      <section
        v-if="loading && !overview"
        class="llm-observability__state llm-observability__state--loading"
        aria-live="polite"
      >
        <Activity :size="24" />
        <div>
          <strong>正在读取真实模型调用数据</strong>
          <p>正在汇总调用次数、Token、响应时间与并发情况。</p>
        </div>
      </section>

      <template v-else-if="overview">
        <section
          class="llm-observability__kpis"
          aria-label="模型性能关键指标"
        >
          <article
            v-for="item in kpiItems"
            :key="item.key"
            class="llm-observability__kpi"
          >
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
            <em>{{ item.helper }}</em>
          </article>
        </section>

        <section
          v-if="hasObservedCalls"
          class="llm-observability__health-strip"
          aria-label="调用质量摘要"
        >
          <span>成功尝试 {{ formatInteger(overview.kpis.successful_attempts) }}</span>
          <span>失败尝试 {{ formatInteger(overview.kpis.failed_attempts) }}</span>
          <span>重试 {{ formatInteger(overview.kpis.retry_attempts) }}</span>
          <span>Token 未上报 {{ formatInteger(overview.kpis.unknown_usage_attempts) }}</span>
        </section>

        <section
          v-if="hasTrendData"
          class="llm-observability__chart-grid"
        >
          <article class="llm-observability__surface">
            <div class="llm-observability__section-head">
              <div>
                <h3>调用与 Token 趋势</h3>
                <p>逻辑调用与 HTTP 尝试分开统计，重试不会被隐藏。</p>
              </div>
            </div>
            <VChart
              class="llm-observability__chart"
              :option="callTokenChartOption"
              autoresize
              data-testid="call-token-chart"
            />
          </article>

          <article class="llm-observability__surface">
            <div class="llm-observability__section-head">
              <div>
                <h3>响应与并发</h3>
                <p>P95 响应时间反映尾部等待，峰值并发按真实重叠请求计算。</p>
              </div>
            </div>
            <VChart
              class="llm-observability__chart"
              :option="latencyConcurrencyChartOption"
              autoresize
              data-testid="latency-concurrency-chart"
            />
          </article>
        </section>

        <section
          v-if="hasObservedCalls"
          class="llm-observability__distribution-grid"
        >
          <article class="llm-observability__surface">
            <div class="llm-observability__section-head">
              <div>
                <h3>模型分布</h3>
                <p>按实际 HTTP 尝试排序，便于识别主要承载模型。</p>
              </div>
            </div>
            <div
              v-if="overview.models.length"
              class="llm-observability__model-list"
            >
              <div
                v-for="item in overview.models"
                :key="modelKey(item)"
                class="llm-observability__model-row"
              >
                <div>
                  <strong>{{ item.model }}</strong>
                  <span>{{ item.provider_code }} · {{ modelRoleLabel(item.model_role) }}</span>
                </div>
                <div class="llm-observability__model-metrics">
                  <span>{{ formatInteger(item.logical_calls) }} 次调用</span>
                  <span>{{ formatInteger(item.http_attempts) }} 次尝试</span>
                  <span>
                    {{ formatNullableInteger(item.total_tokens) }}
                    {{ aggregateTokenLabel(item.unknown_usage_attempts, item.total_tokens) }}
                  </span>
                  <span>均值 {{ formatNullableDuration(item.avg_latency_ms) }}</span>
                </div>
              </div>
            </div>
            <p
              v-else
              class="llm-observability__inline-empty"
            >
              当前范围暂无模型分布数据。
            </p>
          </article>

          <article class="llm-observability__surface">
            <div class="llm-observability__section-head">
              <div>
                <h3>安全错误分布</h3>
                <p>只展示脱敏错误类别，不展示异常原文和服务地址。</p>
              </div>
            </div>
            <div
              v-if="overview.safe_errors.length"
              class="llm-observability__error-list"
            >
              <div
                v-for="item in overview.safe_errors"
                :key="item.safe_error_kind"
                class="llm-observability__error-row"
              >
                <div>
                  <span>{{ safeErrorLabel(item.safe_error_kind) }}</span>
                  <strong>{{ formatInteger(item.count) }}</strong>
                </div>
                <div class="llm-observability__error-track">
                  <i :style="{ width: errorBarWidth(item.count) }" />
                </div>
              </div>
            </div>
            <div
              v-else
              class="llm-observability__healthy-empty"
            >
              <CircleCheck :size="20" />
              当前范围没有安全错误事件
            </div>
          </article>
        </section>

        <section
          v-if="hasObservedCalls"
          class="llm-observability__surface llm-observability__records"
        >
          <div class="llm-observability__section-head">
            <div>
              <h3>单病历调用概览</h3>
              <p>病例仅以不可逆哈希短标识展示；点击查看该病例的 HTTP 尝试明细。</p>
            </div>
            <span>{{ formatInteger(overview.records.total) }} 份</span>
          </div>

          <div class="llm-observability__table-scroll">
            <table>
              <thead>
                <tr>
                  <th>病历标识</th>
                  <th>逻辑调用</th>
                  <th>HTTP 尝试</th>
                  <th>
                    {{
                      aggregateTokenLabel(
                        overview.kpis.unknown_usage_attempts,
                        overview.kpis.total_tokens,
                      )
                    }}
                  </th>
                  <th>P95 响应</th>
                  <th>最近调用</th>
                  <th>状态</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="record in overview.records.items"
                  :key="record.record_key_hash"
                >
                  <td>
                    <strong>{{ shortRecordRef(record.record_key_hash) }}</strong>
                  </td>
                  <td>{{ formatInteger(record.logical_calls) }}</td>
                  <td>{{ formatInteger(record.http_attempts) }}</td>
                  <td>{{ formatNullableInteger(record.total_tokens) }}</td>
                  <td>{{ formatNullableDuration(record.p95_latency_ms) }}</td>
                  <td>{{ formatDateTime(record.last_called_at) }}</td>
                  <td>
                    <span :class="['llm-observability__status', statusTone(record.status)]">
                      {{ recordStatusLabel(record.status) }}
                    </span>
                  </td>
                  <td>
                    <button
                      type="button"
                      class="llm-observability__link"
                      data-testid="view-record-calls"
                      @click="openRecordCalls(record.record_key_hash)"
                    >
                      查看明细
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <a-pagination
            v-if="overview.records.total > overview.records.page_size"
            :current="overview.records.page"
            :page-size="overview.records.page_size"
            :total="overview.records.total"
            :show-size-changer="false"
            @change="handleRecordPageChange"
          />
        </section>

        <section
          v-if="!hasObservedCalls"
          class="llm-observability__state llm-observability__state--empty"
        >
          <Activity :size="24" />
          <div>
            <strong>当前范围暂无真实模型调用记录</strong>
            <p>质控任务产生真实模型请求后，此处会显示调用、Token、响应时间与并发数据。</p>
          </div>
        </section>
      </template>
    </a-spin>

    <a-drawer
      :open="drawerOpen"
      :width="860"
      placement="right"
      :title="drawerTitle"
      @close="closeRecordCalls"
    >
      <div class="llm-observability__drawer-intro">
        <ShieldCheck :size="18" />
        明细不包含模型输入、响应正文、服务地址、密钥或患者三坐标。
      </div>

      <div
        v-if="detailError"
        class="llm-observability__drawer-state"
      >
        <strong>调用明细暂不可用</strong>
        <p>未展示任何推测数据，请稍后重试。</p>
      </div>
      <a-spin
        v-else
        :spinning="detailLoading"
      >
        <div
          v-if="recordCalls?.items.length"
          class="llm-observability__attempt-list"
        >
          <article
            v-for="attempt in recordCalls.items"
            :key="`${attempt.logical_call_id}-${attempt.attempt_no}`"
            class="llm-observability__attempt"
          >
            <div class="llm-observability__attempt-head">
              <div>
                <strong>{{ attempt.executor_key || '未标记执行器' }}</strong>
                <span>{{ sceneLabel(attempt.business_scene) }} · 第
                  {{ attempt.attempt_no }} 次尝试</span>
              </div>
              <span :class="['llm-observability__status', statusTone(attempt.status)]">
                {{ attemptStatusLabel(attempt.status) }}
              </span>
            </div>
            <dl>
              <div>
                <dt>模型</dt>
                <dd>{{ attempt.model }}</dd>
              </div>
              <div>
                <dt>服务商</dt>
                <dd>{{ attempt.provider_code }}</dd>
              </div>
              <div>
                <dt>Token 用量</dt>
                <dd>{{ usageStateLabel(attempt.usage_state) }}</dd>
              </div>
              <div>
                <dt>输入 Token</dt>
                <dd>{{ formatNullableInteger(attempt.input_tokens) }}</dd>
              </div>
              <div>
                <dt>输出 Token</dt>
                <dd>{{ formatNullableInteger(attempt.output_tokens) }}</dd>
              </div>
              <div>
                <dt>总 Token</dt>
                <dd>{{ formatNullableInteger(attempt.total_tokens) }}</dd>
              </div>
              <div>
                <dt>响应时间</dt>
                <dd>{{ formatNullableDuration(attempt.latency_ms) }}</dd>
              </div>
              <div>
                <dt>开始时间</dt>
                <dd>{{ formatDateTime(attempt.started_at) }}</dd>
              </div>
              <div>
                <dt>错误类别</dt>
                <dd>
                  {{ attempt.safe_error_kind ? safeErrorLabel(attempt.safe_error_kind) : '无' }}
                </dd>
              </div>
            </dl>
          </article>
          <a-pagination
            v-if="recordCalls.total > recordCalls.page_size"
            :current="recordCalls.page"
            :page-size="recordCalls.page_size"
            :total="recordCalls.total"
            :show-size-changer="false"
            @change="handleDetailPageChange"
          />
        </div>
        <div
          v-else-if="recordCalls"
          class="llm-observability__drawer-state"
        >
          当前病历暂无调用尝试记录。
        </div>
      </a-spin>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import { Activity, CircleAlert, CircleCheck, Clock3, RefreshCw, ShieldCheck } from 'lucide-vue-next'
import { getLlmObservabilityOverview, getLlmRecordCallAttempts } from '@/services/llmObservability'
import type {
  LlmObservabilityModelSummary,
  LlmObservabilityOverview,
  LlmObservabilityQuery,
  LlmRecordCallAttempts,
} from '@/types/llmObservability'

use([BarChart, LineChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer])

type RangeKey = '24h' | '7d' | '30d'

const rangeKey = ref<RangeKey>('7d')
const providerCode = ref('')
const modelCode = ref('')
const businessScene = ref('')
const overview = ref<LlmObservabilityOverview | null>(null)
const activeOverviewQuery = ref<LlmObservabilityQuery | null>(null)
const knownModelOptions = ref<Array<{ provider_code: string; model: string }>>([])
const loading = ref(false)
const errorMessage = ref('')
const drawerOpen = ref(false)
const detailLoading = ref(false)
const detailError = ref(false)
const selectedRecordHash = ref('')
const recordCalls = ref<LlmRecordCallAttempts | null>(null)
let overviewRequestSequence = 0
let detailRequestSequence = 0

const rangeOptions = [
  { label: '近 24 小时', value: '24h' },
  { label: '近 7 天', value: '7d' },
  { label: '近 30 天', value: '30d' },
]

const sceneOptions = [
  { label: '全部场景', value: '' },
  { label: '泸县 0609 病历质控', value: 'luxian_0609_qc' },
  { label: '编码质控', value: 'coding_qc' },
  { label: '首页抽取', value: 'frontpage_extraction' },
  { label: '首页报告生成', value: 'frontpage_report_generation' },
  { label: '自定义质控提示生成', value: 'custom_qc_prompt_generation' },
  { label: '兼容模型代理', value: 'legacy_llm_proxy' },
  { label: '模型配置探测', value: 'llm_config_probe' },
  { label: '泸县 0609 预生产验证', value: 'luxian_0609_preproduction' },
  { label: '智能上传字段映射', value: 'smart_upload_field_mapping' },
  { label: 'ICD 编码建议', value: 'icd_coding' },
  { label: '诊断手术画像', value: 'diagnosis_surgery_profiling' },
  { label: '质控助手意图识别', value: 'qc_agent_intent' },
  { label: '演示规则生成', value: 'demo_custom_rule_generation' },
  { label: 'ICD 语义检索', value: 'icd_semantic_embedding' },
]

const hasObservedCalls = computed(() => Number(overview.value?.kpis.http_attempts || 0) > 0)
const hasTrendData = computed(() => Boolean(overview.value?.trends.length))

const providerOptions = computed(() => {
  const values = new Set(knownModelOptions.value.map((item) => item.provider_code).filter(Boolean))
  if (providerCode.value) values.add(providerCode.value)
  return [
    { label: '全部服务商', value: '' },
    ...Array.from(values)
      .sort()
      .map((value) => ({ label: value, value })),
  ]
})

const modelOptions = computed(() => {
  const models = knownModelOptions.value.filter(
    (item) => !providerCode.value || item.provider_code === providerCode.value,
  )
  const values = new Set(models.map((item) => item.model).filter(Boolean))
  if (modelCode.value) values.add(modelCode.value)
  return [
    { label: '全部模型', value: '' },
    ...Array.from(values)
      .sort()
      .map((value) => ({ label: value, value })),
  ]
})

const kpiItems = computed(() => {
  if (!overview.value) return []
  const kpis = overview.value.kpis
  return [
    {
      key: 'logical',
      label: '逻辑调用',
      value: formatInteger(kpis.logical_calls),
      helper: '一次业务请求计一次',
    },
    {
      key: 'attempts',
      label: 'HTTP 尝试',
      value: formatInteger(kpis.http_attempts),
      helper: `含重试 ${formatInteger(kpis.retry_attempts)} 次`,
    },
    {
      key: 'records',
      label: '病历数',
      value: formatInteger(kpis.record_count),
      helper: '按脱敏病例标识去重',
    },
    {
      key: 'tokens',
      label: aggregateTokenLabel(kpis.unknown_usage_attempts, kpis.total_tokens),
      value: formatNullableInteger(kpis.total_tokens),
      helper: [
        `输入 ${formatNullableInteger(kpis.input_tokens)} · 输出 ${formatNullableInteger(kpis.output_tokens)}`,
        kpis.unknown_usage_attempts > 0
          ? `${formatInteger(kpis.unknown_usage_attempts)} 次未上报`
          : '',
      ]
        .filter(Boolean)
        .join(' · '),
    },
    {
      key: 'latency',
      label: 'P95 响应',
      value: formatNullableDuration(kpis.p95_latency_ms),
      helper: `平均 ${formatNullableDuration(kpis.avg_latency_ms)}`,
    },
    {
      key: 'concurrency',
      label: '峰值并发',
      value: formatInteger(kpis.peak_concurrency),
      helper: '按重叠 HTTP 尝试计算',
    },
  ]
})

const chartLabels = computed(() =>
  (overview.value?.trends || []).map((point) => formatBucket(point.bucket)),
)

const chartBase = {
  animationDuration: 350,
  tooltip: { trigger: 'axis', confine: true },
  legend: {
    top: 0,
    right: 0,
    textStyle: { color: 'rgba(29,29,31,.6)', fontSize: 11 },
  },
  grid: { left: 18, right: 18, top: 38, bottom: 8, containLabel: true },
}

const callTokenChartOption = computed(() => ({
  ...chartBase,
  xAxis: {
    type: 'category',
    data: chartLabels.value,
    boundaryGap: false,
    axisLine: { lineStyle: { color: 'rgba(0,0,0,.08)' } },
    axisTick: { show: false },
    axisLabel: { color: 'rgba(29,29,31,.45)', fontSize: 11 },
  },
  yAxis: [
    {
      type: 'value',
      splitLine: { lineStyle: { color: 'rgba(0,0,0,.055)' } },
      axisLabel: { color: 'rgba(29,29,31,.45)' },
    },
    {
      type: 'value',
      splitLine: { show: false },
      axisLabel: { color: 'rgba(29,29,31,.45)' },
    },
  ],
  series: [
    {
      name: '逻辑调用',
      type: 'line',
      smooth: true,
      symbolSize: 5,
      data: (overview.value?.trends || []).map((point) => point.logical_calls),
      lineStyle: { color: '#0066cc', width: 2 },
      itemStyle: { color: '#0066cc' },
      areaStyle: { color: 'rgba(0,102,204,.08)' },
    },
    {
      name: 'HTTP 尝试',
      type: 'line',
      smooth: true,
      symbolSize: 5,
      data: (overview.value?.trends || []).map((point) => point.http_attempts),
      lineStyle: { color: '#06b6d4', width: 2 },
      itemStyle: { color: '#06b6d4' },
    },
    {
      name: aggregateTokenLabel(
        overview.value?.kpis.unknown_usage_attempts || 0,
        overview.value?.kpis.total_tokens ?? null,
      ),
      type: 'bar',
      yAxisIndex: 1,
      barMaxWidth: 20,
      data: (overview.value?.trends || []).map((point) => point.total_tokens),
      itemStyle: { color: 'rgba(16,185,129,.42)', borderRadius: [4, 4, 0, 0] },
    },
  ],
}))

const latencyConcurrencyChartOption = computed(() => ({
  ...chartBase,
  xAxis: {
    type: 'category',
    data: chartLabels.value,
    boundaryGap: false,
    axisLine: { lineStyle: { color: 'rgba(0,0,0,.08)' } },
    axisTick: { show: false },
    axisLabel: { color: 'rgba(29,29,31,.45)', fontSize: 11 },
  },
  yAxis: [
    {
      type: 'value',
      axisLabel: { color: 'rgba(29,29,31,.45)', formatter: '{value} ms' },
      splitLine: { lineStyle: { color: 'rgba(0,0,0,.055)' } },
    },
    {
      type: 'value',
      minInterval: 1,
      splitLine: { show: false },
      axisLabel: { color: 'rgba(29,29,31,.45)' },
    },
  ],
  series: [
    {
      name: 'P95 响应',
      type: 'line',
      smooth: true,
      symbolSize: 5,
      data: (overview.value?.trends || []).map((point) => point.p95_latency_ms),
      lineStyle: { color: '#f59e0b', width: 2 },
      itemStyle: { color: '#f59e0b' },
      areaStyle: { color: 'rgba(245,158,11,.08)' },
    },
    {
      name: '峰值并发',
      type: 'bar',
      yAxisIndex: 1,
      barMaxWidth: 22,
      data: (overview.value?.trends || []).map((point) => point.peak_concurrency),
      itemStyle: { color: 'rgba(0,102,204,.48)', borderRadius: [4, 4, 0, 0] },
    },
  ],
}))

const drawerTitle = computed(() =>
  selectedRecordHash.value ? `${shortRecordRef(selectedRecordHash.value)} · 调用明细` : '调用明细',
)

function rangeBounds(): { start_at: string; end_at: string } {
  const end = new Date()
  const hours = rangeKey.value === '24h' ? 24 : rangeKey.value === '30d' ? 24 * 30 : 24 * 7
  const start = new Date(end.getTime() - hours * 60 * 60 * 1000)
  return { start_at: start.toISOString(), end_at: end.toISOString() }
}

function buildOverviewQuery(page = 1): LlmObservabilityQuery {
  return {
    ...rangeBounds(),
    provider_code: providerCode.value || undefined,
    model: modelCode.value || undefined,
    business_scene: businessScene.value || undefined,
    page,
    page_size: 20,
  }
}

async function loadOverview(page = 1) {
  const requestSequence = ++overviewRequestSequence
  const query = buildOverviewQuery(page)
  loading.value = true
  errorMessage.value = ''
  try {
    const nextOverview = await getLlmObservabilityOverview(query)
    if (requestSequence !== overviewRequestSequence) return
    rememberModelOptions(nextOverview.models)
    activeOverviewQuery.value = query
    overview.value = nextOverview
  } catch {
    if (requestSequence !== overviewRequestSequence) return
    overview.value = null
    errorMessage.value = '模型性能数据暂不可用'
  } finally {
    if (requestSequence === overviewRequestSequence) {
      loading.value = false
    }
  }
}

function rememberModelOptions(models: LlmObservabilityModelSummary[]) {
  const known = new Map(
    knownModelOptions.value.map((item) => [`${item.provider_code}\u0000${item.model}`, item]),
  )
  for (const item of models) {
    if (!item.provider_code || !item.model) continue
    known.set(`${item.provider_code}\u0000${item.model}`, {
      provider_code: item.provider_code,
      model: item.model,
    })
  }
  knownModelOptions.value = Array.from(known.values())
}

function handleFilterChange() {
  void loadOverview(1)
}

function handleProviderChange() {
  modelCode.value = ''
  void loadOverview(1)
}

function handleRecordPageChange(page: number) {
  void loadOverview(page)
}

async function openRecordCalls(recordKeyHash: string) {
  selectedRecordHash.value = recordKeyHash
  drawerOpen.value = true
  await loadRecordCalls(1)
}

async function loadRecordCalls(page: number) {
  const requestSequence = ++detailRequestSequence
  const recordHash = selectedRecordHash.value
  detailLoading.value = true
  detailError.value = false
  recordCalls.value = null
  try {
    const sourceQuery = activeOverviewQuery.value || buildOverviewQuery(1)
    const nextRecordCalls = await getLlmRecordCallAttempts(recordHash, {
      start_at: sourceQuery.start_at,
      end_at: sourceQuery.end_at,
      provider_code: sourceQuery.provider_code,
      model: sourceQuery.model,
      business_scene: sourceQuery.business_scene,
      page,
      page_size: 20,
    })
    if (requestSequence !== detailRequestSequence || recordHash !== selectedRecordHash.value) return
    recordCalls.value = nextRecordCalls
  } catch {
    if (requestSequence !== detailRequestSequence) return
    detailError.value = true
  } finally {
    if (requestSequence === detailRequestSequence) {
      detailLoading.value = false
    }
  }
}

function closeRecordCalls() {
  detailRequestSequence += 1
  drawerOpen.value = false
  detailLoading.value = false
}

function handleDetailPageChange(page: number) {
  void loadRecordCalls(page)
}

function formatInteger(value: number): string {
  return Number(value || 0).toLocaleString('zh-CN')
}

function formatNullableInteger(value: number | null): string {
  return value === null ? '未知' : Number(value).toLocaleString('zh-CN')
}

function aggregateTokenLabel(unknownUsageAttempts: number, totalTokens: number | null): string {
  if (Number(unknownUsageAttempts || 0) <= 0) return '总 Token'
  return totalTokens === null ? 'Token' : '已上报 Token'
}

function usageStateLabel(value: 'known' | 'unknown'): string {
  return value === 'known' ? '用量已上报' : '用量未上报'
}

function formatDuration(value: number): string {
  if (!Number.isFinite(value)) return '未知'
  if (value >= 1000) return `${(value / 1000).toFixed(value >= 10000 ? 0 : 1)} 秒`
  return `${Math.round(value)} ms`
}

function formatNullableDuration(value: number | null): string {
  return value === null ? '未知' : formatDuration(value)
}

function formatDateTime(value: string | null): string {
  if (!value) return '未知'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '未知'
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date)
}

function formatRange(start: string | null, end: string | null): string {
  const startLabel = start ? formatDateTime(start) : '未限定'
  const endLabel = end ? formatDateTime(end) : '现在'
  return `${startLabel} 至 ${endLabel}`
}

function formatBucket(value: string): string {
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return value.slice(5)
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '未知'
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date)
}

function shortRecordRef(hash: string): string {
  return `病历 #${String(hash || '').slice(0, 8) || '未知'}`
}

function modelKey(item: LlmObservabilityModelSummary): string {
  return `${item.provider_code}:${item.model}:${item.model_role}`
}

function modelRoleLabel(value: string): string {
  const labels: Record<string, string> = {
    first_pass: '初审模型',
    adjudicator: '裁决模型',
    qc_fact_extractor: '质控事实抽取模型',
    quality_control: '质控模型',
    extraction: '抽取模型',
    coding: '编码模型',
    general: '通用模型',
  }
  return labels[value] || '未标记用途'
}

function sceneLabel(value: string): string {
  const match = sceneOptions.find((item) => item.value === value)
  return match?.label || '其他业务场景'
}

function safeErrorLabel(value: string): string {
  const labels: Record<string, string> = {
    timeout: '请求超时',
    transport_error: '网络连接失败',
    http_transport: '网络连接失败',
    upstream_429: '上游限流',
    upstream_5xx: '上游服务异常',
    upstream_4xx: '上游请求被拒绝',
    configuration_error: '配置不可用',
    configuration: '配置不可用',
    cancelled: '请求已取消',
    abandoned: '请求未正常结束',
    stale_running: '调用未正常结束',
    unclassified: '未分类异常',
  }
  return labels[value] || '其他安全错误'
}

function errorBarWidth(count: number): string {
  const max = Math.max(...(overview.value?.safe_errors || []).map((item) => item.count), 1)
  return `${Math.max(4, Math.round((count / max) * 100))}%`
}

function statusTone(value: string): string {
  if (value === 'success' || value === 'healthy') return 'is-success'
  if (value === 'partial_failure' || value === 'timeout' || value === 'upstream_429')
    return 'is-warning'
  if (value === 'running') return 'is-running'
  return 'is-error'
}

function recordStatusLabel(value: string): string {
  const labels: Record<string, string> = {
    healthy: '正常',
    success: '正常',
    partial_failure: '部分失败',
    failed: '调用失败',
    running: '调用中',
  }
  return labels[value] || '需核查'
}

function attemptStatusLabel(value: string): string {
  const labels: Record<string, string> = {
    success: '成功',
    running: '执行中',
    timeout: '请求超时',
    transport_error: '连接失败',
    upstream_429: '上游限流',
    upstream_5xx: '上游异常',
    configuration_error: '配置异常',
    cancelled: '已取消',
    abandoned: '未正常结束',
    unclassified: '调用异常',
  }
  return labels[value] || '调用异常'
}

onMounted(() => {
  void loadOverview()
})
</script>

<style scoped>
.llm-observability {
  min-height: 100%;
  padding: 22px;
  color: #1d1d1f;
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
}

.llm-observability__header,
.llm-observability__filters,
.llm-observability__section-head,
.llm-observability__attempt-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.llm-observability__header {
  margin-bottom: 16px;
}

.llm-observability__eyebrow {
  display: block;
  margin-bottom: 5px;
  color: #0066cc;
  font-size: 12px;
  font-weight: 650;
}

.llm-observability__header h2 {
  margin: 0;
  font-size: 26px;
  line-height: 32px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.llm-observability__header p,
.llm-observability__section-head p,
.llm-observability__state p,
.llm-observability__drawer-state p {
  margin: 4px 0 0;
  color: rgba(29, 29, 31, 0.58);
  font-size: 13px;
  line-height: 20px;
}

.llm-observability__refresh {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  min-height: 34px;
  border-radius: 8px;
}

.llm-observability__filters {
  justify-content: flex-start;
  flex-wrap: wrap;
  padding: 12px 14px;
  margin-bottom: 14px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.86);
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.035);
  backdrop-filter: blur(18px);
}

.llm-observability__filters label {
  display: grid;
  grid-template-columns: auto minmax(128px, 164px);
  align-items: center;
  gap: 8px;
  color: rgba(29, 29, 31, 0.62);
  font-size: 12px;
  font-weight: 600;
}

.llm-observability__filters :deep(.ant-select-selector) {
  min-height: 34px !important;
  border-radius: 8px !important;
  border-color: rgba(0, 0, 0, 0.1) !important;
  box-shadow: none !important;
}

.llm-observability__range-note {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
  color: rgba(29, 29, 31, 0.48);
  font-size: 12px;
}

.llm-observability__kpis {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  margin-bottom: 10px;
  overflow: hidden;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.9);
}

.llm-observability__kpi {
  position: relative;
  min-width: 0;
  padding: 16px 17px 14px;
}

.llm-observability__kpi + .llm-observability__kpi {
  border-left: 1px solid rgba(0, 0, 0, 0.07);
}

.llm-observability__kpi::before {
  position: absolute;
  top: 0;
  left: 17px;
  width: 32px;
  height: 3px;
  border-radius: 0 0 4px 4px;
  background: #0066cc;
  content: '';
}

.llm-observability__kpi span,
.llm-observability__kpi em {
  display: block;
  color: rgba(29, 29, 31, 0.52);
  font-size: 12px;
  font-style: normal;
}

.llm-observability__kpi strong {
  display: block;
  margin: 7px 0 3px;
  font-size: 24px;
  line-height: 28px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.llm-observability__health-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 20px;
  padding: 8px 14px;
  margin-bottom: 14px;
  color: rgba(29, 29, 31, 0.58);
  font-size: 12px;
}

.llm-observability__chart-grid,
.llm-observability__distribution-grid {
  display: grid;
  grid-template-columns: minmax(0, 3fr) minmax(320px, 2fr);
  gap: 14px;
  margin-bottom: 14px;
}

.llm-observability__surface {
  min-width: 0;
  padding: 18px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
}

.llm-observability__section-head {
  margin-bottom: 12px;
}

.llm-observability__section-head h3 {
  margin: 0;
  font-size: 17px;
  line-height: 22px;
  font-weight: 650;
}

.llm-observability__section-head > span {
  color: rgba(29, 29, 31, 0.46);
  font-size: 12px;
}

.llm-observability__chart {
  width: 100%;
  height: 270px;
}

.llm-observability__model-list,
.llm-observability__error-list {
  display: grid;
  gap: 0;
}

.llm-observability__model-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 12px 0;
  border-top: 1px solid rgba(0, 0, 0, 0.065);
}

.llm-observability__model-row:first-child {
  border-top: 0;
}

.llm-observability__model-row > div:first-child {
  min-width: 0;
}

.llm-observability__model-row strong,
.llm-observability__model-row span {
  display: block;
}

.llm-observability__model-row strong {
  overflow: hidden;
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.llm-observability__model-row span {
  color: rgba(29, 29, 31, 0.52);
  font-size: 11px;
}

.llm-observability__model-metrics {
  display: grid;
  grid-template-columns: repeat(2, auto);
  gap: 3px 16px;
  text-align: right;
}

.llm-observability__error-row {
  padding: 9px 0;
}

.llm-observability__error-row > div:first-child {
  display: flex;
  justify-content: space-between;
  margin-bottom: 7px;
  font-size: 13px;
}

.llm-observability__error-track {
  height: 6px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.055);
}

.llm-observability__error-track i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: #ef4444;
}

.llm-observability__healthy-empty,
.llm-observability__inline-empty {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 110px;
  margin: 0;
  color: rgba(29, 29, 31, 0.5);
  font-size: 13px;
}

.llm-observability__healthy-empty svg {
  color: #10b981;
}

.llm-observability__records {
  margin-bottom: 8px;
}

.llm-observability__table-scroll {
  overflow-x: auto;
}

.llm-observability table {
  width: 100%;
  min-width: 850px;
  border-collapse: collapse;
}

.llm-observability th,
.llm-observability td {
  padding: 11px 10px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.065);
  text-align: left;
  white-space: nowrap;
}

.llm-observability th {
  color: rgba(29, 29, 31, 0.48);
  font-size: 11px;
  font-weight: 650;
}

.llm-observability td {
  color: rgba(29, 29, 31, 0.72);
  font-size: 13px;
}

.llm-observability__status {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 8px;
  border-radius: 999px;
  background: rgba(29, 29, 31, 0.06);
  color: rgba(29, 29, 31, 0.62);
  font-size: 11px;
  font-weight: 650;
}

.llm-observability__status.is-success {
  background: rgba(16, 185, 129, 0.1);
  color: #047857;
}

.llm-observability__status.is-warning {
  background: rgba(245, 158, 11, 0.12);
  color: #b45309;
}

.llm-observability__status.is-running {
  background: rgba(0, 102, 204, 0.1);
  color: #0066cc;
}

.llm-observability__status.is-error {
  background: rgba(239, 68, 68, 0.1);
  color: #dc2626;
}

.llm-observability__link {
  padding: 0;
  border: 0;
  background: none;
  color: #0066cc;
  font: inherit;
  font-weight: 650;
  cursor: pointer;
}

.llm-observability__state {
  display: flex;
  align-items: center;
  gap: 14px;
  min-height: 150px;
  padding: 24px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.9);
}

.llm-observability__state > div {
  flex: 1;
}

.llm-observability__state--error svg {
  color: #ef4444;
}

.llm-observability__state--empty svg {
  color: #0066cc;
}

.llm-observability__state--loading svg {
  color: #0066cc;
  animation: llm-observability-pulse 1.1s ease-in-out infinite alternate;
}

@keyframes llm-observability-pulse {
  from {
    opacity: 0.4;
    transform: scale(0.92);
  }

  to {
    opacity: 1;
    transform: scale(1);
  }
}

.llm-observability__drawer-intro {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 11px 13px;
  margin-bottom: 12px;
  border-radius: 10px;
  background: rgba(0, 102, 204, 0.06);
  color: rgba(29, 29, 31, 0.64);
  font-size: 12px;
}

.llm-observability__drawer-intro svg {
  flex: 0 0 auto;
  color: #0066cc;
}

.llm-observability__attempt-list {
  display: grid;
  gap: 10px;
}

.llm-observability__attempt {
  padding: 15px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 12px;
  background: #fff;
}

.llm-observability__attempt-head strong,
.llm-observability__attempt-head span {
  display: block;
}

.llm-observability__attempt-head > div > span {
  margin-top: 3px;
  color: rgba(29, 29, 31, 0.48);
  font-size: 12px;
}

.llm-observability__attempt dl {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px 14px;
  margin: 14px 0 0;
}

.llm-observability__attempt dl > div {
  min-width: 0;
}

.llm-observability__attempt dt {
  color: rgba(29, 29, 31, 0.46);
  font-size: 11px;
}

.llm-observability__attempt dd {
  overflow: hidden;
  margin: 3px 0 0;
  color: rgba(29, 29, 31, 0.8);
  font-size: 13px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.llm-observability__drawer-state {
  padding: 28px 4px;
  color: rgba(29, 29, 31, 0.65);
}

@media (max-width: 1280px) {
  .llm-observability__kpis {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .llm-observability__kpi:nth-child(4) {
    border-left: 0;
    border-top: 1px solid rgba(0, 0, 0, 0.07);
  }

  .llm-observability__kpi:nth-child(5),
  .llm-observability__kpi:nth-child(6) {
    border-top: 1px solid rgba(0, 0, 0, 0.07);
  }
}

@media (max-width: 920px) {
  .llm-observability {
    padding: 14px;
  }

  .llm-observability__chart-grid,
  .llm-observability__distribution-grid {
    grid-template-columns: 1fr;
  }

  .llm-observability__filters label {
    grid-template-columns: 1fr;
    min-width: calc(50% - 8px);
  }

  .llm-observability__range-note {
    width: 100%;
    margin-left: 0;
  }
}

@media (max-width: 640px) {
  .llm-observability__header {
    align-items: flex-start;
  }

  .llm-observability__kpis {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .llm-observability__kpi:nth-child(odd) {
    border-left: 0;
  }

  .llm-observability__kpi:nth-child(n + 3) {
    border-top: 1px solid rgba(0, 0, 0, 0.07);
  }

  .llm-observability__filters label {
    min-width: 100%;
  }

  .llm-observability__attempt dl {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>

<style>
.llm-observability-popup {
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', Inter, 'PingFang SC',
    'Microsoft YaHei UI', system-ui, sans-serif;
  backdrop-filter: blur(18px);
}

.llm-observability-popup .ant-select-item {
  min-height: 34px;
  padding: 7px 12px;
  color: rgba(29, 29, 31, 0.78);
  font-size: 13px;
  line-height: 20px;
}

.llm-observability-popup .ant-select-item-option-selected {
  background: rgba(0, 102, 204, 0.08) !important;
  color: #0066cc;
  font-weight: 650;
}
</style>
