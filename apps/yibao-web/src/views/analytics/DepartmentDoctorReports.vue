<template>
  <div class="department-doctor-reports">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-content">
        <h1>科室医生质控报告</h1>
        <p>科室绩效分析与医生个人质控档案</p>
      </div>
      <div class="header-actions">
        <a-space>
          <a-select v-model:value="timeRange" @change="refreshData" style="width: 120px">
            <a-select-option value="7d">最近7天</a-select-option>
            <a-select-option value="30d">最近30天</a-select-option>
            <a-select-option value="90d">最近90天</a-select-option>
          </a-select>
          <a-button type="primary" @click="exportReports" :loading="exporting">
            <template #icon><DownloadOutlined /></template>
            批量导出
          </a-button>
          <a-button @click="refreshData" :loading="loading">
            <template #icon><ReloadOutlined /></template>
            刷新数据
          </a-button>
        </a-space>
      </div>
    </div>

    <!-- 标签页切换 -->
    <a-tabs v-model:activeKey="activeTab" @change="onTabChange">
      <!-- 科室分析标签页 -->
      <a-tab-pane key="departments" tab="科室分析">
        <div class="departments-analysis">
          <!-- 科室概览指标 -->
          <div class="overview-metrics">
            <a-row :gutter="[16, 16]">
              <a-col :xs="24" :sm="12" :md="6">
                <a-card class="metric-card">
                  <a-statistic
                    title="参与科室数"
                    :value="departmentSummary.total_departments"
                    :value-style="{ color: '#1890ff' }"
                  >
                    <template #prefix><BankOutlined /></template>
                  </a-statistic>
                </a-card>
              </a-col>
              <a-col :xs="24" :sm="12" :md="6">
                <a-card class="metric-card">
                  <a-statistic
                    title="平均违规率"
                    :value="departmentSummary.avg_violation_rate"
                    :precision="2"
                    suffix="%"
                    :value-style="{ color: '#faad14' }"
                  >
                    <template #prefix><ExclamationCircleOutlined /></template>
                  </a-statistic>
                </a-card>
              </a-col>
              <a-col :xs="24" :sm="12" :md="6">
                <a-card class="metric-card">
                  <a-statistic
                    title="高风险科室"
                    :value="departmentSummary.high_risk_departments"
                    :value-style="{ color: '#ff4d4f' }"
                  >
                    <template #prefix><WarningOutlined /></template>
                  </a-statistic>
                </a-card>
              </a-col>
              <a-col :xs="24" :sm="12" :md="6">
                <a-card class="metric-card">
                  <a-statistic
                    title="改进趋势科室"
                    :value="departmentSummary.departments_with_increasing_trend"
                    :value-style="{ color: '#52c41a' }"
                  >
                    <template #prefix><ArrowUpOutlined /></template>
                  </a-statistic>
                </a-card>
              </a-col>
            </a-row>
          </div>

          <!-- 科室排行榜和对比图表 -->
          <a-row :gutter="[24, 24]">
            <a-col :xs="24" :lg="14">
              <a-card title="科室绩效排行" class="ranking-card">
                <template #extra>
                  <a-radio-group v-model:value="rankingMetric" @change="updateRankingChart" size="small">
                    <a-radio-button value="violation_rate">违规率</a-radio-button>
                    <a-radio-button value="quality_score">质控评分</a-radio-button>
                    <a-radio-button value="improvement">改进幅度</a-radio-button>
                  </a-radio-group>
                </template>
                <div ref="departmentRankingChartRef" class="chart-container"></div>
              </a-card>
            </a-col>
            <a-col :xs="24" :lg="10">
              <a-card title="风险分布" class="risk-distribution-card">
                <div ref="riskDistributionChartRef" class="chart-container"></div>
                <div class="risk-legend">
                  <div class="legend-item">
                    <span class="legend-color high-risk"></span>
                    <span>高风险 (违规率 > 5%)</span>
                  </div>
                  <div class="legend-item">
                    <span class="legend-color medium-risk"></span>
                    <span>中风险 (2% < 违规率 ≤ 5%)</span>
                  </div>
                  <div class="legend-item">
                    <span class="legend-color low-risk"></span>
                    <span>低风险 (违规率 ≤ 2%)</span>
                  </div>
                </div>
              </a-card>
            </a-col>
          </a-row>

          <!-- 科室详细列表 -->
          <a-card title="科室详细分析" class="departments-table-card">
            <template #extra>
              <a-space>
                <a-input-search
                  v-model:value="departmentSearchText"
                  placeholder="搜索科室"
                  style="width: 200px"
                  @search="filterDepartments"
                />
                <a-select v-model:value="departmentFilter" @change="filterDepartments" style="width: 120px">
                  <a-select-option value="">全部风险</a-select-option>
                  <a-select-option value="high">高风险</a-select-option>
                  <a-select-option value="medium">中风险</a-select-option>
                  <a-select-option value="low">低风险</a-select-option>
                </a-select>
              </a-space>
            </template>
            <a-table
              :dataSource="filteredDepartments"
              :columns="departmentColumns"
              :pagination="{ pageSize: 10, showSizeChanger: true }"
              :loading="loading"
              row-key="department_code"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'risk_level'">
                  <a-tag :color="getRiskColor(record.risk_level)">
                    {{ getRiskText(record.risk_level) }}
                  </a-tag>
                </template>
                <template v-if="column.key === 'trend'">
                  <span :class="getTrendClass(record.trend)">
                    <component :is="getTrendIcon(record.trend)" />
                    {{ getTrendText(record.trend) }}
                  </span>
                </template>
                <template v-if="column.key === 'actions'">
                  <a-space>
                    <a-button type="link" size="small" @click="viewDepartmentDetail(record)">
                      详情
                    </a-button>
                    <a-button type="link" size="small" @click="exportDepartmentReport(record)">
                      导出
                    </a-button>
                  </a-space>
                </template>
              </template>
            </a-table>
          </a-card>
        </div>
      </a-tab-pane>

      <!-- 医生分析标签页 -->
      <a-tab-pane key="doctors" tab="医生分析">
        <div class="doctors-analysis">
          <!-- 医生概览指标 -->
          <div class="overview-metrics">
            <a-row :gutter="[16, 16]">
              <a-col :xs="24" :sm="12" :md="6">
                <a-card class="metric-card">
                  <a-statistic
                    title="参与医生数"
                    :value="doctorSummary.total_doctors"
                    :value-style="{ color: '#1890ff' }"
                  >
                    <template #prefix><UserOutlined /></template>
                  </a-statistic>
                </a-card>
              </a-col>
              <a-col :xs="24" :sm="12" :md="6">
                <a-card class="metric-card">
                  <a-statistic
                    title="平均质控评分"
                    :value="doctorSummary.avg_quality_score"
                    :precision="1"
                    :value-style="{ color: '#52c41a' }"
                  >
                    <template #prefix><StarOutlined /></template>
                  </a-statistic>
                </a-card>
              </a-col>
              <a-col :xs="24" :sm="12" :md="6">
                <a-card class="metric-card">
                  <a-statistic
                    title="高风险医生"
                    :value="doctorSummary.high_risk_doctors"
                    :value-style="{ color: '#ff4d4f' }"
                  >
                    <template #prefix><AlertOutlined /></template>
                  </a-statistic>
                </a-card>
              </a-col>
              <a-col :xs="24" :sm="12" :md="6">
                <a-card class="metric-card">
                  <a-statistic
                    title="优秀医生 (A级)"
                    :value="doctorSummary.grade_distribution?.A || 0"
                    :value-style="{ color: '#722ed1' }"
                  >
                    <template #prefix><CrownOutlined /></template>
                  </a-statistic>
                </a-card>
              </a-col>
            </a-row>
          </div>

          <!-- 医生绩效分析图表 -->
          <a-row :gutter="[24, 24]">
            <a-col :xs="24" :lg="12">
              <a-card title="绩效等级分布" class="grade-distribution-card">
                <div ref="gradeDistributionChartRef" class="chart-container"></div>
              </a-card>
            </a-col>
            <a-col :xs="24" :lg="12">
              <a-card title="质控评分分布" class="score-distribution-card">
                <div ref="scoreDistributionChartRef" class="chart-container"></div>
              </a-card>
            </a-col>
          </a-row>

          <!-- 医生筛选和列表 -->
          <a-card title="医生质控档案" class="doctors-table-card">
            <template #extra>
              <a-space>
                <a-select
                  v-model:value="selectedDepartment"
                  @change="filterDoctors"
                  placeholder="选择科室"
                  style="width: 150px"
                  allow-clear
                >
                  <a-select-option v-for="dept in departments" :key="dept.department_code" :value="dept.department_code">
                    {{ dept.department_name }}
                  </a-select-option>
                </a-select>
                <a-select v-model:value="doctorGradeFilter" @change="filterDoctors" style="width: 100px">
                  <a-select-option value="">全部等级</a-select-option>
                  <a-select-option value="A">A级</a-select-option>
                  <a-select-option value="B">B级</a-select-option>
                  <a-select-option value="C">C级</a-select-option>
                  <a-select-option value="D">D级</a-select-option>
                </a-select>
                <a-input-search
                  v-model:value="doctorSearchText"
                  placeholder="搜索医生"
                  style="width: 200px"
                  @search="filterDoctors"
                />
              </a-space>
            </template>
            <a-table
              :dataSource="filteredDoctors"
              :columns="doctorColumns"
              :pagination="{ pageSize: 10, showSizeChanger: true }"
              :loading="loading"
              row-key="doctor_code"
              :expandable="{ expandedRowRender: renderDoctorDetail }"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'performance_grade'">
                  <a-tag :color="getGradeColor(record.performance_grade)">
                    {{ record.performance_grade }}级
                  </a-tag>
                </template>
                <template v-if="column.key === 'risk_level'">
                  <a-tag :color="getRiskColor(record.risk_level)">
                    {{ getRiskText(record.risk_level) }}
                  </a-tag>
                </template>
                <template v-if="column.key === 'quality_score'">
                  <a-progress
                    :percent="record.quality_score"
                    size="small"
                    :stroke-color="getScoreColor(record.quality_score)"
                  />
                </template>
                <template v-if="column.key === 'actions'">
                  <a-space>
                    <a-button type="link" size="small" @click="viewDoctorProfile(record)">
                      档案
                    </a-button>
                    <a-button type="link" size="small" @click="exportDoctorReport(record)">
                      导出
                    </a-button>
                  </a-space>
                </template>
              </template>
            </a-table>
          </a-card>
        </div>
      </a-tab-pane>
    </a-tabs>

    <!-- 科室详情模态框 -->
    <a-modal
      v-model:open="departmentDetailVisible"
      :title="`${selectedDepartmentDetail?.department_name} - 详细分析`"
      width="800px"
      :footer="null"
    >
      <div v-if="selectedDepartmentDetail" class="department-detail">
        <a-descriptions :column="2" bordered>
          <a-descriptions-item label="科室编码">{{ selectedDepartmentDetail.department_code }}</a-descriptions-item>
          <a-descriptions-item label="风险等级">
            <a-tag :color="getRiskColor(selectedDepartmentDetail.risk_level)">
              {{ getRiskText(selectedDepartmentDetail.risk_level) }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="总违规数">{{ selectedDepartmentDetail.total_violations }}</a-descriptions-item>
          <a-descriptions-item label="违规率">{{ selectedDepartmentDetail.violation_rate }}%</a-descriptions-item>
          <a-descriptions-item label="涉及就诊">{{ selectedDepartmentDetail.unique_visits }}</a-descriptions-item>
          <a-descriptions-item label="触发规则">{{ selectedDepartmentDetail.unique_rules }}</a-descriptions-item>
        </a-descriptions>

        <div class="detail-charts">
          <h4>违规类型分布</h4>
          <div ref="departmentDetailChartRef" class="chart-container small"></div>
        </div>

        <div class="top-rules">
          <h4>高频违规规则 (Top 5)</h4>
          <a-list
            :dataSource="selectedDepartmentDetail.top_rules"
            size="small"
          >
            <template #renderItem="{ item, index }">
              <a-list-item>
                <a-list-item-meta>
                  <template #title>
                    <span>{{ index + 1 }}. {{ item.name }}</span>
                  </template>
                  <template #description>
                    规则编码: {{ item.code }} | 违规次数: {{ item.count }}
                  </template>
                </a-list-item-meta>
              </a-list-item>
            </template>
          </a-list>
        </div>
      </div>
    </a-modal>

    <!-- 医生档案模态框 -->
    <a-modal
      v-model:open="doctorProfileVisible"
      :title="`${selectedDoctorProfile?.doctor_name} - 质控档案`"
      width="800px"
      :footer="null"
    >
      <div v-if="selectedDoctorProfile" class="doctor-profile">
        <a-descriptions :column="2" bordered>
          <a-descriptions-item label="医生编码">{{ selectedDoctorProfile.doctor_code }}</a-descriptions-item>
          <a-descriptions-item label="所属科室">{{ selectedDoctorProfile.department_name }}</a-descriptions-item>
          <a-descriptions-item label="绩效等级">
            <a-tag :color="getGradeColor(selectedDoctorProfile.performance_grade)">
              {{ selectedDoctorProfile.performance_grade }}级
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="风险等级">
            <a-tag :color="getRiskColor(selectedDoctorProfile.risk_level)">
              {{ getRiskText(selectedDoctorProfile.risk_level) }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="质控评分">
            <a-progress
              :percent="selectedDoctorProfile.quality_score"
              size="small"
              :stroke-color="getScoreColor(selectedDoctorProfile.quality_score)"
            />
          </a-descriptions-item>
          <a-descriptions-item label="违规率">{{ selectedDoctorProfile.violation_rate }}%</a-descriptions-item>
        </a-descriptions>

        <div class="improvement-suggestions">
          <h4>改进建议</h4>
          <a-list
            :dataSource="selectedDoctorProfile.improvement_suggestions"
            size="small"
          >
            <template #renderItem="{ item, index }">
              <a-list-item>
                <a-typography-text>{{ index + 1 }}. {{ item }}</a-typography-text>
              </a-list-item>
            </template>
          </a-list>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { message } from 'ant-design-vue'
import * as echarts from 'echarts'
import {
  DownloadOutlined,
  ReloadOutlined,
  BankOutlined,
  ExclamationCircleOutlined,
  WarningOutlined,
  ArrowUpOutlined,
  UserOutlined,
  StarOutlined,
  AlertOutlined,
  CrownOutlined,
  ArrowDownOutlined,
  MinusOutlined
} from '@ant-design/icons-vue'

// 响应式数据
const loading = ref(false)
const exporting = ref(false)
const activeTab = ref('departments')
const timeRange = ref('30d')
const rankingMetric = ref('violation_rate')

// 科室相关
const departmentSearchText = ref('')
const departmentFilter = ref('')
const departmentDetailVisible = ref(false)
const selectedDepartmentDetail = ref(null)

// 医生相关
const selectedDepartment = ref('')
const doctorGradeFilter = ref('')
const doctorSearchText = ref('')
const doctorProfileVisible = ref(false)
const selectedDoctorProfile = ref(null)

// 数据状态
const departments = ref([])
const doctors = ref([])
const departmentSummary = ref({
  total_departments: 0,
  avg_violation_rate: 0,
  high_risk_departments: 0,
  departments_with_increasing_trend: 0
})
const doctorSummary = ref({
  total_doctors: 0,
  avg_quality_score: 0,
  high_risk_doctors: 0,
  grade_distribution: { A: 0, B: 0, C: 0, D: 0 }
})

// 图表引用
const departmentRankingChartRef = ref<HTMLDivElement>()
const riskDistributionChartRef = ref<HTMLDivElement>()
const gradeDistributionChartRef = ref<HTMLDivElement>()
const scoreDistributionChartRef = ref<HTMLDivElement>()
const departmentDetailChartRef = ref<HTMLDivElement>()

// 图表实例
let departmentRankingChart: echarts.ECharts | null = null
let riskDistributionChart: echarts.ECharts | null = null
let gradeDistributionChart: echarts.ECharts | null = null
let scoreDistributionChart: echarts.ECharts | null = null
let departmentDetailChart: echarts.ECharts | null = null

// 计算属性
const filteredDepartments = computed(() => {
  let filtered = departments.value

  if (departmentSearchText.value) {
    filtered = filtered.filter(dept => 
      dept.department_name.includes(departmentSearchText.value) ||
      dept.department_code.includes(departmentSearchText.value)
    )
  }

  if (departmentFilter.value) {
    filtered = filtered.filter(dept => dept.risk_level === departmentFilter.value)
  }

  return filtered
})

const filteredDoctors = computed(() => {
  let filtered = doctors.value

  if (selectedDepartment.value) {
    filtered = filtered.filter(doctor => doctor.department_code === selectedDepartment.value)
  }

  if (doctorGradeFilter.value) {
    filtered = filtered.filter(doctor => doctor.performance_grade === doctorGradeFilter.value)
  }

  if (doctorSearchText.value) {
    filtered = filtered.filter(doctor => 
      doctor.doctor_name.includes(doctorSearchText.value) ||
      doctor.doctor_code.includes(doctorSearchText.value)
    )
  }

  return filtered
})

// 表格列定义
const departmentColumns = [
  { title: '科室名称', dataIndex: 'department_name', key: 'department_name', width: 150 },
  { title: '违规数', dataIndex: 'total_violations', key: 'total_violations', width: 100, sorter: true },
  { title: '违规率(%)', dataIndex: 'violation_rate', key: 'violation_rate', width: 100, sorter: true },
  { title: '风险等级', dataIndex: 'risk_level', key: 'risk_level', width: 100 },
  { title: '趋势', dataIndex: 'trend', key: 'trend', width: 100 },
  { title: '涉及就诊', dataIndex: 'unique_visits', key: 'unique_visits', width: 100 },
  { title: '操作', key: 'actions', width: 120 }
]

const doctorColumns = [
  { title: '医生姓名', dataIndex: 'doctor_name', key: 'doctor_name', width: 120 },
  { title: '科室', dataIndex: 'department_name', key: 'department_name', width: 120 },
  { title: '违规数', dataIndex: 'total_violations', key: 'total_violations', width: 80, sorter: true },
  { title: '违规率(%)', dataIndex: 'violation_rate', key: 'violation_rate', width: 100, sorter: true },
  { title: '质控评分', dataIndex: 'quality_score', key: 'quality_score', width: 120 },
  { title: '绩效等级', dataIndex: 'performance_grade', key: 'performance_grade', width: 100 },
  { title: '风险等级', dataIndex: 'risk_level', key: 'risk_level', width: 100 },
  { title: '操作', key: 'actions', width: 120 }
]

// 方法
const refreshData = async () => {
  loading.value = true
  try {
    if (activeTab.value === 'departments') {
      await loadDepartmentData()
    } else {
      await loadDoctorData()
    }
  } catch (error) {
    message.error('数据加载失败')
    console.error('Failed to refresh data:', error)
  } finally {
    loading.value = false
  }
}

const loadDepartmentData = async () => {
  // 模拟加载科室数据
  departments.value = [
    {
      department_code: 'CARDIO',
      department_name: '心内科',
      total_violations: 45,
      violation_rate: 3.2,
      risk_level: 'medium',
      trend: 'decreasing',
      unique_visits: 1420,
      unique_rules: 12,
      top_rules: [
        { code: 'YB001', name: '药品超量使用', count: 15 },
        { code: 'YB002', name: '检查项目重复', count: 12 }
      ]
    },
    {
      department_code: 'NEURO',
      department_name: '神经科',
      total_violations: 23,
      violation_rate: 1.8,
      risk_level: 'low',
      trend: 'stable',
      unique_visits: 1280,
      unique_rules: 8,
      top_rules: [
        { code: 'YB003', name: '诊断编码错误', count: 8 },
        { code: 'YB004', name: '治疗方案不当', count: 6 }
      ]
    }
  ]

  departmentSummary.value = {
    total_departments: departments.value.length,
    avg_violation_rate: 2.5,
    high_risk_departments: 0,
    departments_with_increasing_trend: 1
  }

  await nextTick()
  initDepartmentCharts()
}

const loadDoctorData = async () => {
  // 模拟加载医生数据
  doctors.value = [
    {
      doctor_code: 'DOC001',
      doctor_name: '张医生',
      department_code: 'CARDIO',
      department_name: '心内科',
      total_violations: 12,
      violation_rate: 2.1,
      quality_score: 85,
      performance_grade: 'B',
      risk_level: 'low',
      improvement_suggestions: [
        '重点关注药品使用规范',
        '建议参加质控培训'
      ]
    },
    {
      doctor_code: 'DOC002',
      doctor_name: '李医生',
      department_code: 'NEURO',
      department_name: '神经科',
      total_violations: 5,
      violation_rate: 1.2,
      quality_score: 92,
      performance_grade: 'A',
      risk_level: 'low',
      improvement_suggestions: [
        '继续保持良好表现'
      ]
    }
  ]

  doctorSummary.value = {
    total_doctors: doctors.value.length,
    avg_quality_score: 88.5,
    high_risk_doctors: 0,
    grade_distribution: { A: 1, B: 1, C: 0, D: 0 }
  }

  await nextTick()
  initDoctorCharts()
}

const initDepartmentCharts = () => {
  initDepartmentRankingChart()
  initRiskDistributionChart()
}

const initDoctorCharts = () => {
  initGradeDistributionChart()
  initScoreDistributionChart()
}

const initDepartmentRankingChart = () => {
  if (!departmentRankingChartRef.value) return
  
  if (departmentRankingChart) {
    departmentRankingChart.dispose()
  }
  
  departmentRankingChart = echarts.init(departmentRankingChartRef.value)
  updateRankingChart()
}

const updateRankingChart = () => {
  if (!departmentRankingChart) return
  
  const data = departments.value.map(dept => ({
    name: dept.department_name,
    value: dept[rankingMetric.value]
  })).sort((a, b) => b.value - a.value)

  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' }
    },
    xAxis: {
      type: 'category',
      data: data.map(item => item.name)
    },
    yAxis: {
      type: 'value'
    },
    series: [{
      name: rankingMetric.value,
      type: 'bar',
      data: data.map(item => item.value),
      itemStyle: {
        color: '#1890ff'
      }
    }]
  }
  
  departmentRankingChart.setOption(option)
}

const initRiskDistributionChart = () => {
  if (!riskDistributionChartRef.value) return
  
  if (riskDistributionChart) {
    riskDistributionChart.dispose()
  }
  
  riskDistributionChart = echarts.init(riskDistributionChartRef.value)
  
  const riskCounts = departments.value.reduce((acc, dept) => {
    acc[dept.risk_level] = (acc[dept.risk_level] || 0) + 1
    return acc
  }, {})

  const option = {
    tooltip: {
      trigger: 'item'
    },
    series: [{
      name: '风险分布',
      type: 'pie',
      radius: '70%',
      data: [
        { value: riskCounts.high || 0, name: '高风险', itemStyle: { color: '#ff4d4f' } },
        { value: riskCounts.medium || 0, name: '中风险', itemStyle: { color: '#faad14' } },
        { value: riskCounts.low || 0, name: '低风险', itemStyle: { color: '#52c41a' } }
      ]
    }]
  }
  
  riskDistributionChart.setOption(option)
}

const initGradeDistributionChart = () => {
  if (!gradeDistributionChartRef.value) return
  
  if (gradeDistributionChart) {
    gradeDistributionChart.dispose()
  }
  
  gradeDistributionChart = echarts.init(gradeDistributionChartRef.value)
  
  const option = {
    tooltip: {
      trigger: 'item'
    },
    series: [{
      name: '绩效等级',
      type: 'pie',
      radius: '70%',
      data: [
        { value: doctorSummary.value.grade_distribution.A, name: 'A级', itemStyle: { color: '#722ed1' } },
        { value: doctorSummary.value.grade_distribution.B, name: 'B级', itemStyle: { color: '#1890ff' } },
        { value: doctorSummary.value.grade_distribution.C, name: 'C级', itemStyle: { color: '#faad14' } },
        { value: doctorSummary.value.grade_distribution.D, name: 'D级', itemStyle: { color: '#ff4d4f' } }
      ]
    }]
  }
  
  gradeDistributionChart.setOption(option)
}

const initScoreDistributionChart = () => {
  if (!scoreDistributionChartRef.value) return
  
  if (scoreDistributionChart) {
    scoreDistributionChart.dispose()
  }
  
  scoreDistributionChart = echarts.init(scoreDistributionChartRef.value)
  
  // 模拟评分分布数据
  const scoreRanges = ['0-60', '60-70', '70-80', '80-90', '90-100']
  const scoreCounts = [0, 0, 0, 1, 1] // 根据实际数据计算

  const option = {
    tooltip: {
      trigger: 'axis'
    },
    xAxis: {
      type: 'category',
      data: scoreRanges
    },
    yAxis: {
      type: 'value'
    },
    series: [{
      name: '医生数量',
      type: 'bar',
      data: scoreCounts,
      itemStyle: {
        color: '#52c41a'
      }
    }]
  }
  
  scoreDistributionChart.setOption(option)
}

// 工具函数
const getRiskColor = (level: string) => {
  const colors = {
    high: 'red',
    medium: 'orange',
    low: 'green'
  }
  return colors[level] || 'default'
}

const getRiskText = (level: string) => {
  const texts = {
    high: '高风险',
    medium: '中风险',
    low: '低风险'
  }
  return texts[level] || level
}

const getGradeColor = (grade: string) => {
  const colors = {
    A: 'purple',
    B: 'blue',
    C: 'orange',
    D: 'red'
  }
  return colors[grade] || 'default'
}

const getScoreColor = (score: number) => {
  if (score >= 90) return '#52c41a'
  if (score >= 80) return '#1890ff'
  if (score >= 70) return '#faad14'
  return '#ff4d4f'
}

const getTrendClass = (trend: string) => {
  return {
    'trend-increasing': trend === 'increasing',
    'trend-decreasing': trend === 'decreasing',
    'trend-stable': trend === 'stable'
  }
}

const getTrendIcon = (trend: string) => {
  const icons = {
    increasing: ArrowUpOutlined,
    decreasing: ArrowDownOutlined,
    stable: MinusOutlined
  }
  return icons[trend] || MinusOutlined
}

const getTrendText = (trend: string) => {
  const texts = {
    increasing: '上升',
    decreasing: '下降',
    stable: '平稳'
  }
  return texts[trend] || trend
}

// 事件处理
const onTabChange = (key: string) => {
  activeTab.value = key
  refreshData()
}

const filterDepartments = () => {
  // 过滤逻辑已在计算属性中实现
}

const filterDoctors = () => {
  // 过滤逻辑已在计算属性中实现
}

const viewDepartmentDetail = (department: any) => {
  selectedDepartmentDetail.value = department
  departmentDetailVisible.value = true
  
  nextTick(() => {
    if (departmentDetailChartRef.value) {
      if (departmentDetailChart) {
        departmentDetailChart.dispose()
      }
      
      departmentDetailChart = echarts.init(departmentDetailChartRef.value)
      
      const option = {
        tooltip: {
          trigger: 'item'
        },
        series: [{
          name: '违规类型',
          type: 'pie',
          radius: '60%',
          data: [
            { value: department.severity_breakdown?.block || 0, name: '阻断', itemStyle: { color: '#ff4d4f' } },
            { value: department.severity_breakdown?.warn || 0, name: '警告', itemStyle: { color: '#faad14' } },
            { value: department.severity_breakdown?.info || 0, name: '提醒', itemStyle: { color: '#1890ff' } }
          ]
        }]
      }
      
      departmentDetailChart.setOption(option)
    }
  })
}

const viewDoctorProfile = (doctor: any) => {
  selectedDoctorProfile.value = doctor
  doctorProfileVisible.value = true
}

const exportDepartmentReport = (department: any) => {
  message.info(`正在导出 ${department.department_name} 的报告...`)
}

const exportDoctorReport = (doctor: any) => {
  message.info(`正在导出 ${doctor.doctor_name} 的档案...`)
}

const exportReports = () => {
  exporting.value = true
  setTimeout(() => {
    message.success('批量导出完成')
    exporting.value = false
  }, 2000)
}

const renderDoctorDetail = (record: any) => {
  return `
    <div style="padding: 16px; background: #fafafa;">
      <p><strong>规则类型分布:</strong> ${Object.entries(record.rule_types || {}).map(([type, count]) => `${type}: ${count}`).join(', ')}</p>
      <p><strong>严重程度分布:</strong> 阻断: ${record.severity_breakdown?.block || 0}, 警告: ${record.severity_breakdown?.warn || 0}, 提醒: ${record.severity_breakdown?.info || 0}</p>
    </div>
  `
}

// 生命周期
onMounted(() => {
  refreshData()
  
  // 监听窗口大小变化
  window.addEventListener('resize', () => {
    departmentRankingChart?.resize()
    riskDistributionChart?.resize()
    gradeDistributionChart?.resize()
    scoreDistributionChart?.resize()
    departmentDetailChart?.resize()
  })
})
</script>

<style scoped>
.department-doctor-reports {
  padding: 24px;
  background: #f5f5f5;
  min-height: 100vh;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  padding: 24px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.header-content h1 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: #262626;
}

.header-content p {
  margin: 4px 0 0 0;
  color: #8c8c8c;
}

.overview-metrics {
  margin-bottom: 24px;
}

.metric-card {
  border-radius: 8px;
  transition: all 0.3s ease;
}

.metric-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.ranking-card,
.risk-distribution-card,
.grade-distribution-card,
.score-distribution-card,
.departments-table-card,
.doctors-table-card {
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  margin-bottom: 24px;
}

.chart-container {
  height: 300px;
  width: 100%;
}

.chart-container.small {
  height: 200px;
}

.risk-legend {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.legend-color {
  width: 12px;
  height: 12px;
  border-radius: 2px;
}

.legend-color.high-risk {
  background: #ff4d4f;
}

.legend-color.medium-risk {
  background: #faad14;
}

.legend-color.low-risk {
  background: #52c41a;
}

.trend-increasing {
  color: #ff4d4f;
}

.trend-decreasing {
  color: #52c41a;
}

.trend-stable {
  color: #1890ff;
}

.department-detail,
.doctor-profile {
  padding: 16px 0;
}

.detail-charts,
.top-rules,
.improvement-suggestions {
  margin-top: 24px;
}

.detail-charts h4,
.top-rules h4,
.improvement-suggestions h4 {
  margin-bottom: 16px;
  color: #262626;
  font-weight: 600;
}
</style>
