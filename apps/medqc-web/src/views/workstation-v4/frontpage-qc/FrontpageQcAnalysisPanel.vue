<template>
  <section
    class="fpqc-analysis"
    data-testid="fpqc-analysis"
  >
    <p
      v-if="loading && !data"
      class="fpqc-analysis__placeholder"
    >
      正在统计…
    </p>
    <p
      v-else-if="error"
      class="fpqc-analysis__placeholder fpqc-analysis__placeholder--danger"
      role="alert"
    >
      {{ error }}
    </p>
    <p
      v-else-if="data && !data.summary.records"
      class="fpqc-analysis__placeholder"
    >
      当前范围内还没有已质控的首页。
    </p>

    <template v-else-if="data">
      <div class="fpqc-analysis__indicators">
        <article
          v-for="item in data.indicators"
          :key="item.key"
          class="mq-card fpqc-analysis__indicator"
          data-testid="fpqc-indicator"
        >
          <span>{{ item.label }}</span>
          <strong>{{ formatPercent(item.rate) }}</strong>
          <small>{{ item.numerator }} / {{ item.denominator }} 份</small>
        </article>
      </div>

      <div class="fpqc-analysis__grid">
        <article class="mq-card mq-card--padded fpqc-analysis__card">
          <h3 class="mq-card__title">
            扣分问题 Top {{ data.top_rules.length }}
          </h3>
          <p class="mq-card__desc">
            按命中病历数排序，含必填缺项
          </p>
          <ol
            v-if="data.top_rules.length"
            class="fpqc-analysis__rank"
          >
            <li
              v-for="item in data.top_rules"
              :key="item.rule_id"
            >
              <span class="fpqc-analysis__rank-name">
                <span class="mq-mono">{{ item.rule_id }}</span> {{ item.rule_name }}
              </span>
              <span class="fpqc-analysis__bar"><span :style="{ width: barWidth(item.rate) }" /></span>
              <strong>{{ item.records }} 份</strong>
            </li>
          </ol>
          <p
            v-else
            class="fpqc-analysis__none"
          >
            暂无扣分问题
          </p>
        </article>

        <article class="mq-card mq-card--padded fpqc-analysis__card">
          <h3 class="mq-card__title">
            科室排名
          </h3>
          <p class="mq-card__desc">
            按平均分由低到高
          </p>
          <div class="fpqc-analysis__table-wrap">
            <table class="mq-table fpqc-analysis__table">
              <thead>
                <tr>
                  <th>科室</th>
                  <th>份数</th>
                  <th>平均分</th>
                  <th>优秀率</th>
                  <th>有扣分问题</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="item in data.departments"
                  :key="item.department"
                >
                  <td>{{ item.department }}</td>
                  <td>{{ item.records }}</td>
                  <td>{{ formatScore(item.avg_score) }}</td>
                  <td>{{ formatPercent(item.excellent_rate) }}</td>
                  <td>{{ item.issue_records }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </article>

        <article class="mq-card mq-card--padded fpqc-analysis__card">
          <h3 class="mq-card__title">
            提示 Top {{ data.top_hints.length }}
          </h3>
          <p class="mq-card__desc">
            不扣分，需人工核实
          </p>
          <ol
            v-if="data.top_hints.length"
            class="fpqc-analysis__rank"
          >
            <li
              v-for="item in data.top_hints"
              :key="item.rule_id"
            >
              <span class="fpqc-analysis__rank-name">{{ item.rule_name }}</span>
              <span class="fpqc-analysis__bar fpqc-analysis__bar--hint"><span :style="{ width: barWidth(item.rate) }" /></span>
              <strong>{{ item.records }} 份</strong>
            </li>
          </ol>
          <p
            v-else
            class="fpqc-analysis__none"
          >
            暂无提示
          </p>
        </article>

        <article class="mq-card mq-card--padded fpqc-analysis__card">
          <h3 class="mq-card__title">
            资料不足来源
          </h3>
          <p class="mq-card__desc">
            首页同步未带入或缺少记录的项目，不扣分；供数据同步排查
          </p>
          <ol
            v-if="data.top_data_gaps.length"
            class="fpqc-analysis__rank"
          >
            <li
              v-for="item in data.top_data_gaps"
              :key="item.rule_id"
            >
              <span class="fpqc-analysis__rank-name">{{ item.rule_name }}</span>
              <span class="fpqc-analysis__bar fpqc-analysis__bar--gap"><span :style="{ width: barWidth(item.rate) }" /></span>
              <strong>{{ item.records }} 份</strong>
            </li>
          </ol>
          <p
            v-else
            class="fpqc-analysis__none"
          >
            无资料不足项
          </p>
        </article>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

import {
  getFrontpageQcAnalytics,
  type FrontpageQcAnalytics,
  type FrontpageQcScopeFilters,
} from '@/services/frontpage-qc-v2-service'

import { formatPercent, formatScore } from './presentation'

const props = defineProps<{ filters: FrontpageQcScopeFilters; refreshKey: number }>()

const data = ref<FrontpageQcAnalytics | null>(null)
const loading = ref(false)
const error = ref('')
let seq = 0

function barWidth(rate: number | null) {
  return `${Math.max(2, Math.round((rate ?? 0) * 100))}%`
}

async function load() {
  const current = ++seq
  loading.value = true
  error.value = ''
  try {
    const next = await getFrontpageQcAnalytics(props.filters)
    if (current === seq) data.value = next
  } catch (err) {
    if (current === seq) error.value = err instanceof Error ? err.message : '读取首页质控统计失败'
  } finally {
    if (current === seq) loading.value = false
  }
}

watch(
  () => [props.filters.department, props.filters.start_date, props.filters.end_date, props.refreshKey],
  () => {
    void load()
  },
  { immediate: true },
)
</script>

<style scoped>
.fpqc-analysis {
  display: grid;
  gap: 16px;
}

.fpqc-analysis__placeholder {
  margin: 48px 0;
  color: var(--mq-text-tertiary);
  text-align: center;
}

.fpqc-analysis__placeholder--danger {
  color: var(--mq-danger-text);
}

.fpqc-analysis__indicators {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
}

.fpqc-analysis__indicator {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 16px 20px;
}

.fpqc-analysis__indicator span {
  color: var(--mq-text-secondary);
  font-size: var(--mq-font-13);
}

.fpqc-analysis__indicator strong {
  font-family: var(--mq-font-display);
  font-size: 26px;
  line-height: 1.1;
}

.fpqc-analysis__indicator small {
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-12);
}

.fpqc-analysis__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 440px), 1fr));
  gap: 16px;
}

.fpqc-analysis__card {
  display: grid;
  align-content: start;
  gap: 12px;
  min-width: 0;
}

.fpqc-analysis__rank {
  display: grid;
  gap: 10px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.fpqc-analysis__rank li {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(60px, 1fr) auto;
  align-items: center;
  gap: 10px;
  font-size: var(--mq-font-13);
}

.fpqc-analysis__rank-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.fpqc-analysis__rank strong {
  white-space: nowrap;
}

.fpqc-analysis__bar {
  height: 8px;
  overflow: hidden;
  border-radius: 999px;
  background: var(--mq-bg-muted);
}

.fpqc-analysis__bar span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--mq-danger-icon);
}

.fpqc-analysis__bar--hint span {
  background: var(--mq-info-icon);
}

.fpqc-analysis__bar--gap span {
  background: var(--mq-warning-icon);
}

.fpqc-analysis__table-wrap {
  max-height: 360px;
  overflow: auto;
}

.fpqc-analysis__table thead th {
  position: sticky;
  top: 0;
  z-index: 1;
  background: var(--mq-bg-surface);
}

.fpqc-analysis__table td,
.fpqc-analysis__table th {
  white-space: nowrap;
}

.fpqc-analysis__none {
  margin: 0;
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-13);
}
</style>
