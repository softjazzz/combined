<template>
  <div class="diagnosis-surgery-timeline">
    <a-spin :spinning="loading">
      <!-- 诊断时间轴 -->
      <a-card
        size="small"
        title="诊断发生发展时间轴"
        class="timeline-card"
      >
        <template #extra>
          <a-tag color="blue">
            {{ diagnosisTimeline.length }} 个诊断
          </a-tag>
        </template>

        <a-empty
          v-if="diagnosisTimeline.length === 0"
          description="暂无诊断时间轴数据"
        />

        <a-timeline
          v-else
          mode="left"
        >
          <a-timeline-item
            v-for="(diag, idx) in diagnosisTimeline"
            :key="idx"
            :color="getStatusColor(diag.status)"
          >
            <div class="timeline-item-content">
              <div class="diagnosis-header">
                <span class="diagnosis-name">{{ diag.diagnosis_name }}</span>
                <a-tag
                  :color="getStatusColor(diag.status)"
                  size="small"
                >
                  {{ getStatusText(diag.status) }}
                </a-tag>
              </div>

              <div class="diagnosis-meta">
                <span v-if="diag.first_mention_time">
                  <ClockCircleOutlined /> {{ diag.first_mention_time }}
                </span>
                <span
                  v-if="diag.first_mention_source"
                  class="source-tag"
                >
                  <FileTextOutlined /> {{ diag.first_mention_source }}
                </span>
              </div>

              <!-- 事件子时间轴 -->
              <div
                v-if="(diag.timeline_events?.length || 0) > 0"
                class="sub-events"
              >
                <div
                  v-for="(event, eIdx) in diag.timeline_events"
                  :key="eIdx"
                  class="sub-event"
                >
                  <span class="event-time">{{ event.time }}</span>
                  <span class="event-desc">{{ event.event }}</span>
                  <a-tag size="small">
                    {{ event.source }}
                  </a-tag>
                </div>
              </div>
            </div>
          </a-timeline-item>
        </a-timeline>
      </a-card>

      <!-- 手术闭环验证 -->
      <a-card
        size="small"
        title="手术操作闭环验证"
        class="timeline-card mt-3"
      >
        <template #extra>
          <a-tag color="purple">
            {{ surgeryVerification.length }} 个手术
          </a-tag>
        </template>

        <a-empty
          v-if="surgeryVerification.length === 0"
          description="暂无手术记录"
        />

        <a-list
          v-else
          :data-source="surgeryVerification"
          size="small"
        >
          <template #renderItem="{ item }">
            <a-list-item>
              <a-list-item-meta>
                <template #avatar>
                  <a-avatar
                    :style="{ backgroundColor: getVerificationColor(item.verification_status) }"
                    size="small"
                  >
                    <template #icon>
                      <CheckCircleOutlined v-if="item.verification_status === 'verified'" />
                      <WarningOutlined v-else-if="item.verification_status === 'planned_only'" />
                      <ExclamationCircleOutlined v-else />
                    </template>
                  </a-avatar>
                </template>
                <template #title>
                  <span>{{ item.surgery_name }}</span>
                  <a-tag
                    :color="getVerificationColor(item.verification_status)"
                    size="small"
                    class="ml-2"
                  >
                    {{ getVerificationText(item.verification_status) }}
                  </a-tag>
                </template>
                <template #description>
                  <div class="surgery-meta">
                    <span v-if="item.execution_time">
                      <ClockCircleOutlined /> {{ item.execution_time }}
                    </span>
                    <span
                      v-if="item.plan_source"
                      class="source-tag"
                    >
                      计划: {{ item.plan_source }}
                    </span>
                    <span
                      v-if="item.execution_source"
                      class="source-tag"
                    >
                      执行: {{ item.execution_source }}
                    </span>
                  </div>
                </template>
              </a-list-item-meta>
            </a-list-item>
          </template>
        </a-list>
      </a-card>

      <!-- 差异分析 -->
      <a-card
        v-if="discrepancies.length > 0"
        size="small"
        title="首页差异分析"
        class="timeline-card mt-3"
      >
        <template #extra>
          <a-badge
            :count="discrepancies.length"
            :number-style="{ backgroundColor: '#fa8c16' }"
          />
        </template>

        <a-alert
          v-for="(disc, idx) in discrepancies"
          :key="idx"
          :type="disc.severity === 'error' ? 'error' : 'warning'"
          :message="getDiscrepancyTitle(disc)"
          :description="disc.suggestion"
          show-icon
          class="mb-2"
        />
      </a-card>
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import {
  ClockCircleOutlined,
  FileTextOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  WarningOutlined,
} from '@ant-design/icons-vue'

interface TimelineEvent {
  time: string
  event: string
  source: string
}

interface DiagnosisTimeline {
  diagnosis_name: string
  first_mention_time?: string
  first_mention_source?: string
  status: 'suspected' | 'confirmed' | 'ruled_out'
  timeline_events?: TimelineEvent[]
}

interface SurgeryVerification {
  surgery_name: string
  plan_source?: string
  execution_source?: string
  execution_time?: string
  verification_status: 'verified' | 'planned_only' | 'executed_only'
}

interface Discrepancy {
  type: 'missing_in_frontpage' | 'not_supported_by_record' | 'inconsistent'
  item_category: 'diagnosis' | 'procedure'
  item_name: string
  suggestion: string
  severity: 'warning' | 'error'
}

interface Props {
  diagnosisTimeline?: DiagnosisTimeline[]
  surgeryVerification?: SurgeryVerification[]
  discrepancies?: Discrepancy[]
  loading?: boolean
}

withDefaults(defineProps<Props>(), {
  diagnosisTimeline: () => [],
  surgeryVerification: () => [],
  discrepancies: () => [],
  loading: false,
})

const getStatusColor = (status: string) => {
  switch (status) {
    case 'confirmed':
      return 'green'
    case 'suspected':
      return 'orange'
    case 'ruled_out':
      return 'gray'
    default:
      return 'blue'
  }
}

const getStatusText = (status: string) => {
  switch (status) {
    case 'confirmed':
      return '已确诊'
    case 'suspected':
      return '疑诊'
    case 'ruled_out':
      return '已排除'
    default:
      return '未知'
  }
}

const getVerificationColor = (status: string) => {
  switch (status) {
    case 'verified':
      return '#52c41a'
    case 'planned_only':
      return '#faad14'
    case 'executed_only':
      return '#ff4d4f'
    default:
      return '#1890ff'
  }
}

const getVerificationText = (status: string) => {
  switch (status) {
    case 'verified':
      return '验证通过'
    case 'planned_only':
      return '计划未执行'
    case 'executed_only':
      return '无计划记录'
    default:
      return '未知'
  }
}

const getDiscrepancyTitle = (disc: Discrepancy) => {
  const category = disc.item_category === 'diagnosis' ? '诊断' : '手术'
  switch (disc.type) {
    case 'missing_in_frontpage':
      return `${category}漏填：${disc.item_name}`
    case 'not_supported_by_record':
      return `${category}无据：${disc.item_name}`
    case 'inconsistent':
      return `${category}不一致：${disc.item_name}`
    default:
      return disc.item_name
  }
}
</script>

<style scoped>
.diagnosis-surgery-timeline {
  padding: 8px 0;
}
.timeline-card {
  background: #fff;
}
.timeline-item-content {
  padding-bottom: 8px;
}
.diagnosis-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.diagnosis-name {
  font-weight: 500;
  color: #333;
}
.diagnosis-meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #666;
}
.source-tag {
  color: #1890ff;
}
.sub-events {
  margin-top: 8px;
  padding-left: 16px;
  border-left: 2px solid #e8e8e8;
}
.sub-event {
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 4px 0;
  font-size: 12px;
}
.event-time {
  color: #999;
  min-width: 120px;
}
.event-desc {
  flex: 1;
  color: #333;
}
.surgery-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
}
.mt-3 {
  margin-top: 12px;
}
.ml-2 {
  margin-left: 8px;
}
.mb-2 {
  margin-bottom: 8px;
}
</style>
