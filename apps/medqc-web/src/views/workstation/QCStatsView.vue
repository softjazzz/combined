<template>
  <div class="stats-container">
    <!-- 头部 -->
    <div class="stats-header">
      <h2>
        <BarChartOutlined />
        质控统计分析
      </h2>
      <div class="header-actions">
        <a-segmented v-model:value="timePeriod" :options="timePeriods" size="small" />
      </div>
    </div>

    <!-- 关键指标 -->
    <div class="kpi-grid">
      <div v-for="kpi in kpiData" :key="kpi.label" class="kpi-card" :style="{ borderTopColor: kpi.color }">
        <div class="kpi-header">
          <span class="kpi-label">{{ kpi.label }}</span>
          <component :is="kpi.icon" :style="{ color: kpi.color }" />
        </div>
        <div class="kpi-value">{{ kpi.value }}</div>
        <div class="kpi-sub">{{ kpi.subLabel }}: {{ kpi.subValue }}</div>
        <div class="kpi-progress">
          <a-progress :percent="kpi.percent" :stroke-color="kpi.color" :show-info="false" size="small" />
          <span class="kpi-target">目标: {{ kpi.target }}</span>
        </div>
      </div>
    </div>

    <!-- 图表区域 -->
    <div class="chart-grid">
      <!-- 质控趋势 -->
      <div class="chart-card">
        <div class="chart-title">每日质控量趋势（近 14 天）</div>
        <div class="chart-body">
          <div class="bar-chart">
            <div v-for="(bar, idx) in trendData" :key="idx" class="bar-group">
              <div class="bar-wrapper">
                <div class="bar" :style="{ height: bar.height + '%', background: '#1677ff' }">
                  <span class="bar-value">{{ bar.value }}</span>
                </div>
              </div>
              <span class="bar-label">{{ bar.label }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 科室分布 -->
      <div class="chart-card">
        <div class="chart-title">科室质控问题分布</div>
        <div class="chart-body">
          <div v-for="dept in deptDistribution" :key="dept.name" class="dist-item">
            <div class="dist-header">
              <span>{{ dept.name }}</span>
              <span>{{ dept.count }} 个问题（{{ dept.percent }}%）</span>
            </div>
            <a-progress :percent="dept.percent" :stroke-color="dept.color" :show-info="false" size="small" />
          </div>
        </div>
      </div>
    </div>

    <!-- 下方详细数据 -->
    <div class="chart-grid">
      <!-- 问题类型 -->
      <div class="chart-card">
        <div class="chart-title">问题类型 Top 5</div>
        <div class="chart-body">
          <div v-for="(item, idx) in topIssues" :key="item.name" class="top-item">
            <div class="top-rank" :class="idx < 3 ? 'hot' : ''">{{ idx + 1 }}</div>
            <div class="top-info">
              <div class="top-name">{{ item.name }}</div>
              <a-progress :percent="item.percent" :stroke-color="idx < 3 ? '#ff4d4f' : '#faad14'" size="small" style="width: 200px" />
            </div>
            <div class="top-count">{{ item.count }} 次</div>
          </div>
        </div>
      </div>

      <!-- 首页填充率 -->
      <div class="chart-card">
        <div class="chart-title">病案首页 AI 提取质量</div>
        <div class="chart-body">
          <div class="quality-grid">
            <div v-for="q in qualityMetrics" :key="q.label" class="quality-item">
              <a-progress type="circle" :percent="q.value" :width="80" :stroke-color="q.value >= 90 ? '#52c41a' : q.value >= 80 ? '#faad14' : '#ff4d4f'" />
              <div class="quality-label">{{ q.label }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  BarChartOutlined,
  FileTextOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  AlertOutlined,
  AimOutlined,
} from '@ant-design/icons-vue'

const timePeriod = ref('week')
const timePeriods = [
  { label: '本周', value: 'week' },
  { label: '本月', value: 'month' },
  { label: '本季', value: 'quarter' },
]

// KPI 数据
const kpiData = computed(() => [
  {
    label: '质控病历数',
    value: '156',
    subLabel: '今日新增',
    subValue: '12',
    percent: 78,
    target: '200',
    color: '#1677ff',
    icon: FileTextOutlined,
  },
  {
    label: '平均合格率',
    value: '91.3%',
    subLabel: '较上周',
    subValue: '+2.1%',
    percent: 91,
    target: '95%',
    color: '#52c41a',
    icon: CheckCircleOutlined,
  },
  {
    label: '首页生成耗时',
    value: '18.5s',
    subLabel: 'P95',
    subValue: '28.3s',
    percent: 72,
    target: '≤30s',
    color: '#faad14',
    icon: ClockCircleOutlined,
  },
  {
    label: 'ICD 命中率',
    value: '87.6%',
    subLabel: 'Top-3',
    subValue: '92.1%',
    percent: 88,
    target: '≥85%',
    color: '#722ed1',
    icon: AimOutlined,
  },
])

// 趋势数据
const trendData = computed(() => {
  const days = ['2/15', '2/16', '2/17', '2/18', '2/19', '2/20', '2/21', '2/22', '2/23', '2/24', '2/25', '2/26', '2/27', '2/28']
  const values = [8, 12, 15, 10, 14, 18, 11, 9, 16, 20, 13, 17, 22, 12]
  const max = Math.max(...values)
  return days.map((label, idx) => ({
    label,
    value: values[idx],
    height: (values[idx] / max) * 90,
  }))
})

// 科室分布
const deptDistribution = [
  { name: '心内科', count: 28, percent: 22, color: '#1677ff' },
  { name: '呼吸内科', count: 24, percent: 19, color: '#52c41a' },
  { name: '普外科', count: 21, percent: 17, color: '#faad14' },
  { name: '骨科', count: 18, percent: 14, color: '#722ed1' },
  { name: '产科', count: 15, percent: 12, color: '#13c2c2' },
  { name: '其他', count: 20, percent: 16, color: '#8c8c8c' },
]

// Top 问题
const topIssues = [
  { name: '出院记录缺失或不完整', count: 32, percent: 85 },
  { name: '诊断编码未填写', count: 28, percent: 74 },
  { name: '入院24h内首次病程未完成', count: 22, percent: 58 },
  { name: '手术记录时限超标', count: 15, percent: 40 },
  { name: '知情同意书缺失', count: 12, percent: 32 },
]

// AI 提取质量
const qualityMetrics = [
  { label: '字段填充率', value: 92 },
  { label: '诊断提取', value: 88 },
  { label: 'ICD Top3', value: 87 },
  { label: '手术提取', value: 83 },
]
</script>

<style scoped>
.stats-container {
  padding: 20px 24px;
  max-width: 1400px;
  margin: 0 auto;
}

.stats-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.stats-header h2 {
  margin: 0;
  font-size: 20px;
  display: flex;
  align-items: center;
  gap: 8px;
}

/* KPI 卡片 */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

.kpi-card {
  background: #fff;
  border-radius: 12px;
  padding: 20px;
  border-top: 3px solid;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}

.kpi-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.kpi-label {
  font-size: 13px;
  color: #888;
}

.kpi-value {
  font-size: 32px;
  font-weight: 700;
  color: #1a1a1a;
  line-height: 1.2;
}

.kpi-sub {
  font-size: 12px;
  color: #999;
  margin: 4px 0 12px;
}

.kpi-progress {
  display: flex;
  align-items: center;
  gap: 8px;
}

.kpi-target {
  font-size: 11px;
  color: #bbb;
  white-space: nowrap;
}

/* 图表卡片 */
.chart-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 20px;
}

.chart-card {
  background: #fff;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}

.chart-title {
  font-weight: 600;
  font-size: 14px;
  margin-bottom: 16px;
  color: #1a1a1a;
}

/* 柱状图 */
.bar-chart {
  display: flex;
  align-items: flex-end;
  gap: 6px;
  height: 180px;
}

.bar-group {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.bar-wrapper {
  width: 100%;
  height: 150px;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}

.bar {
  width: 80%;
  border-radius: 3px 3px 0 0;
  position: relative;
  transition: height 0.5s ease;
  min-height: 4px;
}

.bar-value {
  position: absolute;
  top: -18px;
  left: 50%;
  transform: translateX(-50%);
  font-size: 10px;
  color: #888;
  white-space: nowrap;
}

.bar-label {
  font-size: 10px;
  color: #999;
  margin-top: 4px;
}

/* 分布 */
.dist-item {
  margin-bottom: 12px;
}

.dist-header {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  margin-bottom: 4px;
}

/* Top 问题 */
.top-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid #f5f5f5;
}

.top-rank {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  background: #f0f0f0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  color: #888;
  flex-shrink: 0;
}

.top-rank.hot {
  background: #fff2f0;
  color: #ff4d4f;
}

.top-info {
  flex: 1;
}

.top-name {
  font-size: 13px;
  color: #333;
  margin-bottom: 4px;
}

.top-count {
  font-size: 13px;
  font-weight: 600;
  color: #1a1a1a;
  flex-shrink: 0;
}

/* 质量指标 */
.quality-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  text-align: center;
}

.quality-label {
  margin-top: 8px;
  font-size: 12px;
  color: #666;
}
</style>
