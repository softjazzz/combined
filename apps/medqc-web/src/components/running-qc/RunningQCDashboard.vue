<template>
  <div class="running-qc-dashboard">
    <a-row :gutter="24">
      <!-- 左侧：在院病人列表 -->
      <a-col :span="16">
        <a-card title="在院病人运行质控" class="mb-4">
          <template #extra>
            <a-space>
              <a-select
                v-model:value="selectedDepartment"
                placeholder="选择科室"
                style="width: 150px"
                @change="filterPatients"
              >
                <a-select-option value="">全部科室</a-select-option>
                <a-select-option v-for="dept in departments" :key="dept" :value="dept">
                  {{ dept }}
                </a-select-option>
              </a-select>
              
              <a-button type="primary" @click="refreshPatients">
                <template #icon>
                  <ReloadOutlined />
                </template>
                刷新
              </a-button>
            </a-space>
          </template>
          
          <!-- 患者列表 -->
          <a-table
            :columns="patientColumns"
            :data-source="filteredPatients"
            :loading="loading"
            :pagination="{ pageSize: 10 }"
            row-key="id"
            size="middle"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'riskLevel'">
                <a-tag :color="getRiskColor(record.riskLevel)">
                  {{ getRiskText(record.riskLevel) }}
                </a-tag>
              </template>
              
              <template v-if="column.key === 'grade'">
                <a-tag :color="getGradeColor(record.grade)">
                  {{ record.grade }}
                </a-tag>
              </template>
              
              <template v-if="column.key === 'daysSinceAdmission'">
                <a-tag :color="getDaysColor(record.daysSinceAdmission)">
                  第{{ record.daysSinceAdmission }}天
                </a-tag>
              </template>
              
              <template v-if="column.key === 'actions'">
                <a-space>
                  <a-button 
                    type="primary" 
                    size="small" 
                    @click="analyzePatient(record)"
                    :loading="analyzingPatients.includes(record.id)"
                  >
                    质控分析
                  </a-button>
                  <a-button 
                    size="small" 
                    @click="viewDetails(record)"
                  >
                    查看详情
                  </a-button>
                </a-space>
              </template>
            </template>
          </a-table>
        </a-card>
      </a-col>
      
      <!-- 右侧：实时统计 -->
      <a-col :span="8">
        <a-card title="实时统计" class="mb-4">
          <a-row :gutter="16">
            <a-col :span="12">
              <a-statistic
                title="在院病人"
                :value="statistics.totalPatients"
                :prefix="h(UserOutlined)"
                style="text-align: center"
              />
            </a-col>
            <a-col :span="12">
              <a-statistic
                title="高风险病人"
                :value="statistics.highRiskPatients"
                :prefix="h(ExclamationCircleOutlined)"
                style="text-align: center"
                :value-style="{ color: '#ff4d4f' }"
              />
            </a-col>
          </a-row>
        </a-card>
        
        <!-- 风险分布 -->
        <a-card title="风险分布" class="mb-4">
          <div ref="riskChartRef" style="height: 200px;"></div>
        </a-card>
        
        <!-- 科室分布 -->
        <a-card title="科室分布" class="mb-4">
          <div ref="departmentChartRef" style="height: 200px;"></div>
        </a-card>
        
        <!-- 近期提醒 -->
        <a-card title="近期提醒" class="mb-4">
          <a-list
            :data-source="recentAlerts"
            size="small"
            :locale="{ emptyText: '暂无提醒' }"
          >
            <template #renderItem="{ item }">
              <a-list-item>
                <a-list-item-meta>
                  <template #title>
                    <a-space>
                      <a-tag :color="getAlertColor(item.level)">
                        {{ item.level }}
                      </a-tag>
                      <span>{{ item.patientName }}</span>
                    </a-space>
                  </template>
                  <template #description>
                    {{ item.message }}
                  </template>
                </a-list-item-meta>
                <template #actions>
                  <a @click="handleAlert(item)">处理</a>
                </template>
              </a-list-item>
            </template>
          </a-list>
        </a-card>
      </a-col>
    </a-row>
    
    <!-- 质控分析结果弹窗 -->
    <a-modal
      v-model:open="analysisModalVisible"
      title="运行病历质控分析结果"
      width="80%"
      :footer="null"
    >
      <running-qc-result
        v-if="currentAnalysisResult"
        :result="currentAnalysisResult"
        @close="analysisModalVisible = false"
      />
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, h } from 'vue'
import { message } from 'ant-design-vue'
import { 
  ReloadOutlined, 
  UserOutlined, 
  ExclamationCircleOutlined 
} from '@ant-design/icons-vue'
import * as echarts from 'echarts'
import { runningQCService } from '../../lib/running-qc-service'
import type { RunningQCResult as RunningQCResultType } from '../../lib/running-qc-service'
import RunningQCResult from './RunningQCResult.vue'

// 在院病人接口
interface InpatientRecord {
  id: string
  patientName: string
  patientAge: number
  patientGender: 'M' | 'F' | 'U'
  department: string
  admissionDate: string
  daysSinceAdmission: number
  riskLevel: 'low' | 'medium' | 'high' | 'critical'
  grade: '甲级' | '乙级' | '丙级'
  lastQCTime?: string
  nextCheckTime?: string
  doctorId: string
  doctorName: string
}

// 提醒接口
interface Alert {
  id: string
  patientId: string
  patientName: string
  level: 'low' | 'medium' | 'high' | 'critical'
  message: string
  time: string
}

// 响应式数据
const loading = ref(false)
const selectedDepartment = ref('')
const analyzingPatients = ref<string[]>([])
const analysisModalVisible = ref(false)
const currentAnalysisResult = ref<RunningQCResultType | null>(null)

// 数据
const patients = ref<InpatientRecord[]>([])
const filteredPatients = ref<InpatientRecord[]>([])
const departments = ref<string[]>([])
const recentAlerts = ref<Alert[]>([])

// 统计数据
const statistics = reactive({
  totalPatients: 0,
  highRiskPatients: 0,
  criticalPatients: 0,
  overduePatients: 0
})

// 图表引用
const riskChartRef = ref<HTMLElement>()
const departmentChartRef = ref<HTMLElement>()

// 表格列定义
const patientColumns = [
  {
    title: '患者姓名',
    dataIndex: 'patientName',
    key: 'patientName',
    width: 100
  },
  {
    title: '科室',
    dataIndex: 'department',
    key: 'department',
    width: 100
  },
  {
    title: '入院天数',
    key: 'daysSinceAdmission',
    width: 80
  },
  {
    title: '风险等级',
    key: 'riskLevel',
    width: 80
  },
  {
    title: '质控等级',
    key: 'grade',
    width: 80
  },
  {
    title: '主治医生',
    dataIndex: 'doctorName',
    key: 'doctorName',
    width: 100
  },
  {
    title: '操作',
    key: 'actions',
    width: 150
  }
]

// 组件挂载
onMounted(async () => {
  await loadInpatients()
  initCharts()
  
  // 设置定时刷新
  setInterval(refreshPatients, 5 * 60 * 1000) // 每5分钟刷新
})

// 加载在院病人数据
const loadInpatients = async () => {
  loading.value = true
  try {
    // 模拟数据，实际应该从API获取
    const mockPatients: InpatientRecord[] = [
      {
        id: '1',
        patientName: '张三',
        patientAge: 45,
        patientGender: 'M',
        department: '内一科',
        admissionDate: '2024-01-15T10:00:00Z',
        daysSinceAdmission: 3,
        riskLevel: 'medium',
        grade: '乙级',
        lastQCTime: '2024-01-18T09:00:00Z',
        nextCheckTime: '2024-01-18T21:00:00Z',
        doctorId: 'doctor1',
        doctorName: '李医生'
      },
      {
        id: '2',
        patientName: '李四',
        patientAge: 32,
        patientGender: 'F',
        department: '外三科',
        admissionDate: '2024-01-16T14:00:00Z',
        daysSinceAdmission: 2,
        riskLevel: 'high',
        grade: '丙级',
        lastQCTime: '2024-01-17T16:00:00Z',
        nextCheckTime: '2024-01-18T22:00:00Z',
        doctorId: 'doctor2',
        doctorName: '王医生'
      },
      {
        id: '3',
        patientName: '王五',
        patientAge: 58,
        patientGender: 'M',
        department: '内一科',
        admissionDate: '2024-01-17T08:00:00Z',
        daysSinceAdmission: 1,
        riskLevel: 'low',
        grade: '甲级',
        lastQCTime: '2024-01-18T10:00:00Z',
        nextCheckTime: '2024-01-19T10:00:00Z',
        doctorId: 'doctor1',
        doctorName: '李医生'
      }
    ]
    
    patients.value = mockPatients
    filteredPatients.value = mockPatients
    
    // 提取科室列表
    departments.value = [...new Set(mockPatients.map(p => p.department))]
    
    // 更新统计数据
    updateStatistics()
    
    // 加载提醒数据
    await loadRecentAlerts()
    
  } catch (error) {
    console.error('加载在院病人数据失败:', error)
    message.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

// 刷新患者数据
const refreshPatients = async () => {
  await loadInpatients()
  message.success('数据已刷新')
}

// 过滤患者
const filterPatients = () => {
  if (!selectedDepartment.value) {
    filteredPatients.value = patients.value
  } else {
    filteredPatients.value = patients.value.filter(p => p.department === selectedDepartment.value)
  }
}

// 分析患者
const analyzePatient = async (patient: InpatientRecord) => {
  analyzingPatients.value.push(patient.id)
  
  try {
    const result = await runningQCService.analyzeRunningRecord({
      recordId: `running-${patient.id}`,
      patientId: patient.id,
      content: `患者：${patient.patientName}，科室：${patient.department}，入院日期：${patient.admissionDate}`,
      department: patient.department,
      admissionDate: patient.admissionDate,
      currentDate: new Date().toISOString(),
      doctorId: patient.doctorId,
      analysisType: 'real-time'
    })
    
    currentAnalysisResult.value = result
    analysisModalVisible.value = true
    
    // 更新患者状态
    const patientIndex = patients.value.findIndex(p => p.id === patient.id)
    if (patientIndex !== -1) {
      patients.value[patientIndex].riskLevel = result.summary.riskLevel
      patients.value[patientIndex].grade = result.summary.grade
      patients.value[patientIndex].lastQCTime = result.analysisTime
      patients.value[patientIndex].nextCheckTime = result.nextCheckTime
    }
    
    message.success('质控分析完成')
  } catch (error) {
    console.error('质控分析失败:', error)
    message.error('质控分析失败')
  } finally {
    analyzingPatients.value = analyzingPatients.value.filter(id => id !== patient.id)
  }
}

// 查看详情
const viewDetails = (patient: InpatientRecord) => {
  // 跳转到患者详情页面
  console.log('查看患者详情:', patient)
}

// 加载近期提醒
const loadRecentAlerts = async () => {
  // 模拟提醒数据
  recentAlerts.value = [
    {
      id: '1',
      patientId: '2',
      patientName: '李四',
      level: 'high',
      message: '入院记录超时24小时未完成',
      time: '2024-01-18T10:30:00Z'
    },
    {
      id: '2',
      patientId: '1',
      patientName: '张三',
      level: 'medium',
      message: '首次病程记录需要完善',
      time: '2024-01-18T11:00:00Z'
    }
  ]
}

// 处理提醒
const handleAlert = (alert: Alert) => {
  console.log('处理提醒:', alert)
  // 实现提醒处理逻辑
}

// 更新统计数据
const updateStatistics = () => {
  statistics.totalPatients = patients.value.length
  statistics.highRiskPatients = patients.value.filter(p => 
    p.riskLevel === 'high' || p.riskLevel === 'critical'
  ).length
  statistics.criticalPatients = patients.value.filter(p => p.riskLevel === 'critical').length
  statistics.overduePatients = patients.value.filter(p => p.daysSinceAdmission > 7).length
}

// 初始化图表
const initCharts = () => {
  // 风险分布图表
  if (riskChartRef.value) {
    const riskChart = echarts.init(riskChartRef.value)
    const riskData = [
      { name: '低风险', value: patients.value.filter(p => p.riskLevel === 'low').length },
      { name: '中风险', value: patients.value.filter(p => p.riskLevel === 'medium').length },
      { name: '高风险', value: patients.value.filter(p => p.riskLevel === 'high').length },
      { name: '严重风险', value: patients.value.filter(p => p.riskLevel === 'critical').length }
    ]
    
    riskChart.setOption({
      tooltip: { trigger: 'item' }, series: [{
        type: 'pie', radius: '60%', data: riskData, itemStyle: {
          color: (params: any) => {
            const colors = ['#52c41a', '#faad14', '#ff7875', '#ff4d4f']
            return colors[params.dataIndex]
          }
        }
      }]
    })
  }
  
  // 科室分布图表
  if (departmentChartRef.value) {
    const deptChart = echarts.init(departmentChartRef.value)
    const deptData = departments.value.map(dept => ({
      name: dept,
      value: patients.value.filter(p => p.department === dept).length
    }))
    
    deptChart.setOption({
      tooltip: { trigger: 'item' },
      series: [{
        type: 'pie',
        radius: '60%',
        data: deptData
      }]
    })
  }
}

// 辅助函数
const getRiskColor = (level: string) => {
  switch (level) {
    case 'low': return 'green'
    case 'medium': return 'orange'
    case 'high': return 'red'
    case 'critical': return 'red'
    default: return 'default'
  }
}

const getRiskText = (level: string) => {
  switch (level) {
    case 'low': return '低风险'
    case 'medium': return '中风险'
    case 'high': return '高风险'
    case 'critical': return '严重风险'
    default: return '未知'
  }
}

const getGradeColor = (grade: string) => {
  switch (grade) {
    case '甲级': return 'green'
    case '乙级': return 'orange'
    case '丙级': return 'red'
    default: return 'default'
  }
}

const getDaysColor = (days: number) => {
  if (days <= 3) return 'green'
  if (days <= 7) return 'orange'
  return 'red'
}

const getAlertColor = (level: string) => {
  switch (level) {
    case 'low': return 'default'
    case 'medium': return 'orange'
    case 'high': return 'red'
    case 'critical': return 'red'
    default: return 'default'
  }
}
</script>

<style scoped>
.running-qc-dashboard {
  padding: 24px;
}

.ant-statistic {
  margin-bottom: 16px;
}

.ant-list-item {
  padding: 8px 0;
}
</style> 