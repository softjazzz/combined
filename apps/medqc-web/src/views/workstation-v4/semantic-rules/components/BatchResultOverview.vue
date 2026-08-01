<template>
  <div
    v-if="model"
    class="result-review-overview result-overview-card"
  >
    <div class="result-overview-card-main">
      <div class="result-overview-identity">
        <div class="result-overview-icon">
          <span>质</span>
        </div>
        <div class="result-review-overview-copy">
          <div class="result-review-overview-title-row">
            <h3>{{ model.title }}</h3>
            <span
              class="result-review-status-chip"
              :class="model.statusClass"
            >
              {{ model.statusText }}
            </span>
          </div>
          <div class="result-review-overview-meta">
            <span v-if="model.createdAtText"> 创建时间：{{ model.createdAtText }} </span>
            <span v-if="model.finishedAtText"> 完成时间：{{ model.finishedAtText }} </span>
            <span>规则集：泸县0609质控点验证 v1</span>
            <span>执行病历：{{ model.recordCount }} 份</span>
          </div>
          <p class="result-review-overview-desc">
            {{ model.outcomeText }}
          </p>
          <p class="result-review-overview-scope">
            {{ model.scopeText }}
          </p>
        </div>
      </div>
      <div class="result-review-overview-stats">
        <div>
          <span>病历</span>
          <strong>{{ model.recordCount }}</strong>
          <small>份</small>
        </div>
        <div>
          <span>客户质控点</span>
          <strong>{{ model.customerRuleCount }}</strong>
          <small>个</small>
        </div>
        <div>
          <span>结果</span>
          <strong>{{ model.resultCount }}</strong>
          <small>条</small>
        </div>
      </div>
      <div class="result-overview-status-block">
        <span class="result-overview-status-label">状态分布</span>
        <div class="result-review-status-pills">
          <span
            v-for="item in model.statusPills"
            :key="item.key"
            class="result-review-status-pill"
            :class="item.className"
          >
            {{ item.label }} <strong>{{ item.value }}</strong>
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
type BatchResultOverviewStatusPill = {
  key: string
  label: string
  value: number
  className: string
}

type BatchResultOverviewModel = {
  title: string
  statusClass: string
  statusText: string
  createdAtText: string
  finishedAtText: string
  recordCount: number
  customerRuleCount: number
  resultCount: number
  outcomeText: string
  scopeText: string
  statusPills: BatchResultOverviewStatusPill[]
}

defineProps<{
  model: BatchResultOverviewModel | null
}>()
</script>

<style scoped>
.result-review-overview {
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.04);
  padding: 18px 20px;
}

.result-overview-card {
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.86);
  box-shadow:
    0 2px 12px rgba(0, 0, 0, 0.045),
    0 6px 22px rgba(0, 0, 0, 0.04);
  backdrop-filter: blur(18px);
}

.result-overview-card-main {
  display: grid;
  grid-template-columns: minmax(420px, 1fr) auto minmax(430px, 0.92fr);
  gap: 20px;
  align-items: center;
}

.result-overview-identity {
  display: grid;
  grid-template-columns: 50px minmax(0, 1fr);
  gap: 14px;
  align-items: center;
  min-width: 0;
}

.result-overview-icon {
  display: inline-flex;
  width: 44px;
  height: 44px;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(0, 102, 204, 0.16);
  border-radius: 12px;
  background: rgba(0, 102, 204, 0.08);
  color: #0066cc;
  font-size: 18px;
  font-weight: 850;
  box-shadow: none;
}

.result-overview-status-block {
  min-width: 0;
  border-left: 1px solid rgba(0, 0, 0, 0.08);
  padding-left: 20px;
}

.result-overview-status-label {
  display: block;
  margin-bottom: 8px;
  color: rgba(29, 29, 31, 0.6);
  font-size: 12px;
  font-weight: 800;
  line-height: 18px;
}

.result-overview-status-block .result-review-status-pills {
  margin-top: 0;
}

.result-review-overview-copy {
  min-width: 0;
}

.result-review-overview-title-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.result-review-overview-title-row h3 {
  margin: 0;
  color: #1d1d1f;
  font-size: 17px;
  font-weight: 600;
  line-height: 22px;
}

.result-review-status-chip {
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  border: 1px solid rgba(16, 185, 129, 0.18);
  border-radius: 999px;
  background: rgba(16, 185, 129, 0.08);
  color: #087f5b;
  padding: 0 10px;
  font-size: 12px;
  font-weight: 600;
  line-height: 20px;
}

.result-review-overview-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 14px;
  margin-top: 8px;
  color: rgba(29, 29, 31, 0.6);
  font-size: 12px;
  line-height: 20px;
}

.result-review-overview-desc,
.result-review-overview-scope {
  margin: 8px 0 0;
  color: rgba(29, 29, 31, 0.6);
  font-size: 12px;
  line-height: 20px;
}

.result-review-overview-scope {
  margin-top: 6px;
}

.result-review-overview-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(106px, 1fr));
  gap: 0;
}

.result-review-overview-stats div {
  min-width: 104px;
  border-left: 1px solid rgba(0, 0, 0, 0.08);
  padding: 0 20px;
}

.result-review-overview-stats span {
  display: block;
  color: rgba(29, 29, 31, 0.6);
  font-size: 13px;
  font-weight: 700;
  line-height: 20px;
}

.result-review-overview-stats strong {
  margin-right: 4px;
  color: #1d1d1f;
  font-size: 28px;
  font-weight: 850;
  line-height: 32px;
}

.result-review-overview-stats small {
  color: rgba(29, 29, 31, 0.6);
  font-size: 13px;
  font-weight: 700;
}

.result-review-status-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 18px;
}

.result-review-status-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 32px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.82);
  color: rgba(29, 29, 31, 0.72);
  padding: 0 12px;
  font-size: 12px;
  font-weight: 600;
}

.result-review-status-pill strong {
  font-size: 15px;
}

.result-review-status-pill.is-warning,
.result-review-status-pill.is-success,
.result-review-status-pill.is-muted {
  border-color: rgba(0, 0, 0, 0.08);
  background: rgba(0, 0, 0, 0.035);
  color: rgba(29, 29, 31, 0.68);
}

.result-review-status-pill.is-danger {
  border-color: rgba(239, 68, 68, 0.2);
  background: rgba(239, 68, 68, 0.055);
  color: #b42318;
}
</style>
