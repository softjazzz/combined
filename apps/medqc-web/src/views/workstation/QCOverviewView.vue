<template>
  <div class="qc-overview">
    <!-- 头部统计 -->
    <div class="overview-header">
      <h2>
        <AlertOutlined />
        质控消息概览
      </h2>
      <div class="header-actions">
        <a-range-picker v-model:value="dateRange" style="width: 260px" />
        <a-button @click="refreshData">
          <ReloadOutlined />
          刷新
        </a-button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="stat-cards">
      <div class="stat-card" v-for="stat in summaryStats" :key="stat.label">
        <div class="stat-icon" :style="{ background: stat.bg }">
          <component :is="stat.icon" :style="{ color: stat.color, fontSize: '24px' }" />
        </div>
        <div class="stat-info">
          <div class="stat-value">{{ stat.value }}</div>
          <div class="stat-label">{{ stat.label }}</div>
        </div>
        <div class="stat-trend" :class="stat.trend > 0 ? 'up' : 'down'">
          {{ stat.trend > 0 ? '↑' : '↓' }} {{ Math.abs(stat.trend) }}%
        </div>
      </div>
    </div>

    <!-- 主体区域 -->
    <div class="overview-body">
      <!-- 左侧：消息列表 -->
      <div class="msg-panel">
        <div class="msg-header">
          <a-segmented v-model:value="messageTab" :options="messageTabs" size="small" />
          <a-badge :count="unreadCount" :offset="[-8, -4]">
            <a-button size="small" type="link" @click="markAllRead">全部已读</a-button>
          </a-badge>
        </div>
        <div class="msg-list">
          <div
            v-for="msg in filteredMessages"
            :key="msg.id"
            class="msg-item"
            :class="{ unread: !msg.read, active: selectedMsg?.id === msg.id }"
            @click="selectMessage(msg)"
          >
            <div class="msg-dot" v-if="!msg.read"></div>
            <div class="msg-content">
              <div class="msg-title">
                <a-tag :color="severityColor(msg.severity)" size="small">{{ severityLabel(msg.severity) }}</a-tag>
                <span>{{ msg.title }}</span>
              </div>
              <div class="msg-meta">
                {{ msg.deptName }} · {{ msg.patientName }} · {{ msg.time }}
              </div>
            </div>
          </div>
          <div v-if="filteredMessages.length === 0" class="msg-empty">
            <CheckCircleOutlined style="font-size: 40px; color: #52c41a" />
            <p>暂无质控消息</p>
          </div>
        </div>
      </div>

      <!-- 右侧：消息详情 -->
      <div class="detail-panel">
        <template v-if="selectedMsg">
          <div class="detail-header">
            <h3>{{ selectedMsg.title }}</h3>
            <a-tag :color="severityColor(selectedMsg.severity)">{{ severityLabel(selectedMsg.severity) }}</a-tag>
          </div>
          <a-descriptions bordered size="small" :column="2" class="detail-info">
            <a-descriptions-item label="患者">{{ selectedMsg.patientName }}</a-descriptions-item>
            <a-descriptions-item label="住院号">{{ selectedMsg.inpatNo }}</a-descriptions-item>
            <a-descriptions-item label="科室">{{ selectedMsg.deptName }}</a-descriptions-item>
            <a-descriptions-item label="发现时间">{{ selectedMsg.time }}</a-descriptions-item>
            <a-descriptions-item label="规则编号">{{ selectedMsg.ruleId }}</a-descriptions-item>
            <a-descriptions-item label="扣分">
              <span style="color: #ff4d4f; font-weight: 600">-{{ selectedMsg.deduction }}分</span>
            </a-descriptions-item>
          </a-descriptions>
          <div class="detail-body">
            <h4>问题描述</h4>
            <p>{{ selectedMsg.description }}</p>
            <h4>整改建议</h4>
            <p>{{ selectedMsg.suggestion }}</p>
          </div>
          <div class="detail-actions">
            <a-button type="primary" @click="goToRecord(selectedMsg)">
              <FileSearchOutlined />
              查看病历
            </a-button>
            <a-button @click="dismissMsg(selectedMsg)">
              标记已处理
            </a-button>
          </div>
        </template>
        <template v-else>
          <div class="detail-empty">
            <BellOutlined style="font-size: 48px; color: #d9d9d9" />
            <p>选择一条消息查看详情</p>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  AlertOutlined,
  ReloadOutlined,
  CheckCircleOutlined,
  FileSearchOutlined,
  BellOutlined,
  WarningOutlined,
  CloseCircleOutlined,
  ExclamationCircleOutlined,
  FileTextOutlined,
} from '@ant-design/icons-vue'

const router = useRouter()
const dateRange = ref<any>(null)

// ==================== Mock 数据 ====================
interface QCMessage {
  id: string
  title: string
  severity: 'error' | 'warning' | 'info'
  deptName: string
  patientName: string
  inpatNo: string
  time: string
  ruleId: string
  deduction: number
  description: string
  suggestion: string
  read: boolean
  category: string
}

const messages = ref<QCMessage[]>([
  {
    id: '1', title: '出院记录缺失', severity: 'error', deptName: '呼吸内科', patientName: '王建国',
    inpatNo: 'ZY2025001789', time: '2025-02-28 14:30', ruleId: 'F003', deduction: 5,
    description: '患者王建国（ZY2025001789）已在院 18 天，但出院记录仍未完成。根据《病历书写基本规范》第二十二条，出院记录应在出院后 24 小时内完成。',
    suggestion: '请主管医生尽快完成出院记录的书写。如患者尚处于住院状态，请核实出院日期是否已正确录入。',
    read: false, category: 'completeness'
  },
  {
    id: '2', title: '入院诊断与出院诊断不一致', severity: 'warning', deptName: '心内科', patientName: '张三丰',
    inpatNo: 'ZY2025001234', time: '2025-02-28 10:15', ruleId: 'F006', deduction: 3,
    description: '入院诊断"急性前壁ST段抬高型心肌梗死 Killip II级"与出院诊断"冠心病 急性前壁ST段抬高型心肌梗死 PCI术后 Killip II级"存在差异，需确认修改诊断的记录是否在病程中有充分记载。',
    suggestion: '请在病程记录中补充诊断变更说明，说明修改诊断的依据和时间。',
    read: false, category: 'logic'
  },
  {
    id: '3', title: '手术记录时限预警', severity: 'warning', deptName: '骨科', patientName: '陈志强',
    inpatNo: 'ZY2025002234', time: '2025-02-27 09:00', ruleId: 'F005', deduction: 0,
    description: '患者陈志强拟行人工股骨头置换术，术前讨论已完成。请在术后 24 小时内完成手术记录。',
    suggestion: '术后及时在系统中录入手术记录，包括手术方式、术中情况、出血量等。',
    read: true, category: 'timelimit'
  },
  {
    id: '4', title: '首页主诉超出 20 字限制', severity: 'info', deptName: '产科', patientName: '赵敏慧',
    inpatNo: 'ZY2025002001', time: '2025-02-26 16:00', ruleId: 'F002', deduction: 1,
    description: '病案首页"主诉"字段为"停经39+2周，要求入院待产"，实际字数为 14 字，符合要求。但入院记录中主诉描述较为简略，建议补充更多临床信息。',
    suggestion: '主诉已符合规范，仅建议入院记录中可适当丰富主诉相关的现病史描述。',
    read: true, category: 'format'
  },
  {
    id: '5', title: '诊断编码缺失', severity: 'error', deptName: '普外科', patientName: '李秀英',
    inpatNo: 'ZY2025001456', time: '2025-02-26 11:20', ruleId: 'C001', deduction: 5,
    description: '主要诊断"急性化脓性阑尾炎"对应的 ICD-10 编码未填写。出院诊断 ICD 编码是病案首页的必填项。',
    suggestion: '请在病案首页中填写主要诊断 ICD-10 编码 K35.8（急性阑尾炎，其他和未特指的）。',
    read: false, category: 'coding'
  },
  {
    id: '6', title: '住院超 15 天预警', severity: 'warning', deptName: '呼吸内科', patientName: '王建国',
    inpatNo: 'ZY2025001789', time: '2025-02-25 08:00', ruleId: 'D001', deduction: 0,
    description: '患者王建国入院已满 15 天（入院日期 2025-02-10），社区获得性肺炎（重症）的平均住院日参考值为 10-14 天，当前住院天数已超出参考值。',
    suggestion: '请主管医师评估患者当前病情，若可出院请及时办理出院手续；若需继续住院，请在病程中记录延长住院的医学依据。',
    read: true, category: 'drg'
  },
])

const selectedMsg = ref<QCMessage | null>(null)
const messageTab = ref('all')
const messageTabs = [
  { label: '全部', value: 'all' },
  { label: '错误', value: 'error' },
  { label: '警告', value: 'warning' },
  { label: '提示', value: 'info' },
]

// ==================== 计算属性 ====================
const unreadCount = computed(() => messages.value.filter(m => !m.read).length)

const filteredMessages = computed(() => {
  if (messageTab.value === 'all') return messages.value
  return messages.value.filter(m => m.severity === messageTab.value)
})

const summaryStats = computed(() => [
  {
    label: '待处理问题',
    value: messages.value.filter(m => !m.read).length,
    icon: ExclamationCircleOutlined,
    color: '#ff4d4f',
    bg: '#fff2f0',
    trend: 12,
  },
  {
    label: '今日新增',
    value: 2,
    icon: AlertOutlined,
    color: '#faad14',
    bg: '#fffbe6',
    trend: -8,
  },
  {
    label: '本周已处理',
    value: 15,
    icon: CheckCircleOutlined,
    color: '#52c41a',
    bg: '#f6ffed',
    trend: 25,
  },
  {
    label: '累计扣分',
    value: messages.value.reduce((s, m) => s + m.deduction, 0),
    icon: FileTextOutlined,
    color: '#1677ff',
    bg: '#e6f4ff',
    trend: -3,
  },
])

// ==================== 方法 ====================
function severityColor(s: string) {
  return s === 'error' ? 'red' : s === 'warning' ? 'orange' : 'blue'
}

function severityLabel(s: string) {
  return s === 'error' ? '错误' : s === 'warning' ? '警告' : '提示'
}

function selectMessage(msg: QCMessage) {
  selectedMsg.value = msg
  msg.read = true
}

function markAllRead() {
  messages.value.forEach(m => m.read = true)
}

function goToRecord(msg: QCMessage) {
  router.push('/dashboard/workstation')
}

function dismissMsg(msg: QCMessage) {
  msg.read = true
  selectedMsg.value = null
}

function refreshData() {
  // TODO: 刷新数据
}
</script>

<style scoped>
.qc-overview {
  padding: 20px 24px;
  max-width: 1400px;
  margin: 0 auto;
}

.overview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.overview-header h2 {
  margin: 0;
  font-size: 20px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-actions {
  display: flex;
  gap: 8px;
}

/* 统计卡片 */
.stat-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

.stat-card {
  background: #fff;
  border-radius: 12px;
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
  transition: transform 0.2s;
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.08);
}

.stat-icon {
  width: 52px;
  height: 52px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #1a1a1a;
  line-height: 1;
}

.stat-label {
  font-size: 13px;
  color: #888;
  margin-top: 4px;
}

.stat-trend {
  margin-left: auto;
  font-size: 12px;
  font-weight: 500;
  padding: 2px 8px;
  border-radius: 10px;
}

.stat-trend.up {
  color: #ff4d4f;
  background: #fff2f0;
}

.stat-trend.down {
  color: #52c41a;
  background: #f6ffed;
}

/* 主体 */
.overview-body {
  display: flex;
  gap: 16px;
  background: #fff;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
  min-height: 500px;
}

.msg-panel {
  width: 420px;
  border-right: 1px solid #f0f0f0;
  display: flex;
  flex-direction: column;
}

.msg-header {
  padding: 12px 16px;
  border-bottom: 1px solid #f0f0f0;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.msg-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.msg-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
  margin-bottom: 4px;
}

.msg-item:hover {
  background: #f5f5ff;
}

.msg-item.active {
  background: #e6f4ff;
}

.msg-item.unread {
  background: #fafafa;
}

.msg-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #1677ff;
  margin-top: 6px;
  flex-shrink: 0;
}

.msg-content {
  flex: 1;
  min-width: 0;
}

.msg-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 500;
  color: #1a1a1a;
}

.msg-meta {
  font-size: 11px;
  color: #999;
  margin-top: 4px;
}

.msg-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: #999;
}

.msg-empty p {
  margin-top: 12px;
}

/* 详情 */
.detail-panel {
  flex: 1;
  padding: 20px;
  display: flex;
  flex-direction: column;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.detail-header h3 {
  margin: 0;
  font-size: 16px;
}

.detail-info {
  margin-bottom: 20px;
}

.detail-body h4 {
  font-size: 14px;
  margin: 16px 0 8px;
  color: #1a1a1a;
}

.detail-body p {
  font-size: 13px;
  color: #555;
  line-height: 1.8;
}

.detail-actions {
  margin-top: auto;
  display: flex;
  gap: 8px;
  padding-top: 16px;
  border-top: 1px solid #f0f0f0;
}

.detail-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  color: #999;
}

.detail-empty p {
  margin-top: 12px;
  font-size: 13px;
}
</style>
