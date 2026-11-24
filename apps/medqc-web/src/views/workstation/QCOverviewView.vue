<template>
  <div class="qc-home-shell">
    <div class="mq-page">
      <!-- 页头：眉标一行写清范围（纯文字，不做胶囊）；右侧工具栏只留科室筛选与刷新 -->
      <header
        class="mq-page-head"
        data-testid="home-scope"
      >
        <div class="mq-page-head__copy">
          <span class="mq-page-eyebrow">{{ scopeLine }}</span>
          <h1 class="mq-page-title">
            质控首页概览
          </h1>
        </div>
        <div
          v-if="clinicalQc || loadError || departmentFilter !== 'all' || keyword.trim()"
          class="qc-home-toolbar"
        >
          <span
            v-if="keyword.trim()"
            class="qc-home-toolbar__keyword-group"
          >
            <span
              class="qc-home-toolbar__keyword"
              :title="`关键词：${keyword.trim()}`"
            >关键词：{{ keyword.trim() }}</span>
            <button
              type="button"
              class="qc-home-toolbar__clear"
              aria-label="清除关键词"
              @click="clearKeyword"
            >
              清除
            </button>
          </span>
          <label class="qc-home-pulldown qc-home-pulldown--bordered">
            <select
              v-model="departmentFilter"
              class="qc-home-department"
              aria-label="统计科室"
              :title="scopeDepartmentText"
            >
              <option value="all">全部科室</option>
              <option
                v-for="department in departmentOptions"
                :key="department"
                :value="department"
              >
                {{ department }}
              </option>
            </select>
            <svg
              class="qc-home-pulldown__caret"
              width="11"
              height="11"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2.6"
              stroke-linecap="round"
              stroke-linejoin="round"
              aria-hidden="true"
            ><path d="m6 9 6 6 6-6" /></svg>
          </label>
          <span
            v-if="isRefreshing"
            class="qc-home-toolbar__refreshing"
            role="status"
            aria-live="polite"
          >更新中…</span>
          <span
            v-else-if="clinicalQc"
            class="qc-home-toolbar__time"
          >生成于 {{ formatDateTime(clinicalQc.scope.generated_at) }}</span>
          <button
            type="button"
            class="qc-home-icon-button"
            :class="{ 'is-refreshing': isRefreshing }"
            aria-label="刷新首页数据"
            :disabled="loading"
            @click="void fetchHome()"
          >
            <MqIcon
              name="sync"
              :size="16"
              color="#515154"
            />
          </button>
        </div>
      </header>

      <section
        v-if="loadError"
        class="mq-card qc-home-notice"
        data-testid="home-load-error"
        role="alert"
      >
        <MqIconTile
          name="tech_error"
          tone="danger"
          :size="36"
        />
        <div class="qc-home-notice__copy">
          <strong>暂时无法加载质控首页</strong>
          <span>请稍后刷新；不会以旧任务或缓存数据替代当前结果。</span>
        </div>
        <button
          type="button"
          class="qc-home-button"
          @click="void fetchHome()"
        >
          重新加载
        </button>
      </section>

      <section
        v-else-if="loading && !clinicalQc"
        class="mq-card qc-home-loading"
        data-testid="home-loading"
        aria-live="polite"
        aria-busy="true"
      >
        <a-spin />
        <div>
          <strong>正在加载全院质控概览</strong>
          <span>正在汇总当前范围内的病历与最新质控结果。</span>
        </div>
      </section>

      <div
        v-else-if="clinicalQc"
        class="qc-home-body"
        :class="{ 'is-refreshing': isRefreshing }"
        :aria-busy="isRefreshing ? 'true' : undefined"
      >
        <section
          v-if="recordsTotal === 0"
          class="mq-card qc-home-zero-hint"
          data-testid="home-zero-records"
          role="status"
        >
          <MqIconTile
            name="stack"
            tone="neutral"
            :size="36"
          />
          <div class="qc-home-zero-hint__copy">
            <strong>{{ hasActiveFilters ? '当前筛选范围内暂无纳入病历' : '当前范围内暂无纳入病历' }}</strong>
            <span>{{ hasActiveFilters ? '可切换回全部科室、清除关键词，或前往病历池查看病历。' : '请先在病历池同步或选择病历发起质控。' }}</span>
          </div>
          <div class="qc-home-zero-hint__actions">
            <button
              v-if="hasActiveFilters"
              type="button"
              class="qc-home-button"
              @click="resetFilters"
            >
              重置筛选
            </button>
            <button
              type="button"
              class="qc-home-button qc-home-button--primary"
              @click="openRecordPool"
            >
              进入病历池
            </button>
          </div>
        </section>

        <section
          class="qc-home-overview"
          aria-label="质控总览"
          data-testid="home-overview"
        >
          <!-- 主卡：待质控 + 工作入口 -->
          <div class="qc-home-hero">
            <span
              class="qc-home-hero__glow"
              aria-hidden="true"
            />
            <span class="qc-home-hero__label">
              <MqIcon
                name="task"
                :size="18"
                color="#FFFFFF"
              />待质控
            </span>
            <div class="qc-home-hero__value">
              <strong>{{ pendingKpi.value }}</strong>
              <span>/ {{ recordsTotal }} 份</span>
            </div>
            <div class="qc-home-hero__progress">
              <span
                class="qc-home-hero__track"
                aria-hidden="true"
              >
                <i :style="{ width: `${rates.pending}%` }" />
              </span>
              <span>占纳入病历 {{ formatRate(rates.pending) }}%，尚未生成最终结果。</span>
            </div>
            <nav
              class="qc-home-shortcuts"
              data-testid="home-workspace"
              aria-label="质控工作入口"
            >
              <button
                type="button"
                class="qc-home-shortcuts__primary"
                @click="openRecordPool"
              >
                选择病历质控
              </button>
              <template v-if="canAccessStageRecordLists">
                <button
                  type="button"
                  @click="openStageRecordList('running')"
                >
                  运行病历质控
                </button>
                <button
                  type="button"
                  @click="openStageRecordList('final')"
                >
                  终末病历质控
                </button>
              </template>
            </nav>
          </div>

          <!-- 质控进度圆环卡（浅色玻璃，比例均由现有 KPI 计算） -->
          <div
            class="qc-home-rings"
            aria-label="质控进度"
          >
            <span class="qc-home-rings__title">质控进度</span>
            <div class="qc-home-rings__body">
              <svg
                width="96"
                height="96"
                viewBox="0 0 200 200"
                aria-hidden="true"
              >
                <defs>
                  <linearGradient
                    v-for="ring in ringDefs"
                    :id="ring.gradient"
                    :key="ring.gradient"
                    x1="0"
                    y1="0"
                    x2="1"
                    y2="1"
                  >
                    <stop
                      offset="0"
                      :stop-color="ring.from"
                    />
                    <stop
                      offset="1"
                      :stop-color="ring.to"
                    />
                  </linearGradient>
                </defs>
                <g
                  v-for="ring in ringDefs"
                  :key="ring.key"
                >
                  <circle
                    cx="100"
                    cy="100"
                    :r="ring.r"
                    fill="none"
                    :stroke="`url(#${ring.gradient})`"
                    stroke-opacity="0.14"
                    stroke-width="20"
                  />
                  <!-- 零值不画进度弧，避免圆角端点残留成一个点 -->
                  <circle
                    v-if="ring.rate > 0"
                    cx="100"
                    cy="100"
                    :r="ring.r"
                    fill="none"
                    :stroke="`url(#${ring.gradient})`"
                    stroke-width="20"
                    stroke-linecap="round"
                    :stroke-dasharray="ringDash(ring.r, ring.rate)"
                    transform="rotate(-90 100 100)"
                  />
                </g>
              </svg>
              <dl class="qc-home-rings__legend">
                <div
                  v-for="ring in ringDefs"
                  :key="ring.key"
                >
                  <dt :style="{ color: ring.textColor }">
                    {{ ring.label }}
                  </dt>
                  <dd>{{ formatRate(ring.rate) }}<small> %</small></dd>
                </div>
              </dl>
            </div>
          </div>
        </section>

        <!-- 三栏指标卡 -->
        <section
          class="mq-card qc-home-metrics"
          data-testid="home-kpis"
          aria-label="质控指标汇总"
        >
          <div
            v-for="card in metricCards"
            :key="card.key"
            :class="['qc-home-metric', `qc-home-metric--${card.key}`, { 'is-zero': card.value === 0 }]"
          >
            <div class="qc-home-metric__head">
              <MqIconTile
                :name="card.icon"
                :tone="card.value === 0 ? 'neutral' : card.tone"
                :size="40"
              />
              <div class="qc-home-metric__titles">
                <span class="qc-home-metric__label">{{ card.label }}</span>
                <p class="qc-home-metric__helper">
                  {{ card.helper }}
                </p>
              </div>
            </div>
            <div class="qc-home-metric__foot">
              <strong class="qc-home-metric__value">{{ card.value }}<small>份</small></strong>
              <span class="qc-home-metric__rate">
                <em
                  :style="{ color: card.value === 0 ? undefined : toneTextColor(card.tone) }"
                  :title="card.rateLabel"
                >{{ card.rateLabel }}</em>
                <span
                  class="qc-home-metric__track"
                  aria-hidden="true"
                >
                  <i :style="{ width: `${card.rate}%`, background: card.value === 0 ? 'transparent' : toneGradient(card.tone) }" />
                </span>
              </span>
            </div>
          </div>
        </section>

        <section
          class="qc-home-analysis"
          data-testid="home-analysis"
        >
          <section
            class="mq-card qc-home-panel qc-home-defect-analysis"
            data-testid="defect-analysis-chart"
            aria-labelledby="defect-analysis-title"
          >
            <header class="qc-home-panel__head qc-home-defect-analysis__head">
              <div>
                <h2
                  id="defect-analysis-title"
                  class="mq-card__title"
                >
                  质控缺陷分析
                </h2>
                <p>{{ confirmedResultsOnly ? '缺陷仅统计确定问题。' : '缺陷仅统计确定问题，资料待核实与待判断不计入缺陷数。' }}</p>
              </div>
              <!-- 一个分段控件切统计对象；指标与排序收进下拉 -->
              <div class="qc-home-defect-analysis__toolbar">
                <div
                  class="mq-segmented mq-segmented--sm"
                  role="group"
                  aria-label="统计对象"
                >
                  <button
                    type="button"
                    class="mq-segmented__item"
                    :class="{ 'is-active': analysisObject === 'department' }"
                    :aria-pressed="analysisObject === 'department'"
                    data-testid="analysis-object-department"
                    @click="analysisObject = 'department'"
                  >
                    按科室
                  </button>
                  <button
                    type="button"
                    class="mq-segmented__item"
                    :class="{ 'is-active': analysisObject === 'physician' }"
                    :aria-pressed="analysisObject === 'physician'"
                    data-testid="analysis-object-physician"
                    @click="analysisObject = 'physician'"
                  >
                    按主治医师
                  </button>
                </div>
                <label class="qc-home-pulldown">
                  <span class="qc-home-pulldown__label">指标</span>
                  <select
                    v-model="analysisMetric"
                    data-testid="analysis-metric"
                    aria-label="分析指标"
                  >
                    <option value="total">缺陷总数</option>
                    <option value="average">平均缺陷数</option>
                  </select>
                  <svg
                    class="qc-home-pulldown__caret"
                    width="11"
                    height="11"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2.6"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    aria-hidden="true"
                  ><path d="m6 9 6 6 6-6" /></svg>
                </label>
                <label class="qc-home-pulldown">
                  <span class="qc-home-pulldown__label">排序</span>
                  <select
                    v-model="analysisSort"
                    data-testid="analysis-sort"
                    aria-label="排序方式"
                  >
                    <option value="metric">当前指标</option>
                    <option value="risk">高风险病历</option>
                    <option
                      v-if="!confirmedResultsOnly"
                      value="gap"
                    >
                      资料待核实
                    </option>
                  </select>
                  <svg
                    class="qc-home-pulldown__caret"
                    width="11"
                    height="11"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2.6"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    aria-hidden="true"
                  ><path d="m6 9 6 6 6-6" /></svg>
                </label>
              </div>
            </header>
            <div
              v-if="defectAnalysisItems.length"
              class="qc-home-defect-analysis__list"
            >
              <component
                :is="analysisObject === 'department' ? 'button' : 'div'"
                v-for="item in defectAnalysisItems"
                :key="item.name"
                :type="analysisObject === 'department' ? 'button' : undefined"
                :class="[
                  'qc-home-defect-analysis__row',
                  {
                    'is-active': analysisObject === 'department' && departmentFilter === item.name,
                    'is-physician': analysisObject === 'physician',
                  },
                ]"
                data-testid="defect-analysis-row"
                :aria-pressed="
                  analysisObject === 'department' ? departmentFilter === item.name : undefined
                "
                :aria-label="
                  analysisObject === 'department'
                    ? departmentFilter === item.name
                      ? `取消${item.name}科室筛选，返回全部科室`
                      : `切换到${item.name}科室质控范围`
                    : undefined
                "
                @click="analysisObject === 'department' && selectDepartment(item.name)"
              >
                <div class="qc-home-defect-analysis__meta">
                  <strong :title="item.name">{{ item.name }}</strong>
                  <span>纳入 {{ item.recordsTotal }} 份 · 完成
                    {{ item.completedRecordTotal }} 份</span>
                </div>
                <div class="qc-home-defect-analysis__metric">
                  <div
                    class="qc-home-defect-analysis__track"
                    aria-hidden="true"
                  >
                    <i
                      :class="{ 'is-nonzero': defectAnalysisValue(item) > 0 }"
                      :style="{ width: `${defectAnalysisPercent(item)}%` }"
                    />
                  </div>
                  <strong>{{ formatAnalysisMetric(item) }}</strong>
                </div>
                <div class="qc-home-defect-analysis__counts">
                  <strong :class="{ 'is-zero': !item.highRiskReviewTotal }">高风险 {{ item.highRiskReviewTotal }}</strong>
                  <span
                    v-if="!confirmedResultsOnly"
                    :class="{ 'is-zero': !item.dataGapRecordTotal }"
                  >待核实 {{ item.dataGapRecordTotal }}</span>
                </div>
                <svg
                  v-if="analysisObject === 'department'"
                  class="qc-home-defect-analysis__chevron"
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2.2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  aria-hidden="true"
                ><path d="m9 6 6 6-6 6" /></svg>
              </component>
              <p
                v-if="hiddenDefectAnalysisCount"
                class="qc-home-defect-analysis__note"
              >
                仅展示前 8 项；其余 {{ hiddenDefectAnalysisCount }} 个{{
                  analysisObjectLabel
                }}已收起。
              </p>
            </div>
            <a-empty
              v-else
              :description="`当前范围内暂无${analysisObjectLabel}统计`"
              :image-style="{ height: '58px' }"
            />
          </section>

          <div class="qc-home-side">
            <section
              class="mq-card qc-home-panel qc-home-conclusion"
              data-testid="qc-conclusion-chart"
              aria-labelledby="qc-conclusion-title"
            >
              <header class="qc-home-panel__head">
                <div>
                  <h2
                    id="qc-conclusion-title"
                    class="mq-card__title"
                  >
                    结论结构
                  </h2>
                  <p>{{ hasPartialFailedConclusion ? '已回写的有效规则结论，含未全部完成病历。' : '已完成病历中的规则结论。' }}</p>
                </div>
              </header>
              <div
                v-if="conclusionSegments.length"
                class="qc-home-conclusion__content"
              >
                <div
                  class="qc-home-conclusion__ring"
                  role="img"
                  :aria-label="conclusionRingAriaLabel"
                >
                  <svg
                    class="qc-home-conclusion__svg"
                    width="120"
                    height="120"
                    viewBox="0 0 120 120"
                    aria-hidden="true"
                  >
                    <circle
                      cx="60"
                      cy="60"
                      :r="CONCLUSION_RING_RADIUS"
                      fill="none"
                      stroke="rgba(118, 128, 160, 0.12)"
                      stroke-width="14"
                    />
                    <circle
                      v-for="arc in conclusionRingArcs"
                      :key="arc.status"
                      cx="60"
                      cy="60"
                      :r="CONCLUSION_RING_RADIUS"
                      fill="none"
                      :stroke="arc.color"
                      stroke-width="14"
                      stroke-linecap="butt"
                      :stroke-dasharray="arc.dashArray"
                      :stroke-dashoffset="arc.dashOffset"
                      transform="rotate(-90 60 60)"
                    />
                  </svg>
                  <div class="qc-home-conclusion__center">
                    <strong>{{ conclusionTotal }}</strong>
                    <span>规则结论</span>
                  </div>
                </div>
                <ul
                  class="qc-home-conclusion__legend"
                  :aria-label="hasPartialFailedConclusion ? '已回写有效规则结论图例' : '已完成病历中的规则结论图例'"
                >
                  <li
                    v-for="segment in conclusionSegments"
                    :key="segment.status"
                  >
                    <i
                      :style="{ background: segment.color }"
                      aria-hidden="true"
                    />
                    <span class="qc-home-conclusion__item-main">
                      <span class="qc-home-conclusion__label">{{ segment.label }}</span>{{ ' ' }}<strong class="qc-home-conclusion__count">{{ segment.value }}</strong>
                    </span>
                    <small class="qc-home-conclusion__percent">{{ segment.percent.toFixed(1) }}%</small>
                  </li>
                </ul>
              </div>
              <a-empty
                v-else
                description="暂无已完成质控结论"
                :image-style="{ height: '52px' }"
              />
            </section>

            <section
              class="mq-card qc-home-panel qc-home-panel--health"
              data-testid="data-health"
            >
              <header class="qc-home-panel__head">
                <div>
                  <h2 class="mq-card__title">
                    数据与服务状态
                  </h2>
                  <p>用于判断数据与任务是否可正常使用，不代表医疗结论。</p>
                </div>
              </header>
              <dl class="qc-home-health-list">
                <div data-testid="health-status-item">
                  <MqIconTile
                    name="sync"
                    tone="brand"
                    :size="34"
                  />
                  <dt>资料同步</dt>
                  <dd>{{ sourceStateText }}</dd>
                </div>
                <div data-testid="health-status-item">
                  <MqIconTile
                    name="task"
                    tone="brand"
                    :size="34"
                  />
                  <dt>质控任务</dt>
                  <dd>{{ runningTaskText }}</dd>
                </div>
                <div
                  v-if="!confirmedResultsOnly"
                  data-testid="health-status-item"
                >
                  <MqIconTile
                    name="tech_error"
                    tone="warning"
                    :size="34"
                  />
                  <dt>技术异常</dt>
                  <dd :class="{ 'is-danger': clinicalQc.data_health.technical_error_total > 0 }">
                    {{ clinicalQc.data_health.technical_error_total }} 份
                  </dd>
                </div>
                <div data-testid="health-status-item">
                  <MqIconTile
                    name="success"
                    tone="success"
                    :size="34"
                  />
                  <dt>最近成功质控</dt>
                  <dd>{{ formatDateTime(clinicalQc.data_health.last_successful_qc_at) }}</dd>
                </div>
                <div
                  v-if="!confirmedResultsOnly && (clinicalQc.kpis.qc_partial_failed_total || clinicalQc.kpis.qc_failed_total)"
                  data-testid="qc-execution-failures"
                >
                  <MqIconTile
                    name="failed"
                    tone="warning"
                    :size="34"
                  />
                  <dt>未全部完成</dt>
                  <dd>部分失败 {{ clinicalQc.kpis.qc_partial_failed_total || 0 }} 份、执行失败 {{ clinicalQc.kpis.qc_failed_total || 0 }} 份</dd>
                </div>
              </dl>
            </section>
          </div>
        </section>
      </div>

      <section
        v-else-if="!loading"
        class="mq-card qc-home-empty"
        data-testid="home-empty"
      >
        <a-empty>
          <template #description>
            <strong class="qc-home-empty__title">当前暂无可展示的全病历质控汇总</strong>
            <p class="qc-home-empty__desc">请先在病历池完成质控；系统不会用旧工作流数据代替正式质控结果。</p>
          </template>
          <button
            type="button"
            class="qc-home-button qc-home-button--primary"
            @click="openRecordPool"
          >
            进入病历池
          </button>
        </a-empty>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import dayjs from 'dayjs'
import MqIcon from '@/components/icons/MqIcon.vue'
import MqIconTile from '@/components/icons/MqIconTile.vue'
import { type MqIconName, type MqIconTone } from '@/components/icons/mqIcons'
import { useQcResultVisibility } from '@/composables/useQcResultVisibility'
import { ApiService } from '@/services/apiService'
import { useAuthStore } from '@/stores/auth'
import { QC_RESULT_STATUS_LABELS } from '../workstation-v4/utils/qcResultStatusLabels'
import { parseQcTaskTime, shanghaiQcTaskTimeParts } from '../workstation-v4/utils/qcTaskTime'
import type {
  ClinicalQcHomeDepartmentItem,
  ClinicalQcHomePhysicianItem,
  ClinicalQcHomePayload,
} from './types'

interface KpiCard {
  key: string
  label: string
  value: number
  helper: string
  icon: MqIconName
  tone: MqIconTone
}

interface MetricCard extends KpiCard {
  /** 进度条比例（0-100） */
  rate: number
  rateLabel: string
}

interface ConclusionSegment {
  status: string
  label: string
  value: number
  color: string
  percent: number
}

interface ConclusionRingArc {
  status: string
  color: string
  dashArray: string
  dashOffset: string
}

const CONCLUSION_RING_RADIUS = 46
const CONCLUSION_RING_CIRCUMFERENCE = 2 * Math.PI * CONCLUSION_RING_RADIUS
const CONCLUSION_RING_GAP = 1.5
const CONCLUSION_RING_MIN_ARC = 6

type AnalysisObject = 'department' | 'physician'
type AnalysisMetric = 'total' | 'average'
type AnalysisSort = 'metric' | 'risk' | 'gap'

interface DefectAnalysisItem {
  name: string
  recordsTotal: number
  completedRecordTotal: number
  highRiskReviewTotal: number
  dataGapRecordTotal: number
  defectTotal: number
  averageDefectCount: number
}

const CONCLUSION_STATUS_META = [
  { status: 'non_compliant', label: QC_RESULT_STATUS_LABELS.non_compliant, color: '#ef4444' },
  { status: 'data_gap', label: QC_RESULT_STATUS_LABELS.data_gap, color: '#f59e0b' },
  { status: 'uncertain', label: QC_RESULT_STATUS_LABELS.uncertain, color: '#64748b' },
  { status: 'compliant', label: '合规', color: '#10b981' },
  // 与质控分析页保持同一套语义色，避免同一状态在不同首页模块变色。
  { status: 'not_applicable', label: '不适用', color: '#94a3b8' },
  { status: 'not_executed', label: '未执行', color: '#cbd5e1' },
] as const

const QC_STAGE_RECORD_LIST_ROLES = new Set(['admin', 'qc_manager', 'sync_admin'])
const CONFIRMED_CONCLUSION_STATUSES = new Set(['non_compliant', 'compliant'])
const SOURCE_SYNC_STATUS_LABELS: Record<string, string> = {
  synced: '已同步',
  healthy: '正常',
  ok: '正常',
  degraded: '部分异常',
  failed: '同步失败',
  error: '同步失败',
  syncing: '同步中',
  running: '同步中',
}

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const { confirmedResultsOnly } = useQcResultVisibility()
// 首次进入即处于加载态，避免请求尚未发起时短暂展示无内容的页面框架。
const loading = ref(true)
const loadError = ref(false)
const departmentFilter = ref('all')
const keyword = ref('')
const analysisObject = ref<AnalysisObject>('department')
const analysisMetric = ref<AnalysisMetric>('total')
const analysisSort = ref<AnalysisSort>('metric')
const syncingFromRoute = ref(false)
const homeData = ref<ClinicalQcHomePayload | null>(null)
const cachedDepartmentOptions = ref<string[]>([])

const clinicalQc = computed(() => homeData.value?.clinical_qc ?? null)
const isRefreshing = computed(() => loading.value && Boolean(clinicalQc.value))
const hasActiveFilters = computed(
  () => departmentFilter.value !== 'all' || Boolean(keyword.value.trim()),
)
const currentUserRoles = computed<string[]>(() => {
  if (Array.isArray(authStore.userRoles)) {
    return authStore.userRoles.map((role) => String(role).trim().toLowerCase()).filter(Boolean)
  }
  const user = authStore.user
  if (Array.isArray(user?.roles)) {
    return user.roles.map((role) => String(role).trim().toLowerCase()).filter(Boolean)
  }
  if (typeof user?.role === 'string' && user.role.trim()) {
    return [user.role.trim().toLowerCase()]
  }
  return []
})
const canAccessStageRecordLists = computed(() =>
  currentUserRoles.value.some((role) => QC_STAGE_RECORD_LIST_ROLES.has(role)),
)
const departmentOptions = computed(() => {
  const merged = new Set<string>()
  for (const dept of cachedDepartmentOptions.value) {
    const normalized = dept.trim()
    if (normalized) merged.add(normalized)
  }
  for (const dept of homeData.value?.department_options ?? []) {
    const normalized = dept.trim()
    if (normalized) merged.add(normalized)
  }
  const active = departmentFilter.value.trim()
  if (active && active !== 'all') {
    merged.add(active)
  }
  return Array.from(merged)
})
const scopeHospitalText = computed(() => {
  const scope = String(clinicalQc.value?.scope.hospital_scope || '').trim().toLowerCase()
  if (scope === 'doctor') return '本人负责病历'
  if (scope === 'institute') return '本院区'
  if (scope === 'all') return '全院'
  return '当前范围'
})
const activeDepartmentLabel = computed(() => {
  const active = departmentFilter.value.trim()
  if (active && active !== 'all') return active
  return clinicalQc.value?.scope.department?.trim() || ''
})
const scopeDepartmentText = computed(() => activeDepartmentLabel.value || '全部科室')
const scopeSceneText = computed(() =>
  clinicalQc.value?.scope.scene === 'final'
    ? '最终结果'
    : clinicalQc.value?.scope.scene || '场景待确认',
)

function formatRuleSetLabel(ruleSetKey?: string | null, ruleSetVersion?: string | null): string {
  const key = String(ruleSetKey || '').trim()
  const version = String(ruleSetVersion || '').trim()
  if (!key || key.toLowerCase().startsWith('luxian_0609')) {
    return '泸县0609质控点'
  }
  if (version && !key.toLowerCase().includes(version.toLowerCase())) {
    return `${key} ${version}`
  }
  return key
}

const scopeRuleSetText = computed(() =>
  formatRuleSetLabel(
    clinicalQc.value?.scope.rule_set_key,
    clinicalQc.value?.scope.rule_set_version,
  ),
)

const kpiCards = computed<KpiCard[]>(() => {
  const kpis = clinicalQc.value?.kpis
  return [
    {
      key: 'risk',
      label: '有确定问题的病历',
      value: Number(kpis?.high_risk_review_total || 0),
      helper: '含确定问题的病历',
      icon: 'issue',
      tone: 'danger',
    },
    {
      key: 'pending',
      label: '待质控',
      value: Number(kpis?.qc_pending_total || 0),
      helper: '尚未生成最终结果',
      icon: 'task',
      tone: 'warning',
    },
    {
      key: 'completed',
      label: '已完成',
      value: Number(kpis?.qc_completed_total || 0),
      helper: '已生成正式质控结果',
      icon: 'fp_qc',
      tone: 'success',
    },
    {
      key: 'records',
      label: '纳入病历',
      value: Number(kpis?.records_total || 0),
      helper: '当前筛选范围',
      icon: 'stack',
      tone: 'brand',
    },
  ]
})

const kpiByKey = computed(() =>
  Object.fromEntries(kpiCards.value.map((card) => [card.key, card])),
)
const pendingKpi = computed(() => kpiByKey.value.pending)
const recordsTotal = computed(() => kpiByKey.value.records.value)

function ratio(part: number, whole: number): number {
  return whole > 0 ? Math.min(100, (part / whole) * 100) : 0
}

function formatRate(value: number): string {
  return String(Math.round(value * 10) / 10)
}

// 进度比例全部由现有 KPI 计算，不引入新口径
const rates = computed(() => ({
  pending: ratio(kpiByKey.value.pending.value, recordsTotal.value),
  completion: ratio(kpiByKey.value.completed.value, recordsTotal.value),
  issue: ratio(kpiByKey.value.risk.value, kpiByKey.value.completed.value + (clinicalQc.value?.kpis.qc_partial_failed_total || 0)),
}))

const metricCards = computed<MetricCard[]>(() => [
  {
    ...kpiByKey.value.risk,
    rate: rates.value.issue,
    rateLabel: `占${clinicalQc.value?.kpis.qc_partial_failed_total ? '有结果病历' : '已完成'} ${formatRate(rates.value.issue)}%`,
  },
  {
    ...kpiByKey.value.completed,
    rate: rates.value.completion,
    rateLabel: `完成率 ${formatRate(rates.value.completion)}%`,
  },
  {
    ...kpiByKey.value.records,
    rate: recordsTotal.value > 0 ? 100 : 0,
    rateLabel: activeDepartmentLabel.value
      ? `${scopeHospitalText.value} · ${activeDepartmentLabel.value}`
      : scopeHospitalText.value,
  },
])

const ringDefs = computed(() => [
  {
    key: 'issue',
    label: '问题率',
    r: 84,
    rate: rates.value.issue,
    gradient: 'qcRingRed',
    from: '#FF6B61',
    to: '#FF3B30',
    textColor: 'var(--qc-danger-text, #c81e32)',
  },
  {
    key: 'completion',
    label: '完成率',
    r: 60,
    rate: rates.value.completion,
    gradient: 'qcRingGreen',
    from: '#5FD97E',
    to: '#34C759',
    textColor: 'var(--qc-success-text, #147a36)',
  },
  {
    key: 'pending',
    label: '待质控',
    r: 36,
    rate: rates.value.pending,
    gradient: 'qcRingAmber',
    from: '#FFB340',
    to: '#FF9500',
    textColor: 'var(--qc-warning-text, #a64d00)',
  },
])

function ringDash(radius: number, rate: number): string {
  const circumference = 2 * Math.PI * radius
  return `${((circumference * rate) / 100).toFixed(1)} ${circumference.toFixed(1)}`
}

const TONE_GRADIENTS: Record<MqIconTone, string> = {
  neutral: 'linear-gradient(90deg, #A1A7B3, #6E7585)',
  brand: 'linear-gradient(90deg, #6FB0FF, #0A6CFF)',
  success: 'linear-gradient(90deg, #6EE08E, #34C759)',
  warning: 'linear-gradient(90deg, #FFC36B, #FF9500)',
  danger: 'linear-gradient(90deg, #FF7A70, #FF3B30)',
}

const TONE_TEXT_COLORS: Record<MqIconTone, string> = {
  neutral: 'var(--mq-text-tertiary)',
  brand: 'var(--qc-brand-text, #0a58cc)',
  success: 'var(--qc-success-text, #147a36)',
  warning: 'var(--qc-warning-text, #a64d00)',
  danger: 'var(--qc-danger-text, #c81e32)',
}

function toneTextColor(tone: MqIconTone): string {
  return TONE_TEXT_COLORS[tone]
}

function toneGradient(tone: MqIconTone): string {
  return TONE_GRADIENTS[tone]
}

const todayLabel = computed(() => dayjs().format('M月D日 dddd'))

// 眉标：日期与范围合成一行纯文字（原先拆成多个胶囊）
const scopeLine = computed(() => {
  const parts = [todayLabel.value]
  if (clinicalQc.value) {
    parts.push(scopeHospitalText.value)
    if (activeDepartmentLabel.value) parts.push(activeDepartmentLabel.value)
    parts.push(scopeSceneText.value)
  } else if (activeDepartmentLabel.value) {
    parts.push(activeDepartmentLabel.value)
  }
  parts.push(scopeRuleSetText.value)
  return parts.join(' · ')
})

const hasPartialFailedConclusion = computed(
  () => !confirmedResultsOnly.value && Boolean(clinicalQc.value?.kpis.qc_partial_failed_total),
)

const conclusionSegments = computed<ConclusionSegment[]>(() => {
  const counts = clinicalQc.value?.canonical_status_counts || {}
  const visibleMeta = confirmedResultsOnly.value
    ? CONCLUSION_STATUS_META.filter((meta) => CONFIRMED_CONCLUSION_STATUSES.has(meta.status))
    : CONCLUSION_STATUS_META
  const values = visibleMeta
    .map((meta) => ({
      ...meta,
      value: Math.max(0, Number(counts[meta.status] || 0)),
    }))
    .filter((segment) => segment.value > 0)
  const total = values.reduce((sum, segment) => sum + segment.value, 0)
  if (!total || !values.length) return []

  // 最大余额法归一化到精确 100.0%（十分之一百分位总和 = 1000），非零项至少 0.1%
  const raw = values.map((segment, index) => {
    const exactTenths = (segment.value / total) * 1000
    const floorTenths = Math.floor(exactTenths)
    return {
      index,
      value: segment.value,
      tenths: Math.max(1, floorTenths),
      remainder: exactTenths - floorTenths,
    }
  })

  let diff = 1000 - raw.reduce((sum, entry) => sum + entry.tenths, 0)
  if (diff > 0) {
    const order = [...raw].sort(
      (a, b) => b.remainder - a.remainder || b.value - a.value || a.index - b.index,
    )
    for (let i = 0; i < diff; i += 1) {
      order[i % order.length].tenths += 1
    }
  } else if (diff < 0) {
    const order = [...raw]
      .filter((entry) => entry.tenths > 1)
      .sort((a, b) => a.remainder - b.remainder || b.value - a.value || b.index - a.index)
    let cursor = 0
    while (diff < 0 && order.length) {
      const target = order[cursor % order.length]
      if (target.tenths > 1) {
        target.tenths -= 1
        diff += 1
      }
      cursor += 1
      if (cursor > order.length * 10) break
    }
  }

  return values.map((segment, index) => ({
    ...segment,
    percent: Number((raw[index].tenths / 10).toFixed(1)),
  }))
})

const conclusionTotal = computed(() =>
  conclusionSegments.value.reduce((sum, segment) => sum + segment.value, 0),
)

const conclusionRingAriaLabel = computed(() => {
  const prefix = hasPartialFailedConclusion.value
    ? `已回写有效规则结论共 ${conclusionTotal.value} 条（含未全部完成病历）`
    : `已完成规则结论共 ${conclusionTotal.value} 条`
  if (!conclusionSegments.value.length) return prefix
  const details = conclusionSegments.value
    .map((segment) => `${segment.label} ${segment.value} 条（${segment.percent.toFixed(1)}%）`)
    .join('，')
  return `${prefix}：${details}`
})

const conclusionRingArcs = computed<ConclusionRingArc[]>(() => {
  const segments = conclusionSegments.value
  const total = conclusionTotal.value
  if (!segments.length || !total) return []

  if (segments.length === 1) {
    return [
      {
        status: segments[0].status,
        color: segments[0].color,
        dashArray: `${CONCLUSION_RING_CIRCUMFERENCE.toFixed(2)} 0`,
        dashOffset: '0',
      },
    ]
  }

  const available = CONCLUSION_RING_CIRCUMFERENCE - segments.length * CONCLUSION_RING_GAP
  const lengths = new Array<number>(segments.length).fill(0)
  const clamped = new Array<boolean>(segments.length).fill(false)

  // 迭代为极小非零切片保留最小可见弧长，其余切片按真实权重占满剩余周长
  let changed = true
  while (changed) {
    changed = false
    let clampedSum = 0
    let freeWeight = 0
    for (let i = 0; i < segments.length; i += 1) {
      if (clamped[i]) {
        clampedSum += CONCLUSION_RING_MIN_ARC
      } else {
        freeWeight += segments[i].value
      }
    }
    const remaining = Math.max(0, available - clampedSum)
    for (let i = 0; i < segments.length; i += 1) {
      if (clamped[i]) {
        lengths[i] = CONCLUSION_RING_MIN_ARC
        continue
      }
      const share = freeWeight > 0 ? (segments[i].value / freeWeight) * remaining : 0
      if (share < CONCLUSION_RING_MIN_ARC) {
        clamped[i] = true
        lengths[i] = CONCLUSION_RING_MIN_ARC
        changed = true
      } else {
        lengths[i] = share
      }
    }
  }

  let cursor = 0
  return segments.map((segment, index) => {
    const length = lengths[index]
    const arc: ConclusionRingArc = {
      status: segment.status,
      color: segment.color,
      dashArray: `${length.toFixed(2)} ${(CONCLUSION_RING_CIRCUMFERENCE - length).toFixed(2)}`,
      dashOffset: `${(-cursor).toFixed(2)}`,
    }
    cursor += length + CONCLUSION_RING_GAP
    return arc
  })
})

const sourceStateText = computed(() => {
  const rawStatus = String(clinicalQc.value?.data_health?.source_sync_status || '').trim()
  const normalized = rawStatus.toLowerCase()
  if (!normalized || normalized === 'unknown') return '待核实'
  return SOURCE_SYNC_STATUS_LABELS[normalized] || rawStatus
})
const runningTaskText = computed(() => {
  const health = clinicalQc.value?.data_health
  const rawState = String(health?.running_task_state || '').trim()
  const normalized = rawState.toLowerCase()
  const total =
    typeof health?.running_task_total === 'number' && Number.isFinite(health.running_task_total)
      ? Math.max(0, health.running_task_total)
      : null

  if (!normalized || normalized === 'unknown') {
    if (total !== null) return total > 0 ? `运行中（${total} 个）` : '空闲'
    return '待接入'
  }
  if (normalized === 'running') {
    return total !== null && total > 0 ? `运行中（${total} 个）` : '运行中'
  }
  if (normalized === 'idle') {
    return total !== null && total > 0 ? `运行中（${total} 个）` : '空闲'
  }
  if (normalized === 'failed' || normalized === 'error') {
    return '任务异常'
  }
  return total !== null && total > 0 ? `${rawState}（${total} 个）` : rawState
})
const analysisObjectLabel = computed(() =>
  analysisObject.value === 'department' ? '科室' : '主治医师',
)
const allDefectAnalysisItems = computed<DefectAnalysisItem[]>(() => {
  if (analysisObject.value === 'physician') {
    return (clinicalQc.value?.physician_distribution || []).map(
      (item: ClinicalQcHomePhysicianItem) => ({
        name: item.physician,
        recordsTotal: Math.max(0, Number(item.records_total || 0)),
        completedRecordTotal: Math.max(0, Number(item.completed_record_total || 0)),
        highRiskReviewTotal: Math.max(0, Number(item.high_risk_review_total || 0)),
        dataGapRecordTotal: Math.max(0, Number(item.data_gap_record_total || 0)),
        defectTotal: Math.max(0, Number(item.defect_total || 0)),
        averageDefectCount: Math.max(0, Number(item.average_defect_count || 0)),
      }),
    )
  }
  return (clinicalQc.value?.department_distribution || []).map(
    (item: ClinicalQcHomeDepartmentItem) => ({
      name: item.department,
      recordsTotal: Math.max(0, Number(item.records_total || 0)),
      completedRecordTotal: Math.max(0, Number(item.completed_record_total || 0)),
      highRiskReviewTotal: Math.max(0, Number(item.high_risk_review_total || 0)),
      dataGapRecordTotal: Math.max(0, Number(item.data_gap_record_total || 0)),
      defectTotal: Math.max(0, Number(item.defect_total || 0)),
      averageDefectCount: Math.max(0, Number(item.average_defect_count || 0)),
    }),
  )
})
const defectAnalysisItems = computed(() => {
  const effectiveSort =
    confirmedResultsOnly.value && analysisSort.value === 'gap' ? 'metric' : analysisSort.value
  return [...allDefectAnalysisItems.value]
    .sort((left, right) => {
      const primary =
        effectiveSort === 'risk'
          ? right.highRiskReviewTotal - left.highRiskReviewTotal
          : effectiveSort === 'gap'
            ? right.dataGapRecordTotal - left.dataGapRecordTotal
            : analysisMetric.value === 'average'
              ? right.averageDefectCount - left.averageDefectCount
              : right.defectTotal - left.defectTotal
      return (
        primary ||
        right.defectTotal - left.defectTotal ||
        right.recordsTotal - left.recordsTotal ||
        left.name.localeCompare(right.name, 'zh-CN')
      )
    })
    .slice(0, 8)
})
const hiddenDefectAnalysisCount = computed(() =>
  Math.max(0, allDefectAnalysisItems.value.length - defectAnalysisItems.value.length),
)
function defectAnalysisValue(item: DefectAnalysisItem): number {
  return analysisMetric.value === 'average' ? item.averageDefectCount : item.defectTotal
}

const defectAnalysisMaximum = computed(() => {
  const max = Math.max(0, ...defectAnalysisItems.value.map((item) => defectAnalysisValue(item)))
  return max > 0 ? max : 1
})

function defectAnalysisPercent(item: DefectAnalysisItem): number {
  const value = defectAnalysisValue(item)
  return Number(((value / defectAnalysisMaximum.value) * 100).toFixed(1))
}

function formatAnalysisMetric(item: DefectAnalysisItem): string {
  return analysisMetric.value === 'average'
    ? item.averageDefectCount.toFixed(2)
    : String(item.defectTotal)
}

function selectDepartment(department: string) {
  departmentFilter.value = departmentFilter.value === department ? 'all' : department
}

function formatDateTime(value?: string | null): string {
  const date = parseQcTaskTime(value)
  if (!date) return '暂未返回'
  const { year, month, day, hour, minute } = shanghaiQcTaskTimeParts(date)
  return `${year}-${month}-${day} ${hour}:${minute}`
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
    path: '/workstation-v5/worklist',
    query: {
      source: 'dashboard',
      department: departmentFilter.value !== 'all' ? departmentFilter.value : undefined,
      keyword: keyword.value.trim() || undefined,
    },
  })
}

function openStageRecordList(stage: 'running' | 'final') {
  void router.push({
    path: `/workstation-v5/records/${stage}`,
    query: {
      department: departmentFilter.value !== 'all' ? departmentFilter.value : undefined,
      keyword: keyword.value.trim() || undefined,
    },
  })
}

function clearKeyword() {
  const query = { ...route.query }
  delete query.keyword
  if (departmentFilter.value === 'all') delete query.department
  else query.department = departmentFilter.value
  void router.replace({ query })
}

function resetFilters() {
  if (typeof route.query.keyword === 'string' || typeof route.query.department === 'string') {
    const query = { ...route.query }
    delete query.keyword
    delete query.department
    void router.replace({ query })
    return
  }
  if (keyword.value.trim()) {
    syncingFromRoute.value = true
    keyword.value = ''
    departmentFilter.value = 'all'
    syncingFromRoute.value = false
    clearKeywordDebounceTimer()
    void fetchHome()
    return
  }
  departmentFilter.value = 'all'
}

const KEYWORD_DEBOUNCE_MS = 280
let fetchSeq = 0
let activeFetchController: AbortController | null = null
let keywordDebounceTimer: ReturnType<typeof setTimeout> | null = null

function clearKeywordDebounceTimer() {
  if (keywordDebounceTimer !== null) {
    clearTimeout(keywordDebounceTimer)
    keywordDebounceTimer = null
  }
}

function abortActiveFetch() {
  if (activeFetchController) {
    activeFetchController.abort()
    activeFetchController = null
  }
}

async function fetchHome() {
  abortActiveFetch()
  const controller = new AbortController()
  activeFetchController = controller
  const seq = ++fetchSeq
  const requestDepartment = departmentFilter.value !== 'all' ? departmentFilter.value : undefined
  const requestKeyword = keyword.value.trim() || undefined
  loading.value = true
  loadError.value = false
  try {
    const res = await ApiService.get<ClinicalQcHomePayload>(
      '/api/v1/workstation/qc-home',
      {
        department: requestDepartment,
        keyword: requestKeyword,
        priority_limit: 20,
      },
      { signal: controller.signal },
    )
    if (seq !== fetchSeq || controller.signal.aborted) return
    if (!res.success || !res.data?.clinical_qc)
      throw new Error(String(res.error || '首页聚合未返回'))
    homeData.value = res.data
    const incomingDepartments = (res.data.department_options ?? [])
      .map((dept) => dept.trim())
      .filter(Boolean)
    if (!requestDepartment && !requestKeyword) {
      cachedDepartmentOptions.value = incomingDepartments
    } else if (incomingDepartments.length) {
      const merged = new Set(cachedDepartmentOptions.value)
      for (const dept of incomingDepartments) merged.add(dept)
      cachedDepartmentOptions.value = Array.from(merged)
    }
  } catch {
    if (seq !== fetchSeq || controller.signal.aborted) return
    homeData.value = null
    loadError.value = true
  } finally {
    if (activeFetchController === controller) {
      activeFetchController = null
    }
    if (seq === fetchSeq) {
      loading.value = false
    }
  }
}

watch(
  confirmedResultsOnly,
  (restricted) => {
    if (restricted && analysisSort.value === 'gap') {
      analysisSort.value = 'metric'
    }
  },
  { immediate: true },
)

watch(
  () => route.fullPath,
  () => {
    clearKeywordDebounceTimer()
    applyRouteFilters()
    void fetchHome()
  },
  { immediate: true },
)

watch(
  departmentFilter,
  () => {
    if (syncingFromRoute.value) return
    clearKeywordDebounceTimer()
    void fetchHome()
  },
  // 路由同步期间立即识别保护标记，由路由监听统一请求，避免重复加载。
  { flush: 'sync' },
)

watch(
  keyword,
  () => {
    if (syncingFromRoute.value) return
    clearKeywordDebounceTimer()
    keywordDebounceTimer = setTimeout(() => {
      keywordDebounceTimer = null
      void fetchHome()
    }, KEYWORD_DEBOUNCE_MS)
  },
  { flush: 'sync' },
)

onBeforeUnmount(() => {
  clearKeywordDebounceTimer()
  abortActiveFetch()
  fetchSeq += 1
})
</script>

<style scoped src="./styles/qc-overview.css"></style>
